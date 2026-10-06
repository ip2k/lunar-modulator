/* fm1_mod_ui.h -- modulation on the virtual FM-1's panel (docs/16 §5, stage
 * MG3): the state of the RACK, MATRIX and CHAIN pages, the routing gesture,
 * and the names, lists and script lines they share. fm1_mod_view.h draws
 * them; fm1_app.c hosts the runtime (fm1_mod.h) and feeds this module the
 * panel's edges.
 *
 * The pages (owner decisions, 2026-10-02):
 *   RACK    LFO opens it at the LFOs, ENV at the Envelopes (a tap; again
 *           steps to the next one of that kind). A page per module, its
 *           parameters on KNOB1-4; SELECT walks every (position, page) of
 *           the 8 positions; ALGORITHM opens the kind picker, which commits
 *           after a second without a turn; SEL grabs the module so SELECT
 *           moves it in the rack.
 *   MATRIX  EDIT opens it: 7 of the 32 slots as rows of 19 characters and a
 *           hint line. A row is the source (6 characters), a mark for the
 *           slot's state, then page A's destination (7) and amount (4)
 *           or page B's VIA (5), curve and polarity. Page A: KNOB1 source, KNOB2 destination (a picker,
 *           ALGORITHM jumps between groups while it is open, commit after a
 *           second), KNOB3 amount, KNOB4 offset. ALGORITHM otherwise flips
 *           to page B: KNOB1 VIA, KNOB2 curve, KNOB3 polarity, KNOB4 on.
 *   CHAIN   SEL in MATRIX: the longest path through the selected slot.
 *   Gesture Hold ENV or LFO and turn KNOB1-4 on HOME, FX or RACK: a cable
 *           from the selected Envelope or LFO (the last one shown on its
 *           page; the first by default) to that knob's parameter, its
 *           amount following the turn (docs/16's quick assign).
 * Modules are named by kind and position, docs/16 §2.4's labels: the
 * kind's three-letter abbreviation and the rack position, so the default
 * rack is LFO1, LFO2, ENV3, ENV4 and CHN5, and no two modules share a name
 * whatever their kinds (Chance, Calc, Compare and Coin all begin with C:
 * CHN, CLC, CMP, COI). fm1-render's script names positions the same way
 * (lfo1 lfo2 env3 env4 chance5, or mod3).
 *
 * Destinations. A cable's destination is the slot's dst_unit code and a uid
 * (or a gate input's index), fm1_mod.h's codes (docs/16 MG3, "Destination
 * codes"): 0 sound unit 1 (also 16), 17-19 sound units 2-4, 20 + 4k + j
 * sound unit k + 1's insert j + 1, 1 and 2 the master slots (also 40, 41),
 * 3 HOST, 8 + position a module. The lists walk a table of sink groups
 * (kSinks in fm1_mod_ui.c), in the order S1, S1 In1, S1 In2, S2 ... S4 In2,
 * M1, M2, Host, then the modules; a group whose unit is empty has no
 * entries. Short names (a MATRIX row's seven characters) are the group's
 * tag and the parameter, unique within its engine: S1Tmbre, S2Color,
 * S1I1Bts, M1Mix, Pitch; full names S1 Timbre, S1 In1 Bits, M1 Mix, Host
 * Pitch. A new cable's target picker opens at the current sound
 * (env->sound), as the gesture on HOME makes cables to it.
 *
 * Scope. Every cable here is global. The slot record keeps
 * FM1_MOD_SLOT_VOICE for per-voice cables (one instance per note, the next
 * stage); a MATRIX row shows such a slot with `v` and the script line for
 * it does not exist yet, so a log that meets one says it is incomplete.
 *
 * Edits go through fm1_mod_ui_set_* below, which apply them to the runtime
 * and hand each one to env->emit as a line of fm1-render's --mod format
 * (engines/host/mod_script.h), so the native harness can log a panel
 * session that fm1-render replays byte for byte.
 *
 * C99, no heap. MIT licence, like the rest of this repository.
 */
