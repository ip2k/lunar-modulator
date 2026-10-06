/* fx_filter.cc -- "Filter": a multimode filter audio effect
 * (FM1_KIND_AUDIO_FX) with six types, written for this repository. Notes
 * in engines/README.md ("Filter"). Comb, its seventh type until 2026-10-05,
 * is an effect of its own now (fx_comb.cc), so a Filter instance holds no
 * delay line: 656 bytes where it took 18,368 at 44,118 Hz.
 *
 * Signal path, per channel and per sample:
 *
 *   input guard -> x Drive -> the selected type (two types crossfading for
 *   5 ms after a Type change) -> make-up gain -> x Level -> Mix with the dry
 *
 * Parameters. Page 1: Type, Cutoff (20 Hz..18 kHz, on the LOG law of engine
 * API v3), Resonance, Drive. Page 2: Mode (0..3, continuous, its meaning per
 * type), Morph (0..1: stereo Spread for the five analogue-style types, the
 * vowel for Formant), Mix, Level (0..2).
 *
 * The types. Each is solved with zero-delay feedback where it has feedback
 * (Zavalishin, "The Art of VA Filter Design", rev. 2: trapezoidal
 * integrators with the bilinear transform's frequency prewarped, so the
 * resonance lands on Cutoff exactly). Where a saturating curve sits inside
 * a loop, the loop is solved as a linear system with the curve replaced by
 * its secant gain (curve / input) at the previous sample's operating point
 * (the "cheap non-linear zero-delay filter" method Teemu Voipio published
 * on the KVR forum in 2012); then the true curve is applied once to the
 * solved value and the stages advance with it, so every state stays bounded
 * however hard the loop is driven. SVF, Ladder and Diode solve once per
 * sample. Sallen-Key and SK Mixed, whose curves sit deeper in the loop, take
 * the secant again at that first solution and solve a second time: a fixed
 * single refinement, never a convergence loop. Without it their
 * self-oscillation drifted up to 75 cents sharp above 5 kHz [verified].
 *
 *   SVF      Two trapezoidal integrators in the state-variable topology, in
 *            Andrew Simper's (Cytomic) published "linear trap" form. Mode
 *            0 low-pass, 1 band-pass, 2 high-pass, 3 notch, crossfaded in
 *            between. Resonance from Q 0.707 to self-oscillation: the
 *            damping goes slightly negative at the top of the knob and an
 *            energy term (bp^2 + lp^2, previous sample) restores it, so the
 *            oscillation settles at a fixed level, sinusoidal (the two
 *            states are in quadrature, so the energy is constant over a
 *            cycle).
 *   Ladder   Four one-pole stages with feedback from the fourth, after the
 *            transistor ladder (Moog's patent; Huovilainen, "Non-linear
 *            digital implementation of the Moog ladder filter", DAFx-04;
 *            Zavalishin ch. 5), with one saturating curve where the
 *            feedback meets the input. Mode taps the fourth, third, second
 *            or first stage: 24, 18, 12 or 6 dB/octave, crossfaded.
 *            Self-oscillates from feedback 4.
 *   Diode    A coupled four-capacitor ladder as in the TB-303's diode
 *            ladder, written here from the circuit's node equations (equal
 *            capacitors; analyses: Stinchcombe 2008, Zavalishin ch. 5):
 *              y1' = w(u - 2 y1 + y2), y2' = w(y1 - 2 y2 + y3),
 *              y3' = w(y2 - 2 y3 + y4), y4' = w(y3 - y4), u = x - k y4.
 *            Its linear part is a tridiagonal system, eliminated with
 *            coefficients that change only with the cutoff. Analysed here:
 *            the feedback oscillates at k = 18.39, at 1.195 w, and with no
 *            feedback the response is down 3 dB already at 0.119 w, so the
 *            corner moves 3.3 octaves as the resonance rises. The
 *            normalisation of w follows it (a fitted curve), so Cutoff
 *            sits near the -3 dB point with no resonance and is the
 *            self-oscillation pitch at full resonance. Mode taps as Ladder.
 *   Sallen-Key  A Sallen-Key low-pass: two one-poles with positive
 *            feedback through a one-pole high-pass, H = 1 / (s^2 + (2 - k) s
 *            + 1), the feedback through a saturating curve (Zavalishin
 *            ch. 5; the circuit it follows is credited in engines/README.md,
 *            "Filter"). Mode as SVF, the band-pass and high-pass taken from
 *            the same loop. Self-oscillates from k = 2.
 *   SK Mixed  An equal-component Sallen-Key whose inputs are mixed rather
 *            than its outputs (credited in engines/README.md, "Filter"). The
 *            low-pass input drives the first resistor, the band-pass input
 *            the bottom of the first capacitor (with the feedback), the
 *            high-pass input the bottom of the second. Node equations
 *            (written here): y (s^2 + (3 - K) s + 1) = L + s B + (s^2 + 2 s) H,
 *            so its high-pass input has a 6 dB/octave skirt below the
 *            corner, unlike the others' 12. Distinct from Sallen-Key in
 *            three ways: the inputs are mixed; the feedback passes an
 *            asymmetric diode clip (even harmonics); and both resistors are
 *            diodes, whose current saturates with the voltage across them,
 *            so a loud input is slew-limited and pulls the corner down: the
 *            growl. Mode 0 low-pass input, 1 band-pass, 2 high-pass, 3
 *            notch (L, -2B, H). Self-oscillates from K = 3, about 20 cents
 *            flat at every pitch: the diodes load the oscillation.
 *   Formant  Three band-passes (constant peak gain, Simper's SVF) at the
 *            first three formants of the vowels A (hod), E (head), I
 *            (heed), O (hawed), U (who'd), from Peterson and Barney's
 *            average formant frequencies (JASA 24, 1952). Morph sweeps the
 *            vowel A-E-I-O-U, Mode the voice: men 0, women 1.5, children 3.
 *            Cutoff shifts every formant by half its distance from 1 kHz in
 *            octaves; Resonance narrows them.
 *
 * Levels. Drive multiplies the input into the filter (1x to 16x, 2^(4
 * Drive)) and divides the output by the square root of that, so quiet
 * signals come out up to 12 dB louder and loud ones saturate. Every type
 * but Ladder and SK Mixed blends the soft clip into its input as Drive
 * rises; Ladder's loop saturates on its own, and SK Mixed's diodes take the
 * level (its input is bounded at +/-4 inside and its make-up falls with
 * Drive, so its small signals stay at unity). Resonance gain compensation:
 * Ladder and Diode lose bass as their feedback rises (DC gain 1 / (1 + k)),
 * so their input (and Diode's output) is raised with k; the others keep
 * their pass band, and their output is lowered as the peak grows. The pass
 * band ends 4-8 dB down at Resonance 0.9; self-oscillation peaks at 0.35 to
 * 0.65 on every type and Mode (-9 to -4 dBFS), the notches excepted.
 *
 * Determinism. No libm in the audio path or anywhere else: 2^x, log2 and
 * tan are the polynomials below (only fabsf, floorf and sqrtf, which IEEE
 * 754 defines exactly), and clang fuses no multiply-add here (the pragma
 * below), so a WebAssembly build matches the native one sample for sample.
 *
 * Control rate. The filter controls (cutoff, resonance, drive, mode, morph)
 * glide at a control rate of one step per 8 samples, counted from create,
 * not from the block, so any block size gives the same output; each step
 * moves them 1 - exp(-8 / (5 ms fs)) of the way to their target and
 * recomputes the coefficients of the running type(s). Mix and Level glide
 * every sample. A Type change starts the new type from rest, unheard, with
 * its input faded in over 5 ms, then crossfades the old type into it over 5
 * ms more (both run meanwhile): the new type's start from rest (a resonance
 * ringing up) swells instead of stepping, so a change is clean however fast
 * it comes. A change asked for meanwhile waits for the crossfade's end.
 *
 * Contracts (fm1_engine.h): no heap; every field read is set in create;
 * NaN-safe parameters
 * (fm1_param_clamp); the input guard of mi_fx.cc (NaN reads as 0, +/-16
 * clamp); finite output; silence in gives exact silence out at any setting
 * from rest. States below 1e-15 flush to zero, so tails never go subnormal.
 *
 * Written in the C subset of C++11 so it would build as C99 unchanged apart
 * from the extern "C" linkage below. MIT licence, like the rest of this
 * repository.
 */

