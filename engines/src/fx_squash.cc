/* fx_squash.cc -- "Squash": three small compressors after Airwindows designs
 * (FM1_KIND_AUDIO_FX). Notes in engines/README.md ("Squash").
 *
 * The three Types are ports of Chris Johnson's Airwindows plug-ins, MIT:
 *
 *   Copyright (c) 2016 airwindows, Airwindows uses the MIT license
 *   (Pop3, Pressure4, ButterComp2; the licence text is in
 *   engines/third_party/airwindows/LICENSE, the pinned commit and what was
 *   taken in its UPSTREAM.md)
 *
 * ported into single precision without libm, with these changes, each one
 * the porting rules of notes/2026-10-02-filters-dynamics-options.md §3:
 *
 *   - no denormal noise: the plug-ins add a pseudo-random dither of about
 *     1e-17 to every sample and, in ButterComp2, a "live air" residue whose
 *     state is function-static (shared by every instance). Both are gone, so
 *     silence in gives exact silence out; states flush to 0 under 1e-20;
 *   - sin, pow and sqrt in the loop are polynomials and Newton steps (below);
 *   - the knobs are in units (ms, dB) where the plug-ins' 0..1 knobs map onto
 *     times or levels, with the same arithmetic underneath (each mapping is
 *     at its knob below), and Output and Mix are ours, for every Type;
 *   - Mu leaves out Pressure4's makeup and its output sine, and writes its
 *     one-pole steps so float keeps them (below);
 *   - Split's targets have a floor (below).
 *
 * Snap, after Pop3: a compressor and a gate, per channel with the gains
 * linked. Over the threshold T = (1 - Squash)^4 the gain's state p moves by
 * Attack towards T / |x| (p -= p a; p += (T / |x|) a), under it by Release
 * towards 1; the channel with the higher p is pulled down by a once more
 * (Pop3's order; SnapFrame keeps the pair as the lower state and the gap,
 * which matters in float, as it explains), and p is held to 0..1. The gain
 * is (1 - R) + p R, R = 1 - (1 - Ratio)^2.
 * Attack and Release are Pop3's C Atk and C Rls as times: a = 1 / (Attack
 * x fs), C = 0.5 being 25.5 ms. The gate: any sample over Gate sets its
 * state to its sustain, pi/2 (Hold + 1)^4; otherwise it decays by Gate Rel;
 * under pi/2 the gain is multiplied by (1 - Q) + sin(state) Q, Q = 1 - (1 -
 * Gate Depth)^2: a quarter-sine close. Gate at -80 dB (its left end) is off
 * (Pop3's E = 0). Snap can only turn the sound down.
 *
 * Mu, after Pressure4: a variable-mu leveller with one gain for both
 * channels. Its threshold is t = 1 - 0.95 Squash; Pressure4 lifts the input
 * by 1/t before its detector and leaves it lifted; Mu detects the same way
 * (sense = max(|L|, |R|) / t against t) but divides the lift out again, so,
 * like Snap, it can only turn the sound down, and Output makes up (the
 * filters note's verdict: Pressure4's 1/t makeup raised quiet passages and
 * the noise floor by up to 26 dB, and its sin() output stage was its clip
 * guard). Above t the gain's state c moves towards max(t / sense, t) by a
 * one-pole of sqrt(speed) samples, under it towards 1 by one of speed^2;
 * speed follows sense x release + sqrt(release) (Pressure4's "speed"), so
 * it recovers slowly after loud passages: release = Release x fs, so
 * Release is the quiet release time (Pressure4's Speed B maps to (1.28 -
 * B)^5 x 32768 samples at 44.1 kHz, B = 0.2 being 1.09 s). Shape is
 * Mewiness: the gain is c^2 blended with c by Shape above 0, sqrt(c) by
 * -Shape below.
 *
 * Split, after ButterComp2: per channel, each half-wave of the input lifted
 * by 10^(14 Squash / 20) has its own one-pole target, the mean of (1 + x)^2
 * for the positive side and (1 - x)^2 for the negative, and its own gain,
 * which follows 1 / target^2 by the same pole, only while the input is on
 * its side and only on every other sample for each of two gain sets (A and
 * B, alternating, ButterComp2's flip): the gain applied blends the
 * positive and negative gains of the set in turn by where the sample sits
 * between -1 and 1. The pole is 0.012 Squash / 135 / (1 + |last output|),
 * per 44.1 kHz sample: no timing knobs, and slower while loud. The result
 * is divided by 1 + (lift - 1) / 1.5. Squash 0 passes the sound untouched
 * (within +/-1). A target is held at 0.25 or more (its gain at 16 or less):
 * ButterComp2's runs towards 0 under a negative offset beyond -1 and its
 * gain to infinity; ordinary audio never reaches the floor.
 *
 * Type changes. A new Type starts from the gain the old one was applying
 * (its state set to give that gain: Snap's p and an open gate, Mu's c from
 * Shape's curve and a speed at rest, Split's four gains and two targets),
 * and the two run together while the output crossfades from the old to the
 * new over 5 ms; a change asked for meanwhile waits for the fade's end. So
 * Type is lockable and modulated (rounded) without a step.
 *
 * Contracts (fm1_engine.h): no heap, every field set in create, NaN-safe
 * parameters and input (NaN reads as 0, beyond +/-16 is clamped, as
 * mi_fx.cc), finite output, silence in gives exact silence out (every Type
 * multiplies the input by a gain). Every FLOAT is SMOOTH (fm1_smooth.h): a
 * change ramps over 2.5 ms of samples, one step per frame, so any block size
 * gives the same output; values set before the first render apply at once.
 * Determinism: no libm (2^x and log2 from fm1_math.h, sin, sqrt below) and
 * floating-point contraction off, so every build computes the same bits.
 *
 * Cost, per stereo frame, the Type in use only (two while a Type fades): Snap
 * two divides when over the threshold; Mu three divides and one or two
 * square roots; Split six divides. Measured in engines/README.md.
 *
 * Written in the C subset of C++11. The ported arithmetic stays under the
 * Airwindows notice above; the rest is MIT like this repository.
 */

