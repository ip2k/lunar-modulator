/* mp_lfo.c -- the phase-accumulator LFO (fm1_mp.h).
 *
 * Shapes follow the set in Schwung's src/host/lfo_common.h (Charles Vestal,
 * MIT) plus smooth random and a random walk, as the 2026-10-01 options note
 * (§3) recommends; the code is our own. Schwung keeps a double phase and
 * re-rolls its S&H when phase < 0.05; this keeps a uint32 phase and draws on
 * every carry out of the accumulator, which no block size can skip. */
#include "mp_int.h"

#define TWO32F 4294967296.0f

/* sin(2 pi x) for x in -0.25..0.25 turns: the Taylor series to x^11, whose
 * first omitted term is under 6e-8 at the ends. Coefficients (2 pi)^k / k!. */
static float sin_quarter(float x) {
  const float x2 = x * x;
  float y = 15.094642576822984f;
  y = 42.058693944897634f - x2 * y;
  y = 76.70585975306136f - x2 * y;
  y = 81.60524927607504f - x2 * y;
  y = 41.341702240399755f - x2 * y;
  y = 6.283185307179586f - x2 * y;
  return x * y;
}

/* The phase folded onto -0.25..0.25 turns with the same sine: 0..1/4 rises,
 * 1/4..3/4 falls, 3/4..1 rises again. Also the triangle, scaled by 4. */
static float fold(uint32_t p) {
  int64_t q = (int64_t)p;
  if (q >= 0xC0000000ll) {
    q -= 0x100000000ll;
  } else if (q >= 0x40000000ll) {
    q = 0x80000000ll - q;
  }
  return (float)q * (1.0f / TWO32F);
}

static float smoothstep(uint32_t p) {
  const float t = (float)p * (1.0f / TWO32F);
  return t * t * (3.0f - 2.0f * t);
}

/* A new cycle: two draws, always in this order, whatever the shape. */
static void new_cycle(fm1_mp_lfo_t *l) {
  const float r1 = fm1_mp_rng_bipolar(&l->rng);
  const float r2 = fm1_mp_rng_bipolar(&l->rng);
  float w = l->walk_next + l->walk * r2;
  if (w > 1.0f) {
    w = 2.0f - w;
  } else if (w < -1.0f) {
    w = -2.0f - w;
  }
  l->prev = l->next;
  l->next = r1;
  l->walk_prev = l->walk_next;
  l->walk_next = w;
  ++l->wraps;
}

static void wrap(fm1_mp_lfo_t *l) {
  if (l->owed) {
    --l->owed;
  } else {
    new_cycle(l);
  }
}

static uint64_t run_end(const fm1_mp_lfo_t *l) {
  return l->mode == FM1_MP_LFO_HALF ? 0x80000000ull : 0x100000000ull;
}

static void advance(fm1_mp_lfo_t *l, uint32_t n) {
  uint64_t d, sum;
  uint32_t w;
  if (l->done || n == 0 || (l->inc == 0 && l->inc_frac == 0)) return;
  sum = (uint64_t)l->frac + (uint64_t)l->inc_frac * n;
  l->frac = (uint32_t)sum;
  d = (uint64_t)l->inc * n + (sum >> 32);
  if (l->mode != FM1_MP_LFO_FREE) {
    const uint64_t last = run_end(l) - 1u;
    const uint64_t room = l->run < last ? last - l->run : 0;
    if (d >= room) {
      d = room;
      l->done = 1;
    }
    l->run += d;
  }
  sum = (uint64_t)l->phase + d;
  l->phase = (uint32_t)sum;
  for (w = (uint32_t)(sum >> 32); w; --w) wrap(l);
}

void fm1_mp_lfo_seed(fm1_mp_lfo_t *l, uint32_t seed) {
  fm1_mp_rng_seed(&l->rng, seed);
  l->next = fm1_mp_rng_bipolar(&l->rng);
  l->walk_next = fm1_mp_rng_bipolar(&l->rng);
  l->owed = 0;
  new_cycle(l);
  l->wraps = 0;
}

void fm1_mp_lfo_init(fm1_mp_lfo_t *l, float sample_rate, uint32_t seed) {
  l->sample_rate = mp_rate(sample_rate);
  l->phase = 0;
  l->frac = 0;
  l->start = 0;
  l->run = 0;
  l->pw = 0x80000000ull;
  l->walk = 0.25f;
  l->shape = FM1_MP_LFO_SINE;
  l->mode = FM1_MP_LFO_FREE;
  l->done = 0;
  l->owed = 0;
  l->prev = l->next = l->walk_prev = l->walk_next = 0.0f;
  l->wraps = 0;
  fm1_mp_lfo_set_rate(l, 1.0f, 1.0f);
  fm1_mp_lfo_seed(l, seed);
}

