/* fx_shaper.cc -- "Transient": a transient shaper (FM1_KIND_AUDIO_FX),
 * written for this repository. Notes in engines/README.md ("Transient").
 *
 * Per frame, both channels sharing one detector and one gain:
 *
 *   guard -> level x = max(|L|, |R|) -> two followers, in a chain:
 *     fast F of x: instant attack, release 40 ms (fixed)
 *     slow S of F: attack Window, release Tail
 *   -> D = 20 log10(F / S), in dB, clamped to +/-12 dB
 *   -> gain (dB) = Attack x D where D > 0 (an onset: F ahead of S),
 *                  Sustain x (-D) where D < 0 (a decay: F under S),
 *                  plus Output
 *   -> out = dry x (1 + Mix (gain - 1))
 *
 * The differential-envelope design: two envelope followers of different
 * speeds disagree only where the level changes, so their difference in dB
 * isolates the onsets (positive) and the decays (negative), whatever the
 * level, and a steady tone, where both agree, is left alone (within the
 * fast follower's ripple on low notes). It is the classic transient
 * designer's principle; this is our own arithmetic, after the two-follower
 * law noted from legsmechanical's Bus Driver (MIT, `36b6788`, notes
 * 2026-10-02-filters-dynamics-options.md §3: a fast and a slow follower),
 * with no code or table taken from it or anywhere else.
 *
 * Why a chain (review, 2026-10-06). The slow follower reads the fast one,
 * not x: on a steady tone x itself swings from 0 to the peak every half
 * cycle, and a follower of x settles where its rise and fall balance, which
 * depends on its own two times. With S on x, Window 100 ms and Tail 50 ms
 * sat 4.8 dB under F on any steady sine (Attack +100 % lifted it by that
 * much), Window 20 ms and Tail 50 ms 2 dB. Following F, which is already
 * near the peaks, S settles on F whatever Window and Tail are, and only F's
 * ripple is left: 0.3 dB at most at 40 Hz, 0.02 dB at 1 kHz, anywhere on
 * the two knobs [verified: fm1-squash-test's `steady`]. F rises at once,
 * not over 1 ms: at an onset after a held tail (S still high), the gain
 * Sustain gives the tail then ends as soon as the new note passes S, rather
 * than lifting the note's first millisecond by up to 12 dB (it came out
 * over its own peak), and the attack it finds is the sharper.
 *
 * The law, in dB of the level x_dB: at +100 % Attack an onset comes out at
 * x_dB + (F - S), so its rise is twice as steep against the slow envelope;
 * at -100 % at x_dB - (F - S) ~ S, so it rises no faster than Window lets
 * the slow follower. At +100 % Sustain a decay comes out at about S, so it
 * falls as slowly as Tail; at -100 % about twice as fast. The clamp keeps
 * either share within 12 dB (an onset out of silence would otherwise ask
 * for 100). Between, the gain scales with the knob.
 *
 * Exactness. Attack and Sustain at 0 and Output at 0 dB pass the input bit
 * for bit (the gain is 2^0, exactly 1, and Mix multiplies 1 + Mix x 0), so
 * the centre of the knobs is a true bypass, and the followers keep running
 * so a turned knob starts from where the music is. Silence in gives exact
 * silence out (the gain multiplies the input).
 *
 * Contracts (fm1_engine.h): no heap, every field set in create, NaN-safe
 * parameters (fm1_param_clamp), finite output. Input guard as the other
 * effects' (mi_fx.cc): NaN reads as 0, anything beyond +/-16 is clamped.
 * Every parameter is SMOOTH (fm1_smooth.h): from the first render on, a
 * change ramps over 2.5 ms of samples, one step per frame, so any block
 * size gives the same output; values set before the first render apply at
 * once. The followers flush to 0 under 1e-20: no subnormals.
 *
 * Determinism: no libm. log2 and 2^x are fm1_math.h's polynomials and the
 * one-pole coefficients come from them; floating-point contraction is off
 * (below), so every build computes the same bits.
 *
 * Cost, per frame (stereo): two follower steps, one divide, one log2 and
 * one 2^x: about 60 operations; at the centre the log and the exponential
 * are skipped. Measured in engines/README.md.
 *
 * Written in the C subset of C++11. MIT licence, like the rest of this
 * repository.
 */

