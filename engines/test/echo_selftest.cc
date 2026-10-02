// echo_selftest.cc -- fm1-echo-selftest: checks of Echo (src/fx_echo.cc)
// that fm1-render cannot make, because it sets an effect's parameters only
// before the first block. Run by tests/test_engines_echo.py; prints one JSON
// line per check and exits non-zero if any fails.
//
//   - host rates it must refuse, and a size that does not depend on the rate;
//   - every parameter turned while it runs, to any value (NaN, infinities,
//     out of range), with non-finite and huge input mixed in: the output
//     stays finite and bounded, and the instance memory's prior contents
//     never show;
//   - Time swept end to end, many times a second, across the change of clock;
//   - the same schedule gives the same output, whatever the block sizes;
//   - with the input silent, the line decays to exact zeros, no subnormals.
//
// A desktop tool: it allocates and prints. MIT licence.

#include "fm1_engine.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

extern "C" const fm1_engine_t fm1_engine_echo;

namespace {

const fm1_engine_t &E = fm1_engine_echo;
int g_passed = 0;
int g_failed = 0;

void Report(const char *check, bool ok, const std::string &detail = "") {
  printf("{\"check\":\"%s\",\"ok\":%s%s%s}\n", check, ok ? "true" : "false",
         detail.empty() ? "" : ",", detail.c_str());
  if (ok) ++g_passed; else ++g_failed;
}

std::string Num(const char *key, double v) {
  char b[64];
  snprintf(b, sizeof(b), "\"%s\":%.9g", key, v);
  return b;
}

int ParamIndex(const char *name) {
  for (uint16_t i = 0; i < E.n_params; ++i) {
    if (strcmp(E.params[i].name, name) == 0) return i;
  }
  fprintf(stderr, "no parameter %s\n", name);
  exit(2);
}

struct Rng {                                   // deterministic, for schedules
  uint32_t s;
  uint32_t Next() { s = s * 1664525u + 1013904223u; return s; }
  float Unit() { return (Next() >> 8) * (1.0f / 16777216.0f); }   // [0, 1)
};

// One instance in its own memory, filled with `fill` before create.
struct Unit {
  std::vector<unsigned char> raw;
  void *self;
  Unit(const fm1_host_t &host, int fill) : raw(E.instance_size(&host) + 16, 0), self(NULL) {
    unsigned char *mem = Aligned();
    memset(mem, fill, E.instance_size(&host));
    self = E.create(mem, &host);
  }
  ~Unit() { if (self) E.destroy(self); }
  unsigned char *Aligned() {
    uintptr_t p = reinterpret_cast<uintptr_t>(&raw[0]);
    return &raw[0] + ((16 - (p & 15)) & 15);
  }
};

// A schedule: at each frame, maybe a parameter change; an input signal with
// bad samples mixed in; the output collected.
struct Event { uint32_t frame; uint16_t index; float value; };

float Weird(Rng &rng, const fm1_param_t &p) {
  switch (rng.Next() % 9) {
    case 0: return NAN;
    case 1: return INFINITY;
    case 2: return -INFINITY;
    case 3: return 1e30f;
    case 4: return -1e30f;
    case 5: return p.min;
    case 6: return p.max;
    case 7: return p.max + (p.max - p.min) * 3.0f;
    default: return p.min + (p.max - p.min) * rng.Unit();
  }
}

float Input(Rng &rng, uint32_t frame, bool bad) {
  float x = 0.5f * (2.0f * rng.Unit() - 1.0f);
  if (bad) {
    switch (frame % 4096) {
      case 100: return NAN;
      case 200: return INFINITY;
      case 300: return -INFINITY;
      case 400: return 1e30f;
      default: break;
    }
  }
  return x;
}

std::vector<float> Run(const fm1_host_t &host, int fill, const std::vector<Event> &events,
                       uint32_t frames, bool bad_input, uint32_t seed, Rng *blocks) {
  Unit u(host, fill);
  std::vector<float> out(2 * static_cast<size_t>(frames));
  Rng in = { seed };
  size_t next = 0;
  uint32_t pos = 0;
  while (pos < frames) {
    while (next < events.size() && events[next].frame <= pos) {
      E.set_param(u.self, events[next].index, events[next].value);
      ++next;
    }
    uint32_t n = blocks ? 1 + blocks->Next() % host.max_frames : host.max_frames;
    if (n > frames - pos) n = frames - pos;
    // Stop at the next event, so changes land on the same frame whatever the
    // block sizes.
    if (next < events.size() && events[next].frame - pos < n) n = events[next].frame - pos;
    float *b = &out[2 * static_cast<size_t>(pos)];
    for (uint32_t f = 0; f < n; ++f) {
      b[2 * f] = Input(in, pos + f, bad_input);
      b[2 * f + 1] = (pos + f) % 3 ? b[2 * f] : -0.5f * b[2 * f];   // not quite mono
    }
    E.render(u.self, b, n);
    pos += n;
  }
  return out;
}

void CheckRates() {
  const float refused[] = { 0.0f, -44118.0f, NAN, INFINITY, 500.0f, 2e6f };
  bool ok = true;
  for (size_t i = 0; i < sizeof(refused) / sizeof(refused[0]); ++i) {
    fm1_host_t host = { FM1_ENGINE_API_VERSION, refused[i], 64 };
    Unit u(host, 0xA5);
    if (u.self) { ok = false; u.self = NULL; }
  }
  Report("refuses_bad_rates", ok);

  const float rates[] = { 8000.0f, 22050.0f, 44118.0f, 48000.0f, 96000.0f, 192000.0f };
  const fm1_host_t base = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
  const size_t size = E.instance_size(&base);
  ok = size % 16 == 0 && size >= 65536 && size <= 65536 + 512;
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    fm1_host_t host = { FM1_ENGINE_API_VERSION, rates[i], 64 };
    ok = ok && E.instance_size(&host) == size;
    Unit u(host, 0xFF);
    ok = ok && u.self != NULL;
  }
  Report("size_is_fixed", ok, Num("bytes", static_cast<double>(size)));
}

