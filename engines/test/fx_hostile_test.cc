// fx_hostile_test.cc -- fm1-fx-hostile-test: the same hostile checks, run
// alike on every effect of the master-bus pack (DJ Filter, Tilt, EQ,
// Isolator, Master Sat), through their engine structs only. Written for the
// review of the integrated pack (2026-10-05), which found with it that
// Isolator's crossover glide could stall short of its target for ever.
// Each effect's own test program checks its design; this one checks the
// host contracts of fm1_engine.h the same way for all five, and harder:
//
//   blocks     parameters changed at random frames (before the first block
//              too), rendered in blocks of 64, 1, 7, 13, random sizes and
//              one call of 4,096 frames, split at the changes: bit for bit
//              the same output;
//   fills      the instance memory filled with zeros, 0xA5, 0xFF, 0x7F,
//              NaNs, infinities or random bytes before create: the same;
//   chaos      3 s of NaN, infinities, 1e30, -0 and out-of-range values
//              written to random parameters every few frames, with NaN,
//              infinities, 3e38 and subnormals in the input: finite and
//              bounded output, and then, 3 s after one setting is written,
//              the output of an instance made with that setting (no
//              latching, and every glide lands);
//   neutral    each effect's pass-through settings, from every fill, on
//              input with -0, subnormals, FLT_MIN and values at and next to
//              the guard's +/-16: the input bit for bit; and again a time
//              after a visit to a busy setting (printed in ms);
//   extremes   parameters thrown between their ends every frame (blocks of
//              one frame): finite and bounded;
//   tail       loud input, then 30 s of silence: when the output becomes
//              exact zeros, and whether a subnormal ever comes out;
//   rates      refused outside 8-384 kHz and when not a number; random
//              changes stay bounded and the neutral setting stays exact at
//              8, 11.025, 22.05, 32, 48, 96, 192 and 384 kHz;
//   glides     each parameter moved end to end and between random values at
//              8, 44.118, 96 and 384 kHz: 1.5 s later the output is within
//              1e-5 of an instance made at the new value (a few routes into
//              a narrow 20 Hz band keep float rounding noise near 1e-6,
//              which the count of not bit-identical routes shows);
//   index      writes to an index past the table change nothing.
//
// Prints one JSON object; tests/test_engines_fx_hostile.py reads it. MIT
// licence.

#include "fm1_engine.h"

#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <vector>

extern "C" const fm1_engine_t fm1_engine_djfilter, fm1_engine_tilt, fm1_engine_sat,
    fm1_engine_isolator, fm1_engine_eq;

namespace {

const float kRate = 44118.0f;

struct Rng {
  uint64_t s;
  explicit Rng(uint64_t seed) : s(seed * 2654435761u + 0x9E3779B97F4A7C15ull) {}
  uint32_t Next() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return static_cast<uint32_t>(s >> 16); }
  float Unit() { return (Next() >> 8) / 16777216.0f; }   // [0, 1)
  float Bipolar() { return 2.0f * Unit() - 1.0f; }
};

alignas(16) unsigned char g_mem[16384];

const int kFills = 7;

void Fill(unsigned char *m, size_t n, int mode) {
  Rng r(77);
  switch (mode) {
    case 0: memset(m, 0, n); break;
    case 1: memset(m, 0xA5, n); break;
    case 2: memset(m, 0xFF, n); break;
    case 3: { const float q = NAN; for (size_t i = 0; i + 4 <= n; i += 4) memcpy(m + i, &q, 4); break; }
    case 4: for (size_t i = 0; i < n; ++i) m[i] = static_cast<unsigned char>(r.Next()); break;
    case 5: { const float q = INFINITY; for (size_t i = 0; i + 4 <= n; i += 4) memcpy(m + i, &q, 4); break; }
    default: memset(m, 0x7F, n); break;
  }
}

void *Make(const fm1_engine_t &e, float rate, uint32_t max_frames, int fill) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, max_frames };
  if (e.instance_size(&host) > sizeof(g_mem)) return NULL;
  Fill(g_mem, sizeof(g_mem), fill);
  return e.create(g_mem, &host);
}

struct Event { uint32_t frame; uint16_t index; float value; };
typedef std::vector<float> Buf;
typedef std::vector<Event> Events;

