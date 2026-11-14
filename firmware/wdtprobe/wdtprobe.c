/* SPDX-License-Identifier: MIT
 * K1-K3 watchdog probe, portable logic. Independently written; the UART,
 * the watchdog kick and the reset to the application are ramtest.c's, linked
 * unchanged. The P33 byte frame is ramtest.c's too (SDK p33_buf shape), here
 * with a read that never writes back.
 *
 * Register facts (WL82.h, p33.h and wdt.h of the pinned AC79 SDK [verified]):
 *   JL_CLOCK 0x10000: PWR_CON +0, SYS_DIV +8, CLK_CON0..3 +0xc..+0x18.
 *   JL_SYSTEM->RST_SRC 0x100c0 (map_adr(0x00, 0x30)).
 *   JL_ANA 0x11900: PLL_CON0 +0xa0, PLL_CON1 +0xa4, PLL2_CON0 +0xa8,
 *     PLL2_CON1 +0xac (forty WLA_CON words precede them).
 *   JL_TIMER4 0x10800: CON +0, CNT +4, PRD +8. CON bit 0 run, bit 3 OSC
 *     source, [7:4] prescaler index (2 = /16), bit 14 clear pending
 *     [verified: SDK timer test2.c, as firmware/m6/m6_core.h].
 *   P33: P3_RST_SRC 0x12, P3_VLD_KEEP 0x17 (bit 6 WDT_EXPT_EN), P3_WDT_CON
 *     0x80 ([3:0] time code, 0xc = WDT_4S, 0xb = WDT_2S; bit 4 enable;
 *     bit 6 clear), P3_PR_PWR 0xa0 (bit 4 chip reset).
 *   Boot marker "usb_update_mode\0" at 0x01c7fd80 (ramtest.c). Crumb B sits
 *     at the start of 0x01c7c000-0x01c7fd50, which survives resets and UBOOT
 *     entry [reported: Felucca app.ld, docs/01 §2], well below the
 *     UPDATA_PARM record at 0x01c7fd88 and the kit app's fail-open record.
 */
#include "wdtprobe.h"
#include "../display/m5_pattern.h"

#define PWR_CON 0x10000u
#define SYS_DIV 0x10008u
#define CLK_CON0 0x1000cu
#define CLK_CON1 0x10010u
#define CLK_CON2 0x10014u
#define CLK_CON3 0x10018u
#define SYS_RST_SRC 0x100c0u
#define PLL_CON0 0x119a0u
#define PLL_CON1 0x119a4u
#define PLL2_CON0 0x119a8u
#define PLL2_CON1 0x119acu
#define TIMER4_CON 0x10800u
#define TIMER4_CNT 0x10804u
#define TIMER4_PRD 0x10808u
#define P33_CON 0x13e08u
#define P33_DAT 0x13e0cu
#define P33_SELECT 0x001u
#define P33_BUSY 0x002u
#define P33_START 0x010u
#define P33_RTC 0x100u
#define P3_RST_SRC 0x12u
#define P3_VLD_KEEP 0x17u
#define P3_WDT_CON 0x80u
#define P3_PR_PWR 0xa0u
#define P3_CHIP_RESET 0x10u
#define WDT_ENABLE 0x10u
#define WDT_INTERRUPT 0x20u
#define MARKER LUNAR_RAMTEST_BOOT_MARKER
#define KICK_TRIALS 240u

static const unsigned clock_regs[] = {
    PWR_CON, SYS_DIV, CLK_CON0, CLK_CON1, CLK_CON2, CLK_CON3,
    PLL_CON0, PLL_CON1, PLL2_CON0, PLL2_CON1
};
static const char *const clock_names[] = {
    " pwr_con=", " sys_div=", " clk_con0=", " clk_con1=", " clk_con2=",
    " clk_con3=", " pll_con0=", " pll_con1=", " pll2_con0=", " pll2_con1="
};
#define CLOCKS (sizeof clock_regs / sizeof clock_regs[0])
static const unsigned p33_regs[] = { P3_WDT_CON, P3_VLD_KEEP, P3_RST_SRC, P3_PR_PWR };
static const char *const p33_names[] = { " wdt_con=", " vld_keep=", " rst_src=", " pr_pwr=" };
#define P33S (sizeof p33_regs / sizeof p33_regs[0])
static const char *const mode_names[] = { "?", "read", "kick", "disarm", "mailbox" };
static const char *const failures[] = { "none", "args", "p33", "timer", "no_reset" };
/* "usb_update_mode\0" as four little-endian words. */
static const unsigned marker_words[4] = {
    0x5f627375u, 0x61647075u, 0x6d5f6574u, 0x0065646fu
};

