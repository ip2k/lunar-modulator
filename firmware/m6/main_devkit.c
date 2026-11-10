/* SPDX-License-Identifier: MIT
 * M6 entry for the AC79 dev kit: the same core and ALNK0 driver as the FM-1
 * image, with the FM-1's board layer left out. No panel, PA2 or key matrix:
 * on the kit PA0-PA7 carry camera data and PC7-PC10 are LCD and touch pins
 * [verified: SDK DevKitBoard.c]. ALNK0's PORTC pin writes (OUT, DIR, PU, PD
 * at 0x50080-0x50094) are dropped and counted, so no kit pin changes
 * direction; the rest of the sequence runs as on the FM-1. Reports go out on
 * the M4 debug UART (UART1 TX, PB3, 1,000,000 baud, ramtest.c): a banner, a
 * line per 1,024-block window sent a byte at a time in each block's slack, a
 * summary, then the M4 reset back to the kit's application. The P33
 * watchdog the kit's application left armed is cleared every 256 blocks. No audio is
 * heard: nothing on the kit listens to ALNK0.
 */
#include "../board/alnk0_audio.h"
#include "../ramtest/ramtest.h"
#include "../timing/timer4.h"
#include "m6_core.h"

#ifndef LUNAR_BUILD_ID
#define LUNAR_BUILD_ID "UNKNOWN"
#endif
#define KIT_BLOCKS 40960u   /* about 59 s at 44,100 Hz */
#define ALIVE_POLLS 100000u
#define SPIN_PER_TENTH 1000000u

volatile struct lunar_m6_status lunar_m6_status;
static const char build_id[] = LUNAR_BUILD_ID;
static int32_t audio[2u * LUNAR_M6_HALF_WORDS] __attribute__((aligned(32)));
extern unsigned __bss_begin[], __bss_end[];
extern char _start[], __image_end[];

static struct lunar_ramtest_io uart;
static struct lunar_timer_io timer_io;
static struct lunar_alnk0_ops kit_ops;
static struct lunar_m6_platform platform;
static struct lunar_m6 run;
static char line[128];
static unsigned wdt_con;
static unsigned line_length, line_sent, windows_sent;

static unsigned native_read(void *context, unsigned address, unsigned width)
{
    return lunar_alnk0_mmio_read(context, address, width);
}

static void native_write(void *context, unsigned address, unsigned width, unsigned value)
{
    lunar_alnk0_mmio_write(context, address, width, value);
}

static void native_pause(void *context, unsigned tenths)
{
    volatile unsigned i;
    (void)context;
    while (tenths--)
        for (i = 0; i < SPIN_PER_TENTH; ++i) {}
}

static void kit_write(void *context, uint32_t address, unsigned bytes, uint32_t value)
{
    if (lunar_m6_kit_masks(address)) {
        ++lunar_m6_status.pins_masked;
        lunar_m6_status.flags |= LUNAR_M6_FLAG_PINS_MASKED;
        return;
    }
    lunar_alnk0_mmio_write(context, address, bytes, value);
}

/* The kit's application arms the P33 watchdog and it keeps running through
 * the jump into the mask ROM: run 2026-11-09-m6-b was reset by it ("system
 * reset reason: WDT") after two windows, about 3-4.5 s in. */
static void kit_kick(void *context)
{
    (void)context;
    if (!lunar_ramtest_wdt_kick(&uart, 0)) lunar_m6_status.flags |= LUNAR_M6_FLAG_WDT_FAILED;
}

/* One UART byte of the current window line, or format the next one. */
static int kit_report(void *context)
{
    (void)context;
    if (line_sent < line_length) {
        lunar_ramtest_putc(&uart, line[line_sent++]);
        return 1;
    }
    if (lunar_m6_status.windows != windows_sent) {
        windows_sent = lunar_m6_status.windows;
        line_length = lunar_m6_format_window(&lunar_m6_status, line, sizeof line);
        line_sent = 0;
        return 1;
    }
    return 0;
}

static void put_field(const char *name, uint32_t value, int hex)
{
    char digits[12];
    unsigned n = hex ? lunar_m6_put_hex(digits, 8u, value) : lunar_m6_put_u(digits, 10u, value);
    digits[n] = 0;
    lunar_ramtest_puts(&uart, " ");
    lunar_ramtest_puts(&uart, name);
    lunar_ramtest_puts(&uart, hex ? "=0x" : "=");
    lunar_ramtest_puts(&uart, digits);
}

static void summary(void)
{
    const volatile struct lunar_m6_status *s = &lunar_m6_status;
    lunar_ramtest_puts(&uart, "LUNAR_M6 end");
    put_field("end", s->end, 0);
    put_field("step", s->step, 0);
    put_field("flags", s->flags, 1);
    put_field("alnk0_neg", (uint32_t)-s->alnk0_result, 0);
    put_field("first_wait", s->first_wait, 0);
    put_field("blocks", s->blocks, 0);
    put_field("late", s->late, 0);
    put_field("missed", s->missed, 0);
    lunar_ramtest_puts(&uart, "\r\nLUNAR_M6 ticks");
    put_field("render_min", s->render_min, 0);
    put_field("render_max", s->render_max, 0);
    put_field("interval_min", s->interval_min, 0);
    put_field("interval_max", s->interval_max, 0);
    put_field("busy_max", s->busy_max, 0);
    put_field("windows", s->windows, 0);
    put_field("win_render", s->win_render, 0);
    put_field("win_interval", s->win_interval, 0);
    lunar_ramtest_puts(&uart, "\r\nLUNAR_M6 derived");
    put_field("fs_if_24m", lunar_m6_fs_estimate(s->win_interval, LUNAR_M6_TICK_HZ_24M), 0);
    put_field("fs_if_40m", lunar_m6_fs_estimate(s->win_interval, LUNAR_M6_TICK_HZ_40M), 0);
    put_field("load_permille", lunar_m6_load_permille(s->win_render, s->win_interval), 0);
    put_field("pcm_hash", s->pcm_hash, 1);
    put_field("pcm_blocks", s->pcm_hash_blocks, 0);
    put_field("pins_masked", s->pins_masked, 0);
    lunar_ramtest_puts(&uart, "\r\n");
}

