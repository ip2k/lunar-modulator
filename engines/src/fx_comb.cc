/* fx_comb.cc -- "Comb": a comb filter audio effect (FM1_KIND_AUDIO_FX),
 * written for this repository. Notes in engines/README.md ("Comb").
 *
 * It was the Filter's seventh type until 2026-10-05 (owner's decision,
 * notes/2026-10-02-filters-dynamics-options.md, FD0): its delay lines made
 * every Filter instance 18 KB. As its own effect it keeps the type's code,
 * parameters and memory, and renders what a Filter set to Comb from the
 * start rendered, sample for sample [verified: tests/test_engines_comb.py
 * against renders pinned at main d538f1e, tests/fixtures/comb-split.json].
 *
 * Signal path, per channel and per sample:
 *
 *   input guard -> x Drive -> comb -> make-up gain -> x Level -> Mix with
 *   the dry
 *
 * The comb is Zoelzer's universal comb ("DAFX", ch. 2): one delay line of
 * fs / Cutoff samples, read with linear interpolation, with feedback and
 * feedforward. Mode 0 feedback (peaks), 3 feedforward (notches), blended
 * between. Morph is the polarity: 0 positive (peaks at multiples of
 * Cutoff), 0.5 none, 1 negative (odd multiples of Cutoff / 2: an octave
 * lower, hollow). Resonance is the loop gain, 0.25 to 0.98. The loop
 * passes the Filter's saturating curve, so it stays bounded however hard
 * it is driven.
 *
 * Parameters: the Filter's, less Type, with the Filter's uids (Cutoff 2 ..
 * Level 8; uid 1, the Filter's Type, is never used here), so a Filter that
 * was set to Comb maps onto this effect uid for uid and value for value.
 * Page 1: Cutoff (20 Hz..18 kHz, the LOG law), Resonance, Drive. Page 2:
 * Mode, Morph, Mix, Level (0..2).
 *
 * Levels. Drive multiplies the input into the comb (1x to 16x, 2^(4 Drive))
 * and divides the output by the square root of that, with the soft clip
 * blended into its input as Drive rises; the input is lowered as the loop
 * gain grows (sqrt(1 - |feedback|)).
 *
 * Control rate, as the Filter's: Cutoff, Resonance, Drive, Mode and Morph
 * glide one step per 8 samples, counted from create, so any block size
 * gives the same output; the delay is interpolated sample by sample across
 * each step, so a moving delay never jumps. Mix and Level glide every
 * sample.
 *
 * Contracts (fm1_engine.h): no heap; every field read is set in create (the
 * delay lines, the bulk of the instance, are read only where written since
 * create, so they are never cleared); NaN-safe parameters; the input guard
 * (NaN reads as 0, +/-16 clamp); finite output; silence in gives exact
 * silence out from rest. Determinism: no libm (fx_filter_dsp.h), no fused
 * multiply-adds. Written in the C subset of C++11. MIT licence, like the
 * rest of this repository.
 */

#include "fm1_engine.h"

#include <math.h>
#include <string.h>

/* No fused multiply-adds in this file (see fx_filter.cc). */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

#include "fx_filter_dsp.h"

enum { P_CUTOFF, P_RES, P_DRIVE, P_MODE, P_MORPH, P_MIX, P_LEVEL, P_COUNT };

