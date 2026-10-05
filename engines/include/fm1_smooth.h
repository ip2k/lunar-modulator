/* fm1_smooth.h -- the SMOOTH ramp (engine API v2, FM1_PARAM_SMOOTH; docs/15
 * stage S7b, docs/12 §5.3).
 *
 * A change to a SMOOTH parameter while an engine sounds does not jump: the
 * value the engine reads moves to the new one in equal steps, one per
 * control block of the engine's own, and lands on it exactly after
 * FM1_SMOOTH_US (2.5 ms) of the engine's native samples, rounded up to whole
 * blocks. A control block is where the engine reads its parameters anyway:
 * 12 samples at 47,872.34 Hz in Macro and Macro Heavy, 16 there in Six-Op,
 * 24 at 96 kHz in Shapes, one sample in Test Sine and the effects. Those
 * blocks sit at fixed native samples, rendered as the engine's resampler or
 * its own loop needs them, so the steps are keyed to samples, never to
 * render calls: the output is the same at any host block size and any split
 * of a block (fm1_seq_host.h splits at event frames).
 *
 * When there is nothing to ramp, a change applies at once: while no voice
 * sounds (a lock on the trig of a note that starts a silent engine plays
 * that note at the locked value from its first sample), and before an
 * effect's first render (settings made at load apply from sample 0). An
 * engine decides which case it is in and passes steps = 0 for a jump.
 *
 * Exactness, so native and WebAssembly builds give the same bits (docs/14,
 * docs/16 §2.7):
 *   - no libm: the step count is integer arithmetic;
 *   - nothing to contract into a fused multiply-add: a ramp's step is
 *     (target - value) / steps, computed once, each block adds it, and no
 *     expression multiplies and adds;
 *   - a ramp never passes its target (each step is clamped to it), so every
 *     value read lies between the old value and the new one, both within the
 *     parameter's range; its last block stores the target itself;
 *   - a value with no ramp is never touched, so a render with no change while
 *     sounding is the render without this header, bit for bit.
 *
 * Plain C99, header-only, no state outside the caller's arrays. MIT licence,
 * like the rest of this repository.
 */
#ifndef FM1_SMOOTH_H_
#define FM1_SMOOTH_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The ramp time, in microseconds: 2.5 ms (docs/15 O13 asked for 2-3 ms). */
#define FM1_SMOOTH_US 2500u

typedef struct fm1_smooth {
  float target;    /* where the value goes */
  float step;      /* added each control block while more than one is left */
  uint32_t left;   /* control blocks still to go; 0 = the value is the target */
} fm1_smooth_t;

/* The control blocks one ramp takes: FM1_SMOOTH_US of native samples at
 * native_rate (rounded to the nearest sample), divided by the engine's
 * control block (stride samples) and rounded up; at least 1. 120 samples,
 * 10 blocks of 12 at 47,872.34 Hz; 240 samples, 10 blocks of 24 at 96 kHz;
 * 110 samples at 44,118 Hz. Integer arithmetic after one rounding. */
static inline uint32_t fm1_smooth_steps(float native_rate, uint32_t stride) {
  uint32_t hz, samples;
  if (!(native_rate >= 1.0f)) native_rate = 1.0f;   /* NaN too */
  if (native_rate > 4.0e6f) native_rate = 4.0e6f;
  hz = (uint32_t)(native_rate + 0.5f);
  samples = (uint32_t)(((uint64_t)hz * FM1_SMOOTH_US + 500000u) / 1000000u);
  if (!stride) stride = 1u;
  samples = (samples + stride - 1u) / stride;
  return samples ? samples : 1u;
}

/* Every ramp in s[0..n) at rest, on the values the engine starts with. */
static inline void fm1_smooth_init(fm1_smooth_t *s, const float *values, unsigned n) {
  unsigned k;
  for (k = 0; k < n; ++k) {
    s[k].target = values[k];
    s[k].step = 0.0f;
    s[k].left = 0u;
  }
}

/* A new value for *value. steps = 0: at once, ending any ramp. Otherwise a
 * ramp of that many control blocks from where *value stands now (mid-ramp
 * included) to target. A target equal to the one already set changes
 * nothing, so a running ramp keeps its course and a repeated write is free. */
static inline void fm1_smooth_set(fm1_smooth_t *s, float *value, float target, uint32_t steps) {
  if (!steps) {
    *value = target;
    s->target = target;
    s->left = 0u;
    return;
  }
  if (target == s->target) return;
  s->target = target;
  if (target == *value) {          /* turned back to where it stands */
    *value = target;
    s->left = 0u;
    return;
  }
  s->step = (target - *value) / (float)steps;
  s->left = steps;
}

/* One control block of every ramp in s[0..n): call it at the start of each
 * block, before the block reads values[0..n). Returns nonzero while a ramp
 * still has blocks to go after this one. */
static inline int fm1_smooth_tick(fm1_smooth_t *s, float *values, unsigned n) {
  int moving = 0;
  unsigned k;
  for (k = 0; k < n; ++k) {
    float v;
    if (!s[k].left) continue;
    if (--s[k].left) {
      v = values[k] + s[k].step;
      if (s[k].step > 0.0f ? v > s[k].target : v < s[k].target) v = s[k].target;
      values[k] = v;
      moving = 1;
    } else {
      values[k] = s[k].target;
    }
  }
  return moving;
}

/* Whether any ramp in s[0..n) has blocks to go. */
static inline int fm1_smooth_moving(const fm1_smooth_t *s, unsigned n) {
  unsigned k;
  for (k = 0; k < n; ++k) {
    if (s[k].left) return 1;
  }
  return 0;
}

#ifdef __cplusplus
}
#endif

#endif /* FM1_SMOOTH_H_ */
