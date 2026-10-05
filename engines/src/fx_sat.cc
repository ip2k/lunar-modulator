/* fx_sat.cc -- "Master Sat": gentle saturation for the master bus
 * (FM1_KIND_AUDIO_FX), written for this repository. Notes in
 * engines/README.md ("Master Sat"); the design is §6 of
 * notes/2026-10-02-delay-reverb-eq-gates-options.md.
 *
 * Signal path, per channel and per sample:
 *
 *   input guard -> high-pass (Clean Lo) -> low-pass (Clean Hi) = band
 *   u = Drive x band;  the Glue gain G (stereo-linked, below);  v = G u
 *   residual = (h(v) - v) / Drive  -> DC blocker (10 Hz) = r
 *   wet = G x + r;   out = x + Mix (Level x wet - x)
 *
 * f is an odd polynomial of the 11th degree, clamped where its slope reaches
 * zero (a C1 plateau); h is f shifted by Asymmetry's offset a and normalised
 * to slope 1 at the origin: h(v) = (f(v + a) - f(a)) / f'(a). Only the
 * residual h(v) - v, the part that is not linear, is added to the dry
 * signal, so:
 *   - small signals pass unchanged: the residual falls as v^3 (v^2 with
 *     Asymmetry); for a -60 dBFS sine at full Drive and Glue the output
 *     differs from the input by at most -96 dB of its peak (-54 dB with
 *     Asymmetry at 1);
 *   - only the band between Clean Lo and Clean Hi is saturated: the lows (no
 *     intermodulation of the kick and the bass with the rest) and the highs
 *     (fewer harmonics to alias) pass clean, whatever the filters' phase,
 *     since the dry signal is never split;
 *   - Drive sets where the curve starts to bend: its gain into the curve is
 *     divided out again, so a quiet passage keeps its level.
 *
 *   Drive       0..18 dB of gain into the curve.
 *   Clean Lo    20..300 Hz, a 12 dB/octave high-pass before the curve:
 *               below it nothing is saturated, and Glue does not hear it.
 *   Glue        0..1. The curve's squash, s = 1 - |h(u)| / |u| of the
 *               louder channel, follows an envelope (2 ms attack, 200 ms
 *               release); G = 1 - Glue s / 2 lowers the drive into the
 *               curve and the level of the whole signal, by up to 6 dB, a
 *               bus compressor keyed by how hard the curve works. G = 1
 *               exactly at Glue 0.
 *   Mix         0..1, default 0: at 0 the (guarded) input passes bit for bit,
 *               so the default is an exact bypass (§5 of the note).
 *   Shape       Smooth (Airwindows PurestSaturation's coefficients) or Dense
 *               (TapeHack2's): Dense bends sooner and tops out lower. A
 *               change crossfades over 5 ms.
 *   Asymmetry   -1..+1: the curve's input is offset by 0.5 x Asymmetry, so
 *               one side bends before the other and even harmonics appear;
 *               f(a) is subtracted, the slope renormalised, and the DC that a
 *               lopsided curve makes is removed by the residual's DC blocker.
 *   Clean Hi    1..20 kHz (at most 0.45 of the host's rate), a 12 dB/octave
 *               low-pass before the curve: above it nothing is saturated.
 *   Level       -12..+12 dB, the wet signal's gain.
 *
 * The curves. The research (§6) compared Airwindows' PurestSaturation and
 * TapeHack2 against stmlib's SoftClip and tanh: odd polynomials of the 11th
 * degree make no harmonic above the 11th before they clamp, so at moderate
 * drive their aliases sit near -126 dB where the usual soft clips' sit at
 * -66 to -70 dB [verified in the note]. Airwindows clamps PurestSaturation
 * at 2.0326 (where its slope is still 0.0065) and TapeHack2 at 2.3059 (a
 * local minimum after a 0.4 % dip past its peak at 1.9580). Here each is
 * clamped at the first zero of its slope, 2.04500628 and 1.9580127 (found by
 * bisection on the polynomial's derivative in double precision), so both are
 * monotonic and C1, with ceilings of 1.2212 and 1.0821. Beyond the clamp a
 * driven peak is flat-topped: harmonics without end, which the Clean Hi
 * low-pass is there to keep down (engines/README.md has the aliasing
 * measured). No oversampling and no antiderivative anti-aliasing, as the
 * note recommends for a bus effect. The residual is evaluated as a
 * polynomial in v about the offset (SatShift below), never as the difference
 * f(v + a) - f(a), which would lose a quiet signal to the rounding of v + a.
 *
 * Glue's idea, a saturator whose overspill turns its own drive down, is
 * Airwindows Compresaturator's (MIT); no code from it is used. The note asked
 * for the overspill |u| - |h(u)| itself as the detector; it is divided by
 * |u| here so that the reduction is bounded and the same at any Drive, and
 * so that the release takes the same time whatever the level falls to (the
 * ratio of two envelopes would hold until the louder one had decayed). The
 * envelope is two lines; when the shared libm-free maths header of the
 * note's stage B1 lands, it belongs there with the Comp's smoothing.
 *
 * Determinism: no libm call at all. 2^x, sine and cosine for the controls
 * are polynomials written here; everything else is +, -, *, / and
 * comparisons, so the native and WebAssembly builds compute the same bits.
 * Clang fuses no multiply-add here (the pragma below); a GCC build for a
 * target with fused multiply-adds takes -ffp-contract=off (docs/14).
 *
 * Contracts (fm1_engine.h): no heap, every field set in create, NaN-safe
 * parameters (fm1_param_clamp), finite output. Input guard as the Mutable
 * effects' (mi_fx.cc): NaN reads as 0 and anything beyond +/-16 is clamped,
 * so non-finite input cannot reach the state. Silence in gives exact silence
 * out at any setting, also while the knobs move: the residual is a
 * polynomial with no constant term, 0 at v = 0 whatever the offset.
 * Parameters glide (one pole, 5 ms) sample by sample and Shape crossfades,
 * so any block size gives the same output; values set before the first
 * render take effect at once. States below 1e-20 flush to zero (a filter's
 * two states together, below), so a tail ends in exact zeros.
 *
 * Cost, per frame (stereo): two two-pole filters, the curve and the DC
 * blocker per channel and one divide for Glue, about 100 operations; with
 * Glue above 0 the curve runs twice per channel (about 130), with Asymmetry
 * away from 0 it has ten terms instead of five (about 170 with Glue), and
 * during a Shape crossfade both curves run. Desktop timings are in
 * engines/README.md.
 *
 * Written in the C subset of C++11 so it would build as C99 unchanged apart
 * from the extern "C" linkage below. MIT licence, like the rest of this
 * repository.
 */

