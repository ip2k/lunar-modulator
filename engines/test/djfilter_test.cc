// djfilter_test.cc -- fm1-djfilter-test: drives the DJ Filter effect
// (src/fx_djfilter.cc) through its engine struct where fm1-render cannot:
// parameters that change while audio runs (fm1-render sets an effect's
// parameters only before the first block), block sizes that change from
// call to call, exact bypass checked on floats rather than 16-bit WAVs, the
// frequency response, transitions, tails, host rates and the cost per block.
// Prints one JSON object; tests/test_engines_djfilter.py reads it. With a
// directory as its argument it also writes two swept renders there
// (zipper-lp.f32, zipper-hp.f32: the left channel, raw float32) for the
// test's spectrum check. MIT licence.

#include "fm1_engine.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

extern "C" const fm1_engine_t fm1_engine_djfilter;

namespace {

const fm1_engine_t &E = fm1_engine_djfilter;
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

uint16_t Index(const char *name) {
  for (uint16_t i = 0; i < E.n_params; ++i) {
    if (strcmp(E.params[i].name, name) == 0) return i;
  }
  fprintf(stderr, "no parameter %s\n", name);
  return 0xFFFF;
}

void Set(void *self, const char *name, float v) { E.set_param(self, Index(name), v); }

void SetDefaults(void *self) {
  for (uint16_t i = 0; i < E.n_params; ++i) E.set_param(self, i, E.params[i].def);
}

const uint32_t kMax = 2 * 44118;
float g_in[2 * kMax], g_a[2 * kMax], g_b[2 * kMax];

// An input: both channels, deterministic.
enum Input { IN_NOISE, IN_MIX, IN_SINE60, IN_SPECIAL };

void Fill(Input kind, float *buf, uint32_t total) {
  Lcg rng = { 7u };
  for (uint32_t i = 0; i < total; ++i) {
    const double t = i / static_cast<double>(kRate);
    float l, r;
    switch (kind) {
      case IN_NOISE:
        l = 0.5f * rng.Bipolar();
        r = 0.5f * rng.Bipolar();
        break;
      case IN_MIX:   // a bass line, a mid tone and noise: every band busy
        l = static_cast<float>(0.4 * sin(2 * M_PI * 55.0 * t) + 0.2 * sin(2 * M_PI * 1250.0 * t)) +
            0.1f * rng.Bipolar();
        r = static_cast<float>(0.4 * sin(2 * M_PI * 82.5 * t) + 0.2 * sin(2 * M_PI * 3300.0 * t)) +
            0.1f * rng.Bipolar();
        break;
      case IN_SINE60:
        l = r = static_cast<float>(0.8 * sin(2 * M_PI * 60.0 * t));
        break;
      default: {     // values a bypass must keep bit for bit
        static const float kOdd[] = { -0.0f, 0.0f, 1e-40f, -1e-40f, 1e-30f, 15.999f, -15.999f,
                                      1.0f, -1.0f, 3.4e-38f, 0.333333343f };
        const uint32_t k = rng.Next() % 24;
        l = k < 11 ? kOdd[k] : 0.7f * rng.Bipolar();
        r = (k & 1) ? -l : 0.9f * rng.Bipolar();
        break;
      }
    }
    buf[2 * i] = l;
    buf[2 * i + 1] = r;
  }
}

struct Change { uint32_t at; const char *name; float value; };

// Renders `in` (total frames) in blocks of `block` frames, split at the
// changes, which apply before the frame they name.
void Run(uint32_t block, const Change *changes, int n_changes, const float *in, uint32_t total,
         float *out, int fill = 0) {
  void *self = Make(kRate, fill);
  memcpy(out, in, sizeof(float) * 2 * total);
  int next = 0;
  for (uint32_t pos = 0; pos < total;) {
    while (next < n_changes && changes[next].at <= pos) {
      Set(self, changes[next].name, changes[next].value);
      ++next;
    }
    uint32_t n = total - pos < block ? total - pos : block;
    if (next < n_changes && changes[next].at - pos < n) n = changes[next].at - pos;
    E.render(self, out + 2 * pos, n);
    pos += n;
  }
  E.destroy(self);
}

// 1. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while noise plays, with a bad sample (NaN, an infinity or 1e30) now and
// then (with `bad`), for 20 s. Then the defaults again: the effect must
// return to an exact bypass.
void Sweep(bool bad) {
  void *self = Make(kRate, 0xA5);
  Lcg rng = { 1u };
  float buf[128];
  uint64_t samples = 0, nonfinite = 0, bad_in = 0;
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
    for (uint32_t i = 0; i < 2 * n; ++i) {
      buf[i] = 0.5f * rng.Bipolar();
      if (bad && rng.Next() % 8192 == 0) {
        static const float kBad[] = { NAN, INFINITY, -INFINITY, 1e30f, -1e30f };
        buf[i] = kBad[rng.Next() % 5];
        ++bad_in;
      }
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < 2 * n; ++i) {
      if (!(fabsf(buf[i]) <= 3.4e38f)) ++nonfinite;            // NaN or infinite
      else if (fabsf(buf[i]) > peak) peak = fabsf(buf[i]);
    }
    samples += n;
  }
  // Back to the defaults: after the glide and the fade, out == in exactly.
  SetDefaults(self);
  uint64_t differ = 0;
  for (int b = 0; b < 700; ++b) {                     // about 1 s
    float in[128];
    for (int i = 0; i < 128; ++i) buf[i] = in[i] = 0.5f * rng.Bipolar();
    E.render(self, buf, 64);
    if (b >= 350 && memcmp(buf, in, sizeof(buf)) != 0) ++differ;
  }
  E.destroy(self);
  printf("\"%s\":{\"samples\":%llu,\"bad_inputs\":%llu,\"nonfinite\":%llu,\"peak\":%.6f,"
         "\"blocks_not_bypassed_after\":%llu}",
         bad ? "sweep_bad_input" : "sweep", static_cast<unsigned long long>(samples),
         static_cast<unsigned long long>(bad_in),
         static_cast<unsigned long long>(nonfinite), peak, static_cast<unsigned long long>(differ));
}

