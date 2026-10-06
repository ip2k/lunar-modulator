// squash_test.cc -- fm1-squash-test: drives Squash (src/fx_squash.cc) and
// Transient (src/fx_shaper.cc) through their engine structs where fm1-render
// cannot: float output, frame by frame.
//
//   - oracle: each Type on the reference signals, decimated, for
//     tests/test_engines_squash.py to compare against the upstream renders
//     in tests/fixtures/squash-oracle.json (the Airwindows loops in double,
//     run in a container: engines/third_party/airwindows/oracle/), and the
//     Limiter's Round mode against ClipOnly2 the same way;
//   - the contracts: silence, block sizes and memory fills while parameters
//     and Types change, hostile input, host rates;
//   - what each knob does: Squash's reduction per Type, Snap's gate, Mu and
//     Snap never lifting, Split's lift, Type changes starting from the gain
//     in force; Transient's centre bit for bit, its attack and sustain on a
//     drum hit, a steady tone left alone;
//   - with --cost, ns per 64-frame block.
//
// With --dump DIR it writes the reference signals (interleaved stereo
// float32, 44,100 Hz) and the cases for the oracle and exits; with --ours
// DIR, its own full renders of the cases. Prints one JSON object
// otherwise. A desktop tool: it allocates and prints. MIT licence.

#include "fm1_engine.h"

#include <chrono>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <vector>

extern "C" const fm1_engine_t fm1_engine_squash, fm1_engine_shaper, fm1_engine_limit;

// The values this file computes (parameter schedules, test signals) must be
// the same on every build for the pinned hashes to mean anything: no fused
// multiply-adds here either (Apple clang on arm64 fuses by default).
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

namespace {

alignas(16) unsigned char g_mem[2][1 << 15];

struct Lcg {
  uint32_t s;
  uint32_t Next() { s = s * 1664525u + 1013904223u; return s; }
  float Bipolar() { return static_cast<int32_t>(Next()) / 2147483648.0f; }  // [-1, 1)
  float Unit() { return (Next() >> 8) / 16777216.0f; }                        // [0, 1)
};

struct Kv { const char *name; float value; };

void *Make(const fm1_engine_t &e, float rate, int fill, int slot = 0) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  const size_t n = e.instance_size(&host);
  if (n > sizeof(g_mem[slot])) return NULL;
  memset(g_mem[slot], fill, sizeof(g_mem[slot]));
  return e.create(g_mem[slot], &host);
}

int Index(const fm1_engine_t &e, const char *name) {
  for (uint16_t i = 0; i < e.n_params; ++i) {
    if (strcmp(e.params[i].name, name) == 0) return i;
  }
  fprintf(stderr, "no parameter %s\n", name);
  exit(1);
}

void Set(const fm1_engine_t &e, void *self, const char *name, float v) {
  e.set_param(self, static_cast<uint16_t>(Index(e, name)), v);
}

void SetAll(const fm1_engine_t &e, void *self, const Kv *kv, int n) {
  for (int i = 0; i < n; ++i) Set(e, self, kv[i].name, kv[i].value);
}

// Render a stereo buffer in place in blocks of `block` frames (0: random 1-64).
void RenderAll(const fm1_engine_t &e, void *self, float *buf, uint32_t frames, uint32_t block,
               uint32_t seed = 9u) {
  Lcg rng = { seed };
  for (uint32_t pos = 0; pos < frames;) {
    uint32_t n = block ? block : 1 + rng.Next() % 64;
    if (n > frames - pos) n = frames - pos;
    e.render(self, buf + 2 * pos, n);
    pos += n;
  }
}

uint32_t Hash(const float *x, size_t n) {    // FNV-1a over the bits
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < n; ++i) {
    uint32_t b;
    memcpy(&b, &x[i], 4);
    for (int k = 0; k < 4; ++k) {
      h ^= (b >> (8 * k)) & 0xFFu;
      h *= 16777619u;
    }
  }
  return h;
}

// --- the reference signals (44,100 Hz, 1.5 s) ---------------------------------

const float kOracleRate = 44100.0f;
const uint32_t kOracleFrames = 66150;