// Renders `in` (stereo, interleaved) through a new instance, applying each
// event before the frame it names. part: 0 blocks of 64, 1 of 1, 2 of 7,
// 3 random 1..max_frames, 4 of 13, 5 of max_frames; always split at events.
Buf Run(const fm1_engine_t &e, float rate, int fill, const Buf &in, const Events &ev, int part,
        uint32_t max_frames = 64, uint32_t seed = 5) {
  void *self = Make(e, rate, max_frames, fill);
  Buf buf = in;
  if (!self) { buf.assign(in.size(), NAN); return buf; }
  const uint32_t n = static_cast<uint32_t>(in.size() / 2);
  Rng r(seed);
  size_t k = 0;
  for (uint32_t f = 0; f < n;) {
    while (k < ev.size() && ev[k].frame <= f) { e.set_param(self, ev[k].index, ev[k].value); ++k; }
    const uint32_t sizes[] = { 64, 1, 7, 1 + r.Next() % max_frames, 13, max_frames };
    uint32_t want = sizes[part];
    if (want > max_frames) want = max_frames;
    if (k < ev.size() && ev[k].frame - f < want) want = ev[k].frame - f;
    if (want > n - f) want = n - f;
    e.render(self, buf.data() + 2 * f, want);
    f += want;
  }
  e.destroy(self);
  return buf;
}

int Index(const fm1_engine_t &e, const char *name) {
  for (uint16_t i = 0; i < e.n_params; ++i) {
    if (strcmp(e.params[i].name, name) == 0) return i;
  }
  return -1;
}

// A test signal: a gated 55 Hz bass, an 880 Hz tone and noise, the right
// channel a mix of the left and more noise.
Buf Music(uint32_t frames, float amp, uint32_t seed, float rate) {
  Buf v(2 * frames);
  Rng r(seed);
  for (uint32_t i = 0; i < frames; ++i) {
    const double t = i / static_cast<double>(rate);
    const double gate = fmod(t, 0.25) < 0.18 ? 1.0 : 0.0;
    const double s = 0.5 * sin(2 * M_PI * 55 * t) * gate + 0.3 * sin(2 * M_PI * 880 * t) +
                     0.1 * r.Bipolar();
    v[2 * i] = static_cast<float>(amp * s);
    v[2 * i + 1] = static_cast<float>(amp * (0.8 * s + 0.05 * r.Bipolar()));
  }
  return v;
}

// Music with awkward values within the guard scattered through it.
Buf AwkwardInput(uint32_t frames, uint32_t seed) {
  Buf v = Music(frames, 0.9f, seed, kRate);
  Rng r(seed + 3);
  const float special[] = { -0.0f, 0.0f, 1e-40f, -1e-40f, FLT_MIN, -FLT_MIN, 1e-30f, 15.999999f,
                            -15.999999f, 16.0f, -16.0f, 8.0f, -12.5f, 1e-20f, 3e-39f };
  for (size_t i = 0; i < v.size(); ++i) {
    if (r.Next() % 9 == 0) v[i] = special[r.Next() % 15];
  }
  return v;
}

// The largest magnitude, or infinity if anything is not finite.
float Peak(const Buf &v) {
  float p = 0.0f;
  for (float x : v) {
    if (!(fabsf(x) <= FLT_MAX)) return INFINITY;
    if (fabsf(x) > p) p = fabsf(x);
  }
  return p;
}

bool SameBits(const Buf &a, const Buf &b) {
  return a.size() == b.size() && memcmp(a.data(), b.data(), a.size() * sizeof(float)) == 0;
}

float RandomValue(const fm1_param_t &p, Rng &r, bool garbage) {
  if (garbage) {
    switch (r.Next() % 12) {
      case 0: return NAN;
      case 1: return INFINITY;
      case 2: return -INFINITY;
      case 3: return 1e30f;
      case 4: return -1e30f;
      case 5: return -0.0f;
      case 6: return p.min - 1.0f;
      case 7: return p.max + 1.0f;
      default: break;
    }
  }
  float v = p.min + (p.max - p.min) * r.Unit();
  if (p.type == FM1_PARAM_ENUM && r.Next() % 2) v = static_cast<float>(static_cast<int>(v + 0.5f));
  if (r.Next() % 5 == 0) v = (r.Next() % 2) ? p.min : p.max;
  if (r.Next() % 7 == 0) v = p.def;
  return v;
}

