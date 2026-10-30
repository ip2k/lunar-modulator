/* SPDX-License-Identifier: MIT */
#include "benchmark.h"
#include "fm1_resampler.h"

static fm1_resampler_t state;
static float signal_table[256];
static float outputs[64];

/* Mirrors the fixed-block producer queue, without running an instrument.
 * The producer fixture is deliberately cheap; this is resampler cost, not
 * the complete Drums/SixOp renderer and not an underrun measurement. */
static uint32_t block(uint32_t *cursor, uint32_t *available, uint32_t frames,
                      uint32_t active)
{
    uint32_t i, used = 0;
    for (i = 0; i < 64; ++i) {
        uint32_t need;
        while ((need = fm1_resampler_needed(&state)) != 0) {
            float input;
            if (!*available) *available = frames;
            input = active ? signal_table[*cursor & 255u] : 0.0f;
            if (fm1_resampler_push(&state, &input, 1) != 1) return UINT32_MAX;
            ++*cursor;
            --*available;
            ++used;
        }
        outputs[i] = fm1_resampler_pop(&state);
    }
    return used;
}

int lunar_devkit_benchmark(uint32_t (*now)(void),
                          void (*emit)(const struct lunar_devkit_result *))
{
    const uint32_t rates[] = {44118, 47872, 96000};
    const uint32_t producer_frames[] = {12, 16};
    uint32_t r, p, signal, i;
    if (!now || !emit) return 0;
    for (i = 0; i < 256; ++i)
        signal_table[i] = (float)((int)((i * 73u) & 255u) - 128) / 256.0f;
    for (r = 0; r < 3; ++r) for (p = 0; p < 2; ++p)
        for (signal = 0; signal < 3; ++signal) {
            struct lunar_devkit_result result = {0};
            uint32_t cursor = 0, available = 0, b;
            float input_rate = rates[r] == 47872 ? 47872.34f : (float)rates[r];
            if (!fm1_resampler_init(&state, input_rate, 44118.0f)) return 0;
            /* Untimed warm-up; tail starts with a filled, active history. */
            for (b = 0; b < 8; ++b)
                if (block(&cursor, &available, producer_frames[p], signal != 0) == UINT32_MAX)
                    return 0;
            result.rate = rates[r];
            result.producer_frames = producer_frames[p];
            result.signal = signal;
            result.blocks = signal == 2 ? 8 : 128;
            result.min_ticks = UINT32_MAX;
            result.checksum = 2166136261u;
            for (b = 0; b < result.blocks; ++b) {
                uint32_t start = now();
                uint32_t used = block(&cursor, &available, producer_frames[p], signal == 1);
                uint32_t elapsed = now() - start;
                if (used == UINT32_MAX) return 0;
                result.ticks += elapsed;
                if (elapsed < result.min_ticks) result.min_ticks = elapsed;
                if (elapsed > result.max_ticks) result.max_ticks = elapsed;
                result.input_frames += used;
                /* Checksum and UART printing are outside the timed region. */
                for (i = 0; i < 64; ++i) {
                    union { float f; uint32_t u; } bits;
                    bits.f = outputs[i];
                    result.checksum = (result.checksum ^ bits.u) * 16777619u;
                }
            }
            emit(&result);
        }
    return 1;
}