struct snapshot {
    unsigned clocks[CLOCKS], p33[P33S], p33_ok, sys_rst_src, timer_con;
    unsigned marker[4], crumb_a[4], crumb_b[4];
};

struct stopwatch {
    unsigned last, total, failed;
};

static void puthex(struct lunar_ramtest_io *io, unsigned value)
{
    unsigned shift = 32u;
    lunar_ramtest_puts(io, "0x");
    while (shift) {
        unsigned nibble;
        shift -= 4u;
        nibble = (value >> shift) & 0xfu;
        lunar_ramtest_putc(io, (char)(nibble < 10u ? '0' + nibble : 'a' + nibble - 10u));
    }
}

static void say(struct lunar_ramtest_io *io, const char *what)
{
    lunar_ramtest_puts(io, "LUNAR_WDTPROBE ");
    lunar_ramtest_puts(io, what);
}

static void end_line(struct lunar_ramtest_io *io)
{
    lunar_ramtest_puts(io, "\r\n");
}

static int p33_idle(const struct lunar_ramtest_io *io)
{
    unsigned n;
    for (n = 0; n < LUNAR_RAMTEST_POLLS; ++n)
        if (!(io->read(io->context, P33_CON, 4) & P33_BUSY)) return 1;
    return 0;
}

static int p33_byte(const struct lunar_ramtest_io *io, unsigned out, unsigned *in)
{
    io->write(io->context, P33_DAT, 4, out);
    io->write(io->context, P33_CON, 4, io->read(io->context, P33_CON, 4) | P33_START);
    io->sync(io->context);
    if (!p33_idle(io)) return 0;
    *in = io->read(io->context, P33_DAT, 4) & 0xffu;
    return 1;
}

/* Three bytes inside one select, as ramtest.c and the SDK do. */
static int p33_frame(const struct lunar_ramtest_io *io, unsigned first, unsigned second,
                     unsigned third, unsigned *value)
{
    unsigned ignored, ok;
    if (!p33_idle(io)) return 0;
    io->write(io->context, P33_CON, 4,
              (io->read(io->context, P33_CON, 4) & ~P33_RTC) | P33_SELECT);
    ok = p33_byte(io, first, &ignored) && p33_byte(io, second, &ignored) &&
         p33_byte(io, third, value);
    io->write(io->context, P33_CON, 4,
              io->read(io->context, P33_CON, 4) & ~(P33_SELECT | P33_RTC));
    return (int)ok;
}

int lunar_wdtprobe_p33_read(const struct lunar_ramtest_io *io, unsigned address,
                            unsigned *value)
{
    if (!io || !io->read || !io->write || !io->sync || !value || address > 0x3ffu) return 0;
    return p33_frame(io, 0x80u | (address >> 8), address & 0xffu, 0x5eu, value);
}

int lunar_wdtprobe_p33_write(const struct lunar_ramtest_io *io, unsigned address,
                             unsigned value)
{
    unsigned ignored;
    if (!io || !io->read || !io->write || !io->sync || address > 0x3ffu) return 0;
    if (!p33_frame(io, address >> 8, address & 0xffu, value & 0xffu, &ignored)) return 0;
    io->sync(io->context);
    return 1;
}

unsigned lunar_wdtprobe_ticks_between(unsigned then, unsigned now)
{
    then %= LUNAR_WDTPROBE_TIMER_MOD;
    now %= LUNAR_WDTPROBE_TIMER_MOD;
    return now >= then ? now - then : now + LUNAR_WDTPROBE_TIMER_MOD - then;
}

static void read_words(const struct lunar_ramtest_io *io, unsigned address, unsigned *out)
{
    unsigned i;
    for (i = 0; i < 4u; ++i) out[i] = io->read(io->context, address + 4u * i, 4);
}

static void write_words(const struct lunar_ramtest_io *io, unsigned address,
                        const unsigned *words)
{
    unsigned i;
    for (i = 0; i < 4u; ++i) io->write(io->context, address + 4u * i, 4, words ? words[i] : 0);
    io->sync(io->context);
}

