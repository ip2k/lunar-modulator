/* fx_room_math.h -- base-2 logarithm, exponential and power without libm,
 * for Room (src/fx_room.cc) and for its reference tool (test/ref_room.cc),
 * which applies Room's rate rule with these same functions. Written for
 * this repository. MIT licence.
 *
 * Why not libm: logf, exp2f and powf differ in their last bits between C
 * libraries (Apple's, glibc, musl in Emscripten), and Room feeds the results
 * into a loop that stores 12-bit words, where a coefficient one ulp away
 * eventually flips a truncation and the output drifts by whole LSBs. These
 * use only IEEE single-precision +, -, * and / and bit moves, one operation
 * per statement, so every build that does not fuse multiply-adds (see the
 * FP_CONTRACT pragma in the files that include this) computes the same bits.
 *
 * Accuracy, against double precision [verified: build/fm1-room-test "math",
 * tests/test_engines_room.py]: RoomLog2 within 3e-7 absolute for x in
 * [2^-20, 1]; RoomExp2 within 3e-7 relative on [-30, 0]; RoomPow within
 * 5e-7 relative over the arguments Room uses. The method is the textbook
 * one (an atanh series for the logarithm, a Taylor polynomial and a direct
 * exponent for the exponential).
 */
#ifndef FM1_FX_ROOM_MATH_H_
#define FM1_FX_ROOM_MATH_H_

#include <stdint.h>
#include <string.h>

/* log2(x) for a finite x > 0 (the callers never pass anything else; a
 * subnormal x is scaled by 2^64 first). With x = m 2^e, m reduced to
 * (sqrt(1/2), sqrt(2)], log2(m) = (2 / ln 2) atanh(t), t = (m - 1) /
 * (m + 1), |t| <= 0.1716, summed to t^9 (the next term is under 2e-9).
 * m - 1 is exact (Sterbenz). */
static inline float RoomLog2(float x) {
  int bias = -127;
  if (x < 1.17549435e-38f) {                    /* subnormal: 2^64 x is normal */
    x = x * 1.84467441e19f;
    bias = -127 - 64;
  }
  uint32_t bits;
  memcpy(&bits, &x, sizeof bits);
  int e = (int)((bits >> 23) & 0xFFu) + bias;
  bits = (bits & 0x007FFFFFu) | 0x3F800000u;   /* m in [1, 2) */
  float m;
  memcpy(&m, &bits, sizeof m);
  if (m > 1.41421356f) {
    m = 0.5f * m;
    e = e + 1;
  }
  const float num = m - 1.0f;
  const float den = m + 1.0f;
  const float t = num / den;
  const float t2 = t * t;
  float s = 0.320598898f * t2;                  /* 2 / (9 ln 2) */
  s = s + 0.412198583f;                         /* 2 / (7 ln 2) */
  s = s * t2;
  s = s + 0.577078016f;                         /* 2 / (5 ln 2) */
  s = s * t2;
  s = s + 0.961796694f;                         /* 2 / (3 ln 2) */
  s = s * t2;
  s = s + 2.88539008f;                          /* 2 / ln 2 */
  s = s * t;
  return (float)e + s;
}

/* 2^y. 0 at or below -126 (and for NaN), 2^127 at or above 127. y = n + f
 * with n the nearest integer and |f| <= 1/2; 2^f = e^(f ln 2) by its Taylor
 * polynomial to degree 7 (truncation under 6e-9), times 2^n set directly
 * in the exponent. y - n is exact. */
static inline float RoomExp2(float y) {
  if (!(y > -126.0f)) return 0.0f;
  if (y > 127.0f) y = 127.0f;
  const float h = y + 0.5f;
  int n = (int)h;                               /* truncates towards zero, */
  if ((float)n > h) n = n - 1;                  /* so step down below zero */
  const float f = y - (float)n;
  const float u = f * 0.693147181f;
  float p = 0.000198412698f * u;                /* 1/5040 */
  p = p + 0.00138888889f;                       /* 1/720 */
  p = p * u;
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
  const uint32_t bits = (uint32_t)(n + 127) << 23;   /* n in [-126, 127] */
  float scale;
  memcpy(&scale, &bits, sizeof scale);
  return p * scale;
}

/* g^r for g in (0, 1] and r > 0. r == 1 returns g itself, bit for bit, so
 * at Clouds' own rate the rate rule changes nothing. */
static inline float RoomPow(float g, float r) {
  if (r == 1.0f) return g;
  if (!(g > 0.0f)) return 0.0f;
  if (g >= 1.0f) return 1.0f;
  const float l = RoomLog2(g);
  const float y = r * l;
  return RoomExp2(y);
}

#endif /* FM1_FX_ROOM_MATH_H_ */
