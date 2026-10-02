// USB_KEY recovery dongle for the M-VAVE FM-1 (JieLi AC791N) on a Raspberry Pi
// Pico. Bit-bangs the JieLi mask-ROM key on the target's USB data lines, senses
// the acknowledge, optionally supplies the 1 ms SOF edges the ROM needs for PLL
// calibration, then hands the bus to the PC. Nothing here writes to the device.
//
// Behaviour is specified in docs/10-usb-key-dongle.md and mirrored by
// dongle/sim/dongle.py, which is tested against a model of the ROM.

#include <stdio.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>

#include "pico/stdlib.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"

#include "config.h"
#include "usb_key.pio.h"

// ---------------------------------------------------------------- state ----
typedef enum { ST_SELFTEST, ST_KEY, ST_ACK, ST_SOF_WAIT_HIGH, ST_SOF_GEN, ST_DONE, ST_FAILED, ST_FAULT } state_t;

static PIO pio = pio0;
static uint sm_key, sm_sof, off_key, off_sof;
static int polarity_mode = DEFAULT_POLARITY_MODE;
static int sof_mode = DEFAULT_SOF_MODE;

static const char *pol_name(int pol) { return pol == POLARITY_DP_CLOCK ? "A(D+clk,D-data)" : "B(D-clk,D+data)"; }
static uint64_t t0;
static void dlog(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void dlog(const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    printf("[%9llu us] ", (unsigned long long)(time_us_64() - t0));
    vprintf(fmt, ap); printf("\n");
    va_end(ap);
}

// ------------------------------------------------------------- hardware ----
static const uint PULLUP_PINS[2] = {PIN_PULLUP_DP, PIN_PULLUP_DM};
static void pullups(bool on) {
    for (int i = 0; i < 2; i++) {
        if (on) { gpio_set_dir(PULLUP_PINS[i], GPIO_OUT); gpio_put(PULLUP_PINS[i], 1); }
        else    { gpio_set_dir(PULLUP_PINS[i], GPIO_IN); }   // hi-Z: pad pulls are disabled in main()
    }
}
static void mux_to_dongle(void) { gpio_put(PIN_MUX_SEL, MUX_SEL_DONGLE); }
static void mux_to_pc(void)     { gpio_put(PIN_MUX_SEL, MUX_SEL_PC); }
static bool dp(void) { return gpio_get(PIN_DP); }
static bool dm(void) { return gpio_get(PIN_DM); }
static bool button_pressed(void) { return !gpio_get(PIN_BUTTON); }
static void led(bool on) { gpio_put(PICO_DEFAULT_LED_PIN, on); }

static void lines_release(void) {
    // Both PIO state machines off, pins back to plain inputs (released).
    pio_sm_set_enabled(pio, sm_key, false);
    pio_sm_set_enabled(pio, sm_sof, false);
    gpio_set_function(PIN_DP, GPIO_FUNC_SIO); gpio_set_dir(PIN_DP, GPIO_IN);
    gpio_set_function(PIN_DM, GPIO_FUNC_SIO); gpio_set_dir(PIN_DM, GPIO_IN);
}

// Configure the key state machine for one polarity: SET pin = clock, OUT pin = data.
static void key_start(int pol) {
    uint clock_pin = (pol == POLARITY_DP_CLOCK) ? PIN_DP : PIN_DM;
    uint data_pin  = (pol == POLARITY_DP_CLOCK) ? PIN_DM : PIN_DP;
    pio_sm_set_enabled(pio, sm_key, false);
    pio_gpio_init(pio, PIN_DP);
    pio_gpio_init(pio, PIN_DM);
    pio_sm_config c = usb_key_program_get_default_config(off_key);
    sm_config_set_set_pins(&c, clock_pin, 1);
    sm_config_set_out_pins(&c, data_pin, 1);
    sm_config_set_out_shift(&c, false /* shift left = MSB first */, false /* no autopull */, KEY_BITS);
    sm_config_set_clkdiv(&c, (float)clock_get_hz(clk_sys) / (float)KEY_PIO_HZ);
    pio_sm_init(pio, sm_key, off_key, &c);
    uint32_t mask = (1u << PIN_DP) | (1u << PIN_DM);
    pio_sm_set_pins_with_mask(pio, sm_key, 0, mask);      // output value latched at 0 ...
    pio_sm_set_pindirs_with_mask(pio, sm_key, 0, mask);   // ... and both lines released
    pio_sm_clear_fifos(pio, sm_key);
    pio_sm_set_enabled(pio, sm_key, true);
}

static void key_send_packet(void) {
    uint32_t word = ((uint32_t)(~USB_KEY_WORD) & 0xFFFFu) << 16;   // inverted, top 16 bits
    pio_sm_put_blocking(pio, sm_key, word);
    sleep_us(KEY_PACKET_US);                                       // the SM is now stalled on "pull block"
}

static void sof_start(void) {
    pio_gpio_init(pio, PIN_DP);
    pio_sm_config c = sof_pulse_program_get_default_config(off_sof);
    sm_config_set_set_pins(&c, PIN_DP, 1);
    sm_config_set_clkdiv(&c, (float)clock_get_hz(clk_sys) / (float)SOF_PIO_HZ);
    pio_sm_init(pio, sm_sof, off_sof, &c);
    pio_sm_set_pins_with_mask(pio, sm_sof, 0, 1u << PIN_DP);
    pio_sm_set_pindirs_with_mask(pio, sm_sof, 0, 1u << PIN_DP);
    pio_sm_set_enabled(pio, sm_sof, true);
}

// Sample both lines during the inter-packet gap. Returns true on an acknowledge
// (both lines low for at least ACK_MIN_LOW_US while we drive nothing).
static bool gap_sense_ack(void) {
    int low_us = 0;
    for (int elapsed = 0; elapsed < KEY_GAP_US; elapsed += ACK_SAMPLE_US) {
        if (!dp() && !dm()) { low_us += ACK_SAMPLE_US; if (low_us >= ACK_MIN_LOW_US) return true; }
        else low_us = 0;
        sleep_us(ACK_SAMPLE_US);
    }
    return false;
}

static bool wait_lines(bool want_dp, bool want_dm, uint32_t timeout_ms) {
    uint64_t deadline = time_us_64() + (uint64_t)timeout_ms * 1000;
    while (time_us_64() < deadline) {
        if (dp() == want_dp && dm() == want_dm) return true;
        sleep_us(50);
    }
    return false;
}

// ---------------------------------------------------------------- phases ---
static bool selftest(void) {
    lines_release(); pullups(true); sleep_ms(2);
    bool ok = dp() && dm();
    dlog("SELFTEST %s (D+=%d D-=%d with pull-ups on)", ok ? "ok" : "FAULT: a line reads low - check wiring/pull-ups", dp(), dm());
    return ok;
}

// Returns the polarity that produced the acknowledge, or -1 on button abort.
static int key_phase(void) {
    int pol = (polarity_mode == POLARITY_DM_CLOCK) ? POLARITY_DM_CLOCK : POLARITY_DP_CLOCK;
    uint32_t packets = 0, in_block = 0;
    uint64_t start = time_us_64(), last_blink = start;
    bool led_on = false;
    pullups(true); mux_to_dongle(); key_start(pol);
    dlog("KEY start: polarity mode=%s sof_mode=%s", polarity_mode == POLARITY_ALTERNATE ? "alternate" : pol_name(pol),
         sof_mode == SOF_MODE_DONGLE ? "dongle-SOF" : "pc-SOF");
    for (;;) {
        key_send_packet(); packets++; in_block++;
        if (gap_sense_ack()) {
            dlog("ACK polarity=%s after %lu packets (%.1f ms)", pol_name(pol), (unsigned long)packets, (time_us_64() - start) / 1000.0);
            return pol;
        }
        if (polarity_mode == POLARITY_ALTERNATE && in_block >= KEY_PACKETS_PER_POLARITY) {
            pol = (pol == POLARITY_DP_CLOCK) ? POLARITY_DM_CLOCK : POLARITY_DP_CLOCK;
            in_block = 0; key_start(pol);
        }
        if (KEY_TIMEOUT_MS && time_us_64() - start > (uint64_t)KEY_TIMEOUT_MS * 1000) { dlog("KEY timeout"); return -1; }
        if (button_pressed()) { dlog("KEY aborted by button"); return -1; }
        if (time_us_64() - last_blink > 500000) { led_on = !led_on; led(led_on); last_blink = time_us_64(); }
    }
}

static bool sof_phase(void) {
    pullups(false);                                   // we must see the chip's own D+ pull-up come and go
    lines_release();
    if (!wait_lines(true, false, SOF_DP_HIGH_TIMEOUT_MS)) {
        dlog("SOF: D+ did not go high within %d ms (D+=%d D-=%d)", SOF_DP_HIGH_TIMEOUT_MS, dp(), dm());
        return false;
    }
    dlog("SOF: D+ high (chip pull-up), generating %d us pulses every %d us", SOF_PULSE_CYCLES, SOF_PERIOD_CYCLES);
    sof_start();
    uint64_t start = time_us_64(); uint32_t low_run = 0, samples = 0;
    while (time_us_64() - start < (uint64_t)SOF_PHASE_TIMEOUT_MS * 1000) {
        sleep_us(SOF_SAMPLE_US); samples++;
        if (!dp()) { if (++low_run * SOF_SAMPLE_US >= SOF_DONE_LOW_MS * 1000) {
                        dlog("SOF: D+ released after ~%lu pulses (%.1f ms) - calibration done", (unsigned long)((time_us_64() - start) / SOF_PERIOD_CYCLES), (time_us_64() - start) / 1000.0);
                        lines_release(); return true; } }
        else low_run = 0;
    }
    dlog("SOF: timeout after %d ms (D+=%d)", SOF_PHASE_TIMEOUT_MS, dp());
    lines_release();
    return false;
}

static void blink(int times, int period_ms) { for (int i = 0; i < times; i++) { led(true); sleep_ms(period_ms / 2); led(false); sleep_ms(period_ms / 2); } }

int main(void) {
    stdio_init_all();
    gpio_init(PICO_DEFAULT_LED_PIN); gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);
    gpio_init(PIN_MUX_SEL); gpio_set_dir(PIN_MUX_SEL, GPIO_OUT); mux_to_pc();
    for (int i = 0; i < 2; i++) { gpio_init(PULLUP_PINS[i]); gpio_disable_pulls(PULLUP_PINS[i]); }  // pads default to pull-down
    pullups(false);
    gpio_init(PIN_BUTTON); gpio_set_dir(PIN_BUTTON, GPIO_IN); gpio_pull_up(PIN_BUTTON);
    gpio_init(PIN_DP); gpio_init(PIN_DM);
    gpio_disable_pulls(PIN_DP); gpio_disable_pulls(PIN_DM);          // RP2040 pads default to pull-down
    gpio_set_dir(PIN_DP, GPIO_IN); gpio_set_dir(PIN_DM, GPIO_IN);

    off_key = pio_add_program(pio, &usb_key_program);
    off_sof = pio_add_program(pio, &sof_pulse_program);
    sm_key = pio_claim_unused_sm(pio, true);
    sm_sof = pio_claim_unused_sm(pio, true);

    sleep_ms(1500);                                                   // let the USB console attach
    t0 = time_us_64();
    printf("\nFM-1 USB_KEY dongle (docs/10-usb-key-dongle.md). Key 0x%04X, %d kHz, gap %d us.\n",
           USB_KEY_WORD, KEY_PIO_HZ / KEY_BIT_CYCLES / 1000, KEY_GAP_US);
    if (button_pressed()) { polarity_mode = POLARITY_DM_CLOCK; dlog("button held at boot: fixed polarity %s", pol_name(POLARITY_DM_CLOCK)); while (button_pressed()) sleep_ms(10); }

    for (;;) {
        state_t st = selftest() ? ST_KEY : ST_FAULT;
        if (st == ST_KEY) {
            int pol = key_phase();
            if (pol < 0) st = ST_FAILED;
            else {
                st = ST_ACK; blink(3, 100);
                pio_sm_set_enabled(pio, sm_key, false); lines_release(); pullups(true);
                if (!wait_lines(true, true, ACK_RELEASE_TIMEOUT_MS))
                    dlog("ACK: lines not released within %d ms (D+=%d D-=%d), continuing", ACK_RELEASE_TIMEOUT_MS, dp(), dm());
                else dlog("ACK: lines released");
                if (sof_mode == SOF_MODE_PC) { pullups(false); mux_to_pc(); dlog("bus -> PC (pc-SOF mode)"); st = ST_DONE; }
                else st = sof_phase() ? ST_DONE : ST_FAILED;
                if (st == ST_DONE) {
                    pullups(false); lines_release(); mux_to_pc();
                    dlog("DONE: bus -> PC. On the Linux PC run: python3 jldevfind.py  (expect a 'UBOOT1.00' mass-storage device)");
                }
            }
        }
        pullups(false); lines_release(); mux_to_pc();
        // Idle until the button is pressed; LED shows the outcome.
        dlog("state=%s - press the button to restart (power-cycle the FM-1 first)",
             st == ST_DONE ? "DONE" : st == ST_FAULT ? "FAULT" : "FAILED");
        while (!button_pressed()) {
            if (st == ST_DONE) { led(true); sleep_ms(50); }
            else if (st == ST_FAULT) blink(1, 100);
            else blink(1, 200);
        }
        while (button_pressed()) sleep_ms(10);
        led(false);
    }
}