// 2. Changes mid-stream, a stretch of them every 32 frames as the
// modulation matrix writes, give the same output at host blocks of 64, 12,
// 7 and 1, from any instance fill.
void Blocks() {
  static Change ch[2048];
  int n = 0;
  ch[n++] = { 0, "Sweep", -0.4f };
  ch[n++] = { 0, "Resonance", 0.5f };
  ch[n++] = { 4410, "Sweep", 0.6f };
  ch[n++] = { 4410, "Slope", 1.0f };
  ch[n++] = { 8820, "Range", 0.5f };
  ch[n++] = { 8820, "Dead Zone", 0.1f };
  ch[n++] = { 13230, "Sweep", -0.9f };
  ch[n++] = { 13230, "Mix", 0.7f };
  ch[n++] = { 17640, "Slope", 0.0f };
  ch[n++] = { 19000, "Sweep", 0.0f };
  for (uint32_t at = 22050; at < 40000 && n < 2040; at += 32) {     // an LFO, 3 Hz
    ch[n++] = { at, "Sweep", static_cast<float>(0.95 * sin(2 * M_PI * 3.0 * (at - 22050) / kRate)) };
  }
  ch[n++] = { 41000, "Sweep", 0.0f };
  const uint32_t total = 44118;
  Fill(IN_MIX, g_in, total);
  Run(64, ch, n, g_in, total, g_a);
  bool same = true;
  const uint32_t blocks[] = { 12, 7, 1 };
  for (uint32_t b : blocks) {
    Run(b, ch, n, g_in, total, g_b, b == 7 ? 0xFF : 0x5A);
    same = same && memcmp(g_a, g_b, sizeof(float) * 2 * total) == 0;
  }
  // The last 2,000 frames are past the final return to the centre.
  bool tail_exact = memcmp(g_a + 2 * (total - 2000), g_in + 2 * (total - 2000),
                           sizeof(float) * 2 * 2000) == 0;
  printf("\"blocks\":{\"changes\":%d,\"block_independent\":%s,\"tail_bypassed\":%s}", n,
         same ? "true" : "false", tail_exact ? "true" : "false");
}

