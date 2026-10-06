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
extern "C" float fm1_limit_probe_stage;

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
  double worst[3][2] = { { 0, 0 }, { 0, 0 }, { 0, 0 } };   // [mode][lookahead 0 or not]
  float envelope = 0.0f;   // BRICKWALL with a lookahead: |u x a| / c before the clamp
  float peak_at_0db = 0.0f;
  uint64_t over = 0, frames_checked = 0;
  int runs = 0;
  float buf[128];
  const uint32_t total = static_cast<uint32_t>(0.25f * kRate);
  for (int mode = 0; mode < 3; ++mode) {
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
         "\"round\":%.9g,\"round_zero\":%.9g,\"envelope\":%.9g}",
         runs, static_cast<unsigned long long>(frames_checked),
         static_cast<unsigned long long>(over), peak_at_0db, worst[0][0], worst[0][1],
         worst[1][0], worst[1][1], worst[2][0], worst[2][1], envelope);
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
    { "round", { 0.0f, 0.0f, 100.0f, 2.0f, 2.0f, 1.0f, 1.0f }, 0.999f },
    { "round-minus6", { -6.0f, 0.0f, 100.0f, 5.0f, 2.0f, 0.0f, 1.0f }, 0.5f },
    { "round-zero", { 0.0f, 0.0f, 100.0f, 0.0f, 2.0f, 1.0f, 1.0f }, 0.999f },
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
  // Mode BRICKWALL -> ROUND -> SOFT CLIP -> ROUND -> BRICKWALL on the same
  // sine: each held for a quarter of a second, the steps measured over the
  // 1,000 frames after each change against the steady ones before them.
  {
    void *self = Make(kRate, 0);
    Set(self, "Ceiling", -3.0f);
    for (uint32_t i = 0; i < total; ++i) {
      g_out[2 * i] = g_out[2 * i + 1] = 2.0f * static_cast<float>(sin(2 * M_PI * 440.0 * i / kRate));
    }
    const uint32_t at[4] = { 8832, 17664, 26496, 35328 };
    const float to[4] = { 2.0f, 1.0f, 2.0f, 0.0f };
    for (uint32_t pos = 0; pos < total; pos += 64) {
      for (int k = 0; k < 4; ++k) {
        if (pos == at[k]) Set(self, "Mode", to[k]);
      }
      E.render(self, &g_out[2 * pos], 64 < total - pos ? 64 : total - pos);
    }
    E.destroy(self);
    float steady = MaxStep(g_out, 4000, at[0]), moving = 0.0f;
    for (int k = 0; k < 4; ++k) {
      moving = fmaxf(moving, MaxStep(g_out, at[k], at[k] + 1000));
      if (k < 3) steady = fmaxf(steady, MaxStep(g_out, at[k] + 2000, at[k + 1]));
    }
    float peak = 0.0f;
    for (uint32_t i = 0; i < 2 * total; ++i) peak = fmaxf(peak, fabsf(g_out[i]));
    printf(",\"round_move\":{\"steady_step\":%.6f,\"moving_step\":%.6f,\"peak\":%.6f}",
           steady, moving, peak);
  }
}

// 11. Lookahead and Mode modulated: changed every third block (4.4 ms, under
// the 5 ms crossfade, so changes also queue) while a 440 Hz sine swells and
// fades between 0.3 and 2.0 with raised-cosine ramps (1-10 ms) into a -6 dB
// ceiling with Drive +6 dB, so the gain is often ramping when a change
// lands. The largest step between samples, against the largest with the
// control held at each of several values over the same input, from the
// start (its own release and attack included); a crossfade between two
// outputs within the ceiling c can add at most 2c / 220 to a step. Six
// inputs per case. Before each tap of a Lookahead crossfade had a gain path
// of its own (2026-10-02), a shorter lookahead restarted the shared boxes
// at the held gain, and changes to and from 0 swapped envelopes: steps of
// up to 8 times the held ones.
const uint32_t kModFrames = 64 * 2068;   // 3 s at 44,118 Hz, whole blocks
float g_mod_in[2 * kModFrames], g_mod_out[2 * kModFrames];

