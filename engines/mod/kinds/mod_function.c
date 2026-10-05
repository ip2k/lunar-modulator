/* kinds/mod_function.c -- the Function module kind (docs/16 §3.1): a
 * function generator, the rise-and-fall core every classic one shares.
 *
 * OUT rises from where it is to Level in Rise, then falls to the floor in
 * Fall (times on Peaks' knob-to-time curve, 0.5 ms to 8 s; with Sync on,
 * the two share one cycle of a division of the sequencer's tempo in the
 * ratio of their knobs). The floor is Floor + IN (IN a bare signal input).
 * A rise or fall always takes its whole time from wherever it starts, as
 * Contour 1 does (Maths keeps its slope instead). Shape bends both, from
 * -1 (fast start: Peaks' exponential curve) through 0 (linear) to +1 (slow
 * start: Peaks' quartic). Mode:
 *   AD     each TRIG (normalled to the note trigger) starts a rise, then a
 *          fall;
 *   AR     rises while GATE (normalled to the key gate) is high, holds at
 *          Level, falls when it drops;
 *   Cycle  rises and falls for ever; TRIG restarts it;
 *   Slew   OUT glides to the floor (Floor + IN) whenever it moves, rising
 *          in Rise and falling in Fall per full-scale move: a lag with a
 *          shape. When the target moves on in the direction OUT is going,
 *          a slow start (Shape above 0) keeps its place on its curve, so a
 *          target that moves every tick cannot hold it at the curve's flat
 *          start; at Shape 0 and below the glide starts afresh from where
 *          OUT is;
 *   Gated  cycles while GATE is high, finishing the cycle it is in.
 * CYCLE high makes any mode but Slew cycle; HOLD high freezes the function
 * where it is. A TRIG is taken only once the function is far enough
 * through its cycle: Retrig 1 always (Contour 1), 0.5 from the start of
 * the fall (Maths), 0 only when idle (Just Friends); the rise then starts
 * from the current value.
 *
 * With Sync on, the sequencer's Start restarts a cycling function at its
 * frame, so synced ones start together.
 *
 * Outputs: OUT (0..1), INV (1 - OUT), UP and DOWN (gates, high while rising
 * and falling), EOR and EOC (triggers at the end of the rise and of the
 * fall), all at their own frames inside the tick.
 *
 * Our own code, MIT, from the published behaviour of Make Noise's Maths,
 * Joranalogue's Contour 1, Serge's DUSG and Befaco's Rampage (closed or
 * GPL; manuals read, no code taken). Shape curves from Mutable Instruments'
 * Peaks (Emilie Gillet, MIT) by way of fm1_mp. */
#include "kinds_int.h"

#include "mp_int.h"

enum { P_RISE, P_FALL, P_SHAPE, P_MODE, P_LEVEL, P_FLOOR, P_RETRIG, P_SYNC, P_IN, P_COUNT };
enum { G_TRIG, G_GATE, G_CYCLE, G_HOLD, E_START };
enum { O_OUT, O_INV, O_UP, O_DOWN, O_EOR, O_EOC };
enum { M_AD, M_AR, M_CYCLE, M_SLEW, M_GATED };
enum { S_IDLE, S_RISE, S_FALL, S_TOP };

static const char *const kModes[] = { "AD", "AR", "Cycle", "Slew", "Gated" };
static const char *const kSyncs[] = { "Off", "4 Bars", "2 Bars", "1 Bar", "1/2", "1/4", "1/8",
                                      "1/16", "1/32", "1/4T", "1/8T", "1/16T", "1/2D", "1/4D",
                                      "1/8D" };
/* Cycles per beat for each Sync value (as the LFO's). */
static const float kSyncRatio[] = { 0.0f, 0.0625f, 0.125f, 0.25f, 0.5f, 1.0f, 2.0f, 4.0f, 8.0f,
                                    1.5f, 3.0f, 6.0f, 1.0f / 3.0f, 2.0f / 3.0f, 4.0f / 3.0f };