#include "fm1_engine.h"

#include <stdint.h>
#include <string.h>

/* No fused multiply-adds in this file: the browser's WebAssembly cannot fuse,
 * so a native build that did would round differently (Apple clang on arm64
 * fuses by default). GCC ignores the pragma: build for a GCC target with FMA
 * with -ffp-contract=off. */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

#if defined(__GNUC__) || defined(__clang__)
#define SAT_INLINE static inline __attribute__((always_inline))
#else
#define SAT_INLINE static inline
#endif

enum {
  P_DRIVE, P_BASS, P_GLUE, P_MIX,
  P_SHAPE, P_ASYMMETRY, P_HIGHS, P_LEVEL,
  P_COUNT
};
enum { SH_SMOOTH, SH_DENSE, SH_COUNT };

static const char *const kShapeNames[SH_COUNT] = { "Smooth", "Dense" };

/* Uids (API v2) are fixed: never renumber one; a new parameter takes the next
 * free uid. The FLOATs are read every sample: SMOOTH and MOD. Shape
 * crossfades over 5 ms, so a lock or a (rounded) route on it is clean however
 * fast: MOD, lockable. Drive and Level are in dB, for which fm1_unit_t has no
 * code yet. */
static const fm1_param_t kSatParams[P_COUNT] = {
  { "Drive",       FM1_PARAM_FLOAT, 0, 18, 6.0f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Drive" },
  { "Clean Lo",    FM1_PARAM_FLOAT, 20, 300, 100.0f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_HZ, "ClnLo" },
  { "Glue",        FM1_PARAM_FLOAT, 0, 1, 0.25f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Glue" },
  { "Mix",         FM1_PARAM_FLOAT, 0, 1, 0.0f, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Shape",       FM1_PARAM_ENUM, 0, SH_COUNT - 1, SH_SMOOTH, kShapeNames, 1, 5, FM1_PARAM_MOD, FM1_UNIT_NONE, "Shape" },
  { "Asymmetry",   FM1_PARAM_FLOAT, -1, 1, 0.0f, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Asym" },
  { "Clean Hi",    FM1_PARAM_FLOAT, 1000, 20000, 6000.0f, NULL, 1, 7, FM1_PARAM_CONTINUOUS, FM1_UNIT_HZ, "ClnHi" },
  { "Level",       FM1_PARAM_FLOAT, -12, 12, 0.0f, NULL, 1, 8, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Level" },
};

/* The gliding control values. */
enum { S_GAIN, S_DEPTH, S_MIX, S_LEVEL, S_OFFSET, S_BASS_G, S_HIGH_G, S_COUNT };

static const float kOffsetScale = 0.5f;      /* Asymmetry 1 = an offset of 0.5 */
static const float kGlueDepth = 0.5f;        /* Glue 1: G down to 1 - 0.5 s */
static const float kAttackSeconds = 0.002f;  /* Glue's envelope */
static const float kReleaseSeconds = 0.2f;
static const float kMaxOfRate = 0.45f;       /* filter corners below 0.45 fs */
static const float kDcHz = 10.0f;            /* DC blocker corner */
static const float kSmoothSeconds = 0.005f;  /* parameter glide time constant */
static const float kFadeSeconds = 0.005f;    /* Shape crossfade */
static const float kInputLimit = 16.0f;      /* the input guard, as mi_fx.cc */
static const float kFlush = 1e-20f;          /* states below this become 0 */
static const float kTiny = 1e-11f;           /* |v| below this: no residual */
static const float kSqrt2 = 1.41421356237310f;
static const float kDbToOctaves = 0.166096404744368f;   /* log2(10) / 20 */
static const float kLog2e = 1.44269504088896f;
static const float kPi = 3.14159265358979f;

/* ---------------------------------------------------------------------- */
/* The curves                                                              */
/* ---------------------------------------------------------------------- */

/* f(x) = x + c3 x^3 + c5 x^5 + c7 x^7 + c9 x^9 + c11 x^11 for |x| <= clamp,
 * f(+/-clamp) beyond.
 *
 * The coefficients c3..c11 of both curves are Airwindows', from
 * PurestSaturation (Smooth: -1/8, 1/128, -1/4096, 1/262144, -1/33554432) and
 * TapeHack2 (Dense: -1/6, 1/69, -1/2530.08, 1/224985.6, -1/9979200), read at
 * github.com/airwindows/airwindows commit d22a25b7f7c0c8c05e9f3ae480e7f1da9769f49d
 * (PurestSaturationProc.cpp and TapeHack2Proc.cpp under plugins/LinuxVST/src,
 * whose headers read "Copyright (c) airwindows, Airwindows uses the MIT license").
 * Their notice, from that commit's LICENSE:
 *
 *   MIT License
 *
 *   Copyright (c) 2018 Chris Johnson
 *
 *   Permission is hereby granted, free of charge, to any person obtaining a
 *   copy of this software and associated documentation files (the
 *   "Software"), to deal in the Software without restriction, including
 *   without limitation the rights to use, copy, modify, merge, publish,
 *   distribute, sublicense, and/or sell copies of the Software, and to
 *   permit persons to whom the Software is furnished to do so, subject to
 *   the following conditions:
 *
 *   The above copyright notice and this permission notice shall be included
 *   in all copies or substantial portions of the Software.
 *
 *   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
 *   OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 *   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 *   IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
 *   CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
 *   TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 *   SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 *
 * The clamps (the first zero of each slope) and everything else here are
 * this repository's. */
typedef struct SatShape {
  float c[5];     /* c3, c5, c7, c9, c11 */
  float clamp;
} SatShape;

static const SatShape kShapes[SH_COUNT] = {
  { { -0.125f, 0.0078125f, -0.000244140625f, 3.81469727e-06f, -2.98023224e-08f }, 2.04500628f },
  { { -0.166666672f, 0.0144927539f, -0.000395244424f, 4.4447288e-06f, -1.00208432e-07f },
    1.9580127f },
};

/* f(x), clamped: for the plateaus only. */
static float SatCurve(const SatShape *s, float x) {
  if (x > s->clamp) x = s->clamp;
  if (x < -s->clamp) x = -s->clamp;
  const float x2 = x * x;
  float p = s->c[4] * x2;
  p = (p + s->c[3]) * x2;
  p = (p + s->c[2]) * x2;
  p = (p + s->c[1]) * x2;
  p = (p + s->c[0]) * x2;
  return x + x * p;
}

/* The curve about the offset a. With h(v) = (f(a + v) - f(a)) / f'(a), what
 * h adds to v is, inside the clamp, the polynomial
 *   h(v) - v = b2 v^2 + b3 v^3 + ... + b11 v^11,  b_j = f^(j)(a) / (j! f'(a)),
 * evaluated as v^2 times a Horner sum: no difference of two nearly equal
 * values, so it is exact in relative terms at any level (f(a + v) - f(a)
 * would lose a small v to the rounding of a + v), and exactly 0 at v = 0.
 * Beyond the clamp h is the plateau, hi or lo. */
typedef struct SatPoly {
  float b[10];            /* b2..b11 */
  float hi, lo;           /* h beyond +clamp and -clamp */
  int odd;                /* a == 0: the even b are 0, so sum the odd ones in v^2 */
} SatPoly;

static void SatShift(const SatShape *s, float a, SatPoly *out) {
  /* f's coefficients by power, then a Taylor shift by a (repeated synthetic
   * division): afterwards p[j] = f^(j)(a) / j!. */
  float p[12] = { 0.0f, 1.0f, 0.0f, s->c[0], 0.0f, s->c[1], 0.0f, s->c[2], 0.0f, s->c[3],
                  0.0f, s->c[4] };
  for (int i = 0; i < 11; ++i) {
    for (int j = 10; j >= i; --j) p[j] = p[j] + a * p[j + 1];
  }
  const float inv = 1.0f / p[1];          /* f'(a) >= 0.87 for |a| <= 0.5 */
  for (int j = 2; j < 12; ++j) out->b[j - 2] = p[j] * inv;
  const float top = SatCurve(s, s->clamp);
  out->hi = (top - p[0]) * inv;
  out->lo = (-top - p[0]) * inv;
  out->odd = a == 0.0f;
}

/* h(v) - v. Below kTiny (-220 dB) it is 0: the cubic term there would be
 * near the subnormals, and the true residual is under 1e-33. */
SAT_INLINE float SatResidual(const SatShape *s, const SatPoly *p, float v, float a) {
  const float x = v + a;
  if (x >= s->clamp) return p->hi - v;
  if (x <= -s->clamp) return p->lo - v;
  if (v > -kTiny && v < kTiny) return 0.0f;
  const float *b = p->b;
  if (p->odd) {                   /* Asymmetry 0: half the work */
    const float v2 = v * v;
    float t = b[9] * v2;
    t = (t + b[7]) * v2;
    t = (t + b[5]) * v2;
    t = (t + b[3]) * v2;
    t = t + b[1];
    return (t * v2) * v;
  }
  float t = b[9] * v;
  t = (t + b[8]) * v;
  t = (t + b[7]) * v;
  t = (t + b[6]) * v;
  t = (t + b[5]) * v;
  t = (t + b[4]) * v;
  t = (t + b[3]) * v;
  t = (t + b[2]) * v;
  t = (t + b[1]) * v;
  t = t + b[0];
  return (t * v) * v;
}

/* ---------------------------------------------------------------------- */
/* Arithmetic for the controls, without libm                               */
/* ---------------------------------------------------------------------- */

/* 2^x: the nearest integer n and a Taylor polynomial of 2^f on [-0.5, 0.5]
 * (truncation 5e-9), scaled by 2^n built from its bits. x is clamped to
 * +/-126, so the result is a normal float. */
static float SatExp2(float x) {
  if (!(x > -126.0f)) x = -126.0f;
  if (x > 126.0f) x = 126.0f;
  float n = (float)(int)x;                     /* truncates towards zero.. */
  if (n > x) n = n - 1.0f;                     /* ..so floor for x < 0 */
  if (x - n >= 0.5f) n = n + 1.0f;             /* nearest: f in [-0.5, 0.5) */
  const float f = x - n;
  float p = 1.52527338e-05f * f;
  p = (p + 0.000154035304f) * f;
  p = (p + 0.00133335581f) * f;
  p = (p + 0.00961812911f) * f;
  p = (p + 0.0555041087f) * f;
  p = (p + 0.240226507f) * f;
  p = (p + 0.693147181f) * f;
  p = p + 1.0f;
  const uint32_t bits = (uint32_t)((int)n + 127) << 23;
  float scale;
  memcpy(&scale, &bits, sizeof scale);
  return p * scale;
}

static float SatDbToGain(float db) { return SatExp2(db * kDbToOctaves); }

/* One-pole coefficient for a time constant of tau seconds: 1 - e^(-1/(tau fs)). */
static float SatPole(float tau, float fs) {
  return 1.0f - SatExp2(-kLog2e / (tau * fs));
}

/* tan(pi hz / fs) for the TPT filters, from sine and cosine polynomials
 * (Taylor to x^13 and x^12; the angle stays below 0.45 pi = 1.414, where the
 * truncation is under 2e-10). */
static float SatTan(float hz, float fs) {
  const float top = kMaxOfRate * fs;
  if (hz > top) hz = top;
  const float x = kPi * hz / fs, x2 = x * x;
  float s = x2 * (1.0f / 6227020800.0f);
  s = (s - 1.0f / 39916800.0f) * x2;
  s = (s + 1.0f / 362880.0f) * x2;
  s = (s - 1.0f / 5040.0f) * x2;
  s = (s + 1.0f / 120.0f) * x2;
  s = (s - 1.0f / 6.0f) * x2;
  s = (s + 1.0f) * x;
  float c = x2 * (1.0f / 479001600.0f);
  c = (c - 1.0f / 3628800.0f) * x2;
  c = (c + 1.0f / 40320.0f) * x2;
  c = (c - 1.0f / 720.0f) * x2;
  c = (c + 1.0f / 24.0f) * x2;
  c = (c - 0.5f) * x2;
  c = c + 1.0f;
  return s / c;
}

/* ---------------------------------------------------------------------- */
/* The instance                                                            */
/* ---------------------------------------------------------------------- */

typedef struct SatFilter {
  float g, a1, a2, a3;      /* TPT SVF coefficients for g = tan(pi fc / fs) */
} SatFilter;

typedef struct SatChannel {
  float hp1, hp2;           /* Bass high-pass integrator states */
  float lp1, lp2;           /* Clean Hi low-pass integrator states */
  float dc_x1, dc_y1;       /* the residual's DC blocker */
} SatChannel;

typedef struct SatInstance {
  float param[P_COUNT];     /* knob values, clamped */
  float target[S_COUNT];    /* control values the knobs ask for */
  float value[S_COUNT];     /* control values in use (gliding to target) */
  float sample_rate;
  float glide;              /* one-pole coefficient of the glide */
  float k_attack, k_release;
  float dc_r;               /* DC blocker pole */
  float fade, fade_step;    /* Shape crossfade, 0..1 */
  float gain_at, inv_gain;  /* value[S_GAIN] and its inverse */
  float offset_at;          /* value[S_OFFSET] poly was made for */
  SatPoly poly[SH_COUNT];   /* each curve about that offset */
  float squash;             /* Glue's envelope, 0..1 */
  SatFilter hp, lp;
  int shape_target, shape_from, shape_to;
  int primed;               /* 0 until the first render */
  SatChannel ch[2];
} SatInstance;

static inline float SatGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

static inline float SatAbs(float x) { return x < 0.0f ? -x : x; }

static inline float SatFlush(float v) {
  return (v > -kFlush && v < kFlush) ? 0.0f : v;
}

/* A two-pole filter's states flush together, once both are small: flushing
 * one alone would cut their coupling, and at a 20 Hz corner leave the other
 * decaying with a time constant of seconds instead of milliseconds. (A lone
 * state could only go subnormal by landing within 1e-38 of zero while its
 * partner is above 1e-20: harmless once, and not worth a test per sample.) */
static inline void SatStore2(float *s1, float *s2, float n1, float n2) {
  const int quiet = n1 > -kFlush && n1 < kFlush && n2 > -kFlush && n2 < kFlush;
  *s1 = quiet ? 0.0f : n1;
  *s2 = quiet ? 0.0f : n2;
}

/* One step of the glide; snaps when within 1e-4 (relative), so a value
 * reaches its target exactly instead of stalling an ulp short of it. */
static inline float SatGlide(float v, float t, float k) {
  const float e = t - v;
  if (SatAbs(e) <= 1e-4f * (1.0f + SatAbs(t))) return t;
  return v + k * e;
}

static inline int SatShapeOf(float v) {
  const int i = (int)(v + 0.5f);              /* v >= 0 after the clamp */
  return i < 0 ? 0 : (i >= SH_COUNT ? SH_COUNT - 1 : i);
}

static void SatSetTarget(SatInstance *self, int index) {
  const float v = self->param[index];
  const float fs = self->sample_rate;
  switch (index) {
    case P_DRIVE: self->target[S_GAIN] = SatDbToGain(v); break;
    case P_BASS: self->target[S_BASS_G] = SatTan(v, fs); break;
    case P_GLUE: self->target[S_DEPTH] = kGlueDepth * v; break;
    case P_MIX: self->target[S_MIX] = v; break;
    case P_SHAPE: self->shape_target = SatShapeOf(v); break;
    case P_ASYMMETRY: self->target[S_OFFSET] = kOffsetScale * v; break;
    case P_HIGHS: self->target[S_HIGH_G] = SatTan(v, fs); break;
    case P_LEVEL: self->target[S_LEVEL] = SatDbToGain(v); break;
    default: break;
  }
}

static void SatSetFilter(SatFilter *f, float g) {
  /* Zavalishin's TPT state-variable filter, Q = 1/sqrt(2) (k = sqrt(2)). */
  f->g = g;
  f->a1 = 1.0f / (1.0f + g * (g + kSqrt2));
  f->a2 = g * f->a1;
  f->a3 = g * f->a2;
}

/* What depends on gliding values, recomputed only when they have moved. */
static void SatUpdateDerived(SatInstance *self) {
  if (self->value[S_GAIN] != self->gain_at) {
    self->gain_at = self->value[S_GAIN];
    self->inv_gain = 1.0f / self->gain_at;
  }
  if (self->value[S_OFFSET] != self->offset_at) {
    self->offset_at = self->value[S_OFFSET];
    for (int s = 0; s < SH_COUNT; ++s) SatShift(&kShapes[s], self->offset_at, &self->poly[s]);
  }
  if (self->value[S_BASS_G] != self->hp.g) SatSetFilter(&self->hp, self->value[S_BASS_G]);
  if (self->value[S_HIGH_G] != self->lp.g) SatSetFilter(&self->lp, self->value[S_HIGH_G]);
}

/* Everything at its target at once: create, and the first render. */
static void SatSnap(SatInstance *self) {
  for (int s = 0; s < S_COUNT; ++s) self->value[s] = self->target[s];
  self->shape_from = self->shape_to = self->shape_target;
  self->fade = 0.0f;
  self->gain_at = -1.0f;                   /* force the derived values */
  self->offset_at = -1.0f;
  self->hp.g = self->lp.g = -1.0f;
  SatUpdateDerived(self);
}

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t SatInstanceSize(const fm1_host_t *host) {
  (void)host;
  return (sizeof(SatInstance) + 15u) & ~(size_t)15u;
}

static void *SatCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;
  SatInstance *self = (SatInstance *)mem;
  memset(self, 0, sizeof(*self));
  self->sample_rate = fs;
  self->glide = SatPole(kSmoothSeconds, fs);
  self->k_attack = SatPole(kAttackSeconds, fs);
  self->k_release = SatPole(kReleaseSeconds, fs);
  self->dc_r = SatExp2(-2.0f * kPi * kDcHz * kLog2e / fs);
  self->fade_step = 1.0f / (kFadeSeconds * fs);
  for (int i = 0; i < P_COUNT; ++i) {
    self->param[i] = kSatParams[i].def;
    SatSetTarget(self, i);
  }
  SatSnap(self);
  self->primed = 0;
  return self;
}

static void SatDestroy(void *self) { (void)self; }

static void SatSet(void *s, uint16_t index, float v) {
  SatInstance *self = (SatInstance *)s;
  if (index >= P_COUNT) return;
  self->param[index] = fm1_param_clamp(&kSatParams[index], v);
  SatSetTarget(self, index);
}

/* One channel's two filters: the band the curve sees. */
SAT_INLINE float SatBand(SatChannel *h, const SatFilter *hp, const SatFilter *lp, float x) {
  float v3 = x - h->hp2;                                  /* high-pass */
  float v1 = hp->a1 * h->hp1 + hp->a2 * v3;
  float v2 = h->hp2 + hp->a2 * h->hp1 + hp->a3 * v3;
  SatStore2(&h->hp1, &h->hp2, 2.0f * v1 - h->hp1, 2.0f * v2 - h->hp2);
  const float high = x - kSqrt2 * v1 - v2;
  v3 = high - h->lp2;                                     /* low-pass */
  v1 = lp->a1 * h->lp1 + lp->a2 * v3;
  v2 = h->lp2 + lp->a2 * h->lp1 + lp->a3 * v3;
  SatStore2(&h->lp1, &h->lp2, 2.0f * v1 - h->lp1, 2.0f * v2 - h->lp2);
  return v2;
}

static void SatRender(void *s, float *lr, uint32_t frames) {
  SatInstance *self = (SatInstance *)s;
  if (!self->primed) {
    /* Settings made before the first block apply from its first sample. */
    SatSnap(self);
    self->primed = 1;
  }
  /* The per-channel state lives in locals for the block: lr may alias any
   * float, so working through self would reload it after every store. */
  SatChannel ch[2] = { self->ch[0], self->ch[1] };
  const float glide = self->glide, dc_r = self->dc_r;
  const float k_attack = self->k_attack, k_release = self->k_release;
  float squash = self->squash;
  for (uint32_t f = 0; f < frames; ++f) {
    int moving = 0;
    for (int k = 0; k < S_COUNT; ++k) {
      if (self->value[k] != self->target[k]) {
        self->value[k] = SatGlide(self->value[k], self->target[k], glide);
        moving = 1;
      }
    }
    if (moving) SatUpdateDerived(self);
    /* A new Shape waits for a running crossfade to finish (at most 5 ms). */
    if (self->shape_from == self->shape_to && self->shape_target != self->shape_to) {
      self->shape_to = self->shape_target;
      self->fade = 0.0f;
    }
    int fading = 0;
    if (self->shape_from != self->shape_to) {
      self->fade += self->fade_step;
      if (self->fade >= 1.0f) {
        self->shape_from = self->shape_to;
        self->fade = 0.0f;
      } else {
        fading = 1;
      }
    }

    const int sf = self->shape_from, st = self->shape_to;
    const SatShape *cf = &kShapes[sf], *ct = &kShapes[st];
    const float w = self->fade;
    const float a = self->value[S_OFFSET];
    const SatPoly *pf = &self->poly[sf], *pt = &self->poly[st];
    const float gain = self->value[S_GAIN], inv_gain = self->inv_gain;
    const SatFilter hp = self->hp, lp = self->lp;

    /* The band, the drive, and the curve at the drive as set. */
    float x[2], u[2], res[2];
    for (int c = 0; c < 2; ++c) {
      x[c] = SatGuard(lr[2 * f + c]);
      u[c] = gain * SatBand(&ch[c], &hp, &lp, x[c]);
      float r = SatResidual(cf, pf, u[c], a);
      if (fading) r = r + w * (SatResidual(ct, pt, u[c], a) - r);
      res[c] = r;
    }

    /* Glue: the squash of the louder channel, 1 - h(u) / u = -residual / u
     * (h keeps u's sign), through the envelope. */
    const int loud = SatAbs(u[1]) > SatAbs(u[0]) ? 1 : 0;
    float sq = 0.0f;
    if (res[loud] != 0.0f) {          /* so |u| >= kTiny */
      sq = -res[loud] / u[loud];
      if (sq < 0.0f) sq = 0.0f;       /* the steeper side of a shifted curve */
      if (sq > 1.0f) sq = 1.0f;
    }
    squash += (sq > squash ? k_attack : k_release) * (sq - squash);
    squash = SatFlush(squash);
    const float g = 1.0f - self->value[S_DEPTH] * squash;

    const float mix = self->value[S_MIX], level = self->value[S_LEVEL];
    for (int c = 0; c < 2; ++c) {
      SatChannel *h = &ch[c];
      float r = res[c];
      if (g != 1.0f) {                /* the drive lowered: the curve again */
        const float v = g * u[c];
        r = SatResidual(cf, pf, v, a);
        if (fading) r = r + w * (SatResidual(ct, pt, v, a) - r);
      }
      r = r * inv_gain;
      const float y = r - h->dc_x1 + dc_r * h->dc_y1;        /* DC blocker */
      h->dc_x1 = r;
      h->dc_y1 = SatFlush(y);
      const float wet = g * x[c] + y;
      lr[2 * f + c] = mix != 0.0f ? x[c] + mix * (level * wet - x[c]) : x[c];
    }
  }
  self->squash = squash;
  self->ch[0] = ch[0];
  self->ch[1] = ch[1];
}

#ifdef __cplusplus
extern "C" {
#endif

extern const fm1_engine_t fm1_engine_sat;
const fm1_engine_t fm1_engine_sat = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "sat", "Master Sat",
  "This repository (MIT): band-limited bus saturation; curve coefficients "
  "from Airwindows PurestSaturation and TapeHack2 (Chris Johnson, MIT, "
  "notice in the source); Glue after Airwindows Compresaturator, no code taken",
  kSatParams, P_COUNT, 0,
  SatInstanceSize, SatCreate, SatDestroy,
  NULL, NULL, NULL,
  SatSet, SatRender,
};

#ifdef __cplusplus
}
#endif
