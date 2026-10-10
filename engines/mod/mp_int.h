/* mp_int.h -- shared internals of the modulation primitives (not API). */
#ifndef FM1_MP_INT_H
#define FM1_MP_INT_H

#include "fm1_mp.h"

#define FM1_MP_TABLE_SIZE 257

extern const float fm1_mp_curve_expo[FM1_MP_TABLE_SIZE];
extern const float fm1_mp_curve_log[FM1_MP_TABLE_SIZE];
extern const float fm1_mp_curve_quartic[FM1_MP_TABLE_SIZE];
extern const float fm1_mp_env_times[FM1_MP_TABLE_SIZE];

/* Finite without libm or <math.h> classification macros: NaN fails the first
 * test, +-inf the second (inf - inf is NaN). Needs IEEE semantics, so never
 * build these files with -ffast-math. */
static inline int mp_finite(float x) {
  return x == x && (x - x) == 0.0f;
}

/* x clamped to lo..hi; NaN gives `nan_value`. */
static inline float mp_clampf(float x, float lo, float hi, float nan_value) {
  if (x != x) return nan_value;
  if (x < lo) return lo;
  if (x > hi) return hi;
  return x;
}

static inline float mp_rate(float sample_rate) {
  return (sample_rate >= 1000.0f && sample_rate <= 384000.0f) ? sample_rate
                                                             : FM1_MP_DEFAULT_RATE;
}

/* Linear interpolation in a 257-point table over a uint32 position: the top
 * 8 bits pick the point, the next 24 the fraction. */
static inline float mp_table(const float *t, uint32_t phase) {
  const uint32_t i = phase >> 24;
  const float f = (float)(phase & 0xFFFFFFu) * (1.0f / 16777216.0f);
  return t[i] + (t[i + 1] - t[i]) * f;
}

#endif /* FM1_MP_INT_H */