// Uids are the Filter's (fx_filter.cc) for the same parameters: never
// renumber one, never give out 1 (the Filter's Type). Every FLOAT is read
// each block: SMOOTH and MOD; Cutoff, the comb's pitch, moves on the LOG law
// (API v3).
static const fm1_param_t kCombParams[P_COUNT] = {
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

static const float kCombMinHz = 20.0f;      /* the longest delay is fs / 20 Hz */
static const float kCombLoopMin = 0.25f;    /* loop gain at Resonance 0 */
static const float kCombLoopSpan = 0.73f;   /* ... and 0.98 at 1 */

typedef struct CombInstance {
  float param[P_COUNT];           /* knob values, clamped */
  float target[C_COUNT];          /* control values the knobs ask for */
  float value[C_COUNT];           /* control values in use */
  float mix, mix_t, level, level_t;
  float sample_rate;
  float glide1, glide_ctrl;       /* one-pole coefficients: per sample, per step */
  float in_gain, out_gain, drv;   /* Drive: into the comb, out of it, presat blend */
  float d0, d1;                   /* delay, samples, at the last and this control step */
  float fb, ff, cin;              /* feedback, feedforward, input gain */
  uint32_t count;                 /* samples since create (mod 2^32) */
  uint32_t n, w, filled;          /* line length, write index, samples written */
  int primed;
  /* Then the delay lines: 2 x n floats (CombInstanceSize). */
} CombInstance;

static inline size_t CombHeaderBytes(void) {
  return (sizeof(CombInstance) + 15u) & ~(size_t)15u;
}

static inline float *CombLine(CombInstance *self, int c) {
  return (float *)((unsigned char *)self + CombHeaderBytes()) + (size_t)c * self->n;
}

static uint32_t CombCells(float fs) {
  return (uint32_t)(fs / kCombMinHz) + 4u;
}

static void CombUpdateShared(CombInstance *self) {
  const float drive = self->value[C_DRIVE];
  self->in_gain = FiltDriveIn(drive);
  self->out_gain = FiltDriveOut(drive);
  self->drv = drive;
}

static void CombUpdateCoefs(CombInstance *self) {
  const float res = self->value[C_RES], mode = self->value[C_MODE];
  const float morph = self->value[C_MORPH];
  float d = self->sample_rate * FiltExp2(-self->value[C_PITCH]);
  const float dmax = (float)(self->n - 3u);
  if (d < 1.0f / kMaxOfRate) d = 1.0f / kMaxOfRate;   /* fs / fmax: 2.22 samples */
  if (d > dmax) d = dmax;
  self->d1 = d;
  const float loop = kCombLoopMin + kCombLoopSpan * res;
  const float sign = 1.0f - 2.0f * morph;
  const float t = mode * (1.0f / 3.0f);
  self->fb = sign * loop * (1.0f - t);
  self->ff = sign * loop * t;
  self->cin = sqrtf(1.0f - fabsf(self->fb));
}

static inline float CombRead(const CombInstance *self, const float *line, uint32_t age) {
  if (age > self->filled) return 0.0f;   /* not written since create */
  const uint32_t w = self->w;
  return line[w >= age ? w - age : w + self->n - age];
}

/* One frame, both channels; j is the sample's place in its control step. */
FILT_INLINE void CombFrame(CombInstance *self, const float xin[2], uint32_t j, float y[2]) {
  const float d = self->d0 + (self->d1 - self->d0) * (float)(j + 1u) * 0.125f;
  const uint32_t di = (uint32_t)d;            /* d >= 2 */
  const float fr = d - (float)di;
  for (int c = 0; c < 2; ++c) {
    float *line = CombLine(self, c);
    const float a = CombRead(self, line, di), b = CombRead(self, line, di + 1u);
    const float r = a + fr * (b - a);
    const float x = FiltPresat(xin[c], self->drv) * self->cin;
    float s;
    const float xh = 2.0f * FiltSat(0.5f * (x + self->fb * r), &s);
    line[self->w] = FiltFlush(xh);
    y[c] = xh + self->ff * r;
  }
}

static inline void CombAdvance(CombInstance *self) {
  self->w = self->w + 1u == self->n ? 0u : self->w + 1u;
  if (self->filled < self->n) ++self->filled;
}

static void CombSetTarget(CombInstance *self, int index) {
  const float v = self->param[index];
  switch (index) {
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
static void CombPrime(CombInstance *self) {
  for (int i = 0; i < C_COUNT; ++i) self->value[i] = self->target[i];
  self->mix = self->mix_t;
  self->level = self->level_t;
  CombUpdateShared(self);
  self->filled = 0u;                       /* the line itself is never read stale */
  CombUpdateCoefs(self);
  self->d0 = self->d1;
}

/* A control step: glide the controls and recompute what moved. */
static void CombControl(CombInstance *self) {
  self->d0 = self->d1;
  int moved = 0;
  for (int i = 0; i < C_COUNT; ++i) {
    if (self->value[i] != self->target[i]) {
      self->value[i] = FiltGlide(self->value[i], self->target[i], self->glide_ctrl);
      moved = 1;
    }
  }
  if (!moved) return;
  CombUpdateShared(self);
  CombUpdateCoefs(self);
}

/* ---------------------------------------------------------------------- */
/* The engine API                                                          */
/* ---------------------------------------------------------------------- */

static size_t CombInstanceSize(const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return CombHeaderBytes();
  const size_t line = (size_t)2u * CombCells(fs) * sizeof(float);
  return CombHeaderBytes() + ((line + 15u) & ~(size_t)15u);
}

static void *CombCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;
  CombInstance *self = (CombInstance *)mem;
  memset(self, 0, sizeof(*self));            /* the delay lines after it stay as they are */
  self->sample_rate = fs;
  /* exp(-x) = 2^(-x / ln 2) */
  self->glide1 = 1.0f - FiltExp2(-1.4426950f / (kSmoothSeconds * fs));
  self->glide_ctrl = 1.0f - FiltExp2(-1.4426950f * kCtrlSamples / (kSmoothSeconds * fs));
  self->n = CombCells(fs);
  self->w = 0u;
  self->filled = 0u;
  for (int i = 0; i < P_COUNT; ++i) {
    self->param[i] = kCombParams[i].def;
    CombSetTarget(self, i);
  }
  CombPrime(self);
  self->count = 0u;
  self->primed = 0;
  return self;
}

static void CombDestroy(void *self) { (void)self; }

static void CombSet(void *s, uint16_t index, float v) {
  CombInstance *self = (CombInstance *)s;
  if (index >= P_COUNT) return;
  self->param[index] = fm1_param_clamp(&kCombParams[index], v);
  CombSetTarget(self, index);
}

static void CombRender(void *s, float *lr, uint32_t frames) {
  CombInstance *self = (CombInstance *)s;
  if (!self->primed) {
    /* Settings made before the first block apply from its first sample. */
    CombPrime(self);
    self->primed = 1;
  }
  for (uint32_t f = 0; f < frames; ++f) {
    const uint32_t j = self->count & kCtrlMask;
    if (j == 0u) CombControl(self);
    if (self->mix != self->mix_t) self->mix = FiltGlide(self->mix, self->mix_t, self->glide1);
    if (self->level != self->level_t) {
      self->level = FiltGlide(self->level, self->level_t, self->glide1);
    }
    const float x[2] = { FiltGuard(lr[2 * f]), FiltGuard(lr[2 * f + 1]) };
    const float in_gain = self->in_gain;
    const float xin[2] = { in_gain * x[0], in_gain * x[1] };
    float y[2];
    CombFrame(self, xin, j, y);
    CombAdvance(self);
    const float wet = self->level * self->out_gain, mix = self->mix;
    lr[2 * f] = x[0] + mix * (wet * y[0] - x[0]);
    lr[2 * f + 1] = x[1] + mix * (wet * y[1] - x[1]);
    ++self->count;
  }
}

#ifdef __cplusplus
extern "C" {
#endif

extern const fm1_engine_t fm1_engine_comb;
const fm1_engine_t fm1_engine_comb = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "comb", "Comb",
  "This repository (MIT): Zoelzer's universal comb (DAFX, ch. 2), with the "
  "Filter's saturating loop. No code taken",
  kCombParams, P_COUNT, 0,
  CombInstanceSize, CombCreate, CombDestroy,
  NULL, NULL, NULL,
  CombSet, CombRender,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
};

#ifdef __cplusplus
}
#endif
