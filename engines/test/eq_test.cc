// eq_test.cc -- fm1-eq-test: drives the EQ effect (src/fx_eq.cc) through
// its engine struct where fm1-render cannot: the frequency response measured
// in float precision (fm1-render writes 16-bit WAVs), parameters changed
// while audio runs at any block size, the exact pass-through at 0 dB down to
// the bit, clicks while bands are swept, decay to exact silence, host rates,
// the accuracy of fx_eq_math.h against libm, a hash of the output for
// cross-build checks, and the cost per block. Prints one JSON object;
// tests/test_engines_eq.py reads it. MIT licence.

#include "fm1_engine.h"
#include "../src/fx_eq_math.h"

#include <chrono>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_eq;

namespace {

const fm1_engine_t &E = fm1_engine_eq;
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
  fprintf(stderr, "no parameter %s\n", name);
  return 0;
}

void Set(void *self, const char *name, float v) {
  E.set_param(self, static_cast<uint16_t>(Index(name)), v);
}

struct Kv { const char *name; float value; };

void SetAll(void *self, const Kv *kv, int n) {
  for (int i = 0; i < n; ++i) Set(self, kv[i].name, kv[i].value);
}

uint32_t Bits(float x) {
  uint32_t u;
  memcpy(&u, &x, sizeof u);
  return u;
}

// 1. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while noise plays, for 20 s. The output must stay finite.
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

// A sine on both channels, with parameter changes at given samples.
struct Change { uint32_t at; const char *name; float value; };