void fm1_mp_lfo_set_shape(fm1_mp_lfo_t *l, int shape) {
  l->shape = (uint8_t)((shape >= 0 && shape < FM1_MP_LFO_SHAPE_COUNT) ? shape : FM1_MP_LFO_SINE);
}

void fm1_mp_lfo_set_mode(fm1_mp_lfo_t *l, int mode) {
  l->mode = (uint8_t)((mode >= 0 && mode < FM1_MP_LFO_MODE_COUNT) ? mode : FM1_MP_LFO_FREE);
  if (l->mode == FM1_MP_LFO_FREE) {
    l->done = 0;
  } else if (l->run >= run_end(l) - 1u) {
    l->done = 1;
  }
}

void fm1_mp_lfo_set_rate(fm1_mp_lfo_t *l, float base_hz, float ratio) {
  const float hz = mp_clampf(base_hz * ratio, 0.0f, l->sample_rate * 0.5f, 0.0f);
  const double x = (double)hz / (double)l->sample_rate * 4294967296.0; /* at most 2^31 */
  double f;
  l->hz = hz;
  l->inc = (uint32_t)x;
  f = (x - (double)l->inc) * 4294967296.0;
  l->inc_frac = (uint32_t)f;
  if ((double)l->inc_frac < f) { /* round up */
    if (++l->inc_frac == 0) ++l->inc;
  }
}

void fm1_mp_lfo_set_pulse_width(fm1_mp_lfo_t *l, float pw) {
  pw = mp_clampf(pw, 0.0f, 1.0f, 0.5f);
  l->pw = (uint64_t)(pw * TWO32F);
}

void fm1_mp_lfo_set_walk(fm1_mp_lfo_t *l, float walk) {
  l->walk = mp_clampf(walk, 0.0f, 1.0f, 0.25f);
}

void fm1_mp_lfo_set_start_phase(fm1_mp_lfo_t *l, float turns) {
  turns = mp_clampf(turns, 0.0f, 1.0f, 0.0f);
  l->start = (uint32_t)((uint64_t)(turns * TWO32F) & 0xFFFFFFFFull);
}

void fm1_mp_lfo_reset(fm1_mp_lfo_t *l) {
  l->phase = l->start;
  l->frac = 0;
  l->run = 0;
  l->done = 0;
  l->owed = 0;
  new_cycle(l);
}

void fm1_mp_lfo_sync(fm1_mp_lfo_t *l, uint32_t phase) {
  const uint32_t forward = phase - l->phase;
  if (l->done) return;
  if (forward < 0x80000000u) {
    if (phase < l->phase) wrap(l);
  } else if (phase > l->phase && l->owed < 255u) {
    ++l->owed;
  }
  l->phase = phase;
  l->frac = 0;
}

float fm1_mp_lfo_value(const fm1_mp_lfo_t *l) {
  const uint32_t p = l->phase;
  float v;
  switch (l->shape) {
    case FM1_MP_LFO_TRIANGLE: v = 4.0f * fold(p); break;
    case FM1_MP_LFO_SAW_UP: v = (float)p * (2.0f / TWO32F) - 1.0f; break;
    case FM1_MP_LFO_SAW_DOWN: v = 1.0f - (float)p * (2.0f / TWO32F); break;
    case FM1_MP_LFO_SQUARE: v = (uint64_t)p < l->pw ? 1.0f : -1.0f; break;
    case FM1_MP_LFO_SMOOTH_RANDOM: v = l->prev + (l->next - l->prev) * smoothstep(p); break;
    case FM1_MP_LFO_SAMPLE_HOLD: v = l->next; break;
    case FM1_MP_LFO_RANDOM_WALK:
      v = l->walk_prev + (l->walk_next - l->walk_prev) * smoothstep(p);
      break;
    default: v = sin_quarter(fold(p)); break;
  }
  return mp_clampf(v, -1.0f, 1.0f, 0.0f);
}

float fm1_mp_lfo_process(fm1_mp_lfo_t *l, uint32_t n) {
  advance(l, n);
  return fm1_mp_lfo_value(l);
}

void fm1_mp_lfo_render(fm1_mp_lfo_t *l, float *out, uint32_t n) {
  uint32_t i;
  for (i = 0; i < n; ++i) {
    advance(l, 1);
    out[i] = fm1_mp_lfo_value(l);
  }
}
