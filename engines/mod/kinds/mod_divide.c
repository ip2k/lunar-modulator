/* kinds/mod_divide.c -- the Divide module kind (docs/16 §3.5): two channels
 * of clock division, multiplication, Euclidean rhythm and probability.
 *
 * CLOCK (normalled to the sequencer's CLOCK, a trigger each step) counts
 * steps; RESET (normalled to START) makes the next clock step 0. Each
 * channel sends a trigger on OUT1 or OUT2 for the steps its Mode picks:
 *   Div     every Value-th step, Rot steps late (Value 1-16);
 *   Mult    Value evenly spaced triggers per clock period, the period
 *           measured between the last two clocks (one on the first clock);
 *   Euclid  Fill x Value hits spread evenly over a loop of Value steps
 *           (Bjorklund's pattern in its Bresenham form), rotated Rot steps;
 *   Prob    each step passes with probability Fill.
 * Swing delays every second trigger of a channel by Swing x half its
 * period (Div: Value steps; Mult: a Value-th of a step; else one step), so
 * 1 lands the off-beat three quarters of the way. Delay (0-1,000 ms) moves
 * every trigger later. A clock's own triggers keep its frame. In Mult a new
 * clock restarts the run, dropping what it had not yet sent; RESET drops
 * everything scheduled. Up to 8 triggers wait per channel; more are dropped.
 * Prob draws once per step and channel whatever the mode, from the
 * instance's own generator, so switching modes never shifts the stream.
 *
 * Our own code, MIT. After Phazerville's ClockDivider, ProbabilityDivider,
 * Shuffle and GateDelay applets and Piqued's Euclidean filter (Jason
 * Justian, Nicholas J. Michalek and others; MIT); no code taken. */
#include "kinds_int.h"

enum { P_MODE1, P_VALUE1, P_FILL1, P_ROT1, P_MODE2, P_VALUE2, P_FILL2, P_ROT2, P_SWING, P_DELAY,
       P_COUNT };
enum { G_CLOCK, G_RESET };
enum { O_OUT1, O_OUT2 };
enum { M_DIV, M_MULT, M_EUCLID, M_PROB };
enum { QUEUE = 8 };

static const char *const kModes[] = { "Div", "Mult", "Euclid", "Prob" };

