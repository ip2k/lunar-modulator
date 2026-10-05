/* kinds/mod_chance.c -- the Chance module kind (docs/16 §3.4; the options
 * note's CHANCE source): random voltages and sample-and-hold.
 *
 * A clock: TRIG's rising edges when a cable reaches TRIG, else an internal
 * clock at Rate (0.01-100 Hz, the LFO's scale). Mode:
 *   S&H     each clock takes a new value: IN when a cable reaches IN, else a
 *           random draw in -1..1;
 *   T&H     follows IN (or fresh noise, one draw a tick) while TRIG is high,
 *           holds while it is low; unpatched, TRIG counts as high, so with a
 *           cable into IN it passes IN straight through (a chain link);
 *   Smooth  glides from the last draw to a new one over one clock period;
 *   Drift   a random walk: each clock moves the target by up to Walk.
 * Smooth and Drift ignore IN. Level scales HELD. SMOOTH is HELD through a
 * linear slew (Slew: 0 off, else Peaks' knob-to-time curve, 0.5 ms to 8 s,
 * for a full-scale move). STEP is a trigger at each new value. Each
 * instance draws from its own generator, seeded per preset and position, so
 * a preset repeats exactly.
 *
 * Our own code, MIT, on fm1_mp's LFO (its random shapes), slew and
 * generator. After DaisySP's SampleHold (Electrosmith, Paul Batchelor, MIT)
 * and the random voltages of Music Thing Modular's Workshop System Computer
 * card 106 (Matt Allison, MIT); no code taken from either. */
#include "mod_int.h"

enum { P_MODE, P_RATE, P_SLEW, P_LEVEL, P_WALK, P_IN, P_COUNT };
enum { O_HELD, O_SMOOTH, O_STEP };
enum { M_SH, M_TH, M_SMOOTH, M_DRIFT };

static const char *const kModes[] = { "S&H", "T&H", "Smooth", "Drift" };