// 0 "drums": a kick (80 Hz, 120 ms decay) and a snare (noise and 180 Hz,
// 60 ms) every 0.25 s at changing levels over a quiet bed; the right channel
// 0.8 of the left plus its own noise. 1 "steps": a 220 Hz sine whose level
// steps through 0.03, 0.3, 0.9, 0.1, 0.6 and 0.01 every 0.25 s, the right a
// quarter-cycle behind. 2 "hot": 110 Hz and 1.7 kHz, peaks up to 1.3.
void MakeSignal(int k, std::vector<float> &out) {
  out.assign(2 * kOracleFrames, 0.0f);
  Lcg rng = { 1234u + 77u * static_cast<uint32_t>(k) };
  const double fs = kOracleRate;
  for (uint32_t i = 0; i < kOracleFrames; ++i) {
    const double t = i / fs;
    double l = 0.0, r = 0.0;
    if (k == 0) {
      const uint32_t hit = i / 11025, at = i % 11025;
      const double ta = at / fs;
      const double level = 0.25 + 0.65 * ((hit * 7) % 5) / 4.0;
      const float n1 = rng.Bipolar(), n2 = rng.Bipolar();
      if (hit % 2 == 0) {
        l = level * exp(-ta / 0.12) * sin(2 * M_PI * 80.0 * ta);
      } else {
        l = level * exp(-ta / 0.06) * (0.6 * n1 + 0.4 * sin(2 * M_PI * 180.0 * ta));
      }
      l += 0.01 * n2;
      r = 0.8 * l + 0.05 * rng.Bipolar();
    } else if (k == 1) {
      const double lv[6] = { 0.03, 0.3, 0.9, 0.1, 0.6, 0.01 };
      const double a = lv[(i / 11025) % 6];
      l = a * sin(2 * M_PI * 220.0 * t);
      r = a * sin(2 * M_PI * 220.0 * t - M_PI / 2);
    } else {
      const double env = 0.55 + 0.45 * sin(2 * M_PI * 1.3 * t);
      l = 1.3 * env * (0.7 * sin(2 * M_PI * 110.0 * t) + 0.3 * sin(2 * M_PI * 1700.0 * t));
      r = -0.9 * l;
    }
    out[2 * i] = static_cast<float>(l);
    out[2 * i + 1] = static_cast<float>(r);
  }
}

// The oracle cases: what the upstream renders were made with
// (run-on-aeon.sh), and the same as Squash's knobs (the mappings in
// fx_squash.cc's header).
struct OracleCase {
  const char *name, *kind;
  int signal;
  double k[8];
};

const OracleCase kCases[] = {
  { "snap_a", "pop3", 0, { 0.5, 0.5, 0.5, 0.5, 0.3, 0.5, 0.5, 0.5 } },
  { "snap_b", "pop3", 1, { 0.25, 0.9, 0.1, 0.8, 0.0, 0.5, 0.5, 0.5 } },
  { "snap_c", "pop3", 0, { 0.7, 1.0, 0.0, 0.2, 0.45, 1.0, 0.0, 0.1 } },
  { "mu_a", "pressure4", 0, { 0.5, 0.2, 1.0 } },
  { "mu_b", "pressure4", 1, { 0.8, 0.6, 0.2 } },
  { "split_a", "buttercomp2", 0, { 0.5, 0.5, 1.0 } },
  { "split_b", "buttercomp2", 1, { 1.0, 0.4, 0.6 } },
  { "round", "clip", 2, { 0 } },
};
const int kNumCases = sizeof(kCases) / sizeof(kCases[0]);
const uint32_t kDecimate = 61;             // every 61st frame goes in the fixture

