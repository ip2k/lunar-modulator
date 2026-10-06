// gate_test.cc -- fm1-gate-test: drives the Gate effect (src/fx_gate.cc)
// through its engine struct and its hooks (include/fm1_gate.h) where
// fm1-render cannot: the gate's timing read frame by frame from its state,
// Range, Return's hysteresis, Duck, Lockout, the look-ahead's latency, the
// key filters' responses through Listen, a key other than the input,
// chattering on noisy keys, bad keys, parameters that change while audio
// runs at block sizes that change between calls, host rates, its tan
// against libm (through the probe build, engines/mk/gate.mk), the output's
// bits, and (with --cost) its cost. Prints one JSON object;
// tests/test_engines_gate.py reads it. MIT licence.

#include "fm1_engine.h"
#include "fm1_gate.h"

#include <chrono>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_gate;
extern "C" float fm1_gate_probe_tan(float x);   // the probe build's GateTan

namespace {

const fm1_engine_t &E = fm1_engine_gate;
const float kRate = 44118.0f;
alignas(16) unsigned char g_mem[16384];

struct Lcg {
  uint32_t s;
  uint32_t Next() { s = s * 1664525u + 1013904223u; return s; }
  float Bipolar() { return static_cast<int32_t>(Next()) / 2147483648.0f; }  // [-1, 1)
  float Unit() { return (Next() >> 8) / 16777216.0f; }                        // [0, 1)
};

struct Kv { const char *name; float value; };

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
  return -1;
}

void Set(void *self, const char *name, float v) {
  E.set_param(self, static_cast<uint16_t>(Index(name)), v);
}

void SetAll(void *self, const Kv *kv, int n) {
  for (int i = 0; i < n; ++i) Set(self, kv[i].name, kv[i].value);
}

// One frame: audio on both channels, the key on both channels.
float Frame(void *self, float audio, float key, fm1_gate_state_t *st) {
  float io[2] = { audio, audio };
  const float k[2] = { key, key };
  fm1_gate_render_key(self, io, k, 1);
  if (st) fm1_gate_state(self, st);
  return io[0];
}

double Db(double x) { return 20.0 * log10(x); }

// 1. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while bursts of noise play (so the gate opens and closes), for 20 s;
// a quarter of the blocks keyed from a separate noise. The output must stay
// finite and bounded.
float g_key[128];
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
    const float level = ((samples / 4410) % 3 == 0) ? 0.002f : 0.5f;   // bursts
    for (uint32_t i = 0; i < n; ++i) {
      buf[2 * i] = level * rng.Bipolar();
      buf[2 * i + 1] = level * rng.Bipolar();
      g_key[2 * i] = 0.5f * rng.Bipolar();
      g_key[2 * i + 1] = 0.5f * rng.Bipolar();
    }
    if (rng.Next() % 4 == 0) fm1_gate_render_key(self, buf, g_key, n);
    else E.render(self, buf, n);
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

// Noise in bursts on both channels (different noise left and right), with
// parameter changes at given samples; renders in blocks of `block`, split at
// the changes, through render or render_key(NULL) or render_key with a copy
// of the input as the key.
struct Change { uint32_t at; const char *name; float value; };

const uint32_t kTotal = 2 * 44118;
float g_a[2 * kTotal], g_b[2 * kTotal], g_c[2 * kTotal], g_d[2 * kTotal], g_e[2 * kTotal];

void Source(float *out, uint32_t total, uint32_t seed) {
  Lcg rng = { seed };
  for (uint32_t i = 0; i < total; ++i) {
    const float level = ((i / 6000) % 3 == 2) ? 0.003f : 0.5f;
    out[2 * i] = level * rng.Bipolar();
    out[2 * i + 1] = level * rng.Bipolar();
  }
}

enum { VIA_RENDER, VIA_KEY_NULL, VIA_KEY_COPY };

void RenderChanges(uint32_t block, const Change *changes, int n_changes, float *io, int via) {
  void *self = Make(kRate, 0);
  float key[128];
  int next = 0;
  for (uint32_t pos = 0; pos < kTotal;) {
    while (next < n_changes && changes[next].at <= pos) {
      Set(self, changes[next].name, changes[next].value);
      ++next;
    }
    uint32_t n = kTotal - pos < block ? kTotal - pos : block;
    if (next < n_changes && changes[next].at - pos < n) n = changes[next].at - pos;
    float *p = io + 2 * pos;
    if (via == VIA_RENDER) {
      E.render(self, p, n);
    } else if (via == VIA_KEY_NULL) {
      fm1_gate_render_key(self, p, NULL, n);
    } else {
      memcpy(key, p, 2 * n * sizeof(float));
      fm1_gate_render_key(self, p, key, n);
    }
    pos += n;
  }
  E.destroy(self);
}