/* Everything at entry, before the UART or TIMER4 is touched. Reads only. */
static void take_snapshot(const struct lunar_ramtest_io *io, struct snapshot *s)
{
    unsigned i;
    for (i = 0; i < CLOCKS; ++i) s->clocks[i] = io->read(io->context, clock_regs[i], 4);
    s->sys_rst_src = io->read(io->context, SYS_RST_SRC, 4);
    s->timer_con = io->read(io->context, TIMER4_CON, 4);
    s->p33_ok = 1;
    for (i = 0; i < P33S; ++i)
        if (!lunar_wdtprobe_p33_read(io, p33_regs[i], &s->p33[i])) {
            s->p33[i] = 0xffffffffu;
            s->p33_ok = 0;
        }
    read_words(io, MARKER, s->marker);
    read_words(io, LUNAR_WDTPROBE_CRUMB_A, s->crumb_a);
    read_words(io, LUNAR_WDTPROBE_CRUMB_B, s->crumb_b);
}

static int crumb_valid(const unsigned *w)
{
    return w[0] == LUNAR_WDTPROBE_MAGIC && w[3] == ~LUNAR_WDTPROBE_MAGIC;
}

static int marker_set(const unsigned *w)
{
    unsigned i;
    for (i = 0; i < 4u; ++i) if (w[i] != marker_words[i]) return 0;
    return 1;
}

static void print_words(struct lunar_ramtest_io *io, const unsigned *w)
{
    unsigned i;
    for (i = 0; i < 4u; ++i) {
        lunar_ramtest_putc(io, ' ');
        puthex(io, w[i]);
    }
}

static void report(struct lunar_ramtest_io *io, const struct snapshot *s)
{
    unsigned i, wdt = s->p33[0];
    say(io, "clock");
    for (i = 0; i < CLOCKS; ++i) {
        lunar_ramtest_puts(io, clock_names[i]);
        puthex(io, s->clocks[i]);
    }
    lunar_ramtest_puts(io, " timer4_con=");
    puthex(io, s->timer_con);
    end_line(io);
    say(io, "p33 ok=");
    lunar_ramtest_putu(io, s->p33_ok);
    for (i = 0; i < P33S; ++i) {
        lunar_ramtest_puts(io, p33_names[i]);
        puthex(io, s->p33[i]);
    }
    lunar_ramtest_puts(io, " sys_rst_src=");
    puthex(io, s->sys_rst_src);
    end_line(io);
    say(io, "wdt armed=");
    lunar_ramtest_putu(io, s->p33_ok ? !!(wdt & WDT_ENABLE) : 9u);
    lunar_ramtest_puts(io, " code=");
    lunar_ramtest_putu(io, wdt & 0xfu);
    lunar_ramtest_puts(io, " interrupt=");
    lunar_ramtest_putu(io, !!(wdt & WDT_INTERRUPT));
    lunar_ramtest_puts(io, " expt_en=");
    lunar_ramtest_putu(io, !!(s->p33[1] & 0x40u));
    end_line(io);
    say(io, "mailbox usb_update_mode=");
    lunar_ramtest_putu(io, marker_set(s->marker));
    print_words(io, s->marker);
    end_line(io);
    say(io, "crumb a=0x01c07c00 valid=");
    lunar_ramtest_putu(io, crumb_valid(s->crumb_a));
    print_words(io, s->crumb_a);
    end_line(io);
    say(io, "crumb b=0x01c7c000 valid=");
    lunar_ramtest_putu(io, crumb_valid(s->crumb_b));
    print_words(io, s->crumb_b);
    end_line(io);
}

static unsigned timer_count(const struct lunar_ramtest_io *io)
{
    return io->read(io->context, TIMER4_CNT, 4);
}

/* Free-running TIMER4 as M6's stopwatch: stop and clear, CNT 0, PRD, run. */
static void stopwatch_start(const struct lunar_ramtest_io *io, struct stopwatch *w)
{
    io->write(io->context, TIMER4_CON, 4, 1u << 14);
    io->sync(io->context);
    io->write(io->context, TIMER4_CNT, 4, 0);
    io->write(io->context, TIMER4_PRD, 4, LUNAR_WDTPROBE_TIMER_MOD - 1u);
    io->write(io->context, TIMER4_CON, 4, LUNAR_WDTPROBE_TIMER_RUN);
    io->sync(io->context);
    w->last = timer_count(io);
    w->total = 0;
    w->failed = 0;
}

/* Fold elapsed ticks into the running total. Between two calls less than one
 * timer period (21.8 ms at 1.5 MHz) may pass. */
static void stopwatch_poll(const struct lunar_ramtest_io *io, struct stopwatch *w)
{
    unsigned now = timer_count(io);
    w->total += lunar_wdtprobe_ticks_between(w->last, now);
    w->last = now;
}

