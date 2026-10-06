/* mod_int.h -- internals of the modulation runtime (fm1_mod.h): the state's
 * layout and the helpers the core, the planner and the kinds share. Not API.
 *
 * The state holds no pointers and puts every 64-bit member at an 8-aligned
 * offset after the arena, so its layout, and fm1_mod_size(), are the same
 * in 32- and 64-bit builds (i386 aligns uint64_t to 4 inside structs). */
#ifndef FM1_MOD_INT_H
#define FM1_MOD_INT_H

#include "fm1_mod.h"
#include "fm1_mp.h"

#define MOD_NONE 0xFFu
#define MOD_NO_FRAME 0xFFFFFFFFFFFFFFFFull
#define MOD_SYS_GATES 28u      /* KEY TRIG CLOCK BEAT BAR RUN START RTRG SEQ1-8, then
                                  each sound unit's KEY, TRIG and RTRG (MG9) */
#define MOD_SINK_UNITS FM1_MOD_SINKS   /* by sink index (fm1_mod_sink_unit) */
#define MOD_HOST_SINK 3u       /* HOST's sink index; its records are 0-5 */
#define MOD_PITCH_BIT 32u      /* a voice's restore bit for its pitch offset */
#define MOD_SINK_RECS FM1_MOD_SINK_PARAMS
#define MOD_MAX_WRITES MOD_SINK_RECS

/* A sink parameter's description, copied from its engine at bind time so
 * that the state needs no pointer to it. */
typedef struct mod_meta {
  float min, max, def;
  uint16_t uid;
  uint16_t flags;              /* FM1_PARAM_*: 16 bits since engine API v3 */
  uint8_t type, unit;
  uint8_t reserved[2];
} mod_meta_t;

/* A destination with enabled slots: the slots, in ascending order, sum
 * into it. A module's global instance takes the slots without VOICE; its
 * per-voice instances those too, read globally, and the VOICE ones (MG9),
 * whose destinations are listed apart (gate 2 and 3 below). */
typedef struct mod_dest {
  uint32_t slots;
  uint16_t index;              /* parameter index, or gate input index */
  uint8_t unit;                /* a sink's canonical code, or 8 + position */
  uint8_t gate;                /* 1: a gate input; 2 and 3: a VOICE parameter or gate */
} mod_dest_t;

/* A sound parameter, or a sound's pitch, that VOICE slots reach (MG9): the
 * slots sum per voice of that sound into its per-note offset. */
typedef struct mod_vdest {
  uint32_t slots;              /* the pitch's: its own and, for the current
                                  sound, PITCH_CUR's */
  uint16_t index;              /* the sound unit's parameter index; 0 for pitch */
  uint8_t sound;               /* 0-3 */
  uint8_t pitch;               /* 1: the note's pitch (FM1_PARAM_NOTE_PITCH) */
} mod_vdest_t;

typedef struct mod_plan {
  uint32_t active, refused, delayed_src, delayed_via;
  uint32_t vslots;                             /* active VOICE slots */
  uint32_t routed[FM1_MOD_POSITIONS];          /* module parameters with slots */
  uint32_t vrouted[FM1_MOD_POSITIONS];         /* ...with VOICE slots (their dest
                                                  is found by mod_vdest_of) */
  uint32_t sink_routed[MOD_SINK_UNITS];        /* sink parameters with slots, by index */
  mod_dest_t dest[FM1_MOD_SLOTS];
  mod_vdest_t vd[FM1_MOD_VDESTS];
  uint8_t pdest[FM1_MOD_POSITIONS][FM1_MOD_MAX_PARAMS];   /* -> dest, or NONE */
  uint8_t gdest[FM1_MOD_POSITIONS][FM1_MOD_MAX_GATES];
  uint8_t sdest[MOD_SINK_RECS];                /* sink parameter record -> dest */
  uint8_t order[FM1_MOD_POSITIONS];
  uint8_t comp[FM1_MOD_POSITIONS];             /* by position */
  uint8_t gate_conn[FM1_MOD_POSITIONS];
  uint8_t vgate_conn[FM1_MOD_POSITIONS];
  /* Where the per-voice instances live (MG9): after the highest global
   * instance, one block of vsize bytes per voice, position p's at voff[p],
   * its outputs first (vhdr[p] bytes) and the instance after them. */
  uint16_t vbase, vsize;
  uint16_t voff[FM1_MOD_POSITIONS], vhdr[FM1_MOD_POSITIONS];
  uint8_t n_order, n_dest, n_vd;
  uint8_t poly;                                /* positions that run per voice */
  uint8_t vsounds;                             /* sound units whose notes start voices */
  uint8_t vcap;                                /* voices the arena holds */
  uint8_t reserved[2];
} mod_plan_t;

