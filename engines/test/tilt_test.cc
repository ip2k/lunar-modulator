// tilt_test.cc -- fm1-tilt-test: drives the Tilt effect (src/fx_tilt.cc)
// through its engine struct where fm1-render cannot: its frequency response
// in float (fm1-render writes 16-bit WAVs through the limiter), the exact
// bypass bit for bit, parameters that change at any frame (fm1-render
// turns them only between its 64-frame blocks), block sizes that change
// from call to call, and host rates. Prints one JSON object;
// tests/test_engines_tilt.py reads it. MIT licence.

#include "fm1_engine.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_tilt;

namespace {

const fm1_engine_t &E = fm1_engine_tilt;
const float kRate = 44118.0f;
alignas(16) unsigned char g_mem[1024];

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

void SetP(void *self, const char *name, float v) {
  E.set_param(self, static_cast<uint16_t>(Index(name)), v);
}

struct Setting { float tilt, pivot, curve, level; };

void Apply(void *self, const Setting &s) {
  SetP(self, "Tilt", s.tilt);
  SetP(self, "Pivot", s.pivot);
  SetP(self, "Curve", s.curve);
  SetP(self, "Level", s.level);
}

// 1. The frequency response: the impulse response of a fresh instance (the
// setting applied before the first block), 32,768 frames, and its DFT in
// double at chosen frequencies, in dB. Both channels must agree exactly.
const uint32_t kImpulse = 32768;
float g_ir[2 * kImpulse];

double GainDb(const float *ir, uint32_t n, double hz) {
  double re = 0.0, im = 0.0;
  const double w = 2.0 * 3.141592653589793 * hz / kRate;
  for (uint32_t i = 0; i < n; ++i) {
    re += ir[2 * i] * cos(w * i);
    im -= ir[2 * i] * sin(w * i);
  }
  return 10.0 * log10(re * re + im * im);
}

void Response() {
  const float tilts[] = { -9.0f, -6.0f, -3.0f, 3.0f, 6.0f, 9.0f };
  const float pivots[] = { 200.0f, 1000.0f, 5000.0f };
  const double freqs[] = { 0.0, 20.0, 50.0, 100.0, 200.0, 300.0, 500.0, 700.0, 1000.0, 1500.0,
                           2000.0, 3000.0, 5000.0, 7000.0, 10000.0, 15000.0, 20000.0,
                           kRate / 2.0 };
  const int nf = static_cast<int>(sizeof(freqs) / sizeof(freqs[0]));
  printf("\"response\":[");
  int first = 1;
  for (int c = 0; c < 2; ++c) {
    for (size_t p = 0; p < sizeof(pivots) / sizeof(pivots[0]); ++p) {
      for (size_t t = 0; t < sizeof(tilts) / sizeof(tilts[0]); ++t) {
        for (int lv = 0; lv < 2; ++lv) {
          const Setting s = { tilts[t], pivots[p], static_cast<float>(c), lv ? -6.0f : 0.0f };
          if (lv && !(t == 5 && p == 1)) continue;          // Level once is enough
          void *self = Make(kRate, 0x5A);
          Apply(self, s);
          memset(g_ir, 0, sizeof(g_ir));
          g_ir[0] = g_ir[1] = 1.0f;
          for (uint32_t pos = 0; pos < kImpulse; pos += 64) E.render(self, g_ir + 2 * pos, 64);
          E.destroy(self);
          int stereo = 1;
          for (uint32_t i = 0; i < kImpulse; ++i) stereo &= g_ir[2 * i] == g_ir[2 * i + 1];
          double tail = 0.0;
          for (uint32_t i = kImpulse - 1024; i < kImpulse; ++i) tail = fmax(tail, fabs(g_ir[2 * i]));
          printf("%s{\"tilt\":%g,\"pivot\":%g,\"curve\":%d,\"level\":%g,\"stereo\":%s,"
                 "\"tail\":%.3g,\"pivot_db\":%.7f,\"db\":[",
                 first ? "" : ",", s.tilt, s.pivot, c, s.level, stereo ? "true" : "false", tail,
                 GainDb(g_ir, kImpulse, s.pivot));
          for (int k = 0; k < nf; ++k) {
            printf("%s[%.4f,%.7f]", k ? "," : "", freqs[k], GainDb(g_ir, kImpulse, freqs[k]));
          }
          printf("]}");
          first = 0;
        }
      }
    }
  }
  printf("]");
}

// Bits of a float, for exact comparisons (-0 and +0 differ).
uint32_t Bits(float x) { uint32_t b; memcpy(&b, &x, sizeof b); return b; }

// 2. The exact bypass: at Tilt 0 (any Pivot and Curve, Level 0 dB) every
// finite input within the guard comes out bit for bit, signed zeros and
// subnormals included, at random block sizes; and after Tilt, Curve, Pivot
// and Level have moved and come back, it does again once the glide lands.
const uint32_t kBypass = 44118;
float g_in[2 * kBypass], g_out[2 * kBypass];

void FillAwkward(Lcg *rng) {
  const float special[] = { 0.0f, -0.0f, 1e-40f, -1e-40f, 1.4e-45f, -1.4e-45f, 1e-30f,
                            -1e-30f, 15.999999f, -15.999999f, 1.0f, -1.0f, 3.0e-8f };
  const int ns = static_cast<int>(sizeof(special) / sizeof(special[0]));
  for (uint32_t i = 0; i < 2 * kBypass; ++i) {
    const uint32_t r = rng->Next() % 8;
    if (r == 0) g_in[i] = special[rng->Next() % ns];
    else if (r == 1) g_in[i] = 15.9f * rng->Bipolar();
    else g_in[i] = rng->Bipolar();
  }
}

// Renders g_in into g_out at random block sizes, applying `later` at frame
// `at` and `back` at frame `back_at` (when given).
void RenderAwkward(const Setting &s, Lcg *rng, const Setting *later, uint32_t at,
                   const Setting *back, uint32_t back_at) {
  void *self = Make(kRate, 0xC3);
  Apply(self, s);
  memcpy(g_out, g_in, sizeof(g_in));
  for (uint32_t pos = 0; pos < kBypass;) {
    if (later && pos == at) Apply(self, *later);
    if (back && pos == back_at) Apply(self, *back);
    uint32_t n = 1 + rng->Next() % 64;
    if (n > kBypass - pos) n = kBypass - pos;
    if (later && pos < at && pos + n > at) n = at - pos;
    if (back && pos < back_at && pos + n > back_at) n = back_at - pos;
    E.render(self, g_out + 2 * pos, n);
    pos += n;
  }
  E.destroy(self);
}

uint32_t Mismatches(uint32_t from) {
  uint32_t bad = 0;
  for (uint32_t i = 2 * from; i < 2 * kBypass; ++i) bad += Bits(g_in[i]) != Bits(g_out[i]);
  return bad;
}

void Bypass() {
  Lcg rng = { 7u };
  FillAwkward(&rng);
  const Setting neutral[] = {
    { 0.0f, 1000.0f, 0.0f, 0.0f },     // the defaults
    { 0.0f, 200.0f, 1.0f, 0.0f },
    { 0.0f, 5000.0f, 1.0f, 0.0f },
    { 0.0f, 3333.0f, 0.0f, 0.0f },
  };
  printf("\"bypass\":{\"mismatches\":[");
  for (size_t k = 0; k < sizeof(neutral) / sizeof(neutral[0]); ++k) {
    RenderAwkward(neutral[k], &rng, NULL, 0, NULL, 0);
    printf("%s%u", k ? "," : "", Mismatches(0));
  }
  // Away and back: Tilt +9, Slope, Pivot 300, Level -5 at 0.1 s; back to
  // Tilt 0 and Level 0 at 0.5 s (Curve and Pivot stay).
  const Setting away = { 9.0f, 300.0f, 1.0f, -5.0f };
  const Setting back = { 0.0f, 300.0f, 1.0f, 0.0f };
  RenderAwkward(neutral[0], &rng, &away, 4412, &back, 22059);
  uint32_t last_bad = 0;
  for (uint32_t f = 0; f < kBypass; ++f) {
    if (Bits(g_in[2 * f]) != Bits(g_out[2 * f]) || Bits(g_in[2 * f + 1]) != Bits(g_out[2 * f + 1])) {
      last_bad = f;
    }
  }
  printf("],\"away_moved\":%s,\"exact_again_after_ms\":%.2f,\"tail_mismatches\":%u}",
         Mismatches(4412) > 0 ? "true" : "false", (last_bad + 1 - 22059) * 1000.0 / kRate,
         Mismatches(22059 + 2206));
}

// A sine on both channels through one instance, with parameter changes at
// given frames, rendered in blocks of `block` (split at the changes).
struct Change { uint32_t at; const char *name; float value; };

void RenderSine(uint32_t block, const Setting &start, const Change *changes, int n_changes,
                uint32_t total, double hz, float amplitude, float *out_left) {
  void *self = Make(kRate, 0);
  Apply(self, start);
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
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < n; ++i) out_left[pos + i] = buf[2 * i];
    pos += n;
  }
  E.destroy(self);
}

