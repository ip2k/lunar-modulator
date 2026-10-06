// idle_test.cc -- fm1-idle-test: the idle paths of EQ, Isolator and Master
// Sat (include/fm1_fx_idle.h) against the same three effects built without
// them (-DFM1_FX_IDLE=0, linked as fm1_engine_*_ref by mk/idle.mk): the code
// as it was. Through their engine structs only:
//
//   same      random settings away from pass-through, changed at random
//             frames for 6 s: the output is the reference's, bit for bit;
//   blocks    the same streams with rests at pass-through and wakes among
//             them, rendered in blocks of 64, 7, 1 and 4,096 frames and
//             from four memory fills: bit for bit the same;
//   neutral   10 s at the pass-through settings (idle from 2 s) on input
//             with -0, subnormals, FLT_MIN, values at and past the guard's
//             +/-16, NaN and infinities, with the other knobs turned while
//             idle: the guarded input bit for bit, as the reference gives;
//   wake      3 s at pass-through, then a knob that leaves it: until the
//             release the output is the input bit for bit; from then on it
//             is the reference's output with the same knob turned at the
//             release, within the residue printed (dB of the input's peak),
//             and bit for bit the same after the time printed. The same
//             move after 1 s of rest (before the effect idles) gives the
//             reference's output bit for bit, at once;
//   silence   the wake cases on silence: exact zeros throughout;
//   hostile   (review) a band retuned in its own warm-up, a band tuned from
//             idle where EQ never idles with its gain raised 0.12 s later,
//             DC and loud low sines, Glue after a burst that ends just
//             before the wake: the residue, and the output's largest second
//             difference against the reference's (a click would show
//             there); a lock shorter than the warm-up after a rest, which is
//             not heard; every knob re-sent every block at pass-through and
//             EQ's Mid Freq swept across the settings that never idle (the
//             input throughout); and rests and wakes at 8, 96 and 384 kHz;
//   driven    (2026-10-06) FM1_PARAM_DRIVEN, the host's word that a lock
//             lane or a cable reaches the effect: driven from the start,
//             the short locks after a long rest are heard, bit for bit as
//             the reference plays them, and pass-through is still the
//             guarded input; driven from inside a rest, the effect wakes at
//             once and a lock 0.5 s later is heard; undriven again, it
//             idles after its rest and loses a short lock as before; the
//             same bits at blocks of 64, 7 and 1;
//   bound     fm1_idle_svf_decay against the exact decay of the slowest
//             mode of a TPT state-variable section, over g and k;
//   --hash    for cross-build checks: each effect through rests, wakes and
//             busy settings on integer noise, every output float hashed
//             (FNV-1a over the bits): the same on every build without fused
//             multiply-adds, WebAssembly included;
//   --cost    nanoseconds per 64-frame stereo block of noise, at the
//             pass-through settings in the reference (what they cost
//             before) and idle, and at a busy setting in both.
//
// Prints one JSON object; tests/test_engines_idle.py reads it. MIT licence.

#include "fm1_engine.h"
#include "fm1_fx_idle.h"

#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <algorithm>
#include <chrono>
#include <vector>

extern "C" const fm1_engine_t fm1_engine_eq, fm1_engine_isolator, fm1_engine_sat;
extern "C" const fm1_engine_t fm1_engine_eq_ref, fm1_engine_isolator_ref, fm1_engine_sat_ref;

namespace {

const float kRate = 44118.0f;
const uint32_t kSecond = 44118;

struct Lcg {
  uint32_t s;
  uint32_t Next() { s = s * 1664525u + 1013904223u; return s; }
  float Bipolar() { return static_cast<int32_t>(Next()) / 2147483648.0f; }  // [-1, 1)
  float Unit() { return (Next() >> 8) / 16777216.0f; }                        // [0, 1)
};

typedef std::vector<float> Buf;

struct Ev {
  uint32_t at;
  const char *name;
  float value;
};
typedef std::vector<Ev> Events;

// A parameter's index, or "*driven" for the host's FM1_PARAM_DRIVEN.
int Index(const fm1_engine_t &e, const char *name) {
  if (strcmp(name, "*driven") == 0) return FM1_PARAM_DRIVEN;
  for (uint16_t i = 0; i < e.n_params; ++i) {
    if (strcmp(e.params[i].name, name) == 0) return i;
  }
  fprintf(stderr, "no parameter %s in %s\n", name, e.id);
  return 0;
}

// Renders `in` through a fresh instance, applying the events (sorted by
// frame) before the frame they name, in blocks of `block` frames split at
// the events.
Buf Run(const fm1_engine_t &e, const Buf &in, Events ev, uint32_t block, int fill = 0,
        float rate = kRate) {
  alignas(16) static unsigned char mem[4096];
  std::stable_sort(ev.begin(), ev.end(), [](const Ev &a, const Ev &b) { return a.at < b.at; });
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, block };
  if (e.instance_size(&host) > sizeof(mem)) return Buf();
  memset(mem, fill, sizeof(mem));
  void *self = e.create(mem, &host);
  const uint32_t n = static_cast<uint32_t>(in.size() / 2);
  Buf out(in);
  size_t k = 0;
  for (uint32_t pos = 0; pos < n;) {
    while (k < ev.size() && ev[k].at <= pos) {
      e.set_param(self, static_cast<uint16_t>(Index(e, ev[k].name)), ev[k].value);
      ++k;
    }
    uint32_t len = n - pos < block ? n - pos : block;
    if (k < ev.size() && ev[k].at - pos < len) len = ev[k].at - pos;
    e.render(self, out.data() + 2 * pos, len);
    pos += len;
  }
  e.destroy(self);
  return out;
}