/* Poll until the total reaches `until`. *loops gets the polls spent. */
static int stopwatch_wait(const struct lunar_ramtest_io *io, struct stopwatch *w,
                          unsigned until, unsigned *loops)
{
    unsigned n, still = 0, before;
    for (n = 0; n < LUNAR_WDTPROBE_BEAT_POLLS && w->total < until; ++n) {
        before = w->total;
        stopwatch_poll(io, w);
        if (w->total == before) {
            if (++still == LUNAR_WDTPROBE_STALL_POLLS) break;
        } else {
            still = 0;
        }
    }
    *loops = n;
    if (w->total < until) w->failed = 1;
    return !w->failed;
}

static void reset_app(struct lunar_ramtest_io *io, enum lunar_wdtprobe_result *result)
{
    enum lunar_ramtest_result r;
    say(io, "reset=app");
    end_line(io);
    r = lunar_ramtest_reset_to_app(io);
    *result = r == LUNAR_RAMTEST_FAIL_NO_RESET ? LUNAR_WDTPROBE_FAIL_NO_RESET
                                               : LUNAR_WDTPROBE_FAIL_P33;
}

/* Reset through P3_PR_PWR bit 4 with the marker left in place. */
static enum lunar_wdtprobe_result reset_uboot(struct lunar_ramtest_io *io)
{
    unsigned value;
    say(io, "reset=uboot");
    end_line(io);
    if (!lunar_wdtprobe_p33_read(io, P3_PR_PWR, &value) ||
        !lunar_wdtprobe_p33_write(io, P3_PR_PWR, value | P3_CHIP_RESET))
        return LUNAR_WDTPROBE_FAIL_P33;
    io->pause(io->context, 10u);
    return LUNAR_WDTPROBE_FAIL_NO_RESET;
}

static void beat_line(struct lunar_ramtest_io *io, unsigned beat, const struct stopwatch *w,
                      unsigned loops, unsigned wdt)
{
    say(io, "beat=");
    lunar_ramtest_putu(io, beat);
    lunar_ramtest_puts(io, " ticks=");
    lunar_ramtest_putu(io, w->total);
    lunar_ramtest_puts(io, " loops=");
    lunar_ramtest_putu(io, loops);
    lunar_ramtest_puts(io, " wdt_con=");
    puthex(io, wdt);
    end_line(io);
}

/* Time the M5 pattern's pixel function over the whole frame, a kick per row
 * (no SPI: on the kit PC7-PC10 are its LCD/touch pins), then 240 kicks alone. */
static int time_pixels(struct lunar_ramtest_io *io, struct stopwatch *w, const char *build_id)
{
    unsigned x, y, start, pixels, kicks, mix = 0, wdt = 0;
    stopwatch_poll(io, w);
    start = w->total;
    for (y = 0; y < LUNAR_M5_HEIGHT; ++y) {
        for (x = 0; x < LUNAR_M5_WIDTH; ++x) mix = (mix * 31u) ^ lunar_m5_pixel(x, y, build_id);
        if (!lunar_ramtest_wdt_kick(io, &wdt)) return 0;
        stopwatch_poll(io, w);
    }
    pixels = w->total - start;
    start = w->total;
    for (x = 0; x < KICK_TRIALS; ++x) {
        if (!lunar_ramtest_wdt_kick(io, &wdt)) return 0;
        stopwatch_poll(io, w);
    }
    kicks = w->total - start;
    say(io, "m5_pixels=57600 ticks=");
    lunar_ramtest_putu(io, pixels);
    lunar_ramtest_puts(io, " kick240_ticks=");
    lunar_ramtest_putu(io, kicks);
    lunar_ramtest_puts(io, " mix=");
    puthex(io, mix);
    end_line(io);
    return 1;
}

