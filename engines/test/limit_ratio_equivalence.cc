// Compares the optimized limiter against a test-only baseline compiled from
// the same source. Audio and every byte of the pointer-free instance must be
// identical after each render block.
#include "fm1_engine.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_limit;
extern "C" const fm1_engine_t fm1_engine_limit_reference;

namespace {

const uint32_t kMaxFrames = 64;
const uint32_t kTotalFrames = 6000;
alignas(16) unsigned char g_fast[1 << 16];
alignas(16) unsigned char g_reference[1 << 16];
float g_fast_audio[2 * kMaxFrames];
float g_reference_audio[2 * kMaxFrames];

uint32_t g_rng = 0x8f31a92du;
uint32_t Next() { g_rng = g_rng * 1664525u + 1013904223u; return g_rng; }
float Noise() { return static_cast<int32_t>(Next()) / 2147483648.0f; }

int ParamIndex(const fm1_engine_t &engine, const char *name) {
  for (uint16_t i = 0; i < engine.n_params; ++i) {
    if (strcmp(engine.params[i].name, name) == 0) return i;
  }
  return -1;
}

void SetPair(void *fast, void *reference, const char *name, float value) {
  const int index = ParamIndex(fm1_engine_limit, name);
  if (index < 0 || index != ParamIndex(fm1_engine_limit_reference, name)) {
    fprintf(stderr, "parameter mismatch: %s\n", name);
    abort();
  }
  fm1_engine_limit.set_param(fast, static_cast<uint16_t>(index), value);
  fm1_engine_limit_reference.set_param(reference, static_cast<uint16_t>(index), value);
}

bool CheckState(const void *fast, const void *reference, size_t bytes,
                uint32_t scenario, uint32_t frame) {
  if (memcmp(fast, reference, bytes) == 0) return true;
  const unsigned char *a = static_cast<const unsigned char *>(fast);
  const unsigned char *b = static_cast<const unsigned char *>(reference);
  size_t at = 0;
  while (at < bytes && a[at] == b[at]) ++at;
  fprintf(stderr, "state mismatch scenario=%u frame=%u byte=%zu fast=%02x ref=%02x\n",
          scenario, frame, at, at < bytes ? a[at] : 0, at < bytes ? b[at] : 0);
  return false;
}

void Fill(float *dst, uint32_t pos, uint32_t n, uint32_t stereo_case) {
  for (uint32_t i = 0; i < n; ++i) {
    const uint32_t f = pos + i;
    float left = Noise(), right = Noise();
    // Exercise equal peaks both through mono/unlinked material and through
    // linked maxima; the unequal case keeps the two unlinked peaks distinct.
    if (stereo_case == 0) right = left;
    if (stereo_case == 1) {
      left *= 0.35f;
      right *= 1.4f;
    }
    // Loud bursts followed by silence exercise attack, hold and release.
    if ((f / 700u) % 2u == 0u && (f % 700u) < 280u) {
      left *= 12.0f;
      right *= 12.0f;
    } else if ((f % 700u) >= 280u && (f % 700u) < 560u) {
      left = right = 0.0f;
    }
    // Guarded non-finite and out-of-range inputs must retain old behavior.
    if (f % 997u == 11u) left = NAN;
    if (f % 991u == 13u) right = INFINITY;
    if (f % 983u == 17u) left = -23.0f;
    dst[2 * i] = left;
    dst[2 * i + 1] = right;
  }
}

bool RunScenario(uint32_t scenario, float rate, float initial_look,
                 uint32_t stereo_case, float link, uint32_t initial_mode) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, kMaxFrames };
  const size_t fast_bytes = fm1_engine_limit.instance_size(&host);
  const size_t ref_bytes = fm1_engine_limit_reference.instance_size(&host);
  if (fast_bytes != ref_bytes || fast_bytes > sizeof(g_fast)) return false;
  memset(g_fast, 0xa5, sizeof(g_fast));
  memset(g_reference, 0xa5, sizeof(g_reference));
  void *fast = fm1_engine_limit.create(g_fast, &host);
  void *reference = fm1_engine_limit_reference.create(g_reference, &host);
  if (!fast || !reference || !CheckState(g_fast, g_reference, fast_bytes, scenario, 0)) return false;

  SetPair(fast, reference, "Ceiling", -4.0f);
  SetPair(fast, reference, "Drive", 15.0f);
  SetPair(fast, reference, "Release", 18.0f);
  SetPair(fast, reference, "Lookahead", initial_look);
  SetPair(fast, reference, "Mode", static_cast<float>(initial_mode));
  SetPair(fast, reference, "Link", link);
  SetPair(fast, reference, "Mix", 1.0f);

  const uint32_t blocks[] = { 1, 17, 64, 7, 31, 53 };
  uint32_t pos = 0, block_index = 0;
  uint32_t next_transition = 997u, transition_count = 0;
  while (pos < kTotalFrames) {
    // Change settings while the limiter is active, including both directions
    // across zero lookahead, and vary the release/mode/link state. Blocks are
    // split below so every boundary is reached exactly despite irregular sizes.
    if (pos == next_transition) {
      const uint32_t step = transition_count + 1u;
      SetPair(fast, reference, "Lookahead", step % 2u ? 0.0f : 3.7f);
      SetPair(fast, reference, "Ceiling", step % 2u ? -18.0f : -2.0f);
      SetPair(fast, reference, "Release", step % 2u ? 1.0f : 240.0f);
      SetPair(fast, reference, "Mode", static_cast<float>((initial_mode + step) % 3u));
      SetPair(fast, reference, "Link", step % 2u ? 1.0f : 0.0f);
      ++transition_count;
      next_transition += 997u;
    }
    uint32_t n = blocks[block_index++ % (sizeof(blocks) / sizeof(blocks[0]))];
    if (n > kTotalFrames - pos) n = kTotalFrames - pos;
    if (pos < next_transition && n > next_transition - pos) n = next_transition - pos;
    Fill(g_fast_audio, pos, n, stereo_case);
    memcpy(g_reference_audio, g_fast_audio, 2u * n * sizeof(float));
    fm1_engine_limit.render(fast, g_fast_audio, n);
    fm1_engine_limit_reference.render(reference, g_reference_audio, n);
    if (memcmp(g_fast_audio, g_reference_audio, 2u * n * sizeof(float)) != 0) {
      fprintf(stderr, "audio mismatch scenario=%u frame=%u block=%u\n", scenario, pos, n);
      return false;
    }
    pos += n;
    if (!CheckState(g_fast, g_reference, fast_bytes, scenario, pos)) return false;
  }
  const uint32_t expected_transitions = (kTotalFrames - 1u) / 997u;
  if (transition_count != expected_transitions) {
    fprintf(stderr, "transition count mismatch scenario=%u got=%u want=%u\n",
            scenario, transition_count, expected_transitions);
    return false;
  }
  fm1_engine_limit.destroy(fast);
  fm1_engine_limit_reference.destroy(reference);
  return true;
}

}  // namespace

int main() {
  uint32_t scenario = 0;
  const float rates[] = { 44118.0f, 96000.0f };
  const float looks[] = { 0.0f, 2.0f, 5.0f };
  const float links[] = { 0.0f, 0.5f, 1.0f };
  const uint32_t modes[] = { 0, 1, 2 };
  for (size_t r = 0; r < sizeof(rates) / sizeof(rates[0]); ++r) {
    for (size_t l = 0; l < sizeof(looks) / sizeof(looks[0]); ++l) {
      for (size_t stereo = 0; stereo < 2; ++stereo) {
        for (size_t link = 0; link < sizeof(links) / sizeof(links[0]); ++link) {
          for (size_t mode = 0; mode < sizeof(modes) / sizeof(modes[0]); ++mode) {
            if (!RunScenario(scenario, rates[r], looks[l], stereo, links[link], modes[mode])) return 1;
            ++scenario;
          }
        }
      }
    }
  }
  printf("{\"scenarios\":%u,\"frames_per_scenario\":%u,\"transitions_per_scenario\":%u,"
         "\"audio_bitwise_equal\":true,"
         "\"full_instance_state_bitwise_equal\":true}\n", scenario, kTotalFrames,
         (kTotalFrames - 1u) / 997u);
  return 0;
}
