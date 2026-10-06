/* kinds/mod_burst.c -- the Burst module kind (docs/16 §3.5): ratchets,
 * delays and random repeats, after Mutable Instruments' Peaks.
 *
 * Each rising edge at TRIG (normalled to the note trigger) starts:
 *   Burst   Count pulses (1-8), Spacing apart, each Length long: Peaks'
 *           pulse shaper with no pre-delay;
 *   Delay   the same after a pre-delay of Delay: with Count 1, a trigger
 *           delay;
 *   Random  Peaks' pulse randomizer: a pulse passes with probability
 *           Accept, then repeats with probability Repeat, Spacing apart on
 *           average, the gap varied by Jitter.
 * Spacing, Length and Delay follow Peaks' delay table, 5 to 60,000 calls:
 * 0.42 ms to 5 s (the table was built for 1 ms to 10 s at 6 kHz; Peaks
 * calls the processors at 12 kHz). Accel (ours)
 * shortens (above 0) or stretches (below) each gap after the first by
 * 2^(-Accel / 2) per repeat, a bouncing-ball ratchet; at 0 the shaper is
 * Peaks'. With a cable into CLOCK (ours) the repeats share the measured
 * clock period: the gap is the period / Count, Spacing ignored.
 *
 * OUT is Peaks' output, a gate; GATE is high while a burst runs (to the end
 * of its last gap); DONE is a trigger when GATE falls. Changing Mode starts
 * the new processor empty.
 *
 * The processors are C ports of Peaks' pulse_shaper and pulse_randomizer
 * (Emilie Gillet, 2013, MIT; engines/mod/mod_mi.c), byte for byte the
 * originals' output (fm1-mod-mi-ref). They count calls, one per 4 samples at
 * 48 kHz (12,000 a second), so each tick runs the calls that fall inside
 * it: a trigger at frame F is the call floor(F x 12,000 / rate), and an
 * output change made by call c lands at the frame of the boundary after it.
 * The randomizer draws from this instance's own copy of stmlib::Random's
 * generator, seeded per preset and position. */
#include "kinds_int.h"

#include "mod_mi.h"

enum { P_MODE, P_COUNT_, P_SPACING, P_LENGTH, P_DELAY, P_ACCEL, P_ACCEPT, P_REPEAT, P_JITTER,
       P_COUNT };
enum { G_TRIG, G_CLOCK };
enum { O_OUT, O_GATE, O_DONE };
enum { M_BURST, M_DELAY, M_RANDOM };

static const char *const kModes[] = { "Burst", "Delay", "Random" };

