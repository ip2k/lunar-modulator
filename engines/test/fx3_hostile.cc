// fx3_hostile.cc -- fm1-fx3-hostile: a reviewer's hostile checks across the
// third effects pack (Room, Hall, Gate and Plate with Freeze), the same four
// effects driven the same way, beyond what each effect's own tool does:
//
//   - schedule: a random schedule of every parameter (in range; or any
//     value, NaN and infinities included; or with NaN, infinities, 1e30 and
//     subnormals mixed into the input), each change applied between frames
//     at a fixed frame, rendered in blocks of 64, 1, 7, 13 and random 1-64
//     frames and from instance memory filled with 0x00, 0xFF, 0xA5, 0x7F and
//     0x80, at 32, 44.118 and 48 kHz: every render the same bits, all
//     finite;
//   - gate_gain: the Gate never amplifies with Listen off: no output sample
//     exceeds the largest input sample of the look-ahead's window, under a
//     random schedule of every other parameter;
//   - gate_key: fm1_gate_render_key with a key that is a copy of the input
//     equals render, bit for bit, under the wild schedule and bad input;
//   - tails: after a burst, at the longest settings (Decay 1, Damping 0 and
//     1, Size 1 and Mod 0 for Hall, where whole-sample delays and rounding
//     stores invite a limit cycle; Freeze held and released), the output
//     reaches exact zeros and stays there, with no subnormal on the way.
//
// Prints one JSON object; tests/test_engines_fx3_hostile.py reads it. A
// desktop tool: it allocates and prints. MIT licence.

#include "fm1_engine.h"
#include "fm1_gate.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <vector>

extern "C" const fm1_engine_t fm1_engine_room, fm1_engine_hall, fm1_engine_gate, fm1_engine_plate;

namespace {

struct Lcg {
  uint32_t s;
  uint32_t Next() { s = s * 1664525u + 1013904223u; return s; }
  float Unit() { return (Next() >> 8) * (1.0f / 16777216.0f); }   // [0, 1)
  float Bipolar() { return 2.0f * Unit() - 1.0f; }
};

struct Change { uint32_t frame; uint16_t index; float value; };

struct Run {
  const fm1_engine_t *e;
  float rate;
  std::vector<Change> schedule;
  std::vector<float> input, key;
  bool keyed;
};

uint32_t Hash(const std::vector<float> &v) {         // FNV-1a over the bits
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < v.size(); ++i) {
    uint32_t b;
    memcpy(&b, &v[i], sizeof b);
    for (int k = 0; k < 4; ++k) { h ^= (b >> (8 * k)) & 0xFFu; h *= 16777619u; }
  }
  return h;
}

int Index(const fm1_engine_t *e, const char *name) {
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (strcmp(e->params[i].name, name) == 0) return i;
  }
  fprintf(stderr, "%s has no parameter %s\n", e->id, name);
  exit(2);
}

// pattern: 0 for 64-frame blocks, k > 0 for k-frame blocks, -1 for random
// 1-64. A block never runs past the next change's frame.
std::vector<float> Render(const Run &r, int pattern, int fill, uint32_t seed) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, r.rate, 64 };
  const size_t n = r.e->instance_size(&host);
  std::vector<unsigned char> raw(n + 16);
  unsigned char *mem = &raw[0] + ((16 - (reinterpret_cast<uintptr_t>(&raw[0]) & 15)) & 15);
  memset(mem, fill, n);
  void *self = r.e->create(mem, &host);
  if (!self) { fprintf(stderr, "%s refused %g Hz\n", r.e->id, r.rate); exit(2); }
  std::vector<float> out(r.input);
  const uint32_t frames = static_cast<uint32_t>(out.size() / 2);
  Lcg rng = { seed };
  size_t c = 0;
  for (uint32_t f = 0; f < frames;) {
    while (c < r.schedule.size() && r.schedule[c].frame == f) {
      r.e->set_param(self, r.schedule[c].index, r.schedule[c].value);
      ++c;
    }
    uint32_t len = pattern == 0 ? 64u : (pattern > 0 ? static_cast<uint32_t>(pattern) : 1u + rng.Next() % 64u);
    if (len > frames - f) len = frames - f;
    if (c < r.schedule.size() && r.schedule[c].frame < f + len) len = r.schedule[c].frame - f;
    if (r.keyed) fm1_gate_render_key(self, &out[2 * f], &r.key[2 * f], len);
    else r.e->render(self, &out[2 * f], len);
    f += len;
  }
  r.e->destroy(self);
  return out;
}

