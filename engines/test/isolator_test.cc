// isolator_test.cc -- fm1-isolator-test: drives the Isolator effect
// (src/fx_isolator.cc) through its engine struct where fm1-render cannot:
// parameters that change while audio runs (fm1-render sets an effect's
// parameters only before the first block), block sizes that change from call
// to call, host rates, and the frequency response measured in float rather
// than through a 16-bit WAV. Prints one JSON object;
// tests/test_engines_isolator.py reads it. `--bench` prints the cost of a
// 64-frame block instead. MIT licence.

#include "fm1_engine.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <chrono>

extern "C" const fm1_engine_t fm1_engine_isolator;

namespace {

const fm1_engine_t &E = fm1_engine_isolator;
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

void Set(void *self, const char *name, float v) {
  E.set_param(self, static_cast<uint16_t>(Index(name)), v);
}

// 1. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while noise plays, for 20 s. The output must stay finite and bounded. Then
// the same with silence in: the output must be exact silence throughout.
void Sweep() {
  float peak_noise = 0.0f, peak_silence = 0.0f;
  uint64_t samples = 0, nonfinite = 0;
  for (int pass = 0; pass < 2; ++pass) {
    void *self = Make(kRate, 0xA5);
    Lcg rng = { 1u };
    float buf[128];
    uint64_t done = 0;
    while (done < static_cast<uint64_t>(20 * kRate)) {
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
        const float x = 0.5f * rng.Bipolar();
        buf[2 * i] = buf[2 * i + 1] = pass ? 0.0f : x;
      }
      E.render(self, buf, n);
      for (uint32_t i = 0; i < 2 * n; ++i) {
        if (!(fabsf(buf[i]) <= 3.4e38f)) ++nonfinite;            // NaN or infinite
        else if (pass == 0) peak_noise = fmaxf(peak_noise, fabsf(buf[i]));
        else peak_silence = fmaxf(peak_silence, fabsf(buf[i]));
      }
      done += n;
    }
    samples += done;
    E.destroy(self);
  }
  printf("\"sweep\":{\"samples\":%llu,\"nonfinite\":%llu,\"peak\":%.6f,\"silence_peak\":%.9g}",
         static_cast<unsigned long long>(samples), static_cast<unsigned long long>(nonfinite),
         peak_noise, peak_silence);
}

// A test signal on both channels: sines at 100 Hz, 1 kHz and 8 kHz, one in
// each band at the defaults, 0.2 each.
float Signal(uint32_t n) {
  const double t = n / static_cast<double>(kRate);
  const double tau = 2.0 * 3.141592653589793;
  return static_cast<float>(0.2 * (sin(tau * 100.0 * t) + sin(tau * 1000.0 * t) +
                                   sin(tau * 8000.0 * t)));
}

struct Change { uint32_t at; const char *name; float value; };

// Renders kTotal frames of Signal() in blocks of `block`, split at the
// changes; the left channel goes to out_left.
void RenderSignal(uint32_t block, const Change *changes, int n_changes, uint32_t total,
                  float *out_left, float *in_left) {
  void *self = Make(kRate, 0);
  float buf[128];
  int next = 0;
  for (uint32_t pos = 0; pos < total;) {
    while (next < n_changes && changes[next].at <= pos) {
      Set(self, changes[next].name, changes[next].value);
      ++next;
    }
    uint32_t n = total - pos < block ? total - pos : block;
    if (next < n_changes && changes[next].at - pos < n) n = changes[next].at - pos;
    for (uint32_t i = 0; i < n; ++i) {
      buf[2 * i] = buf[2 * i + 1] = Signal(pos + i);
      if (in_left) in_left[pos + i] = buf[2 * i];
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < n; ++i) out_left[pos + i] = buf[2 * i];
    pos += n;
  }
  E.destroy(self);
}

const uint32_t kTotal = 44118;
float g_a[kTotal], g_b[kTotal], g_c[kTotal], g_in[kTotal];

