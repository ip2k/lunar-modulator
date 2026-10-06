/* fm1_mod.h -- the modulation runtime (docs/16, stage MG1): a rack of up to 8
 * modulation modules inside a 32-slot matrix of 1:1 cables.
 *
 * One system (owner, 2026-10-02). The matrix's sources are the system
 * sources (velocity, note, key gate, the sequencer's gates and clock) and
 * every module output; its destinations are the sound's, the effects' and
 * the host's parameters and every module parameter and gate input. A chain
 * A -> B -> C -> D is three ordinary slots. The planner (Tarjan, then Kahn,
 * rack order breaking ties) runs the modules in cable order, so a chain
 * without a loop arrives in one tick; inside a loop the cable that runs up
 * the rack reads the previous tick, exactly one tick late, and is marked
 * delayed.
 *
 * Time. Modules run once per control tick of FM1_MOD_TICK frames on
 * absolute sample time: tick k runs at frame t(k) = k x 32 (k >= 1) and
 * covers [t(k-1), t(k)). Gate edges keep their frame offset inside a tick,
 * so triggers stay sample-accurate. Output is the same at any host block
 * size: the host bridge (fm1_seq_host.h, fm1_mod_host.h) runs each tick at
 * its own frame and splits a unit's render only where a tick writes to it.
 *
 * Values. Rule M1 (docs/16 §6.1): a knob, a lock or a preset writes a
 * parameter's base; the runtime sends clamp(base + the sum of the enabled
 * slots' contributions, in ascending slot order), or for a LOG parameter
 * (engine API v3) clamp(base x 2^(the sum)), the contributions in octaves
 * (docs/16 §2.3, the octave rule). A destination with no
 * enabled slot is never written, so every render without routes is
 * byte-identical to one without this runtime.
 *
 * Memory. No heap and no pointers in the state: the host asks fm1_mod_size()
 * for the bytes (the same in 32- and 64-bit builds), provides them 16-byte
 * aligned and in any state, and fm1_mod_create() builds the runtime there.
 * Kinds are held by registry index and instances by offset in the runtime's
 * own 8 KB arena. No libm: tables and polynomials only, built with
 * -ffp-contract=off (docs/14's ladder profile), so native and WebAssembly
 * builds agree bit for bit.
 *
 * Voices (docs/16 MG9). A slot flagged VOICE runs once for every voice: a
 * note sounding on a sound unit. Its sources are read in the voice's
 * context: VEL, NOTE, RAND, KEY, TRIG and RTRG are that note's own (and so
 * are S1NOTE ... S4RTRG of the voice's own sound unit), and a
 * module whose kind is POLY_OK (Envelope, LFO, Chance) runs one instance
 * per voice, made in the arena at the note-on and gated by its note unless
 * a VOICE cable patches its gate. A VOICE slot reaches a sound unit's POLY
 * parameter or its pitch through the engine's per-note offsets
 * (set_param_note, fm1_mod_voice_writes), or a per-voice module's input;
 * one into anything else (an effect, a parameter the engine keeps for every
 * note, HOST AMP, a module that does not run per voice) is refused: poly
 * never reaches mono. A slot without VOICE stays global; into a module
 * that runs per voice it moves every voice's instance alike (mono to poly).
 *
 * Threads: in MG1 everything runs on one task (the audio task); edits take
 * effect at the next tick. engines/mod/README.md has the rules and the
 * formulas. MIT licence, like the rest of this repository.
 */
#ifndef FM1_MOD_H_
#define FM1_MOD_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_engine.h"

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_MOD_MAGIC 0x464D314Du       /* "FM1M" */
#define FM1_MOD_API_VERSION 1u
#define FM1_MOD_TICK 32u                /* frames per control tick (owner, 2026-10-02) */
#define FM1_MOD_EDGES 4u                /* gate edges per port per tick */
#define FM1_MOD_POSITIONS 8u            /* rack positions */
#define FM1_MOD_SLOTS 32u               /* matrix slots */
#define FM1_MOD_MAX_PARAMS 32u          /* parameters per kind */
#define FM1_MOD_MAX_GATES 8u            /* gate inputs per kind */
#define FM1_MOD_MAX_OUTS 8u             /* outputs per kind */
#define FM1_MOD_ARENA 8192u             /* bytes for module instances */
#define FM1_MOD_UNIT_PARAMS 32u         /* parameters of a sound or effect unit
                                           that can be destinations */
#define FM1_MOD_Q14 16384               /* amount and offset 1.0 in Q1.14 */
#define FM1_MOD_NONE 0xFFu              /* no source, no frame */
#define FM1_MOD_VOICES 12u              /* voices the runtime tracks (MG9): the
                                           engines' own polyphony */
#define FM1_MOD_VDESTS 8u               /* sound parameters (pitch included) that
                                           VOICE slots may reach at once */

