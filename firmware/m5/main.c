/* SPDX-License-Identifier: MIT
 * M5 test-pattern entry: RAM-only, SDK-free, interrupts masked, built but NOT
 * run. Order: core check, PA2 low, take TIMER4, SPI1 + panel pattern with the
 * build id, then the matrix with an LED blink code = the last step reached.
 * Known unknowns are in notes/2026-11-08-fm1-board-layer.md.
 */
#include "../board/board_io.h"
#include "../board/matrix.h"
#include "../display/m5_pattern.h"
#include "../display/spi1_transport.h"
#include "../third_party/fm1-nes/fm1_keys.h"
#include "../timing/timer4.h"

#ifndef LUNAR_BUILD_ID
#define LUNAR_BUILD_ID "UNKNOWN"
#endif
#define M5_MAGIC 0x5054354du /* "M5TP" little-endian */
/* TIMER4's oscillator is 24 MHz under ROM/UBOOT [reported: Felucca], and
 * stock V15 chooses 24 or 40 MHz [verified: timing/README.md]. Binding at the
 * 40 MHz upper bound makes every delay at least as long as requested for any
 * oscillator up to 40 MHz (1.67x long at 24 MHz): panel waits never fall short. */
#define OSC_HZ 40000000u
#define POLLS 65536u
#define SPIN_PER_MS 20000u   /* uncalibrated fallback only */

enum m5_step {
    M5_STARTED = 1, M5_CORE_OK, M5_TIMER_OK, M5_SPI_OK, M5_PATTERN_OK, M5_MATRIX_OK
};

/* Read it with a debugger: the map file gives its address. */
struct lunar_m5_status {
    unsigned magic, step, core, timer_con_before, panel_result, timer_fallback;
    unsigned blink_cycles, pressed[2];
    unsigned char rows[LUNAR_MATRIX_COLUMNS];
    char build_id[LUNAR_M5_ID_MAX + 1];
};
volatile struct lunar_m5_status lunar_m5_status;
static const char build_id[] = LUNAR_BUILD_ID;

extern unsigned __bss_begin[], __bss_end[];

static struct lunar_board_io board;
static struct lunar_timer_io timer_io;
static struct lunar_timer timer;
static struct lunar_spi1_io spi_io;
static struct lunar_spi1 spi;
static struct lunar_panel_transport panel;
static unsigned timer_ok;

static void spin(unsigned milliseconds)
{
    volatile unsigned i;
    while (milliseconds--)
        for (i = 0; i < SPIN_PER_MS; ++i) {}
}

/* TIMER4 when it works; after its first failure (for example a poll budget
 * that runs out before a 40,000-tick period), an uncalibrated spin. */
static void wait_ms(unsigned milliseconds)
{
    if (timer_ok && lunar_timer_delay(&timer, milliseconds)) return;
    timer_ok = 0;
    lunar_m5_status.timer_fallback = 1;
    spin(milliseconds);
}

/* Panel waits use the same fallback, so a timer failure cannot abort the
 * SPI transport (spi1_transport.c latches failure when wait_ms returns 0). */
static int panel_delay(void *context, unsigned milliseconds)
{
    (void)context;
    wait_ms(milliseconds);
    return 1;
}

/* Hold every column for 1 ms with `leds` lit, sampling the rows. */
static void hold(unsigned milliseconds, unsigned leds)
{
    unsigned column = 0;
    unsigned char rows[LUNAR_MATRIX_COLUMNS];
    unsigned pressed[2];
    while (milliseconds--) {
        unsigned i;
        rows[column] = (unsigned char)lunar_matrix_select(&board, column, leds);
        lunar_m5_status.rows[column] = rows[column];
        if (++column == LUNAR_MATRIX_COLUMNS) {
            column = 0;
            lunar_keys_decode(rows, pressed);
            for (i = 0; i < 2; ++i) lunar_m5_status.pressed[i] = pressed[i];
        }
        wait_ms(1);
    }
    lunar_matrix_release(&board);
}

void lunar_m5_main(void)
{
    unsigned core, i;
    volatile unsigned *word;
    /* The loader does not clear BSS; volatile keeps this a plain loop. */
    for (word = __bss_begin; word < __bss_end; ++word) *word = 0;
    lunar_m5_status.magic = M5_MAGIC;
    lunar_m5_status.step = M5_STARTED;
    for (i = 0; i < LUNAR_M5_ID_MAX && build_id[i]; ++i) lunar_m5_status.build_id[i] = build_id[i];

    __asm__ volatile("%0 = cnum;" : "=r"(core));
    lunar_m5_status.core = core;
    if (core != 0) for (;;) {} /* Only core 0 runs this image. */
    lunar_m5_status.step = M5_CORE_OK;

    lunar_board_native_io(&board);
    lunar_backlight_on(&board);

    /* After entry this image owns the machine. TIMER4 may have been left
     * running by ROM/UBOOT [reported]; stop it (and clear its pending flag)
     * because lunar_timer_delay refuses an enabled timer. */
    lunar_timer_native_io(&timer_io);
    lunar_m5_status.timer_con_before = timer_io.read(0, LUNAR_TIMER_CON);
    timer_io.write(0, LUNAR_TIMER_CON, 1u << 14);
    timer_io.sync(0);
    timer_ok = (unsigned)lunar_timer_bind(&timer, &timer_io, OSC_HZ, POLLS);
    if (timer_ok) lunar_m5_status.step = M5_TIMER_OK;

    lunar_spi1_native_io(&spi_io, 0, panel_delay);
    lunar_m5_status.panel_result = 0xffu;
    if (lunar_spi1_bind(&spi, &spi_io, POLLS, &panel) &&
        lunar_spi1_configure(&spi)) {
        lunar_m5_status.step = M5_SPI_OK;
        lunar_m5_status.panel_result = lunar_panel_m5_pattern(&panel, build_id);
        if (lunar_m5_status.panel_result == LUNAR_PANEL_OK) lunar_m5_status.step = M5_PATTERN_OK;
    }

    if (lunar_matrix_init(&board) && lunar_m5_status.step == M5_PATTERN_OK)
        lunar_m5_status.step = M5_MATRIX_OK;

    /* Blink code: `step` blinks of every LED line, then a pause, forever.
     * Six blinks means every step above succeeded. */
    for (;;) {
        unsigned n;
        for (n = 0; n < lunar_m5_status.step; ++n) {
            hold(200, LUNAR_LED_LINES);
            hold(200, 0);
        }
        hold(1000, 0);
        ++lunar_m5_status.blink_cycles;
    }
}