Events RandomEvents(const fm1_engine_t &e, uint32_t frames, uint32_t every, uint32_t seed,
                    bool garbage) {
  Events ev;
  Rng r(seed);
  for (uint16_t i = 0; i < e.n_params; ++i) {
    if (r.Next() % 2) ev.push_back({ 0, i, RandomValue(e.params[i], r, garbage) });
  }
  for (uint32_t f = 1 + r.Next() % every; f < frames; f += 1 + r.Next() % every) {
    const uint16_t i = static_cast<uint16_t>(r.Next() % e.n_params);
    ev.push_back({ f, i, RandomValue(e.params[i], r, garbage) });
  }
  return ev;
}

struct Named { const char *name; float value; };

struct Spec {
  const fm1_engine_t *e;
  std::vector<std::vector<Named> > neutral;   // pass the input bit for bit
  std::vector<Named> busy;                    // far from neutral
  std::vector<std::vector<Named> > extremes;  // cycled through, one per frame
};

Events At(const fm1_engine_t &e, uint32_t frame, const std::vector<Named> &s) {
  Events ev;
  for (const Named &n : s) ev.push_back({ frame, static_cast<uint16_t>(Index(e, n.name)), n.value });
  return ev;
}

// Every parameter back to its default, then the setting.
Events Reset(const fm1_engine_t &e, uint32_t frame, const std::vector<Named> &s) {
  Events ev;
  for (uint16_t i = 0; i < e.n_params; ++i) ev.push_back({ frame, i, e.params[i].def });
  Events more = At(e, frame, s);
  ev.insert(ev.end(), more.begin(), more.end());
  return ev;
}

