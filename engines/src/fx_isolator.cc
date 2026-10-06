/* fx_isolator.cc -- "Isolator": a three-band DJ kill EQ (FM1_KIND_AUDIO_FX),
 * written for this repository. Notes in engines/README.md ("Isolator").
 *
 * Per channel and per sample:
 *
 *   guard -> Linkwitz-Riley split at Low Xover (f1) and High Xover (f2)
 *         -> low x Low + mid x Mid + high x High (Kill zeroes a band)
 *         -> crossfade from the input while every band is at unity
 *
 * The split is the three-band Linkwitz-Riley tree of Faust's crossover3LR4
 * (filters.lib, STK-4.3; the structure only, no code taken), with
 * fourth-order (24 dB/octave) Linkwitz-Riley crossovers, each a pair of
 * Butterworth second-order sections:
 *
 *   low  = AP2(f2)  (LR4-LP(f1) (x))
 *   mid  = LR4-LP(f2) (LR4-HP(f1) (x))
 *   high = LR4-HP(f2) (LR4-HP(f1) (x))
 *
 * LR4-LP + LR4-HP at one frequency is the second-order all-pass AP2 with
 * Q = 1/sqrt(2), so the bands sum to AP2(f1) AP2(f2) x: flat in magnitude,
 * shifted in phase. AP2(f2) on the low band is what makes that sum hold.
 * Each second-order section is Zavalishin's topology-preserving
 * (trapezoidal) state-variable filter, Cytomic's form (Andrew Simper's
 * equations, public domain): one update gives low-pass, band-pass and
 * high-pass at once, so a crossover's first section serves both its LR4
 * low-pass and high-pass, and the all-pass is x - 2k bp. That is 7 SVF
 * updates per channel per sample: 3 for f1, 3 for f2, 1 all-pass. Every
 * section shares its crossover's g, and the trapezoidal rule maps the analog
 * identities to the digital ones exactly, so the flat sum holds in the
 * digital filter too, to float rounding. With the gains held still it is
 * linear and time-invariant; the SVF's states are integrator charges, so a
 * crossover can glide or be modulated without the jumps a direct-form
 * biquad's history would give.
 *
 *   Low, Mid, High  0..1 knobs: 0 is a true zero, 0.75 unity, 1 is +6 dB
 *                   (x2). Below unity (k / 0.75)^3, above 2^(4 (k - 0.75)).
 *   Kill            a mask: None, Low, Mid, Low+Mid, High, Low+High,
 *                   Mid+High, All (bit 0 low, bit 1 mid, bit 2 high). A
 *                   killed band's gain glides to 0 whatever its knob says;
 *                   un-killing returns it to the knob's gain.
 *   Low Xover       f1, 80-400 Hz (250).
 *   High Xover      f2, 1.5-5 kHz (2.5 kHz). Both at most 0.45 of the host
 *                   rate.
 *
 * Unity is the input, bit for bit. While all three band gains ask for
 * exactly 1 and nothing is killed (the defaults), the output is the guarded
 * input itself rather than the all-passed band sum. The filters keep
 * running, so leaving unity crossfades linearly from the input to the band
 * sum over 5 ms, and returning to unity crossfades back. The two differ only
 * in phase, so during a crossfade the sum dips briefly around the
 * crossovers: at the midpoint, for the defaults, -17 dB at f1 itself and a
 * full null where the all-passes turn the phase by half a cycle, at 228 Hz
 * and 2.73 kHz [verified 2026-10-05: the response with the crossfade held
 * at 0.5]; it is over in 5 ms.
 *
 * Idle (fm1_fx_idle.h). After 2 s at unity with the crossfade and every
 * glide landed, Isolator idles: the filters are cleared and a block is only
 * the input guard, the same bits as before. Leaving unity wakes it at the
 * next render: the crossovers land where they were set, and the gains stay
 * at unity and the output the input while the filters warm up from rest,
 * for the frames the slower crossover's Butterworth sections take to settle
 * (IsoWake); then the gains glide and the crossfade runs as above. Away from
 * unity the code below does what it did before, in the same order: the same
 * bits.
 *
 * Gains and crossovers glide (one pole, 5 ms) sample by sample, so a kill
 * does not click, any block size gives the same output, and values set
 * before the first render apply from its first sample. The crossovers glide
 * in g = tan(pi f / fs), the SVF's own coefficient, and the sections'
 * coefficients follow per sample while they move (one divide per moving
 * crossover).
 *
 * No libm. tan comes from polynomials for sin and cos written here, 2^x
 * from a polynomial, and the glide coefficient from a series; everything
 * else is +, -, *, / and comparisons. Floating-point contraction is off for
 * this file under clang (below), so a build that fuses multiply-adds
 * computes the same bits as WebAssembly, which never fuses.
 *
 * Cost per channel and sample: 7 SVF updates (12 arithmetic operations and
 * 4 comparisons each, the flushes included), the high-pass and all-pass
 * taps and the gains: about 103 operations and 28 comparisons, so about
 * 13,000 and 3,600 per 64-frame stereo block, and no divide while nothing
 * moves (one per moving crossover per frame while one glides). The filters
 * run at unity too, so that leaving it starts from warm states, until the
 * effect idles: then only the input guard, two comparisons per sample.
 * Measured on the desktop in engines/README.md.
 *
 * Contracts (fm1_engine.h): no heap, every field set in create, NaN-safe
 * parameters (fm1_param_clamp), finite output. Input guard as the Mutable
 * effects' (mi_fx.cc): NaN reads as 0 and anything beyond +/-16 is clamped,
 * so non-finite input cannot reach the state. Silence in gives exact silence
 * out at any setting. Filter states below 1e-20 flush to zero (no subnormals
 * in long tails).
 *
 * Written in the C subset of C++11 so it would build as C99 unchanged apart
 * from the extern "C" linkage below. MIT licence, like the rest of this
 * repository.
 */

