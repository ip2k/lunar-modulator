/* fx_eq.cc -- "EQ": a three-band parametric equaliser (FM1_KIND_AUDIO_FX),
 * written for this repository. Notes in engines/README.md ("EQ").
 *
 * Signal path, per channel and per sample:
 *
 *   input guard -> low shelf -> bell -> high shelf -> x Level
 *
 * Each band is one linear trapezoidal state-variable filter (two
 * integrators, solved with zero delay) whose input and band-pass and
 * low-pass outputs are mixed, in the form Andrew Simper (Cytomic) published
 * in his technical paper on the linear trapezoidal SVF
 * ("SvfLinearTrapOptimised2"), whose maths is public domain [reported:
 * notes/2026-10-02-delay-reverb-eq-gates-options.md §1, §4.1, §4.5]; the
 * integrators are those of Zavalishin's "The Art of VA Filter Design". No
 * code is taken from anywhere. With g = tan(pi f / fs), k the damping, ic1 and ic2 the two
 * integrator states and x the band's input:
 *
 *   v3 = x - ic2,  v1 = a1 ic1 + a2 v3,  v2 = ic2 + a2 ic1 + a3 v3,
 *   ic1 <- 2 v1 - ic1,  ic2 <- 2 v2 - ic2,
 *   a1 = 1 / (1 + g (g + k)),  a2 = g a1,  a3 = g a2,
 *
 * where v1 is the band-pass and v2 the low-pass output. With A = 10^(dB/40)
 * and Q the band's Q:
 *
 *   low shelf   g = tan(..) / sqrt(A), k = 1/Q:      y = x + k (A - 1) v1 + (A^2 - 1) v2
 *   bell        g = tan(..),           k = 1/(Q A):  y = x + k (A^2 - 1) v1
 *   high shelf  g = tan(..) sqrt(A),   k = 1/Q:      y = A^2 x + k (1 - A) A v1 + (1 - A^2) v2
 *
 * These are, transformed, exactly the RBJ Audio EQ Cookbook's peakingEQ,
 * lowShelf and highShelf (its shelves with Q, not S), prewarped at the
 * band's frequency: the bell peaks at A^2 (the band's gain in dB) at its
 * frequency, each shelf reaches A^2 at DC or Nyquist and A (half the dB) at
 * its frequency, and Q 0.7071 is the steepest shelf that does not overshoot
 * (tests/test_engines_eq.py measures the response against the cookbook's
 * biquads computed in double precision).
 *
 * Why this filter: the states are the integrators' charges, so new
 * coefficients change what the filter does next and not what it holds, and
 * it can be swept and modulated without the thumps a direct-form biquad
 * makes when its coefficients move (its history is only right for the old
 * ones). The cookbook is the test reference only.
 *
 * 0 dB is exact. At 0 dB A is exactly 1, every mixing coefficient is
 * exactly 0 and the band is marked flat: it passes its input itself, bit for
 * bit (the integrators keep running, so turning the gain up later starts
 * from a settled filter). All gains and Level at 0 dB pass the guarded input
 * through unchanged, whatever the frequencies and Qs.
 *
 * Idle (fm1_fx_idle.h). After 2 s with every gain and Level at 0 dB, every
 * band flat and Level landed (counted at control steps), EQ idles: the
 * integrators are cleared and a block is only the input guard, the same bits
 * as before. A gain or Level away from 0 dB wakes it at the next render: the
 * frequencies and Qs land where they were set, and each band's gain is held
 * at 0 dB (the band flat, the output still the input) for its own warm-up,
 * the frames its section at 0 dB takes to settle from rest (EqSettle); then
 * it glides as above. Level needs no filter and glides at once. Settings
 * where a band needs more than FM1_IDLE_MAX_WARM_SECONDS (a band low and
 * narrow) never idle: EQ runs there as it always has; tuned there while
 * idle, it wakes and holds the bands for at most that long. Away from
 * pass-through the code below does what it did before, in the same order:
 * the same bits.
 *
 * Control rate. Each band's frequency (as log2 Hz), gain (dB) and Q (as
 * log2 Q) glide towards their targets one step per 8 samples, counted from
 * create, not from the block, so any block size gives the same output; each
 * step moves them 1 - exp(-8 / (5 ms fs)) of the way and recomputes that
 * band's coefficients. The filter coefficients change at the step; the
 * mixing coefficients ramp linearly across the 8 samples to their new
 * values, so a gain change never steps the output. Level glides every
 * sample. Values set before the first render take effect at once.
 *
 * Determinism. No libm anywhere: 2^x, log2 and tan are the polynomials of
 * fx_eq_math.h, everything else is +, -, *, / and comparisons, and clang
 * fuses no multiply-add in this file (the pragma below), so the browser's
 * WebAssembly computes the same samples as a native build.
 *
 * Contracts (fm1_engine.h): no heap; every field set in create; NaN-safe
 * parameters (fm1_param_clamp); the input guard of mi_fx.cc (NaN reads as 0,
 * anything beyond +/-16 is clamped), so non-finite input cannot reach the
 * state; finite output. Silence in gives exact silence out at any setting
 * (a linear filter from rest). A band's two integrator states flush to zero
 * together once both are below 1e-15, so tails never run in subnormals and
 * decay to exact silence at the filter's own rate.
 *
 * Cost, per sample and channel: three filter updates (6 multiplies, 6 adds
 * and up to 4 comparisons each) and their mixes (1 to 3 multiply-adds):
 * about 60 operations, 7,700 per 64-frame stereo block, whether a band is
 * flat or not; plus, while a band glides, about 130 operations and 2
 * divides per band per 8 samples. Idle, only the input guard: two
 * comparisons per sample. Measured on the desktop in engines/README.md.
 *
 * Written in the C subset of C++11 so it would build as C99 unchanged apart
 * from the extern "C" linkage below. MIT licence, like the rest of this
 * repository.
 */

