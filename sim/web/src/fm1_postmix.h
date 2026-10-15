/* SPDX-License-Identifier: GPL-3.0-only */
/* Internal postmix helpers shared with the native equivalence harness. */
#ifndef FM1_POSTMIX_H
#define FM1_POSTMIX_H

#include <math.h>
#include <stdint.h>

/* The renderer supplies a valid position in [0, scope_size).  An explicit
 * wrap avoids a remainder operation while preserving arbitrary scope sizes. */
static inline void fm1_postmix_advance_scope(int *scope_pos,
                                             uint32_t scope_size) {
  ++*scope_pos;
  if (*scope_pos == (int)scope_size) *scope_pos = 0;
}

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
      const float left_abs = fabsf(left);
      const float right_abs = fabsf(right);
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
      const float left_abs = fabsf(out[2 * i]);
      const float right_abs = fabsf(out[2 * i + 1]);
      const float sample_peak = left_abs > right_abs ? left_abs : right_abs;
      if (sample_peak > *peak) *peak = sample_peak;
    }
  }
}

#endif