// 2. Changes mid-stream give the same output whatever the block size (64, 7
// and 1 frames, split at the changes), and render, render_key(NULL) and
// render_key(a copy of the input) agree bit for bit.
void Blocks() {
  const Change ch[] = {
    { 0, "Threshold", -30.0f }, { 0, "Hold", 20.0f }, { 0, "Decay", 60.0f },
    { 0, "Key HP", 150.0f }, { 0, "Lookahead", 1.5f },
    { 9000, "Mode", 1.0f }, { 9000, "Range", -30.0f }, { 9000, "Key LP", 3000.0f },
    { 20000, "Link", 1.0f }, { 20000, "Return", 9.0f }, { 20000, "Lookahead", 4.0f },
    { 31000, "Listen", 1.0f }, { 31000, "Key HP", 20.0f }, { 33000, "Listen", 0.0f },
    { 40000, "Link", 2.0f }, { 40000, "Lockout", 120.0f }, { 40000, "Attack", 3.0f },
    { 52000, "Mode", 0.0f }, { 52000, "Key LP", 20000.0f }, { 52000, "Lookahead", 0.0f },
    { 70000, "Threshold", -60.0f }, { 70000, "Range", -90.0f },
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  Source(g_a, kTotal, 7u);
  memcpy(g_b, g_a, sizeof(g_a));
  memcpy(g_c, g_a, sizeof(g_a));
  memcpy(g_d, g_a, sizeof(g_a));
  memcpy(g_e, g_a, sizeof(g_a));
  RenderChanges(64, ch, n, g_a, VIA_RENDER);
  RenderChanges(7, ch, n, g_b, VIA_RENDER);
  RenderChanges(1, ch, n, g_c, VIA_RENDER);
  RenderChanges(64, ch, n, g_d, VIA_KEY_NULL);
  RenderChanges(13, ch, n, g_e, VIA_KEY_COPY);
  const bool blocks = memcmp(g_a, g_b, sizeof(g_a)) == 0 && memcmp(g_a, g_c, sizeof(g_a)) == 0;
  const bool key_null = memcmp(g_a, g_d, sizeof(g_a)) == 0;
  const bool key_copy = memcmp(g_a, g_e, sizeof(g_a)) == 0;
  printf("\"blocks\":{\"block_independent\":%s,\"render_key_null\":%s,\"render_key_copy\":%s}",
         blocks ? "true" : "false", key_null ? "true" : "false", key_copy ? "true" : "false");
}

// 3. Attack: frames from the trigger to a fully open gate (gain exactly 1),
// and the gain a quarter and half way through (dB-linear ramps). Range -80,
// a key step from silence to 0.5.
void Attack() {
  const float attacks[] = { 0.0f, 0.5f, 2.0f, 10.0f, 100.0f };
  printf("\"attack\":[");
  for (int a = 0; a < 5; ++a) {
    void *self = Make(kRate, 0);
    const Kv kv[] = { { "Attack", attacks[a] } };
    SetAll(self, kv, 1);
    fm1_gate_state_t st;
    int trigger = -1, open = -1;
    float quarter = -1.0f, half = -1.0f;
    const double t = attacks[a] * 0.001 * kRate;
    const int kq = static_cast<int>(lround(t / 4)), kh = static_cast<int>(lround(t / 2));
    for (int i = 0; i < 10000 && open < 0; ++i) {
      Frame(self, 1.0f, i < 100 ? 0.0f : 0.5f, &st);
      if (trigger < 0 && st.key_high) trigger = i;
      if (trigger >= 0) {
        const int k = i - trigger + 1;     // frames of attack so far
        if (k == kq) quarter = st.gain;
        if (k == kh) half = st.gain;
        if (st.gain == 1.0f) open = i;
      }
    }
    printf("%s[%g,%d,%d,%.9g,%.9g,%d,%d]", a ? "," : "", attacks[a], trigger,
           open - trigger + 1, quarter, half, kq, kh);
  }
  printf("]");
}

// 4. The close: a key at 0.5 for 2,000 frames, then silence. Frames from the
// key's end to the Schmitt trigger's fall (the detector's 4 ms fall to
// Threshold - Return), from there to the decay's first frame (Hold), and
// from there to the closed gate (Decay, for Range -80 and -40). Attack 0.
void Close() {
  struct Case { float hold, decay, range; };
  const Case cases[] = { { 2, 100, -80 }, { 50, 100, -80 }, { 500, 100, -80 },
                         { 50, 400, -80 }, { 50, 400, -40 }, { 50, 2, -80 } };
  printf("\"close\":[");
  for (int c = 0; c < 6; ++c) {
    void *self = Make(kRate, 0);
    const Kv kv[] = { { "Attack", 0.0f }, { "Hold", cases[c].hold }, { "Decay", cases[c].decay },
                      { "Range", cases[c].range } };
    SetAll(self, kv, 4);
    fm1_gate_state_t st;
    int fall = -1, decay = -1, closed = -1;
    float closed_gain = -1.0f, mid_gain = -1.0f;
    const int end = 2100;
    for (int i = 0; i < 400000 && closed < 0; ++i) {
      Frame(self, 1.0f, (i >= 100 && i < end) ? 0.5f : 0.0f, &st);
      if (i < end) continue;
      if (fall < 0 && !st.key_high) fall = i;
      if (fall >= 0 && decay < 0 && st.gain < 1.0f) decay = i;
      if (decay >= 0 && !st.open && st.env == 0.0f) {
        closed = i;
        closed_gain = st.gain;
      }
    }
    // The gain half way through the decay, by a second run.
    if (decay >= 0 && closed >= 0) {
      void *again = Make(kRate, 0);
      SetAll(again, kv, 4);
      const int mid = decay + (closed - decay) / 2;
      for (int i = 0; i <= mid; ++i) {
        Frame(again, 1.0f, (i >= 100 && i < end) ? 0.5f : 0.0f, &st);
      }
      mid_gain = st.gain;
    }
    printf("%s[%g,%g,%g,%d,%d,%d,%.9g,%.9g]", c ? "," : "", cases[c].hold, cases[c].decay,
           cases[c].range, fall - end, decay - fall, closed - decay + 1, closed_gain, mid_gain);
  }
  printf("]");
}

// 5. Range: the closed gate's gain.
void Range() {
  const float ranges[] = { 0.0f, -20.0f, -40.0f, -80.0f, -89.9f, -90.0f };
  printf("\"range\":[");
  for (int r = 0; r < 6; ++r) {
    void *self = Make(kRate, 0);
    Set(self, "Range", ranges[r]);
    fm1_gate_state_t st;
    float out = 0.0f;
    for (int i = 0; i < 1000; ++i) out = Frame(self, 1.0f, 0.0f, &st);
    printf("%s[%g,%.9g,%.9g]", r ? "," : "", ranges[r], st.gain, out);
  }
  printf("]");
}

// A gate driven by DC key levels, `frames` frames each; the open state and
// the gain at the end of each segment.
void Segments(void *self, const float *levels, int n, int frames, int *open, float *gain) {
  fm1_gate_state_t st;
  for (int s = 0; s < n; ++s) {
    for (int i = 0; i < frames; ++i) Frame(self, 1.0f, levels[s], &st);
    open[s] = static_cast<int>(st.open);
    gain[s] = st.gain;
  }
}

// 6. Return: Threshold -20 dB, Return 6 dB: closes only below -26 dB.
// Levels -20.9 (closed), -19.2 (opens), -24.4 (stays open), -28 dB (closes);
// with Return 0 the third closes it. Hold and Decay 2 ms, Attack 0.
void Hysteresis() {
  const float levels[] = { 0.09f, 0.11f, 0.06f, 0.04f };
  printf("\"hysteresis\":[");
  const float returns[] = { 6.0f, 0.0f };
  for (int r = 0; r < 2; ++r) {
    void *self = Make(kRate, 0);
    const Kv kv[] = { { "Threshold", -20.0f }, { "Return", returns[r] }, { "Attack", 0.0f },
                      { "Hold", 2.0f }, { "Decay", 2.0f } };
    SetAll(self, kv, 5);
    int open[4];
    float gain[4];
    Segments(self, levels, 4, 4000, open, gain);
    printf("%s[%g,[%d,%d,%d,%d]]", r ? "," : "", returns[r], open[0], open[1], open[2], open[3]);
  }
  printf("]");
}

// 7. Duck: the key pulls the gain down to Range, and lets it back.
void Duck() {
  void *self = Make(kRate, 0);
  const Kv kv[] = { { "Mode", 1.0f }, { "Range", -20.0f }, { "Attack", 1.0f }, { "Hold", 10.0f },
                    { "Decay", 50.0f } };
  SetAll(self, kv, 5);
  const float levels[] = { 0.0f, 0.5f, 0.0f, 0.003f };
  int open[4];
  float gain[4];
  Segments(self, levels, 4, 8000, open, gain);
  printf("\"duck\":{\"gains\":[%.9g,%.9g,%.9g,%.9g],\"open\":[%d,%d,%d,%d]}",
         gain[0], gain[1], gain[2], gain[3], open[0], open[1], open[2], open[3]);
}

// 8. Lockout: five 10 ms bursts 100 ms apart (the gate closes between them);
// the openings counted for several Lockout times.
void Lockout() {
  const float lockouts[] = { 0.0f, 50.0f, 150.0f, 250.0f, 450.0f };
  printf("\"lockout\":[");
  for (int l = 0; l < 5; ++l) {
    void *self = Make(kRate, 0);
    const Kv kv[] = { { "Attack", 0.0f }, { "Hold", 2.0f }, { "Decay", 2.0f },
                      { "Lockout", lockouts[l] } };
    SetAll(self, kv, 4);
    fm1_gate_state_t st;
    int openings = 0, closed_between = 1;
    uint32_t was = 0;
    const int period = 4412, burst = 441;
    for (int i = 0; i < 5 * period; ++i) {
      const int phase = i % period;
      Frame(self, 1.0f, phase < burst ? 0.5f : 0.0f, &st);
      if (st.open && !was) ++openings;
      if (phase == period - 1 && st.gain == 1.0f) closed_between = 0;
      was = st.open;
    }
    printf("%s[%g,%d,%d]", l ? "," : "", lockouts[l], openings, closed_between);
  }
  printf("]");
}

// 9. Latency: Range 0 (the gain is 1 throughout), an impulse in; where it
// comes out, what the state says, and that nothing else came out.
void Latency() {
  const float rates[] = { 44118.0f, 48000.0f, 96000.0f, 192000.0f };
  const float looks[] = { 0.0f, 1.0f, 2.0f, 5.0f };
  printf("\"latency\":[");
  int first = 1;
  for (int r = 0; r < 4; ++r) {
    for (int k = 0; k < 4; ++k) {
      void *self = Make(rates[r], 0);
      const Kv kv[] = { { "Range", 0.0f }, { "Lookahead", looks[k] } };
      SetAll(self, kv, 2);
      fm1_gate_state_t st;
      int at = -1;
      bool clean = true;
      for (int i = 0; i < 2000; ++i) {
        const float y = Frame(self, i == 10 ? 1.0f : 0.0f, 0.0f, &st);
        if (y == 1.0f && at < 0) at = i - 10;
        else if (y != 0.0f) clean = false;
      }
      printf("%s[%g,%g,%d,%u,%s]", first ? "" : ",", rates[r], looks[k], at, st.latency,
             clean ? "true" : "false");
      first = 0;
    }
  }
  printf("]");
}

// 10. A burst after silence, Range -90, Attack 0.5 ms: with Lookahead 2 ms
// the burst comes out whole (the gate is open before it arrives), without
// it its first half millisecond is cut. The largest difference from the
// input over the burst's first 5 ms, and its first sample out.
void Onset() {
  printf("\"onset\":[");
  const float looks[] = { 0.0f, 2.0f };
  for (int k = 0; k < 2; ++k) {
    void *self = Make(kRate, 0);
    const Kv kv[] = { { "Range", -90.0f }, { "Attack", 0.5f }, { "Lookahead", looks[k] } };
    SetAll(self, kv, 3);
    const int d = static_cast<int>(lround(looks[k] * 0.001 * kRate));
    static float in[8000], out[8000];
    Lcg rng = { 5u };
    for (int i = 0; i < 8000; ++i) in[i] = i < 2000 ? 0.0f : 0.5f * rng.Bipolar();
    for (int i = 0; i < 8000; ++i) {
      float io[2] = { in[i], in[i] };
      E.render(self, io, 1);
      out[i] = io[0];
    }
    float worst = 0.0f;
    for (int i = 2000; i < 2000 + 220; ++i) worst = fmaxf(worst, fabsf(out[i + d] - in[i]));
    printf("%s[%g,%d,%.9g,%.9g,%.9g]", k ? "," : "", looks[k], d, worst, out[2000 + d], in[2000]);
  }
  printf("]");
}

// The steady amplitude (relative to the input's 0.5) of Listen's output for
// a sine of integer frequency hz: 1.5 s rendered, the last second measured
// at its exact bin.
double ListenGain(const Kv *kv, int n, double hz, float rate) {
  void *self = Make(rate, 0);
  SetAll(self, kv, n);
  Set(self, "Listen", 1.0f);
  const int total = static_cast<int>(1.5 * rate), from = total - static_cast<int>(rate);
  double re = 0.0, im = 0.0;
  float buf[128];
  for (int pos = 0; pos < total; pos += 64) {
    const int n = total - pos < 64 ? total - pos : 64;
    for (int i = 0; i < n; ++i) {
      const double t = (pos + i) / static_cast<double>(rate);
      buf[2 * i] = buf[2 * i + 1] = static_cast<float>(0.5 * sin(2.0 * M_PI * hz * t));
    }
    E.render(self, buf, static_cast<uint32_t>(n));
    for (int i = 0; i < n; ++i) {
      const int k = pos + i;
      if (k < from) continue;
      const double w = 2.0 * M_PI * hz * k / rate;
      re += buf[2 * i] * cos(w);
      im += buf[2 * i] * sin(w);
    }
  }
  E.destroy(self);
  const int m = total - from;
  return 2.0 * sqrt(re * re + im * im) / m / 0.5;
}

// 11. The key filters' magnitude responses through Listen.
void Filters() {
  struct Case { float hp, lp; };
  const Case cases[] = { { 100, 20000 }, { 1000, 20000 }, { 20, 500 }, { 20, 5000 },
                         { 300, 3000 }, { 10000, 20000 }, { 20, 200 } };
  const double hzs[] = { 20, 50, 100, 200, 300, 500, 1000, 2000, 3000, 5000, 8000, 12000, 16000 };
  printf("\"filters\":[");
  for (int c = 0; c < 7; ++c) {
    const Kv kv[] = { { "Key HP", cases[c].hp }, { "Key LP", cases[c].lp } };
    printf("%s[%g,%g,[", c ? "," : "", cases[c].hp, cases[c].lp);
    for (int h = 0; h < 13; ++h) {
      printf("%s[%g,%.6f]", h ? "," : "", hzs[h], Db(ListenGain(kv, 2, hzs[h], kRate)));
    }
    printf("]]");
  }
  printf("]");
}

// 12. Listen's output, sample by sample, for a reference to check: stereo
// noise (the Lcg's, seed 11, 0.5 x, left then right) through Key HP 300 Hz
// and Key LP 3 kHz, Link Max: both channels, 2,000 frames.
void ListenRef() {
  void *self = Make(kRate, 0);
  const Kv kv[] = { { "Key HP", 300.0f }, { "Key LP", 3000.0f }, { "Listen", 1.0f } };
  SetAll(self, kv, 3);
  Lcg rng = { 11u };
  static float buf[4000];
  for (int i = 0; i < 2000; ++i) {
    buf[2 * i] = 0.5f * rng.Bipolar();
    buf[2 * i + 1] = 0.5f * rng.Bipolar();
  }
  E.render(self, buf, 2000);
  printf("\"listen_ref\":[");
  for (int i = 0; i < 4000; ++i) printf("%s%.9g", i ? "," : "", buf[i]);
  printf("]");
}

// 13. Link, heard through Listen with the filters out: Max is the key in
// stereo, Sum is 0.5 (L + R) on both, Left is L on both, exactly.
void LinkListen() {
  printf("\"link_listen\":[");
  for (int link = 0; link < 3; ++link) {
    void *self = Make(kRate, 0);
    const Kv kv[] = { { "Listen", 1.0f }, { "Link", static_cast<float>(link) } };
    SetAll(self, kv, 2);
    Lcg rng = { 13u };
    static float in[1000], buf[1000];
    for (int i = 0; i < 1000; ++i) in[i] = buf[i] = 0.5f * rng.Bipolar();
    E.render(self, buf, 500);
    bool exact = true;
    for (int i = 0; i < 500; ++i) {
      const float l = in[2 * i], r = in[2 * i + 1];
      float wl = l, wr = r;
      if (link == 1) wl = wr = 0.5f * (l + r);
      if (link == 2) wl = wr = l;
      if (buf[2 * i] != wl || buf[2 * i + 1] != wr) exact = false;
    }
    printf("%s[%d,%s]", link ? "," : "", link, exact ? "true" : "false");
  }
  printf("]");
}

// 14. Link on the detector: a key on one channel only. Left channel loud:
// every Link opens. Right channel loud: Max and Sum open, Left does not.
// Anti-phase (R = -L): Max and Left open, Sum does not.
void LinkDetect() {
  printf("\"link_detect\":[");
  for (int link = 0; link < 3; ++link) {
    int opened[3];
    for (int k = 0; k < 3; ++k) {
      void *self = Make(kRate, 0);
      Set(self, "Link", static_cast<float>(link));
      fm1_gate_state_t st;
      opened[k] = 0;
      for (int i = 0; i < 2000; ++i) {
        float io[2] = { 1.0f, 1.0f };
        const float x = 0.2f;
        const float key[2] = { k == 1 ? 0.0f : x, k == 0 ? 0.0f : (k == 2 ? -x : x) };
        fm1_gate_render_key(self, io, key, 1);
        fm1_gate_state(self, &st);
        if (st.open) opened[k] = 1;
      }
    }
    printf("%s[%d,%d,%d,%d]", link ? "," : "", link, opened[0], opened[1], opened[2]);
  }
  printf("]");
}

// 15. Key LP delays the trigger: a key step from 0 to 1 at frame 100,
// Threshold -6.0206 dB (0.5): frames from the step to the trigger, per LP.
void LpTrigger() {
  const float lps[] = { 20000.0f, 4000.0f, 1000.0f, 250.0f };
  printf("\"lp_trigger\":[");
  for (int k = 0; k < 4; ++k) {
    void *self = Make(kRate, 0);
    const Kv kv[] = { { "Threshold", -6.0206f }, { "Key LP", lps[k] }, { "Attack", 0.0f } };
    SetAll(self, kv, 3);
    fm1_gate_state_t st;
    int at = -1;
    for (int i = 0; i < 3000 && at < 0; ++i) {
      Frame(self, 1.0f, i < 100 ? 0.0f : 1.0f, &st);
      if (st.key_high) at = i - 100;
    }
    printf("%s[%g,%d]", k ? "," : "", lps[k], at);
  }
  printf("]");
}

// 16. Chatter: a 200 Hz tone decaying from -6 dBFS through the -40 dB
// threshold over 2 s, on noise at -46 dB (peaks near -40), so the key
// hovers around the threshold for a long while. The gate's openings,
// counted for settings from none of the defences to all of them.
void Chatter() {
  struct Case { float ret, hold, lockout; };
  const Case cases[] = { { 0, 2, 0 }, { 4, 2, 0 }, { 0, 50, 0 }, { 4, 50, 0 }, { 0, 2, 300 },
                         { 8, 50, 0 } };
  printf("\"chatter\":[");
  for (int c = 0; c < 6; ++c) {
    void *self = Make(kRate, 0);
    const Kv kv[] = { { "Return", cases[c].ret }, { "Hold", cases[c].hold },
                      { "Lockout", cases[c].lockout }, { "Attack", 0.0f }, { "Decay", 2.0f } };
    SetAll(self, kv, 5);
    fm1_gate_state_t st;
    Lcg rng = { 17u };
    int openings = 0;
    uint32_t was = 0;
    const int total = static_cast<int>(3 * kRate);
    for (int i = 0; i < total; ++i) {
      const double t = i / static_cast<double>(kRate);
      const double amp = 0.5 * pow(10.0, -50.0 * t / 20.0);     // -50 dB per second
      const float key = static_cast<float>(amp * sin(2.0 * M_PI * 200.0 * t)) +
                        0.005f * rng.Bipolar();
      Frame(self, 1.0f, key, &st);
      if (st.open && !was) ++openings;
      was = st.open;
    }
    printf("%s[%g,%g,%g,%d]", c ? "," : "", cases[c].ret, cases[c].hold, cases[c].lockout,
           openings);
  }
  printf("]");
}

// 17. Bad keys: 100 frames of NaN, an infinity or 1e30 on a silent key, then
// silence. The gate must close (no latched hold or level), on the frame a
// clean run with a full-scale (16, the guard's clamp) key closes on; NaN
// reads as silence and never opens it.
void BadKey() {
  const float bad[] = { NAN, INFINITY, -INFINITY, 1e30f, 16.0f };
  printf("\"bad_key\":[");
  for (int b = 0; b < 5; ++b) {
    void *self = Make(kRate, 0);
    fm1_gate_state_t st;
    int opened = 0, closed_at = -1;
    bool finite = true;
    for (int i = 0; i < 40000; ++i) {
      const float y = Frame(self, 0.25f, (i >= 100 && i < 200) ? bad[b] : 0.0f, &st);
      if (!(fabsf(y) <= 1.0f) || !(st.key >= 0.0f && st.key <= 1.0f)) finite = false;
      if (st.open) opened = 1;
      if (opened && closed_at < 0 && !st.open && st.env == 0.0f) closed_at = i;
    }
    printf("%s[\"%g\",%d,%d,%s,%u,%.9g]", b ? "," : "", bad[b], opened, closed_at,
           finite ? "true" : "false", st.open, st.gain);
  }
  printf("]");
}

// 18. A key other than the input: noise in, a click every 250 ms as the key.
// The gate opens on each click and closes between them: the output's RMS
// in the 40 ms after a click against the 50 ms before the next.
void ExternalKey() {
  void *self = Make(kRate, 0);
  const Kv kv[] = { { "Hold", 20.0f }, { "Decay", 30.0f }, { "Range", -60.0f } };
  SetAll(self, kv, 3);
  Lcg rng = { 19u };
  const int period = 11030, total = 4 * period;
  double open2 = 0.0, closed2 = 0.0;
  int n_open = 0, n_closed = 0;
  float buf[2], key[2];
  for (int i = 0; i < total; ++i) {
    buf[0] = buf[1] = 0.5f * rng.Bipolar();
    key[0] = key[1] = (i % period == 0) ? 0.9f : 0.0f;
    fm1_gate_render_key(self, buf, key, 1);
    const int ph = i % period;
    if (ph < 1765) { open2 += buf[0] * buf[0]; ++n_open; }
    if (ph >= period - 2206) { closed2 += buf[0] * buf[0]; ++n_closed; }
  }
  printf("\"external_key\":{\"open_db\":%.3f,\"closed_db\":%.3f}",
         10.0 * log10(open2 / n_open), 10.0 * log10(closed2 / n_closed + 1e-30));
}

// 19. Host rates: refused outside 8 kHz..384 kHz and when not a number; the
// instance size at each (the line grows with the rate, up to its cap).
void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 44118.0f, 48000.0f, 96000.0f, 102000.0f,
                          192000.0f, 384000.0f, 400000.0f, NAN, INFINITY, -44118.0f };
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

