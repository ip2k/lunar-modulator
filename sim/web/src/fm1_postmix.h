/* SPDX-License-Identifier: GPL-3.0-only */
/* Internal postmix helpers shared with the native equivalence harness. */
#ifndef FM1_POSTMIX_H
#define FM1_POSTMIX_H

#include <math.h>
#include <stdint.h>

/* Keep the fallback for non-GCC/Clang consumers while making the explicit
 * builtin available to target builds that disable implicit builtins. */
#if defined(__GNUC__) || defined(__clang__)
#define FM1_POSTMIX_ABS_F32(x) __builtin_fabsf(x)
#else
#define FM1_POSTMIX_ABS_F32(x) fabsf(x)
#endif

/* The renderer supplies a valid position in [0, scope_size).  An explicit
 * wrap avoids a remainder operation while preserving arbitrary scope sizes.
 * Keep the stores in the caller's frame loop: besides removing a call per
 * sample on pi32v2, this preserves the existing per-iteration pointer writes. */
#if defined(__GNUC__) || defined(__clang__)
#define FM1_POSTMIX_INLINE static inline __attribute__((__always_inline__))
#else
#define FM1_POSTMIX_INLINE static inline
#endif
FM1_POSTMIX_INLINE void fm1_postmix_advance_scope(int *scope_pos,
                                                 uint32_t scope_size) {
  ++*scope_pos;
  if (*scope_pos == (int)scope_size) *scope_pos = 0;
}
#undef FM1_POSTMIX_INLINE

/* Record the pre-master-gain scope and peak, then apply master gain.  The
 * meters intentionally observe the un-gained post-limiter signal.  Keeping
 * each sample in locals lets this single traversal preserve that observation
 * while writing the same gained samples as the former second pass. */
static inline void fm1_postmix_scope_and_gain(float *out, uint32_t frames,
                                              float *scope, uint32_t scope_size,
                                              int *scope_pos, float *peak,
                                              float gain) {
  if (gain != 1.0f) {
    for (uint32_t i = 0; i < frames; ++i) {
      const float left = out[2 * i];
      const float right = out[2 * i + 1];
      const float mono = 0.5f * (left + right);
      scope[*scope_pos] = mono;
      fm1_postmix_advance_scope(scope_pos, scope_size);
      const float left_abs = FM1_POSTMIX_ABS_F32(left);
      const float right_abs = FM1_POSTMIX_ABS_F32(right);
      const float sample_peak = left_abs > right_abs ? left_abs : right_abs;
      if (sample_peak > *peak) *peak = sample_peak;
      out[2 * i] = left * gain;
      out[2 * i + 1] = right * gain;
    }
  } else {
    for (uint32_t i = 0; i < frames; ++i) {
      const float mono = 0.5f * (out[2 * i] + out[2 * i + 1]);
      scope[*scope_pos] = mono;
      fm1_postmix_advance_scope(scope_pos, scope_size);
      const float left_abs = FM1_POSTMIX_ABS_F32(out[2 * i]);
      const float right_abs = FM1_POSTMIX_ABS_F32(out[2 * i + 1]);
      const float sample_peak = left_abs > right_abs ? left_abs : right_abs;
      if (sample_peak > *peak) *peak = sample_peak;
    }
  }
}

/* Application hot-DSP path: the limiter has already accumulated the exact
 * post-limiter peak before the output meter observes the buffer.  Preserve
 * the meter's position in fm1_app_render, then do only the scope/gain work
 * here.  Keep the baseline helper above as the reference/non-opt-in path. */
#if defined(FM1_HOT_DSP_RAM) && FM1_HOT_DSP_RAM && \
    defined(FM1_EXPERIMENT_POSTMIX_PEAK_HANDOFF) && \
    FM1_EXPERIMENT_POSTMIX_PEAK_HANDOFF
static inline void fm1_postmix_scope_and_gain_peak(float *out, uint32_t frames,
                                                   float *scope, uint32_t scope_size,
                                                   int *scope_pos, float *peak,
                                                   float block_peak, float gain) {
  if (frames != 0 && block_peak > *peak) *peak = block_peak;
  if (gain != 1.0f) {
    for (uint32_t i = 0; i < frames; ++i) {
      const float left = out[2 * i];
      const float right = out[2 * i + 1];
      const float mono = 0.5f * (left + right);
      scope[*scope_pos] = mono;
      fm1_postmix_advance_scope(scope_pos, scope_size);
      out[2 * i] = left * gain;
      out[2 * i + 1] = right * gain;
    }
  } else {
    for (uint32_t i = 0; i < frames; ++i) {
      const float mono = 0.5f * (out[2 * i] + out[2 * i + 1]);
      scope[*scope_pos] = mono;
      fm1_postmix_advance_scope(scope_pos, scope_size);
    }
  }
}
#endif

#undef FM1_POSTMIX_ABS_F32

#endif
