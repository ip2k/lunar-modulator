// fold_test.cc -- fm1-fold-test: drives the Fold effect (src/fx_fold.cc)
// through its engine struct where fm1-render cannot: parameters that change
// while audio runs (fm1-render sets an effect's parameters only before the
// first block), block sizes that change from call to call, and host rates.
// Prints one JSON object; tests/test_engines_fold.py reads it. MIT licence.

#include "fm1_engine.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_fold;

namespace {

const fm1_engine_t &E = fm1_engine_fold;
const float kRate = 44118.0f;
alignas(16) unsigned char g_mem[4096];

struct Lcg {
  uint32_t s;
  uint32_t Next() { s = s * 1664525u + 1013904223u; return s; }
  float Bipolar() { return static_cast<int32_t>(Next()) / 2147483648.0f; }  // [-1, 1)
  float Unit() { return (Next() >> 8) / 16777216.0f; }                        // [0, 1)
};

void *Make(float rate, int fill) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  const size_t n = E.instance_size(&host);
  if (n > sizeof(g_mem)) return NULL;
  memset(g_mem, fill, sizeof(g_mem));
  return E.create(g_mem, &host);
}

int Index(const char *name) {
  for (uint16_t i = 0; i < E.n_params; ++i) {
    if (strcmp(E.params[i].name, name) == 0) return i;
  }
  return -1;
}

// 1. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while noise plays, for 20 s. The output must stay finite and bounded.
void Sweep() {
  void *self = Make(kRate, 0xA5);
  Lcg rng = { 1u };
  float buf[128];
  uint64_t samples = 0, nonfinite = 0;
  float peak = 0.0f;
  while (samples < static_cast<uint64_t>(20 * kRate)) {
    const uint32_t n = 1 + rng.Next() % 64;
    for (int changes = rng.Next() % 3; changes > 0; --changes) {
      const fm1_param_t &p = E.params[rng.Next() % E.n_params];
      float v;
      switch (rng.Next() % 8) {
        case 0: v = p.min; break;
        case 1: v = p.max; break;
        case 2: v = p.def; break;
        case 3: v = 4 * p.max - 3 * p.min + 1; break;
        case 4: v = NAN; break;
        case 5: v = (rng.Next() & 1) ? INFINITY : -INFINITY; break;
        default: v = p.min + (p.max - p.min) * rng.Unit(); break;
      }
      E.set_param(self, static_cast<uint16_t>(&p - E.params), v);
    }
    for (uint32_t i = 0; i < n; ++i) buf[2 * i] = buf[2 * i + 1] = 0.5f * rng.Bipolar();
    E.render(self, buf, n);
    for (uint32_t i = 0; i < 2 * n; ++i) {
      if (!(fabsf(buf[i]) <= 3.4e38f)) ++nonfinite;            // NaN or infinite
      else if (fabsf(buf[i]) > peak) peak = fabsf(buf[i]);
    }
    samples += n;
  }
  E.destroy(self);
  printf("\"sweep\":{\"samples\":%llu,\"nonfinite\":%llu,\"peak\":%.6f}",
         static_cast<unsigned long long>(samples), static_cast<unsigned long long>(nonfinite),
         peak);
}

// A 440 Hz sine on both channels, with parameter changes at given samples.
struct Change { uint32_t at; const char *name; float value; };

void RenderSine(uint32_t block, const Change *changes, int n_changes, uint32_t total,
                float amplitude, float *out_left) {
  void *self = Make(kRate, 0);
  float buf[128];
  double phase = 0.0;
  int next = 0;
  for (uint32_t pos = 0; pos < total;) {
    while (next < n_changes && changes[next].at <= pos) {
      E.set_param(self, static_cast<uint16_t>(Index(changes[next].name)), changes[next].value);
      ++next;
    }
    uint32_t n = total - pos < block ? total - pos : block;
    if (next < n_changes && changes[next].at - pos < n) n = changes[next].at - pos;
    for (uint32_t i = 0; i < n; ++i) {
      const float x = amplitude * static_cast<float>(sin(phase));
      phase += 2.0 * 3.141592653589793 * 440.0 / kRate;
      buf[2 * i] = buf[2 * i + 1] = x;
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < n; ++i) out_left[pos + i] = buf[2 * i];
    pos += n;
  }
  E.destroy(self);
}

const uint32_t kTotal = 44118;
float g_a[kTotal], g_b[kTotal], g_c[kTotal];