#define MOD FM1_PARAM_MOD
static const fm1_param_t kParams[P_COUNT] = {
  { "Mode", FM1_PARAM_ENUM, 0.0f, 2.0f, 0.0f, kModes, 0, 1, 0, FM1_UNIT_NONE, "Mode" },
  { "Count", FM1_PARAM_FLOAT, 1.0f, 8.0f, 4.0f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Count" },
  { "Spacing", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.4f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Space" },
  { "Length", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.2f, NULL, 0, 4, MOD, FM1_UNIT_NONE, "Length" },
  { "Delay", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.3f, NULL, 1, 5, MOD, FM1_UNIT_NONE, "Delay" },
  { "Accel", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 6, MOD, FM1_UNIT_NONE, "Accel" },
  { "Accept", FM1_PARAM_FLOAT, 0.0f, 1.0f, 1.0f, NULL, 1, 7, MOD, FM1_UNIT_NONE, "Accept" },
  { "Repeat", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 1, 8, MOD, FM1_UNIT_NONE, "Repeat" },
  { "Jitter", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.0f, NULL, 2, 9, MOD, FM1_UNIT_NONE, "Jitter" },
};
#undef MOD

static const fm1_port_t kGates[] = {
  { "Trig", FM1_PORT_GATE, FM1_UNIT_NONE, FM1_MOD_SRC_TRIG, 0 },
  { "Clock", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
};
static const fm1_port_t kOuts[] = { { "Out", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Gate", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Done", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };

typedef struct burst {
  union {
    mod_mi_shaper_t shaper;
    mod_mi_randomizer_t randomizer;
  } u;
  uint64_t clock_at;           /* the last CLOCK rise, absolute frame */
  uint32_t fs;
  uint32_t seed;               /* the randomizer's first state */
  uint32_t clock_calls;        /* the measured clock period in calls; 0: none */
  kind_gate_t out, gate;
  mod_trig_t done;
  uint8_t mode, pending, have_clock, level;
} burst_t;

static size_t burst_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(burst_t);
}

static void start(burst_t *s, unsigned mode) {
  s->mode = (uint8_t)mode;
  if (mode == M_RANDOM) mod_mi_randomizer_init(&s->u.randomizer, s->seed);
  else mod_mi_shaper_init(&s->u.shaper);
}

static void *burst_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  burst_t *s = (burst_t *)mem;
  s->clock_at = 0;
  s->fs = kind_rate(host);
  s->seed = seed;
  s->clock_calls = 0;
  kind_gate_init(&s->out);
  kind_gate_init(&s->gate);
  mod_trig_init(&s->done);
  s->pending = s->have_clock = s->level = 0;
  start(s, M_BURST);
  return s;
}

static void configure(burst_t *s, const float *p, int clocked) {
  const unsigned count = (unsigned)kind_int(p[P_COUNT_], 1, 8);
  uint16_t k[4];
  if (s->mode == M_RANDOM) {
    k[0] = kind_u16(p[P_ACCEPT]);
    k[1] = kind_u16(p[P_REPEAT]);
    k[2] = kind_u16(p[P_SPACING]);
    k[3] = kind_u16(p[P_JITTER]);
    mod_mi_randomizer_configure(&s->u.randomizer, k);
    return;
  }
  k[0] = s->mode == M_DELAY ? kind_u16(p[P_DELAY]) : 0u;
  k[1] = kind_u16(p[P_LENGTH]);
  k[2] = kind_u16(p[P_SPACING]);
  k[3] = (uint16_t)((count - 1u) << 13);
  mod_mi_shaper_configure(&s->u.shaper, k);
  s->u.shaper.accel = (int16_t)mod_round(mod_clampf(p[P_ACCEL], -1.0f, 1.0f, 0.0f) * 16384.0f);
  s->u.shaper.clocked = 0;
  if (clocked && s->clock_calls) {
    const uint32_t gap = s->clock_calls / count;
    s->u.shaper.clocked = (uint16_t)(gap < 1u ? 1u : gap > 65535u ? 65535u : gap);
  }
}

static void burst_process(void *self, const fm1_mod_io_t *io) {
  burst_t *s = (burst_t *)self;
  const uint64_t t0 = kind_t0(io), t1 = t0 + FM1_MOD_TICK;
  const uint32_t r = MOD_MI_PULSE_RATE;
  const uint64_t c0 = kind_native(t0, r, s->fs), c1 = kind_native(t1, r, s->fs);
  const fm1_mod_gate_t *trig = &io->gate[G_TRIG], *clk = &io->gate[G_CLOCK];
  const unsigned mode = (unsigned)io->p[P_MODE];
  uint64_t rise[FM1_MOD_EDGES + 1u];
  unsigned n_rise = 0, e, next = 0;
  uint64_t c;

  if (mode != s->mode) start(s, mode);
  /* CLOCK: the period between its last two rises, in calls. */
  for (e = 0; e < clk->n; ++e) {
    const uint64_t at = t0 + clk->ev[e].frame;
    if (!clk->ev[e].high) continue;
    if (s->have_clock && at > s->clock_at) {
      const uint64_t calls = kind_native(at, r, s->fs) - kind_native(s->clock_at, r, s->fs);
      s->clock_calls = calls > 0xFFFFFFFFull ? 0xFFFFFFFFu : (uint32_t)calls;
    }
    s->clock_at = at;
    s->have_clock = 1;
  }
  configure(s, io->p, (int)(io->gate_connected >> G_CLOCK) & 1);

  kind_gate_begin(&s->out, &io->gout[O_OUT]);
  kind_gate_begin(&s->gate, &io->gout[O_GATE]);
  mod_trig_begin(&s->done, &io->gout[O_DONE]);
  /* TRIG's rises as calls of this tick; one that maps past its last call
   * (the host frame before t(k) can) waits for the next tick's first. */
  if (s->pending) rise[n_rise++] = c0;
  s->pending = 0;
  for (e = 0; e < trig->n; ++e) {
    if (!trig->ev[e].high) continue;
    c = kind_native(t0 + trig->ev[e].frame, r, s->fs);
    if (c >= c1) s->pending = 1;
    else if (n_rise < FM1_MOD_EDGES + 1u) rise[n_rise++] = c;
  }
  for (c = c0; c < c1; ++c) {
    int new_pulse = 0, active;
    int16_t out;
    while (next < n_rise && rise[next] <= c) {   /* rises in one call are one (Peaks ORs a block's flags) */
      new_pulse = 1;
      ++next;
    }
    if (s->mode == M_RANDOM) {
      out = mod_mi_randomizer_call(&s->u.randomizer, new_pulse);
      active = mod_mi_randomizer_active(&s->u.randomizer);
    } else {
      out = mod_mi_shaper_call(&s->u.shaper, new_pulse);
      active = mod_mi_shaper_active(&s->u.shaper);
    }
    if ((out != 0) != (s->level != 0) || (unsigned)active != kind_gate_now(&s->gate)) {
      const unsigned f = kind_after_native(c, r, s->fs, t0);
      s->level = (uint8_t)(out != 0);
      kind_gate_set(&s->out, &io->gout[O_OUT], f, s->level);
      if ((unsigned)active != kind_gate_now(&s->gate)) {
        kind_gate_set(&s->gate, &io->gout[O_GATE], f, (unsigned)active);
        if (!active) mod_trig_fire(&s->done, &io->gout[O_DONE], f);
      }
    }
  }
  io->out[O_OUT] = (float)s->out.level;
  io->out[O_GATE] = (float)s->gate.level;
  mod_trig_end(&s->done, &io->gout[O_DONE], &io->out[O_DONE]);
}

static void burst_reset(void *self, uint32_t why) {
  burst_t *s = (burst_t *)self;
  if (why == FM1_MOD_RESET_PRESET) {
    start(s, s->mode);
    s->have_clock = 0;
    s->clock_calls = 0;
    s->pending = 0;
  }
}

const fm1_mod_kind_t fm1_mod_kind_burst = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "burst", 0x42535420u /* "BST " */, "Burst", "BST",
  "Ported from Mutable Instruments' Peaks pulse shaper and pulse randomizer (Emilie Gillet, "
  "MIT), byte-identical; Accel and the clocked spacing are ours. After Phazerville's Burst "
  "(Jason Justian, MIT; no code taken).",
  kParams, P_COUNT, 2, 3, kGates, kOuts, 0, 0, 0,
  burst_size, burst_create, NULL, burst_reset, burst_process, NULL, NULL, NULL
};