enum lunar_wdtprobe_result lunar_wdtprobe_run(struct lunar_ramtest_io *io, unsigned mode,
                                              const char *build_id, unsigned image_bytes,
                                              unsigned beats)
{
    static const unsigned crumb[4] = {
        LUNAR_WDTPROBE_MAGIC, 0, 0, ~LUNAR_WDTPROBE_MAGIC
    };
    struct snapshot s;
    struct stopwatch w;
    unsigned beat, loops, wdt, words[4];
    enum lunar_wdtprobe_result result = LUNAR_WDTPROBE_FAIL_ARGS;
    if (!io || !io->read || !io->write || !io->sync || !io->pause || !build_id ||
        mode < LUNAR_WDTPROBE_READ || mode > LUNAR_WDTPROBE_MAILBOX)
        return LUNAR_WDTPROBE_FAIL_ARGS;
    take_snapshot(io, &s);
    if (!lunar_ramtest_uart_init(io)) return LUNAR_WDTPROBE_FAIL_ARGS;
    io->uart_failed = 0;
    lunar_ramtest_puts(io, "\r\n");
    say(io, "ready=1 build=");
    lunar_ramtest_puts(io, build_id);
    lunar_ramtest_puts(io, " mode=");
    lunar_ramtest_puts(io, mode_names[mode]);
    lunar_ramtest_puts(io, " entry=0x01c02000 bytes=");
    lunar_ramtest_putu(io, image_bytes);
    end_line(io);
    report(io, &s);
    if (!s.p33_ok) {
        reset_app(io, &result);
        goto failed;
    }
    wdt = s.p33[0];
    words[0] = crumb[0];
    words[1] = mode;
    words[2] = s.p33[0];
    words[3] = crumb[3];

    if (mode == LUNAR_WDTPROBE_DISARM) {
        unsigned after = 0;
        if (!lunar_wdtprobe_p33_write(io, P3_WDT_CON, LUNAR_WDTPROBE_DISARMED) ||
            !lunar_wdtprobe_p33_read(io, P3_WDT_CON, &after)) {
            reset_app(io, &result);
            goto failed;
        }
        say(io, "disarm wdt_con=");
        puthex(io, after);
        end_line(io);
        write_words(io, LUNAR_WDTPROBE_CRUMB_A, words);
        write_words(io, LUNAR_WDTPROBE_CRUMB_B, words);
        write_words(io, MARKER, marker_words);
        result = reset_uboot(io);
        goto failed;
    }

    if (mode == LUNAR_WDTPROBE_MAILBOX) {
        if (!(wdt & WDT_ENABLE)) {
            if (!lunar_wdtprobe_p33_write(io, P3_WDT_CON, LUNAR_WDTPROBE_ARM_4S) ||
                !lunar_wdtprobe_p33_read(io, P3_WDT_CON, &wdt)) {
                reset_app(io, &result);
                goto failed;
            }
            say(io, "armed_by_probe=1 wdt_con=");
            puthex(io, wdt);
            end_line(io);
        }
        write_words(io, LUNAR_WDTPROBE_CRUMB_A, words);
        write_words(io, LUNAR_WDTPROBE_CRUMB_B, words);
        write_words(io, MARKER, marker_words);
        say(io, "mailbox=set waiting_for_wdt=1");
        end_line(io);
    } else {
        /* READ and KICK: a later reset of either kind must land in the app. */
        write_words(io, MARKER, 0);
        write_words(io, LUNAR_WDTPROBE_CRUMB_A, 0);
        write_words(io, LUNAR_WDTPROBE_CRUMB_B, 0);
        say(io, "cleared marker=1 crumbs=1");
        end_line(io);
    }

    stopwatch_start(io, &w);
    for (beat = 1; beat <= beats; ++beat) {
        if (!stopwatch_wait(io, &w, beat * LUNAR_WDTPROBE_BEAT_TICKS, &loops)) {
            say(io, "timer=stalled ticks=");
            lunar_ramtest_putu(io, w.total);
            end_line(io);
            reset_app(io, &result);
            if (result == LUNAR_WDTPROBE_FAIL_NO_RESET) result = LUNAR_WDTPROBE_FAIL_TIMER;
            goto failed;
        }
        if (mode == LUNAR_WDTPROBE_KICK) {
            if (!lunar_ramtest_wdt_kick(io, &wdt)) wdt = 0xffffffffu;
        } else if (!lunar_wdtprobe_p33_read(io, P3_WDT_CON, &wdt)) {
            wdt = 0xffffffffu;
        }
        beat_line(io, beat, &w, loops, wdt);
    }
    if (mode == LUNAR_WDTPROBE_KICK && !time_pixels(io, &w, build_id)) {
        say(io, "kick=failed");
        end_line(io);
    }
    say(io, "alive beats=");
    lunar_ramtest_putu(io, beats);
    lunar_ramtest_puts(io, " ticks=");
    lunar_ramtest_putu(io, w.total);
    end_line(io);
    io->pause(io->context, 1u); /* let the last byte leave the shifter */
    reset_app(io, &result);
failed:
    say(io, "reset_failed=");
    lunar_ramtest_puts(io, failures[result < 5u ? result : 1u]);
    end_line(io);
    return result;
}
