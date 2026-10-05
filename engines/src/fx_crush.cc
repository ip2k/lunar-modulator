// fx_crush.cc -- "Crush": a bitcrusher and sample-rate reducer, that is an
// audio-rate sample-and-hold followed by a quantiser (FM1_KIND_AUDIO_FX).
// Written for this repository, MIT licence. The pairing of a decimator and a
// bit reducer follows DaisySP's Decimator and Bitcrush (Electro-Smith, MIT);
// no DaisySP code is used. C++11 in a plain-C style (one struct, no heap, no
// library beyond libm), in a .cc file so the simulator's build links it like
// every other engine (sim/web/mk/sim.mk links the OUR_SRC objects).
//
// Per frame, both channels sharing one hold clock:
//
//   guard -> hold (Rate, Jitter) -> quantise (Bits) -> low-pass (Tone)
//         -> x Level = wet;   out = dry * (1 - Mix) + wet * Mix
//
//   Bits    1..16, fractional for smooth sweeps. The quantiser step is
//           2^(1 - Bits), the step of a Bits-bit converter spanning +/-1.
//           Mid-tread (round to nearest step), so silence stays silent and
//           no DC appears; at 1 bit the levels are -1, 0 and +1.
//   Rate    0..1, the hold rate on a log scale from 100 Hz (0) to the host
//           rate (1): interval = (host / 100 Hz)^(1 - Rate) samples. At 1
//           every sample is taken, so Rate 1 with Bits 16 is all but
//           transparent. A fractional interval is kept as a running count,
//           so the mean rate is exact and holds last floor or ceil samples.
//   Jitter  0..1, random variation of each hold interval: interval *
//           (1 + 0.9 * Jitter * u), u uniform in [-1, 1), at least one
//           sample. The mean rate is unchanged while no draw falls under
//           one sample (holds of 10 samples or more); faster, the floor
//           lengthens it, by 22.5 % at Rate 1 and Jitter 1. Without the
//           floor the countdown would drift like a random walk at Rate 1.
//           u comes from a xorshift32 generator owned by the instance and
//           seeded the same way in every create, so renders are
//           deterministic.
//   Mix     0..1, a linear crossfade; 0 is the dry signal exactly.
//   Tone    0..1 (page 2), a one-pole low-pass on the wet signal: its
//           coefficient is k0^(1 - Tone), k0 for a 150 Hz cutoff, so the
//           cutoff rises roughly exponentially and Tone 1 (k = 1) is no
//           filter at all.
//   Level   0..2 (page 2), the wet signal's gain.
//
// Input guard as in mi_fx.cc: NaN reads as 0 and anything beyond +/-16 is
// clamped, dry path included, so no state ever holds a non-finite value and a
// bad sample from upstream cannot latch the effect. The low-pass state is
// flushed to zero below 1e-20 so a decaying tail never goes subnormal.
//
// Renders sample by sample: any block size gives the same output.
//
// Every parameter is SMOOTH (fm1_smooth.h): from the first render on, a
// change ramps sample by sample over 2.5 ms. What ramps is what the frame
// loop runs on, derived once per change (with libm, as before): the
// quantiser step (its inverse is 1 / step during a Bits ramp, and exp2f's
// value again at the end), the hold interval, the jitter spread, the
// low-pass pole, Mix and Level. Before the first render a change applies at
// once.

#include "fm1_engine.h"
#include "fm1_smooth.h"

#include <math.h>
#include <new>

