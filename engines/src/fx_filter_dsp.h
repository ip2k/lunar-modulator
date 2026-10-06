/* fx_filter_dsp.h -- the arithmetic Filter (fx_filter.cc) and Comb
 * (fx_comb.cc) share: libm-free 2^x and log2, the saturating curve, the
 * input guard, the denormal flush and the glide, with the constants of the
 * control rate. Moved out of fx_filter.cc unchanged when Comb became its own
 * effect (2026-10-05), so both compute what the one file computed, bit for
 * bit [verified: the renders pinned in tests/fixtures/comb-split.json].
 *
 * Only fabsf and floorf from <math.h> (IEEE 754 defines both exactly); no
 * fused multiply-adds (the pragma below; GCC ignores it, so a GCC target
 * with FMA builds with -ffp-contract=off, as docs/14 says). Written in the C
 * subset of C++11. MIT licence, like the rest of this repository.
 */
#ifndef FM1_FX_FILTER_DSP_H_
#define FM1_FX_FILTER_DSP_H_

#include <math.h>
#include <stdint.h>
#include <string.h>

#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

/* The per-type processors run once or twice per frame; inlined, their
 * states stay in registers. */
#if defined(__GNUC__) || defined(__clang__)
#define FILT_INLINE static inline __attribute__((always_inline))
#else
#define FILT_INLINE static inline
#endif

static const uint32_t kCtrlMask = 7u;       /* a control step every 8 samples */
static const float kCtrlSamples = 8.0f;
static const float kSmoothSeconds = 0.005f; /* glide time constant */
static const float kInputLimit = 16.0f;     /* the input guard, as mi_fx.cc */
static const float kFlush = 1e-15f;         /* states below this become 0 */
static const float kMaxOfRate = 0.45f;      /* nothing tuned above 0.45 fs */

/* 2^x, x clamped to +/-100: 2^round(x) from the exponent bits, the rest by
 * a degree-6 Taylor series of 2^t, |t| <= 0.5 (relative error 1.2e-7). */
static inline float FiltExp2(float x) {
  if (!(x > -100.0f)) x = -100.0f;
  if (x > 100.0f) x = 100.0f;
  const float n = floorf(x + 0.5f);
  const float t = x - n;
  const float p = 1.0f + t * (0.693147181f + t * (0.240226507f + t * (0.0555041087f +
                  t * (0.00961812911f + t * (0.00133335581f + t * 0.000154035304f)))));
  const uint32_t bits = (uint32_t)((int32_t)n + 127) << 23;
  float scale;
  memcpy(&scale, &bits, sizeof(scale));
  return p * scale;
}

/* log2(x) for finite x > 0 (normal): the exponent, and atanh's series for
 * the mantissa taken to [0.707, 1.414] (error below 1e-7). */
static inline float FiltLog2(float x) {
  uint32_t bits;
  memcpy(&bits, &x, sizeof(bits));
  int32_t e = (int32_t)((bits >> 23) & 0xFFu) - 127;
  bits = (bits & 0x007FFFFFu) | 0x3F800000u;
  float m;
  memcpy(&m, &bits, sizeof(m));
  if (m > 1.41421356f) { m *= 0.5f; e += 1; }
  const float t = (m - 1.0f) / (m + 1.0f);
  const float t2 = t * t;
  const float a = t * (1.0f + t2 * (0.333333333f + t2 * (0.2f + t2 * 0.142857143f)));
  return (float)e + 2.88539008f * a;      /* 2 / ln 2 */
}

/* The saturating curve: v - v^3 / 6.75 up to |v| = 1.5, where it reaches
 * +/-1 with zero slope, flat beyond. Also returns its secant gain (curve /
 * v), which the next sample's loop solve uses; no divide below the knee. */
FILT_INLINE float FiltSat(float v, float *secant) {
  const float a = fabsf(v);
  if (a < 1.5f) {
    const float s = 1.0f - v * v * 0.148148148f;
    *secant = s;
    return v * s;
  }
  *secant = 1.0f / a;
  return v > 0.0f ? 1.0f : -1.0f;
}

static inline float FiltFlush(float v) {
  return fabsf(v) < kFlush ? 0.0f : v;
}

static inline float FiltGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

/* One step of a glide; snaps when within 1e-4 (relative), so a value
 * reaches its target exactly instead of stalling an ulp short of it. */
static inline float FiltGlide(float v, float t, float k) {
  const float e = t - v;
  if (fabsf(e) <= 1e-4f * (1.0f + fabsf(t))) return t;
  return v + k * e;
}

/* The input with Drive's soft clip blended in. */
FILT_INLINE float FiltPresat(float x, float drv) {
  float s;
  return x + drv * (FiltSat(x, &s) - x);
}

/* Drive's gains: into the filter 1x..16x (2^(4 Drive), halved), out of it
 * the square root of that, inverted (twice 2^(-2 Drive)). */
static inline float FiltDriveIn(float drive) { return 0.5f * FiltExp2(4.0f * drive); }
static inline float FiltDriveOut(float drive) { return 2.0f * FiltExp2(-2.0f * drive); }

#endif /* FM1_FX_FILTER_DSP_H_ */
