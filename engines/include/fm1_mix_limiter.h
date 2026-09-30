/* fm1_mix_limiter.h -- the mix-bus limiter the host applies after the engines.
 *
 * Engines render with headroom for a few voices; a 12-note chord started in
 * phase can still sum past full scale, so the host's master bus limits (the
 * stock firmware saturates its mix for the same reason). Peak follower with
 * instant attack and ~100 ms release: output never exceeds the ceiling, and a
 * single voice passes untouched. MIT licence.
 */
#ifndef FM1_MIX_LIMITER_H_
#define FM1_MIX_LIMITER_H_

#include <math.h>
#include <stdint.h>

typedef struct fm1_mix_limiter {
  float envelope;
  float release;   /* per-sample coefficient */
  float ceiling;
} fm1_mix_limiter_t;

static inline void fm1_mix_limiter_init(fm1_mix_limiter_t *l, float sample_rate) {
  l->envelope = 0.0f;
  l->release = 1.0f - expf(-1.0f / (0.1f * sample_rate));
  l->ceiling = 0.98f;
}

static inline void fm1_mix_limiter_process(fm1_mix_limiter_t *l, float *lr, uint32_t frames) {
  for (uint32_t n = 0; n < frames; ++n) {
    float a = fabsf(lr[2 * n]);
    float b = fabsf(lr[2 * n + 1]);
    float peak = a > b ? a : b;
    if (peak > l->envelope) {
      l->envelope = peak;
    } else {
      l->envelope += (peak - l->envelope) * l->release;
    }
    if (l->envelope > l->ceiling) {
      float g = l->ceiling / l->envelope;
      lr[2 * n] *= g;
      lr[2 * n + 1] *= g;
    }
  }
}

#endif /* FM1_MIX_LIMITER_H_ */
