/* fx_comp_math.h -- base-2 logarithm and exponential for Comp
 * (src/fx_comp.cc), DJ Filter and Tilt, without libm. MIT licence.
 *
 * Since engine API v3 (2026-10-05) the code lives in include/fm1_math.h,
 * which the hosts share for the LOG parameter law (fm1_engine.h); these
 * names stay so the effects read as before, and compute the same bits: the
 * same operations in the same order, each rounded once [verified: the
 * effects' renders are unchanged, tests/test_engines_comp.py and the
 * byte-identity check of the API v3 stream].
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

#include "fm1_math.h"

/* log2(x) for normal x > 0; the caller floors x (fm1_log2f). */
static inline float CompLog2(float x) { return fm1_log2f(x); }

/* 2^x, 0 below -126, saturating at 2^126 (fm1_exp2f). */
static inline float CompExp2(float x) { return fm1_exp2f(x); }

#endif /* FM1_FX_COMP_MATH_H_ */
