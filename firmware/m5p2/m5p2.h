/* SPDX-License-Identifier: MIT
 * m5-plan-2: the successor to the M5 RAM image (firmware/m5). Portable logic;
 * every register and SRAM access goes through `struct lunar_m5p2_io`, so the
 * host tests (tests/test_m5p2_image.py) record the whole sequence, model the
 * time between watchdog kicks, and check the register allow-list.
 *
 * What changed from M5, and why (notes/2026-11-14-m5-plan-2.md):
 *   - the ROM's 4 s watchdog is cleared at entry, in every wait slice
 *     (10 ms or less), on every pixel row, between spin units and in the
 *     blink loop (lunar_ramtest_wdt_kick, verified on the dev kit);
 *   - PA2 (backlight, active low) is driven before TIMER4 or the panel, and
 *     flashes a cadence that measures the FM-1's clocks without a UART;
 *   - display-on (0x29) is sent right after the panel setup, before the
 *     frame;
 *   - SRAM breadcrumbs at LUNAR_M5P2_CRUMBS, inside the 16 KiB window.
 * The configuration (kit stubs, UART trace, mailbox, finish) is chosen by
 * main.c, so this object is the same in every build.
 */
#ifndef LUNAR_M5P2_H
#define LUNAR_M5P2_H

#include "../ramtest/ramtest.h"

struct lunar_m5p2_io {
    /* read/write/sync/uart_failed as ramtest; pause only after a reset request. */
    struct lunar_ramtest_io base;
    /* Busy loop of `iterations` volatile increments; uncalibrated. */
    void (*spin)(void *, unsigned iterations);
};

enum lunar_m5p2_finish {
    LUNAR_M5P2_FOREVER = 0,     /* FM-1 default: kick and blink until power-off */
    LUNAR_M5P2_STOP_KICKING,    /* mailbox: stop kicking; the armed watchdog resets */
    LUNAR_M5P2_RESET_APP        /* kit: P33 soft reset into the application */
};

struct lunar_m5p2_config {
    const char *build_id;
    unsigned stub_pins; /* kit: PORTA/PORTB/PORTH/PORTC/IOMAP_CON1/SPI1 dropped, counted */
    unsigned trace;     /* kit: UART1 TX on PB3, 1,000,000 baud, as ramtest */
    unsigned mailbox;   /* write the "usb_update_mode" marker at entry */
    unsigned finish;    /* enum lunar_m5p2_finish */
    /* Nominal milliseconds (at the 40 MHz binding) after which `finish`
     * happens; 0 = never (only meaningful with LUNAR_M5P2_FOREVER). */
    unsigned finish_ms;
    /* After STOP_KICKING: heartbeat lines (trace only) before returning. */
    unsigned beats;
};

enum lunar_m5p2_stage {
    LUNAR_M5P2_ENTRY = 1,      /* first kick done, crumbs written */
    LUNAR_M5P2_PA2_ON,         /* PA2 driven low: backlight on */
    LUNAR_M5P2_TIMER_OK,       /* TIMER4 counts */
    LUNAR_M5P2_TIMER_DEAD,     /* TIMER4 stalled: spin waits from here on */
    LUNAR_M5P2_MEASURED,       /* ticks per spin block recorded */
    LUNAR_M5P2_CADENCE_A,      /* three TIMER4-timed PA2 flashes done */
    LUNAR_M5P2_CADENCE_B,      /* three spin-timed PA2 flashes done */
    LUNAR_M5P2_SPI_OK,         /* SPI1 configured */
    LUNAR_M5P2_SETUP_OK,       /* sleep-out and the V15 setup sent */
    LUNAR_M5P2_DISPLAY_ON,     /* 0x29 sent */
    LUNAR_M5P2_FRAME_DONE,     /* 240x240 pixel stream sent without error */
    LUNAR_M5P2_BLINKING,       /* matrix up, LED blink loop running */
    LUNAR_M5P2_FINISHING       /* about to stop kicking or reset */
};

