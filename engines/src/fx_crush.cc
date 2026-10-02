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

#include "fm1_engine.h"

#include <math.h>
#include <new>

namespace fm1 {
namespace crush {

enum { P_BITS, P_RATE, P_JITTER, P_MIX, P_TONE, P_LEVEL, P_COUNT };

const fm1_param_t kParams[P_COUNT] = {
  { "Bits",   FM1_PARAM_FLOAT, 1, 16, 8.0f,  NULL, 0 },
  { "Rate",   FM1_PARAM_FLOAT, 0, 1,  0.75f, NULL, 0 },
  { "Jitter", FM1_PARAM_FLOAT, 0, 1,  0.0f,  NULL, 0 },
  { "Mix",    FM1_PARAM_FLOAT, 0, 1,  1.0f,  NULL, 0 },
  { "Tone",   FM1_PARAM_FLOAT, 0, 1,  1.0f,  NULL, 1 },
  { "Level",  FM1_PARAM_FLOAT, 0, 2,  1.0f,  NULL, 1 },
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

  // Derived from the parameters by Apply().
  float step, inv_step;    // quantiser step and its inverse
  float interval;          // mean hold interval in samples, >= 1
  float spread;            // kJitterDepth * Jitter
  float tone_pole;         // one-pole feedback, 1 - coefficient; 0 = no filter
  float level, mix;

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
    interval = 1.0f;
    Apply();
  }

  void Apply() {
    step = exp2f(1.0f - value[P_BITS]);
    inv_step = exp2f(value[P_BITS] - 1.0f);
    interval = powf(host_over_min, 1.0f - value[P_RATE]);
    if (!(interval >= 1.0f)) interval = 1.0f;
    // A faster rate takes effect now rather than after the current hold.
    if (countdown > interval) countdown = interval;
    spread = kJitterDepth * value[P_JITTER];
    tone_pole = 1.0f - powf(tone_k0, 1.0f - value[P_TONE]);
    level = value[P_LEVEL];
    mix = value[P_MIX];
  }

  void Set(uint16_t index, float v) {
    if (index >= P_COUNT) return;
    value[index] = fm1_param_clamp(&kParams[index], v);
    Apply();
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

  void Render(float *lr, uint32_t frames) {
    const float wet_gain = mix * level, dry_gain = 1.0f - mix;
    for (uint32_t f = 0; f < frames; ++f) {
      const float x0 = Guard(lr[2 * f]), x1 = Guard(lr[2 * f + 1]);
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
      lr[2 * f] = x0 * dry_gain + lp[0] * wet_gain;
      lr[2 * f + 1] = x1 * dry_gain + lp[1] * wet_gain;
    }
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