void Report(const Spec &s, bool first) {
  const fm1_engine_t &e = *s.e;
  printf("%s\"%s\":{", first ? "" : ",", e.id);

  // blocks and fills
  {
    int block_mismatch = 0, fill_mismatch = 0;
    float peak = 0.0f;
    const uint32_t n = 44118;
    const Buf in = Music(n, 0.8f, 11, kRate);
    for (int trial = 0; trial < 4; ++trial) {
      const Events ev = RandomEvents(e, n, trial < 2 ? 300 : 40, 100 + trial, trial == 3);
      const Buf ref = Run(e, kRate, 0, in, ev, 0);
      peak = fmaxf(peak, Peak(ref));
      for (int part = 1; part <= 4; ++part) block_mismatch += !SameBits(ref, Run(e, kRate, 0, in, ev, part));
      block_mismatch += !SameBits(ref, Run(e, kRate, 0, in, ev, 5, 4096));
      for (int fill = 1; fill < kFills; ++fill) fill_mismatch += !SameBits(ref, Run(e, kRate, fill, in, ev, 3));
    }
    printf("\"block_mismatch\":%d,\"fill_mismatch\":%d,\"random_peak\":%g,", block_mismatch,
           fill_mismatch, peak);
  }

  // chaos, then one setting: the output of an instance made with it
  {
    const uint32_t n = 3 * 44118, m = 3 * 44118;
    Buf in = Music(n + m, 1.0f, 31, kRate);
    Rng r(4);
    const float bad[] = { NAN, INFINITY, -INFINITY, 1e30f, -3e38f, 1e-41f };
    for (uint32_t i = 0; i < 2 * n; ++i) {
      const uint32_t k = r.Next() % 40;
      if (k < 6) in[i] = bad[k];
    }
    Events ev = RandomEvents(e, n, 20, 55, true);
    const Events then = Reset(e, n, s.busy);
    ev.insert(ev.end(), then.begin(), then.end());
    const Buf out = Run(e, kRate, 4, in, ev, 3, 64, 77);
    const Buf clean(in.begin() + 2 * n, in.end());
    const Buf ref = Run(e, kRate, 0, clean, At(e, 0, s.busy), 0);
    double diff = 0.0;
    for (uint32_t i = 2 * (m - 22059); i < 2 * m; ++i) {
      diff = fmax(diff, fabs(static_cast<double>(out[2 * n + i]) - ref[i]));
    }
    printf("\"chaos_peak\":%g,\"chaos_settled_diff\":%g,", Peak(out), diff);
  }

  // neutral settings
  {
    printf("\"neutral\":[");
    for (size_t k = 0; k < s.neutral.size(); ++k) {
      const uint32_t n = 44118, visit = 8823, back = 13235;
      const Buf in = AwkwardInput(n, 8 + static_cast<uint32_t>(k));
      const Events ev = At(e, 0, s.neutral[k]);
      int exact_fills = 0;
      for (int fill = 0; fill < kFills; ++fill) exact_fills += SameBits(in, Run(e, kRate, fill, in, ev, 3, 64, 40 + fill));
      Events ev2 = ev;
      const Events go = At(e, visit, s.busy), ret = Reset(e, back, s.neutral[k]);
      ev2.insert(ev2.end(), go.begin(), go.end());
      ev2.insert(ev2.end(), ret.begin(), ret.end());
      const Buf out = Run(e, kRate, 0, in, ev2, 2);
      size_t last = 0;
      for (size_t i = 0; i < in.size(); ++i) {
        if (memcmp(&in[i], &out[i], sizeof(float)) != 0) last = i;
      }
      const bool exact_before = memcmp(in.data(), out.data(), 2 * visit * sizeof(float)) == 0;
      printf("%s{\"exact_fills\":%d,\"exact_before_visit\":%s,\"changed_by_visit\":%s,"
             "\"exact_again_ms\":%.1f}", k ? "," : "", exact_fills, exact_before ? "true" : "false",
             last > 2 * visit ? "true" : "false",
             last / 2 < back ? 0.0 : (last / 2 + 1 - back) * 1000.0 / kRate);
    }
    printf("],");
  }

  // extremes, every frame
  {
    printf("\"extremes_peak\":[");
    const uint32_t n = 2 * 44118;
    const Buf in = Music(n, 1.0f, 3, kRate);
    for (size_t k = 0; k < s.extremes.size(); ++k) {
      const std::vector<Named> &set = s.extremes[k];
      Events ev;
      for (uint32_t f = 0; f < n; ++f) {
        const Named &a = set[f % set.size()];
        ev.push_back({ f, static_cast<uint16_t>(Index(e, a.name)), a.value });
      }
      printf("%s%g", k ? "," : "", Peak(Run(e, kRate, 0, in, ev, 1)));
    }
    printf("],");
  }

  // tail
  {
    const uint32_t loud = 44118, quiet = 30 * 44118;
    Buf in = Music(loud + quiet, 1.0f, 9, kRate);
    for (size_t i = 2 * loud; i < in.size(); ++i) in[i] = 0.0f;
    const Buf out = Run(e, kRate, 0, in, At(e, 0, s.busy), 0);
    size_t last = 0;
    bool subnormal = false;
    for (size_t i = 0; i < out.size(); ++i) {
      if (out[i] != 0.0f) last = i;
      if (out[i] != 0.0f && fabsf(out[i]) < FLT_MIN) subnormal = true;
    }
    printf("\"tail_s\":%.3f,\"subnormal_out\":%s,", (last / 2.0 - loud) / kRate,
           subnormal ? "true" : "false");
  }

  // rates
  {
    const float refused[] = { 0.0f, -44100.0f, 7999.0f, 384001.0f, NAN, INFINITY };
    int accepted_bad = 0;
    for (float rate : refused) {
      fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
      memset(g_mem, 0, sizeof(g_mem));
      accepted_bad += e.create(g_mem, &host) != NULL;
    }
    const float rates[] = { 8000.0f, 11025.0f, 22050.0f, 32000.0f, 48000.0f, 96000.0f,
                            192000.0f, 384000.0f };
    float peak = 0.0f;
    int neutral_exact = 0;
    for (float rate : rates) {
      const uint32_t n = static_cast<uint32_t>(rate);
      const Buf in = Music(n, 1.0f, 2, rate);
      for (int trial = 0; trial < 2; ++trial) {
        peak = fmaxf(peak, Peak(Run(e, rate, 0, in, RandomEvents(e, n, 200, 900 + trial, false), 3, 64, 7)));
      }
      neutral_exact += SameBits(in, Run(e, rate, 0, in, At(e, 0, s.neutral[0]), 3, 64, 7));
    }
    printf("\"bad_rates_accepted\":%d,\"rates_peak\":%g,\"rates_neutral_exact\":%d,", accepted_bad,
           peak, neutral_exact);
  }

  // glides
  {
    printf("\"glides\":[");
    const float rates[] = { 8000.0f, 44118.0f, 96000.0f, 384000.0f };
    for (int ri = 0; ri < 4; ++ri) {
      const float rate = rates[ri];
      const uint32_t n0 = static_cast<uint32_t>(0.1f * rate), n1 = static_cast<uint32_t>(1.6f * rate);
      const Buf in = Music(n0 + n1, 0.7f, 5, rate);
      const Buf later(in.begin() + 2 * n0, in.end());
      Rng r(17);
      double worst = 0.0;
      int worst_param = -1, not_identical = 0, routes = 0;
      for (uint16_t i = 0; i < e.n_params; ++i) {
        const fm1_param_t &p = e.params[i];
        for (int trial = 0; trial < 6; ++trial) {
          float a = p.min + (p.max - p.min) * r.Unit(), b = p.min + (p.max - p.min) * r.Unit();
          if (trial == 0) { a = p.min; b = p.max; }
          if (trial == 1) { a = p.max; b = p.min; }
          if (p.type == FM1_PARAM_ENUM) {
            a = static_cast<float>(static_cast<int>(a + 0.5f));
            b = static_cast<float>(static_cast<int>(b + 0.5f));
          }
          Events ev = At(e, 0, s.busy);
          ev.push_back({ 0, i, a });
          ev.push_back({ n0, i, b });
          const Buf out = Run(e, rate, 0, in, ev, 0);
          Events ev2 = At(e, 0, s.busy);
          ev2.push_back({ 0, i, b });
          const Buf ref = Run(e, rate, 0, later, ev2, 0);
          double diff = 0.0;
          for (uint32_t k = 2 * (n1 - n1 / 4); k < 2 * n1; ++k) {
            diff = fmax(diff, fabs(static_cast<double>(out[2 * n0 + k]) - ref[k]));
          }
          ++routes;
          not_identical += diff != 0.0;
          if (diff > worst) { worst = diff; worst_param = i; }
        }
      }
      printf("%s{\"rate\":%g,\"routes\":%d,\"not_identical\":%d,\"worst\":%g,\"worst_param\":\"%s\"}",
             ri ? "," : "", rate, routes, not_identical, worst,
             worst_param >= 0 ? e.params[worst_param].name : "");
    }
    printf("],");
  }

  // index past the table
  {
    const Buf in = Music(8000, 0.5f, 1, kRate);
    Events ev = At(e, 0, s.busy);
    const Buf ref = Run(e, kRate, 0, in, ev, 0);
    ev.push_back({ 100, e.n_params, 1.0f });
    ev.push_back({ 200, 65535, NAN });
    printf("\"bad_index_ignored\":%s", SameBits(ref, Run(e, kRate, 0, in, ev, 0)) ? "true" : "false");
  }
  printf("}");
}

}  // namespace