/* Breadcrumbs: twelve words at a fixed address in the RAM window, above the
 * stacks (app.ld asserts it). Word 0 magic, word 11 its complement. */
#define LUNAR_M5P2_CRUMBS 0x01c05fc0u
#define LUNAR_M5P2_CRUMB_WORDS 12u
#define LUNAR_M5P2_MAGIC 0x3250354du /* "M5P2" little-endian */
enum lunar_m5p2_crumb {
    LUNAR_M5P2_C_MAGIC = 0,
    LUNAR_M5P2_C_STAGE,         /* last enum lunar_m5p2_stage reached */
    LUNAR_M5P2_C_WDT_CON,       /* P3_WDT_CON as read by the first kick */
    LUNAR_M5P2_C_TICKS_PER_BLOCK, /* TIMER4 ticks over LUNAR_M5P2_BLOCK spins */
    LUNAR_M5P2_C_MAX_GAP,       /* longest kick-to-kick gap, TIMER4 ticks */
    LUNAR_M5P2_C_KICKS,
    LUNAR_M5P2_C_KICK_FAILURES,
    LUNAR_M5P2_C_PANEL,         /* enum lunar_panel_result, 0xff if not run */
    LUNAR_M5P2_C_ELAPSED_MS,    /* nominal ms waited (40 MHz binding) */
    LUNAR_M5P2_C_CYCLES,        /* blink cycles completed */
    LUNAR_M5P2_C_TICKS,         /* TIMER4 ticks since the stopwatch started */
    LUNAR_M5P2_C_CHECK          /* ~magic */
};

/* TIMER4 as M6's and wdtprobe's stopwatch: CON 0x29 (run, OSC, /16),
 * PRD 0x7fff. The waits assume a 40 MHz oscillator: 2,500 ticks per ms. A
 * slower oscillator only makes them longer (1.67x at 24 MHz). */
#define LUNAR_M5P2_TICKS_PER_MS 2500u
#define LUNAR_M5P2_SLICE_MS 10u          /* longest wait between two kicks */
#define LUNAR_M5P2_STALL_POLLS 4096u     /* same CNT this often: TIMER4 is dead */
#define LUNAR_M5P2_SLICE_POLLS 262144u   /* backstop for one 10 ms slice */
#define LUNAR_M5P2_SPIN_UNIT 100000u     /* spins between kicks in spin waits */
#define LUNAR_M5P2_SPIN_CHUNK 1000u      /* spins between TIMER4 polls when measuring */
#define LUNAR_M5P2_BLOCK 200000u         /* the measured spin block */
#define LUNAR_M5P2_SPIN_PER_MS 20000u    /* dead-timer fallback, uncalibrated (as M5) */
#define LUNAR_M5P2_FLASH_MS 400u         /* cadence A half-period, nominal */
#define LUNAR_M5P2_FLASH_UNITS 40u       /* cadence B half-period, in spin units */
#define LUNAR_M5P2_SPI_POLLS 4096u       /* per SPI1 byte phase */

enum lunar_m5p2_result {
    LUNAR_M5P2_RETURNED = 0, /* finish_ms reached with FOREVER (host only) */
    LUNAR_M5P2_FAIL_ARGS,
    LUNAR_M5P2_STOPPED,      /* STOP_KICKING: kicks stopped, beats done */
    LUNAR_M5P2_RESET_FAILED  /* RESET_APP returned: the reset did not happen */
};

/* Runs the whole sequence. With FOREVER and finish_ms 0 it never returns. */
enum lunar_m5p2_result lunar_m5p2_run(struct lunar_m5p2_io *io,
                                      const struct lunar_m5p2_config *config);
/* The panel label: build id, P3_WDT_CON at entry (2 hex digits) and ticks
 * per block (5 hex digits), space separated, cut to `size - 1` characters. */
void lunar_m5p2_label(char *out, unsigned size, const char *build_id,
                      unsigned wdt_con, unsigned ticks_per_block);
#endif
