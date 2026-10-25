/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DEVKIT_RENDERER_TIMING_H
#define LUNAR_DEVKIT_RENDERER_TIMING_H
#include "renderer_live.h"
struct lunar_renderer_timing {
    uint32_t test_case, blocks, min_ticks, max_ticks, over_budget;
    uint64_t ticks;
    struct lunar_renderer_status state;
#ifdef LUNAR_RENDERER_PROFILE
    uint32_t worst_block, worst_stages[LUNAR_RENDERER_PROFILE_STAGES];
#endif
};
/* Worker-context preflight, never an audio-output acceptance test. The caller
 * yields between batches and emits outside the measured render region. */
int lunar_devkit_renderer_timing(uint32_t (*now)(void), void (*yield)(void),
    void (*emit)(const struct lunar_renderer_timing *));
#endif