// 3. Exact bypass: the output is the input, bit for bit (negative zero,
// subnormals and values near the guard's limit included), at the defaults,
// inside the dead zone, at Mix 0 anywhere; and after a visit to a side,
// once the fade is over.
void Bypass() {
  const uint32_t total = 22059;   // 0.5 s
  Fill(IN_SPECIAL, g_in, total);
  struct Case { const char *label; Change ch[3]; int n; };
  const Case cases[] = {
    { "defaults", {}, 0 },
    { "inside_dead_zone_left", { { 0, "Sweep", -0.049f } }, 1 },
    { "inside_dead_zone_right", { { 0, "Sweep", 0.049f }, { 0, "Resonance", 1.0f } }, 2 },
    { "wide_dead_zone", { { 0, "Dead Zone", 0.2f }, { 0, "Sweep", 0.199f } }, 2 },
    { "mix_zero_left", { { 0, "Sweep", -0.7f }, { 0, "Mix", 0.0f }, { 0, "Slope", 1.0f } }, 3 },
    { "mix_zero_right", { { 0, "Sweep", 1.0f }, { 0, "Mix", 0.0f } }, 2 },
  };
  printf("\"bypass\":{");
  for (size_t c = 0; c < sizeof(cases) / sizeof(cases[0]); ++c) {
    Run(64, cases[c].ch, cases[c].n, g_in, total, g_a, 0xA5);
    const bool exact = memcmp(g_a, g_in, sizeof(float) * 2 * total) == 0;
    printf("%s\"%s\":%s", c ? "," : "", cases[c].label, exact ? "true" : "false");
  }
  // A visit: Sweep -0.6 (24 dB, resonant) from the start, back to 0 at
  // frame 8,000; and +0.8 back to 0. When is the output the input again?
  const Change visits[2][4] = {
    { { 0, "Sweep", -0.6f }, { 0, "Slope", 1.0f }, { 0, "Resonance", 0.8f }, { 8000, "Sweep", 0.0f } },
    { { 0, "Sweep", 0.8f }, { 0, "Resonance", 0.3f }, { 0, "Mix", 0.6f }, { 8000, "Sweep", 0.0f } },
  };
  for (int v = 0; v < 2; ++v) {
    Run(64, visits[v], 4, g_in, total, g_a);
    uint32_t from = total;   // the first frame of the exact run that ends the render
    while (from > 0 && memcmp(&g_a[2 * (from - 1)], &g_in[2 * (from - 1)], 2 * sizeof(float)) == 0) {
      --from;
    }
    printf(",\"%s_exact_after_ms\":%.3f", v ? "visit_right" : "visit_left",
           (static_cast<double>(from) - 8000.0) * 1000.0 / kRate);
  }
  printf("}");
}

// The gain at `hz` of a steady-state render: a 0.25 s least-squares fit of
// a sine and a cosine at hz, after 1.5 s to settle (60 Hz at Q 8 rings for
// about 0.3 s).
double Gain(const Change *ch, int n, double hz, int slope24) {
  void *self = Make(kRate, 0);
  for (int i = 0; i < n; ++i) Set(self, ch[i].name, ch[i].value);
  Set(self, "Slope", static_cast<float>(slope24));
  const uint32_t settle = static_cast<uint32_t>(1.5 * kRate), fit = static_cast<uint32_t>(0.25 * kRate);
  float buf[128];
  double ss = 0, cc = 0, sc = 0, ys = 0, yc = 0;
  for (uint32_t pos = 0; pos < settle + fit; pos += 64) {
    for (int i = 0; i < 64; ++i) {
      const double t = (pos + i) / static_cast<double>(kRate);
      buf[2 * i] = buf[2 * i + 1] = static_cast<float>(0.25 * sin(2 * M_PI * hz * t));
    }
    E.render(self, buf, 64);
    if (pos < settle) continue;
    for (int i = 0; i < 64; ++i) {
      const double t = (pos + i) / static_cast<double>(kRate);
      const double s = sin(2 * M_PI * hz * t), c = cos(2 * M_PI * hz * t);
      const double y = buf[2 * i];
      ss += s * s; cc += c * c; sc += s * c; ys += y * s; yc += y * c;
    }
  }
  E.destroy(self);
  const double det = ss * cc - sc * sc;
  const double a = (ys * cc - yc * sc) / det, b = (yc * ss - ys * sc) / det;
  return 20.0 * log10(sqrt(a * a + b * b) / 0.25);
}

