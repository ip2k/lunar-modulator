// filter_test.cc -- fm1-filter-test: drives the Filter effect
// (src/fx_filter.cc) through its engine struct where fm1-render cannot:
// parameters that change while audio runs (fm1-render sets an effect's
// parameters only before the first block), block sizes that change from
// call to call, host rates, sine sweeps for frequency responses, and
// self-oscillation. With no arguments it prints one JSON object, which
// tests/test_engines_filter.py reads. For exploration:
//
//   fm1-filter-test --gain TYPE MODE RES CUTOFF MORPH DRIVE HZ...   gains in dB (left)
//   fm1-filter-test --osc TYPE MODE RES CUTOFF [RATE]              self-oscillation
//   fm1-filter-test --bench                                        ns per 64-frame block
//
// The analysis uses double precision and libm; only the effect must not.
// MIT licence.

#include "fm1_engine.h"

#include <chrono>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_filter;

namespace {

const fm1_engine_t &E = fm1_engine_filter;
const float kRate = 44118.0f;
const double kPi = 3.141592653589793;
alignas(16) unsigned char g_mem[1u << 18];   // 384 kHz needs about 155 KB

enum { SVF, LADDER, DIODE, K35, STEINER, COMB, FORMANT, NTYPES };
const char *const kTypes[NTYPES] = { "svf", "ladder", "diode", "k35", "steiner", "comb", "formant" };

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
  exit(2);
}

void Set(void *self, const char *name, float v) {
  E.set_param(self, static_cast<uint16_t>(Index(name)), v);
}

struct Settings {
  int type;
  float mode, res, cutoff, morph, drive;
};

void Apply(void *self, const Settings &s) {
  Set(self, "Type", static_cast<float>(s.type));
  Set(self, "Mode", s.mode);
  Set(self, "Resonance", s.res);
  Set(self, "Cutoff", s.cutoff);
  Set(self, "Morph", s.morph);
  Set(self, "Drive", s.drive);
  Set(self, "Mix", 1.0f);
  Set(self, "Level", 1.0f);
}

// Amplitude of the component at hz in y (a whole number of samples), by
// correlation; exact for whole periods, and within 1/n otherwise.
double Amplitude(const float *y, size_t n, size_t stride, double hz, double rate, double phase0) {
  double a = 0.0, b = 0.0;
  const double w = 2.0 * kPi * hz / rate;
  for (size_t i = 0; i < n; ++i) {
    const double ph = phase0 + w * static_cast<double>(i);
    a += y[i * stride] * sin(ph);
    b += y[i * stride] * cos(ph);
  }
  return 2.0 * sqrt(a * a + b * b) / static_cast<double>(n);
}

// Small-signal gain in dB at hz, channel ch, after the filter settles.
// Measured over whole periods (rounded), after 0.25 s and 30 periods.
double GainDb(const Settings &s, double hz, int ch = 0, double amp = 0.01, float rate = kRate,
              double *harm2 = NULL, double *harm3 = NULL) {
  void *self = Make(rate, 0);
  Apply(self, s);
  const double settle_s = 0.25 + 30.0 / hz;
  const size_t settle = static_cast<size_t>(settle_s * rate);
  size_t periods = static_cast<size_t>(0.25 * hz) + 8;
  const size_t meas = static_cast<size_t>(floor(periods * rate / hz + 0.5));
  const size_t total = settle + meas;
  static float out[2 * 200000];   // the measured part only
  if (meas > 200000) { fprintf(stderr, "too long\n"); exit(2); }
  const double w = 2.0 * kPi * hz / rate;
  float buf[128];
  for (size_t pos = 0; pos < total;) {
    const size_t n = total - pos < 64 ? total - pos : 64;
    for (size_t i = 0; i < n; ++i) {
      const float x = static_cast<float>(amp * sin(w * static_cast<double>(pos + i)));
      buf[2 * i] = buf[2 * i + 1] = x;
    }
    E.render(self, buf, static_cast<uint32_t>(n));
    for (size_t i = 0; i < n; ++i) {
      if (pos + i >= settle) {
        out[2 * (pos + i - settle)] = buf[2 * i];
        out[2 * (pos + i - settle) + 1] = buf[2 * i + 1];
      }
    }
    pos += n;
  }
  E.destroy(self);
  const double ph0 = w * static_cast<double>(settle);
  const double a = Amplitude(&out[ch], meas, 2, hz, rate, ph0);
  if (harm2) *harm2 = Amplitude(&out[ch], meas, 2, 2 * hz, rate, 2 * ph0) / a;
  if (harm3) *harm3 = Amplitude(&out[ch], meas, 2, 3 * hz, rate, 3 * ph0) / a;
  return 20.0 * log10(a / amp + 1e-30);
}