/* ---- Units (a slot's dst_unit) ------------------------------------------
 * A host with one sound binds SOUND, FX1 and FX2; the virtual FM-1's
 * multi-sound (docs/15 §3.16) adds sound units 2-4 and every sound unit's
 * inserts (docs/16 MG3). Codes 4-7, 36-39 (HOST per sound unit), inserts 3
 * and 4 of each sound unit and 42 on are kept for later and name nothing:
 * a slot that names them is refused. */
enum {
  FM1_MOD_SOUND = 0,                    /* sound unit 1's parameters (a host's one sound) */
  FM1_MOD_FX1 = 1,                      /* the master effect slots, in order */
  FM1_MOD_FX2 = 2,
  FM1_MOD_HOST = 3,                     /* PITCH and AMP, below */
  FM1_MOD_MODULE = 8,                   /* 8 + position: a module's parameters
                                           and, with GATE_DST, its gate inputs */
  FM1_MOD_SOUND_UNIT = 16,              /* 16 + k: sound unit k + 1; 16 is SOUND */
  FM1_MOD_INSERT = 20,                  /* 20 + 4k + j: sound unit k + 1's insert j + 1 */
  FM1_MOD_MASTER = 40                   /* 40 + j: master slot j + 1, i.e. FX1 and FX2 */
};
#define FM1_MOD_SOUNDS 4u               /* sound units */
#define FM1_MOD_INSERTS 2u              /* inserts per sound unit (codes for 4) */
#define FM1_MOD_SINKS 15u               /* SOUND FX1 FX2 HOST, sound units 2-4, the 8 inserts */
#define FM1_MOD_SINK_PARAMS 200u        /* parameter records the bound units share,
                                           HOST's six included; fm1_mod_bind: four
                                           of Macro Heavy's 16 (glide's modes,
                                           2026-10-06), ten of a 13-parameter
                                           effect and HOST's six */

/* Sound unit k's code (k < FM1_MOD_SOUNDS): SOUND for k = 0, so a host
 * with one sound and the multi-sound host write the same slots. */
static inline unsigned fm1_mod_sound_unit(unsigned k) {
  return k ? FM1_MOD_SOUND_UNIT + k : (unsigned)FM1_MOD_SOUND;
}
/* Insert j of sound unit k (j < FM1_MOD_INSERTS). */
static inline unsigned fm1_mod_insert_unit(unsigned k, unsigned j) {
  return FM1_MOD_INSERT + 4u * k + j;
}
/* A unit code as slots keep it: 16 is 0 and 40 and 41 are 1 and 2 (a slot
 * set with an alias reads back with the canonical code); any code that
 * names a sink or a module is itself; FM1_MOD_NONE for the rest. */
unsigned fm1_mod_unit_canonical(unsigned unit);
/* The sound unit (0..3) a code names, or -1. */
int fm1_mod_unit_sound(unsigned unit);
/* The sinks in their fixed order (the order of a tick's writes and of
 * fm1_mod_sink): SOUND, FX1, FX2, HOST, sound units 2-4, then each sound
 * unit's inserts. fm1_mod_sink_unit gives sink i's code (FM1_MOD_NONE past
 * the last), fm1_mod_sink_index a code's sink (aliases too), or -1. */
unsigned fm1_mod_sink_unit(unsigned i);
int fm1_mod_sink_index(unsigned unit);

/* The host unit's parameters (fm1_mod_host_params). PITCH is sound unit
 * 1's pitch in semitones, summed with MIDI bend into its engine's
 * pitch_bend: its base is the bend. AMP is a gain before the bus limiter:
 * tremolo. PITCH2-PITCH4 are sound units 2-4's pitches, each based on that
 * sound's bend, and PITCH_CUR the current sound's (fm1_mod_set_current):
 * its cables add to the pitch of whichever sound is current, and it is
 * never written itself (owner, 2026-10-05: a PITCH destination per sound,
 * plus the current sound). */
enum {
  FM1_MOD_HOST_PITCH = 0, FM1_MOD_HOST_AMP = 1, FM1_MOD_HOST_PITCH2 = 2, FM1_MOD_HOST_PITCH3 = 3,
  FM1_MOD_HOST_PITCH4 = 4, FM1_MOD_HOST_PITCH_CUR = 5, FM1_MOD_HOST_PARAMS = 6
};
#define FM1_MOD_HOST_PITCH_UID 1u
#define FM1_MOD_HOST_AMP_UID 2u
#define FM1_MOD_HOST_PITCH2_UID 3u      /* 3, 4, 5: sound units 2-4 */
#define FM1_MOD_HOST_PITCH_CUR_UID 6u
extern const fm1_param_t fm1_mod_host_params[FM1_MOD_HOST_PARAMS];
/* HOST's parameter index for sound unit k's pitch (k < FM1_MOD_SOUNDS). */
static inline unsigned fm1_mod_host_pitch(unsigned k) {
  return k ? FM1_MOD_HOST_PITCH2 + k - 1u : (unsigned)FM1_MOD_HOST_PITCH;
}
/* The sound unit a HOST pitch index bends (PITCH_CUR: -2), or -1 (AMP). */
static inline int fm1_mod_host_pitch_sound(unsigned index) {
  if (index == FM1_MOD_HOST_PITCH) return 0;
  if (index >= FM1_MOD_HOST_PITCH2 && index <= FM1_MOD_HOST_PITCH4) {
    return (int)(index - FM1_MOD_HOST_PITCH2) + 1;
  }
  return index == FM1_MOD_HOST_PITCH_CUR ? -2 : -1;
}

