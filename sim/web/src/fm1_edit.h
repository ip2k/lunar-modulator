/* fm1_edit.h -- the edit layer (notes/2026-10-06-web-editor.md §5, §7, §12,
 * stage ED1): one way into the virtual FM-1's state for the panel's own
 * handlers and the web editor, so both make the same changes, the same
 * change-ring entries and the same --mod lines (one truth).
 *
 * Edits are the state core's records (fm1_state.h's fm1_rec_t: a unit, a
 * MIDI effect's on, a parameter, a level, a rack position's kind, a matrix
 * slot) plus four verbs: swap, move, current and view. fm1_edit_apply runs
 * a record through the same app functions a knob, a picker or the Mix page
 * calls, with their clamps, the LOG law and the RAM rule: a live apply, not
 * a load (nothing is muted, no unit is re-created for a value). A refusal is
 * a code of fm1_refusal.h and changes nothing, except a cable's codes (32
 * and on): those come from the matrix planner about a slot that was written
 * and is on but does not run, as the panel's MATRIX leaves such a cable.
 *
 * The change ring. Every base change the hooks in fm1_app.c see goes into a
 * ring of FM1_EDIT_RING entries, each with its number (gen), its source
 * (who was editing when it happened: the panel's keys, buttons and
 * encoders, the editor, a load, the page's own menus) and the editor's tag.
 * A load is one LOADED entry, not one per value. A reader that falls more
 * than a ring behind is told to resync (fm1_edit_changes), and asks for a
 * snapshot. Values only: a lock playing, a cable moving a parameter and the
 * arpeggiator's notes never enter it (they are telemetry).
 *
 * Telemetry: the block of include/fm1_tele.h, filled for the rows the
 * subscription mask names and nothing else, at most FM1_TELE_HZ times a
 * second of audio (fm1_edit_telemetry returns 0 sooner). Meters and module
 * outputs are gathered as the blocks render, only while subscribed.
 *
 * Packed records. Across the audio thread's port every record and verb is
 * FM1_EDIT_REC_BYTES bytes, little-endian (fm1_edit_pack, fm1_edit_unpack):
 *
 *   0 type, 1 role, 2 sound, 3 slot   (fm1_state.h's FM1_REC_*, FM1_ROLE_*)
 *   PARAM   4-5 uid, 6 focus (0xFF none), 7 value type (FM1_VAL_*), 8-11 bits
 *   UNIT    4-19 engine id, NUL-padded ("" an empty unit)
 *   MODULE  slot: the rack position (0xFF the first empty one); 4-19 kind id
 *   ON      4 on
 *   LEVEL   4-7 percent, float32 bits
 *   CABLE   slot: the matrix slot (0xFF the first empty one); 4 src, 5 via,
 *           6 dst_unit, 7 flags, 8-9 dst, 10-11 amount, 12-13 offset, 14-15 uid
 *   SWAP, MOVE  1-3 the first block (role, sound, slot), 4-6 the second
 *   CURRENT     2 the sound
 *   VIEW        4 mode (FM1_VIEW_*), 6-7 which keys are set, 8-16 the keys
 *   LOADED      (ring only) a load replaced what the editor mirrors
 *
 * C99, no heap, no stdio but snprintf. MIT licence, like the rest of this
 * repository.
 */
#ifndef FM1_EDIT_H_
#define FM1_EDIT_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_app.h"
#include "fm1_mod.h"
#include "fm1_state.h"
#include "fm1_tele.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Who is editing. */
enum {
  FM1_EDIT_HOST = 0,            /* the page's own menus, a harness */
  FM1_EDIT_PANEL = 1,           /* the panel's keys, buttons and encoders */
  FM1_EDIT_EDITOR = 2,          /* the web editor's ops */
  FM1_EDIT_LOAD = 3,            /* a state load */
  FM1_EDIT_SEQ = 4              /* a recorded knob move (none changes a base yet) */
};

/* Verb and ring-only types, after FM1_REC_*. */
enum {
  FM1_EDIT_SWAP = 0x40,         /* two effect slots trade places, cables and all */
  FM1_EDIT_MOVE = 0x41,         /* a block to another place: a rack module moves (its
                                   cables follow); an effect slot, in groups of two, swaps */
  FM1_EDIT_CURRENT = 0x42,      /* the current sound */
  FM1_EDIT_VIEW = 0x43,         /* the page the panel shows (follow): never in history */
  FM1_EDIT_LOADED = 0x50        /* ring only: a load */
};

#define FM1_EDIT_REC_BYTES 24u
#define FM1_EDIT_MAX_RECS 64u         /* records one call applies: a render quantum's */
#define FM1_EDIT_RING 256u            /* change-ring entries */
#define FM1_EDIT_CHANGE_BYTES 32u     /* gen, source, tag, the record */
#define FM1_EDIT_RESYNC 0xFFFFFFFFu   /* fm1_edit_changes: the reader fell behind */
#define FM1_EDIT_ANY 0xFFu            /* MODULE, CABLE slot: the first empty one */
#define FM1_EDIT_VIEW_BYTES 40u       /* fm1_edit_view_pack */