void RenderSine(uint32_t block, const Change *changes, int n_changes, uint32_t total,
                double hz, float amplitude, float *out_left) {
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
      phase += 2.0 * M_PI * hz / kRate;
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
// size (every parameter changed on samples 4410 and 22050, some of them off
// the 8-sample control grid, rendered at 64, 7 and 1 frames, split at the
// changes), and a step of Level from 0 to -15 dB fades over a few
// milliseconds and then holds exactly 10^(-15/20) of the 0 dB output.
void Glide() {
  const Change ch[] = {
    { 0, "Low Gain", 6.0f }, { 0, "Mid Gain", -4.0f }, { 0, "High Gain", 3.0f },
    { 4410, "Low Freq", 300.0f }, { 4410, "Low Gain", -12.0f }, { 4410, "Low Q", 1.8f },
    { 4413, "Mid Freq", 440.0f }, { 4413, "Mid Gain", 15.0f }, { 4413, "Mid Q", 6.0f },
    { 4417, "High Freq", 2000.0f }, { 4417, "High Gain", -15.0f }, { 4417, "High Q", 0.4f },
    { 22050, "Level", -15.0f },
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  RenderSine(64, ch, n, kTotal, 440.0, 0.25f, g_a);
  RenderSine(7, ch, n, kTotal, 440.0, 0.25f, g_b);
  RenderSine(1, ch, n, kTotal, 440.0, 0.25f, g_c);
  const int same = memcmp(g_a, g_b, sizeof(g_a)) == 0 && memcmp(g_a, g_c, sizeof(g_a)) == 0;
  // The same without the Level step: the reference for the faded part.
  RenderSine(64, ch, n - 1, kTotal, 440.0, 0.25f, g_b);
  float before = 0.0f, first_ms = 0.0f;
  for (uint32_t i = 22050 - 441; i < 22050; ++i) before = fmaxf(before, fabsf(g_a[i]));
  for (uint32_t i = 22050; i < 22050 + 44; ++i) first_ms = fmaxf(first_ms, fabsf(g_a[i]));
  const float want = EqExp2(-15.0f * 0.166096405f);     // the gain the effect uses
  int exact_tail = 1;
  for (uint32_t i = 22050 + 2205; i < kTotal; ++i) {
    if (g_a[i] != g_b[i] * want) exact_tail = 0;
  }
  printf("\"glide\":{\"block_independent\":%s,\"before\":%.6f,\"first_ms\":%.6f,"
         "\"tail_exact\":%s,\"level\":%.9g}", same ? "true" : "false", before, first_ms,
         exact_tail ? "true" : "false", want);
}

// 3. The frequency response: the DFT of a 32,768-sample impulse response (an
// impulse of 0.25, so nothing nears the input guard), in dB, at fixed
// frequencies and at each band's own frequency.
struct Setting { const char *name; Kv kv[10]; int n; };

const Setting kSettings[] = {
  { "low_p12_100", { { "Low Gain", 12 }, { "Low Freq", 100 } }, 2 },
  { "low_m9_300_q15", { { "Low Gain", -9 }, { "Low Freq", 300 }, { "Low Q", 1.5f } }, 3 },
  { "low_p15_20_q2", { { "Low Gain", 15 }, { "Low Freq", 20 }, { "Low Q", 2 } }, 3 },
  { "bell_p9_1k", { { "Mid Gain", 9 } }, 1 },
  { "bell_m15_5k_q8", { { "Mid Gain", -15 }, { "Mid Freq", 5000 }, { "Mid Q", 8 } }, 3 },
  { "bell_p15_15k_q05", { { "Mid Gain", 15 }, { "Mid Freq", 15000 }, { "Mid Q", 0.5f } }, 3 },
  { "bell_p6_60_q10", { { "Mid Gain", 6 }, { "Mid Freq", 60 }, { "Mid Q", 10 } }, 3 },
  { "high_p6_8k", { { "High Gain", 6 } }, 1 },
  { "high_m12_2k_q2", { { "High Gain", -12 }, { "High Freq", 2000 }, { "High Q", 2 } }, 3 },
  { "high_p15_18k_q03", { { "High Gain", 15 }, { "High Freq", 18000 }, { "High Q", 0.3f } }, 3 },
  { "all_three", { { "Low Gain", 4 }, { "Low Freq", 80 }, { "Mid Gain", -6 }, { "Mid Freq", 700 },
                   { "Mid Q", 2 }, { "High Gain", 5 }, { "High Freq", 6000 }, { "High Q", 1 },
                   { "Level", -6 } }, 9 },
};
const double kFreqs[] = { 20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500,
                          630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000,
                          10000, 12500, 15000, 16000, 18000, 20000, 21000 };
const uint32_t kIr = 32768;
float g_ir[kIr * 2];

double ResponseDb(const float *h, double hz) {
  double re = 0.0, im = 0.0;
  const double w = 2.0 * M_PI * hz / kRate;
  for (uint32_t n = 0; n < kIr; ++n) {
    re += h[n] * cos(w * n);
    im -= h[n] * sin(w * n);
  }
  return 10.0 * log10(re * re + im * im);
}

void Response() {
  printf("\"response\":{");
  static float h[kIr];
  for (size_t s = 0; s < sizeof(kSettings) / sizeof(kSettings[0]); ++s) {
    const Setting &st = kSettings[s];
    void *self = Make(kRate, 0x5A);
    SetAll(self, st.kv, st.n);
    memset(g_ir, 0, sizeof(g_ir));
    g_ir[0] = g_ir[1] = 0.25f;
    for (uint32_t pos = 0; pos < kIr; pos += 64) E.render(self, g_ir + 2 * pos, 64);
    float tail = 0.0f;
    for (uint32_t n = 0; n < kIr; ++n) {
      h[n] = 4.0f * g_ir[2 * n];
      if (n >= kIr - 1024) tail = fmaxf(tail, fabsf(g_ir[2 * n]));
    }
    E.destroy(self);
    printf("%s\"%s\":{\"tail\":%.3g,\"db\":[", s ? "," : "", st.name, tail);
    for (size_t i = 0; i < sizeof(kFreqs) / sizeof(kFreqs[0]); ++i) {
      printf("%s[%g,%.6f]", i ? "," : "", kFreqs[i], ResponseDb(h, kFreqs[i]));
    }
    // And at each band's own frequency, as set (or its default).
    const char *freqs[3] = { "Low Freq", "Mid Freq", "High Freq" };
    for (int b = 0; b < 3; ++b) {
      double hz = E.params[Index(freqs[b])].def;
      for (int k = 0; k < st.n; ++k) {
        if (strcmp(st.kv[k].name, freqs[b]) == 0) hz = st.kv[k].value;
      }
      printf(",[%g,%.6f]", hz, ResponseDb(h, hz));
    }
    printf("]}");
  }
  printf("}");
}

// 4. 0 dB is exact: with every gain and Level at 0 dB the output is the
// input bit for bit (negative zero, subnormals and +/-15.9 included),
// whatever the frequencies and Qs, and again once a band has been turned up
// and back to 0 dB (the glide lands on 0 exactly).
const uint32_t kExactFrames = 22050;
float g_x[2 * kExactFrames], g_y[2 * kExactFrames];

float ExactInput(Lcg &rng, uint32_t i) {
  switch (i % 16) {
    case 0: return -0.0f;
    case 1: return 1e-40f * rng.Bipolar();               // subnormal
    case 2: return 15.9f * rng.Bipolar();
    case 3: return 1e-30f * rng.Bipolar();
    default: return rng.Bipolar();
  }
}

uint32_t ExactRun(const Kv *kv, int n, const Change *ch, int n_ch, uint32_t block) {
  void *self = Make(kRate, 0x77);
  SetAll(self, kv, n);
  Lcg rng = { 9u };
  for (uint32_t i = 0; i < 2 * kExactFrames; ++i) g_x[i] = ExactInput(rng, i);
  memcpy(g_y, g_x, sizeof(g_x));
  int next = 0;
  for (uint32_t pos = 0; pos < kExactFrames;) {
    while (next < n_ch && ch[next].at <= pos) { Set(self, ch[next].name, ch[next].value); ++next; }
    uint32_t len = kExactFrames - pos < block ? kExactFrames - pos : block;
    if (next < n_ch && ch[next].at - pos < len) len = ch[next].at - pos;
    E.render(self, g_y + 2 * pos, len);
    pos += len;
  }
  E.destroy(self);
  // The last sample (frame index + 1) that differs from the input in its
  // bits; 0 when none does.
  uint32_t last = 0;
  for (uint32_t i = 0; i < 2 * kExactFrames; ++i) {
    if (Bits(g_x[i]) != Bits(g_y[i])) last = i / 2 + 1;
  }
  return last;
}

void Exact() {
  const Kv odd[] = { { "Low Freq", 20 }, { "Low Q", 2 }, { "Mid Freq", 17000 }, { "Mid Q", 0.3f },
                     { "High Freq", 1000 }, { "High Q", 0.3f } };
  const Change round_trip[] = {
    { 2000, "Mid Gain", 12.0f }, { 2000, "Low Gain", -15.0f }, { 2003, "High Gain", 9.0f },
    { 2003, "Level", 6.0f }, { 6000, "Mid Gain", 0.0f }, { 6000, "Low Gain", 0.0f },
    { 6001, "High Gain", 0.0f }, { 6001, "Level", 0.0f },
  };
  const Change sweep_at_zero[] = {
    { 100, "Mid Freq", 20.0f }, { 3000, "Mid Freq", 18000.0f }, { 3000, "Low Q", 0.3f },
    { 5000, "High Freq", 1000.0f }, { 7000, "Mid Q", 10.0f },
  };
  printf("\"exact\":{\"defaults\":%u,\"odd\":%u,\"sweep_at_zero\":%u,\"round_trip_last\":%u,"
         "\"round_trip_last_7\":%u}",
         ExactRun(NULL, 0, NULL, 0, 64), ExactRun(odd, 6, NULL, 0, 64),
         ExactRun(NULL, 0, sweep_at_zero, 5, 64), ExactRun(NULL, 0, round_trip, 8, 64),
         ExactRun(NULL, 0, round_trip, 8, 7));
}

// 5. Silence: silence in gives exact silence out at any setting from any
// prior memory; and after a second of loud noise, the tail decays to exact
// zeros (the flush) -- how long that takes at the slowest settings, in
// frames (0: silent from the first frame of silence).
void Silence() {
  float buf[128];
  float peak = 0.0f;
  Lcg rng = { 5u };
  for (int run = 0; run < 50; ++run) {
    void *self = Make(kRate, run & 1 ? 0xFF : 0xA5);
    for (uint16_t p = 0; p < E.n_params; ++p) {
      const fm1_param_t &q = E.params[p];
      E.set_param(self, p, q.min + (q.max - q.min) * rng.Unit());
    }
    for (int b = 0; b < 100; ++b) {
      memset(buf, 0, sizeof(buf));
      E.render(self, buf, 64);
      for (int i = 0; i < 128; ++i) peak = fmaxf(peak, fabsf(buf[i]));
    }
    E.destroy(self);
  }
  // The slowest tails: every band at its lowest frequency and highest Q,
  // boosted, and cut.
  int frames_to_zero[2];
  for (int cut = 0; cut < 2; ++cut) {
    void *self = Make(kRate, 0);
    const float g = cut ? -15.0f : 15.0f;
    const Kv kv[] = { { "Low Freq", 20 }, { "Low Q", 2 }, { "Low Gain", g },
                      { "Mid Freq", 20 }, { "Mid Q", 10 }, { "Mid Gain", g },
                      { "High Freq", 1000 }, { "High Q", 2 }, { "High Gain", g } };
    SetAll(self, kv, 9);
    Lcg noise = { 11u };
    for (int b = 0; b < 690; ++b) {                       // 1 s of noise
      for (int i = 0; i < 128; ++i) buf[i] = 0.5f * noise.Bipolar();
      E.render(self, buf, 64);
    }
    int last_nonzero = 0;
    for (int b = 0; b < 20700; ++b) {                     // 30 s of silence
      memset(buf, 0, sizeof(buf));
      E.render(self, buf, 64);
      for (int i = 0; i < 128; ++i) {
        if (buf[i] != 0.0f) last_nonzero = 64 * b + i / 2 + 1;
      }
    }
    frames_to_zero[cut] = last_nonzero;
    E.destroy(self);
  }
  printf("\"silence\":{\"peak\":%.9g,\"zero_after_boost\":%d,\"zero_after_cut\":%d}", peak,
         frames_to_zero[0], frames_to_zero[1]);
}

// 6. Clicks: a 100 Hz sine at 0.25 through a band that jumps (set_param at
// once, no ramp from the host) every 50 ms. The largest second difference
// of the output, |y[n] - 2 y[n-1] + y[n-2]|, against (a) the largest of
// static renders at both ends of the jump and (b) a switch: the two static
// renders spliced at the same instants, which is what changing the filter
// at once, from a settled state, would sound like at best. A click or a
// thump shows up in the second difference at about the size of the step it
// makes in the waveform; the glide leaves only the bend of its own fade.
float MaxD2(const float *y, uint32_t n, uint32_t from) {
  float m = 0.0f;
  for (uint32_t i = from < 2 ? 2 : from; i < n; ++i) {
    m = fmaxf(m, fabsf(y[i] - 2.0f * y[i - 1] + y[i - 2]));
  }
  return m;
}

const uint32_t kClickTotal = 44118;
float g_s1[kClickTotal], g_s2[kClickTotal], g_mv[kClickTotal];

void ClickCase(const char *label, const Kv *base, int n_base, const char *param, float v1,
               float v2, bool comma) {
  Change ch[32];
  int n = 0;
  for (int i = 0; i < n_base; ++i) ch[n++] = { 0, base[i].name, base[i].value };
  ch[n++] = { 0, param, v1 };
  const int fixed = n;
  RenderSine(64, ch, fixed, kClickTotal, 100.0, 0.25f, g_s1);
  ch[fixed - 1].value = v2;
  RenderSine(64, ch, fixed, kClickTotal, 100.0, 0.25f, g_s2);
  ch[fixed - 1].value = v1;
  for (uint32_t at = 2205; at < kClickTotal && n < 32; at += 2205) {
    ch[n++] = { at, param, ((at / 2205) & 1) ? v2 : v1 };
  }
  RenderSine(64, ch, n, kClickTotal, 100.0, 0.25f, g_mv);
  const float s = fmaxf(MaxD2(g_s1, kClickTotal, 4410), MaxD2(g_s2, kClickTotal, 4410));
  const float m = MaxD2(g_mv, kClickTotal, 2205);
  float sw = 0.0f;
  for (uint32_t at = 4410; at + 2 < kClickTotal; at += 2205) {
    const float *before = ((at / 2205) & 1) ? g_s1 : g_s2;   // what played up to `at`
    const float *after = ((at / 2205) & 1) ? g_s2 : g_s1;
    const float y0 = before[at - 2], y1 = before[at - 1], y2 = after[at], y3 = after[at + 1];
    sw = fmaxf(sw, fmaxf(fabsf(y2 - 2.0f * y1 + y0), fabsf(y3 - 2.0f * y2 + y1)));
  }
  printf("%s\"%s\":{\"static\":%.6g,\"moving\":%.6g,\"switch\":%.6g}", comma ? "," : "",
         label, s, m, sw);
}

void Clicks() {
  printf("\"clicks\":{");
  const Kv bell[] = { { "Mid Gain", 15 }, { "Mid Q", 4 } };
  ClickCase("bell_freq_100_2k", bell, 2, "Mid Freq", 100.0f, 2000.0f, false);
  const Kv bell_at[] = { { "Mid Freq", 100 }, { "Mid Q", 4 } };
  ClickCase("bell_gain_m15_p15", bell_at, 2, "Mid Gain", -15.0f, 15.0f, true);
  const Kv bell_q[] = { { "Mid Freq", 200 }, { "Mid Gain", 15 } };
  ClickCase("bell_q_03_10", bell_q, 2, "Mid Q", 0.3f, 10.0f, true);
  const Kv low[] = { { "Low Freq", 200 }, { "Low Q", 2 } };
  ClickCase("low_gain_m15_p15", low, 2, "Low Gain", -15.0f, 15.0f, true);
  const Kv low_f[] = { { "Low Gain", 15 }, { "Low Q", 2 } };
  ClickCase("low_freq_20_1k", low_f, 2, "Low Freq", 20.0f, 1000.0f, true);
  const Kv high[] = { { "High Freq", 1000 }, { "High Q", 2 } };
  ClickCase("high_gain_m15_p15", high, 2, "High Gain", -15.0f, 15.0f, true);
  ClickCase("level_m15_p15", NULL, 0, "Level", -15.0f, 15.0f, true);
  printf("}");
}

// 7. Host rates: refused outside 8 kHz..384 kHz, and when not a number; and
// at each accepted rate a bell at +9 dB still peaks at +9 dB, at 1 kHz.
void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 44118.0f, 48000.0f, 96000.0f, 384000.0f,
                          400000.0f, NAN, INFINITY, -44118.0f };
  printf("\"rates\":[");
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    void *self = Make(rates[i], 0);
    double peak_db = 0.0;
    if (self) {
      Set(self, "Mid Gain", 9.0f);
      float buf[128];
      double phase = 0.0;
      const uint32_t total = static_cast<uint32_t>(rates[i] / 2);   // 0.5 s
      float peak = 0.0f;
      for (uint32_t pos = 0; pos < total; pos += 64) {
        for (int k = 0; k < 64; ++k) {
          buf[2 * k] = buf[2 * k + 1] = 0.25f * static_cast<float>(sin(phase));
          phase += 2.0 * M_PI * 1000.0 / rates[i];
        }
        E.render(self, buf, 64);
        if (pos > total / 2) {
          for (int k = 0; k < 128; ++k) peak = fmaxf(peak, fabsf(buf[k]));
        }
      }
      peak_db = 20.0 * log10(peak / 0.25);
      E.destroy(self);
    }
    printf("%s[\"%g\",%s,%.4f]", i ? "," : "", rates[i], self ? "true" : "false", peak_db);
  }
  printf("]");
}

