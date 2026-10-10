// Warble host-contract checks that fm1-render cannot make: exact dry bypass,
// per-instance determinism/reset, rate-scaled delay, smooth Mix changes,
// refusal/memory limits and hostile values. MIT.
#include "fm1_engine.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

extern "C" const fm1_engine_t fm1_engine_warble;

namespace {
const fm1_engine_t &E = fm1_engine_warble;
int failed = 0;

void RenderBlocks(void *state, float *lr, uint32_t frames, uint32_t block = 64) {
  for (uint32_t at = 0; at < frames;) {
    const uint32_t n = frames - at < block ? frames - at : block;
    E.render(state, lr + 2 * at, n);
    at += n;
  }
}

void Check(const char *name, bool pass, double value = 0.0) {
  printf("{\"check\":\"%s\",\"ok\":%s,\"value\":%.9g}\n", name,
         pass ? "true" : "false", value);
  if (!pass) ++failed;
}

int Param(const char *name) {
  for (uint16_t i = 0; i < E.n_params; ++i)
    if (strcmp(E.params[i].name, name) == 0) return i;
  fprintf(stderr, "missing param %s\n", name);
  exit(2);
}

struct Unit {
  std::vector<unsigned char> mem;
  void *state;
  fm1_host_t host;
  static size_t Size(float rate) { fm1_host_t h = Host(rate); return E.instance_size(&h); }
  Unit(float rate, int fill = 0xA5) : mem(Size(rate) + 16), state(NULL),
                                     host{FM1_ENGINE_API_VERSION, rate, 64} {
    uintptr_t p = reinterpret_cast<uintptr_t>(&mem[0]);
    unsigned char *aligned = &mem[0] + ((16 - (p & 15)) & 15);
    memset(aligned, fill, E.instance_size(&host));
    state = E.create(aligned, &host);
  }
  ~Unit() { if (state) E.destroy(state); }
  static fm1_host_t Host(float rate) { return fm1_host_t{FM1_ENGINE_API_VERSION, rate, 64}; }
};

void RateAndSize() {
  const float bad[] = { 0.0f, -44100.0f, NAN, INFINITY, 7999.0f, 192001.0f };
  bool ok = true;
  for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i) {
    Unit u(bad[i]);
    ok = ok && !u.state;
  }
  Check("refuses_bad_rates", ok);
  const float rates[] = { 8000.0f, 22050.0f, 44118.0f, 48000.0f, 96000.0f, 192000.0f };
  const fm1_host_t standard_host = Unit::Host(44118.0f);
  const size_t size = E.instance_size(&standard_host);
  ok = size % 16 == 0 && size >= 16384 && size <= 16896;
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    Unit u(rates[i]);
    ok = ok && u.state && E.instance_size(&u.host) == size;
  }
  Check("fixed_bounded_instance", ok, size);
}

std::vector<float> RenderImpulse(float rate) {
  Unit u(rate);
  E.set_param(u.state, Param("Wow"), 1.0f);
  E.set_param(u.state, Param("Flutter"), 1.0f);
  E.set_param(u.state, Param("Mix"), 1.0f);
  const uint32_t n = static_cast<uint32_t>(rate * 0.03f);
  std::vector<float> out(2 * n, 0.0f);
  out[0] = out[1] = 0.5f;
  RenderBlocks(u.state, &out[0], n);
  return out;
}

void RateScaling() {
  const float rates[] = { 22050.0f, 44118.0f, 96000.0f };
  double times[3] = {};
  bool ok = true;
  for (int r = 0; r < 3; ++r) {
    std::vector<float> x = RenderImpulse(rates[r]);
    size_t first = x.size();
    for (size_t i = 2; i < x.size(); i += 2) {
      if (fabsf(x[i]) > 0.001f || fabsf(x[i + 1]) > 0.001f) { first = i / 2; break; }
    }
    times[r] = first / rates[r];
    ok = ok && first < x.size() / 2 && times[r] > 0.010 && times[r] < 0.016;
  }
  ok = ok && fabs(times[0] - times[1]) < 0.0003 && fabs(times[1] - times[2]) < 0.0003;
  Check("delay_scales_in_seconds", ok, times[1] * 1000.0);
}

std::vector<float> DeterministicRun(float rate, int split) {
  Unit u(rate);
  E.set_param(u.state, Param("Wow"), 0.9f);
  E.set_param(u.state, Param("Flutter"), 0.8f);
  E.set_param(u.state, Param("Mix"), 0.7f);
  const uint32_t n = static_cast<uint32_t>(rate * 0.25f);
  std::vector<float> x(2 * n);
  for (uint32_t i = 0; i < n; ++i) {
    x[2 * i] = 0.4f * sinf(6.28318530718f * 330.0f * i / rate);
    x[2 * i + 1] = 0.3f * sinf(6.28318530718f * 440.0f * i / rate + 0.2f);
  }
  uint32_t at = 0;
  const uint32_t block = split <= 0 ? 64 : static_cast<uint32_t>(split);
  while (at < n) {
    uint32_t count = n - at < block ? n - at : block;
    E.render(u.state, &x[2 * at], count);
    at += count;
  }
  return x;
}

