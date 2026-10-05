/* fx_eq_math.h -- 2^x, log2 and tan for EQ (src/fx_eq.cc) without libm,
 * written for this repository. MIT licence.
 *
 * Only IEEE single-precision +, -, *, / and bit moves, each rounded once:
 * floating-point contraction is off wherever this header is included under
 * clang (the pragma below), and GCC's x86 builds have no fused multiply-add
 * to use, so every build that keeps to IEEE single precision computes the
 * same bits (tests/test_engines_eq.py pins a hash of EQ's output). libm's
 * exp2f, logf and tanf differ in their last bits between C libraries, which
 * is what keeps Fold one LSB off the browser's parity under glibc
 * (sim/web/README.md, "Parity").
 *
 * They run at control rate only (set_param, and once per 8 samples while a
 * band glides), never per sample. Accuracy against double precision is in
 * engines/README.md ("EQ") [verified: fm1-eq-test "approx"].
 */
#ifndef FM1_FX_EQ_MATH_H_
#define FM1_FX_EQ_MATH_H_

#include <stdint.h>
#include <string.h>

#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

/* 2^x, x clamped to [-100, 100]; NaN reads as -100. x = n + t with
 * n = floor(x + 1/2), t in [-1/2, 1/2): 2^t = e^(t ln 2) by its Taylor
 * polynomial to degree 7 (truncation under 1e-9 relative), then 2^n from
 * the exponent bits. 2^0 is exactly 1, so 0 dB is a gain of exactly 1. */
static inline float EqExp2(float x) {
  if (!(x > -100.0f)) x = -100.0f;
  if (x > 100.0f) x = 100.0f;
  const float h = x + 0.5f;
  int32_t n = (int32_t)h;                       /* truncates towards zero... */
  if ((float)n > h) n = n - 1;                  /* ...so step down below 0 */
  const float t = x - (float)n;
  const float p = 1.0f + t * (0.693147181f + t * (0.240226507f + t * (0.0555041087f +
                  t * (0.00961812911f + t * (0.00133335581f + t * (0.000154035304f +
                  t * 1.52527338e-05f))))));
  const uint32_t bits = (uint32_t)(n + 127) << 23;   /* n in [-100, 100] */
  float scale;
  memcpy(&scale, &bits, sizeof scale);
  return p * scale;
}

/* log2(x) for normal x > 0 (the callers pass clamped parameters: Hz from
 * 20, Q from 0.3, a sample rate). x = m 2^e with m in (sqrt(1/2), sqrt(2)];
 * log2(m) = (2 / ln 2) atanh(s), s = (m - 1) / (m + 1), |s| <= 0.1716, by
 * its series to s^9 (the next term is under 2e-9). One divide. */
static inline float EqLog2(float x) {
  uint32_t bits;
  memcpy(&bits, &x, sizeof bits);
  int32_t e = (int32_t)((bits >> 23) & 0xFFu) - 127;
  bits = (bits & 0x007FFFFFu) | 0x3F800000u;   /* the mantissa as m in [1, 2) */
  float m;
  memcpy(&m, &bits, sizeof m);
  if (m > 1.41421356f) {
    m = 0.5f * m;
    e = e + 1;
  }
  const float s = (m - 1.0f) / (m + 1.0f);      /* m - 1 is exact here */
  const float s2 = s * s;
  const float a = s * (1.0f + s2 * (0.333333333f + s2 * (0.2f + s2 * (0.142857143f +
                  s2 * 0.111111111f))));
  return (float)e + 2.88539008f * a;            /* 2 / ln 2 */
}

/* tan(w) for 0 <= w <= 1.42 (0.45 pi is 1.4137): sine and cosine by their
 * Taylor series to w^13 and w^14 (truncation under 2e-10 at 1.42), then one
 * divide. */
static inline float EqTan(float w) {
  const float w2 = w * w;
  const float s = w * (1.0f - w2 * (0.166666667f - w2 * (0.00833333333f - w2 * (0.000198412698f -
                  w2 * (2.75573192e-06f - w2 * (2.50521084e-08f - w2 * 1.60590438e-10f))))));
  const float c = 1.0f - w2 * (0.5f - w2 * (0.0416666667f - w2 * (0.00138888889f -
                  w2 * (2.48015873e-05f - w2 * (2.75573192e-07f - w2 * (2.08767570e-09f -
                  w2 * 1.14707456e-11f))))));
  return s / c;
}

#endif /* FM1_FX_EQ_MATH_H_ */
