// Differential checks for the dual-empty-history resampler fast path.
#include "fm1_resampler.h"

#include <algorithm>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <vector>

static uint32_t bits(float x) {
  uint32_t out;
  std::memcpy(&out, &x, sizeof(out));
  return out;
}

/* Exact pre-fastpath ready-pop implementation. This retains the current
 * intermediate zero-history optimization but has no dual-empty pop shortcut. */
#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
static float baseline_pop_ready(fm1_resampler_t *r) {
  const float *h = fm1_resampler_lowpass, *e;
  float y0 = 0.0f, y1 = 0.0f, y2 = 0.0f, y3 = 0.0f;
  uint32_t j;
  if (r->mode != FM1_RESAMPLER_CONVERT) {
    if (!r->held) return 0.0f;
    r->held = 0;
    return r->in[0];
  }
  for (j = 0; j < 2; ++j) {
    const float x = fm1_resampler_intermediate_(r);
    const uint32_t slot = r->mid_w;
    if (r->mid[slot] != 0.0f) --r->mid_nonzero;
    if (x != 0.0f) ++r->mid_nonzero;
    r->mid[slot] = r->mid[slot + FM1_RESAMPLER_MID_CAP] = x;
    if (++r->mid_w == FM1_RESAMPLER_MID_CAP) r->mid_w = 0;
  }
  if (r->mid_nonzero == 0) return 0.0f;
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

static void same_state(const fm1_resampler_t &a, const fm1_resampler_t &b) {
  assert(a.step == b.step);
  assert(a.lead == b.lead);
  assert(a.rel == b.rel);
  assert(a.tap_step == b.tap_step);
  assert(bits(a.gain) == bits(b.gain));
  assert(a.mode == b.mode);
  assert(a.held == b.held);
  assert(a.in_w == b.in_w && a.mid_w == b.mid_w);
  assert(a.in_nonzero == b.in_nonzero && a.mid_nonzero == b.mid_nonzero);
  assert(std::memcmp(a.in, b.in, sizeof(a.in)) == 0);
  assert(std::memcmp(a.mid, b.mid, sizeof(a.mid)) == 0);
}

static void reference_push(fm1_resampler_t *r, const float *in, uint32_t n) {
  uint32_t need = fm1_resampler_needed(r);
  if (n > need) n = need;
  if (r->mode != FM1_RESAMPLER_CONVERT) {
    if (n) { r->in[0] = in[0]; r->held = 1; }
    return;
  }
  for (uint32_t i = 0; i < n; ++i) {
    const uint32_t slot = r->in_w;
    if (r->in[slot] != 0.0f) --r->in_nonzero;
    if (in[i] != 0.0f) ++r->in_nonzero;
    r->in[slot] = r->in[slot + FM1_RESAMPLER_IN_CAP] = in[i];
    if (++r->in_w == FM1_RESAMPLER_IN_CAP) r->in_w = 0;
  }
  r->rel -= (int64_t)n << 32;
}

static void run_case(float input_rate, float output_rate, uint32_t outputs,
                     uint32_t seed, bool reset_and_change_rate = false) {
  fm1_resampler_t fast, baseline;
  const float negative_zero = -0.0f;
  const float nan = std::numeric_limits<float>::quiet_NaN();
  const float inf = std::numeric_limits<float>::infinity();
  assert(fm1_resampler_init(&fast, input_rate, output_rate));
  assert(fm1_resampler_init(&baseline, input_rate, output_rate));
  same_state(fast, baseline);

  std::vector<float> input(static_cast<size_t>(outputs) * 4u + 128u, 0.0f);
  for (size_t i = 8; i < 48 && i < input.size(); ++i) input[i] = negative_zero;
  for (size_t i = 60; i < 65 && i < input.size(); ++i) input[i] = 1.0f;
  if (input.size() > 100) input[100] = 0.75f;
  if (input.size() > 4095) input[4095] = -0.75f;
  if (input.size() > 8191) {
    input[8191] = nan;
    input[8192] = inf;
    input[8193] = -inf;
  }
  if (input.size() > 10000)
    for (size_t i = 10000; i < 10200; ++i)
      input[i] = (i & 1) ? -0.125f : 0.25f;
  if (input.size() > 12000) input[12000] = 0.5f;
  const float zeros[16] = {};

  size_t used = 0;
  uint32_t zero_outputs = 0;
  for (uint32_t out = 0; out < outputs; ++out) {
    if (reset_and_change_rate && out == outputs / 2u) {
      /* Reset a live, nonempty stream and change rates; both histories must
       * clear identically before the new stream starts. */
      assert(fm1_resampler_init(&fast, 96000.0f, 44118.0f));
      assert(fm1_resampler_init(&baseline, 96000.0f, 44118.0f));
      used = 0;
      same_state(fast, baseline);
    }
    while (fm1_resampler_needed(&fast)) {
      const uint32_t need = fm1_resampler_needed(&fast);
      seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5;
      const uint32_t chunk = 1u + seed % 11u;
      const float *src = used < input.size() ? &input[used] : zeros;
      const size_t available = used < input.size() ? input.size() - used : 16u;
      const uint32_t n = static_cast<uint32_t>(std::min<size_t>(need, std::min<size_t>(chunk, available)));
      assert(n != 0);
      assert(fm1_resampler_push(&fast, src, n) == n);
      reference_push(&baseline, src, n);
      if (used < input.size()) used += n;
      same_state(fast, baseline);
    }
    const float got = fm1_resampler_pop(&fast);
    const float want = baseline_pop_ready(&baseline);
    assert(bits(got) == bits(want));
    same_state(fast, baseline);
    if (got == 0.0f) ++zero_outputs;
  }
  assert(zero_outputs > outputs / 20u);
}

static double timed_ns_per_output(bool use_baseline, uint32_t outputs) {
  fm1_resampler_t r;
  assert(fm1_resampler_init(&r, 47872.34f, 44118.0f));
  const float zeros[16] = {};
  uint32_t checksum = 0;
  const auto start = std::chrono::steady_clock::now();
  for (uint32_t i = 0; i < outputs; ++i) {
    uint32_t need = fm1_resampler_needed(&r);
    while (need) {
      const uint32_t n = std::min<uint32_t>(need, 16u);
      fm1_resampler_push_ready_(&r, zeros, n);
      need -= n;
    }
    const float y = use_baseline ? baseline_pop_ready(&r) : fm1_resampler_pop_ready_(&r);
    checksum = checksum * 33u + bits(y);
  }
  const auto end = std::chrono::steady_clock::now();
  volatile uint32_t keep = checksum;
  (void)keep;
  return std::chrono::duration<double, std::nano>(end - start).count() / outputs;
}

static void bench() {
  const uint32_t count = 1200000;
  const int repetitions = 7;
  (void)timed_ns_per_output(false, 100000);
  (void)timed_ns_per_output(true, 100000);
  std::vector<double> old_ns, new_ns;
  for (int i = 0; i < repetitions; ++i) {
    if (i & 1) {
      old_ns.push_back(timed_ns_per_output(true, count));
      new_ns.push_back(timed_ns_per_output(false, count));
    } else {
      new_ns.push_back(timed_ns_per_output(false, count));
      old_ns.push_back(timed_ns_per_output(true, count));
    }
  }
  std::sort(old_ns.begin(), old_ns.end());
  std::sort(new_ns.begin(), new_ns.end());
  std::printf("host silent resampler: prior %.2f ns/output, candidate %.2f ns/output, ratio %.3fx (median of %d; %u outputs/run)\n",
              old_ns[repetitions / 2], new_ns[repetitions / 2],
              old_ns[repetitions / 2] / new_ns[repetitions / 2], repetitions, count);
}

int main(int argc, char **argv) {
  if (argc > 1 && std::strcmp(argv[1], "--bench") == 0) {
    bench();
    return 0;
  }
  run_case(47872.34f, 44118.0f, 22000, 0x13579bdfu, true);
  run_case(96000.0f, 44118.0f, 4000, 0x2468ace1u);
  run_case(44118.0f, 44118.0f, 128, 0x10293847u);
  fm1_resampler_t off_a, off_b;
  assert(!fm1_resampler_init(&off_a, 0.0f, 44118.0f));
  assert(!fm1_resampler_init(&off_b, 0.0f, 44118.0f));
  same_state(off_a, off_b);
  for (uint32_t i = 0; i < 8; ++i) {
    assert(bits(fm1_resampler_pop(&off_a)) == bits(baseline_pop_ready(&off_b)));
    same_state(off_a, off_b);
  }
  std::puts("zero-pop fast path matches prior ready-pop bit-for-bit, including full ring state");
  return 0;
}