#include "fm1_engine.h"
#include "fm1_fx_idle.h"
#include "fx_eq_math.h"

#include <stdint.h>
#include <string.h>

/* No fused multiply-adds in this file: the browser's WebAssembly cannot fuse,
 * so a native build that did would round differently (Apple clang on arm64
 * fuses by default). GCC ignores the pragma: build for a GCC target with FMA
 * with -ffp-contract=off (the x86 builds here have none to use). */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

enum {
  P_LOW_FREQ, P_LOW_GAIN, P_LOW_Q,
  P_MID_FREQ, P_MID_GAIN, P_MID_Q,
  P_HIGH_FREQ, P_HIGH_GAIN, P_HIGH_Q,
  P_LEVEL,
  P_COUNT
};

enum { B_LOW, B_MID, B_HIGH, B_COUNT };

/* A band's gliding values: frequency as log2 Hz, gain in dB, log2 Q. */
enum { V_PITCH, V_DB, V_LOGQ, V_COUNT };

/* Uids (API v2) are fixed: never renumber one; a new parameter takes the next
 * free uid. Every parameter is read each block and glides: SMOOTH and MOD.
 * One page per band, in the order hardware equalisers label them
 * (frequency, gain, Q); Level fills the last page. Gains and Level are in
 * dB (FM1_UNIT_DB, API v3); the frequencies move on the LOG law
 * (fm1_engine.h). */