// 2. Glides and the unity crossfade: changes mid-stream give the same output
// whatever the block size (64, 7 and 1, split at the changes); a kill fades
// over a few milliseconds; returning every band to unity crossfades back to
// the input, after which the output is the input bit for bit.
void Glide() {
  const Change ch[] = {
    { 2205, "Low", 0.6f },
    { 6615, "Kill", 2.0f }, { 6615, "High Xover", 4000.0f },
    { 11025, "Low Xover", 100.0f }, { 11025, "High", 1.0f },
    { 15435, "Kill", 5.0f },
    { 22059, "Kill", 0.0f }, { 22059, "Low", 0.75f }, { 22059, "High", 0.75f },
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  RenderSignal(64, ch, n, kTotal, g_a, g_in);
  RenderSignal(7, ch, n, kTotal, g_b, NULL);
  RenderSignal(1, ch, n, kTotal, g_c, NULL);
  const int same = memcmp(g_a, g_b, sizeof(g_a)) == 0 && memcmp(g_a, g_c, sizeof(g_a)) == 0;
  // Before the first change the defaults pass the input exactly.
  int exact_before = 1;
  for (uint32_t i = 0; i < 2205; ++i) exact_before &= g_a[i] == g_in[i];
  // The first sample from which the output is the input to the end.
  uint32_t exact_from = kTotal;
  while (exact_from > 0 && g_a[exact_from - 1] == g_in[exact_from - 1]) --exact_from;
  printf("\"glide\":{\"block_independent\":%s,\"exact_before\":%s,\"exact_from\":%u,"
         "\"unity_at\":22059}", same ? "true" : "false", exact_before ? "true" : "false",
         exact_from);
}

// 3. Controls turned every third block (64 frames) while a 100 Hz sine at
// 0.5 plays, in the low band at the defaults: the largest sample-to-sample
// step of the output, against the sine's own (0.0071). A hard switch of the
// low band would step by up to 0.5.
//   kill:   Kill through all eight masks (each in and out of unity too);
//   xover:  Low at 0.5, Low Xover 80 <-> 400 Hz and High Xover 1.5 <-> 5 kHz;
//   unity:  Low 0.75 <-> 0.7, so the output crossfades in and out of unity.
float SwitchStep(int kind, float *in_step) {
  void *self = Make(kRate, 0);
  float buf[128];
  float prev = 0.0f, prev_in = 0.0f, out_step = 0.0f;
  *in_step = 0.0f;
  int mask = 0;
  if (kind == 1) Set(self, "Low", 0.5f);
  const double w = 2.0 * 3.141592653589793 * 100.0 / kRate;
  for (uint32_t b = 0; b < 900; ++b) {
    if (b % 3 == 0) {
      const int odd = (b / 3) & 1;
      if (kind == 0) {
        mask = (mask + 3) % 8;   // 3, 6, 1, 4, 7, 2, 5, 0: every mask
        Set(self, "Kill", static_cast<float>(mask));
      } else if (kind == 1) {
        Set(self, "Low Xover", odd ? 400.0f : 80.0f);
        Set(self, "High Xover", odd ? 5000.0f : 1500.0f);
      } else {
        Set(self, "Low", odd ? 0.7f : 0.75f);
      }
    }
    float in[64];
    for (uint32_t i = 0; i < 64; ++i) {
      in[i] = buf[2 * i] = buf[2 * i + 1] = static_cast<float>(0.5 * sin(w * (64 * b + i)));
    }
    E.render(self, buf, 64);
    for (uint32_t i = 0; i < 64; ++i) {
      if (b || i) {
        out_step = fmaxf(out_step, fabsf(buf[2 * i] - prev));
        *in_step = fmaxf(*in_step, fabsf(in[i] - prev_in));
      }
      prev = buf[2 * i];
      prev_in = in[i];
    }
  }
  E.destroy(self);
  return out_step;
}

void Switching() {
  float in_step = 0.0f;
  const float kill = SwitchStep(0, &in_step);
  const float xover = SwitchStep(1, &in_step);
  const float unity = SwitchStep(2, &in_step);
  printf("\"switching\":{\"kill\":%.6f,\"xover\":%.6f,\"unity\":%.6f,\"in_step\":%.6f}",
         kill, xover, unity, in_step);
}

// 4. Frequency response: the impulse response in float, its transform at
// chosen frequencies in double. The response is linear and time-invariant
// once the settings, made before the first render, are in force.
const uint32_t kIr = 32768;
float g_ir[kIr];
double g_sum[kIr];

struct Setting { const char *name; float value; };

void ImpulseResponse(const Setting *s, int n, float *ir) {
  void *self = Make(kRate, 0x5A);
  for (int i = 0; i < n; ++i) Set(self, s[i].name, s[i].value);
  float buf[128];
  for (uint32_t pos = 0; pos < kIr; pos += 64) {
    memset(buf, 0, sizeof(buf));
    if (pos == 0) buf[0] = buf[1] = 1.0f;
    E.render(self, buf, 64);
    for (uint32_t i = 0; i < 64; ++i) ir[pos + i] = buf[2 * i];
  }
  E.destroy(self);
}

template <typename T>
double MagnitudeDb(const T *ir, double hz) {
  const double w = 2.0 * 3.141592653589793 * hz / kRate;
  const double cr = cos(w), ci = -sin(w);
  double pr = 1.0, pi = 0.0, re = 0.0, im = 0.0;
  for (uint32_t n = 0; n < kIr; ++n) {
    re += ir[n] * pr;
    im += ir[n] * pi;
    const double t = pr * cr - pi * ci;
    pi = pr * ci + pi * cr;
    pr = t;
  }
  return 10.0 * log10(re * re + im * im + 1e-300);
}

const double kFreqs[] = { 20, 40, 80, 100, 150, 250, 400, 600, 1000, 1500, 2500, 4000, 5000,
                          10000, 15000, 20000 };
const int kNFreqs = static_cast<int>(sizeof(kFreqs) / sizeof(kFreqs[0]));

void PrintResponse(const char *label, const float *ir) {
  printf("\"%s\":[", label);
  for (int i = 0; i < kNFreqs; ++i) {
    printf("%s[%g,%.6f]", i ? "," : "", kFreqs[i], MagnitudeDb(ir, kFreqs[i]));
  }
  printf("]");
}

struct Config { const char *label; Setting s[6]; int n; };

void Response() {
  const Config configs[] = {
    { "low_only", { { "Mid", 0 }, { "High", 0 } }, 2 },
    { "mid_only", { { "Low", 0 }, { "High", 0 } }, 2 },
    { "high_only", { { "Low", 0 }, { "Mid", 0 } }, 2 },
    { "kill_low", { { "Low", 0 } }, 1 },
    { "kill_mid", { { "Mid", 0 } }, 1 },
    { "kill_high", { { "High", 0 } }, 1 },
    { "boost_low", { { "Low", 1 } }, 1 },
    { "half_low", { { "Low", 0.5f } }, 1 },
    { "boost_all", { { "Low", 1 }, { "Mid", 1 }, { "High", 1 } }, 3 },
    { "low_only_80", { { "Mid", 0 }, { "High", 0 }, { "Low Xover", 80 } }, 3 },
    { "low_only_400", { { "Mid", 0 }, { "High", 0 }, { "Low Xover", 400 } }, 3 },
    { "high_only_1500", { { "Low", 0 }, { "Mid", 0 }, { "High Xover", 1500 } }, 3 },
    { "high_only_5000", { { "Low", 0 }, { "Mid", 0 }, { "High Xover", 5000 } }, 3 },
  };
  printf("\"response\":{");
  for (size_t c = 0; c < sizeof(configs) / sizeof(configs[0]); ++c) {
    ImpulseResponse(configs[c].s, configs[c].n, g_ir);
    if (c) printf(",");
    PrintResponse(configs[c].label, g_ir);
  }
  // The bands at unity, summed: the three one-band responses added in double
  // (the effect itself passes the input at unity, so the sum is built here).
  memset(g_sum, 0, sizeof(g_sum));
  const char *bands[3][2] = { { "Mid", "High" }, { "Low", "High" }, { "Low", "Mid" } };
  for (int b = 0; b < 3; ++b) {
    const Setting s[2] = { { bands[b][0], 0 }, { bands[b][1], 0 } };
    ImpulseResponse(s, 2, g_ir);
    for (uint32_t n = 0; n < kIr; ++n) g_sum[n] += g_ir[n];
  }
  double worst = 0.0;
  for (int i = 0; i <= 300; ++i) {             // 20 Hz to 20 kHz, log-spaced
    const double hz = 20.0 * pow(1000.0, i / 300.0);
    const double db = MagnitudeDb(g_sum, hz);
    if (fabs(db) > worst) worst = fabs(db);
  }
  printf(",\"sum_worst_db\":%.9f", worst);
  // Kill = Low gives the same response as Low at 0, sample for sample.
  static float other[kIr];
  const Setting knob[1] = { { "Low", 0 } }, mask[1] = { { "Kill", 1 } };
  ImpulseResponse(knob, 1, g_ir);
  ImpulseResponse(mask, 1, other);
  printf(",\"kill_mask_is_zero_gain\":%s}", memcmp(g_ir, other, sizeof(other)) ? "false" : "true");
}

// 5. The defaults on noise: the output is the input, every sample of both
// channels, from any fill of the instance memory.
void Defaults() {
  int exact = 1;
  const int fills[3] = { 0, 0xA5, 0xFF };
  for (int k = 0; k < 3; ++k) {
    void *self = Make(kRate, fills[k]);
    Lcg rng = { 7u };
    float buf[128], in[128];
    for (int b = 0; b < 700; ++b) {
      for (int i = 0; i < 128; ++i) in[i] = buf[i] = 0.9f * rng.Bipolar();
      E.render(self, buf, 64);
      exact &= memcmp(buf, in, sizeof(buf)) == 0;
    }
    E.destroy(self);
  }
  printf("\"defaults\":{\"exact\":%s}", exact ? "true" : "false");
}

// 6. Host rates: refused outside 8 kHz..384 kHz, and when not a number; at
// every accepted rate the crossovers stay below Nyquist and the output
// stays finite.
void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 44118.0f, 48000.0f, 96000.0f, 384000.0f,
                          400000.0f, NAN, INFINITY, -44118.0f };
  printf("\"rates\":[");
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    void *self = Make(rates[i], 0);
    int finite = 1;
    if (self) {
      Set(self, "High Xover", 5000.0f);
      Set(self, "Low", 0.2f);
      Lcg rng = { 3u };
      float buf[128];
      for (int b = 0; b < 200; ++b) {
        for (int k = 0; k < 128; ++k) buf[k] = 0.5f * rng.Bipolar();
        E.render(self, buf, 64);
        for (int k = 0; k < 128; ++k) finite &= fabsf(buf[k]) < 100.0f;
      }
      E.destroy(self);
    }
    printf("%s[\"%g\",%s,%s]", i ? "," : "", rates[i], self ? "true" : "false",
           finite ? "true" : "false");
  }
  printf("]");
}

