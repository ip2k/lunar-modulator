/* fx_comp.cc -- "Comp": a feed-forward compressor (FM1_KIND_AUDIO_FX),
 * written for this repository. Notes in engines/README.md ("Comp").
 *
 * Per frame, both channels sharing one detector and one gain:
 *
 *   guard -> level (the louder channel; peak or RMS) -> dB -> static curve
 *   (Threshold, Ratio, Knee) = the reduction it asks for -> smoothing in dB
 *   (Attack, Release; Character; Auto Rel) -> [Auto Gain: at least the
 *   curve's reduction at this frame's peak] -> gain = Makeup (+ Auto
 *   Gain's) - reduction -> out = dry x (1 - Mix) + dry x gain x Mix
 *
 * The design is the textbook one of Giannoulis, Massberg and Reiss, "Digital
 * Dynamic Range Compressor Design -- A Tutorial and Analysis" (JAES 60(6),
 * 2012): a feed-forward gain computer with a quadratic soft knee, its
 * output smoothed in the log domain by one-pole "branching" (attack on the
 * way up, release on the way down) or "decoupled" detectors, and automatic
 * makeup from the static curve. No code is taken from anywhere; the
 * Airwindows compressors were not used.
 *
 *   Level     Peak: max(|L|, |R|), squared. RMS: a one-pole mean of
 *             2 max(L^2, R^2) (10 or 30 ms), so a sine reads its peak level
 *             in both (sine-calibrated). In dB: 10 log10 of that power,
 *             floored at -200 dB.
 *   Curve     d = level - Threshold, S = 1 - 1/Ratio (Ratio 20 to 21 goes on
 *             to S = 1, a limiter's flat line), W = Knee:
 *               2d <= -W: 0;  2d >= W: S d;  between: S (d + W/2)^2 / (2W).
 *   Smoothing a first stage pole a1 rising / r1 falling, a second a2u / a2d,
 *             per Character (below); with Auto Rel, a slow envelope
 *             (time constant Release) follows the first stage, the first
 *             stage releases five times faster, and the larger of the two
 *             wins: short peaks recover quickly, long compression slowly.
 *   Character Peak:  peak level; one stage, Attack up, Release down.
 *             RMS:   RMS over 10 ms; as Peak.
 *             Glue:  RMS over 30 ms; decoupled (the first stage catches at
 *                    once and releases, the second smooths both ways by
 *                    Attack: a rounder, slower recovery); Knee + 6 dB.
 *             Punch: peak level; two attack stages of Attack / 2 each, so
 *                    the reduction starts with zero slope (an S-shaped
 *                    onset that lets the front of a hit through) and
 *                    reaches 63 % at 1.07 Attack; Release as set.
 *   Makeup    dB added after the reduction; Makeup then trims Auto Gain's.
 *   Auto Gain adds A = the curve's reduction at 0 dBFS, at most 24 dB (the
 *             manual Makeup's top), so a full-scale steady signal stays at
 *             full scale (under it, where the cap bites). It is clip-safe,
 *             and touches only what would clip (owner, 2026-10-05; until
 *             then it held every sample to the curve at its own peak, which
 *             rounded the peaks of steady tones too). With the lift L = w A
 *             in force (w its share, below) and xp this frame's peak in dB
 *             (both channels' louder), a sample comes out of the compressor,
 *             before Makeup, at xp + L - r for the smoothed reduction r. If
 *             that is under 0 dBFS (less a margin of 1e-4 dB, for rounding)
 *             nothing changes: a steady tone, or anything else that stays
 *             under full scale, has exactly the gain it would have with the
 *             same makeup set by hand. If it would pass, the reduction
 *             applied for that sample alone rises by just enough to bring
 *             it to the margin under 0 dBFS, but by no more than L and the
 *             margin: Auto Gain gives up as much of its lift as the sample
 *             needs, never more than all of it. So an input at or under 0 dBFS comes out
 *             at or under 0 dBFS (with Makeup at or under 0; Makeup above 0
 *             lifts that bound by itself), even while the smoothing still
 *             lags behind an onset; louder input comes out no louder than
 *             it would with Auto Gain off. The touch is per sample, so
 *             where it acts (at an onset the smoothing has not caught yet,
 *             or on the tips of a tone the RMS detectors read under its
 *             peaks) it clips those samples at the margin under full scale;
 *             r and the smoothing never see it. Mix keeps the bound: dry and
 *             compressed are each within it and have the same sign. Turning
 *             Auto Gain on or off glides w, so L and the bound move in or
 *             out together (5 ms), and the bound holds part-way: it only
 *             ever takes back the part of the lift that is in force.
 *
 * Gain reduction, for a modulation source: fm1_comp_reduction_db()
 * (include/fm1_comp.h) returns the last frame's smoothed reduction in dB.
 *
 * Determinism: no libm at all. Logarithm and exponential are the
 * polynomials of fx_comp_math.h; everything else is +, -, *, / and
 * comparisons. Floating-point contraction is off for this file under clang
 * (below), so a build that fuses multiply-adds (Apple clang on arm64 does by
 * default) computes the same bits as WebAssembly, which never fuses.
 *
 * Contracts (fm1_engine.h): no heap, every field set in create, NaN-safe
 * parameters (fm1_param_clamp), finite output. Input guard as the Mutable
 * effects' (mi_fx.cc): NaN reads as 0 and anything beyond +/-16 is clamped,
 * so non-finite input cannot reach the state. Silence in gives exact silence
 * out at any setting (the gain multiplies the input). Threshold, Ratio,
 * Knee, Makeup, Mix and Auto Gain's share glide (one pole, 5 ms) sample by
 * sample; Character crossfades the detector over the same 5 ms; a change of
 * Character or Auto Rel that would step the reduction hands over through an
 * offset that decays in 5 ms. So any block size gives the same output, and values set
 * before the first render take effect at once. States flush to zero (the
 * mean power below 1e-20, reductions below 1e-6 dB): no subnormals.
 *
 * Cost, per frame (stereo): one divide in the logarithm, one exponential,
 * the curve and three one-pole steps: about 75 operations, under 5,000 per
 * 64-frame block; Auto Gain adds the curve once more and, for RMS and Glue,
 * a second logarithm. Measured on the desktop in engines/README.md.
 *
 * Written in the C subset of C++11 so it would build as C99 unchanged apart
 * from the extern "C" linkage below. MIT licence, like the rest of this
 * repository.
 */

