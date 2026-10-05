/* kinds/mod_logic.c -- the Logic module kind (docs/16 §3.6): gate logic.
 *
 * Gates A and B in, OUT and NOT out, evaluated at every edge in frame order
 * (A before B at the same frame), so the result keeps the inputs' frames:
 *   AND OR XOR NAND NOR XNOR  of the two levels;
 *   SR      a rising A sets OUT, a rising B resets it (B wins at a tie);
 *   D       a rising B (the clock) copies A's level, A's edges at the same
 *           frame first;
 *   Toggle  a rising A flips OUT, a rising B resets it.
 * Op takes modulation (rounded), so a cable can switch the function; the
 * flip-flops keep their state across a switch.
 *
 * Our own code, MIT. After the disting NT's Logic (closed; idea only) and
 * Phazerville's Logic and TL Neuron applets (Jason Justian, MIT); no code
 * taken. */
#include "kinds_int.h"

enum { P_OP, P_COUNT };
enum { G_A, G_B };
enum { O_OUT, O_NOT };
enum { OP_AND, OP_OR, OP_XOR, OP_NAND, OP_NOR, OP_XNOR, OP_SR, OP_D, OP_TOGGLE, OP_COUNT };

static const char *const kOps[OP_COUNT] = { "AND", "OR", "XOR", "NAND", "NOR", "XNOR",
                                            "SR", "D", "Toggle" };

static const fm1_param_t kParams[P_COUNT] = {
  { "Op", FM1_PARAM_ENUM, 0.0f, 8.0f, 0.0f, kOps, 0, 1, FM1_PARAM_MOD, FM1_UNIT_NONE, "Op" },
};

static const fm1_port_t kGates[] = { { "A", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
                                     { "B", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };
static const fm1_port_t kOuts[] = { { "Out", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Not", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };

typedef struct logic {
  kind_gate_t out, not_;
  uint8_t a, b, q, reserved;   /* input levels, the flip-flops' state */
} logic_t;

static size_t logic_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(logic_t);
}

static void *logic_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  logic_t *s = (logic_t *)mem;
  (void)host;
  (void)seed;
  kind_gate_init(&s->out);
  kind_gate_init(&s->not_);
  s->a = s->b = s->q = s->reserved = 0;
  return s;
}

static unsigned eval(const logic_t *s, unsigned op) {
  switch (op) {
    case OP_AND: return s->a & s->b;
    case OP_OR: return s->a | s->b;
    case OP_XOR: return s->a ^ s->b;
    case OP_NAND: return !(s->a & s->b);
    case OP_NOR: return !(s->a | s->b);
    case OP_XNOR: return !(s->a ^ s->b);
    default: return s->q;
  }
}

static void put(logic_t *s, const fm1_mod_io_t *io, unsigned frame, unsigned v) {
  kind_gate_set(&s->out, &io->gout[O_OUT], frame, v);
  kind_gate_set(&s->not_, &io->gout[O_NOT], frame, !v);
}

static void logic_process(void *self, const fm1_mod_io_t *io) {
  logic_t *s = (logic_t *)self;
  const unsigned op = (unsigned)io->p[P_OP];
  kind_event_t ev[2u * FM1_MOD_EDGES];
  unsigned n, e;
  kind_gate_begin(&s->out, &io->gout[O_OUT]);
  kind_gate_begin(&s->not_, &io->gout[O_NOT]);
  /* The levels at the tick's start (a cable patched or pulled arrives as an
   * edge at frame 0). */
  s->a = io->gate[G_A].start;
  s->b = io->gate[G_B].start;
  put(s, io, 0, eval(s, op));   /* an Op change, and NOT high from the start */
  n = kind_events(io, 2, ev);
  for (e = 0; e < n; ++e) {
    const unsigned rise = ev[e].high && !(ev[e].input == G_A ? s->a : s->b);
    if (ev[e].input == G_A) s->a = ev[e].high;
    else s->b = ev[e].high;
    if (rise) {
      if (op == OP_SR) s->q = ev[e].input == G_A;
      else if (op == OP_D && ev[e].input == G_B) s->q = s->a;
      else if (op == OP_TOGGLE) s->q = ev[e].input == G_A ? (uint8_t)!s->q : 0u;
    }
    put(s, io, ev[e].frame, eval(s, op));
  }
  io->out[O_OUT] = (float)s->out.level;
  io->out[O_NOT] = (float)s->not_.level;
}

static void logic_reset(void *self, uint32_t why) {
  logic_t *s = (logic_t *)self;
  if (why == FM1_MOD_RESET_PRESET) s->q = 0;
}

const fm1_mod_kind_t fm1_mod_kind_logic = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "logic", 0x4C4F4720u /* "LOG " */, "Logic", "LOG",
  "Our own. After Phazerville's Logic and TL Neuron (Jason Justian, MIT) and the disting NT's "
  "Logic (Expert Sleepers; idea only); no code taken.",
  kParams, P_COUNT, 2, 2, kGates, kOuts, 0, 0,
  logic_size, logic_create, NULL, logic_reset, logic_process, NULL, NULL, NULL
};
