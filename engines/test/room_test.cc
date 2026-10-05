// room_test.cc -- fm1-room-test: drives the Room effect (src/fx_room.cc)
// through its engine struct where fm1-render cannot: parameters that change
// while audio runs (fm1-render sets an effect's parameters only before the
// first block), block sizes that change from call to call, bad input mixed
// into running audio, host rates, the libm-free maths of fx_room_math.h, and
// the time a block takes while settled and while gliding. Prints one JSON
// object; tests/test_engines_room.py reads it. Desktop only. MIT licence.

#include "fm1_engine.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <chrono>

#include "../src/fx_room_math.h"

extern "C" const fm1_engine_t fm1_engine_room;
// The probe build of the effect (FM1_ROOM_PROBE, mk/room.mk): the diffuser's
// cells holding a nonzero value below 1e-20.
extern "C" uint32_t fm1_room_probe_tiny(const void *instance);

namespace {

const fm1_engine_t &E = fm1_engine_room;
const float kRate = 44118.0f;
alignas(16) unsigned char g_mem[64 * 1024];

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

void SetParam(void *self, const char *name, float v) {
  E.set_param(self, static_cast<uint16_t>(Index(name)), v);
}

float RandomValue(Lcg *rng, const fm1_param_t &p) {
  switch (rng->Next() % 8) {
    case 0: return p.min;
    case 1: return p.max;
    case 2: return p.def;
    case 3: return 4 * p.max - 3 * p.min + 1;
    case 4: return NAN;
    case 5: return (rng->Next() & 1) ? INFINITY : -INFINITY;
    default: return p.min + (p.max - p.min) * rng->Unit();
  }
}

// 1. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while noise plays, for 20 s: the output must stay finite and bounded. Then
// 20 s more with bad samples (NaN, infinities, 1e30) mixed into the input
// one block in eight: still finite, and once the input is clean and silent
// the output decays to exact zeros (nothing latched).
void Sweep() {
  void *self = Make(kRate, 0xA5);
  Lcg rng = { 1u };
  float buf[128];
  uint64_t samples = 0, nonfinite = 0, bad_nonfinite = 0;
  float peak = 0.0f, bad_peak = 0.0f;
  const uint64_t phase = static_cast<uint64_t>(20 * kRate);
  while (samples < 2 * phase) {
    const bool bad = samples >= phase;
    const uint32_t n = 1 + rng.Next() % 64;
    for (int changes = rng.Next() % 3; changes > 0; --changes) {
      const fm1_param_t &p = E.params[rng.Next() % E.n_params];
      E.set_param(self, static_cast<uint16_t>(&p - E.params), RandomValue(&rng, p));
    }
    const bool poison = bad && rng.Next() % 8 == 0;
    for (uint32_t i = 0; i < n; ++i) {
      float x = 0.5f * rng.Bipolar();
      if (poison && rng.Next() % 4 == 0) {
        const float kinds[4] = { NAN, INFINITY, -INFINITY, 1e30f };
        x = kinds[rng.Next() % 4];
      }
      buf[2 * i] = x;
      buf[2 * i + 1] = 0.5f * rng.Bipolar();
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < 2 * n; ++i) {
      const float a = fabsf(buf[i]);
      if (!(a <= 3.4e38f)) {
        if (bad) ++bad_nonfinite; else ++nonfinite;
      } else if (bad) {
        if (a > bad_peak) bad_peak = a;
      } else if (a > peak) {
        peak = a;
      }
    }
    samples += n;
  }
  // Recovery: the longest setting short of Decay 1, then silence.
  SetParam(self, "Decay", 0.9f);
  SetParam(self, "Mix", 1.0f);
  float last = 1.0f;
  int blocks = 0;
  for (; blocks < 60 * 690 && last != 0.0f; ++blocks) {     // up to 60 s
    memset(buf, 0, sizeof(buf));
    E.render(self, buf, 64);
    last = 0.0f;
    for (int i = 0; i < 128; ++i) last = fmaxf(last, fabsf(buf[i]));
  }
  E.destroy(self);
  printf("\"sweep\":{\"samples\":%llu,\"nonfinite\":%llu,\"peak\":%.6f,"
         "\"bad_nonfinite\":%llu,\"bad_peak\":%.6f,\"silent_after_s\":%.3f,"
         "\"last_peak\":%.9g}",
         static_cast<unsigned long long>(samples), static_cast<unsigned long long>(nonfinite),
         peak, static_cast<unsigned long long>(bad_nonfinite), bad_peak,
         blocks * 64 / kRate, last);
}

// Noise on both channels (decorrelated), with parameter changes at given
// samples; the render is split at each change, otherwise in blocks of
// `block` frames.
struct Change { uint32_t at; const char *name; float value; };

void RenderNoise(uint32_t block, const Change *changes, int n_changes, uint32_t total,
                 float *out_lr, float *in_lr) {
  void *self = Make(kRate, 0);
  Lcg rng = { 7u };
  float buf[128];
  int next = 0;
  for (uint32_t pos = 0; pos < total;) {
    while (next < n_changes && changes[next].at <= pos) {
      SetParam(self, changes[next].name, changes[next].value);
      ++next;
    }
    uint32_t n = total - pos < block ? total - pos : block;
    if (next < n_changes && changes[next].at - pos < n) n = changes[next].at - pos;
    for (uint32_t i = 0; i < n; ++i) {
      buf[2 * i] = in_lr[2 * (pos + i)] = 0.5f * rng.Bipolar();
      buf[2 * i + 1] = in_lr[2 * (pos + i) + 1] = 0.5f * rng.Bipolar();
    }
    E.render(self, buf, n);
    memcpy(&out_lr[2 * pos], buf, 2 * n * sizeof(float));
    pos += n;
  }
  E.destroy(self);
}

const uint32_t kTotal = 2 * 44118;
float g_a[2 * kTotal], g_b[2 * kTotal], g_c[2 * kTotal], g_in[2 * kTotal];

// 2. The glide: changes mid-stream give the same output whatever the block
// size (rendered at 64, 7 and 1 frames, split at the changes); Mix stepped
// from 1 to 0 fades over a few milliseconds and then gives the input back
// bit for bit, the reverb still running behind it.
void Glide() {
  const Change ch[] = {
    { 0, "Mix", 1.0f }, { 0, "Decay", 0.6f },
    { 4410, "Decay", 1.0f }, { 4410, "Damping", 0.9f }, { 4410, "Diffusion", 0.1f },
    { 11025, "Blur", 1.0f }, { 11025, "Width", 0.2f },
    { 22050, "Decay", 0.0f }, { 22050, "Blur", 0.0f }, { 22050, "Damping", 0.0f },
    { 44118, "Mix", 0.0f },
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  RenderNoise(64, ch, n, kTotal, g_a, g_in);
  RenderNoise(7, ch, n, kTotal, g_b, g_in);
  RenderNoise(1, ch, n, kTotal, g_c, g_in);
  const int same = memcmp(g_a, g_b, sizeof(g_a)) == 0 && memcmp(g_a, g_c, sizeof(g_a)) == 0;
  // The distance from the dry input: before the Mix step (all wet), in its
  // first millisecond, and from 60 ms after it to the end.
  float before = 0.0f, first_ms = 0.0f, after = 0.0f;
  for (uint32_t i = 2 * (44118 - 441); i < 2 * 44118; ++i) {
    before = fmaxf(before, fabsf(g_a[i] - g_in[i]));
  }
  for (uint32_t i = 2 * 44118; i < 2 * (44118 + 44); ++i) {
    first_ms = fmaxf(first_ms, fabsf(g_a[i] - g_in[i]));
  }
  uint32_t exact = 1;
  for (uint32_t i = 2 * (44118 + 2647); i < 2 * kTotal; ++i) {
    after = fmaxf(after, fabsf(g_a[i] - g_in[i]));
    if (memcmp(&g_a[i], &g_in[i], sizeof(float)) != 0 && !(g_a[i] == 0.0f && g_in[i] == 0.0f)) {
      exact = 0;
    }
  }
  // FNV-1a over the output's bits: the same number from every compiler that
  // keeps to IEEE single precision without fused multiply-adds.
  uint32_t hash = 2166136261u;
  for (uint32_t i = 0; i < 2 * kTotal; ++i) {
    uint32_t bits;
    memcpy(&bits, &g_a[i], sizeof bits);
    for (int b = 0; b < 4; ++b) {
      hash ^= (bits >> (8 * b)) & 0xFFu;
      hash *= 16777619u;
    }
  }
  printf("\"glide\":{\"block_independent\":%s,\"before\":%.6f,\"first_ms\":%.6f,"
         "\"after\":%.9g,\"dry_exact\":%s,\"hash\":\"%08x\"}", same ? "true" : "false",
         before, first_ms, after, exact ? "true" : "false", hash);
}

// 3. Silence after a burst: 0.5 s of full-scale noise, then silence, at
// settings that cover the damping coefficient on both sides of 0.5 (below
// it the vendored damping state can stop on a subnormal): seconds until the
// output is exactly zero for good (checked over 2 s more), and how many of
// the diffuser's cells then still hold a tiny nonzero value (without the
// wrapper's sweep, all 2,048 hold a subnormal for good).
void Silence() {
  struct Setting { float decay, damping, blur; };
  const Setting settings[] = {
    { 0.5f, 0.4f, 0.5f }, { 0.8f, 0.0f, 1.0f }, { 0.8f, 1.0f, 0.0f }, { 0.0f, 0.7f, 0.5f },
  };
  printf("\"silence\":[");
  for (size_t k = 0; k < sizeof(settings) / sizeof(settings[0]); ++k) {
    void *self = Make(kRate, 0xFF);
    SetParam(self, "Mix", 1.0f);
    SetParam(self, "Decay", settings[k].decay);
    SetParam(self, "Damping", settings[k].damping);
    SetParam(self, "Blur", settings[k].blur);
    Lcg rng = { 3u };
    float buf[128];
    for (int b = 0; b < 345; ++b) {
      for (int i = 0; i < 128; ++i) buf[i] = rng.Bipolar();
      E.render(self, buf, 64);
    }
    int zero_from = -1, b = 0;
    float tiny = 0.0f;                        // the smallest nonzero |output|
    for (; b < 40 * 690; ++b) {               // 40 s
      memset(buf, 0, sizeof(buf));
      E.render(self, buf, 64);
      float peak = 0.0f;
      for (int i = 0; i < 128; ++i) {
        const float a = fabsf(buf[i]);
        peak = fmaxf(peak, a);
        if (a > 0.0f && (tiny == 0.0f || a < tiny)) tiny = a;
      }
      if (peak == 0.0f) {
        if (zero_from < 0) zero_from = b;
        if (b - zero_from >= 1380) break;     // 2 s of exact zeros
      } else {
        zero_from = -1;
      }
    }
    const uint32_t diffuser_tiny = fm1_room_probe_tiny(self);
    E.destroy(self);
    printf("%s{\"decay\":%g,\"damping\":%g,\"zero_after_s\":%.3f,\"held\":%s,"
           "\"smallest\":%.9g,\"diffuser_tiny\":%u}", k ? "," : "", settings[k].decay,
           settings[k].damping, zero_from < 0 ? -1.0 : zero_from * 64 / kRate,
           zero_from >= 0 && b - zero_from >= 1380 ? "true" : "false", tiny,
           static_cast<unsigned>(diffuser_tiny));
  }
  printf("]");
}

// 4. Host rates: refused outside 8 kHz..384 kHz, and when not a number.
void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 32000.0f, 44118.0f, 48000.0f, 384000.0f,
                          400000.0f, NAN, INFINITY, -44118.0f };
  printf("\"rates\":[");
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    void *self = Make(rates[i], 0);
    printf("%s[\"%g\",%s]", i ? "," : "", rates[i], self ? "true" : "false");
    if (self) E.destroy(self);
  }
  printf("]");
}

