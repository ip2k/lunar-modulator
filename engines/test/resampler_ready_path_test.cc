// Bitwise differential test for the trusted-ready render helpers.
#include "fm1_resampler.h"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>

static uint32_t bits(float x) {
  uint32_t value;
  std::memcpy(&value, &x, sizeof(value));
  return value;
}

static void same_state(const fm1_resampler_t &a, const fm1_resampler_t &b) {
  assert(std::memcmp(&a, &b, sizeof(a)) == 0);
}

static float sample(uint32_t index) {
  if (index % 4093u == 0) return -0.0f;
  if (index == 8191u) return std::numeric_limits<float>::quiet_NaN();
  if (index == 8192u) return std::numeric_limits<float>::infinity();
  if (index == 8193u) return -std::numeric_limits<float>::infinity();
  if (index >= 12000u && index < 12096u) return 0.0f;
  if (index == 12096u) return 0.75f;  // exact silence-to-impulse transition
  return static_cast<float>(static_cast<int32_t>((index * 37u) % 2001u) - 1000) / 2048.0f;
}

static void exercise(float input_rate, float output_rate, uint32_t block_size,
                     uint32_t chunk_limit, uint32_t frames) {
  fm1_resampler_t checked, ready;
  std::memset(&checked, 0, sizeof(checked));
  std::memset(&ready, 0, sizeof(ready));
  assert(fm1_resampler_init(&checked, input_rate, output_rate));
  assert(fm1_resampler_init(&ready, input_rate, output_rate));
  same_state(checked, ready);

  // The public pop must retain its checked/no-mutation behavior when input is
  // missing. The ready helper is only used after the caller's readiness loop.
  if (fm1_resampler_needed(&checked) != 0) {
    const fm1_resampler_t before = checked;
    assert(bits(fm1_resampler_pop(&checked)) == bits(0.0f));
    same_state(checked, before);
  }

  float block[32];
  uint32_t pending_checked = 0, pending_ready = 0;
  uint32_t input_index = 0, next_chunk = 1;
  for (uint32_t frame = 0; frame < frames; ++frame) {
    uint32_t need_checked = fm1_resampler_needed(&checked);
    uint32_t need_ready = fm1_resampler_needed(&ready);
    assert(need_checked == need_ready);
    while (need_checked != 0) {
      if (pending_checked == 0) {
        assert(pending_ready == 0);
        for (uint32_t i = 0; i < block_size; ++i) block[i] = sample(input_index + i);
        input_index += block_size;
        pending_checked = pending_ready = block_size;
      }
      uint32_t n = std::min(need_checked, pending_checked);
      n = std::min(n, next_chunk);
      next_chunk = next_chunk % chunk_limit + 1;
      const uint32_t took_checked = fm1_resampler_push(&checked, block + block_size - pending_checked, n);
      const uint32_t took_ready = fm1_resampler_push_ready_(&ready, block + block_size - pending_ready, n);
      assert(took_checked == n && took_ready == n);
      pending_checked -= took_checked;
      pending_ready -= took_ready;
      need_checked -= took_checked;
      need_ready -= took_ready;
      assert(need_checked == need_ready);
      same_state(checked, ready);
    }
    const float got = fm1_resampler_pop(&checked);
    const float fast = fm1_resampler_pop_ready_(&ready);
    assert(bits(got) == bits(fast));
    same_state(checked, ready);
  }
}

int main() {
  // Pass mode plus conversion ratios above 1, including the supported 4:1 edge.
  exercise(44118.0f, 44118.0f, 12, 5, 4096);
  exercise(47872.34f, 44118.0f, 12, 5, 8192);
  exercise(96000.0f, 44118.0f, 16, 7, 8192);
  exercise(176472.0f, 44118.0f, 32, 11, 8192);

  fm1_resampler_t off;
  std::memset(&off, 0, sizeof(off));
  assert(!fm1_resampler_init(&off, 1.0f, 100.0f));
  assert(fm1_resampler_needed(&off) == 0);
  assert(fm1_resampler_push_ready_(&off, nullptr, 0) == 0);
  assert(bits(fm1_resampler_pop_ready_(&off)) == bits(0.0f));
  assert(bits(fm1_resampler_pop(&off)) == bits(0.0f));

  std::puts("trusted-ready and checked resampler paths match bit-for-bit");
  return 0;
}
