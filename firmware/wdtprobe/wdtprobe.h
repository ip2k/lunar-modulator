/* SPDX-License-Identifier: MIT
 * K1-K3 watchdog probe image for the AC79 dev kit: portable logic. Register
 * access goes through ramtest's `struct lunar_ramtest_io`, so the host tests
 * record and check every access (tests/test_wdtprobe_image.py). Register
 * facts and their sources are in wdtprobe.c.
 */
#ifndef LUNAR_WDTPROBE_H
#define LUNAR_WDTPROBE_H
#include "../ramtest/ramtest.h"

enum lunar_wdtprobe_mode {
    /* K1/K2: report, clear marker and crumbs, beat WITHOUT kicking; if still
     * alive after `beats`, reset to the application (expect SOFT). */
    LUNAR_WDTPROBE_READ = 1,
    /* K2 control: report, kick every beat, time the M5 pixel loop with a
     * kick per row, reset to the application (expect SOFT). */
    LUNAR_WDTPROBE_KICK = 2,
    /* K1 ROM self-arming: write WDT_CON disarmed with time code 0xB, set the
     * marker and crumbs, P33 reset into the ROM. A READ load reads it next. */
    LUNAR_WDTPROBE_DISARM = 3,
    /* K3: set the marker and crumbs, arm the watchdog (4 s, reset mode) if
     * it is not armed, beat without kicking until it fires. */
    LUNAR_WDTPROBE_MAILBOX = 4
};

enum lunar_wdtprobe_result {
    LUNAR_WDTPROBE_RESET_REQUESTED = 0, /* never seen on hardware */
    LUNAR_WDTPROBE_FAIL_ARGS,
    LUNAR_WDTPROBE_FAIL_P33,
    LUNAR_WDTPROBE_FAIL_TIMER,
    LUNAR_WDTPROBE_FAIL_NO_RESET
};

#define LUNAR_WDTPROBE_CRUMB_A 0x01c07c00u /* in the ROM's loader window */
#define LUNAR_WDTPROBE_CRUMB_B 0x01c7c000u /* Felucca's reset-surviving .noinit */
#define LUNAR_WDTPROBE_MAGIC 0x5444574cu   /* "LWDT" little-endian */
#define LUNAR_WDTPROBE_TIMER_MOD 0x8000u   /* PRD 0x7fff, as M6 */
#define LUNAR_WDTPROBE_TIMER_RUN 0x29u     /* run, OSC source, /16, as M6 */
/* 150,000 ticks: 100 ms if the oscillator is 24 MHz (1.5 MHz ticks). */
#define LUNAR_WDTPROBE_BEAT_TICKS 150000u
/* Poll budget of one beat; a timer that stops counting fails the run. */
#define LUNAR_WDTPROBE_BEAT_POLLS 20000000u
#define LUNAR_WDTPROBE_STALL_POLLS 1000000u
#define LUNAR_WDTPROBE_DISARMED 0x0bu      /* bit 4 clear, distinctive code */
#define LUNAR_WDTPROBE_ARM_4S 0x1cu        /* WDT_4S | enable, reset mode */

/* Read-only P33 byte read (0x80 | addr>>8, addr, 0x5e). 1 on success. */
int lunar_wdtprobe_p33_read(const struct lunar_ramtest_io *io, unsigned address,
                            unsigned *value);
/* P33 byte write (addr>>8, addr, value). Used for P3_WDT_CON and P3_PR_PWR
 * only, by the DISARM and MAILBOX modes. 1 on success. */
int lunar_wdtprobe_p33_write(const struct lunar_ramtest_io *io, unsigned address,
                             unsigned value);
/* Wrap-safe difference of two TIMER4 counts modulo LUNAR_WDTPROBE_TIMER_MOD. */
unsigned lunar_wdtprobe_ticks_between(unsigned then, unsigned now);
/* Runs one mode; returns only on failure or on the host. */
enum lunar_wdtprobe_result lunar_wdtprobe_run(struct lunar_ramtest_io *io, unsigned mode,
                                              const char *build_id, unsigned image_bytes,
                                              unsigned beats);
#endif