// Bass-heavy tones (41-3,520 Hz), filtered and white noise; or a sine.
Buf Music(uint32_t frames, float amp, uint32_t seed, double sine_hz = 0.0) {
  Buf v(2 * frames);
  Lcg r = { seed };
  const double hz[6] = { 41.2, 55.0, 98.0, 233.1, 880.0, 3520.0 };
  const double a[6] = { 0.45, 0.3, 0.2, 0.12, 0.08, 0.04 };
  double ph[6] = { 0.0 };
  float lp = 0.0f;
  for (uint32_t i = 0; i < frames; ++i) {
    double s = 0.0;
    for (int k = 0; k < 6; ++k) {
      s += a[k] * sin(ph[k]);
      ph[k] += 2.0 * M_PI * hz[k] / kRate;
    }
    lp += 0.2f * (r.Bipolar() - lp);
    float x = static_cast<float>(s) + 0.1f * lp + 0.02f * r.Bipolar();
    if (sine_hz > 0.0) x = 0.6f * static_cast<float>(sin(2.0 * M_PI * sine_hz * i / kRate));
    v[2 * i] = amp * x;
    v[2 * i + 1] = amp * (0.8f * x + 0.05f * r.Bipolar());
  }
  return v;
}

float Guard(float x) {
  if (x > -16.0f && x < 16.0f) return x;
  if (x >= 16.0f) return 16.0f;
  if (x <= -16.0f) return -16.0f;
  return 0.0f;
}

uint32_t Bits(float x) {
  uint32_t u;
  memcpy(&u, &x, sizeof u);
  return u;
}

bool SameBits(const Buf &a, const Buf &b) {
  return a.size() == b.size() && memcmp(a.data(), b.data(), a.size() * sizeof(float)) == 0;
}

float Peak(const Buf &v) {
  float p = 0.0f;
  for (float x : v) p = fmaxf(p, fabsf(x));
  return p;
}

struct Fx {
  const char *id;
  const fm1_engine_t *idle, *ref;
  // The knobs whose settings make pass-through, and a busy setting.
  const char *keys[4];
  int n_keys;
  Events busy;
};

const Fx kFx[] = {
  { "eq", &fm1_engine_eq, &fm1_engine_eq_ref,
    { "Low Gain", "Mid Gain", "High Gain", "Level" }, 4,
    { { 0, "Low Gain", 6 }, { 0, "Mid Gain", -6 }, { 0, "High Gain", 6 } } },
  { "isolator", &fm1_engine_isolator, &fm1_engine_isolator_ref,
    { "Low", "Mid", "High" }, 3,
    { { 0, "Low", 0.6f }, { 0, "Kill", 4 } } },
  { "sat", &fm1_engine_sat, &fm1_engine_sat_ref,
    { "Mix" }, 1,
    { { 0, "Mix", 1 }, { 0, "Glue", 1 } } },
};
const int kFxCount = 3;

bool IsKey(const Fx &fx, const char *name) {
  for (int i = 0; i < fx.n_keys; ++i) {
    if (strcmp(fx.keys[i], name) == 0) return true;
  }
  return false;
}

// Random settings every 0.1-1.5 s. With `rests`, a quarter of the changes
// return every knob to its default (pass-through) for 3 s; without, the
// knobs that make pass-through never sit at it.
Events RandomEvents(const Fx &fx, uint32_t frames, uint32_t seed, bool rests) {
  const fm1_engine_t &e = *fx.idle;
  Lcg r = { seed * 7919u };
  Events ev;
  for (uint32_t at = 0; at < frames;) {
    const bool neutral = rests && r.Next() % 4 == 0;
    for (uint16_t p = 0; p < e.n_params; ++p) {
      const fm1_param_t &q = e.params[p];
      const bool key = IsKey(fx, q.name);
      float v;
      if (neutral) {
        v = q.def;
      } else if (r.Next() % 3 == 0 && !(key && !rests)) {
        v = q.def;
      } else {
        v = q.min + (q.max - q.min) * (0.01f + 0.98f * r.Unit());
        if (key && !rests && v == q.def) v = q.def + 0.01f * (q.max - q.min);
      }
      if (at == 0 || neutral || r.Next() % 2) ev.push_back({ at, q.name, v });
    }
    at += neutral ? 3 * kSecond : 4410 + r.Next() % 60000;
  }
  return ev;
}