// Self-oscillation: a 1e-3 click, then silence; the pitch over the last
// half second (rising zero crossings, interpolated) and the peak there.
void Oscillate(const Settings &s, float rate, double *hz, double *peak) {
  void *self = Make(rate, 0);
  Apply(self, s);
  const size_t total = static_cast<size_t>(2.0 * rate);
  const size_t from = static_cast<size_t>(1.5 * rate);
  float buf[128];
  double prev = 0.0, first = -1.0, last = -1.0, pk = 0.0;
  int crossings = 0;
  for (size_t pos = 0; pos < total; pos += 64) {
    memset(buf, 0, sizeof(buf));
    if (pos == 0) buf[0] = buf[1] = 1e-3f;
    E.render(self, buf, 64);
    for (size_t i = 0; i < 64; ++i) {
      const double y = buf[2 * i];
      const size_t n = pos + i;
      if (n >= from) {
        if (fabs(y) > pk) pk = fabs(y);
        if (prev < 0.0 && y >= 0.0) {
          const double t = static_cast<double>(n - 1) + (-prev) / (y - prev);
          if (first < 0.0) first = t;
          last = t;
          ++crossings;
        }
      }
      prev = y;
    }
  }
  E.destroy(self);
  *hz = crossings > 1 ? (crossings - 1) * static_cast<double>(rate) / (last - first) : 0.0;
  *peak = pk;
}

// 1. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while noise plays, with loud bursts, for 10 s at each host rate. The
// output must stay finite and bounded.
void Sweep() {
  const float rates[] = { 8000.0f, 44118.0f, 96000.0f, 384000.0f };
  printf("\"sweep\":[");
  for (size_t r = 0; r < sizeof(rates) / sizeof(rates[0]); ++r) {
    void *self = Make(rates[r], 0xA5);
    Lcg rng = { 7u + static_cast<uint32_t>(r) };
    float buf[128];
    uint64_t samples = 0, nonfinite = 0;
    float peak = 0.0f;
    const uint64_t total = static_cast<uint64_t>(10.0 * rates[r]);
    float loud = 0.5f;
    while (samples < total) {
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
      if (rng.Next() % 200 == 0) loud = (rng.Next() & 1) ? 16.0f : 0.5f;  // bursts at the guard
      for (uint32_t i = 0; i < n; ++i) {
        buf[2 * i] = loud * rng.Bipolar();
        buf[2 * i + 1] = loud * rng.Bipolar();
      }
      E.render(self, buf, n);
      for (uint32_t i = 0; i < 2 * n; ++i) {
        if (!(fabsf(buf[i]) <= 3.4e38f)) ++nonfinite;
        else if (fabsf(buf[i]) > peak) peak = fabsf(buf[i]);
      }
      samples += n;
    }
    E.destroy(self);
    printf("%s{\"rate\":%g,\"samples\":%llu,\"nonfinite\":%llu,\"peak\":%.6f}", r ? "," : "",
           rates[r], static_cast<unsigned long long>(samples),
           static_cast<unsigned long long>(nonfinite), peak);
  }
  printf("]");
}