// 8. fx_eq_math.h against double precision over the ranges EQ uses: 2^x
// for x in [-100, 100] (relative error), log2 over [2^-1, 2^19] (absolute),
// tan over [0, 0.45 pi] (relative).
void Approx() {
  double exp_err = 0.0, log_err = 0.0, tan_err = 0.0;
  float exp_at = 0.0f, log_at = 0.0f, tan_at = 0.0f;
  for (int i = 0; i <= 2000000; ++i) {
    const float x = -100.0f + i * 0.0001f;
    const double want = exp2(static_cast<double>(x));
    const double err = fabs(EqExp2(x) - want) / want;
    if (err > exp_err) { exp_err = err; exp_at = x; }
  }
  for (int e = -1; e <= 18; ++e) {
    for (int m = 0; m < 65536; ++m) {
      const float x = ldexpf(1.0f + m / 65536.0f, e);
      const double err = fabs(EqLog2(x) - log2(static_cast<double>(x)));
      if (err > log_err) { log_err = err; log_at = x; }
    }
  }
  for (int i = 1; i <= 1000000; ++i) {
    const float w = static_cast<float>(i * (0.45 * M_PI / 1000000.0));
    const double want = tan(static_cast<double>(w));
    const double err = fabs(EqTan(w) - want) / want;
    if (err > tan_err) { tan_err = err; tan_at = w; }
  }
  printf("\"approx\":{\"exp2_rel\":%.3g,\"exp2_at\":%.6g,\"exp2_0\":%.9g,\"exp2_nan\":%.9g,"
         "\"exp2_low\":%.9g,\"log2_abs\":%.3g,\"log2_at\":%.6g,\"tan_rel\":%.3g,"
         "\"tan_at\":%.6g}",
         exp_err, exp_at, EqExp2(0.0f), EqExp2(NAN), EqExp2(-1000.0f), log_err, log_at, tan_err,
         tan_at);
}