// 1-2. Away from pass-through, the reference's bits; with rests and wakes,
// the same bits at any block size and from any memory fill.
void Same() {
  printf("\"same\":{");
  for (int i = 0; i < kFxCount; ++i) {
    const Fx &fx = kFx[i];
    int runs = 0, mismatch = 0, block_mismatch = 0, fill_mismatch = 0;
    for (uint32_t seed = 1; seed <= 12; ++seed) {
      const uint32_t n = 6 * kSecond;
      const Buf in = Music(n, 0.6f, seed);
      const Events busy = RandomEvents(fx, n, seed, false);
      mismatch += !SameBits(Run(*fx.ref, in, busy, 64), Run(*fx.idle, in, busy, 64));
      const Events rests = RandomEvents(fx, n, seed, true);
      const Buf ref = Run(*fx.idle, in, rests, 64);
      const uint32_t blocks[3] = { 7, 1, 4096 };
      for (uint32_t b : blocks) block_mismatch += !SameBits(ref, Run(*fx.idle, in, rests, b));
      const int fills[3] = { 0xA5, 0xFF, 0x7F };
      for (int f : fills) fill_mismatch += !SameBits(ref, Run(*fx.idle, in, rests, 13, f));
      ++runs;
    }
    printf("%s\"%s\":{\"runs\":%d,\"mismatch\":%d,\"block_mismatch\":%d,\"fill_mismatch\":%d}",
           i ? "," : "", fx.id, runs, mismatch, block_mismatch, fill_mismatch);
  }
  printf("}");
}

// 3. Pass-through, idle, on awkward input, with the other knobs turned
// while idle: the guarded input, bit for bit, and the reference's output.
void Neutral() {
  printf("\"neutral\":{");
  const uint32_t n = 10 * kSecond;
  Buf in = Music(n, 0.9f, 3);
  Lcg r = { 17u };
  for (uint32_t i = 0; i < 2 * n; i += 7) {
    switch (r.Next() % 9) {
      case 0: in[i] = -0.0f; break;
      case 1: in[i] = 1e-40f * r.Bipolar(); break;            // subnormal
      case 2: in[i] = FLT_MIN; break;
      case 3: in[i] = 16.0f; break;
      case 4: in[i] = -15.999999f; break;
      case 5: in[i] = 1e30f; break;
      case 6: in[i] = NAN; break;
      case 7: in[i] = (r.Next() & 1) ? INFINITY : -INFINITY; break;
      default: break;
    }
  }
  Buf guarded(in);
  for (float &x : guarded) x = Guard(x);
  for (int i = 0; i < kFxCount; ++i) {
    const Fx &fx = kFx[i];
    // Every knob but the pass-through ones turned at 4 s and 7 s (idle).
    Events ev;
    for (uint16_t p = 0; p < fx.idle->n_params; ++p) {
      const fm1_param_t &q = fx.idle->params[p];
      if (IsKey(fx, q.name) || strcmp(q.name, "Kill") == 0) continue;
      ev.push_back({ 4 * kSecond, q.name, q.min });
      ev.push_back({ 7 * kSecond + 3, q.name, q.max });
    }
    const Buf out = Run(*fx.idle, in, ev, 64);
    uint32_t last = 0;
    for (uint32_t k = 0; k < 2 * n; ++k) {
      if (Bits(out[k]) != Bits(guarded[k])) last = k / 2 + 1;
    }
    printf("%s\"%s\":{\"exact\":%s,\"last_inexact\":%u,\"same_as_ref\":%s}", i ? "," : "", fx.id,
           last == 0 ? "true" : "false", last,
           SameBits(out, Run(*fx.ref, in, ev, 64)) ? "true" : "false");
  }
  printf("}");
}

// 4-5. Wakes.
struct WakeCase {
  const char *fx;
  const char *label;
  Events base;    // at frame 0
  Events moves;   // at the wake
  double sine_hz;
};

const Fx &FxOf(const char *id) {
  for (int i = 0; i < kFxCount; ++i) {
    if (strcmp(kFx[i].id, id) == 0) return kFx[i];
  }
  return kFx[0];
}

// The first frame from `from` on where the output is not the guarded input.
uint32_t Release(const Buf &in, const Buf &out, uint32_t from) {
  for (uint32_t k = 2 * from; k < out.size(); ++k) {
    if (Bits(out[k]) != Bits(Guard(in[k]))) return k / 2;
  }
  return static_cast<uint32_t>(out.size() / 2);
}

