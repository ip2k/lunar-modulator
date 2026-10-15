/* SPDX-License-Identifier: GPL-3.0-only */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <float.h>

#include "fm1_postmix.h"

#define MAX_SCOPE_SIZE 512u
#define MAX_FRAMES 1025u

static void reference_two_pass(float *out, uint32_t frames, float *scope,
                               uint32_t scope_size, int *scope_pos,
                               float *peak, float gain) {
  for (uint32_t i = 0; i < frames; ++i) {
    const float mono = 0.5f * (out[2 * i] + out[2 * i + 1]);
    scope[*scope_pos] = mono;
    *scope_pos = (*scope_pos + 1) % (int)scope_size;
    const float sample_peak = fabsf(out[2 * i]) > fabsf(out[2 * i + 1])
                                  ? fabsf(out[2 * i])
                                  : fabsf(out[2 * i + 1]);
    if (sample_peak > *peak) *peak = sample_peak;
  }
  if (gain != 1.0f) {
    for (uint32_t i = 0; i < 2 * frames; ++i) out[i] *= gain;
  }
}

static void fill_samples(float *out, uint32_t frames, unsigned kind) {
  static const float edges[] = {
      0.0f, -0.0f, 1.0f, -1.0f, 0.25f, -0.75f, FLT_MAX, -FLT_MAX,
      INFINITY, -INFINITY, NAN, 0x1p-149f, -0x1p-149f,
  };
  for (uint32_t i = 0; i < 2 * frames; ++i) {
    if (kind == 0) {
      out[i] = (float)((int)(i % 19u) - 9) * 0.03125f;
    } else if (kind == 1) {
      out[i] = (i & 1u) ? -0.0f : 0.0f;
    } else {
      out[i] = edges[(i * 7u + kind) % (sizeof(edges) / sizeof(edges[0]))];
    }
  }
}

static int same_case(uint32_t frames, uint32_t scope_size, float gain, unsigned kind,
                     int initial_pos, float initial_peak) {
  float reference[2 * MAX_FRAMES];
  float actual[2 * MAX_FRAMES];
  float reference_scope[MAX_SCOPE_SIZE];
  float actual_scope[MAX_SCOPE_SIZE];
  int reference_pos = initial_pos;
  int actual_pos = initial_pos;
  float reference_peak = initial_peak;
  float actual_peak = initial_peak;

  fill_samples(reference, MAX_FRAMES, kind);
  memcpy(actual, reference, sizeof(actual));
  for (unsigned i = 0; i < MAX_SCOPE_SIZE; ++i) {
    reference_scope[i] = actual_scope[i] = (float)i * 0.0625f - 0.25f;
  }

  reference_two_pass(reference, frames, reference_scope, scope_size, &reference_pos,
                     &reference_peak, gain);
  fm1_postmix_scope_and_gain(actual, frames, actual_scope, scope_size,
                             &actual_pos, &actual_peak, gain);

  return memcmp(reference, actual, sizeof(actual)) == 0 &&
         memcmp(reference_scope, actual_scope, sizeof(actual_scope)) == 0 &&
         reference_pos == actual_pos &&
         memcmp(&reference_peak, &actual_peak, sizeof(reference_peak)) == 0;
}

int main(void) {
  const uint32_t scope_sizes[] = {1u, 2u, 3u, 17u, MAX_SCOPE_SIZE};
  const float gains[] = {0.0f, 0.375f, 1.0f};
  const uint32_t small_scope_frames[] = {0u, 1u, 37u, 65u};
  const uint32_t large_scope_frames[] = {1u, 65u, MAX_FRAMES};
  const float initial_peaks[] = {0.0f, 0.5f, INFINITY, NAN};
  unsigned checks = 0;
  for (unsigned g = 0; g < sizeof(gains) / sizeof(gains[0]); ++g) {
    for (unsigned kind = 0; kind < 3; ++kind) {
      for (unsigned s = 0; s < sizeof(scope_sizes) / sizeof(scope_sizes[0]); ++s) {
        const uint32_t *frame_cases = scope_sizes[s] == MAX_SCOPE_SIZE
                                          ? large_scope_frames
                                          : small_scope_frames;
        const unsigned frame_count = scope_sizes[s] == MAX_SCOPE_SIZE
                                         ? sizeof(large_scope_frames) / sizeof(large_scope_frames[0])
                                         : sizeof(small_scope_frames) / sizeof(small_scope_frames[0]);
          for (uint32_t pos = 0; pos < scope_sizes[s]; ++pos) {
            for (unsigned peak = 0; peak < sizeof(initial_peaks) / sizeof(initial_peaks[0]); ++peak) {
              for (unsigned f = 0; f < frame_count; ++f) {
                if (!same_case(frame_cases[f], scope_sizes[s], gains[g], kind,
                               (int)pos, initial_peaks[peak])) {
                  fprintf(stderr, "mismatch gain=%g frames=%u kind=%u scope=%u pos=%u peak=%u\n",
                          gains[g], frame_cases[f], kind, scope_sizes[s], pos, peak);
                  return 1;
                }
                ++checks;
              }
            }
          }
      }
    }
  }
  printf("postmix optimized/reference exact equivalence: PASS (%u cases)\n", checks);
  return 0;
}