typedef struct fm1_change {
  uint32_t gen;                 /* 1, 2, ... */
  uint8_t src;                  /* FM1_EDIT_HOST ... */
  uint8_t pad_;
  uint16_t tag;                 /* the editor's op number; 0 from anyone else */
  uint8_t rec[FM1_EDIT_REC_BYTES];   /* packed */
} fm1_change_t;

/* A verb, unpacked. */
typedef struct fm1_edit_verb {
  uint8_t verb;                 /* FM1_EDIT_SWAP ... */
  uint8_t role[2], sound[2], slot[2];
  uint8_t mode;                 /* VIEW: FM1_VIEW_* */
  uint16_t has;                 /* VIEW: bit k, key k is set */
  uint8_t v[FM1_VIEW_KEYS];     /* VIEW: the keys, 1-based as a file's */
} fm1_edit_verb_t;

/* What the panel shows, and what each knob turns now (the K1-K4 chips). */
typedef struct fm1_view_knob {
  uint8_t kind;                 /* 0 nothing, 1 a parameter, 2 a sound's level */
  uint8_t role, sound, slot;    /* as a record's */
  uint16_t uid;                 /* kind 1 */
} fm1_view_knob_t;
typedef struct fm1_view {
  uint8_t mode;                 /* FM1_VIEW_* */
  uint8_t sound;                /* the current sound, 0-3 */
  uint8_t page;                 /* 0-based: the page the knobs are on */
  uint8_t slot;                 /* FX: 0 In1, 1 In2, 2 Mix, 3 M1, 4 M2; RACK the position;
                                   MATRIX the slot; else 0 */
  uint8_t arp;                  /* 1: the ARP pages are open (mode stays HOME) */
  fm1_view_knob_t knob[4];
} fm1_view_t;

/* The layer's state. The host owns it (fm1_web.c, the native harness) and
 * attaches it after fm1_app_init; it survives a project load. */
typedef struct fm1_edit {
  uint8_t src;                  /* who is editing now */
  uint8_t depth_;
  uint16_t tag;
  uint32_t gen;                 /* the newest entry's */
  fm1_change_t ring[FM1_EDIT_RING];
  /* The modulation as last seen, so its changes are found whoever made
   * them (the RACK, MATRIX and CHAIN pages, a script line, an engine change
   * re-aiming cables, the editor). */
  uint8_t mod_known;
  int8_t kind[FM1_MOD_POSITIONS];
  fm1_mod_slot_t slot[FM1_MOD_SLOTS];
  uint32_t base[FM1_MOD_POSITIONS][FM1_MOD_MAX_PARAMS];   /* float bits */
  /* Telemetry. */
  uint32_t mask[FM1_TELE_MASK_WORDS];
  uint8_t meters_on, outs_on;
  uint64_t tele_at;             /* a->frames at the last block filled; ~0 none yet */
  float peak[FM1_TELE_POINTS], sq[FM1_TELE_POINTS];
  uint32_t n[FM1_TELE_POINTS];
  float omin[FM1_MOD_POSITIONS][8], omax[FM1_MOD_POSITIONS][8];
  uint8_t out_seen;
  uint32_t gen_rendered;        /* gen at the last block's end: an edit since may
                                   leave the modulation plan to build, which
                                   telemetry must not do early (dests read NaN) */
  /* Counters, for tests and the page's status. */
  uint32_t applied, refused, dropped_;
} fm1_edit_t;

/* Attaches e to a (zeroing it unless `keep`) and records a LOADED entry: a
 * reader starts from a snapshot. NULL detaches. */
void fm1_edit_attach(fm1_app_t *a, fm1_edit_t *e, int keep);

/* Records, from the editor (src EDITOR) or anyone: codes[i] is 0 or the
 * FM1_REFUSE_* code for r[i]. Returns how many were applied (code 0, or a
 * cable's planner code). At most FM1_EDIT_MAX_RECS are read. */
int fm1_edit_apply(fm1_app_t *a, const fm1_rec_t *r, uint32_t n, uint8_t src, uint16_t tag,
                   int8_t *codes);
/* One verb: 0, or an FM1_REFUSE_* code. */
int fm1_edit_verb(fm1_app_t *a, const fm1_edit_verb_t *v, uint8_t src, uint16_t tag);
/* n packed records or verbs (n x FM1_EDIT_REC_BYTES bytes): what the
 * worklet hands over. Returns how many were applied. */
int fm1_edit_packed(fm1_app_t *a, const uint8_t *b, uint32_t n, uint8_t src, uint16_t tag,
                    int8_t *codes);

/* Packing. fm1_edit_unpack: 1 a record (into *r), 2 a verb (into *v), 0 a
 * type this layer does not take. */