static const fm1_param_t kEqParams[P_COUNT] = {
  { "Low Freq",  FM1_PARAM_FLOAT, 20, 1000, 100, NULL, 0, 1, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_HZ, "LoFrq" },
  { "Low Gain",  FM1_PARAM_FLOAT, -15, 15, 0, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "LoGain" },
  { "Low Q",     FM1_PARAM_FLOAT, 0.3f, 2, 0.7071f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "LoQ" },
  { "Mid Freq",  FM1_PARAM_FLOAT, 20, 18000, 1000, NULL, 1, 4, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_HZ, "MdFrq" },
  { "Mid Gain",  FM1_PARAM_FLOAT, -15, 15, 0, NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "MdGain" },
  { "Mid Q",     FM1_PARAM_FLOAT, 0.3f, 10, 1, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "MdQ" },
  { "High Freq", FM1_PARAM_FLOAT, 1000, 18000, 8000, NULL, 2, 7, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_HZ, "HiFrq" },
  { "High Gain", FM1_PARAM_FLOAT, -15, 15, 0, NULL, 2, 8, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "HiGain" },
  { "High Q",    FM1_PARAM_FLOAT, 0.3f, 2, 0.7071f, NULL, 2, 9, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "HiQ" },
  { "Level",     FM1_PARAM_FLOAT, -15, 15, 0, NULL, 2, 10, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Level" },
};

static const uint32_t kCtrlMask = 7u;       /* a control step every 8 samples */
static const float kCtrlSamples = 8.0f;
static const float kSmoothSeconds = 0.005f; /* glide time constant */
static const float kInputLimit = 16.0f;     /* the input guard, as mi_fx.cc */
static const float kFlush = 1e-15f;         /* states below this become 0 */
static const float kMaxOfRate = 0.45f;      /* no band tuned above 0.45 fs */
static const float kPi = 3.14159265358979f;
static const float kLog2E = 1.44269504f;    /* log2(e) */
static const float kDbToLog2A = 0.0830482024f;     /* log2(10) / 40: dB -> log2 A */
static const float kDbToLog2Gain = 0.166096405f;   /* log2(10) / 20: dB -> log2 gain */

typedef struct EqBand {
  float value[V_COUNT];     /* in use, gliding to target */
  float target[V_COUNT];
  float a1, a2, a3;         /* filter coefficients (above) */
  /* The mix, as what it adds to the band's input x:
   * y = x + m[0] x + m[1] v1 + m[2] v2 (m[0] is A^2 - 1 for the high shelf
   * and 0 otherwise; m[2] is 0 for the bell). In use, its per-sample
   * increment, and where this control step's ramp ends. */
  float m[3], dm[3], m_end[3];
  int ramp;                 /* dm is not all zero */
  int flat;                 /* m and m_end all zero: the band passes its input */
  uint32_t settle;          /* idle path: frames the band takes to warm up at
                             * its target frequency and Q, at 0 dB */
  uint32_t warm;            /* frames of warm-up left: the gain held at 0 dB */
} EqBand;

typedef struct EqChannel {
  float ic1[B_COUNT], ic2[B_COUNT];
} EqChannel;

typedef struct EqInstance {
  float param[P_COUNT];     /* knob values, clamped */
  float sample_rate;
  float pi_over_fs;
  float max_pitch;          /* log2(0.45 fs) */
  float glide_ctrl;         /* one-pole coefficient per control step */
  float glide_sample;       /* ... and per sample (Level) */
  float level, level_target;  /* linear gain */
  uint32_t count;           /* samples since create (mod 2^32) */
  int primed;               /* 0 until the first render */
  /* The idle path (fm1_fx_idle.h). */
  uint32_t rest;            /* frames at pass-through, counted at control steps */
  uint32_t rest_frames;     /* FM1_IDLE_REST_SECONDS in frames */
  uint32_t max_warm;        /* FM1_IDLE_MAX_WARM_SECONDS in frames */
  int idle;                 /* the filters are stopped; the output is the input */
  int driven;               /* FM1_PARAM_DRIVEN: locks or cables, so never idle */
  int warming;              /* some band's warm is not 0 */
  int settle_stale;         /* a frequency or Q target moved: settle is old */
  EqBand band[B_COUNT];
  EqChannel ch[2];
} EqInstance;

/* ---------------------------------------------------------------------- */
/* Controls                                                                */
/* ---------------------------------------------------------------------- */

static inline float EqGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

/* A band's two states flush together, once both are below kFlush: in a
 * low band the band-pass state is far smaller than the low-pass one (about g
 * times), and flushing it alone would leave the low-pass state to leak away
 * through the tiny a3 term only (a tail at -115 dB that took minutes). */
static inline void EqStore(float *ic1, float *ic2, float n1, float n2) {
  if (n1 > -kFlush && n1 < kFlush && n2 > -kFlush && n2 < kFlush) {
    n1 = 0.0f;
    n2 = 0.0f;
  }
  *ic1 = n1;
  *ic2 = n2;
}

/* One step of a glide; snaps when within 1e-4 (relative), so a value
 * reaches its target exactly (0 dB included) instead of stalling an ulp
 * short of it. */
static inline float EqGlide(float v, float t, float k) {
  const float e = t - v;
  const float tol = 1e-4f * (1.0f + (t < 0.0f ? -t : t));
  if (e <= tol && e >= -tol) return t;
  return v + k * e;
}

static void EqSetTarget(EqInstance *self, int index) {
  const float v = self->param[index];
  if (index == P_LEVEL) {
    self->level_target = EqExp2(kDbToLog2Gain * v);
    return;
  }
  EqBand *b = &self->band[index / 3];
  switch (index % 3) {
    case 0: {
      float pitch = EqLog2(v);
      if (pitch > self->max_pitch) pitch = self->max_pitch;
      b->target[V_PITCH] = pitch;
      self->settle_stale = 1;
      break;
    }
    case 1: b->target[V_DB] = v; break;
    default:
      b->target[V_LOGQ] = EqLog2(v);
      self->settle_stale = 1;
      break;
  }
}

/* The band's filter coefficients and the end of its mixing ramp, from its
 * values in use. */
static void EqCoefs(EqInstance *self, int which) {
  EqBand *b = &self->band[which];
  const float log_a = kDbToLog2A * b->value[V_DB];
  const float a = EqExp2(log_a);                /* exactly 1 at 0 dB */
  const float a2 = a * a;
  const float g0 = EqTan(self->pi_over_fs * EqExp2(b->value[V_PITCH]));
  float g, k;
  switch (which) {
    case B_LOW:
      g = g0 * EqExp2(-0.5f * log_a);
      k = EqExp2(-b->value[V_LOGQ]);
      b->m_end[0] = 0.0f;
      b->m_end[1] = k * (a - 1.0f);
      b->m_end[2] = a2 - 1.0f;
      break;
    case B_MID:
      g = g0;
      k = EqExp2(-b->value[V_LOGQ] - log_a);
      b->m_end[0] = 0.0f;
      b->m_end[1] = k * (a2 - 1.0f);
      b->m_end[2] = 0.0f;
      break;
    default:
      g = g0 * EqExp2(0.5f * log_a);
      k = EqExp2(-b->value[V_LOGQ]);
      b->m_end[0] = a2 - 1.0f;
      b->m_end[1] = k * ((1.0f - a) * a);
      b->m_end[2] = 1.0f - a2;
      break;
  }
  b->a1 = 1.0f / (1.0f + g * (g + k));
  b->a2 = g * b->a1;
  b->a3 = g * b->a2;
}

/* Snap every value to its target, coefficients to match, no ramp: at create
 * and before the first render. */
static void EqSnap(EqInstance *self) {
  for (int i = 0; i < B_COUNT; ++i) {
    EqBand *b = &self->band[i];
    for (int v = 0; v < V_COUNT; ++v) b->value[v] = b->target[v];
    EqCoefs(self, i);
    for (int j = 0; j < 3; ++j) {
      b->m[j] = b->m_end[j];
      b->dm[j] = 0.0f;
    }
    b->ramp = 0;
    b->flat = b->m[0] == 0.0f && b->m[1] == 0.0f && b->m[2] == 0.0f;
  }
  self->level = self->level_target;
}

/* One control step (every 8 samples from create): the last ramp lands
 * exactly, the values glide, and gliding bands get new coefficients and a
 * new ramp. */
static void EqControl(EqInstance *self) {
  const float k = self->glide_ctrl;
  for (int i = 0; i < B_COUNT; ++i) {
    EqBand *b = &self->band[i];
    for (int j = 0; j < 3; ++j) b->m[j] = b->m_end[j];
    int moving = 0;
    for (int v = 0; v < V_COUNT; ++v) {
      float t = b->target[v];
#if FM1_FX_IDLE
      if (v == V_DB && b->warm != 0u) t = b->value[V_DB];   /* warming: held at 0 dB */
#endif
      if (b->value[v] != t) {
        b->value[v] = EqGlide(b->value[v], t, k);
        moving = 1;
      }
    }
    b->ramp = 0;
    if (moving) {
      EqCoefs(self, i);
      for (int j = 0; j < 3; ++j) {
        b->dm[j] = (b->m_end[j] - b->m[j]) * (1.0f / kCtrlSamples);
        if (b->dm[j] != 0.0f) b->ramp = 1;
      }
    }
    if (!b->ramp) {
      for (int j = 0; j < 3; ++j) {
        b->dm[j] = 0.0f;
        b->m[j] = b->m_end[j];
      }
    }
    b->flat = !b->ramp && b->m[0] == 0.0f && b->m[1] == 0.0f && b->m[2] == 0.0f;
  }
}

/* ---------------------------------------------------------------------- */
/* The idle path (fm1_fx_idle.h)                                           */
/* ---------------------------------------------------------------------- */

#if FM1_FX_IDLE
/* Pass-through: every gain and Level ask for 0 dB. */
static int EqNeutral(const EqInstance *self) {
  if (self->level_target != 1.0f) return 0;
  for (int i = 0; i < B_COUNT; ++i) {
    if (self->band[i].target[V_DB] != 0.0f) return 0;
  }
  return 1;
}

/* At rest, at a control step: at pass-through, every band flat with its gain
 * landed on 0 dB, and Level (the block's running value) landed on 1. */
static int EqAtRest(const EqInstance *self, float level) {
  if (level != 1.0f || !EqNeutral(self)) return 0;
  for (int i = 0; i < B_COUNT; ++i) {
    const EqBand *b = &self->band[i];
    if (!b->flat || b->value[V_DB] != 0.0f) return 0;
  }
  return 1;
}

/* Each band's warm-up at its target frequency and Q, at 0 dB, where EqCoefs
 * gives every band g = tan(pi f / fs) and k = 1/Q. */
static void EqSettle(EqInstance *self) {
  for (int i = 0; i < B_COUNT; ++i) {
    EqBand *b = &self->band[i];
    const float g = EqTan(self->pi_over_fs * EqExp2(b->target[V_PITCH]));
    const float k = EqExp2(-b->target[V_LOGQ]);
    b->settle = fm1_idle_settle_frames(FM1_IDLE_SETTLE_NEPERS, fm1_idle_svf_decay(g, k),
                                       self->max_warm);
  }
  self->settle_stale = 0;
}

/* Every band warms up within FM1_IDLE_MAX_WARM_SECONDS: these settings may
 * idle. A band low and narrow enough to need longer keeps EQ running. */
static int EqFits(EqInstance *self) {
  if (self->settle_stale) EqSettle(self);
  for (int i = 0; i < B_COUNT; ++i) {
    if (self->band[i].settle > self->max_warm) return 0;
  }
  return 1;
}

/* What an idle EQ outputs: the guarded input, as every band flat and Level
 * at 0 dB give. */
static void EqPass(float *lr, uint32_t frames) {
  for (uint32_t i = 0; i < 2u * frames; ++i) lr[i] = EqGuard(lr[i]);
}

/* Leave idle: the frequencies and Qs land where they were set while the
 * filters stood (nothing played them), the integrators start from rest (they
 * were cleared), and each band's gain is held at 0 dB for its warm-up. Level
 * needs no filter and glides at once. */
static void EqWake(EqInstance *self) {
  if (self->settle_stale) EqSettle(self);
  self->idle = 0;
  self->rest = 0;
  self->warming = 0;
  for (int i = 0; i < B_COUNT; ++i) {
    EqBand *b = &self->band[i];
    b->value[V_PITCH] = b->target[V_PITCH];
    b->value[V_LOGQ] = b->target[V_LOGQ];
    EqCoefs(self, i);                       /* at 0 dB: m_end is all 0 */
    for (int j = 0; j < 3; ++j) {
      b->m[j] = b->m_end[j];
      b->dm[j] = 0.0f;
    }
    b->ramp = 0;
    b->flat = 1;
    b->warm = b->settle > self->max_warm ? self->max_warm : b->settle;
    if (b->warm != 0u) self->warming = 1;
  }
}

/* Count down the warm-ups by a run of frames. */
static void EqWarmBy(EqInstance *self, uint32_t run) {
  int warming = 0;
  for (int i = 0; i < B_COUNT; ++i) {
    EqBand *b = &self->band[i];
    b->warm = b->warm > run ? b->warm - run : 0u;
    if (b->warm != 0u) warming = 1;
  }
  self->warming = warming;
}
#endif

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t EqInstanceSize(const fm1_host_t *host) {
  (void)host;
  return (sizeof(EqInstance) + 15u) & ~(size_t)15u;
}

static void *EqCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;   /* NaN fails too */
  EqInstance *self = (EqInstance *)mem;
  memset(self, 0, sizeof(*self));
  self->sample_rate = fs;
  self->pi_over_fs = kPi / fs;
  self->max_pitch = EqLog2(kMaxOfRate * fs);
  self->glide_ctrl = 1.0f - EqExp2(-kLog2E * kCtrlSamples / (kSmoothSeconds * fs));
  self->glide_sample = 1.0f - EqExp2(-kLog2E / (kSmoothSeconds * fs));
  for (int i = 0; i < P_COUNT; ++i) {
    self->param[i] = kEqParams[i].def;
    EqSetTarget(self, i);
  }
  EqSnap(self);
  self->count = 0;
  self->primed = 0;
  self->rest = 0;
  self->rest_frames = fm1_idle_frames_of(FM1_IDLE_REST_SECONDS, fs);
  self->max_warm = fm1_idle_frames_of(FM1_IDLE_MAX_WARM_SECONDS, fs);
  self->idle = 0;
  self->warming = 0;
  self->settle_stale = 1;
  return self;
}

