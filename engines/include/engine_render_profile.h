/* SPDX-License-Identifier: MIT */
#ifndef FM1_ENGINE_RENDER_PROFILE_H
#define FM1_ENGINE_RENDER_PROFILE_H

#include <stdint.h>

#define FM1_ENGINE_PROFILE_DRUMS 0u
#define FM1_ENGINE_PROFILE_SIXOP 1u

/* Optional target-only timing hooks. With the option absent, these macros
 * compile away so normal engine builds make no timer calls or state changes. */
#if defined(LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE)
#ifdef __cplusplus
extern "C" {
#endif
uint32_t lunar_engine_profile_ticks(void);
void lunar_engine_profile_render(uint32_t engine, uint32_t ticks,
                                             uint32_t block_ticks,
                                             uint32_t block_calls);
#ifdef __cplusplus
}
#endif
#define FM1_ENGINE_PROFILE_RENDER_BEGIN() \
  const uint32_t fm1_profile_render_start = lunar_engine_profile_ticks(); \
  uint32_t fm1_profile_block_ticks = 0u; \
  uint32_t fm1_profile_block_calls = 0u;
#define FM1_ENGINE_PROFILE_BLOCK_BEGIN() \
  const uint32_t fm1_profile_block_start = lunar_engine_profile_ticks();
#define FM1_ENGINE_PROFILE_BLOCK_END() do { \
  const uint32_t fm1_profile_elapsed = \
      lunar_engine_profile_ticks() - fm1_profile_block_start; \
  fm1_profile_block_ticks += fm1_profile_elapsed; \
  ++fm1_profile_block_calls; \
} while (0)
#define FM1_ENGINE_PROFILE_RENDER_END(engine_id) \
  lunar_engine_profile_render((engine_id), \
      lunar_engine_profile_ticks() - fm1_profile_render_start, \
      fm1_profile_block_ticks, fm1_profile_block_calls)
#else
#define FM1_ENGINE_PROFILE_RENDER_BEGIN() ((void)0)
#define FM1_ENGINE_PROFILE_BLOCK_BEGIN() ((void)0)
#define FM1_ENGINE_PROFILE_BLOCK_END() ((void)0)
#define FM1_ENGINE_PROFILE_RENDER_END(engine_id) ((void)(engine_id))
#endif

/* Schema 9 samples one output in 32, phase retained per resampler instance.
 * Snapshots pair TIMER4 wall ticks and the tracked IRQ busy union. */
#if defined(LUNAR_DIAGNOSTIC_RESAMPLER_STAGE_PROFILE)
#define FM1_RESAMPLER_PROFILE_STRIDE 32u
typedef struct { uint32_t ticks, irq_ticks; } fm1_stage_stamp_t;
#ifdef __cplusplus
extern "C" {
#endif
void lunar_resampler_profile_snapshot(fm1_stage_stamp_t *stamp);
void lunar_resampler_profile_count(uint32_t engine, uint32_t counter);
void lunar_resampler_profile_stage(uint32_t engine, uint32_t stage,
                                  const fm1_stage_stamp_t *start,
                                  const fm1_stage_stamp_t *end);
#ifdef __cplusplus
}
#endif
#define FM1_STAGE_BEGIN(name, active) fm1_stage_stamp_t name; \
  if (active) lunar_resampler_profile_snapshot(&name)
#define FM1_STAGE_END(name, active, engine, stage) do { \
  if (active) { fm1_stage_stamp_t end; lunar_resampler_profile_snapshot(&end); \
    lunar_resampler_profile_stage(engine, stage, &name, &end); } \
} while (0)
#else
#define FM1_STAGE_BEGIN(name, active) ((void)0)
#define FM1_STAGE_END(name, active, engine, stage) ((void)0)
#endif

#endif
