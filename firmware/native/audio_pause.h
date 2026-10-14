/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_NATIVE_AUDIO_PAUSE_H
#define LUNAR_NATIVE_AUDIO_PAUSE_H
#include "audio_queue.h"

/* Include after the FM1 audio/IRQ HAL. Core-0 main loop only, with global
 * interrupts disabled for BOTH calls. The caller restores global interrupts
 * after each call; they need not stay disabled throughout the SAVE operation.
 * This masks ALNK0 and stops its DMA, not TIMER5, USB or display DMA. A complete
 * SAVE scheduler must separately silence USB audio and finish display transfers.
 * No physical restart acceptance or storage admission is established here. */
#define LUNAR_AUDIO_DMA_WORDS 1024u /* two halves of 256 stereo frames */
typedef struct {
    lunar_audio_queue_t *queue;
    int32_t *dma;
    uint32_t irq_bits;
    uint16_t running;
    uint8_t active;
} lunar_audio_pause_t;

static int lunar_audio_pause_begin(lunar_audio_pause_t *pause,
        lunar_audio_queue_t *queue, int32_t *dma, uint32_t words)
{
    const uint32_t shift = (FM1_IRQ_ALNK0 & 7u) * 4u;
    if (!pause || pause->active || !queue || !dma ||
            words != LUNAR_AUDIO_DMA_WORDS) return 0;
    pause->queue = queue;
    pause->dma = dma;
    pause->irq_bits = FM1_ICFG(FM1_IRQ_ALNK0) & (0xFu << shift);
    pause->running = FM1_ALNK_CON0 & 0x800u;
    fm1_irq_mask(FM1_IRQ_ALNK0);
    fm1_audio_stop();
    lunar_audio_publish();
    pause->active = 1;
    return 1;
}

static int lunar_audio_pause_end(lunar_audio_pause_t *pause)
{
    const uint32_t mask = 0xFu << ((FM1_IRQ_ALNK0 & 7u) * 4u);
    if (!pause || !pause->active) return 0;
    /* Discard queued pre-SAVE sound. Preserve the cumulative underrun count.
     * Both DMA halves become silence before either DMA or its IRQ can resume. */
    for (uint32_t i = 0; i < LUNAR_AUDIO_DMA_WORDS; ++i) pause->dma[i] = 0;
    pause->queue->read = 0;
    pause->queue->written = 0;
    lunar_audio_publish();
    FM1_ALNK_CON0 = (uint16_t)((FM1_ALNK_CON0 & ~0x800u) | pause->running);
    FM1_ICFG(FM1_IRQ_ALNK0) =
        (FM1_ICFG(FM1_IRQ_ALNK0) & ~mask) | pause->irq_bits;
    pause->active = 0;
    pause->queue = 0;
    pause->dma = 0;
    return 1;
}
#endif
