// limit_test.cc -- fm1-limit-test: drives the Limiter (src/fx_limit.cc)
// through its engine struct where fm1-render cannot: float output (no 16-bit
// WAV, no bus limiter after it) against the ceiling on hostile input,
// latency, release time, transparency, parameters that change while audio
// runs, block sizes that change from call to call, host rates and instance
// sizes. Prints one JSON object; tests/test_engines_limit.py reads it. MIT
// licence.

#include "fm1_engine.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_limit;
extern "C" float fm1_limit_probe_worst;   // fx_limit.cc built with FM1_LIMIT_PROBE

namespace {

const fm1_engine_t &E = fm1_engine_limit;
const float kRate = 44118.0f;
alignas(16) unsigned char g_mem[1 << 16];

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

struct Setting {
  float ceiling, drive, release, lookahead, mode, link, mix;
};

void Apply(void *self, const Setting &s) {
  Set(self, "Ceiling", s.ceiling);
  Set(self, "Drive", s.drive);
  Set(self, "Release", s.release);
  Set(self, "Lookahead", s.lookahead);
  Set(self, "Mode", s.mode);
  Set(self, "Link", s.link);
  Set(self, "Mix", s.mix);
}

// Render total frames of buf in place, in blocks of `block` (the last shorter).
void RenderAll(void *self, float *buf, uint32_t total, uint32_t block) {
  for (uint32_t pos = 0; pos < total; pos += block) {
    E.render(self, &buf[2 * pos], total - pos < block ? total - pos : block);
  }
}

uint32_t Frames(float ms, float rate) {
  return static_cast<uint32_t>(floor(ms * 0.001 * rate + 0.5));
}

// --- hostile signals ----------------------------------------------------------

// square-50, square-1k, square-11k, nyquist, impulses, impulses-16, noise,
// noise-x20, dc-steps, onset-burst, chirp
const int kSignals = 11;

// Frame i of signal k, left and right (decorrelated where it matters).
void Signal(int k, uint32_t i, Lcg &rng, float *l, float *r) {
  const double t = i / static_cast<double>(kRate);
  float x = 0.0f, y;
  switch (k) {
    case 0: x = fmod(t * 50.0, 1.0) < 0.5 ? 1.0f : -1.0f; break;
    case 1: x = fmod(t * 1000.0, 1.0) < 0.5 ? 1.0f : -1.0f; break;
    case 2: x = fmod(t * 11000.0, 1.0) < 0.5 ? 1.0f : -1.0f; break;
    case 3: x = (i & 1) ? -1.0f : 1.0f; break;
    case 4: x = (i % 997 == 0) ? ((i / 997) & 1 ? -1.0f : 1.0f) : 0.0f; break;
    case 5: x = (i % 331 == 0 || i % 331 == 2) ? ((i / 331) & 1 ? -16.0f : 16.0f) : 0.0f; break;
    case 6: x = rng.Bipolar(); break;
    case 7: x = 20.0f * rng.Bipolar(); break;                      // the guard clamps at 16
    case 8: { const float lv[4] = { 0.0f, 1.0f, -1.0f, 0.5f }; x = lv[(i / 2000) % 4]; break; }
    case 9: x = ((i % 8000) < 4000) ? 0.0f : (fmod(t * 220.0, 1.0) < 0.5 ? 1.0f : -1.0f); break;
    case 10: x = static_cast<float>(sin(2 * M_PI * (20.0 * t + 0.5 * (20000.0 - 20.0) * t * t / 0.5))); break;
    default: break;
  }
  y = x;
  if (k == 6 || k == 7) y = (k == 7 ? 20.0f : 1.0f) * rng.Bipolar();
  if (k == 4) y = -x;
  *l = x;
  *r = y;
}

// 1. The ceiling on hostile input. Every signal under many settings, in host
// blocks of random size; the largest |output| / 10^(Ceiling/20), the true
// ceiling in double precision. Mix 1 throughout.
void Ceiling() {
  const float ceilings[] = { 0.0f, -1.0f, -6.0f, -24.0f, -0.3f };
  const float drives[] = { 0.0f, 12.0f, 24.0f, -12.0f };
  const float looks[] = { 0.0f, 0.02f, 0.5f, 2.0f, 5.0f };
  const float releases[] = { 1.0f, 100.0f, 1000.0f };
  const float links[] = { 0.0f, 0.5f, 1.0f };
  Lcg pick = { 7u };
  double worst[2][2] = { { 0, 0 }, { 0, 0 } };   // [mode][lookahead 0 or not]
  float envelope = 0.0f;   // BRICKWALL with a lookahead: |u x a| / c before the clamp
  float peak_at_0db = 0.0f;
  uint64_t over = 0, frames_checked = 0;
  int runs = 0;
  float buf[128];
  const uint32_t total = static_cast<uint32_t>(0.25f * kRate);
  for (int mode = 0; mode < 2; ++mode) {
    for (int combo = 0; combo < 60; ++combo) {
      Setting s;
      s.ceiling = ceilings[pick.Next() % 5];
      s.drive = drives[pick.Next() % 4];
      s.lookahead = looks[combo % 5];
      s.release = releases[pick.Next() % 3];
      s.link = links[pick.Next() % 3];
      s.mode = static_cast<float>(mode);
      s.mix = 1.0f;
      const double c = pow(10.0, s.ceiling / 20.0);
      for (int k = 0; k < kSignals; ++k) {
        void *self = Make(kRate, 0xA5);
        Apply(self, s);
        fm1_limit_probe_worst = 0.0f;
        Lcg rng = { 99u + static_cast<uint32_t>(k) };
        for (uint32_t pos = 0; pos < total;) {
          uint32_t n = 1 + pick.Next() % 64;
          if (n > total - pos) n = total - pos;
          for (uint32_t i = 0; i < n; ++i) Signal(k, pos + i, rng, &buf[2 * i], &buf[2 * i + 1]);
          E.render(self, buf, n);
          for (uint32_t i = 0; i < 2 * n; ++i) {
            const double r = fabs(buf[i]) / c;
            const int z = s.lookahead == 0.0f;
            if (r > worst[mode][z]) worst[mode][z] = r;
            if (r > 1.0 + 5e-7) ++over;
            if (s.ceiling == 0.0f && fabsf(buf[i]) > peak_at_0db) peak_at_0db = fabsf(buf[i]);
          }
          frames_checked += n;
          pos += n;
        }
        E.destroy(self);
        if (mode == 0 && s.lookahead > 0.0f && fm1_limit_probe_worst > envelope) {
          envelope = fm1_limit_probe_worst;
        }
        ++runs;
      }
    }
  }
  printf("\"ceiling\":{\"runs\":%d,\"frames\":%llu,\"over\":%llu,\"peak_at_0db\":%.9g,"
         "\"brickwall\":%.9g,\"brickwall_zero\":%.9g,\"soft\":%.9g,\"soft_zero\":%.9g,"
         "\"envelope\":%.9g}",
         runs, static_cast<unsigned long long>(frames_checked),
         static_cast<unsigned long long>(over), peak_at_0db, worst[0][0], worst[0][1],
         worst[1][0], worst[1][1], envelope);
}

// 2. Latency: an impulse under the ceiling comes out alone, unchanged, d
// frames later, d = Lookahead in frames (rounded; at most 510).
void Latency() {
  const float rates[] = { 44118.0f, 48000.0f, 96000.0f, 192000.0f };
  const float looks[] = { 0.0f, 0.01f, 0.02f, 0.5f, 1.0f, 2.0f, 3.3f, 5.0f };
  printf("\"latency\":[");
  int first = 1;
  static float buf[2 * 4096];
  for (float rate : rates) {
    for (float ms : looks) {
      void *self = Make(rate, 0xFF);
      Set(self, "Ceiling", 0.0f);
      Set(self, "Lookahead", ms);
      const uint32_t total = 2048, at = 100;
      memset(buf, 0, sizeof(buf));
      buf[2 * at] = 0.5f;
      buf[2 * at + 1] = -0.25f;
      RenderAll(self, buf, total, 64);
      int found = -1, clean = 1;
      for (uint32_t i = 0; i < total; ++i) {
        if (buf[2 * i] != 0.0f || buf[2 * i + 1] != 0.0f) {
          if (found < 0 && buf[2 * i] == 0.5f && buf[2 * i + 1] == -0.25f) found = static_cast<int>(i);
          else clean = 0;
        }
      }
      uint32_t want = Frames(ms, rate);
      if (want > 510) want = 510;
      printf("%s[%g,%g,%d,%u,%s]", first ? "" : ",", rate, ms,
             found < 0 ? -1 : found - static_cast<int>(at), want, clean ? "true" : "false");
      first = 0;
      E.destroy(self);
    }
  }
  printf("]");
}

// 3. Transparency: below the ceiling (and below the knee of the stage in
// use) the output is the input delayed by the lookahead, exactly, in every
// mode; and again once a loud burst has been released.
const uint32_t kLong = 3 * 44118;
float g_in[2 * kLong], g_out[2 * kLong];

bool Transparent(const Setting &s, float amplitude, uint32_t *mismatch_from) {
  void *self = Make(kRate, 0x5A);
  Apply(self, s);
  Lcg rng = { 3u };
  const uint32_t total = kRate;
  for (uint32_t i = 0; i < total; ++i) {
    g_in[2 * i] = amplitude * rng.Bipolar();
    g_in[2 * i + 1] = amplitude * rng.Bipolar();
  }
  memcpy(g_out, g_in, 2 * total * sizeof(float));
  RenderAll(self, g_out, total, 37);
  const uint32_t d = Frames(s.lookahead, kRate);
  bool same = true;
  for (uint32_t i = 0; i < total && same; ++i) {
    const float l = i >= d ? g_in[2 * (i - d)] : 0.0f, r = i >= d ? g_in[2 * (i - d) + 1] : 0.0f;
    if (g_out[2 * i] != l || g_out[2 * i + 1] != r) { same = false; *mismatch_from = i; }
  }
  E.destroy(self);
  return same;
}

void Transparency() {
  struct Case { const char *name; Setting s; float amplitude; };
  const Case cases[] = {
    { "brickwall", { 0.0f, 0.0f, 100.0f, 2.0f, 0.0f, 1.0f, 1.0f }, 0.999f },
    { "brickwall-unlinked", { 0.0f, 0.0f, 10.0f, 5.0f, 0.0f, 0.0f, 1.0f }, 0.999f },
    { "brickwall-minus6", { -6.0f, 0.0f, 100.0f, 1.0f, 0.0f, 1.0f, 1.0f }, 0.5f },
    { "zero-lookahead", { 0.0f, 0.0f, 100.0f, 0.0f, 0.0f, 1.0f, 1.0f }, 0.89f },
    { "soft-clip", { 0.0f, 0.0f, 100.0f, 2.0f, 1.0f, 1.0f, 1.0f }, 0.5f },
  };
  printf("\"transparent\":{");
  for (size_t k = 0; k < sizeof(cases) / sizeof(cases[0]); ++k) {
    uint32_t at = 0;
    const bool ok = Transparent(cases[k].s, cases[k].amplitude, &at);
    printf("%s\"%s\":%s", k ? "," : "", cases[k].name, ok ? "true" : "false");
    if (!ok) fprintf(stderr, "%s differs from frame %u\n", cases[k].name, at);
  }
  printf("}");

  // After limiting: 0.3 s of a loud square, then quiet noise. Release 50 ms:
  // from some frame on the output is the delayed input again, exactly.
  void *self = Make(kRate, 0);
  Set(self, "Release", 50.0f);
  Lcg rng = { 5u };
  for (uint32_t i = 0; i < kLong; ++i) {
    const float q = 0.25f * rng.Bipolar();
    const bool loud = i < static_cast<uint32_t>(0.3f * kRate);
    g_in[2 * i] = loud ? ((i / 50) & 1 ? 3.0f : -3.0f) : q;
    g_in[2 * i + 1] = loud ? -g_in[2 * i] : -q;
  }
  memcpy(g_out, g_in, sizeof(g_in));
  RenderAll(self, g_out, kLong, 64);
  const uint32_t d = Frames(2.0f, kRate);
  uint32_t last_diff = 0;
  for (uint32_t i = d; i < kLong; ++i) {
    if (g_out[2 * i] != g_in[2 * (i - d)] || g_out[2 * i + 1] != g_in[2 * (i - d) + 1]) last_diff = i;
  }
  E.destroy(self);
  printf(",\"exact_again_after_ms\":%.3f", (last_diff + 1 - d - 0.3 * kRate) * 1000.0 / kRate);
}

// 4. Release: 0.5 s of a square at +12 dB over a 0 dB ceiling (gain 0.25;
// 0.223 at Lookahead 0, which aims 1 dB lower), then a quiet DC probe; the
// time from the probe's first output frame until the gain has made up
// 63.2 % (1 - 1/e) of the way back to 1.
void Release() {
  const float releases[] = { 10.0f, 100.0f, 500.0f };
  const float looks[] = { 0.0f, 2.0f, 5.0f };
  printf("\"release\":[");
  int first = 1;
  for (float rel : releases) {
    for (float look : looks) {
      void *self = Make(kRate, 0);
      Set(self, "Ceiling", 0.0f);
      Set(self, "Release", rel);
      Set(self, "Lookahead", look);
      const uint32_t burst = kRate / 2, total = kLong;
      const float probe = 0.01f;
      for (uint32_t i = 0; i < total; ++i) {
        const float x = i < burst ? ((i / 25) & 1 ? 4.0f : -4.0f) : probe;
        g_out[2 * i] = g_out[2 * i + 1] = x;
      }
      RenderAll(self, g_out, total, 64);
      const uint32_t d = Frames(look, kRate);
      const uint32_t start = burst + d;            // the probe's first frame out
      const double g0 = g_out[2 * (start - 1)] / 4.0;   // the gain on the burst's end
      const double goal = 1.0 - (1.0 - fabs(g0)) / M_E;
      int hit = -1;
      for (uint32_t i = start; i < total; ++i) {
        if (g_out[2 * i] / probe >= goal) { hit = static_cast<int>(i - start); break; }
      }
      printf("%s[%g,%g,%.6f,%.4f]", first ? "" : ",", rel, look, fabs(g0),
             hit < 0 ? -1.0 : hit * 1000.0 / kRate);
      first = 0;
      E.destroy(self);
    }
  }
  printf("]");
}

// 5. Link: the left channel a square at +12 dB over the ceiling, the right a
// quiet sine. The right channel's steady gain at Link 0, 0.5 and 1.
void Link() {
  const float links[] = { 0.0f, 0.5f, 1.0f };
  printf("\"link\":[");
  for (int k = 0; k < 3; ++k) {
    void *self = Make(kRate, 0);
    Set(self, "Ceiling", 0.0f);
    Set(self, "Link", links[k]);
    const uint32_t total = kRate;
    for (uint32_t i = 0; i < total; ++i) {
      g_in[2 * i] = (i / 30) & 1 ? 4.0f : -4.0f;
      g_in[2 * i + 1] = 0.25f * static_cast<float>(sin(2 * M_PI * 330.0 * i / kRate));
    }
    memcpy(g_out, g_in, 2 * total * sizeof(float));
    RenderAll(self, g_out, total, 64);
    const uint32_t d = Frames(2.0f, kRate);
    double num = 0, den = 0, left = 0;
    bool exact = true;
    for (uint32_t i = total / 2; i < total; ++i) {
      num += g_out[2 * i + 1] * g_in[2 * (i - d) + 1];
      den += g_in[2 * (i - d) + 1] * g_in[2 * (i - d) + 1];
      if (g_out[2 * i + 1] != g_in[2 * (i - d) + 1]) exact = false;
      left = fmax(left, fabs(g_out[2 * i]));
    }
    printf("%s[%g,%.6f,%.6f,%s]", k ? "," : "", links[k], num / den, left, exact ? "true" : "false");
    E.destroy(self);
  }
  printf("]");
}

// 6. Changes mid-stream, at blocks of 64, 7 and 1 frames (split at the
// changes): the output must not depend on the block size. Every parameter
// moves, Lookahead and Mode included.
struct Change { uint32_t at; const char *name; float value; };

void RenderChanges(uint32_t block, const Change *changes, int n_changes, uint32_t total,
                   float *out) {
  void *self = Make(kRate, 0x33);
  float buf[128];
  Lcg rng = { 11u };
  int next = 0;
  for (uint32_t pos = 0; pos < total;) {
    while (next < n_changes && changes[next].at <= pos) {
      Set(self, changes[next].name, changes[next].value);
      ++next;
    }
    uint32_t n = total - pos < block ? total - pos : block;
    if (next < n_changes && changes[next].at - pos < n) n = changes[next].at - pos;
    for (uint32_t i = 0; i < n; ++i) {
      buf[2 * i] = 1.5f * rng.Bipolar();
      buf[2 * i + 1] = 0.7f * static_cast<float>(sin(2 * M_PI * 220.0 * (pos + i) / kRate));
    }
    E.render(self, buf, n);
    memcpy(&out[2 * pos], buf, 2 * n * sizeof(float));
    pos += n;
  }
  E.destroy(self);
}

const uint32_t kChangeTotal = 44118;
float g_a[2 * kChangeTotal], g_b[2 * kChangeTotal], g_c[2 * kChangeTotal];

void Changes() {
  const Change ch[] = {
    { 0, "Release", 30.0f },
    { 4410, "Ceiling", -12.0f }, { 4410, "Drive", 12.0f },
    { 8820, "Lookahead", 4.0f }, { 8820, "Release", 300.0f },
    { 13230, "Mode", 1.0f }, { 13230, "Link", 0.3f },
    { 17640, "Mix", 0.6f }, { 17640, "Ceiling", -3.0f },
    { 22050, "Lookahead", 0.0f },
    { 26460, "Mode", 0.0f }, { 26460, "Mix", 1.0f },
    { 30870, "Lookahead", 1.0f }, { 30870, "Drive", -6.0f },
    { 30900, "Lookahead", 5.0f },       // during the crossfade: waits for it
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  RenderChanges(64, ch, n, kChangeTotal, g_a);
  RenderChanges(7, ch, n, kChangeTotal, g_b);
  RenderChanges(1, ch, n, kChangeTotal, g_c);
  const int same = memcmp(g_a, g_b, sizeof(g_a)) == 0 && memcmp(g_a, g_c, sizeof(g_a)) == 0;
  int finite = 1;
  float peak = 0.0f;
  for (uint32_t i = 0; i < 2 * kChangeTotal; ++i) {
    if (!(fabsf(g_a[i]) <= 3.4e38f)) finite = 0;
    else peak = fmaxf(peak, fabsf(g_a[i]));
  }
  printf("\"changes\":{\"block_independent\":%s,\"finite\":%s,\"peak\":%.6f}",
         same ? "true" : "false", finite ? "true" : "false", peak);
}

// 7. Smooth changes: a 440 Hz sine under the ceiling while Lookahead moves
// (the delay crossfades instead of jumping), and a loud sine while Mode
// switches (the stage crossfades). The largest step between samples, against
// the steady signal's.
float MaxStep(const float *x, uint32_t from, uint32_t to) {
  float m = 0.0f;
  for (uint32_t i = from + 1; i < to; ++i) m = fmaxf(m, fabsf(x[2 * i] - x[2 * (i - 1)]));
  return m;
}

void Smooth() {
  const uint32_t total = kRate, at = 22050;
  // Lookahead 2 -> 4.5 ms.
  {
    void *self = Make(kRate, 0);
    Set(self, "Ceiling", 0.0f);
    for (uint32_t i = 0; i < total; ++i) {
      g_out[2 * i] = g_out[2 * i + 1] = 0.5f * static_cast<float>(sin(2 * M_PI * 440.0 * i / kRate));
    }
    for (uint32_t pos = 0; pos < total; pos += 64) {
      if (pos == at - at % 64) Set(self, "Lookahead", 4.5f);
      E.render(self, &g_out[2 * pos], 64 < total - pos ? 64 : total - pos);
    }
    E.destroy(self);
    const uint32_t d = Frames(4.5f, kRate);
    bool exact_after = true;
    for (uint32_t i = at + 1000; i < total; ++i) {
      const float want = 0.5f * static_cast<float>(sin(2 * M_PI * 440.0 * (i - d) / kRate));
      if (g_out[2 * i] != want) exact_after = false;
    }
    printf("\"lookahead_move\":{\"steady_step\":%.6f,\"moving_step\":%.6f,\"exact_after\":%s}",
           MaxStep(g_out, 1000, at - 64), MaxStep(g_out, at - 64, at + 1000),
           exact_after ? "true" : "false");
  }
  // Mode BRICKWALL -> SOFT CLIP -> BRICKWALL on a loud sine.
  {
    void *self = Make(kRate, 0);
    Set(self, "Ceiling", -3.0f);
    for (uint32_t i = 0; i < total; ++i) {
      g_out[2 * i] = g_out[2 * i + 1] = 2.0f * static_cast<float>(sin(2 * M_PI * 440.0 * i / kRate));
    }
    for (uint32_t pos = 0; pos < total; pos += 64) {
      if (pos == 11008) Set(self, "Mode", 1.0f);
      if (pos == 33024) Set(self, "Mode", 0.0f);
      E.render(self, &g_out[2 * pos], 64 < total - pos ? 64 : total - pos);
    }
    E.destroy(self);
    printf(",\"mode_move\":{\"steady_step\":%.6f,\"moving_step\":%.6f,\"peak\":%.6f}",
           fmaxf(MaxStep(g_out, 4000, 11000), MaxStep(g_out, 23000, 33000)),
           fmaxf(MaxStep(g_out, 11000, 12000), MaxStep(g_out, 33000, 34000)),
           [] { float m = 0; for (uint32_t i = 0; i < 2 * 44118; ++i) m = fmaxf(m, fabsf(g_out[i])); return m; }());
  }
}

// 8. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while hostile input plays (with NaN and infinities in it), for 20 s.
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
    for (uint32_t i = 0; i < n; ++i) {
      const uint32_t kind = rng.Next() % 64;
      float x = 2.0f * rng.Bipolar();
      if (kind == 0) x = NAN;
      else if (kind == 1) x = (rng.Next() & 1) ? INFINITY : -INFINITY;
      else if (kind == 2) x = 1e30f;
      buf[2 * i] = x;
      buf[2 * i + 1] = kind < 8 ? -x : 0.3f * rng.Bipolar();
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < 2 * n; ++i) {
      if (!(fabsf(buf[i]) <= 3.4e38f)) ++nonfinite;
      else if (fabsf(buf[i]) > peak) peak = fabsf(buf[i]);
    }
    samples += n;
  }
  E.destroy(self);
  printf("\"sweep\":{\"samples\":%llu,\"nonfinite\":%llu,\"peak\":%.6f}",
         static_cast<unsigned long long>(samples), static_cast<unsigned long long>(nonfinite),
         peak);
}