// 20. The tan polynomial against libm's, on [0, 0.45 pi].
void Approx() {
  double worst = 0.0, at = 0.0;
  for (int i = 0; i <= 100000; ++i) {
    const float x = static_cast<float>(0.45 * M_PI * i / 100000.0);
    const double want = tan(static_cast<double>(x));
    const double got = fm1_gate_probe_tan(x);
    const double err = want > 0.0 ? fabs(got - want) / want : fabs(got);
    if (err > worst) { worst = err; at = x; }
  }
  printf("\"approx\":{\"tan_rel\":%.3g,\"tan_at\":%.6g,\"tan_0\":%.9g}", worst, at,
         fm1_gate_probe_tan(0.0f));
}

// 21. Every float of three renders (2 s of noise bursts each, settings
// changed mid-stream), hashed (FNV-1a over the bits): the same on every
// build that keeps to IEEE single precision without fused multiply-adds.
// tests/test_engines_gate.py pins it.
void Hash() {
  printf("\"hash\":[");
  for (int c = 0; c < 3; ++c) {
    const Change set0[] = {
      { 0, "Key HP", 120.0f }, { 0, "Key LP", 6000.0f }, { 0, "Lookahead", 2.0f },
      { 0, "Threshold", -30.0f }, { 44000, "Mode", 1.0f }, { 60000, "Range", -40.0f },
    };
    const Change set1[] = {
      { 0, "Attack", 5.0f }, { 0, "Hold", 10.0f }, { 0, "Decay", 40.0f }, { 0, "Return", 8.0f },
      { 0, "Lockout", 90.0f }, { 30000, "Link", 1.0f }, { 50000, "Listen", 1.0f },
      { 50500, "Listen", 0.0f }, { 61000, "Lookahead", 5.0f },
    };
    const Change set2[] = {
      { 0, "Range", -90.0f }, { 0, "Link", 2.0f }, { 0, "Key HP", 2000.0f },
      { 25000, "Key HP", 20.0f }, { 25000, "Threshold", -55.0f }, { 70000, "Mode", 1.0f },
    };
    const Change *sets[3] = { set0, set1, set2 };
    const int counts[3] = { 6, 9, 6 };
    Source(g_a, kTotal, 23u + c);
    RenderChanges(64, sets[c], counts[c], g_a, VIA_RENDER);
    uint32_t h = 2166136261u;
    for (uint32_t i = 0; i < 2 * kTotal; ++i) {
      uint32_t u;
      memcpy(&u, &g_a[i], sizeof u);
      h = (h ^ u) * 16777619u;
    }
    printf("%s\"%08x\"", c ? "," : "", h);
  }
  printf("]");
}

