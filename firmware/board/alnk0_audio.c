/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Lunar Modulator contributors
 *
 * ALNK0 bring-up for the FM-1. Written from the facts table in
 * notes/2026-11-08-alnk0-codec-driver.md (F1..F22); the order follows the
 * Apache-2.0 AC79 SDK driver's. No GPL code was used.
 */
#include "alnk0_audio.h"

#include <stddef.h>

/* CON0 bits (F5-F8, F12, F17) */
#define CON0_MASTER       (1u << 7)
#define CON0_MCLK_OUT     (1u << 8)
#define CON0_BIT6         (1u << 6)  /* cleared by every source; meaning unknown */
#define CON0_ENABLE       (1u << 11)
#define CON0_HALF(ch)     (1u << (12u + (ch)))
/* CON1 per-channel nibble (F10) */
#define CON1_EN(ch)       (1u << (4u * (ch)))
#define CON1_24BIT(ch)    (1u << (4u * (ch) + 2u))
#define CON1_DIR_IN(ch)   (1u << (4u * (ch) + 3u))
/* CON3 (F5, F13) */
#define CON3_MASTER_CLK   0x03u
#define CON3_DIV_MASK     0x1Cu
#define CON3_RATE_KEEP    0x1Fu
#define CON3_RATE_44K1    (4u << 5)
/* CLK_CON2, ALNK0's bits only (F13) */
#define CLK_ALNK0_48K     (1u << 8)
#define CLK_ALNK0_BIT9    (1u << 9)
#define IOMAP_ALNK0_PORT  0xC0u      /* both clear = port group C (F3) */

static uint32_t rd(const struct lunar_alnk0_ops *ops, uint32_t a, unsigned n)
{
    return ops->read(ops->context, a, n);
}

static void wr(const struct lunar_alnk0_ops *ops, uint32_t a, unsigned n, uint32_t v)
{
    ops->write(ops->context, a, n, v);
}

static void set_bits(const struct lunar_alnk0_ops *ops, uint32_t a, unsigned n, uint32_t m)
{
    wr(ops, a, n, rd(ops, a, n) | m);
}

static void clear_bits(const struct lunar_alnk0_ops *ops, uint32_t a, unsigned n, uint32_t m)
{
    wr(ops, a, n, rd(ops, a, n) & ~m);
}

void lunar_alnk0_default_config(struct lunar_alnk0_config *config,
                                int32_t *buffer, uint32_t dma_address)
{
    config->buffer = buffer;
    config->dma_address = dma_address;
    config->half_words = LUNAR_ALNK0_HALF_WORDS;
    config->irq_priority = LUNAR_ALNK0_IRQ_PRIORITY;
    config->settle_ms = LUNAR_ALNK0_SETTLE_MS;
}

int lunar_alnk0_validate(const struct lunar_alnk0_ops *ops,
                         const struct lunar_alnk0_config *config)
{
    if (ops == NULL || ops->read == NULL || ops->write == NULL ||
        ops->sync == NULL || ops->attach_irq == NULL)
        return LUNAR_ALNK0_EINVAL;
    if (config == NULL || config->buffer == NULL)
        return LUNAR_ALNK0_EINVAL;
    if (config->dma_address == 0u || (config->dma_address % LUNAR_ALNK0_ALIGN) != 0u)
        return LUNAR_ALNK0_EINVAL;
    /* LEN counts words per half; a stereo frame is two words */
    if (config->half_words < 2u || (config->half_words & 1u) != 0u)
        return LUNAR_ALNK0_EINVAL;
    if (config->irq_priority > 7u)
        return LUNAR_ALNK0_EINVAL;
    if (config->settle_ms != 0u && ops->delay_ms == NULL)
        return LUNAR_ALNK0_EINVAL;
    return LUNAR_ALNK0_OK;
}

