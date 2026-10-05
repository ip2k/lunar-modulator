// sat_test.cc -- fm1-sat-test: drives Master Sat (src/fx_sat.cc) through its
// engine struct where fm1-render cannot. tests/test_engines_sat.py reads its
// JSON. MIT licence.
//
//   fm1-sat-test                 parameters changed while audio runs, block
//                                sizes that change between calls, silence,
//                                float-exact bypass, small signals, the Shape
//                                crossfade, Glue's envelope, a digest of the
//                                output's bits and the host rates it accepts
//   fm1-sat-test tone HZ AMP [NAME=VALUE...]
//                                a sine of HZ (a whole number) and peak AMP on
//                                both channels for 1.5 s, settings applied
//                                before the first block; the last second
//                                analysed at 1 Hz resolution: the
//                                fundamental's gain, each harmonic, the
//                                distortion within the band and the aliases

#include "fm1_engine.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_sat;

namespace {

const fm1_engine_t &E = fm1_engine_sat;
const float kRate = 44118.0f;
const int kRateInt = 44118;
alignas(16) unsigned char g_mem[4096];

struct Lcg {
  uint32_t s;
  uint32_t Next() { s = s * 1664525u + 1013904223u; return s; }
  float Bipolar() { return static_cast<int32_t>(Next()) / 2147483648.0f; }  // [-1, 1)
  float Unit() { return (Next() >> 8) / 16777216.0f; }                        // [0, 1)
};

void *Make(unsigned char *mem, float rate, int fill) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  const size_t n = E.instance_size(&host);
  if (n > sizeof(g_mem)) return NULL;
  memset(mem, fill, sizeof(g_mem));
  return E.create(mem, &host);
}

int Index(const char *name) {
  for (uint16_t i = 0; i < E.n_params; ++i) {
    if (strcmp(E.params[i].name, name) == 0) return i;
  }
  fprintf(stderr, "no parameter %s\n", name);
  exit(2);
}

void SetP(void *self, const char *name, float v) {
  E.set_param(self, static_cast<uint16_t>(Index(name)), v);
}

// "Name=value"; the name may contain spaces.
void SetArg(void *self, const char *arg) {
  const char *eq = strchr(arg, '=');
  if (!eq) { fprintf(stderr, "want NAME=VALUE: %s\n", arg); exit(2); }
  char name[64];
  const size_t n = static_cast<size_t>(eq - arg);
  if (n >= sizeof(name)) exit(2);
  memcpy(name, arg, n);
  name[n] = 0;
  SetP(self, name, static_cast<float>(atof(eq + 1)));
}

