/* fx_fold.cc -- "Fold": a wavefolder audio effect (FM1_KIND_AUDIO_FX),
 * written for this repository. Notes in engines/README.md ("Fold").
 *
 * Signal path, per channel and per sample:
 *
 *   input guard -> u = gain * x + offset -> fold (triangle/sine blend, with
 *   first-order antiderivative anti-aliasing) -> minus the fold of silence
 *   -> DC blocker (10 Hz) -> tone low-pass (12 dB/oct) -> level -> mix
 *
 *   Fold      pre-gain into the folder, 1x to 16x (2^(4 * Fold)).
 *   Symmetry  a DC offset added before folding, -1..+1 in units of the
 *             folder's input (a fold point sits at +/-1): away from 0 the
 *             folds become uneven and even harmonics appear.
 *   Shape     0 folds with a triangle (straight segments, sharp corners: a
 *             bright, buzzy fold), 1 with a sine (rounded corners: softer);
 *             in between a blend of the two.
 *   Mix       dry to wet. At 0 the (guarded) input passes through unchanged.
 *   Tone      a Butterworth low-pass on the wet signal, 200 Hz to 19.4 kHz.
 *   Level     the wet signal's gain, 0..1.
 *
 * Both fold curves have period 4 and peaks of +/-1 at u = +/-1: the triangle
 * is the identity on [-1, 1] and folds back beyond it, the sine is
 * sin(pi u / 2). Folding is how the Serge and Buchla wavefolders shape a
 * signal; Mutable Instruments' Warps (cross-folding) and Plaits (its
 * waveshaping engine's wavefolder) do it digitally. This file takes no code
 * from any of them.
 *
 * Aliasing. A folder makes harmonics far above Nyquist, which a plain
 * per-sample fold reflects back into the audio band. We use first-order
 * antiderivative anti-aliasing (ADAA; Parker, Zavalishin and Le Bivic,
 * DAFx-16, 2016; applied to the Serge and Lockhart folders by Esqueda,
 * Pontynen, Parker and Bilbao, 2017): each output is the mean of the curve
 * over the segment from the previous input to this one,
 *   y[n] = (F(u[n]) - F(u[n-1])) / (u[n] - u[n-1]),  F' = f,
 * rather than f(u[n]). It costs a half-sample delay and a gentle top-end
 * roll-off on the wet path (cos(pi f / fs) on unfolded signals: -0.6 dB at
 * 5 kHz, -3 dB at 11 kHz at 44,118 Hz), no extra state beyond u[n-1], and
 * no oversampling. Measured on the renderer's 440 Hz sine, aliases below
 * 5 kHz sit 21-23 dB lower than a plain fold's (tests/test_engines_fold.py).
 * The textbook form divides a difference of two nearly equal F values by a
 * small step, which loses precision in float; both curves here are
 * evaluated without that cancellation:
 *   - the sine's mean has a closed form,
 *       sin(pi m / 2) * sinc(pi d / 4),  m = midpoint, d = step,
 *     exact for any step;
 *   - the triangle's mean is computed piecewise for steps under 0.5 (at
 *     most one corner can lie inside: the exact mean of |x| over an
 *     interval), and from F only for larger steps, where the division is
 *     well conditioned.
 * So there is no epsilon and no fallback to the naive fold.
 *
 * Cost, per sample and channel: the midpoint sine (a range reduction and a
 * degree-10 even polynomial, five multiply-adds) and the triangle (one
 * floor); for steps of 0.5 or more also two triangle antiderivatives, a
 * second sine for the sinc and one divide (a step under 0.5 that straddles
 * a corner divides instead); then the DC blocker, the filter and the mix.
 * About 65 operations for small steps and 80 for large ones, never more than
 * one divide: at most about 10,000 operations and 128 divides per 64-frame
 * stereo block, plus six comparisons per frame for the parameter glides.
 * One stream of the native-rate resampler costs about 114 multiply-adds per
 * output sample (resampler.md), so Fold costs about as much as 1.4 of them.
 * On the desktop (Apple M1 Max, noise in) a block takes about 1.8 us, 0.12 %
 * of the 1.451 ms block, against 0.06 % for Plate. 2x oversampling with
 * short half-band filters would cost about as much and, for a fold whose
 * harmonics fall as 1/k^2, lower the aliases by roughly 9 dB [inferred].
 *
 * Contracts (fm1_engine.h): no heap, every field set in create, NaN-safe
 * parameters (fm1_param_clamp), finite output. Input guard as the Mutable
 * effects' (mi_fx.cc): NaN reads as 0 and anything beyond +/-16 is clamped,
 * so non-finite input cannot reach the state. Silence in gives exact silence
 * out at any setting. Parameters glide (one pole, 5 ms) sample by sample, so
 * any block size gives the same output; values set before the first render
 * take effect at once. Filter states below 1e-20 flush to zero (no subnormals in
 * long tails).
 *
 * Written in the C subset of C++11 so it would build as C99 unchanged apart
 * from the extern "C" linkage below. MIT licence, like the rest of this
 * repository.
 */

