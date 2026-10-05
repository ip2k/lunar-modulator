/* fx_gate.cc -- "Gate": a triggerable noise gate with a Duck mode
 * (FM1_KIND_AUDIO_FX), written for this repository. Notes in
 * engines/README.md ("Gate"); the design is §7.1-§7.2 and §7.6 of
 * notes/2026-10-02-delay-reverb-eq-gates-options.md.
 *
 * The controls follow the operator manuals of Drawmer's DS201 and DS301
 * gates (credited as the inspiration only; no circuit or code is taken, and
 * the algorithm is ours): Threshold, Attack, Hold, Decay, Range, a Duck
 * mode, key filters with Listen, and the DS301's retrigger inhibit
 * (Lockout here). Return (hysteresis) and Lookahead are additions neither
 * manual has.
 *
 * Per frame, both channels sharing one detector and one gain:
 *
 *   key (the input itself, or fm1_gate_render_key's key) -> guard
 *     -> Key HP -> Key LP (12 dB/oct each, per channel; out at their ends)
 *     -> Link (Max, Sum or Left) -> level: a peak, instant up, 4 ms down
 *     -> Schmitt trigger (opens above Threshold, closes below Threshold -
 *        Return) -> the gate's state (Lockout, Attack, Hold, Decay) -> the
 *        attenuation in dB, 0..Range -> gain (Mode: Gate or Duck)
 *   input -> guard -> look-ahead line (Lookahead) -> x gain = gated
 *   out = gated, or the filtered key (Listen)
 *
 *   State   Closed (at Range), Attack (the attenuation falls at 80 dB per
 *           Attack: a started attack always completes), Open (Hold counts
 *           down once the key has fallen; it reloads while the key stays
 *           high), Decay (it rises at 80 dB per Decay back to Range).
 *           "Decay 4 s" is 80 dB in 4 s, so from Range -40 dB the gate
 *           closes in 2 s; Attack likewise. The ramps are linear in dB,
 *           as a gain cell's exponential response makes them.
 *   Trigger a rise of the Schmitt trigger. While the gate is open (Attack,
 *           Open) a rise only keeps it open. While it decays or is closed
 *           a rise re-opens it, unless it comes within Lockout of the last
 *           opening: then it is ignored, and so is the rest of that key
 *           episode (until the key falls and rises again).
 *   Duck    inverts the attenuation: Range - attenuation, so the key pulls
 *           the level down to Range over Attack and lets it back over
 *           Decay. Mode crossfades the two gains over 5 ms.
 *   Range   -90..0 dB; at -90 the closed gate is silence (gain 0), above it
 *           10^(Range / 20).
 *   Lookahead delays the audio only, by 0-5 ms, so the gate opens before
 *           the transient that opened it arrives. A change crossfades the
 *           old delay into the new over 5 ms, as the Limiter's does.
 *   Listen  sends the filtered key (stereo for Max; mono for Sum and Left)
 *           to the output instead of the gated audio, as the DS201's Key
 *           Listen does; it crossfades over 5 ms.
 *
 * Hooks for later stages (include/fm1_gate.h and engines/README.md):
 * fm1_gate_render_key takes a key buffer (the note's fm1_fx_ext_t
 * render_key); a matrix trigger joins the Schmitt trigger's output
 * (`key_high` and `rise` in GateProcess: the note's Trig, Gate replacing
 * them, Either OR-ing into them), so Hold, Attack, Decay and Lockout apply
 * to it; fm1_gate_state reads the OPEN, ENV and KEY outputs and the
 * latency.
 *
 * Determinism: no libm. 2^x and log2 are fx_comp_math.h's polynomials (the
 * shared libm-free maths the note plans to promote), tan is a polynomial
 * written below; everything else is +, -, *, / and comparisons, and
 * floating-point contraction is off for this file under clang (below), so a
 * build that fuses multiply-adds computes the same bits as WebAssembly.
 *
 * Contracts (fm1_engine.h): no heap, every byte set in create, NaN-safe
 * parameters (fm1_param_clamp), finite output. The input and the key pass
 * the Mutable effects' guard (mi_fx.cc): NaN reads as 0 and anything beyond
 * +/-16 is clamped, so non-finite samples cannot reach the state. Silence
 * in gives exact silence out at any setting. Threshold, Return, Range, the
 * key filters' cutoffs and their in/out, Mode, Listen and Link glide (one
 * pole, 5 ms) sample by sample; Attack, Decay, Hold and Lockout are rates
 * and counts, which take a new value at once (a running count is cut to
 * the new length), so nothing steps. Any block size gives the same output,
 * and values set before the first render take effect at once. Filter
 * states and the detector flush to zero below 1e-20: no subnormals.
 *
 * Cost, per frame (stereo): with the key filters out (their defaults),
 * about 25 operations and no exponential while the gain is steady (one
 * while it ramps, two while Mode crossfades); each key filter in adds about
 * 20. Measured on the desktop in engines/README.md.
 *
 * Written in the C subset of C++11 so it would build as C99 unchanged apart
 * from the extern "C" linkage below. MIT licence, like the rest of this
 * repository.
 */