/* A voice (MG9): a note on a sound unit, from its note-on until it is
 * stolen or, after its note-off, its per-voice modules stop moving. Its
 * GATE (rises at the note-on, retriggered by the same key again, falls at
 * the note-off) and TRIG are fed in windows as the system gates are. The
 * layout is the same in 32- and 64-bit builds: 64-bit members first, the
 * size a multiple of 8. */
enum { MOD_V_FREE = 0, MOD_V_HELD = 1, MOD_V_RELEASED = 2 };
enum { MOD_VG_GATE = 0, MOD_VG_TRIG = 1 };
typedef struct mod_voice {
  uint64_t trig_fall;          /* TRIG's pending fall, or MOD_NO_FRAME */
  uint64_t gate_at;            /* the gate's last rise or retrigger */
  uint64_t restore;            /* bit i (parameter index, MOD_PITCH_BIT the
                                  pitch): an offset to put back to 0 */
  fm1_mp_rng_t rng;            /* its probability cables' draws */
  uint32_t age;                /* order of starts and retriggers */
  uint32_t serial;             /* which start this is: seeds its instances */
  uint32_t glevel;             /* bit i: VOICE gate cable i's level here */
  float vel, note, rand;
  float sent[FM1_MOD_VDESTS];  /* the offset the engine holds, per plan.vd */
  fm1_mod_gate_t pend[2][2];   /* [window][GATE, TRIG] */
  fm1_mod_gate_t gate[2];      /* this tick's */
  uint8_t fed[2];              /* each gate's level after every fed event */
  uint8_t sound, key, state, velocity;
  uint8_t ready;               /* bit p: its instance at position p exists */
  uint8_t changed;             /* bit j: sent[j] changed since voice_writes */
} mod_voice_t;
typedef char mod_voice_size[sizeof(mod_voice_t) % 8u == 0 ? 1 : -1];

/* The head of a per-voice instance's block in the arena. */
typedef struct mod_vblk {
  uint16_t handle;             /* create's handle, as an arena offset */
  uint8_t kind;                /* the kind it was made of */
  uint8_t gin;                 /* gate inputs' levels at the last tick's end */
  uint8_t moved;               /* an output moved at the last tick */
  uint8_t reserved[3];
} mod_vblk_t;
#define MOD_VBLK_HEAD 8u

/* A slot's own running state: its probability generator and, for a cable
 * into a gate input, its output level and whether the current pulse passed. */
typedef struct mod_slot_rt {
  fm1_mp_rng_t rng;
  uint8_t level;
  uint8_t pass;
  uint8_t reserved[6];
} mod_slot_rt_t;