void Wake() {
  const WakeCase cases[] = {
    { "eq", "low_shelf_up", {}, { { 0, "Low Gain", 15 } }, 0 },
    { "eq", "low_shelf_down", {}, { { 0, "Low Gain", -15 } }, 0 },
    { "eq", "low_shelf_35", { { 0, "Low Freq", 35 } }, { { 0, "Low Gain", 15 } }, 0 },
    { "eq", "bell", {}, { { 0, "Mid Gain", 15 } }, 0 },
    { "eq", "bell_200_q4", { { 0, "Mid Freq", 200 }, { 0, "Mid Q", 4 } }, { { 0, "Mid Gain", 15 } }, 0 },
    { "eq", "bell_500_q10_on_500", { { 0, "Mid Freq", 500 }, { 0, "Mid Q", 10 } },
      { { 0, "Mid Gain", 15 } }, 500.0 },
    { "eq", "high_1k_q2", { { 0, "High Freq", 1000 }, { 0, "High Q", 2 } },
      { { 0, "High Gain", -15 } }, 0 },
    { "eq", "high_18k_q03", { { 0, "High Freq", 18000 }, { 0, "High Q", 0.3f } },
      { { 0, "High Gain", 15 } }, 0 },
    { "eq", "three_bands", {},
      { { 0, "Low Gain", 15 }, { 0, "Mid Gain", -15 }, { 0, "High Gain", 15 } }, 0 },
    { "eq", "level", {}, { { 0, "Level", 9 } }, 0 },
    { "eq", "never_idles_300_q10", { { 0, "Mid Freq", 300 }, { 0, "Mid Q", 10 } },
      { { 0, "Mid Gain", -15 } }, 0 },
    { "isolator", "kill_low", {}, { { 0, "Kill", 1 } }, 0 },
    { "isolator", "kill_all", {}, { { 0, "Kill", 7 } }, 0 },
    { "isolator", "high_up", {}, { { 0, "High", 1 } }, 0 },
    { "isolator", "kill_low_80", { { 0, "Low Xover", 80 } }, { { 0, "Kill", 1 } }, 0 },
    { "isolator", "low_up_80", { { 0, "Low Xover", 80 } }, { { 0, "Low", 1 } }, 0 },
    { "isolator", "kill_high_400_5k", { { 0, "Low Xover", 400 }, { 0, "High Xover", 5000 } },
      { { 0, "Kill", 4 } }, 0 },
    { "sat", "mix_glue_0", { { 0, "Glue", 0 } }, { { 0, "Mix", 1 } }, 0 },
    { "sat", "mix_defaults", {}, { { 0, "Mix", 1 } }, 0 },
    { "sat", "mix_hot_glue_0", { { 0, "Glue", 0 }, { 0, "Drive", 18 }, { 0, "Asymmetry", 1 } },
      { { 0, "Mix", 1 } }, 0 },
    { "sat", "mix_hot_glue_1", { { 0, "Glue", 1 }, { 0, "Drive", 18 }, { 0, "Asymmetry", 1 } },
      { { 0, "Mix", 1 } }, 0 },
    { "sat", "mix_open", { { 0, "Glue", 0 }, { 0, "Drive", 18 }, { 0, "Clean Lo", 20 },
      { 0, "Clean Hi", 20000 } }, { { 0, "Mix", 1 } }, 0 },
  };
  const uint32_t wake = 3 * kSecond, n = 5 * kSecond;
  printf("\"wake\":{");
  int silence_peak_nonzero = 0, block_mismatch = 0;
  for (size_t c = 0; c < sizeof(cases) / sizeof(cases[0]); ++c) {
    const WakeCase &wc = cases[c];
    const Fx &fx = FxOf(wc.fx);
    const Buf in = Music(n, 0.8f, 7, wc.sine_hz);
    // Each knob's own release, found alone; the reference turns each there.
    Events ref_ev = wc.base;
    uint32_t first = n;
    for (const Ev &m : wc.moves) {
      Events one = wc.base;
      one.push_back({ wake, m.name, m.value });
      const uint32_t at = Release(in, Run(*fx.idle, in, one, 64), wake);
      if (at < first) first = at;
      ref_ev.push_back({ at, m.name, m.value });
    }
    Events ev = wc.base;
    for (const Ev &m : wc.moves) ev.push_back({ wake, m.name, m.value });
    const Buf out = Run(*fx.idle, in, ev, 64);
    const Buf ref = Run(*fx.ref, in, ref_ev, 64);
    const float peak = Peak(in);
    float resid = 0.0f;
    uint32_t last = 0;
    bool exact_before = true;
    for (uint32_t k = 0; k < 2 * n; ++k) {
      if (k < 2 * first && Bits(out[k]) != Bits(Guard(in[k]))) exact_before = false;
      if (Bits(out[k]) != Bits(ref[k])) last = k / 2 + 1;
      if (k >= 2 * first) resid = fmaxf(resid, fabsf(out[k] - ref[k]));
    }
    // The same move after 1 s of rest: the reference's bits.
    Events early = wc.base;
    for (const Ev &m : wc.moves) early.push_back({ kSecond, m.name, m.value });
    const bool early_same = SameBits(Run(*fx.idle, in, early, 64), Run(*fx.ref, in, early, 64));
    // Any block size, any fill; and on silence, silence.
    if (!SameBits(out, Run(*fx.idle, in, ev, 7, 0xFF)) || !SameBits(out, Run(*fx.idle, in, ev, 1)))
      ++block_mismatch;
    const Buf zeros(2 * n, 0.0f);
    if (Peak(Run(*fx.idle, zeros, ev, 64)) != 0.0f) ++silence_peak_nonzero;
    printf("%s\"%s/%s\":{\"warm_ms\":%.2f,\"exact_before\":%s,\"resid_db\":%.1f,"
           "\"same_after_s\":%.3f,\"early_same\":%s}",
           c ? "," : "", wc.fx, wc.label, (first - wake) * 1000.0 / kRate,
           exact_before ? "true" : "false",
           resid > 0.0f ? 20.0 * log10(resid / peak) : -999.0,
           last > first ? (last - first) / kRate : 0.0, early_same ? "true" : "false");
  }
  printf("},\"wake_blocks_mismatch\":%d,\"wake_silence_nonzero\":%d", block_mismatch,
         silence_peak_nonzero);
}

