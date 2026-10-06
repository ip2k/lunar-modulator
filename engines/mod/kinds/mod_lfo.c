/* kinds/mod_lfo.c -- the LFO module kind (docs/16 §3.2; the options note's
 * LFO), a wrapper round fm1_mp's LFO.
 *
 * Rate is a knob, 0.01-100 Hz on an exponential scale (0.5 is 1 Hz), or, with
 * Sync on, a division of the sequencer's tempo (Start then restarts the
 * cycle). Shape picks one of fm1_mp's eight (sine, triangle, saws, square
 * with Width, smooth random, sample-and-hold, random walk). Depth scales the
 * output, bipolar. Mode is Elektron's set:
 *   Free  runs on; RESET restarts the cycle only when a cable reaches it;
 *   Trig  runs on and restarts at every RESET (unpatched: every note-on);
 *   Hold  runs on unseen; the output holds its value at each RESET;
 *   One   one cycle from Phase after each RESET, then holds;
 *   Half  half a cycle, then holds.
 * One and Half wait for their first RESET at Phase. WRAP is a trigger at the
 * start of every cycle (a restart included), at its own frame.
 *
 * Our own code, MIT. The shapes follow Schwung's lfo_common.h (Charles
 * Vestal, MIT) and Mutable Instruments' Peaks (Emilie Gillet, MIT), the
 * modes Elektron's; engines/mod/README.md has the primitive. */
#include "mod_int.h"

enum { P_RATE, P_SHAPE, P_DEPTH, P_MODE, P_PHASE, P_SYNC, P_WIDTH, P_COUNT };
enum { O_OUT, O_WRAP };
enum { M_FREE, M_TRIG, M_HOLD, M_ONE, M_HALF };

static const char *const kShapes[] = { "Sine", "Triangle", "Saw Up", "Saw Down",
                                       "Square", "Smooth", "S&H", "Walk" };
static const char *const kModes[] = { "Free", "Trig", "Hold", "One", "Half" };
static const char *const kSyncs[] = { "Off", "4 Bars", "2 Bars", "1 Bar", "1/2", "1/4", "1/8",
                                      "1/16", "1/32", "1/4T", "1/8T", "1/16T", "1/2D", "1/4D",
                                      "1/8D" };
/* Cycles per beat for each Sync value. */
static const float kSyncRatio[] = { 0.0f, 0.0625f, 0.125f, 0.25f, 0.5f, 1.0f, 2.0f, 4.0f, 8.0f,
                                    1.5f, 3.0f, 6.0f, 1.0f / 3.0f, 2.0f / 3.0f, 4.0f / 3.0f };

