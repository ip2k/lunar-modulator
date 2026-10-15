/* SPDX-License-Identifier: GPL-3.0-only */
/* Internal postmix helpers shared with the native equivalence harness. */
#ifndef FM1_POSTMIX_H
#define FM1_POSTMIX_H

#include <math.h>
#include <stdint.h>

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
      *scope_pos = (*scope_pos + 1) % (int)scope_size;
      const float sample_peak = fabsf(left) > fabsf(right) ? fabsf(left) : fabsf(right);
      if (sample_peak > *peak) *peak = sample_peak;
      out[2 * i] = left * gain;
      out[2 * i + 1] = right * gain;
    }
  } else {
    for (uint32_t i = 0; i < frames; ++i) {
      const float mono = 0.5f * (out[2 * i] + out[2 * i + 1]);
      scope[*scope_pos] = mono;
      *scope_pos = (*scope_pos + 1) % (int)scope_size;
      const float sample_peak = fabsf(out[2 * i]) > fabsf(out[2 * i + 1])
                                    ? fabsf(out[2 * i])
                                    : fabsf(out[2 * i + 1]);
      if (sample_peak > *peak) *peak = sample_peak;
    }
  }
}

#endif
