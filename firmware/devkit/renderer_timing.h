/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DEVKIT_RENDERER_TIMING_H
#define LUNAR_DEVKIT_RENDERER_TIMING_H
#include "renderer_live.h"
#if defined(LUNAR_QUEUE_PROFILE) && !defined(LUNAR_DEVKIT_ENGINE_QUEUE)
#error Queue region profiling requires the whole-engine queue
#endif
struct lunar_renderer_timing {
    uint32_t test_case, blocks, min_ticks, max_ticks, over_budget;
    uint64_t ticks;
    struct lunar_renderer_status state;
#ifdef LUNAR_QUEUE_PROFILE
    uint64_t queue_ticks[6];
    uint32_t queue_max[6], queue_worst[6];
#endif
#ifdef LUNAR_QUEUE_DETAIL
    uint64_t queue_detail_ticks[10];
    uint32_t queue_detail_max[10], queue_detail_worst[10];
#endif
#ifdef LUNAR_RENDERER_PROFILE
    uint32_t worst_block, worst_stages[LUNAR_RENDERER_PROFILE_STAGES];
    uint32_t worst_details[LUNAR_RENDERER_DETAIL_REGIONS];
    uint32_t worst_units[8];
#ifdef LUNAR_RENDERER_PREP_PROFILE
    uint32_t worst_prep[LUNAR_RENDERER_PREP_REGIONS];
#endif
#endif
};
/* Worker-context preflight, never an audio-output acceptance test. The caller
 * yields between batches and emits outside the measured render region. */
int lunar_devkit_renderer_timing(uint32_t (*now)(void), void (*yield)(void),
    void (*emit)(const struct lunar_renderer_timing *));
#endif
