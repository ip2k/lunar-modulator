/* SPDX-License-Identifier: MIT. Run the unchanged workload without a DAC IRQ. */
#include "renderer_timing.h"
#include <stddef.h>
#include <string.h>
#ifdef LUNAR_DEVKIT_ENGINE_QUEUE
#include "renderer_queue_bridge.h"
#endif
#ifdef LUNAR_DEVKIT_QUEUE_SDK
#include "renderer_queue_sdk.h"
#endif
#ifdef LUNAR_DEVKIT_FM6_SDK
#include "fm6_pair_sdk.h"
#endif

#define CASE_BLOCKS ((8u * 44100u + 63u) / 64u)
#define BUDGET_TICKS (24000000u * 64u / 44100u)

int lunar_devkit_renderer_timing(uint32_t (*now)(void), void (*yield)(void),
    void (*emit)(const struct lunar_renderer_timing *)) {
    int16_t samples[64 * 4];
    if (!now || !yield || !emit) return 0;
#ifdef LUNAR_RENDERER_PROFILE
    lunar_devkit_renderer_profile_clock(now);
#endif
    if (!lunar_devkit_renderer_init()) return 0;
    for (unsigned c = 0; c < 4; ++c) {
        struct lunar_renderer_timing result;
        memset(&result, 0, sizeof result);
        result.test_case = c;
        result.min_ticks = UINT32_MAX;
        for (unsigned b = 0; b < CASE_BLOCKS; ++b) {
#ifdef LUNAR_DEVKIT_FM6_SDK
            lunar_fm6_sdk_parent_block();
#endif
#ifdef LUNAR_DEVKIT_QUEUE_SDK
            lunar_renderer_queue_sdk_parent_block();
#endif
            uint32_t start = now();
            lunar_devkit_renderer_render(samples);
#ifdef LUNAR_DEVKIT_ENGINE_QUEUE
            if (lunar_renderer_queue_error()) return 0;
#endif
            /* Unsigned subtraction handles the 24 MHz timer wrap. */
            uint32_t end = now();
            uint32_t elapsed = end - start;
#ifdef LUNAR_QUEUE_PROFILE
            uint32_t regions[6];
            if (!lunar_renderer_queue_profile_read(start, end, regions)) return 0;
            for (unsigned i = 0; i < 6; ++i) {
                result.queue_ticks[i] += regions[i];
                if (regions[i] > result.queue_max[i]) result.queue_max[i] = regions[i];
                if (elapsed > result.max_ticks) result.queue_worst[i] = regions[i];
            }
#endif
#ifdef LUNAR_QUEUE_DETAIL
            uint32_t details[LUNAR_QUEUE_DETAILS];
            if (!lunar_renderer_queue_detail_read(details)) return 0;
            uint64_t detail_sum = 0;
            for (unsigned i = 0; i < LUNAR_QUEUE_DETAILS; ++i) detail_sum += details[i];
            if (detail_sum > elapsed) return 0;
            for (unsigned i = 0; i < LUNAR_QUEUE_DETAILS; ++i) {
                result.queue_detail_ticks[i] += details[i];
                if (details[i] > result.queue_detail_max[i]) result.queue_detail_max[i] = details[i];
                if (elapsed > result.max_ticks) result.queue_detail_worst[i] = details[i];
            }
#endif
            result.ticks += elapsed;
            if (elapsed < result.min_ticks) result.min_ticks = elapsed;
            if (elapsed > result.max_ticks) {
                result.max_ticks = elapsed;
#ifdef LUNAR_RENDERER_PROFILE
                result.worst_block = b;
                for (unsigned u = 0; u < 8; ++u)
                    result.worst_units[u] = lunar_devkit_renderer_unit_last(u);
                for (unsigned s = 0; s < LUNAR_RENDERER_PROFILE_STAGES; ++s)
                    result.worst_stages[s] = lunar_devkit_renderer_stage_last(s);
                for (unsigned d = 0; d < LUNAR_RENDERER_DETAIL_REGIONS; ++d)
                    result.worst_details[d] = lunar_devkit_renderer_detail_last(d);
#ifdef LUNAR_RENDERER_PREP_PROFILE
                for (unsigned p = 0; p < LUNAR_RENDERER_PREP_REGIONS; ++p)
                    result.worst_prep[p] = lunar_devkit_renderer_prep_last(p);
#endif
#endif
            }
            if (elapsed >= BUDGET_TICKS) ++result.over_budget;
            ++result.blocks;
            if (!(b % 16u)) yield();
        }
        lunar_devkit_renderer_status(&result.state);
        emit(&result);
#ifdef LUNAR_RENDERER_PROFILE
        lunar_devkit_renderer_profile_reset();
#endif
        yield();
    }
    return 1;
}