#define MOD FM1_PARAM_MOD
static const fm1_param_t kParams[P_COUNT] = {
  { "Mode1", FM1_PARAM_ENUM, 0.0f, 3.0f, 0.0f, kModes, 0, 1, 0, FM1_UNIT_NONE, "Mode1" },
  { "Value1", FM1_PARAM_FLOAT, 1.0f, 16.0f, 2.0f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Val1" },
  { "Fill1", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Fill1" },
  { "Rot1", FM1_PARAM_FLOAT, 0.0f, 15.0f, 0.0f, NULL, 0, 4, MOD, FM1_UNIT_NONE, "Rot1" },
  { "Mode2", FM1_PARAM_ENUM, 0.0f, 3.0f, 2.0f, kModes, 1, 5, 0, FM1_UNIT_NONE, "Mode2" },
  { "Value2", FM1_PARAM_FLOAT, 1.0f, 16.0f, 8.0f, NULL, 1, 6, MOD, FM1_UNIT_NONE, "Val2" },
  { "Fill2", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.375f, NULL, 1, 7, MOD, FM1_UNIT_NONE, "Fill2" },
  { "Rot2", FM1_PARAM_FLOAT, 0.0f, 15.0f, 0.0f, NULL, 1, 8, MOD, FM1_UNIT_NONE, "Rot2" },
  { "Swing", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.0f, NULL, 2, 9, MOD, FM1_UNIT_NONE, "Swing" },
  { "Delay", FM1_PARAM_FLOAT, 0.0f, 1000.0f, 0.0f, NULL, 2, 10, MOD, FM1_UNIT_MS, "Delay" },
};
#undef MOD

static const fm1_port_t kGates[] = {
  { "Clock", FM1_PORT_GATE, FM1_UNIT_NONE, FM1_MOD_SRC_CLOCK, 0 },
  { "Reset", FM1_PORT_GATE, FM1_UNIT_NONE, FM1_MOD_SRC_START, 0 },
};
static const fm1_port_t kOuts[] = { { "Out1", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Out2", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };

typedef struct channel {
  uint64_t at[QUEUE];          /* absolute frames of waiting triggers, ascending */
  uint32_t sent;               /* triggers scheduled since RESET (for Swing) */
  mod_trig_t trig;
  uint8_t n, reserved[3];
} channel_t;

typedef struct divide {
  channel_t ch[2];
  uint64_t last;               /* the last clock's absolute frame */
  fm1_mp_rng_t rng;
  uint32_t step;               /* clocks since RESET */
  uint32_t period;             /* frames between the last two clocks; 0: unknown */
  uint32_t fs;
  uint8_t have_last, reserved[3];
} divide_t;

static size_t divide_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(divide_t);
}

static void channel_init(channel_t *c) {
  unsigned i;
  for (i = 0; i < QUEUE; ++i) c->at[i] = 0;
  c->sent = 0;
  mod_trig_init(&c->trig);
  c->n = 0;
  c->reserved[0] = c->reserved[1] = c->reserved[2] = 0;
}

static void *divide_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  divide_t *s = (divide_t *)mem;
  channel_init(&s->ch[0]);
  channel_init(&s->ch[1]);
  s->last = 0;
  fm1_mp_rng_seed(&s->rng, seed);
  s->step = 0;
  s->period = 0;
  s->fs = kind_rate(host);
  s->have_last = 0;
  s->reserved[0] = s->reserved[1] = s->reserved[2] = 0;
  return s;
}

/* Inserts a trigger at absolute frame `at`, keeping the queue sorted. */
static void schedule(channel_t *c, uint64_t at) {
  unsigned i;
  if (c->n >= QUEUE) return;
  for (i = c->n; i > 0 && c->at[i - 1] > at; --i) c->at[i] = c->at[i - 1];
  c->at[i] = at;
  ++c->n;
}

/* A trigger of this channel at `at`, with Swing and Delay applied. */
static void emit(const divide_t *s, channel_t *c, const float *p, uint64_t at,
                 uint64_t out_period) {
  uint64_t extra = (uint64_t)(p[P_DELAY] * 0.001f * (float)s->fs);
  if (c->sent & 1u) extra += (uint64_t)(p[P_SWING] * 0.5f * (float)out_period);
  ++c->sent;
  schedule(c, at + extra);
}

static void clock(divide_t *s, const float *p, uint64_t at) {
  unsigned k;
  if (s->have_last && at > s->last && at - s->last < 0x80000000ull) {
    s->period = (uint32_t)(at - s->last);
  }
  s->last = at;
  s->have_last = 1;
  for (k = 0; k < 2u; ++k) {
    channel_t *c = &s->ch[k];
    const unsigned base = k ? P_MODE2 : P_MODE1;
    const unsigned mode = (unsigned)p[base];
    const uint32_t v = (uint32_t)kind_int(p[base + 1u], 1, 16);
    const float fill = p[base + 2u];
    const uint32_t rot = (uint32_t)kind_int(p[base + 3u], 0, 15);
    const uint32_t draw = fm1_mp_rng_next(&s->rng);   /* one per step and channel */
    switch (mode) {
      case M_DIV:
        if ((s->step + rot) % v == 0) emit(s, c, p, at, (uint64_t)s->period * v);
        break;
      case M_MULT: {
        uint32_t j;
        c->n = 0;                                    /* a new clock restarts the run */
        for (j = 0; j < (s->period ? v : 1u); ++j) {
          emit(s, c, p, at + (uint64_t)s->period * j / v, s->period / v);
        }
        break;
      }
      case M_EUCLID: {
        const uint32_t hits = (uint32_t)kind_int(fill * (float)v, 0, (int)v);
        const uint32_t pos = (s->step + rot) % v;
        if ((pos * hits) % v < hits) emit(s, c, p, at, s->period);
        break;
      }
      default: {
        const uint64_t threshold = fill >= 1.0f ? 0x100000000ull
                                   : fill <= 0.0f ? 0u : (uint64_t)(fill * 4294967296.0f);
        if ((uint64_t)draw < threshold) emit(s, c, p, at, s->period);
        break;
      }
    }
  }
  ++s->step;
}

static void divide_process(void *self, const fm1_mod_io_t *io) {
  divide_t *s = (divide_t *)self;
  const uint64_t t0 = kind_t0(io), t1 = t0 + FM1_MOD_TICK;
  kind_event_t ev[2u * FM1_MOD_EDGES];
  unsigned n, e, k;
  for (k = 0; k < 2u; ++k) mod_trig_begin(&s->ch[k].trig, &io->gout[O_OUT1 + k]);
  /* Rising edges in frame order; at one frame RESET before CLOCK, so a
   * Start's first step is step 0. */
  n = kind_events(io, 2, ev);
  for (e = 0; e < n;) {
    unsigned end = e, pass, a;
    while (end < n && ev[end].frame == ev[e].frame) ++end;
    for (pass = 0; pass < 2u; ++pass) {
      for (a = e; a < end; ++a) {
        if (!ev[a].high || ev[a].input != (pass ? G_CLOCK : G_RESET)) continue;
        if (pass) {
          clock(s, io->p, t0 + ev[a].frame);
        } else {
          s->step = 0;
          for (k = 0; k < 2u; ++k) {
            s->ch[k].n = 0;
            s->ch[k].sent = 0;
          }
        }
      }
    }
    e = end;
  }
  for (k = 0; k < 2u; ++k) {
    channel_t *c = &s->ch[k];
    unsigned i = 0, j;
    while (i < c->n && c->at[i] < t1) {
      mod_trig_fire(&c->trig, &io->gout[O_OUT1 + k],
                    c->at[i] > t0 ? (unsigned)(c->at[i] - t0) : 0u);
      ++i;
    }
    for (j = i; j < c->n; ++j) c->at[j - i] = c->at[j];
    c->n = (uint8_t)(c->n - i);
    mod_trig_end(&c->trig, &io->gout[O_OUT1 + k], &io->out[O_OUT1 + k]);
  }
}

static void divide_reset(void *self, uint32_t why) {
  divide_t *s = (divide_t *)self;
  if (why == FM1_MOD_RESET_PRESET) {
    s->step = 0;
    s->period = 0;
    s->have_last = 0;
    s->ch[0].n = s->ch[1].n = 0;
    s->ch[0].sent = s->ch[1].sent = 0;
  }
}

const fm1_mod_kind_t fm1_mod_kind_divide = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "divide", 0x44495620u /* "DIV " */, "Divide", "DIV",
  "Our own. After Phazerville's ClockDivider, ProbabilityDivider, Shuffle and GateDelay and "
  "Piqued's Euclidean filter (Jason Justian, Nicholas J. Michalek and others, MIT); no code "
  "taken.",
  kParams, P_COUNT, 2, 2, kGates, kOuts, 0, 0,
  divide_size, divide_create, NULL, divide_reset, divide_process, NULL, NULL, NULL
};