// 1. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while noise plays, with now and then a NaN, an infinity or a huge sample,
// for 20 s. The output must stay finite and bounded.
void Sweep() {
  void *self = Make(g_mem, kRate, 0xA5);
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
    for (uint32_t i = 0; i < n; ++i) {
      buf[2 * i] = 0.5f * rng.Bipolar();
      buf[2 * i + 1] = 0.5f * rng.Bipolar();
      if (rng.Next() % 4096 == 0) {
        const float bad[3] = { NAN, INFINITY, -1e30f };
        buf[2 * i + (rng.Next() & 1)] = bad[rng.Next() % 3];
      }
    }
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

// A sine on both channels, with parameter changes at given samples, rendered
// in blocks of `block` frames, split at the changes.
struct Change { uint32_t at; const char *name; float value; };

void RenderSine(uint32_t block, const Change *changes, int n_changes, uint32_t total,
                double hz, float amplitude, float *out_in, float *out_left) {
  void *self = Make(g_mem, kRate, 0);
  float buf[128];
  double phase = 0.0;
  int next = 0;
  for (uint32_t pos = 0; pos < total;) {
    while (next < n_changes && changes[next].at <= pos) {
      SetP(self, changes[next].name, changes[next].value);
      ++next;
    }
    uint32_t n = total - pos < block ? total - pos : block;
    if (next < n_changes && changes[next].at - pos < n) n = changes[next].at - pos;
    for (uint32_t i = 0; i < n; ++i) {
      const float x = amplitude * static_cast<float>(sin(phase));
      phase += 2.0 * 3.141592653589793 * hz / kRate;
      buf[2 * i] = buf[2 * i + 1] = x;
      if (out_in) out_in[pos + i] = x;
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < n; ++i) out_left[pos + i] = buf[2 * i];
    pos += n;
  }
  E.destroy(self);
}

const uint32_t kTotal = 44118;
float g_in[kTotal], g_a[kTotal], g_b[kTotal], g_c[kTotal];

// 2. The glide: changes mid-stream give the same output whatever the block
// size (rendered at 64, 7 and 1 frames, split at the changes, Shape switched
// on the way), and once Mix has glided back to 0 the output is the input,
// bit for bit, though everything else is still turned up.
void Glide() {
  const Change ch[] = {
    { 0, "Mix", 1.0f }, { 0, "Drive", 9.0f }, { 0, "Glue", 0.5f },
    { 4410, "Drive", 18.0f }, { 4410, "Shape", 1.0f }, { 4410, "Asymmetry", 0.6f },
    { 4410, "Clean Hi", 3000.0f }, { 4410, "Clean Lo", 200.0f }, { 4410, "Level", 3.0f },
    { 11025, "Glue", 1.0f }, { 11025, "Shape", 0.0f },
    { 22050, "Mix", 0.0f },
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  RenderSine(64, ch, n, kTotal, 440.0, 0.5f, g_in, g_a);
  RenderSine(7, ch, n, kTotal, 440.0, 0.5f, NULL, g_b);
  RenderSine(1, ch, n, kTotal, 440.0, 0.5f, NULL, g_c);
  const int same = memcmp(g_a, g_b, sizeof(g_a)) == 0 && memcmp(g_a, g_c, sizeof(g_a)) == 0;
  float wet = 0.0f;
  for (uint32_t i = 22050 - 441; i < 22050; ++i) wet = fmaxf(wet, fabsf(g_a[i] - g_in[i]));
  uint32_t differ = 0;
  for (uint32_t i = 22050 + 2205; i < kTotal; ++i) differ += memcmp(&g_a[i], &g_in[i], 4) != 0;
  printf("\"glide\":{\"block_independent\":%s,\"wet_before\":%.6f,\"bypass_differ\":%u}",
         same ? "true" : "false", wet, differ);
}

// 3. Silence in while every knob moves, Shape switching too: exact zeros
// throughout. Then loud noise stops: the tail decays to exact zeros.
void Silence() {
  void *self = Make(g_mem, kRate, 0xFF);
  float buf[128];
  float moving = 0.0f;
  SetP(self, "Mix", 1.0f);
  Lcg rng = { 7u };
  for (int b = 0; b < 2000; ++b) {                       // 2.9 s
    if (b % 50 == 0) {
      for (uint16_t i = 0; i < E.n_params; ++i) {
        const fm1_param_t &p = E.params[i];
        if (strcmp(p.name, "Mix") == 0) continue;
        E.set_param(self, i, p.min + (p.max - p.min) * rng.Unit());
      }
    }
    memset(buf, 0, sizeof(buf));
    E.render(self, buf, 64);
    for (int i = 0; i < 128; ++i) moving = fmaxf(moving, fabsf(buf[i]));
  }
  for (int b = 0; b < 400; ++b) {                        // 0.6 s of loud noise
    for (int i = 0; i < 128; ++i) buf[i] = rng.Bipolar();
    E.render(self, buf, 64);
  }
  float last = 0.0f;
  int first_zero = -1;
  for (int b = 0; b < 2100; ++b) {                       // 3 s of silence
    memset(buf, 0, sizeof(buf));
    E.render(self, buf, 64);
    float pk = 0.0f;
    for (int i = 0; i < 128; ++i) pk = fmaxf(pk, fabsf(buf[i]));
    if (pk == 0.0f && first_zero < 0) first_zero = b;
    if (pk != 0.0f) first_zero = -1;
    if (b == 2099) last = pk;
  }
  E.destroy(self);
  printf("\"silence\":{\"moving_peak\":%.9g,\"last_block_peak\":%.9g,\"zero_after_ms\":%.1f}",
         moving, last, first_zero < 0 ? -1.0 : first_zero * 64 * 1000.0 / kRate);
}

// 4. Bypass: at the defaults, and with every other knob turned while Mix is
// 0, any finite input within +/-16 (signed zeros, subnormals and the edges
// included) comes out bit for bit.
void Bypass() {
  uint32_t differ[2] = { 0, 0 };
  uint64_t count = 0;
  for (int busy = 0; busy < 2; ++busy) {
    void *self = Make(g_mem, kRate, 0x5A);
    if (busy) {
      SetP(self, "Drive", 18.0f); SetP(self, "Glue", 1.0f); SetP(self, "Shape", 1.0f);
      SetP(self, "Asymmetry", -0.7f); SetP(self, "Level", 12.0f); SetP(self, "Clean Lo", 300.0f);
    }
    Lcg rng = { 99u };
    float buf[128], in[128];
    const float edge[8] = { -0.0f, 0.0f, 1e-40f, -1e-40f, 15.999999f, -16.0f, 16.0f, 1.0f };
    for (int b = 0; b < 2000; ++b) {
      for (int i = 0; i < 128; ++i) {
        const uint32_t r = rng.Next();
        in[i] = (r % 16 == 0) ? edge[(r >> 4) % 8] : 16.0f * rng.Bipolar();
      }
      memcpy(buf, in, sizeof(buf));
      E.render(self, buf, 64);
      for (int i = 0; i < 128; ++i) differ[busy] += memcmp(&buf[i], &in[i], 4) != 0;
      count += 128;
    }
    E.destroy(self);
  }
  printf("\"bypass\":{\"samples\":%llu,\"differ_default\":%u,\"differ_busy\":%u}",
         static_cast<unsigned long long>(count), differ[0], differ[1]);
}

// 5. Small signals: a 440 Hz sine at -60 dBFS, Mix 1, Drive 18, Glue 1.
// The largest difference from the input, relative to its peak.
void Linear() {
  printf("\"linear\":{");
  const char *shape[2] = { "0", "1" };
  const float asym[2] = { 0.0f, 1.0f };
  bool first = true;
  for (int s = 0; s < 2; ++s) {
    for (int k = 0; k < 2; ++k) {
      const Change ch[] = {
        { 0, "Mix", 1.0f }, { 0, "Drive", 18.0f }, { 0, "Glue", 1.0f },
        { 0, "Shape", static_cast<float>(atof(shape[s])) }, { 0, "Asymmetry", asym[k] },
        { 0, "Clean Hi", 20000.0f }, { 0, "Clean Lo", 20.0f },
      };
      RenderSine(64, ch, 7, kTotal, 440.0, 0.001f, g_in, g_a);
      float worst = 0.0f;
      for (uint32_t i = 4410; i < kTotal; ++i) worst = fmaxf(worst, fabsf(g_a[i] - g_in[i]));
      printf("%s\"shape%d_asym%d\":%.6g", first ? "" : ",", s, k, worst / 0.001f);
      first = false;
    }
  }
  printf("}");
}

// 6. The Shape crossfade: switching at full drive bends the waveform no
// more than the clipped sine already does from sample to sample (its second
// difference), where an instant switch would step it.
float Curve(const float *x, uint32_t i) { return fabsf(x[i + 1] - 2.0f * x[i] + x[i - 1]); }

void Fade() {
  const uint32_t at = 22050;
  const Change sw[] = {
    { 0, "Mix", 1.0f }, { 0, "Drive", 18.0f }, { 0, "Glue", 0.0f }, { at, "Shape", 1.0f },
  };
  const Change a[] = { { 0, "Mix", 1.0f }, { 0, "Drive", 18.0f }, { 0, "Glue", 0.0f } };
  const Change b[] = {
    { 0, "Mix", 1.0f }, { 0, "Drive", 18.0f }, { 0, "Glue", 0.0f }, { 0, "Shape", 1.0f },
  };
  RenderSine(64, sw, 4, kTotal, 440.0, 0.5f, NULL, g_a);
  RenderSine(64, a, 3, kTotal, 440.0, 0.5f, NULL, g_b);
  RenderSine(64, b, 4, kTotal, 440.0, 0.5f, NULL, g_c);
  for (uint32_t i = at; i < kTotal; ++i) g_in[i] = g_c[i];   // an instant switch
  for (uint32_t i = 0; i < at; ++i) g_in[i] = g_b[i];
  float fade = 0.0f, steady = 0.0f, hard = 0.0f, before = 0.0f;
  for (uint32_t i = at - 1; i < at + 441; ++i) {
    fade = fmaxf(fade, Curve(g_a, i));
    hard = fmaxf(hard, Curve(g_in, i));
  }
  for (uint32_t i = 4411; i < at - 441; ++i) {           // either Shape's own
    steady = fmaxf(steady, fmaxf(Curve(g_a, i), Curve(g_c, i)));
  }
  for (uint32_t i = 1; i < at; ++i) before = fmaxf(before, fabsf(g_a[i] - g_b[i]));
  float settled = 0.0f;   // 50 ms on, the switched render is Dense's own
  for (uint32_t i = at + 2205; i < kTotal; ++i) settled = fmaxf(settled, fabsf(g_a[i] - g_c[i]));
  printf("\"fade\":{\"curve_fade\":%.6f,\"curve_steady\":%.6f,\"curve_hard\":%.6f,"
         "\"before\":%.9g,\"settled\":%.9g}", fade, steady, hard, before, settled);
}

// 7. Glue's envelope: a 440 Hz sine steps from 0.05 to 0.5 at 0.5 s and
// back at 1.0 s, Drive 12, rendered with Glue 1 and with Glue 0. The ratio
// of their peaks per 10 ms window shows the reduction: caught within
// milliseconds of the step up, released over about 200 ms after the step
// down, and gone a second later.
float g_loud[2 * kTotal], g_ref[2 * kTotal];

void GlueStep(float glue, float *out) {
  void *self = Make(g_mem, kRate, 0);
  SetP(self, "Mix", 1.0f);
  SetP(self, "Drive", 12.0f);
  SetP(self, "Glue", glue);
  float buf[128];
  double phase = 0.0;
  const uint32_t total = 2 * kTotal;
  for (uint32_t pos = 0; pos < total; pos += 64) {
    const uint32_t n = total - pos < 64 ? total - pos : 64;
    for (uint32_t i = 0; i < n; ++i) {
      const uint32_t t = pos + i;
      const float amp = (t >= kTotal / 2 && t < kTotal) ? 0.5f : 0.05f;
      buf[2 * i] = buf[2 * i + 1] = amp * static_cast<float>(sin(phase));
      phase += 2.0 * 3.141592653589793 * 440.0 / kRate;
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < n; ++i) out[pos + i] = buf[2 * i];
  }
  E.destroy(self);
}

double PeakRatio(double t0, double t1) {
  const uint32_t a = static_cast<uint32_t>(t0 * kRateInt), b = static_cast<uint32_t>(t1 * kRateInt);
  float pa = 0.0f, pb = 0.0f;
  for (uint32_t i = a; i < b; ++i) {
    pa = fmaxf(pa, fabsf(g_loud[i]));
    pb = fmaxf(pb, fabsf(g_ref[i]));
  }
  return pa / pb;
}

void Glue() {
  GlueStep(1.0f, g_loud);
  GlueStep(0.0f, g_ref);
  printf("\"glue\":{\"quiet_before\":%.6f,\"loud_5ms\":%.6f,\"loud_end\":%.6f,"
         "\"after_200ms\":%.6f,\"after_1s\":%.6f}",
         PeakRatio(0.4, 0.5), PeakRatio(0.505, 0.515), PeakRatio(0.9, 1.0),
         PeakRatio(1.19, 1.21), PeakRatio(1.95, 2.0));
}

// 8. A digest of the output's bits: 3 s of noise with louder bursts, in
// blocks of 1-64 frames, every knob turned on the way. Every build of the
// effect (Apple clang on arm64, GCC on x86-64 and i386 with SSE, clang with
// sanitizers, WebAssembly) must print the same digest: no libm, no fused
// multiply-adds.
void Digest() {
  void *self = Make(g_mem, kRate, 0x33);
  const char *start[] = { "Mix=1", "Drive=12", "Glue=0.6", "Asymmetry=0.3",
                          "Clean Hi=8000", "Clean Lo=60" };
  const char *one[] = { "Shape=1", "Asymmetry=-0.5", "Drive=18" };
  const char *two[] = { "Glue=0", "Level=-3", "Shape=0", "Clean Hi=2000", "Asymmetry=0" };
  for (size_t i = 0; i < sizeof(start) / sizeof(start[0]); ++i) SetArg(self, start[i]);
  Lcg rng = { 2024u };
  uint32_t hash = 2166136261u;
  float buf[128];
  const uint32_t total = 3 * kRateInt;
  bool did_one = false, did_two = false;
  for (uint32_t pos = 0; pos < total;) {
    if (!did_one && pos >= static_cast<uint32_t>(kRateInt)) {
      for (size_t i = 0; i < sizeof(one) / sizeof(one[0]); ++i) SetArg(self, one[i]);
      did_one = true;
    }
    if (!did_two && pos >= static_cast<uint32_t>(2 * kRateInt)) {
      for (size_t i = 0; i < sizeof(two) / sizeof(two[0]); ++i) SetArg(self, two[i]);
      did_two = true;
    }
    uint32_t n = 1 + rng.Next() % 64;
    if (n > total - pos) n = total - pos;
    const float gain = (pos / 4410) % 3 == 0 ? 2.0f : 0.5f;
    for (uint32_t i = 0; i < 2 * n; ++i) buf[i] = gain * rng.Bipolar();
    E.render(self, buf, n);
    const unsigned char *b = reinterpret_cast<const unsigned char *>(buf);
    for (uint32_t i = 0; i < 8 * n; ++i) hash = (hash ^ b[i]) * 16777619u;
    pos += n;
  }
  E.destroy(self);
  fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
  printf("\"digest\":\"%08x\",\"instance_bytes\":%u", hash,
         static_cast<unsigned>(E.instance_size(&host)));
}

// 9. Host rates: refused outside 8 kHz..384 kHz, and when not a number.
void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 44118.0f, 48000.0f, 96000.0f, 384000.0f,
                          400000.0f, NAN, INFINITY, -44118.0f };
  printf("\"rates\":[");
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    void *self = Make(g_mem, rates[i], 0);
    printf("%s[\"%g\",%s]", i ? "," : "", rates[i], self ? "true" : "false");
    if (self) E.destroy(self);
  }
  printf("]");
}

