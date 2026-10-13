/* SPDX-License-Identifier: GPL-3.0-only */
/* Native engine integration probe. Build only; device admission is separate. */
#define APP_NAME "LUNAR MODULATOR"
#define APP_VER "NATIVE PROBE"
#include "platform.c"
#include "engine_adapter.h"

static volatile uint32_t engine_ready;
static volatile uint32_t render_ticks_max, render_overruns, event_overflow;
static volatile uint32_t event_write, event_read;
static uint32_t events[64];

/* Main loop produces, audio ISR consumes. Payload precedes publication. */
static void enqueue(uint8_t status, uint8_t note, uint8_t velocity)
{
    uint32_t w = event_write;
    if (w - event_read == 64u) { event_overflow++; return; }
    events[w & 63u] = status | ((uint32_t)note << 8) | ((uint32_t)velocity << 16);
    RING_PUBLISH();
    event_write = w + 1u;
}
static void app_audio(int32_t *out, uint32_t n)
{
    static uint32_t overflow_seen;
    uint32_t start, offset, r, end, overflow;
    if (!engine_ready) return;
    start = fm1_ticks();
    r = event_read;
    end = event_write;
    overflow = event_overflow;
    if (overflow != overflow_seen) {
        /* A lost note-off must not leave a voice held. Discard this burst. */
        lunar_engine_all_notes_off();
        r = end;
        overflow_seen = overflow;
    }
    while (r != end) {
        uint32_t e = events[r & 63u];
        lunar_engine_event((uint8_t)e, (uint8_t)(e >> 8), (uint8_t)(e >> 16));
        r++;
    }
    RING_PUBLISH();
    event_read = r;
    for (offset = 0; offset < n; offset += 64u) {
        uint32_t count = n - offset;
        if (count > 64u) count = 64u;
        lunar_engine_render(out + offset * 2u, count);
    }
    start = fm1_ticks() - start;
    if (start > render_ticks_max) render_ticks_max = start;
    if (start > (24000000u / FS) * n) render_overruns++;
}
static void app_main(void)
{
    uint32_t previous = 0, last_status = 0;
    uint32_t probe_start = fm1_ticks();
    uint8_t held[27] = {0};
    int octave = 0;
    uint32_t page = 0;
    uint32_t ready = lunar_engine_init(FS);
    lcd_fill(0, 0, 240, 240, C_BLACK);
    draw_text_box(0, 18, 240, &FONT_S, APP_NAME, C_WHITE, 1);
    draw_text_box(0, 52, 240, &FONT_S, ready ? "TRIO - KNOBS %" : "ENGINE INIT FAILED", C_WHITE, 1);
    RING_PUBLISH();
    engine_ready = ready;
    for (;;) {
        uint32_t k, released, buttons, keys, down, up;
        uint8_t st, a, b;
        /* TIMER4 remains usable even if the TIMER5 millisecond IRQ stops. */
        if ((uint32_t)(fm1_ticks() - probe_start) >= 20u * 1000000u * FM1_TICKS_PER_US) {
            fm1_audio_stop();
            usb_detach();
            fm1_delay_ms(30);
            bootguard_clear(&bootguard);
            fm1_enter_uboot();
        }
        platform_poll();
        keys = fm1_in.notes; down = keys & ~previous; up = previous & ~keys; previous = keys;
        for (k = 0; k < 27u; k++) {
            if ((down >> k) & 1u) {
                held[k] = (uint8_t)(53 + 12 * octave + (int)k);
                enqueue(0x90, held[k], 100); midi_send(0x90, held[k], 100);
            }
            if ((up >> k) & 1u) { enqueue(0x80, held[k], 0); midi_send(0x80, held[k], 0); }
            fm1_led_key(KEY_LED(k), (keys >> k) & 1u);
        }
        buttons = fm1_input_edges(&released);
        if ((buttons & (1u << BTN_OCT_DOWN)) && octave > -2) octave--;
        if ((buttons & (1u << BTN_OCT_UP)) && octave < 2) octave++;
        {
            int32_t step = fm1_enc_take(ENC_SELECT);
            int32_t pages = (lunar_engine_param_count() + 3u) / 4u;
            int32_t next = (int32_t)page + step;
            if (next < 0) next = 0;
            if (next >= pages) next = pages - 1;
            page = pages ? (uint32_t)next : 0;
            for (k = 0; k < 4u; k++) {
                step = fm1_enc_take(ENC_KNOB1 + k);
                if (step > 127) step = 127;
                if (step < -127) step = -127;
                if (step) enqueue(1u, (uint8_t)(page * 4u + k), (uint8_t)(int8_t)step);
            }
        }
        if (buttons & (1u << BTN_HOME)) enqueue(0xb0, 123, 0);
        while (midi_get(&st, &a, &b)) enqueue(st, a, b);
        if (fm1_ms - last_status >= 500u) {
            char text[16];
            last_status = fm1_ms;
            for (k = 0; k < 4u; k++) {
                uint16_t index = (uint16_t)(page * 4u + k);
                draw_text_box(8, 84 + k * 24u, 140, &FONT_S, lunar_engine_param_name(index), C_WHITE, 0);
                fmt_int(text, lunar_engine_param_position(index));
                draw_text_box(156, 84 + k * 24u, 76, &FONT_S, text, C_WHITE, 0);
            }
            draw_text_box(8, 188, 140, &FONT_S, "PEAK US", C_WHITE, 0);
            fmt_int(text, (int32_t)(render_ticks_max / FM1_TICKS_PER_US));
            draw_text_box(156, 188, 76, &FONT_S,
                          render_ticks_max / FM1_TICKS_PER_US > 99999u ? "99999+" : text, C_WHITE, 0);
            fmt_int(text, (int32_t)render_overruns);
            draw_text_box(8, 216, 140, &FONT_S, "OVERRUNS", C_WHITE, 0);
            draw_text_box(156, 216, 76, &FONT_S,
                          render_overruns > 99999u ? "99999+" : text, C_WHITE, 0);
        }
    }
}
