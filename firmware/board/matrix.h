/* SPDX-License-Identifier: MIT
 * Independently authored FM-1 key/encoder/LED matrix driver. Pin facts and
 * their sources are in firmware/board/README.md; no GPL code was copied.
 */
#ifndef LUNAR_MATRIX_H
#define LUNAR_MATRIX_H
#include "board_io.h"

/* Port bits (bit n = pin Pxn). */
#define LUNAR_595_LATCH (1u << 1)   /* PA1 */
#define LUNAR_595_CLOCK (1u << 3)   /* PA3 */
#define LUNAR_595_DATA (1u << 4)    /* PA4 */
#define LUNAR_ROWS_PA ((1u << 0) | (0xfu << 5)) /* PA0, PA5-PA8 */
#define LUNAR_ROWS_PB (1u << 7)                 /* PB7 */
#define LUNAR_LED_PA ((1u << 9) | (1u << 10))   /* PA9, PA10 */
#define LUNAR_LED_PH ((1u << 6) | (1u << 9))    /* PH6, PH9 */
#define LUNAR_BACKLIGHT_PA (1u << 2)            /* PA2, active low */

/* LED line mask: bit0 PA9, bit1 PA10, bit2 PH6, bit3 PH9. A line lights its
 * LED only while a column is selected [reported]. */
#define LUNAR_LED_LINES 0xfu

/* 16-bit word shifted MSB first into the two 595s to select one column,
 * active low; columns 0 and 1 also pull outputs 11 and 12 low [reported]. */
unsigned lunar_matrix_word(unsigned column);

/* Configure the 595 pins, row inputs (pull-up) and LED lines (high drive,
 * off), then shift an all-high word so no column is selected. */
int lunar_matrix_init(const struct lunar_board_io *io);
/* LEDs off, shift the column word with read-modify-write edges, sample the
 * rows (packed as in fm1_keys.h), then light `leds` (LUNAR_LED_LINES bits).
 * Returns the packed row sample, or 0xff for a bad column/io. */
unsigned lunar_matrix_select(const struct lunar_board_io *io, unsigned column, unsigned leds);
/* One pass over all 11 columns; LEDs of the last column stay lit. */
int lunar_matrix_scan(const struct lunar_board_io *io, const unsigned char leds[11],
                      unsigned char rows[11]);
/* As lunar_matrix_scan, but a column that has an LED lit stays selected for
 * `dwell_us` microseconds (dwell(context, us), caller-supplied, bounded) with
 * its LEDs on, so every lit LED gets the same on-time instead of the last
 * column getting the task's whole sleep. Every column's LEDs are off again
 * when the call returns. */
typedef void (*lunar_matrix_dwell_fn)(void *context, unsigned microseconds);
int lunar_matrix_scan_lit(const struct lunar_board_io *io, const unsigned char leds[11],
                          unsigned char rows[11], lunar_matrix_dwell_fn dwell, void *context,
                          unsigned dwell_us);
/* LEDs off and no column selected. */
void lunar_matrix_release(const struct lunar_board_io *io);

/* PA2 output low. Its role (backlight, reset or enable) is reported, not
 * established; stock and fm1-nes both drive it low before panel output. */
void lunar_backlight_on(const struct lunar_board_io *io);
void lunar_backlight_off(const struct lunar_board_io *io);
#endif
