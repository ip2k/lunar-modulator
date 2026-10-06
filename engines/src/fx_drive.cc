/* fx_drive.cc -- "Drive": overdrive and saturation (FM1_KIND_AUDIO_FX),
 * written for this repository. Notes in engines/README.md ("Drive").
 *
 * Signal path, per channel and per sample:
 *
 *   input guard -> pre-emphasis (Tape) -> x Drive = u -> shaper (the Type's
 *   curve, with a dead zone of width Gate and an offset of Bias, first-order
 *   antiderivative anti-aliasing) -> minus the shaper of silence ->
 *   de-emphasis (Tape) -> DC blocker (10 Hz) -> tilt (Tone) -> x Level (and
 *   the automatic gain) -> mix
 *
 *   Type   Soft, Tube, Diode, Fuzz or Tape; a change crossfades over 5 ms.
 *   Drive  the gain into the shaper, -12 to +36 dB.
 *   Tone   a tilt about 800 Hz: 0.5 is flat, 0 cuts the highs by up to
 *          18 dB, 1 the lows.
 *   Mix    dry to wet. At 0 the (guarded) input passes through unchanged.
 *   Bias   an offset added at the curve's input, -1..+1 in its units: the
 *          clipping becomes uneven and even harmonics appear.
 *   Gate   a dead zone at the curve's input, 0..0.5 in its units: a signal
 *          that small after Drive comes out silent (crossover distortion; a
 *          starved, sputtering fuzz on decays).
 *   Level  the wet signal's gain, -24 to +12 dB.
 *   Auto   On divides the wet signal by what the shaper does to the level of
 *          a reference sine (0.5 peak), so Drive changes the character and
 *          not the loudness; Off leaves the level to Level.
 *
 * The curves. Each Type is a C2 piecewise quintic (Hermite: value, slope and
 * curvature given at each knot) and constant beyond its outer knots, so the
 * shaper saturates at a ceiling (Fuzz: corners, C0, on purpose):
 *
 *   Soft   knots at 0 (slope 1) and +/-2.5 (+/-1, flat): within 0.047 of
 *          tanh everywhere, odd harmonics only.
 *   Tube   slope 1 and curvature 0.3 at 0, reaching +1 at +2.2 and -0.8 at
 *          -1.6: the quadratic term gives a second harmonic at every level,
 *          and the negative side compresses earlier and lower, as a triode
 *          driven towards grid current does [inferred: the usual reading of
 *          triode transfer curves, no circuit model].
 *   Diode  linear to +/-0.6, then a short knee to +/-1 at +/-1.35: the hard
 *          knee of an antiparallel diode pair to ground, capped (a real pair
 *          keeps rising logarithmically) [inferred].
 *   Fuzz   a hard clip at +/-1, with its own offset of 0.25 (asymmetric) and
 *          its own dead zone of 0.04 (gated), added to Bias and Gate.
 *   Tape   Soft at twice the scale (knots at +/-5, ceiling +/-2: 6 dB more
 *          headroom), inside a first-order pre-emphasis (+12 dB above
 *          3.2 kHz, the 50 us record time constant) and its exact inverse
 *          after: quiet signals pass flat, loud highs saturate first and
 *          come out softened, as on tape [reported: record/replay
 *          equalisation; no code taken]. The emphasis glides in and out with
 *          the Type crossfade; for the other Types it is exactly the
 *          identity.
 *
 * The coefficient table kCurves is generated from the knots by
 * tests/test_engines_drive.py (python -m tests.test_engines_drive prints
 * it), which also checks the table against the knots.
 *
 * Aliasing. A saturator makes harmonics above Nyquist that a plain
 * per-sample curve reflects back into the band. Every Type uses first-order
 * antiderivative anti-aliasing (ADAA; Parker, Zavalishin and Le Bivic,
 * DAFx-16, 2016), as Fold does: each output is the mean of the curve over the
 * segment from the previous input to this one. For a piecewise polynomial
 * that mean needs no division by a small step: within one polynomial piece,
 * in local coordinates t, the mean of t^k over [a, b] is
 *   h_{k+1}(a, b) / (k + 1),  h_n = (b^n - a^n) / (b - a)
 *                                 = s h_{n-1} - p h_{n-2},  s = a + b, p = a b,
 * a recurrence without cancellation; across pieces the means are weighted by
 * the pieces' lengths, a convex combination. So there is no epsilon, no
 * fallback, and a step of zero gives the curve itself, exactly. The cost is
 * Fold's: a half-sample delay and a gentle roll-off of the wet path (-0.6 dB
 * at 5 kHz, -3 dB at 11 kHz at 44,118 Hz). Measured against a plain
 * per-sample curve on 440 and 1,760 Hz sines, it lowers the aliases below
 * 5 kHz by 21-29 dB and across the band by 5-10 dB, alike for every Type
 * (engines/README.md has the table and the comparison with 2x oversampling,
 * which was not taken: about three times the cost; tests/test_engines_drive.py
 * checks the figures).
 *
 * Determinism: no libm call beyond floorf, fabsf and sqrtf, whose results
 * IEEE 754 defines exactly. 2^x, sine and cosine for the controls are
 * polynomials written here, so the native and WebAssembly builds compute the
 * same bits. Clang fuses no multiply-add here (the pragma below; Apple clang
 * otherwise would). GCC ignores the pragma and fuses where the target has a
 * fused instruction (not x86-64 without -mfma, not WebAssembly): a GCC build
 * for such a target takes -ffp-contract=off, docs/14's ladder profile.
 *
 * Contracts (fm1_engine.h): no heap, every field set in create, NaN-safe
 * parameters (fm1_param_clamp), finite output. Input guard as the Mutable
 * effects' (mi_fx.cc): NaN reads as 0 and anything beyond +/-16 is clamped,
 * so non-finite input cannot reach the state. Silence in gives exact silence
 * out at any setting (the shaper of silence is subtracted, computed by the
 * same code on the same values). Parameters glide (one pole, 5 ms) sample by
 * sample and Type crossfades, so any block size gives the same output;
 * values set before the first render take effect at once. Filter states
 * below 1e-20 flush to zero.
 *
 * Written in the C subset of C++11 so it would build as C99 unchanged apart
 * from the extern "C" linkage below. MIT licence, like the rest of this
 * repository.
 */

