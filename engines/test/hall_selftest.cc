// hall_selftest.cc -- fm1-hall-selftest: checks of Hall (src/fx_hall.cc) that
// fm1-render cannot make, because it sets an effect's parameters only before
// the first block. Run by tests/test_engines_hall.py; prints one JSON line
// per check and exits non-zero if any fails.
//
//   - host rates it must refuse, and the size it asks for at each rate;
//   - every parameter turned while it runs, to any value (NaN, infinities,
//     out of range), with non-finite and huge input mixed in: the output
//     stays finite and bounded, and the instance memory's prior contents
//     never show;
//   - the same schedule gives the same output, whatever the block sizes;
//   - Size, Pre-delay, Mod and Freeze swept many times a second at three
//     host rates, at the longest decay: bounded;
//   - with the input silent, the tail decays to exact zeros, no subnormals;
//   - the decay time is what Decay says (Schroeder's backward integration);
//   - Freeze holds the tail, lets nothing more in, lets go again, and
//     switches without a click.
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

extern "C" const fm1_engine_t fm1_engine_hall;

namespace {

const fm1_engine_t &E = fm1_engine_hall;
const float kRate = 44118.0f;
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

uint16_t P(const char *name) {
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
  float Bipolar() { return 2.0f * Unit() - 1.0f; }
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

fm1_host_t Host(float rate) {
  fm1_host_t h = { FM1_ENGINE_API_VERSION, rate, 64 };
  return h;
}

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
  const float x = 0.5f * rng.Bipolar();
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

// Render `frames` of input through a schedule of parameter changes. Blocks
// stop at each event, so changes land on the same frame whatever the block
// sizes; `blocks` picks random sizes, NULL means 64.
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

double Peak(const std::vector<float> &x, bool *finite) {
  double peak = 0.0;
  *finite = true;
  for (size_t i = 0; i < x.size(); ++i) {
    if (!std::isfinite(x[i])) { *finite = false; continue; }
    if (fabs(x[i]) > peak) peak = fabs(x[i]);
  }
  return peak;
}

void CheckRates() {
  const float refused[] = { 0.0f, -44118.0f, NAN, INFINITY, 7999.0f, 192001.0f, 1e6f };
  bool ok = true;
  for (size_t i = 0; i < sizeof(refused) / sizeof(refused[0]); ++i) {
    Unit u(Host(refused[i]), 0xA5);
    if (u.self) { ok = false; u.self = NULL; }
  }
  Report("refuses_bad_rates", ok);

  // The rings are powers of two sized for the rate: 16,384 + 8,192 words at
  // 44,100 and 44,118 Hz.
  const float rates[] = { 8000.0f, 22050.0f, 44100.0f, 44118.0f, 48000.0f, 96000.0f, 192000.0f };
  std::string detail;
  ok = true;
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    const fm1_host_t host = Host(rates[i]);
    const size_t size = E.instance_size(&host);
    Unit u(host, 0xFF);
    ok = ok && u.self != NULL && size % 16 == 0;
    char key[32];
    snprintf(key, sizeof(key), "bytes_%.0f", rates[i]);
    detail += (detail.empty() ? "" : ",") + Num(key, static_cast<double>(size));
  }
  const fm1_host_t fm1 = Host(44118.0f), cd = Host(44100.0f);
  const size_t at_fm1 = E.instance_size(&fm1);
  ok = ok && at_fm1 == E.instance_size(&cd) && at_fm1 > 49152 && at_fm1 <= 49152 + 1024;
  Report("size_follows_the_rate", ok, detail);
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
  const fm1_host_t host = Host(kRate);
  const uint32_t frames = 10 * 44118;
  std::vector<Event> ev = Abuse(frames, 7);
  std::vector<float> a = Run(host, 0x00, ev, frames, true, 11, NULL);
  bool finite;
  const double peak = Peak(a, &finite);
  // The guard clamps the input to 16, and the dry path is at most 1 x that;
  // each word is within +/-2, and a side is four words: at most 8.
  Report("abuse_stays_finite_and_bounded", finite && peak <= 16.0 + 8.0,
         Num("peak", peak) + "," + Num("events", static_cast<double>(ev.size())));

  std::vector<float> b = Run(host, 0xA5, ev, frames, true, 11, NULL);
  std::vector<float> c = Run(host, 0xFF, ev, frames, true, 11, NULL);
  Report("ignores_prior_memory", a == b && a == c);

  Rng blocks = { 3 };
  std::vector<float> d = Run(host, 0x5A, ev, frames, true, 11, &blocks);
  Rng ones = { 5 };
  fm1_host_t one = host;
  one.max_frames = 1;
  std::vector<float> e = Run(one, 0x5A, ev, frames, true, 11, &ones);
  Report("block_sizes_do_not_matter", a == d && a == e);
}

void CheckSweeps() {
  // At the longest decay, with Mod at full: Size end to end every 20 ms,
  // Pre-delay every 30 ms, Freeze on and off every 170 ms, at three rates.
  bool ok = true;
  double worst = 0.0;
  const float rates[] = { 22050.0f, 44118.0f, 96000.0f };
  for (size_t r = 0; r < 3; ++r) {
    const fm1_host_t host = Host(rates[r]);
    const uint32_t frames = static_cast<uint32_t>(6 * rates[r]);
    std::vector<Event> ev;
    ev.push_back(Event{ 0, P("Decay"), 1.0f });
    ev.push_back(Event{ 0, P("Mod"), 1.0f });
    ev.push_back(Event{ 0, P("Damping"), 0.0f });
    ev.push_back(Event{ 0, P("Mix"), 1.0f });
    const uint32_t size_step = static_cast<uint32_t>(0.02f * rates[r]);
    const uint32_t pre_step = static_cast<uint32_t>(0.03f * rates[r]);
    const uint32_t freeze_step = static_cast<uint32_t>(0.17f * rates[r]);
    for (uint32_t f = 1, k = 0; f < frames; ++f) {
      if (f % size_step == 0) ev.push_back(Event{ f, P("Size"), (++k) % 2 ? 0.0f : 1.0f });
      if (f % pre_step == 0) ev.push_back(Event{ f, P("Pre-delay"), (f / pre_step) % 2 ? 150.0f : 0.0f });
      if (f % freeze_step == 0) ev.push_back(Event{ f, P("Freeze"), static_cast<float>((f / freeze_step) % 2) });
    }
    std::vector<float> out = Run(host, 0x33, ev, frames, false, 5, NULL);
    bool finite;
    const double peak = Peak(out, &finite);
    ok = ok && finite;
    if (peak > worst) worst = peak;
  }
  Report("sweeps_stay_bounded", ok && worst <= 4.0, Num("peak", worst));
}

void CheckDecayToZero() {
  // Abuse first, then a long decay with the input silent: the lines must
  // reach exact zeros, with no subnormal left anywhere in the output.
  const fm1_host_t host = Host(kRate);
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
  const char *names[] = { "Decay", "Size", "Damping", "Mix", "Mod", "Freeze", "Diffusion",
                          "Width", "Low Cut", "Pre-delay" };
  const float values[] = { 0.6f, 1.0f, 0.0f, 1.0f, 1.0f, 0.0f, 1.0f, 1.0f, 0.0f, 150.0f };
  for (size_t i = 0; i < sizeof(values) / sizeof(values[0]); ++i) {
    E.set_param(u.self, P(names[i]), values[i]);
  }
  // Fill the lines with full-scale noise for a second, then silence.
  for (uint32_t pos = 0; pos < 44118; pos += 64) {
    for (int f = 0; f < 64; ++f) block[2 * f] = block[2 * f + 1] = in.Bipolar();
    E.render(u.self, &block[0], 64);
  }
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
  Report("decays_to_exact_zero", loud > 0.05 && silent_from < frames - 44118 && subnormal == 0,
         Num("silent_after_s", silent_from / 44118.0) + "," + Num("first_100ms_peak", loud) +
         "," + Num("subnormal", subnormal));
}

// The decay time: a burst of low-passed noise (0.3 s, about 0 dBFS, its
// highs off so that the interpolation's high-frequency loss does not count),
// then Schroeder's backward integral of the energy after it, both channels,
// fitted between -5 and -25 dB and extrapolated to -60. Damping 0, Mod 0.
double MeasureT60(float decay, float size, float rate, double seconds) {
  const fm1_host_t host = Host(rate);
  Unit u(host, 0);
  const char *names[] = { "Decay", "Size", "Damping", "Mix", "Mod", "Pre-delay", "Low Cut" };
  const float values[] = { decay, size, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f };
  for (size_t i = 0; i < sizeof(values) / sizeof(values[0]); ++i) {
    E.set_param(u.self, P(names[i]), values[i]);
  }
  const uint32_t burst = static_cast<uint32_t>(0.3 * rate);
  const uint32_t frames = static_cast<uint32_t>(seconds * rate);
  std::vector<double> energy;
  float block[128];
  Rng in = { 77 };
  const float k = 1.0f - expf(-6.2831853f * 300.0f / rate);      // 300 Hz
  float lp = 0.0f;
  for (uint32_t pos = 0; pos < burst + frames; pos += 64) {
    for (int f = 0; f < 64; ++f) {
      lp += k * (2.0f * in.Bipolar() - lp);
      block[2 * f] = block[2 * f + 1] = pos + f < burst ? lp : 0.0f;
    }
    E.render(u.self, block, 64);
    for (uint32_t f = 0; f < 64; ++f) {
      if (pos + f >= burst && energy.size() < frames) {
        energy.push_back(static_cast<double>(block[2 * f]) * block[2 * f] +
                         static_cast<double>(block[2 * f + 1]) * block[2 * f + 1]);
      }
    }
  }
  std::vector<double> edc(frames);
  double sum = 0.0;
  for (uint32_t i = frames; i-- > 0;) { sum += energy[i]; edc[i] = sum; }
  double sx = 0, sy = 0, sxx = 0, sxy = 0;
  int n = 0;
  for (uint32_t i = 0; i < frames; ++i) {
    const double db = 10.0 * log10(edc[i] / edc[0] + 1e-30);
    if (db > -5.0) continue;
    if (db < -25.0) break;
    const double t = i / rate;
    sx += t; sy += db; sxx += t * t; sxy += t * db; ++n;
  }
  const double slope = (n * sxy - sx * sy) / (n * sxx - sx * sx);
  return -60.0 / slope;
}

void CheckDecayTime() {
  // Decay maps 0..1 to 0.2..20 s on a log scale; Size and the rate do not
  // change it.
  struct Case { float decay, size, rate; double seconds; };
  const Case cases[] = {
    { 0.2f, 0.7f, 44118.0f, 2.0 }, { 0.5f, 0.7f, 44118.0f, 4.0 }, { 0.5f, 0.0f, 44118.0f, 4.0 },
    { 0.5f, 1.0f, 44118.0f, 4.0 }, { 0.8f, 0.7f, 44118.0f, 10.0 }, { 0.5f, 0.7f, 96000.0f, 4.0 },
  };
  std::string detail;
  double worst = 0.0;
  for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
    const Case &c = cases[i];
    const double want = 0.2 * pow(100.0, c.decay);
    const double got = MeasureT60(c.decay, c.size, c.rate, c.seconds);
    const double err = fabs(got / want - 1.0);
    if (!(err <= worst)) worst = err;
    char key[48];
    snprintf(key, sizeof(key), "t60_d%.1f_s%.1f_%.0f", c.decay, c.size, c.rate);
    detail += (detail.empty() ? "" : ",") + Num(key, got);
  }
  Report("decay_time_is_decay", worst < 0.1, detail + "," + Num("worst_error", worst));
}