// 5. The libm-free maths against libm in double precision.
void Maths() {
  double log2_abs = 0.0, exp2_rel = 0.0, pow_rel = 0.0;
  for (int i = 0; i <= 200000; ++i) {          // x in [2^-20, 1]
    const float x = static_cast<float>(pow(2.0, -20.0 * i / 200000.0));
    log2_abs = fmax(log2_abs, fabs(RoomLog2(x) - log2(static_cast<double>(x))));
  }
  for (int i = 0; i <= 200000; ++i) {          // y in [-30, 0]
    const float y = -30.0f * i / 200000.0f;
    const double want = exp2(static_cast<double>(y));
    exp2_rel = fmax(exp2_rel, fabs(RoomExp2(y) - want) / want);
  }
  // The arguments Room uses: loop gains and one-pole complements in
  // [0.001, 1), at the ratios of 8 kHz to 384 kHz hosts.
  const float ratios[] = { 4.0f, 32000.0f / 44118.0f, 32000.0f / 48000.0f, 32000.0f / 96000.0f,
                           32000.0f / 384000.0f };
  for (size_t k = 0; k < sizeof(ratios) / sizeof(ratios[0]); ++k) {
    for (int i = 1; i < 100000; ++i) {
      const float g = 0.001f + 0.999f * i / 100000.0f;
      const double want = pow(static_cast<double>(g), static_cast<double>(ratios[k]));
      pow_rel = fmax(pow_rel, fabs(RoomPow(g, ratios[k]) - want) / want);
    }
  }
  const float identity = RoomPow(0.6789f, 1.0f);
  // Subnormal and edge arguments stay finite.
  const float sub = RoomPow(1e-40f, 0.25f);
  const double sub_want = pow(1e-40, 0.25);
  printf("\"maths\":{\"log2_abs\":%.3g,\"exp2_rel\":%.3g,\"pow_rel\":%.3g,"
         "\"identity\":%s,\"subnormal_rel\":%.3g,\"exp2_low\":%.9g,\"exp2_high\":%.9g}",
         log2_abs, exp2_rel, pow_rel, identity == 0.6789f ? "true" : "false",
         fabs(sub - sub_want) / sub_want, RoomExp2(-200.0f), RoomExp2(200.0f));
}

