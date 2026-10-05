/* mod_mi.c -- C ports of Mutable Instruments' Peaks bouncing ball, pulse
 * shaper and pulse randomizer and Braids' quantizer (mod_mi.h), for the
 * Bounce, Burst and Quantize kinds (docs/16 MG2). Ported from
 * peaks/modulations/bouncing_ball.h, peaks/pulse_processor/pulse_shaper.cc,
 * peaks/pulse_processor/pulse_randomizer.cc and braids/quantizer.cc at
 * eurorack 08460a6 (vendored in engines/third_party/mutable), statement for
 * statement; the comments mark what is ours.
 *
 * Copyright 2013 Emilie Gillet (Peaks); copyright 2015 Emilie Gillet
 * (Braids). C port and additions copyright 2026 the Lunar Modulator
 * authors.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE. */
#include "mod_mi.h"

#include "mod_int.h"

uint16_t mod_mi_interpolate88(const uint16_t *table, uint16_t index) {
  const int32_t a = table[index >> 8];
  const int32_t b = table[(index >> 8) + 1];
  return (uint16_t)(a + ((b - a) * (int32_t)(index & 0xff) >> 8));
}

/* ---- the bouncing ball ------------------------------------------------------ */

void mod_mi_bounce_init(mod_mi_bounce_t *b) {
  b->initial_amplitude = (int32_t)65535 * 16384;   /* 65535L << 14 */
  b->gravity = 40;
  b->bounce_loss = 4095;
  b->initial_velocity = 0;
  b->velocity = 0;
  b->position = 0;
}

void mod_mi_bounce_configure(mod_mi_bounce_t *b, const uint16_t p[4]) {
  uint32_t loss = 65535u - p[1];
  const int16_t velocity = (int16_t)((int32_t)p[3] - 32768);
  b->gravity = mod_mi_interpolate88(mod_mi_lut_gravity, p[0]);
  loss = loss * loss >> 16;
  b->bounce_loss = 4095 - (int32_t)(loss >> 4);
  b->initial_amplitude = (int32_t)p[2] * 16384;            /* << 14 */
  b->initial_velocity = (int32_t)velocity * 16;            /* << 4, defined for negatives */
}

int16_t mod_mi_bounce_sample(mod_mi_bounce_t *b, int rising, int *floor) {
  *floor = 0;
  if (rising) {
    b->velocity = b->initial_velocity;
    b->position = b->initial_amplitude;
  }
  b->velocity -= b->gravity;
  b->position += b->velocity;
  if (b->position < 0) {
    b->position = 0;
    b->velocity = -(b->velocity >> 12) * b->bounce_loss;
    *floor = 1;
  }
  if (b->position > (int32_t)32767 * 32768) {              /* 32767L << 15 */
    b->position = (int32_t)32767 * 32768;
    b->velocity = -(b->velocity >> 12) * b->bounce_loss;
  }
  return (int16_t)(b->position >> 15);
}

/* ---- the pulse shaper --------------------------------------------------------- */

void mod_mi_shaper_init(mod_mi_shaper_t *s) {
  unsigned i;
  s->initial_delay = s->duration = s->delay = s->num_repetitions = 0;
  for (i = 0; i < MOD_MI_PULSES; ++i) {
    s->pulse[i].initial_delay_counter = s->pulse[i].duration_counter = 0;
    s->pulse[i].delay_counter = s->pulse[i].repetition_counter = 0;
  }
  s->previous_num_pulses = 0;
  s->retrig_counter = 0;
  s->accel = 0;
  s->clocked = 0;
}

void mod_mi_shaper_configure(mod_mi_shaper_t *s, const uint16_t p[4]) {
  s->initial_delay = p[0];
  s->duration = (uint16_t)(p[1] >> 1);
  s->delay = (uint16_t)(p[2] >> 1);
  s->num_repetitions = (uint16_t)(p[3] >> 13);
}

static uint16_t shaper_duration(const mod_mi_shaper_t *s) {
  return mod_mi_interpolate88(mod_mi_lut_delay_times, s->duration);
}

static uint16_t shaper_initial_delay(const mod_mi_shaper_t *s) {
  return mod_mi_interpolate88(mod_mi_lut_delay_times, s->initial_delay);
}

/* Peaks' delay(), or ours: a clocked gap, and ACCEL's factor for the gap
 * after the pulse numbered `gap` (0 for the first). */
static uint16_t shaper_delay(const mod_mi_shaper_t *s, int gap) {
  uint32_t d = s->clocked ? s->clocked - 1u
                          : (uint16_t)(mod_mi_interpolate88(mod_mi_lut_delay_times, s->delay) - 1);
  if (s->accel && gap > 0) {
    const float f = fm1_mod_exp2(-(float)s->accel * (0.5f / 16384.0f) * (float)gap);
    const float x = (float)d * f;
    d = x >= 65535.0f ? 65535u : (uint32_t)x;
  }
  return (uint16_t)d;
}