#ifndef FM1_MOD_UI_H_
#define FM1_MOD_UI_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_engine.h"
#include "fm1_mod.h"

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_MOD_UI_NONE 0xFFu
#define FM1_MOD_UI_ROWS 7            /* MATRIX: slot rows on the screen */
#define FM1_MOD_UI_ROW_CHARS 19      /* a row, LINE_CHARS */
#define FM1_MOD_UI_DST_CHARS 7       /* a destination's short form in a row */
#define FM1_MOD_UI_SINKS FM1_MOD_SINKS   /* env->unit, by sink index (fm1_mod_sink_unit) */
#define FM1_MOD_UI_MAX_DESTS \
  ((FM1_MOD_SINKS - 1) * FM1_MOD_UNIT_PARAMS + FM1_MOD_HOST_PARAMS + \
   FM1_MOD_POSITIONS * (FM1_MOD_MAX_PARAMS + FM1_MOD_MAX_GATES))
#define FM1_MOD_UI_MAX_SOURCES (FM1_MOD_SRC_SYSTEM + FM1_MOD_POSITIONS * FM1_MOD_MAX_OUTS)
#define FM1_MOD_UI_CHAIN_LINES 18    /* 9 nodes and 9 cables at most */
#define FM1_MOD_UI_LINE 160          /* a script line */

enum { FM1_MOD_PICK_NONE = 0, FM1_MOD_PICK_KIND = 1, FM1_MOD_PICK_DEST = 2 };

/* MATRIX's fields, as the hint line names them: page A's knobs, then B's. */
enum {
  FM1_MOD_F_SRC = 0, FM1_MOD_F_DST, FM1_MOD_F_AMT, FM1_MOD_F_OFS,
  FM1_MOD_F_VIA, FM1_MOD_F_CURVE, FM1_MOD_F_POL, FM1_MOD_F_ON
};

/* A destination: what a slot's dst_unit, dst and GATE_DST say, resolved. */
typedef struct fm1_mod_dest {
  uint8_t unit;                /* the dst_unit code (above) */
  uint8_t gate;                /* 1: a module's gate input */
  uint16_t dst;                /* the parameter's uid, or the gate input's index */
  int16_t index;               /* the parameter's index in its unit, or the gate's */
  uint16_t reserved;
} fm1_mod_dest_t;

/* Where edits go and what names they use: the runtime, the engines bound
 * to its sinks (by sink index, fm1_mod_sink_unit's order; HOST's unused),
 * the current sound, and a callback that takes each edit as one script
 * line; emit may be NULL. */
typedef struct fm1_mod_ui_env {
  fm1_mod_t *m;
  float rate;                  /* the host's sample rate (0: unknown), for values in Hz */
  uint8_t sound;               /* the current sound unit, 0..FM1_MOD_SOUNDS - 1 */
  const fm1_engine_t *unit[FM1_MOD_UI_SINKS];
  void (*emit)(void *ctx, const char *line);
  void *ctx;
} fm1_mod_ui_env_t;

/* A popup a gesture asks the app to show: up to three lines, `mark` the
 * highlighted one or -1; n 0 for none. */
typedef struct fm1_mod_ui_say {
  char line[3][24];
  int8_t n, mark;
} fm1_mod_ui_say_t;

typedef struct fm1_mod_ui {
  uint8_t pos, page;           /* RACK: the position and its page shown */
  uint8_t sel_lfo, sel_env;    /* the LFO and Envelope last shown on their page */
  uint8_t grab;                /* RACK: SEL took the module; SELECT moves it */
  uint8_t slot, top;           /* MATRIX: the selected slot and the first row shown */
  uint8_t mpage;               /* MATRIX: page A (0) or B (1) */
  int8_t field;                /* the field on MATRIX's hint line (FM1_MOD_F_*), or -1 */
  uint8_t picker;              /* FM1_MOD_PICK_* waiting to commit */
  uint8_t pick_at;             /* its position (KIND) or slot (DEST) */
  uint8_t held;                /* FM1_BTN_ENV or FM1_BTN_LFO held for the gesture, or NONE */
  uint8_t held_used;           /* a knob turned while it was held */
  uint8_t unloggable;          /* an edit had no script line: a log is incomplete */
  int16_t pick;                /* the picker's entry */
  uint64_t field_until;        /* frame at which the hint line goes back */
  uint32_t srcset;             /* slots whose source was chosen before a destination */
  int8_t off_kind[FM1_MOD_POSITIONS];    /* the kind a position held when a change
                                            switched its cables off, or -1 */
  uint32_t off_slots[FM1_MOD_POSITIONS]; /* those cables, switched on again when
                                            the kind comes back (docs/16 §2.4) */
  fm1_mod_plan_info_t plan;    /* the plan as the last block ran it (delayed,
                                  refused); the app refreshes it after a tick */
} fm1_mod_ui_t;