#include "fm1_engine.h"
#include "fm1_gate.h"
#include "fx_comp_math.h"

#include <stdint.h>
#include <string.h>

/* No fused multiply-adds in this file: the browser's WebAssembly cannot fuse,
 * so a native build that did would round differently (Apple clang on arm64
 * fuses by default). GCC ignores the pragma: build for a GCC target with FMA
 * with -ffp-contract=off (the x86 builds here have none to use). */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

#if defined(__GNUC__) || defined(__clang__)
#define GATE_INLINE static inline __attribute__((always_inline))
#else
#define GATE_INLINE static inline
#endif

enum {
  P_THRESHOLD, P_ATTACK, P_HOLD, P_DECAY,
  P_RANGE, P_RETURN, P_MODE,
  P_KEY_HP, P_KEY_LP, P_LISTEN,
  P_LOCKOUT, P_LOOKAHEAD, P_LINK,
  P_COUNT
};

enum { M_GATE, M_DUCK, M_COUNT };
enum { L_MAX, L_SUM, L_LEFT, L_COUNT };

static const char *const kModeNames[M_COUNT] = { "Gate", "Duck" };
static const char *const kListenNames[2] = { "Off", "Key" };
static const char *const kLinkNames[L_COUNT] = { "Max", "Sum", "Left" };

/* Uids (API v2) are fixed: never renumber one; a new parameter takes the next
 * free uid (the note's Trig and Key controls, when a host can feed them,
 * take 14 and 15). Every FLOAT is read every frame: SMOOTH and MOD; Attack,
 * Hold, Decay and Lockout are rates and counts, which change nothing
 * audibly at the moment they change. The switches crossfade (Mode, Listen,
 * Link) over 5 ms, so they can be locked and modulated (MOD; a route is
 * rounded), however fast. Lookahead crossfades its delay, as the Limiter's
 * does. Threshold, Range and Return are in dB, for which fm1_unit_t has no
 * code yet. */