/* ---- Ports ---------------------------------------------------------------- */
typedef enum {
  FM1_PORT_CV_BI = 0,                   /* -1..1, the value at the tick's end */
  FM1_PORT_CV_UNI = 1,                  /* 0..1 */
  FM1_PORT_GATE = 2                     /* 0 or 1, plus edges with frame offsets */
} fm1_port_kind_t;

/* A gate input or an output. unit is an fm1_unit_t: SEMI on a port means
 * semitones / 60, so +-1 is +-5 octaves (docs/16 §2.3). A gate input's
 * `normal` is the system source it reads while no slot reaches it (a jack
 * normalled on a eurorack module): FM1_MOD_SRC_KEY for an envelope's gate,
 * FM1_MOD_NONE for none. io->gate_connected still says "no cable". */
typedef struct fm1_port {
  const char *name;                     /* <= 5 characters */
  uint8_t kind;                         /* fm1_port_kind_t */
  uint8_t unit;                         /* fm1_unit_t */
  uint8_t normal;                       /* gate inputs: a system gate, or NONE */
  uint8_t reserved;
} fm1_port_t;

/* ---- Gates ----------------------------------------------------------------
 * One tick of a gate: its level at the tick's start and up to FM1_MOD_EDGES
 * changes, in frame order, each frame < FM1_MOD_TICK. Edges alternate (every
 * edge changes the level), so the level at the tick's end is the last edge's,
 * or `start`. Two edges may share a frame: a fall and a rise there is a
 * retrigger. A trigger is a gate that falls FM1_MOD_TICK frames after it
 * rose (one tick, 0.725 ms). Beyond FM1_MOD_EDGES the runtime keeps the
 * first three edges and the final level, and counts what it dropped. */
typedef struct fm1_mod_edge {
  uint8_t frame;
  uint8_t high;
} fm1_mod_edge_t;

typedef struct fm1_mod_gate {
  uint8_t start;
  uint8_t n;
  uint8_t reserved[2];
  fm1_mod_edge_t ev[FM1_MOD_EDGES];
} fm1_mod_gate_t;

static inline int fm1_mod_gate_end(const fm1_mod_gate_t *g) {
  return g->n ? g->ev[g->n - 1u].high : g->start;
}

/* ---- The transport, as a kind flagged TRANSPORT sees it ------------------- */
typedef struct fm1_mod_transport {
  uint32_t bpm_x100;                    /* the sequencer's tempo; 12000 without one */
  uint8_t running;                      /* the transport ran at the tick's start,
                                           t(k-1): RUN's level there, so it is the
                                           same at any block size */
  uint8_t start;                        /* frame of a Start in this tick, or NONE */
  uint8_t reserved[2];
} fm1_mod_transport_t;

/* ---- A module kind (docs/16 §2.2) ------------------------------------------
 * A struct of function pointers, like an engine in fm1_engine.h: the
 * runtime asks for the instance size, provides arena memory (16-byte
 * aligned, contents unspecified), and the kind constructs itself there. It
 * never allocates, prints or calls libm, and behaves the same whatever the
 * memory held before.
 *
 * Parameters are API v2 fm1_param_t (fm1_engine.h) with uids pinned in
 * tests/fixtures/mod-uids.json. A module's CV inputs are its parameters: a
 * cable adds to the parameter's base (rule M1). MOD parameters take
 * modulation (an ENUM only with MOD, and is then rounded); INPUT parameters
 * are bare signal inputs, -1..1, base 0, where a cable at 100 % passes its
 * source unchanged. Gate inputs and outputs are ports, by index; their
 * order is part of the kind's contract. */
