/* kinds/mod_compare.c -- the Compare module kind (docs/16 §3.6): gates from
 * comparing signals.
 *
 * The compared value is d = A - (B + Thresh), or in Trend mode A's slope
 * (1.0 is a change of 10 per second, as Calc's Slope) minus (B + Thresh).
 *   GATE  A > B: high while d is above 0, a Schmitt trigger with a band of
 *         Hyst (rises above +Hyst/2, falls below -Hyst/2). Window: high
 *         while |d| < Width (enters below Width - Hyst/2, leaves above Width
 *         + Hyst/2). Trend: as A > B on the slope, so it is high while A
 *         rises faster than B + Thresh.
 *   NOT   the inverse of GATE; RISE and FALL a trigger at each of its edges.
 *   ABOVE, MID, BELOW  in every mode: d above +Width, between, below -Width,
 *         with the same hysteresis.
 * Inputs change once a tick, so an edge lands where the straight line
 * between the last tick's d and this tick's crosses the threshold, to a
 * frame: a Compare is the sample-accurate way to turn a CV into a gate (a
 * CV cable into a gate input switches at the tick's first frame).
 *
 * Our own code, MIT. After the disting mk4's A-7 (closed; idea only),
 * Phazerville's Compare, Schmitt and Trending applets (Jason Justian, MIT),
 * Chris Johnson's Utility Pair window comparator (MIT) and Contour 1's slope
 * gates (Joranalogue; idea only); no code taken. */
#include "kinds_int.h"

enum { P_MODE, P_THRESH, P_HYST, P_WIDTH, P_A, P_B, P_COUNT };
enum { O_GATE, O_NOT, O_RISE, O_FALL, O_ABOVE, O_MID, O_BELOW, N_OUT };
enum { M_GREATER, M_WINDOW, M_TREND };
enum { Z_BELOW, Z_MID, Z_ABOVE };

static const char *const kModes[] = { "A>B", "Window", "Trend" };

#define MOD FM1_PARAM_MOD
#define IN FM1_PARAM_INPUT
static const fm1_param_t kParams[P_COUNT] = {
  { "Mode", FM1_PARAM_ENUM, 0.0f, 2.0f, 0.0f, kModes, 0, 1, 0, FM1_UNIT_NONE, "Mode" },
  { "Thresh", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Thr" },
  { "Hyst", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.05f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Hyst" },
  { "Width", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.25f, NULL, 0, 4, MOD, FM1_UNIT_NONE, "Width" },
  { "A", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 5, IN, FM1_UNIT_NONE, "A" },
  { "B", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 6, IN, FM1_UNIT_NONE, "B" },
};
#undef MOD
#undef IN

#define GATE(n) { n, FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 }
static const fm1_port_t kOuts[N_OUT] = { GATE("Gate"), GATE("Not"), GATE("Rise"), GATE("Fall"),
                                         GATE("Above"), GATE("Mid"), GATE("Below") };
#undef GATE

typedef struct cmp {
  float prev_d;                /* d at the last tick */
  float prev_a;                /* Trend: A at the last tick */
  float per_tick;              /* the slope's scale: ticks per 0.1 s */
  kind_gate_t gate, not_, above, mid, below;
  mod_trig_t rise, fall;
  uint8_t primed, zone, reserved[2];
} cmp_t;

static size_t cmp_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(cmp_t);
}

static void *cmp_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  cmp_t *s = (cmp_t *)mem;
  (void)seed;
  s->prev_d = s->prev_a = 0.0f;
  s->per_tick = 0.1f / kind_tick_s(kind_rate(host));
  kind_gate_init(&s->gate);
  kind_gate_init(&s->not_);
  kind_gate_init(&s->above);
  kind_gate_init(&s->mid);
  kind_gate_init(&s->below);
  mod_trig_init(&s->rise);
  mod_trig_init(&s->fall);
  s->primed = 0;
  s->zone = Z_MID;
  s->reserved[0] = s->reserved[1] = 0;
  return s;
}

/* The frame where the line from the last tick's d to this one crosses
 * `level`; 0 on the first tick or a flat line. */
static unsigned crossing(const cmp_t *s, float d, float level) {
  float f;
  if (!s->primed || d == s->prev_d) return 0;
  f = (level - s->prev_d) / (d - s->prev_d);
  f = mod_clampf(f, 0.0f, 1.0f, 0.0f) * (float)FM1_MOD_TICK;
  return f >= (float)(FM1_MOD_TICK - 1u) ? FM1_MOD_TICK - 1u : (unsigned)f;
}