void ModInput(uint32_t seed) {
  Lcg r = { seed };
  float amp = 0.3f, from = 0.3f, target = 2.0f;
  uint32_t left = 0, ramp = 0, ramp_len = 1;
  for (uint32_t i = 0; i < kModFrames; ++i) {
    if (left == 0) {
      from = amp;
      target = (r.Next() & 1) ? 2.0f : 0.3f;
      ramp_len = 50 + r.Next() % 400;
      ramp = 0;
      left = ramp_len + 200 + r.Next() % 2000;
    }
    if (ramp < ramp_len) {
      const double t = static_cast<double>(ramp) / ramp_len;
      amp = from + (target - from) * static_cast<float>(0.5 * (1.0 - cos(M_PI * t)));
      ++ramp;
    }
    --left;
    g_mod_in[2 * i] = g_mod_in[2 * i + 1] = amp * static_cast<float>(sin(2 * M_PI * 440.0 * i / kRate));
  }
}

// kind 0: Lookahead held at `value`, Mode at `mode`. 1: Lookahead 1-5 ms every
// third block. 2: Lookahead 0-5 ms (0 one time in five). 3: Mode every third
// block. 4: Mode every 64th block (93 ms: its glide completes). 5: Lookahead (0-5)
// and Mode together, every second block. 6, 7 and 8: as 3, 4 and 5 with
// ROUND among the Modes (in turn, and at random in 8).
float ModRun(int kind, float value, float mode, uint32_t seed, float *out_peak) {
  void *self = Make(kRate, 0x77);
  Set(self, "Ceiling", -6.0f);
  Set(self, "Drive", 6.0f);
  Set(self, "Release", 30.0f);
  Set(self, "Lookahead", kind == 0 ? value : 2.0f);
  Set(self, "Mode", mode);
  memcpy(g_mod_out, g_mod_in, sizeof(g_mod_out));
  Lcg r = { seed * 7u + 3u };
  for (uint32_t pos = 0, block = 0; pos < kModFrames; pos += 64, ++block) {
    if ((kind == 1 || kind == 2) && block % 3 == 0) {
      Set(self, "Lookahead", kind == 1 ? 1.0f + 4.0f * r.Unit()
                                       : (r.Next() % 5 == 0 ? 0.0f : 5.0f * r.Unit()));
    }
    if (kind == 3 && block % 3 == 0) Set(self, "Mode", static_cast<float>((block / 3) & 1));
    if (kind == 4 && block % 64 == 0) Set(self, "Mode", static_cast<float>((block / 64) & 1));
    if (kind == 5 && block % 2 == 0) {
      Set(self, "Lookahead", r.Next() % 5 == 0 ? 0.0f : 5.0f * r.Unit());
      Set(self, "Mode", static_cast<float>(r.Next() & 1));
    }
    if (kind == 6 && block % 3 == 0) Set(self, "Mode", static_cast<float>((block / 3) % 3));
    if (kind == 7 && block % 64 == 0) Set(self, "Mode", static_cast<float>((block / 64) % 3));
    if (kind == 8 && block % 2 == 0) {
      Set(self, "Lookahead", r.Next() % 5 == 0 ? 0.0f : 5.0f * r.Unit());
      Set(self, "Mode", static_cast<float>(r.Next() % 3));
    }
    E.render(self, &g_mod_out[2 * pos], 64);
  }
  E.destroy(self);
  float peak = 0.0f;
  for (uint32_t i = 0; i < 2 * kModFrames; ++i) peak = fmaxf(peak, fabsf(g_mod_out[i]));
  *out_peak = peak;
  return MaxStep(g_mod_out, 0, kModFrames);
}

void Modulated() {
  const char *names[] = { "", "lookahead", "lookahead0", "mode", "mode_slow", "both",
                          "mode3", "mode3_slow", "both3" };
  const float held_la[] = { 1.0f, 2.0f, 3.5f, 5.0f };
  const float held_la0[] = { 0.0f, 0.1f, 0.5f, 1.0f, 2.5f, 5.0f };
  const double c = pow(10.0, -6.0 / 20.0);
  printf("\"modulated\":{");
  fm1_limit_probe_worst = fm1_limit_probe_stage = 0.0f;
  float peak_all = 0.0f;
  for (int kind = 1; kind <= 8; ++kind) {
    float worst_ratio = 0.0f, moving_max = 0.0f, steady_max = 0.0f;
    for (uint32_t seed = 1; seed <= 6; ++seed) {
      ModInput(seed);
      float peak, steady = 0.0f;
      const bool la = kind == 1, la0 = kind == 2 || kind == 5 || kind == 8;
      const int n_la = la ? 4 : (la0 ? 6 : 1);
      const int n_mode = kind >= 6 ? 3 : (kind >= 3 ? 2 : 1);
      for (int a = 0; a < n_la; ++a) {
        for (int m = 0; m < n_mode; ++m) {
          const float v = la ? held_la[a] : (la0 ? held_la0[a] : 2.0f);
          steady = fmaxf(steady, ModRun(0, v, static_cast<float>(m), seed, &peak));
        }
      }
      const float moving = ModRun(kind, 0.0f, 0.0f, seed, &peak);
      peak_all = fmaxf(peak_all, peak);
      const float allowance = static_cast<float>(2.0 * c / 220.0);
      worst_ratio = fmaxf(worst_ratio, (moving - steady) / allowance);
      moving_max = fmaxf(moving_max, moving);
      steady_max = fmaxf(steady_max, steady);
    }
    printf("%s\"%s\":{\"excess\":%.4f,\"moving\":%.6f,\"steady\":%.6f}", kind > 1 ? "," : "",
           names[kind], worst_ratio, moving_max, steady_max);
  }
  printf(",\"peak\":%.9g,\"envelope\":%.9g,\"stage\":%.9g}", peak_all / c,
         fm1_limit_probe_worst, fm1_limit_probe_stage);
}