typedef struct fm1_mod_io {
  uint64_t tick;                        /* k: this call covers [t(k-1), t(k)) */
  const float *p;                       /* effective parameters: base + routes,
                                           clamped, ENUMs rounded */
  uint32_t routed;                      /* bit i: parameter i has an enabled slot */
  uint32_t gate_connected;              /* bit j: gate input j has an enabled slot */
  const fm1_mod_gate_t *gate;           /* one per gate input (normalled when
                                           unconnected); each starts where the
                                           last tick's ended: a cable patched or
                                           pulled, or a normal broken, is an
                                           edge at frame 0 */
  const fm1_mod_transport_t *tp;
  float *out;                           /* every output's value at t(k); a gate's
                                           level there */
  fm1_mod_gate_t *gout;                 /* one per output: edges inside this tick
                                           (gate outputs only; start is filled in) */
} fm1_mod_io_t;

#define FM1_MOD_KIND_TRANSPORT 0x01u    /* uses io->tp (tempo, Start) */
#define FM1_MOD_KIND_POLY_OK 0x02u      /* may run one instance per voice (MG9) */
#define FM1_MOD_KIND_AUDIO_TAP 0x04u    /* later (MG8): reads the audio */

enum { FM1_MOD_RESET_PRESET = 0, FM1_MOD_RESET_START = 1, FM1_MOD_RESET_STOP = 2 };

typedef struct fm1_mod_kind {
  uint32_t magic;                       /* FM1_MOD_MAGIC */
  uint32_t api_version;                 /* FM1_MOD_API_VERSION */
  const char *id;                       /* "lfo" */
  uint32_t guid;                        /* 4 characters, saved in presets */
  const char *name;                     /* "LFO" */
  const char *abbr;                     /* 3 characters: "LFO", "ENV", "CHN" */
  const char *credits;                  /* who and what it is after */
  const fm1_param_t *params;
  uint16_t n_params;                    /* <= FM1_MOD_MAX_PARAMS */
  uint8_t n_gate_in;                    /* <= FM1_MOD_MAX_GATES */
  uint8_t n_out;                        /* <= FM1_MOD_MAX_OUTS */
  const fm1_port_t *gate_in;
  const fm1_port_t *out;
  uint32_t flags;                       /* FM1_MOD_KIND_* */
  uint16_t data_bytes;                  /* pattern data saved with presets; 0: none */
  size_t (*instance_size)(const fm1_host_t *host);
  /* Constructs an instance in mem; seed is per preset and position. */
  void *(*create)(void *mem, const fm1_host_t *host, uint32_t seed);
  void (*destroy)(void *self);          /* may be NULL */
  void (*reset)(void *self, uint32_t why);   /* FM1_MOD_RESET_*; may be NULL */
  void (*process)(void *self, const fm1_mod_io_t *io);
  void (*get_data)(const void *self, uint8_t *buf);   /* NULL when data_bytes is 0 */
  int (*set_data)(void *self, const uint8_t *buf, uint16_t n, uint8_t version);
  const void *(*view)(const void *self);  /* read-only state for drawing; may be NULL */
} fm1_mod_kind_t;

/* The static registry (engines/mod/mod_registry.c). */
extern const fm1_mod_kind_t *const fm1_mod_kinds[];
extern const size_t fm1_mod_kind_count;
/* The registry index of a kind by id or abbreviation (ASCII case ignored),
 * or -1. */
int fm1_mod_kind_find(const char *name);

/* ---- System sources (ids 0-63) ---------------------------------------------
 * The ones MG1 provides, and since MG9 the note sources of one sound unit
 * (44-63; owner, 2026-10-05: note sources selectable per sound, all by
 * default). The gaps are reserved for the later ones (docs/16 §2.4): mod
 * wheel, aftertouch, bend, CC A and B, MACRO 1-4, audio level, keys held
 * (3-15), the arpeggiator's step and gate (40-43). In a VOICE slot (MG9)
 * VEL, NOTE, RAND, KEY, TRIG and RTRG are the voice's own note; KEY and
 * RTRG there are its gate, which a re-struck key retriggers. One sound
 * unit's (S1VEL ...) are the voice's own note in a voice of that sound unit
 * and that sound unit's last note in any other. */
