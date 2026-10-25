/* SPDX-License-Identifier: MIT. Run the unchanged workload without a DAC IRQ. */
#include "renderer_timing.h"
#include <stddef.h>
#include <string.h>
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
            uint32_t start = now();
            lunar_devkit_renderer_render(samples);
            /* Unsigned subtraction handles the 24 MHz timer wrap. */
            uint32_t elapsed = now() - start;
            result.ticks += elapsed;
            if (elapsed < result.min_ticks) result.min_ticks = elapsed;
            if (elapsed > result.max_ticks) {
                result.max_ticks = elapsed;
#ifdef LUNAR_RENDERER_PROFILE
                result.worst_block = b;
                for (unsigned s = 0; s < LUNAR_RENDERER_PROFILE_STAGES; ++s)
                    result.worst_stages[s] = lunar_devkit_renderer_stage_last(s);
                for (unsigned d = 0; d < LUNAR_RENDERER_DETAIL_REGIONS; ++d)
                    result.worst_details[d] = lunar_devkit_renderer_detail_last(d);
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