#include "fm1_engine.h"

#include <math.h>
#include <string.h>

/* The fold runs twice per frame; left to itself the compiler calls it, which
 * spills the filter states around each call (desktop: about a quarter
 * slower). */
#if defined(__GNUC__) || defined(__clang__)
#define FOLD_INLINE static inline __attribute__((always_inline))
#else
#define FOLD_INLINE static inline
#endif

enum { P_FOLD, P_SYMMETRY, P_SHAPE, P_MIX, P_TONE, P_LEVEL, P_COUNT };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every parameter is read each block: SMOOTH and MOD.
static const fm1_param_t kFoldParams[P_COUNT] = {
  { "Fold",     FM1_PARAM_FLOAT,  0, 1, 0.4f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Fold" },
  { "Symmetry", FM1_PARAM_FLOAT, -1, 1, 0.0f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Sym" },
  { "Shape",    FM1_PARAM_FLOAT,  0, 1, 0.0f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Shape" },
  { "Mix",      FM1_PARAM_FLOAT,  0, 1, 1.0f, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Tone",     FM1_PARAM_FLOAT,  0, 1, 0.8f, NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Tone" },
  { "Level",    FM1_PARAM_FLOAT,  0, 1, 0.7f, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Level" },
};

/* The smoothed control values. */
enum { S_GAIN, S_OFFSET, S_SHAPE, S_MIX, S_LEVEL, S_G, S_COUNT };

static const float kFoldOctaves = 4.0f;     /* Fold 1 = gain 2^4 = 16 */
static const float kToneLowHz = 200.0f;     /* Tone 0 */
static const float kToneOctaves = 6.6f;     /* Tone 1 = 200 * 2^6.6 = 19.4 kHz */
static const float kToneMaxOfRate = 0.45f;  /* cutoff never above 0.45 fs */
static const float kDcHz = 10.0f;           /* DC blocker corner */
static const float kSmoothSeconds = 0.005f; /* parameter glide time constant */
static const float kInputLimit = 16.0f;     /* the input guard, as mi_fx.cc */
static const float kFlush = 1e-20f;         /* states below this become 0 */
static const float kWideStep = 0.5f;        /* ADAA: from here F differences */
static const float kPi = 3.14159265358979f;
static const float kSqrt2 = 1.41421356237310f;

typedef struct FoldChannel {
  float u0;                 /* the folder's previous input */
  float dc_x1, dc_y1;       /* DC blocker */
  float ic1, ic2;           /* low-pass integrator states (TPT SVF) */
} FoldChannel;

typedef struct FoldInstance {
  float param[P_COUNT];     /* knob values, clamped */
  float target[S_COUNT];    /* control values the knobs ask for */
  float value[S_COUNT];     /* control values in use (gliding to target) */
  float sample_rate;
  float glide;              /* one-pole coefficient of the glide */
  float dc_r;               /* DC blocker pole */
  float dc0;                /* the fold of silence at value[S_OFFSET, S_SHAPE] */
  float dc0_offset, dc0_shape;
  float coef_g, a1, a2, a3; /* low-pass coefficients for coef_g */
  int primed;               /* 0 until the first render */
  FoldChannel ch[2];
} FoldInstance;

/* ---------------------------------------------------------------------- */
/* The curves                                                              */
/* ---------------------------------------------------------------------- */

/* cos(pi v / 2) for any finite v: reduce to [-2, 2), fold to [0, 1], and a
 * Taylor polynomial in r^2 to r^10 (truncation 4.7e-7 at r = 1). */
static inline float FoldCos4(float v) {
  const float k = floorf((v + 2.0f) * 0.25f);
  float a = fabsf(v - 4.0f * k);        /* exact: 4k is a multiple of ulp(v) */
  float sign = 1.0f;
  if (a > 1.0f) {                       /* cos(pi s / 2) = -cos(pi (2 - s) / 2) */
    a = 2.0f - a;
    sign = -1.0f;
  }
  const float r2 = a * a;
  const float c = 1.0f + r2 * (-1.23370055f + r2 * (0.253669508f + r2 * (-0.0208634808f +
                  r2 * (0.000919260275f + r2 * -2.52020424e-05f))));
  return sign * c;
}

/* sin(pi d / 4) / (pi d / 4), with inv_d = 1 / d when |d| >= kWideStep. */
static inline float FoldSinc4(float d, float inv_d) {
  if (fabsf(d) < kWideStep) {           /* h < 0.393: series, error < 2e-9 */
    const float h = 0.785398163f * d;
    const float h2 = h * h;
    return 1.0f - h2 * (0.166666667f - h2 * (0.00833333333f - h2 * 0.000198412698f));
  }
  return FoldCos4(0.5f * d - 1.0f) * 1.27323954f * inv_d;   /* sin(h) / h */
}

/* The triangle fold: s = u reduced so that f(u) = 1 - |s|, s in [-2, 2).
 * Its corners: s = 0 (peak, +1, u = 1 mod 4) and s = +/-2 (trough, -1). */
static inline float FoldTriS(float u) {
  const float k = floorf((u + 1.0f) * 0.25f);
  return (u - 4.0f * k) - 1.0f;
}

/* The triangle's antiderivative, periodic and continuous: s - s|s| / 2. */
static inline float FoldTriF(float u) {
  const float s = FoldTriS(u);
  return s - 0.5f * s * fabsf(s);
}

/* The mean of |x| over [a, b] (either order), without cancellation. */
static inline float FoldAbsMean(float a, float b) {
  if (a * b >= 0.0f) return 0.5f * fabsf(a + b);
  return (a * a + b * b) / (2.0f * (fabsf(a) + fabsf(b)));
}

/* The anti-aliased fold: the mean of the blended curve over [u0, u1]. With
 * u0 == u1 it is the curve itself at that point, exactly. */
FOLD_INLINE float FoldAdaa(float u0, float u1, float shape) {
  const float d = u1 - u0;
  const float m = 0.5f * (u0 + u1);
  const int wide = !(fabsf(d) < kWideStep);
  const float inv_d = wide ? 1.0f / d : 0.0f;

  float tri;
  if (wide) {
    tri = (FoldTriF(u1) - FoldTriF(u0)) * inv_d;
  } else {
    /* At most one corner within [m - h, m + h]. */
    const float s = FoldTriS(m);
    const float h = 0.5f * d;
    if (fabsf(s) <= 1.0f) {
      tri = 1.0f - FoldAbsMean(s - h, s + h);        /* near a peak */
    } else {
      const float q = s - (s > 0.0f ? 2.0f : -2.0f); /* near a trough */
      tri = FoldAbsMean(q - h, q + h) - 1.0f;
    }
  }
  const float sine = FoldCos4(m - 1.0f) * FoldSinc4(d, inv_d);   /* sin(pi m / 2) */
  return tri + shape * (sine - tri);
}

/* ---------------------------------------------------------------------- */
/* Controls                                                                */
/* ---------------------------------------------------------------------- */

static inline float FoldGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

static inline float FoldFlush(float v) {
  return fabsf(v) < kFlush ? 0.0f : v;
}

/* One step of the glide; snaps when within 1e-4 (relative), so a value
 * reaches its target exactly instead of stalling an ulp short of it. */
static inline float FoldGlide(float v, float t, float k) {
  const float e = t - v;
  if (fabsf(e) <= 1e-4f * (1.0f + fabsf(t))) return t;
  return v + k * e;
}

static void FoldSetTarget(FoldInstance *self, int index) {
  const float v = self->param[index];
  switch (index) {
    case P_FOLD: self->target[S_GAIN] = exp2f(kFoldOctaves * v); break;
    case P_SYMMETRY: self->target[S_OFFSET] = v; break;
    case P_SHAPE: self->target[S_SHAPE] = v; break;
    case P_MIX: self->target[S_MIX] = v; break;
    case P_LEVEL: self->target[S_LEVEL] = v; break;
    case P_TONE: {
      float hz = kToneLowHz * exp2f(kToneOctaves * v);
      const float top = kToneMaxOfRate * self->sample_rate;
      if (hz > top) hz = top;
      self->target[S_G] = tanf(kPi * hz / self->sample_rate);
      break;
    }
    default: break;
  }
}

static void FoldUpdateDc0(FoldInstance *self) {
  self->dc0_offset = self->value[S_OFFSET];
  self->dc0_shape = self->value[S_SHAPE];
  /* The same function, on the same values, as the per-sample path sees for
   * silence: the difference is exactly zero. */
  self->dc0 = FoldAdaa(self->dc0_offset, self->dc0_offset, self->dc0_shape);
}

static void FoldUpdateFilter(FoldInstance *self) {
  /* Zavalishin's TPT state-variable filter, Q = 1/sqrt(2) (k = sqrt(2)). */
  const float g = self->value[S_G];
  self->coef_g = g;
  self->a1 = 1.0f / (1.0f + g * (g + kSqrt2));
  self->a2 = g * self->a1;
  self->a3 = g * self->a2;
}

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t FoldInstanceSize(const fm1_host_t *host) {
  (void)host;
  return (sizeof(FoldInstance) + 15u) & ~(size_t)15u;
}

static void *FoldCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;
  FoldInstance *self = (FoldInstance *)mem;
  memset(self, 0, sizeof(*self));
  self->sample_rate = fs;
  self->glide = 1.0f - expf(-1.0f / (kSmoothSeconds * fs));
  self->dc_r = expf(-2.0f * kPi * kDcHz / fs);
  for (int i = 0; i < P_COUNT; ++i) {
    self->param[i] = kFoldParams[i].def;
    FoldSetTarget(self, i);
  }
  for (int s = 0; s < S_COUNT; ++s) self->value[s] = self->target[s];
  FoldUpdateDc0(self);
  FoldUpdateFilter(self);
  for (int c = 0; c < 2; ++c) self->ch[c].u0 = self->value[S_OFFSET];
  self->primed = 0;
  return self;
}

static void FoldDestroy(void *self) { (void)self; }

static void FoldSet(void *s, uint16_t index, float v) {
  FoldInstance *self = (FoldInstance *)s;
  if (index >= P_COUNT) return;
  self->param[index] = fm1_param_clamp(&kFoldParams[index], v);
  FoldSetTarget(self, index);
}

static void FoldRender(void *s, float *lr, uint32_t frames) {
  FoldInstance *self = (FoldInstance *)s;
  if (!self->primed) {
    /* Settings made before the first block apply from its first sample. */
    for (int k = 0; k < S_COUNT; ++k) self->value[k] = self->target[k];
    FoldUpdateDc0(self);
    FoldUpdateFilter(self);
    for (int c = 0; c < 2; ++c) self->ch[c].u0 = self->value[S_OFFSET];
    self->primed = 1;
  }
  /* The per-channel state lives in locals for the block: lr may alias any
   * float, so working through self would reload it after every store. */
  FoldChannel ch[2] = { self->ch[0], self->ch[1] };
  const float glide = self->glide, dc_r = self->dc_r;
  for (uint32_t f = 0; f < frames; ++f) {
    int gliding = 0;
    for (int k = 0; k < S_COUNT; ++k) {
      if (self->value[k] != self->target[k]) {
        self->value[k] = FoldGlide(self->value[k], self->target[k], glide);
        gliding = 1;
      }
    }
    if (gliding) {
      if (self->value[S_OFFSET] != self->dc0_offset || self->value[S_SHAPE] != self->dc0_shape) {
        FoldUpdateDc0(self);
      }
      if (self->value[S_G] != self->coef_g) FoldUpdateFilter(self);
    }
    const float gain = self->value[S_GAIN], offset = self->value[S_OFFSET];
    const float shape = self->value[S_SHAPE], mix = self->value[S_MIX];
    const float level = self->value[S_LEVEL], dc0 = self->dc0;
    const float a1 = self->a1, a2 = self->a2, a3 = self->a3;
    for (int c = 0; c < 2; ++c) {
      FoldChannel *h = &ch[c];
      const float x = FoldGuard(lr[2 * f + c]);
      const float u1 = gain * x + offset;
      const float w = FoldAdaa(h->u0, u1, shape) - dc0;
      h->u0 = u1;
      const float y = w - h->dc_x1 + dc_r * h->dc_y1;      /* DC blocker */
      h->dc_x1 = w;
      h->dc_y1 = FoldFlush(y);
      const float v3 = y - h->ic2;                           /* low-pass */
      const float v1 = a1 * h->ic1 + a2 * v3;
      const float v2 = h->ic2 + a2 * h->ic1 + a3 * v3;
      h->ic1 = FoldFlush(2.0f * v1 - h->ic1);
      h->ic2 = FoldFlush(2.0f * v2 - h->ic2);
      lr[2 * f + c] = x + mix * (level * v2 - x);
    }
  }
  self->ch[0] = ch[0];
  self->ch[1] = ch[1];
}

#ifdef __cplusplus
extern "C" {
#endif

extern const fm1_engine_t fm1_engine_fold;
const fm1_engine_t fm1_engine_fold = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "fold", "Fold",
  "This repository (MIT): a wavefolder after the Serge and Buchla folders and "
  "the folding in Mutable Instruments Warps and Plaits (Emilie Gillet), no code "
  "taken; anti-aliasing after Parker, Zavalishin and Le Bivic (DAFx-16)",
  kFoldParams, P_COUNT, 0,
  FoldInstanceSize, FoldCreate, FoldDestroy,
  NULL, NULL, NULL,
  FoldSet, FoldRender,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
};

#ifdef __cplusplus
}
#endif
