/* fm1_fx_idle.h -- the idle path of the effects that have an exact
 * pass-through setting: EQ, Isolator and Master Sat (owner's decision,
 * 2026-10-05; engines/README.md, "Idle at pass-through"). Written for this
 * repository; MIT licence.
 *
 * At its pass-through settings (every gain at 0 dB; every band at unity;
 * Mix at 0) such an effect already outputs its guarded input bit for bit,
 * but its filters used to keep running so that leaving the setting would
 * start from settled filters. Now:
 *
 *   rest   once the effect has sat at its pass-through settings, with every
 *          glide and crossfade landed, for FM1_IDLE_REST_SECONDS, it idles:
 *          its filter states are cleared, and each block costs only the
 *          input guard, whose output is the one it gave before, bit for bit.
 *          Rhythmic moves (a kill and back within a bar, a lock every few
 *          steps) come back sooner than that and never wait for a wake.
 *          After a longer rest a move waits for the warm-up, and a lock
 *          that comes back within the warm-up is not heard at all;
 *   wake   a setting that leaves pass-through wakes it, at the start of the
 *          render after set_param (where every change arrives). Its filters
 *          start from rest and run on the input while the knobs that leave
 *          pass-through are held where they were, so the output is still the
 *          input bit for bit, for the warm-up: the frames the slowest mode
 *          of its filters at the new settings takes to decay by
 *          FM1_IDLE_SETTLE_NEPERS (-104 dB of the state it started from;
 *          what reached the output stayed under -92 dB of the input's peak
 *          in every case measured, engines/README.md);
 *   fade   then the held knobs are released and glide or crossfade exactly
 *          as they always have, from the states the filters would have held
 *          had they never stopped (to within that residue). No click and no
 *          jump: the knob answers a warm-up later, that is all.
 *
 * At any other setting nothing changes: the same operations in the same
 * order, so the same bits as before this header (each effect's test checks
 * it against a build with FM1_FX_IDLE 0, which is the code as it was).
 *
 * The decay bound. Each effect is built of trapezoidal (TPT) state-variable
 * sections, g = tan(pi f / fs) and damping k = 1/Q, which are the bilinear
 * transform of the analog prototype: an analog pole s gives the digital pole
 * z = (1 + g s) / (1 - g s). For k < 2 the poles are complex, s = -k/2 +/-
 * j sqrt(1 - k^2/4), and
 *   |z|^2 = (1 + g^2 - g k) / (1 + g^2 + g k),  -ln|z| = atanh(g k / (1 + g^2));
 * for k >= 2 they are real, s = -k/2 +/- sqrt(k^2/4 - 1), each giving
 * -ln|z| = 2 atanh(min(r, 1/r)) with r = g |s|, and |s| lies in [1/k, 2/k]
 * for the slow pole and in [k/2, k] for the fast one. atanh(y) >= y, so
 *   k < 2:   d >= g k / (1 + g^2)
 *   k >= 2:  d >= 2 min(g/k, k/(2g), g k/2, 1/(g k))
 * is a lower bound on the slowest mode's decay per sample, d nepers, and
 * ceil(L / d) frames an upper bound on the time it takes to fall by L.
 *
 * Determinism: integer results from IEEE +, -, * and /, one rounding each
 * (every product its own expression; no contraction under clang, the pragma
 * below), so a native build and WebAssembly agree on every warm-up length,
 * and with it on every output sample. Control rate only: a wake, or a
 * setting changed at rest.
 *
 * Plain C99 (and the C subset of C++11); static inline, no state.
 */
#ifndef FM1_FX_IDLE_H_
#define FM1_FX_IDLE_H_

#include <stdint.h>

#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

/* Build with -DFM1_FX_IDLE=0 for the effects without their idle paths: the
 * code as it was before them, which the tests use as the reference. */
#ifndef FM1_FX_IDLE
#define FM1_FX_IDLE 1
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* How long an effect sits at its pass-through settings before it idles. */
#define FM1_IDLE_REST_SECONDS 2.0f

/* How far the slowest filter mode decays during a wake's warm-up: e^-12,
 * -104 dB of the state it started from (the measured residue, with the
 * resonance and the band gains that scale it, is in engines/README.md). */
#define FM1_IDLE_SETTLE_NEPERS 12.0f

/* The longest warm-up a setting may need and still idle. Only EQ reaches it:
 * a low shelf below about 27 Hz at Q 0.71, or a bell below about 380 Hz at
 * Q 10, needs longer, and EQ keeps running there instead. Tuned there while
 * idle, EQ wakes and holds its bands for at most this long, not their full
 * warm-up, so a gain turned soon after is not kept waiting: it starts from a
 * filter still settling into the new tuning, as the old code's would have
 * been after the retune (engines/README.md). */
#define FM1_IDLE_MAX_WARM_SECONDS 0.1f

/* Seconds to whole frames at rate fs, rounded up; at least 1. */
static inline uint32_t fm1_idle_frames_of(float seconds, float fs) {
  const float x = seconds * fs;
  uint32_t n;
  if (!(x < 4.0e9f)) return 4000000000u;       /* NaN too */
  if (!(x > 1.0f)) return 1u;
  n = (uint32_t)x;
  if ((float)n < x) n = n + 1u;
  return n;
}

/* A lower bound on the decay per sample, in nepers, of the slowest mode of a
 * TPT state-variable section with g = tan(pi f / fs) > 0 and damping
 * k = 1/Q > 0 (above). */
static inline float fm1_idle_svf_decay(float g, float k) {
  float gk, g2, d, t;
  gk = g * k;
  if (k < 2.0f) {
    g2 = g * g;
    return gk / (1.0f + g2);
  }
  d = g / k;
  t = k / (2.0f * g);
  if (t < d) d = t;
  t = 0.5f * gk;
  if (t < d) d = t;
  t = 1.0f / gk;
  if (t < d) d = t;
  return 2.0f * d;
}

/* Frames for a mode decaying by `decay` nepers per sample to fall by
 * `nepers`: ceil(nepers / decay), at least 1 and at most `cap` (cap + 1
 * when it would need more, so a caller can tell). */
static inline uint32_t fm1_idle_settle_frames(float nepers, float decay, uint32_t cap) {
  float x;
  uint32_t n;
  if (!(decay > 0.0f)) return cap + 1u;          /* NaN too */
  x = nepers / decay;
  if (!(x <= (float)cap)) return cap + 1u;
  n = (uint32_t)x;
  if ((float)n < x) n = n + 1u;
  return n < 1u ? 1u : n;
}

#ifdef __cplusplus
}
#endif

#endif /* FM1_FX_IDLE_H_ */
