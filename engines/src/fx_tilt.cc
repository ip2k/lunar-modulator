/* fx_tilt.cc -- "Tilt": a tilt equaliser (FM1_KIND_AUDIO_FX), written for
 * this repository. Notes in engines/README.md ("Tilt"); the design is
 * notes/2026-10-02-delay-reverb-eq-gates-options.md §4.2.
 *
 * One knob turns the whole spectrum about a pivot frequency: to the right
 * the highs rise and the lows fall by the same amount (brighter), to the
 * left the reverse (darker). The pivot itself stays at 0 dB.
 *
 *   Tilt   -9..+9 dB per side: the gain at the top of the spectrum (the
 *          Nyquist frequency); the bottom (DC) gets the opposite. 0 is flat.
 *   Pivot  200 Hz..5 kHz, default 1 kHz: the frequency left at 0 dB.
 *   Curve  Shelf: one first-order section; the tilt turns over within about
 *          two octaves of the pivot and levels into shelves. Slope: two
 *          sections staggered 1.5 octaves either side of the pivot, each
 *          with half the tilt: a gentler, straighter slope (within 0.13 dB
 *          of a straight line from 200 Hz to 5 kHz about a 1 kHz pivot at
 *          +/-9 dB, against 1.1 dB for Shelf). A change glides (5 ms).
 *   Level  -24..+12 dB, the output's gain.
 *
 * One section. With T the section's gain at the top and LP a first-order
 * low-pass,
 *
 *   H = T - (T - 1/T) LP:  1/T at DC, T at Nyquist (LP = 0 there).
 *
 * In the analogue prototype LP = Tw/(s + Tw), w the pivot, so H = T (s +
 * w/T) / (s + T w): a pole at T w and a zero at w/T, symmetric about w on a
 * log axis, and |H(jw)| = 1 exactly (the dB response is odd about the
 * pivot). Discretised by the bilinear transform prewarped at the pivot, the
 * low-pass is a trapezoidal (TPT) one-pole with g = T tan(pi fp / fs), and
 * the digital response at fp is the analogue one at w: exactly 0 dB. So
 * turning Tilt needs no tan at all (g = T g_pivot); only the pivot does,
 * evaluated here by sine and cosine polynomials, never libm.
 *
 * Two sections (Slope). Each has gain sqrt(T); section A's analogue pivot is
 * w / 2^1.5, section B's w 2^1.5. Mapped with the same prewarp at w, their g
 * are sqrt(T) g_pivot / 2^1.5 and sqrt(T) g_pivot 2^1.5, and the pair's
 * response at fp is the prototype's at w: A's gain there and B's are equal
 * and opposite in dB (each is odd about its own pivot, and w sits 1.5
 * octaves above one and below the other), so the pivot is again exactly
 * 0 dB, DC is 1/T and Nyquist T. The stagger of 1.5 octaves is the one that
 * keeps the slope straightest from 200 Hz to 5 kHz about 1 kHz (searched
 * over 0.6 to 2 octaves; tests/test_engines_tilt.py checks the result). Staggered
 * first-order sections are how Faust's fi.spectral_tilt approximates a
 * constant slope [reported]; Airwindows' ToneSlant is a one-knob tilt
 * [reported]. No code is taken from either.
 *
 * Both curves run on the same two sections: Shelf is section A with gain T
 * at the pivot and section B at gain 1, which passes its input unchanged.
 * A change of Curve glides the sections' gains and A's pivot, so it changes
 * cleanly, as Tilt and Pivot do: the one-poles' states are integrator
 * charges, so new coefficients change the filter's future, not what it has
 * stored, and there is nothing to crossfade.
 *
 * Exact bypass. At Tilt 0 both sections have T = 1, so T - 1/T = 0 and each
 * returns its input itself (not 1 x - 0 lp, which could turn -0 into +0);
 * Level 0 dB is a gain of exactly 1. So at the defaults, and at Tilt 0 with
 * any Pivot and Curve, the output is the input bit for bit, for every finite
 * input within the guard. The low-passes keep running underneath, so moving
 * Tilt away from 0 starts from a settled filter.
 *
 * Cost: per sample and channel, the guard, two one-pole updates, two
 * output mixes and the level, about 25 operations and no divide: about
 * 3,200 per 64-frame stereo block. While any control glides, each frame
 * adds the two glide stages of five values and four divides for the
 * coefficients: at most about 6,000 operations and 256 divides per block.
 * Measured on the desktop in engines/README.md.
 *
 * Contracts (fm1_engine.h): no heap, every field set in create (the
 * instance is cleared first), NaN-safe parameters (fm1_param_clamp), finite
 * output. Input guard as the Mutable effects' (mi_fx.cc): NaN reads as 0
 * and anything beyond +/-16 is clamped, so non-finite input cannot reach the
 * state. Silence in gives exact silence out; a tail's states flush to zero
 * below 1e-20 (no subnormals). Controls glide sample by sample, so any
 * block size gives the same output; values set before the first render take
 * effect at once. The glide is two one-poles in series (2.5 ms each, about
 * 5 ms in all), not one: a single one-pole starts moving at full speed, a
 * corner in the control that showed as a kink in the output, its second
 * difference 47 times a steady sine's when Tilt jumps end to end; with two
 * stages it is 1.5 times [verified 2026-10-05, fm1-tilt-test "jumps"].
 *
 * Determinism: no libm. The dB-to-gain conversions are CompExp2
 * (fx_comp_math.h, shared with Comp), the pivot's tan is a ratio of Taylor
 * polynomials, and everything else is +, -, *, / and comparisons, with
 * floating-point contraction off for this file under clang (below), so a
 * build that fuses multiply-adds computes the same bits as WebAssembly.
 *
 * Written in the C subset of C++11 so it would build as C99 unchanged apart
 * from the extern "C" linkage below. MIT licence, like the rest of this
 * repository.
 */