// 4. The frequency response at points the test computes analytically.
void Response() {
  struct Point { float sweep, reso, dead, range; int slope24; double hz; };
  const Point pts[] = {
    // The low-pass's far end: 60 Hz, Q 0.707 (the window is 0 at u = 1).
    { -1.0f, 1.0f, 0.05f, 1.0f, 0, 60.0 }, { -1.0f, 0.0f, 0.05f, 1.0f, 0, 30.0 },
    { -1.0f, 0.0f, 0.05f, 1.0f, 0, 240.0 }, { -1.0f, 0.0f, 0.05f, 1.0f, 0, 960.0 },
    { -1.0f, 0.0f, 0.05f, 1.0f, 1, 240.0 },
    // Mid travel (u = 0.5, 1,095 Hz): Resonance 0 and 1, both slopes.
    { -0.525f, 0.0f, 0.05f, 1.0f, 0, 1095.445 }, { -0.525f, 1.0f, 0.05f, 1.0f, 0, 1095.445 },
    { -0.525f, 0.5f, 0.05f, 1.0f, 0, 1095.445 }, { -0.525f, 1.0f, 0.05f, 1.0f, 1, 1095.445 },
    { -0.525f, 0.0f, 0.05f, 1.0f, 1, 2190.89 }, { -0.525f, 0.0f, 0.05f, 1.0f, 0, 2190.89 },
    { -0.525f, 0.0f, 0.05f, 1.0f, 0, 300.0 },
    // The high-pass: far end 8 kHz, mid travel 400 Hz.
    { 1.0f, 0.0f, 0.05f, 1.0f, 0, 8000.0 }, { 1.0f, 0.0f, 0.05f, 1.0f, 0, 2000.0 },
    { 1.0f, 0.0f, 0.05f, 1.0f, 1, 2000.0 }, { 0.525f, 1.0f, 0.05f, 1.0f, 0, 400.0 },
    { 0.525f, 0.0f, 0.05f, 1.0f, 0, 100.0 }, { 0.525f, 0.0f, 0.05f, 1.0f, 1, 100.0 },
    { 0.525f, 0.0f, 0.05f, 1.0f, 0, 5000.0 },
    // Range and Dead Zone move along the same law.
    { -1.0f, 0.0f, 0.05f, 0.5f, 0, 1095.445 }, { -0.6f, 0.0f, 0.2f, 1.0f, 0, 1095.445 },
    { 0.7f, 0.6f, 0.05f, 0.75f, 1, 700.0 },
    // Near the open ends: barely there.
    { -0.06f, 1.0f, 0.05f, 1.0f, 0, 1000.0 }, { 0.06f, 1.0f, 0.05f, 1.0f, 1, 1000.0 },
  };
  printf("\"response\":[");
  for (size_t i = 0; i < sizeof(pts) / sizeof(pts[0]); ++i) {
    const Point &p = pts[i];
    const Change ch[] = { { 0, "Sweep", p.sweep }, { 0, "Resonance", p.reso },
                          { 0, "Dead Zone", p.dead }, { 0, "Range", p.range } };
    const double db = Gain(ch, 4, p.hz, p.slope24);
    printf("%s{\"sweep\":%g,\"resonance\":%g,\"dead\":%g,\"range\":%g,\"slope24\":%d,\"hz\":%.3f,"
           "\"db\":%.5f}", i ? "," : "", p.sweep, p.reso, p.dead, p.range, p.slope24, p.hz, db);
  }
  printf("]");
}