// --bench: nanoseconds per 64-frame stereo block of noise, the best of five
// runs of 20,000 blocks, at three settings.
void Bench() {
  struct { const char *label; float low, kill, glide; } cases[] = {
    { "unity", 0.75f, 0.0f, 0.0f },   // the input passes; the filters run
    { "cut", 0.6f, 2.0f, 0.0f },      // the band sum
    { "moving", 0.6f, 0.0f, 1.0f },   // crossovers set every block: they glide
  };
  const fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
  printf("{\"bytes\":%u", static_cast<unsigned>(E.instance_size(&host)));
  for (size_t c = 0; c < sizeof(cases) / sizeof(cases[0]); ++c) {
    double best = 1e30;
    for (int run = 0; run < 5; ++run) {
      void *self = Make(kRate, 0);
      Set(self, "Low", cases[c].low);
      Set(self, "Kill", cases[c].kill);
      Lcg rng = { 9u };
      static float noise[128 * 64];
      for (int k = 0; k < 128 * 64; ++k) noise[k] = 0.5f * rng.Bipolar();
      float buf[128];
      const auto t0 = std::chrono::steady_clock::now();
      for (int b = 0; b < 20000; ++b) {
        memcpy(buf, noise + 128 * (b & 63), sizeof(buf));
        if (cases[c].glide != 0.0f) {
          Set(self, "Low Xover", (b & 1) ? 120.0f : 300.0f);
          Set(self, "High Xover", (b & 1) ? 2000.0f : 4000.0f);
        }
        E.render(self, buf, 64);
      }
      const auto t1 = std::chrono::steady_clock::now();
      const double ns = std::chrono::duration<double, std::nano>(t1 - t0).count() / 20000.0;
      if (ns < best) best = ns;
      E.destroy(self);
    }
    printf(",\"%s_ns\":%.1f", cases[c].label, best);
  }
  printf("}\n");
}

}  // namespace

int main(int argc, char **argv) {
  if (argc > 1 && strcmp(argv[1], "--bench") == 0) {
    Bench();
    return 0;
  }
  printf("{");
  Sweep(); printf(",");
  Glide(); printf(",");
  Switching(); printf(",");
  Response(); printf(",");
  Defaults(); printf(",");
  Rates();
  printf("}\n");
  return 0;
}