#include "fm1_engine.h"
#include "fm1_comp.h"
#include "fx_comp_math.h"

#include <stdint.h>
#include <string.h>

/* No fused multiply-adds in this file: the browser's WebAssembly cannot fuse,
 * so a native build that did would round differently. Without this pragma
 * Apple clang's arm64 build does fuse, and its output differs [verified,
 * 2026-10-02]. GCC ignores the pragma: build for a GCC target with FMA with
 * -ffp-contract=off (the x86 builds here have none to use). */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

#if defined(__GNUC__) || defined(__clang__)
#define COMP_INLINE static inline __attribute__((always_inline))
#else
#define COMP_INLINE static inline
#endif

enum {
  P_THRESHOLD, P_RATIO, P_ATTACK, P_RELEASE,
  P_KNEE, P_MAKEUP, P_MIX, P_CHARACTER,
  P_AUTO_RELEASE, P_AUTO_MAKEUP,
  P_COUNT
};

enum { C_PEAK, C_RMS, C_GLUE, C_PUNCH, C_COUNT };

static const char *const kCharacterNames[C_COUNT] = { "Peak", "RMS", "Glue", "Punch" };
static const char *const kOffOn[2] = { "Off", "On" };

/* Uids (API v2) are fixed: never renumber one; a new parameter takes the next
 * free uid. The FLOATs are read every sample: SMOOTH and MOD. The switches
 * change nothing destructively (Character and Auto Rel hand over, Auto Gain
 * glides; no NOLOCK) and are not note-bound (no LATCH), so they can be locked
 * and modulated (MOD; a route is rounded), however fast. Threshold, Knee and
 * Makeup are in dB (FM1_UNIT_DB, API v3). Release moves on the LOG law
 * (fm1_engine.h): a ratio a detent, octaves under modulation; Attack, whose
 * range starts at 0, stays linear. */