// 6. Time per 64-frame block of noise at the defaults, settled, and with a
// parameter moving every block (the classes then run a frame at a time).
void Timing() {
  void *self = Make(kRate, 0);
  Lcg rng = { 11u };
  float buf[128];
  const int blocks = 20000;
  double settled = 0.0, gliding = 0.0;
  for (int pass = 0; pass < 2; ++pass) {
    const auto t0 = std::chrono::steady_clock::now();
    for (int b = 0; b < blocks; ++b) {
      if (pass == 1) SetParam(self, "Decay", (b & 1) ? 0.3f : 0.7f);
      for (int i = 0; i < 128; ++i) buf[i] = 0.5f * rng.Bipolar();
      E.render(self, buf, 64);
    }
    const auto t1 = std::chrono::steady_clock::now();
    const double ns = std::chrono::duration<double, std::nano>(t1 - t0).count() / blocks;
    if (pass == 0) settled = ns; else gliding = ns;
  }
  E.destroy(self);
  fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
  printf("\"timing\":{\"ns_per_block_settled\":%.1f,\"ns_per_block_gliding\":%.1f,"
         "\"instance_bytes\":%zu}", settled, gliding, E.instance_size(&host));
}

}  // namespace

int main() {
  printf("{");
  Sweep(); printf(",");
  Glide(); printf(",");
  Silence(); printf(",");
  Rates(); printf(",");
  Maths(); printf(",");
  Timing();
  printf("}\n");
  return 0;
}