// Our render of an oracle case, at 44,100 Hz, full length.
void OurRender(const OracleCase &c, std::vector<float> &io) {
  std::vector<float> in;
  MakeSignal(c.signal, in);
  io = in;
  const double *k = c.k;
  if (strcmp(c.kind, "clip") == 0) {
    // The Limiter, Mode Round, its ceiling at ClipOnly2's 0.9549925859 and a
    // 2 ms lookahead: its output, d frames late, is ClipOnly2's, 1 late.
    const fm1_engine_t &e = fm1_engine_limit;
    void *self = Make(e, kOracleRate, 0);
    Set(e, self, "Mode", 2.0f);
    Set(e, self, "Ceiling", static_cast<float>(20.0 * log10(0.9549925859)));
    Set(e, self, "Lookahead", 2.0f);
    RenderAll(e, self, io.data(), kOracleFrames, 64);
    e.destroy(self);
    const uint32_t d = static_cast<uint32_t>(floor(2.0 * 0.001 * kOracleRate + 0.5));
    std::vector<float> shifted(io.size(), 0.0f);    // our frame i + d is the oracle's i + 1
    for (uint32_t i = 0; i + d < kOracleFrames; ++i) {
      if (i + 1 < kOracleFrames) {
        shifted[2 * (i + 1)] = io[2 * (i + d)];
        shifted[2 * (i + 1) + 1] = io[2 * (i + d) + 1];
      }
    }
    io = shifted;
    return;
  }
  const fm1_engine_t &e = fm1_engine_squash;
  void *self = Make(e, kOracleRate, 0);
  if (strcmp(c.kind, "pop3") == 0) {
    const Kv kv[] = {
      { "Type", 0.0f }, { "Squash", static_cast<float>(1.0 - k[0]) },
      { "Ratio", static_cast<float>(k[1]) },
      { "Attack", static_cast<float>((pow(k[2], 3) * 5000.0 + 500.0) / 44.1) },
      { "Release", static_cast<float>((pow(k[3], 5) * 50000.0 + 500.0) / 44.1) },
      { "Gate", k[4] > 0.0 ? static_cast<float>(80.0 * log10(k[4])) : -80.0f },
      { "Gate Depth", static_cast<float>(k[5]) }, { "Hold", static_cast<float>(k[6]) },
      { "Gate Rel", static_cast<float>((pow(k[7], 5) * 500000.0 + 500.0) / 44.1) } };
    SetAll(e, self, kv, 9);
  } else if (strcmp(c.kind, "pressure4") == 0) {
    const Kv kv[] = {
      { "Type", 1.0f }, { "Squash", static_cast<float>(k[0]) },
      { "Release", static_cast<float>(pow(1.28 - k[1], 5) * 32768.0 / 44.1) },
      { "Shape", static_cast<float>(2.0 * k[2] - 1.0) } };
    SetAll(e, self, kv, 4);
  } else {
    const Kv kv[] = {
      { "Type", 2.0f }, { "Squash", static_cast<float>(k[0]) },
      { "Output", static_cast<float>(20.0 * log10(2.0 * k[1])) },
      { "Mix", static_cast<float>(k[2]) } };
    SetAll(e, self, kv, 4);
  }
  RenderAll(e, self, io.data(), kOracleFrames, 64);
  e.destroy(self);
}

void Dump(const char *dir) {
  for (int k = 0; k < 3; ++k) {
    std::vector<float> s;
    MakeSignal(k, s);
    char path[1024];
    snprintf(path, sizeof path, "%s/sig%d.f32", dir, k);
    FILE *f = fopen(path, "wb");
    if (!f) { perror(path); exit(1); }
    fwrite(s.data(), sizeof(float), s.size(), f);
    fclose(f);
  }
  // The cases, for the runner: name kind signal A..H.
  char path[1024];
  snprintf(path, sizeof path, "%s/cases.txt", dir);
  FILE *f = fopen(path, "w");
  for (int c = 0; c < kNumCases; ++c) {
    fprintf(f, "%s %s %d", kCases[c].name, kCases[c].kind, kCases[c].signal);
    for (int j = 0; j < 8; ++j) fprintf(f, " %.17g", kCases[c].k[j]);
    fprintf(f, "\n");
  }
  fclose(f);
}

void Oracle() {
  printf("\"oracle\":{\"decimate\":%u", kDecimate);
  for (int c = 0; c < kNumCases; ++c) {
    std::vector<float> io;
    OurRender(kCases[c], io);
    printf(",\"%s\":[", kCases[c].name);
    for (uint32_t i = 0, n = 0; i < kOracleFrames; i += kDecimate, ++n) {
      printf("%s%.9g,%.9g", n ? "," : "", io[2 * i], io[2 * i + 1]);
    }
    printf("]");
  }
  printf("}");
}

// --- the contracts --------------------------------------------------------------

const float kRate = 44118.0f;

// Settings that put every Type and Transient through everything they have.
struct Busy { const fm1_engine_t *e; Kv kv[12]; int n; };