// 7. Hostile wakes (review, 2026-10-06). Each case's events are applied as
// given to the idle build; the reference applies the `held` ones at the
// release found in the idle build's output (as Wake() does) and the others
// where they are. Printed: the release (ms after `wake`), the residue (dB of
// the input's peak) and the largest second difference of the output from
// 10 ms before the release to 200 ms after it, against the reference's: a
// click or a jump would show there, a different transient would not.
const uint32_t kAtStart = 0xFFFFFFFFu;   // at frame 0, before the rest

struct HEv {
  uint32_t at;          // frames after `wake`, or kAtStart
  const char *name;
  float value;
  bool held;
};

struct HCase {
  const char *fx;
  const char *label;
  int signal;           // 0 music, 1 sine, 2 DC 0.9 + a quiet 1 kHz, 3 burst
  double hz;
  std::vector<HEv> ev;
};

Buf Signal(int kind, uint32_t frames, uint32_t wake, double hz) {
  if (kind == 0) return Music(frames, 0.8f, 7);
  Buf v(2 * frames);
  for (uint32_t i = 0; i < frames; ++i) {
    float x;
    if (kind == 1) {
      x = 0.95f * static_cast<float>(sin(2.0 * M_PI * hz * i / kRate));
    } else if (kind == 2) {
      x = 0.9f + 0.05f * static_cast<float>(sin(2.0 * M_PI * 1000.0 * i / kRate));
    } else {
      // A loud 220 Hz burst for the 0.5 s before the wake, ending 5 ms
      // before it, then the same tone at 0.05.
      const bool loud = i + kSecond / 2 > wake && i + kSecond / 200 < wake;
      x = (loud ? 0.9f : 0.05f) * static_cast<float>(sin(2.0 * M_PI * 220.0 * i / kRate));
    }
    v[2 * i] = x;
    v[2 * i + 1] = -x;
  }
  return v;
}

float MaxBend(const Buf &v, uint32_t from, uint32_t to) {
  float m = 0.0f;
  for (uint32_t k = 2 * from + 4; k < 2 * to && k < v.size(); ++k) {
    m = fmaxf(m, fabsf(v[k] - 2.0f * v[k - 2] + v[k - 4]));
  }
  return m;
}

