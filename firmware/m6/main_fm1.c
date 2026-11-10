/* SPDX-License-Identifier: MIT
 * M6 entry for the FM-1: RAM-only, SDK-free, core 0, interrupts masked,
 * built but NOT run (its approval request is in notes/2026-11-09-m6-image.md).
 * Order: core check, read the clock words, PA2 low, TIMER4 paces the panel
 * setup, the static frame and the eight status lines, then TIMER4 becomes a
 * free-running stopwatch and ALNK0 starts; one reduced voice is rendered per
 * polled block while the panel lines are redrawn in the slack. On a stop the
 * last screen stays up and the lines keep redrawing.
 */
#include "../board/alnk0_audio.h"
#include "../board/board_io.h"
#include "../board/matrix.h"
#include "../display/spi1_transport.h"
#include "../ramtest/ramtest.h"
#include "../timing/timer4.h"
#include "m6_core.h"
#include "m6_screen.h"

#ifndef LUNAR_BUILD_ID
#define LUNAR_BUILD_ID "UNKNOWN"
#endif
/* As M5: bind TIMER4 at the 40 MHz upper bound so every panel wait is at
 * least as long as asked for any oscillator up to 40 MHz. */
#define OSC_HZ 40000000u
#define POLLS 65536u
#define SPIN_PER_MS 20000u   /* uncalibrated fallback only */
#define ALIVE_POLLS 100000u

/* The RAM status block (m6_core.h); the map file and the build log give its
 * address. */
volatile struct lunar_m6_status lunar_m6_status;
static const char build_id[] = LUNAR_BUILD_ID;
static int32_t audio[2u * LUNAR_M6_HALF_WORDS] __attribute__((aligned(32)));

extern unsigned __bss_begin[], __bss_end[];

static struct lunar_board_io board;
static struct lunar_timer_io timer_io;
static struct lunar_timer timer;
static struct lunar_spi1_io spi_io;
static struct lunar_spi1 spi;
static struct lunar_panel_transport panel;
static struct lunar_m6_screen screen;
static struct lunar_alnk0_ops mmio;
static struct lunar_m6_platform platform;
static struct lunar_m6 run;
static unsigned timer_ok;
static struct lunar_ramtest_io p33;   /* P33 watchdog access only; no UART */

static void spin(unsigned milliseconds)
{
    volatile unsigned i;
    while (milliseconds--)
        for (i = 0; i < SPIN_PER_MS; ++i) {}
}

static int panel_delay(void *context, unsigned milliseconds)
{
    (void)context;
    if (timer_ok && lunar_timer_delay(&timer, milliseconds)) return 1;
    timer_ok = 0;
    lunar_m6_status.flags |= LUNAR_M6_FLAG_TIMER_FALLBACK;
    spin(milliseconds);
    return 1;
}

static unsigned p33_read(void *context, unsigned address, unsigned width)
{
    return lunar_alnk0_mmio_read(context, address, width);
}

static void p33_write(void *context, unsigned address, unsigned width, unsigned value)
{
    lunar_alnk0_mmio_write(context, address, width, value);
}

/* Clear the P33 watchdog if an application left it armed (SDK wdt_clear). On
 * the AC79 kit it survives the jump into the mask ROM and reset run
 * 2026-11-09-m6-b after about 3-4.5 s [verified: kit UART]; whether it is
 * armed under the FM-1's ROM is not known, so the image checks and clears. */
static void kick(void *context)
{
    unsigned con = 0;
    (void)context;
    if (!lunar_ramtest_wdt_kick(&p33, &con)) lunar_m6_status.flags |= LUNAR_M6_FLAG_WDT_FAILED;
    if (con & 0x10u) lunar_m6_status.flags |= LUNAR_M6_FLAG_WDT_ARMED;
}

static int idle(void *context)
{
    (void)context;
    return 0;
}

