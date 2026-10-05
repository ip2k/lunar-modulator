/* fm1_math.h -- base-2 logarithm and exponential without libm, shared by
 * the hosts (the LOG parameter law, fm1_engine.h) and the effects (Comp's
 * levels, src/fx_comp_math.h). Written for this repository; MIT licence.
 *
 * Both use only IEEE single-precision +, -, * and / and bit moves, each
 * rounded once: every product is its own statement, so a compiler that
 * contracts only within an expression (clang's default) has nothing to fuse,
 * and the builds here that could fuse across statements (GCC in a GNU mode
 * on a target with FMA) are ISO C99 / C++11, where GCC does not. So every
 * build computes the same bits [verified for Comp's output, which has used
 * this code since 2026-10-02: Apple clang arm64, GCC i386 and x86-64,
 * Emscripten WebAssembly; pi32v2 compiled, not run]. libm's logf and exp2f
 * differ in their last bits between C libraries, which is what keeps Sophie
 * out of the browser's bit-exact parity (sim/web/README.md, "Parity").
 *
 * Accuracy, against double precision [verified: tests/test_engines_comp.py,
 * fm1-comp-test "approx", 2026-10-02, as CompLog2 and CompExp2]:
 *   fm1_log2f  within 2.1 ulp of its result for x from 2^-66 to 2^13, and
 *              1.9e-7 absolute on [1/16, 16];
 *   fm1_exp2f  relative error 2.4e-7 (2 ulp) on (-126, 126]; exact at
 *              every integer in that range (2^n, n whole, is a power of two
 *              times p = 1).
 *
 * Plain C99 (and the C subset of C++11); static inline, no state.
 */
#ifndef FM1_MATH_H_
#define FM1_MATH_H_

#include <stdint.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/* log2(x) for normal x > 0; the caller floors x (zero, subnormal, negative
 * and NaN inputs are not handled). x = m 2^e with m reduced to
 * [sqrt(1/2), sqrt(2)); then log2(m) = (2 / ln 2) atanh(t), t = (m - 1) /
 * (m + 1), |t| <= 0.1716, by its series to t^7 (the next term, t^9 / 9 x
 * 2.885, is under 5e-8). One divide. */
static inline float fm1_log2f(float x) {
  uint32_t bits;
  int e;
  float m, t, t2, s;
  memcpy(&bits, &x, sizeof bits);
  e = (int)((bits >> 23) & 0xFFu) - 127;
  bits = (bits & 0x007FFFFFu) | 0x3F800000u;   /* the mantissa as m in [1, 2) */
  memcpy(&m, &bits, sizeof m);
  if (m > 1.41421356f) {                        /* to (sqrt(1/2), sqrt(2)] */
    m = 0.5f * m;
    e = e + 1;
  }
  t = (m - 1.0f) / (m + 1.0f);                  /* m - 1 is exact here */
  t2 = t * t;
  s = 0.412198583f * t2;                        /* 2 / (7 ln 2) */
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
static inline float fm1_exp2f(float x) {
  float h, u, p, scale;
  int n;
  uint32_t bits;
  if (!(x > -126.0f)) return 0.0f;              /* NaN fails too */
  if (x > 126.0f) x = 126.0f;
  h = x + 0.5f;
  n = (int)h;                                   /* truncates towards zero... */
  if ((float)n > h) n = n - 1;                  /* ...so step down for h < 0 */
  u = (x - (float)n) * 0.693147181f;
  p = 0.00138888889f * u;                       /* 1/720 */
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
  bits = (uint32_t)(n + 127) << 23;             /* n in [-126, 126] */
  memcpy(&scale, &bits, sizeof scale);
  return p * scale;
}

#ifdef __cplusplus
}
#endif

#endif /* FM1_MATH_H_ */