#include "fm1_engine.h"

#include <math.h>
#include <string.h>

#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

#if defined(__GNUC__) || defined(__clang__)
#define DRIVE_INLINE static inline __attribute__((always_inline))
#else
#define DRIVE_INLINE static inline
#endif

enum { P_TYPE, P_DRIVE, P_TONE, P_MIX, P_BIAS, P_GATE, P_LEVEL, P_AUTO, P_COUNT };
enum { T_SOFT, T_TUBE, T_DIODE, T_FUZZ, T_TAPE, T_COUNT };

static const char *const kTypeNames[T_COUNT] = { "Soft", "Tube", "Diode", "Fuzz", "Tape" };
static const char *const kAutoNames[2] = { "Off", "On" };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. The floats are read every block (SMOOTH and MOD). Type crossfades
// and Auto's gain glides, so a lock or a (rounded) route on either is clean,
// however fast: MOD. Drive and Level are in dB (FM1_UNIT_DB, API v3).
static const fm1_param_t kDriveParams[P_COUNT] = {
  { "Type",  FM1_PARAM_ENUM,    0,  4,  0.0f, kTypeNames, 0, 1, FM1_PARAM_MOD, FM1_UNIT_NONE, "Type" },
  { "Drive", FM1_PARAM_FLOAT, -12, 36, 12.0f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Drive" },
  { "Tone",  FM1_PARAM_FLOAT,   0,  1,  0.5f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Tone" },
  { "Mix",   FM1_PARAM_FLOAT,   0,  1,  1.0f, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Bias",  FM1_PARAM_FLOAT,  -1,  1,  0.0f, NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Bias" },
  { "Gate",  FM1_PARAM_FLOAT,   0,  1,  0.0f, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Gate" },
  { "Level", FM1_PARAM_FLOAT, -24, 12,  0.0f, NULL, 1, 7, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Level" },
  { "Auto",  FM1_PARAM_ENUM,    0,  1,  1.0f, kAutoNames, 1, 8, FM1_PARAM_MOD, FM1_UNIT_NONE, "Auto" },
};

/* The smoothed control values. */
enum { S_GAIN, S_BIAS, S_GATE, S_MIX, S_OUT, S_TILT_LO, S_TILT_HI, S_EMPH, S_COUNT };

static const float kGateScale = 0.5f;        /* Gate 1 = a dead zone of +/-0.5 */
static const float kTiltHz = 800.0f;         /* the tilt's pivot */
static const float kTiltOctaves = 3.0f;      /* Tone 0 or 1: 2^-3, -18 dB */
static const float kEmphHz = 3183.1f;        /* 1 / (2 pi 50 us) */
static const float kEmphBoost = 3.0f;        /* +12 dB shelf: 1 + 3 = 4 */
static const float kMaxOfRate = 0.45f;       /* filter corners below 0.45 fs */
static const float kDcHz = 10.0f;            /* DC blocker corner */
static const float kSmoothSeconds = 0.005f;  /* parameter glide time constant */
static const float kFadeSeconds = 0.005f;    /* Type crossfade */
static const float kInputLimit = 16.0f;      /* the input guard, as mi_fx.cc */
static const float kFlush = 1e-20f;          /* states below this become 0 */
static const float kRefAmp = 0.5f;           /* Auto's reference sine, peak */
static const float kCompMin = 1.0f / 64.0f;  /* Auto's gain, -36 dB.. */
static const float kCompMax = 8.0f;          /* ..+18 dB */
static const float kDbToOctaves = 0.166096404744368f;   /* log2(10) / 20 */
static const float kLog2e = 1.44269504088896f;
static const float kPi = 3.14159265358979f;

/* ---------------------------------------------------------------------- */
/* The curves                                                              */
/* ---------------------------------------------------------------------- */

/* A Type's curve: n knots x[0] < .. < x[n - 1], constant lo below the first
 * and hi above the last, and between knots j and j + 1 a quintic in the
 * local coordinate t = (v - x[j]) inv_w[j], stored as r[j][k] = q_k / (k + 1)
 * so that the mean over [ta, tb] is sum_k r[j][k] h_{k+1}(ta, tb). area[j]
 * is the integral over the whole piece. gate and bias are the Type's own,
 * added to Gate's and Bias's. */
typedef struct DriveCurve {
  int n;
  float x[4];
  float lo, hi;
  float inv_w[3];
  float r[3][6];
  float area[3];
  float gate, bias;
} DriveCurve;

/* Generated by tests/test_engines_drive.py from the knots (x, f, f', f''):
 *   Soft   (-2.5, -1, 0, 0) (0, 0, 1, 0) (2.5, 1, 0, 0)
 *   Tube   (-1.6, -0.8, 0, 0) (0, 0, 1, 0.3) (2.2, 1, 0, 0)
 *   Diode  (-1.35, -1, 0, 0) (-0.6, -0.6, 1, 0) (0.6, 0.6, 1, 0) (1.35, 1, 0, 0)
 *   Fuzz   (-1, -1, 1, 0) (1, 1, 1, 0); outside, the constants: corners
 *   Tape   (-5, -2, 0, 0) (0, 0, 1, 0) (5, 2, 0, 0)
 * BEGIN GENERATED CURVES */
static const DriveCurve kCurves[T_COUNT] = {
  { 3, { -2.5f, 0.0f, 2.5f, 0.0f }, -1.0f, 1.0f, { 0.400000006f, 0.400000006f, 0.0f },
    { { -1.0f, 0.0f, 0.0f, 0.0f, 0.5f, -0.25f },
      { 0.0f, 1.25f, 0.0f, -1.25f, 1.0f, -0.25f },
      { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f } },
    { -1.875f, 1.875f, 0.0f }, 0.0f, 0.0f },
  { 3, { -1.60000002f, 0.0f, 2.20000005f, 0.0f }, -0.800000012f, 1.0f, { 0.625f, 0.454545468f, 0.0f },
    { { -0.800000012f, 0.0f, 0.0f, 0.495999992f, -0.313600004f, 0.064000003f },
      { 0.0f, 1.10000002f, 0.241999999f, -1.34449995f, 0.955600023f, -0.221000001f },
      { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f } },
    { -0.885760009f, 1.61062002f, 0.0f }, 0.0f, 0.0f },
  { 4, { -1.35000002f, -0.600000024f, 0.600000024f, 1.35000002f }, -1.0f, 1.0f, { 1.33333337f, 0.833333313f, 1.33333337f },
    { { -1.0f, 0.0f, 0.0f, 0.25f, -0.150000006f, 0.0250000004f },
      { -0.600000024f, 0.600000024f, 0.0f, 0.0f, 0.0f, 0.0f },
      { 0.600000024f, 0.375f, 0.0f, -0.125f, 0.0f, 0.0250000004f } },
    { -0.65625f, 0.0f, 0.65625f }, 0.0f, 0.0f },
  { 2, { -1.0f, 1.0f, 0.0f, 0.0f }, -1.0f, 1.0f, { 0.5f, 0.0f, 0.0f },
    { { -1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f },
      { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f },
      { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f } },
    { 0.0f, 0.0f, 0.0f }, 0.0399999991f, 0.25f },
  { 3, { -5.0f, 0.0f, 5.0f, 0.0f }, -2.0f, 2.0f, { 0.200000003f, 0.200000003f, 0.0f },
    { { -2.0f, 0.0f, 0.0f, 0.0f, 1.0f, -0.5f },
      { 0.0f, 2.5f, 0.0f, -2.5f, 2.0f, -0.5f },
      { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f } },
    { -7.5f, 7.5f, 0.0f }, 0.0f, 0.0f },
};
/* END GENERATED CURVES */

/* sin((k + 0.5) pi / 32), k = 0..15: a quarter of a 64-point sine, for
 * Auto's quadrature. Generated with the table above. */
static const float kQuadSin[16] = {
  0.0490676761f, 0.146730468f, 0.242980182f, 0.336889863f, 0.427555084f, 0.514102757f,
  0.59569931f, 0.671558976f, 0.740951121f, 0.803207517f, 0.857728601f, 0.903989315f,
  0.941544056f, 0.970031261f, 0.989176512f, 0.99879545f,
};

/* Which piece holds v: 0 below x[0], j + 1 between x[j] and x[j + 1], n
 * above x[n - 1]. */
static inline int DrivePiece(const DriveCurve *c, float v) {
  int k = 0;
  while (k < c->n && v >= c->x[k]) ++k;
  return k;
}

/* The mean of piece k over [a, b], a <= b, both within it. */
DRIVE_INLINE float DrivePieceMean(const DriveCurve *c, int k, float a, float b) {
  if (k == 0) return c->lo;
  if (k == c->n) return c->hi;
  const int j = k - 1;
  const float x0 = c->x[j], iw = c->inv_w[j];
  const float ta = (a - x0) * iw, tb = (b - x0) * iw;
  const float s = ta + tb, p = ta * tb;
  const float h2 = s;
  const float h3 = s * h2 - p;
  const float h4 = s * h3 - p * h2;
  const float h5 = s * h4 - p * h3;
  const float h6 = s * h5 - p * h4;
  const float *r = c->r[j];
  return r[0] + r[1] * h2 + r[2] * h3 + r[3] * h4 + r[4] * h5 + r[5] * h6;
}

/* The mean of the curve over [a, b], a <= b; with a == b, the curve at a. */
static float DriveCurveMean(const DriveCurve *c, float a, float b) {
  const int ka = DrivePiece(c, a), kb = DrivePiece(c, b);
  if (ka == kb) return DrivePieceMean(c, ka, a, b);
  const float xa = c->x[ka], xb = c->x[kb - 1];
  float acc = DrivePieceMean(c, ka, a, xa) * (xa - a);
  for (int k = ka + 1; k < kb; ++k) acc += c->area[k - 1];
  acc += DrivePieceMean(c, kb, xb, b) * (b - xb);
  return acc / (b - a);
}

/* The anti-aliased shaper: the mean over [u0, u1] of c(dz(u) + b), where dz
 * is a dead zone of half-width t (zero inside, shifted towards zero
 * outside). With u0 == u1, the shaper at that point. */
DRIVE_INLINE float DriveShaper(const DriveCurve *c, float u0, float u1, float t, float b) {
  const float lo = u0 < u1 ? u0 : u1, hi = u0 < u1 ? u1 : u0;
  if (!(t > 0.0f)) return DriveCurveMean(c, lo + b, hi + b);
  const int pa = lo < -t ? 0 : (lo <= t ? 1 : 2);
  const int pb = hi < -t ? 0 : (hi <= t ? 1 : 2);
  if (pa == pb) {
    if (pa == 0) return DriveCurveMean(c, (lo + t) + b, (hi + t) + b);
    if (pa == 2) return DriveCurveMean(c, (lo - t) + b, (hi - t) + b);
    return DriveCurveMean(c, b, b);
  }
  float acc = 0.0f;
  if (pa == 0) acc += (-t - lo) * DriveCurveMean(c, (lo + t) + b, b);
  const float s = lo > -t ? lo : -t, e = hi < t ? hi : t;
  if (e > s) acc += (e - s) * DriveCurveMean(c, b, b);
  if (pb == 2) acc += (hi - t) * DriveCurveMean(c, b, (hi - t) + b);
  return acc / (hi - lo);
}

/* ---------------------------------------------------------------------- */
/* Arithmetic for the controls, without libm                               */
/* ---------------------------------------------------------------------- */

/* 2^x: the nearest integer n and a Taylor polynomial of 2^f on [-0.5, 0.5]
 * (truncation 5e-9), scaled by 2^n built from its bits. x is clamped to
 * +/-126, so the result is a normal float. */
static float DriveExp2(float x) {
  if (!(x > -126.0f)) x = -126.0f;
  if (x > 126.0f) x = 126.0f;
  const float n = floorf(x + 0.5f);
  const float f = x - n;
  const float p = 1.0f + f * (0.693147181f + f * (0.240226507f + f * (0.0555041087f +
                  f * (0.00961812911f + f * (0.00133335581f + f * (0.000154035304f +
                  f * 1.52527338e-05f))))));
  const uint32_t bits = (uint32_t)((int)n + 127) << 23;
  float scale;
  memcpy(&scale, &bits, sizeof scale);
  return p * scale;
}

static float DriveDbToGain(float db) { return DriveExp2(db * kDbToOctaves); }

/* G = g / (1 + g) of a TPT one-pole at hz, g = tan(pi hz / fs), from sine
 * and cosine polynomials (Taylor to x^12; the angle stays below 1.42). */
static float DriveOnePoleG(float hz, float fs) {
  const float top = kMaxOfRate * fs;
  if (hz > top) hz = top;
  const float x = kPi * hz / fs, x2 = x * x;
  const float s = x * (1.0f - x2 * (1.0f / 6.0f - x2 * (1.0f / 120.0f - x2 * (1.0f / 5040.0f -
                  x2 * (1.0f / 362880.0f - x2 * (1.0f / 39916800.0f))))));
  const float c = 1.0f - x2 * (0.5f - x2 * (1.0f / 24.0f - x2 * (1.0f / 720.0f - x2 *
                  (1.0f / 40320.0f - x2 * (1.0f / 3628800.0f - x2 * (1.0f / 479001600.0f))))));
  return s / (s + c);
}

/* ---------------------------------------------------------------------- */
/* The instance                                                            */
/* ---------------------------------------------------------------------- */

typedef struct DriveChannel {
  float u0;                 /* the shaper's previous input */
  float pre, post;          /* pre- and de-emphasis one-pole states */
  float dc_x1, dc_y1;       /* DC blocker */
  float tilt;               /* tilt one-pole state */
} DriveChannel;

typedef struct DriveInstance {
  float param[P_COUNT];     /* knob values, clamped */
  float target[S_COUNT];    /* control values the knobs ask for */
  float value[S_COUNT];     /* control values in use (gliding to target) */
  float sample_rate;
  float glide;              /* one-pole coefficient of the glide */
  float dc_r;               /* DC blocker pole */
  float g_emph, g_tilt;     /* one-pole G of the emphasis and the tilt */
  float emph_k;             /* value[S_EMPH] the next two were made for */
  float emph_kk, emph_inv;  /* k (1 - G) and 1 / (1 + k (1 - G)) */
  float level, comp;        /* Level as a gain; Auto's gain */
  float fade, fade_step;    /* Type crossfade, 0..1 */
  float dc_bias, dc_gate;   /* the values dc_from and dc_to were made for */
  float dc_from, dc_to;     /* the shaper of silence, per Type of the fade */
  int dc_type_from, dc_type_to;
  int type_target, type_from, type_to;
  int dirty;                /* Auto's gain needs computing */
  int primed;               /* 0 until the first render */
  DriveChannel ch[2];
} DriveInstance;

static inline float DriveGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

static inline float DriveFlush(float v) {
  return fabsf(v) < kFlush ? 0.0f : v;
}

/* One step of the glide; snaps when within 1e-4 (relative), so a value
 * reaches its target exactly instead of stalling an ulp short of it. */
static inline float DriveGlide(float v, float t, float k) {
  const float e = t - v;
  if (fabsf(e) <= 1e-4f * (1.0f + fabsf(t))) return t;
  return v + k * e;
}

static inline int DriveTypeOf(float v) {
  const int i = (int)floorf(v + 0.5f);
  return i < 0 ? 0 : (i >= T_COUNT ? T_COUNT - 1 : i);
}

/* Auto's gain: the reference sine's level over the AC level of what the
 * static shaper makes of it, by a 64-point quadrature (16 values of |sin|,
 * each at four phases). */
static float DriveAutoGain(int type, float gain, float gate, float bias) {
  const DriveCurve *c = &kCurves[type];
  const float t = gate + c->gate, b = bias + c->bias;
  const float silence = DriveShaper(c, 0.0f, 0.0f, t, b);
  float sum = 0.0f, sum2 = 0.0f;
  for (int k = 0; k < 16; ++k) {
    const float v = kRefAmp * gain * kQuadSin[k];
    const float yp = DriveShaper(c, v, v, t, b) - silence;
    const float yn = DriveShaper(c, -v, -v, t, b) - silence;
    sum += yp + yn;
    sum2 += yp * yp + yn * yn;
  }
  const float mean = sum * (1.0f / 32.0f);
  const float power = sum2 * (1.0f / 32.0f) - mean * mean;
  const float want = 0.5f * kRefAmp * kRefAmp;
  if (!(power * (kCompMax * kCompMax) > want)) return kCompMax;
  const float comp = sqrtf(want / power);
  return comp < kCompMin ? kCompMin : comp;
}

static void DriveSetTarget(DriveInstance *self, int index) {
  const float v = self->param[index];
  switch (index) {
    case P_TYPE:
      self->type_target = DriveTypeOf(v);
      self->target[S_EMPH] = self->type_target == T_TAPE ? kEmphBoost : 0.0f;
      self->dirty = 1;
      break;
    case P_DRIVE: self->target[S_GAIN] = DriveDbToGain(v); self->dirty = 1; break;
    case P_BIAS: self->target[S_BIAS] = v; self->dirty = 1; break;
    case P_GATE: self->target[S_GATE] = kGateScale * v; self->dirty = 1; break;
    case P_LEVEL: self->level = DriveDbToGain(v); self->dirty = 1; break;
    case P_AUTO: self->dirty = 1; break;
    case P_MIX: self->target[S_MIX] = v; break;
    case P_TONE: {
      const float lo = v > 0.5f ? DriveExp2(-kTiltOctaves * (2.0f * v - 1.0f)) : 1.0f;
      const float hi = v < 0.5f ? DriveExp2(-kTiltOctaves * (1.0f - 2.0f * v)) : 1.0f;
      self->target[S_TILT_LO] = lo;
      self->target[S_TILT_HI] = hi;
      break;
    }
    default: break;
  }
}

/* Auto's gain for the values the knobs ask for, folded into S_OUT. */
static void DriveUpdateOut(DriveInstance *self) {
  self->comp = self->param[P_AUTO] > 0.5f
      ? DriveAutoGain(self->type_target, self->target[S_GAIN], self->target[S_GATE],
                      self->target[S_BIAS])
      : 1.0f;
  self->target[S_OUT] = self->level * self->comp;
  self->dirty = 0;
}

/* What depends on gliding values: the shaper of silence for the Types of the
 * fade, and the de-emphasis for the emphasis amount. Recomputed only when
 * those values have moved. */
static void DriveUpdateDerived(DriveInstance *self) {
  const float bias = self->value[S_BIAS], gate = self->value[S_GATE];
  if (bias != self->dc_bias || gate != self->dc_gate || self->type_from != self->dc_type_from ||
      self->type_to != self->dc_type_to) {
    const DriveCurve *cf = &kCurves[self->type_from], *ct = &kCurves[self->type_to];
    self->dc_bias = bias;
    self->dc_gate = gate;
    self->dc_type_from = self->type_from;
    self->dc_type_to = self->type_to;
    /* The same function, on the same values, as the per-sample path sees for
     * silence: the difference is exactly zero. */
    self->dc_from = DriveShaper(cf, 0.0f, 0.0f, gate + cf->gate, bias + cf->bias);
    self->dc_to = DriveShaper(ct, 0.0f, 0.0f, gate + ct->gate, bias + ct->bias);
  }
  const float k = self->value[S_EMPH];
  if (k != self->emph_k) {
    self->emph_k = k;
    self->emph_kk = k * (1.0f - self->g_emph);
    self->emph_inv = 1.0f / (1.0f + self->emph_kk);
  }
}

/* Everything at its target at once: create, and the first render. */
static void DriveSnap(DriveInstance *self) {
  if (self->dirty) DriveUpdateOut(self);
  for (int s = 0; s < S_COUNT; ++s) self->value[s] = self->target[s];
  self->type_from = self->type_to = self->type_target;
  self->fade = 0.0f;
  self->dc_type_from = -1;                 /* force the derived values */
  self->emph_k = -1.0f;
  DriveUpdateDerived(self);
  for (int c = 0; c < 2; ++c) self->ch[c].u0 = 0.0f;
}

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t DriveInstanceSize(const fm1_host_t *host) {
  (void)host;
  return (sizeof(DriveInstance) + 15u) & ~(size_t)15u;
}

static void *DriveCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;
  DriveInstance *self = (DriveInstance *)mem;
  memset(self, 0, sizeof(*self));
  self->sample_rate = fs;
  self->glide = 1.0f - DriveExp2(-kLog2e / (kSmoothSeconds * fs));
  self->dc_r = DriveExp2(-2.0f * kPi * kDcHz * kLog2e / fs);
  self->g_emph = DriveOnePoleG(kEmphHz, fs);
  self->g_tilt = DriveOnePoleG(kTiltHz, fs);
  self->fade_step = 1.0f / (kFadeSeconds * fs);
  for (int i = 0; i < P_COUNT; ++i) {
    self->param[i] = kDriveParams[i].def;
    DriveSetTarget(self, i);
  }
  DriveSnap(self);
  self->primed = 0;
  return self;
}

static void DriveDestroy(void *self) { (void)self; }

static void DriveSet(void *s, uint16_t index, float v) {
  DriveInstance *self = (DriveInstance *)s;
  if (index >= P_COUNT) return;
  self->param[index] = fm1_param_clamp(&kDriveParams[index], v);
  DriveSetTarget(self, index);
}

static void DriveRender(void *s, float *lr, uint32_t frames) {
  DriveInstance *self = (DriveInstance *)s;
  if (self->dirty) DriveUpdateOut(self);
  if (!self->primed) {
    /* Settings made before the first block apply from its first sample. */
    DriveSnap(self);
    self->primed = 1;
  }
  /* The per-channel state lives in locals for the block: lr may alias any
   * float, so working through self would reload it after every store. */
  DriveChannel ch[2] = { self->ch[0], self->ch[1] };
  const float glide = self->glide, dc_r = self->dc_r;
  const float ge = self->g_emph, gt = self->g_tilt;
  for (uint32_t f = 0; f < frames; ++f) {
    int moving = 0;
    for (int k = 0; k < S_COUNT; ++k) {
      if (self->value[k] != self->target[k]) {
        self->value[k] = DriveGlide(self->value[k], self->target[k], glide);
        moving = 1;
      }
    }
    /* A new Type waits for a running crossfade to finish (at most 5 ms). */
    if (self->type_from == self->type_to && self->type_target != self->type_to) {
      self->type_to = self->type_target;
      self->fade = 0.0f;
    }
    if (self->type_from != self->type_to) {
      self->fade += self->fade_step;
      if (self->fade >= 1.0f) {
        self->type_from = self->type_to;
        self->fade = 0.0f;
      }
      moving = 1;
    }
    if (moving) DriveUpdateDerived(self);

    const DriveCurve *cf = &kCurves[self->type_from], *ct = &kCurves[self->type_to];
    const int fading = self->type_from != self->type_to;
    const float w = self->fade;
    const float gain = self->value[S_GAIN], mix = self->value[S_MIX];
    const float out = self->value[S_OUT];
    const float tl = self->value[S_TILT_LO], th = self->value[S_TILT_HI];
    const float bias = self->value[S_BIAS], gate = self->value[S_GATE];
    const float tf = gate + cf->gate, bf = bias + cf->bias;
    const float tt = gate + ct->gate, bt = bias + ct->bias;
    const float k = self->value[S_EMPH], kk = self->emph_kk, inv = self->emph_inv;
    const float silence = fading ? self->dc_from + w * (self->dc_to - self->dc_from)
                                 : self->dc_from;
    for (int c = 0; c < 2; ++c) {
      DriveChannel *h = &ch[c];
      const float x = DriveGuard(lr[2 * f + c]);
      const float vp = (x - h->pre) * ge;                    /* pre-emphasis */
      const float lp = vp + h->pre;
      h->pre = DriveFlush(lp + vp);
      const float u1 = gain * (x + k * (x - lp));
      float m = DriveShaper(cf, h->u0, u1, tf, bf);
      if (fading) {
        const float m2 = DriveShaper(ct, h->u0, u1, tt, bt);
        m = m + w * (m2 - m);
      }
      h->u0 = u1;
      const float d = (m - silence + kk * h->post) * inv;    /* de-emphasis */
      const float vd = (d - h->post) * ge;
      h->post = DriveFlush(vd + h->post + vd);
      const float y = d - h->dc_x1 + dc_r * h->dc_y1;        /* DC blocker */
      h->dc_x1 = d;
      h->dc_y1 = DriveFlush(y);
      const float vt = (y - h->tilt) * gt;                   /* tilt */
      const float lt = vt + h->tilt;
      h->tilt = DriveFlush(lt + vt);
      const float wet = tl * lt + th * (y - lt);
      lr[2 * f + c] = x + mix * (out * wet - x);
    }
  }
  self->ch[0] = ch[0];
  self->ch[1] = ch[1];
}

#ifdef __cplusplus
extern "C" {
#endif

extern const fm1_engine_t fm1_engine_drive;
const fm1_engine_t fm1_engine_drive = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "drive", "Drive",
  "This repository (MIT): overdrive and saturation curves written here; "
  "anti-aliasing after Parker, Zavalishin and Le Bivic (DAFx-16)",
  kDriveParams, P_COUNT, 0,
  DriveInstanceSize, DriveCreate, DriveDestroy,
  NULL, NULL, NULL,
  DriveSet, DriveRender,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
  NULL,                     // API v4: no get_param, the host keeps its values
};

#ifdef __cplusplus
}
#endif