int fm1_edit_pack(const fm1_rec_t *r, uint8_t out[FM1_EDIT_REC_BYTES]);
int fm1_edit_unpack(const uint8_t in[FM1_EDIT_REC_BYTES], fm1_rec_t *r, fm1_edit_verb_t *v);
void fm1_edit_verb_pack(const fm1_edit_verb_t *v, uint8_t out[FM1_EDIT_REC_BYTES]);

/* The change feed: entries newer than `gen`, oldest first, at most max;
 * returns how many, or FM1_EDIT_RESYNC when some of them have been
 * overwritten (the reader takes a snapshot and starts from fm1_edit_gen). */
uint32_t fm1_edit_changes(const fm1_app_t *a, uint32_t gen, fm1_change_t *out, uint32_t max);
uint32_t fm1_edit_gen(const fm1_app_t *a);

/* Telemetry. fm1_edit_subscribe sets the mask (FM1_TELE_MASK_WORDS words);
 * fm1_edit_telemetry fills `out` (fm1_tele_floats() floats; max is its
 * room) for the subscribed rows and returns the floats in the block, or 0
 * when no subscription is set, max is short, or less than 1/FM1_TELE_HZ s
 * of audio has passed since the last block (nothing is written then). */
void fm1_edit_subscribe(fm1_app_t *a, const uint32_t *mask);
uint32_t fm1_edit_telemetry(fm1_app_t *a, float *out, uint32_t max);

/* The panel's view, and the same as FM1_EDIT_VIEW_BYTES bytes: mode,
 * sound, page, slot, arp, three pad bytes, then per knob kind, role,
 * sound, slot, uid (2), two pad bytes. */
void fm1_edit_view(const fm1_app_t *a, fm1_view_t *out);
void fm1_edit_view_pack(const fm1_view_t *v, uint8_t out[FM1_EDIT_VIEW_BYTES]);

/* A text form of a record or verb, for scripts, tests and logs:
 *   param ROLE SOUND SLOT UID VALUE [focus=N] [index]
 *   unit ROLE SOUND SLOT ID|-      on SOUND 0|1      level SOUND PERCENT
 *   module POS|any KIND|-          cable SLOT|any SRC VIA DST_UNIT FLAGS DST AMOUNT OFFSET [UID]
 *   swap ROLE SOUND SLOT ROLE SOUND SLOT     move (the same)     current SOUND
 *   view MODE [KEY=V]...  (MODE home|fx|glo|seq|rack|matrix|chain; KEY sound|page|unit|pos|slot)
 * ROLE sound|insert|master|mfx|module; numbers are 0-based but the view's
 * keys, which are a file's (1-based); VALUE a float (or an entry with
 * `index`). fm1_edit_parse_text packs one line: 1, or 0 for a line it
 * cannot read. fm1_edit_rec_text writes a packed record back as a line. */
int fm1_edit_parse_text(const char *line, uint8_t out[FM1_EDIT_REC_BYTES]);
void fm1_edit_rec_text(const uint8_t rec[FM1_EDIT_REC_BYTES], char *buf, size_t cap);

/* The ring, the view and the state's hash (CRC-32 of the whole project as
 * the binary container with no chunk deflated, its view left out) as text:
 * what the parity test compares between the module and the native harness.
 * Returns the length written (NUL included in cap). */
size_t fm1_edit_dump(fm1_app_t *a, char *buf, size_t cap);
uint32_t fm1_edit_state_hash(fm1_app_t *a);

/* A parameter's descriptor by its module's id (an engine, an effect, a MIDI
 * effect, a modulation kind, or "host") and uid, or NULL. */
const fm1_param_t *fm1_edit_find_param(const char *id, uint16_t uid);

/* ---- hooks: called from fm1_app.c and fm1_app_state.c ------------------------- */
/* Who edits from here on; returns what to restore with fm1_edit_leave,
 * which also looks for modulation changes. Both do nothing without a layer. */
int fm1_edit_enter(fm1_app_t *a, uint8_t src);
void fm1_edit_leave(fm1_app_t *a, int was);
void fm1_edit_note_param(fm1_app_t *a, int unit, int index);
void fm1_edit_note_unit(fm1_app_t *a, int unit);
void fm1_edit_note_level(fm1_app_t *a, int sound);
void fm1_edit_note_mfx(fm1_app_t *a, int sound, int param);   /* -1 on, -2 the effect, else a parameter */
void fm1_edit_note_current(fm1_app_t *a);
void fm1_edit_note_swap(fm1_app_t *a, int ua, int ub);
void fm1_edit_note_loaded(fm1_app_t *a);
void fm1_edit_mod_scan(fm1_app_t *a);
/* Telemetry taps on the render path: a meter point's stereo block, and the
 * block's end (module outputs). Read only: the audio is not touched. */
void fm1_edit_meter(fm1_app_t *a, unsigned point, const float *lr, uint32_t n);
void fm1_edit_block_end(fm1_app_t *a);

#ifdef __cplusplus
}
#endif

#endif /* FM1_EDIT_H_ */
