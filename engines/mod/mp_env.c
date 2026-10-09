/* mp_env.c -- the multistage envelope (fm1_mp.h).
 *
 * Reimplemented in C99 after Peaks' MultistageEnvelope, Copyright 2013 Emilie
 * Gillet, MIT: pichenettes/eurorack at 08460a6,
 * peaks/modulations/multistage_envelope.h (the presets, set_adsr..set_adar_loop)
 * and multistage_envelope.cc (Process). The structure is Peaks': levels,
 * times and shapes per segment, a sustain point that holds while the gate is
 * high and that the gate's fall jumps to, a loop from loop_end back to
 * loop_start, a uint32 phase whose overflow ends a segment (the overshoot is
 * dropped, as Peaks does), retrigger from the current value unless hard reset
 * is on. The differences are in engines/mod/README.md. */
#include "mp_int.h"

float fm1_mp_env_curve_at(uint8_t c, uint32_t phase) {
  switch (c) {
    case FM1_MP_CURVE_EXPO: return mp_table(fm1_mp_curve_expo, phase);
    case FM1_MP_CURVE_QUARTIC: return mp_table(fm1_mp_curve_quartic, phase);
    case FM1_MP_CURVE_LOG: return mp_table(fm1_mp_curve_log, phase);
    case FM1_MP_CURVE_SMOOTH: {
      float t = (float)phase / 4294967296.0f;
      return t * t * (3.0f - 2.0f * t);
    }
    default: return (float)phase * (1.0f / 4294967296.0f);
  }
}

static uint32_t seconds_to_inc(float seconds, float sample_rate) {
  const float samples = mp_clampf(seconds, 0.0f, 3600.0f, 0.0f) * sample_rate;
  float inc;
  if (samples <= 1.0f) return 0xFFFFFFFFu;
  inc = 4294967296.0f / samples;
  if (inc >= 4294967040.0f) return 0xFFFFFFFFu; /* the largest float below 2^32 */
  return inc < 1.0f ? 1u : (uint32_t)inc;
}

static int is_done(const fm1_mp_env_t *e) {
  return e->seg >= e->num_segments;
}

static int frozen(const fm1_mp_env_t *e) {
  return is_done(e) || (e->sustain && e->seg == e->sustain && e->gate);
}

static void next_segment(fm1_mp_env_t *e) {
  e->start = e->level[e->seg + 1];
  e->phase = 0;
  ++e->seg;
  if (e->loop_end > e->loop_start && e->seg == e->loop_end) e->seg = e->loop_start;
}

static void step(fm1_mp_env_t *e) {
  uint64_t sum;
  if (frozen(e)) return;
  sum = (uint64_t)e->phase + e->inc[e->seg];
  if (sum >> 32) {
    next_segment(e);
  } else {
    e->phase = (uint32_t)sum;
  }
}

/* n steps at once: whole segments are skipped by counting the steps to each
 * overflow, so the state is exactly that of n calls to step(). */
static void advance(fm1_mp_env_t *e, uint32_t n) {
  while (n) {
    uint64_t left, steps;
    uint32_t inc;
    if (frozen(e)) return;
    inc = e->inc[e->seg];
    left = 0x100000000ull - e->phase;
    steps = (left + inc - 1u) / inc;
    if ((uint64_t)n < steps) {
      e->phase += (uint32_t)((uint64_t)inc * n);
      return;
    }
    n -= (uint32_t)steps;
    next_segment(e);
  }
}

float fm1_mp_env_value(const fm1_mp_env_t *e) {
  float a, b;
  if (is_done(e)) return e->start;
  a = e->start;
  b = e->level[e->seg + 1];
  return mp_clampf(a + (b - a) * fm1_mp_env_curve_at(e->curve[e->seg], e->phase), -1.0f, 1.0f, 0.0f);
}

/* After a change of shape: a finished envelope stays finished (at its value),
 * a running one carries on in its segment, unless that segment is gone. */