std::vector<Event> Abuse(uint32_t frames, uint32_t seed) {
  Rng rng = { seed };
  std::vector<Event> ev;
  for (uint32_t f = 0; f < frames; f += 1 + rng.Next() % 900) {
    uint16_t index = static_cast<uint16_t>(rng.Next() % (E.n_params + 2));
    if (index >= E.n_params) index = index == E.n_params ? E.n_params : 0xFFFF;  // ignored
    const fm1_param_t &p = E.params[index < E.n_params ? index : 0];
    ev.push_back(Event{ f, index, Weird(rng, p) });
  }
  return ev;
}

void CheckAbuse() {
  const fm1_host_t host = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
  const uint32_t frames = 10 * 44118;
  std::vector<Event> ev = Abuse(frames, 7);
  std::vector<float> a = Run(host, 0x00, ev, frames, true, 11, NULL);
  float peak = 0.0f;
  bool finite = true;
  for (size_t i = 0; i < a.size(); ++i) {
    if (!std::isfinite(a[i])) { finite = false; break; }
    if (fabsf(a[i]) > peak) peak = fabsf(a[i]);
  }
  // The guard clamps input to 16; the echo adds at most 2 on top.
  Report("abuse_stays_finite_and_bounded", finite && peak <= 18.0f,
         Num("peak", peak) + "," + Num("events", static_cast<double>(ev.size())));

  std::vector<float> b = Run(host, 0xA5, ev, frames, true, 11, NULL);
  std::vector<float> c = Run(host, 0xFF, ev, frames, true, 11, NULL);
  Report("ignores_prior_memory", a == b && a == c);

  Rng blocks = { 3 };
  std::vector<float> d = Run(host, 0x5A, ev, frames, true, 11, &blocks);
  Report("block_sizes_do_not_matter", a == d);
}