// 9. Every float of three renders (3.2 s of noise each, bands moved
// mid-stream), hashed (FNV-1a over the bits): the same on every build that
// keeps to IEEE single precision without fused multiply-adds.
void Hash() {
  printf("\"hash\":[");
  for (int c = 0; c < 3; ++c) {
    void *self = Make(kRate, 0);
    if (c == 0) {
      const Kv kv[] = { { "Low Gain", 6 }, { "Mid Gain", -9 }, { "Mid Freq", 2500 },
                        { "High Gain", 4 } };
      SetAll(self, kv, 4);
    } else if (c == 1) {
      const Kv kv[] = { { "Low Freq", 40 }, { "Low Q", 1.7f }, { "Low Gain", 12 },
                        { "Mid Q", 9 }, { "Mid Gain", 15 }, { "Level", -9 } };
      SetAll(self, kv, 6);
    } else {
      const Kv kv[] = { { "High Freq", 17000 }, { "High Gain", -15 }, { "High Q", 0.3f },
                        { "Mid Freq", 20 }, { "Mid Gain", 3 } };
      SetAll(self, kv, 5);
    }
    uint32_t noise = 1u, h = 2166136261u;
    float buf[128];
    for (int b = 0; b < 2200; ++b) {
      for (int i = 0; i < 64; ++i) {
        noise = noise * 1664525u + 1013904223u;
        buf[2 * i] = 0.5f * (static_cast<int32_t>(noise) / 2147483648.0f);
        buf[2 * i + 1] = -0.5f * buf[2 * i];
      }
      if (b == 700) Set(self, "Mid Freq", 300.0f + 4000.0f * c);
      if (b == 900) Set(self, "Low Gain", -7.0f);
      if (b == 1100) Set(self, "High Q", 1.9f);
      if (b == 1500) Set(self, "Mid Gain", 0.0f);
      E.render(self, buf, 64);
      for (int i = 0; i < 128; ++i) h = (h ^ Bits(buf[i])) * 16777619u;
    }
    E.destroy(self);
    printf("%s\"%08x\"", c ? "," : "", h);
  }
  printf("]");
}

