/* mp_slew.c -- the slew limiter (fm1_mp.h).
 *
 * The state is integer, Q4.28 in an int32 (-8..8 in steps of 2^-28), so both
 * modes are exact and identical on every rung:
 * - LINEAR moves by at most `step` per sample; n samples at once move by at
 *   most n x step, which is exactly n single steps, so process(n) is O(1).
 * - EXPO moves by |d| x k per sample (k in Q32), rounded toward zero but at
 *   least one LSB, so it lands exactly on the target instead of stalling a
 *   few float ulps short, as a float one-pole with a long time constant does.
 *   It loops per sample.
 * The value is quantised to 2^-28 (3.7e-9) and limited to -8..8. */
#include "mp_int.h"

#define Q 268435456.0f       /* 2^28 */
#define QMAX 2147483520.0f   /* the largest float below 2^31: inputs clamp to just under 8 */
#define INSTANT 0x100000000ull

static int32_t to_q(float x) {
  return (int32_t)mp_clampf(x * Q, -QMAX, QMAX, 0.0f);
}

/* Per-sample step for LINEAR: 2^28 / samples (a full 1.0 in `seconds`). */
static uint64_t linear_step(float seconds, float sample_rate) {
  const float samples = mp_clampf(seconds, 0.0f, 3600.0f, 0.0f) * sample_rate;
  float s;
  if (samples <= 1.0f) return INSTANT;
  s = Q / samples;
  return s < 1.0f ? 1u : (uint64_t)s;
}

/* Coefficient for EXPO, k = 1 - e^(-1/samples) in Q32, from the [2/2] Pade
 * approximant of e^-x (x <= 1 here, error under 0.1 %), so no libm. */
static uint64_t expo_coeff(float seconds, float sample_rate) {
  const float samples = mp_clampf(seconds, 0.0f, 3600.0f, 0.0f) * sample_rate;
  float x, k;
  if (samples <= 1.0f) return INSTANT;
  x = 1.0f / samples;
  k = x / (1.0f + x * (0.5f + x * (1.0f / 12.0f)));
  k *= 4294967296.0f;
  return k < 1.0f ? 1u : (uint64_t)k;
}

static void coeffs(fm1_mp_slew_t *s) {
  if (s->mode == FM1_MP_SLEW_EXPO) {
    s->up = expo_coeff(s->rise_s, s->sample_rate);
    s->down = expo_coeff(s->fall_s, s->sample_rate);
  } else {
    s->up = linear_step(s->rise_s, s->sample_rate);
    s->down = linear_step(s->fall_s, s->sample_rate);
  }
}

void fm1_mp_slew_init(fm1_mp_slew_t *s, float sample_rate) {
  s->sample_rate = mp_rate(sample_rate);
  s->y = s->target = 0;
  s->rise_s = s->fall_s = 0.0f;
  s->mode = FM1_MP_SLEW_LINEAR;
  s->pad_[0] = s->pad_[1] = s->pad_[2] = 0;
  coeffs(s);
}

void fm1_mp_slew_set_mode(fm1_mp_slew_t *s, int mode) {
  s->mode = (uint8_t)((mode >= 0 && mode < FM1_MP_SLEW_MODE_COUNT) ? mode : FM1_MP_SLEW_LINEAR);
  coeffs(s);
}

void fm1_mp_slew_set_times(fm1_mp_slew_t *s, float rise_s, float fall_s) {
  s->rise_s = mp_clampf(rise_s, 0.0f, 3600.0f, 0.0f);
  s->fall_s = mp_clampf(fall_s, 0.0f, 3600.0f, 0.0f);
  coeffs(s);
}

void fm1_mp_slew_reset(fm1_mp_slew_t *s, float value) {
  s->y = s->target = mp_finite(value) ? to_q(value) : 0;
}

/* The distance still to go, |target - y|, and its direction. */
static uint64_t distance(const fm1_mp_slew_t *s, int *up) {
  const int64_t d = (int64_t)s->target - (int64_t)s->y;
  *up = d > 0;
  return (uint64_t)(d < 0 ? -d : d);
}

static void move(fm1_mp_slew_t *s, uint64_t by, int up) {
  s->y = (int32_t)(up ? (int64_t)s->y + (int64_t)by : (int64_t)s->y - (int64_t)by);
}

static void advance(fm1_mp_slew_t *s, uint32_t n) {
  int up;
  uint64_t d = distance(s, &up);
  if (d == 0 || n == 0) return;
  if (s->mode == FM1_MP_SLEW_LINEAR) {
    const uint64_t step = up ? s->up : s->down;
    /* n x step >= d without overflowing: d < 2^32 and n < 2^32. */
    move(s, (step >= d || (uint64_t)n >= (d + step - 1u) / step) ? d : (uint64_t)n * step, up);
    return;
  }
  while (n-- && d) {
    uint64_t by = (d * (up ? s->up : s->down)) >> 32;
    if (by == 0) by = 1;
    move(s, by, up);
    d -= by;
  }
}

float fm1_mp_slew_value(const fm1_mp_slew_t *s) {
  return (float)s->y * (1.0f / Q);
}

float fm1_mp_slew_process(fm1_mp_slew_t *s, float in, uint32_t n) {
  if (mp_finite(in)) s->target = to_q(in);
  advance(s, n);
  return fm1_mp_slew_value(s);
}

void fm1_mp_slew_render(fm1_mp_slew_t *s, const float *in, float *out, uint32_t n) {
  uint32_t i;
  for (i = 0; i < n; ++i) {
    if (in && mp_finite(in[i])) s->target = to_q(in[i]);
    advance(s, 1);
    out[i] = fm1_mp_slew_value(s);
  }
}