// Every type at its hottest settings, held for 4 s each, with full-scale
// noise at the guard's limit: the largest output. Level 2, Mix 1.
void Extremes() {
  printf("\"extremes\":[");
  for (int t = 0; t < NTYPES; ++t) {
    float worst = 0.0f;
    uint64_t nonfinite = 0;
    const float modes[] = { 0.0f, 1.0f, 2.0f, 3.0f };
    for (int m = 0; m < 4; ++m) {
      for (int hot = 0; hot < 2; ++hot) {
        void *self = Make(kRate, 0);
        const Settings s = { t, modes[m], 1.0f, hot ? 18000.0f : 60.0f, hot ? 1.0f : 0.0f, 1.0f };
        Apply(self, s);
        Set(self, "Level", 2.0f);
        Lcg rng = { 99u };
        float buf[128];
        for (int b = 0; b < static_cast<int>(4 * kRate / 64); ++b) {
          for (int i = 0; i < 128; ++i) buf[i] = 16.0f * rng.Bipolar();
          if (b > 2 * kRate / 64) memset(buf, 0, sizeof(buf));   // then silence: ringing
          E.render(self, buf, 64);
          for (int i = 0; i < 128; ++i) {
            if (!(fabsf(buf[i]) <= 3.4e38f)) ++nonfinite;
            else if (fabsf(buf[i]) > worst) worst = fabsf(buf[i]);
          }
        }
        E.destroy(self);
      }
    }
    printf("%s{\"type\":\"%s\",\"peak\":%.4f,\"nonfinite\":%llu}", t ? "," : "", kTypes[t], worst,
           static_cast<unsigned long long>(nonfinite));
  }
  printf("]");
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
      Set(self, changes[next].name, changes[next].value);
      ++next;
    }
    uint32_t n = total - pos < block ? total - pos : block;
    if (next < n_changes && changes[next].at - pos < n) n = changes[next].at - pos;
    for (uint32_t i = 0; i < n; ++i) {
      const float x = amplitude * static_cast<float>(sin(phase));
      phase += 2.0 * kPi * 440.0 / kRate;
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

// 2. The glide: changes mid-stream, Type switches among them, give the same
// output whatever the block size (64, 7 and 1 frames, split at the
// changes), and Level 1 -> 0 fades over a few milliseconds, then reaches
// exact silence.
void Glide() {
  const Change ch[] = {
    { 0, "Cutoff", 800.0f }, { 0, "Resonance", 0.6f }, { 0, "Type", 0.0f },
    { 3001, "Cutoff", 5000.0f }, { 3001, "Mode", 1.4f }, { 3001, "Drive", 0.5f },
    { 6003, "Type", 1.0f }, { 6100, "Type", 3.0f },        // the second waits for the first
    { 9000, "Morph", 0.7f }, { 9000, "Resonance", 0.97f },
    { 12007, "Type", 4.0f }, { 15011, "Type", 5.0f }, { 15011, "Cutoff", 300.0f },
    { 18013, "Type", 6.0f }, { 18013, "Morph", 0.4f }, { 18013, "Mix", 0.6f },
    { 21017, "Type", 2.0f }, { 21017, "Mode", 3.0f },
    { 30000, "Level", 0.0f }, { 30000, "Mix", 1.0f },
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  RenderSine(64, ch, n, kTotal, 0.5f, g_a);
  RenderSine(7, ch, n, kTotal, 0.5f, g_b);
  RenderSine(1, ch, n, kTotal, 0.5f, g_c);
  const int same = memcmp(g_a, g_b, sizeof(g_a)) == 0 && memcmp(g_a, g_c, sizeof(g_a)) == 0;
  float before = 0.0f, first_ms = 0.0f, tail = 0.0f;
  for (uint32_t i = 30000 - 441; i < 30000; ++i) before = fmaxf(before, fabsf(g_a[i]));
  for (uint32_t i = 30000; i < 30000 + 44; ++i) first_ms = fmaxf(first_ms, fabsf(g_a[i]));
  for (uint32_t i = 30000 + 2205; i < kTotal; ++i) tail = fmaxf(tail, fabsf(g_a[i]));
  printf("\"glide\":{\"block_independent\":%s,\"before\":%.6f,\"first_ms\":%.6f,"
         "\"tail\":%.9g}", same ? "true" : "false", before, first_ms, tail);
}

// 3. A Type change crossfades: a 440 Hz sine through each pair of types,
// switched at 0.5 s. The largest step between neighbouring samples in the
// 20 ms after the switch, against the largest in the 100 ms before it and
// in the 100 ms that start 100 ms after it (each type's own steady state).
void Switch() {
  printf("\"switch\":[");
  int first = 1;
  for (int a = 0; a < NTYPES; ++a) {
    for (int b = 0; b < NTYPES; ++b) {
      if (a == b) continue;
      const Change ch[] = {
        { 0, "Type", static_cast<float>(a) }, { 0, "Cutoff", 1500.0f }, { 0, "Resonance", 0.5f },
        { 22059, "Type", static_cast<float>(b) },
      };
      RenderSine(64, ch, 4, kTotal, 0.5f, g_a);
      float steady = 0.0f, across = 0.0f;
      for (uint32_t i = 22059 - 4411; i < 22059; ++i) steady = fmaxf(steady, fabsf(g_a[i] - g_a[i - 1]));
      for (uint32_t i = 22059 + 4411; i < 22059 + 8822; ++i) {
        steady = fmaxf(steady, fabsf(g_a[i] - g_a[i - 1]));
      }
      for (uint32_t i = 22059; i < 22059 + 882; ++i) across = fmaxf(across, fabsf(g_a[i] - g_a[i - 1]));
      printf("%s{\"from\":\"%s\",\"to\":\"%s\",\"steady\":%.6f,\"across\":%.6f}", first ? "" : ",",
             kTypes[a], kTypes[b], steady, across);
      first = 0;
    }
  }
  printf("]");
}

// 4. Silence in: from rest, exact silence at any setting; after a burst of
// noise, a tail that flushes to exact silence (settings that do not
// oscillate), so no subnormals are left behind.
void Silence() {
  printf("\"silence\":[");
  for (int t = 0; t < NTYPES; ++t) {
    float rest = 0.0f;
    for (int m = 0; m <= 3; ++m) {
      void *self = Make(kRate, 0xFF);
      const Settings s = { t, static_cast<float>(m), 1.0f, 3000.0f, 0.5f, 1.0f };
      Apply(self, s);
      float buf[128];
      for (int b = 0; b < 700; ++b) {
        memset(buf, 0, sizeof(buf));
        E.render(self, buf, 64);
        for (int i = 0; i < 128; ++i) rest = fmaxf(rest, fabsf(buf[i]));
      }
      E.destroy(self);
    }
    void *self = Make(kRate, 0);
    const Settings s = { t, 0.0f, 0.7f, 1000.0f, 0.3f, 0.3f };
    Apply(self, s);
    Lcg rng = { 5u };
    float buf[128];
    int quiet_at = -1;
    for (int b = 0; b < static_cast<int>(40 * kRate / 64); ++b) {
      if (b < 100) for (int i = 0; i < 128; ++i) buf[i] = 0.5f * rng.Bipolar();
      else memset(buf, 0, sizeof(buf));
      E.render(self, buf, 64);
      float pk = 0.0f;
      for (int i = 0; i < 128; ++i) pk = fmaxf(pk, fabsf(buf[i]));
      if (pk != 0.0f) quiet_at = -1;
      else if (quiet_at < 0) quiet_at = b;
    }
    E.destroy(self);
    printf("%s{\"type\":\"%s\",\"rest_peak\":%.9g,\"silent_after_s\":%.3f}", t ? "," : "", kTypes[t],
           rest, quiet_at < 0 ? -1.0 : (quiet_at - 100) * 64.0 / kRate);
  }
  printf("]");
}

// 5. Host rates: refused outside 8 kHz..384 kHz, and when not a number;
// the instance size at each.
void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 44118.0f, 48000.0f, 96000.0f, 384000.0f,
                          400000.0f, NAN, INFINITY, -44118.0f };
  printf("\"rates\":[");
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    fm1_host_t host = { FM1_ENGINE_API_VERSION, rates[i], 64 };
    void *self = Make(rates[i], 0);
    printf("%s[\"%g\",%s,%zu]", i ? "," : "", rates[i], self ? "true" : "false",
           E.instance_size(&host));
    if (self) E.destroy(self);
  }
  printf("]");
}