const uint32_t kTotal = 44118;
float g_a[kTotal], g_b[kTotal], g_c[kTotal];

// 3. Changes mid-stream give the same output whatever the block size.
void Glide() {
  const Setting start = { -4.0f, 700.0f, 0.0f, 0.0f };
  const Change ch[] = {
    { 3000, "Tilt", 9.0f }, { 3000, "Pivot", 4000.0f },
    { 9000, "Curve", 1.0f }, { 9001, "Level", -12.0f },
    { 15000, "Tilt", -9.0f }, { 15000, "Pivot", 200.0f }, { 15000, "Curve", 0.0f },
    { 30000, "Tilt", 0.0f }, { 30000, "Level", 0.0f },
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  RenderSine(64, start, ch, n, kTotal, 440.0, 0.5f, g_a);
  RenderSine(7, start, ch, n, kTotal, 440.0, 0.5f, g_b);
  RenderSine(1, start, ch, n, kTotal, 440.0, 0.5f, g_c);
  const int same = memcmp(g_a, g_b, sizeof(g_a)) == 0 && memcmp(g_a, g_c, sizeof(g_a)) == 0;
  printf("\"glide\":{\"block_independent\":%s}", same ? "true" : "false");
}

// The largest |second difference| over [from, to): the size of a click on a
// smooth signal, which for a steady sine is A (2 sin(w / 2))^2.
float MaxD2(const float *x, uint32_t from, uint32_t to) {
  float m = 0.0f;
  for (uint32_t i = from + 1; i + 1 < to; ++i) m = fmaxf(m, fabsf(x[i + 1] - 2.0f * x[i] + x[i - 1]));
  return m;
}

// 4. A jump of one control, all the way, while a sine plays: ours against a
// hard switch between the two steady outputs at the same frame (what an
// unsmoothed change would come close to), and against the steady outputs'
// own second differences.
void Jump(const char *label, const Setting &before, const char *name, float to, double hz,
          float amp, int *first) {
  const uint32_t at = 22059;
  Setting after = before;
  if (!strcmp(name, "Tilt")) after.tilt = to;
  else if (!strcmp(name, "Pivot")) after.pivot = to;
  else if (!strcmp(name, "Curve")) after.curve = to;
  else after.level = to;
  const Change ch[] = { { at, name, to } };
  RenderSine(64, before, ch, 1, kTotal, hz, amp, g_a);
  RenderSine(64, before, NULL, 0, kTotal, hz, amp, g_b);
  RenderSine(64, after, NULL, 0, kTotal, hz, amp, g_c);
  const float steady = fmaxf(MaxD2(g_b, at - 4410, at + 4410), MaxD2(g_c, at - 4410, at + 4410));
  const float ours = MaxD2(g_a, at - 4410, at + 4410);
  for (uint32_t i = at; i < kTotal; ++i) g_b[i] = g_c[i];       // the hard switch
  const float hard = MaxD2(g_b, at - 4410, at + 4410);
  float settled = 0.0f;                                           // 50 ms on: the new output
  for (uint32_t i = at + 2206; i < kTotal; ++i) settled = fmaxf(settled, fabsf(g_a[i] - g_c[i]));
  printf("%s\"%s\":{\"ours\":%.4g,\"steady\":%.4g,\"hard\":%.4g,\"settled_err\":%.3g}",
         *first ? "" : ",", label, ours, steady, hard, settled);
  *first = 0;
}

void Jumps() {
  int first = 1;
  printf("\"jumps\":{");
  Jump("tilt", { -9.0f, 1000.0f, 0.0f, 0.0f }, "Tilt", 9.0f, 100.0, 0.25f, &first);
  Jump("pivot", { 9.0f, 200.0f, 0.0f, 0.0f }, "Pivot", 5000.0f, 1000.0, 0.25f, &first);
  Jump("curve", { 9.0f, 1000.0f, 0.0f, 0.0f }, "Curve", 1.0f, 150.0, 0.25f, &first);
  Jump("curve_back", { -9.0f, 1000.0f, 1.0f, 0.0f }, "Curve", 0.0f, 5000.0, 0.25f, &first);
  Jump("level", { 3.0f, 1000.0f, 0.0f, -24.0f }, "Level", 12.0f, 1000.0, 0.1f, &first);
  printf("}");
}

// 5. Modulation at the matrix's rate: Tilt follows a 1 Hz sine across its
// whole range, set every 32 frames (and, for comparison, every frame), on a
// 100 Hz sine. Zipper noise would show as energy far above 100 Hz; the
// third difference measures it (it passes 100 Hz at -110 dB and 5 kHz at
// -10 dB), relative to the signal.
double ZipperDb(uint32_t every) {
  void *self = Make(kRate, 0);
  float buf[2];
  double phase = 0.0, sum_x = 0.0, sum_d3 = 0.0;
  float h[4] = { 0, 0, 0, 0 };
  for (uint32_t pos = 0; pos < 2 * kTotal; ++pos) {
    if (pos % every == 0) SetP(self, "Tilt", 9.0f * static_cast<float>(sin(2.0 * 3.141592653589793 * pos / kRate)));
    buf[0] = buf[1] = 0.25f * static_cast<float>(sin(phase));
    phase += 2.0 * 3.141592653589793 * 100.0 / kRate;
    E.render(self, buf, 1);
    h[0] = h[1]; h[1] = h[2]; h[2] = h[3]; h[3] = buf[0];
    if (pos >= 4410) {
      const double d3 = h[3] - 3.0 * h[2] + 3.0 * h[1] - h[0];
      sum_d3 += d3 * d3;
      sum_x += static_cast<double>(h[3]) * h[3];
    }
  }
  E.destroy(self);
  return 10.0 * log10(sum_d3 / sum_x);
}

void Zipper() {
  printf("\"zipper\":{\"every_32\":%.2f,\"every_1\":%.2f}", ZipperDb(32), ZipperDb(1));
}

// 6. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while noise plays, for 20 s; and the same with input at the guard's
// limit. The output must stay finite and bounded.
void Sweep(float amplitude, const char *label) {
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
    for (uint32_t i = 0; i < n; ++i) {
      const float x = rng.Bipolar();
      buf[2 * i] = amplitude * x;
      buf[2 * i + 1] = amplitude * (x < 0.0f ? -1.0f : 1.0f);
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < 2 * n; ++i) {
      if (!(fabsf(buf[i]) <= 3.4e38f)) ++nonfinite;            // NaN or infinite
      else if (fabsf(buf[i]) > peak) peak = fabsf(buf[i]);
    }
    samples += n;
  }
  E.destroy(self);
  printf("\"%s\":{\"samples\":%llu,\"nonfinite\":%llu,\"peak\":%.6f}", label,
         static_cast<unsigned long long>(samples), static_cast<unsigned long long>(nonfinite),
         peak);
}

