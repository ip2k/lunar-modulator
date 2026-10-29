/* SPDX-License-Identifier: MIT. Private dev-kit diagnostic. */
#ifndef LUNAR_DEVKIT_CLOCK360_H
#define LUNAR_DEVKIT_CLOCK360_H

#include <stdint.h>

/* Run the AC79 dev kit at the FM-1's stock clock tree and power profile.
 *
 * Raises the core and IO rails to the FM-1's levels, then switches the
 * system clock from the kit's 320 MHz to 360 MHz, so that HSB is 180 MHz and
 * LSB 60 MHz, and prints one LUNAR_CLOCK360 receipt line before
 * ("before=-") and one after ("after=PASS" or "after=FAIL"). Returns 1 only
 * when every readback matches; the board then stays at 360 MHz with the
 * stock rails until it is reset. Otherwise it prints "result=FAIL reason=N"
 * and returns 0; the caller must then not start audio. Reasons, before any
 * write: 1 not at 320 MHz / 160 MHz HSB, 2 PLL source not 6, 3 bus dividers
 * not HSB /2 and LSB /3, 4 OS tick not 10 ms, 5 UART clock not 48 MHz,
 * 6 DCDC off. After a write: 7 a rail did not read back at the stock level
 * (rails put back, clock untouched); 8 a readback failed at 360 MHz, the
 * clock read back at 320/160 MHz after the restore and the kit's rails were
 * put back ("restored=OK rails=kit"); 9 as 8, but the clock did not read
 * back at 320/160 MHz, so the stock rails were kept ("restored=FAIL
 * rails=kept"). Reset the board after any run.
 *
 * Call it from a task, before the DAC is opened: the SDK refuses a clock
 * change while the DAC runs. now() is the 24 MHz TIMER4 counter, already
 * running. Built only by tools/jieli/prepare-pipeline-devkit.py --sys-clk
 * 360; clock360.c gives the evidence behind each register write. */
int lunar_clock360_apply(uint32_t (*now)(void));

/* Audio-rate check over a window of DAC callbacks (64 frames each), timed
 * by TIMER4. Prints the measured rate; returns 1 when it is within 0.5 % of
 * 44,100 Hz, else prints result=FAIL and returns 0. */
int lunar_clock360_audio_rate(const char *window, uint32_t callbacks, uint32_t ticks);

/* End-of-run readback, after the soak: clk_get sys/hsb/lsb/sfc, the raw SFC
 * BAUD, the rails and the OS tick, as one "end=PASS" or "end=FAIL" line
 * (PASS: still the FM-1's clock tree and rails). Prints only. */
void lunar_clock360_end(uint32_t (*now)(void));

#endif
