/* SPDX-License-Identifier: MIT. Private dev-kit diagnostic. */
#ifndef LUNAR_DEVKIT_CLOCK360_H
#define LUNAR_DEVKIT_CLOCK360_H

#include <stdint.h>

/* The dev kit at the FM-1's clock and power profile: NOT AVAILABLE.
 *
 * In every kit build (2026-10-29) this reads and prints the kit's clock
 * tree, rails and OS tick ("before=-") and its PLL/SDRAM registers
 * ("pll=-"), checks the state, and returns 0 having written nothing: the
 * kit boots on a fixed 320 MHz tap, and no reviewed run-time path from it
 * to 360 MHz exists (clock360.c gives the evidence). The caller must then
 * not start audio. It prints "result=FAIL reason=N":
 *  1 not at 320 MHz / 160 MHz HSB;
 *  2 CLK_CON2[7:0] is not 2, the kit's fixed 320 MHz tap with both
 *    post-dividers /1 (in the host switch model: PLL source not 6);
 *  3 bus dividers not HSB /2 and LSB /3; 4 OS tick not 10 ms;
 *  5 UART clock not 48 MHz; 6 DCDC off;
 *  10 the kit is in the analysed state and no reviewed switch exists
 *    (the expected result of a kit run).
 * 7-9 exist only in the host model of the 2026-10-28 switch
 * (LUNAR_DEVKIT_CLOCK360_SWITCH, which cannot be built for the kit):
 *  7 a rail did not read back at the stock level (rails put back, clock
 *    untouched); 8 a readback failed at 360 MHz, the clock read back at
 *    320/160 MHz after the restore and the kit's rails were put back
 *    ("restored=OK rails=kit"); 9 as 8, but the clock did not read back at
 *    320/160 MHz, so the stock rails were kept ("restored=FAIL rails=kept").
 *
 * Call it from a task, before the DAC is opened. now() is the 24 MHz TIMER4
 * counter, already running. Built only by tools/jieli/prepare-pipeline-devkit.py
 * --sys-clk 360. */
int lunar_clock360_apply(uint32_t (*now)(void));

/* Audio-rate check over the preroll's DAC callbacks (64 frames each), timed
 * by TIMER4. Prints the measured rate as one "audio=preroll" line; returns 1
 * when it is within 0.5 % of 44,100 Hz, else prints result=FAIL and
 * returns 0. */
int lunar_clock360_audio_rate(uint32_t callbacks, uint32_t ticks);

/* End-of-run readback, after the DAC run returns: clk_get sys/hsb/lsb/sfc,
 * the raw SFC BAUD, the rails and the OS tick, as one "end=-" line in the
 * receipt format. Prints only; tools/devkit_pipeline_result.py judges it
 * against the after line. */
void lunar_clock360_end(uint32_t (*now)(void));

#endif