// 6. Frequency responses: small-signal gains (dB) at listed frequencies.
struct Case { const char *name; Settings s; int ch; float rate; double hz[8]; };

void Responses() {
  const Case cases[] = {
    // name, {type, mode, res, cutoff, morph, drive}, channel, rate, frequencies
    { "svf_lp",     { SVF, 0, 0, 1000, 0, 0 }, 0, kRate, { 50, 1000, 4000, 8000 } },
    { "svf_bp",     { SVF, 1, 0, 1000, 0, 0 }, 0, kRate, { 1000, 125, 8000 } },
    { "svf_hp",     { SVF, 2, 0, 1000, 0, 0 }, 0, kRate, { 15000, 1000, 250, 125 } },
    { "svf_notch",  { SVF, 3, 0.5f, 1000, 0, 0 }, 0, kRate, { 1000, 100, 10000 } },
    { "svf_lp_q",   { SVF, 0, 0.8f, 1000, 0, 0 }, 0, kRate, { 1000, 50 } },
    { "ladder_4",   { LADDER, 0, 0, 500, 0, 0 }, 0, kRate, { 30, 500, 2000, 4000 } },
    { "ladder_3",   { LADDER, 1, 0, 500, 0, 0 }, 0, kRate, { 30, 500, 2000, 4000 } },
    { "ladder_2",   { LADDER, 2, 0, 500, 0, 0 }, 0, kRate, { 30, 500, 2000, 4000 } },
    { "ladder_1",   { LADDER, 3, 0, 500, 0, 0 }, 0, kRate, { 30, 500, 2000, 4000 } },
    { "ladder_res", { LADDER, 0, 0.85f, 1000, 0, 0 }, 0, kRate, { 30, 1000, 4000 } },
    { "diode_0",    { DIODE, 0, 0, 1000, 0, 0 }, 0, kRate, { 30, 1000, 4000, 8000 } },
    { "diode_res",  { DIODE, 0, 0.85f, 1000, 0, 0 }, 0, kRate, { 30, 1000, 500, 2000 } },
    { "diode_1p",   { DIODE, 3, 0, 1000, 0, 0 }, 0, kRate, { 30, 4000, 8000 } },
    { "k35_lp",     { K35, 0, 0, 1000, 0, 0 }, 0, kRate, { 30, 1000, 4000, 8000 } },
    { "k35_hp",     { K35, 2, 0, 1000, 0, 0 }, 0, kRate, { 15000, 1000, 250, 125 } },
    { "k35_bp",     { K35, 1, 0, 1000, 0, 0 }, 0, kRate, { 1000, 100, 10000 } },
    { "k35_res",    { K35, 0, 0.85f, 1000, 0, 0 }, 0, kRate, { 30, 1000, 4000 } },
    { "steiner_lp", { STEINER, 0, 0, 1000, 0, 0 }, 0, kRate, { 30, 1000, 4000, 8000 } },
    { "steiner_hp", { STEINER, 2, 0, 1000, 0, 0 }, 0, kRate, { 15000, 1000, 125, 62.5 } },
    { "steiner_bp", { STEINER, 1, 0.6f, 1000, 0, 0 }, 0, kRate, { 1000, 100, 10000 } },
    { "steiner_notch", { STEINER, 3, 0, 1000, 0, 0 }, 0, kRate, { 1000, 30, 15000 } },
    { "steiner_res", { STEINER, 0, 0.85f, 1000, 0, 0 }, 0, kRate, { 30, 1000, 4000 } },
    // Comb at 441.18 Hz (100 samples): positive peaks at k f, troughs at
    // (k + 1/2) f; negative: the reverse; feedforward: notches.
    { "comb_pos",   { COMB, 0, 0.8f, 441.18f, 0, 0 }, 0, kRate, { 441.18, 882.36, 661.77, 1102.95 } },
    { "comb_neg",   { COMB, 0, 0.8f, 441.18f, 1, 0 }, 0, kRate, { 220.59, 661.77, 441.18, 882.36 } },
    { "comb_ff",    { COMB, 3, 1.0f, 441.18f, 0, 0 }, 0, kRate, { 441.18, 220.59, 661.77 } },
    // Formant, men's A (730, 1090, 2440 Hz) and I (270, 2290, 3010 Hz).
    { "formant_a",  { FORMANT, 0, 0.5f, 1000, 0, 0 }, 0, kRate, { 730, 1090, 2440, 1700, 270, 2290 } },
    { "formant_i",  { FORMANT, 0, 0.5f, 1000, 0.5f, 0 }, 0, kRate, { 270, 2290, 3010, 730, 1090 } },
    // Formant shifted by Cutoff 4 kHz: x2 (730 -> 1460).
    { "formant_a_up", { FORMANT, 0, 0.5f, 4000, 0, 0 }, 0, kRate, { 1460, 730 } },
    // Spread: Morph 1 puts the left channel an octave down, the right one up.
    { "spread_l",   { SVF, 0, 0, 1000, 1, 0 }, 0, kRate, { 500, 1000, 2000 } },
    { "spread_r",   { SVF, 0, 0, 1000, 1, 0 }, 1, kRate, { 500, 1000, 2000 } },
    // The same SVF low-pass at other host rates.
    { "svf_lp_8k",  { SVF, 0, 0, 1000, 0, 0 }, 0, 8000.0f, { 50, 1000, 3000 } },
    { "svf_lp_96k", { SVF, 0, 0, 1000, 0, 0 }, 0, 96000.0f, { 50, 1000, 8000 } },
    { "svf_lp_384k", { SVF, 0, 0, 1000, 0, 0 }, 0, 384000.0f, { 50, 1000, 8000 } },
    // Cutoff clamps below Nyquist: 18 kHz asked at 8 kHz is 3.6 kHz.
    { "svf_lp_8k_top", { SVF, 0, 0, 18000, 0, 0 }, 0, 8000.0f, { 3600, 100 } },
    // Resonance compensation: the pass band at full resonance.
    { "pass_svf",     { SVF, 0, 0.9f, 2000, 0, 0 }, 0, kRate, { 40 } },
    { "pass_ladder",  { LADDER, 0, 0.9f, 2000, 0, 0 }, 0, kRate, { 40 } },
    { "pass_diode",   { DIODE, 0, 0.9f, 2000, 0, 0 }, 0, kRate, { 40 } },
    { "pass_k35",     { K35, 0, 0.9f, 2000, 0, 0 }, 0, kRate, { 40 } },
    { "pass_steiner", { STEINER, 0, 0.9f, 2000, 0, 0 }, 0, kRate, { 40 } },
  };
  printf("\"response\":{");
  for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
    const Case &c = cases[i];
    printf("%s\"%s\":[", i ? "," : "", c.name);
    for (int k = 0; k < 8 && c.hz[k] > 0.0; ++k) {
      printf("%s[%g,%.3f]", k ? "," : "", c.hz[k], GainDb(c.s, c.hz[k], c.ch, 0.01, c.rate));
    }
    printf("]");
  }
  printf("}");
}