#include "fm1_engine.h"
#include "fx_comp_math.h"

#include <stdint.h>
#include <string.h>

/* No fused multiply-adds in this file (see fx_comp.cc): WebAssembly cannot
 * fuse, so a native build that did would round differently. GCC ignores the
 * pragma; build for a GCC target with FMA with -ffp-contract=off. */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

enum { P_TILT, P_PIVOT, P_CURVE, P_LEVEL, P_COUNT };
enum { CURVE_SHELF, CURVE_SLOPE, CURVE_COUNT };

static const char *const kTiltCurveNames[CURVE_COUNT] = { "Shelf", "Slope" };

/* Uids (API v2) are fixed: never renumber one; a new parameter takes the next
 * free uid. The FLOATs are read every sample: SMOOTH and MOD. Curve changes
 * nothing destructively (it glides) and is not note-bound, so it can be
 * locked and modulated (MOD; a route is rounded). Tilt and Level are in dB
 * (FM1_UNIT_DB, API v3); Pivot moves on the LOG law (fm1_engine.h). */
static const fm1_param_t kTiltParams[P_COUNT] = {
  { "Tilt",  FM1_PARAM_FLOAT, -9, 9, 0.0f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Tilt" },
  { "Pivot", FM1_PARAM_FLOAT, 200, 5000, 1000.0f, NULL, 0, 2, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_HZ, "Pivot" },
  { "Curve", FM1_PARAM_ENUM, 0, CURVE_COUNT - 1, CURVE_SHELF, kTiltCurveNames, 0, 3, FM1_PARAM_MOD, FM1_UNIT_NONE, "Curve" },
  { "Level", FM1_PARAM_FLOAT, -24, 12, 0.0f, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Level" },
};

/* The smoothed control values: the sections' gains at the top, section A's
 * pivot as a multiple of Pivot (B's is fixed at kStagger), tan(pi fp / fs)
 * and the output gain. */
enum { S_TA, S_TB, S_MA, S_GP, S_LEVEL, S_COUNT };

static const float kStagger = 2.82842712474619f;     /* 2^1.5: Slope's sections */
static const float kInvStagger = 0.353553390593274f; /* 2^-1.5 */
static const float kDbToOctaves = 0.166096404744368f; /* log2(10) / 20 */
static const float kLog2e = 1.44269504088896f;
static const float kPi = 3.14159265358979f;
static const float kMaxOfRate = 0.45f;       /* the pivot stays below 0.45 fs */
static const float kStageSeconds = 0.0025f; /* each of the glide's two stages */
static const float kInputLimit = 16.0f;      /* the input guard, as mi_fx.cc */
static const float kFlush = 1e-20f;          /* states below this become 0 */

typedef struct TiltChannel {
  float sa, sb;             /* the two one-poles' states */
} TiltChannel;

typedef struct TiltInstance {
  float param[P_COUNT];     /* knob values, clamped (Curve rounded) */
  float target[S_COUNT];    /* control values the knobs ask for */
  float mid[S_COUNT];       /* the glide's first stage */
  float value[S_COUNT];     /* control values in use (gliding to target) */
  float sample_rate;
  float glide;              /* one-pole coefficient of each glide stage */
  float pivot_top;          /* the highest pivot, kMaxOfRate fs */
  float ta, ka, ga;         /* section A: T, T - 1/T, G = g / (1 + g) */
  float tb, kb, gb;         /* section B */
  int primed;               /* 0 until the first render */
  TiltChannel ch[2];
} TiltInstance;

/* ---------------------------------------------------------------------- */
/* Maths                                                                   */
/* ---------------------------------------------------------------------- */

/* tan(x) for x in [0, 0.45 pi]: sine and cosine by their Taylor polynomials
 * (to x^13 and x^14; the first terms left out are under 2e-10 at 0.45 pi),
 * then one divide. */
static float TiltTan(float x) {
  const float x2 = x * x;
  float s = x2 * (1.0f / 6227020800.0f);
  s = (1.0f / 39916800.0f) - s;
  s = s * x2;
  s = (1.0f / 362880.0f) - s;
  s = s * x2;
  s = (1.0f / 5040.0f) - s;
  s = s * x2;
  s = (1.0f / 120.0f) - s;
  s = s * x2;
  s = (1.0f / 6.0f) - s;
  s = s * x2;
  s = 1.0f - s;
  s = s * x;
  float c = x2 * (1.0f / 87178291200.0f);
  c = (1.0f / 479001600.0f) - c;
  c = c * x2;
  c = (1.0f / 3628800.0f) - c;
  c = c * x2;
  c = (1.0f / 40320.0f) - c;
  c = c * x2;
  c = (1.0f / 720.0f) - c;
  c = c * x2;
  c = (1.0f / 24.0f) - c;
  c = c * x2;
  c = 0.5f - c;
  c = c * x2;
  c = 1.0f - c;
  return s / c;
}

static inline float TiltDbToGain(float db) { return CompExp2(db * kDbToOctaves); }

static inline float TiltGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

static inline float TiltAbs(float v) { return v < 0.0f ? -v : v; }

static inline float TiltFlush(float v) {
  return (v > -kFlush && v < kFlush) ? 0.0f : v;
}

/* One step of one glide stage. It lands on the target when within 1e-6 of
 * it (relative), or when its step is under about half an ulp of the value,
 * where a float one-pole would stall short of the target for ever; a larger
 * step always moves the value. So the glide always ends exactly on the
 * target (Tilt back at 0 is exactly T = 1 again), and the test is on
 * magnitudes, not on whether a sum rounded back to the value, so it holds
 * with excess precision too (i386's x87 [verified 2026-10-05]). The snap is
 * kept small on purpose: at 1e-4 (Fold's), a target moved every 32 frames
 * (the matrix's rate) snapped near the turns of a sweep, and those steps
 * were zipper noise: energy above 1 kHz at -92 dB against -120 dB at 1e-6,
 * for Tilt swept end to end at 1 Hz over a 100 Hz sine [verified
 * 2026-10-05]. */
static inline float TiltGlide(float v, float t, float k) {
  const float e = t - v;
  const float step = k * e;
  if (TiltAbs(e) <= 1e-6f * (1.0f + TiltAbs(t)) || TiltAbs(step) <= 6e-8f * TiltAbs(v)) return t;
  return v + step;
}

/* ---------------------------------------------------------------------- */
/* Controls                                                                */
/* ---------------------------------------------------------------------- */

static void TiltSetTarget(TiltInstance *self, int index) {
  switch (index) {
    case P_TILT:
    case P_CURVE: {
      const float db = self->param[P_TILT];
      if ((int)self->param[P_CURVE] == CURVE_SLOPE) {
        const float half = TiltDbToGain(0.5f * db);
        self->target[S_TA] = half;
        self->target[S_TB] = half;
        self->target[S_MA] = kInvStagger;
      } else {
        self->target[S_TA] = TiltDbToGain(db);
        self->target[S_TB] = 1.0f;
        self->target[S_MA] = 1.0f;
      }
      break;
    }
    case P_PIVOT: {
      float hz = self->param[P_PIVOT];
      if (hz > self->pivot_top) hz = self->pivot_top;
      self->target[S_GP] = TiltTan(kPi * hz / self->sample_rate);
      break;
    }
    case P_LEVEL: self->target[S_LEVEL] = TiltDbToGain(self->param[P_LEVEL]); break;
    default: break;
  }
}

/* The sections' coefficients from the values in use. */
static void TiltUpdateCoefs(TiltInstance *self) {
  const float ta = self->value[S_TA], tb = self->value[S_TB], gp = self->value[S_GP];
  const float ga = ta * gp * self->value[S_MA];
  const float gb = tb * gp * kStagger;
  self->ta = ta;
  self->ka = ta - 1.0f / ta;
  self->ga = ga / (1.0f + ga);
  self->tb = tb;
  self->kb = tb - 1.0f / tb;
  self->gb = gb / (1.0f + gb);
}

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t TiltInstanceSize(const fm1_host_t *host) {
  (void)host;
  return (sizeof(TiltInstance) + 15u) & ~(size_t)15u;
}

static void *TiltCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;
  TiltInstance *self = (TiltInstance *)mem;
  memset(self, 0, sizeof(*self));
  self->sample_rate = fs;
  self->glide = 1.0f - CompExp2(-kLog2e / (kStageSeconds * fs));
  self->pivot_top = kMaxOfRate * fs;
  for (int i = 0; i < P_COUNT; ++i) {
    self->param[i] = kTiltParams[i].def;
    TiltSetTarget(self, i);
  }
  for (int s = 0; s < S_COUNT; ++s) self->mid[s] = self->value[s] = self->target[s];
  TiltUpdateCoefs(self);
  self->primed = 0;
  return self;
}

static void TiltDestroy(void *self) { (void)self; }

static void TiltSet(void *s, uint16_t index, float v) {
  TiltInstance *self = (TiltInstance *)s;
  if (index >= P_COUNT) return;
  v = fm1_param_clamp(&kTiltParams[index], v);
  if (kTiltParams[index].type == FM1_PARAM_ENUM) v = (float)(int)(v + 0.5f);  /* v >= 0 */
  self->param[index] = v;
  TiltSetTarget(self, index);
}

static void TiltRender(void *s, float *lr, uint32_t frames) {
  TiltInstance *self = (TiltInstance *)s;
  if (!self->primed) {
    /* Settings made before the first block apply from its first sample. */
    for (int k = 0; k < S_COUNT; ++k) self->mid[k] = self->value[k] = self->target[k];
    TiltUpdateCoefs(self);
    self->primed = 1;
  }
  /* The states live in locals for the block: lr may alias any float, so
   * working through self would reload them after every store. */
  TiltChannel ch[2] = { self->ch[0], self->ch[1] };
  const float glide = self->glide;
  for (uint32_t f = 0; f < frames; ++f) {
    int gliding = 0;
    for (int k = 0; k < S_COUNT; ++k) {
      if (self->value[k] != self->target[k] || self->mid[k] != self->target[k]) {
        self->mid[k] = TiltGlide(self->mid[k], self->target[k], glide);
        self->value[k] = TiltGlide(self->value[k], self->mid[k], glide);
        gliding = 1;
      }
    }
    if (gliding) TiltUpdateCoefs(self);
    const float ta = self->ta, ka = self->ka, ga = self->ga;
    const float tb = self->tb, kb = self->kb, gb = self->gb;
    const float level = self->value[S_LEVEL];
    for (int c = 0; c < 2; ++c) {
      TiltChannel *h = &ch[c];
      const float x = TiltGuard(lr[2 * f + c]);
      float v = (x - h->sa) * ga;                      /* section A */
      float lp = v + h->sa;
      h->sa = TiltFlush(lp + v);
      const float y = ka != 0.0f ? ta * x - ka * lp : x;
      v = (y - h->sb) * gb;                            /* section B */
      lp = v + h->sb;
      h->sb = TiltFlush(lp + v);
      const float z = kb != 0.0f ? tb * y - kb * lp : y;
      lr[2 * f + c] = level * z;
    }
  }
  self->ch[0] = ch[0];
  self->ch[1] = ch[1];
}

#ifdef __cplusplus
extern "C" {
#endif

extern const fm1_engine_t fm1_engine_tilt;
const fm1_engine_t fm1_engine_tilt = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "tilt", "Tilt",
  "This repository (MIT): a tilt equaliser of first-order sections, bilinear "
  "and prewarped at the pivot; the idea after Airwindows ToneSlant (MIT) and "
  "Faust's spectral_tilt (STK-4.3), no code taken",
  kTiltParams, P_COUNT, 0,
  TiltInstanceSize, TiltCreate, TiltDestroy,
  NULL, NULL, NULL,
  TiltSet, TiltRender,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
  NULL,                     // API v4: no get_param, the host keeps its values
};

#ifdef __cplusplus
}
#endif
