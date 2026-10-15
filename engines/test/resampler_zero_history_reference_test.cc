// Bitwise differential test for the exact-zero FIR fast path.
#include "fm1_resampler.h"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <vector>

static float reference_intermediate(fm1_resampler_t *r) {
  const uint32_t ts = r->tap_step;
  const uint32_t end = (uint32_t)(FM1_RESAMPLER_KERNEL_LEN - 1) << 16;
  const int64_t rel = r->rel;
  const uint32_t frac = (uint32_t)((uint64_t)rel & 0xFFFFFFFFu);
  const float *before = &r->in[r->in_w + FM1_RESAMPLER_IN_CAP - 1] + (rel >> 32) + 1;
  const float *after = before + 1;
  uint32_t tb = (uint32_t)(((uint64_t)frac * ts) >> 32);
  uint32_t ta = (uint32_t)((((uint64_t)1 << 32) - frac) * ts >> 32);
  float sb = 0.0f, sa = 0.0f;
  for (; tb < end && ta < end; tb += ts, ta += ts, --before, ++after) {
    sb += fm1_resampler_tap_(tb) * *before;
    sa += fm1_resampler_tap_(ta) * *after;
  }
  for (; tb < end; tb += ts, --before) sb += fm1_resampler_tap_(tb) * *before;
  for (; ta < end; ta += ts, ++after) sa += fm1_resampler_tap_(ta) * *after;
  r->rel = rel + r->step;
  return (sb + sa) * r->gain;
}

static float reference_pop(fm1_resampler_t *r) {
  const float *h = fm1_resampler_lowpass, *e;
  float y0 = 0.0f, y1 = 0.0f, y2 = 0.0f, y3 = 0.0f;
  uint32_t j;
  if (r->mode != FM1_RESAMPLER_CONVERT) {
    if (!r->held) return 0.0f;
    r->held = 0;
    return r->in[0];
  }
  if (fm1_resampler_needed(r)) return 0.0f;
  for (j = 0; j < 2; ++j) {
    const float x = reference_intermediate(r);
    r->mid[r->mid_w] = r->mid[r->mid_w + FM1_RESAMPLER_MID_CAP] = x;
    if (++r->mid_w == FM1_RESAMPLER_MID_CAP) r->mid_w = 0;
  }
  e = &r->mid[r->mid_w];
  for (j = 0; j + 4 <= FM1_RESAMPLER_LP_PAIRS; j += 4) {
    y0 += h[j] * (e[j] + e[FM1_RESAMPLER_LP_LEN - 1 - j]);
    y1 += h[j + 1] * (e[j + 1] + e[FM1_RESAMPLER_LP_LEN - 2 - j]);
    y2 += h[j + 2] * (e[j + 2] + e[FM1_RESAMPLER_LP_LEN - 3 - j]);
    y3 += h[j + 3] * (e[j + 3] + e[FM1_RESAMPLER_LP_LEN - 4 - j]);
  }
  for (; j < FM1_RESAMPLER_LP_PAIRS; ++j)
    y0 += h[j] * (e[j] + e[FM1_RESAMPLER_LP_LEN - 1 - j]);
  return ((y0 + y1) + (y2 + y3)) + h[FM1_RESAMPLER_LP_PAIRS] * e[FM1_RESAMPLER_LP_PAIRS];
}

static uint32_t bits(float x) {
  uint32_t out;
  std::memcpy(&out, &x, sizeof(out));
  return out;
}

static void reference_push(fm1_resampler_t *r, const float *in, uint32_t n) {
  uint32_t need = fm1_resampler_needed(r);
  if (n > need) n = need;
  for (uint32_t i = 0; i < n; ++i) {
    r->in[r->in_w] = r->in[r->in_w + FM1_RESAMPLER_IN_CAP] = in[i];
    if (++r->in_w == FM1_RESAMPLER_IN_CAP) r->in_w = 0;
  }
  r->rel -= (int64_t)n << 32;
}

int main() {
  fm1_resampler_t fast, slow;
  const float negative_zero = -0.0f;
  const float nan = std::numeric_limits<float>::quiet_NaN();
  const float inf = std::numeric_limits<float>::infinity();
  assert(fm1_resampler_init(&fast, 47872.34f, 44118.0f));
  assert(fm1_resampler_init(&slow, 47872.34f, 44118.0f));

  std::vector<float> input(24000, 0.0f);
  // Exercise cold silence, signed zeros, silence->impulse, dense signal,
  // non-finite values, long silence, and enough wraps to retire every sample.
  for (size_t i = 40; i < 90; ++i) input[i] = negative_zero;
  input[123] = 1.0f;
  input[4095] = -0.75f;
  input[8191] = nan;
  input[8192] = inf;
  input[8193] = -inf;
  for (size_t i = 10000; i < 10200; ++i)
    input[i] = (i & 1) ? -0.125f : 0.25f;
  input[12000] = 0.5f;

  size_t used = 0;
  uint32_t compared = 0, zero_outputs = 0;
  while (compared < 22000) {
    uint32_t need = fm1_resampler_needed(&fast);
    if (need) {
      const uint32_t n = static_cast<uint32_t>(std::min<size_t>(need, input.size() - used));
      if (!n) break;
      const uint32_t took = fm1_resampler_push(&fast, &input[used], n);
      reference_push(&slow, &input[used], n);
      assert(took == n);
      used += took;
    }
    assert(fm1_resampler_needed(&fast) == fm1_resampler_needed(&slow));
    float got = fm1_resampler_pop(&fast);
    float want = reference_pop(&slow);
    assert(bits(got) == bits(want));
    if (got == 0.0f) ++zero_outputs;
    ++compared;
  }
  assert(compared == 22000);
  assert(zero_outputs > 1000);

  // Ring accounting must be exact after many wraps and after NaN/Inf retire.
  uint32_t input_count = 0, mid_count = 0;
  for (uint32_t i = 0; i < FM1_RESAMPLER_IN_CAP; ++i)
    if (fast.in[i] != 0.0f) ++input_count;
  for (uint32_t i = 0; i < FM1_RESAMPLER_MID_CAP; ++i)
    if (fast.mid[i] != 0.0f) ++mid_count;
  assert(fast.in_nonzero == input_count);
  assert(fast.mid_nonzero == mid_count);
  std::puts("zero-history fast path matches reference bit-for-bit");
}
