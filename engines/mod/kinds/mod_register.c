/* kinds/mod_register.c -- the Register module kind (docs/16 §3.4): a
 * looping random shift register after Music Thing Modular's Turing Machine.
 *
 * Each rising edge at CLOCK (normalled to the sequencer's CLOCK) shifts the
 * register: the bit from Length steps ago (1-32) comes back, flipped with a
 * chance set by Change: +1 locks the loop, 0 is fresh random every step,
 * -1 locks a loop of twice the length whose second half is inverted (the
 * Turing Machine's big knob, from right to left). A rising edge at WRITE
 * flips the next bit to come back, so the loop can be edited by hand.
 *   CV     the low 8 bits as 0..1 (the module's DAC), x Level + Offset,
 *          through a linear slew (Slew: 0 off, else Peaks' knob-to-time
 *          curve, 0.5 ms to 8 s for a full-scale move);
 *   BIT    the newest bit as a gate: high from a clock edge that shifted in
 *          a 1 until CLOCK falls (CLOCK AND bit);
 *   PITCH  the 8-bit value over Span semitones, rounded to whole notes, in
 *          SEMI (semitones / 60).
 * The register starts from the instance's seed and draws once per clock
 * whatever Change is, so a preset repeats exactly and turning Change never
 * shifts the stream.
 *
 * Our own code, MIT, on fm1_mp's register and slew. After the Turing
 * Machine (Tom Whitwell, Music Thing Modular), Workshop System Computer card
 * 20 (Chris Johnson, MIT) and Phazerville's util_turing.h (Patrick Dowling,
 * MIT); no code taken. */
#include "kinds_int.h"

enum { P_CHANGE, P_LENGTH, P_LEVEL, P_OFFSET, P_SPAN, P_SLEW, P_COUNT };
enum { G_CLOCK, G_WRITE };
enum { O_CV, O_BIT, O_PITCH };

#define MOD FM1_PARAM_MOD
static const fm1_param_t kParams[P_COUNT] = {
  { "Change", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.8f, NULL, 0, 1, MOD, FM1_UNIT_NONE, "Change" },
  { "Length", FM1_PARAM_FLOAT, 1.0f, 32.0f, 16.0f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Length" },
  { "Level", FM1_PARAM_FLOAT, -1.0f, 1.0f, 1.0f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Level" },
  { "Offset", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 0, 4, MOD, FM1_UNIT_NONE, "Ofs" },
  { "Span", FM1_PARAM_FLOAT, 0.0f, 60.0f, 12.0f, NULL, 1, 5, MOD, FM1_UNIT_SEMI, "Span" },
  { "Slew", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.0f, NULL, 1, 6, MOD, FM1_UNIT_NONE, "Slew" },
};
#undef MOD

static const fm1_port_t kGates[] = {
  { "Clock", FM1_PORT_GATE, FM1_UNIT_NONE, FM1_MOD_SRC_CLOCK, 0 },
  { "Write", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
};
static const fm1_port_t kOuts[] = { { "CV", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Bit", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Pitch", FM1_PORT_CV_BI, FM1_UNIT_SEMI, MOD_NONE, 0 } };

typedef struct reg {
  fm1_mp_turing_t tm;
  fm1_mp_slew_t slew;
  float slew_s;                /* the slew time last applied */
  kind_gate_t bit;
  uint8_t clock, reserved[3];  /* CLOCK's level */
} reg_t;

static size_t reg_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(reg_t);
}

static void *reg_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  reg_t *s = (reg_t *)mem;
  fm1_mp_turing_init(&s->tm, seed);
  fm1_mp_slew_init(&s->slew, host ? host->sample_rate : 44118.0f);
  s->slew_s = 0.0f;
  kind_gate_init(&s->bit);
  s->clock = 0;
  s->reserved[0] = s->reserved[1] = s->reserved[2] = 0;
  return s;
}

static void reg_process(void *self, const fm1_mod_io_t *io) {
  reg_t *s = (reg_t *)self;
  const float *p = io->p;
  const int length = kind_int(p[P_LENGTH], 1, 32);
  const float slew_s = p[P_SLEW] > 0.0f ? fm1_mp_env_time_from_knob(p[P_SLEW]) : 0.0f;
  kind_event_t ev[2u * FM1_MOD_EDGES];
  unsigned n, e;
  float v, cv;
  fm1_mp_turing_set_length(&s->tm, length);
  fm1_mp_turing_set_flip(&s->tm, (1.0f - p[P_CHANGE]) * 0.5f);
  if (mod_bits(slew_s) != mod_bits(s->slew_s)) {
    fm1_mp_slew_set_times(&s->slew, slew_s, slew_s);
    s->slew_s = slew_s;
  }
  kind_gate_begin(&s->bit, &io->gout[O_BIT]);
  s->clock = io->gate[G_CLOCK].start;
  /* Edges in frame order; at one frame WRITE's before CLOCK's, so a write
   * lands on that clock. */
  n = kind_events(io, 2, ev);
  for (e = 0; e < n;) {
    unsigned end = e, pass, a;
    while (end < n && ev[end].frame == ev[e].frame) ++end;
    for (pass = 0; pass < 2u; ++pass) {
      for (a = e; a < end; ++a) {
        if (ev[a].input != (pass ? G_CLOCK : G_WRITE)) continue;
        if (!pass) {
          if (ev[a].high) s->tm.reg ^= 1u << (unsigned)(length - 1);
          continue;
        }
        s->clock = ev[a].high;
        if (ev[a].high) fm1_mp_turing_clock(&s->tm);
        kind_gate_set(&s->bit, &io->gout[O_BIT], ev[a].frame,
                      ev[a].high ? (unsigned)fm1_mp_turing_gate(&s->tm) : 0u);
      }
    }
    e = end;
  }
  v = fm1_mp_turing_value(&s->tm);
  cv = mod_clampf(p[P_LEVEL] * v + p[P_OFFSET], -1.0f, 1.0f, 0.0f);
  io->out[O_CV] = fm1_mp_slew_process(&s->slew, cv, FM1_MOD_TICK);
  io->out[O_BIT] = (float)s->bit.level;
  io->out[O_PITCH] = mod_round(v * p[P_SPAN]) * (1.0f / 60.0f);
}

static void reg_reset(void *self, uint32_t why) {
  reg_t *s = (reg_t *)self;
  if (why == FM1_MOD_RESET_PRESET) fm1_mp_slew_reset(&s->slew, 0.0f);
}

const fm1_mod_kind_t fm1_mod_kind_register = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "register", 0x52454720u /* "REG " */, "Register", "REG",
  "Our own, on fm1_mp's register. After Music Thing Modular's Turing Machine (Tom Whitwell), "
  "Workshop System Computer card 20 (Chris Johnson, MIT) and Phazerville's util_turing.h "
  "(Patrick Dowling, MIT); no code taken.",
  kParams, P_COUNT, 2, 3, kGates, kOuts, 0, 0,
  reg_size, reg_create, NULL, reg_reset, reg_process, NULL, NULL, NULL
};