int lunar_alnk0_start(const struct lunar_alnk0_ops *ops,
                      const struct lunar_alnk0_config *config)
{
    const unsigned ch = LUNAR_ALNK0_TX_CH;
    uint32_t i, words;
    int rc = lunar_alnk0_validate(ops, config);
    if (rc != LUNAR_ALNK0_OK)
        return rc;

    /* 1. ALNK0 on port group C */
    clear_bits(ops, LUNAR_IOMAP_CON5, 4, IOMAP_ALNK0_PORT);

    /* 2. a known state; CON2 holds write-1 acknowledges and is left alone */
    wr(ops, LUNAR_ALNK0_CON0, 2, 0);
    wr(ops, LUNAR_ALNK0_CON1, 2, 0);
    wr(ops, LUNAR_ALNK0_CON3, 1, 0);
    wr(ops, LUNAR_ALNK0_LEN, 2, 0);
    for (i = 0; i < 4u; i++)
        wr(ops, LUNAR_ALNK0_ADR(i), 4, 0);

    /* 3. master, MCLK out; 64 bit clocks per frame (bits 9, 10 stay clear) */
    set_bits(ops, LUNAR_ALNK0_CON3, 1, CON3_MASTER_CLK);
    set_bits(ops, LUNAR_ALNK0_CON0, 2, CON0_MASTER);
    set_bits(ops, LUNAR_ALNK0_CON0, 2, CON0_MCLK_OUT);
    clear_bits(ops, LUNAR_ALNK0_CON0, 2, CON0_BIT6);

    /* 4. PC0, PC1, PC2, PC6: output low, no pulls, until ALNK0 drives them */
    clear_bits(ops, LUNAR_PORTC_OUT, 4, LUNAR_ALNK0_PORTC_PINS);
    clear_bits(ops, LUNAR_PORTC_DIR, 4, LUNAR_ALNK0_PORTC_PINS);
    clear_bits(ops, LUNAR_PORTC_PD, 4, LUNAR_ALNK0_PORTC_PINS);
    clear_bits(ops, LUNAR_PORTC_PU, 4, LUNAR_ALNK0_PORTC_PINS);

    /* 5. channel 3 transmits 24-bit words */
    clear_bits(ops, LUNAR_ALNK0_CON1, 2, CON1_DIR_IN(ch));
    set_bits(ops, LUNAR_ALNK0_CON1, 2, CON1_24BIT(ch));

    /* 6. buffer and length, then the module enable after a barrier */
    wr(ops, LUNAR_ALNK0_ADR(ch), 4, config->dma_address);
    wr(ops, LUNAR_ALNK0_LEN, 2, config->half_words);
    ops->sync(ops->context);
    set_bits(ops, LUNAR_ALNK0_CON0, 2, CON0_ENABLE);

    /* 7. the 44.1 kHz family, rate code 4: MCLK = 256 fs (F13, F14) */
    clear_bits(ops, LUNAR_CLK_CON2, 4, CLK_ALNK0_48K);
    clear_bits(ops, LUNAR_ALNK0_CON3, 1, CON3_DIV_MASK);
    wr(ops, LUNAR_ALNK0_CON3, 1,
       (rd(ops, LUNAR_ALNK0_CON3, 1) & CON3_RATE_KEEP) | CON3_RATE_44K1);
    clear_bits(ops, LUNAR_CLK_CON2, 4, CLK_ALNK0_BIT9);

    /* 8. the interrupt, before any channel runs */
    if (ops->attach_irq(ops->context, LUNAR_ALNK0_IRQ, config->irq_priority) != 0) {
        clear_bits(ops, LUNAR_ALNK0_CON0, 2, CON0_ENABLE);
        return LUNAR_ALNK0_EIRQ;
    }

    /* 9. drop a stale pending, start from silence, run the channel */
    set_bits(ops, LUNAR_ALNK0_CON2, 1, 1u << ch);
    words = 2u * (uint32_t)config->half_words;
    for (i = 0; i < words; i++)
        config->buffer[i] = 0;
    set_bits(ops, LUNAR_ALNK0_CON1, 2, CON1_EN(ch));

    /* 10. let the DAC lock to MCLK (F21) */
    if (config->settle_ms != 0u &&
        ops->delay_ms(ops->context, config->settle_ms) != 0) {
        lunar_alnk0_stop(ops);
        return LUNAR_ALNK0_EDELAY;
    }
    return LUNAR_ALNK0_OK;
}

void lunar_alnk0_stop(const struct lunar_alnk0_ops *ops)
{
    const unsigned ch = LUNAR_ALNK0_TX_CH;
    clear_bits(ops, LUNAR_ALNK0_CON1, 2, CON1_EN(ch));
    set_bits(ops, LUNAR_ALNK0_CON2, 1, 1u << ch);
    clear_bits(ops, LUNAR_ALNK0_CON0, 2, CON0_ENABLE);
}

unsigned lunar_alnk0_pending(const struct lunar_alnk0_ops *ops)
{
    return (unsigned)(rd(ops, LUNAR_ALNK0_CON2, 1) >> 4) & 0x0Fu;
}

void lunar_alnk0_ack(const struct lunar_alnk0_ops *ops, unsigned channel_mask)
{
    channel_mask &= 0x0Fu;
    if (channel_mask != 0u)
        set_bits(ops, LUNAR_ALNK0_CON2, 1, channel_mask);
}

unsigned lunar_alnk0_free_half(const struct lunar_alnk0_ops *ops)
{
    return (rd(ops, LUNAR_ALNK0_CON0, 2) & CON0_HALF(LUNAR_ALNK0_TX_CH)) != 0u ? 0u : 1u;
}

int32_t lunar_alnk0_word_from_q23(int32_t sample)
{
    if (sample > LUNAR_ALNK0_Q23_MAX)
        return LUNAR_ALNK0_Q23_MAX;
    if (sample < LUNAR_ALNK0_Q23_MIN)
        return LUNAR_ALNK0_Q23_MIN;
    return sample;
}
