/* kinds/mod_env.c -- the Envelope module kind (docs/16 §3.1; the options
 * note's envelope), a wrapper round fm1_mp's multistage envelope after
 * Mutable Instruments' Peaks.
 *
 * Attack, Decay and Release are Peaks' knob-to-time curve (0.5 ms to 8 s);
 * Sustain is a level. Curve is Peaks' linear, exponential or quartic. Mode
 * Gate is an ADSR that follows GATE (unpatched: RTRG, the keys retriggered,
 * so with no cable every note restarts it, a note over a held one too; the
 * owner's decision of 2026-10-05; MG1 to MG3 normalled it to KEY, the
 * legato gate). Run per voice (MG9), an unpatched GATE is the voice's own
 * note, and each note has its envelope; Loop repeats A-D or A-D-R while
 * the gate is high. Mode Trigger is Peaks' AD: each rising edge starts it,
 * the fall is ignored, and Loop cycles it. A retrigger starts from the
 * current value, as on Peaks. Level scales the output.
 *
 * Outputs: ENV (0..1); EOC, a trigger where the envelope ends or a loop
 * pass completes; ACTIVE, high from a start until the envelope ends. Edges
 * keep their frame inside the tick.
 *
 * Our own code, MIT, after Peaks (Emilie Gillet, MIT); engines/mod/README.md
 * lists where fm1_mp's envelope differs from Peaks. */
#include "mod_int.h"

enum { P_ATK, P_DEC, P_SUS, P_REL, P_CURVE, P_LOOP, P_MODE, P_LEVEL, P_COUNT };
enum { O_ENV, O_EOC, O_ACTIVE };
enum { M_GATE, M_TRIGGER };

static const char *const kCurves[] = { "Linear", "Expo", "Quartic" };
static const char *const kLoops[] = { "Off", "AD", "ADR" };
static const char *const kModes[] = { "Gate", "Trigger" };