void fm1_mod_ui_init(fm1_mod_ui_t *u);

/* ---- names --------------------------------------------------------------- */

/* "LFO1", "ENV3": the kind's abbreviation and the position (1-8); "--"
 * for an empty position. */
void fm1_mod_ui_label(const fm1_mod_t *m, unsigned pos, char *buf, size_t cap);
/* "Envelope 3", or "Empty 6": the kind's name and the position. */
void fm1_mod_ui_title(const fm1_mod_t *m, unsigned pos, char *buf, size_t cap);
/* A source: short (at most 6 characters: "VEL", "LFO1", "LFO1.2") or full
 * ("LFO1 Wrap"). */
void fm1_mod_ui_source(const fm1_mod_t *m, unsigned src, int full, char *buf, size_t cap);
/* The destination a slot names; 0 when it names nothing that exists. */
int fm1_mod_ui_slot_dest(const fm1_mod_ui_env_t *env, const fm1_mod_slot_t *s, fm1_mod_dest_t *d);
/* Its parameter (NULL for a gate input or nothing). */
const fm1_param_t *fm1_mod_ui_dest_param(const fm1_mod_ui_env_t *env, const fm1_mod_dest_t *d);
/* A destination: short (at most FM1_MOD_UI_DST_CHARS: "S1Tmbre", "M1Mix",
 * "ENV3Atk", a unit's tag or a module's label and the parameter, unique
 * among its unit's or kind's) or full ("S1 Timbre", "M1 Mix", "S2 In1 Mix",
 * "ENV3 Attack"). */
void fm1_mod_ui_dest_name(const fm1_mod_ui_env_t *env, const fm1_mod_dest_t *d, int full,
                          char *buf, size_t cap);

/* ---- lists ----------------------------------------------------------------- */

/* Every source in order: the system sources, then each module's outputs. */
int fm1_mod_ui_sources(const fm1_mod_t *m, uint8_t *out, int cap);
/* Every destination that takes modulation, by group: each sound unit's
 * parameters and its inserts', the master slots', the host's, then each
 * module's parameters and gate inputs. */
int fm1_mod_ui_dests(const fm1_mod_ui_env_t *env, fm1_mod_dest_t *out, int cap);

/* ---- slots ------------------------------------------------------------------- */

int fm1_mod_ui_has_dst(const fm1_mod_slot_t *s);
/* Nothing in it: no destination and no source chosen. */
int fm1_mod_ui_empty(const fm1_mod_ui_t *u, const fm1_mod_t *m, unsigned i);
/* Q1.14 as a whole percentage, rounded half away from zero. */
int fm1_mod_ui_pct(int16_t q14);
/* MATRIX row i on page A (0) or B (1): 19 characters and a NUL. */
void fm1_mod_ui_row(const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u, unsigned i, int page,
                    char out[FM1_MOD_UI_ROW_CHARS + 1]);
/* The hint line: the field last turned while it shows, else the slot. */
void fm1_mod_ui_hint(const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u, uint64_t now,
                     char *buf, size_t cap);
/* A module parameter's value as RACK shows it, when the knob's own number
 * is not the clearest: the Filter's Cutoff in Hz (the knob stays 0..1 on
 * its log scale). 0 when the app's usual formatting applies. */
int fm1_mod_ui_value(const fm1_mod_ui_env_t *env, unsigned pos, unsigned index, float v, char *buf,
                     size_t cap);
/* How many switched-on cables reach a destination, and the sum of their
 * amounts' magnitudes (0..32) in *depth. */
int fm1_mod_ui_routes(const fm1_mod_t *m, unsigned unit, uint16_t dst, int gate, float *depth);

/* ---- script lines (engines/host/mod_script.h) ----------------------------- */