// tone: amplitude of the component at hz (a whole number of Hz) over the
// last second.
double Goertzel(const float *x, int n, double hz) {
  const double w = 2.0 * 3.141592653589793 * hz / kRateInt;
  const double c = 2.0 * cos(w);
  double s1 = 0.0, s2 = 0.0;
  for (int i = 0; i < n; ++i) {
    const double s0 = x[i] + c * s1 - s2;
    s2 = s1;
    s1 = s0;
  }
  const double re = s1 - s2 * cos(w), im = s2 * sin(w);
  return 2.0 * sqrt(re * re + im * im) / n;
}

int Folded(long long f) {
  f %= kRateInt;
  if (f > kRateInt / 2) f = kRateInt - f;
  return static_cast<int>(f);
}

float g_tone_out[kTotal * 3 / 2], g_tone_right[kTotal * 3 / 2];

int Tone(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "tone HZ AMP [NAME=VALUE...]\n"); return 2; }
  const int hz = atoi(argv[2]);
  const float amp = static_cast<float>(atof(argv[3]));
  if (hz < 1 || hz >= kRateInt / 2) return 2;
  void *self = Make(g_mem, kRate, 0);
  for (int i = 4; i < argc; ++i) SetArg(self, argv[i]);
  const uint32_t total = kTotal * 3 / 2;
  float buf[128];
  double phase = 0.0;
  for (uint32_t pos = 0; pos < total; pos += 64) {
    const uint32_t n = total - pos < 64 ? total - pos : 64;
    for (uint32_t i = 0; i < n; ++i) {
      buf[2 * i] = buf[2 * i + 1] = amp * static_cast<float>(sin(phase));
      phase += 2.0 * 3.141592653589793 * hz / kRateInt;
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < n; ++i) {
      g_tone_out[pos + i] = buf[2 * i];
      g_tone_right[pos + i] = buf[2 * i + 1];
    }
  }
  E.destroy(self);
  const float *seg = g_tone_out + (total - kTotal);
  const int n = static_cast<int>(kTotal);
  double sum = 0.0, sum2 = 0.0, peak = 0.0, lr = 0.0;
  for (int i = 0; i < n; ++i) {
    sum += seg[i];
    sum2 += static_cast<double>(seg[i]) * seg[i];
    peak = fmax(peak, fabs(seg[i]));
    lr = fmax(lr, fabs(seg[i] - g_tone_right[total - kTotal + i]));
  }
  const double fund = Goertzel(seg, n, hz);
  printf("{\"gain_db\":%.6f,\"dc\":%.9g,\"rms\":%.9g,\"peak\":%.9g,\"lr_differ\":%.9g,\"h_db\":[",
         20.0 * log10(fund / amp + 1e-300), sum / n, sqrt(sum2 / n), peak, lr);
  // Harmonics 2..15 relative to the fundamental, where they land.
  for (int k = 2; k <= 15; ++k) {
    const int f = Folded(static_cast<long long>(k) * hz);
    const double a = f > 0 ? Goertzel(seg, n, f) : 0.0;
    printf("%s%.3f", k > 2 ? "," : "", 20.0 * log10(a / fund + 1e-300));
  }
  // In band: harmonics below Nyquist. Aliases: every distinct frequency a
  // harmonic above Nyquist (up to the 1,000th) reflects to, off the
  // harmonics themselves.
  double thd = 0.0, alias = 0.0;
  static unsigned char seen[kRateInt / 2 + 1];
  memset(seen, 0, sizeof(seen));
  for (int k = 2; k <= 1000; ++k) {
    const long long raw = static_cast<long long>(k) * hz;
    const int f = Folded(raw);
    if (raw < kRateInt / 2) {
      const double a = Goertzel(seg, n, f);
      thd += a * a;
    } else if (f > 20 && f % hz != 0 && !seen[f]) {
      seen[f] = 1;
      const double a = Goertzel(seg, n, f);
      alias += a * a;
    }
  }
  printf("],\"thd_db\":%.3f,\"alias_db\":%.3f}\n", 10.0 * log10(thd / (fund * fund) + 1e-300),
         10.0 * log10(alias / (fund * fund) + 1e-300));
  return 0;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc > 1 && strcmp(argv[1], "tone") == 0) return Tone(argc, argv);
  printf("{");
  Sweep(); printf(",");
  Glide(); printf(",");
  Silence(); printf(",");
  Bypass(); printf(",");
  Linear(); printf(",");
  Fade(); printf(",");
  Glue(); printf(",");
  Digest(); printf(",");
  Rates();
  printf("}\n");
  return 0;
}