struct fm1_mod {
  uint8_t arena[FM1_MOD_ARENA];                /* offset 0, 16-aligned */
  /* 64-bit members, from an 8-aligned offset */
  uint64_t now;                /* first frame of the coming block */
  uint64_t blk;                /* first frame of the current block */
  uint64_t next_tick;          /* t(k) of the next tick */
  uint64_t k;                  /* its index */
  uint64_t trig_fall[MOD_SYS_GATES];   /* a system trigger's pending fall */
  uint64_t cv_has[2];          /* pending CV changes, per window, by id */
  uint64_t rtrg_at;            /* RTRG's last retrigger or rise, as an absolute frame */
  uint64_t rtrg_at_s[FM1_MOD_SOUNDS];          /* each sound unit's RTRG's */
  mod_slot_rt_t srt[FM1_MOD_SLOTS];
  fm1_mp_rng_t note_rng;       /* RAND */
  fm1_mp_rng_t voice_rng;      /* each voice's RAND (MG9) */
  fm1_mod_stats_t stats;
  mod_voice_t voice[FM1_MOD_VOICES];
  /* 32-bit */
  uint32_t magic, seed;
  float rate;
  uint32_t max_frames;
  uint32_t bpm_x100;
  uint32_t restore[MOD_SINK_UNITS];            /* sink parameters to put back to base */
  uint32_t keys[FM1_MOD_SOUNDS][4];            /* notes held, per sound unit */
  uint32_t vage, vserial;                      /* the voices' counters */
  uint32_t seq_keys[8][4];                     /* notes sounding per track */
  float base[FM1_MOD_POSITIONS][FM1_MOD_MAX_PARAMS];
  float peff[FM1_MOD_POSITIONS][FM1_MOD_MAX_PARAMS];
  float out[2][FM1_MOD_POSITIONS][FM1_MOD_MAX_OUTS];
  float sys_cv[FM1_MOD_SRC_SYSTEM];
  float pend_cv[2][FM1_MOD_SRC_SYSTEM];
  /* The sinks' parameters, one record each, in a pool the bound units
   * share: sink i holds records sink_first[i] .. + sink_n[i] (HOST 0 and 1,
   * the others packed after it in binding order). */
  float sink_base[MOD_SINK_RECS];
  float sink_sent[MOD_SINK_RECS];
  float sink_off[MOD_SINK_RECS];               /* the last tick's offset */
  mod_meta_t meta[MOD_SINK_RECS];
  mod_plan_t plan;
  fm1_mod_write_t wr[MOD_MAX_WRITES];
  uint32_t n_wr;
  /* 16-bit */
  fm1_mod_slot_t slot[FM1_MOD_SLOTS];
  uint16_t inst_off[FM1_MOD_POSITIONS];
  uint16_t inst_bytes[FM1_MOD_POSITIONS];
  uint16_t handle[FM1_MOD_POSITIONS];          /* create's handle, as an arena offset */
  /* 8-bit */
  fm1_mod_gate_t gout[2][FM1_MOD_POSITIONS][FM1_MOD_MAX_OUTS];
  fm1_mod_gate_t sys_gate[MOD_SYS_GATES];      /* this tick's system gates */
  fm1_mod_gate_t pend_g[2][MOD_SYS_GATES];     /* pending: [0] the next tick, [1] after */
  uint8_t kind[FM1_MOD_POSITIONS];             /* registry index, or NONE */
  uint8_t glvl_fed[MOD_SYS_GATES];             /* level after every fed event */
  uint8_t sink_first[MOD_SINK_UNITS];
  uint8_t sink_n[MOD_SINK_UNITS];
  uint8_t sink_note[MOD_SINK_UNITS];           /* 1: its engine takes per-note offsets */
  uint8_t cur;                                 /* the output buffer this tick writes */
  uint8_t dirty;                               /* the plan needs a rebuild */
  uint8_t start_frame;                         /* this tick's Start, or NONE */
  uint8_t gin_level[FM1_MOD_POSITIONS];        /* bit j: gate input j's level at the
                                                  last tick's end, as the module saw it */
  uint8_t cur_sound;                           /* the current sound unit (PITCH_CUR) */
  uint8_t vctx;                                /* the voice being run, or NONE */
  uint8_t reserved[1];
};

/* ---- shared by the core, the planner and the kinds ---------------------- */

static inline int mod_finite(float x) { return x == x && (x - x) == 0.0f; }

static inline float mod_clampf(float x, float lo, float hi, float nan_value) {
  if (x != x) return nan_value;
  return x < lo ? lo : (x > hi ? hi : x);
}