// 7. Self-oscillation: pitch against Cutoff, and level.
void Oscillation() {
  const int types[] = { SVF, LADDER, DIODE, K35, STEINER };
  const float cutoffs[] = { 110.0f, 440.0f, 1760.0f, 5000.0f };
  printf("\"osc\":[");
  int first = 1;
  for (size_t t = 0; t < sizeof(types) / sizeof(types[0]); ++t) {
    for (size_t c = 0; c < sizeof(cutoffs) / sizeof(cutoffs[0]); ++c) {
      double hz, peak;
      const Settings s = { types[t], 0, 1.0f, cutoffs[c], 0, 0 };
      Oscillate(s, kRate, &hz, &peak);
      printf("%s{\"type\":\"%s\",\"cutoff\":%g,\"hz\":%.4f,\"peak\":%.4f}", first ? "" : ",",
             kTypes[types[t]], cutoffs[c], hz, peak);
      first = 0;
    }
  }
  // Below the threshold: no oscillation.
  const Settings quiet[] = { { SVF, 0, 0.85f, 1000, 0, 0 }, { LADDER, 0, 0.85f, 1000, 0, 0 },
                             { DIODE, 0, 0.85f, 1000, 0, 0 }, { K35, 0, 0.85f, 1000, 0, 0 } };
  for (size_t i = 0; i < 4; ++i) {
    double hz, peak;
    Oscillate(quiet[i], kRate, &hz, &peak);
    printf(",{\"type\":\"%s\",\"cutoff\":1000,\"res\":0.85,\"hz\":%.4f,\"peak\":%.9g}",
           kTypes[quiet[i].type], hz, peak);
  }
  // Other host rates.
  const float rates[] = { 8000.0f, 96000.0f, 384000.0f };
  for (size_t r = 0; r < 3; ++r) {
    for (size_t t = 0; t < 4; ++t) {
      double hz, peak;
      const Settings s = { types[t], 0, 1.0f, 440.0f, 0, 0 };
      Oscillate(s, rates[r], &hz, &peak);
      printf(",{\"type\":\"%s\",\"cutoff\":440,\"rate\":%g,\"hz\":%.4f,\"peak\":%.4f}",
             kTypes[types[t]], rates[r], hz, peak);
    }
  }
  printf("]");
}

