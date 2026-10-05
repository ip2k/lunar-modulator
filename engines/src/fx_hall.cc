// fx_hall.cc -- "Hall": a stereo hall reverb on an eight-line feedback delay
// network (FM1_KIND_AUDIO_FX), written in this repository. Notes in
// engines/README.md ("Hall").
//
// Signal flow, per sample:
//
//   L, R -> guard -> mono sum -> Low Cut (one-pole high-pass)
//        -> x (1 - Freeze) -> pre-delay (16-bit, 0-150 ms)
//        -> four Schroeder all-passes in series (Diffusion)
//        -> into all eight lines, signs +/- (a fixed pattern)
//
//   eight delay lines (16-bit, read with linear interpolation, each length
//   scaled by Size and moved by its own slow random walk, Mod)
//        -> the reads: four lines to each side, signs +/- -> Width
//        -> the reads: a first-order shelf each (Decay below the crossover,
//           Damping above it) -> 8 x 8 Hadamard mix -> plus the input
//           -> 16-bit store (rounding, saturating), back into the lines
//
//   out = dry x input + wet x (the sides), Echo's mix law
//
// This is Jot's feedback delay network (J.-M. Jot and A. Chaigne, "Digital
// delay networks for designing artificial reverberators", AES 90th
// Convention, 1991): delays of incommensurate lengths fed back through an
// orthogonal matrix, with a gain per line set from its length, so that every
// line loses the same number of decibels per second and the decay time does
// not depend on which line a sound is in. The structure follows the research
// in notes/2026-10-02-delay-reverb-eq-gates-options.md section 3.2, whose
// models were schwung-work's "Voidspace" (MIT) and Geraint Luff's Signalsmith
// "basics" library (MIT); no code from either. The all-pass input diffuser is the one of Schroeder's 1962
// reverberator, with the coefficients Dattorro gives for his plate's input
// diffusers ("Effect Design, Part 1", JAES 1997); the 16-bit truncating delay
// words follow Emilie Gillet's FxEngine (Mutable Instruments, MIT), as Echo's
// do. Every constant here was chosen here.
//
// Mixing matrix. The 8 x 8 Hadamard matrix scaled by 1/sqrt(8), applied as a
// fast Walsh-Hadamard transform (24 additions and subtractions, 8 products).
// Every line feeds every other with the same weight, so the echo density
// grows faster than with the 8-line Householder matrix (I - J/4), which keeps
// three quarters of each line on its own path. Both are orthogonal.
//
// Stability. The Hadamard mix is orthogonal (energy-preserving), each line's
// shelf has a gain of at most g < 1 at every frequency (a first-order filter
// with a real pole and zero has a monotonic magnitude, from g at DC to h <= g
// at Nyquist), and linear interpolation is a convex combination, so the loop
// gain is below 1 at every setting, Freeze included (an hour's decay, never an
// infinite one), and every g is capped at 1 - 2^-16. The stores saturate at
// the 16-bit limits (+/-2.0), so nothing can grow without bound whatever
// happens, even while Size or Mod move the delays.
//
// Silence. Small words truncate towards zero (magnitude truncation), so no
// small signal recirculates for ever: with the input silent the lines reach
// exact zeros, and the wet output, read only from the lines, is exactly 0.
// Larger words round to nearest, so long decays keep their length (LineWord).
// The float filter states flush to zero. Silence in gives exact silence out
// once the tail has gone.
//
// Determinism. No libm anywhere in this file: the one exponential it needs
// (HallExp2) is a polynomial written here, and every operation is a single
// IEEE add, multiply or divide, with fused multiply-adds turned off below, so
// a native build and the browser's WebAssembly compute the same bits. Slow
// controls update every 16 samples, counted from create, and delays ramp
// sample by sample between updates; the gains glide per sample. Any block
// size gives the same output.
//
// Memory: two rings of 16-bit words whose sizes are powers of two, as in
// FxEngine, so every access is one mask: 16,384 words for the eight lines and
// 8,192 for the pre-delay and the all-passes at 44,118 Hz, 49,152 bytes, plus
// the state. The rings are sized for the host's rate, so times stay in
// milliseconds at any rate (at 48 kHz the lines need the next power of two).
//
// MIT licence.