// 10. Cost: ns per 64-frame stereo block of noise, 0.5 s warm-up then 20 s.
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
    if (gliding) {
      // As a modulation route would: every band's gain and frequency, every
      // block, so all three bands glide all the time.
      Set(self, "Low Gain", (b & 1) ? -6.0f : 6.0f);
      Set(self, "Mid Freq", (b & 1) ? 500.0f : 2000.0f);
      Set(self, "High Gain", (b & 1) ? 6.0f : -6.0f);
    }
    memcpy(buf, noise + 128 * (b % 64), sizeof(buf));
    E.render(self, buf, 64);
    sink = sink + buf[0];
  }
  const auto t1 = std::chrono::steady_clock::now();
  E.destroy(self);
  return std::chrono::duration<double, std::nano>(t1 - t0).count() / blocks;
}

void Costs() {
  const Kv active[] = { { "Low Gain", 6 }, { "Mid Gain", -6 }, { "High Gain", 6 } };
  double best_flat = 1e30, best_active = 1e30, best_glide = 1e30;
  for (int run = 0; run < 3; ++run) {
    best_flat = fmin(best_flat, Cost(NULL, 0, false));
    best_active = fmin(best_active, Cost(active, 3, false));
    best_glide = fmin(best_glide, Cost(active, 3, true));
  }
  fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
  printf("\"cost\":{\"ns_per_block_flat\":%.1f,\"ns_per_block_active\":%.1f,"
         "\"ns_per_block_gliding\":%.1f,\"instance_bytes\":%zu}",
         best_flat, best_active, best_glide, E.instance_size(&host));
}

}  // namespace

int main(int argc, char **argv) {
  printf("{");
  if (argc > 1 && strcmp(argv[1], "--cost") == 0) {
    Costs();
  } else if (argc > 1 && strcmp(argv[1], "--hash") == 0) {
    // For cross-build checks: the hash and the instance size alone.
    fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
    Hash();
    printf(",\"instance_bytes\":%zu", E.instance_size(&host));
  } else {
    Sweep(); printf(",");
    Glide(); printf(",");
    Response(); printf(",");
    Exact(); printf(",");
    Silence(); printf(",");
    Clicks(); printf(",");
    Rates(); printf(",");
    Approx(); printf(",");
    Hash();
  }
  printf("}\n");
  return 0;
}