// 7. Silence: exact zeros while every control moves; after noise stops, the
// tail at the slowest setting (Tilt -9, Pivot 200, Slope) and how long until
// the output is exact zeros again (the states flush below 1e-20).
void Silence() {
  void *self = Make(kRate, 0xFF);
  float buf[128];
  float moving = 0.0f;
  const Setting steps[] = { { 9, 5000, 1, 12 }, { -9, 200, 0, -24 }, { 4, 700, 1, 3 },
                            { -9, 200, 1, 12 } };
  for (int k = 0; k < 4; ++k) {
    Apply(self, steps[k]);
    for (int b = 0; b < 100; ++b) {
      memset(buf, 0, sizeof(buf));
      E.render(self, buf, 64);
      for (int i = 0; i < 128; ++i) moving = fmaxf(moving, fabsf(buf[i]));
    }
  }
  Lcg rng = { 3u };
  for (int b = 0; b < 400; ++b) {
    for (int i = 0; i < 128; ++i) buf[i] = 0.5f * rng.Bipolar();
    E.render(self, buf, 64);
  }
  int zero_from = -1;
  float last = 1.0f;
  for (int b = 0; b < 1400; ++b) {                      // 2 s of silence
    memset(buf, 0, sizeof(buf));
    E.render(self, buf, 64);
    last = 0.0f;
    for (int i = 0; i < 128; ++i) last = fmaxf(last, fabsf(buf[i]));
    if (last != 0.0f) zero_from = -1;
    else if (zero_from < 0) zero_from = b;
  }
  E.destroy(self);
  printf("\"silence\":{\"moving_peak\":%.9g,\"zero_after_ms\":%.1f,\"last_block_peak\":%.9g}",
         moving, zero_from < 0 ? -1.0 : zero_from * 64 * 1000.0 / kRate, last);
}

