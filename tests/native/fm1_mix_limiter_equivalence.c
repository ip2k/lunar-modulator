/* SPDX-License-Identifier: MIT */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "fm1_mix_limiter.h"

#define FRAMES 513u
#define CHANNELS 2u
#define SAMPLE_COUNT (FRAMES * CHANNELS)

typedef struct reference_limiter {
  float envelope;
  float release;
  float ceiling;
} reference_limiter_t;

static float reference_guard(float x) {
  if (!(x == x)) return 0.0f;
  return x > 16.0f ? 16.0f : (x < -16.0f ? -16.0f : x);
}

static void reference_process(reference_limiter_t *l, float *lr, uint32_t frames) {
  for (uint32_t n = 0; n < frames; ++n) {
    lr[2 * n] = reference_guard(lr[2 * n]);
    lr[2 * n + 1] = reference_guard(lr[2 * n + 1]);
    const float a = fabsf(lr[2 * n]);
    const float b = fabsf(lr[2 * n + 1]);
    const float peak = a > b ? a : b;
    if (peak > l->envelope) {
      l->envelope = peak;
    } else {
      l->envelope += (peak - l->envelope) * l->release;
    }
    if (l->envelope > l->ceiling) {
      const float g = l->ceiling / l->envelope;
      lr[2 * n] *= g;
      lr[2 * n + 1] *= g;
    }
  }
}

static uint32_t rng_state = 0x9e3779b9u;
static uint32_t next_u32(void) {
  uint32_t x = rng_state;
  x ^= x << 13;
  x ^= x >> 17;
  x ^= x << 5;
  rng_state = x;
  return x;
}

static void fill_samples(float *out, unsigned scenario) {
  static const uint32_t edge_bits[] = {
      0x00000000u, 0x80000000u, 0x3f800000u, 0xbf800000u,
      0x3e800000u, 0xbf400000u, 0x41800000u, 0xc1800000u,
      0x7f800000u, 0xff800000u, 0x7fc12345u, 0xffc54321u,
      0x00000001u, 0x80000001u, 0x007fffffu, 0x807fffffu,
      0x7f7fffffu, 0xff7fffffu,
  };
  for (unsigned i = 0; i < SAMPLE_COUNT; ++i) {
    float value;
    if ((i + scenario) % 5u == 0u) {
      const uint32_t bits = edge_bits[(i * 7u + scenario) %
                                      (sizeof(edge_bits) / sizeof(edge_bits[0]))];
      memcpy(&value, &bits, sizeof(value));
    } else {
      const int32_t centered = (int32_t)(next_u32() & 0x00ffffffu) - 0x007fffff;
      value = (float)centered * (1.0f / 524288.0f);
      if ((i + scenario) % 17u == 0u) value *= 32.0f;
    }
    out[i] = value;
  }
}

static int one_case(uint32_t chunk, unsigned scenario, float initial_envelope,
                    float sample_rate) {
  float ref[SAMPLE_COUNT], actual[SAMPLE_COUNT];
  reference_limiter_t ref_state;
  fm1_mix_limiter_t actual_state;
  memset(&ref_state, 0, sizeof(ref_state));
  memset(&actual_state, 0, sizeof(actual_state));
  actual_state.envelope = initial_envelope;
  actual_state.release = 1.0f - expf(-1.0f / (0.1f * sample_rate));
  actual_state.ceiling = 0.98f;
  memcpy(&ref_state, &actual_state, sizeof(ref_state));
  fill_samples(ref, scenario);
  memcpy(actual, ref, sizeof(actual));

  for (uint32_t offset = 0; offset < FRAMES;) {
    uint32_t count = chunk;
    if (count > FRAMES - offset) count = FRAMES - offset;
    reference_process(&ref_state, &ref[2 * offset], count);
    fm1_mix_limiter_process(&actual_state, &actual[2 * offset], count);
    offset += count;
    if (memcmp(ref, actual, 2u * offset * sizeof(float)) != 0 ||
        memcmp(&ref_state, &actual_state, sizeof(ref_state)) != 0) {
      return 0;
    }
  }
  return 1;
}

int main(void) {
  static const uint32_t chunks[] = {1u, 3u, 7u, 64u, 129u, FRAMES};
  static const float envelopes[] = {0.0f, 0.5f, 0.98f, 1.25f};
  static const float rates[] = {44118.0f, 48000.0f, 96000.0f};
  unsigned checks = 0;
  for (unsigned scenario = 0; scenario < 64; ++scenario) {
    for (unsigned c = 0; c < sizeof(chunks) / sizeof(chunks[0]); ++c) {
      for (unsigned e = 0; e < sizeof(envelopes) / sizeof(envelopes[0]); ++e) {
        for (unsigned r = 0; r < sizeof(rates) / sizeof(rates[0]); ++r) {
          if (!one_case(chunks[c], scenario, envelopes[e], rates[r])) {
            fprintf(stderr, "mismatch scenario=%u chunk=%u envelope=%g rate=%g\n",
                    scenario, chunks[c], envelopes[e], rates[r]);
            return 1;
          }
          ++checks;
        }
      }
    }
  }
  printf("mix limiter optimized/reference exact equivalence: PASS (%u cases)\n", checks);
  return 0;
}