/* Round half away from zero, without libm. |x| < 2^23 here. */
static inline float mod_round(float x) {
  return x >= 0.0f ? (float)(int32_t)(x + 0.5f) : -(float)(int32_t)(0.5f - x);
}

static inline uint32_t mod_bits(float x) {
  union { float f; uint32_t u; } v;
  v.f = x;
  return v.u;
}

/* A per-instance seed from the runtime's and a salt (splitmix-style mix). */
static inline uint32_t mod_mix(uint32_t seed, uint32_t salt) {
  uint32_t z = seed ^ (salt * 0x9E3779B9u);
  z = (z ^ (z >> 16)) * 0x85EBCA6Bu;
  z = (z ^ (z >> 13)) * 0xC2B2AE35u;
  return z ^ (z >> 16);
}

/* Appends an edge, keeping edges alternating and in frame order; beyond
 * FM1_MOD_EDGES the last entry carries the final level (fm1_mod.h). */
static inline void mod_gate_edge(fm1_mod_gate_t *g, unsigned frame, unsigned high,
                                 uint32_t *dropped) {
  const unsigned level = (unsigned)fm1_mod_gate_end(g);
  high = high != 0;
  if (frame >= FM1_MOD_TICK) frame = FM1_MOD_TICK - 1u;
  if (g->n && frame < g->ev[g->n - 1u].frame) frame = g->ev[g->n - 1u].frame;
  if (high == level) return;
  if (g->n < FM1_MOD_EDGES) {
    g->ev[g->n].frame = (uint8_t)frame;
    g->ev[g->n].high = (uint8_t)high;
    ++g->n;
    return;
  }
  /* Full: the new level is the one after the third edge; drop the fourth. */
  --g->n;
  if (dropped) *dropped += 2u;
}

static inline void mod_gate_clear(fm1_mod_gate_t *g, unsigned level) {
  g->start = (uint8_t)(level != 0);
  g->n = 0;
  g->reserved[0] = g->reserved[1] = 0;
}

/* A trigger output for kinds: rises at a frame and falls FM1_MOD_TICK
 * frames later, at the same offset of the next tick; a new rise while high
 * is a retrigger (a fall and a rise at its frame). An edge belongs at the
 * boundary after the sample that caused it (a carry, a segment's end), so
 * one at frame FM1_MOD_TICK, the tick's own end, fires at frame 0 of the
 * next tick. */
typedef struct mod_trig {
  uint8_t level;
  uint8_t fall_now;            /* frame of this tick's pending fall, or NONE */
  uint8_t fall_next;           /* frame of the next tick's */
  uint8_t defer;               /* a rise at the next tick's frame 0 */
} mod_trig_t;

static inline void mod_trig_init(mod_trig_t *t) {
  t->level = 0;
  t->fall_now = t->fall_next = MOD_NONE;
  t->defer = 0;
}

static inline void mod_trig_fire(mod_trig_t *t, fm1_mod_gate_t *g, unsigned frame) {
  if (frame >= FM1_MOD_TICK) {
    t->defer = 1;
    return;
  }
  if (t->fall_now != MOD_NONE && t->fall_now <= frame) {
    mod_gate_edge(g, t->fall_now, 0, NULL);
    t->level = 0;
  }
  t->fall_now = MOD_NONE;
  if (t->level) mod_gate_edge(g, frame, 0, NULL);
  mod_gate_edge(g, frame, 1, NULL);
  t->level = 1;
  t->fall_next = (uint8_t)frame;
}

static inline void mod_trig_begin(mod_trig_t *t, fm1_mod_gate_t *g) {
  t->fall_now = t->fall_next;
  t->fall_next = MOD_NONE;
  mod_gate_clear(g, t->level);
  if (t->defer) {
    t->defer = 0;
    mod_trig_fire(t, g, 0);
  }
}

static inline void mod_trig_end(mod_trig_t *t, fm1_mod_gate_t *g, float *out) {
  if (t->fall_now != MOD_NONE) {
    mod_gate_edge(g, t->fall_now, 0, NULL);
    t->level = 0;
    t->fall_now = MOD_NONE;
  }
  *out = (float)t->level;
}