static void cmp_process(void *self, const fm1_mod_io_t *io) {
  cmp_t *s = (cmp_t *)self;
  const float *p = io->p;
  const unsigned mode = (unsigned)p[P_MODE];
  const float h = p[P_HYST] * 0.5f, w = p[P_WIDTH];
  float x = p[P_A], d;
  unsigned g = s->gate.level, zone = s->zone, f = 0;
  int changed = 0;
  if (mode == M_TREND) x = s->primed ? (p[P_A] - s->prev_a) * s->per_tick : 0.0f;
  s->prev_a = p[P_A];
  d = mod_clampf(x - (p[P_B] + p[P_THRESH]), -1e6f, 1e6f, 0.0f);

  kind_gate_begin(&s->gate, &io->gout[O_GATE]);
  kind_gate_begin(&s->not_, &io->gout[O_NOT]);
  kind_gate_begin(&s->above, &io->gout[O_ABOVE]);
  kind_gate_begin(&s->mid, &io->gout[O_MID]);
  kind_gate_begin(&s->below, &io->gout[O_BELOW]);
  mod_trig_begin(&s->rise, &io->gout[O_RISE]);
  mod_trig_begin(&s->fall, &io->gout[O_FALL]);
  g = s->gate.level;

  /* GATE */
  if (mode == M_WINDOW) {
    const float m = d < 0.0f ? -d : d;
    if (!g && m < w - h) {
      g = 1;
      f = crossing(s, d, d > 0.0f ? w - h : h - w);
      changed = 1;
    } else if (g && m > w + h) {
      g = 0;
      f = crossing(s, d, d > 0.0f ? w + h : -w - h);
      changed = 1;
    }
  } else if (!g && d > h) {
    g = 1;
    f = crossing(s, d, h);
    changed = 1;
  } else if (g && d < -h) {
    g = 0;
    f = crossing(s, d, -h);
    changed = 1;
  }
  if (changed) {
    kind_gate_set(&s->gate, &io->gout[O_GATE], f, g);
    kind_gate_set(&s->not_, &io->gout[O_NOT], f, !g);
    if (g) mod_trig_fire(&s->rise, &io->gout[O_RISE], f);
    else mod_trig_fire(&s->fall, &io->gout[O_FALL], f);
  } else if (s->not_.level == s->gate.level) {
    kind_gate_set(&s->not_, &io->gout[O_NOT], 0, !g);   /* the first tick: NOT starts high */
  }

  /* ABOVE, MID, BELOW */
  if (zone == Z_ABOVE && d < w - h) {
    kind_gate_set(&s->above, &io->gout[O_ABOVE], crossing(s, d, w - h), 0);
    zone = Z_MID;
  } else if (zone == Z_BELOW && d > h - w) {
    kind_gate_set(&s->below, &io->gout[O_BELOW], crossing(s, d, h - w), 0);
    zone = Z_MID;
  }
  if (zone == Z_MID && d > w + h) {
    kind_gate_set(&s->above, &io->gout[O_ABOVE], crossing(s, d, w + h), 1);
    zone = Z_ABOVE;
  } else if (zone == Z_MID && d < -w - h) {
    kind_gate_set(&s->below, &io->gout[O_BELOW], crossing(s, d, -w - h), 1);
    zone = Z_BELOW;
  }
  if ((zone == Z_MID) != (s->mid.level != 0)) {
    /* MID changes where the zone it left or entered changed. */
    const float level = zone == Z_MID ? (s->zone == Z_ABOVE ? w - h : h - w)
                                      : (zone == Z_ABOVE ? w + h : -w - h);
    kind_gate_set(&s->mid, &io->gout[O_MID], s->zone == zone ? 0u : crossing(s, d, level),
                  zone == Z_MID);
  }
  s->zone = (uint8_t)zone;
  s->prev_d = d;
  s->primed = 1;

  mod_trig_end(&s->rise, &io->gout[O_RISE], &io->out[O_RISE]);
  mod_trig_end(&s->fall, &io->gout[O_FALL], &io->out[O_FALL]);
  io->out[O_GATE] = (float)s->gate.level;
  io->out[O_NOT] = (float)s->not_.level;
  io->out[O_ABOVE] = (float)s->above.level;
  io->out[O_MID] = (float)s->mid.level;
  io->out[O_BELOW] = (float)s->below.level;
}

static void cmp_reset(void *self, uint32_t why) {
  cmp_t *s = (cmp_t *)self;
  if (why == FM1_MOD_RESET_PRESET) s->primed = 0;
}

const fm1_mod_kind_t fm1_mod_kind_compare = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "compare", 0x434D5020u /* "CMP " */, "Compare", "CMP",
  "Our own. After Phazerville's Compare, Schmitt and Trending (Jason Justian, MIT), Chris "
  "Johnson's Utility Pair window comparator (MIT) and the disting mk4's comparator (Expert "
  "Sleepers; idea only); no code taken.",
  kParams, P_COUNT, 0, N_OUT, NULL, kOuts, 0, 0,
  cmp_size, cmp_create, NULL, cmp_reset, cmp_process, NULL, NULL, NULL, 0
};