static const fm1_param_t kGateParams[P_COUNT] = {
  { "Threshold", FM1_PARAM_FLOAT, -80, 0, -40, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Thresh" },
  { "Attack",    FM1_PARAM_FLOAT, 0, 1000, 0.5f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_MS, "Atk" },
  { "Hold",      FM1_PARAM_FLOAT, 2, 2000, 50, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_MS, "Hold" },
  { "Decay",     FM1_PARAM_FLOAT, 2, 4000, 150, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_MS, "Decay" },
  { "Range",     FM1_PARAM_FLOAT, -90, 0, -80, NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Range" },
  { "Return",    FM1_PARAM_FLOAT, 0, 12, 4, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Return" },
  { "Mode",      FM1_PARAM_ENUM, 0, M_COUNT - 1, M_GATE, kModeNames, 1, 7, FM1_PARAM_MOD, FM1_UNIT_NONE, "Mode" },
  { "Key HP",    FM1_PARAM_FLOAT, 20, 10000, 20, NULL, 2, 8, FM1_PARAM_CONTINUOUS, FM1_UNIT_HZ, "KeyHP" },
  { "Key LP",    FM1_PARAM_FLOAT, 200, 20000, 20000, NULL, 2, 9, FM1_PARAM_CONTINUOUS, FM1_UNIT_HZ, "KeyLP" },
  { "Listen",    FM1_PARAM_ENUM, 0, 1, 0, kListenNames, 2, 10, FM1_PARAM_MOD, FM1_UNIT_NONE, "Listen" },
  { "Lockout",   FM1_PARAM_FLOAT, 0, 5000, 0, NULL, 3, 11, FM1_PARAM_CONTINUOUS, FM1_UNIT_MS, "Lock" },
  { "Lookahead", FM1_PARAM_FLOAT, 0, 5, 0, NULL, 3, 12, FM1_PARAM_CONTINUOUS, FM1_UNIT_MS, "Look" },
  { "Link",      FM1_PARAM_ENUM, 0, L_COUNT - 1, L_MAX, kLinkNames, 3, 13, FM1_PARAM_MOD, FM1_UNIT_NONE, "Link" },
};

/* The gliding control values. Pitches are log2 of Hz; Range is the closed
 * gate's attenuation in dB (0..90, positive); the rest are weights 0..1. */
enum {
  S_THRESHOLD, S_RETURN, S_RANGE, S_MODE, S_LISTEN,
  S_HP_PITCH, S_LP_PITCH, S_HP_WET, S_LP_WET,
  S_LINK_MAX, S_LINK_SUM, S_LINK_LEFT,
  S_COUNT
};

/* The gate's state (see the header comment). */
enum { PH_CLOSED, PH_ATTACK, PH_OPEN, PH_DECAY };

static const float kMinRate = 8000.0f;
static const float kMaxRate = 384000.0f;
static const float kSmoothSeconds = 0.005f;   /* glides */
static const float kFadeSeconds = 0.005f;     /* Lookahead's crossfade */
static const float kDetectSeconds = 0.004f;   /* the level's fall */
static const float kMaxLookSeconds = 0.005f;  /* Lookahead's top */
static const uint32_t kMaxLookFrames = 510;   /* the memory cap, as the Limiter's */
static const float kRampDb = 80.0f;           /* Attack and Decay: 80 dB per their time */
static const float kOffDb = 90.0f;            /* Range at -90: gain 0 */
static const float kHpOutHz = 20.0f;          /* Key HP at its bottom: out */
static const float kLpOutHz = 20000.0f;       /* Key LP at its top: out */
static const float kMaxCutoff = 0.45f;        /* of the host rate */
static const float kInputLimit = 16.0f;       /* the guard, as mi_fx.cc */
static const float kFlush = 1e-20f;           /* states below this become 0 */
static const float kLog2PerDb = 0.166096405f; /* log2(10) / 20 */
static const float kLog2e = 1.44269504f;
static const float kPi = 3.14159265358979f;
static const float kSqrt2 = 1.41421356237310f;  /* the SVF's k: Q = 1 / sqrt(2) */

typedef struct GateSvf { float ic1, ic2; } GateSvf;   /* trapezoidal integrators */

/* The instance. The look-ahead line, float[2 n] (left, right per frame),
 * follows it at off_line bytes; no pointers, so 32- and 64-bit builds have
 * the same size. */
typedef struct GateInstance {
  float param[P_COUNT];     /* knob values, clamped */
  float target[S_COUNT];    /* control values the knobs ask for */
  float value[S_COUNT];     /* control values in use (gliding to target) */
  float sample_rate;
  float glide;              /* one-pole step of the glides */
  float fall;               /* the detector's pole */
  float pi_over_rate;       /* pi / fs: a cutoff to the SVF's angle */
  float max_pitch;          /* log2 of 0.45 fs */
  /* Derived from value[] */
  float open_lin, close_lin;    /* the Schmitt trigger's levels */
  float hp_a1, hp_a2, hp_a3;    /* Key HP's coefficients */
  float lp_a1, lp_a2, lp_a3;    /* Key LP's */
  /* Rates and counts */
  float attack_db, decay_db;    /* dB per frame */
  uint32_t hold_frames, lock_frames;
  /* The detector and the gate */
  float level;              /* the key level: a peak, instant up, 4 ms down */
  float att;                /* the attenuation, dB: 0 open .. value[S_RANGE] closed */
  float ramp_from;          /* where the running Attack or Decay ramp started, dB */
  float ramp_rate;          /* its dB per frame */
  uint32_t ramp_n;          /* frames into it */
  float gain;               /* the gain of the last frame */
  float gain_att, gain_range, gain_mode;   /* what `gain` was computed from */
  uint32_t hold, lock;      /* frames left of Hold and of Lockout */
  uint32_t phase;           /* PH_* */
  uint32_t key_high;        /* the Schmitt trigger */
  uint32_t accepted;        /* this key episode opened the gate or holds it */
  uint32_t moving;          /* some value[] is still gliding */
  uint32_t primed;          /* 0 until the first render */
  GateSvf hp[2], lp[2];     /* the key filters, per channel */
  /* The look-ahead line */
  uint32_t dmax;            /* longest delay, frames */
  uint32_t n;               /* line length, dmax + 1 frames */
  uint32_t off_line;        /* byte offset of the line */
  uint32_t bytes;           /* the whole instance */
  uint32_t d, d_target;     /* the delay in use and asked for */
  uint32_t d_old;           /* the delay fading out */
  uint32_t fade_pos;        /* 0, or frames into the crossfade */
  uint32_t fade_len;
  float fade_step;          /* 1 / fade_len */
  uint32_t write;           /* the line slot of the current frame */
} GateInstance;

/* ---------------------------------------------------------------------- */
/* Arithmetic without libm                                                 */
/* ---------------------------------------------------------------------- */

static inline float GateAbs(float x) { return x < 0.0f ? -x : x; }

static inline float GateGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

static inline float GateFlush(float v) { return GateAbs(v) < kFlush ? 0.0f : v; }

/* One step of the glide; it lands on the target exactly once within 1e-6
 * of it (relative) or once a step no longer moves it, instead of stalling
 * an ulp short. The landing is small: 1e-6 of a weight (Mode, Listen) is a
 * -114 dB step, 9e-5 dB of Range a -100 dB one. (Fold's and Comp's 1e-4
 * would be -74 and -60 dB here, which a modulation route retargeting every
 * tick would repeat as zipper noise.) */
static inline float GateGlide(float v, float t, float k) {
  const float e = t - v;
  if (GateAbs(e) <= 1e-6f * (1.0f + GateAbs(t))) return t;
  const float next = v + k * e;
  return next == v ? t : next;
}

/* The pole of a one-pole lag with this time constant: exp(-1 / (s fs)). */
static float GatePole(float seconds, float rate) {
  return CompExp2(-kLog2e / (seconds * rate));
}

/* The gain of an attenuation in dB: 1 at 0 (exactly), 0 at kOffDb and
 * beyond (Range -90: off), 10^(-a / 20) between. */
static inline float GateGain(float a) {
  if (!(a > 0.0f)) return 1.0f;
  if (a >= kOffDb) return 0.0f;
  return CompExp2(-kLog2PerDb * a);
}

/* tan(x) for 0 <= x <= 0.45 pi (1.414): sin / cos by their Taylor series to
 * x^11 and x^12 (truncation 1.5e-8 and 1.5e-9 at the top; cos is no less
 * than 0.156 there), one divide. Accuracy against libm in
 * tests/test_engines_gate.py. */
static float GateTan(float x) {
  const float x2 = x * x;
  const float s = x * (1.0f + x2 * (-1.66666667e-01f + x2 * (8.33333333e-03f +
                  x2 * (-1.98412698e-04f + x2 * (2.75573192e-06f + x2 * -2.50521084e-08f)))));
  const float c = 1.0f + x2 * (-0.5f + x2 * (4.16666667e-02f + x2 * (-1.38888889e-03f +
                  x2 * (2.48015873e-05f + x2 * (-2.75573192e-07f + x2 * 2.08767570e-09f)))));
  return s / c;
}

#ifdef FM1_GATE_PROBE
/* Test builds only (fm1-gate-test, engines/mk/gate.mk): GateTan, to check it
 * against libm. */
extern "C" float fm1_gate_probe_tan(float x);
float fm1_gate_probe_tan(float x) { return GateTan(x); }
#endif

/* A Butterworth (Q = 1/sqrt(2)) state-variable filter's coefficients at a
 * pitch (log2 Hz): Zavalishin's trapezoidal SVF, its frequency prewarped
 * (g = tan(pi f / fs)), so -3 dB falls on the cutoff exactly. */
static void GateCoefs(const GateInstance *self, float pitch, float *a1, float *a2, float *a3) {
  const float g = GateTan(CompExp2(pitch) * self->pi_over_rate);
  *a1 = 1.0f / (1.0f + g * (g + kSqrt2));
  *a2 = g * *a1;
  *a3 = g * *a2;
}

/* One sample of the SVF: the high-pass output if `high`, else the low-pass. */
GATE_INLINE float GateSvfStep(GateSvf *s, float x, float a1, float a2, float a3, int high) {
  const float v3 = x - s->ic2;
  const float v1 = a1 * s->ic1 + a2 * v3;
  const float v2 = s->ic2 + a2 * s->ic1 + a3 * v3;
  s->ic1 = GateFlush(2.0f * v1 - s->ic1);
  s->ic2 = GateFlush(2.0f * v2 - s->ic2);
  return high ? x - kSqrt2 * v1 - v2 : v2;
}

/* ---------------------------------------------------------------------- */
/* Controls                                                                */
/* ---------------------------------------------------------------------- */

static inline int GateIndex(float v) { return (int)(v + 0.5f); }   /* v >= 0, clamped */

/* Frames in `ms` milliseconds, rounded. */
static inline uint32_t GateFrames(const GateInstance *self, float ms) {
  return (uint32_t)(ms * 0.001f * self->sample_rate + 0.5f);
}

/* dB per frame of a ramp that covers 80 dB in `ms` (one frame at least). */
static inline float GateRate(const GateInstance *self, float ms) {
  float frames = ms * 0.001f * self->sample_rate;
  if (!(frames > 1.0f)) frames = 1.0f;
  return kRampDb / frames;
}

static float GatePitch(const GateInstance *self, float hz) {
  const float p = CompLog2(hz);   /* hz >= 20: a normal float */
  return p < self->max_pitch ? p : self->max_pitch;
}

static void GateSetTarget(GateInstance *self, int index) {
  const float v = self->param[index];
  switch (index) {
    case P_THRESHOLD: self->target[S_THRESHOLD] = v; break;
    case P_RETURN: self->target[S_RETURN] = v; break;
    case P_RANGE: self->target[S_RANGE] = -v; break;
    case P_MODE: self->target[S_MODE] = GateIndex(v) == M_DUCK ? 1.0f : 0.0f; break;
    case P_LISTEN: self->target[S_LISTEN] = GateIndex(v) ? 1.0f : 0.0f; break;
    case P_KEY_HP:
      self->target[S_HP_PITCH] = GatePitch(self, v);
      self->target[S_HP_WET] = v > kHpOutHz ? 1.0f : 0.0f;
      break;
    case P_KEY_LP:
      self->target[S_LP_PITCH] = GatePitch(self, v);
      self->target[S_LP_WET] = v < kLpOutHz ? 1.0f : 0.0f;
      break;
    case P_LINK: {
      const int link = GateIndex(v);
      self->target[S_LINK_MAX] = link == L_MAX ? 1.0f : 0.0f;
      self->target[S_LINK_SUM] = link == L_SUM ? 1.0f : 0.0f;
      self->target[S_LINK_LEFT] = link == L_LEFT ? 1.0f : 0.0f;
      break;
    }
    case P_ATTACK: self->attack_db = GateRate(self, v); break;
    case P_DECAY: self->decay_db = GateRate(self, v); break;
    case P_HOLD: {
      uint32_t h = GateFrames(self, v);
      if (h < 1u) h = 1u;
      self->hold_frames = h;
      if (self->hold > h) self->hold = h;   /* a running hold is cut to the new length */
      break;
    }
    case P_LOCKOUT:
      self->lock_frames = GateFrames(self, v);
      if (self->lock > self->lock_frames) self->lock = self->lock_frames;
      break;
    case P_LOOKAHEAD: {
      uint32_t d = GateFrames(self, v);
      if (d > self->dmax) d = self->dmax;
      self->d_target = d;
      break;
    }
    default: break;
  }
  self->moving = 1;
}

/* The values derived from value[]: all of them, or those `changed` (a bit
 * per S_* index) touches. */
static void GateDerive(GateInstance *self, uint32_t changed) {
  if (changed & ((1u << S_THRESHOLD) | (1u << S_RETURN))) {
    const float t = self->value[S_THRESHOLD];
    self->open_lin = CompExp2(kLog2PerDb * t);
    self->close_lin = CompExp2(kLog2PerDb * (t - self->value[S_RETURN]));
  }
  if (changed & (1u << S_HP_PITCH)) {
    GateCoefs(self, self->value[S_HP_PITCH], &self->hp_a1, &self->hp_a2, &self->hp_a3);
  }
  if (changed & (1u << S_LP_PITCH)) {
    GateCoefs(self, self->value[S_LP_PITCH], &self->lp_a1, &self->lp_a2, &self->lp_a3);
  }
  /* A filter fully out restarts from rest when it comes back in. */
  if ((changed & (1u << S_HP_WET)) && self->value[S_HP_WET] == 0.0f) {
    memset(self->hp, 0, sizeof(self->hp));
  }
  if ((changed & (1u << S_LP_WET)) && self->value[S_LP_WET] == 0.0f) {
    memset(self->lp, 0, sizeof(self->lp));
  }
}

/* Settings made before the first block apply from its first sample. */
static void GateSnap(GateInstance *self) {
  for (int k = 0; k < S_COUNT; ++k) self->value[k] = self->target[k];
  GateDerive(self, ~0u);
  self->moving = 0;
  self->d = self->d_target;
  self->fade_pos = 0;
  if (self->phase == PH_CLOSED) self->att = self->value[S_RANGE];
}

/* ---------------------------------------------------------------------- */
/* The look-ahead line's layout                                            */
/* ---------------------------------------------------------------------- */

static inline uint32_t GateRound16(uint32_t b) { return (b + 15u) & ~15u; }

/* Longest delay at a host rate (a refused rate gets the smallest layout). */
static uint32_t GateMaxDelay(float rate) {
  if (!(rate >= kMinRate && rate <= kMaxRate)) rate = kMinRate;
  const float frames = rate * kMaxLookSeconds;
  uint32_t d = (uint32_t)frames;
  if ((float)d < frames) ++d;
  return d > kMaxLookFrames ? kMaxLookFrames : d;
}

static uint32_t GateBytes(uint32_t dmax) {
  const uint32_t off = GateRound16((uint32_t)sizeof(GateInstance));
  return GateRound16(off + 8u * (dmax + 1u));
}

/* ---------------------------------------------------------------------- */
/* Rendering                                                               */
/* ---------------------------------------------------------------------- */

/* Steps every gliding value one frame; returns the bits of those that moved
 * (0 once every value has landed). */
static uint32_t GateGlideAll(GateInstance *self) {
  uint32_t changed = 0;
  for (int k = 0; k < S_COUNT; ++k) {
    if (self->value[k] != self->target[k]) {
      self->value[k] = GateGlide(self->value[k], self->target[k], self->glide);
      changed |= 1u << k;
    }
  }
  return changed;
}

/* A Lookahead change starts: the read crossfades from the old delay to the
 * new over fade_len frames. One asked for during a crossfade waits for its
 * end. */
static void GateStartFade(GateInstance *self) {
  self->d_old = self->d;
  self->d = self->d_target;
  self->fade_pos = 1;
}

static void GateProcess(GateInstance *self, float *lr, const float *key, uint32_t frames) {
  if (!self->primed) {
    GateSnap(self);
    self->primed = 1;
  }
  float *line = (float *)((unsigned char *)self + self->off_line);
  const uint32_t n = self->n;
  /* The detector, the gate and the filters live in locals for the block:
   * lr may alias any float, so working through self would reload them after
   * every store. */
  float level = self->level, att = self->att, gain = self->gain;
  float ramp_from = self->ramp_from, ramp_rate = self->ramp_rate;
  uint32_t ramp_n = self->ramp_n;
  float gain_att = self->gain_att, gain_range = self->gain_range, gain_mode = self->gain_mode;
  uint32_t hold = self->hold, lock = self->lock, phase = self->phase;
  uint32_t key_high = self->key_high, accepted = self->accepted;
  const float fall = self->fall;
  for (uint32_t f = 0; f < frames; ++f) {
    if (self->moving) {
      const uint32_t changed = GateGlideAll(self);
      if (changed) {
        GateDerive(self, changed);
      } else {
        self->moving = 0;
      }
    }
    if (self->fade_pos == 0 && self->d_target != self->d) GateStartFade(self);

    /* The input, and the key: the input itself unless a key was given. */
    const float xl = GateGuard(lr[2 * f]), xr = GateGuard(lr[2 * f + 1]);
    float kl = xl, kr = xr;
    if (key) {
      kl = GateGuard(key[2 * f]);
      kr = GateGuard(key[2 * f + 1]);
    }

    /* Key HP, then Key LP, each crossfaded in and out at its end. */
    const float hp_wet = self->value[S_HP_WET];
    if (hp_wet != 0.0f) {
      const float a1 = self->hp_a1, a2 = self->hp_a2, a3 = self->hp_a3;
      const float hl = GateSvfStep(&self->hp[0], kl, a1, a2, a3, 1);
      const float hr = GateSvfStep(&self->hp[1], kr, a1, a2, a3, 1);
      if (hp_wet == 1.0f) {
        kl = hl;
        kr = hr;
      } else {
        kl = (1.0f - hp_wet) * kl + hp_wet * hl;
        kr = (1.0f - hp_wet) * kr + hp_wet * hr;
      }
    }
    const float lp_wet = self->value[S_LP_WET];
    if (lp_wet != 0.0f) {
      const float a1 = self->lp_a1, a2 = self->lp_a2, a3 = self->lp_a3;
      const float ll = GateSvfStep(&self->lp[0], kl, a1, a2, a3, 0);
      const float lr_ = GateSvfStep(&self->lp[1], kr, a1, a2, a3, 0);
      if (lp_wet == 1.0f) {
        kl = ll;
        kr = lr_;
      } else {
        kl = (1.0f - lp_wet) * kl + lp_wet * ll;
        kr = (1.0f - lp_wet) * kr + lp_wet * lr_;
      }
    }

    /* Link: the detector's level and, for Listen, the key heard. */
    const float w_max = self->value[S_LINK_MAX], w_sum = self->value[S_LINK_SUM];
    const float w_left = self->value[S_LINK_LEFT];
    const float al = GateAbs(kl), ar = GateAbs(kr);
    const float peak = al > ar ? al : ar;
    float detect;
    if (w_max == 1.0f) {
      detect = peak;
    } else {
      const float sum = 0.5f * (kl + kr);
      detect = w_max * peak + w_sum * GateAbs(sum) + w_left * al;
    }

    /* The level: a peak, instant up, falling with a 4 ms time constant. */
    const float held = level * fall;
    level = detect > held ? detect : held;
    if (level < kFlush) level = 0.0f;

    /* The Schmitt trigger. (A later stage's trigger input joins here: with
     * Trig at Gate it replaces `key_high` and `rise`, at Either it ORs into
     * them.) */
    uint32_t rise = 0;
    if (!key_high) {
      if (level > self->open_lin) {
        key_high = 1;
        rise = 1;
      }
    } else if (level < self->close_lin) {
      key_high = 0;
      accepted = 0;
    }

    /* The gate. Lockout counts from the last opening. */
    if (lock) --lock;
    if (rise) {
      if (phase == PH_ATTACK || phase == PH_OPEN) {
        accepted = 1;                     /* keeps the open gate open */
      } else if (lock == 0) {
        accepted = 1;                     /* re-opens it */
        phase = PH_ATTACK;
        lock = self->lock_frames;
        ramp_from = att;
        ramp_rate = self->attack_db;
        ramp_n = 0;
      }
    }
    if (key_high && accepted) {
      hold = self->hold_frames;           /* reloads while the key is high */
    } else if (hold) {
      --hold;
    }
    /* The ramps are computed from where they started, ramp_from -/+
     * frames x rate, rather than by adding a step each frame, which would
     * gather rounding over a long Decay; a new Attack or Decay rate starts
     * the ramp again from where it is. */
    const float range = self->value[S_RANGE];
    switch (phase) {
      case PH_ATTACK:                     /* always completes */
        if (self->attack_db != ramp_rate) {
          ramp_from = att;
          ramp_rate = self->attack_db;
          ramp_n = 0;
        }
        ++ramp_n;
        att = ramp_from - (float)ramp_n * ramp_rate;
        if (att <= 0.0f) {
          att = 0.0f;
          phase = PH_OPEN;
        }
        break;
      case PH_OPEN:
        if (!hold) {
          phase = PH_DECAY;               /* from the next frame */
          ramp_from = att;
          ramp_rate = self->decay_db;
          ramp_n = 0;
        }
        break;
      case PH_DECAY:
        if (self->decay_db != ramp_rate) {
          ramp_from = att;
          ramp_rate = self->decay_db;
          ramp_n = 0;
        }
        ++ramp_n;
        att = ramp_from + (float)ramp_n * ramp_rate;
        if (att >= range) {
          att = range;
          phase = PH_CLOSED;
        }
        break;
      default:                            /* closed: at Range, as it glides */
        att = range;
        break;
    }
    if (att > range) att = range;         /* Range glided under it */

    /* The gain, recomputed only when what it depends on moved. */
    const float mode = self->value[S_MODE];
    if (att != gain_att || range != gain_range || mode != gain_mode) {
      gain_att = att;
      gain_range = range;
      gain_mode = mode;
      if (mode == 0.0f) {
        gain = GateGain(att);
      } else if (mode == 1.0f) {
        gain = GateGain(range - att);
      } else {
        gain = (1.0f - mode) * GateGain(att) + mode * GateGain(range - att);
      }
    }

    /* The look-ahead line: in now, out d frames later (crossfading from the
     * old delay while one fades). */
    const uint32_t w = self->write;
    line[2 * w] = xl;
    line[2 * w + 1] = xr;
    const uint32_t r = w >= self->d ? w - self->d : w + n - self->d;
    float yl = line[2 * r], yr = line[2 * r + 1];
    if (self->fade_pos) {
      const uint32_t ro = w >= self->d_old ? w - self->d_old : w + n - self->d_old;
      const float t = (float)self->fade_pos * self->fade_step, u = 1.0f - t;
      yl = u * line[2 * ro] + t * yl;
      yr = u * line[2 * ro + 1] + t * yr;
      if (++self->fade_pos >= self->fade_len) self->fade_pos = 0;
    }
    self->write = w + 1u == n ? 0u : w + 1u;

    float ol = gain * yl, orr = gain * yr;
    const float listen = self->value[S_LISTEN];
    if (listen != 0.0f) {
      /* The key as the detector hears it: stereo for Max, mono for Sum
       * and Left, blended as Link glides. */
      const float sum = 0.5f * (kl + kr);
      const float hl = w_max * kl + w_sum * sum + w_left * kl;
      const float hr = w_max * kr + w_sum * sum + w_left * kl;
      ol = (1.0f - listen) * ol + listen * hl;
      orr = (1.0f - listen) * orr + listen * hr;
    }
    lr[2 * f] = ol;
    lr[2 * f + 1] = orr;
  }
  self->level = level;
  self->att = att;
  self->ramp_from = ramp_from;
  self->ramp_rate = ramp_rate;
  self->ramp_n = ramp_n;
  self->gain = gain;
  self->gain_att = gain_att;
  self->gain_range = gain_range;
  self->gain_mode = gain_mode;
  self->hold = hold;
  self->lock = lock;
  self->phase = phase;
  self->key_high = key_high;
  self->accepted = accepted;
}

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t GateInstanceSize(const fm1_host_t *host) {
  return GateBytes(GateMaxDelay(host->sample_rate));
}

static void *GateCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= kMinRate && fs <= kMaxRate)) return NULL;   /* NaN fails too */
  const uint32_t dmax = GateMaxDelay(fs);
  const uint32_t bytes = GateBytes(dmax);
  memset(mem, 0, bytes);
  GateInstance *self = (GateInstance *)mem;
  self->sample_rate = fs;
  self->glide = 1.0f - GatePole(kSmoothSeconds, fs);
  self->fall = GatePole(kDetectSeconds, fs);
  self->pi_over_rate = kPi / fs;
  self->max_pitch = CompLog2(kMaxCutoff * fs);
  self->dmax = dmax;
  self->n = dmax + 1u;
  self->off_line = GateRound16((uint32_t)sizeof(GateInstance));
  self->bytes = bytes;
  uint32_t fade = (uint32_t)(kFadeSeconds * fs + 0.5f);
  if (fade < 2u) fade = 2u;
  self->fade_len = fade;
  self->fade_step = 1.0f / (float)fade;
  for (int i = 0; i < P_COUNT; ++i) {
    self->param[i] = kGateParams[i].def;
    GateSetTarget(self, i);
  }
  self->phase = PH_CLOSED;
  GateSnap(self);
  self->att = self->value[S_RANGE];
  self->gain_att = self->att;
  self->gain_range = self->value[S_RANGE];
  self->gain_mode = self->value[S_MODE];
  self->gain = GateGain(self->att);
  self->primed = 0;
  return self;
}