#include "fm1_engine.h"
#include "fm1_fx_idle.h"

#include <stdint.h>
#include <string.h>

/* No fused multiply-adds in this file: the browser's WebAssembly cannot fuse,
 * so a native build that did would round differently. Under Apple clang's
 * default (arm64) this file's output without the pragma differs from
 * -ffp-contract=off, and with it is identical [verified, 2026-10-05,
 * fm1-isolator-test]. -ffp-contract=fast overrides the pragma, and GCC
 * ignores it: build for a GCC target with FMA with -ffp-contract=off. */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

#if defined(__GNUC__) || defined(__clang__)
#define ISO_INLINE static inline __attribute__((always_inline))
#else
#define ISO_INLINE static inline
#endif

enum { P_LOW, P_MID, P_HIGH, P_KILL, P_LOW_X, P_HIGH_X, P_COUNT };

enum { KILL_LOW = 1, KILL_MID = 2, KILL_HIGH = 4, KILL_COUNT = 8 };

static const char *const kKillNames[KILL_COUNT] = {
  "None", "Low", "Mid", "Low+Mid", "High", "Low+High", "Mid+High", "All",
};

/* Uids (API v2) are fixed: never renumber one; a new parameter takes the next
 * free uid. The FLOATs are read every sample: SMOOTH and MOD. Kill changes
 * cleanly (the gains glide), so it can be locked and modulated (MOD; a route
 * is rounded); it is not NOLOCK. The crossovers move on the LOG law
 * (fm1_engine.h, API v3). */
