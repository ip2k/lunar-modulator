/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_NATIVE_AUDIO_QUEUE_H
#define LUNAR_NATIVE_AUDIO_QUEUE_H
#include <stdint.h>

/* Core-0 main-loop producer, core-0 audio-interrupt consumer only.
 * Not a portable thread queue or a multicore primitive. The interrupt may
 * preempt the producer; neither counter nor slot has more than one writer.
 * Aligned 32-bit accesses and compiler publication barriers are required.
 * No application callbacks execute in the consumer. */
#define LUNAR_AUDIO_BLOCK_FRAMES 64u
#define LUNAR_AUDIO_QUEUE_BLOCKS 8u
#define LUNAR_AUDIO_WORDS (2u * LUNAR_AUDIO_BLOCK_FRAMES)
typedef struct {
    volatile uint32_t written, read;
    uint32_t underruns; /* consumer-owned; one per missing 64-frame block */
    int32_t samples[LUNAR_AUDIO_QUEUE_BLOCKS][LUNAR_AUDIO_WORDS];
} lunar_audio_queue_t;

static inline void lunar_audio_publish(void)
{
    __asm__ volatile("" ::: "memory");
}

/* NaN is silent; finite overflow and infinities saturate before conversion. */
static inline int32_t lunar_audio_q15(float value)
{
    if (!(value == value)) return 0;
    if (value >= 1.0f) return 32767;
    if (value <= -1.0f) return -32767;
    return (int32_t)(value * 32767.0f);
}

static inline int lunar_audio_push(lunar_audio_queue_t *q, const float *samples)
{
    uint32_t w = q->written;
    uint32_t r = q->read;
    lunar_audio_publish();
    if (w - r >= LUNAR_AUDIO_QUEUE_BLOCKS) return 0;
    for (uint32_t i = 0; i < LUNAR_AUDIO_WORDS; ++i)
        q->samples[w & (LUNAR_AUDIO_QUEUE_BLOCKS - 1u)][i] = lunar_audio_q15(samples[i]);
    lunar_audio_publish();
    q->written = w + 1u;
    return 1;
}

/* Exactly one block. Larger HAL callbacks consume successive blocks. An
 * underrun writes a whole silent block, without advancing the read counter. */
static inline int lunar_audio_pop(lunar_audio_queue_t *q, int32_t *samples)
{
    uint32_t r = q->read;
    uint32_t w = q->written;
    lunar_audio_publish();
    if (r == w) {
        for (uint32_t i = 0; i < LUNAR_AUDIO_WORDS; ++i) samples[i] = 0;
        q->underruns++;
        return 0;
    }
    for (uint32_t i = 0; i < LUNAR_AUDIO_WORDS; ++i)
        samples[i] = q->samples[r & (LUNAR_AUDIO_QUEUE_BLOCKS - 1u)][i];
    lunar_audio_publish();
    q->read = r + 1u;
    return 1;
}
#endif
