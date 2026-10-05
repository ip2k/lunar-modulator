/* fx_comp_math.h -- base-2 logarithm and exponential for Comp
 * (src/fx_comp.cc) without libm, written for this repository. MIT licence.
 *
 * Both use only IEEE single-precision +, -, * and / and bit moves, each
 * rounded once (every product is its own statement, so a compiler that
 * contracts within expressions has nothing to fuse; see also the
 * FP_CONTRACT pragma in fx_comp.cc), so builds compute the same bits
 * [verified for Comp's output: Apple clang arm64, GCC i386 and x86-64,
 * Emscripten WebAssembly; pi32v2 compiled, not run].
 * libm's logf and exp2f differ in their last bits between C libraries, which
 * is what keeps Sophie out of the browser's bit-exact parity
 * (sim/web/README.md, "Parity").
 *
 * Accuracy, against double precision [verified: tests/test_engines_comp.py,
 * fm1-comp-test "approx", 2026-10-02]:
 *   CompLog2  within 2.1 ulp of its result for x from 2^-66 to 2^13, and
 *             1.9e-7 absolute on [1/16, 16]: 6e-7 dB in a level near
 *             0 dBFS, 1.2e-5 dB at -200 dB (3.01 dB per unit of power);
 *   CompExp2  relative error 2.4e-7 (2 ulp) on (-126, 126].
 */
#ifndef FM1_FX_COMP_MATH_H_
#define FM1_FX_COMP_MATH_H_

#include <stdint.h>
#include <string.h>

/* log2(x) for normal x > 0; the caller floors x (zero, subnormal, negative
 * and NaN inputs are not handled). x = m 2^e with m reduced to
 * [sqrt(1/2), sqrt(2)); then log2(m) = (2 / ln 2) atanh(t), t = (m - 1) /
 * (m + 1), |t| <= 0.1716, by its series to t^7 (the next term, t^9 / 9 x
 * 2.885, is under 5e-8). One divide. */
static inline float CompLog2(float x) {
  uint32_t bits;
  memcpy(&bits, &x, sizeof bits);
  int e = (int)((bits >> 23) & 0xFFu) - 127;
  bits = (bits & 0x007FFFFFu) | 0x3F800000u;   /* the mantissa as m in [1, 2) */
  float m;
  memcpy(&m, &bits, sizeof m);
  if (m > 1.41421356f) {                        /* to (sqrt(1/2), sqrt(2)] */
    m = 0.5f * m;
    e = e + 1;
  }
  const float t = (m - 1.0f) / (m + 1.0f);      /* m - 1 is exact here */
  const float t2 = t * t;
  float s = 0.412198583f * t2;                  /* 2 / (7 ln 2) */
  s = s + 0.577078016f;                         /* 2 / (5 ln 2) */
  s = s * t2;
  s = s + 0.961796694f;                         /* 2 / (3 ln 2) */
  s = s * t2;
  s = s + 2.88539008f;                          /* 2 / ln 2 */
  s = s * t;
  return (float)e + s;
}

/* 2^x. Below -126 it is 0 and above 126 it saturates at 2^126 (no
 * subnormals, no infinity); NaN gives 0. x = n + f, n = floor(x + 1/2),
 * f in [-1/2, 1/2): 2^f = e^(f ln 2) by its Taylor polynomial to degree 6
 * (truncation under 1.2e-7 relative), then the exponent n set directly. */
static inline float CompExp2(float x) {
  if (!(x > -126.0f)) return 0.0f;              /* NaN fails too */
  if (x > 126.0f) x = 126.0f;
  const float h = x + 0.5f;
  int n = (int)h;                               /* truncates towards zero... */
  if ((float)n > h) n = n - 1;                  /* ...so step down for h < 0 */
  const float u = (x - (float)n) * 0.693147181f;
  float p = 0.00138888889f * u;                 /* 1/720 */
  p = p + 0.00833333333f;                       /* 1/120 */
  p = p * u;
  p = p + 0.0416666667f;                        /* 1/24 */
  p = p * u;
  p = p + 0.166666667f;                         /* 1/6 */
  p = p * u;
  p = p + 0.5f;
  p = p * u;
  p = p + 1.0f;
  p = p * u;
  p = p + 1.0f;
  const uint32_t bits = (uint32_t)(n + 127) << 23;   /* n in [-126, 126] */
  float scale;
  memcpy(&scale, &bits, sizeof scale);
  return p * scale;
}

#endif /* FM1_FX_COMP_MATH_H_ */