#define MOD FM1_PARAM_MOD
static const fm1_param_t kParams[P_COUNT] = {
  { "Rate", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 1, MOD, FM1_UNIT_NONE, "Rate" },
  { "Shape", FM1_PARAM_ENUM, 0.0f, 7.0f, 0.0f, kShapes, 0, 2, MOD, FM1_UNIT_NONE, "Shape" },
  { "Depth", FM1_PARAM_FLOAT, -1.0f, 1.0f, 1.0f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Depth" },
  { "Mode", FM1_PARAM_ENUM, 0.0f, 4.0f, 0.0f, kModes, 0, 4, 0, FM1_UNIT_NONE, "Mode" },
  { "Phase", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.0f, NULL, 1, 5, MOD, FM1_UNIT_NONE, "Phase" },
  { "Sync", FM1_PARAM_ENUM, 0.0f, 14.0f, 0.0f, kSyncs, 1, 6, 0, FM1_UNIT_NONE, "Sync" },
  { "Width", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 1, 7, MOD, FM1_UNIT_NONE, "Width" },
};
#undef MOD

static const fm1_port_t kGates[] = { { "Reset", FM1_PORT_GATE, FM1_UNIT_NONE, FM1_MOD_SRC_TRIG, 0 } };
static const fm1_port_t kOuts[] = { { "Out", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Wrap", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };

typedef struct lfo {
  fm1_mp_lfo_t lfo;
  float base_hz, ratio;        /* the rate last applied (the setter divides in double) */
  float held;                  /* Hold's sample */
  mod_trig_t wrap;
  uint8_t mode, armed, reserved[2];
} lfo_t;

static size_t lfo_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(lfo_t);
}

static void *lfo_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  lfo_t *s = (lfo_t *)mem;
  fm1_mp_lfo_init(&s->lfo, host ? host->sample_rate : 44118.0f, seed);
  s->base_hz = 1.0f;
  s->ratio = 1.0f;
  s->held = 0.0f;
  mod_trig_init(&s->wrap);
  s->mode = M_FREE;
  s->armed = 0;
  s->reserved[0] = s->reserved[1] = 0;
  return s;
}

/* Advances n frames from *at; in a free-running mode each carry is a WRAP
 * trigger at the boundary after the sample that carried, so a period of P
 * whole samples wraps every P frames and a restart at frame f wraps next at
 * f + P. */
static void lfo_run(lfo_t *s, uint32_t n, uint32_t *at, fm1_mod_gate_t *wrap) {
  if ((s->mode == M_ONE || s->mode == M_HALF) && !s->armed) {
    *at += n;
    return;
  }
  while (n) {
    const uint32_t w = s->lfo.mode == FM1_MP_LFO_FREE ? mod_lfo_to_wrap(&s->lfo, n) : 0u;
    if (!w) {
      fm1_mp_lfo_process(&s->lfo, n);
      *at += n;
      return;
    }
    fm1_mp_lfo_process(&s->lfo, w);
    *at += w;
    n -= w;
    mod_trig_fire(&s->wrap, wrap, *at);   /* the boundary after the carry */
  }
}

static void restart(lfo_t *s, unsigned frame, fm1_mod_gate_t *wrap) {
  fm1_mp_lfo_reset(&s->lfo);
  s->armed = 1;
  mod_trig_fire(&s->wrap, wrap, frame);
}

static void lfo_process(void *self, const fm1_mod_io_t *io) {
  lfo_t *s = (lfo_t *)self;
  const float *p = io->p;
  const unsigned mode = (unsigned)p[P_MODE], sync = (unsigned)p[P_SYNC];
  const fm1_mod_gate_t *reset = &io->gate[0];
  const int patched = (int)(io->gate_connected & 1u);
  fm1_mod_gate_t *wrap = &io->gout[O_WRAP];
  float base_hz = 1.0f, ratio = 1.0f, v;
  uint32_t at = 0;
  unsigned e = 0, start_done = 0;

  if (sync && sync < sizeof(kSyncRatio) / sizeof(kSyncRatio[0])) {
    base_hz = (float)io->tp->bpm_x100 * (1.0f / 6000.0f);
    ratio = kSyncRatio[sync];
  } else {
    base_hz = mod_rate_hz(p[P_RATE]);
  }
  if (mod_bits(base_hz) != mod_bits(s->base_hz) || mod_bits(ratio) != mod_bits(s->ratio)) {
    fm1_mp_lfo_set_rate(&s->lfo, base_hz, ratio);
    s->base_hz = base_hz;
    s->ratio = ratio;
  }
  fm1_mp_lfo_set_shape(&s->lfo, (int)p[P_SHAPE]);
  fm1_mp_lfo_set_pulse_width(&s->lfo, p[P_WIDTH]);
  fm1_mp_lfo_set_start_phase(&s->lfo, p[P_PHASE]);
  if (mode != s->mode) {
    s->mode = (uint8_t)mode;
    fm1_mp_lfo_set_mode(&s->lfo, mode == M_ONE ? FM1_MP_LFO_ONE_SHOT
                                 : mode == M_HALF ? FM1_MP_LFO_HALF : FM1_MP_LFO_FREE);
    s->armed = 0;
  }
  mod_trig_begin(&s->wrap, wrap);

  /* RESET's rising edges and a synced Start, in frame order. */
  for (;;) {
    unsigned f = FM1_MOD_TICK, what = 0;   /* 1 reset, 2 start */
    while (e < reset->n && !reset->ev[e].high) ++e;
    if (e < reset->n) {
      f = reset->ev[e].frame;
      what = 1;
    }
    if (sync && !start_done && io->tp->start != FM1_MOD_NONE && io->tp->start <= f) {
      f = io->tp->start;
      what = 2;
    }
    if (!what) break;
    if (f < at) f = at;
    lfo_run(s, f - at, &at, wrap);
    if (what == 2) {   /* a RESET at the same frame adds nothing to this restart */
      start_done = 1;
      restart(s, f, wrap);
      while (e < reset->n && reset->ev[e].frame <= f) ++e;
      continue;
    }
    ++e;
    if (mode == M_HOLD) s->held = fm1_mp_lfo_value(&s->lfo);
    else if (mode != M_FREE || patched) restart(s, f, wrap);
  }
  lfo_run(s, FM1_MOD_TICK - at, &at, wrap);

  v = mode == M_HOLD ? s->held : fm1_mp_lfo_value(&s->lfo);
  io->out[O_OUT] = p[P_DEPTH] * v;
  mod_trig_end(&s->wrap, wrap, &io->out[O_WRAP]);
}

static void lfo_reset(void *self, uint32_t why) {
  lfo_t *s = (lfo_t *)self;
  if (why == FM1_MOD_RESET_PRESET) {
    fm1_mp_lfo_reset(&s->lfo);
    s->armed = 0;
    s->held = 0.0f;
  }
}

const fm1_mod_kind_t fm1_mod_kind_lfo = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "lfo", 0x4C464F20u /* "LFO " */, "LFO", "LFO",
  "Our own, on fm1_mp's LFO. Shapes after Schwung's lfo_common.h (Charles Vestal, MIT) and "
  "Mutable Instruments' Peaks (Emilie Gillet, MIT); modes after Elektron's.",
  kParams, P_COUNT, 1, 2, kGates, kOuts, FM1_MOD_KIND_TRANSPORT | FM1_MOD_KIND_POLY_OK, 0,
  lfo_size, lfo_create, NULL, lfo_reset, lfo_process, NULL, NULL, NULL, 0
};