enum {
  FM1_MOD_SRC_VEL = 0,          /* CV_UNI: velocity / 127 of the last note-on on the sound */
  FM1_MOD_SRC_NOTE = 1,         /* CV_BI, SEMI: (last note - 60) / 60 */
  FM1_MOD_SRC_RAND = 2,         /* CV_BI: a seeded random value drawn at each note-on */
  FM1_MOD_SRC_KEY = 16,         /* GATE: high while a note is held on the sound (legato:
                                   a note while another is held changes nothing) */
  FM1_MOD_SRC_TRIG = 17,        /* GATE: a trigger at each note-on on the sound */
  FM1_MOD_SRC_CLOCK = 18,       /* GATE: a trigger each sequencer step (1/16) */
  FM1_MOD_SRC_BEAT = 19,        /* GATE: a trigger each beat */
  FM1_MOD_SRC_BAR = 20,         /* GATE: a trigger each bar */
  FM1_MOD_SRC_RUN = 21,         /* GATE: high while the transport runs */
  FM1_MOD_SRC_START = 22,       /* GATE: a trigger at Start */
  FM1_MOD_SRC_RTRG = 23,        /* GATE: KEY retriggered: high while a note is held, and
                                   a fall and a rise at the frame of each note-on that
                                   comes while it is high (notes starting at one frame,
                                   a chord, retrigger it once). The default rack's
                                   envelopes take it (docs/16 MG3, owner, 2026-10-05) */
  FM1_MOD_SRC_SEQ_GATE = 24,    /* GATE, 24-31: high while track 1-8 sounds a note */
  FM1_MOD_SRC_SEQ_VEL = 32,     /* CV_UNI, 32-39: velocity / 127 of track 1-8's last note */
  FM1_MOD_SRC_S_NOTE = 44,      /* 44-47: NOTE, VEL, KEY, TRIG and RTRG of sound unit */
  FM1_MOD_SRC_S_VEL = 48,       /* 48-51:   1-4's notes only (S1NOTE, S2VEL, S3KEY...); */
  FM1_MOD_SRC_S_KEY = 52,       /* 52-55:   the ids above follow every sound unit's */
  FM1_MOD_SRC_S_TRIG = 56,      /* 56-59 */
  FM1_MOD_SRC_S_RTRG = 60,      /* 60-63 */
  FM1_MOD_SRC_SYSTEM = 64,      /* ids below are system sources */
  FM1_MOD_SRC_MODULE = 64       /* 64 + 8 x position + port: module outputs */
};

typedef struct fm1_mod_source_info {
  const char *name;             /* "VEL", "SEQ3" */
  uint8_t kind;                 /* fm1_port_kind_t */
  uint8_t unit;                 /* fm1_unit_t */
} fm1_mod_source_info_t;

/* A system source's description, or NULL for an undefined id. */
const fm1_mod_source_info_t *fm1_mod_system_source(unsigned id);

/* ---- Slots (12 bytes each, docs/16 §2.4) ---------------------------------- */
#define FM1_MOD_SLOT_ON 0x01u           /* enabled */
#define FM1_MOD_SLOT_POL_MASK 0x06u     /* polarity, below */
#define FM1_MOD_SLOT_POL_SHIFT 1u
#define FM1_MOD_SLOT_GATE_DST 0x08u     /* dst is a module's gate input index */
#define FM1_MOD_SLOT_CURVE_MASK 0x70u   /* one of 8 curves, below */
#define FM1_MOD_SLOT_CURVE_SHIFT 4u
#define FM1_MOD_SLOT_VOICE 0x80u        /* per voice (MG9, above) */

enum { FM1_MOD_POL_AUTO = 0, FM1_MOD_POL_UNI = 1, FM1_MOD_POL_BI = 2, FM1_MOD_POL_INV = 3 };
enum {
  FM1_MOD_CURVE_LIN = 0, FM1_MOD_CURVE_SQUARE, FM1_MOD_CURVE_CUBE, FM1_MOD_CURVE_ROOT,
  FM1_MOD_CURVE_CBRT, FM1_MOD_CURVE_EXP, FM1_MOD_CURVE_LOG, FM1_MOD_CURVE_S,
  FM1_MOD_CURVE_COUNT
};

typedef struct fm1_mod_slot {
  uint8_t src;                  /* 0-63 system; 64 + 8 x position + port */
  uint8_t via;                  /* a source scaling the cable (read 0..1), or NONE */
  uint8_t dst_unit;             /* FM1_MOD_SOUND .. FM1_MOD_HOST, or 8 + position */
  uint8_t flags;                /* FM1_MOD_SLOT_* */
  uint16_t dst;                 /* a parameter's uid, or a gate input's index */
  int16_t amount;               /* Q1.14, -1..1 of the destination's range */
  int16_t offset;               /* Q1.14, added to the source before scaling */
  uint16_t uid;                 /* base uid of the slot's own AMT and OFS, for
                                   locks (MG6); unused in MG1 */
} fm1_mod_slot_t;

/* Curve c at s in -1..1: a 33-entry table, sign-preserving, interpolated. */
float fm1_mod_curve(unsigned c, float s);

/* ---- The runtime ------------------------------------------------------------ */
typedef struct fm1_mod fm1_mod_t;

/* Bytes one runtime needs, the arena included; the same at 32 and 64 bits. */
size_t fm1_mod_size(void);

/* Builds a runtime in mem (fm1_mod_size() bytes, 16-byte aligned, any
 * contents): an empty rack, every slot off, no unit bound. `seed` seeds
 * every random stream (instances, probability cables, RAND), so a preset
 * replays exactly. NULL on misaligned memory. */