// 22. Cost: ns per 64-frame stereo block of noise bursts, 0.5 s warm-up then
// 20 s; the best of three runs.
double Cost(const Kv *kv, int n, bool gliding) {
  void *self = Make(kRate, 0);
  SetAll(self, kv, n);
  static float src[64 * 128];
  Lcg rng = { 3u };
  for (int b = 0; b < 64; ++b) {
    const float level = (b % 8) < 5 ? 0.5f : 0.002f;   // the gate opens and closes
    for (int i = 0; i < 128; ++i) src[128 * b + i] = level * rng.Bipolar();
  }
  float buf[128];
  const int blocks = 13786;                     // 20 s
  for (int b = 0; b < 344; ++b) {
    memcpy(buf, src + 128 * (b % 64), sizeof(buf));
    E.render(self, buf, 64);
  }
  volatile float sink = 0.0f;
  const auto t0 = std::chrono::steady_clock::now();
  for (int b = 0; b < blocks; ++b) {
    if (gliding) Set(self, "Threshold", (b & 1) ? -40.0f : -30.0f);
    memcpy(buf, src + 128 * (b % 64), sizeof(buf));
    E.render(self, buf, 64);
    sink = sink + buf[0];
  }
  const auto t1 = std::chrono::steady_clock::now();
  E.destroy(self);
  return std::chrono::duration<double, std::nano>(t1 - t0).count() / blocks;
}