const Busy kBusy[] = {
  { &fm1_engine_squash, { { "Type", 0 }, { "Squash", 0.7f }, { "Attack", 3 }, { "Release", 80 },
                          { "Ratio", 0.8f }, { "Output", 6 }, { "Mix", 0.8f }, { "Gate", -30 },
                          { "Gate Depth", 0.9f }, { "Hold", 0.2f }, { "Gate Rel", 40 } }, 11 },
  { &fm1_engine_squash, { { "Type", 1 }, { "Squash", 0.9f }, { "Release", 200 }, { "Shape", -0.6f },
                          { "Output", 12 }, { "Mix", 0.7f } }, 6 },
  { &fm1_engine_squash, { { "Type", 2 }, { "Squash", 1.0f }, { "Output", -3 }, { "Mix", 0.6f } }, 4 },
  { &fm1_engine_shaper, { { "Attack", 80 }, { "Sustain", -70 }, { "Window", 8 }, { "Tail", 900 },
                          { "Output", -4 }, { "Mix", 0.8f } }, 6 },
};
const int kNumBusy = sizeof(kBusy) / sizeof(kBusy[0]);

// Noise bursts over a quiet bed, with level changes: 1 s at 44,118 Hz.
void Bursts(std::vector<float> &x, uint32_t frames, uint32_t seed) {
  x.assign(2 * frames, 0.0f);
  Lcg rng = { seed };
  for (uint32_t i = 0; i < frames; ++i) {
    const uint32_t ph = i % 9000;
    const float level = ph < 3000 ? 0.9f * (1.0f - ph / 3000.0f) : (ph < 6000 ? 0.05f : 0.3f);
    x[2 * i] = level * rng.Bipolar();
    x[2 * i + 1] = (i & 4096) ? x[2 * i] : level * rng.Bipolar();
  }
}

// Every case rendered with a schedule of parameter (and Type) changes at
// fixed frames, in blocks of 64, 1, 7 and random sizes and from memory
// filled four ways: the same bits every time; all finite.
void Contracts() {
  const uint32_t frames = 44118;
  std::vector<float> in, ref, out;
  int same = 0, tried = 0, finite = 1;
  printf("\"contracts\":[");
  for (int c = 0; c < kNumBusy; ++c) {
    const fm1_engine_t &e = *kBusy[c].e;
    Bursts(in, frames, 5u + c);
    const int fills[4] = { 0x00, 0xFF, 0xA5, 0x7F };
    const uint32_t blocks[4] = { 64, 1, 7, 0 };
    uint32_t h0 = 0;
    for (int fi = 0; fi < 4; ++fi) {
      for (int bi = 0; bi < 4; ++bi) {
        void *self = Make(e, kRate, fills[fi]);
        SetAll(e, self, kBusy[c].kv, kBusy[c].n);
        out = in;
        // Changes at fixed frames: every parameter to a new value, the
        // Type round the three; rendered up to each change, then on.
        Lcg pick = { 77u };
        uint32_t pos = 0;
        Lcg rng = { 3u };
        for (uint32_t at = 2205; pos < frames; at += 2205) {
          const uint32_t stop = at < frames ? at : frames;
          while (pos < stop) {
            uint32_t n = blocks[bi] ? blocks[bi] : 1 + rng.Next() % 64;
            if (n > stop - pos) n = stop - pos;
            e.render(self, out.data() + 2 * pos, n);
            pos += n;
          }
          const fm1_param_t &p = e.params[pick.Next() % e.n_params];
          float v = p.min + (p.max - p.min) * pick.Unit();
          if (pick.Next() % 7 == 0) v = NAN;
          e.set_param(self, static_cast<uint16_t>(&p - e.params), v);
        }
        e.destroy(self);
        for (float v : out) {
          if (!(fabsf(v) <= 1e6f)) finite = 0;
        }
        const uint32_t h = Hash(out.data(), out.size());
        if (fi == 0 && bi == 0) h0 = h;
        else { ++tried; if (h == h0) ++same; }
      }
    }
    printf("%s\"%08x\"", c ? "," : "", h0);
  }
  printf("],\"contracts_same\":%d,\"contracts_tried\":%d,\"contracts_finite\":%s",
         same, tried, finite ? "true" : "false");
}