void DeterminismAndReset() {
  const std::vector<float> a = DeterministicRun(44118.0f, 0);
  const std::vector<float> b = DeterministicRun(44118.0f, 17);
  const std::vector<float> c = DeterministicRun(44118.0f, 0);
  Check("deterministic_and_reblockable", a == b && a == c);
}

void DryAndSmooth() {
  Unit u(44118.0f);
  E.set_param(u.state, Param("Mix"), 0.0f);
  float dry[] = { -0.0f, 0.25f, -0.5f, 1.0f, NAN, INFINITY, 1e20f, -1e20f };
  float original[sizeof(dry) / sizeof(dry[0])];
  memcpy(original, dry, sizeof(dry));
  E.render(u.state, dry, 4);
  const bool exact = memcmp(original, dry, sizeof(dry)) == 0;

  // Start at Mix 0 and make a live full-wet change on a steady sine. A 5 ms
  // glide keeps the first step bounded; a block-rate jump would be much larger.
  E.set_param(u.state, Param("Mix"), 0.0f);
  float pre[512];
  for (int i = 0; i < 256; ++i) pre[2*i] = pre[2*i+1] = 0.5f * sinf(6.28318530718f * 220.0f * i / 44118.0f);
  RenderBlocks(u.state, pre, 256);
  E.set_param(u.state, Param("Mix"), 1.0f);
  float live[2 * 256];
  for (int i = 0; i < 256; ++i) live[2*i] = live[2*i+1] = 0.5f * sinf(6.28318530718f * 220.0f * (i+256) / 44118.0f);
  RenderBlocks(u.state, live, 256);
  float step = 0.0f;
  for (int i = 1; i < 256; ++i) step = fmaxf(step, fabsf(live[2*i] - live[2*(i-1)]));
  Check("exact_dry_and_smooth_mix", exact && step < 0.12f, step);
}

void ModulationSmoothing() {
  Unit u(44118.0f);
  E.set_param(u.state, Param("Wow"), 0.0f);
  E.set_param(u.state, Param("Flutter"), 0.0f);
  E.set_param(u.state, Param("Mix"), 1.0f);
  float before[2 * 1024];
  for (int i = 0; i < 1024; ++i)
    before[2 * i] = before[2 * i + 1] = 0.5f * sinf(6.28318530718f * 330.0f * i / 44118.0f);
  RenderBlocks(u.state, before, 1024);
  E.set_param(u.state, Param("Wow"), 1.0f);
  E.set_param(u.state, Param("Flutter"), 1.0f);
  float after[2 * 256];
  for (int i = 0; i < 256; ++i) {
    const int frame = i + 1024;
    after[2 * i] = after[2 * i + 1] = 0.5f * sinf(6.28318530718f * 330.0f * frame / 44118.0f);
  }
  RenderBlocks(u.state, after, 256);
  float step = 0.0f;
  for (int i = 1; i < 128; ++i)
    step = fmaxf(step, fabsf(after[2 * i] - after[2 * (i - 1)]));
  Check("live_wow_flutter_are_smoothed", step < 0.10f, step);
}

void Hostile() {
  Unit u(44118.0f, 0xFF);
  E.set_param(u.state, Param("Mix"), 0.65f);
  E.set_param(u.state, Param("Wow"), NAN);
  E.set_param(u.state, Param("Flutter"), INFINITY);
  std::vector<float> x(4096);
  for (size_t i = 0; i < x.size(); i += 2) {
    switch ((i / 2) % 5) {
      case 0: x[i] = NAN; break;
      case 1: x[i] = INFINITY; break;
      case 2: x[i] = -INFINITY; break;
      case 3: x[i] = 1e30f; break;
      default: x[i] = -1e30f; break;
    }
    x[i + 1] = x[i];
  }
  RenderBlocks(u.state, &x[0], static_cast<uint32_t>(x.size() / 2));
  bool ok = true;
  for (size_t i = 0; i < x.size(); ++i) ok = ok && std::isfinite(x[i]) && fabsf(x[i]) <= 16.0f;
  Check("hostile_values_finite_and_bounded", ok);
}
}  // namespace

int main() {
  RateAndSize();
  RateScaling();
  DeterminismAndReset();
  DryAndSmooth();
  ModulationSmoothing();
  Hostile();
  return failed ? 1 : 0;
}