void lunar_m6_kit_main(void)
{
    unsigned core, beat = 0;
    volatile unsigned *word;
    for (word = __bss_begin; word < __bss_end; ++word) *word = 0;
    lunar_m6_status_init(&lunar_m6_status, build_id);
    __asm__ volatile("%0 = cnum;" : "=r"(core));
    if (core != 0) for (;;) {} /* Only core 0 runs this image. */
    lunar_m6_status.step = LUNAR_M6_CORE_OK;

    lunar_m6_status.sys_div = lunar_alnk0_mmio_read(0, LUNAR_SYS_DIV, 4);
    lunar_m6_status.clk_con0 = lunar_alnk0_mmio_read(0, LUNAR_CLK_CON0, 4);
    lunar_m6_status.clk_con1 = lunar_alnk0_mmio_read(0, LUNAR_CLK_CON1, 4);
    lunar_m6_status.clk_con2 = lunar_alnk0_mmio_read(0, LUNAR_CLK_CON2, 4);

    uart.context = 0;
    uart.read = native_read;
    uart.write = native_write;
    uart.sync = lunar_alnk0_mmio_sync;
    uart.pause = native_pause;
    uart.uart_failed = 0;
    if (!lunar_ramtest_wdt_kick(&uart, &wdt_con)) lunar_m6_status.flags |= LUNAR_M6_FLAG_WDT_FAILED;
    if (wdt_con & 0x10u) lunar_m6_status.flags |= LUNAR_M6_FLAG_WDT_ARMED;
    if (!lunar_ramtest_uart_init(&uart)) lunar_m6_status.report_result = 1;
    else lunar_m6_status.step = LUNAR_M6_REPORT_OK;
    lunar_ramtest_puts(&uart, "\r\nLUNAR_M6 build=");
    lunar_ramtest_puts(&uart, build_id);
    put_field("image", (uint32_t)(__image_end - _start), 0);
    put_field("status", (uint32_t)(uintptr_t)&lunar_m6_status, 1);
    put_field("buffer", (uint32_t)(uintptr_t)audio, 1);
    lunar_ramtest_puts(&uart, "\r\nLUNAR_M6 clock");
    put_field("sys_div", lunar_m6_status.sys_div, 1);
    put_field("clk_con0", lunar_m6_status.clk_con0, 1);
    put_field("clk_con1", lunar_m6_status.clk_con1, 1);
    put_field("clk_con2", lunar_m6_status.clk_con2, 1);
    put_field("wdt_con", wdt_con, 1);

    lunar_timer_native_io(&timer_io);
    lunar_m6_status.timer_con_before = timer_io.read(0, LUNAR_TIMER_CON);
    put_field("timer_con", lunar_m6_status.timer_con_before, 1);
    lunar_m6_stopwatch_start(&timer_io);
    lunar_m6_status.step = LUNAR_M6_TIMER_OK;
    if (lunar_m6_stopwatch_alive(&timer_io, ALIVE_POLLS)) {
        lunar_m6_status.step = LUNAR_M6_STOPWATCH_OK;
        lunar_m6_status.cpu_polls = lunar_m6_wait_ticks(&timer_io, LUNAR_M6_CALIBRATE_TICKS);
        put_field("cpu_polls", lunar_m6_status.cpu_polls, 0);
        lunar_ramtest_puts(&uart, "\r\n");

        kit_ops.context = 0;
        kit_ops.read = lunar_alnk0_mmio_read;
        kit_ops.write = kit_write;
        kit_ops.sync = lunar_alnk0_mmio_sync;
        platform.context = 0;
        platform.alnk0 = &kit_ops;
        platform.timer = &timer_io;
        platform.report = kit_report;
        platform.kick = kit_kick;
        run.status = &lunar_m6_status;
        lunar_m6_run(&run, &platform, audio, (uint32_t)(uintptr_t)audio, KIT_BLOCKS);
        while (kit_report(0)) {}
        kit_kick(0);
    } else {
        lunar_ramtest_puts(&uart, " stopwatch=dead\r\n");
    }
    summary();
    lunar_ramtest_puts(&uart, "LUNAR_M6 reset=app\r\n");
    lunar_ramtest_reset_to_app(&uart);
    for (;;) {
        native_pause(0, 10u);
        lunar_ramtest_puts(&uart, "LUNAR_M6 stuck beat=");
        lunar_ramtest_putu(&uart, ++beat);
        lunar_ramtest_puts(&uart, "\r\n");
    }
}
