/* SPDX-License-Identifier: GPL-3.0-only */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <float.h>

#include "fm1_postmix.h"

#define SCOPE_SIZE 17u
#define MAX_FRAMES 65u

static void reference_two_pass(float *out, uint32_t frames, float *scope,
                               int *scope_pos, float *peak, float gain) {
  for (uint32_t i = 0; i < frames; ++i) {
    const float mono = 0.5f * (out[2 * i] + out[2 * i + 1]);
    scope[*scope_pos] = mono;
    *scope_pos = (*scope_pos + 1) % (int)SCOPE_SIZE;
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

static int same_case(uint32_t frames, float gain, unsigned kind,
                     int initial_pos, float initial_peak) {
  float reference[2 * MAX_FRAMES];
  float actual[2 * MAX_FRAMES];
  float reference_scope[SCOPE_SIZE];
  float actual_scope[SCOPE_SIZE];
  int reference_pos = initial_pos;
  int actual_pos = initial_pos;
  float reference_peak = initial_peak;
  float actual_peak = initial_peak;

  fill_samples(reference, MAX_FRAMES, kind);
  memcpy(actual, reference, sizeof(actual));
  for (unsigned i = 0; i < SCOPE_SIZE; ++i) {
    reference_scope[i] = actual_scope[i] = (float)i * 0.0625f - 0.25f;
  }

  reference_two_pass(reference, frames, reference_scope, &reference_pos,
                     &reference_peak, gain);
  fm1_postmix_scope_and_gain(actual, frames, actual_scope, SCOPE_SIZE,
                             &actual_pos, &actual_peak, gain);

  return memcmp(reference, actual, sizeof(actual)) == 0 &&
         memcmp(reference_scope, actual_scope, sizeof(actual_scope)) == 0 &&
         reference_pos == actual_pos &&
         memcmp(&reference_peak, &actual_peak, sizeof(reference_peak)) == 0;
}

int main(void) {
  const float gains[] = {0.0f, 0.375f, 1.0f};
  const uint32_t frames[] = {0u, 1u, 37u, MAX_FRAMES};
  const float initial_peaks[] = {0.0f, 0.5f, INFINITY, NAN};
  unsigned checks = 0;
  for (unsigned g = 0; g < sizeof(gains) / sizeof(gains[0]); ++g) {
    for (unsigned f = 0; f < sizeof(frames) / sizeof(frames[0]); ++f) {
      for (unsigned kind = 0; kind < 3; ++kind) {
        for (unsigned p = 0; p < 2; ++p) {
          for (unsigned peak = 0; peak < sizeof(initial_peaks) / sizeof(initial_peaks[0]); ++peak) {
            if (!same_case(frames[f], gains[g], kind, p ? 15 : 0,
                           initial_peaks[peak])) {
              fprintf(stderr, "mismatch gain=%g frames=%u kind=%u pos=%u peak=%u\n",
                      gains[g], frames[f], kind, p ? 15u : 0u, peak);
              return 1;
            }
            ++checks;
          }
        }
      }
    }
  }
  printf("postmix fused/reference exact equivalence: PASS (%u cases)\n", checks);
  return 0;
}