int main() {
  std::vector<Spec> specs;
  specs.push_back({ &fm1_engine_djfilter,
                    { {}, { { "Sweep", 0.05f }, { "Resonance", 1 }, { "Slope", 1 } },
                      { { "Sweep", -0.7f }, { "Mix", 0 } }, { { "Dead Zone", 0 }, { "Sweep", -0.0f } },
                      { { "Dead Zone", 0.2f }, { "Sweep", -0.2f }, { "Range", 0.1f } } },
                    { { "Sweep", -0.5f }, { "Resonance", 1 }, { "Slope", 1 }, { "Mix", 0.9f } },
                    { { { "Sweep", -1 }, { "Sweep", 1 }, { "Resonance", 1 } },
                      { { "Sweep", -0.5f }, { "Resonance", 1 }, { "Sweep", 0.5f }, { "Slope", 1 },
                        { "Slope", 0 }, { "Dead Zone", 0 } },
                      { { "Sweep", 0.55f }, { "Resonance", 1 }, { "Range", 0.1f }, { "Range", 1 },
                        { "Dead Zone", 0.2f }, { "Dead Zone", 0 }, { "Mix", 0 }, { "Mix", 1 } } } });
  specs.push_back({ &fm1_engine_tilt,
                    { {}, { { "Tilt", 0 }, { "Pivot", 200 }, { "Curve", 1 } },
                      { { "Tilt", -0.0f }, { "Pivot", 5000 }, { "Curve", 0.4f } } },
                    { { "Tilt", 9 }, { "Pivot", 300 }, { "Curve", 1 }, { "Level", 6 } },
                    { { { "Tilt", -9 }, { "Tilt", 9 } },
                      { { "Pivot", 200 }, { "Pivot", 5000 }, { "Tilt", 9 }, { "Curve", 1 }, { "Curve", 0 },
                        { "Tilt", -9 } },
                      { { "Level", 12 }, { "Tilt", 9 }, { "Curve", 0 }, { "Curve", 1 }, { "Pivot", 5000 },
                        { "Pivot", 200 } } } });
  specs.push_back({ &fm1_engine_eq,
                    { {}, { { "Low Freq", 20 }, { "Mid Freq", 18000 }, { "Mid Q", 10 }, { "High Freq", 1000 },
                            { "High Q", 0.3f } },
                      { { "Low Gain", -0.0f }, { "Mid Q", 0.3f }, { "Low Q", 2 } } },
                    { { "Low Gain", 12 }, { "Low Freq", 40 }, { "Low Q", 2 }, { "Mid Gain", -15 }, { "Mid Q", 10 },
                      { "High Gain", 15 }, { "High Q", 2 } },
                    { { { "Mid Gain", 15 }, { "Mid Q", 10 }, { "Mid Freq", 20 }, { "Mid Freq", 18000 } },
                      { { "Low Gain", 15 }, { "Low Q", 2 }, { "Low Freq", 20 }, { "Low Freq", 1000 },
                        { "High Gain", 15 }, { "High Q", 2 }, { "High Freq", 1000 }, { "High Freq", 18000 } },
                      { { "Mid Gain", -15 }, { "Mid Gain", 15 }, { "Mid Q", 0.3f }, { "Mid Q", 10 },
                        { "Level", 15 }, { "Level", -15 } } } });
  specs.push_back({ &fm1_engine_isolator,
                    { {}, { { "Low Xover", 80 }, { "High Xover", 5000 } },
                      { { "Kill", 0.4f }, { "Low Xover", 400 } } },
                    { { "Low", 1 }, { "Mid", 0.2f }, { "Kill", 4 }, { "Low Xover", 120 } },
                    { { { "Kill", 0 }, { "Kill", 7 }, { "Low", 1 }, { "Mid", 1 }, { "High", 1 } },
                      { { "Low Xover", 80 }, { "Low Xover", 400 }, { "High Xover", 1500 },
                        { "High Xover", 5000 }, { "Low", 1 }, { "High", 1 }, { "Mid", 1 } } } });
  specs.push_back({ &fm1_engine_sat,
                    { {}, { { "Drive", 18 }, { "Glue", 1 }, { "Asymmetry", 1 }, { "Shape", 1 } },
                      { { "Mix", 0 }, { "Level", 12 }, { "Clean Lo", 20 }, { "Clean Hi", 20000 } } },
                    { { "Mix", 1 }, { "Drive", 18 }, { "Glue", 1 }, { "Asymmetry", -0.7f }, { "Clean Lo", 20 },
                      { "Clean Hi", 20000 }, { "Shape", 1 } },
                    { { { "Mix", 1 }, { "Drive", 18 }, { "Drive", 0 }, { "Asymmetry", 1 }, { "Asymmetry", -1 },
                        { "Shape", 0 }, { "Shape", 1 } },
                      { { "Mix", 1 }, { "Clean Lo", 20 }, { "Clean Lo", 300 }, { "Clean Hi", 1000 },
                        { "Clean Hi", 20000 }, { "Level", 12 }, { "Glue", 1 }, { "Glue", 0 } } } });
  printf("{");
  for (size_t i = 0; i < specs.size(); ++i) Report(specs[i], i == 0);
  printf("}\n");
  return 0;
}
