// fx_echo.cc -- "Echo": a stereo ping-pong delay (FM1_KIND_AUDIO_FX),
// written in this repository. Notes in engines/README.md ("Echo").
//
// Signal flow, per sample and per side:
//
//   in -> guard -> Level -> routing (Ping-pong) -+-> soft clip -> anti-alias
//                                                 ^              -> 16-bit store
//   out <- Mix <- reconstruction <- read (linear) +
//                       |                         |
//                       +-> Tone low-pass -> cross-feed (Ping-pong) x Feedback
//
// Ping-pong 0 is two straight delays, one per side. Ping-pong 1 sends the
// mono sum into the left line only and feeds each line into the other, so the
// repeats alternate left, right, left. In between, both the routing and the
// cross-feed crossfade.
//
// Memory: 16,384 stereo cells of 16-bit words, 65,536 bytes, plus about 200
// bytes of state. The words hold +/-2.0 (16,384 per unit), so the loop has
// 6 dB of headroom over full scale before its soft clip saturates.
//
// Time, 10-1,000 ms. Up to 16,380 cells (371 ms at 44,118 Hz) the line runs at
// the host rate, a plain digital delay. Beyond that the number of cells stays
// fixed and the line's clock slows, as in a bucket-brigade delay: at 1,000 ms
// the cells run at 16.4 kHz, and two-pole low-passes on the way in and out of
// the line (cutoff proportional to the clock) keep it from aliasing much, so
// long echoes are darker, as on those delays. Either way, turning Time glides
// the delay (a 100 ms smoothing), which bends the pitch of what is in the
// line like a tape echo's speed control.
//
// Parameters glide sample by sample from the first render on (before it they
// apply at once): Time and Wow's depth over about 0.1 s, the gains (Feedback,
// Ping-pong, Mix, Level) with a 5 ms one-pole, and Tone's low-pass
// coefficient over 2.5 ms with the shared SMOOTH ramp (fm1_smooth.h, docs/15
// S7b).
//
// Wow: a slow modulation of the delay time, a 0.55 Hz sine plus a smoothed
// random walk from a fixed seed, up to +/-3 ms. Renders stay deterministic.
//
// Stability and silence. Every element of the loop is a convex combination
// (linear interpolation, the one-pole filters, the cross-feed), so none has a
// gain above 1, and Feedback is a loop gain of at most 0.95: the loop cannot
// grow. The 16-bit store truncates towards zero (magnitude truncation), so
// the loop has no dead band in which a small signal recirculates for ever:
// with silent input the line decays to exact zeros, and the float filter
// states are flushed to zero below 1e-15, so no subnormals are left behind.
// Interpolation is linear, not all-pass or cubic, because linear has no
// feedback of its own and never exceeds its inputs, under any modulation.
//
// Inspiration, no code: the ping-pong topology is the textbook stereo delay
// (Zoelzer, "DAFX", 2nd ed., ch. 2); the slowing clock beyond the memory is
// how bucket-brigade echoes set their time; the 16-bit truncating delay word
// is the format of Emilie Gillet's FxEngine in Mutable Instruments' Rings and
// Clouds (MIT); magnitude truncation against limit cycles is standard
// fixed-point filter practice. The input guard is the one in mi_fx.cc.
//
// MIT licence.

#include "fm1_engine.h"
#include "fm1_smooth.h"

#include <cmath>
#include <cstring>
#include <new>