static const fm1_param_t kIsoParams[P_COUNT] = {
  { "Low",        FM1_PARAM_FLOAT, 0, 1, 0.75f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Low" },
  { "Mid",        FM1_PARAM_FLOAT, 0, 1, 0.75f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mid" },
  { "High",       FM1_PARAM_FLOAT, 0, 1, 0.75f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "High" },
  { "Kill",       FM1_PARAM_ENUM,  0, KILL_COUNT - 1, 0, kKillNames, 0, 4, FM1_PARAM_MOD, FM1_UNIT_NONE, "Kill" },
  { "Low Xover",  FM1_PARAM_FLOAT, 80, 400, 250, NULL, 1, 5, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_HZ, "LoXov" },
  { "High Xover", FM1_PARAM_FLOAT, 1500, 5000, 2500, NULL, 1, 6, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_HZ, "HiXov" },
};

/* The gliding control values: the three band gains and the two crossovers'
 * g. */
enum { S_LOW, S_MID, S_HIGH, S_G1, S_G2, S_COUNT };

/* The SVF sections of one channel. */
enum {
  F1_SPLIT,   /* f1's first section: its LP feeds F1_LP, its HP feeds F1_HP */
  F1_LP,      /* LR4-LP(f1) = this section's LP */
  F1_HP,      /* LR4-HP(f1) = this section's HP */
  F2_SPLIT,   /* the same three at f2, on LR4-HP(f1) */
  F2_LP,      /* the mid band */
  F2_HP,      /* the high band */
  F2_AP,      /* AP2(f2) on LR4-LP(f1): the low band */
  SVF_COUNT
};

static const float kUnityKnob = 0.75f;      /* the knob position of unity */
static const float kBoostOctaves = 4.0f;    /* 2^(4 x 0.25) = 2 at the top */
static const float kSmoothSeconds = 0.005f; /* glides and the unity crossfade */
static const float kMaxOfRate = 0.45f;      /* crossovers at most 0.45 fs */
static const float kInputLimit = 16.0f;     /* the input guard, as mi_fx.cc */
static const float kFlush = 1e-20f;         /* states below this become 0 */
static const float kK = 1.41421356237310f;  /* 1/Q, Butterworth */
static const float kTwoK = 2.82842712474619f;
static const float kPi = 3.14159265358979f;

typedef struct IsoSvf {
  float ic1, ic2;           /* integrator states (TPT SVF) */
} IsoSvf;

typedef struct IsoChannel {
  IsoSvf s[SVF_COUNT];
} IsoChannel;

typedef struct IsoCoef {
  float g, a1, a2, a3;      /* SVF coefficients for g, k = sqrt(2) */
} IsoCoef;

typedef struct IsoInstance {
  float param[P_COUNT];     /* knob values, clamped */
  float target[S_COUNT];    /* control values the knobs ask for */
  float value[S_COUNT];     /* control values in use (gliding to target) */
  float sample_rate;
  float glide;              /* one-pole step of the glides */
  float ramp;               /* the unity crossfade's step per sample */
  float wet;                /* 0: the input; 1: the band sum */
  float wet_target;
  IsoCoef c1, c2;           /* the crossovers' coefficients, for value[] */
  int primed;               /* 0 until the first render */
  /* The idle path (fm1_fx_idle.h). */
  uint32_t rest;            /* frames at unity with everything landed */
  uint32_t rest_frames;     /* FM1_IDLE_REST_SECONDS in frames */
  uint32_t warm;            /* frames of warm-up left: the gains held at unity */
  int idle;                 /* the filters are stopped; the output is the input */
  IsoChannel ch[2];
} IsoInstance;

/* ---------------------------------------------------------------------- */
/* Arithmetic without libm                                                 */
/* ---------------------------------------------------------------------- */

static inline float IsoAbs(float x) { return x < 0.0f ? -x : x; }

/* 2^f for f in [0, 1]: the Taylor series of e^(f ln 2) to degree 9 (error
 * under 1e-8 relative at f = 1); exactly 1 at f = 0. */
static float IsoExp2Unit(float f) {
  const float t = f * 0.693147181f;
  return 1.0f + t * (1.0f + t * (0.5f + t * (0.166666667f + t * (0.0416666667f +
         t * (0.00833333333f + t * (0.00138888889f + t * (0.000198412698f +
         t * (2.48015873e-05f + t * 2.75573192e-06f))))))));
}

/* tan(x) for x in [0, 1.42] (0.45 of the rate is 1.414): sin and cos from
 * their Taylor series to degrees 13 and 14 (truncation under 2e-10 at the
 * top), then one divide. */
static float IsoTan(float x) {
  const float x2 = x * x;
  const float s = x * (1.0f - x2 * (0.166666667f - x2 * (0.00833333333f - x2 *
                  (0.000198412698f - x2 * (2.75573192e-06f - x2 * (2.50521084e-08f -
                  x2 * 1.60590438e-10f))))));
  const float c = 1.0f - x2 * (0.5f - x2 * (0.0416666667f - x2 * (0.00138888889f - x2 *
                  (2.48015873e-05f - x2 * (2.75573192e-07f - x2 * (2.08767570e-09f -
                  x2 * 1.14707456e-11f))))));
  return s / c;
}

/* The one-pole step for a time constant of n samples, 1 - e^(-1/n), from its
 * series; n >= 40 here (5 ms at 8 kHz), so a = 1/n <= 0.025 and the terms
 * to a^6 leave an error under 1e-15. */
static float IsoOnePole(float n) {
  const float a = 1.0f / n;
  return a * (1.0f - a * (0.5f - a * (0.166666667f - a * (0.0416666667f -
         a * (0.00833333333f - a * 0.00138888889f)))));
}

/* ---------------------------------------------------------------------- */
/* Controls                                                                */
/* ---------------------------------------------------------------------- */

static inline float IsoGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

static inline float IsoFlush(float v) {
  return (v > -kFlush && v < kFlush) ? 0.0f : v;
}

/* A band knob's gain: 0 at 0, (k / 0.75)^3 up to unity at 0.75 (exactly 1),
 * then 2^(4 (k - 0.75)) up to 2 (+6.02 dB) at 1. */
static float IsoBandGain(float k) {
  if (k <= kUnityKnob) {
    const float t = k / kUnityKnob;
    return t * t * t;
  }
  return IsoExp2Unit(kBoostOctaves * (k - kUnityKnob));
}

/* A crossover's g for f Hz, capped at 0.45 of the rate. */
static float IsoG(float hz, float rate) {
  const float top = kMaxOfRate * rate;
  if (hz > top) hz = top;
  return IsoTan(kPi * hz / rate);
}

static inline int IsoKill(const IsoInstance *self) {
  return (int)(self->param[P_KILL] + 0.5f);   /* clamped to 0..7 */
}

static void IsoSetTargets(IsoInstance *self) {
  const int kill = IsoKill(self);
  self->target[S_LOW] = (kill & KILL_LOW) ? 0.0f : IsoBandGain(self->param[P_LOW]);
  self->target[S_MID] = (kill & KILL_MID) ? 0.0f : IsoBandGain(self->param[P_MID]);
  self->target[S_HIGH] = (kill & KILL_HIGH) ? 0.0f : IsoBandGain(self->param[P_HIGH]);
  self->target[S_G1] = IsoG(self->param[P_LOW_X], self->sample_rate);
  self->target[S_G2] = IsoG(self->param[P_HIGH_X], self->sample_rate);
  /* The input itself while every band asks for exactly unity. */
  const int unity = self->target[S_LOW] == 1.0f && self->target[S_MID] == 1.0f &&
                    self->target[S_HIGH] == 1.0f;
  self->wet_target = unity ? 0.0f : 1.0f;
}

static void IsoUpdateCoef(IsoCoef *c, float g) {
  c->g = g;
  c->a1 = 1.0f / (1.0f + g * (g + kK));
  c->a2 = g * c->a1;
  c->a3 = g * c->a2;
}

/* One step of a gain's glide; snaps when within 1e-4 (relative), so a value
 * reaches its target exactly instead of stalling an ulp short of it. */
static inline float IsoGlideGain(float v, float t, float k) {
  const float e = t - v;
  if (IsoAbs(e) <= 1e-4f * (1.0f + IsoAbs(t))) return t;
  return v + k * e;
}

/* The same for a g, relative to the target alone (g is 0.006-6 at
 * 44,118 Hz). It also lands when its step is under about half an ulp of the
 * value: there a float one-pole stalls short of the target for ever (the
 * step rounds away), which a tolerance of 1e-5 alone let happen for 38 % of
 * crossover changes at 44,118 Hz and for every one at 96 kHz and above,
 * leaving the crossover off by up to 1e-4 and its coefficients recomputed
 * every frame from then on [verified 2026-10-05, review of the master-bus
 * pack]. The test is on magnitudes, as Tilt's (fx_tilt.cc), so it holds with
 * excess precision too. */
static inline float IsoGlideG(float v, float t, float k) {
  const float e = t - v;
  const float step = k * e;
  if (IsoAbs(e) <= 1e-5f * t || IsoAbs(step) <= 6e-8f * IsoAbs(v)) return t;
  return v + step;
}

/* ---------------------------------------------------------------------- */
/* The filters                                                             */
/* ---------------------------------------------------------------------- */

/* One update of a TPT SVF section with input x; returns band-pass in *bp and
 * low-pass in *lp. High-pass is x - k bp - lp, all-pass x - 2k bp. */
ISO_INLINE void IsoSvfTick(IsoSvf *s, const IsoCoef *c, float x, float *bp, float *lp) {
  const float v3 = x - s->ic2;
  const float v1 = c->a1 * s->ic1 + c->a2 * v3;
  const float v2 = s->ic2 + c->a2 * s->ic1 + c->a3 * v3;
  s->ic1 = IsoFlush(2.0f * v1 - s->ic1);
  s->ic2 = IsoFlush(2.0f * v2 - s->ic2);
  *bp = v1;
  *lp = v2;
}

/* The three bands of one channel, weighted by the gains and summed. */
ISO_INLINE float IsoBands(IsoChannel *h, const IsoCoef *c1, const IsoCoef *c2, float x,
                          float g_low, float g_mid, float g_high) {
  float bp, lp;
  IsoSvfTick(&h->s[F1_SPLIT], c1, x, &bp, &lp);
  const float lp_a = lp;
  const float hp_a = x - kK * bp - lp;
  IsoSvfTick(&h->s[F1_LP], c1, lp_a, &bp, &lp);
  const float low4 = lp;                                /* LR4-LP(f1) */
  IsoSvfTick(&h->s[F1_HP], c1, hp_a, &bp, &lp);
  const float high4 = hp_a - kK * bp - lp;              /* LR4-HP(f1) */

  IsoSvfTick(&h->s[F2_SPLIT], c2, high4, &bp, &lp);
  const float lp_b = lp;
  const float hp_b = high4 - kK * bp - lp;
  IsoSvfTick(&h->s[F2_LP], c2, lp_b, &bp, &lp);
  const float mid = lp;                                 /* LR4-LP(f2) */
  IsoSvfTick(&h->s[F2_HP], c2, hp_b, &bp, &lp);
  const float high = hp_b - kK * bp - lp;               /* LR4-HP(f2) */

  IsoSvfTick(&h->s[F2_AP], c2, low4, &bp, &lp);
  const float low = low4 - kTwoK * bp;                  /* AP2(f2) */

  return g_low * low + g_mid * mid + g_high * high;
}

/* ---------------------------------------------------------------------- */
/* The idle path (fm1_fx_idle.h)                                           */
/* ---------------------------------------------------------------------- */

#if FM1_FX_IDLE
/* What an idle Isolator outputs: the guarded input, as unity gives. */
static void IsoPass(float *lr, uint32_t frames) {
  for (uint32_t i = 0; i < 2u * frames; ++i) lr[i] = IsoGuard(lr[i]);
}

/* Leave idle: the crossovers land where they were set while the filters
 * stood, the filters start from rest (they were cleared), and the gains stay
 * at unity, with the output the input, for the warm-up: the slower of the
 * two crossovers' Butterworth sections decaying by FM1_IDLE_SETTLE_NEPERS.
 * Then they glide and the crossfade runs as when unity is left without a
 * rest. */
static void IsoWake(IsoInstance *self) {
  self->idle = 0;
  self->rest = 0;
  self->value[S_G1] = self->target[S_G1];
  self->value[S_G2] = self->target[S_G2];
  IsoUpdateCoef(&self->c1, self->value[S_G1]);
  IsoUpdateCoef(&self->c2, self->value[S_G2]);
  float d = fm1_idle_svf_decay(self->value[S_G1], kK);
  const float d2 = fm1_idle_svf_decay(self->value[S_G2], kK);
  if (d2 < d) d = d2;
  self->warm = fm1_idle_settle_frames(FM1_IDLE_SETTLE_NEPERS, d, 0x7FFFFFFFu);
}
#endif

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t IsoInstanceSize(const fm1_host_t *host) {
  (void)host;
  return (sizeof(IsoInstance) + 15u) & ~(size_t)15u;
}

static void IsoSnap(IsoInstance *self) {
  for (int k = 0; k < S_COUNT; ++k) self->value[k] = self->target[k];
  self->wet = self->wet_target;
  IsoUpdateCoef(&self->c1, self->value[S_G1]);
  IsoUpdateCoef(&self->c2, self->value[S_G2]);
}

static void *IsoCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;
  IsoInstance *self = (IsoInstance *)mem;
  memset(self, 0, sizeof(*self));
  self->sample_rate = fs;
  const float n = kSmoothSeconds * fs;   /* 40 samples or more */
  self->glide = IsoOnePole(n);
  self->ramp = 1.0f / n;
  for (int i = 0; i < P_COUNT; ++i) self->param[i] = kIsoParams[i].def;
  IsoSetTargets(self);
  IsoSnap(self);
  self->primed = 0;
  self->rest = 0;
  self->rest_frames = fm1_idle_frames_of(FM1_IDLE_REST_SECONDS, fs);
  self->warm = 0;
  self->idle = 0;
  return self;
}

static void IsoDestroy(void *self) { (void)self; }

static void IsoSet(void *s, uint16_t index, float v) {
  IsoInstance *self = (IsoInstance *)s;
  if (index >= P_COUNT) return;
  self->param[index] = fm1_param_clamp(&kIsoParams[index], v);
  IsoSetTargets(self);
}

static void IsoRender(void *s, float *lr, uint32_t frames) {
  IsoInstance *self = (IsoInstance *)s;
  if (!self->primed) {
    /* Settings made before the first block apply from its first sample. */
    IsoSnap(self);
    self->primed = 1;
  }
#if FM1_FX_IDLE
  if (self->idle) {
    if (self->wet_target == 0.0f) {     /* still unity */
      IsoPass(lr, frames);
      return;
    }
    IsoWake(self);
  }
  uint32_t warm = self->warm, rest = self->rest;
  const uint32_t rest_frames = self->rest_frames;
#endif
  /* The per-channel state lives in locals for the block: lr may alias any
   * float, so working through self would reload it after every store. */
  IsoChannel ch[2];
  ch[0] = self->ch[0];
  ch[1] = self->ch[1];
  IsoCoef c1 = self->c1, c2 = self->c2;
  float value[S_COUNT];
  for (int k = 0; k < S_COUNT; ++k) value[k] = self->value[k];
  float wet = self->wet;
  const float glide = self->glide, ramp = self->ramp, wet_target = self->wet_target;
  for (uint32_t f = 0; f < frames; ++f) {
    int moving = 0;           /* a gain or a crossover glided this frame */
    int hold = 0;             /* warming up: the gains and the input held */
#if FM1_FX_IDLE
    if (warm != 0u) {
      --warm;
      hold = 1;
    }
#endif
    if (!hold) {
      for (int k = S_LOW; k <= S_HIGH; ++k) {
        if (value[k] != self->target[k]) {
          value[k] = IsoGlideGain(value[k], self->target[k], glide);
          moving = 1;
        }
      }
    }
    if (value[S_G1] != self->target[S_G1]) {
      value[S_G1] = IsoGlideG(value[S_G1], self->target[S_G1], glide);
      IsoUpdateCoef(&c1, value[S_G1]);
      moving = 1;
    }
    if (value[S_G2] != self->target[S_G2]) {
      value[S_G2] = IsoGlideG(value[S_G2], self->target[S_G2], glide);
      IsoUpdateCoef(&c2, value[S_G2]);
      moving = 1;
    }
    const float to = hold ? 0.0f : wet_target;
    if (wet != to) {   /* a linear crossfade, landing exactly */
      if (wet < to) {
        wet += ramp;
        if (wet > to) wet = to;
      } else {
        wet -= ramp;
        if (wet < to) wet = to;
      }
    }
    for (int c = 0; c < 2; ++c) {
      const float x = IsoGuard(lr[2 * f + c]);
      const float y = IsoBands(&ch[c], &c1, &c2, x, value[S_LOW], value[S_MID],
                               value[S_HIGH]);
      float out;
      if (wet == 0.0f) out = x;
      else if (wet == 1.0f) out = y;
      else out = x + wet * (y - x);
      lr[2 * f + c] = out;
    }
#if FM1_FX_IDLE
    /* At rest: unity asked for and reached, every glide landed. */
    if (!moving && wet == 0.0f && wet_target == 0.0f) {
      if (++rest >= rest_frames) {
        /* Idle from the next frame; a wake starts the filters from rest. */
        memset(ch, 0, sizeof(ch));
        self->idle = 1;
        IsoPass(lr + 2u * (f + 1u), frames - f - 1u);
        break;
      }
    } else {
      rest = 0;
    }
#else
    (void)moving;
#endif
  }
#if FM1_FX_IDLE
  self->warm = warm;
  self->rest = rest;
#endif
  for (int k = 0; k < S_COUNT; ++k) self->value[k] = value[k];
  self->wet = wet;
  self->c1 = c1;
  self->c2 = c2;
  self->ch[0] = ch[0];
  self->ch[1] = ch[1];
}

#ifdef __cplusplus
extern "C" {
#endif

extern const fm1_engine_t fm1_engine_isolator;
const fm1_engine_t fm1_engine_isolator = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "isolator", "Isolator",
  "This repository (MIT): a three-band kill EQ with Linkwitz-Riley crossovers, "
  "the band tree after Faust's crossover3LR4 (filters.lib, STK-4.3), no code "
  "taken; TPT state-variable filters after Zavalishin and Simper (Cytomic)",
  kIsoParams, P_COUNT, 0,
  IsoInstanceSize, IsoCreate, IsoDestroy,
  NULL, NULL, NULL,
  IsoSet, IsoRender,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
};

#ifdef __cplusplus
}
#endif