// Silence in: exact zeros at every busy setting, through Type changes.
void Silence() {
  float peak = 0.0f;
  for (int c = 0; c < kNumBusy; ++c) {
    const fm1_engine_t &e = *kBusy[c].e;
    void *self = Make(e, kRate, 0x5A);
    SetAll(e, self, kBusy[c].kv, kBusy[c].n);
    float buf[128];
    for (int b = 0; b < 1500; ++b) {
      if (b % 100 == 50 && &e == &fm1_engine_squash) Set(e, self, "Type", static_cast<float>((b / 100) % 3));
      memset(buf, 0, sizeof buf);
      e.render(self, buf, 64);
      for (float v : buf) peak = fmaxf(peak, fabsf(v));
    }
    e.destroy(self);
  }
  printf("\"silence\":{\"peak\":%.9g}", peak);
}

// Hostile input: NaN, infinities, 1e30 and huge noise for 0.3 s within 2 s
// of bursts, every busy setting: finite throughout, and the peak.
void Hostile() {
  const uint32_t frames = 2 * 44118;
  std::vector<float> in;
  float peak = 0.0f;
  int finite = 1;
  for (int c = 0; c < kNumBusy; ++c) {
    const fm1_engine_t &e = *kBusy[c].e;
    Bursts(in, frames, 11u + c);
    Lcg rng = { 17u };
    for (uint32_t i = 13000; i < 26000; ++i) {
      const uint32_t k = rng.Next() % 5;
      const float v = k == 0 ? NAN : (k == 1 ? INFINITY : (k == 2 ? -INFINITY : (k == 3 ? 1e30f : 40.0f * rng.Bipolar())));
      in[2 * i] = v;
      in[2 * i + 1] = (k & 1) ? -v : 0.1f;
    }
    void *self = Make(e, kRate, 0);
    SetAll(e, self, kBusy[c].kv, kBusy[c].n);
    RenderAll(e, self, in.data(), frames, 0);
    e.destroy(self);
    for (float v : in) {
      if (!(fabsf(v) <= 3.4e38f)) finite = 0;
      else peak = fmaxf(peak, fabsf(v));
    }
  }
  printf("\"hostile\":{\"finite\":%s,\"peak\":%.6g}", finite ? "true" : "false", peak);
}

void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 44100.0f, 44118.0f, 48000.0f, 96000.0f,
                          384000.0f, 400000.0f, NAN, INFINITY, -44118.0f };
  printf("\"rates\":[");
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    void *a = Make(fm1_engine_squash, rates[i], 0, 0);
    void *b = Make(fm1_engine_shaper, rates[i], 0, 1);
    printf("%s[\"%g\",%s,%s]", i ? "," : "", rates[i], a ? "true" : "false", b ? "true" : "false");
  }
  fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
  printf("],\"bytes\":{\"squash\":%zu,\"shaper\":%zu}", fm1_engine_squash.instance_size(&host),
         fm1_engine_shaper.instance_size(&host));
}

// --- what the knobs do ------------------------------------------------------------

// A sine of `amp` at `hz` for `frames`, both channels.
void Sine(std::vector<float> &x, uint32_t frames, float amp, double hz) {
  x.resize(2 * frames);
  for (uint32_t i = 0; i < frames; ++i) {
    x[2 * i] = x[2 * i + 1] = amp * static_cast<float>(sin(2 * M_PI * hz * i / kRate));
  }
}

double PeakDb(const std::vector<float> &x, uint32_t from, uint32_t to) {
  float p = 0.0f;
  for (uint32_t i = 2 * from; i < 2 * to; ++i) p = fmaxf(p, fabsf(x[i]));
  return 20.0 * log10(p > 1e-30f ? p : 1e-30f);
}