#define MOD FM1_PARAM_MOD
static const fm1_param_t kParams[P_COUNT] = {
  { "Mode", FM1_PARAM_ENUM, 0.0f, 3.0f, 0.0f, kModes, 0, 1, MOD, FM1_UNIT_NONE, "Mode" },
  { "Rate", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Rate" },
  { "Slew", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.0f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Slew" },
  { "Level", FM1_PARAM_FLOAT, -1.0f, 1.0f, 1.0f, NULL, 0, 4, MOD, FM1_UNIT_NONE, "Level" },
  { "Walk", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.25f, NULL, 1, 5, MOD, FM1_UNIT_NONE, "Walk" },
  { "In", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 6, FM1_PARAM_INPUT, FM1_UNIT_NONE, "In" },
};
#undef MOD

static const fm1_port_t kGates[] = { { "Trig", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };
static const fm1_port_t kOuts[] = { { "Held", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Smth", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Step", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };

typedef struct chance {
  fm1_mp_lfo_t clk;            /* the internal clock and the random shapes */
  fm1_mp_slew_t slew;
  fm1_mp_rng_t rng;            /* T&H's noise */
  float rate_hz, slew_s;       /* last applied */
  float sampled;               /* S&H's sample of IN */
  float tracked;               /* T&H's value */
  mod_trig_t step;
  uint8_t mode, lfo_mode, high, reserved;
} chance_t;

static size_t chance_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(chance_t);
}

static void *chance_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  chance_t *s = (chance_t *)mem;
  const float rate = host ? host->sample_rate : 44118.0f;
  fm1_mp_lfo_init(&s->clk, rate, seed);
  fm1_mp_lfo_set_shape(&s->clk, FM1_MP_LFO_SAMPLE_HOLD);
  fm1_mp_slew_init(&s->slew, rate);
  fm1_mp_rng_seed(&s->rng, mod_mix(seed, 0x5EEDu));
  s->rate_hz = 1.0f;
  s->slew_s = 0.0f;
  s->sampled = s->tracked = 0.0f;
  mod_trig_init(&s->step);
  s->mode = M_SH;
  s->lfo_mode = FM1_MP_LFO_FREE;
  s->high = 0;
  s->reserved = 0;
  return s;
}

/* The internal clock: n frames from *at, a STEP at each carry; S&H takes
 * IN there when IN is patched. */
static void clock_run(chance_t *s, uint32_t n, uint32_t *at, fm1_mod_gate_t *step, int take,
                      float in) {
  while (n) {
    const uint32_t w = s->clk.mode == FM1_MP_LFO_FREE ? mod_lfo_to_wrap(&s->clk, n) : 0u;
    if (!w) {
      fm1_mp_lfo_process(&s->clk, n);
      *at += n;
      return;
    }
    fm1_mp_lfo_process(&s->clk, w);
    *at += w;
    n -= w;
    mod_trig_fire(&s->step, step, *at);   /* the boundary after the carry */
    if (take) s->sampled = in;
  }
}

static void chance_process(void *self, const fm1_mod_io_t *io) {
  chance_t *s = (chance_t *)self;
  const float *p = io->p;
  const unsigned mode = (unsigned)p[P_MODE];
  const int patched = (int)(io->gate_connected & 1u);
  const int in_patched = (int)((io->routed >> P_IN) & 1u);
  const float in = p[P_IN];
  const fm1_mod_gate_t *trig = &io->gate[0];
  fm1_mod_gate_t *step = &io->gout[O_STEP];
  const float hz = mod_rate_hz(p[P_RATE]);
  const float slew_s = p[P_SLEW] > 0.0f ? fm1_mp_env_time_from_knob(p[P_SLEW]) : 0.0f;
  const int lfo_mode = patched ? FM1_MP_LFO_ONE_SHOT : FM1_MP_LFO_FREE;
  uint32_t at = 0;
  unsigned e;
  float x;

  if (mode != s->mode) {
    s->mode = (uint8_t)mode;
    fm1_mp_lfo_set_shape(&s->clk, mode == M_SMOOTH ? FM1_MP_LFO_SMOOTH_RANDOM
                                  : mode == M_DRIFT ? FM1_MP_LFO_RANDOM_WALK
                                                    : FM1_MP_LFO_SAMPLE_HOLD);
  }
  if (lfo_mode != s->lfo_mode) {
    s->lfo_mode = (uint8_t)lfo_mode;
    fm1_mp_lfo_set_mode(&s->clk, lfo_mode);
  }
  if (mod_bits(hz) != mod_bits(s->rate_hz)) {
    fm1_mp_lfo_set_rate(&s->clk, hz, 1.0f);
    s->rate_hz = hz;
  }
  fm1_mp_lfo_set_walk(&s->clk, p[P_WALK]);
  if (mod_bits(slew_s) != mod_bits(s->slew_s)) {
    fm1_mp_slew_set_times(&s->slew, slew_s, slew_s);
    s->slew_s = slew_s;
  }
  mod_trig_begin(&s->step, step);

  if (patched) {
    s->high = trig->start;
    for (e = 0; e < trig->n; ++e) {
      const unsigned f = trig->ev[e].frame < at ? at : trig->ev[e].frame;
      clock_run(s, f - at, &at, step, 0, in);
      s->high = trig->ev[e].high;
      if (!s->high) continue;
      if (mode != M_TH) {
        fm1_mp_lfo_reset(&s->clk);   /* a new draw, and Smooth's glide starts */
        if (in_patched) s->sampled = in;
      }
      mod_trig_fire(&s->step, step, f);
    }
    clock_run(s, FM1_MOD_TICK - at, &at, step, 0, in);
  } else {
    s->high = 1;
    clock_run(s, FM1_MOD_TICK, &at, step, mode == M_SH && in_patched, in);
  }

  if (mode == M_TH) {
    if (s->high) s->tracked = in_patched ? in : fm1_mp_rng_bipolar(&s->rng);
    x = s->tracked;
  } else if (mode == M_SH && in_patched) {
    x = s->sampled;
  } else {
    x = fm1_mp_lfo_value(&s->clk);
  }
  io->out[O_HELD] = mod_clampf(p[P_LEVEL] * x, -1.0f, 1.0f, 0.0f);
  io->out[O_SMOOTH] = fm1_mp_slew_process(&s->slew, io->out[O_HELD], FM1_MOD_TICK);
  mod_trig_end(&s->step, step, &io->out[O_STEP]);
}

static void chance_reset(void *self, uint32_t why) {
  chance_t *s = (chance_t *)self;
  if (why == FM1_MOD_RESET_PRESET) {
    fm1_mp_lfo_reset(&s->clk);
    fm1_mp_slew_reset(&s->slew, 0.0f);
    s->sampled = s->tracked = 0.0f;
  }
}

const fm1_mod_kind_t fm1_mod_kind_chance = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "chance", 0x43484E20u /* "CHN " */, "Chance", "CHN",
  "Our own, on fm1_mp's LFO, slew and generator. After DaisySP's SampleHold (Electrosmith, "
  "Paul Batchelor, MIT) and Music Thing Modular Workshop System Computer card 106 (Matt "
  "Allison, MIT).",
  kParams, P_COUNT, 1, 3, kGates, kOuts, 0, 0,
  chance_size, chance_create, NULL, chance_reset, chance_process, NULL, NULL, NULL
};