void lunar_m6_main(void)
{
    unsigned core;
    volatile unsigned *word;
    int panel_ok = 0;
    unsigned steps;
    for (word = __bss_begin; word < __bss_end; ++word) *word = 0;
    lunar_m6_status_init(&lunar_m6_status, build_id);

    __asm__ volatile("%0 = cnum;" : "=r"(core));
    if (core != 0) for (;;) {} /* Only core 0 runs this image. */
    lunar_m6_status.step = LUNAR_M6_CORE_OK;

    /* Read only: the clock as the mask ROM left it. */
    lunar_m6_status.sys_div = lunar_alnk0_mmio_read(0, LUNAR_SYS_DIV, 4);
    lunar_m6_status.clk_con0 = lunar_alnk0_mmio_read(0, LUNAR_CLK_CON0, 4);
    lunar_m6_status.clk_con1 = lunar_alnk0_mmio_read(0, LUNAR_CLK_CON1, 4);
    lunar_m6_status.clk_con2 = lunar_alnk0_mmio_read(0, LUNAR_CLK_CON2, 4);

    p33.context = 0;
    p33.read = p33_read;
    p33.write = p33_write;
    p33.sync = lunar_alnk0_mmio_sync;
    p33.pause = 0;
    kick(0);

    lunar_board_native_io(&board);
    lunar_backlight_on(&board);

    lunar_timer_native_io(&timer_io);
    lunar_m6_status.timer_con_before = timer_io.read(0, LUNAR_TIMER_CON);
    timer_io.write(0, LUNAR_TIMER_CON, 1u << 14);
    timer_io.sync(0);
    timer_ok = (unsigned)lunar_timer_bind(&timer, &timer_io, OSC_HZ, POLLS);
    if (timer_ok) lunar_m6_status.step = LUNAR_M6_TIMER_OK;

    lunar_spi1_native_io(&spi_io, 0, panel_delay);
    lunar_m6_status.report_result = 0xffu;
    if (lunar_spi1_bind(&spi, &spi_io, POLLS, &panel) && lunar_spi1_configure(&spi)) {
        lunar_m6_status.report_result = lunar_m6_screen_frame(&panel, build_id);
        panel_ok = lunar_m6_status.report_result == LUNAR_PANEL_OK;
    }
    kick(0);
    if (panel_ok) lunar_m6_status.step = LUNAR_M6_REPORT_OK;
    else lunar_m6_status.flags |= LUNAR_M6_FLAG_REPORT_FAILED;

    /* TIMER4 now becomes the stopwatch; no lunar_timer_delay after this. */
    lunar_m6_stopwatch_start(&timer_io);
    lunar_m6_screen_init(&screen, &panel, &lunar_m6_status);
    if (lunar_m6_stopwatch_alive(&timer_io, ALIVE_POLLS)) {
        lunar_m6_status.step = LUNAR_M6_STOPWATCH_OK;
        lunar_m6_status.cpu_polls = lunar_m6_wait_ticks(&timer_io, LUNAR_M6_CALIBRATE_TICKS);
    }
    /* Every line once, blocking, before audio. */
    while (panel_ok && screen.passes == 0 && lunar_m6_screen_step(&screen)) {}
    kick(0);
    if (panel_ok && screen.failed) lunar_m6_status.flags |= LUNAR_M6_FLAG_REPORT_FAILED;

    if (lunar_m6_status.step == LUNAR_M6_STOPWATCH_OK) {
        mmio.context = 0;
        mmio.read = lunar_alnk0_mmio_read;
        mmio.write = lunar_alnk0_mmio_write;
        mmio.sync = lunar_alnk0_mmio_sync;
        platform.context = &screen;
        platform.alnk0 = &mmio;
        platform.timer = &timer_io;
        platform.report = panel_ok && !screen.failed ? lunar_m6_screen_step : idle;
        platform.kick = kick;
        run.status = &lunar_m6_status;
        lunar_m6_run(&run, &platform, audio, (uint32_t)(uintptr_t)audio, 0);
    }
    /* Stopped (or never started): keep the lines current and the watchdog
     * clear. If the panel failed, stop kicking: a watchdog reset then boots
     * the stock application. */
    for (steps = 0;; ++steps) {
        if (!panel_ok || !lunar_m6_screen_step(&screen)) for (;;) {}
        if ((steps & 0xfffu) == 0u) kick(0);
    }
}
