/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DEVKIT_FM6_BENCHMARK_H
#define LUNAR_DEVKIT_FM6_BENCHMARK_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
struct lunar_fm6_result {
    uint32_t patch, voices, blocks, instance_bytes;
    uint32_t ticks, min_ticks, max_ticks, note_on_ticks, note_off_ticks;
    uint32_t checksum, invalid_samples, nonzero_samples;
};
/* Real FM6 at 44100 Hz, without a DAC, mixer or effects. Raw caller clock
 * ticks; this is a workload comparison, not a real-time dropout test. */
int lunar_devkit_fm6_benchmark(uint32_t (*now)(void),
                             void (*emit)(const struct lunar_fm6_result *));
#ifdef __cplusplus
}
#endif
#endif
