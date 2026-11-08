/* SPDX-License-Identifier: MIT
 * Independently authored. CON layout [verified: SDK adc_api.c adc_sample]:
 * bits 0-2 clock divider (0b110 = /96), bit 3 set by the SDK, bit 4 enable,
 * bit 5 interrupt enable (left off here), bit 6 start/clear, bit 7 done,
 * bits 8-11 channel, bits 12-15 start delay (0xf).
 */
#include "adc.h"

#define EN (1u << 4)
#define IE (1u << 5)
#define KICK (1u << 6)
#define DONE (1u << 7)
#define PINS ((1u << 1) | (1u << 6)) /* PB1 battery, PB6 MASTER */
#define PB(field) ((enum lunar_board_register)(LUNAR_PB + (field)))

int lunar_adc_init(struct lunar_adc *s, const struct lunar_board_io *io, unsigned limit)
{
    if (!s || !lunar_board_io_valid(io) || !limit || limit > 65536u) return 0;
    s->io = io;
    s->poll_limit = limit;
    s->ready = 0;
    s->failed = 0;
    if (io->read(io->context, LUNAR_ADC_CON) & (EN | IE)) {
        s->failed = 1;
        return 0;
    }
    lunar_board_change(io, PB(LUNAR_DIR), 0, PINS);
    lunar_board_change(io, PB(LUNAR_DIE), PINS, 0);
    lunar_board_change(io, PB(LUNAR_PU), PINS, 0);
    lunar_board_change(io, PB(LUNAR_PD), PINS, 0);
    lunar_board_change(io, PB(LUNAR_DIEH), PINS, 0);
    /* SDK __adc_init: SYSPLL1 test off; RWF bias on, IGEN 2, test outputs
     * off, TEST_TO_ADC_S 0b100; TEST_TO_ADC_EN (bit 14) off for GPIO channels. */
    lunar_board_change(io, LUNAR_ANA_PLL_CON1, 1u << 16, 0);
    lunar_board_change(io, LUNAR_ANA_WLA_CON0, 0x3c0ffu, 0x20005u);
    io->write(io->context, LUNAR_ADC_CON, 0);
    io->sync(io->context);
    s->ready = 1;
    return 1;
}

static void stop(struct lunar_adc *s)
{
    s->io->write(s->io->context, LUNAR_ADC_CON, KICK);
    s->io->write(s->io->context, LUNAR_ADC_CON, 0);
}

int lunar_adc_read(struct lunar_adc *s, unsigned channel, unsigned *value)
{
    unsigned i, raw;
    if (!s || !s->ready || s->failed || !value ||
        (channel != LUNAR_ADC_BATTERY && channel != LUNAR_ADC_MASTER)) return 0;
    s->io->write(s->io->context, LUNAR_ADC_CON,
                 (0xfu << 12) | (channel << 8) | KICK | (1u << 3) | 6u);
    lunar_board_change(s->io, LUNAR_ADC_CON, 0, EN);
    lunar_board_change(s->io, LUNAR_ADC_CON, 0, KICK);
    s->io->sync(s->io->context);
    for (i = 0; i < s->poll_limit; ++i)
        if (s->io->read(s->io->context, LUNAR_ADC_CON) & DONE) break;
    if (i == s->poll_limit) {
        stop(s);
        s->failed = 1;
        return 0;
    }
    raw = s->io->read(s->io->context, LUNAR_ADC_RES);
    stop(s);
    if (raw > 1023u) {
        s->failed = 1;
        return 0;
    }
    *value = raw;
    return 1;
}

void lunar_pot_reset(struct lunar_pot *p)
{
    if (p) p->accepted = p->debounce = p->level = 0;
}

int lunar_pot_update(struct lunar_pot *p, unsigned raw)
{
    int delta;
    if (!p || raw > 1023u) return 0;
    delta = (int)raw - (int)p->accepted;
    if (delta >= -6 && delta <= 6) {
        p->debounce = 0;
        return 0;
    }
    if (++p->debounce < 10u) return 0;
    p->debounce = 0;
    if ((raw >> 3) == (p->accepted >> 3)) return 0;
    p->accepted = raw;
    p->level = raw >> 3;
    return 1;
}