void Hostile() {
  const uint32_t ms64 = 64, s012 = kSecond * 12 / 100;
  const HCase cases[] = {
    // A band retuned lower and narrower 64 frames into its own warm-up.
    { "eq", "retune_400_q10_in_warm_up", 1, 400.0,
      { { 0, "Mid Gain", 15, true }, { ms64, "Mid Freq", 400, false }, { ms64, "Mid Q", 10, false } } },
    { "eq", "retune_100_q10_in_warm_up", 1, 100.0,
      { { 0, "Mid Gain", 15, true }, { ms64, "Mid Freq", 100, false }, { ms64, "Mid Q", 10, false } } },
    // Tuned from idle where EQ never idles: it wakes, warms for at most
    // 0.1 s, and the gain raised 0.12 s later answers at once.
    { "eq", "never_idles_bell_30_q10_gain_after", 1, 30.0,
      { { 0, "Mid Freq", 30, false }, { 0, "Mid Q", 10, false }, { s012, "Mid Gain", 15, true } } },
    { "eq", "never_idles_low_20_q03_gain_after_dc", 2, 0.0,
      { { 0, "Low Freq", 20, false }, { 0, "Low Q", 0.3f, false }, { s012, "Low Gain", 15, true } } },
    // DC and a loud sine at the slowest settings that still idle, set
    // before the rest.
    { "eq", "low_shelf_dc", 2, 0.0, { { 0, "Low Gain", 15, true } } },
    { "eq", "low_shelf_35_dc", 2, 0.0,
      { { kAtStart, "Low Freq", 35, false }, { 0, "Low Gain", 15, true } } },
    { "eq", "bell_400_q10_on_400", 1, 400.0,
      { { kAtStart, "Mid Freq", 400, false }, { kAtStart, "Mid Q", 10, false },
        { 0, "Mid Gain", 15, true } } },
    { "isolator", "kill_high_80_dc", 2, 0.0,
      { { kAtStart, "Low Xover", 80, false }, { 0, "Kill", 4, true } } },
    { "isolator", "low_up_80_on_80", 1, 80.0,
      { { kAtStart, "Low Xover", 80, false }, { 0, "Low", 1, true } } },
    { "sat", "asym_drive_dc", 2, 0.0,
      { { kAtStart, "Asymmetry", 1, false }, { kAtStart, "Drive", 18, false },
        { kAtStart, "Glue", 0, false }, { 0, "Mix", 1, true } } },
    // Glue's envelope after a loud burst that ends 5 ms before the wake: the
    // old build's would still be releasing (200 ms), the idle one's starts
    // from rest.
    { "sat", "glue_after_burst", 3, 0.0,
      { { kAtStart, "Glue", 1, false }, { kAtStart, "Drive", 18, false }, { 0, "Mix", 1, true } } },
  };
  const uint32_t wake = 3 * kSecond, n = 5 * kSecond;
  printf("\"hostile\":{");
  for (size_t c = 0; c < sizeof(cases) / sizeof(cases[0]); ++c) {
    const HCase &hc = cases[c];
    const Fx &fx = FxOf(hc.fx);
    const Buf in = Signal(hc.signal, n, wake, hc.hz);
    Events ev;
    for (const HEv &h : hc.ev) ev.push_back({ h.at == kAtStart ? 0 : wake + h.at, h.name, h.value });
    const Buf out = Run(*fx.idle, in, ev, 64);
    const uint32_t release = Release(in, out, wake);
    Events ref_ev;
    for (const HEv &h : hc.ev) {
      ref_ev.push_back({ h.held ? release : (h.at == kAtStart ? 0 : wake + h.at), h.name, h.value });
    }
    const Buf ref = Run(*fx.ref, in, ref_ev, 64);
    float resid = 0.0f;
    for (uint32_t k = 2 * release; k < 2 * n; ++k) resid = fmaxf(resid, fabsf(out[k] - ref[k]));
    const uint32_t from = release - kSecond / 100, to = release + kSecond / 5;
    const float bend = MaxBend(out, from, to), bend_ref = MaxBend(ref, from, to);
    printf("%s\"%s/%s\":{\"release_ms\":%.2f,\"resid_db\":%.1f,\"bend_ratio\":%.6f}", c ? "," : "",
           hc.fx, hc.label, (release - wake) * 1000.0 / kRate,
           resid > 0.0f ? 20.0 * log10(resid / Peak(in)) : -999.0,
           bend_ref > 0.0f ? bend / bend_ref : (bend > 0.0f ? 1e9 : 1.0));
  }
  printf("}");

  // A lock that leaves pass-through after a rest and comes back within the
  // warm-up is not heard at all (the trade-off of a clean wake): Master Sat's
  // Mix for 0.1 s, Isolator's Kill for 5 ms. The same lock 1 s into the rest
  // is heard, as before.
  struct Lock { const char *fx, *label, *name; float value; uint32_t len; };
  const Lock locks[] = {
    { "sat", "mix_100ms", "Mix", 1.0f, kSecond / 10 },
    { "isolator", "kill_low_5ms", "Kill", 1.0f, kSecond / 200 },
    { "eq", "low_gain_20ms", "Low Gain", 12.0f, kSecond / 50 },
  };
  printf(",\"short_lock\":{");
  for (size_t c = 0; c < sizeof(locks) / sizeof(locks[0]); ++c) {
    const Lock &l = locks[c];
    const Fx &fx = FxOf(l.fx);
    const Buf in = Music(n, 0.8f, 11);
    const float def = fx.idle->params[Index(*fx.idle, l.name)].def;
    const Events late = { { wake, l.name, l.value }, { wake + l.len, l.name, def } };
    const Events early = { { kSecond, l.name, l.value }, { kSecond + l.len, l.name, def } };
    Buf guarded(in);
    for (float &x : guarded) x = Guard(x);
    const Buf out_late = Run(*fx.idle, in, late, 64), ref_late = Run(*fx.ref, in, late, 64);
    printf("%s\"%s/%s\":{\"lost_after_rest\":%s,\"heard_by_ref\":%s,\"early_same\":%s}",
           c ? "," : "", l.fx, l.label, SameBits(out_late, guarded) ? "true" : "false",
           SameBits(ref_late, guarded) ? "false" : "true",
           SameBits(Run(*fx.idle, in, early, 64), Run(*fx.ref, in, early, 64)) ? "true" : "false");
  }
  printf("}");

  // Driven (FM1_PARAM_DRIVEN, owner's decision 2026-10-06): an effect a lock
  // lane or a cable reaches never idles, so the same locks are heard, as the
  // reference (which never idles) plays them, bit for bit.
  printf(",\"driven\":{");
  for (size_t c = 0; c < sizeof(locks) / sizeof(locks[0]); ++c) {
    const Lock &l = locks[c];
    const Fx &fx = FxOf(l.fx);
    const Buf in = Music(n, 0.8f, 11);
    const float def = fx.idle->params[Index(*fx.idle, l.name)].def;
    const Events plain = { { wake, l.name, l.value }, { wake + l.len, l.name, def } };
    Events from_start(plain), from_rest(plain), undriven(plain), only = { { 0, "*driven", 1.0f } };
    from_start.push_back({ 0, "*driven", 1.0f });
    from_rest.push_back({ wake - kSecond / 2, "*driven", 1.0f });       // idle since 2 s
    undriven.push_back({ 0, "*driven", 1.0f });
    undriven.push_back({ kSecond / 2, "*driven", 0.0f });               // idle again from 2.5 s
    Buf guarded(in);
    for (float &x : guarded) x = Guard(x);
    const Buf ref = Run(*fx.ref, in, plain, 64);
    const Buf start = Run(*fx.idle, in, from_start, 64);
    const int blocks = !SameBits(start, Run(*fx.idle, in, from_start, 7)) +
                       !SameBits(start, Run(*fx.idle, in, from_start, 1, 0xA5));
    printf("%s\"%s/%s\":{\"heard_as_ref\":%s,\"pass_input\":%s,\"woken_heard\":%s,"
           "\"undriven_lost\":%s,\"block_mismatch\":%d}", c ? "," : "", l.fx, l.label,
           SameBits(start, ref) ? "true" : "false",
           SameBits(Run(*fx.idle, in, only, 64), guarded) ? "true" : "false",
           SameBits(Run(*fx.idle, in, from_rest, 64), guarded) ? "false" : "true",
           SameBits(Run(*fx.idle, in, undriven, 64), guarded) ? "true" : "false", blocks);
  }
  printf("}");

  // At pass-through with every knob sent again every block (a host that
  // re-sends values), and with EQ's Mid Freq swept at Q 10 across the
  // settings where it never idles (it wakes and idles again): the guarded
  // input, bit for bit, throughout.
  printf(",\"resend\":{");
  for (int i = 0; i < kFxCount; ++i) {
    const Fx &fx = kFx[i];
    const uint32_t m = 6 * kSecond;
    const Buf in = Music(m, 0.8f, 13);
    Events ev;
    for (uint32_t at = 0; at < m; at += 64) {
      for (uint16_t p = 0; p < fx.idle->n_params; ++p) {
        ev.push_back({ at, fx.idle->params[p].name, fx.idle->params[p].def });
      }
    }
    if (strcmp(fx.id, "eq") == 0) {
      ev.push_back({ 0, "Mid Q", 10 });
      for (uint32_t at = 0; at < m; at += 64) {
        const float sweep = static_cast<float>(at % (2 * kSecond)) / (2 * kSecond);  // 0..1
        ev.push_back({ at, "Mid Freq", 200.0f + 400.0f * (sweep < 0.5f ? sweep : 1.0f - sweep) });
      }
    }
    Buf guarded(in);
    for (float &x : guarded) x = Guard(x);
    printf("%s\"%s\":%s", i ? "," : "", fx.id, SameBits(Run(*fx.idle, in, ev, 64), guarded) ? "true" : "false");
  }
  printf("}");

  // Other host rates: a rest, then a wake, at blocks of 64, 1, 7 and 4,096
  // frames and from other fills (the same bits), silence (exact zeros), and
  // the release.
  printf(",\"rates\":{");
  const float rates[3] = { 8000.0f, 96000.0f, 384000.0f };
  int first = 1;
  for (float fs : rates) {
    const uint32_t s = static_cast<uint32_t>(fs), m = 3 * s, at = 2 * s + s / 2;
    const Buf in = Music(m, 0.7f, 5);
    for (int i = 0; i < kFxCount; ++i) {
      const Fx &fx = kFx[i];
      Events ev;
      for (const Ev &b : fx.busy) ev.push_back({ at, b.name, b.value });
      const Buf out = Run(*fx.idle, in, ev, 64, 0, fs);
      const int blocks = !SameBits(out, Run(*fx.idle, in, ev, 1, 0, fs)) +
                         !SameBits(out, Run(*fx.idle, in, ev, 7, 0xFF, fs)) +
                         !SameBits(out, Run(*fx.idle, in, ev, 4096, 0x7F, fs));
      int nonfinite = 0;
      for (float x : out) nonfinite += !(x == x && x - x == 0.0f);
      const Buf zeros(2 * m, 0.0f);
      printf("%s\"%s@%.0f\":{\"block_mismatch\":%d,\"silence_peak\":%g,\"nonfinite\":%d,"
             "\"release_ms\":%.2f}", first ? "" : ",", fx.id, fs, blocks,
             Peak(Run(*fx.idle, zeros, ev, 64, 0, fs)), nonfinite,
             (Release(in, out, at) - at) * 1000.0 / fs);
      first = 0;
    }
  }
  printf("}");
}