// 5. Swept renders for the spectrum check: a 1000.3 Hz sine (bin 743 of a
// 32,768-point transform) while Sweep follows a 0.7 Hz sine LFO written
// every 32 frames, the way the modulation matrix will write it.
void Zipper(const char *dir) {
  const uint32_t total = 2 * 32768;
  struct Leg { const char *file; float centre, depth, reso; int slope24; };
  const Leg legs[] = {
    { "zipper-lp.f32", -0.5f, 0.35f, 0.6f, 0 },
    { "zipper-hp.f32", 0.5f, 0.35f, 0.6f, 1 },
  };
  for (const Leg &leg : legs) {
    void *self = Make(kRate, 0);
    Set(self, "Resonance", leg.reso);
    Set(self, "Slope", static_cast<float>(leg.slope24));
    static float left[2 * 32768];
    float buf[64];
    for (uint32_t pos = 0; pos < total; pos += 32) {
      const double t = pos / static_cast<double>(kRate);
      Set(self, "Sweep", static_cast<float>(leg.centre + leg.depth * sin(2 * M_PI * 0.7 * t)));
      for (int i = 0; i < 32; ++i) {
        const double ti = (pos + i) / static_cast<double>(kRate);
        buf[2 * i] = buf[2 * i + 1] = static_cast<float>(0.25 * sin(2 * M_PI * (743.0 * kRate / 32768.0) * ti));
      }
      E.render(self, buf, 32);
      for (int i = 0; i < 32; ++i) left[pos + i] = buf[2 * i];
    }
    E.destroy(self);
    if (dir) {
      char path[1024];
      snprintf(path, sizeof(path), "%s/%s", dir, leg.file);
      FILE *f = fopen(path, "wb");
      if (f) {
        fwrite(left, sizeof(float), total, f);
        fclose(f);
      }
    }
  }
  printf("\"zipper\":{\"written\":%s}", dir ? "true" : "false");
}

// A 4th-order Butterworth high-pass at 4 kHz (two TPT SVFs, double): what
// it lets through of a 60 Hz sine is under -140 dB, so its output is what a
// transition adds above 4 kHz, which is where a click is heard.
struct Highpass4k {
  double s[4] = { 0, 0, 0, 0 };
  double Step(double x) {
    const double g = tan(M_PI * 4000.0 / kRate);
    const double r[2] = { 2.0 * 0.923879533, 2.0 * 0.382683432 };   // 1/Q of the two sections
    for (int k = 0; k < 2; ++k) {
      double &s1 = s[2 * k], &s2 = s[2 * k + 1];
      const double hp = (x - (r[k] + g) * s1 - s2) / (1.0 + r[k] * g + g * g);
      const double bp = g * hp + s1;
      const double lp = g * bp + s2;
      s1 = g * hp + bp;
      s2 = g * bp + lp;
      x = hp;
    }
    return x;
  }
};

