/* SPDX-License-Identifier: MIT */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <float.h>

#include "fm1_mix_limiter.h"
#include "fm1_postmix.h"

#define MAX_FRAMES 257u
#define MAX_SCOPE 512u

static uint32_t rng = 0x6d2b79f5u;
static uint32_t random_u32(void) {
  uint32_t x = rng;
  x ^= x << 13;
  x ^= x >> 17;
  x ^= x << 5;
  rng = x;
  return x;
}

static void fill(float *samples, uint32_t frames, unsigned pattern) {
  static const uint32_t edge_bits[] = {
      0x00000000u, 0x80000000u, 0x00000001u, 0x80000001u,
      0x007fffffu, 0x807fffffu, 0x3f800000u, 0xbf800000u,
      0x41800000u, 0xc1800000u, 0x7f7fffffu, 0xff7fffffu,
      0x7f800000u, 0xff800000u, 0x7fc12345u, 0xffc54321u,
  };
  for (uint32_t i = 0; i < 2u * frames; ++i) {
    if ((i + pattern) % 3u == 0u) {
      const uint32_t bits = edge_bits[(i * 7u + pattern) %
                                      (sizeof(edge_bits) / sizeof(edge_bits[0]))];
      memcpy(&samples[i], &bits, sizeof(bits));
    } else {
      const int32_t value = (int32_t)(random_u32() & 0x00ffffffu) - 0x007fffff;
      samples[i] = (float)value * (1.0f / 524288.0f);
      if ((i + pattern) % 11u == 0u) samples[i] *= 32.0f;
    }
  }
}

static void output_meter_observe(const float *samples, uint32_t frames,
                                 float *meter_peak) {
  for (uint32_t i = 0; i < frames; ++i) {
    const float left = fabsf(samples[2u * i]);
    const float right = fabsf(samples[2u * i + 1u]);
    const float sample_peak = left > right ? left : right;
    if (sample_peak > *meter_peak) *meter_peak = sample_peak;
  }
}

static int run_case(uint32_t frames, uint32_t scope_size, uint32_t initial_pos,
                    float gain, float envelope, float release, float ceiling,
                    float initial_peak, unsigned pattern) {
  float reference[2u * MAX_FRAMES], candidate[2u * MAX_FRAMES];
  float ref_scope[MAX_SCOPE], candidate_scope[MAX_SCOPE];
  fm1_mix_limiter_t ref_limiter = {envelope, release, ceiling};
  fm1_mix_limiter_t candidate_limiter = ref_limiter;
  int ref_pos = (int)initial_pos, candidate_pos = (int)initial_pos;
  float ref_peak = initial_peak, candidate_peak = initial_peak;
  float ref_meter_peak = 0.0f, candidate_meter_peak = 0.0f;

  fill(reference, MAX_FRAMES, pattern);
  memcpy(candidate, reference, sizeof(reference));
  for (uint32_t i = 0; i < MAX_SCOPE; ++i) {
    ref_scope[i] = candidate_scope[i] = (float)i * 0.03125f - 1.0f;
  }

  fm1_mix_limiter_process(&ref_limiter, reference, frames);
  output_meter_observe(reference, frames, &ref_meter_peak);
  fm1_postmix_scope_and_gain(reference, frames, ref_scope, scope_size,
                             &ref_pos, &ref_peak, gain);

  float block_peak = 0.0f;
  fm1_mix_limiter_process_peak(&candidate_limiter, candidate, frames, &block_peak);
  output_meter_observe(candidate, frames, &candidate_meter_peak);
  fm1_postmix_scope_and_gain_peak(candidate, frames, candidate_scope, scope_size,
                                  &candidate_pos, &candidate_peak, block_peak, gain);

  return memcmp(reference, candidate, sizeof(reference)) == 0 &&
         memcmp(&ref_limiter, &candidate_limiter, sizeof(ref_limiter)) == 0 &&
         memcmp(ref_scope, candidate_scope, sizeof(ref_scope)) == 0 &&
         ref_pos == candidate_pos &&
         memcmp(&ref_peak, &candidate_peak, sizeof(ref_peak)) == 0 &&
         memcmp(&ref_meter_peak, &candidate_meter_peak, sizeof(ref_meter_peak)) == 0;
}

int main(void) {
#if !defined(FM1_HOT_DSP_RAM) || !FM1_HOT_DSP_RAM
  fprintf(stderr, "pipeline candidate must be compiled with FM1_HOT_DSP_RAM=1\n");
  return 2;
#endif
  const uint32_t scope_sizes[] = {1u, 3u, 17u, MAX_SCOPE};
  const uint32_t frame_sizes[] = {0u, 1u, 7u, 64u, MAX_FRAMES};
  const float gains[] = {1.0f, 0.0f, -0.0f, 0.375f, -1.25f, INFINITY, NAN};
  const float envelopes[] = {0.0f, 0.5f, 0.98f, 1.5f, NAN, INFINITY};
  const float releases[] = {0.0f, 0.01f, 1.0f, NAN};
  const float ceilings[] = {0.98f, 0.0f, -0.5f, NAN, INFINITY};
  const float initial_peaks[] = {0.0f, -0.0f, 0.25f, INFINITY, NAN};
  unsigned checks = 0;
  for (unsigned pattern = 0; pattern < 12; ++pattern) {
    for (unsigned s = 0; s < sizeof(scope_sizes) / sizeof(scope_sizes[0]); ++s) {
      for (uint32_t pos = 0; pos < scope_sizes[s]; ++pos) {
        for (unsigned f = 0; f < sizeof(frame_sizes) / sizeof(frame_sizes[0]); ++f) {
          for (unsigned g = 0; g < sizeof(gains) / sizeof(gains[0]); ++g) {
            const unsigned state = (pattern + f + g + pos) %
                                   (sizeof(envelopes) / sizeof(envelopes[0]));
            const unsigned rel = (pattern + s + g) %
                                 (sizeof(releases) / sizeof(releases[0]));
            const unsigned ceil = (pattern * 3u + f) %
                                  (sizeof(ceilings) / sizeof(ceilings[0]));
            const unsigned peak = (pattern + pos + s) %
                                  (sizeof(initial_peaks) / sizeof(initial_peaks[0]));
            if (!run_case(frame_sizes[f], scope_sizes[s], pos, gains[g],
                          envelopes[state], releases[rel], ceilings[ceil],
                          initial_peaks[peak], pattern)) {
              fprintf(stderr, "pipeline mismatch pattern=%u scope=%u pos=%u frames=%u gain=%u\n",
                      pattern, scope_sizes[s], pos, frame_sizes[f], g);
              return 1;
            }
            ++checks;
          }
        }
      }
    }
  }
  printf("limiter/postmix peak pipeline exact equivalence: PASS (%u cases)\n", checks);
  return 0;
}