static void GateDestroy(void *self) { (void)self; }

static void GateSet(void *s, uint16_t index, float v) {
  GateInstance *self = (GateInstance *)s;
  if (index >= P_COUNT) return;
  self->param[index] = fm1_param_clamp(&kGateParams[index], v);
  GateSetTarget(self, index);
}

static void GateRender(void *s, float *lr, uint32_t frames) {
  GateProcess((GateInstance *)s, lr, NULL, frames);
}

#ifdef __cplusplus
extern "C" {
#endif

void fm1_gate_render_key(void *instance, float *io_lr, const float *key_lr, uint32_t frames) {
  GateProcess((GateInstance *)instance, io_lr, key_lr, frames);
}

void fm1_gate_state(const void *instance, fm1_gate_state_t *out) {
  if (!instance || !out) return;
  const GateInstance *self = (const GateInstance *)instance;
  const float range = self->value[S_RANGE];
  const int open = self->phase == PH_ATTACK || self->phase == PH_OPEN;
  out->gain = self->gain;
  if (range > 0.0f) {
    float env = 1.0f - self->att / range;
    out->env = env < 0.0f ? 0.0f : (env > 1.0f ? 1.0f : env);
  } else {
    out->env = open ? 1.0f : 0.0f;      /* Range 0: the limit of a shallow gate */
  }
  out->key = self->level > 1.0f ? 1.0f : self->level;
  out->open = open ? 1u : 0u;
  out->key_high = self->key_high;
  out->latency = self->d;
}

extern const fm1_engine_t fm1_engine_gate;
const fm1_engine_t fm1_engine_gate = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "gate", "Gate",
  "This repository (MIT): a noise gate with controls after the Drawmer "
  "DS201 and DS301 manuals; algorithm ours, no code taken",
  kGateParams, P_COUNT, 0,
  GateInstanceSize, GateCreate, GateDestroy,
  NULL, NULL, NULL,
  GateSet, GateRender,
  NULL,                     // no notes, so no per-note offsets
};

#ifdef __cplusplus
}
#endif