// 6. fm1_idle_svf_decay is a lower bound on the slowest mode's decay, from
// the poles of the bilinear transform in double precision.
double ExactDecay(double g, double k) {
  if (k < 2.0) return atanh(g * k / (1.0 + g * g));
  const double root = sqrt(k * k / 4.0 - 1.0);
  const double s[2] = { k / 2.0 - root, k / 2.0 + root };   // |s| of the two real poles
  double d = 1e300;
  for (double m : s) {
    const double z = (1.0 - g * m) / (1.0 + g * m);
    d = fmin(d, -log(fabs(z)));
  }
  return d;
}

void Bound() {
  double worst = 0.0, loosest = 1e300;
  int points = 0, over = 0;
  for (int gi = 0; gi <= 400; ++gi) {
    const double g = pow(10.0, -4.0 + 5.0 * gi / 400.0);       // 1e-4 .. 10
    for (int ki = 0; ki <= 200; ++ki) {
      const double k = 0.05 + (4.0 - 0.05) * ki / 200.0;
      const double exact = ExactDecay(g, k);
      const double bound = fm1_idle_svf_decay(static_cast<float>(g), static_cast<float>(k));
      const double ratio = bound / exact;
      if (ratio > 1.0 + 1e-6) ++over;
      worst = fmax(worst, ratio);
      loosest = fmin(loosest, ratio);
      ++points;
    }
  }
  printf("\"bound\":{\"points\":%d,\"over\":%d,\"max_ratio\":%.6f,\"min_ratio\":%.6f}", points,
         over, worst, loosest);
}

