/* SPDX-License-Identifier: GPL-3.0-only */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
/* Register model: the production helper itself is compiled below. */
enum { FM1_IRQ_ALNK0 = 11 };
static uint32_t cfg[16];
static uint16_t con0;
static unsigned masked, stopped;
#define FM1_ICFG(n) cfg[(n) >> 3]
#define FM1_ALNK_CON0 con0
static void fm1_irq_mask(uint32_t n) {
    FM1_ICFG(n) &= ~(1u << ((n & 7u) * 4u)); ++masked;
}
static void fm1_audio_stop(void) { con0 &= ~0x800u; ++stopped; }
#include "audio_pause.h"

static uint32_t random_word(uint32_t *state) {
    *state ^= *state << 13; *state ^= *state >> 17; *state ^= *state << 5;
    return *state;
}
int main(int argc, char **argv) {
    unsigned shard = argc > 1 ? (unsigned)strtoul(argv[1], 0, 10) : 0;
    assert(shard < 30);
    uint32_t rng = 0x72518ABDu + shard;
    for (unsigned test = 0; test < 2000; ++test) {
        lunar_audio_pause_t p = {0};
        lunar_audio_queue_t q;
        struct { uint32_t lo; int32_t words[LUNAR_AUDIO_DMA_WORDS]; uint32_t hi; } dma;
        memset(&q, 0xA7, sizeof q);
        dma.lo = 0x12345678; dma.hi = 0xDEADBEEF;
        for (unsigned i = 0; i < LUNAR_AUDIO_DMA_WORDS; ++i)
            dma.words[i] = (int32_t)random_word(&rng);
        uint32_t before_cfg = random_word(&rng), underruns = q.underruns;
        uint16_t before_con = (uint16_t)random_word(&rng);
        cfg[1] = before_cfg; con0 = before_con;
        masked = stopped = 0;
        assert(!lunar_audio_pause_begin(0, &q, dma.words, 1024));
        assert(!lunar_audio_pause_begin(&p, 0, dma.words, 1024));
        assert(!lunar_audio_pause_begin(&p, &q, 0, 1024));
        assert(!lunar_audio_pause_begin(&p, &q, dma.words, 1023));
        assert(!lunar_audio_pause_end(0));
        assert(!lunar_audio_pause_end(&p));
        assert(!masked && !stopped && cfg[1] == before_cfg && con0 == before_con);
        assert(lunar_audio_pause_begin(&p, &q, dma.words, 1024));
        assert(masked == 1 && stopped == 1);
        assert(cfg[1] == (before_cfg & ~(1u << 12)));
        assert(con0 == (uint16_t)(before_con & ~0x800u));
        assert(!lunar_audio_pause_begin(&p, &q, dma.words, 1024));
        assert(masked == 1 && stopped == 1);
        /* Other interrupt configurations may change during SAVE. */
        uint32_t other = random_word(&rng) & ~(0xFu << 12);
        cfg[1] = other | (cfg[1] & (0xFu << 12));
        assert(lunar_audio_pause_end(&p));
        assert(cfg[1] == (other | (before_cfg & (0xFu << 12))));
        assert(con0 == before_con && !p.active && !p.queue && !p.dma);
        assert(q.written == 0 && q.read == 0 && q.underruns == underruns);
        for (unsigned i = 0; i < LUNAR_AUDIO_DMA_WORDS; ++i) assert(dma.words[i] == 0);
        assert(dma.lo == 0x12345678 && dma.hi == 0xDEADBEEF);
        assert(!lunar_audio_pause_end(&p));
        /* A failed SAVE still takes the same resume path; next playback works. */
        float samples[LUNAR_AUDIO_WORDS]; int32_t output[LUNAR_AUDIO_WORDS];
        for (unsigned i = 0; i < LUNAR_AUDIO_WORDS; ++i) samples[i] = 0.5f;
        assert(lunar_audio_push(&q, samples)); assert(lunar_audio_pop(&q, output));
        for (unsigned i = 0; i < LUNAR_AUDIO_WORDS; ++i) assert(output[i] == 16383);
        assert(lunar_audio_pause_begin(&p, &q, dma.words, 1024));
        assert(lunar_audio_pause_end(&p));
    }
    printf("shard=%u cases=2000 PASS\n", shard);
    return 0;
}