#include "fm1_engine.h"

#include <stdint.h>
#include <string.h>

#include <new>

/* No fused multiply-adds in this file: the browser's WebAssembly cannot fuse,
 * so a native build that did would round differently (as in fx_comp.cc).
 * GCC ignores the pragma: build for a GCC target with FMA with
 * -ffp-contract=off. */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

namespace fm1 {
namespace hall {

enum {
  P_DECAY, P_SIZE, P_DAMPING, P_MIX,
  P_PREDELAY, P_DIFFUSION, P_MOD, P_FREEZE,
  P_WIDTH, P_LOWCUT,
  P_COUNT
};

const char *const kFreezeNames[] = { "Off", "On" };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every FLOAT is read each block: SMOOTH and MOD. Freeze crossfades
// (the input fades out as the decay lengthens), so it is lockable and takes
// modulation, rounded.
const fm1_param_t kParams[P_COUNT] = {
  { "Decay",     FM1_PARAM_FLOAT, 0, 1,   0.5f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Decay" },
  { "Size",      FM1_PARAM_FLOAT, 0, 1,   0.7f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Size" },
  { "Damping",   FM1_PARAM_FLOAT, 0, 1,   0.4f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Damp" },
  { "Mix",       FM1_PARAM_FLOAT, 0, 1,   0.3f, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Pre-delay", FM1_PARAM_FLOAT, 0, 150, 20.0f, NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_MS, "PreDly" },
  { "Diffusion", FM1_PARAM_FLOAT, 0, 1,   0.7f, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Diff" },
  { "Mod",       FM1_PARAM_FLOAT, 0, 1,   0.3f, NULL, 1, 7, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mod" },
  { "Freeze",    FM1_PARAM_ENUM,  0, 1,   0.0f, kFreezeNames, 1, 8, FM1_PARAM_MOD, FM1_UNIT_NONE, "Freeze" },
  { "Width",     FM1_PARAM_FLOAT, 0, 1,   1.0f, NULL, 2, 9, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Width" },
  { "Low Cut",   FM1_PARAM_FLOAT, 0, 1,   0.2f, NULL, 2, 10, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "LoCut" },
};

const int kLines = 8;
const int kAllPasses = 4;
const float kRefRate = 44118.0f;
// Line lengths at Size 1, in samples at 44,118 Hz (29.5-65.3 ms): primes about
// 12 % apart, 15,986 in all. Other rates scale them.
const float kLineLength[kLines] = { 1301, 1459, 1627, 1831, 2039, 2293, 2557, 2879 };
// The input all-passes, samples at 44,118 Hz (2.6-9.1 ms), and their
// coefficients at Diffusion 1 (Dattorro's input diffusers: 0.75, 0.625).
const float kApLength[kAllPasses] = { 113, 167, 263, 401 };
const float kApGain[kAllPasses] = { 0.75f, 0.75f, 0.625f, 0.625f };
// How the diffused input enters the lines: a sign pattern that is no row of
// the Hadamard matrix, times kInject.
const float kInSign[kLines] = { 1, 1, -1, 1, -1, -1, 1, -1 };
// The output taps (in Render): the left side is lines 0, 2, 5 and 7 with
// signs + - + -, the right side lines 1, 3, 4 and 6, + - + -. Each side has
// short and long lines (8,100 and 7,886 samples in all); no line is in both,
// so the sides are uncorrelated, and their sum (Width 0, mono) has all eight.
// Each line's random walk draws a new target this often (Hz at Mod's rate).
const float kModHz[kLines] = { 0.73f, 1.19f, 0.91f, 1.37f, 0.83f, 1.07f, 1.29f, 0.97f };
const float kModSmoothHz = 1.0f;          // two one-poles smooth each walk
const float kModMaxMs = 1.0f;             // Mod 1: up to +/-1 ms per line
const float kMaxPreMs = 150.0f;           // Pre-delay's range
const float kSizeOctaves = 2.0f;          // Size 0: lengths x 1/4; 1: x 1
const float kDecayMin = 0.2f;             // s, Decay 0
const float kDecayOctaves = 6.64385619f;  // log2(100): Decay 1 is 20 s
const float kFreezeT60 = 3600.0f;         // s, Freeze: an hour to -60 dB
const float kDampOctaves = 5.0f;          // Damping 1: highs decay 32 x faster
const float kDampHz = 10000.0f;           // crossover at Damping 0...
const float kDampSpan = 3.32192809f;      // ...log2(10): 1 kHz at Damping 1
const float kMaxOfRate = 0.45f;           // no one-pole corner above 0.45 fs
const float kLowCutHz = 10.0f;            // Low Cut 0...
const float kLowCutSpan = 6.64385619f;    // ...log2(100): 1 kHz at 1
const float kMaxLoopGain = 1.0f - 1.0f / 65536.0f;
const float k3Log2Of10 = 9.96578428f;     // -60 dB is 2^-9.966
const float kTwoPiLog2e = 9.06472028f;    // 2 pi log2(e)
const float kLog2e = 1.44269504f;
const float kHadamardScale = 0.353553391f;  // 1 / sqrt(8)
const float kInScale = 0.5f;              // into the pre-delay
const float kInject = 0.5f;               // into each line
const float kOutGain = 1.0f;              // the taps' sum to the wet output
const float kWordScale = 16384.0f;        // a word of 16,384 is 1.0
const float kRoundAbove = 4.0f;           // words: rounding above, truncation below
const float kInputLimit = 16.0f;          // the input guard, as mi_fx.cc
const float kFlush = 1e-15f;              // float states below this are 0
const float kFlushWords = 1e-10f;         // the same, for states in words
const uint32_t kTick = 16;                // samples per control update
const float kInvTick = 1.0f / 16.0f;
// Glide time constants, seconds.
const float kGainTau = 0.005f;            // Mix, Width
const float kTimeTau = 0.1f;              // Size, Pre-delay
const float kControlTau = 0.05f;          // Decay, Damping, Diffusion, Mod, Low Cut
const float kFreezeTau = 0.025f;          // Freeze's crossfade
const uint32_t kSeed = 0x2545F491u;

// 2^x without libm. Below -126 it is 0, above 126 it saturates at 2^126; NaN
// gives 0. x = n + f, n = floor(x + 1/2), f in [-1/2, 1/2): 2^f by its Taylor
// polynomial in f ln 2 to degree 7 (truncation under 2e-9 relative), then
// the exponent n set directly. Each operation is its own rounding.
inline float HallExp2(float x) {
  if (!(x > -126.0f)) return 0.0f;                  // NaN fails too
  if (x > 126.0f) x = 126.0f;
  const int32_t n = static_cast<int32_t>(x + 126.5f) - 126;   // x + 126.5 > 0
  const float f = x - static_cast<float>(n);
  float p = 1.52527338e-05f;
  p = p * f + 1.54035304e-04f;
  p = p * f + 1.33335581e-03f;
  p = p * f + 9.61812911e-03f;
  p = p * f + 5.55041087e-02f;
  p = p * f + 2.40226507e-01f;
  p = p * f + 6.93147181e-01f;
  p = p * f + 1.0f;
  const uint32_t bits = static_cast<uint32_t>(n + 127) << 23;
  float scale;
  memcpy(&scale, &bits, sizeof scale);
  return p * scale;
}

// One-pole coefficient for a corner at hz: 1 - e^(-2 pi hz / rate).
inline float OnePole(float hz, float rate) {
  return 1.0f - HallExp2(-kTwoPiLog2e * hz / rate);
}

// One-pole coefficient for a time constant of tau seconds, stepped every
// `every` samples.
inline float TauCoefficient(float tau, float rate, float every) {
  return 1.0f - HallExp2(-kLog2e * every / (tau * rate));
}

inline float Guard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;  // NaN fails both
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                        // NaN
}

inline float Flush(float y) { return (y > -kFlush && y < kFlush) ? 0.0f : y; }

// The rings hold 16-bit words, 16,384 to 1.0, so +/-2.0 fits: 6 dB over full
// scale. The signal path from the pre-delay to the taps works in words
// (floats counting words), so neither a read nor a store needs scaling.
// Every value on that path is finite by construction (guarded input, words
// within +/-32,767, finite coefficients), so a store needs no NaN test.

// A word: saturated at the 16-bit limits, as FxEngine's stores are (a hard
// clip, reached only 6 dB over full scale), and truncated towards zero.
inline int16_t Word(float s) {
  s = s > 32767.0f ? 32767.0f : s;
  s = s < -32767.0f ? -32767.0f : s;
  return static_cast<int16_t>(s);
}

// The lines' store. Words of kRoundAbove or more round to nearest, so the
// decay does not lose half a word on every pass, which would shorten long
// decays (truncation alone made Decay's 8 s measure 6.9). Smaller words
// truncate towards zero, moved first by `bias` words away from zero: 0
// leaves plain magnitude truncation, so nothing small recirculates for ever
// and the tail ends in exact zeros; Freeze takes it to 0.5, rounding
// everywhere, so a held sound does not fade.
inline int16_t LineWord(float s, float bias) {
  const float a = s < 0.0f ? -s : s;
  const float b = a >= kRoundAbove ? 0.5f : bias;
  return Word(s < 0.0f ? s - b : s + b);
}

// Where a line's read may aim: two samples or more, and short of the end of
// its stretch of the ring by more than the ramp's rounding (16 additions of
// the step add well under 0.01 sample), so the ramp between two such targets
// needs no clamp per sample.
inline float ClampDelay(float t, float max) {
  if (t < 2.0f) return 2.0f;
  if (t > max - 0.01f) return max - 0.01f;
  return t;
}

// A parameter glide: a one-pole that lands exactly on its target.
struct Glide {
  float value, target;
  void Snap() { value = target; }
  void Step(float k, float epsilon) {
    const float d = target - value;
    if (d > -epsilon && d < epsilon) value = target;
    else value += k * d;
  }
};

inline uint32_t NextPow2(uint32_t n) {
  uint32_t p = 1;
  while (p < n) p <<= 1;
  return p;
}

// Where everything sits in the two rings, for a host rate. instance_size and
// create both use it, so they agree.
struct Layout {
  uint32_t fdn_cells, pre_cells;            // ring sizes, powers of two
  uint32_t line_base[kLines];
  float line_length[kLines];                // at Size 1, samples
  float line_max[kLines];                   // the longest read, samples
  uint32_t ap_base[kAllPasses], ap_length[kAllPasses];
  float pre_max;                            // the longest pre-delay, samples
  float mod_max;                            // Mod 1's depth, samples
};

bool RateOk(float rate) { return rate >= 8000.0f && rate <= 192000.0f; }   // NaN fails

void MakeLayout(float rate, Layout *l) {
  const float ratio = rate / kRefRate;
  l->mod_max = kModMaxMs * 0.001f * rate;
  uint32_t at = 0;
  for (int i = 0; i < kLines; ++i) {
    l->line_length[i] = kLineLength[i] * ratio;
    // Reads reach length + mod_max and the cell after it.
    const uint32_t cells = static_cast<uint32_t>(l->line_length[i] + l->mod_max) + 4;
    l->line_base[i] = at;
    l->line_max[i] = static_cast<float>(cells - 2);
    at += cells;
  }
  l->fdn_cells = NextPow2(at);
  const uint32_t pre = static_cast<uint32_t>(kMaxPreMs * 0.001f * rate) + 3;
  l->pre_max = static_cast<float>(pre - 2);
  at = pre;                                  // the pre-delay sits at 0
  for (int k = 0; k < kAllPasses; ++k) {
    uint32_t n = static_cast<uint32_t>(kApLength[k] * ratio + 0.5f);
    if (n < 1) n = 1;
    l->ap_base[k] = at;
    l->ap_length[k] = n;
    at += n + 1;                             // written at base, read at base + n
  }
  l->pre_cells = NextPow2(at);
}

// No pointers and no size_t, so the layout is the same on 32 and 64 bits.
struct Instance {
  Layout layout;
  float rate;
  float value[P_COUNT];
  int32_t running;                           // set by the first render
  uint32_t tick;                             // samples since the last update, mod 16
  uint32_t fdn_ptr, pre_ptr;                 // both rings' write heads
  float k_gain, k_time, k_control, k_freeze, k_mod;
  Glide mix, width;                          // per sample
  Glide size, pre, decay, damping, diffusion, depth, freeze, lowcut;   // per update
  // Derived at an update.
  float c_size, c_decay, c_damping, c_freeze, c_lowcut;   // what they came from
  float scale;                               // Size's length factor
  float gain_lo[kLines], gain_hi[kLines];    // the shelf: DC and Nyquist gains
  float shelf_k;                             // its crossover, one-pole
  float hp_k;                                // Low Cut, one-pole
  float ap_gain[kAllPasses];
  float in_gain;                             // into the pre-delay, in words
  // Delays, in samples, ramping between updates.
  float delay[kLines], delay_step[kLines], delay_target[kLines];
  float pre_delay, pre_step, pre_target;
  float round_bias;                          // 0: the stores truncate; 0.5: they round
  // The random walks.
  uint32_t seed;
  uint32_t mod_count[kLines], mod_period[kLines];
  float mod_target[kLines], mod1[kLines], mod2[kLines];
  // Filter states.
  float shelf[kLines];
  float hp;

  int16_t *Cells() {
    return reinterpret_cast<int16_t *>(reinterpret_cast<unsigned char *>(this) + HeaderBytes());
  }
  static size_t HeaderBytes() { return (sizeof(Instance) + 15u) & ~static_cast<size_t>(15u); }

  void Init(float sample_rate) {
    rate = sample_rate;
    MakeLayout(rate, &layout);
    k_gain = TauCoefficient(kGainTau, rate, 1.0f);
    k_time = TauCoefficient(kTimeTau, rate, kTick);
    k_control = TauCoefficient(kControlTau, rate, kTick);
    k_freeze = TauCoefficient(kFreezeTau, rate, kTick);
    k_mod = OnePole(kModSmoothHz * kTick, rate);
    seed = kSeed;
    for (int i = 0; i < kLines; ++i) {
      uint32_t period = static_cast<uint32_t>(rate / (kModHz[i] * kTick));
      mod_period[i] = period < 1 ? 1 : period;
      mod_count[i] = 0;                      // draw a target at the first update
    }
    for (int i = 0; i < P_COUNT; ++i) {
      value[i] = kParams[i].def;
      Apply(i);
    }
  }

  // A parameter's new target; before the first render, everything snaps.
  void Apply(int index) {
    const float v = value[index];
    switch (index) {
      case P_DECAY: decay.target = v; break;
      case P_SIZE: size.target = v; break;
      case P_DAMPING: damping.target = v; break;
      case P_MIX: mix.target = v; break;
      case P_PREDELAY: pre.target = v * 0.001f * rate; break;
      case P_DIFFUSION: diffusion.target = v; break;
      case P_MOD: depth.target = v * layout.mod_max; break;
      case P_FREEZE: freeze.target = v >= 0.5f ? 1.0f : 0.0f; break;   // modulation rounds
      case P_WIDTH: width.target = v; break;
      case P_LOWCUT: lowcut.target = v; break;
      default: break;
    }
  }

  void Set(uint16_t index, float v) {
    if (index >= P_COUNT) return;
    value[index] = fm1_param_clamp(&kParams[index], v);
    Apply(index);
  }

  // The loop's gains from Size, Decay, Damping and Freeze. A gain per line,
  // in log2 per sample: Decay's for the lows, Damping's for the highs.
  void Coefficients() {
    c_size = size.value;
    c_decay = decay.value;
    c_damping = damping.value;
    c_freeze = freeze.value;
    scale = HallExp2(kSizeOctaves * (size.value - 1.0f));
    const float t60 = kDecayMin * HallExp2(kDecayOctaves * decay.value);
    const float lo = -k3Log2Of10 / (t60 * rate);
    const float hi = lo * HallExp2(kDampOctaves * damping.value);
    const float held = -k3Log2Of10 / (kFreezeT60 * rate);
    const float f = freeze.value;
    const float k_lo = lo + f * (held - lo), k_hi = hi + f * (held - hi);
    for (int i = 0; i < kLines; ++i) {
      const float length = layout.line_length[i] * scale;
      float g = HallExp2(k_lo * length), h = HallExp2(k_hi * length);
      if (g > kMaxLoopGain) g = kMaxLoopGain;
      if (h > g) h = g;
      gain_lo[i] = g;
      gain_hi[i] = h;
    }
    float hz = kDampHz * HallExp2(-kDampSpan * damping.value);
    if (hz > kMaxOfRate * rate) hz = kMaxOfRate * rate;
    shelf_k = OnePole(hz, rate);
  }

  void LowCut() {
    c_lowcut = lowcut.value;
    hp_k = OnePole(kLowCutHz * HallExp2(kLowCutSpan * lowcut.value), rate);
  }

  // The slow controls, every kTick samples; the delays then ramp towards
  // where this update puts them, one step per sample.
  void Update() {
    size.Step(k_time, 1e-6f);
    pre.Step(k_time, 1e-3f);
    decay.Step(k_control, 1e-6f);
    damping.Step(k_control, 1e-6f);
    diffusion.Step(k_control, 1e-6f);
    depth.Step(k_control, 1e-4f);
    lowcut.Step(k_control, 1e-6f);
    freeze.Step(k_freeze, 1e-5f);
    if (size.value != c_size || decay.value != c_decay || damping.value != c_damping ||
        freeze.value != c_freeze) {
      Coefficients();
    }
    if (lowcut.value != c_lowcut) LowCut();
    for (int k = 0; k < kAllPasses; ++k) ap_gain[k] = kApGain[k] * diffusion.value;
    const float f = freeze.value;
    in_gain = kInScale * kWordScale * (1.0f - f);
    round_bias = 0.5f * f;
    for (int i = 0; i < kLines; ++i) {
      if (mod_count[i] == 0) {
        seed = seed * 1664525u + 1013904223u;
        mod_target[i] = static_cast<float>(static_cast<int32_t>(seed)) * (1.0f / 2147483648.0f);
        mod_count[i] = mod_period[i];
      }
      --mod_count[i];
      mod1[i] += k_mod * (mod_target[i] - mod1[i]);
      mod2[i] += k_mod * (mod1[i] - mod2[i]);
      // Frozen, each line holds a whole number of samples, unmoved by its
      // walk, so the reads need no interpolation, which would dull the highs
      // on every pass.
      const float nominal = layout.line_length[i] * scale;
      const float moving = nominal + depth.value * mod2[i];
      const float whole = static_cast<float>(static_cast<uint32_t>(nominal + 0.5f));
      delay[i] = delay_target[i];            // exactly where the last update aimed
      delay_target[i] = ClampDelay((1.0f - f) * moving + f * whole, layout.line_max[i]);
      delay_step[i] = (delay_target[i] - delay[i]) * kInvTick;
      // The float states flush here rather than every sample. With no
      // one-pole corner above 0.45 of the rate, a state falls by at most
      // e^(-2 pi 0.45 x 16), about 2e-20, in 16 samples, so from either
      // threshold it is still a normal float at the next flush.
      if (shelf[i] > -kFlushWords && shelf[i] < kFlushWords) shelf[i] = 0.0f;
    }
    hp = Flush(hp);
    pre_delay = pre_target;
    pre_target = pre.value;
    pre_step = (pre_target - pre_delay) * kInvTick;
  }

  // Settings made before the first block apply from its first sample.
  void Start() {
    mix.Snap(); width.Snap(); size.Snap(); pre.Snap(); decay.Snap(); damping.Snap();
    diffusion.Snap(); depth.Snap(); freeze.Snap(); lowcut.Snap();
    Coefficients();
    LowCut();
    const float f = freeze.value;
    for (int i = 0; i < kLines; ++i) {
      const float nominal = layout.line_length[i] * scale;
      const float whole = static_cast<float>(static_cast<uint32_t>(nominal + 0.5f));
      delay[i] = delay_target[i] = ClampDelay((1.0f - f) * nominal + f * whole, layout.line_max[i]);
      delay_step[i] = 0.0f;
    }
    pre_delay = pre_target = pre.value;
    pre_step = 0.0f;
    round_bias = 0.5f * f;
    running = 1;
  }

  void Render(float *lr, uint32_t frames) {
    if (!running) Start();
    int16_t *const fdn = Cells();
    int16_t *const pre_ring = fdn + layout.fdn_cells;
    const uint32_t fdn_mask = layout.fdn_cells - 1, pre_mask = layout.pre_cells - 1;
    for (uint32_t n = 0; n < frames; ++n, lr += 2) {
      if (tick == 0) Update();
      tick = (tick + 1) & (kTick - 1);
      mix.Step(k_gain, 1e-6f);
      width.Step(k_gain, 1e-6f);
      const float in_l = Guard(lr[0]), in_r = Guard(lr[1]);

      // The input: mono, Low Cut, into the pre-delay (written before it is
      // read, so a pre-delay of 0 is the sample itself).
      const float mono = 0.5f * (in_l + in_r);
      hp += hp_k * (mono - hp);
      pre_ring[pre_ptr & pre_mask] = Word((mono - hp) * in_gain);
      float d = pre_delay + pre_step;
      if (!(d >= 0.0f)) d = 0.0f;
      if (d > layout.pre_max) d = layout.pre_max;
      pre_delay = d;
      const uint32_t di = static_cast<uint32_t>(d);
      const float frac = d - static_cast<float>(di);
      const float a = pre_ring[(pre_ptr + di) & pre_mask];
      const float b = pre_ring[(pre_ptr + di + 1) & pre_mask];
      float x = (1.0f - frac) * a + frac * b;

      // Diffusion: four all-passes, v = x + g v[n - N], y = v[n - N] - g v.
      for (int k = 0; k < kAllPasses; ++k) {
        const uint32_t base = pre_ptr + layout.ap_base[k];
        const float delayed = pre_ring[(base + layout.ap_length[k]) & pre_mask];
        const float v = x + ap_gain[k] * delayed;
        pre_ring[base & pre_mask] = Word(v);
        x = delayed - ap_gain[k] * v;
      }

      // The lines: read, tap, damp, mix, add the input, store.
      float y[kLines], r[kLines];
      for (int i = 0; i < kLines; ++i) {
        const float t = delay[i] + delay_step[i];   // within the line: see Update
        delay[i] = t;
        const uint32_t ti = static_cast<uint32_t>(t);
        const float tf = t - static_cast<float>(ti);
        const uint32_t at = fdn_ptr + layout.line_base[i] + ti;
        const float s0 = fdn[at & fdn_mask], s1 = fdn[(at + 1) & fdn_mask];
        r[i] = (1.0f - tf) * s0 + tf * s1;
        shelf[i] += shelf_k * (r[i] - shelf[i]);
        y[i] = gain_hi[i] * r[i] + (gain_lo[i] - gain_hi[i]) * shelf[i];
      }
      float wet_l = (r[0] - r[2]) + (r[5] - r[7]);
      float wet_r = (r[1] - r[3]) + (r[4] - r[6]);
      // Fast Walsh-Hadamard transform, in place.
      for (int span = 1; span < kLines; span <<= 1) {
        for (int i = 0; i < kLines; i += span << 1) {
          for (int j = i; j < i + span; ++j) {
            const float p = y[j], q = y[j + span];
            y[j] = p + q;
            y[j + span] = p - q;
          }
        }
      }
      const float inject = kInject * x;
      for (int i = 0; i < kLines; ++i) {
        const float z = kHadamardScale * y[i] + kInSign[i] * inject;
        fdn[(fdn_ptr + layout.line_base[i]) & fdn_mask] = LineWord(z, round_bias);
      }
      fdn_ptr = (fdn_ptr - 1) & fdn_mask;
      pre_ptr = (pre_ptr - 1) & pre_mask;

      // Width (mid and side), then the mix: the dry stays at full level up
      // to 0.5, the reverb reaches full level there (Echo's law).
      wet_l *= kOutGain / kWordScale;
      wet_r *= kOutGain / kWordScale;
      const float mid = 0.5f * (wet_l + wet_r), side = 0.5f * (wet_l - wet_r) * width.value;
      float dry = 2.0f * (1.0f - mix.value), wet = 2.0f * mix.value;
      if (dry > 1.0f) dry = 1.0f;
      if (wet > 1.0f) wet = 1.0f;
      lr[0] = dry * in_l + wet * (mid + side);
      lr[1] = dry * in_r + wet * (mid - side);
    }
  }
};

size_t InstanceSize(const fm1_host_t *host) {
  Layout l;
  const float rate = host->sample_rate;
  if (!RateOk(rate)) return Instance::HeaderBytes();
  MakeLayout(rate, &l);
  const size_t bytes = Instance::HeaderBytes() + 2u * (static_cast<size_t>(l.fdn_cells) + l.pre_cells);
  return (bytes + 15u) & ~static_cast<size_t>(15u);
}

void *Create(void *mem, const fm1_host_t *host) {
  const float rate = host->sample_rate;
  if (!RateOk(rate)) return NULL;
  const size_t bytes = InstanceSize(host);
  memset(mem, 0, bytes);                   // the rings start silent
  Instance *self = new (mem) Instance();   // zeroes the state
  self->Init(rate);
  return self;
}
void Destroy(void *s) { static_cast<Instance *>(s)->~Instance(); }
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->Set(i, v); }
void Render(void *s, float *lr, uint32_t n) { static_cast<Instance *>(s)->Render(lr, n); }

}  // namespace hall
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_hall = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "hall", "Hall",
  "This repository (MIT): a feedback delay network after Jot and Chaigne (1991), "
  "structure after schwung-work's Voidspace and Geraint Luff's Signalsmith basics "
  "(MIT), no code taken; input all-passes after Schroeder and Dattorro; 16-bit "
  "delay words after Emilie Gillet's FxEngine (Mutable Instruments, MIT)",
  fm1::hall::kParams, fm1::hall::P_COUNT, 0,
  fm1::hall::InstanceSize, fm1::hall::Create, fm1::hall::Destroy,
  NULL, NULL, NULL,
  fm1::hall::Set, fm1::hall::Render,
  NULL,                     // no notes, so no per-note offsets
};
