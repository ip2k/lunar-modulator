/* fx_djfilter.cc -- "DJ Filter": one knob that low-passes to the left of
 * centre and high-passes to the right, and leaves the sound untouched in
 * between (FM1_KIND_AUDIO_FX). Written for this repository; notes in
 * engines/README.md ("DJ Filter"), design in
 * notes/2026-10-02-delay-reverb-eq-gates-options.md §4.3. Built for the end
 * of a chain (the master bus, or FX2 until there is one): at its default it
 * costs a guard per sample and passes the input bit for bit.
 *
 * Per frame, both channels sharing one set of coefficients:
 *
 *   guard -> [dead zone: out = in, no filter runs]
 *         -> SVF (Resonance) -> [24 dB: a second SVF at Q 0.707] = wet
 *         -> out = in + Wet x (wet - in),  Wet = Mix x the entry fade
 *
 *   Sweep      -1..1. Left of the dead zone the low-pass tap, right of it
 *              the high-pass tap. u = (|Sweep| - Dead Zone) / (1 - Dead
 *              Zone) is the travel past the dead zone, 0..1. The cutoff is
 *              exponential in u (equal octaves for equal travel): low-pass
 *              20 kHz * 2^(-8.38 u Range), 20 kHz down to 60 Hz; high-pass
 *              20 Hz * 2^(8.64 u Range), 20 Hz up to 8 kHz; never above
 *              0.45 of the host rate.
 *   Resonance  0..1. Q = 0.707 + Resonance * (8 - 0.707) * 4u(1 - u): the
 *              open end (u = 0) and the far end (u = 1) never whistle, and
 *              Q reaches 8 (+18 dB at the cutoff) at mid travel.
 *   Slope      12 or 24 dB per octave. 24 dB runs a second SVF of the same
 *              type and cutoff at Q 0.707 after the first, which alone
 *              resonates. A change crossfades the two outputs over 5 ms.
 *   Mix        0..1, filtered against dry; 0 is a bypass.
 *   Dead Zone  0..0.2, the span either side of centre in which the input
 *              passes untouched.
 *   Range      0.1..1, how much of the sweep the knob reaches, in octaves:
 *              at 0.5 the low-pass stops at 1.1 kHz and the high-pass at
 *              400 Hz.
 *
 * The filter is the trapezoidal ("zero-delay feedback", TPT) state-variable
 * filter of Andrew Simper (Cytomic, "Linear Trap Integrated SVF", 2013) and
 * Vadim Zavalishin ("The Art of VA Filter Design"), the form stmlib's Svf
 * (Emilie Gillet, MIT) uses, written out here because entering a side sets
 * the states, which stmlib::Svf keeps private. g = tan(pi fc / fs), r = 1/Q,
 * h = 1 / (1 + r g + g^2):
 *   hp = (x - (r + g) s1 - s2) h;  bp = g hp + s1;  lp = g bp + s2;
 *   s1 <- g hp + bp;  s2 <- g bp + lp.
 * Its states are the two integrators' charges, so new coefficients change
 * the filter's future and not its stored energy: it can be swept at audio
 * rate without the transients of a direct-form biquad.
 *
 * Why the cutoff law is exponential in frequency and not in g, as the
 * research note proposed: g = g_a (g_b / g_a)^u spends a third of the
 * low-pass side's travel between 20 kHz and 7 kHz, where little changes,
 * because tan() stretches the top octaves; equal octaves per travel is how
 * a cutoff knob is expected to behave. The cost is one tan() per control
 * tick (below), by our own polynomial, so it stays libm-free.
 *
 * Smoothing, zipper-free and block-size independent. Every 16 frames, on a
 * grid kept by the instance's own frame counter, a control tick glides the
 * knobs (Sweep through two 5 ms one-poles in series, so a jump of the knob
 * starts the sweep with no corner; the others through one of 5 ms), moves
 * the travel u in force towards where the knob is (rate limits below),
 * works out g and r there, and sets linear ramps from the values in force to
 * them over the next 16 frames. Every frame while they ramp, h is
 * recomputed and the wet share is evaluated from the ramped u and Mix. So
 * the coefficients never step, a host's parameter writes every 32 frames
 * (the modulation matrix) come out as a smooth sweep, and a change set
 * between any two blocks is read at the same frame whatever the block size.
 * Values set before the first render apply from its first sample.
 *
 * Entering and leaving a side. In the dead zone (or at Mix 0) the filter does
 * not run. Entering a side, u starts at 0, the open end, with the states
 * where they would be had the filter been running there on a slowly moving
 * input: the low-pass's low-pass integrator holds the input (its output is
 * the input), the high-pass's states are zero (its output is the input, less
 * what it would have removed). The wet share is Mix x smoothstep(u / 0.08):
 * it fades in over the first 8 % of the travel, and u crosses that zone in
 * no less than 3 ms either way, and moves no faster than 0 to 1 in 10 ms
 * elsewhere (only the catch-up after entering reaches that). Leaving, u
 * returns to 0 the same way before the filter stops; crossing to the other
 * side goes through 0 and the bypass. Switching one SVF between its low- and
 * high-pass taps would click (Airwindows' Isolator3 notes the same, cited in
 * the research note). Measured while writing this (fm1-djfilter-test's
 * transitions, 2026-10-03, with the starting states changed): starting the
 * high-pass from the input's DC steady state, as the note proposed, doubles
 * what entering it adds above 4 kHz and overshoots a bass note by 15 % when
 * crossing with no dead zone; starting the low-pass from zero adds 100
 * times more above 4 kHz when 24 dB starts. A fade tied to u alone, with no
 * rate limit and evaluated per tick, left 25 times more on a fast crossing.
 *
 * Determinism: no libm. 2^x (CompExp2, fx_comp_math.h) and tan(pi x) are
 * polynomials written in this repository, and everything else is +, -, *, /
 * and comparisons, with floating-point
 * contraction off for this file under clang (below), so a native build and
 * the browser's WebAssembly compute the same bits [verified 2026-10-03: the
 * same output bits, with parameters moving, at three host rates, from Apple
 * clang arm64 at -O0 and -O2, GCC x86-64 (also with FMA available and
 * -ffp-contract=off), GCC i386 with SSE, and Emscripten; Apple clang without
 * the pragma differs].
 *
 * Contracts (fm1_engine.h): no heap, every field set in create, NaN-safe
 * parameters (fm1_param_clamp), finite output. Input guard as the Mutable
 * effects' (mi_fx.cc): NaN reads as 0 and anything beyond +/-16 is clamped,
 * dry path included, so nothing non-finite reaches a state. States below
 * 1e-20 flush to zero, so a tail ends in exact silence, not subnormals.
 *
 * Cost, per frame while filtering: 10 operations per SVF and channel, two
 * SVFs per channel at 24 dB, the guard and the mix: about 30 operations
 * per frame at 12 dB, 50 at 24 dB. While a sweep moves: 6 adds of the
 * ramps, one divide per SVF in use and the smoothstep in the entry zone; a
 * control tick (one in 16 frames) adds about 90 operations and two divides
 * (2^x, tan, 1/Q). In the dead zone: the guard alone. Measured in
 * engines/README.md.
 *
 * Written in the C subset of C++11 so it would build as C99 unchanged apart
 * from the extern "C" linkage below. MIT licence, like the rest of this
 * repository.
 */