fm1_mod_t *fm1_mod_create(void *mem, const fm1_host_t *host, uint32_t seed);
/* Destroys the instances (the memory is the host's). */
void fm1_mod_destroy(fm1_mod_t *m);

/* Binds a sound or effect unit (any sink but HOST, by code; aliases too) to
 * an engine: its first FM1_MOD_UNIT_PARAMS parameters can be destinations.
 * Every base and every value sent becomes the parameter's default, which is
 * what a new engine instance holds; a host then sets the bases it changes.
 * NULL unbinds. The bound units share FM1_MOD_SINK_PARAMS parameter records
 * (HOST takes two): an engine that would need more than are left is not
 * bound (its unit's cables are refused). Returns the parameters taken, or
 * -1 for a bad unit or no room. */
int fm1_mod_bind(fm1_mod_t *m, unsigned unit, const fm1_engine_t *e);

/* Places a kind (a registry index, or -1 for none) at a position 0-7. The
 * old instance is destroyed; the new one starts from its defaults, seeded
 * by the runtime's seed and the position. When a different kind replaces
 * one, the slots that touch the position are switched off (docs/16 §2.4:
 * disabled, never deleted). Returns how many, or -1 if the index is bad or
 * the kind does not fit the arena (the old module then stays), or if the
 * kind's create fails (the position is then empty). The new module's gate
 * inputs start low, so one whose input is high sees a rise at its first
 * tick; its outputs start low too, and so does every gate cable from it, so
 * a module it reached sees a fall rather than a gate held open. */
int fm1_mod_set_kind(fm1_mod_t *m, unsigned pos, int kind);
int fm1_mod_kind_at(const fm1_mod_t *m, unsigned pos);   /* -1: empty */
/* The default rack, which reproduces the options note's C1: LFO, LFO,
 * Envelope, Envelope, Chance at positions 0-4, no slot on. */
void fm1_mod_default_rack(fm1_mod_t *m);
/* Moves the module at `from` to `to`, shifting those between, and rewrites
 * every slot that names them. Display order breaks the planner's ties. */
int fm1_mod_move(fm1_mod_t *m, unsigned from, unsigned to);

/* A module parameter's base (a knob, a lock, a preset), by index. NaN
 * becomes the default. Returns 0 for a bad position or index. */
int fm1_mod_set_param(fm1_mod_t *m, unsigned pos, unsigned index, float value);
float fm1_mod_param_base(const fm1_mod_t *m, unsigned pos, unsigned index);
/* Its effective value at the last tick (base + routes). */
float fm1_mod_param(const fm1_mod_t *m, unsigned pos, unsigned index);

/* An edit that keeps a slot's ends (source, VIA, unit, destination and
 * GATE_DST) keeps its running state: a gate cable stays high or low and
 * its probability stream runs on, so turning an amount never restarts or
 * strands a gate. New ends make a new cable, low, with its stream from the
 * seed. */
int fm1_mod_set_slot(fm1_mod_t *m, unsigned i, const fm1_mod_slot_t *s);
int fm1_mod_get_slot(const fm1_mod_t *m, unsigned i, fm1_mod_slot_t *out);
/* 1 when an enabled slot's cable reaches a parameter of `unit` (any code
 * of a sink, aliases too), whatever its amount: the host's answer for
 * FM1_PARAM_DRIVEN (fm1_engine.h), with its own lock lanes. 0 otherwise,
 * and for a gate input's cable or a code that names no sink. */
int fm1_mod_unit_routed(const fm1_mod_t *m, unsigned unit);
/* Q1.14 from a float in -1..1; NaN gives 0. */
int16_t fm1_mod_q14(float x);

/* Rule M1 for sinks (any sink's code, aliases too). A knob, a lock or a revert
 * sets the base of the unit's parameter `index`; the return value is what
 * the host sends now: the value itself when nothing routes there, else
 * clamp(base + the last tick's offset). The host must send it. NaN is the
 * default. */
float fm1_mod_set_base(fm1_mod_t *m, unsigned unit, unsigned index, float value);
float fm1_mod_base(const fm1_mod_t *m, unsigned unit, unsigned index);
/* What the runtime last sent, or what the host sent through set_base,
 * clamped to the range as the engine holds it (NaN as the default, an
 * ENUM rounded), so a route at zero amount writes nothing. */
float fm1_mod_sent(const fm1_mod_t *m, unsigned unit, unsigned index);

/* ---- Time: one block at a time ------------------------------------------------
 * A host runs, per block: live input (fm1_mod_live_note), then begin, then
 * the block's events and ticks in frame order (the bridge does this:
 * fm1_mod_host.h), then the next block. */

/* A note on sound unit 1 from live input (keys, USB-MIDI), at the start
 * of the coming block; velocity 0 is a note-off. fm1_mod_live_sound_note
 * is the same on sound unit `sound` (0-3): the note sources of every sound
 * and that sound's own (S1KEY...) hear it, and a voice starts for it when a
 * VOICE slot reaches that sound (MG9; the host then sends
 * fm1_mod_voice_start's offsets after the engine's note_on). */
