/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef FM1_ENGINE_RENDER_PROFILE_H
#define FM1_ENGINE_RENDER_PROFILE_H

#include <stdint.h>

#define FM1_ENGINE_PROFILE_DRUMS 0u
#define FM1_ENGINE_PROFILE_SIXOP 1u

/* Optional target-only timing hooks. With the option absent, these macros
 * compile away so normal engine builds make no timer calls or state changes. */
#if defined(LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE)
extern "C" uint32_t lunar_engine_profile_ticks(void);
extern "C" void lunar_engine_profile_render(uint32_t engine, uint32_t ticks,
                                             uint32_t block_ticks,
                                             uint32_t block_calls);
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

#endif