// 6. Transitions on a 0.8 60 Hz sine (a bass note: the worst case for a
// thump), each at a positive peak 0.5 s in: the largest second difference
// of the output (a click shows as a large one) before and after, and the
// output's peak after.
void Transitions() {
  struct Event { const char *label; Change before[3]; int nb; Change after[2]; int na; };
  const uint32_t at = 22243;   // 60 Hz: (30 + 1/4) cycles of 735.3 frames, a positive peak
  const Event events[] = {
    { "enter_lp", { { 0, "Resonance", 0.0f } }, 1, { { at, "Sweep", -0.3f } }, 1 },
    { "enter_hp", { { 0, "Resonance", 0.0f } }, 1, { { at, "Sweep", 0.3f } }, 1 },
    { "enter_lp_24_reso", { { 0, "Resonance", 1.0f }, { 0, "Slope", 1.0f } }, 2, { { at, "Sweep", -0.7f } }, 1 },
    { "enter_hp_24_reso", { { 0, "Resonance", 1.0f }, { 0, "Slope", 1.0f } }, 2, { { at, "Sweep", 0.2f } }, 1 },
    { "lp_to_hp", { { 0, "Sweep", -0.5f } }, 1, { { at, "Sweep", 0.5f } }, 1 },
    { "hp_to_lp", { { 0, "Sweep", 0.15f } }, 1, { { at, "Sweep", -0.5f } }, 1 },
    { "lp_to_hp_no_dead_zone", { { 0, "Sweep", -0.3f }, { 0, "Dead Zone", 0.0f } }, 2, { { at, "Sweep", 0.3f } }, 1 },
    { "slope_up", { { 0, "Sweep", -0.75f }, { 0, "Resonance", 0.5f } }, 2, { { at, "Slope", 1.0f } }, 1 },
    { "slope_down", { { 0, "Sweep", -0.75f }, { 0, "Resonance", 0.5f }, { 0, "Slope", 1.0f } }, 3, { { at, "Slope", 0.0f } }, 1 },
    { "leave_lp", { { 0, "Sweep", -0.8f } }, 1, { { at, "Sweep", 0.0f } }, 1 },
    { "leave_hp", { { 0, "Sweep", 0.4f } }, 1, { { at, "Sweep", 0.0f } }, 1 },
    { "mix_up", { { 0, "Sweep", -0.8f }, { 0, "Mix", 0.0f } }, 2, { { at, "Mix", 1.0f } }, 1 },
  };
  const uint32_t total = 44118;
  Fill(IN_SINE60, g_in, total);
  float in_d2 = 0.0f;
  for (uint32_t i = 2; i < total; ++i) {
    const float d2 = fabsf(g_in[2 * i] - 2.0f * g_in[2 * (i - 1)] + g_in[2 * (i - 2)]);
    if (d2 > in_d2) in_d2 = d2;
  }
  printf("\"transitions\":{\"input_d2\":%.9g,\"input_peak\":0.8", in_d2);
  for (const Event &ev : events) {
    Change ch[5];
    int n = 0;
    for (int i = 0; i < ev.nb; ++i) ch[n++] = ev.before[i];
    for (int i = 0; i < ev.na; ++i) ch[n++] = ev.after[i];
    Run(64, ch, n, g_in, total, g_a);
    float d2_before = 0.0f, d2_after = 0.0f, peak_after = 0.0f;
    double hf_before = 0.0, hf_after = 0.0;
    uint32_t hf_at = at;
    const uint32_t w = static_cast<uint32_t>(0.1 * kRate);
    Highpass4k hf;
    for (uint32_t i = 0; i < at + 2 * w; ++i) {
      const double h = hf.Step(g_a[2 * i]);
      if (i < at - w) continue;
      double &hslot = i < at ? hf_before : hf_after;
      if (fabs(h) > hslot) {
        hslot = fabs(h);
        if (i >= at) hf_at = i;
      }
      for (int c = 0; c < 2; ++c) {
        const float d2 = fabsf(g_a[2 * i + c] - 2.0f * g_a[2 * (i - 1) + c] + g_a[2 * (i - 2) + c]);
        float &slot = i < at ? d2_before : d2_after;
        if (d2 > slot) slot = d2;
        if (i >= at && fabsf(g_a[2 * i + c]) > peak_after) peak_after = fabsf(g_a[2 * i + c]);
      }
    }
    printf(",\"%s\":{\"d2_before\":%.9g,\"d2_after\":%.9g,\"hf_before\":%.9g,"
           "\"hf_after\":%.9g,\"hf_at_ms\":%.2f,\"peak_after\":%.6f}", ev.label, d2_before,
           d2_after, hf_before, hf_after, (hf_at - at) * 1000.0 / kRate, peak_after);
  }
  printf("}");
}

// 7. Silence after full-scale noise, through the most resonant settings:
// the tail rings down and the states flush, so the output becomes exact
// zeros; and silence in from the start is exact silence out.
void Tails() {
  printf("\"tails\":{");
  const float sweeps[] = { -0.525f, -1.0f, 0.525f, 0.05001f };
  for (size_t s = 0; s < sizeof(sweeps) / sizeof(sweeps[0]); ++s) {
    void *self = Make(kRate, 0xFF);
    Set(self, "Sweep", sweeps[s]);
    Set(self, "Resonance", 1.0f);
    Set(self, "Slope", 1.0f);
    Lcg rng = { 3u };
    float buf[128];
    for (int b = 0; b < 345; ++b) {                 // 0.5 s of noise
      for (int i = 0; i < 128; ++i) buf[i] = rng.Bipolar();
      E.render(self, buf, 64);
    }
    int last_nonzero = -1;
    for (int b = 0; b < 3446; ++b) {                // 5 s of silence
      memset(buf, 0, sizeof(buf));
      E.render(self, buf, 64);
      for (int i = 0; i < 128; ++i) {
        if (buf[i] != 0.0f) last_nonzero = b;
      }
    }
    E.destroy(self);
    printf("%s\"sweep_%g_zero_after_ms\":%.1f", s ? "," : "", sweeps[s],
           (last_nonzero + 1) * 64 * 1000.0 / kRate);
  }
  printf("}");
}