// Squash per Type: the settled gain (dB) on a 440 Hz sine at -6 dBFS for
// Squash 0, 0.25, 0.5, 0.75 and 1; and the largest gain anywhere on bursts
// (Snap and Mu only turn down; Split lifts by its makeup at most).
void Reduction() {
  const float squashes[] = { 0.0f, 0.25f, 0.5f, 0.75f, 1.0f };
  std::vector<float> x;
  printf("\"reduction\":[");
  for (int t = 0; t < 3; ++t) {
    printf("%s[", t ? "," : "");
    for (int k = 0; k < 5; ++k) {
      void *self = Make(fm1_engine_squash, kRate, 0);
      Set(fm1_engine_squash, self, "Type", static_cast<float>(t));
      Set(fm1_engine_squash, self, "Squash", squashes[k]);
      Set(fm1_engine_squash, self, "Release", 200.0f);
      Sine(x, 3 * 44118, 0.5f, 440.0);
      RenderAll(fm1_engine_squash, self, x.data(), 3 * 44118, 64);
      fm1_engine_squash.destroy(self);
      printf("%s%.4f", k ? "," : "", PeakDb(x, 2 * 44118, 3 * 44118) - 20.0 * log10(0.5));
    }
    printf("]");
  }
  printf("],\"most_gain\":[");
  for (int t = 0; t < 3; ++t) {
    double most = -1e9;
    for (int k = 0; k < 5; ++k) {
      std::vector<float> in;
      Bursts(in, 44118, 21u + k);
      x = in;
      void *self = Make(fm1_engine_squash, kRate, 0);
      Set(fm1_engine_squash, self, "Type", static_cast<float>(t));
      Set(fm1_engine_squash, self, "Squash", squashes[k]);
      RenderAll(fm1_engine_squash, self, x.data(), 44118, 0);
      fm1_engine_squash.destroy(self);
      for (size_t i = 0; i < x.size(); ++i) {
        if (fabsf(in[i]) > 1e-3f) most = fmax(most, 20.0 * log10(fabs(x[i] / in[i])));
      }
    }
    printf("%s%.4f", t ? "," : "", most);
  }
  printf("]");
}

// Snap's gate: 0.5 s of a -6 dBFS sine, then -50 dBFS, Gate at -30 dB, Gate
// Depth 1: the quiet part is shut after Hold and Gate Rel (the output's
// peak over its last 0.25 s), and with Gate off it passes.
void SnapGate() {
  std::vector<float> x;
  double shut = 0.0, open = 0.0;
  for (int pass = 0; pass < 2; ++pass) {
    Sine(x, 2 * 44118, 0.5f, 440.0);
    for (uint32_t i = 22059; i < 2 * 44118; ++i) {
      x[2 * i] *= 0.00632f;
      x[2 * i + 1] *= 0.00632f;
    }
    void *self = Make(fm1_engine_squash, kRate, 0);
    const Kv kv[] = { { "Squash", 0.0f }, { "Gate", pass == 0 ? -30.0f : -80.0f },
                      { "Gate Depth", 1.0f }, { "Hold", 0.0f }, { "Gate Rel", 50.0f } };
    SetAll(fm1_engine_squash, self, kv, 5);
    RenderAll(fm1_engine_squash, self, x.data(), 2 * 44118, 64);
    fm1_engine_squash.destroy(self);
    (pass == 0 ? shut : open) = PeakDb(x, 66000, 2 * 44118);
  }
  printf("\"gate\":{\"shut_db\":%.3f,\"open_db\":%.3f}", shut, open);
}

// Type changes: on a loud sine and on bursts, Squash 0.8, the Type changed
// every 2,000 frames round all three: the largest step between samples,
// against the largest with each Type held; and the largest jump in the
// output's short-term level (dB over 64 frames) across a change.
void TypeChanges() {
  const uint32_t frames = 2 * 44118;
  std::vector<float> in, x;
  double held_step = 0.0, moving_step = 0.0;
  for (int src = 0; src < 2; ++src) {
    if (src == 0) Sine(in, frames, 0.7f, 220.0);
    else Bursts(in, frames, 31u);
    for (int t = 0; t < 4; ++t) {
      x = in;
      void *self = Make(fm1_engine_squash, kRate, 0);
      Set(fm1_engine_squash, self, "Squash", 0.8f);
      Set(fm1_engine_squash, self, "Release", 120.0f);
      Set(fm1_engine_squash, self, "Type", static_cast<float>(t < 3 ? t : 0));
      for (uint32_t pos = 0; pos < frames; pos += 64) {
        if (t == 3 && pos % 1984 == 0 && pos > 0) {
          Set(fm1_engine_squash, self, "Type", static_cast<float>((pos / 1984) % 3));
        }
        fm1_engine_squash.render(self, x.data() + 2 * pos, 64 < frames - pos ? 64 : frames - pos);
      }
      fm1_engine_squash.destroy(self);
      double step = 0.0;
      for (uint32_t i = 2 * 4410 + 2; i < 2 * frames; ++i) step = fmax(step, fabs(x[i] - x[i - 2]));
      if (t < 3) held_step = fmax(held_step, step);
      else moving_step = fmax(moving_step, step);
    }
  }
  printf("\"types\":{\"held_step\":%.6f,\"moving_step\":%.6f}", held_step, moving_step);
}

