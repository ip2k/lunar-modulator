/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DEVKIT_RENDERER_LIVE_H
#define LUNAR_DEVKIT_RENDERER_LIVE_H
#include <stdint.h>
#ifndef LUNAR_RENDERER_WORKLOAD
#define LUNAR_RENDERER_WORKLOAD 0
#endif
#if LUNAR_RENDERER_WORKLOAD == 0
#define LUNAR_RENDERER_WORKLOAD_NAME "mixed"
#elif LUNAR_RENDERER_WORKLOAD == 1
#define LUNAR_RENDERER_WORKLOAD_NAME "keys"
#else
#error Unsupported diagnostic renderer workload
#endif
#ifdef __cplusplus
extern "C" {
#endif
struct lunar_renderer_status {
    uint32_t test_case, cycles, blocks, controls, invalid, clipped;
    uint32_t completed_cases, completed_case, completed_hash, arena_bytes, init_error;
    uint32_t unit_bytes[8];
};
/* One audio owner, initialized before DAC start. Status must be copied with
 * that IRQ excluded. Initialization failure refuses output, not a smaller kit. */
int lunar_devkit_renderer_init(void);
struct fm1_dx7_kernel_adapter;
/* Diagnostic audio owner, before init only. Adapter storage must be permanent;
 * NULL retains the normal sequential path. Refused after successful init. */
int lunar_devkit_renderer_kernel_adapter(const struct fm1_dx7_kernel_adapter *adapter);
void lunar_devkit_renderer_render(int16_t *four_channel_64_frames);
void lunar_devkit_renderer_status(struct lunar_renderer_status *out);
#ifdef LUNAR_RENDERER_PROFILE
#define LUNAR_RENDERER_PROFILE_STAGES 6u
/* Outer render regions: note/control preparation, shared app, PCM conversion. */
#define LUNAR_RENDERER_DETAIL_REGIONS 3u
struct lunar_renderer_profile { uint64_t ticks; uint32_t calls, frames, max_ticks; };
/* Worker diagnostic only. Set clock before init; read/reset outside rendering. */
void lunar_devkit_renderer_profile_clock(uint32_t (*now)(void));
void lunar_devkit_renderer_profile_read(unsigned workload_unit, struct lunar_renderer_profile *out);
/* Stage IDs are fm1_app_profile_stage; stage totals include nested units. */
unsigned lunar_devkit_renderer_profile_stages(void);
void lunar_devkit_renderer_stage_read(unsigned stage, struct lunar_renderer_profile *out);
/* Last completed block, using existing observer clock samples. */
uint32_t lunar_devkit_renderer_stage_last(unsigned stage);
void lunar_devkit_renderer_profile_reset(void);
void lunar_devkit_renderer_detail_read(unsigned region, struct lunar_renderer_profile *out);
uint32_t lunar_devkit_renderer_detail_last(unsigned region);
#ifdef LUNAR_RENDERER_ENGINE_PROFILE
/* Diagnostic prepared copies only: Macro generate/pop, drums generate/pop.
 * These regions are nested inside unit/stage totals, never additional work. */
#define LUNAR_RENDERER_ENGINE_REGIONS 4
void lunar_devkit_engine_profile(unsigned region, uint32_t frames, int entering);
void lunar_devkit_renderer_engine_read(unsigned region, struct lunar_renderer_profile *out);
#endif
#endif
#ifdef __cplusplus
}
#endif
#endif