// 8. Host rates: refused outside 8 kHz..384 kHz, and when not a number.
// Accepted ones must filter: the high-pass far end at a low rate is capped
// at 0.45 of it.
void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 44118.0f, 48000.0f, 96000.0f, 384000.0f,
                          400000.0f, NAN, INFINITY, -44118.0f };
  printf("\"rates\":[");
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    void *self = Make(rates[i], 0);
    bool finite = true;
    if (self) {
      Set(self, "Sweep", 1.0f);
      Set(self, "Resonance", 1.0f);
      Lcg rng = { 9u };
      float buf[128];
      for (int b = 0; b < 400; ++b) {
        for (int k = 0; k < 128; ++k) buf[k] = 0.5f * rng.Bipolar();
        E.render(self, buf, 64);
        for (int k = 0; k < 128; ++k) finite = finite && fabsf(buf[k]) < 100.0f;
      }
      E.destroy(self);
    }
    printf("%s[\"%g\",%s,%s]", i ? "," : "", rates[i], self ? "true" : "false",
           finite ? "true" : "false");
  }
  printf("]");
}

// 9. Cost per 64-frame block on this machine: the best of five runs of 20 s
// of noise each.
double NsPerBlock(const Change *ch, int n, bool lfo) {
  double best = 1e30;
  for (int run = 0; run < 5; ++run) {
    void *self = Make(kRate, 0);
    for (int i = 0; i < n; ++i) Set(self, ch[i].name, ch[i].value);
    Lcg rng = { 11u };
    static float noise[128 * 64];
    for (int i = 0; i < 128 * 64; ++i) noise[i] = 0.5f * rng.Bipolar();
    float buf[128];
    const int blocks = 13784;                         // 20 s
    float sink = 0.0f;
    timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int b = 0; b < blocks; ++b) {
      if (lfo) {   // the matrix: a write every 32 frames, so one per block here
        Set(self, "Sweep", -0.5f + 0.4f * static_cast<float>((b % 400) < 200 ? (b % 200) : 200 - (b % 200)) / 200.0f);
      }
      memcpy(buf, noise + 128 * (b % 64), sizeof(buf));
      E.render(self, buf, 64);
      sink += buf[b & 127];
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    E.destroy(self);
    const double ns = ((t1.tv_sec - t0.tv_sec) * 1e9 + (t1.tv_nsec - t0.tv_nsec)) / blocks;
    if (ns < best) best = ns;
    if (sink == 12345.0f) printf(" ");                // keep the work
  }
  return best;
}

void Bench() {
  const Change lp12[] = { { 0, "Sweep", -0.5f }, { 0, "Resonance", 0.5f } };
  const Change lp24[] = { { 0, "Sweep", -0.5f }, { 0, "Resonance", 0.5f }, { 0, "Slope", 1.0f } };
  fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
  printf("\"bench\":{\"instance_bytes\":%zu,\"bypass_ns\":%.1f,\"lp12_ns\":%.1f,\"lp24_ns\":%.1f,"
         "\"lp24_modulated_ns\":%.1f}",
         E.instance_size(&host), NsPerBlock(NULL, 0, false), NsPerBlock(lp12, 2, false),
         NsPerBlock(lp24, 3, false), NsPerBlock(lp24, 3, true));
}

}  // namespace

int main(int argc, char **argv) {
  const bool bench_only = argc > 1 && strcmp(argv[1], "--bench") == 0;
  printf("{");
  if (!bench_only) {
    Sweep(false); printf(",");
    Sweep(true); printf(",");
    Blocks(); printf(",");
    Bypass(); printf(",");
    Response(); printf(",");
    Zipper(argc > 1 ? argv[1] : NULL); printf(",");
    Transitions(); printf(",");
    Tails(); printf(",");
    Rates();
  } else {
    Bench();
  }
  printf("}\n");
  return 0;
}