// 8. Drive and the nonlinear character: harmonics of a 200 Hz sine at
// 0.5 through the low-pass modes at 5 kHz.
void Harmonics() {
  printf("\"harmonics\":[");
  int first = 1;
  for (int t = 0; t < NTYPES; ++t) {
    if (t == COMB) continue;
    const float drives[] = { 0.0f, 1.0f };
    for (int d = 0; d < 2; ++d) {
      const Settings s = { t, 0, 0.5f, t == FORMANT ? 1000.0f : 5000.0f, 0, drives[d] };
      double h2, h3;
      const double g = GainDb(s, 200.0, 0, 0.5, kRate, &h2, &h3);
      printf("%s{\"type\":\"%s\",\"drive\":%g,\"gain\":%.3f,\"h2\":%.3f,\"h3\":%.3f}",
             first ? "" : ",", kTypes[t], drives[d], g, 20 * log10(h2 + 1e-12), 20 * log10(h3 + 1e-12));
      first = 0;
    }
  }
  printf("]");
}

// 9. Steiner's diodes: with Drive 1, a louder input darkens it (the gain
// at 2 kHz falls further than at 250 Hz); K35, whose drive clips before
// its loop, keeps its tilt. Cutoff 1 kHz, low-pass, Resonance 0.3.
void Level() {
  printf("\"level\":[");
  const int types[] = { STEINER, K35 };
  const double amps[] = { 0.01, 0.5 };
  for (int t = 0; t < 2; ++t) {
    for (int a = 0; a < 2; ++a) {
      const Settings s = { types[t], 0, 0.3f, 1000, 0, 1.0f };
      const double lo = GainDb(s, 250.0, 0, amps[a]), hi = GainDb(s, 2000.0, 0, amps[a]);
      printf("%s{\"type\":\"%s\",\"amp\":%g,\"g250\":%.3f,\"g2000\":%.3f}", (t || a) ? "," : "",
             kTypes[types[t]], amps[a], lo, hi);
    }
  }
  printf("]");
}

