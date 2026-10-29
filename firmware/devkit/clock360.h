/* SPDX-License-Identifier: MIT. Private dev-kit diagnostic. */
#ifndef LUNAR_DEVKIT_CLOCK360_H
#define LUNAR_DEVKIT_CLOCK360_H

#include <stdint.h>

/* Run the AC79 dev kit at the FM-1's stock clock tree and power profile.
 *
 * Raises the core and RF rails to the FM-1's levels, then switches the
 * system clock from the kit's 320 MHz to 360 MHz, so that HSB is 180 MHz and
 * LSB 60 MHz, and prints one LUNAR_CLOCK360 receipt line before and one
 * after. Returns 1 only when every readback matches. Otherwise it prints
 * result=FAIL, puts back what it changed, and returns 0; the caller must
 * then not start audio.
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

#endif
