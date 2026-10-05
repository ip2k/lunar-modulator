// test_gain.cc -- "Test Gain": the smallest audio effect, a gain stage. It
// exists to test the host's effect chain (FM1_KIND_AUDIO_FX) independently of
// any real effect. MIT licence.
//
// Gain is SMOOTH: from the first render on, a change ramps sample by sample
// over 2.5 ms (fm1_smooth.h); before it, a change applies at once.

#include "fm1_engine.h"
#include "fm1_smooth.h"

#include <new>

namespace fm1 {
namespace test_gain {

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every parameter is read each block: SMOOTH and MOD.
const fm1_param_t kParams[1] = {
  { "Gain", FM1_PARAM_FLOAT, 0, 2, 1.0f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Gain" },
};

struct Instance {
  float gain;
  fm1_smooth_t smooth;      // Gain's ramp
  uint32_t smooth_steps;    // samples in a ramp
  bool started;             // rendered at least once
};

size_t InstanceSize(const fm1_host_t *) { return sizeof(Instance); }
void *Create(void *mem, const fm1_host_t *host) {
  Instance *self = new (mem) Instance();
  self->gain = kParams[0].def;
  fm1_smooth_init(&self->smooth, &self->gain, 1);
  self->smooth_steps = fm1_smooth_steps(host->sample_rate, 1);
  self->started = false;
  return self;
}
void Destroy(void *self) { static_cast<Instance *>(self)->~Instance(); }
void Set(void *s, uint16_t i, float v) {
  Instance *self = static_cast<Instance *>(s);
  if (i == 0) {
    fm1_smooth_set(&self->smooth, &self->gain, fm1_param_clamp(&kParams[0], v),
                   self->started ? self->smooth_steps : 0);
  }
}
void Render(void *s, float *lr, uint32_t n) {
  Instance *self = static_cast<Instance *>(s);
  self->started = true;
  uint32_t f = 0;
  for (; f < n && self->smooth.left; ++f) {    // a ramp: a step per frame
    fm1_smooth_tick(&self->smooth, &self->gain, 1);
    lr[2 * f] *= self->gain;
    lr[2 * f + 1] *= self->gain;
  }
  const float g = self->gain;
  for (uint32_t k = 2 * f; k < 2 * n; ++k) lr[k] *= g;
}

}  // namespace test_gain
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_test_gain = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "test-gain", "Test Gain", "This repository (MIT)",
  fm1::test_gain::kParams, 1, 0,
  fm1::test_gain::InstanceSize, fm1::test_gain::Create, fm1::test_gain::Destroy,
  NULL, NULL, NULL,
  fm1::test_gain::Set, fm1::test_gain::Render,
  NULL,                     // no notes, so no per-note offsets
};