// Cost per 64-frame stereo block of noise, each type: parameters still;
// and the worst case, Cutoff and Resonance moved twice a block (a
// modulation route at docs/16's G = 32) with Morph's spread on, so every
// control step recomputes both channels' coefficients.
void Bench() {
  printf("{\"ns_per_block\":[");
  for (int t = 0; t < NTYPES; ++t) {
    double ns[2];
    for (int moving = 0; moving < 2; ++moving) {
      void *self = Make(kRate, 0);
      const Settings s = { t, 1.5f, 0.6f, 1200.0f, moving ? 0.3f : 0.0f, 0.3f };
      Apply(self, s);
      Lcg rng = { 3u };
      float buf[128];
      const int blocks = 20000;
      double total = 0.0;
      for (int b = 0; b < blocks; ++b) {
        for (int i = 0; i < 128; ++i) buf[i] = 0.5f * rng.Bipolar();
        const auto t0 = std::chrono::steady_clock::now();
        if (moving) {
          Set(self, "Cutoff", 300.0f + 3000.0f * rng.Unit());
          Set(self, "Resonance", 0.5f + 0.4f * rng.Unit());
          E.render(self, buf, 32);
          Set(self, "Cutoff", 300.0f + 3000.0f * rng.Unit());
          E.render(self, buf + 64, 32);
        } else {
          E.render(self, buf, 64);
        }
        total += std::chrono::duration<double, std::nano>(std::chrono::steady_clock::now() - t0).count();
      }
      E.destroy(self);
      ns[moving] = total / blocks;
    }
    printf("%s{\"type\":\"%s\",\"still\":%.1f,\"moving\":%.1f}", t ? "," : "", kTypes[t], ns[0], ns[1]);
  }
  printf("],\"block_ns\":%.1f}\n", 64e9 / kRate);
}

