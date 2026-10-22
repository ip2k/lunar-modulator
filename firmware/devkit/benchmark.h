/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DEVKIT_BENCHMARK_H
#define LUNAR_DEVKIT_BENCHMARK_H
#include <stdint.h>
struct lunar_devkit_result {
    uint32_t rate, producer_frames, signal, blocks;
    uint32_t ticks, min_ticks, max_ticks, input_frames, checksum;
};
/* now returns an unsigned free-running timer; emit runs outside timed blocks.
 * signal: 0 silence, 1 deterministic active signal, 2 active-to-zero tail. */
int lunar_devkit_benchmark(uint32_t (*now)(void),
                          void (*emit)(const struct lunar_devkit_result *));
#endif