#include "fm1_engine.h"
#include "fm1_smooth.h"

#include <stdint.h>
#include <string.h>

#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

enum {
  P_TYPE, P_SQUASH, P_ATTACK, P_RELEASE, P_RATIO, P_SHAPE, P_OUTPUT, P_MIX,
  P_GATE, P_DEPTH, P_HOLD, P_GATE_REL, P_COUNT
};

enum { T_SNAP, T_MU, T_SPLIT, T_COUNT };

static const char *const kTypeNames[T_COUNT] = { "Snap", "Mu", "Split" };

/* Uids (API v2) are fixed: never renumber one; a new parameter takes the next
 * free uid. The FLOATs are read every frame (SMOOTH and MOD); Type
 * crossfades (MOD, rounded when modulated; lockable). Times are LOG; Output
 * and Gate are in dB. Defaults: Pop3's (C, D, F, G, H = 0.5), Squash
 * half-way, Shape Pressure4's (Mewiness 1). */
static const fm1_param_t kSquashParams[P_COUNT] = {
  { "Type",       FM1_PARAM_ENUM,  0, T_COUNT - 1, T_SNAP, kTypeNames, 0, 1, FM1_PARAM_MOD, FM1_UNIT_NONE, "Type" },
  { "Squash",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Squash" },
  { "Attack",     FM1_PARAM_FLOAT, 1, 200, 25.5f, NULL, 0, 3, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_MS, "Atk" },
  { "Release",    FM1_PARAM_FLOAT, 1, 3000, 46.8f, NULL, 0, 4, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_MS, "Rel" },
  { "Ratio",      FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Ratio" },
  { "Shape",      FM1_PARAM_FLOAT, -1, 1, 1.0f, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Shape" },
  { "Output",     FM1_PARAM_FLOAT, -24, 24, 0.0f, NULL, 1, 7, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Out" },
  { "Mix",        FM1_PARAM_FLOAT, 0, 1, 1.0f, NULL, 1, 8, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Gate",       FM1_PARAM_FLOAT, -80, 0, -80.0f, NULL, 2, 9, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Gate" },
  { "Gate Depth", FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 2, 10, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "GDepth" },
  { "Hold",       FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 2, 11, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Hold" },
  { "Gate Rel",   FM1_PARAM_FLOAT, 10, 12000, 365.6f, NULL, 2, 12, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_MS, "GRel" },
};

static const float kInputLimit = 16.0f;       /* the input guard, as mi_fx.cc */
static const float kFlush = 1e-20f;           /* states below are 0 */
static const float kFadeSeconds = 0.005f;     /* Type crossfade */
static const float kHalfPi = 1.57079633f;
static const float kLog2PerDb = 0.166096405f; /* log2(10) / 20 */
static const float kSplitTargetFloor = 0.25f; /* Split's targets: gains of 16 or less */
static const float kMuSpeedStart = 10000.0f;  /* Pressure4's starting speed */
static const float kSnapEqual = 1e-14f;       /* Snap: d under this x m is 0 (about where a double's rounding ends it) */

/* The control values the knobs imply (recomputed while a knob ramps). */
typedef struct SquashCtl {
  /* Snap */
  float thr, ratio, atk, rel, gthr, gratio, gsus, grel;
  /* Mu */
  float mu_thr, mu_lift, mu_release, mu_fastest, mew;
  int mu_positive;
  /* Split */
  float lift, factor, inv_outgain;
  /* all */
  float out, mix;
} SquashCtl;

/* Snap's two gain states as the lower, m, and how far the other is above
 * it, d >= 0 (hi: which channel that is), so d keeps its precision when it
 * is tiny (SnapFrame explains why that matters); and the gate. */
typedef struct SnapState { float m, d, gate; int hi; } SnapState;
typedef struct MuState { float coef, speed; } MuState;
typedef struct SplitState {
  float tpos[2], tneg[2];
  float a_pos[2], a_neg[2], b_pos[2], b_neg[2];
  float last[2];
  int flip;
} SplitState;

typedef struct SquashInstance {
  float value[P_COUNT];         /* values in use (FLOATs ramp; Type is taken at once) */
  fm1_smooth_t ramp[P_COUNT];
  uint32_t steps;
  int started;
  float rate;
  float inv_scale;              /* 44,100 / fs */
  SquashCtl ctl;
  int type, want;               /* the Type sounding, the one asked for */
  int from;                     /* fading out while fade > 0 */
  uint32_t fade, fade_len;      /* frames left in the crossfade, its length */
  float inv_fade;
  float gain[2];                /* the last gain the sounding Type applied, per channel */
  SnapState snap;
  MuState mu;
  SplitState split;
} SquashInstance;

/* ---------------------------------------------------------------------- */
/* Arithmetic without libm                                                 */
/* ---------------------------------------------------------------------- */

static inline float SqAbs(float x) { return x < 0.0f ? -x : x; }

static inline float SqGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

static inline float SqClamp01(float x) { return x < 0.0f ? 0.0f : (x > 1.0f ? 1.0f : x); }

/* sqrt(x) for x >= 0: the reciprocal square root from the float's bits and
 * three Newton steps (multiplies only), then one Newton step on the root
 * itself. Within an ulp or two of the true root; 0 for x <= 0 or NaN. */
static float SqSqrt(float x) {
  if (!(x > 0.0f)) return 0.0f;
  if (x > 3.0e38f) x = 3.0e38f;
  uint32_t i;
  memcpy(&i, &x, sizeof i);
  i = 0x5f3759dfu - (i >> 1);
  float r;
  memcpy(&r, &i, sizeof r);
  const float h = 0.5f * x;
  r = r * (1.5f - h * r * r);
  r = r * (1.5f - h * r * r);
  r = r * (1.5f - h * r * r);
  const float y = x * r;
  return 0.5f * (y + x / y);
}

/* sin(x) for 0 <= x <= pi/2, Taylor to x^11: within 6e-8 there. */
static inline float SqSinQ(float x) {
  const float x2 = x * x;
  return x * (1.0f - x2 * (1.66666667e-01f - x2 * (8.33333333e-03f - x2 * (1.98412698e-04f -
         x2 * (2.75573192e-06f - x2 * 2.50521084e-08f)))));
}

static inline float SqDbToGain(float db) { return fm1_exp2f(kLog2PerDb * db); }

static inline int SqTypeOf(float v) {
  const int t = (int)(v + 0.5f);   /* v is clamped to 0..2 */
  return t < 0 ? 0 : (t >= T_COUNT ? T_COUNT - 1 : t);
}

/* ---------------------------------------------------------------------- */
/* Controls                                                                */
/* ---------------------------------------------------------------------- */

static void SquashDerive(SquashInstance *self) {
  const float fs = self->rate;
  const float *v = self->value;
  SquashCtl *c = &self->ctl;
  const float squash = v[P_SQUASH];
  /* Snap: Pop3's A = 1 - Squash, T = A^4; B, C, D, F, G, H as above. */
  const float a = 1.0f - squash;
  c->thr = a * a * a * a;
  const float rb = 1.0f - v[P_RATIO];
  c->ratio = 1.0f - rb * rb;
  c->atk = 1.0f / (0.001f * v[P_ATTACK] * fs);
  c->rel = 1.0f / (0.001f * v[P_RELEASE] * fs);
  c->gthr = v[P_GATE] <= kSquashParams[P_GATE].min ? 0.0f : SqDbToGain(v[P_GATE]);
  const float rf = 1.0f - v[P_DEPTH];
  c->gratio = 1.0f - rf * rf;
  const float g1 = v[P_HOLD] + 1.0f;
  c->gsus = kHalfPi * (g1 * g1) * (g1 * g1);
  c->grel = 1.0f / (0.001f * v[P_GATE_REL] * fs);
  /* Mu: Pressure4's threshold from A = Squash; release in samples. */
  c->mu_thr = 1.0f - 0.95f * squash;
  c->mu_lift = 1.0f / c->mu_thr;
  c->mu_release = 0.001f * v[P_RELEASE] * fs;
  c->mu_fastest = SqSqrt(c->mu_release);
  c->mu_positive = v[P_SHAPE] >= 0.0f;
  c->mew = SqAbs(v[P_SHAPE]);
  /* Split: ButterComp2's A = Squash. */
  c->lift = SqDbToGain(14.0f * squash);
  c->factor = 0.012f * (squash / 135.0f) * self->inv_scale;
  c->inv_outgain = 1.0f / ((c->lift - 1.0f) / 1.5f + 1.0f);
  /* Ours. */
  c->out = SqDbToGain(v[P_OUTPUT]);
  c->mix = v[P_MIX];
}

/* ---------------------------------------------------------------------- */
/* The three Types: one frame each, returning the gains they apply         */
/* ---------------------------------------------------------------------- */

static void SnapFrame(SquashInstance *self, float l, float r, float g[2]) {
  const SquashCtl *c = &self->ctl;
  SnapState *s = &self->snap;
  const float x[2] = { SqAbs(l), SqAbs(r) };
  /* Each channel's state moves by Pop3's step: towards T / |x| by the
   * attack when over the threshold, else towards 1 by the release. Both
   * steps are p alpha + beta. */
  float alpha[2], beta[2];
  for (int k = 0; k < 2; ++k) {
    if (x[k] > c->thr) {
      alpha[k] = 1.0f - c->atk;
      beta[k] = (c->thr / x[k]) * c->atk;
    } else {
      alpha[k] = 1.0f - c->rel;
      beta[k] = c->rel;
    }
  }
  float m = s->m, d = s->d;
  int hi = s->hi;
  if (alpha[0] == alpha[1] && beta[0] == beta[1]) {
    /* The same step for both: the lower moves, the gap scales. */
    m = m * alpha[0] + beta[0];
    d = d * alpha[0];
  } else {
    const float pl = hi == 0 ? m + d : m, pr = hi == 1 ? m + d : m;
    const float nl = pl * alpha[0] + beta[0], nr = pr * alpha[1] + beta[1];
    hi = nr > nl;
    m = hi ? nl : nr;
    d = hi ? nr - nl : nl - nr;
  }
  /* Pop3's link, in its order: if the left state is the higher it is
   * pulled down by the attack, and then the right if it is now the higher;
   * if the right is the higher only it is pulled. e = d - (m + d) attack is
   * how far the pulled one ends above the other. With the left higher and
   * within a pull (e < 0) both are pulled on every frame and the gap shrinks
   * by 1 - attack: a hold that the release balances at rel / (atk + rel)
   * until the two are equal. In double precision that lasts as long as the
   * gap takes to reach the last bits of m; kept as m and d it does here too
   * (d < 1e-14 m is equality). Kept as two floats it would never end: each
   * state would stall on a fixed point of its own float rounding, a few
   * ulps apart, and hold the gain there for good. */
  if (d > 0.0f) {
    const float e = d - (m + d) * c->atk;
    if (e > 0.0f) {
      d = e;                             /* only the higher is pulled */
    } else if (e == 0.0f) {
      d = 0.0f;                          /* pulled level */
    } else if (hi == 0) {
      m = m - m * c->atk;                /* left, then right: the gap shrinks with them */
      d = d - d * c->atk;
    } else {
      m = m + e;                         /* right only, now under the left */
      d = -e;
      hi = 0;
    }
    if (d < kSnapEqual * m) d = 0.0f;
  }
  if (x[0] > c->gthr || x[1] > c->gthr) {
    s->gate = c->gsus;
  } else {
    s->gate = s->gate * (1.0f - c->grel);
    if (s->gate < kFlush) s->gate = 0.0f;
  }
  /* Both held to 0..1. */
  if (m > 1.0f) m = 1.0f;
  if (!(m >= kFlush)) m = 0.0f;
  if (m + d > 1.0f) d = 1.0f - m;
  if (!(d >= kFlush)) d = 0.0f;
  s->m = m;
  s->d = d;
  s->hi = hi;
  const float p[2] = { hi == 0 ? m + d : m, hi == 1 ? m + d : m };
  for (int k = 0; k < 2; ++k) g[k] = (1.0f - c->ratio) + p[k] * c->ratio;
  if (s->gate < kHalfPi) {
    const float gg = (1.0f - c->gratio) + SqSinQ(s->gate) * c->gratio;
    g[0] = g[0] * gg;
    g[1] = g[1] * gg;
  }
}

static void MuFrame(SquashInstance *self, float l, float r, float g[2]) {
  const SquashCtl *c = &self->ctl;
  MuState *s = &self->mu;
  const float al = SqAbs(l), ar = SqAbs(r);
  const float sense = (al > ar ? al : ar) * c->mu_lift;
  const float thr = c->mu_thr, speed = s->speed;
  float coef = s->coef;
  /* Pressure4's steps, (c (n - 1) + target) / n, written as c + (target -
   * c) / n: the same in exact arithmetic, and in float they keep the target's
   * share where n (up to 1e15 for speed^2) would swallow it. */
  if (sense > thr) {
    const float vary = thr / sense;
    const float att = SqSqrt(speed);
    coef = coef + ((vary < thr ? thr : vary) - coef) / att;
  } else {
    coef = coef + (1.0f - coef) / (speed * speed);
  }
  s->coef = coef;
  /* (speed (speed - 1) + sense release + sqrt(release)) / speed, likewise. */
  s->speed = (speed - 1.0f) + (sense * c->mu_release + c->mu_fastest) / speed;
  const float curved = c->mu_positive ? coef * coef : SqSqrt(coef);
  const float gain = curved * c->mew + coef * (1.0f - c->mew);
  g[0] = g[1] = gain;
}

static void SplitFrame(SquashInstance *self, float l, float r, float g[2]) {
  const SquashCtl *c = &self->ctl;
  SplitState *s = &self->split;
  const float in[2] = { l, r };
  for (int k = 0; k < 2; ++k) {
    const float x = in[k] * c->lift;
    float divisor = c->factor / (1.0f + SqAbs(s->last[k]));
    const float remainder = divisor;
    divisor = 1.0f - divisor;
    float ipos = x + 1.0f;
    if (ipos < 0.0f) ipos = 0.0f;
    float opos = ipos * 0.5f;
    if (opos > 1.0f) opos = 1.0f;
    ipos = ipos * ipos;
    float tpos = s->tpos[k] * divisor + ipos * remainder;
    if (tpos < kSplitTargetFloor) tpos = kSplitTargetFloor;
    s->tpos[k] = tpos;
    const float ip = 1.0f / tpos;
    const float cpos = ip * ip;
    float ineg = -x + 1.0f;
    if (ineg < 0.0f) ineg = 0.0f;
    float oneg = ineg * 0.5f;
    if (oneg > 1.0f) oneg = 1.0f;
    ineg = ineg * ineg;
    float tneg = s->tneg[k] * divisor + ineg * remainder;
    if (tneg < kSplitTargetFloor) tneg = kSplitTargetFloor;
    s->tneg[k] = tneg;
    const float in_ = 1.0f / tneg;
    const float cneg = in_ * in_;
    if (x > 0.0f) {
      if (s->flip) s->a_pos[k] = s->a_pos[k] * divisor + cpos * remainder;
      else s->b_pos[k] = s->b_pos[k] * divisor + cpos * remainder;
    } else {
      if (s->flip) s->a_neg[k] = s->a_neg[k] * divisor + cneg * remainder;
      else s->b_neg[k] = s->b_neg[k] * divisor + cneg * remainder;
    }
    const float total = s->flip ? s->a_pos[k] * opos + s->a_neg[k] * oneg
                                : s->b_pos[k] * opos + s->b_neg[k] * oneg;
    g[k] = c->lift * total * c->inv_outgain;
  }
  s->flip = !s->flip;
}

static void TypeFrame(SquashInstance *self, int type, float l, float r, float g[2]) {
  switch (type) {
    case T_MU: MuFrame(self, l, r, g); break;
    case T_SPLIT: SplitFrame(self, l, r, g); break;
    default: SnapFrame(self, l, r, g); break;
  }
}

/* Start `type` from the gains g the sounding Type was applying, at a frame
 * whose level is `level` (max |L|, |R|). */
static void SeedType(SquashInstance *self, int type, const float g[2], float level) {
  const SquashCtl *c = &self->ctl;
  switch (type) {
    case T_MU: {
      float gl = g[0] < g[1] ? g[0] : g[1];
      if (gl > 1.0f) gl = 1.0f;
      if (gl < 0.0f) gl = 0.0f;
      const float m = c->mew;
      float coef;
      if (c->mu_positive) {   /* m c^2 + (1 - m) c = g */
        coef = m > 1e-6f
            ? (-(1.0f - m) + SqSqrt((1.0f - m) * (1.0f - m) + 4.0f * m * gl)) / (2.0f * m)
            : gl;
      } else {                /* m sqrt(c) + (1 - m) c = g */
        const float t = (1.0f - m) > 1e-6f
            ? (-m + SqSqrt(m * m + 4.0f * (1.0f - m) * gl)) / (2.0f * (1.0f - m))
            : gl;
        coef = t * t;
      }
      if (coef < c->mu_thr) coef = c->mu_thr;
      if (coef > 1.0f) coef = 1.0f;
      self->mu.coef = coef;
      self->mu.speed = c->mu_fastest + level * c->mu_lift * c->mu_release;
      break;
    }
    case T_SPLIT: {
      for (int k = 0; k < 2; ++k) {
        float t = g[k] / (c->lift * c->inv_outgain);
        if (t > 16.0f) t = 16.0f;
        if (t < 0.0f) t = 0.0f;
        SplitState *s = &self->split;
        s->a_pos[k] = s->a_neg[k] = s->b_pos[k] = s->b_neg[k] = t;
        float target = t > 1e-6f ? 1.0f / SqSqrt(t) : 1000.0f;   /* its gain is 1 / target^2 */
        if (target < kSplitTargetFloor) target = kSplitTargetFloor;
        s->tpos[k] = s->tneg[k] = target;
      }
      break;
    }
    default: {
      float p[2];
      for (int k = 0; k < 2; ++k) {
        p[k] = c->ratio > 1e-6f ? SqClamp01((g[k] - (1.0f - c->ratio)) / c->ratio) : 1.0f;
      }
      self->snap.hi = p[1] > p[0];
      self->snap.m = self->snap.hi ? p[0] : p[1];
      self->snap.d = self->snap.hi ? p[1] - p[0] : p[0] - p[1];
      self->snap.gate = c->gsus;
      break;
    }
  }
}

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t SquashInstanceSize(const fm1_host_t *host) {
  (void)host;
  return (sizeof(SquashInstance) + 15u) & ~(size_t)15u;
}

static void SquashReset(SquashInstance *self) {
  self->snap.m = 1.0f;
  self->snap.d = 0.0f;
  self->snap.hi = 0;
  self->snap.gate = 1.0f;                  /* Pop3 starts its gate at 1 */
  self->mu.coef = 1.0f;
  self->mu.speed = kMuSpeedStart;
  SplitState *s = &self->split;
  for (int k = 0; k < 2; ++k) {
    s->tpos[k] = s->tneg[k] = 1.0f;
    s->a_pos[k] = s->a_neg[k] = s->b_pos[k] = s->b_neg[k] = 1.0f;
    s->last[k] = 0.0f;
  }
  s->flip = 0;
  self->gain[0] = self->gain[1] = 1.0f;
}

static void *SquashCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;   /* NaN fails too */
  SquashInstance *self = (SquashInstance *)mem;
  memset(self, 0, sizeof(*self));
  self->rate = fs;
  self->inv_scale = 44100.0f / fs;
  for (int i = 0; i < P_COUNT; ++i) self->value[i] = kSquashParams[i].def;
  fm1_smooth_init(self->ramp, self->value, P_COUNT);
  self->steps = fm1_smooth_steps(fs, 1);
  uint32_t n = (uint32_t)(kFadeSeconds * fs + 0.5f);
  self->fade_len = n > 0u ? n : 1u;
  self->inv_fade = 1.0f / (float)self->fade_len;
  self->type = self->want = self->from = SqTypeOf(kSquashParams[P_TYPE].def);
  SquashDerive(self);
  SquashReset(self);
  return self;
}

static void SquashDestroy(void *self) { (void)self; }

static void SquashSet(void *s, uint16_t index, float v) {
  SquashInstance *self = (SquashInstance *)s;
  if (index >= P_COUNT) return;
  v = fm1_param_clamp(&kSquashParams[index], v);
  if (index == P_TYPE) {
    self->value[P_TYPE] = v;
    self->want = SqTypeOf(v);
    if (!self->started) self->type = self->from = self->want;   /* before the first render: at once */
    return;
  }
  fm1_smooth_set(&self->ramp[index], &self->value[index], v, self->started ? self->steps : 0u);
  if (!self->started) SquashDerive(self);
}

static void SquashRender(void *s, float *lr, uint32_t frames) {
  SquashInstance *self = (SquashInstance *)s;
  self->started = 1;
  for (uint32_t f = 0; f < frames; ++f) {
    if (fm1_smooth_moving(self->ramp, P_COUNT)) {
      fm1_smooth_tick(self->ramp, self->value, P_COUNT);
      SquashDerive(self);
    }
    const float l = SqGuard(lr[2 * f]), r = SqGuard(lr[2 * f + 1]);
    if (self->fade == 0u && self->want != self->type) {
      /* A Type change: the new one starts from the gain in force. */
      const float al = SqAbs(l), ar = SqAbs(r);
      self->from = self->type;
      self->type = self->want;
      SeedType(self, self->type, self->gain, al > ar ? al : ar);
      self->fade = self->fade_len;
    }
    float g[2];
    TypeFrame(self, self->type, l, r, g);
    self->gain[0] = g[0];
    self->gain[1] = g[1];
    if (self->fade) {
      float o[2];
      TypeFrame(self, self->from, l, r, o);
      const float t = 1.0f - (float)self->fade * self->inv_fade, u = 1.0f - t;
      g[0] = u * o[0] + t * g[0];
      g[1] = u * o[1] + t * g[1];
      --self->fade;
    }
    const SquashCtl *c = &self->ctl;
    const float wet = c->mix * c->out, dry = 1.0f - c->mix;
    const float yl = l * dry + l * (g[0] * wet), yr = r * dry + r * (g[1] * wet);
    lr[2 * f] = yl;
    lr[2 * f + 1] = yr;
    self->split.last[0] = yl;   /* Split slows its recovery while its output is loud */
    self->split.last[1] = yr;
  }
}

#ifdef __cplusplus
extern "C" {
#endif

extern const fm1_engine_t fm1_engine_squash;
const fm1_engine_t fm1_engine_squash = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "squash", "Squash",
  "Airwindows (Chris Johnson), MIT: Pop3, Pressure4 and ButterComp2, ported "
  "to single precision without libm by this repository (MIT)",
  kSquashParams, P_COUNT, 0,
  SquashInstanceSize, SquashCreate, SquashDestroy,
  NULL, NULL, NULL,
  SquashSet, SquashRender,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
};

#ifdef __cplusplus
}
#endif