// 12. ROUND against ClipOnly2's recurrence, written out here in double from
// its published code (Airwindows, MIT; engines/README.md, "Limiter"), with
// the ceiling at 0 dB (c = 1 exactly) and Drive 0: a 440 Hz sine of 1.25
// (+1.9 dB) with noise of 0.05 on it, both channels, so every peak is over
// the ceiling and under ROUND's 3 dB of headroom, where the envelope does
// nothing and the gain is exactly 1. With a lookahead the output is
// ClipOnly2 of the input, delayed by the lookahead and by nothing more
// (ClipOnly2's own one-sample delay is taken up by looking one frame ahead);
// at Lookahead 0 it is the causal form, each frame its own replaced or
// passed value. Reported: the largest difference from the recurrence, the
// frames over the ceiling, whether every other frame came out bit for bit,
// and the largest |output|.
struct ClipRef {
  double last;
  bool pos, neg;
  // Feeds x; returns the value for the frame before it (ClipOnly2's output).
  double Step(double x) {
    const double h = 0.7390851332, sft = 0.2609148668;
    if (x > 4.0) x = 4.0;
    if (x < -4.0) x = -4.0;
    if (pos) last = x < last ? h + x * sft : sft + last * h;
    pos = false;
    if (x > 1.0) { pos = true; x = h + last * sft; }
    if (neg) last = x > last ? -h + x * sft : -sft + last * h;
    neg = false;
    if (x < -1.0) { neg = true; x = -h + last * sft; }
    const double out = last;
    last = x;
    return out;
  }
};