#define MOD FM1_PARAM_MOD
static const fm1_param_t kParams[P_COUNT] = {
  { "Attack", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.1f, NULL, 0, 1, MOD, FM1_UNIT_NONE, "Atk" },
  { "Decay", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Dec" },
  { "Sustain", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.7f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Sus" },
  { "Release", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 4, MOD, FM1_UNIT_NONE, "Rel" },
  { "Curve", FM1_PARAM_ENUM, 0.0f, 2.0f, 1.0f, kCurves, 1, 5, 0, FM1_UNIT_NONE, "Curve" },
  { "Loop", FM1_PARAM_ENUM, 0.0f, 2.0f, 0.0f, kLoops, 1, 6, 0, FM1_UNIT_NONE, "Loop" },
  { "Mode", FM1_PARAM_ENUM, 0.0f, 1.0f, 0.0f, kModes, 1, 7, 0, FM1_UNIT_NONE, "Mode" },
  { "Level", FM1_PARAM_FLOAT, 0.0f, 1.0f, 1.0f, NULL, 1, 8, MOD, FM1_UNIT_NONE, "Level" },
};
#undef MOD

static const fm1_port_t kGates[] = { { "Gate", FM1_PORT_GATE, FM1_UNIT_NONE, FM1_MOD_SRC_RTRG, 0 } };
static const fm1_port_t kOuts[] = { { "Env", FM1_PORT_CV_UNI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "EOC", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Act", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };

typedef struct env {
  fm1_mp_env_t env;
  uint32_t shape[4];           /* the knob values last applied, as bits */
  mod_trig_t eoc;
  uint8_t curve, loop, mode, active, configured, fall_next, reserved[2];
} env_t;

static size_t env_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(env_t);
}

static void *env_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  env_t *s = (env_t *)mem;
  unsigned i;
  (void)seed;
  fm1_mp_env_init(&s->env, host ? host->sample_rate : 44118.0f);
  for (i = 0; i < 4; ++i) s->shape[i] = 0;
  mod_trig_init(&s->eoc);
  s->curve = s->loop = s->mode = s->active = s->configured = s->fall_next = 0;
  s->reserved[0] = s->reserved[1] = 0;
  return s;
}

static void configure(env_t *s, const float *p) {
  const unsigned curve = (unsigned)p[P_CURVE], loop = (unsigned)p[P_LOOP], mode = (unsigned)p[P_MODE];
  const uint32_t a = mod_bits(p[P_ATK]), d = mod_bits(p[P_DEC]), su = mod_bits(p[P_SUS]),
                 r = mod_bits(p[P_REL]);
  if (s->configured && a == s->shape[0] && d == s->shape[1] && su == s->shape[2] &&
      r == s->shape[3] && curve == s->curve && loop == s->loop && mode == s->mode) {
    return;
  }
  if (mode == M_TRIGGER) {
    fm1_mp_env_set_ad(&s->env, fm1_mp_env_time_from_knob(p[P_ATK]),
                      fm1_mp_env_time_from_knob(p[P_DEC]), (int)curve, loop != 0);
  } else {
    fm1_mp_env_set_adsr(&s->env, fm1_mp_env_time_from_knob(p[P_ATK]),
                        fm1_mp_env_time_from_knob(p[P_DEC]), p[P_SUS],
                        fm1_mp_env_time_from_knob(p[P_REL]), (int)curve, (int)loop);
  }
  s->shape[0] = a;
  s->shape[1] = d;
  s->shape[2] = su;
  s->shape[3] = r;
  s->curve = (uint8_t)curve;
  s->loop = (uint8_t)loop;
  s->mode = (uint8_t)mode;
  s->configured = 1;
}

static int frozen(const fm1_mp_env_t *e) {
  return e->seg >= e->num_segments || (e->sustain && e->seg == e->sustain && e->gate);
}

/* Advances n frames from *at, a segment at a time, so the frame where the
 * envelope ends, or a loop pass completes, is known: EOC at the boundary
 * after its last sample, and ACTIVE falls there (at the next tick's frame 0
 * when that is this tick's end). */
static void env_run(env_t *s, uint32_t n, uint32_t *at, fm1_mod_gate_t *eoc,
                    fm1_mod_gate_t *active) {
  fm1_mp_env_t *e = &s->env;
  while (n) {
    uint64_t steps;
    unsigned last;
    if (frozen(e)) break;
    steps = (0x100000000ull - e->phase + e->inc[e->seg] - 1u) / e->inc[e->seg];
    if ((uint64_t)n < steps) {
      fm1_mp_env_process(e, n);
      break;
    }
    last = e->seg;
    fm1_mp_env_process(e, (uint32_t)steps);
    *at += (uint32_t)steps;
    n -= (uint32_t)steps;
    if (fm1_mp_env_done(e)) {
      mod_trig_fire(&s->eoc, eoc, *at);
      if (*at < FM1_MOD_TICK) {
        mod_gate_edge(active, *at, 0, NULL);
        s->active = 0;
      } else {
        s->fall_next = 1;
      }
    } else if (e->loop_end > e->loop_start && last + 1u == e->loop_end) {
      mod_trig_fire(&s->eoc, eoc, *at);
    }
  }
  *at += n;
}

static void env_process(void *self, const fm1_mod_io_t *io) {
  env_t *s = (env_t *)self;
  const fm1_mod_gate_t *gate = &io->gate[0];
  fm1_mod_gate_t *eoc = &io->gout[O_EOC], *active = &io->gout[O_ACTIVE];
  uint32_t at = 0;
  unsigned e;
  configure(s, io->p);
  mod_trig_begin(&s->eoc, eoc);
  mod_gate_clear(active, s->active);
  if (s->fall_next) {
    s->fall_next = 0;
    mod_gate_edge(active, 0, 0, NULL);
    s->active = 0;
  }
  for (e = 0; e < gate->n; ++e) {
    const unsigned f = gate->ev[e].frame < at ? at : gate->ev[e].frame;
    env_run(s, f - at, &at, eoc, active);
    if (s->mode == M_TRIGGER) {
      if (gate->ev[e].high) fm1_mp_env_trigger(&s->env);
    } else {
      fm1_mp_env_gate(&s->env, gate->ev[e].high);
    }
    if (!fm1_mp_env_done(&s->env) && !s->active) {
      mod_gate_edge(active, f, 1, NULL);
      s->active = 1;
    }
  }
  env_run(s, FM1_MOD_TICK - at, &at, eoc, active);
  io->out[O_ENV] = io->p[P_LEVEL] * fm1_mp_env_value(&s->env);
  mod_trig_end(&s->eoc, eoc, &io->out[O_EOC]);
  io->out[O_ACTIVE] = (float)s->active;
}

static void env_reset(void *self, uint32_t why) {
  env_t *s = (env_t *)self;
  if (why == FM1_MOD_RESET_PRESET) {
    fm1_mp_env_init(&s->env, s->env.sample_rate);
    s->configured = 0;
    /* ACT falls at the next tick's first frame, as an edge: the runtime
     * keeps a gate output's level from tick to tick. */
    if (s->active) s->fall_next = 1;
  }
}

const fm1_mod_kind_t fm1_mod_kind_env = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "env", 0x454E5620u /* "ENV " */, "Envelope", "ENV",
  "Our own, on fm1_mp's multistage envelope after Mutable Instruments' Peaks (Emilie Gillet, "
  "MIT): its segments, presets, curves and knob-to-time curve.",
  kParams, P_COUNT, 1, 3, kGates, kOuts, FM1_MOD_KIND_POLY_OK, 0, 0,
  env_size, env_create, NULL, env_reset, env_process, NULL, NULL, NULL
};