int16_t mod_mi_shaper_call(mod_mi_shaper_t *s, int new_pulse) {
  uint8_t num_pulses = 0;
  unsigned i;
  for (i = 0; i < MOD_MI_PULSES; ++i) {
    mod_mi_pulse_t *p = &s->pulse[i];
    if (p->repetition_counter) {
      /* A duration longer than the delay is cut a sample short of it. */
      if (p->delay_counter < p->duration_counter && p->repetition_counter > 1) {
        p->duration_counter = p->delay_counter;
      }
      if (p->initial_delay_counter == 0) {
        if (p->duration_counter) {
          --p->duration_counter;
          ++num_pulses;
        }
        if (p->delay_counter) {
          --p->delay_counter;
        } else {
          --p->repetition_counter;
          p->duration_counter = shaper_duration(s);
          p->delay_counter = shaper_delay(s, (int)s->num_repetitions + 1 - (int)p->repetition_counter);
        }
      } else {
        --p->initial_delay_counter;
      }
    } else if (new_pulse) {
      p->repetition_counter = (uint16_t)(s->num_repetitions + 1u);
      p->initial_delay_counter = shaper_initial_delay(s);
      p->duration_counter = shaper_duration(s);
      p->delay_counter = shaper_delay(s, 0);
      new_pulse = 0;
      num_pulses = (uint8_t)(num_pulses + (p->initial_delay_counter ? 0u : 1u));
    }
  }
  /* Already high and a new pulse arrives: a short dip retriggers. */
  if (s->previous_num_pulses && num_pulses > s->previous_num_pulses) s->retrig_counter = 6;
  s->previous_num_pulses = num_pulses;
  if (s->retrig_counter) --s->retrig_counter;
  return num_pulses > 0 && !s->retrig_counter ? MOD_MI_PULSE_HIGH : 0;
}

int mod_mi_shaper_active(const mod_mi_shaper_t *s) {
  unsigned i;
  for (i = 0; i < MOD_MI_PULSES; ++i) {
    if (s->pulse[i].repetition_counter) return 1;
  }
  return 0;
}

/* ---- the pulse randomizer ------------------------------------------------------- */

/* stmlib::Random::GetWord() on this instance's own state. */
static uint32_t random_word(mod_mi_randomizer_t *r) {
  r->rng = r->rng * 1664525u + 1013904223u;
  return r->rng;
}

/* GetSample(): the word's top half as int16 (two's complement). */
static int32_t random_sample(mod_mi_randomizer_t *r) {
  const int32_t w = (int32_t)(random_word(r) >> 16);
  return w >= 32768 ? w - 65536 : w;
}

void mod_mi_randomizer_init(mod_mi_randomizer_t *r, uint32_t rng) {
  unsigned i;
  r->repetition_probability = 32767;
  r->acceptance_probability = 65535;
  r->delay_average = 32767;
  r->delay_randomness = 0;
  for (i = 0; i < MOD_MI_PULSES; ++i) r->delay_counter[i] = 0xffff;
  r->num_pulses = 0;
  r->retrig_counter = 0;
  r->rng = rng;
}

void mod_mi_randomizer_configure(mod_mi_randomizer_t *r, const uint16_t p[4]) {
  r->acceptance_probability = p[0];
  r->repetition_probability = p[1];
  r->delay_average = (uint16_t)(p[2] >> 1);
  r->delay_randomness = p[3];
}

static uint16_t randomizer_delay(mod_mi_randomizer_t *r) {
  int32_t delay = r->delay_average;
  delay += r->delay_average + (random_sample(r) * (int32_t)r->delay_randomness >> 16);
  if (delay < 0) delay = 0;
  else if (delay > 0xffff) delay = 0xffff;
  return mod_mi_interpolate88(mod_mi_lut_delay_times, (uint16_t)delay);
}

int16_t mod_mi_randomizer_call(mod_mi_randomizer_t *r, int new_pulse) {
  unsigned i;
  if ((random_word(r) >> 16) > r->acceptance_probability) new_pulse = 0;   /* ignored */
  if (new_pulse) ++r->num_pulses;
  for (i = 0; i < MOD_MI_PULSES; ++i) {
    if (r->delay_counter[i] == 0xffff) {
      if (new_pulse) {
        r->delay_counter[i] = randomizer_delay(r);
        new_pulse = 0;
      }
    } else if (r->delay_counter[i]) {
      --r->delay_counter[i];
    } else if ((random_word(r) >> 16) < r->repetition_probability) {
      ++r->num_pulses;
      r->delay_counter[i] = randomizer_delay(r);
    } else {
      r->delay_counter[i] = 0xffff;
    }
  }
  if (r->retrig_counter) {
    --r->retrig_counter;
  } else if (r->num_pulses) {
    r->retrig_counter = 12;
    --r->num_pulses;
  }
  return r->retrig_counter > 6 ? MOD_MI_PULSE_HIGH : 0;
}