namespace fm1 {
namespace crush {

enum { P_BITS, P_RATE, P_JITTER, P_MIX, P_TONE, P_LEVEL, P_COUNT };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every parameter is read each block: SMOOTH and MOD.
const fm1_param_t kParams[P_COUNT] = {
  { "Bits",   FM1_PARAM_FLOAT, 1, 16, 8.0f,  NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Bits" },
  { "Rate",   FM1_PARAM_FLOAT, 0, 1,  0.75f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Rate" },
  { "Jitter", FM1_PARAM_FLOAT, 0, 1,  0.0f,  NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Jitter" },
  { "Mix",    FM1_PARAM_FLOAT, 0, 1,  1.0f,  NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Tone",   FM1_PARAM_FLOAT, 0, 1,  1.0f,  NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Tone" },
  { "Level",  FM1_PARAM_FLOAT, 0, 2,  1.0f,  NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Level" },
};

const float kMinRateHz = 100.0f;     // Rate 0
const float kJitterDepth = 0.9f;     // Jitter 1: intervals 0.1x..1.9x
const float kToneMinHz = 150.0f;     // Tone 0
const float kInputLimit = 16.0f;     // the input guard, +24 dBFS
const float kFlush = 1e-20f;         // low-pass state below this is zero
const uint32_t kSeed = 0x2545F491u;  // any nonzero xorshift32 state

inline float Guard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   // NaN fails both
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         // NaN
}

inline size_t Round16(size_t n) { return (n + 15u) & ~static_cast<size_t>(15u); }

struct Instance {
  float value[P_COUNT];    // parameters as set, clamped
  float rate;              // host sample rate
  float host_over_min;     // host rate / kMinRateHz, at least 1
  float tone_k0;           // one-pole coefficient at Tone 0

  // Derived from the parameters (Target), each ramped by ramp[] (Field).
  float step, inv_step;    // quantiser step and its inverse
  float interval;          // mean hold interval in samples, >= 1
  float spread;            // kJitterDepth * Jitter
  float tone_pole;         // one-pole feedback, 1 - coefficient; 0 = no filter
  float level, mix;
  float inv_target;        // inv_step once a Bits ramp ends
  fm1_smooth_t ramp[P_COUNT];
  uint32_t smooth_steps;
  bool started;            // rendered at least once

  // State.
  float countdown;         // samples until the next capture
  float held[2];           // the last captured frame, quantised
  float lp[2];             // the low-pass state
  uint32_t rng;            // xorshift32

  void Init(float sample_rate) {
    rate = sample_rate;
    host_over_min = rate / kMinRateHz;
    if (!(host_over_min >= 1.0f)) host_over_min = 1.0f;
    tone_k0 = 1.0f - expf(-6.28318530718f * kToneMinHz / rate);
    for (int i = 0; i < P_COUNT; ++i) value[i] = kParams[i].def;
    countdown = 0.0f;                 // the first frame is captured at once
    held[0] = held[1] = 0.0f;
    lp[0] = lp[1] = 0.0f;
    rng = kSeed;
    for (int i = 0; i < P_COUNT; ++i) {
      *Field(i) = Target(i);
      fm1_smooth_init(&ramp[i], Field(i), 1);
    }
    inv_step = inv_target = exp2f(value[P_BITS] - 1.0f);
    smooth_steps = fm1_smooth_steps(rate, 1);
    started = false;
  }

  // What parameter i sets, and where.
  float Target(int i) const {
    switch (i) {
      case P_BITS: return exp2f(1.0f - value[P_BITS]);
      case P_RATE: {
        const float n = powf(host_over_min, 1.0f - value[P_RATE]);
        return n >= 1.0f ? n : 1.0f;
      }
      case P_JITTER: return kJitterDepth * value[P_JITTER];
      case P_MIX: return value[P_MIX];
      case P_TONE: return 1.0f - powf(tone_k0, 1.0f - value[P_TONE]);
      default: return value[P_LEVEL];
    }
  }

  float *Field(int i) {
    switch (i) {
      case P_BITS: return &step;
      case P_RATE: return &interval;
      case P_JITTER: return &spread;
      case P_MIX: return &mix;
      case P_TONE: return &tone_pole;
      default: return &level;
    }
  }

  void Set(uint16_t index, float v) {
    if (index >= P_COUNT) return;
    value[index] = fm1_param_clamp(&kParams[index], v);
    fm1_smooth_set(&ramp[index], Field(index), Target(index), started ? smooth_steps : 0);
    if (index == P_BITS) {
      inv_target = exp2f(value[P_BITS] - 1.0f);
      if (!ramp[P_BITS].left) inv_step = inv_target;
    }
    // A faster rate takes effect now rather than after the current hold.
    if (countdown > interval) countdown = interval;
  }

  // One frame of every ramp.
  void Tick() {
    for (int i = 0; i < P_COUNT; ++i) fm1_smooth_tick(&ramp[i], Field(i), 1);
    inv_step = ramp[P_BITS].left ? 1.0f / step : inv_target;
    if (countdown > interval) countdown = interval;
  }

  float NextInterval() {
    rng ^= rng << 13;
    rng ^= rng >> 17;
    rng ^= rng << 5;
    // u in [-1, 1): the top bits as a signed fraction.
    const float u = static_cast<float>(static_cast<int32_t>(rng)) * (1.0f / 2147483648.0f);
    const float n = interval * (1.0f + spread * u);
    return n >= 1.0f ? n : 1.0f;
  }

  float Quantise(float x) const { return step * floorf(x * inv_step + 0.5f); }

  // One frame, in place.
  void Frame(float *io, float wet_gain, float dry_gain) {
    const float x0 = Guard(io[0]), x1 = Guard(io[1]);
    if (countdown <= 0.0f) {
      held[0] = Quantise(x0);
      held[1] = Quantise(x1);
      countdown += NextInterval();   // the generator runs at every capture
    }
    countdown -= 1.0f;
    // lp += k * (held - lp), written so that k = 1 gives held exactly.
    lp[0] = held[0] + tone_pole * (lp[0] - held[0]);
    lp[1] = held[1] + tone_pole * (lp[1] - held[1]);
    if (!(fabsf(lp[0]) >= kFlush)) lp[0] = 0.0f;
    if (!(fabsf(lp[1]) >= kFlush)) lp[1] = 0.0f;
    io[0] = x0 * dry_gain + lp[0] * wet_gain;
    io[1] = x1 * dry_gain + lp[1] * wet_gain;
  }

  void Render(float *lr, uint32_t frames) {
    started = true;
    uint32_t f = 0;
    for (; f < frames && fm1_smooth_moving(ramp, P_COUNT); ++f) {   // a step per frame
      Tick();
      Frame(&lr[2 * f], mix * level, 1.0f - mix);
    }
    const float wet_gain = mix * level, dry_gain = 1.0f - mix;
    for (; f < frames; ++f) Frame(&lr[2 * f], wet_gain, dry_gain);
  }
};

size_t InstanceSize(const fm1_host_t *) { return Round16(sizeof(Instance)); }

void *Create(void *mem, const fm1_host_t *host) {
  if (!(host->sample_rate >= 1000.0f && host->sample_rate <= 1e6f)) return NULL;
  Instance *self = new (mem) Instance;   // default-init: Init sets every field
  self->Init(host->sample_rate);
  return self;
}

void Destroy(void *self) { static_cast<Instance *>(self)->~Instance(); }

void Set(void *self, uint16_t index, float value) {
  static_cast<Instance *>(self)->Set(index, value);
}

void Render(void *self, float *lr, uint32_t frames) {
  static_cast<Instance *>(self)->Render(lr, frames);
}

}  // namespace crush
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_crush = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "crush", "Crush",
  "This repository (MIT); after DaisySP's Decimator and Bitcrush "
  "(Electro-Smith, MIT), no code copied",
  fm1::crush::kParams, fm1::crush::P_COUNT, 0,
  fm1::crush::InstanceSize, fm1::crush::Create, fm1::crush::Destroy,
  NULL, NULL, NULL,
  fm1::crush::Set, fm1::crush::Render,
};