// --hash: no libm anywhere in the input or the events, so every build that
// keeps to IEEE single precision must print the same hashes.
void Hash() {
  printf("{");
  for (int i = 0; i < kFxCount; ++i) {
    const Fx &fx = kFx[i];
    const uint32_t n = 12 * kSecond;
    Buf in(2 * n);
    uint32_t noise = 1u + i;
    float lp = 0.0f;
    for (uint32_t k = 0; k < n; ++k) {
      noise = noise * 1664525u + 1013904223u;
      lp = lp + 0.05f * (static_cast<int32_t>(noise) / 2147483648.0f - lp);
      in[2 * k] = 2.0f * lp;
      in[2 * k + 1] = -1.5f * lp;
    }
    // 3 s at pass-through, a wake to the busy setting, back at 5 s, idle
    // again from 7 s, a wake to the busy setting at 9 s.
    Events ev;
    for (const Ev &b : fx.busy) {
      ev.push_back({ 3 * kSecond, b.name, b.value });
      ev.push_back({ 9 * kSecond + 5, b.name, b.value });
    }
    for (uint16_t p = 0; p < fx.idle->n_params; ++p) {
      ev.push_back({ 5 * kSecond, fx.idle->params[p].name, fx.idle->params[p].def });
    }
    const Buf out = Run(*fx.idle, in, ev, 64);
    uint32_t h = 2166136261u;
    for (float x : out) h = (h ^ Bits(x)) * 16777619u;
    printf("%s\"%s\":\"%08x\"", i ? "," : "", fx.id, h);
  }
  printf("}\n");
}

// --cost: ns per 64-frame stereo block of noise, the best of five runs of
// 20 s, after 3 s at the setting (so an idle path has gone idle).
double Cost(const fm1_engine_t &e, const Events &ev) {
  alignas(16) static unsigned char mem[4096];
  static float noise[128 * 64];
  Lcg rng = { 9u };
  for (int k = 0; k < 128 * 64; ++k) noise[k] = 0.5f * rng.Bipolar();
  double best = 1e30;
  for (int run = 0; run < 5; ++run) {
    fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
    memset(mem, 0, sizeof(mem));
    void *self = e.create(mem, &host);
    for (const Ev &x : ev) e.set_param(self, static_cast<uint16_t>(Index(e, x.name)), x.value);
    float buf[128];
    for (int b = 0; b < 2068; ++b) {                       // 3 s
      memcpy(buf, noise + 128 * (b & 63), sizeof(buf));
      e.render(self, buf, 64);
    }
    volatile float sink = 0.0f;
    const int blocks = 13786;                              // 20 s
    const auto t0 = std::chrono::steady_clock::now();
    for (int b = 0; b < blocks; ++b) {
      memcpy(buf, noise + 128 * (b & 63), sizeof(buf));
      e.render(self, buf, 64);
      sink = sink + buf[0];
    }
    const auto t1 = std::chrono::steady_clock::now();
    e.destroy(self);
    best = fmin(best, std::chrono::duration<double, std::nano>(t1 - t0).count() / blocks);
  }
  return best;
}

void Costs() {
  printf("{");
  for (int i = 0; i < kFxCount; ++i) {
    const Fx &fx = kFx[i];
    printf("%s\"%s\":{\"pass_through_before_ns\":%.1f,\"idle_ns\":%.1f,\"busy_before_ns\":%.1f,"
           "\"busy_ns\":%.1f}",
           i ? "," : "", fx.id, Cost(*fx.ref, Events()), Cost(*fx.idle, Events()),
           Cost(*fx.ref, fx.busy), Cost(*fx.idle, fx.busy));
  }
  printf("}\n");
}

}  // namespace

int main(int argc, char **argv) {
  if (argc > 1 && strcmp(argv[1], "--cost") == 0) {
    Costs();
    return 0;
  }
  if (argc > 1 && strcmp(argv[1], "--hash") == 0) {
    Hash();
    return 0;
  }
  printf("{");
  Same(); printf(",");
  Neutral(); printf(",");
  Wake(); printf(",");
  Hostile(); printf(",");
  Bound();
  printf("}\n");
  return 0;
}