namespace fm1 {
namespace echo {

enum { P_TIME, P_FEEDBACK, P_PINGPONG, P_MIX, P_TONE, P_WOW, P_LEVEL, P_COUNT };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every parameter is read each block: SMOOTH and MOD. Time moves on
// the LOG law (fm1_engine.h, API v3): a ratio a detent, octaves under
// modulation.
const fm1_param_t kParams[P_COUNT] = {
  { "Time",      FM1_PARAM_FLOAT, 10, 1000, 300, NULL, 0, 1, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_MS, "Time" },
  { "Feedback",  FM1_PARAM_FLOAT, 0, 1, 0.4f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Fdbk" },
  { "Ping-pong", FM1_PARAM_FLOAT, 0, 1, 1.0f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "PingPg" },
  { "Mix",       FM1_PARAM_FLOAT, 0, 1, 0.35f, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Tone",      FM1_PARAM_FLOAT, 0, 1, 0.6f, NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Tone" },
  { "Wow",       FM1_PARAM_FLOAT, 0, 1, 0.1f, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Wow" },
  { "Level",     FM1_PARAM_FLOAT, 0, 1, 1.0f, NULL, 1, 7, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Level" },
};

const uint32_t kCells = 16384;                // per side; a power of two
const uint32_t kMask = kCells - 1;
const float kMaxLine = static_cast<float>(kCells - 4);  // longest read, cells
const float kMinDelay = 2.0f;                 // shortest read, cells
const float kWordScale = 16384.0f;            // a word of 16,384 is 1.0
const float kMaxLoopGain = 0.95f;             // Feedback 1
const float kWowMs = 3.0f;                    // Wow 1: +/-3 ms
const float kWowSineHz = 0.55f;
const float kWowRandomHz = 3.0f;              // new random target this often
const float kWowSmoothHz = 1.5f;              // two one-poles smooth the walk
const float kTimeTau = 0.1f;                  // s, Time and Wow depth glide
const float kGainTau = 0.005f;                // s, the gains, against zipper noise
const float kToneLowHz = 400.0f;              // Tone 0; six octaves up at Tone 1
const float kClockFilter = 1.25f;             // anti-alias k = 1.25 x clock ratio
const float kInputLimit = 16.0f;              // the input guard, as mi_fx.cc
const float kFlush = 1e-15f;

inline float Guard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;  // NaN fails both
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                        // NaN
}

inline float Flush(float y) { return (y > -kFlush && y < kFlush) ? 0.0f : y; }

// Linear up to |x| = 1, then bending smoothly towards +/-2 (slope 1 at the
// knee); never larger in magnitude than x.
inline float SoftClip(float x) {
  if (x > 1.0f) { const float u = x - 1.0f; return 1.0f + u / (1.0f + u); }
  if (x < -1.0f) { const float u = -x - 1.0f; return -1.0f - u / (1.0f + u); }
  return x;
}

// Truncates towards zero; NaN, which the loop never produces, stores 0.
inline int16_t Store(float x) {
  float s = x * kWordScale;
  if (s >= 32767.0f) s = 32767.0f;
  else if (s <= -32767.0f) s = -32767.0f;
  else if (!(s == s)) s = 0.0f;
  return static_cast<int16_t>(s);
}

// One-pole coefficient for a time constant of tau seconds.
inline float TauCoefficient(float tau, float rate) { return 1.0f - expf(-1.0f / (tau * rate)); }

// A parameter glide: a one-pole that lands exactly on its target.
struct Glide {
  float value, target;
  void Snap(float v) { value = target = v; }
  void Step(float k, float epsilon) {
    const float d = target - value;
    if (d > -epsilon && d < epsilon) value = target;
    else value += k * d;
  }
};

// No constructor of our own: `new (mem) Instance()` value-initialises, which
// zeroes the whole object, the delay words included.
struct Instance {
  float rate;
  float k_time, k_gain;                       // glide coefficients
  float k_tone;                               // in-loop low-pass coefficient
  fm1_smooth_t k_tone_ramp;                   // its SMOOTH ramp
  uint32_t smooth_steps;                      // samples in a ramp
  float value[P_COUNT];
  bool running;                               // set by the first render
  Glide time, depth;                          // in samples
  Glide feedback, pingpong, mix, level;
  // Wow
  float sine_phase, sine_inc;
  uint32_t seed, random_count, random_period;
  float random_target, random1, random2, k_random;
  // The line
  uint32_t write;                             // the cell written last
  float phase;                                // clock phase past it, [0, 1)
  float prev[2];                              // last sample offered to the line
  float aa1[2], aa2[2];                       // anti-alias, into the line
  float rc1[2], rc2[2];                       // reconstruction, out of the line
  float tone[2];                              // the in-loop damping
  alignas(16) int16_t cells[2 * kCells];      // interleaved left, right

  void Init(const fm1_host_t *host) {
    rate = host->sample_rate;
    k_time = TauCoefficient(kTimeTau, rate);
    k_gain = TauCoefficient(kGainTau, rate);
    sine_inc = kWowSineHz / rate;
    random_period = static_cast<uint32_t>(rate / kWowRandomHz);
    if (random_period < 1) random_period = 1;
    k_random = 1.0f - expf(-6.28318530718f * kWowSmoothHz / rate);
    seed = 0x2545F491u;
    smooth_steps = fm1_smooth_steps(rate, 1);
    for (int i = 0; i < P_COUNT; ++i) value[i] = kParams[i].def;
    for (int i = 0; i < P_COUNT; ++i) Apply(i);
  }

  // Bring one parameter's derived state up to date. Before the first render
  // the glides snap, so parameters set at load take effect from sample 0.
  void Apply(int index) {
    const float v = value[index];
    Glide *g = NULL;
    float target = v;
    switch (index) {
      case P_TIME: g = &time; target = v * 0.001f * rate; break;
      case P_WOW: g = &depth; target = v * kWowMs * 0.001f * rate; break;
      case P_FEEDBACK: g = &feedback; target = v * kMaxLoopGain; break;
      case P_PINGPONG: g = &pingpong; break;
      case P_MIX: g = &mix; break;
      case P_LEVEL: g = &level; break;
      case P_TONE: {
        const float hz = kToneLowHz * powf(2.0f, 6.0f * v);
        fm1_smooth_set(&k_tone_ramp, &k_tone, 1.0f - expf(-6.28318530718f * hz / rate),
                       running ? smooth_steps : 0);
        return;
      }
      default: return;
    }
    if (running) g->target = target;
    else g->Snap(target);
  }

  void Set(uint16_t index, float v) {
    if (index >= P_COUNT) return;
    value[index] = fm1_param_clamp(&kParams[index], v);
    Apply(index);
  }

  // The wow signal, within +/-1.
  float Wow() {
    sine_phase += sine_inc;
    if (sine_phase >= 1.0f) sine_phase -= 1.0f;
    const float t = 2.0f * sine_phase - 1.0f;           // a parabolic sine
    const float sine = -4.0f * t * (1.0f - fabsf(t));
    if (++random_count >= random_period) {
      random_count = 0;
      seed = seed * 1664525u + 1013904223u;
      random_target = static_cast<float>(static_cast<int32_t>(seed)) * (1.0f / 2147483648.0f);
    }
    random1 += k_random * (random_target - random1);
    random2 += k_random * (random1 - random2);
    return 0.6f * sine + 0.4f * random2;
  }

  void Render(float *lr, uint32_t frames) {
    running = true;
    const float max_delay = (kParams[P_TIME].max + kWowMs) * 0.001f * rate;
    for (uint32_t i = 0; i < frames; ++i, lr += 2) {
      const float in[2] = { Guard(lr[0]), Guard(lr[1]) };
      time.Step(k_time, 1e-3f);
      depth.Step(k_time, 1e-3f);
      feedback.Step(k_gain, 1e-6f);
      pingpong.Step(k_gain, 1e-6f);
      mix.Step(k_gain, 1e-6f);
      level.Step(k_gain, 1e-6f);
      if (k_tone_ramp.left) fm1_smooth_tick(&k_tone_ramp, &k_tone, 1);

      // The delay, and the clock that gives it: the full rate while the line
      // is long enough, a slower one beyond.
      float delay = time.value + depth.value * Wow();
      if (!(delay >= kMinDelay)) delay = kMinDelay;
      if (delay > max_delay) delay = max_delay;
      float clock = 1.0f, length = delay;
      if (delay > kMaxLine) { clock = kMaxLine / delay; length = kMaxLine; }
      float k_aa = kClockFilter * clock;
      if (k_aa > 1.0f) k_aa = 1.0f;

      // Read `length` cells behind the write head's position after this
      // sample's advance; with length >= 2 both cells are already written.
      const float r = phase + clock - length;
      const float fl = floorf(r);
      const float frac = r - fl;
      const uint32_t c0 = (write + static_cast<uint32_t>(static_cast<int32_t>(fl))) & kMask;
      const uint32_t c1 = (c0 + 1) & kMask;

      float wet[2], damped[2];
      for (uint32_t s = 0; s < 2; ++s) {
        const float a = cells[2 * c0 + s], b = cells[2 * c1 + s];
        const float x = ((1.0f - frac) * a + frac * b) * (1.0f / kWordScale);
        rc1[s] = Flush((1.0f - k_aa) * rc1[s] + k_aa * x);
        rc2[s] = Flush((1.0f - k_aa) * rc2[s] + k_aa * rc1[s]);
        wet[s] = rc2[s];
        tone[s] = Flush((1.0f - k_tone) * tone[s] + k_tone * wet[s]);
        damped[s] = tone[s];
      }

      const float p = pingpong.value, q = 1.0f - p;
      const float g = feedback.value;
      const float mono = 0.5f * (in[0] + in[1]);
      const float send[2] = { level.value * (q * in[0] + p * mono), level.value * (q * in[1]) };
      const float back[2] = { g * (q * damped[0] + p * damped[1]),
                              g * (q * damped[1] + p * damped[0]) };

      // Offer this sample to the line; the clock writes a cell when its phase
      // crosses one, interpolating between this sample and the last.
      const bool tick = phase + clock >= 1.0f;
      // Where between the last sample and this one the clock ticked; at the
      // full rate that is exactly this sample (t = 1), with no division.
      const float t = !tick ? 0.0f : clock < 1.0f ? (1.0f - phase) / clock : 1.0f - phase;
      if (tick) write = (write + 1) & kMask;
      for (uint32_t s = 0; s < 2; ++s) {
        const float x = SoftClip(send[s] + back[s]);
        aa1[s] = Flush((1.0f - k_aa) * aa1[s] + k_aa * x);
        aa2[s] = Flush((1.0f - k_aa) * aa2[s] + k_aa * aa1[s]);
        if (tick) cells[2 * write + s] = Store((1.0f - t) * prev[s] + t * aa2[s]);
        prev[s] = aa2[s];
      }
      phase = tick ? phase + clock - 1.0f : phase + clock;

      // Mix: the dry stays at full level up to 0.5, the echoes reach it there.
      float dry = 2.0f * (1.0f - mix.value), echo = 2.0f * mix.value;
      if (dry > 1.0f) dry = 1.0f;
      if (echo > 1.0f) echo = 1.0f;
      lr[0] = dry * in[0] + echo * wet[0];
      lr[1] = dry * in[1] + echo * wet[1];
    }
  }
};

inline size_t Round16(size_t n) { return (n + 15u) & ~static_cast<size_t>(15u); }

size_t InstanceSize(const fm1_host_t *) { return Round16(sizeof(Instance)); }

void *Create(void *mem, const fm1_host_t *host) {
  const float rate = host->sample_rate;
  if (!(rate >= 1000.0f && rate <= 1000000.0f)) return NULL;   // NaN fails too
  Instance *self = new (mem) Instance();
  self->Init(host);
  return self;
}
void Destroy(void *s) { static_cast<Instance *>(s)->~Instance(); }
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->Set(i, v); }
void Render(void *s, float *lr, uint32_t n) { static_cast<Instance *>(s)->Render(lr, n); }

}  // namespace echo
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_echo = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "echo", "Echo",
  "This repository (MIT). Ping-pong topology after Zoelzer's DAFX; 16-bit "
  "delay words after Emilie Gillet's FxEngine (Mutable Instruments, MIT)",
  fm1::echo::kParams, fm1::echo::P_COUNT, 0,
  fm1::echo::InstanceSize, fm1::echo::Create, fm1::echo::Destroy,
  NULL, NULL, NULL,
  fm1::echo::Set, fm1::echo::Render,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
};
