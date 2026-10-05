// mi_fx.cc -- the first audio effects (FM1_KIND_AUDIO_FX): three stereo
// effects built from Mutable Instruments DSP code by Emilie Gillet (MIT;
// vendored unmodified in third_party/mutable). docs/11 §4; notes in
// engines/mi-fx.md.
//
//   Plate     the reverb from Rings: Dattorro's plate topology (Griesinger
//             loop: four input all-passes, then two all-pass + delay
//             branches in a modulated loop). Mono in (L+R), stereo out.
//             64 KB of 16-bit delay memory.
//   Ensemble  the string-machine ensemble from Plaits: three taps per side
//             on two short delay lines, swept by a slow and a fast LFO at
//             120 degrees. Stereo in, stereo out, with our Width control so
//             a mono source comes out wide. 4 KB of float delay memory.
//   Diffuse   the granular diffuser from Plaits (four all-passes and a
//             modulated feedback delay), with our own tone filter and a
//             one-all-pass-per-side decorrelator so a mono source comes out
//             wide. Mono in (L+R), stereo out. 16 KB of 12-bit delay memory.
//
// Rate: Rings ran at 48,000 Hz and Plaits at 47,872.34 Hz. Delay lengths and
// LFO rates are fixed in samples inside the vendored classes, so at 44,118 Hz
// every delay is 8.8 % (Plate) / 8.5 % (Plaits effects) longer and every LFO
// that much slower. The wrappers rate-compensate what they own: the loop gain
// (so decay time in seconds matches the original) and the in-loop damping
// coefficient of Plate, and the loop gain of Diffuse. See engines/mi-fx.md.
//
// Each effect renders sample by sample, so any block size 1..max_frames gives
// the same output; the wrappers deinterleave in 32-frame chunks on the stack.
// Every input sample passes the input guard first (Guard: NaN to 0, clamped
// to +/-16), so bad input from upstream never reaches the loops.
//
// Every parameter is SMOOTH (fm1_smooth.h): from the first render on, a
// change ramps sample by sample over 2.5 ms of the host's samples, and the
// effect renders one frame at a time while a ramp runs, so the vendored
// classes, which take their settings per call, see each step. What ramps is
// what the effect runs on: Mix and Width as set, and Plate's loop gain and
// damping, Diffuse's loop gain and tone coefficient as derived from Decay,
// Damping, Time and Tone, so the ramp needs no libm. Before the first render
// a change applies at once.
//
// MIT licence (this file). Not affiliated with or endorsed by Mutable
// Instruments; effect names here are our own (docs/11 §7).

#include "fm1_engine.h"
#include "fm1_smooth.h"

#include <cmath>
#include <new>

#include "plaits/dsp/dsp.h"
#include "plaits/dsp/fx/diffuser.h"
#include "plaits/dsp/fx/ensemble.h"
#include "rings/dsp/fx/reverb.h"