int mod_mi_randomizer_active(const mod_mi_randomizer_t *r) {
  unsigned i;
  if (r->num_pulses || r->retrig_counter) return 1;
  for (i = 0; i < MOD_MI_PULSES; ++i) {
    if (r->delay_counter[i] != 0xffff) return 1;
  }
  return 0;
}

/* ---- the quantizer ---------------------------------------------------------------- */

#define MOD_MI_INIT_SCALE 0xFFu        /* Init()'s semitone codebook */

void mod_mi_quantizer_init(mod_mi_quantizer_t *q) {
  q->enabled = 1;
  q->scale = MOD_MI_INIT_SCALE;
  q->codeword = 0;
  q->previous_boundary = 0;
  q->next_boundary = 0;
  q->reserved[0] = q->reserved[1] = 0;
}

void mod_mi_quantizer_configure(mod_mi_quantizer_t *q, unsigned scale) {
  const mod_mi_scale_t *sc;
  if (scale >= MOD_MI_SCALES) scale = 0;
  sc = &mod_mi_scales[scale];
  /* Braids leaves the codebook alone when the scale is off; Init()'s
   * semitones then stay unused, since Process returns the pitch. */
  q->enabled = (uint8_t)(sc->num_notes != 0 && sc->span != 0);
  q->scale = (uint8_t)scale;
  /* Ours: the held cell goes, as after Init(). */
  q->codeword = 0;
  q->previous_boundary = 0;
  q->next_boundary = 0;
}

static int32_t clip16(int32_t x) {
  return x < -32767 ? -32767 : x > 32767 ? 32767 : x;
}

/* int16_t conversion of an int, wrapping as every compiler here does. */
static int32_t wrap16(int32_t x) {
  const uint32_t u = (uint32_t)x & 0xFFFFu;
  return u >= 32768u ? (int32_t)u - 65536 : (int32_t)u;
}

int32_t mod_mi_quantizer_entry(const mod_mi_quantizer_t *q, int i) {
  const mod_mi_scale_t *sc;
  int n, j;
  if (q->scale >= MOD_MI_SCALES) return (int32_t)(i - 64) * 128;   /* Init() */
  sc = &mod_mi_scales[q->scale];
  n = sc->num_notes ? sc->num_notes : 1;
  if (i >= 64) {
    j = i - 64;
    return clip16(sc->notes[j % n] + (int32_t)sc->span * (j / n));
  }
  j = 63 - i;
  return clip16(sc->notes[n - 1 - j % n] + (int32_t)(-(j / n) - 1) * sc->span);
}

int32_t mod_mi_quantizer_process(mod_mi_quantizer_t *q, int32_t pitch, int32_t root) {
  if (!q->enabled) return pitch;
  pitch -= root;
  if (pitch >= q->previous_boundary && pitch <= q->next_boundary) {
    pitch = q->codeword;   /* still in the active codeword's Voronoi cell */
  } else {
    const int32_t key = wrap16(pitch);
    int lo = 3, hi = 126, i, best_i = -1;
    int32_t best = 16384;
    while (lo < hi) {   /* std::upper_bound over codebook_[3..126) */
      const int mid = lo + (hi - lo) / 2;
      if (key < mod_mi_quantizer_entry(q, mid)) hi = mid;
      else lo = mid + 1;
    }
    for (i = lo - 2; i <= lo; ++i) {
      const int32_t d = pitch - mod_mi_quantizer_entry(q, i);
      const int32_t distance = wrap16(d < 0 ? -d : d);
      if (distance < best) {
        best = distance;
        best_i = i;
      }
    }
    if (best_i < 0) best_i = lo - 2;   /* ours: upstream would read codebook_[-1] */
    q->codeword = mod_mi_quantizer_entry(q, best_i);
    /* The cell, enlarged a little for hysteresis. */
    q->previous_boundary = (9 * mod_mi_quantizer_entry(q, best_i - 1) + 7 * q->codeword) >> 4;
    q->next_boundary = (9 * mod_mi_quantizer_entry(q, best_i + 1) + 7 * q->codeword) >> 4;
    pitch = q->codeword;
  }
  return pitch + root;
}