#include "fm1_engine.h"
#include "fx_comp_math.h"

#include <stdint.h>
#include <string.h>

/* No fused multiply-adds in this file: the browser's WebAssembly cannot fuse,
 * so a native build that did would round differently (Apple clang on arm64
 * fuses by default; Comp found the same). GCC ignores the pragma: build for
 * a GCC target with FMA with -ffp-contract=off. */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

#if defined(__GNUC__) || defined(__clang__)
#define DJ_INLINE static inline __attribute__((always_inline))
#else
#define DJ_INLINE static inline
#endif

enum { P_SWEEP, P_RESONANCE, P_SLOPE, P_MIX, P_DEAD, P_RANGE, P_COUNT };

static const char *const kDjSlopeNames[2] = { "12 dB", "24 dB" };

/* Uids (API v2) are fixed: never renumber one; a new parameter takes the next
 * free uid. The FLOATs are read at every control tick: SMOOTH and MOD. Slope
 * crossfades over 5 ms, so it is lockable and takes modulation (rounded). */
static const fm1_param_t kDjParams[P_COUNT] = {
  { "Sweep",     FM1_PARAM_FLOAT, -1, 1, 0.0f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Sweep" },
  { "Resonance", FM1_PARAM_FLOAT, 0, 1, 0.2f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Reso" },
  { "Slope",     FM1_PARAM_ENUM, 0, 1, 0.0f, kDjSlopeNames, 0, 3, FM1_PARAM_MOD, FM1_UNIT_NONE, "Slope" },
  { "Mix",       FM1_PARAM_FLOAT, 0, 1, 1.0f, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Dead Zone", FM1_PARAM_FLOAT, 0, 0.2f, 0.05f, NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Dead" },
  { "Range",     FM1_PARAM_FLOAT, 0.1f, 1, 1.0f, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Range" },
};

/* The knobs as glided at the control tick. */
enum { G_SWEEP, G_RESONANCE, G_SLOPE, G_MIX, G_DEAD, G_RANGE, G_COUNT };

enum { SIDE_NONE = 0, SIDE_LP = 1, SIDE_HP = 2 };

static const int kTick = 16;                    /* frames per control tick */
static const float kTickInv = 0.0625f;          /* 1 / kTick */
static const float kLpOpenHz = 20000.0f;        /* low-pass at u = 0 */
static const float kLpOctaves = 8.38082178f;    /* log2(20000 / 60): 60 Hz at u = 1 */
static const float kHpOpenHz = 20.0f;           /* high-pass at u = 0 */
static const float kHpOctaves = 8.64385619f;    /* log2(8000 / 20): 8 kHz at u = 1 */
static const float kMaxRatio = 0.45f;           /* cutoff / host rate, at most */
static const float kEntry = 0.08f;              /* the wet share fades in over this much u */
static const float kEntrySeconds = 0.003f;      /* the entry zone takes at least this */
static const float kTravelSeconds = 0.010f;     /* u 0 -> 1 takes at least this */
static const float kQ0 = 0.707106781f;          /* Butterworth: no peak */
static const float kQMax = 8.0f;                /* Resonance 1, mid travel */
static const float kSqrt2 = 1.41421356f;        /* r of the second stage */
static const float kSweepSeconds = 0.005f;      /* each of Sweep's two glide stages */
static const float kGlideSeconds = 0.005f;      /* every other knob's, and Slope's crossfade */
static const float kSnap = 1e-4f;               /* a glide this close lands */
static const float kInputLimit = 16.0f;         /* the input guard, as mi_fx.cc */
static const float kFlush = 1e-20f;             /* states below this become 0 */
static const float kLog2e = 1.44269504f;
static const float kPi = 3.14159265f;

typedef struct DjChannel {
  float s1, s2;             /* first SVF: band-pass and low-pass integrators */
  float t1, t2;             /* second SVF (24 dB) */
} DjChannel;

typedef struct DjInstance {
  float param[P_COUNT];     /* knob values, clamped */
  float glide[G_COUNT];     /* the knobs as glided at the last tick */
  float sweep_mid;          /* Sweep's glide, first stage */
  float k_sweep, k_glide;   /* one-pole steps per tick */
  float slow_step;          /* u's largest change per tick in the entry zone */
  float fast_step;          /* ... and elsewhere */
  float lp_open, hp_open;   /* open-end cutoffs over the host rate */
  /* In force at the last frame rendered. u is the travel on `side`, mix the
   * glided Mix, slope the 24 dB share (0..1). */
  float g, r, u, mix, slope;
  float h1, h2, wet;        /* derived from them */
  /* This segment's end values and per-frame steps. */
  float g_end, r_end, u_end, mix_end, slope_end;
  float dg, dr, du, dmix, dslope;
  int side;                 /* SIDE_*: the tap in use, NONE in bypass */
  int next_side;            /* the side after this segment */
  int phase;                /* frame within the segment, 0..kTick-1 */
  int coef_moving;          /* g or r ramp in this segment */
  int blend_moving;         /* u, mix or slope ramp in this segment */
  int init1, init2;         /* set the states at the segment's first frame */
  int stage2;               /* the second SVF runs */
  int primed;               /* 0 until the first tick */
  DjChannel ch[2];
} DjInstance;

/* ---------------------------------------------------------------------- */
/* Maths without libm                                                      */
/* ---------------------------------------------------------------------- */

/* 2^x is CompExp2 (fx_comp_math.h, shared with Comp and Tilt): a Taylor
 * polynomial and the exponent set directly, the same bits on every build.
 * This file had a private copy of it, identical line for line, from before
 * Comp reached main. */

/* tan(pi x) for x in [0, 0.45]: sin and cos of y = pi x (or of pi (1/2 - x)
 * above 1/4, then cos / sin), each by its Taylor polynomial on [0, pi/4]
 * (truncation under 3e-9 relative). 1/2 - x is exact there (Sterbenz), so
 * the cutoff keeps full precision near the top. One divide. */
static float DjTanPi(float x) {
  const int above = x > 0.25f;
  float y = above ? 0.5f - x : x;
  y = y * kPi;
  const float y2 = y * y;
  float s = 2.75573192e-06f * y2;           /* 1/9! */
  s = s - 1.98412698e-04f;                  /* 1/7! */
  s = s * y2;
  s = s + 8.33333333e-03f;                  /* 1/5! */
  s = s * y2;
  s = s - 1.66666667e-01f;                  /* 1/3! */
  s = s * y2;
  s = s * y;
  s = s + y;
  float c = -2.75573192e-07f * y2;          /* 1/10! */
  c = c + 2.48015873e-05f;                  /* 1/8! */
  c = c * y2;
  c = c - 1.38888889e-03f;                  /* 1/6! */
  c = c * y2;
  c = c + 4.16666667e-02f;                  /* 1/4! */
  c = c * y2;
  c = c - 0.5f;
  c = c * y2;
  c = c + 1.0f;
  return above ? c / s : s / c;
}

/* ---------------------------------------------------------------------- */
/* Controls                                                                */
/* ---------------------------------------------------------------------- */

static inline float DjGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

static inline float DjFlush(float v) {
  return (v > -kFlush && v < kFlush) ? 0.0f : v;
}

/* One step of a glide; lands exactly when within kSnap (relative). */
static inline float DjGlide(float v, float t, float k) {
  const float e = t - v;
  const float a = t < 0.0f ? -t : t;
  const float m = e < 0.0f ? -e : e;
  if (m <= kSnap * (1.0f + a)) return t;
  return v + k * e;
}

/* The value each knob glides to. */
static float DjTarget(const DjInstance *self, int g) {
  switch (g) {
    case G_SWEEP: return self->param[P_SWEEP];
    case G_RESONANCE: return self->param[P_RESONANCE];
    case G_SLOPE: return self->param[P_SLOPE] >= 0.5f ? 1.0f : 0.0f;
    case G_MIX: return self->param[P_MIX];
    case G_DEAD: return self->param[P_DEAD];
    default: return self->param[P_RANGE];
  }
}

/* Where the glided Sweep and Dead Zone put the knob: its side by the sign
 * of Sweep, and its travel u past the dead zone, 0..1. */
static float DjAskTravel(const DjInstance *self, int *side) {
  const float sweep = self->glide[G_SWEEP];
  const float dead = self->glide[G_DEAD];
  const float a = sweep < 0.0f ? -sweep : sweep;
  *side = sweep < 0.0f ? SIDE_LP : SIDE_HP;
  float u = (a - dead) / (1.0f - dead);
  if (!(u > 0.0f)) u = 0.0f;
  if (u > 1.0f) u = 1.0f;
  return u;
}

/* The coefficients at travel u on a side. */
static void DjCoefficients(const DjInstance *self, int side, float u, float *g, float *r) {
  const float octaves = u * self->glide[G_RANGE];
  float ratio;
  if (side == SIDE_LP) {
    const float e = -kLpOctaves * octaves;
    ratio = self->lp_open * CompExp2(e);
  } else {
    const float e = kHpOctaves * octaves;
    ratio = self->hp_open * CompExp2(e);
  }
  if (ratio > kMaxRatio) ratio = kMaxRatio;
  *g = DjTanPi(ratio);
  const float window = 4.0f * u * (1.0f - u);
  const float depth = self->glide[G_RESONANCE] * (kQMax - kQ0);
  const float q = kQ0 + depth * window;
  *r = 1.0f / q;
}

/* The wet share at travel u: Mix, faded in over the entry zone by a
 * smoothstep, which has no corners at either end. Evaluated every frame
 * while u or Mix ramp, so the fade is as smooth as the travel. */
static inline float DjWet(float u, float mix) {
  if (!(u < kEntry)) return mix;
  float e = u * (1.0f / kEntry);
  if (e < 0.0f) e = 0.0f;
  const float e2 = e * e;
  const float e3 = 2.0f * e;
  const float t = 3.0f - e3;
  const float entry = e2 * t;
  return mix * entry;
}

/* The travel in force moved towards goal: within the entry zone by at most
 * `slow` per tick, elsewhere by at most `fast`. */
static float DjMove(float u, float goal, float slow, float fast) {
  if (goal >= u) {
    const float up = u + (u < kEntry ? slow : fast);
    return goal < up ? goal : up;
  }
  float down = u - fast;
  const float in_zone = (u < kEntry ? u : kEntry) - slow;
  if (down < in_zone) down = in_zone;
  return goal > down ? goal : down;
}

static inline float DjH(float g, float r) {
  const float rg = r + g;
  const float d = g * rg;
  return 1.0f / (1.0f + d);
}

static void DjUpdateH(DjInstance *self) {
  self->h1 = DjH(self->g, self->r);
  self->h2 = self->stage2 ? DjH(self->g, kSqrt2) : 1.0f;
}

/* The control tick, at the first frame of each 16-frame segment. */
static void DjTick(DjInstance *self) {
  const int first = !self->primed;
  self->primed = 1;
  for (int k = 0; k < G_COUNT; ++k) {
    const float t = DjTarget(self, k);
    if (first) {
      self->glide[k] = t;
      if (k == G_SWEEP) self->sweep_mid = t;
    } else if (k == G_SWEEP) {
      /* Two one-poles in series: the sweep starts moving with no jump in
       * its speed, so a jump of the knob makes no corner in the cutoff. */
      self->sweep_mid = DjGlide(self->sweep_mid, t, self->k_sweep);
      self->glide[k] = DjGlide(self->glide[k], self->sweep_mid, self->k_sweep);
    } else {
      self->glide[k] = DjGlide(self->glide[k], t, self->k_glide);
    }
  }
  int want_side;
  const float want = DjAskTravel(self, &want_side);
  const int active = want > 0.0f && self->glide[G_MIX] > 0.0f;
  self->init1 = self->init2 = 0;

  float goal;
  if (self->side == SIDE_NONE) {
    self->next_side = SIDE_NONE;
    if (!active) return;                          /* bypass segment */
    /* Enter at the open end, where the wet share is 0 (where asked at once
     * when set before the first render). */
    self->side = want_side;
    self->u = first ? want : 0.0f;
    DjCoefficients(self, self->side, self->u, &self->g, &self->r);
    self->mix = self->glide[G_MIX];
    self->slope = self->glide[G_SLOPE];
    self->wet = DjWet(self->u, self->mix);
    self->stage2 = self->slope > 0.0f;
    self->init1 = 1;
    self->init2 = self->stage2;
    DjUpdateH(self);
    goal = want;
  } else {
    /* Back to the open end and out when the knob is in the dead zone, on
     * the other side, or at Mix 0; the other side is entered at the tick
     * after the travel reaches 0. */
    goal = (active && want_side == self->side) ? want : 0.0f;
  }
  self->u_end = first ? goal : DjMove(self->u, goal, self->slow_step, self->fast_step);
  DjCoefficients(self, self->side, self->u_end, &self->g_end, &self->r_end);
  self->mix_end = self->glide[G_MIX];
  self->slope_end = self->glide[G_SLOPE];
  self->next_side = (self->u_end > 0.0f || goal > 0.0f) ? self->side : SIDE_NONE;
  if (self->wet == 0.0f && DjWet(self->u_end, self->mix_end) == 0.0f) {
    self->side = self->next_side = SIDE_NONE;     /* nothing to fade */
    return;
  }
  self->dg = (self->g_end - self->g) * kTickInv;
  self->dr = (self->r_end - self->r) * kTickInv;
  self->du = (self->u_end - self->u) * kTickInv;
  self->dmix = (self->mix_end - self->mix) * kTickInv;
  self->dslope = (self->slope_end - self->slope) * kTickInv;
  self->coef_moving = self->g != self->g_end || self->r != self->r_end;
  self->blend_moving = self->u != self->u_end || self->mix != self->mix_end ||
                       self->slope != self->slope_end;
  if (!self->stage2 && self->slope_end > 0.0f) {     /* 12 -> 24 dB starts */
    self->stage2 = 1;
    self->init2 = 1;
    DjUpdateH(self);
  }
}

/* After the segment's last frame. */
static void DjSegmentEnd(DjInstance *self) {
  self->side = self->next_side;
  if (self->slope == 0.0f) self->stage2 = 0;          /* 24 -> 12 dB done */
}

/* ---------------------------------------------------------------------- */
/* The filter                                                              */
/* ---------------------------------------------------------------------- */

/* One trapezoidal SVF step; returns the high-pass or low-pass tap. rg is
 * r + g, h is 1 / (1 + g rg). */
DJ_INLINE float DjSvf(float x, float g, float rg, float h, float *s1, float *s2, int hp_tap) {
  const float a = rg * *s1;
  const float b = x - a;
  const float c = b - *s2;
  const float hp = c * h;
  const float v = g * hp;
  const float bp = v + *s1;
  const float w = g * bp;
  const float lp = w + *s2;
  *s1 = DjFlush(v + bp);
  *s2 = DjFlush(w + lp);
  return hp_tap ? hp : lp;
}

/* n frames of one segment, from the instance's phase on (n <= what is left
 * of the segment). */
static void DjRun(DjInstance *self, DjChannel *ch, float *lr, uint32_t n) {
  float g = self->g, r = self->r, u = self->u, mix = self->mix, slope = self->slope;
  float h1 = self->h1, h2 = self->h2, wet = self->wet;
  const float dg = self->dg, dr = self->dr, du = self->du, dmix = self->dmix;
  const float dslope = self->dslope;
  const int hp_tap = self->side == SIDE_HP;
  const int stage2 = self->stage2;
  const int coef_moving = self->coef_moving, blend_moving = self->blend_moving;
  int init1 = self->init1, init2 = self->init2;
  int phase = self->phase;
  for (uint32_t i = 0; i < n; ++i, ++phase) {
    if (coef_moving) {
      if (phase == kTick - 1) {               /* the segment lands exactly */
        g = self->g_end;
        r = self->r_end;
      } else {
        g = g + dg;
        r = r + dr;
      }
      h1 = DjH(g, r);
      if (stage2) h2 = DjH(g, kSqrt2);
    }
    if (blend_moving) {
      if (phase == kTick - 1) {
        u = self->u_end;
        mix = self->mix_end;
        slope = self->slope_end;
      } else {
        u = u + du;
        mix = mix + dmix;
        slope = slope + dslope;
      }
      wet = DjWet(u, mix);
    }
    const float rg1 = r + g, rg2 = kSqrt2 + g;
    for (int c = 0; c < 2; ++c) {
      DjChannel *k = &ch[c];
      const float x = DjGuard(lr[2 * i + c]);
      if (init1) {                            /* as if running at the open end */
        k->s1 = 0.0f;
        k->s2 = hp_tap ? 0.0f : x;
      }
      const float y1 = DjSvf(x, g, rg1, h1, &k->s1, &k->s2, hp_tap);
      float y = y1;
      if (stage2) {
        if (init2) {
          k->t1 = 0.0f;
          k->t2 = hp_tap ? 0.0f : y1;
        }
        const float y2 = DjSvf(y1, g, rg2, h2, &k->t1, &k->t2, hp_tap);
        const float d2 = y2 - y1;
        const float m2 = slope * d2;
        y = y1 + m2;
      }
      const float d = y - x;
      const float m = wet * d;
      lr[2 * i + c] = x + m;
    }
    init1 = init2 = 0;
  }
  self->g = g;
  self->r = r;
  self->u = u;
  self->mix = mix;
  self->slope = slope;
  self->h1 = h1;
  self->h2 = h2;
  self->wet = wet;
  self->init1 = self->init2 = 0;
}

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t DjInstanceSize(const fm1_host_t *host) {
  (void)host;
  return (sizeof(DjInstance) + 15u) & ~(size_t)15u;
}

/* The one-pole step per tick for a time constant of `seconds`. */
static float DjTickStep(float seconds, float rate) {
  const float frames = (float)kTick;
  const float e = -kLog2e * frames / (seconds * rate);
  return 1.0f - CompExp2(e);
}

static void *DjCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;
  DjInstance *self = (DjInstance *)mem;
  memset(self, 0, sizeof(*self));
  for (int i = 0; i < P_COUNT; ++i) self->param[i] = kDjParams[i].def;
  for (int k = 0; k < G_COUNT; ++k) self->glide[k] = DjTarget(self, k);
  self->sweep_mid = self->glide[G_SWEEP];
  self->k_sweep = DjTickStep(kSweepSeconds, fs);
  self->k_glide = DjTickStep(kGlideSeconds, fs);
  self->slow_step = kEntry * (float)kTick / (kEntrySeconds * fs);
  self->fast_step = (float)kTick / (kTravelSeconds * fs);
  self->lp_open = kLpOpenHz / fs;
  self->hp_open = kHpOpenHz / fs;
  self->g = self->g_end = DjTanPi(self->hp_open);
  self->r = self->r_end = 1.0f / kQ0;
  self->u = self->u_end = 0.0f;
  self->mix = self->mix_end = self->glide[G_MIX];
  self->slope = self->slope_end = self->glide[G_SLOPE];
  self->wet = 0.0f;
  self->side = self->next_side = SIDE_NONE;
  self->phase = 0;
  self->primed = 0;
  DjUpdateH(self);
  return self;
}

static void DjDestroy(void *self) { (void)self; }

static void DjSet(void *s, uint16_t index, float v) {
  DjInstance *self = (DjInstance *)s;
  if (index >= P_COUNT) return;
  self->param[index] = fm1_param_clamp(&kDjParams[index], v);
}

static void DjRender(void *s, float *lr, uint32_t frames) {
  DjInstance *self = (DjInstance *)s;
  /* The states live in locals for the block: lr may alias any float, so
   * working through self would reload them after every store. */
  DjChannel ch[2] = { self->ch[0], self->ch[1] };
  uint32_t f = 0;
  while (f < frames) {
    if (self->phase == 0) DjTick(self);
    uint32_t n = (uint32_t)(kTick - self->phase);
    if (n > frames - f) n = frames - f;
    float *p = lr + 2 * f;
    if (self->side == SIDE_NONE) {
      for (uint32_t i = 0; i < 2 * n; ++i) p[i] = DjGuard(p[i]);
    } else {
      DjRun(self, ch, p, n);
    }
    self->phase += (int)n;
    f += n;
    if (self->phase == kTick) {
      self->phase = 0;
      DjSegmentEnd(self);
    }
  }
  self->ch[0] = ch[0];
  self->ch[1] = ch[1];
}

#ifdef __cplusplus
extern "C" {
#endif

extern const fm1_engine_t fm1_engine_djfilter;
const fm1_engine_t fm1_engine_djfilter = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "djfilter", "DJ Filter",
  "This repository (MIT): a trapezoidal state-variable filter after Andrew "
  "Simper (Cytomic) and Vadim Zavalishin, in the form of stmlib's Svf (Emilie "
  "Gillet, MIT); no code taken",
  kDjParams, P_COUNT, 0,
  DjInstanceSize, DjCreate, DjDestroy,
  NULL, NULL, NULL,
  DjSet, DjRender,
};

#ifdef __cplusplus
}
#endif