// Freeze: noise for a second, then Freeze on while the noise goes on. The
// held tail keeps its level; nothing played after the crossfade reaches it;
// the input goes silent and Freeze off lets the tail decay.
void CheckFreeze() {
  const fm1_host_t host = Host(kRate);
  const uint32_t on = 64 * 690, off = 64 * 8271, quiet = off - 64 * 345, frames = 64 * 11028;
  const uint32_t settled = on + 64 * 207;              // 0.3 s after on
  std::vector<Event> ev;
  ev.push_back(Event{ 0, P("Mix"), 1.0f });
  ev.push_back(Event{ 0, P("Decay"), 0.5f });
  ev.push_back(Event{ on, P("Freeze"), 1.0f });
  ev.push_back(Event{ off, P("Freeze"), 0.0f });
  // Two runs: their input differs between `settled` and `quiet` (the second
  // plays louder, other noise), and is silent in both from `quiet` on.
  std::vector<float> runs[2];
  for (int r = 0; r < 2; ++r) {
    Unit u(host, 0);
    Rng in = { 1 }, other = { 99 };
    runs[r].assign(2 * static_cast<size_t>(frames), 0.0f);
    size_t next = 0;
    for (uint32_t pos = 0; pos < frames; pos += 64) {
      while (next < ev.size() && ev[next].frame <= pos) {
        E.set_param(u.self, ev[next].index, ev[next].value);
        ++next;
      }
      float *blk = &runs[r][2 * static_cast<size_t>(pos)];
      for (uint32_t f = 0; f < 64; ++f) {
        const uint32_t t = pos + f;
        float x = Input(in, t, false);
        if (r == 1 && t >= settled) x = 0.9f * other.Bipolar();
        if (t >= quiet) x = 0.0f;
        blk[2 * f] = x;
        blk[2 * f + 1] = t % 3 ? x : -0.5f * x;
      }
      E.render(u.self, blk, 64);
    }
  }
  const std::vector<float> &a = runs[0];
  Report("freeze_lets_nothing_in", a == runs[1]);
  auto rms = [&](uint32_t t0, uint32_t t1) {
    double s = 0.0;
    for (uint32_t i = t0; i < t1; ++i) s += static_cast<double>(a[2 * i]) * a[2 * i];
    return sqrt(s / (t1 - t0));
  };
  const uint32_t s = 44118;
  const double held0 = rms(on + s / 2, on + s), held1 = rms(off - s / 2, off);
  const double drift_db = 20.0 * log10(held1 / held0);
  const double after = rms(off + 2 * s, off + 3 * s);
  const double fall_db = 20.0 * log10(after / held1 + 1e-30);
  bool finite;
  const double peak = Peak(a, &finite);
  Report("freeze_holds_then_lets_go",
         finite && held0 > 0.05 && fabs(drift_db) < 1.0 && fall_db < -40.0 && peak < 2.0,
         Num("held_rms", held0) + "," + Num("drift_db_over_10s", drift_db) + "," +
         Num("fall_db_2s_after_off", fall_db) + "," + Num("peak", peak));

  // A click is a jump between neighbouring samples: around each switch, the
  // largest one is no larger than in the steady wash before it.
  auto jump = [&](uint32_t t0, uint32_t t1) {
    double m = 0.0;
    for (uint32_t i = t0 + 1; i < t1; ++i) {
      const double d = fabs(static_cast<double>(a[2 * i]) - a[2 * i - 2]);
      if (d > m) m = d;
    }
    return m;
  };
  const double before_on = jump(on - s / 2, on), at_on = jump(on, on + s / 10);
  const double before_off = jump(off - s / 2, off), at_off = jump(off, off + s / 10);
  Report("freeze_switches_cleanly", at_on < 1.2 * before_on && at_off < 1.2 * before_off,
         Num("jump_before_on", before_on) + "," + Num("jump_at_on", at_on) + "," +
         Num("jump_before_off", before_off) + "," + Num("jump_at_off", at_off));
}

}  // namespace

int main() {
  CheckRates();
  CheckAbuse();
  CheckSweeps();
  CheckDecayToZero();
  CheckDecayTime();
  CheckFreeze();
  fprintf(stderr, "%d passed, %d failed\n", g_passed, g_failed);
  return g_failed ? 1 : 0;
}
