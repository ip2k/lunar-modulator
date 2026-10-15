/* fm1_mix_limiter.h -- the mix-bus limiter the host applies after the engines.
 *
 * Engines render with headroom for a few voices; a 12-note chord started in
 * phase can still sum past full scale, so the host's master bus limits (the
 * stock firmware saturates its mix for the same reason). Peak follower with
 * instant attack and ~100 ms release: output never exceeds the ceiling, and a
 * single voice passes untouched. Non-finite samples become silence (see
 * fm1_mix_guard). MIT licence.
 */
#ifndef FM1_MIX_LIMITER_H_
#define FM1_MIX_LIMITER_H_

#include <math.h>
#include <stdint.h>

/* JieLi builds disable implicit builtins globally. Use the explicit compiler
 * builtin for per-sample absolute value when available; preserve the standard
 * library fallback for other compilers. */
#if defined(__GNUC__) || defined(__clang__)
#define FM1_MIX_LIMITER_ABS_F32(x) __builtin_fabsf(x)
#else
#define FM1_MIX_LIMITER_ABS_F32(x) fabsf(x)
#endif

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

/* The guard is called twice per stereo frame. Size-oriented target builds may
 * otherwise retain an out-of-line call even for this small comparison-only
 * helper. Keep ordinary builds unchanged; the opt-in hot-DSP profile requests
 * inlining without changing the arithmetic or IEEE comparison behavior. */
#if defined(FM1_HOT_DSP_RAM) && FM1_HOT_DSP_RAM && \
    (defined(__GNUC__) || defined(__clang__))
#define FM1_MIX_GUARD_INLINE static inline __attribute__((always_inline))
#else
#define FM1_MIX_GUARD_INLINE static inline
#endif

/* Bus guard, applied before the envelope sees a sample. A NaN would otherwise
 * latch the envelope to NaN, after which `envelope > ceiling` is always false
 * and limiting stops for good; an infinity would do the same one sample later.
 * NaN becomes silence, and anything past +/-16 (+24 dBFS, infinities included)
 * is clamped so one wild sample holds the bus down for ~0.3 s, not seconds.
 * Relies on IEEE compares: do not build with -ffast-math/-ffinite-math-only. */
FM1_MIX_GUARD_INLINE float fm1_mix_guard(float x) {
  if (!(x == x)) return 0.0f;
  return x > 16.0f ? 16.0f : (x < -16.0f ? -16.0f : x);
}

#undef FM1_MIX_GUARD_INLINE

static inline void fm1_mix_limiter_process(fm1_mix_limiter_t *l, float *lr, uint32_t frames) {
  for (uint32_t n = 0; n < frames; ++n) {
    lr[2 * n] = fm1_mix_guard(lr[2 * n]);
    lr[2 * n + 1] = fm1_mix_guard(lr[2 * n + 1]);
    float a = FM1_MIX_LIMITER_ABS_F32(lr[2 * n]);
    float b = FM1_MIX_LIMITER_ABS_F32(lr[2 * n + 1]);
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

#undef FM1_MIX_LIMITER_ABS_F32

#endif /* FM1_MIX_LIMITER_H_ */
