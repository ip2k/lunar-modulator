// comp_test.cc -- fm1-comp-test: drives the Comp effect (src/fx_comp.cc)
// through its engine struct and its reduction accessor (include/fm1_comp.h)
// where fm1-render cannot: the static curve and the time constants measured
// on exact test signals, parameters changed while audio runs at any block
// size, the hand-over when Character or Auto Rel changes, release to
// exact zeros, host rates, the accuracy of fx_comp_math.h against libm, and
// the cost per block. Prints one JSON object; tests/test_engines_comp.py
// reads it. MIT licence.

#include "fm1_comp.h"
#include "fm1_engine.h"
#include "../src/fx_comp_math.h"

#include <chrono>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_comp;

namespace {

const fm1_engine_t &E = fm1_engine_comp;
const float kRate = 44118.0f;
alignas(16) unsigned char g_mem[2][1024];

struct Lcg {
  uint32_t s;
  uint32_t Next() { s = s * 1664525u + 1013904223u; return s; }
  float Bipolar() { return static_cast<int32_t>(Next()) / 2147483648.0f; }  // [-1, 1)
  float Unit() { return (Next() >> 8) / 16777216.0f; }                        // [0, 1)
};

void *Make(float rate, int fill, int slot = 0) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  const size_t n = E.instance_size(&host);
  if (n > sizeof(g_mem[slot])) return NULL;
  memset(g_mem[slot], fill, sizeof(g_mem[slot]));
  return E.create(g_mem[slot], &host);
}

int Index(const char *name) {
  for (uint16_t i = 0; i < E.n_params; ++i) {
    if (strcmp(E.params[i].name, name) == 0) return i;
  }
  return -1;
}

void Set(void *self, const char *name, float v) {
  E.set_param(self, static_cast<uint16_t>(Index(name)), v);
}

// A setting: name and value.
struct Kv { const char *name; float value; };

void SetAll(void *self, const Kv *kv, int n) {
  for (int i = 0; i < n; ++i) Set(self, kv[i].name, kv[i].value);
}

// One frame of a constant stereo level; returns the left output.
float Frame(void *self, float x) {
  float buf[2] = { x, x };
  E.render(self, buf, 1);
  return buf[0];
}

float Db(float lin) { return 20.0f * log10f(lin); }

// 1. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while noise plays, for 20 s. The output must stay finite.
void Sweep() {
  void *self = Make(kRate, 0xA5);
  Lcg rng = { 1u };
  float buf[128];
  uint64_t samples = 0, nonfinite = 0;
  float peak = 0.0f, worst_reduction = 0.0f;
  int bad_reduction = 0;
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
    const float level = (rng.Next() % 4 == 0) ? 4.0f : 0.5f;   // overs too
    for (uint32_t i = 0; i < n; ++i) {
      buf[2 * i] = level * rng.Bipolar();
      buf[2 * i + 1] = level * rng.Bipolar();
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < 2 * n; ++i) {
      if (!(fabsf(buf[i]) <= 3.4e38f)) ++nonfinite;            // NaN or infinite
      else if (fabsf(buf[i]) > peak) peak = fabsf(buf[i]);
    }
    const float red = fm1_comp_reduction_db(self);
    if (!(red >= 0.0f && red < 200.0f)) ++bad_reduction;
    else if (red > worst_reduction) worst_reduction = red;
    samples += n;
  }
  E.destroy(self);
  printf("\"sweep\":{\"samples\":%llu,\"nonfinite\":%llu,\"peak\":%.6f,"
         "\"bad_reduction\":%d,\"max_reduction\":%.4f,\"null_reads\":%.1f}",
         static_cast<unsigned long long>(samples), static_cast<unsigned long long>(nonfinite),
         peak, bad_reduction, worst_reduction, fm1_comp_reduction_db(NULL));
}

// A 440 Hz sine on both channels, with parameter changes at given samples.
struct Change { uint32_t at; const char *name; float value; };

