/* SPDX-License-Identifier: MIT
 * Independently authored. Facts used (README.md): 595 pins PA4/PA3/PA1, rows
 * PA0/PA5-PA8/PB7 active low with pull-ups, LED lines PA9/PA10/PH6/PH9 active
 * high, per-edge read-modify-write because write-only edges were reported too
 * short and latched the neighbouring column.
 */
#include "matrix.h"
#include "../third_party/fm1-nes/fm1_keys.h"

#define PA(field) ((enum lunar_board_register)(LUNAR_PA + (field)))
#define PB(field) ((enum lunar_board_register)(LUNAR_PB + (field)))
#define PH(field) ((enum lunar_board_register)(LUNAR_PH + (field)))
#define SHIFT_PINS (LUNAR_595_LATCH | LUNAR_595_CLOCK | LUNAR_595_DATA)

unsigned lunar_matrix_word(unsigned column)
{
    unsigned word = 0xffffu ^ (1u << column);
    if (column < 2u) word ^= 1u << (11u + column);
    return word;
}

static void leds_off(const struct lunar_board_io *io)
{
    lunar_board_change(io, PA(LUNAR_OUT), LUNAR_LED_PA, 0);
    lunar_board_change(io, PH(LUNAR_OUT), LUNAR_LED_PH, 0);
}

static void leds_on(const struct lunar_board_io *io, unsigned leds)
{
    unsigned pa = ((leds & 1u) ? (1u << 9) : 0) | ((leds & 2u) ? (1u << 10) : 0);
    unsigned ph = ((leds & 4u) ? (1u << 6) : 0) | ((leds & 8u) ? (1u << 9) : 0);
    if (pa) lunar_board_change(io, PA(LUNAR_OUT), 0, pa);
    if (ph) lunar_board_change(io, PH(LUNAR_OUT), 0, ph);
}

static void shift(const struct lunar_board_io *io, unsigned word)
{
    unsigned bit = 16;
    while (bit--) {
        unsigned data = (word >> bit) & 1u;
        lunar_board_change(io, PA(LUNAR_OUT), data ? 0 : LUNAR_595_DATA, data ? LUNAR_595_DATA : 0);
        lunar_board_change(io, PA(LUNAR_OUT), 0, LUNAR_595_CLOCK);
        lunar_board_change(io, PA(LUNAR_OUT), LUNAR_595_CLOCK, 0);
    }
    lunar_board_change(io, PA(LUNAR_OUT), 0, LUNAR_595_LATCH);
    lunar_board_change(io, PA(LUNAR_OUT), LUNAR_595_LATCH, 0);
    io->sync(io->context);
}

int lunar_matrix_init(const struct lunar_board_io *io)
{
    if (!lunar_board_io_valid(io)) return 0;
    /* Inactive output levels before directions: latch/clock low, data high,
     * LED lines off. DIR bit 1 = input on WL82. */
    lunar_board_change(io, PA(LUNAR_OUT), LUNAR_595_LATCH | LUNAR_595_CLOCK | LUNAR_LED_PA,
                       LUNAR_595_DATA);
    lunar_board_change(io, PH(LUNAR_OUT), LUNAR_LED_PH, 0);
    lunar_board_change(io, PA(LUNAR_DIR), SHIFT_PINS | LUNAR_LED_PA, LUNAR_ROWS_PA);
    lunar_board_change(io, PH(LUNAR_DIR), LUNAR_LED_PH, 0);
    lunar_board_change(io, PA(LUNAR_HD0), 0, LUNAR_LED_PA);
    lunar_board_change(io, PA(LUNAR_HD), 0, LUNAR_LED_PA);
    lunar_board_change(io, PH(LUNAR_HD0), 0, LUNAR_LED_PH);
    lunar_board_change(io, PH(LUNAR_HD), 0, LUNAR_LED_PH);
    lunar_board_change(io, PA(LUNAR_PD), LUNAR_ROWS_PA, 0);
    lunar_board_change(io, PA(LUNAR_PU), 0, LUNAR_ROWS_PA);
    lunar_board_change(io, PA(LUNAR_DIE), 0, LUNAR_ROWS_PA);
    lunar_board_change(io, PB(LUNAR_DIR), 0, LUNAR_ROWS_PB);
    lunar_board_change(io, PB(LUNAR_PD), LUNAR_ROWS_PB, 0);
    lunar_board_change(io, PB(LUNAR_PU), 0, LUNAR_ROWS_PB);
    lunar_board_change(io, PB(LUNAR_DIE), 0, LUNAR_ROWS_PB);
    shift(io, 0xffffu);
    return 1;
}

unsigned lunar_matrix_select(const struct lunar_board_io *io, unsigned column, unsigned leds)
{
    unsigned rows;
    if (!lunar_board_io_valid(io) || column >= LUNAR_MATRIX_COLUMNS) return 0xffu;
    leds_off(io);
    shift(io, lunar_matrix_word(column));
    /* No settle delay between the latch and the row read: the 595 output and
     * the row pull-ups are assumed to settle within the sync and the register
     * access. [hardware-unverified]: if a first run shows ghost or smeared
     * keys, add a short bounded settle here (a few dummy reads of PORTA IN). */
    rows = lunar_keys_pack(io->read(io->context, PA(LUNAR_IN)),
                           io->read(io->context, PB(LUNAR_IN)));
    leds_on(io, leds & LUNAR_LED_LINES);
    return rows;
}

int lunar_matrix_scan(const struct lunar_board_io *io, const unsigned char leds[11],
                      unsigned char rows[11])
{
    unsigned column;
    if (!lunar_board_io_valid(io) || !rows) return 0;
    for (column = 0; column < LUNAR_MATRIX_COLUMNS; ++column)
        rows[column] = (unsigned char)lunar_matrix_select(io, column, leds ? leds[column] : 0);
    return 1;
}

int lunar_matrix_scan_lit(const struct lunar_board_io *io, const unsigned char leds[11],
                          unsigned char rows[11], lunar_matrix_dwell_fn dwell, void *context,
                          unsigned dwell_us)
{
    unsigned column;
    if (!lunar_board_io_valid(io) || !rows) return 0;
    for (column = 0; column < LUNAR_MATRIX_COLUMNS; ++column) {
        unsigned lit = leds ? (leds[column] & LUNAR_LED_LINES) : 0;
        rows[column] = (unsigned char)lunar_matrix_select(io, column, lit);
        if (lit && dwell) dwell(context, dwell_us);
    }
    lunar_matrix_release(io);
    return 1;
}

void lunar_matrix_release(const struct lunar_board_io *io)
{
    if (!lunar_board_io_valid(io)) return;
    leds_off(io);
    shift(io, 0xffffu);
}

void lunar_backlight_on(const struct lunar_board_io *io)
{
    if (!lunar_board_io_valid(io)) return;
    lunar_board_change(io, PA(LUNAR_OUT), LUNAR_BACKLIGHT_PA, 0);
    lunar_board_change(io, PA(LUNAR_DIR), LUNAR_BACKLIGHT_PA, 0);
    io->sync(io->context);
}

void lunar_backlight_off(const struct lunar_board_io *io)
{
    if (!lunar_board_io_valid(io)) return;
    lunar_board_change(io, PA(LUNAR_OUT), 0, LUNAR_BACKLIGHT_PA);
    lunar_board_change(io, PA(LUNAR_DIR), LUNAR_BACKLIGHT_PA, 0);
    io->sync(io->context);
}