static void reshape(fm1_mp_env_t *e, int segments, int sustain, int loop_start,
                    int loop_end, float value, int was_done) {
  if (segments < 1) segments = 1;
  if (segments > FM1_MP_ENV_MAX_SEGMENTS) segments = FM1_MP_ENV_MAX_SEGMENTS;
  e->num_segments = (uint8_t)segments;
  e->sustain = (uint8_t)((sustain >= 1 && sustain < segments) ? sustain : 0);
  if (loop_start >= 0 && loop_start < loop_end && loop_end <= segments) {
    e->loop_start = (uint8_t)loop_start;
    e->loop_end = (uint8_t)loop_end;
  } else {
    e->loop_start = e->loop_end = 0;
  }
  if (was_done || e->seg >= e->num_segments) {
    e->seg = e->num_segments;
    e->start = value;
    e->phase = 0;
  }
}

void fm1_mp_env_set_segment(fm1_mp_env_t *e, int i, float end_level, float seconds,
                            int curve) {
  if (i < 0 || i >= FM1_MP_ENV_MAX_SEGMENTS) return;
  e->level[i + 1] = mp_clampf(end_level, -1.0f, 1.0f, 0.0f);
  e->inc[i] = seconds_to_inc(seconds, e->sample_rate);
  e->curve[i] = (uint8_t)((curve >= 0 && curve < FM1_MP_CURVE_COUNT) ? curve : FM1_MP_CURVE_LINEAR);
}

void fm1_mp_env_set_start_level(fm1_mp_env_t *e, float level) {
  e->level[0] = mp_clampf(level, -1.0f, 1.0f, 0.0f);
}

void fm1_mp_env_configure(fm1_mp_env_t *e, int segments, int sustain, int loop_start,
                          int loop_end) {
  reshape(e, segments, sustain, loop_start, loop_end, fm1_mp_env_value(e), is_done(e));
}

void fm1_mp_env_set_adsr(fm1_mp_env_t *e, float a, float d, float s, float r, int curve,
                         int loop) {
  const float v = fm1_mp_env_value(e);
  const int was_done = is_done(e);
  s = mp_clampf(s, 0.0f, 1.0f, 0.0f);
  e->delay_stage = 0;
  e->level[0] = 0.0f;
  fm1_mp_env_set_segment(e, 0, 1.0f, a, curve);
  if (loop == FM1_MP_ENV_LOOP_AD) {
    /* A and D cycle 0 -> 1 -> 0; segment 2 is the release. */
    fm1_mp_env_set_segment(e, 1, 0.0f, d, curve);
    fm1_mp_env_set_segment(e, 2, 0.0f, r, curve);
    reshape(e, 3, 2, 0, 2, v, was_done);
  } else if (loop == FM1_MP_ENV_LOOP_ADR) {
    /* A, D and R cycle 0 -> 1 -> s -> 0; segment 3 is the release. */
    fm1_mp_env_set_segment(e, 1, s, d, curve);
    fm1_mp_env_set_segment(e, 2, 0.0f, r, curve);
    fm1_mp_env_set_segment(e, 3, 0.0f, r, curve);
    reshape(e, 4, 3, 0, 3, v, was_done);
  } else {
    /* Peaks' set_adsr: segment 2 holds at s, then releases. */
    fm1_mp_env_set_segment(e, 1, s, d, curve);
    fm1_mp_env_set_segment(e, 2, 0.0f, r, curve);
    reshape(e, 3, 2, 0, 0, v, was_done);
  }
}

void fm1_mp_env_set_ad(fm1_mp_env_t *e, float a, float d, int curve, int loop) {
  const float v = fm1_mp_env_value(e);
  const int was_done = is_done(e);
  e->delay_stage = 0;
  e->level[0] = 0.0f;
  fm1_mp_env_set_segment(e, 0, 1.0f, a, curve);
  fm1_mp_env_set_segment(e, 1, 0.0f, d, curve);
  reshape(e, 2, 0, 0, loop ? 2 : 0, v, was_done);
}


/* Always reserve segment 0 for delay, so changing Delay during a note does
 * not renumber its running stages. Loops start at attack, without pre-delay. */