/* Slot i as one line ("slot 5 mod1.1 > snd:Timbre amt=40 ..."); 0 when it
 * has no destination (nothing to write) or no line can say it. */
int fm1_mod_ui_slot_line(const fm1_mod_ui_env_t *env, unsigned i, char *buf, size_t cap);
/* The whole state as lines, through env->emit: the seed, every position,
 * every base that is not its default, every slot with a destination. 1 if
 * every line could be written. */
int fm1_mod_ui_dump(const fm1_mod_ui_env_t *env, uint32_t seed);

/* ---- edits: applied to the runtime, then emitted --------------------------------- */

int fm1_mod_ui_set_slot(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, unsigned i,
                        const fm1_mod_slot_t *s);
/* A kind (registry index, -1 empty) at a position. The cables the change
 * switches off are remembered and switched on again when the position gets
 * that kind back. Returns the runtime's result. */
int fm1_mod_ui_set_kind(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, unsigned pos, int kind);
int fm1_mod_ui_set_param(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, unsigned pos,
                         unsigned index, float value);
int fm1_mod_ui_move(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, unsigned from, unsigned to);
/* The default rack (LFO, LFO, Envelope, Envelope, Chance) and its two
 * cables, RTRG into each Envelope's GATE at 100 %, so every note on any
 * sound unit (keys, MIDI in and the sequencer) restarts the envelopes, a
 * note played while another is held too (owner, 2026-10-05). They are
 * ordinary slots 1 and 2: KEY in their place makes the envelopes legato.
 * Not emitted: a log starts with fm1_mod_ui_dump. */
void fm1_mod_ui_default(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u);

/* ---- the pages ---------------------------------------------------------------- */

/* Pages of the module at pos (1 for an empty position) and the parameters
 * on one, KNOB1 first (INPUT parameters are not on the knobs). */
int fm1_mod_ui_rack_pages(const fm1_mod_t *m, unsigned pos);
int fm1_mod_ui_rack_params(const fm1_mod_t *m, unsigned pos, unsigned page, int idx[4]);
/* The position of the selected module of a kind (the last shown, else the
 * first), or -1. */
int fm1_mod_ui_selected(const fm1_mod_ui_t *u, const fm1_mod_t *m, int kind);
/* LFO or ENV tapped: RACK at the selected module of that kind, or the next
 * one when RACK shows one already. 0 when the rack holds none (RACK then
 * opens at the first empty position, or stays where it was). */
int fm1_mod_ui_open_rack(fm1_mod_ui_t *u, const fm1_mod_t *m, int kind, int in_rack);
void fm1_mod_ui_rack_select(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int delta);
void fm1_mod_ui_rack_knob(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int knob, int delta);
void fm1_mod_ui_rack_algorithm(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int delta,
                               fm1_mod_ui_say_t *say);
void fm1_mod_ui_matrix_select(fm1_mod_ui_t *u, int delta);
void fm1_mod_ui_matrix_knob(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int knob, int delta,
                            uint64_t hint_until, fm1_mod_ui_say_t *say);
void fm1_mod_ui_matrix_algorithm(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int delta,
                                 fm1_mod_ui_say_t *say);
/* CHAIN: SELECT steps to the previous or next slot that has a cable. */
void fm1_mod_ui_chain_select(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int delta);
/* A waiting picker's choice, applied now (its popup timed out, or another
 * control was used). 1 if it changed anything. */
int fm1_mod_ui_commit(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u);

/* The gesture: a cable from output 1 of the module at src_pos to d, its
 * amount moved by delta percent (a new cable starts at 0). Says what it
 * did. 1 if a slot changed. */
int fm1_mod_ui_route(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, unsigned src_pos,
                     const fm1_mod_dest_t *d, int delta, fm1_mod_ui_say_t *say);

/* CHAIN's lines (each at most 19 characters): the longest path through
 * slot i, nodes and cables alternating; *hl the selected cable's line.
 * Returns the count. */
int fm1_mod_ui_chain(const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u, unsigned i,
                     char lines[FM1_MOD_UI_CHAIN_LINES][FM1_MOD_UI_ROW_CHARS + 1], int *hl);

#ifdef __cplusplus
}
#endif

#endif /* FM1_MOD_UI_H_ */