// Transient: (1) the centre passes bit for bit (Attack, Sustain 0, Output 0,
// any Window, Tail and Mix); (2) on a drum hit (a 60 Hz sine with a 1 ms
// rise and a 150 ms decay, every 0.5 s at -6 dBFS): the onset's peak (first
// 10 ms) and the tail's RMS (100-300 ms after the hit) against the dry, at
// Attack +-100 % and Sustain +-100 %; (3) a steady 1 kHz sine at Attack and
// Sustain +100 %: its settled level against the dry (dB).
double Rms(const std::vector<float> &x, uint32_t from, uint32_t to) {
  double s = 0.0;
  for (uint32_t i = from; i < to; ++i) s += static_cast<double>(x[2 * i]) * x[2 * i];
  return sqrt(s / (to - from));
}

void Hits(std::vector<float> &x, uint32_t frames) {
  x.assign(2 * frames, 0.0f);
  for (uint32_t i = 0; i < frames; ++i) {
    const uint32_t at = i % 22059;
    const double t = at / kRate;
    const double env = fmin(1.0, t / 0.001) * exp(-t / 0.15);
    x[2 * i] = x[2 * i + 1] = static_cast<float>(0.5 * env * sin(2 * M_PI * 60.0 * t));
  }
}

void Shaper() {
  const fm1_engine_t &e = fm1_engine_shaper;
  std::vector<float> in, x;
  const uint32_t frames = 2 * 44118;
  Bursts(in, frames, 41u);
  bool centre = true;
  const float windows[] = { 5.0f, 20.0f, 100.0f }, mixes[] = { 1.0f, 0.37f, 0.0f };
  for (float w : windows) {
    for (float m : mixes) {
      x = in;
      void *self = Make(e, kRate, 0x11);
      const Kv kv[] = { { "Window", w }, { "Tail", 50.0f * w }, { "Mix", m } };
      SetAll(e, self, kv, 3);
      RenderAll(e, self, x.data(), frames, 0);
      e.destroy(self);
      if (memcmp(x.data(), in.data(), x.size() * sizeof(float)) != 0) centre = false;
    }
  }
  // Knobs turned away and back to the centre while it plays: exact again
  // once the ramps have landed.
  {
    x = in;
    void *self = Make(e, kRate, 0x11);
    for (uint32_t pos = 0; pos < frames; pos += 64) {
      if (pos == 6400) { Set(e, self, "Attack", 60.0f); Set(e, self, "Output", 3.0f); }
      if (pos == 12800) { Set(e, self, "Attack", 0.0f); Set(e, self, "Output", 0.0f); }
      e.render(self, x.data() + 2 * pos, 64 < frames - pos ? 64 : frames - pos);
    }
    e.destroy(self);
    if (memcmp(x.data() + 2 * 20000, in.data() + 2 * 20000, (frames - 20000) * 2 * sizeof(float)) != 0) {
      centre = false;
    }
  }
  printf("\"shaper\":{\"centre_exact\":%s", centre ? "true" : "false");
  Hits(in, frames);
  struct { const char *name; float attack, sustain; } cases[] = {
    { "attack_up", 100, 0 }, { "attack_down", -100, 0 }, { "sustain_up", 0, 100 },
    { "sustain_down", 0, -100 }, { "both", 50, -50 } };
  const uint32_t onset = 441, tail0 = 4412, tail1 = 13235;
  for (auto &c : cases) {
    x = in;
    void *self = Make(e, kRate, 0);
    Set(e, self, "Attack", c.attack);
    Set(e, self, "Sustain", c.sustain);
    RenderAll(e, self, x.data(), frames, 64);
    e.destroy(self);
    // The second hit (the first starts the followers from silence).
    const uint32_t h = 22059;
    const double on = PeakDb(x, h, h + onset) - PeakDb(in, h, h + onset);
    const double tail = 20.0 * log10(Rms(x, h + tail0, h + tail1) / Rms(in, h + tail0, h + tail1));
    float peak = 0.0f;
    for (float v : x) peak = fmaxf(peak, fabsf(v));
    printf(",\"%s\":{\"onset_db\":%.3f,\"tail_db\":%.3f,\"peak\":%.4f}", c.name, on, tail, peak);
  }
  // A steady 1 kHz sine and a 100 Hz one, both knobs +100 %.
  for (int k = 0; k < 2; ++k) {
    Sine(in, frames, 0.5f, k ? 100.0 : 1000.0);
    x = in;
    void *self = Make(e, kRate, 0);
    Set(e, self, "Attack", 100.0f);
    Set(e, self, "Sustain", 100.0f);
    RenderAll(e, self, x.data(), frames, 64);
    e.destroy(self);
    printf(",\"steady_%s_db\":%.3f", k ? "100" : "1k",
           20.0 * log10(Rms(x, 44118, frames) / Rms(in, 44118, frames)));
  }
  printf("}");
}