float Value(const fm1_param_t &p, Lcg *rng, bool wild) {
  if (wild) {
    switch (rng->Next() % 12) {
      case 0: return NAN;
      case 1: return INFINITY;
      case 2: return -INFINITY;
      case 3: return p.max * 10.0f + 1e6f;
      case 4: return p.min - 1e6f;
      default: break;
    }
  }
  if (p.type == FM1_PARAM_ENUM) return static_cast<float>(rng->Next() % static_cast<uint32_t>(p.max - p.min + 1));
  return p.min + (p.max - p.min) * rng->Unit();
}

// Bursts of noise with near-silent gaps (so gates open and close and tails
// ring out), and a random schedule of every parameter.
Run Make(const fm1_engine_t *e, float rate, float seconds, uint32_t seed, bool wild, bool bad,
         uint32_t every, int skip = -1) {
  Run r;
  r.e = e;
  r.rate = rate;
  r.keyed = false;
  Lcg rng = { seed };
  const uint32_t frames = static_cast<uint32_t>(seconds * rate);
  r.input.resize(2 * frames);
  for (uint32_t i = 0; i < frames; ++i) {
    const bool on = ((i / 3000) % 3) != 2;
    float a = on ? 0.6f * rng.Bipolar() : 0.001f * rng.Bipolar();
    float b = on ? 0.6f * rng.Bipolar() : 0.0f;
    if (bad) {
      switch (rng.Next() % 4000) {
        case 0: a = NAN; break;
        case 1: b = INFINITY; break;
        case 2: a = -1e30f; break;
        case 3: b = 1e-40f; break;
        default: break;
      }
    }
    r.input[2 * i] = a;
    r.input[2 * i + 1] = b;
  }
  for (uint32_t f = every; f < frames; f += every / 2 + rng.Next() % every) {
    Change c;
    c.frame = f;
    c.index = static_cast<uint16_t>(rng.Next() % e->n_params);
    if (static_cast<int>(c.index) == skip) continue;
    c.value = Value(e->params[c.index], &rng, wild);
    r.schedule.push_back(c);
  }
  return r;
}

const fm1_engine_t *const kEffects[] = { &fm1_engine_room, &fm1_engine_hall, &fm1_engine_gate,
                                         &fm1_engine_plate };

void Schedule() {
  const float rates[] = { 32000.0f, 44118.0f, 48000.0f };
  const int patterns[] = { 1, 7, 13, -1 };
  const int fills[] = { 0x00, 0xFF, 0xA5, 0x7F, 0x80 };
  printf("\"schedule\":[");
  bool first = true;
  for (const fm1_engine_t *e : kEffects) {
    for (float rate : rates) {
      for (uint32_t seed = 1; seed <= 3; ++seed) {
        const Run r = Make(e, rate, 3.0f, seed, seed == 2, seed == 3, 3000);
        const std::vector<float> ref = Render(r, 0, 0, 1);
        bool finite = true;
        float peak = 0.0f;
        for (float x : ref) {
          if (!isfinite(x)) finite = false;
          if (fabsf(x) > peak) peak = fabsf(x);
        }
        const uint32_t h = Hash(ref);
        int same = 0, tried = 0;
        for (int p : patterns) { ++tried; same += Hash(Render(r, p, 0, 7u + p)) == h; }
        for (int fill : fills) { ++tried; same += Hash(Render(r, -1, fill, 99u)) == h; }
        printf("%s{\"fx\":\"%s\",\"rate\":%g,\"seed\":%u,\"changes\":%u,\"finite\":%s,"
               "\"peak\":%.6g,\"same\":%d,\"tried\":%d}", first ? "" : ",", e->id, rate, seed,
               static_cast<unsigned>(r.schedule.size()), finite ? "true" : "false", peak, same, tried);
        first = false;
      }
    }
  }
  printf("]");
}

void GateGain() {
  printf("\"gate_gain\":[");
  for (uint32_t seed = 1; seed <= 4; ++seed) {
    const Run r = Make(&fm1_engine_gate, 44118.0f, 4.0f, seed, false, false, 2000,
                       Index(&fm1_engine_gate, "Listen"));
    const std::vector<float> out = Render(r, -1, 0xA5, seed);
    const uint32_t frames = static_cast<uint32_t>(out.size() / 2);
    const uint32_t window = 221;                // Lookahead's 5 ms at 44,118 Hz
    double worst = -1.0;
    for (uint32_t i = 0; i < frames; ++i) {
      float m = 0.0f;
      for (uint32_t j = i >= window ? i - window : 0; j <= i; ++j) {
        m = fmaxf(m, fmaxf(fabsf(r.input[2 * j]), fabsf(r.input[2 * j + 1])));
      }
      const double o = fmaxf(fabsf(out[2 * i]), fabsf(out[2 * i + 1]));
      if (o - m > worst) worst = o - m;
    }
    printf("%s{\"seed\":%u,\"changes\":%u,\"excess\":%.9g}", seed > 1 ? "," : "", seed,
           static_cast<unsigned>(r.schedule.size()), worst);
  }
  printf("]");
}