static void EqDestroy(void *self) { (void)self; }

static void EqSet(void *s, uint16_t index, float v) {
  EqInstance *self = (EqInstance *)s;
  if (index == FM1_PARAM_DRIVEN) {      /* the host's word: never idle (fm1_engine.h) */
    self->driven = v != 0.0f && v == v;
    return;
  }
  if (index >= P_COUNT) return;
  self->param[index] = fm1_param_clamp(&kEqParams[index], v);
  EqSetTarget(self, index);
}

static void EqRender(void *s, float *lr, uint32_t frames) {
  EqInstance *self = (EqInstance *)s;
  if (!self->primed) {
    /* Settings made before the first block apply from its first sample. */
    EqSnap(self);
    self->primed = 1;
  }
#if FM1_FX_IDLE
  if (self->idle) {
    if (!self->driven && EqNeutral(self) && EqFits(self)) {
      EqPass(lr, frames);
      self->count += frames;
      return;
    }
    EqWake(self);
  }
#endif
  /* The per-channel states live in locals for the block: lr may alias any
   * float, so working through self would reload them after every store. */
  EqChannel ch[2] = { self->ch[0], self->ch[1] };
  float level = self->level;
  const float level_target = self->level_target, glide1 = self->glide_sample;
  uint32_t f = 0;
  while (f < frames) {
    if ((self->count & kCtrlMask) == 0u) {
      EqControl(self);
#if FM1_FX_IDLE
      if (!self->driven && EqAtRest(self, level)) {
        if (self->rest < self->rest_frames) self->rest += kCtrlMask + 1u;
        if (self->rest >= self->rest_frames && EqFits(self)) {
          /* Idle from here; a wake starts the integrators from rest. */
          memset(ch, 0, sizeof(ch));
          self->idle = 1;
          EqPass(lr + 2u * f, frames - f);
          self->count += frames - f;
          break;
        }
      } else {
        self->rest = 0;
      }
#endif
    }
    /* Up to the next control step, the coefficients are fixed but for the
     * mixing ramps. */
    uint32_t run = kCtrlMask + 1u - (self->count & kCtrlMask);
    if (run > frames - f) run = frames - f;
    self->count += run;
#if FM1_FX_IDLE
    if (self->warming) EqWarmBy(self, run);
#endif
    EqBand *lo = &self->band[B_LOW], *mi = &self->band[B_MID], *hi = &self->band[B_HIGH];
    const float la1 = lo->a1, la2 = lo->a2, la3 = lo->a3;
    const float ma1 = mi->a1, ma2 = mi->a2, ma3 = mi->a3;
    const float ha1 = hi->a1, ha2 = hi->a2, ha3 = hi->a3;
    float lm1 = lo->m[1], lm2 = lo->m[2];
    float mm1 = mi->m[1];
    float hm0 = hi->m[0], hm1 = hi->m[1], hm2 = hi->m[2];
    const float ld1 = lo->dm[1], ld2 = lo->dm[2], md1 = mi->dm[1];
    const float hd0 = hi->dm[0], hd1 = hi->dm[1], hd2 = hi->dm[2];
    const int lflat = lo->flat, mflat = mi->flat, hflat = hi->flat;
    const int lramp = lo->ramp, mramp = mi->ramp, hramp = hi->ramp;
    for (uint32_t i = 0; i < run; ++i, ++f) {
      if (level != level_target) level = EqGlide(level, level_target, glide1);
      if (lramp) { lm1 = lm1 + ld1; lm2 = lm2 + ld2; }
      if (mramp) { mm1 = mm1 + md1; }
      if (hramp) { hm0 = hm0 + hd0; hm1 = hm1 + hd1; hm2 = hm2 + hd2; }
      for (int c = 0; c < 2; ++c) {
        EqChannel *h = &ch[c];
        const float x = EqGuard(lr[2 * f + c]);
        float y = x;
        { /* low shelf */
          const float v3 = y - h->ic2[B_LOW];
          const float v1 = la1 * h->ic1[B_LOW] + la2 * v3;
          const float v2 = h->ic2[B_LOW] + la2 * h->ic1[B_LOW] + la3 * v3;
          EqStore(&h->ic1[B_LOW], &h->ic2[B_LOW], 2.0f * v1 - h->ic1[B_LOW], 2.0f * v2 - h->ic2[B_LOW]);
          if (!lflat) y = y + (lm1 * v1 + lm2 * v2);
        }
        { /* bell */
          const float v3 = y - h->ic2[B_MID];
          const float v1 = ma1 * h->ic1[B_MID] + ma2 * v3;
          const float v2 = h->ic2[B_MID] + ma2 * h->ic1[B_MID] + ma3 * v3;
          EqStore(&h->ic1[B_MID], &h->ic2[B_MID], 2.0f * v1 - h->ic1[B_MID], 2.0f * v2 - h->ic2[B_MID]);
          if (!mflat) y = y + mm1 * v1;
        }
        { /* high shelf */
          const float v3 = y - h->ic2[B_HIGH];
          const float v1 = ha1 * h->ic1[B_HIGH] + ha2 * v3;
          const float v2 = h->ic2[B_HIGH] + ha2 * h->ic1[B_HIGH] + ha3 * v3;
          EqStore(&h->ic1[B_HIGH], &h->ic2[B_HIGH], 2.0f * v1 - h->ic1[B_HIGH], 2.0f * v2 - h->ic2[B_HIGH]);
          if (!hflat) y = y + (hm0 * y + hm1 * v1 + hm2 * v2);
        }
        lr[2 * f + c] = y * level;
      }
    }
    lo->m[1] = lm1; lo->m[2] = lm2;
    mi->m[1] = mm1;
    hi->m[0] = hm0; hi->m[1] = hm1; hi->m[2] = hm2;
  }
  self->level = level;
  self->ch[0] = ch[0];
  self->ch[1] = ch[1];
}

#ifdef __cplusplus
extern "C" {
#endif

extern const fm1_engine_t fm1_engine_eq;
const fm1_engine_t fm1_engine_eq = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "eq", "EQ",
  "This repository (MIT): low shelf, bell and high shelf on the trapezoidal "
  "state-variable filter in the form Andrew Simper (Cytomic) published "
  "(public domain), no code taken; tested against the RBJ Audio EQ Cookbook",
  kEqParams, P_COUNT, 0,
  EqInstanceSize, EqCreate, EqDestroy,
  NULL, NULL, NULL,
  EqSet, EqRender,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
};

#ifdef __cplusplus
}
#endif