void Costs() {
  const Kv plain[] = { { "Threshold", -30.0f } };
  const Kv full[] = { { "Threshold", -30.0f }, { "Key HP", 100.0f }, { "Key LP", 5000.0f },
                      { "Lookahead", 2.0f }, { "Hold", 2.0f }, { "Decay", 20.0f } };
  double best_plain = 1e30, best_full = 1e30, best_glide = 1e30;
  for (int run = 0; run < 3; ++run) {
    best_plain = fmin(best_plain, Cost(plain, 1, false));
    best_full = fmin(best_full, Cost(full, 6, false));
    best_glide = fmin(best_glide, Cost(full, 6, true));
  }
  fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
  printf("\"cost\":{\"ns_per_block_default\":%.1f,\"ns_per_block_filters_look\":%.1f,"
         "\"ns_per_block_gliding\":%.1f,\"instance_bytes\":%zu}",
         best_plain, best_full, best_glide, E.instance_size(&host));
}

}  // namespace

int main(int argc, char **argv) {
  const bool cost = argc > 1 && strcmp(argv[1], "--cost") == 0;
  printf("{");
  if (cost) {
    Costs();
  } else {
    Sweep(); printf(",");
    Blocks(); printf(",");
    Attack(); printf(",");
    Close(); printf(",");
    Range(); printf(",");
    Hysteresis(); printf(",");
    Duck(); printf(",");
    Lockout(); printf(",");
    Latency(); printf(",");
    Onset(); printf(",");
    Filters(); printf(",");
    ListenRef(); printf(",");
    LinkListen(); printf(",");
    LinkDetect(); printf(",");
    LpTrigger(); printf(",");
    Chatter(); printf(",");
    BadKey(); printf(",");
    ExternalKey(); printf(",");
    Rates(); printf(",");
    Approx(); printf(",");
    Hash();
  }
  printf("}\n");
  return 0;
}
