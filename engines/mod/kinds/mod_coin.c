/* kinds/mod_coin.c -- the Coin module kind (docs/16 §3.5): a Bernoulli gate.
 *
 * Each rising edge at IN tosses a coin and sends the gate to A or B:
 *   Direct  B with probability Prob, else A (0: always A, 1: always B);
 *   Toggle  switch to the other output with probability Prob, else stay.
 * Latch Off: the chosen output follows IN (it falls when IN falls). Latch
 * On: it stays high, and the other low, until a toss picks the other side.
 * Edges keep IN's frames. One draw per rising edge whatever Prob is, from
 * the instance's own generator (seeded per preset and position), so turning
 * Prob never shifts the sequence and a preset repeats exactly. IN is
 * normalled to the note trigger.
 *
 * Our own code, MIT, written from the published behaviour of Mutable
 * Instruments' Branches (its firmware is GPL-3 and was not read). MIT
 * references: Marbles' coin-toss T model and Phazerville's Brancher. */
#include "kinds_int.h"

enum { P_PROB, P_MODE, P_LATCH, P_COUNT };
enum { O_A, O_B };
enum { M_DIRECT, M_TOGGLE };

static const char *const kModes[] = { "Direct", "Toggle" };
static const char *const kLatch[] = { "Off", "On" };

static const fm1_param_t kParams[P_COUNT] = {
  { "Prob", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 1, FM1_PARAM_MOD, FM1_UNIT_NONE, "Prob" },
  { "Mode", FM1_PARAM_ENUM, 0.0f, 1.0f, 0.0f, kModes, 0, 2, 0, FM1_UNIT_NONE, "Mode" },
  { "Latch", FM1_PARAM_ENUM, 0.0f, 1.0f, 0.0f, kLatch, 0, 3, 0, FM1_UNIT_NONE, "Latch" },
};

static const fm1_port_t kGates[] = { { "In", FM1_PORT_GATE, FM1_UNIT_NONE, FM1_MOD_SRC_TRIG, 0 } };
static const fm1_port_t kOuts[] = { { "A", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "B", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };

typedef struct coin {
  fm1_mp_rng_t rng;
  kind_gate_t out[2];
  uint8_t side, reserved[3];   /* the output the last toss chose: 0 A, 1 B */
} coin_t;

static size_t coin_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(coin_t);
}

static void *coin_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  coin_t *s = (coin_t *)mem;
  (void)host;
  fm1_mp_rng_seed(&s->rng, seed);
  kind_gate_init(&s->out[0]);
  kind_gate_init(&s->out[1]);
  s->side = 0;
  s->reserved[0] = s->reserved[1] = s->reserved[2] = 0;
  return s;
}

static void coin_process(void *self, const fm1_mod_io_t *io) {
  coin_t *s = (coin_t *)self;
  const fm1_mod_gate_t *in = &io->gate[0];
  const unsigned mode = (unsigned)io->p[P_MODE], latch = io->p[P_LATCH] >= 0.5f;
  const float prob = io->p[P_PROB];
  const uint64_t threshold = prob >= 1.0f ? 0x100000000ull
                             : prob <= 0.0f ? 0u : (uint64_t)(prob * 4294967296.0f);
  unsigned e;
  kind_gate_begin(&s->out[0], &io->gout[O_A]);
  kind_gate_begin(&s->out[1], &io->gout[O_B]);
  for (e = 0; e < in->n; ++e) {
    const unsigned f = in->ev[e].frame;
    if (in->ev[e].high) {
      const int heads = (uint64_t)fm1_mp_rng_next(&s->rng) < threshold;
      if (mode == M_TOGGLE) s->side = (uint8_t)(heads ? !s->side : s->side);
      else s->side = (uint8_t)heads;
      kind_gate_set(&s->out[!s->side], &io->gout[s->side ? O_A : O_B], f, 0);
      kind_gate_set(&s->out[s->side], &io->gout[s->side ? O_B : O_A], f, 1);
    } else if (!latch) {
      kind_gate_set(&s->out[0], &io->gout[O_A], f, 0);
      kind_gate_set(&s->out[1], &io->gout[O_B], f, 0);
    }
  }
  if (!latch && !fm1_mod_gate_end(in)) {   /* Latch switched off while held high */
    kind_gate_set(&s->out[0], &io->gout[O_A], FM1_MOD_TICK - 1u, 0);
    kind_gate_set(&s->out[1], &io->gout[O_B], FM1_MOD_TICK - 1u, 0);
  }
  io->out[O_A] = (float)s->out[0].level;
  io->out[O_B] = (float)s->out[1].level;
}

const fm1_mod_kind_t fm1_mod_kind_coin = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "coin", 0x434F4920u /* "COI " */, "Coin", "COI",
  "Our own, from the published behaviour of Mutable Instruments' Branches (GPL-3 firmware, "
  "not read). MIT references: Marbles' coin toss and Phazerville's Brancher.",
  kParams, P_COUNT, 1, 2, kGates, kOuts, 0, 0, 0,
  coin_size, coin_create, NULL, NULL, coin_process, NULL, NULL, NULL
};