static const fm1_param_t kCompParams[P_COUNT] = {
  { "Threshold", FM1_PARAM_FLOAT, -60, 0, -18, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Thresh" },
  { "Ratio",     FM1_PARAM_FLOAT, 1, 21, 4, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Ratio" },
  { "Attack",    FM1_PARAM_FLOAT, 0, 100, 10, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_MS, "Atk" },
  { "Release",   FM1_PARAM_FLOAT, 10, 2000, 150, NULL, 0, 4, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_MS, "Rel" },
  { "Knee",      FM1_PARAM_FLOAT, 0, 24, 6, NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Knee" },
  { "Makeup",    FM1_PARAM_FLOAT, -12, 24, 0, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Makeup" },
  { "Mix",       FM1_PARAM_FLOAT, 0, 1, 1, NULL, 1, 7, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Character", FM1_PARAM_ENUM, 0, C_COUNT - 1, C_PEAK, kCharacterNames, 1, 8, FM1_PARAM_MOD, FM1_UNIT_NONE, "Char" },
  { "Auto Rel",  FM1_PARAM_ENUM, 0, 1, 0, kOffOn, 2, 9, FM1_PARAM_MOD, FM1_UNIT_NONE, "ARel" },
  { "Auto Gain", FM1_PARAM_ENUM, 0, 1, 0, kOffOn, 2, 10, FM1_PARAM_MOD, FM1_UNIT_NONE, "AGain" },
};

/* The gliding control values. S_AUTO is Auto Gain's share, 0..1. */
enum { S_THRESHOLD, S_SLOPE, S_KNEE, S_MAKEUP, S_MIX, S_RMS, S_AUTO, S_COUNT };

static const float kSmoothSeconds = 0.005f;   /* glides and hand-overs */
static const float kInputLimit = 16.0f;       /* the input guard, as mi_fx.cc */
static const float kPowerFloor = 1e-20f;      /* -200 dB, and the power flush */
static const float kReductionFlush = 1e-6f;   /* dB; reductions below are 0 */
static const float kDbPerLog2Power = 3.01029996f;   /* 10 log10(2) */
static const float kLog2PerDb = 0.166096405f;       /* log2(10) / 20 */
static const float kLog2e = 1.44269504f;
static const float kAutoFastDivisor = 5.0f;   /* Auto Rel: first stage */
static const float kAutoGainMax = 24.0f;      /* dB: Auto Gain's cap, Makeup's top */
static const float kBoundMargin = 1e-4f;      /* dB: Auto Gain's bound, over rounding */
static const float kRmsSeconds[C_COUNT] = { 0.010f, 0.010f, 0.030f, 0.010f };
static const float kKneeAdd[C_COUNT] = { 0.0f, 0.0f, 6.0f, 0.0f };

/* The poles of the reduction's smoothing; the hand-over between two of them
 * is what Character and Auto Rel change. */
typedef struct CompPoles {
  float a1, r1;     /* first stage, rising and falling */
  float a2u, a2d;   /* second stage, rising and falling */
  float as;         /* the slow envelope (both ways) */
  int slow;         /* Auto Rel: the slow envelope takes part */
} CompPoles;

typedef struct CompInstance {
  float param[P_COUNT];     /* knob values, clamped */
  float target[S_COUNT];    /* control values the knobs ask for */
  float value[S_COUNT];     /* control values in use (gliding to target) */
  float sample_rate;
  float glide;              /* one-pole step of the glides */
  float glide_pole;         /* 1 - glide: the hand-over offset's decay */
  float kq;                 /* S / (2 W) at value[], 0 for a hard knee */
  float auto_db;            /* Auto Gain's full makeup at value[], dB */
  float k_rms;              /* RMS mean: one-pole step */
  CompPoles poles;          /* in force */
  CompPoles applied;        /* in force at the end of the last render */
  int handover;             /* a Character / Auto Rel change is pending */
  int primed;               /* 0 until the first render */
  float power;              /* RMS: the mean of 2 max(L^2, R^2) */
  float y1, y2, ys;         /* reduction states, dB */
  float offset;             /* hand-over offset, dB, decaying */
  float reduction;          /* the last frame's reduction, dB */
} CompInstance;

/* ---------------------------------------------------------------------- */
/* The curve and the smoothing                                             */
/* ---------------------------------------------------------------------- */

static inline float CompAbs(float x) { return x < 0.0f ? -x : x; }

static inline float CompGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

/* The pole of a one-pole lag with this time constant: exp(-1 / (s fs)), 0
 * for 0 s (no lag). */
static float CompPole(float seconds, float rate) {
  if (!(seconds > 0.0f)) return 0.0f;
  return CompExp2(-kLog2e / (seconds * rate));
}

/* The curve's slope above the knee: 1 - 1/Ratio up to 20:1 (0.95), then on
 * to 1 (no rise at all, a limiter's curve) at 21. */
static float CompSlope(float ratio) {
  if (ratio <= 20.0f) return 1.0f - 1.0f / ratio;
  return 0.95f + 0.05f * (ratio - 20.0f);
}

/* The static curve: the reduction (dB, >= 0) asked for at level x (dB).
 * kq = slope / (2 knee), unused when knee is 0. Continuous at both ends of
 * the knee. */
COMP_INLINE float CompCurve(float x, float threshold, float slope, float knee, float kq) {
  const float d = x - threshold;
  const float d2 = d + d;
  if (d2 <= -knee) return 0.0f;
  if (d2 >= knee) return slope * d;
  const float e = d + 0.5f * knee;
  return kq * e * e;
}

static inline float CompFlushDb(float v) { return v < kReductionFlush ? 0.0f : v; }

/* One frame of smoothing towards the asked-for reduction c; returns the
 * reduction to apply. Each stage is y = in + pole (y - in), so a pole of 0
 * passes its input exactly. */
COMP_INLINE float CompStep(const CompPoles *k, float c, float *y1, float *y2, float *ys) {
  const float p1 = c > *y1 ? k->a1 : k->r1;
  const float v1 = c + p1 * (*y1 - c);
  const float p2 = v1 > *y2 ? k->a2u : k->a2d;
  const float v2 = v1 + p2 * (*y2 - v1);
  const float vs = v1 + k->as * (*ys - v1);
  *y1 = CompFlushDb(v1);
  *y2 = CompFlushDb(v2);
  *ys = CompFlushDb(vs);
  return (k->slow && *ys > *y2) ? *ys : *y2;
}

/* ---------------------------------------------------------------------- */
/* Controls                                                                */
/* ---------------------------------------------------------------------- */

static inline int CompIndex(float v) { return (int)(v + 0.5f); }   /* v >= 0, clamped */

/* One step of the glide; snaps when within 1e-4 (relative), so a value
 * reaches its target exactly instead of stalling an ulp short of it. */
static inline float CompGlide(float v, float t, float k) {
  const float e = t - v;
  if (CompAbs(e) <= 1e-4f * (1.0f + CompAbs(t))) return t;
  return v + k * e;
}

static float CompKq(float slope, float knee) {
  return knee > 0.0f ? slope / (knee + knee) : 0.0f;
}

static void CompMakePoles(const CompInstance *self, CompPoles *k) {
  const float fs = self->sample_rate;
  const float attack = 0.001f * self->param[P_ATTACK];
  const float release = 0.001f * self->param[P_RELEASE];
  const int slow = CompIndex(self->param[P_AUTO_RELEASE]);
  k->slow = slow;
  k->as = CompPole(release, fs);
  k->r1 = slow ? CompPole(release / kAutoFastDivisor, fs) : k->as;
  switch (CompIndex(self->param[P_CHARACTER])) {
    case C_GLUE:
      k->a1 = 0.0f;
      k->a2u = k->a2d = CompPole(attack, fs);
      break;
    case C_PUNCH:
      k->a1 = k->a2u = CompPole(0.5f * attack, fs);
      k->a2d = 0.0f;
      break;
    default:   /* Peak, RMS */
      k->a1 = CompPole(attack, fs);
      k->a2u = k->a2d = 0.0f;
      break;
  }
}

/* Auto Gain's makeup at the values in use: the curve's reduction at 0 dB,
 * capped. kq must be current. */
static void CompUpdateAuto(CompInstance *self) {
  const float a = CompCurve(0.0f, self->value[S_THRESHOLD], self->value[S_SLOPE],
                            self->value[S_KNEE], self->kq);
  self->auto_db = a < kAutoGainMax ? a : kAutoGainMax;
}

static void CompSetTarget(CompInstance *self, int index) {
  const float v = self->param[index];
  const int character = CompIndex(self->param[P_CHARACTER]);
  switch (index) {
    case P_THRESHOLD: self->target[S_THRESHOLD] = v; break;
    case P_RATIO: self->target[S_SLOPE] = CompSlope(v); break;
    case P_KNEE:
    case P_CHARACTER:
      self->target[S_KNEE] = self->param[P_KNEE] + kKneeAdd[character];
      self->target[S_RMS] = (character == C_RMS || character == C_GLUE) ? 1.0f : 0.0f;
      self->k_rms = 1.0f - CompPole(kRmsSeconds[character], self->sample_rate);
      break;
    case P_MIX: self->target[S_MIX] = v; break;
    case P_MAKEUP: self->target[S_MAKEUP] = v; break;
    case P_AUTO_MAKEUP: self->target[S_AUTO] = CompIndex(v) ? 1.0f : 0.0f; break;
    default: break;
  }
  switch (index) {
    case P_CHARACTER:
    case P_AUTO_RELEASE:
      /* The smoothing changes shape: hand over at the next frame. */
      if (self->primed) self->handover = 1;
      CompMakePoles(self, &self->poles);
      break;
    case P_ATTACK:
    case P_RELEASE:
      CompMakePoles(self, &self->poles);   /* a new rate, no step */
      break;
    default: break;
  }
}

static void CompSnap(CompInstance *self) {
  for (int k = 0; k < S_COUNT; ++k) self->value[k] = self->target[k];
  self->kq = CompKq(self->value[S_SLOPE], self->value[S_KNEE]);
  CompUpdateAuto(self);
  self->applied = self->poles;
  self->handover = 0;
}

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t CompInstanceSize(const fm1_host_t *host) {
  (void)host;
  return (sizeof(CompInstance) + 15u) & ~(size_t)15u;
}

static void *CompCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;   /* NaN fails too */
  CompInstance *self = (CompInstance *)mem;
  memset(self, 0, sizeof(*self));
  self->sample_rate = fs;
  self->glide_pole = CompPole(kSmoothSeconds, fs);
  self->glide = 1.0f - self->glide_pole;
  for (int i = 0; i < P_COUNT; ++i) self->param[i] = kCompParams[i].def;
  for (int i = 0; i < P_COUNT; ++i) CompSetTarget(self, i);
  CompSnap(self);
  self->primed = 0;
  return self;
}

static void CompDestroy(void *self) { (void)self; }

static void CompSet(void *s, uint16_t index, float v) {
  CompInstance *self = (CompInstance *)s;
  if (index >= P_COUNT) return;
  self->param[index] = fm1_param_clamp(&kCompParams[index], v);
  CompSetTarget(self, index);
}

static void CompRender(void *s, float *lr, uint32_t frames) {
  CompInstance *self = (CompInstance *)s;
  if (!self->primed) {
    /* Settings made before the first block apply from its first sample. */
    CompSnap(self);
    self->primed = 1;
  }
  /* The detector state lives in locals for the block: lr may alias any
   * float, so working through self would reload it after every store. */
  float power = self->power, y1 = self->y1, y2 = self->y2, ys = self->ys;
  float offset = self->offset, reduction = self->reduction;
  const float glide = self->glide, glide_pole = self->glide_pole, k_rms = self->k_rms;
  for (uint32_t f = 0; f < frames; ++f) {
    int gliding = 0;
    for (int k = 0; k < S_COUNT; ++k) {
      if (self->value[k] != self->target[k]) {
        self->value[k] = CompGlide(self->value[k], self->target[k], glide);
        gliding = 1;
      }
    }
    if (gliding) {
      self->kq = CompKq(self->value[S_SLOPE], self->value[S_KNEE]);
      CompUpdateAuto(self);
    }

    /* The level: the louder channel, as power (dB = 10 log10). */
    const float l = CompGuard(lr[2 * f]), r = CompGuard(lr[2 * f + 1]);
    const float al = CompAbs(l), ar = CompAbs(r);
    const float peak = al > ar ? al : ar;
    const float p2 = peak * peak;
    power = power + k_rms * (2.0f * p2 - power);
    if (power < kPowerFloor) power = 0.0f;
    const float m = self->value[S_RMS];
    float level = m == 0.0f ? p2 : (m == 1.0f ? power : p2 + m * (power - p2));
    if (!(level > kPowerFloor)) level = kPowerFloor;
    const float x = kDbPerLog2Power * CompLog2(level);

    const float c = CompCurve(x, self->value[S_THRESHOLD], self->value[S_SLOPE],
                              self->value[S_KNEE], self->kq);
    float gr;
    if (self->handover) {
      /* The old smoothing and the new, from the same states: the difference
       * becomes an offset that decays, so the reduction does not step. */
      float o1 = y1, o2 = y2, os = ys;
      const float old = CompStep(&self->applied, c, &o1, &o2, &os);
      gr = CompStep(&self->poles, c, &y1, &y2, &ys);
      offset = offset + (old - gr);
      self->handover = 0;
    } else {
      gr = CompStep(&self->poles, c, &y1, &y2, &ys);
    }
    reduction = gr + offset;
    if (reduction < 0.0f) reduction = 0.0f;
    if (offset != 0.0f) {
      offset = offset * glide_pole;
      if (CompAbs(offset) < kReductionFlush) offset = 0.0f;
    }

    /* Auto Gain, in by its share w: its lift, and the bound, which touches
     * only a sample the lift would take over 0 dBFS (before Makeup), and
     * takes back at most the lift (above). xp is this frame's peak in dB,
     * which Peak and Punch already have as x. Off (w = 0), none of it is
     * computed. */
    float makeup = self->value[S_MAKEUP], applied = reduction;
    const float w = self->value[S_AUTO];
    if (w != 0.0f) {
      const float lift = w * self->auto_db;
      makeup = makeup + lift;
      float xp = x;
      if (m != 0.0f) {
        const float pp = p2 > kPowerFloor ? p2 : kPowerFloor;
        xp = kDbPerLog2Power * CompLog2(pp);
      }
      const float over = xp + lift - reduction + kBoundMargin;
      const float most = lift + kBoundMargin;
      if (over > 0.0f) applied = reduction + (over < most ? over : most);
    }

    /* dry x (1 - Mix) + dry x gain x Mix: at Mix 1 the output is exactly
     * dry x gain, at 0 exactly dry (dry + Mix (wet - dry) would round a deep
     * reduction to the input's last place, not the output's). */
    const float mix = self->value[S_MIX];
    const float wet = mix * CompExp2(kLog2PerDb * (makeup - applied));
    const float dry = 1.0f - mix;
    lr[2 * f] = l * dry + l * wet;
    lr[2 * f + 1] = r * dry + r * wet;
  }
  self->power = power;
  self->y1 = y1;
  self->y2 = y2;
  self->ys = ys;
  self->offset = offset;
  self->reduction = reduction;
  self->applied = self->poles;
}

#ifdef __cplusplus
extern "C" {
#endif

float fm1_comp_reduction_db(const void *instance) {
  return instance ? ((const CompInstance *)instance)->reduction : 0.0f;
}

extern const fm1_engine_t fm1_engine_comp;
const fm1_engine_t fm1_engine_comp = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "comp", "Comp",
  "This repository (MIT): a feed-forward compressor after Giannoulis, "
  "Massberg and Reiss, \"Digital Dynamic Range Compressor Design\" (JAES "
  "2012); no code taken",
  kCompParams, P_COUNT, 0,
  CompInstanceSize, CompCreate, CompDestroy,
  NULL, NULL, NULL,
  CompSet, CompRender,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
};

#ifdef __cplusplus
}
#endif