void RenderSine(uint32_t block, const Change *changes, int n_changes, uint32_t total,
                float amplitude, float *out_left, float *out_reduction) {
  void *self = Make(kRate, 0);
  float buf[128];
  double phase = 0.0;
  int next = 0;
  for (uint32_t pos = 0; pos < total;) {
    while (next < n_changes && changes[next].at <= pos) {
      Set(self, changes[next].name, changes[next].value);
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
    if (out_reduction) out_reduction[pos + n - 1] = fm1_comp_reduction_db(self);
    pos += n;
  }
  E.destroy(self);
}

const uint32_t kTotal = 44118;
const uint32_t kStep = 30000;    // the Makeup step, 280 ms after the last release began
float g_a[kTotal], g_b[kTotal], g_c[kTotal];

// 2. Changes mid-stream give the same output whatever the block size
// (rendered at 64, 7 and 1 frames, split at the changes; every parameter,
// both hand-overs and the detector crossfade among them), and a step of
// Makeup glides: 0 to +12 dB on an uncompressed sine reaches its target
// within 50 ms, not at once.
void Glide() {
  const Change ch[] = {
    { 0, "Threshold", -30.0f }, { 0, "Character", 2.0f }, { 0, "Auto Rel", 1.0f },
    { 4410, "Ratio", 21.0f }, { 4410, "Knee", 0.0f }, { 4410, "Attack", 0.0f },
    { 8820, "Character", 3.0f }, { 8820, "Mix", 0.4f }, { 8820, "Auto Gain", 1.0f },
    { 13230, "Character", 1.0f }, { 13230, "Release", 40.0f }, { 13230, "Auto Rel", 0.0f },
    { 17640, "Threshold", 0.0f }, { 17640, "Mix", 1.0f }, { 17640, "Auto Gain", 0.0f },
    { 17640, "Character", 0.0f }, { 17640, "Release", 10.0f },
    { kStep, "Makeup", 12.0f },
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  RenderSine(64, ch, n, kTotal, 0.25f, g_a, NULL);
  RenderSine(7, ch, n, kTotal, 0.25f, g_b, NULL);
  RenderSine(1, ch, n, kTotal, 0.25f, g_c, NULL);
  const int same = memcmp(g_a, g_b, sizeof(g_a)) == 0 && memcmp(g_a, g_c, sizeof(g_a)) == 0;
  float before = 0.0f, first_ms = 0.0f, tail = 0.0f;
  for (uint32_t i = kStep - 441; i < kStep; ++i) before = fmaxf(before, fabsf(g_a[i]));
  for (uint32_t i = kStep; i < kStep + 44; ++i) first_ms = fmaxf(first_ms, fabsf(g_a[i]));
  for (uint32_t i = kStep + 2205; i < kTotal; ++i) tail = fmaxf(tail, fabsf(g_a[i]));
  printf("\"glide\":{\"block_independent\":%s,\"before\":%.6f,\"first_ms\":%.6f,"
         "\"tail\":%.6f}", same ? "true" : "false", before, first_ms, tail);
}

// 3. The static curve: a fresh instance per point, Peak, Attack 0 (the
// reduction is the curve's from the first frame), a constant input of each
// level. Reports the accessor's reduction and the measured gain in dB.
void Curve() {
  const float ratios[] = { 1.0f, 1.5f, 2.0f, 4.0f, 10.0f, 20.0f, 20.5f, 21.0f };
  const float knees[] = { 0.0f, 6.0f, 12.0f, 24.0f };
  const float thresholds[] = { -40.0f, -20.0f, 0.0f };
  printf("\"curve\":[");
  int first = 1;
  for (float t : thresholds) {
    for (float ratio : ratios) {
      for (float knee : knees) {
        for (int step = 0; step <= 32; ++step) {
          const float level_db = -60.0f + 2.5f * step;            // -60..+20 dB
          const float x = powf(10.0f, level_db / 20.0f);
          void *self = Make(kRate, 0x5A);
          const Kv kv[] = { { "Threshold", t }, { "Ratio", ratio }, { "Knee", knee },
                            { "Attack", 0.0f }, { "Release", 10.0f }, { "Makeup", 0.0f },
                            { "Mix", 1.0f }, { "Character", 0.0f } };
          SetAll(self, kv, 8);
          float y = 0.0f;
          for (int i = 0; i < 64; ++i) y = Frame(self, x);
          printf("%s[%g,%g,%g,%g,%.7f,%.7f]", first ? "" : ",", t, ratio, knee, level_db,
                 fm1_comp_reduction_db(self), -Db(y / x));
          first = 0;
          E.destroy(self);
        }
      }
    }
  }
  printf("]");
}

// Frames until the accessor's reduction first passes `goal` (rising) or
// falls to it (falling); -1 if it never does within `limit`.
long Until(void *self, float x, float goal, bool rising, long limit) {
  for (long n = 0; n < limit; ++n) {
    Frame(self, x);
    const float r = fm1_comp_reduction_db(self);
    if (rising ? r >= goal : r <= goal) return n + 1;
  }
  return -1;
}

// 4. Time constants: a step from silence to a constant 0 dBFS with the
// threshold at -40 dB and Ratio 21 asks for 40 dB of reduction; the attack
// time is when the reduction passes 63.2 % of it. Then silence: the release
// time is when it has fallen to 36.8 %. Per Character, and Auto Rel's
// two releases after a short and a long burst.
void Times() {
  const float target = 40.0f, up = target * (1.0f - expf(-1.0f)), down = target * expf(-1.0f);
  const float attacks[] = { 2.0f, 10.0f, 50.0f };
  const float releases[] = { 50.0f, 200.0f, 1000.0f };
  const char *names[] = { "peak", "rms", "glue", "punch" };
  printf("\"times\":{");
  for (int character = 0; character < 4; ++character) {
    printf("%s\"%s\":{\"attack\":[", character ? "," : "", names[character]);
    for (int i = 0; i < 3; ++i) {
      void *self = Make(kRate, 0);
      const Kv kv[] = { { "Threshold", -40.0f }, { "Ratio", 21.0f }, { "Knee", 0.0f },
                        { "Attack", attacks[i] }, { "Release", 1000.0f },
                        { "Character", static_cast<float>(character) } };
      SetAll(self, kv, 6);
      const long n = Until(self, 1.0f, up, true, 5 * 44118);
      printf("%s[%g,%.3f]", i ? "," : "", attacks[i], 1000.0 * n / kRate);
      E.destroy(self);
    }
    printf("],\"release\":[");
    for (int i = 0; i < 3; ++i) {
      void *self = Make(kRate, 0);
      const Kv kv[] = { { "Threshold", -40.0f }, { "Ratio", 21.0f }, { "Knee", 0.0f },
                        { "Attack", 1.0f }, { "Release", releases[i] },
                        { "Character", static_cast<float>(character) } };
      SetAll(self, kv, 6);
      for (int k = 0; k < 2 * 44118; ++k) Frame(self, 1.0f);       // settle at 40 dB
      const float settled = fm1_comp_reduction_db(self);
      const long n = Until(self, 0.0f, down, false, 20 * 44118);
      printf("%s[%g,%.3f,%.5f]", i ? "," : "", releases[i], 1000.0 * n / kRate, settled);
      E.destroy(self);
    }
    printf("]}");
  }
  // Auto Rel, Release 500 ms (first stage 100 ms), Attack 1 ms.
  printf(",\"auto\":[");
  const float bursts[] = { 0.01f, 2.0f };
  for (int b = 0; b < 2; ++b) {
    for (int on = 0; on < 2; ++on) {
      void *self = Make(kRate, 0);
      const Kv kv[] = { { "Threshold", -40.0f }, { "Ratio", 21.0f }, { "Knee", 0.0f },
                        { "Attack", 1.0f }, { "Release", 500.0f },
                        { "Auto Rel", static_cast<float>(on) } };
      SetAll(self, kv, 6);
      const int frames = static_cast<int>(bursts[b] * kRate);
      for (int k = 0; k < frames; ++k) Frame(self, 1.0f);
      const float start = fm1_comp_reduction_db(self);
      const long n = Until(self, 0.0f, start * expf(-1.0f), false, 20 * 44118);
      printf("%s[%g,%d,%.4f,%.3f]", (b || on) ? "," : "", bursts[b], on, start,
             1000.0 * n / kRate);
      E.destroy(self);
    }
  }
  printf("]}");
}

// 5. Silence after loud noise: every output sample is exactly zero, the
// reduction only falls (no pumping), and reaches exactly 0.
void Silence() {
  const char *names[] = { "peak", "rms", "glue", "punch", "auto" };
  printf("\"silence\":{");
  for (int c = 0; c < 5; ++c) {
    void *self = Make(kRate, 0xFF);
    const Kv kv[] = { { "Threshold", -40.0f }, { "Ratio", 8.0f }, { "Release", 300.0f },
                      { "Makeup", 18.0f }, { "Auto Gain", 1.0f },
                      { "Character", static_cast<float>(c < 4 ? c : 2) },
                      { "Auto Rel", c == 4 ? 1.0f : 0.0f } };
    SetAll(self, kv, 7);
    Lcg rng = { 7u };
    float buf[128];
    for (int b = 0; b < 700; ++b) {                      // 1 s of loud noise
      for (int i = 0; i < 128; ++i) buf[i] = 0.9f * rng.Bipolar();
      E.render(self, buf, 64);
    }
    const float start = fm1_comp_reduction_db(self);
    float out_peak = 0.0f, prev = start;
    int rises = 0;
    long zero_at = -1;
    for (int b = 0; b < 6000; ++b) {                     // 8.7 s of silence
      memset(buf, 0, sizeof(buf));
      E.render(self, buf, 64);
      for (int i = 0; i < 128; ++i) out_peak = fmaxf(out_peak, fabsf(buf[i]));
      const float r = fm1_comp_reduction_db(self);
      if (r > prev) ++rises;
      if (r == 0.0f && zero_at < 0) zero_at = b;
      prev = r;
    }
    printf("%s\"%s\":{\"start\":%.4f,\"out_peak\":%.9g,\"rises\":%d,\"zero_ms\":%.1f,"
           "\"end\":%.9g}", c ? "," : "", names[c], start, out_peak, rises,
           zero_at < 0 ? -1.0 : 1000.0 * 64 * (zero_at + 1) / kRate, prev);
    E.destroy(self);
  }
  printf("}");
}

// 6. A steady sine: the reduction's ripple (no pumping on a steady tone),
// and the RMS detectors read a sine's peak level, so the static reduction is
// the same for each Character.
void Steady() {
  const char *names[] = { "peak", "rms", "glue", "punch" };
  const float freqs[] = { 440.0f, 100.0f };
  printf("\"steady\":{");
  for (int c = 0; c < 4; ++c) {
    printf("%s\"%s\":[", c ? "," : "", names[c]);
    for (int k = 0; k < 2; ++k) {
      void *self = Make(kRate, 0);
      const Kv kv[] = { { "Threshold", -30.0f }, { "Ratio", 4.0f }, { "Knee", 0.0f },
                        { "Attack", 10.0f }, { "Release", 200.0f },
                        { "Character", static_cast<float>(c) } };
      SetAll(self, kv, 6);
      double phase = 0.0;
      float lo = 1e9f, hi = -1e9f;
      double sum = 0.0;
      int count = 0;
      for (int i = 0; i < 2 * 44118; ++i) {
        Frame(self, 0.5f * static_cast<float>(sin(phase)));
        phase += 2.0 * 3.141592653589793 * freqs[k] / kRate;
        if (i >= 44118 + 22059) {
          const float r = fm1_comp_reduction_db(self);
          lo = fminf(lo, r);
          hi = fmaxf(hi, r);
          sum += r;
          ++count;
        }
      }
      printf("%s[%g,%.4f,%.4f]", k ? "," : "", freqs[k], sum / count, hi - lo);
      E.destroy(self);
    }
    printf("]");
  }
  printf("}");
}

// 7. The hand-over: a change of Character or Auto Rel while compressing
// must not step the reduction. Two cases where the smoothing in force and
// the new one disagree by many dB:
//   auto_off: Peak with Auto Rel, after 2 s at 0 dBFS and 0.5 s at
//     -30 dBFS: the slow envelope still holds a deep reduction that the
//     first stage has let go. Auto Rel then goes off.
//   punch_to_peak: Punch, Attack 100 ms, 50 ms into a step from silence to
//     0 dBFS: its second stage lags its first. Character then goes to Peak,
//     whose single stage is the first.
// Reports the largest frame-to-frame change of the reduction in the 20 ms
// after the switch, and the reduction 25 ms after it, with the switch and
// without (a control run): a real change of many dB, made gradually.
struct Run { float max_step, at_25ms; };

Run HandoverRun(int which, bool do_switch) {
  void *self = Make(kRate, 0);
  double phase = 0.0;
  const double inc = 2.0 * 3.141592653589793 * 440.0 / kRate;
  float level = 1.0f;
  if (which == 0) {
    const Kv kv[] = { { "Threshold", -40.0f }, { "Ratio", 10.0f }, { "Knee", 0.0f },
                      { "Attack", 5.0f }, { "Release", 1000.0f }, { "Character", 0.0f },
                      { "Auto Rel", 1.0f } };
    SetAll(self, kv, 7);
    for (int i = 0; i < 2 * 44118; ++i) {
      Frame(self, static_cast<float>(sin(phase)));
      phase += inc;
    }
    level = 0.0316f;                             // -30 dBFS
    for (int i = 0; i < 22059; ++i) {
      Frame(self, level * static_cast<float>(sin(phase)));
      phase += inc;
    }
  } else {
    const Kv kv[] = { { "Threshold", -40.0f }, { "Ratio", 10.0f }, { "Knee", 0.0f },
                      { "Attack", 100.0f }, { "Release", 1000.0f }, { "Character", 3.0f } };
    SetAll(self, kv, 6);
    for (int i = 0; i < 4410; ++i) Frame(self, 0.0f);
    for (int i = 0; i < 2206; ++i) {
      Frame(self, static_cast<float>(sin(phase)));
      phase += inc;
    }
  }
  float prev = fm1_comp_reduction_db(self);
  Run run = { 0.0f, 0.0f };
  if (do_switch) {
    if (which == 0) Set(self, "Auto Rel", 0.0f);
    else Set(self, "Character", 0.0f);
  }
  for (int i = 0; i < 1103; ++i) {             // 25 ms
    Frame(self, level * static_cast<float>(sin(phase)));
    phase += inc;
    const float r = fm1_comp_reduction_db(self);
    if (i < 882) run.max_step = fmaxf(run.max_step, fabsf(r - prev));
    prev = r;
    run.at_25ms = r;
  }
  E.destroy(self);
  return run;
}

void Handover() {
  const char *names[] = { "auto_off", "punch_to_peak" };
  printf("\"handover\":{");
  for (int k = 0; k < 2; ++k) {
    const Run control = HandoverRun(k, false), run = HandoverRun(k, true);
    printf("%s\"%s\":{\"max_step\":%.5f,\"at_25ms\":%.4f,\"control_max_step\":%.5f,"
           "\"control_at_25ms\":%.4f}", k ? "," : "", names[k], run.max_step, run.at_25ms,
           control.max_step, control.at_25ms);
  }
  printf("}");
}

// 8. Host rates: refused outside 8 kHz..384 kHz, and when not a number.
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

// 9. fx_comp_math.h against double-precision libm. log2 over x = 2^-66 to
// 2^13 (every mantissa step of 2^-13): the worst absolute error on [1/16,
// 16], and over the whole range in units of the result's last place (the
// result's own rounding grows with |log2 x|). exp2 over (-126, 126], in
// steps of 1e-4: the worst relative error.
double Ulp(float v) {
  const float a = fabsf(v);
  return a < 1.0f ? ldexp(1.0, -24) : static_cast<double>(nextafterf(a, INFINITY) - a);
}

void Approx() {
  double log_near = 0.0, log_ulps = 0.0, exp_err = 0.0;
  float log_at = 0.0f, exp_at = 0.0f;
  for (int e = -66; e <= 13; ++e) {
    for (int m = 0; m < 8192; ++m) {
      const float x = ldexpf(1.0f + m / 8192.0f, e);
      const float got = CompLog2(x);
      const double err = fabs(static_cast<double>(got) - log2(static_cast<double>(x)));
      if (x >= 0.0625f && x <= 16.0f && err > log_near) log_near = err;
      if (err / Ulp(got) > log_ulps) { log_ulps = err / Ulp(got); log_at = x; }
    }
  }
  for (int i = 1; i <= 2520000; ++i) {
    const float x = -126.0f + i * 0.0001f;
    const double want = exp2(static_cast<double>(x));
    const double err = fabs(static_cast<double>(CompExp2(x)) - want) / want;
    if (err > exp_err) { exp_err = err; exp_at = x; }
  }
  printf("\"approx\":{\"log2_abs_near_1\":%.3g,\"log2_ulps\":%.3f,\"log2_at\":%.6g,"
         "\"exp2_rel\":%.3g,\"exp2_at\":%.6g,\"exp2_0\":%.9g,\"exp2_low\":%.9g,"
         "\"exp2_high\":%.9g,\"exp2_nan\":%.9g}",
         log_near, log_ulps, log_at, exp_err, exp_at, CompExp2(0.0f), CompExp2(-200.0f),
         CompExp2(1000.0f), CompExp2(NAN));
}

// 10. Every float of three renders (2.9 s of noise each, Character and
// Threshold changed mid-stream), hashed (FNV-1a over the bits): the same on
// every build that keeps to IEEE single precision without fused
// multiply-adds -- Apple clang on arm64, GCC on i386 and x86-64, Emscripten's
// WebAssembly [verified 2026-10-02]. tests/test_engines_comp.py pins it.
void Hash() {
  printf("\"hash\":[");
  for (int c = 0; c < 3; ++c) {
    void *self = Make(kRate, 0);
    if (c == 0) {
      const Kv kv[] = { { "Character", 1.0f }, { "Threshold", -50.0f }, { "Ratio", 21.0f },
                        { "Auto Gain", 1.0f }, { "Mix", 0.5f } };
      SetAll(self, kv, 5);
    } else if (c == 1) {
      const Kv kv[] = { { "Character", 2.0f }, { "Auto Rel", 1.0f }, { "Threshold", -30.0f },
                        { "Knee", 9.0f } };
      SetAll(self, kv, 4);
    } else {
      const Kv kv[] = { { "Character", 3.0f }, { "Attack", 40.0f }, { "Threshold", -40.0f } };
      SetAll(self, kv, 3);
    }
    uint32_t noise = 1u, h = 2166136261u;
    float buf[128];
    for (int b = 0; b < 2000; ++b) {
      for (int i = 0; i < 64; ++i) {
        noise = noise * 1664525u + 1013904223u;
        buf[2 * i] = buf[2 * i + 1] = 0.5f * (static_cast<int32_t>(noise) / 2147483648.0f);
      }
      if (b == 700) Set(self, "Character", static_cast<float>((c + 1) % 4));
      if (b == 900) Set(self, "Threshold", -20.0f);
      E.render(self, buf, 64);
      for (int i = 0; i < 128; ++i) {
        uint32_t u;
        memcpy(&u, &buf[i], sizeof u);
        h = (h ^ u) * 16777619u;
      }
    }
    E.destroy(self);
    printf("%s\"%08x\"", c ? "," : "", h);
  }
  printf("]");
}

// 11. Auto Gain is clip-safe: with it on and Makeup at or under 0 dB, an
// input at or under 0 dBFS never comes out above 0 dBFS (nor the compressed
// path above 10^(Makeup/20), so the output above (1 - Mix) + Mix
// 10^(Makeup/20)), whatever Attack, Character, Auto Rel or Mix, even
// while Auto Gain itself is switched on and off every few blocks. Hostile
// signals at full scale: square waves, the Nyquist square, impulses on
// silence and on a quiet bed, onsets of loud bursts, full-scale noise, DC
// steps, one channel loud and the other quiet, and a slow swell from silence
// to full scale (through the knee). Settings: the extreme (Threshold -60 dB,
// Ratio 21, no knee, so Auto Gain asks for 60 dB and gets its cap, 24) at
// every Attack, Release, Character, Auto Rel and Mix in a grid; the tight
// corner (the curve asking for no more than the cap, so nothing but the
// bound stands between a full-scale input and full scale); then random
// ones. Reports the largest |output| / bound in double, and the steady level
// of a full-scale sine through the cap and through a curve under it.
const int kAgSignals = 10;

float AgSignal(int k, uint32_t i, Lcg &rng, float *right) {
  const double t = i / static_cast<double>(kRate);
  float x = 0.0f;
  *right = -2.0f;                                        // -2: the same as the left
  switch (k) {
    case 0: x = fmod(t * 50.0, 1.0) < 0.5 ? 1.0f : -1.0f; break;
    case 1: x = fmod(t * 1000.0, 1.0) < 0.5 ? 1.0f : -1.0f; break;
    case 2: x = (i & 1) ? -1.0f : 1.0f; break;
    case 3: x = i % 2205 == 7 ? (((i / 2205) & 1) ? -1.0f : 1.0f) : 0.0f; break;
    case 4: x = i % 1999 == 0 ? 1.0f : 0.01f * rng.Bipolar(); break;
    case 5: {
      const uint32_t phase = i % 6615;                   // 20 ms bursts every 150 ms
      x = phase < 882 ? static_cast<float>(sin(2.0 * M_PI * 1000.0 * t)) : 0.0f;
      if (phase < 882 && (i / 6615) % 3 == 2) x = x > 0.0f ? 1.0f : -1.0f;
      break;
    }
    case 6:
      x = rng.Bipolar();
      if (rng.Next() % 64 == 0) x = x < 0.0f ? -1.0f : 1.0f;
      break;
    case 7: {
      const float lv[] = { 0.0f, 1.0f, -1.0f, 0.25f, 1.0f, 0.0f, -1.0f };
      x = lv[(i / 2205) % 7];
      break;
    }
    case 8:
      x = fmod(t * 200.0, 1.0) < 0.5 ? 1.0f : -1.0f;
      *right = 0.01f * static_cast<float>(sin(2.0 * M_PI * 440.0 * t));
      break;
    default: x = static_cast<float>(fmin(1.0, t / 0.25) * sin(2.0 * M_PI * 440.0 * t)); break;
  }
  return x;
}

struct AgSetting {
  float threshold, ratio, knee, attack, release, makeup, mix, character, auto_rel;
};

// One run: every signal through a fresh instance, 0.25 s each; with toggle,
// Auto Gain switches every third block. Returns the largest |out| / bound.
double AgRun(const AgSetting &g, bool toggle, uint32_t seed) {
  // The compressed path is within 10^(Makeup/20) and the dry one within 1,
  // and they have the same sign: the blend is within their blend.
  const double bound = (1.0 - g.mix) + g.mix * pow(10.0, (g.makeup < 0.0f ? g.makeup : 0.0f) / 20.0);
  double worst = 0.0;
  float buf[128];
  for (int k = 0; k < kAgSignals; ++k) {
    void *self = Make(kRate, 0x3C);
    const Kv kv[] = { { "Threshold", g.threshold }, { "Ratio", g.ratio }, { "Knee", g.knee },
                      { "Attack", g.attack }, { "Release", g.release }, { "Makeup", g.makeup },
                      { "Mix", g.mix }, { "Character", g.character }, { "Auto Rel", g.auto_rel },
                      { "Auto Gain", 1.0f } };
    SetAll(self, kv, 10);
    Lcg rng = { seed + 97u * static_cast<uint32_t>(k) };
    uint32_t i = 0;
    for (int b = 0; b < 172; ++b) {
      if (toggle && b % 3 == 2) Set(self, "Auto Gain", static_cast<float>((b / 3) & 1));
      for (int f = 0; f < 64; ++f, ++i) {
        float r;
        const float l = AgSignal(k, i, rng, &r);
        buf[2 * f] = l;
        buf[2 * f + 1] = r < -1.5f ? l : r;
      }
      E.render(self, buf, 64);
      for (int f = 0; f < 128; ++f) worst = fmax(worst, fabs(static_cast<double>(buf[f])) / bound);
    }
    E.destroy(self);
  }
  return worst;
}

// A full-scale 440 Hz sine, RMS, Attack 0, Auto Gain on: its output peak in
// dBFS over the last quarter of a second.
double AgSteadyDb(float threshold, float ratio) {
  void *self = Make(kRate, 0);
  const Kv kv[] = { { "Threshold", threshold }, { "Ratio", ratio }, { "Knee", 0.0f },
                    { "Attack", 0.0f }, { "Character", 1.0f }, { "Auto Gain", 1.0f } };
  SetAll(self, kv, 6);
  float peak = 0.0f;
  for (uint32_t i = 0; i < 44118; ++i) {
    const float y = Frame(self, static_cast<float>(sin(2.0 * M_PI * 440.0 * i / kRate)));
    if (i >= 33088) peak = fmaxf(peak, fabsf(y));
  }
  E.destroy(self);
  return 20.0 * log10(peak);
}

void AutoGain() {
  double grid = 0.0, random = 0.0, toggled = 0.0;
  int runs = 0;
  const float attacks[] = { 0.0f, 10.0f, 100.0f }, releases[] = { 10.0f, 2000.0f };
  const float mixes[] = { 1.0f, 0.5f, 0.1f };
  for (float attack : attacks) {
    for (float release : releases) {
      for (int character = 0; character < 4; ++character) {
        for (int auto_rel = 0; auto_rel < 2; ++auto_rel) {
          for (float mix : mixes) {
            const AgSetting g = { -60.0f, 21.0f, 0.0f, attack, release, 0.0f, mix,
                                  static_cast<float>(character), static_cast<float>(auto_rel) };
            grid = fmax(grid, AgRun(g, false, 11u + runs));
            ++runs;
          }
        }
      }
    }
  }
  // The tight corner: where the curve asks for no more than the cap, Auto
  // Gain's makeup is all of the curve's reduction at 0 dBFS, so a full-scale
  // input above the threshold comes out at full scale less the margin: the
  // bound alone keeps it there (at -60 dB and 21:1 the cap leaves 36 dB).
  // -24 dB at 21:1 with no knee asks for exactly the cap; the others put
  // 0 dBFS on a slope under 1 and inside a knee.
  double tight = 0.0;
  const float corners[][3] = { { -24.0f, 21.0f, 0.0f }, { -12.0f, 4.0f, 12.0f },
                               { -3.0f, 21.0f, 24.0f }, { -20.0f, 2.0f, 6.0f } };
  const float tight_attacks[] = { 0.0f, 100.0f };
  for (const auto &corner : corners) {
    for (float attack : tight_attacks) {
      for (int character = 0; character < 4; ++character) {
        for (int auto_rel = 0; auto_rel < 2; ++auto_rel) {
          for (int toggle = 0; toggle < 2; ++toggle) {
            const AgSetting g = { corner[0], corner[1], corner[2], attack, 200.0f, 0.0f, 1.0f,
                                  static_cast<float>(character), static_cast<float>(auto_rel) };
            tight = fmax(tight, AgRun(g, toggle != 0, 3000u + runs));
            ++runs;
          }
        }
      }
    }
  }
  Lcg rng = { 2024u };
  for (int k = 0; k < 160; ++k, ++runs) {
    AgSetting g;
    g.threshold = -60.0f * rng.Unit();
    g.ratio = 1.0f + 20.0f * rng.Unit();
    g.knee = 24.0f * rng.Unit();
    g.attack = 100.0f * rng.Unit();
    g.release = 10.0f + 1990.0f * rng.Unit();
    g.makeup = (rng.Next() & 1) ? 0.0f : -12.0f * rng.Unit();
    g.mix = rng.Unit();
    g.character = static_cast<float>(rng.Next() % 4);
    g.auto_rel = static_cast<float>(rng.Next() & 1);
    const bool toggle = k % 4 == 0;
    const double w = AgRun(g, toggle, 5000u + k);
    if (toggle) toggled = fmax(toggled, w);
    else random = fmax(random, w);
  }
  printf("\"autogain\":{\"runs\":%d,\"grid\":%.9g,\"tight\":%.9g,\"random\":%.9g,"
         "\"toggled\":%.9g,\"capped_db\":%.4f,\"uncapped_db\":%.4f}",
         runs, grid, tight, random, toggled, AgSteadyDb(-60.0f, 21.0f), AgSteadyDb(-20.0f, 4.0f));
}

// 12. Cost: ns per 64-frame stereo block of noise, 0.5 s warm-up then 20 s.
double Cost(const Kv *kv, int n, bool gliding) {
  void *self = Make(kRate, 0);
  SetAll(self, kv, n);
  Lcg rng = { 3u };
  static float noise[64 * 128];
  for (int i = 0; i < 64 * 128; ++i) noise[i] = 0.5f * rng.Bipolar();
  float buf[128];
  const int blocks = 13786;                     // 20 s
  for (int b = 0; b < 344; ++b) {
    memcpy(buf, noise + 128 * (b % 64), sizeof(buf));
    E.render(self, buf, 64);
  }
  volatile float sink = 0.0f;
  const auto t0 = std::chrono::steady_clock::now();
  for (int b = 0; b < blocks; ++b) {
    if (gliding) Set(self, "Threshold", (b & 1) ? -40.0f : -10.0f);
    memcpy(buf, noise + 128 * (b % 64), sizeof(buf));
    E.render(self, buf, 64);
    sink = sink + buf[0];
  }
  const auto t1 = std::chrono::steady_clock::now();
  E.destroy(self);
  return std::chrono::duration<double, std::nano>(t1 - t0).count() / blocks;
}

void Costs() {
  const Kv peak[] = { { "Threshold", -24.0f } };
  const Kv glue[] = { { "Threshold", -24.0f }, { "Character", 2.0f }, { "Auto Rel", 1.0f },
                      { "Auto Gain", 1.0f } };
  double best_peak = 1e30, best_glue = 1e30, best_glide = 1e30;
  for (int run = 0; run < 3; ++run) {
    best_peak = fmin(best_peak, Cost(peak, 1, false));
    best_glue = fmin(best_glue, Cost(glue, 4, false));
    best_glide = fmin(best_glide, Cost(glue, 4, true));
  }
  fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
  printf("\"cost\":{\"ns_per_block_peak\":%.1f,\"ns_per_block_glue_auto\":%.1f,"
         "\"ns_per_block_gliding\":%.1f,\"instance_bytes\":%zu}",
         best_peak, best_glue, best_glide, E.instance_size(&host));
}

}  // namespace

int main(int argc, char **argv) {
  const bool cost = argc > 1 && strcmp(argv[1], "--cost") == 0;
  printf("{");
  if (cost) {
    Costs();
  } else {
    Sweep(); printf(",");
    Glide(); printf(",");
    Curve(); printf(",");
    Times(); printf(",");
    Silence(); printf(",");
    Steady(); printf(",");
    Handover(); printf(",");
    Rates(); printf(",");
    Approx(); printf(",");
    AutoGain(); printf(",");
    Hash();
  }
  printf("}\n");
  return 0;
}