// 8. Host rates: refused outside 8 kHz..384 kHz, and when not a number; at
// 8 kHz the 5 kHz pivot is held below 0.45 of the rate, and the response
// there stays finite.
void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 44118.0f, 48000.0f, 96000.0f, 384000.0f,
                          400000.0f, NAN, INFINITY, -44118.0f };
  printf("\"rates\":[");
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    void *self = Make(rates[i], 0);
    int finite = 1;
    if (self) {
      Apply(self, { 9.0f, 5000.0f, 1.0f, 12.0f });
      float buf[128];
      Lcg rng = { 9u };
      for (int b = 0; b < 200; ++b) {
        for (int k = 0; k < 128; ++k) buf[k] = 0.5f * rng.Bipolar();
        E.render(self, buf, 64);
        for (int k = 0; k < 128; ++k) finite &= fabsf(buf[k]) <= 3.4e38f;
      }
      E.destroy(self);
    }
    printf("%s[\"%g\",%s,%s]", i ? "," : "", rates[i], self ? "true" : "false",
           finite ? "true" : "false");
  }
  printf("]");
}

}  // namespace

int main() {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
  printf("{\"instance_size\":%zu,", E.instance_size(&host));
  Response(); printf(",");
  Bypass(); printf(",");
  Glide(); printf(",");
  Jumps(); printf(",");
  Zipper(); printf(",");
  Sweep(0.5f, "sweep"); printf(",");
  Sweep(16.0f, "sweep_hot"); printf(",");
  Silence(); printf(",");
  Rates();
  printf("}\n");
  return 0;
}