void CheckTimeSweep() {
  // Time from end to end every 20 ms, Wow at full, at three host rates.
  const int time = ParamIndex("Time"), wow = ParamIndex("Wow"), fb = ParamIndex("Feedback");
  bool ok = true;
  double worst = 0.0;
  const float rates[] = { 22050.0f, 44118.0f, 96000.0f };
  for (size_t r = 0; r < 3; ++r) {
    const fm1_host_t host = { FM1_ENGINE_API_VERSION, rates[r], 64 };
    const uint32_t frames = static_cast<uint32_t>(4 * rates[r]);
    const uint32_t step = static_cast<uint32_t>(0.02f * rates[r]);
    std::vector<Event> ev;
    ev.push_back(Event{ 0, static_cast<uint16_t>(wow), 1.0f });
    ev.push_back(Event{ 0, static_cast<uint16_t>(fb), 1.0f });
    for (uint32_t f = step, k = 0; f < frames; f += step, ++k) {
      ev.push_back(Event{ f, static_cast<uint16_t>(time), k % 2 ? 10.0f : 1000.0f });
    }
    std::vector<float> out = Run(host, 0x33, ev, frames, false, 5, NULL);
    for (size_t i = 0; i < out.size(); ++i) {
      if (!std::isfinite(out[i])) { ok = false; break; }
      if (fabsf(out[i]) > worst) worst = fabsf(out[i]);
    }
  }
  Report("time_sweeps_stay_bounded", ok && worst <= 2.5, Num("peak", worst));
}

void CheckDecayToZero() {
  // Abuse first, then the longest-ringing setting with the input silent and
  // no new sound let in: the line must reach exact zeros, with no subnormal
  // left anywhere in the output.
  const fm1_host_t host = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
  Unit u(host, 0xA5);
  Rng in = { 9 };
  std::vector<Event> ev = Abuse(44118, 21);
  std::vector<float> block(128);
  size_t next = 0;
  for (uint32_t pos = 0; pos < 44118; pos += 64) {
    while (next < ev.size() && ev[next].frame <= pos) {
      E.set_param(u.self, ev[next].index, ev[next].value);
      ++next;
    }
    for (int f = 0; f < 64; ++f) block[2 * f] = block[2 * f + 1] = Input(in, pos + f, true);
    E.render(u.self, &block[0], 64);
  }
  const float settings[][2] = {
    { static_cast<float>(ParamIndex("Feedback")), 1.0f },
    { static_cast<float>(ParamIndex("Tone")), 1.0f },
    { static_cast<float>(ParamIndex("Mix")), 1.0f },
    { static_cast<float>(ParamIndex("Level")), 1.0f },
    { static_cast<float>(ParamIndex("Wow")), 1.0f },
    { static_cast<float>(ParamIndex("Time")), 10.0f },
  };
  for (size_t i = 0; i < sizeof(settings) / sizeof(settings[0]); ++i) {
    E.set_param(u.self, static_cast<uint16_t>(settings[i][0]), settings[i][1]);
  }
  // Fill the loop with full-scale noise for a second, then silence.
  for (uint32_t pos = 0; pos < 44118; pos += 64) {
    for (int f = 0; f < 64; ++f) block[2 * f] = block[2 * f + 1] = 2.0f * in.Unit() - 1.0f;
    E.render(u.self, &block[0], 64);
  }
  E.set_param(u.self, static_cast<uint16_t>(ParamIndex("Level")), 0.0f);
  double loud = 0.0;
  uint32_t silent_from = 0, subnormal = 0;
  const uint32_t frames = 20 * 44118;
  for (uint32_t pos = 0; pos < frames; pos += 64) {
    for (int f = 0; f < 128; ++f) block[f] = 0.0f;
    E.render(u.self, &block[0], 64);
    for (int f = 0; f < 128; ++f) {
      if (block[f] != 0.0f) {
        silent_from = pos + 64;
        if (fabsf(block[f]) < 1.17549435e-38f) ++subnormal;
      }
      if (pos < 4410 && fabsf(block[f]) > loud) loud = fabsf(block[f]);
    }
  }
  Report("decays_to_exact_zero", loud > 0.1 && silent_from < frames - 44118 && subnormal == 0,
         Num("silent_after_s", silent_from / 44118.0) + "," + Num("first_100ms_peak", loud) +
         "," + Num("subnormal", subnormal));
}

}  // namespace

int main() {
  CheckRates();
  CheckAbuse();
  CheckTimeSweep();
  CheckDecayToZero();
  fprintf(stderr, "%d passed, %d failed\n", g_passed, g_failed);
  return g_failed ? 1 : 0;
}