void RoundCheck() {
  const uint32_t total = 22050;
  Lcg rng = { 41u };
  for (uint32_t i = 0; i < total; ++i) {
    const float x = 1.25f * static_cast<float>(sin(2 * M_PI * 440.0 * i / kRate)) + 0.05f * rng.Bipolar();
    g_in[2 * i] = x;
    g_in[2 * i + 1] = -x;
  }
  printf("\"round\":{");
  const float looks[] = { 2.0f, 0.02f, 5.0f, 0.0f };
  for (int k = 0; k < 4; ++k) {
    void *self = Make(kRate, 0x33);
    Set(self, "Ceiling", 0.0f);
    Set(self, "Mode", 2.0f);
    Set(self, "Lookahead", looks[k]);
    memcpy(g_out, g_in, 2 * total * sizeof(float));
    RenderAll(self, g_out, total, 29);
    E.destroy(self);
    const uint32_t d = Frames(looks[k], kRate);
    ClipRef ref[2] = { { 0.0, false, false }, { 0.0, false, false } };
    double diff = 0.0, peak = 0.0;
    uint32_t over = 0;
    bool others_exact = true;
    for (uint32_t i = 0; i + 1 < total; ++i) {
      for (int c = 0; c < 2; ++c) {
        // The frame the effect gives out at step i + d: input frame i.
        double want;
        if (d > 0) {
          if (i == 0) ref[c].Step(g_in[c]);                    // the first frame's look
          want = ref[c].Step(g_in[2 * (i + 1) + c]);           // ...gives frame i out
        } else {
          ref[c].Step(g_in[2 * i + c]);
          want = ref[c].last;                                  // the causal form
        }
        if (i + d >= total) continue;
        const float got = g_out[2 * (i + d) + c];
        diff = fmax(diff, fabs(got - want));
        peak = fmax(peak, fabs(static_cast<double>(got)));
        if (fabsf(g_in[2 * i + c]) > 1.0f) ++over;
        else if (got != g_in[2 * i + c]) others_exact = false;
      }
    }
    printf("%s\"%g\":{\"diff\":%.3g,\"over\":%u,\"others_exact\":%s,\"peak\":%.9g}",
           k ? "," : "", looks[k], diff, over, others_exact ? "true" : "false", peak);
  }
  printf("}");
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

// 10. Lookahead, Mode and Link turned while the limiter works: loud bursts
// over a moderate bed, in random host blocks, at four host rates, with
// Lookahead jumping anywhere in 0..5 ms (0 included), Mode flipping and Link
// moving. The ceiling must come from the gain path and the stage, never from
// the final clamp: the largest |v| / c before it (BRICKWALL) and the largest
// stage output / c (either Mode, gliding included), with a lookahead, and
// the largest output / 10^(Ceiling/20). Then the same steady limiting (a
// 440 Hz sine at +12 dB into -6 dB) while Lookahead moves 2 -> 4.5 -> 1 ms:
// the largest step between samples against the steady signal's.
void Knobs() {
  const float rates[] = { 8000.0f, 44118.0f, 96000.0f, 384000.0f };
  float envelope = 0.0f, stage = 0.0f;
  double out = 0.0;
  uint32_t changes = 0;
  float buf[128];
  for (float rate : rates) {
    for (uint32_t seed = 1; seed <= 25; ++seed) {
      void *self = Make(rate, 0x5A);
      Lcg rng = { 1000u + seed };
      const float ceiling = -24.0f * rng.Unit();
      const double c = pow(10.0, ceiling / 20.0);
      Set(self, "Ceiling", ceiling);
      Set(self, "Drive", -12.0f + 36.0f * rng.Unit());
      Set(self, "Release", 1.0f + 200.0f * rng.Unit());
      fm1_limit_probe_worst = fm1_limit_probe_stage = 0.0f;
      const uint32_t total = static_cast<uint32_t>(1.5f * rate);
      for (uint32_t pos = 0; pos < total;) {
        const uint32_t k = rng.Next() % 24;
        if (k == 0) {
          Set(self, "Lookahead", (rng.Next() & 3) == 0 ? 0.0f : 5.0f * rng.Unit());
          ++changes;
        }
        if (k == 1) Set(self, "Mode", static_cast<float>(rng.Next() & 1));
        if (k == 2) Set(self, "Link", rng.Unit());
        uint32_t n = 1 + rng.Next() % 64;
        if (n > total - pos) n = total - pos;
        for (uint32_t i = 0; i < n; ++i) {
          const float amp = rng.Next() % 200 == 0 ? 16.0f : ((rng.Next() & 1) ? 0.3f : 2.0f);
          buf[2 * i] = amp * rng.Bipolar();
          buf[2 * i + 1] = (rng.Next() & 3) ? buf[2 * i] : amp * rng.Bipolar();
        }
        E.render(self, buf, n);
        for (uint32_t i = 0; i < 2 * n; ++i) out = fmax(out, fabs(buf[i]) / c);
        pos += n;
      }
      E.destroy(self);
      envelope = fmaxf(envelope, fm1_limit_probe_worst);
      stage = fmaxf(stage, fm1_limit_probe_stage);
    }
  }
  printf("\"knobs\":{\"changes\":%u,\"envelope\":%.9g,\"stage\":%.9g,\"out\":%.9g",
         changes, envelope, stage, out);
  const uint32_t total = kRate;
  void *self = Make(kRate, 0);
  Set(self, "Ceiling", -6.0f);
  for (uint32_t i = 0; i < total; ++i) {
    g_out[2 * i] = g_out[2 * i + 1] = 2.0f * static_cast<float>(sin(2 * M_PI * 440.0 * i / kRate));
  }
  for (uint32_t pos = 0; pos < total; pos += 64) {
    if (pos == 11008) Set(self, "Lookahead", 4.5f);
    if (pos == 22016) Set(self, "Lookahead", 1.0f);
    E.render(self, &g_out[2 * pos], 64 < total - pos ? 64 : total - pos);
  }
  E.destroy(self);
  printf(",\"steady_step\":%.6f,\"moving_step\":%.6f}",
         MaxStep(g_out, 4000, 11000),
         fmaxf(MaxStep(g_out, 11000, 12500), MaxStep(g_out, 22000, 23500)));
}

int main() {
  printf("{");
  Knobs(); printf(",");
  Rates(); printf(",");
  Latency(); printf(",");
  Transparency(); printf(",");
  Release(); printf(",");
  Link(); printf(",");
  Changes(); printf(",");
  Smooth(); printf(",");
  Modulated(); printf(",");
  RoundCheck(); printf(",");
  Silence(); printf(",");
  Sweep(); printf(",");
  Ceiling();
  printf("}\n");
  return 0;
}