void fm1_mod_live_note(fm1_mod_t *m, uint8_t key, uint8_t velocity);
void fm1_mod_live_sound_note(fm1_mod_t *m, unsigned sound, uint8_t key, uint8_t velocity);

/* Starts a block of `frames`. bpm_x100 0 keeps the last tempo. Returns the
 * frame of the block's first tick, or a value >= frames for none. The
 * transport's state reaches the kinds through fm1_mod_seq_run, at its
 * frame, not per block. */
uint32_t fm1_mod_begin(fm1_mod_t *m, uint32_t frames, uint32_t bpm_x100);

/* Events of the current block, at their frame, in frame order. */
void fm1_mod_note(fm1_mod_t *m, uint32_t frame, uint8_t key, uint8_t velocity);  /* sound unit 1 */
void fm1_mod_sound_note(fm1_mod_t *m, uint32_t frame, unsigned sound, uint8_t key,
                        uint8_t velocity);
void fm1_mod_seq_note(fm1_mod_t *m, uint32_t frame, uint8_t track, uint8_t key, uint8_t velocity);
/* The sequencer's 24-PPQN clock at master tick `tick` (96 PPQN, 0 at Start):
 * CLOCK each 24, BEAT each 96, BAR each 384. */
void fm1_mod_seq_clock(fm1_mod_t *m, uint32_t frame, uint32_t tick);
void fm1_mod_seq_run(fm1_mod_t *m, uint32_t frame, int running);   /* Start, Stop */

/* A value the tick writes: the host sends it at the tick's frame. A
 * per-voice write (key below 128, MG9) is a per-note offset: the host calls
 * the sound unit's set_param_note(key, index, value), index being a
 * parameter's or FM1_PARAM_NOTE_PITCH. */
typedef struct fm1_mod_write {
  uint8_t unit;                 /* a sink's canonical code (a sound unit's for a voice) */
  uint8_t key;                  /* FM1_MOD_NONE, or the note a per-voice write moves */
  uint16_t index;               /* the unit's parameter index (HOST: PITCH, AMP...) */
  float value;
} fm1_mod_write_t;

/* Runs the tick at `frame` of the current block (the frame begin or the
 * previous tick named). *w gets its writes, in unit and index order, valid
 * until the next call; only values whose bits changed are written. Returns
 * how many. The next tick is at frame + FM1_MOD_TICK. */
uint32_t fm1_mod_tick(fm1_mod_t *m, uint32_t frame, const fm1_mod_write_t **w);

/* The per-voice offsets the last tick changed (MG9), at most cap of them,
 * in voice and destination order; each one once. A host with per-voice
 * engines calls it after every tick and sends them at the tick's frame.
 * Offsets a voice no longer gets (its cable gone, or the voice stopped
 * because the arena holds fewer voices after a rack edit) come back as 0. */
uint32_t fm1_mod_voice_writes(fm1_mod_t *m, fm1_mod_write_t *out, uint32_t cap);
/* A voice's first offsets, right after the engine's note_on for it (which
 * set them to 0): the note's own sources (VEL, NOTE, RAND) and every other
 * source as it stands; its per-voice modules start at the next tick. 0 when
 * no voice sounds that key on that sound. */
uint32_t fm1_mod_voice_start(fm1_mod_t *m, unsigned sound, uint8_t key, fm1_mod_write_t *out,
                             uint32_t cap);

/* Every per-note offset a voice holds that is not 0, as a write of 0 (a
 * host letting the runtime go puts its engines back as they were); the
 * voices then hold none. More than cap of them: call again until it
 * returns 0. */
uint32_t fm1_mod_voice_clear(fm1_mod_t *m, fm1_mod_write_t *out, uint32_t cap);

/* The current sound unit (0-3, the one the keys play): HOST PITCH_CUR's
 * cables bend it. 0 at creation. */
void fm1_mod_set_current(fm1_mod_t *m, unsigned sound);
unsigned fm1_mod_current(const fm1_mod_t *m);

/* Calls every instance's reset(why) (a preset load, a Start), per-voice
 * ones included. */
void fm1_mod_reset(fm1_mod_t *m, uint32_t why);

/* ---- Reading state (logs, tests, the UI) ------------------------------------ */
float fm1_mod_out(const fm1_mod_t *m, unsigned pos, unsigned port);
const fm1_mod_gate_t *fm1_mod_gate_out(const fm1_mod_t *m, unsigned pos, unsigned port);
float fm1_mod_system_value(const fm1_mod_t *m, unsigned id);   /* at the last tick */
/* A system gate's edges at the last tick; NULL for a CV source or a bad id. */
const fm1_mod_gate_t *fm1_mod_system_gate(const fm1_mod_t *m, unsigned id);