// --- cost --------------------------------------------------------------------------

double Cost(const fm1_engine_t &e, const Kv *kv, int n) {
  void *self = Make(e, kRate, 0);
  SetAll(e, self, kv, n);
  Lcg rng = { 3u };
  static float noise[64 * 128];
  for (int i = 0; i < 64 * 128; ++i) noise[i] = 0.5f * rng.Bipolar();
  float buf[128];
  for (int b = 0; b < 344; ++b) {
    memcpy(buf, noise + 128 * (b % 64), sizeof(buf));
    e.render(self, buf, 64);
  }
  const int blocks = 13786;
  volatile float sink = 0.0f;
  const auto t0 = std::chrono::steady_clock::now();
  for (int b = 0; b < blocks; ++b) {
    memcpy(buf, noise + 128 * (b % 64), sizeof(buf));
    e.render(self, buf, 64);
    sink = sink + buf[0];
  }
  const auto t1 = std::chrono::steady_clock::now();
  e.destroy(self);
  return std::chrono::duration<double, std::nano>(t1 - t0).count() / blocks;
}

void Costs() {
  const Kv snap[] = { { "Type", 0 }, { "Gate", -40 } }, mu[] = { { "Type", 1 }, { "Shape", -0.5f } };
  const Kv split[] = { { "Type", 2 } }, shaper[] = { { "Attack", 50 }, { "Sustain", -50 } };
  double best[4] = { 1e30, 1e30, 1e30, 1e30 };
  for (int run = 0; run < 3; ++run) {
    best[0] = fmin(best[0], Cost(fm1_engine_squash, snap, 2));
    best[1] = fmin(best[1], Cost(fm1_engine_squash, mu, 2));
    best[2] = fmin(best[2], Cost(fm1_engine_squash, split, 1));
    best[3] = fmin(best[3], Cost(fm1_engine_shaper, shaper, 2));
  }
  printf("\"cost\":{\"snap\":%.1f,\"mu\":%.1f,\"split\":%.1f,\"shaper\":%.1f}", best[0], best[1],
         best[2], best[3]);
}

}  // namespace

int main(int argc, char **argv) {
  if (argc > 2 && strcmp(argv[1], "--dump") == 0) {
    Dump(argv[2]);
    return 0;
  }
  if (argc > 2 && strcmp(argv[1], "--ours") == 0) {   // full renders, for a residual by hand
    for (int c = 0; c < kNumCases; ++c) {
      std::vector<float> io;
      OurRender(kCases[c], io);
      char path[1024];
      snprintf(path, sizeof path, "%s/%s.ours.f32", argv[2], kCases[c].name);
      FILE *f = fopen(path, "wb");
      if (!f) { perror(path); return 1; }
      fwrite(io.data(), sizeof(float), io.size(), f);
      fclose(f);
    }
    return 0;
  }
  printf("{");
  if (argc > 1 && strcmp(argv[1], "--cost") == 0) {
    Costs();
  } else {
    Oracle(); printf(",");
    Contracts(); printf(",");
    Silence(); printf(",");
    Hostile(); printf(",");
    Rates(); printf(",");
    Reduction(); printf(",");
    SnapGate(); printf(",");
    TypeChanges(); printf(",");
    Shaper();
  }
  printf("}\n");
  return 0;
}