int Type(const char *name) {
  for (int t = 0; t < NTYPES; ++t) {
    if (strcmp(name, kTypes[t]) == 0) return t;
  }
  return atoi(name);
}

}  // namespace

int main(int argc, char **argv) {
  if (argc > 7 && strcmp(argv[1], "--gain") == 0) {
    const Settings s = { Type(argv[2]), static_cast<float>(atof(argv[3])), static_cast<float>(atof(argv[4])),
                         static_cast<float>(atof(argv[5])), static_cast<float>(atof(argv[6])),
                         static_cast<float>(atof(argv[7])) };
    for (int i = 8; i < argc; ++i) {
      double h2, h3;
      const double g = GainDb(s, atof(argv[i]), 0, 0.01, kRate, &h2, &h3);
      printf("%10.2f Hz  %8.3f dB\n", atof(argv[i]), g);
    }
    return 0;
  }
  if (argc > 5 && strcmp(argv[1], "--osc") == 0) {
    const Settings s = { Type(argv[2]), static_cast<float>(atof(argv[3])), static_cast<float>(atof(argv[4])),
                         static_cast<float>(atof(argv[5])), 0, 0 };
    double hz, peak;
    Oscillate(s, argc > 6 ? static_cast<float>(atof(argv[6])) : kRate, &hz, &peak);
    printf("%.4f Hz (%.2f cents)  peak %.4f\n", hz, 1200.0 * log2(hz / atof(argv[5])), peak);
    return 0;
  }
  if (argc > 1 && strcmp(argv[1], "--bench") == 0) {
    Bench();
    return 0;
  }
  printf("{");
  Rates(); printf(",");
  Sweep(); printf(",");
  Extremes(); printf(",");
  Glide(); printf(",");
  Switch(); printf(",");
  Silence(); printf(",");
  Responses(); printf(",");
  Oscillation(); printf(",");
  Harmonics(); printf(",");
  Level();
  printf("}\n");
  return 0;
}
