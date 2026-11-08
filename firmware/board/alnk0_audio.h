/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Lunar Modulator contributors
 *
 * ALNK0 (I2S) audio output for the M-VAVE FM-1 (JieLi AC791N / WL82).
 *
 * The FM-1's DAC takes no configuration (notes/2026-11-08-alnk0-codec-driver.md
 * §1): bringing up audio is bringing up ALNK0 as I2S master with MCLK out,
 * channel 3 transmitting 24-bit words on PC6, at the 44.1 kHz rate code.
 * Every register fact used here is numbered F1..F22 in that note, with its
 * source and confidence mark.
 *
 * The driver touches no memory itself. All register accesses go through
 * `struct lunar_alnk0_ops`, so a host test can record the exact sequence and
 * the target can supply volatile accesses (alnk0_audio_mmio.c).
 */
#ifndef LUNAR_ALNK0_AUDIO_H
#define LUNAR_ALNK0_AUDIO_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Addresses (F1; WL82.h). */
#define LUNAR_ALNK0_BASE      0x00012E00u
#define LUNAR_ALNK0_CON0      (LUNAR_ALNK0_BASE + 0x00u) /* 16-bit */
#define LUNAR_ALNK0_CON1      (LUNAR_ALNK0_BASE + 0x04u) /* 16-bit */
#define LUNAR_ALNK0_CON2      (LUNAR_ALNK0_BASE + 0x08u) /* 8-bit */
#define LUNAR_ALNK0_CON3      (LUNAR_ALNK0_BASE + 0x0Cu) /* 8-bit */
#define LUNAR_ALNK0_ADR(n)    (LUNAR_ALNK0_BASE + 0x10u + 4u * (unsigned)(n)) /* 32-bit */
#define LUNAR_ALNK0_LEN       (LUNAR_ALNK0_BASE + 0x20u) /* 16-bit */
#define LUNAR_CLK_CON2        0x00010014u                /* 32-bit */
#define LUNAR_IOMAP_CON5      0x00051030u                /* 32-bit */
#define LUNAR_PORTC_OUT       0x00050080u                /* 32-bit */
#define LUNAR_PORTC_DIR       0x00050088u
#define LUNAR_PORTC_PU        0x00050090u
#define LUNAR_PORTC_PD        0x00050094u

#define LUNAR_ALNK0_IRQ       11u  /* F2 */
#define LUNAR_ALNK0_TX_CH     3u   /* F4, F10: data on PC6 */
/* PC0 MCLK, PC1, PC2 (bit clock and word clock), PC6 channel-3 data (F4). */
#define LUNAR_ALNK0_PORTC_PINS ((1u << 0) | (1u << 1) | (1u << 2) | (1u << 6))

/* Profile defaults (F20-F22). */
#define LUNAR_ALNK0_HALF_WORDS   128u /* 64 stereo frames per half */
#define LUNAR_ALNK0_IRQ_PRIORITY 3u
#define LUNAR_ALNK0_SETTLE_MS    5u
#define LUNAR_ALNK0_ALIGN        32u

#define LUNAR_ALNK0_Q23_MAX   8388607
#define LUNAR_ALNK0_Q23_MIN   (-8388608)

enum {
    LUNAR_ALNK0_OK = 0,
    LUNAR_ALNK0_EINVAL = -1, /* config or ops refused by validation */
    LUNAR_ALNK0_EIRQ = -2,   /* attach_irq failed */
    LUNAR_ALNK0_EDELAY = -3  /* delay_ms failed */
};

struct lunar_alnk0_ops {
    void *context;
    /* bytes is 1, 2 or 4, the register's width */
    uint32_t (*read)(void *context, uint32_t address, unsigned bytes);
    void (*write)(void *context, uint32_t address, unsigned bytes, uint32_t value);
    /* a store barrier (`csync` on pi32v2) before the module enable (F12) */
    void (*sync)(void *context);
    /* register the ALNK0 handler; 0 on success */
    int (*attach_irq)(void *context, unsigned irq, unsigned priority);
    /* 0 on success; may be NULL when settle_ms is 0 */
    int (*delay_ms)(void *context, unsigned ms);
};

struct lunar_alnk0_config {
    /* 2 * half_words words: half 0 then half 1, L/R interleaved Q23 words */
    int32_t *buffer;
    /* the address ALNK0's DMA sees for buffer[0]; 32-byte aligned */
    uint32_t dma_address;
    /* 32-bit words per half (LEN, F11): even, 2..65534 */
    uint16_t half_words;
    uint8_t irq_priority;
    uint8_t settle_ms;
};

/* The Lunar profile: 64 frames per half, priority 3, 5 ms settle. */
void lunar_alnk0_default_config(struct lunar_alnk0_config *config,
                                int32_t *buffer, uint32_t dma_address);

int lunar_alnk0_validate(const struct lunar_alnk0_ops *ops,
                         const struct lunar_alnk0_config *config);

/* Full bring-up (note §4). Returns LUNAR_ALNK0_OK or a negative code; on a
 * failure after the module enable the module is stopped again. */
int lunar_alnk0_start(const struct lunar_alnk0_ops *ops,
                      const struct lunar_alnk0_config *config);

void lunar_alnk0_stop(const struct lunar_alnk0_ops *ops);

/* ISR helpers (F16, F17). */
unsigned lunar_alnk0_pending(const struct lunar_alnk0_ops *ops); /* bits 0..3 = channel */
void lunar_alnk0_ack(const struct lunar_alnk0_ops *ops, unsigned channel_mask);
unsigned lunar_alnk0_free_half(const struct lunar_alnk0_ops *ops); /* 0 or 1 */

/* Saturate a sample to the signed 24-bit range carried in a 32-bit word (F19). */
int32_t lunar_alnk0_word_from_q23(int32_t sample);

/* Chip accessors (alnk0_audio_mmio.c, pi32v2 builds only). */
uint32_t lunar_alnk0_mmio_read(void *context, uint32_t address, unsigned bytes);
void lunar_alnk0_mmio_write(void *context, uint32_t address, unsigned bytes, uint32_t value);
void lunar_alnk0_mmio_sync(void *context);

#ifdef __cplusplus
}
#endif

#endif /* LUNAR_ALNK0_AUDIO_H */