/* 2^x without libm: x rounded to an integer n and a fraction in
 * -0.5..0.5, 2^f from its Taylor series to the 7th power (error under 1e-8
 * relative), scaled by 2^n through the exponent bits. x clamped to +-60. */
float fm1_mod_exp2(float x);

/* The rate knob of LFO and Chance: 0..1 to 0.01..100 Hz on an exponential
 * scale (0.5 is 1 Hz). */
static inline float mod_rate_hz(float k) {
  k = mod_clampf(k, 0.0f, 1.0f, 0.5f);
  return 0.01f * fm1_mod_exp2(k * 13.287712f);
}

/* Frames until an LFO's accumulator next carries, 1..m, or 0 if not within
 * m frames (free-running modes; the rates here keep m x increment < 2^63). */
static inline uint32_t mod_lfo_to_wrap(const fm1_mp_lfo_t *l, uint32_t m) {
  const uint64_t pfull = ((uint64_t)l->phase << 32) | l->frac;
  const uint64_t inc = ((uint64_t)l->inc << 32) | l->inc_frac;
  uint64_t dist;
  uint32_t lo = 1, hi = m;
  if (l->done || inc == 0 || m == 0 || pfull == 0) return 0;
  dist = ~pfull + 1u;                     /* 2^64 - pfull */
  if (inc > 0x7FFFFFFFFFFFFFFFull / m || (uint64_t)m * inc < dist) return 0;
  while (lo < hi) {                       /* the first n with n x inc >= dist */
    const uint32_t mid = lo + (hi - lo) / 2u;
    if ((uint64_t)mid * inc >= dist) hi = mid;
    else lo = mid + 1u;
  }
  return lo;
}

/* A position's per-voice instances go (their kinds' destroy; MG9): the
 * rack or the plan's layout changed under them. Their outputs restart low,
 * so every voice's gate cables from them do too. */
void mod_voices_drop(fm1_mod_t *m);
/* The slots in `mask` restart low in every voice (vc->glevel), as a
 * slot's own level does (srt.level): a cable rewired, newly planned, or
 * whose source restarts. */
static inline void mod_voices_level_clear(fm1_mod_t *m, uint32_t mask) {
  unsigned v;
  for (v = 0; v < FM1_MOD_VOICES; ++v) m->voice[v].glevel &= ~mask;
}
/* The slots whose source is an output of a position in `poly`. */
uint32_t mod_slots_from(const fm1_mod_t *m, uint32_t poly);
/* The per-voice block of voice v at position pos. */
static inline uint8_t *mod_vblock(fm1_mod_t *m, unsigned v, unsigned pos) {
  return m->arena + m->plan.vbase + (uint32_t)v * m->plan.vsize + m->plan.voff[pos];
}

/* The destination of the VOICE slots into a module's parameter (gate 0) or
 * gate input (gate 1), or NONE: a short search, made only where vrouted or
 * vgate_conn says there is one. */
static inline uint8_t mod_vdest_of(const fm1_mod_t *m, unsigned pos, unsigned index, unsigned gate) {
  unsigned d;
  for (d = 0; d < m->plan.n_dest; ++d) {
    const mod_dest_t *e = &m->plan.dest[d];
    if (e->unit == FM1_MOD_MODULE + pos && e->gate == 2u + gate && e->index == index) return (uint8_t)d;
  }
  return MOD_NONE;
}

/* Planner (mod_plan.c). */
void mod_plan_build(fm1_mod_t *m);
int mod_slot_dst_param(const fm1_mod_t *m, const fm1_mod_slot_t *s);   /* index or -1 */
int mod_source_kind(const fm1_mod_t *m, unsigned src, uint8_t *unit);  /* port kind, or -1 */
const fm1_mod_kind_t *mod_kind_at(const fm1_mod_t *m, unsigned pos);

#endif /* FM1_MOD_INT_H */