#define MOD FM1_PARAM_MOD
static const fm1_param_t kParams[P_COUNT] = {
  { "Rise", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.3f, NULL, 0, 1, MOD, FM1_UNIT_NONE, "Rise" },
  { "Fall", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Fall" },
  { "Shape", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Shape" },
  { "Mode", FM1_PARAM_ENUM, 0.0f, 4.0f, 0.0f, kModes, 0, 4, 0, FM1_UNIT_NONE, "Mode" },
  { "Level", FM1_PARAM_FLOAT, 0.0f, 1.0f, 1.0f, NULL, 1, 5, MOD, FM1_UNIT_NONE, "Level" },
  { "Floor", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.0f, NULL, 1, 6, MOD, FM1_UNIT_NONE, "Floor" },
  { "Retrig", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 1, 7, MOD, FM1_UNIT_NONE, "Retrig" },
  { "Sync", FM1_PARAM_ENUM, 0.0f, 14.0f, 0.0f, kSyncs, 1, 8, 0, FM1_UNIT_NONE, "Sync" },
  { "In", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 2, 9, FM1_PARAM_INPUT, FM1_UNIT_NONE, "In" },
};
#undef MOD

static const fm1_port_t kGates[] = {
  { "Trig", FM1_PORT_GATE, FM1_UNIT_NONE, FM1_MOD_SRC_TRIG, 0 },
  { "Gate", FM1_PORT_GATE, FM1_UNIT_NONE, FM1_MOD_SRC_KEY, 0 },
  { "Cycle", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
  { "Hold", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
};
static const fm1_port_t kOuts[] = { { "Out", FM1_PORT_CV_UNI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Inv", FM1_PORT_CV_UNI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Up", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Down", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "EOR", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "EOC", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };

typedef struct fun {
  float value;                 /* OUT at the current position */
  float from, to;              /* the running segment */
  float span;                  /* Slew: the segment's share of full scale; else 1 */
  float rise_s, fall_s;        /* this tick's times for a full segment */
  float shape, fs;
  uint32_t phase, inc;         /* through the segment, 2^32 at its end */
  mod_trig_t eor, eoc;
  kind_gate_t up, down;
  uint8_t state, mode, gate, cycle, hold, reserved[3];
} fun_t;

typedef struct ctx {
  const fm1_mod_io_t *io;
  float level, floor;
  uint32_t at;                 /* frames of this tick done */
} ctx_t;

static size_t fun_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(fun_t);
}

static void *fun_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  fun_t *s = (fun_t *)mem;
  (void)seed;
  s->value = s->from = s->to = 0.0f;
  s->span = 1.0f;
  s->rise_s = s->fall_s = 0.0f;
  s->shape = 0.0f;
  s->fs = (float)kind_rate(host);
  s->phase = 0;
  s->inc = 0x80000000u;
  mod_trig_init(&s->eor);
  mod_trig_init(&s->eoc);
  kind_gate_init(&s->up);
  kind_gate_init(&s->down);
  s->state = S_IDLE;
  s->mode = M_AD;
  s->gate = s->cycle = s->hold = 0;
  s->reserved[0] = s->reserved[1] = s->reserved[2] = 0;
  return s;
}

/* The phase increment for the running segment: 2^32 over its samples, at
 * least 2 samples. */
static void set_inc(fun_t *s) {
  const float t = (s->state == S_RISE ? s->rise_s : s->fall_s) * s->span;
  const float samples = t * s->fs;
  const float inc = samples > 2.0f ? 4294967296.0f / samples : 2147483648.0f;
  s->inc = inc < 1.0f ? 1u : (uint32_t)inc;
}

static float shaped(uint32_t phase, float shape) {
  const float x = (float)(phase >> 8) * (1.0f / 16777216.0f);
  if (shape < 0.0f) return x - shape * (mp_table(fm1_mp_curve_expo, phase) - x);
  if (shape > 0.0f) return x + shape * (mp_table(fm1_mp_curve_quartic, phase) - x);
  return x;
}

static void start(fun_t *s, ctx_t *c, unsigned state, float to, float span) {
  fm1_mod_gate_t *gout = c->io->gout;
  s->from = s->value;
  s->to = to;
  s->span = span;
  s->phase = 0;
  s->state = (uint8_t)state;
  set_inc(s);
  kind_gate_set(&s->up, &gout[O_UP], c->at, state == S_RISE);
  kind_gate_set(&s->down, &gout[O_DOWN], c->at, state == S_FALL);
}

/* Slew mode: the target moved to `to`. Moving on in the direction OUT is
 * already going, a slow-starting shape keeps its phase: the curve's end
 * moves to the new target and its start moves so that OUT stays where it
 * is, so OUT goes on at the curve's slope there. Restarting would put it
 * back on the flat start each tick a moving target moves, and OUT would
 * barely move. Fast and linear shapes start afresh from OUT (their start
 * is their fast part), as does a glide reversing or near its curve's end. */
static void retarget(fun_t *s, ctx_t *c, float to) {
  const float d = to - s->value;
  const unsigned state = d > 0.0f ? S_RISE : S_FALL;
  if (s->shape > 0.0f && s->state == state) {
    const float y = shaped(s->phase, s->shape);
    if (y < 0.99f) {
      s->from = (s->value - to * y) / (1.0f - y);
      s->to = to;
      s->span = to > s->from ? to - s->from : s->from - to;
      set_inc(s);
      return;
    }
  }
  start(s, c, state, to, d > 0.0f ? d : -d);
}

static int cycling(const fun_t *s) {
  return s->mode != M_SLEW &&
         (s->mode == M_CYCLE || s->cycle || (s->mode == M_GATED && s->gate));
}

static void end_segment(fun_t *s, ctx_t *c) {
  fm1_mod_gate_t *gout = c->io->gout;
  s->value = s->to;
  if (s->state == S_RISE) {
    mod_trig_fire(&s->eor, &gout[O_EOR], c->at);
    if (s->mode == M_SLEW) {
      s->state = S_IDLE;
    } else if (s->mode == M_AR && s->gate && !s->cycle) {
      s->state = S_TOP;
    } else {
      start(s, c, S_FALL, c->floor, 1.0f);
      return;
    }
  } else {
    mod_trig_fire(&s->eoc, &gout[O_EOC], c->at);
    if (cycling(s)) {
      start(s, c, S_RISE, c->level, 1.0f);
      return;
    }
    s->state = S_IDLE;
  }
  kind_gate_set(&s->up, &gout[O_UP], c->at, 0);
  kind_gate_set(&s->down, &gout[O_DOWN], c->at, 0);
}

/* Runs n frames of this tick, ending segments at their frames. */
static void run(fun_t *s, ctx_t *c, uint32_t n) {
  while (n) {
    uint64_t steps;
    if ((s->state != S_RISE && s->state != S_FALL) || s->hold) break;
    steps = (0x100000000ull - s->phase + s->inc - 1u) / s->inc;
    if ((uint64_t)n < steps) {
      s->phase += n * s->inc;
      s->value = s->from + (s->to - s->from) * shaped(s->phase, s->shape);
      break;
    }
    c->at += (uint32_t)steps;
    n -= (uint32_t)steps;
    end_segment(s, c);
  }
  c->at += n;
}

static int accept(const fun_t *s, float retrig) {
  const float x = (float)(s->phase >> 8) * (1.0f / 16777216.0f);
  const float progress = s->state == S_RISE ? 0.5f * x : s->state == S_FALL ? 0.5f + 0.5f * x : 0.5f;
  return s->state == S_IDLE || progress >= 1.0f - retrig;
}

static void fun_process(void *self, const fm1_mod_io_t *io) {
  fun_t *s = (fun_t *)self;
  const float *p = io->p;
  const unsigned sync = (unsigned)p[P_SYNC];
  kind_event_t ev[4u * FM1_MOD_EDGES + 1u];
  ctx_t c;
  unsigned n, e;
  c.io = io;
  c.level = p[P_LEVEL];
  c.floor = mod_clampf(p[P_FLOOR] + p[P_IN], 0.0f, 1.0f, 0.0f);
  c.at = 0;
  s->mode = (uint8_t)p[P_MODE];
  s->shape = p[P_SHAPE];
  if (sync && sync < sizeof(kSyncRatio) / sizeof(kSyncRatio[0]) && io->tp->bpm_x100) {
    const float cycle_s = 6000.0f / ((float)io->tp->bpm_x100 * kSyncRatio[sync]);
    const float sum = p[P_RISE] + p[P_FALL];
    const float share = sum > 0.0f ? p[P_RISE] / sum : 0.5f;
    s->rise_s = cycle_s * share;
    s->fall_s = cycle_s - s->rise_s;
  } else {
    s->rise_s = fm1_mp_env_time_from_knob(p[P_RISE]);
    s->fall_s = fm1_mp_env_time_from_knob(p[P_FALL]);
  }
  if (s->state == S_RISE || s->state == S_FALL) set_inc(s);   /* knobs act at once */

  mod_trig_begin(&s->eor, &io->gout[O_EOR]);
  mod_trig_begin(&s->eoc, &io->gout[O_EOC]);
  kind_gate_begin(&s->up, &io->gout[O_UP]);
  kind_gate_begin(&s->down, &io->gout[O_DOWN]);
  s->gate = io->gate[G_GATE].start;
  s->cycle = io->gate[G_CYCLE].start;
  s->hold = io->gate[G_HOLD].start;

  if (s->state == S_IDLE) s->value = s->mode == M_SLEW ? s->value : c.floor;
  if (s->state == S_TOP) {
    /* AR holds at Level; a switch to another mode lets it go. */
    if (s->mode == M_AR) s->value = c.level;
    else if (s->mode == M_SLEW) s->state = S_IDLE;
    else start(s, &c, S_FALL, c.floor, 1.0f);
  }
  if (s->mode == M_SLEW) {
    /* Glide to the floor whenever it moves: a new segment from here. */
    const float d = c.floor - s->value;
    if (d != 0.0f && (s->state == S_IDLE || mod_bits(s->to) != mod_bits(c.floor))) {
      retarget(s, &c, c.floor);
    }
  } else if (s->state == S_IDLE && cycling(s) && !s->hold) {
    start(s, &c, S_RISE, c.level, 1.0f);
  }

  n = kind_events(io, 4, ev);
  if (sync && io->tp->start != FM1_MOD_NONE) {
    /* A synced cycle restarts at the sequencer's Start, with the others. */
    unsigned i = n++;
    for (; i > 0 && ev[i - 1u].frame > io->tp->start; --i) ev[i] = ev[i - 1u];
    ev[i].frame = io->tp->start;
    ev[i].input = E_START;
    ev[i].high = 1;
    ev[i].reserved = 0;
  }
  for (e = 0; e < n; ++e) {
    const unsigned f = ev[e].frame < c.at ? c.at : ev[e].frame, high = ev[e].high;
    run(s, &c, f - c.at);
    switch (ev[e].input) {
      case G_HOLD: s->hold = (uint8_t)high; break;
      case G_CYCLE:
        s->cycle = (uint8_t)high;
        if (high && s->state == S_IDLE && s->mode != M_SLEW) start(s, &c, S_RISE, c.level, 1.0f);
        break;
      case G_GATE:
        s->gate = (uint8_t)high;
        if (s->mode == M_AR) {
          if (high) start(s, &c, S_RISE, c.level, 1.0f);
          else if (s->state == S_RISE || s->state == S_TOP) start(s, &c, S_FALL, c.floor, 1.0f);
        } else if (s->mode == M_GATED && high && s->state == S_IDLE) {
          start(s, &c, S_RISE, c.level, 1.0f);
        }
        break;
      case E_START:
        if (cycling(s)) {
          s->value = c.floor;
          start(s, &c, S_RISE, c.level, 1.0f);
        }
        break;
      default:   /* TRIG */
        if (high && s->mode != M_AR && s->mode != M_SLEW && accept(s, p[P_RETRIG])) {
          start(s, &c, S_RISE, c.level, 1.0f);
        }
        break;
    }
  }
  run(s, &c, FM1_MOD_TICK - c.at);

  io->out[O_OUT] = mod_clampf(s->value, 0.0f, 1.0f, 0.0f);
  io->out[O_INV] = 1.0f - io->out[O_OUT];
  io->out[O_UP] = (float)s->up.level;
  io->out[O_DOWN] = (float)s->down.level;
  mod_trig_end(&s->eor, &io->gout[O_EOR], &io->out[O_EOR]);
  mod_trig_end(&s->eoc, &io->gout[O_EOC], &io->out[O_EOC]);
}

static void fun_reset(void *self, uint32_t why) {
  fun_t *s = (fun_t *)self;
  if (why == FM1_MOD_RESET_PRESET) {
    s->state = S_IDLE;
    s->value = 0.0f;
    s->phase = 0;
  }
}

const fm1_mod_kind_t fm1_mod_kind_function = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "function", 0x46554E20u /* "FUN " */, "Function", "FUN",
  "Our own, from the published behaviour of Make Noise's Maths, Joranalogue's Contour 1, "
  "Serge's DUSG and Befaco's Rampage; shape curves after Mutable Instruments' Peaks (Emilie "
  "Gillet, MIT).",
  kParams, P_COUNT, 4, 6, kGates, kOuts, FM1_MOD_KIND_TRANSPORT, 0,
  fun_size, fun_create, NULL, fun_reset, fun_process, NULL, NULL, NULL
};