#include "fm1_engine.h"
#include "fm1_smooth.h"

#include <stdint.h>
#include <string.h>

/* No fused multiply-adds: the browser's WebAssembly cannot fuse (fx_comp.cc
 * explains). GCC ignores the pragma: build for a GCC target with FMA with
 * -ffp-contract=off. */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

enum { P_ATTACK, P_SUSTAIN, P_WINDOW, P_TAIL, P_OUTPUT, P_MIX, P_COUNT };

/* Uids (API v2) are fixed: never renumber one; a new parameter takes the next
 * free uid. Every parameter is read every frame: SMOOTH and MOD. Window and
 * Tail are times: LOG (ratios a detent, octaves under modulation). Output is
 * in dB. */
static const fm1_param_t kShaperParams[P_COUNT] = {
  { "Attack",  FM1_PARAM_FLOAT, -100, 100, 0, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_PCT, "Atk" },
  { "Sustain", FM1_PARAM_FLOAT, -100, 100, 0, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_PCT, "Sus" },
  { "Window",  FM1_PARAM_FLOAT, 5, 100, 20, NULL, 0, 3, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_MS, "Win" },
  { "Tail",    FM1_PARAM_FLOAT, 50, 2000, 400, NULL, 0, 4, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_MS, "Tail" },
  { "Output",  FM1_PARAM_FLOAT, -24, 12, 0, NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Out" },
  { "Mix",     FM1_PARAM_FLOAT, 0, 1, 1, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
};

static const float kInputLimit = 16.0f;       /* the input guard, as mi_fx.cc */
static const float kFlush = 1e-20f;           /* follower levels below are 0 */
static const float kFloor = 7.62939453e-6f;   /* 2^-17 (-102 dB): the ratio's floor */
static const float kSpan = 12.0f;             /* dB: the most D counts for */
static const float kFastRelease = 0.040f;     /* s */
static const float kDbPerLog2 = 6.02059991f;  /* 20 log10(2) */
static const float kLog2PerDb = 0.166096405f; /* log2(10) / 20 */
static const float kLog2e = 1.44269504f;

typedef struct ShaperInstance {
  float value[P_COUNT];         /* the values in use, ramping to their targets */
  fm1_smooth_t ramp[P_COUNT];
  uint32_t steps;               /* a ramp's frames, 2.5 ms */
  int started;                  /* rendered at least once */
  float rate;
  float rf;                     /* fast follower: its release (it rises at once) */
  float as, rs;                 /* slow follower: Window and Tail */
  float k_attack, k_sustain;    /* Attack and Sustain as shares, -1..1 */
  float fast, slow;             /* follower levels, linear */
  float gain_db;                /* the last frame's gain, dB (Output included) */
} ShaperInstance;

static inline float ShaperAbs(float x) { return x < 0.0f ? -x : x; }

static inline float ShaperGuard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   /* NaN fails both */
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         /* NaN */
}

/* The step of a one-pole lag with this time constant, 1 - exp(-1 / (s fs)). */
static float ShaperCoef(float seconds, float rate) {
  return 1.0f - fm1_exp2f(-kLog2e / (seconds * rate));
}

/* What the values in use imply. */
static void ShaperDerive(ShaperInstance *self) {
  const float fs = self->rate;
  self->as = ShaperCoef(0.001f * self->value[P_WINDOW], fs);
  self->rs = ShaperCoef(0.001f * self->value[P_TAIL], fs);
  self->k_attack = 0.01f * self->value[P_ATTACK];
  self->k_sustain = 0.01f * self->value[P_SUSTAIN];
}

static size_t ShaperInstanceSize(const fm1_host_t *host) {
  (void)host;
  return (sizeof(ShaperInstance) + 15u) & ~(size_t)15u;
}

static void *ShaperCreate(void *mem, const fm1_host_t *host) {
  const float fs = host->sample_rate;
  if (!(fs >= 8000.0f && fs <= 384000.0f)) return NULL;   /* NaN fails too */
  ShaperInstance *self = (ShaperInstance *)mem;
  memset(self, 0, sizeof(*self));
  self->rate = fs;
  for (int i = 0; i < P_COUNT; ++i) self->value[i] = kShaperParams[i].def;
  fm1_smooth_init(self->ramp, self->value, P_COUNT);
  self->steps = fm1_smooth_steps(fs, 1);
  self->rf = ShaperCoef(kFastRelease, fs);
  ShaperDerive(self);
  return self;
}

static void ShaperDestroy(void *self) { (void)self; }

static void ShaperSet(void *s, uint16_t index, float v) {
  ShaperInstance *self = (ShaperInstance *)s;
  if (index >= P_COUNT) return;
  v = fm1_param_clamp(&kShaperParams[index], v);
  fm1_smooth_set(&self->ramp[index], &self->value[index], v, self->started ? self->steps : 0u);
  if (!self->started) ShaperDerive(self);
}

static void ShaperRender(void *s, float *lr, uint32_t frames) {
  ShaperInstance *self = (ShaperInstance *)s;
  self->started = 1;
  /* The followers live in locals for the block: lr may alias any float. */
  float fast = self->fast, slow = self->slow, gain_db = self->gain_db;
  const float rf = self->rf;
  for (uint32_t f = 0; f < frames; ++f) {
    if (fm1_smooth_moving(self->ramp, P_COUNT)) {
      fm1_smooth_tick(self->ramp, self->value, P_COUNT);
      ShaperDerive(self);
    }
    const float l = ShaperGuard(lr[2 * f]), r = ShaperGuard(lr[2 * f + 1]);
    const float al = ShaperAbs(l), ar = ShaperAbs(r);
    const float x = al > ar ? al : ar;
    fast = x > fast ? x : fast + rf * (x - fast);
    if (fast < kFlush) fast = 0.0f;
    slow = slow + (fast > slow ? self->as : self->rs) * (fast - slow);
    if (slow < kFlush) slow = 0.0f;

    float g = self->value[P_OUTPUT];
    const float ka = self->k_attack, ks = self->k_sustain;
    if (ka != 0.0f || ks != 0.0f) {
      const float fa = fast > kFloor ? fast : kFloor, sa = slow > kFloor ? slow : kFloor;
      float d = kDbPerLog2 * fm1_log2f(fa / sa);
      if (d > kSpan) d = kSpan;
      if (d < -kSpan) d = -kSpan;
      g = g + (d > 0.0f ? ka * d : ks * -d);
    }
    gain_db = g;
    const float gain = g == 0.0f ? 1.0f : fm1_exp2f(kLog2PerDb * g);
    const float mix = self->value[P_MIX];
    const float wet = mix == 1.0f ? gain : 1.0f + mix * (gain - 1.0f);
    lr[2 * f] = l * wet;
    lr[2 * f + 1] = r * wet;
  }
  self->fast = fast;
  self->slow = slow;
  self->gain_db = gain_db;
}

#ifdef __cplusplus
extern "C" {
#endif

extern const fm1_engine_t fm1_engine_shaper;
const fm1_engine_t fm1_engine_shaper = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "shaper", "Transient",
  "This repository (MIT): a transient shaper on the differential-envelope "
  "principle (a fast and a slow follower), our own arithmetic; no code taken",
  kShaperParams, P_COUNT, 0,
  ShaperInstanceSize, ShaperCreate, ShaperDestroy,
  NULL, NULL, NULL,
  ShaperSet, ShaperRender,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
  NULL,                     // API v4: no get_param, the host keeps its values
};

#ifdef __cplusplus
}
#endif