typedef struct fm1_mod_plan_info {
  uint32_t active;              /* slots that run */
  uint32_t refused;             /* slots on but invalid: a missing source or
                                   destination, NOLOCK, an ENUM without MOD, a
                                   VOICE slot whose target is mono (MG9) */
  uint32_t delayed;             /* slots whose source (or VIA) reads a tick late */
  uint8_t order[FM1_MOD_POSITIONS];   /* positions in run order */
  uint8_t comp[FM1_MOD_POSITIONS];    /* order[i]'s component, numbered in run order */
  uint8_t n_order;
  uint8_t n_dest;
  uint8_t poly;                 /* positions that run one instance per voice */
  uint8_t voice_cap;            /* voices the arena holds them for */
  uint32_t voice;               /* active VOICE slots */
  uint8_t voice_sounds;         /* sound units whose notes start voices */
  uint8_t n_vdest;              /* sound parameters VOICE slots reach */
  uint16_t voice_bytes;         /* the arena one voice's instances take */
} fm1_mod_plan_info_t;
/* The plan the next tick uses (built now if an edit is pending). */
void fm1_mod_get_plan(fm1_mod_t *m, fm1_mod_plan_info_t *out);

typedef struct fm1_mod_stats {
  uint64_t ticks;
  uint64_t writes;              /* values written to sinks */
  uint32_t plans;               /* plan builds */
  uint32_t edges_dropped;       /* gate edges beyond FM1_MOD_EDGES per tick */
  uint32_t nonfinite;           /* non-finite values replaced (sources, outputs) */
  uint32_t voice_starts;        /* voices started (MG9) */
  uint64_t voice_writes;        /* per-note offsets handed out */
  uint32_t voice_steals;        /* voices taken from a sounding note */
  uint32_t voice_ends;          /* voices that ran out after their note-off */
} fm1_mod_stats_t;
void fm1_mod_get_stats(const fm1_mod_t *m, fm1_mod_stats_t *out);

/* The routed sinks, for logs and the UI: i-th parameter with an enabled
 * slot, over the sinks in fm1_mod_sink_unit's order. 0 past the last. */
typedef struct fm1_mod_sink_info {
  uint8_t unit;                 /* its canonical code */
  uint8_t reserved;
  uint16_t index;
  uint16_t uid;
  uint16_t slots;               /* how many enabled slots reach it */
  float base;
  float value;                  /* sent */
} fm1_mod_sink_info_t;
int fm1_mod_sink(fm1_mod_t *m, unsigned i, fm1_mod_sink_info_t *out);

/* The voices (MG9), for logs, tests and the UI: voice i's note, or 0 when
 * it is free. state 1: its note is held; 2: released, still running. */
typedef struct fm1_mod_voice_info {
  uint8_t sound, key, state, velocity;
  uint32_t age;                 /* the start or retrigger order */
} fm1_mod_voice_info_t;
int fm1_mod_voice(const fm1_mod_t *m, unsigned i, fm1_mod_voice_info_t *out);
/* Voice i's instance at position pos: an output's value at the last tick
 * (0 when the position does not run per voice or the voice is free). */
float fm1_mod_voice_out(const fm1_mod_t *m, unsigned i, unsigned pos, unsigned port);
/* How many voices sound now (held or still running). */
unsigned fm1_mod_voice_count(const fm1_mod_t *m);

/* ---- Small helpers for hosts and kinds --------------------------------------- */

/* The Resonator kind's Cutoff (0..1, a log knob; NaN as its default) as
 * the frequency it sets at `sample_rate`, in Hz, exactly as the kind
 * computes it: 0.05 Hz x 2^(13 x Cutoff), held below 0.3 x the tick rate (a
 * UI shows the knob in Hz this way; docs/16 MG3). The kind was MG2's
 * Filter until 2026-10-05 (owner: Resonator, so the audio effect alone is
 * the Filter). */
float fm1_mod_resonator_hz(float cutoff, float sample_rate);

/* A gain that moves to each new value over one tick, linearly, on absolute
 * frames, so the result is the same at any block size: the AMP sink. */
typedef struct fm1_mod_ramp {
  uint64_t t0;                  /* where the current move started */
  float from, to;
} fm1_mod_ramp_t;
void fm1_mod_ramp_init(fm1_mod_ramp_t *r, float value);
void fm1_mod_ramp_set(fm1_mod_ramp_t *r, uint64_t frame, float value);
/* Multiplies n stereo frames starting at absolute frame `frame`. */
void fm1_mod_ramp_apply(const fm1_mod_ramp_t *r, uint64_t frame, float *lr, uint32_t n);

#ifdef __cplusplus
}
#endif

#endif /* FM1_MOD_H_ */