// 2. The glide: changes mid-stream give the same output whatever the block
// size (changes on sample 4410 and 22050, rendered at 64, 7 and 1 frames,
// split at the changes), and a step of Level from 1 to 0 fades over a few
// milliseconds, then reaches exact silence.
void Glide() {
  const Change ch[] = {
    { 0, "Fold", 0.6f }, { 0, "Tone", 1.0f }, { 0, "Level", 1.0f },
    { 4410, "Fold", 1.0f }, { 4410, "Symmetry", 0.5f }, { 4410, "Shape", 0.7f },
    { 4410, "Tone", 0.3f }, { 4410, "Mix", 0.6f },
    { 22050, "Level", 0.0f }, { 22050, "Mix", 1.0f },
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  RenderSine(64, ch, n, kTotal, 0.5f, g_a);
  RenderSine(7, ch, n, kTotal, 0.5f, g_b);
  RenderSine(1, ch, n, kTotal, 0.5f, g_c);
  int same = memcmp(g_a, g_b, sizeof(g_a)) == 0 && memcmp(g_a, g_c, sizeof(g_a)) == 0;
  float before = 0.0f, first_ms = 0.0f, tail = 0.0f;
  for (uint32_t i = 22050 - 441; i < 22050; ++i) before = fmaxf(before, fabsf(g_a[i]));
  for (uint32_t i = 22050; i < 22050 + 44; ++i) first_ms = fmaxf(first_ms, fabsf(g_a[i]));
  for (uint32_t i = 22050 + 2205; i < kTotal; ++i) tail = fmaxf(tail, fabsf(g_a[i]));
  printf("\"glide\":{\"block_independent\":%s,\"before\":%.6f,\"first_ms\":%.6f,"
         "\"tail\":%.9g}", same ? "true" : "false", before, first_ms, tail);
}

// 3. Silence in while Symmetry, Shape and Fold move: next to nothing while
// they glide (the fold of silence is subtracted as it moves; without that,
// Symmetry would step the output by up to 1), a DC-blocker tail after, and
// exact silence once the filter states flush.
void Silence() {
  void *self = Make(kRate, 0xFF);
  float buf[128];
  float moving = 0.0f, settled = 0.0f;
  const float sym[] = { 0.0f, 1.0f, -1.0f, 0.3f, -0.7f };
  const float shape[] = { 0.0f, 0.5f, 1.0f, 0.2f, 0.9f };
  for (int step = 0; step < 5; ++step) {
    E.set_param(self, static_cast<uint16_t>(Index("Symmetry")), sym[step]);
    E.set_param(self, static_cast<uint16_t>(Index("Shape")), shape[step]);
    E.set_param(self, static_cast<uint16_t>(Index("Fold")), 0.25f * step);
    for (int b = 0; b < 200; ++b) {                     // 290 ms per step
      memset(buf, 0, sizeof(buf));
      E.render(self, buf, 64);
      for (int i = 0; i < 128; ++i) {
        if (b < 100) moving = fmaxf(moving, fabsf(buf[i]));
        else settled = fmaxf(settled, fabsf(buf[i]));
      }
    }
  }
  float last = 0.0f;
  for (int b = 0; b < 1400; ++b) {                      // 2 s more
    memset(buf, 0, sizeof(buf));
    E.render(self, buf, 64);
    if (b == 1399) {
      for (int i = 0; i < 128; ++i) last = fmaxf(last, fabsf(buf[i]));
    }
  }
  E.destroy(self);
  printf("\"silence\":{\"moving_peak\":%.9g,\"settled_peak\":%.9g,\"last_block_peak\":%.9g}",
         moving, settled, last);
}

// 4. Host rates: refused outside 8 kHz..384 kHz, and when not a number.
void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 44118.0f, 48000.0f, 96000.0f, 384000.0f,
                          400000.0f, NAN, INFINITY, -44118.0f };
  printf("\"rates\":[");
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    void *self = Make(rates[i], 0);
    printf("%s[\"%g\",%s]", i ? "," : "", rates[i], self ? "true" : "false");
    if (self) E.destroy(self);
  }
  printf("]");
}

}  // namespace

int main() {
  printf("{");
  Sweep(); printf(",");
  Glide(); printf(",");
  Silence(); printf(",");
  Rates();
  printf("}\n");
  return 0;
}