void GateKey() {
  printf("\"gate_key\":[");
  for (uint32_t seed = 1; seed <= 3; ++seed) {
    Run r = Make(&fm1_engine_gate, 44118.0f, 3.0f, seed, true, true, 2000);
    const uint32_t h = Hash(Render(r, 0, 0, 1));
    r.key = r.input;
    r.keyed = true;
    printf("%s%s", seed > 1 ? "," : "", Hash(Render(r, -1, 0, 3)) == h ? "true" : "false");
  }
  printf("]");
}

struct Tail {
  const char *name;
  const fm1_engine_t *e;
  const char *params[6];
  float values[6];
  float freeze_on, freeze_off;                  // seconds; 0 for none
};

void Tails() {
  const Tail tails[] = {
    { "hall-longest-whole", &fm1_engine_hall, { "Decay", "Damping", "Size", "Mod", "Mix", NULL },
      { 1, 0, 1, 0, 1, 0 }, 0, 0 },
    { "hall-longest-dark", &fm1_engine_hall, { "Decay", "Damping", "Size", "Mod", "Mix", NULL },
      { 1, 1, 0.3f, 1, 1, 0 }, 0, 0 },
    { "hall-freeze-released", &fm1_engine_hall, { "Decay", "Damping", "Mod", "Mix", NULL, NULL },
      { 1, 0, 0, 1, 0, 0 }, 0.3f, 10 },
    { "room-longest-bright", &fm1_engine_room, { "Decay", "Damping", "Diffusion", "Blur", "Mix", NULL },
      { 1, 0, 1, 1, 1, 0 }, 0, 0 },
    { "room-longest-dark", &fm1_engine_room, { "Decay", "Damping", "Blur", "Mix", NULL, NULL },
      { 1, 1, 1, 1, 0, 0 }, 0, 0 },
    { "plate-freeze-released", &fm1_engine_plate, { "Decay", "Damping", "Mix", NULL, NULL, NULL },
      { 1, 0, 1, 0, 0, 0 }, 0.3f, 10 },
  };
  const float rate = 44118.0f;
  printf("\"tails\":[");
  for (size_t t = 0; t < sizeof(tails) / sizeof(tails[0]); ++t) {
    const Tail &tl = tails[t];
    fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
    std::vector<unsigned char> raw(tl.e->instance_size(&host) + 16);
    unsigned char *mem = &raw[0] + ((16 - (reinterpret_cast<uintptr_t>(&raw[0]) & 15)) & 15);
    memset(mem, 0xA5, tl.e->instance_size(&host));
    void *self = tl.e->create(mem, &host);
    for (int k = 0; k < 6 && tl.params[k]; ++k) {
      tl.e->set_param(self, static_cast<uint16_t>(Index(tl.e, tl.params[k])), tl.values[k]);
    }
    const int freeze = tl.freeze_on > 0 ? Index(tl.e, "Freeze") : -1;
    Lcg rng = { 12345u };
    const uint32_t burst = static_cast<uint32_t>(0.5f * rate);
    const uint32_t total = static_cast<uint32_t>(120.0f * rate);
    uint32_t last = 0, subnormal = 0, nonfinite = 0;
    float buf[128];
    for (uint32_t f = 0; f < total; f += 64) {
      if (freeze >= 0 && f == static_cast<uint32_t>(tl.freeze_on * rate) / 64u * 64u) {
        tl.e->set_param(self, static_cast<uint16_t>(freeze), 1.0f);
      }
      if (freeze >= 0 && f == static_cast<uint32_t>(tl.freeze_off * rate) / 64u * 64u) {
        tl.e->set_param(self, static_cast<uint16_t>(freeze), 0.0f);
      }
      for (int i = 0; i < 128; ++i) buf[i] = f + i / 2 < burst ? 0.5f * rng.Bipolar() : 0.0f;
      tl.e->render(self, buf, 64);
      for (int i = 0; i < 128; ++i) {
        if (!isfinite(buf[i])) ++nonfinite;
        if (buf[i] != 0.0f) last = f + i / 2;
        if (buf[i] != 0.0f && fabsf(buf[i]) < 1.17549435e-38f) ++subnormal;
      }
    }
    tl.e->destroy(self);
    printf("%s{\"name\":\"%s\",\"last_nonzero_s\":%.3f,\"seconds\":120,\"subnormal\":%u,"
           "\"nonfinite\":%u}", t ? "," : "", tl.name, last / rate, subnormal, nonfinite);
  }
  printf("]");
}

}  // namespace

int main() {
  printf("{");
  Schedule(); printf(",");
  GateGain(); printf(",");
  GateKey(); printf(",");
  Tails();
  printf("}\n");
  return 0;
}