namespace fm1 {
namespace mi_fx {

const uint32_t kChunk = 32;                   // frames deinterleaved at a time
const float kTwoPi = 6.28318530718f;

// Rings' kSampleRate (rings/dsp/dsp.h, not vendored: nothing else is used).
const float kRingsRate = 48000.0f;

inline float Clamp(const fm1_param_t &p, float v) {
  if (!(v >= p.min)) v = p.min;               // also maps NaN to min
  if (!(v <= p.max)) v = p.max;
  return v;
}

// A loop gain g per pass, made to give the same decay per second at the host
// rate as at the native one (the loop is the same number of samples, so it
// takes native/host times longer per pass).
inline float RateLoopGain(float g, float native_over_host) {
  return powf(g, native_over_host);
}

// A one-pole coefficient k (y += k * (x - y)) with the same cutoff in Hz.
inline float RateOnePole(float k, float native_over_host) {
  return 1.0f - powf(1.0f - k, native_over_host);
}

inline size_t Round16(size_t n) { return (n + 15u) & ~static_cast<size_t>(15u); }

// The input guard, applied to every input sample before anything else sees
// it, the dry path included: NaN becomes 0, and anything beyond
// +/-kInputLimit, infinities included, is clamped. Without it one non-finite
// sample poisons the float state of Plate's and Diffuse's loops for good
// (their crossfades compute NaN * 0 = NaN, so not even Mix 0 isolates it),
// and an L+R beyond about 330,000 (Plate) or 1,000,000 (Diffuse) overflows
// the vendored float-to-int32 stores, which is undefined behaviour. +/-16
// (+24 dBFS) is far above anything the bus carries and far below either
// limit. Relies on IEEE comparisons: do not build with -ffinite-math-only
// (or -ffast-math). engines/mi-fx.md, "Input guard".
const float kInputLimit = 16.0f;

inline float Guard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;  // NaN fails both
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                        // NaN
}

// ---------------------------------------------------------------------------
// Plate
// ---------------------------------------------------------------------------
namespace plate {

enum { P_MIX, P_DECAY, P_DAMPING, P_DIFFUSION, P_COUNT };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every parameter is read each block: SMOOTH and MOD.
const fm1_param_t kParams[P_COUNT] = {
  { "Mix",       FM1_PARAM_FLOAT, 0, 1, 0.3f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Decay",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Decay" },
  { "Damping",   FM1_PARAM_FLOAT, 0, 1, 0.3f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Damp" },
  { "Diffusion", FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Diffus" },
};

// rings::Reverb is FxEngine<32768, FORMAT_16_BIT>: 32,768 uint16_t words.
const size_t kDelayWords = 32768;

// No constructor of our own: `new (mem) Instance()` value-initialises, which
// zeroes the whole object first. rings::Reverb leaves its two damping-filter
// states to be set by the first Process call; zeroing covers them.
struct Instance {
  rings::Reverb reverb;
  float value[P_COUNT];
  float coef[P_COUNT];                        // what the reverb runs on (Coef)
  fm1_smooth_t smooth[P_COUNT];               // their ramps
  uint32_t smooth_steps;
  bool started;                               // rendered at least once
  float native_over_host;
  alignas(16) uint16_t delay[kDelayWords];

  void Init(const fm1_host_t *host) {
    native_over_host = kRingsRate / host->sample_rate;
    reverb.Init(delay);                       // clears the delay memory
    for (int i = 0; i < P_COUNT; ++i) value[i] = kParams[i].def;
    for (int i = 0; i < P_COUNT; ++i) coef[i] = Coef(i);
    fm1_smooth_init(smooth, coef, P_COUNT);
    smooth_steps = fm1_smooth_steps(host->sample_rate, 1);
    started = false;
    Apply();
  }

  // Ranges follow Rings (time 0.35..0.98 in part.cc, lp 0.3..0.9) and
  // Elements (diffusion 0.55..0.70 around the default 0.625), widened a
  // little for diffusion. Input gain 0.2 is what every upstream user sets.
  float Coef(int index) const {
    switch (index) {
      case P_MIX: return value[P_MIX];
      case P_DECAY: return RateLoopGain(0.35f + 0.63f * value[P_DECAY], native_over_host);
      case P_DAMPING: return RateOnePole(0.9f - 0.6f * value[P_DAMPING], native_over_host);
      default: return 0.5f + 0.25f * value[P_DIFFUSION];
    }
  }

  void Apply() {
    reverb.set_amount(coef[P_MIX]);
    reverb.set_input_gain(0.2f);
    reverb.set_time(coef[P_DECAY]);
    reverb.set_lp(coef[P_DAMPING]);
    reverb.set_diffusion(coef[P_DIFFUSION]);
  }

  void Set(uint16_t index, float v) {
    if (index >= P_COUNT) return;
    value[index] = Clamp(kParams[index], v);
    fm1_smooth_set(&smooth[index], &coef[index], Coef(index), started ? smooth_steps : 0);
    Apply();
  }

  void Render(float *lr, uint32_t frames) {
    float l[kChunk], r[kChunk];
    started = true;
    while (frames) {
      // While a ramp runs, one frame at a time, each with its step.
      const bool ramp = fm1_smooth_moving(smooth, P_COUNT) != 0;
      if (ramp) {
        fm1_smooth_tick(smooth, coef, P_COUNT);
        Apply();
      }
      const uint32_t n = ramp ? 1u : (frames < kChunk ? frames : kChunk);
      for (uint32_t i = 0; i < n; ++i) {
        l[i] = Guard(lr[2 * i]);              // the dry path too: upstream
        r[i] = Guard(lr[2 * i + 1]);          // crossfades l, r in place
      }
      reverb.Process(l, r, n);
      for (uint32_t i = 0; i < n; ++i) { lr[2 * i] = l[i]; lr[2 * i + 1] = r[i]; }
      lr += 2 * n;
      frames -= n;
    }
  }
};

size_t InstanceSize(const fm1_host_t *) { return Round16(sizeof(Instance)); }
void *Create(void *mem, const fm1_host_t *host) {
  Instance *self = new (mem) Instance();
  self->Init(host);
  return self;
}
void Destroy(void *s) { static_cast<Instance *>(s)->~Instance(); }
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->Set(i, v); }
void Render(void *s, float *lr, uint32_t n) { static_cast<Instance *>(s)->Render(lr, n); }

}  // namespace plate

// ---------------------------------------------------------------------------
// Ensemble
// ---------------------------------------------------------------------------
namespace ensemble {

enum { P_MIX, P_DEPTH, P_WIDTH, P_COUNT };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every parameter is read each block: SMOOTH and MOD.
const fm1_param_t kParams[P_COUNT] = {
  { "Mix",   FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Depth", FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Depth" },
  { "Width", FM1_PARAM_FLOAT, 0, 1, 1.0f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Width" },
};

// plaits::Ensemble is FxEngine<1024, FORMAT_32_BIT>: 1,024 floats.
const size_t kDelayWords = 1024;

// Plaits' ensemble reads the same three LFO phases for both outputs and only
// swaps which delay line feeds the third tap, so a mono input (every FM-1
// engine so far) gives L == R. Width feeds the right line a copy of the right
// input delayed by kOffset samples (3 ms at 44,118 Hz), which moves the
// right-hand taps away from the left-hand ones. Width 0 behaves as upstream.
const uint32_t kOffset = 131;

struct Instance {
  plaits::Ensemble ensemble;
  float offset_line[kOffset];
  uint32_t offset_pos;
  float value[P_COUNT];                       // as the effect runs on them (ramped)
  fm1_smooth_t smooth[P_COUNT];
  uint32_t smooth_steps;
  bool started;                               // rendered at least once
  alignas(16) plaits::Ensemble::E::T delay[kDelayWords];

  void Init(const fm1_host_t *host) {
    ensemble.Init(delay);
    ensemble.Reset();                         // Plaits' Init does not clear
    ensemble.set_amount(1.0f);                // see Render
    // Value-initialisation already zeroed offset_line and offset_pos.
    for (int i = 0; i < P_COUNT; ++i) value[i] = kParams[i].def;
    fm1_smooth_init(smooth, value, P_COUNT);
    smooth_steps = fm1_smooth_steps(host->sample_rate, 1);
    started = false;
    Apply();
  }

  void Apply() { ensemble.set_depth(value[P_DEPTH]); }

  void Set(uint16_t index, float v) {
    if (index >= P_COUNT) return;
    fm1_smooth_set(&smooth[index], &value[index], Clamp(kParams[index], v),
                   started ? smooth_steps : 0);
    Apply();
  }

  // Upstream mixes in place as out = wet * amount + in * (1 - amount / 2).
  // It runs here at amount 1, the wet is recovered as out - in / 2, and the
  // same law is applied with Mix against the real dry input, so the right
  // line's offset copy never reaches the dry path and Mix 0 passes the input
  // through untouched.
  void Render(float *lr, uint32_t frames) {
    float l[kChunk], r[kChunk], r_line[kChunk];
    started = true;
    while (frames) {
      // While a ramp runs, one frame at a time, each with its step.
      const bool ramp = fm1_smooth_moving(smooth, P_COUNT) != 0;
      if (ramp) {
        fm1_smooth_tick(smooth, value, P_COUNT);
        Apply();
      }
      const uint32_t n = ramp ? 1u : (frames < kChunk ? frames : kChunk);
      const float mix = value[P_MIX];
      const float dry_gain = 1.0f - 0.5f * mix;
      const float width = value[P_WIDTH];
      for (uint32_t i = 0; i < n; ++i) {
        const float in_l = Guard(lr[2 * i]);
        const float in_r = Guard(lr[2 * i + 1]);
        lr[2 * i] = in_l;                     // the dry path, guarded too
        lr[2 * i + 1] = in_r;
        const float late = offset_line[offset_pos];
        offset_line[offset_pos] = in_r;
        if (++offset_pos == kOffset) offset_pos = 0;
        l[i] = in_l;
        r[i] = r_line[i] = in_r + width * (late - in_r);
      }
      ensemble.Process(l, r, n);
      for (uint32_t i = 0; i < n; ++i) {
        float &out_l = lr[2 * i];
        float &out_r = lr[2 * i + 1];
        const float wet_l = l[i] - 0.5f * out_l;
        const float wet_r = r[i] - 0.5f * r_line[i];
        out_l = wet_l * mix + out_l * dry_gain;
        out_r = wet_r * mix + out_r * dry_gain;
      }
      lr += 2 * n;
      frames -= n;
    }
  }
};

size_t InstanceSize(const fm1_host_t *) { return Round16(sizeof(Instance)); }
void *Create(void *mem, const fm1_host_t *host) {
  Instance *self = new (mem) Instance();
  self->Init(host);
  return self;
}
void Destroy(void *s) { static_cast<Instance *>(s)->~Instance(); }
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->Set(i, v); }
void Render(void *s, float *lr, uint32_t n) { static_cast<Instance *>(s)->Render(lr, n); }

}  // namespace ensemble

// ---------------------------------------------------------------------------
// Diffuse
// ---------------------------------------------------------------------------
namespace diffuse {

enum { P_MIX, P_TIME, P_TONE, P_WIDTH, P_COUNT };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every parameter is read each block: SMOOTH and MOD.
const fm1_param_t kParams[P_COUNT] = {
  { "Mix",   FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Time",  FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Time" },
  { "Tone",  FM1_PARAM_FLOAT, 0, 1, 0.75f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Tone" },
  { "Width", FM1_PARAM_FLOAT, 0, 1, 1.0f, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Width" },
};

// plaits::Diffuser is FxEngine<8192, FORMAT_12_BIT>: 8,192 uint16_t words.
const size_t kDelayWords = 8192;

// A Schroeder all-pass, (-g + z^-N) / (1 - g z^-N): flat magnitude, scattered
// phase. One per side, with different lengths, decorrelates the two outputs.
template<size_t N>
struct AllPass {
  float line[N];
  uint32_t pos;

  float Process(float x, float g) {
    const float delayed = line[pos];
    const float v = x + g * delayed;
    line[pos] = v;
    if (++pos == N) pos = 0;
    return delayed - g * v;
  }
};

const float kDecorrelation = 0.5f;            // all-pass coefficient
// Upstream emits the wet at twice the loop level (c.Write(del, 2.0f)), about
// 5 dB above the Plate's wet for the same input; halve it on the way out.
// The loop itself, and so its 12-bit headroom, is exactly upstream's.
const float kWetGain = 0.5f;

struct Instance {
  plaits::Diffuser diffuser;
  AllPass<241> ap_l;                          // 5.5 ms at 44,118 Hz
  AllPass<349> ap_r;                          // 7.9 ms
  float lp_l, lp_r;                           // tone filter states
  float value[P_COUNT];
  // What the effect runs on (Coef): Mix, the loop gain rt, the tone
  // coefficient and Width.
  float coef[P_COUNT];
  fm1_smooth_t smooth[P_COUNT];               // their ramps
  uint32_t smooth_steps;
  bool started;                               // rendered at least once
  float native_over_host, host_rate;
  alignas(16) uint16_t delay[kDelayWords];

  void Init(const fm1_host_t *host) {
    host_rate = host->sample_rate;
    native_over_host = plaits::kCorrectedSampleRate / host->sample_rate;
    diffuser.Init(delay);
    diffuser.Reset();                         // Plaits' Init does not clear
    // Value-initialisation already zeroed the all-passes and filter states.
    for (int i = 0; i < P_COUNT; ++i) value[i] = kParams[i].def;
    for (int i = 0; i < P_COUNT; ++i) coef[i] = Coef(i);
    fm1_smooth_init(smooth, coef, P_COUNT);
    smooth_steps = fm1_smooth_steps(host->sample_rate, 1);
    started = false;
  }

  // Plaits' particle engine drives rt over 0.25..0.75; the range here goes
  // on to 0.9 for longer tails. Tone is a one-pole low-pass on the wet
  // signal from 250 Hz (0) to beyond Nyquist (1).
  float Coef(int index) const {
    switch (index) {
      case P_TIME: return RateLoopGain(0.25f + 0.65f * value[P_TIME], native_over_host);
      case P_TONE: {
        const float fc = 250.0f * powf(2.0f, 7.0f * value[P_TONE]);
        return 1.0f - expf(-kTwoPi * fc / host_rate);
      }
      default: return value[index];         // Mix, Width
    }
  }

  void Set(uint16_t index, float v) {
    if (index >= P_COUNT) return;
    value[index] = Clamp(kParams[index], v);
    fm1_smooth_set(&smooth[index], &coef[index], Coef(index), started ? smooth_steps : 0);
  }

  void Render(float *lr, uint32_t frames) {
    float wet[kChunk];
    started = true;
    while (frames) {
      // While a ramp runs, one frame at a time, each with its step.
      const bool ramp = fm1_smooth_moving(smooth, P_COUNT) != 0;
      if (ramp) fm1_smooth_tick(smooth, coef, P_COUNT);
      const uint32_t n = ramp ? 1u : (frames < kChunk ? frames : kChunk);
      const float mix = coef[P_MIX];
      const float width = coef[P_WIDTH];
      const float k = coef[P_TONE];
      const float rt = coef[P_TIME];
      for (uint32_t i = 0; i < n; ++i) {
        const float in_l = Guard(lr[2 * i]);
        const float in_r = Guard(lr[2 * i + 1]);
        lr[2 * i] = in_l;                     // the dry path, guarded too
        lr[2 * i + 1] = in_r;
        wet[i] = 0.5f * (in_l + in_r);
      }
      diffuser.Process(1.0f, rt, wet, n);     // amount 1: wet only; we mix
      for (uint32_t i = 0; i < n; ++i) {
        const float w = kWetGain * wet[i];
        const float wl = w + width * (ap_l.Process(w, kDecorrelation) - w);
        const float wr = w + width * (ap_r.Process(w, kDecorrelation) - w);
        lp_l += k * (wl - lp_l);
        lp_r += k * (wr - lp_r);
        float &l = lr[2 * i];
        float &r = lr[2 * i + 1];
        l += mix * (lp_l - l);
        r += mix * (lp_r - r);
      }
      lr += 2 * n;
      frames -= n;
    }
  }
};

size_t InstanceSize(const fm1_host_t *) { return Round16(sizeof(Instance)); }
void *Create(void *mem, const fm1_host_t *host) {
  Instance *self = new (mem) Instance();
  self->Init(host);
  return self;
}
void Destroy(void *s) { static_cast<Instance *>(s)->~Instance(); }
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->Set(i, v); }
void Render(void *s, float *lr, uint32_t n) { static_cast<Instance *>(s)->Render(lr, n); }

}  // namespace diffuse

}  // namespace mi_fx
}  // namespace fm1

#define FM1_MI_FX(sym, ns, id, name, credits)                                  \
  extern "C" const fm1_engine_t sym = {                                        \
    FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,               \
    id, name, credits,                                                         \
    fm1::mi_fx::ns::kParams, fm1::mi_fx::ns::P_COUNT, 0,                       \
    fm1::mi_fx::ns::InstanceSize, fm1::mi_fx::ns::Create,                      \
    fm1::mi_fx::ns::Destroy, NULL, NULL, NULL,                                 \
    fm1::mi_fx::ns::Set, fm1::mi_fx::ns::Render,                               \
    NULL,                     /* no notes, so no per-note offsets */           \
  }

FM1_MI_FX(fm1_engine_plate, plate, "plate", "Plate",
          "Reverb from Mutable Instruments Rings by Emilie Gillet (MIT)");
FM1_MI_FX(fm1_engine_ensemble, ensemble, "ensemble", "Ensemble",
          "Ensemble from Mutable Instruments Plaits by Emilie Gillet (MIT)");
FM1_MI_FX(fm1_engine_diffuse, diffuse, "diffuse", "Diffuse",
          "Diffuser from Mutable Instruments Plaits by Emilie Gillet (MIT); "
          "tone filter and decorrelator from this repository (MIT)");