#include "fm1_engine.h"

#include <math.h>
#include <string.h>

/* No fused multiply-adds in this file: the browser's WebAssembly cannot fuse,
 * so a native build that did would round differently (Apple clang on arm64
 * fuses by default). GCC ignores the pragma: build for a GCC target with FMA
 * with -ffp-contract=off (the x86 builds here have none to use). */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

/* 2^x, log2, the saturating curve, the guard, the flush and the glide,
 * shared with Comb; FILT_INLINE and the control-rate constants too. */
#include "fx_filter_dsp.h"

enum { P_TYPE, P_CUTOFF, P_RES, P_DRIVE, P_MODE, P_MORPH, P_MIX, P_LEVEL, P_COUNT };
/* Comb was type 5 until 2026-10-05 (fx_comb.cc now), so Formant moved from 6
 * to 5. Nothing was released, so nothing is migrated (engines/README.md,
 * "Filter"). */
enum { T_SVF, T_LADDER, T_DIODE, T_SK, T_SKMIX, T_FORMANT, T_COUNT };

/* Generic, descriptive names: what each circuit is, never a maker's or a
 * person's name (the filters they follow are credited in engines/README.md). */
static const char *const kFilterTypeNames[T_COUNT] = {
  "SVF", "Ladder", "Diode", "Sallen-Key", "SK Mixed", "Formant",
};

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every FLOAT is read each block: SMOOTH and MOD; Cutoff moves on
// the LOG law (API v3). Type warms the new type up and crossfades rather than
// cutting, so a lock or a (rounded) route may move it, however fast: MOD.
static const fm1_param_t kFilterParams[P_COUNT] = {
  { "Type",      FM1_PARAM_ENUM,  0, T_COUNT - 1, T_LADDER, kFilterTypeNames, 0, 1,
    FM1_PARAM_MOD, FM1_UNIT_NONE, "Type" },
  { "Cutoff",    FM1_PARAM_FLOAT, 20, 18000, 2000, NULL, 0, 2, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_HZ, "Cutoff" },
  { "Resonance", FM1_PARAM_FLOAT, 0, 1, 0.25f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Reso" },
  { "Drive",     FM1_PARAM_FLOAT, 0, 1, 0.0f,  NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Drive" },
  { "Mode",      FM1_PARAM_FLOAT, 0, 3, 0.0f,  NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mode" },
  { "Morph",     FM1_PARAM_FLOAT, 0, 1, 0.0f,  NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Morph" },
  { "Mix",       FM1_PARAM_FLOAT, 0, 1, 1.0f,  NULL, 1, 7, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Level",     FM1_PARAM_FLOAT, 0, 2, 1.0f,  NULL, 1, 8, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Level" },
};

/* The controls that glide at the control rate. C_PITCH is log2 of Cutoff in Hz. */
enum { C_PITCH, C_RES, C_DRIVE, C_MODE, C_MORPH, C_COUNT };

static const float kFadeSeconds = 0.005f;   /* Type crossfade */
static const float kMinHz = 10.0f;          /* lowest tuning (Cutoff 20 Hz, Spread -1 oct) */
static const float kPi = 3.14159265358979f;
static const float kSqrt2 = 1.41421356237310f;
static const float kLog2Of1k = 9.96578428f; /* log2(1000): Formant's unshifted Cutoff */

/* Resonance laws and level compensation, per type (engines/README.md has
 * the measured results: pass band, peak and self-oscillation levels). */
static const float kSvfQ0Damping = 1.41421356f; /* Resonance 0: Q 0.707 */
static const float kSvfNegDamping = 0.03f;      /* damping at Resonance 1: -0.03 */
static const float kSvfBeta = 0.1f;             /* energy term: oscillation at 0.55 */
static const float kLadderK = 4.3f;             /* feedback at Resonance 1; oscillates from 4 */
static const float kLadderBass = 0.5f;          /* input x (1 + 0.5 k) */
static const float kDiodeK = 19.3f;             /* oscillates from 18.39 */
static const float kDiodeOscK = 18.3878f;
static const float kDiodeBass = 0.05f;          /* input x (1 + 0.05 k) */
static const float kDiodeOut = 0.22f;           /* output x (1 + 0.22 k) */
static const float kDiodeLog2W0 = -3.07716f;    /* log2 of the -3 dB point at k = 0 */
static const float kDiodeLog2Span = 3.33444f;   /* to log2(1.19523), the oscillation */
/* Ladder and Diode taps: at the oscillation the 3rd, 2nd and 1st stages swing
 * R times the 4th (Ladder R = sqrt(2)^n; Diode R = |stage / y4| at s = 1.195 j:
 * 1.558, 3.611, 8.221). Each tap is divided by 1 + rho^2 (R^0.75 - 1), rho the
 * feedback over the oscillation threshold, so the pass band is untouched with
 * no resonance and self-oscillation reaches 0.35-0.6 on every tap. */
static const float kLadderTapR[4] = { 1.0f, 1.29684f, 1.68179f, 2.18102f };
static const float kDiodeTapR[4] = { 1.0f, 1.39478f, 2.61963f, 4.85516f };
static const float kSkK = 2.15f;               /* oscillates from 2 */
static const float kSkComp = 0.5f;             /* output / (1 + 0.5 k) */
static const float kSkMixK = 3.15f;           /* oscillates from 3 */
static const float kSkMixComp = 0.35f;        /* output / (1 + 0.35 K) */
static const float kSkMixDiode = 0.5f;        /* the diodes' knee: 3 (internal units) */
static const float kFormantComp = 1.6f;         /* Formant's make-up gain */

/* Peterson and Barney (1952), average F1, F2, F3 in Hz [voice][vowel][formant]:
 * men, women, children; A (hod), E (head), I (heed), O (hawed), U (who'd). */
static const float kFormantHz[3][5][3] = {
  { { 730, 1090, 2440 }, { 530, 1840, 2480 }, { 270, 2290, 3010 }, { 570, 840, 2410 }, { 300, 870, 2240 } },
  { { 850, 1220, 2810 }, { 610, 2330, 2990 }, { 310, 2790, 3310 }, { 590, 920, 2710 }, { 370, 950, 2670 } },
  { { 1030, 1370, 3170 }, { 690, 2610, 3570 }, { 370, 3200, 3730 }, { 680, 1060, 3180 }, { 430, 1170, 3260 } },
};
static const float kFormantGain[3] = { 1.0f, 0.7f, 0.45f };
static const float kFormantBwHz = 50.0f;    /* bandwidth 50 Hz + 6 % of the formant, */
static const float kFormantBwRel = 0.06f;   /* x 2^(1.5 - 3 Resonance) */

/* ---------------------------------------------------------------------- */
/* State                                                                   */
/* ---------------------------------------------------------------------- */

typedef struct { float ic1, ic2, v1, v2; } SvfCh;          /* v1, v2: last outputs */
typedef struct { float s[4]; float sigma; } LadderCh;      /* Ladder and Diode */
typedef struct { float s1, s2, s3, sigma; } SkCh;
typedef struct { float sa, sb, sigf, sig1, sig2; } SkMixCh;
typedef struct { float ic1[3], ic2[3]; } FormantCh;

typedef struct FilterCoefs {
  float in_gain, out_gain, drv;   /* Drive: into the filter, out of it, presat blend */
  /* The analogue-style types, per channel (Spread). */
  float g[2];                     /* tan(pi f / fs) */
  float G[2], G4[2];              /* Ladder, Sallen-Key: g / (1 + g) and its 4th power */
  float dg[2], dc[2][4], di[2][4], dA[2];   /* Diode: g, c_n, 1 / D_n, c1 c2 c3 c4 */
  /* Each type its own weights: two may run at once (a crossfade). */
  float svf_w[3], sk_w[3];       /* low-, band-, high-pass weights */
  float lad_w[4], dio_w[4];       /* 4-, 3-, 2-, 1-pole taps */
  float skm_w[3];                 /* SK Mixed: LP, BP, HP input weights */
  float svf_k, svf_comp;
  float lad_k, lad_cin;
  float dio_k, dio_cin, dio_cout;
  float sk_k, sk_comp;
  float skm_k, skm_comp;
  /* Formant */
  float fa1[3], fa2[3], fa3[3], famp[3];
} FilterCoefs;

typedef struct FilterInstance {
  float param[P_COUNT];           /* knob values, clamped */
  float target[C_COUNT];          /* control values the knobs ask for */
  float value[C_COUNT];           /* control values in use */
  float mix, mix_t, level, level_t;
  float sample_rate, pi_over_fs, fmax;
  float glide1, glide_ctrl;       /* one-pole coefficients: per sample, per step */
  float inv_fade;
  uint32_t fade_len, fade;        /* crossfade length and samples left */
  uint32_t warm;                  /* samples left before the fade starts (the old type alone) */
  uint32_t count;                 /* samples since create (mod 2^32) */
  int cur, prev, want;            /* the running type, the one fading out, the asked */
  int g_done;                     /* g[] matches the control values */
  int primed;
  FilterCoefs co;
  SvfCh svf[2];
  LadderCh lad[2], dio[2];
  SkCh sk[2];
  SkMixCh skm[2];
  FormantCh frm[2];
} FilterInstance;

/* ---------------------------------------------------------------------- */
/* Arithmetic: no libm                                                     */
/* ---------------------------------------------------------------------- */

/* tan(w) for 0 <= w <= 1.42 (just over 0.45 pi): sine and cosine by their
 * Taylor series to w^11 and w^12 (truncation below 2e-8), then one divide. */
static inline float FiltTan(float w) {
  const float w2 = w * w;
  const float s = w * (1.0f - w2 * (0.166666667f - w2 * (0.00833333333f - w2 * (0.000198412698f -
                  w2 * (2.75573192e-06f - w2 * 2.50521084e-08f)))));
  const float c = 1.0f - w2 * (0.5f - w2 * (0.0416666667f - w2 * (0.00138888889f -
                  w2 * (2.48015873e-05f - w2 * (2.75573192e-07f - w2 * 2.08767570e-09f)))));
  return s / c;
}

/* The same, with the negative half clipping at -0.5: a diode pair with
 * unequal knees, for SK Mixed. */
FILT_INLINE float FiltSatAsym(float v, float *secant) {
  if (v >= 0.0f) return FiltSat(v, secant);
  return 0.5f * FiltSat(2.0f * v, secant);
}

/* ---------------------------------------------------------------------- */
/* Coefficients                                                            */
/* ---------------------------------------------------------------------- */

static inline float FiltPrewarp(const FilterInstance *self, float pitch) {
  float f = FiltExp2(pitch);
  if (f < kMinHz) f = kMinHz;
  if (f > self->fmax) f = self->fmax;
  return FiltTan(f * self->pi_over_fs);
}

/* g for both channels: Morph spreads them +/-1 octave around Cutoff. */
static void FiltComputeG(FilterInstance *self) {
  if (self->g_done) return;
  const float pitch = self->value[C_PITCH], spread = self->value[C_MORPH];
  self->co.g[0] = FiltPrewarp(self, pitch - spread);
  self->co.g[1] = spread == 0.0f ? self->co.g[0] : FiltPrewarp(self, pitch + spread);
  self->g_done = 1;
}

/* SVF and Sallen-Key: low-pass (0), band-pass (1), high-pass (2), notch (3 = LP + HP). */
static void FiltTwoPoleWeights(float m, float w[3]) {
  if (m <= 1.0f) { w[0] = 1.0f - m; w[1] = m; w[2] = 0.0f; }
  else if (m <= 2.0f) { w[0] = 0.0f; w[1] = 2.0f - m; w[2] = m - 1.0f; }
  else { w[0] = m - 2.0f; w[1] = 0.0f; w[2] = 1.0f; }
}

/* Ladder and Diode: the 4th (Mode 0), 3rd, 2nd or 1st (Mode 3) stage, each
 * scaled down near self-oscillation (kLadderTapR). */
static void FiltTapWeights(float m, float rho, const float r[4], float w[4]) {
  int i = (int)m;
  if (i > 2) i = 2;
  const float t = m - (float)i;
  const float r2 = rho * rho;
  w[0] = w[1] = w[2] = w[3] = 0.0f;
  w[i] = (1.0f - t) / (1.0f + r2 * (r[i] - 1.0f));
  w[i + 1] = t / (1.0f + r2 * (r[i + 1] - 1.0f));
}

/* SK Mixed's inputs: LP (0), BP (1), HP (2), notch (3: LP - 2 BP + HP). */
static void FiltSkMixWeights(float m, float w[3]) {
  if (m <= 1.0f) { w[0] = 1.0f - m; w[1] = m; w[2] = 0.0f; }
  else if (m <= 2.0f) { w[0] = 0.0f; w[1] = 2.0f - m; w[2] = m - 1.0f; }
  else { const float t = m - 2.0f; w[0] = t; w[1] = -2.0f * t; w[2] = 1.0f; }
}

static void FiltUpdateShared(FilterInstance *self) {
  const float drive = self->value[C_DRIVE];
  self->co.in_gain = FiltDriveIn(drive);
  self->co.out_gain = FiltDriveOut(drive);
  self->co.drv = drive;
}

static void FiltUpdateCoefs(FilterInstance *self, int type) {
  FilterCoefs *k = &self->co;
  const float res = self->value[C_RES], mode = self->value[C_MODE];
  const float morph = self->value[C_MORPH];
  switch (type) {
    case T_SVF: {
      FiltComputeG(self);
      const float u = 1.0f - res, r2 = res * res, r4 = r2 * r2;
      const float d = kSvfQ0Damping * u * sqrtf(u) - kSvfNegDamping * r4 * r4;
      k->svf_k = d;
      k->svf_comp = ((d > 0.0f ? d : 0.0f) + 1.0f) / (kSvfQ0Damping + 1.0f);
      FiltTwoPoleWeights(mode, k->svf_w);
      break;
    }
    case T_LADDER: {
      FiltComputeG(self);
      for (int c = 0; c < 2; ++c) {
        const float G = k->g[c] / (1.0f + k->g[c]), G2 = G * G;
        k->G[c] = G;
        k->G4[c] = G2 * G2;
      }
      k->lad_k = kLadderK * res * sqrtf(res);
      k->lad_cin = 1.0f + kLadderBass * k->lad_k;
      const float rho = k->lad_k < 4.0f ? 0.25f * k->lad_k : 1.0f;
      FiltTapWeights(mode, rho, kLadderTapR, k->lad_w);
      break;
    }
    case T_DIODE: {
      FiltComputeG(self);
      const float kd = kDiodeK * res;
      float rho = kd * (1.0f / kDiodeOscK);
      if (rho > 1.0f) rho = 1.0f;
      const float h = 1.1f * rho / (rho + 0.1f);   /* fitted: README, "Filter" */
      const float inv_wn = FiltExp2(-(kDiodeLog2W0 + kDiodeLog2Span * h));
      for (int c = 0; c < 2; ++c) {
        const float g = k->g[c] * inv_wn;
        float *cc = k->dc[c], *ii = k->di[c];
        ii[3] = 1.0f / (1.0f + g);
        cc[3] = g * ii[3];
        ii[2] = 1.0f / (1.0f + 2.0f * g - g * cc[3]);
        cc[2] = g * ii[2];
        ii[1] = 1.0f / (1.0f + 2.0f * g - g * cc[2]);
        cc[1] = g * ii[1];
        ii[0] = 1.0f / (1.0f + 2.0f * g - g * cc[1]);
        cc[0] = g * ii[0];
        k->dg[c] = g;
        k->dA[c] = cc[0] * cc[1] * cc[2] * cc[3];
      }
      k->dio_k = kd;
      k->dio_cin = 1.0f + kDiodeBass * kd;
      k->dio_cout = 1.0f + kDiodeOut * kd;
      FiltTapWeights(mode, rho, kDiodeTapR, k->dio_w);
      break;
    }
    case T_SK: {
      FiltComputeG(self);
      for (int c = 0; c < 2; ++c) k->G[c] = k->g[c] / (1.0f + k->g[c]);
      k->sk_k = kSkK * res * sqrtf(res);
      k->sk_comp = 1.0f / (1.0f + kSkComp * k->sk_k);
      FiltTwoPoleWeights(mode, k->sk_w);
      /* The band-pass, 0.5 at its peak with no feedback, x 2; near the
       * oscillation it swings as far as the low-pass, so x 1 there. */
      const float rho = k->sk_k < 2.0f ? 0.5f * k->sk_k : 1.0f;
      k->sk_w[1] *= 2.0f / (1.0f + rho * rho);
      break;
    }
    case T_SKMIX: {
      FiltComputeG(self);
      k->skm_k = kSkMixK * res * sqrtf(res);
      /* Its input reaches +/-4 inside, four times the others' clipped
       * range: with Drive its make-up falls to a quarter, so Drive saturates
       * the diodes without raising small signals. */
      k->skm_comp = 1.0f / ((1.0f + kSkMixComp * k->skm_k) * (1.0f + 3.0f * self->value[C_DRIVE]));
      FiltSkMixWeights(mode, k->skm_w);
      break;
    }
    case T_FORMANT: {
      const float shift = FiltExp2(0.5f * (self->value[C_PITCH] - kLog2Of1k));
      const float bw_scale = FiltExp2(1.5f - 3.0f * res);
      float pv = 4.0f * morph, pu = mode * (1.0f / 1.5f);
      int iv = (int)pv, iu = (int)pu;
      if (iv > 3) iv = 3;
      if (iu > 1) iu = 1;
      const float tv = pv - (float)iv, tu = pu - (float)iu;
      for (int i = 0; i < 3; ++i) {
        const float a = kFormantHz[iu][iv][i] + tv * (kFormantHz[iu][iv + 1][i] - kFormantHz[iu][iv][i]);
        const float b = kFormantHz[iu + 1][iv][i] +
                        tv * (kFormantHz[iu + 1][iv + 1][i] - kFormantHz[iu + 1][iv][i]);
        const float f0 = a + tu * (b - a);
        float f = f0 * shift;
        if (f < kMinHz) f = kMinHz;
        if (f > self->fmax) f = self->fmax;
        float kq = (kFormantBwHz / f0 + kFormantBwRel) * bw_scale;   /* 1 / Q */
        if (kq > 2.0f) kq = 2.0f;
        const float g = FiltTan(f * self->pi_over_fs);
        const float a1 = 1.0f / (1.0f + g * (g + kq));
        k->fa1[i] = a1;
        k->fa2[i] = g * a1;
        k->fa3[i] = g * g * a1;
        k->famp[i] = kFormantGain[i] * kq * kFormantComp;   /* band-pass x 1/Q: unity peak */
      }
      break;
    }
    default: break;
  }
}

/* Put a type at rest, ready to fade in. */
static void FiltResetType(FilterInstance *self, int type) {
  switch (type) {
    case T_SVF: memset(self->svf, 0, sizeof(self->svf)); break;
    case T_LADDER:
    case T_DIODE: {
      LadderCh *h = type == T_LADDER ? self->lad : self->dio;
      for (int c = 0; c < 2; ++c) {
        h[c].s[0] = h[c].s[1] = h[c].s[2] = h[c].s[3] = 0.0f;
        h[c].sigma = 1.0f;
      }
      break;
    }
    case T_SK:
      for (int c = 0; c < 2; ++c) {
        self->sk[c].s1 = self->sk[c].s2 = self->sk[c].s3 = 0.0f;
        self->sk[c].sigma = 1.0f;
      }
      break;
    case T_SKMIX:
      for (int c = 0; c < 2; ++c) {
        self->skm[c].sa = self->skm[c].sb = 0.0f;
        self->skm[c].sigf = self->skm[c].sig1 = self->skm[c].sig2 = 1.0f;
      }
      break;
    case T_FORMANT: memset(self->frm, 0, sizeof(self->frm)); break;
    default: break;
  }
}

static void FiltStartType(FilterInstance *self, int type) {
  FiltResetType(self, type);
  FiltUpdateCoefs(self, type);
}

/* ---------------------------------------------------------------------- */
/* The types, one frame (both channels) each                               */
/* ---------------------------------------------------------------------- */

FILT_INLINE void FiltSvf(FilterInstance *self, const float xin[2], float y[2]) {
  const FilterCoefs *k = &self->co;
  for (int c = 0; c < 2; ++c) {
    SvfCh *h = &self->svf[c];
    const float x = FiltPresat(xin[c], k->drv);
    const float g = k->g[c];
    const float ke = k->svf_k + kSvfBeta * (h->v1 * h->v1 + h->v2 * h->v2);
    const float a1 = 1.0f / (1.0f + g * (g + ke));
    const float a2 = g * a1, a3 = g * a2;
    const float v3 = x - h->ic2;
    const float v1 = a1 * h->ic1 + a2 * v3;
    const float v2 = h->ic2 + a2 * h->ic1 + a3 * v3;
    h->ic1 = FiltFlush(2.0f * v1 - h->ic1);
    h->ic2 = FiltFlush(2.0f * v2 - h->ic2);
    h->v1 = FiltFlush(v1);
    h->v2 = FiltFlush(v2);
    const float hp = x - ke * v1 - v2;
    y[c] = (k->svf_w[0] * v2 + k->svf_w[1] * kSqrt2 * v1 + k->svf_w[2] * hp) * k->svf_comp;
  }
}

FILT_INLINE void FiltLadder(FilterInstance *self, const float xin[2], float y[2]) {
  const FilterCoefs *k = &self->co;
  const float kf = k->lad_k;
  for (int c = 0; c < 2; ++c) {
    LadderCh *h = &self->lad[c];
    const float G = k->G[c];
    const float x = xin[c] * k->lad_cin;
    const float S = (1.0f - G) * (((h->s[0] * G + h->s[1]) * G + h->s[2]) * G + h->s[3]);
    const float v = (x - kf * S) / (1.0f + kf * k->G4[c] * h->sigma);
    float in = FiltSat(v, &h->sigma);
    float st[4];
    for (int i = 0; i < 4; ++i) {
      const float t = G * (in - h->s[i]);
      const float o = t + h->s[i];
      h->s[i] = FiltFlush(o + t);
      st[i] = o;
      in = o;
    }
    y[c] = k->lad_w[0] * st[3] + k->lad_w[1] * st[2] + k->lad_w[2] * st[1] + k->lad_w[3] * st[0];
  }
}

FILT_INLINE void FiltDiode(FilterInstance *self, const float xin[2], float y[2]) {
  const FilterCoefs *k = &self->co;
  const float kf = k->dio_k;
  for (int c = 0; c < 2; ++c) {
    LadderCh *h = &self->dio[c];
    const float g = k->dg[c];
    const float *cc = k->dc[c], *ii = k->di[c];
    const float x = FiltPresat(xin[c], k->drv) * k->dio_cin;
    const float e4 = h->s[3] * ii[3];
    const float e3 = (h->s[2] + g * e4) * ii[2];
    const float e2 = (h->s[1] + g * e3) * ii[1];
    const float e1 = (h->s[0] + g * e2) * ii[0];
    const float B = ((cc[1] * e1 + e2) * cc[2] + e3) * cc[3] + e4;   /* y4 when u = 0 */
    const float v = (x - kf * B) / (1.0f + kf * k->dA[c] * h->sigma);
    const float u = FiltSat(v, &h->sigma);
    const float y1 = cc[0] * u + e1;
    const float y2 = cc[1] * y1 + e2;
    const float y3 = cc[2] * y2 + e3;
    const float y4 = cc[3] * y3 + e4;
    h->s[0] = FiltFlush(2.0f * y1 - h->s[0]);
    h->s[1] = FiltFlush(2.0f * y2 - h->s[1]);
    h->s[2] = FiltFlush(2.0f * y3 - h->s[2]);
    h->s[3] = FiltFlush(2.0f * y4 - h->s[3]);
    y[c] = (k->dio_w[0] * y4 + k->dio_w[1] * y3 + k->dio_w[2] * y2 + k->dio_w[3] * y1) * k->dio_cout;
  }
}

/* Sallen-Key's loop u = a + sat(k HP(LP(u))) with the curve replaced by a secant
 * gain: the predicted input of the curve. */
FILT_INLINE float FiltSkPredict(float a, float ks, float G, float H, float s2, float s3) {
  const float u = (a + ks * H * (H * s2 - s3)) / (1.0f - ks * G * H);   /* denominator >= 0.46 */
  return H * (G * u + H * s2 - s3);                                      /* HP(LP(u)) */
}

FILT_INLINE void FiltSk(FilterInstance *self, const float xin[2], float y[2]) {
  const FilterCoefs *k = &self->co;
  const float kf = k->sk_k;
  for (int c = 0; c < 2; ++c) {
    SkCh *h = &self->sk[c];
    const float G = k->G[c], H = 1.0f - G;
    const float x = FiltPresat(xin[c], k->drv);
    const float t1 = G * (x - h->s1);                 /* the first low-pass */
    const float a = t1 + h->s1;
    h->s1 = FiltFlush(a + t1);
    /* Solve with last sample's secant, take the secant there, solve again,
     * then the true curve. */
    float hp1 = FiltSkPredict(a, kf * h->sigma, G, H, h->s2, h->s3);
    FiltSat(kf * hp1, &h->sigma);
    hp1 = FiltSkPredict(a, kf * h->sigma, G, H, h->s2, h->s3);
    const float u = a + FiltSat(kf * hp1, &h->sigma);
    const float t2 = G * (u - h->s2);                 /* the second low-pass */
    const float lp = t2 + h->s2;
    h->s2 = FiltFlush(lp + t2);
    const float t3 = G * (lp - h->s3);                /* the feedback high-pass's state */
    h->s3 = FiltFlush(t3 + h->s3 + t3);
    const float bp = u - lp;                          /* s / D */
    const float hp = x - (2.0f - kf * h->sigma) * bp - lp;
    y[c] = (k->sk_w[0] * lp + k->sk_w[1] * bp + k->sk_w[2] * hp) * k->sk_comp;
  }
}

/* SK Mixed's two nodes with every curve replaced by its secant gain: the
 * input diode (g1 = g sigma1), the second diode (g2) and the feedback (kf).
 * The determinant is positive for small signals; clamped, the result is an
 * estimate for the curves, never used as a state. */
FILT_INLINE void FiltSkMixPredict(float g1, float g2, float kf, float xl, float xb, float sa,
                                    float rb, float *va, float *vb) {
  const float a11 = 1.0f + g1 + g2, a22 = 1.0f + g2;
  const float ra = g1 * xl + sa + xb;
  float det = a11 * a22 - g2 * (g2 + kf);
  if (det < 0.1f) det = 0.1f;
  const float inv = 1.0f / det;
  *va = (ra * a22 + (g2 + kf) * rb) * inv;
  *vb = (a11 * rb + g2 * ra) * inv;
}

FILT_INLINE void FiltSkMix(FilterInstance *self, const float xin[2], float y[2]) {
  const FilterCoefs *k = &self->co;
  const float K = k->skm_k;
  for (int c = 0; c < 2; ++c) {
    SkMixCh *h = &self->skm[c];
    const float g = k->g[c];
    /* Bounded at +/-4 inside: Drive pushes the diodes, not the range. */
    float sx;
    const float x = 4.0f * FiltSat(0.25f * xin[c], &sx);
    const float xl = k->skm_w[0] * x, xb = k->skm_w[1] * x, xh = k->skm_w[2] * x;
    const float g2 = g * h->sig2;                     /* the second diode, last sample's */
    const float rb = h->sb + xh;
    /* 1. Predict with last sample's secants; take the input diode's and
     * the feedback clip's secants there and predict again. */
    float vap, vbp;
    FiltSkMixPredict(g * h->sig1, g2, K * h->sigf, xl, xb, h->sa, rb, &vap, &vbp);
    FiltSat(kSkMixDiode * (xl - vap), &h->sig1);
    FiltSatAsym(vbp, &h->sigf);
    FiltSkMixPredict(g * h->sig1, g2, K * h->sigf, xl, xb, h->sa, rb, &vap, &vbp);
    /* 2. The true curves at the prediction: the input diode's current and
     * the clipped feedback, both bounded. */
    const float i1 = FiltSat(kSkMixDiode * (xl - vap), &h->sig1) * (1.0f / kSkMixDiode);
    const float fb = K * FiltSatAsym(vbp, &h->sigf);
    /* 3. Solve the rest, linear and passive (determinant 1 + 2 g2). */
    const float rf = g * i1 + h->sa + xb + fb;
    const float a22 = 1.0f + g2;
    const float inv = 1.0f / (1.0f + 2.0f * g2);
    const float va = (rf * a22 + g2 * rb) * inv;
    const float vb = (a22 * rb + g2 * rf) * inv;
    h->sa = FiltFlush(2.0f * (va - xb - fb) - h->sa);
    h->sb = FiltFlush(2.0f * (vb - xh) - h->sb);
    FiltSat(kSkMixDiode * (va - vb), &h->sig2);
    y[c] = vb * k->skm_comp;
  }
}

FILT_INLINE void FiltFormant(FilterInstance *self, const float xin[2], float y[2]) {
  const FilterCoefs *k = &self->co;
  for (int c = 0; c < 2; ++c) {
    FormantCh *h = &self->frm[c];
    const float x = FiltPresat(xin[c], k->drv);
    float acc = 0.0f;
    for (int i = 0; i < 3; ++i) {
      const float v3 = x - h->ic2[i];
      const float v1 = k->fa1[i] * h->ic1[i] + k->fa2[i] * v3;
      const float v2 = h->ic2[i] + k->fa2[i] * h->ic1[i] + k->fa3[i] * v3;
      h->ic1[i] = FiltFlush(2.0f * v1 - h->ic1[i]);
      h->ic2[i] = FiltFlush(2.0f * v2 - h->ic2[i]);
      acc += k->famp[i] * v1;
    }
    y[c] = acc;
  }
}

static void FiltProcess(FilterInstance *self, int type, const float xin[2], float y[2]) {
  switch (type) {
    case T_SVF: FiltSvf(self, xin, y); break;
    case T_LADDER: FiltLadder(self, xin, y); break;
    case T_DIODE: FiltDiode(self, xin, y); break;
    case T_SK: FiltSk(self, xin, y); break;
    case T_SKMIX: FiltSkMix(self, xin, y); break;
    case T_FORMANT: FiltFormant(self, xin, y); break;
    default: y[0] = y[1] = 0.0f; break;
  }
}

/* ---------------------------------------------------------------------- */
/* Controls                                                                */
/* ---------------------------------------------------------------------- */

static void FiltSetTarget(FilterInstance *self, int index) {
  const float v = self->param[index];
  switch (index) {
    case P_TYPE: {
      int t = (int)(v + 0.5f);
      if (t < 0) t = 0;
      if (t > T_COUNT - 1) t = T_COUNT - 1;
      self->want = t;
      break;
    }
    case P_CUTOFF: self->target[C_PITCH] = FiltLog2(v); break;
    case P_RES: self->target[C_RES] = v; break;
    case P_DRIVE: self->target[C_DRIVE] = v; break;
    case P_MODE: self->target[C_MODE] = v; break;
    case P_MORPH: self->target[C_MORPH] = v; break;
    case P_MIX: self->mix_t = v; break;
    case P_LEVEL: self->level_t = v; break;
    default: break;
  }
}

/* Everything from the targets at once: create, and the first render. */
static void FiltPrime(FilterInstance *self) {
  for (int i = 0; i < C_COUNT; ++i) self->value[i] = self->target[i];
  self->mix = self->mix_t;
  self->level = self->level_t;
  self->cur = self->prev = self->want;
  self->fade = 0;
  self->warm = 0;
  self->g_done = 0;
  FiltUpdateShared(self);
  FiltStartType(self, self->cur);
}

/* A control step: glide the filter controls and recompute what moved. */
static void FiltControl(FilterInstance *self) {
  int moved = 0;
  for (int i = 0; i < C_COUNT; ++i) {
    if (self->value[i] != self->target[i]) {
      self->value[i] = FiltGlide(self->value[i], self->target[i], self->glide_ctrl);
      moved = 1;
    }
  }
  if (!moved) return;
  self->g_done = 0;
  FiltUpdateShared(self);
  FiltUpdateCoefs(self, self->cur);
  if (self->fade) FiltUpdateCoefs(self, self->prev);
}

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t FilterInstanceSize(const fm1_host_t *host) {
  (void)host;
  return (sizeof(FilterInstance) + 15u) & ~(size_t)15u;
}

static void *FilterCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;
  FilterInstance *self = (FilterInstance *)mem;
  memset(self, 0, sizeof(*self));
  self->sample_rate = fs;
  self->pi_over_fs = kPi / fs;
  self->fmax = kMaxOfRate * fs;
  /* exp(-x) = 2^(-x / ln 2) */
  self->glide1 = 1.0f - FiltExp2(-1.4426950f / (kSmoothSeconds * fs));
  self->glide_ctrl = 1.0f - FiltExp2(-1.4426950f * kCtrlSamples / (kSmoothSeconds * fs));
  uint32_t n = (uint32_t)(kFadeSeconds * fs + 0.5f);
  self->fade_len = n > 0u ? n : 1u;
  self->inv_fade = 1.0f / (float)self->fade_len;
  for (int i = 0; i < P_COUNT; ++i) {
    self->param[i] = kFilterParams[i].def;
    FiltSetTarget(self, i);
  }
  for (int t = 0; t < T_COUNT; ++t) FiltResetType(self, t);
  FiltPrime(self);
  self->count = 0u;
  self->primed = 0;
  return self;
}

static void FilterDestroy(void *self) { (void)self; }

static void FilterSet(void *s, uint16_t index, float v) {
  FilterInstance *self = (FilterInstance *)s;
  if (index >= P_COUNT) return;
  self->param[index] = fm1_param_clamp(&kFilterParams[index], v);
  FiltSetTarget(self, index);
}

static void FilterRender(void *s, float *lr, uint32_t frames) {
  FilterInstance *self = (FilterInstance *)s;
  if (!self->primed) {
    /* Settings made before the first block apply from its first sample. */
    FiltPrime(self);
    self->primed = 1;
  }
  for (uint32_t f = 0; f < frames; ++f) {
    const uint32_t j = self->count & kCtrlMask;
    if (j == 0u) FiltControl(self);
    if (self->fade == 0u && self->want != self->cur) {
      self->prev = self->cur;
      self->cur = self->want;
      self->fade = self->fade_len;
      self->warm = self->fade_len;
      FiltStartType(self, self->cur);
    }
    if (self->mix != self->mix_t) self->mix = FiltGlide(self->mix, self->mix_t, self->glide1);
    if (self->level != self->level_t) {
      self->level = FiltGlide(self->level, self->level_t, self->glide1);
    }
    const float x[2] = { FiltGuard(lr[2 * f]), FiltGuard(lr[2 * f + 1]) };
    const float in_gain = self->co.in_gain;
    const float xin[2] = { in_gain * x[0], in_gain * x[1] };
    float y[2];
    if (self->warm) {
      /* The new type starts from rest, unheard, with its input faded in
       * over 5 ms, and only then is its output faded in. */
      const float ramp = 1.0f - (float)self->warm * self->inv_fade;
      const float xr[2] = { ramp * xin[0], ramp * xin[1] };
      FiltProcess(self, self->cur, xr, y);
    } else {
      FiltProcess(self, self->cur, xin, y);
    }
    if (self->fade) {
      float old[2];
      FiltProcess(self, self->prev, xin, old);
      if (self->warm) {
        y[0] = old[0];
        y[1] = old[1];
        --self->warm;
      } else {
        const float wc = 1.0f - (float)self->fade * self->inv_fade;
        y[0] = old[0] + wc * (y[0] - old[0]);
        y[1] = old[1] + wc * (y[1] - old[1]);
        --self->fade;
      }
    }
    const float wet = self->level * self->co.out_gain, mix = self->mix;
    lr[2 * f] = x[0] + mix * (wet * y[0] - x[0]);
    lr[2 * f + 1] = x[1] + mix * (wet * y[1] - x[1]);
    ++self->count;
  }
}

#ifdef __cplusplus
extern "C" {
#endif

extern const fm1_engine_t fm1_engine_filter;
const fm1_engine_t fm1_engine_filter = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "filter", "Filter",
  "This repository (MIT): zero-delay-feedback filters after Zavalishin's "
  "The Art of VA Filter Design, Simper's (Cytomic) SVF, Huovilainen's ladder, "
  "the Korg35, diode-ladder and Steiner-Parker circuits; vowels from "
  "Peterson and Barney (1952). No code taken",
  kFilterParams, P_COUNT, 0,
  FilterInstanceSize, FilterCreate, FilterDestroy,
  NULL, NULL, NULL,
  FilterSet, FilterRender,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
};

#ifdef __cplusplus
}
#endif