void fm1_mp_env_set_delayed(fm1_mp_env_t *e, float delay, float a, float d,
                            float s, float r, int curve, int loop, int trigger) {
  const float v = fm1_mp_env_value(e);
  const int was_done = is_done(e);
  delay = mp_clampf(delay, 0.0f, 8.0f, 0.0f);
  s = mp_clampf(s, 0.0f, 1.0f, 0.0f);
  e->delay_stage = delay > 0.0f ? 1 : 2;
  e->level[0] = 0.0f;
  fm1_mp_env_set_segment(e, 0, 0.0f, delay, FM1_MP_CURVE_LINEAR);
  fm1_mp_env_set_segment(e, 1, 1.0f, a, curve);
  if (trigger) {
    fm1_mp_env_set_segment(e, 2, 0.0f, d, curve);
    reshape(e, 3, 0, loop ? 1 : 0, loop ? 3 : 0, v, was_done);
  } else if (loop == FM1_MP_ENV_LOOP_ADR) {
    fm1_mp_env_set_segment(e, 2, s, d, curve);
    fm1_mp_env_set_segment(e, 3, 0.0f, r, curve);
    fm1_mp_env_set_segment(e, 4, 0.0f, r, curve);
    reshape(e, 5, 4, 1, 4, v, was_done);
  } else {
    fm1_mp_env_set_segment(e, 2, loop == FM1_MP_ENV_LOOP_AD ? 0.0f : s, d, curve);
    fm1_mp_env_set_segment(e, 3, 0.0f, r, curve);
    reshape(e, 4, 3, loop == FM1_MP_ENV_LOOP_AD ? 1 : 0,
            loop == FM1_MP_ENV_LOOP_AD ? 3 : 0, v, was_done);
  }
}

void fm1_mp_env_init(fm1_mp_env_t *e, float sample_rate) {
  int i;
  e->sample_rate = mp_rate(sample_rate);
  for (i = 0; i <= FM1_MP_ENV_MAX_SEGMENTS; ++i) e->level[i] = 0.0f;
  for (i = 0; i < FM1_MP_ENV_MAX_SEGMENTS; ++i) {
    e->inc[i] = 0xFFFFFFFFu;
    e->curve[i] = FM1_MP_CURVE_LINEAR;
  }
  e->start = 0.0f;
  e->phase = 0;
  e->num_segments = 0;
  e->seg = 0;
  e->sustain = e->loop_start = e->loop_end = 0;
  e->gate = 0;
  e->hard_reset = 0;
  e->delay_stage = 0;
  fm1_mp_env_set_adsr(e, 0.002f, 0.25f, 0.5f, 0.5f, FM1_MP_CURVE_EXPO, FM1_MP_ENV_LOOP_OFF);
  e->seg = e->num_segments;
  e->start = 0.0f;
}

void fm1_mp_env_set_hard_reset(fm1_mp_env_t *e, int on) {
  e->hard_reset = (uint8_t)(on != 0);
}

static void attack(fm1_mp_env_t *e) {
  e->start = (e->delay_stage == 1 || is_done(e) || e->hard_reset) ? e->level[0] : fm1_mp_env_value(e);
  e->seg = e->delay_stage == 2 ? 1 : 0;
  e->phase = 0;
}

void fm1_mp_env_gate(fm1_mp_env_t *e, int high) {
  high = high != 0;
  if (high && !e->gate) {
    attack(e);
  } else if (!high && e->gate && e->sustain && !is_done(e)) {
    e->start = fm1_mp_env_value(e);
    e->seg = e->sustain;
    e->phase = 0;
  }
  e->gate = (uint8_t)high;
}

void fm1_mp_env_trigger(fm1_mp_env_t *e) {
  attack(e);
  e->gate = 1;
}

float fm1_mp_env_process(fm1_mp_env_t *e, uint32_t n) {
  advance(e, n);
  return fm1_mp_env_value(e);
}

void fm1_mp_env_render(fm1_mp_env_t *e, float *out, uint32_t n) {
  uint32_t i;
  for (i = 0; i < n; ++i) {
    step(e);
    out[i] = fm1_mp_env_value(e);
  }
}

int fm1_mp_env_done(const fm1_mp_env_t *e) {
  return is_done(e);
}

float fm1_mp_env_time_from_knob(float k) {
  float pos, f;
  int i;
  k = mp_clampf(k, 0.0f, 1.0f, 0.0f);
  pos = k * 256.0f;
  i = (int)pos;
  if (i >= 256) return fm1_mp_env_times[256];
  f = pos - (float)i;
  return fm1_mp_env_times[i] + (fm1_mp_env_times[i + 1] - fm1_mp_env_times[i]) * f;
}