// 9. Silence in, every parameter away from its default: exact zeros.
void Silence() {
  void *self = Make(kRate, 0xFF);
  Set(self, "Ceiling", -9.0f);
  Set(self, "Drive", 24.0f);
  Set(self, "Release", 3.0f);
  Set(self, "Lookahead", 0.0f);
  Set(self, "Mode", 1.0f);
  Set(self, "Link", 0.4f);
  Set(self, "Mix", 0.7f);
  float buf[128], peak = 0.0f;
  for (int b = 0; b < 2000; ++b) {
    memset(buf, 0, sizeof(buf));
    if (b == 700) Set(self, "Lookahead", 3.0f);
    if (b == 1400) Set(self, "Mode", 0.0f);
    E.render(self, buf, 64);
    for (int i = 0; i < 128; ++i) peak = fmaxf(peak, fabsf(buf[i]));
  }
  E.destroy(self);
  printf("\"silence\":{\"peak\":%.9g}", peak);
}

// 10. Host rates (refused outside 8 kHz..384 kHz and when not a number) and
// the instance size at each.
void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 44118.0f, 48000.0f, 96000.0f, 102000.0f,
                          192000.0f, 384000.0f, 400000.0f, NAN, INFINITY, -44118.0f };
  printf("\"rates\":[");
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    fm1_host_t host = { FM1_ENGINE_API_VERSION, rates[i], 64 };
    const size_t bytes = E.instance_size(&host);
    void *self = Make(rates[i], 0);
    printf("%s[\"%g\",%s,%zu]", i ? "," : "", rates[i], self ? "true" : "false", bytes);
    if (self) E.destroy(self);
  }
  printf("]");
}

}  // namespace

int main() {
  printf("{");
  Rates(); printf(",");
  Latency(); printf(",");
  Transparency(); printf(",");
  Release(); printf(",");
  Link(); printf(",");
  Changes(); printf(",");
  Smooth(); printf(",");
  Silence(); printf(",");
  Sweep(); printf(",");
  Ceiling();
  printf("}\n");
  return 0;
}
