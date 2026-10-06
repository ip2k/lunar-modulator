/* fm1_state.h -- saved state: one record model, two encodings (stage E3;
 * notes/2026-10-06-state-files.md §6-§8, §16).
 *
 * Every saved thing (a project, a sound, an effects chain, a mod rack, a
 * clip, device settings) is a stream of typed records. Readers produce
 * records and writers are fed them, so a conversion goes through the records
 * and is lossless both ways:
 *
 *   JSON (people, links, git, the coming web editor)   state_json_read.c
 *                                                        state_json_write.c
 *   the binary container (the device: flash, SysEx)      state_bin.c
 *
 * Record order. A reader gives records in its source's order; the canonical
 * order is the canonical JSON document's (§7.2: the schemas' member order,
 * parameters by uid, pads in pad order), which is also the binary
 * container's chunk order. The JSON writer accepts any order (it holds the
 * document and writes it canonically); the binary writer wants the canonical
 * order, which a canonical JSON file's reader gives (fm1-state pack goes
 * through `canon` first). The load order (§10) is the applier's business,
 * whatever the order of the records: a pad kit's focus is applied last.
 *
 * Context first (the reader's rules, §7.2). A streaming reader resolves a
 * name only when it knows whose name it is, so a JSON file must give:
 *   R1 `lunar` first (after an optional `$schema`), then `kind`;
 *   R2 a unit's `engine` before its `params` and `pads`;
 *   R3 a module's `pos` and `kind` before its `params` and `data`;
 *   R4 `mod` after the units its cables name (`sounds` and `master`, `sound`,
 *      `chain`), and `rack` before `cables`.
 * A file that breaks one is refused (BAD) with its path; `fm1-state canon`
 * reorders a whole file first and so puts it right. Canonical files keep
 * every rule.
 *
 * Memory. Readers and the record types allocate nothing and recurse
 * nowhere; the JSON reader's state is a fixed struct (fm1_state_json_reader_t,
 * its tokenizer under 256 B), so it fits the firmware. Only the desktop tools
 * and the simulator carry the JSON writer, which holds a document (477 KB
 * of the caller's memory). The binary writer holds its file (96 KiB
 * at most) in the caller's memory too.
 *
 * What the other stages give it (all in, since the stage-E integration,
 * 2026-10-06):
 *   E2: engine API v4's FM1_PARAM_FOCUS and FM1_PARAM_PER_FOCUS flags name a
 *     pad kit's focus and its per-pad values (fm1_state_param_focus), and
 *     get_param reads them back for a save; the names a parameter or a list
 *     entry had before a rename (fm1_known.h's aliases) resolve; an engine
 *     or kind a build lacks is refused with the known-ids reason (`known`
 *     in the report); pattern data reaches a kind's set_data (state_mod.c);
 *     the caps are fm1_state_caps.h's.
 *   E1: the song's movy1 lines `dq`, `se` and `sn` are typed items in the
 *     binary SEQS and CLIP chunks (state_movy1.c), and the sequencer core
 *     imports a set from text in pieces (fm1_seq_import_begin/_feed/_end),
 *     so a binary set reaches it item by item, decoded into pieces of at
 *     most 64 bytes, and no line is ever held whole.
 *   A1 (next): the app's collector and applier; fm1-render's own (host/
 *     render_state.cc) stand in for the desktop.
 *
 * MIT licence, like the rest of this repository.
 */
#ifndef FM1_STATE_H_
#define FM1_STATE_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_engine.h"
#include "fm1_known.h"
#include "fm1_mod.h"
#include "fm1_state_caps.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The format level this build reads and writes ("lunar": "1.0"). */
#define FM1_STATE_MAJOR 1u
#define FM1_STATE_MINOR 0u

/* File kinds: the binary header's codes; JSON spells them. */
enum {
  FM1_STATE_KIND_NONE = 0,
  FM1_STATE_PROJECT = 1,
  FM1_STATE_SOUND = 2,
  FM1_STATE_FX = 3,
  FM1_STATE_MODS = 4,
  FM1_STATE_CLIP = 5,
  FM1_STATE_SETTINGS = 6,
  FM1_STATE_SET = 7,          /* binary only: a .movy1 set as one SEQS chunk */
  FM1_STATE_DX7BANK = 8,      /* reserved: a .syx bank keeps its own format (fm1_dx7.h's
                                 packer and dump writers); the code is held for a
                                 bank in the container */
  FM1_STATE_KINDS = 9
};
/* "project", "sound", ... ; NULL for none. */
const char *fm1_state_kind_name(unsigned kind);
unsigned fm1_state_kind_code(const char *name, size_t n);

/* ---- Caps (§16): the reader refuses past these (TOO_BIG) ------------------
 * The JSON structure caps and the bytes a kind may hold are fm1_state_caps.h's,
 * the table the metadata export carries to editors (its `limits`). */
#define FM1_STATE_DEPTH FM1_STATE_CAP_DEPTH        /* JSON nesting */
#define FM1_STATE_STRING FM1_STATE_CAP_STRING      /* a JSON string, decoded bytes (a movy1 line) */
#define FM1_STATE_KEY FM1_STATE_CAP_KEY            /* a JSON key, bytes */
#define FM1_STATE_NUMBER FM1_STATE_CAP_NUMBER      /* a JSON number, characters */
#define FM1_STATE_MEMBERS FM1_STATE_CAP_MEMBERS    /* members of one object */
#define FM1_STATE_ITEMS FM1_STATE_CAP_ITEMS        /* items of one array */
#define FM1_STATE_BIN_MAX 98304u      /* a binary file (96 KiB) */
#define FM1_STATE_CHUNKS 64u           /* one a unit: a project has up to 30 units */
#define FM1_STATE_PADS FM1_FOCUS_MAX  /* a FOCUS parameter's entries (fm1_engine.h) */
#define FM1_STATE_DATA 8192u          /* pattern data, all modules together */
#define FM1_STATE_DATA_ONE 4096u      /* one module's (hex in JSON: 8,192 characters) */
/* File bytes after inflating, by kind (index: FM1_STATE_*). */
extern const uint32_t fm1_state_kind_cap[FM1_STATE_KINDS];
/* The RAM budget a load is checked against at 44,118 Hz (ST6); mirrors
 * sim/web/src/fm1_app.h's FM1_APP_RAM_BUDGET (a test holds them equal). */
#define FM1_STATE_RAM_BUDGET 387924u
#define FM1_STATE_HZ 44118u

/* ---- Units -------------------------------------------------------------- */
enum {
  FM1_ROLE_NONE = 0,
  FM1_ROLE_SOUND = 1,         /* sound unit `sound` (0-3); a sound file's is 0 */
  FM1_ROLE_INSERT = 2,        /* sound `sound`'s insert `slot` (0-1) */
  FM1_ROLE_MASTER = 3,        /* master slot `slot` (0-1), or an fx file's chain position (0-3) */
  FM1_ROLE_MFX = 4,           /* sound `sound`'s MIDI effect `slot` (0-3) */
  FM1_ROLE_MODULE = 5         /* rack position `slot` (0-7): parameter records only */
};
#define FM1_STATE_MFX 4u              /* MIDI effects a sound's chain holds */
#define FM1_STATE_CHAIN 4u            /* effects an fx file's chain holds */
#define FM1_FOCUS_NONE 0xFFu

/* The cable unit codes a record carries: the modulation runtime's canonical
 * codes (fm1_mod.h: snd1 0, fx1 1, fx2 2, host 3, module 8 + pos, snd2-4
 * 17-19, inserts 20 + 4k + j), plus FM1_STATE_CHAIN3 and _CHAIN4, an fx
 * file's chain positions 3 and 4, which the runtime keeps unnamed. */
#define FM1_STATE_CHAIN3 42u
#define FM1_STATE_CHAIN4 43u

/* ---- Records (§6) ------------------------------------------------------- */
enum {
  FM1_REC_HEAD = 1,           /* kind, major, minor: always first */
  FM1_REC_INFO,               /* key, text (a piece of it) */
  FM1_REC_SESSION,
  FM1_REC_UNIT,               /* a unit: role, sound, slot, engine ("" for none, JSON null) */
  FM1_REC_ON,                 /* a MIDI effect's on (bypass) */
  FM1_REC_PARAM,              /* a unit's or a module's parameter */
  FM1_REC_LEVEL,              /* a sound's level, percent */
  FM1_REC_DX7,                /* an FM6 user voice */
  FM1_REC_MOD,                /* the modulation block begins */
  FM1_REC_SEED,
  FM1_REC_MODULE,             /* a rack position's kind */
  FM1_REC_DATA,               /* a module's pattern data (a piece of it) */
  FM1_REC_CABLE,              /* a matrix slot */
  FM1_REC_LINE,               /* a movy1 line of the set or of a clip (a piece of it) */
  FM1_REC_VIEW,
  FM1_REC_SETTING,
  FM1_REC_END                 /* always last */
};

/* INFO keys, in canonical order. */
enum {
  FM1_INFO_BY = 1, FM1_INFO_VERSION, FM1_INFO_COMMIT,     /* `made` */
  FM1_INFO_NAME, FM1_INFO_TITLE, FM1_INFO_ABOUT, FM1_INFO_AUTHOR, FM1_INFO_LICENCE,
  FM1_INFO_KEYS
};
/* SETTING keys, in canonical order. */
enum {
  FM1_SET_METRONOME = 1, FM1_SET_COUNT_IN_CLICK, FM1_SET_FULL_VELOCITY, FM1_SET_MIDI_IN_CHANNEL,
  FM1_SET_KEYS
};
/* VIEW modes and keys (schema order); values are the JSON's (1-based). */
enum {
  FM1_VIEW_HOME = 0, FM1_VIEW_FX, FM1_VIEW_GLO, FM1_VIEW_SEQ, FM1_VIEW_SESSION, FM1_VIEW_SONG,
  FM1_VIEW_RACK, FM1_VIEW_MATRIX, FM1_VIEW_CHAIN, FM1_VIEW_MODES
};
enum {
  FM1_VK_SOUND = 0, FM1_VK_PAGE, FM1_VK_UNIT, FM1_VK_TRACK, FM1_VK_BAR, FM1_VK_PANEL, FM1_VK_POS,
  FM1_VK_SLOT, FM1_VK_ENTRY, FM1_VIEW_KEYS
};
/* A piece of a text, line or data record. */
#define FM1_REC_FIRST 0x01u
#define FM1_REC_LAST 0x02u
/* PARAM value types. */
#define FM1_VAL_F32 0u                /* bits: a float32 in the parameter's unit */
#define FM1_VAL_INDEX 1u              /* an ENUM entry, 0-based */
/* LINE: which list. */
#define FM1_LINES_SET 0u
#define FM1_LINES_CLIP 1u

typedef struct fm1_rec {
  uint8_t type;               /* FM1_REC_* */
  uint8_t role;               /* UNIT, ON, PARAM: FM1_ROLE_* */
  uint8_t sound;              /* 0-3 */
  uint8_t slot;               /* insert, master/chain, MIDI effect, rack position, matrix
                                 slot, FM6 user slot (0-based) */
  uint8_t piece;              /* INFO, DATA, LINE: FM1_REC_FIRST | FM1_REC_LAST */
  uint8_t pad_[3];
  union {
    struct { uint8_t kind, major, minor; } head;
    struct { uint8_t key; uint16_t n; const char *s; } info;   /* UTF-8, valid during the call */
    struct {
      int8_t current;         /* 0-3 */
      int8_t octave, transpose;
      uint8_t has_key, root;  /* root 0-11 (C .. B) */
      char scale[25];         /* NUL-terminated id */
    } session;
    struct { char id[16]; } unit;   /* UNIT, MODULE: NUL-terminated; "" a null unit */
    uint8_t on;
    struct { uint16_t uid; uint8_t focus, vtype; uint32_t bits; } param;
    uint32_t level;           /* float32 bits, percent */
    struct { uint8_t vced[155]; } dx7;
    uint32_t seed;
    struct { uint8_t version; uint16_t n; const uint8_t *b; } data;
    struct {
      fm1_mod_slot_t s;
      char name[25];          /* the destination parameter's name when the file's
                                 build could not resolve it to a uid (s.dst 0): a mod
                                 rack file names a project's units, whose engines it
                                 does not hold, so the applier resolves it */
    } cable;
    struct { uint8_t which; uint32_t n; const char *s; } line;
    struct { uint8_t mode; uint16_t has; uint8_t v[FM1_VIEW_KEYS]; } view;
    struct { uint8_t key, is_bool; int32_t value; } setting;
  } u;
} fm1_rec_t;

/* A record sink: returns 1 to go on, 0 to stop (the reader then refuses,
 * keeping the code the sink set in the report, or STOPPED). */
typedef int (*fm1_rec_sink_t)(void *ctx, const fm1_rec_t *r);
/* A source: copies up to n bytes from offset off into buf; returns how many
 * (0 at the end). RAM and flash look the same; pass 2 re-reads. */
typedef uint32_t (*fm1_src_read_t)(void *ctx, uint32_t off, uint8_t *buf, uint32_t n);
/* Output, in order. */
typedef void (*fm1_put_t)(void *ctx, const char *bytes, size_t n);

/* ---- Report (§10.3, §12.1) ---------------------------------------------- */
enum {
  FM1_STATE_OK = 0,
  FM1_STATE_NOT_LUNAR,        /* neither the binary magic nor a JSON object that opens with lunar */
  FM1_STATE_TOO_NEW,          /* a higher level than this build reads */
  FM1_STATE_UNKNOWN,          /* an engine or kind not in this build */
  FM1_STATE_RATE,             /* an engine refuses the host's rate */
  FM1_STATE_RAM,              /* over the budget at 44,118 Hz: always refused */
  FM1_STATE_NO_ROOM,          /* a merge needs room that is not free */
  FM1_STATE_TOO_BIG,          /* a cap of §16 */
  FM1_STATE_BAD,              /* not well formed, out of context order, unreadable */
  FM1_STATE_STOPPED,          /* the sink stopped without saying why */
  FM1_STATE_CODES
};
const char *fm1_state_code_name(unsigned code);   /* "OK", "NOT_LUNAR", ... */

typedef struct fm1_state_report {
  uint8_t code;               /* FM1_STATE_* */
  uint8_t kind;               /* the file's kind, once known */
  uint8_t major, minor;       /* its level */
  uint32_t line, col;         /* JSON: where it stopped (1-based); 0 for binary */
  uint32_t offset;            /* byte offset in the source */
  char path[96];              /* JSON path: /sounds/1/params/Cutoff (0-based items) */
  char what[96];              /* why, in a few words */
  char name[32];              /* the engine, kind or member a refusal or skip names */
  char known[12];             /* an unknown engine or kind's known-ids reason ("gpl",
                                 "planned", "retired"), "" when no list names it */
  char near[44];              /* the source's first 40 characters there */
  uint32_t near_at;           /* where `near` starts: the member's key, or the offset */
  uint32_t skipped;           /* members, names and values left out (unknown or unresolvable) */
  uint32_t repaired;          /* values clamped, text stripped or cut */
  uint32_t defaulted;         /* values a writer filled in with their default */
  uint32_t unknown;           /* engines and kinds not in this build (UNKNOWN unless allowed) */
  uint32_t records;           /* records given to the sink */
  uint16_t units, modules, cables, voices, lines;
  char first_skip[96];        /* what the first skip was, for a report line */
} fm1_state_report_t;

void fm1_state_report_init(fm1_state_report_t *rep);

/* ---- Names (§9) ------------------------------------------------------------
 * What a JSON reader resolves names against and a JSON writer writes: the
 * registries of this build. The binary side never needs it. The metadata
 * export (stage E2, fm1-render --meta) is written from the same tables, so
 * a name a file may use is a name an editor offers. NULL members are empty
 * tables: a reader with none resolves `#UID` keys only. */
typedef struct fm1_state_names {
  const fm1_engine_t *const *engines;    /* sounds and audio effects */
  size_t n_engines;
  const fm1_midi_fx_t *const *mfx;
  size_t n_mfx;
  const fm1_mod_kind_t *const *kinds;
  size_t n_kinds;
  const fm1_param_t *host;               /* the host unit's (Pitch, Amp, ...) */
  unsigned n_host;
  const fm1_mod_source_info_t *(*source)(unsigned id);   /* system sources 0-63 */
  const fm1_alias_t *aliases;            /* old names of parameters and entries (fm1_known.h) */
  size_t n_aliases;
  const fm1_known_id_t *(*known)(const char *id);   /* why a build lacks an id, or NULL */
  uint8_t gpl;                           /* FM1_GPL_MODS in this build */
} fm1_state_names_t;

/* The registries linked into this program (state_registry.c). */
void fm1_state_names_default(fm1_state_names_t *nm);

/* Lookups (state_names.c). Engines by role: SOUND -> sound engines, INSERT
 * and MASTER -> audio effects, MFX -> MIDI effects. */
const fm1_engine_t *fm1_state_engine(const fm1_state_names_t *nm, unsigned role, const char *id);
const fm1_mod_kind_t *fm1_state_kind(const fm1_state_names_t *nm, const char *id);
/* A parameter by key: "#UID", the name exactly, without ASCII case, by
 * abbreviation, then by an old name (fm1_known.h's aliases of the owner:
 * `owner_kind` FM1_ALIAS_ENGINE for an engine, effect or MIDI effect,
 * FM1_ALIAS_MOD for a modulation kind, 0 for none) (§7.3). Returns the
 * index, or -1. */
int fm1_state_param_find(const fm1_state_names_t *nm, unsigned owner_kind, const char *owner,
                         const fm1_param_t *p, unsigned n, const char *key, size_t len);
/* A removed parameter's last name (fm1_known.h's FM1_ALIAS_RETIRED rows of
 * the owner, without ASCII case): its retired uid, which a reader passes on
 * as it would "#UID"; 0 for none. */
uint16_t fm1_state_param_retired(const fm1_state_names_t *nm, unsigned owner_kind, const char *owner,
                                 const char *key, size_t len);
/* An entry of an ENUM by name (exactly, then without ASCII case), then by
 * an old name of one (the owner's entry aliases), or -1. */
int fm1_state_entry_find(const fm1_state_names_t *nm, unsigned owner_kind, const char *owner,
                         const fm1_param_t *p, const char *s, size_t len);
/* Whether a parameter is a pad kit's focus (Pad) or a per-pad value: engine
 * API v4's FM1_PARAM_FOCUS and FM1_PARAM_PER_FOCUS. 0 none, 1 focus, 2 per
 * focus. */
int fm1_state_param_focus(const fm1_engine_t *e, unsigned index);
/* A system source by name (VEL ...) or -1; a module port or gate by name or
 * 1-based index (text "2"), or -1. */
int fm1_state_source_find(const fm1_state_names_t *nm, const char *s, size_t len);
/* Counts an engine or kind that a UNIT or MODULE record names and nm lacks
 * in rep (unknown; the first one's id in name and its known-ids reason in
 * known), as the JSON reader counts them; the binary reader resolves no
 * names, so a loader of binary files passes its records through this. */
void fm1_state_note_unknown(const fm1_state_names_t *nm, const fm1_rec_t *r, fm1_state_report_t *rep);
/* A report's `known` reason in words for a refusal ("in the GPL build
 * only", "not built yet", "retired"), or "" for none. */
const char *fm1_state_known_text(const char *reason);
int fm1_state_port_find(const fm1_port_t *ports, unsigned n, const char *s, size_t len);

/* ---- The JSON reader (§7.6) ------------------------------------------------ */
#include "fm1_json.h"

/* One frame of the reader's context stack (a JSON container). */
typedef struct fm1_state_frame {
  uint8_t ctx;                /* what this container is (state_json_read.c) */
  uint8_t member;             /* its member id in its parent object */
  uint8_t index;              /* its place in its parent array */
  uint8_t role, sound, slot;  /* the unit it belongs to */
  uint8_t flags;
  uint8_t items;              /* items begun, in an array (saturates at 255) */
  uint64_t seen;              /* members seen: known ones by place, parameters by index */
  const void *owner;          /* the unit's engine or the module's kind, if this build has it */
} fm1_state_frame_t;

typedef struct fm1_state_json_reader {
  fm1_json_t tok;             /* the tokenizer, < 256 B */
  const fm1_state_names_t *nm;
  fm1_rec_sink_t sink;
  void *sctx;
  fm1_state_report_t *rep;
  fm1_state_frame_t frame[FM1_STATE_DEPTH + 1];
  uint8_t depth;              /* frames in use */
  uint8_t kind;               /* the file's FM1_STATE_* once read */
  uint8_t member;             /* the member the next value belongs to */
  uint8_t pidx;               /* PARAMS: the parameter it names, or 0xFF */
  uint16_t key_uid;           /* PARAMS: the uid it names */
  uint8_t skip;               /* > 0: inside a skipped subtree, at this depth */
  uint8_t skip_str;           /* skipping a string's pieces */
  uint8_t stop;               /* refused */
  uint8_t top;                /* top members read: 0 none, 1 lunar, 2 kind */
  uint32_t seen_top;          /* top members seen (R4) */
  uint32_t dx7_slots;         /* FM6 slots given (duplicates) */
  uint32_t cable_slots;       /* matrix slots given */
  uint8_t rack_pos;           /* rack positions given */
  uint8_t keylen;
  uint8_t sbuf_n;             /* a short string being gathered */
  uint8_t sbuf_over;
  uint32_t textlen;           /* code points of the current text */
  uint32_t data_total;        /* pattern data bytes so far, all modules */
  uint32_t data_one;          /* this module's */
  uint32_t line_n;            /* bytes of the current movy1 line */
  uint32_t key_at;            /* offset of the current member's key */
  uint32_t lines;             /* lines of the current list */
  uint16_t ops_n;             /* FM6 voice: values read */
  uint16_t glob_n;
  uint8_t level_minor;        /* the file's minor level */
  uint8_t text_key;           /* INFO key of the text being read */
  uint8_t hexhalf;            /* a data nibble pending (0x10 | nibble) */
  uint8_t ref_which;          /* 0 from, 1 via */
  uint8_t acc_has;            /* gathered members of the current small object */
  uint8_t ref_has, tgt_has;
  uint8_t cable_bad;          /* the cable cannot be resolved: skip it */
  uint16_t ref_module, ref_port_idx;   /* the ref being read */
  int16_t ref_source;
  uint16_t tgt_module, tgt_unit, tgt_gate_idx;
  char key[FM1_STATE_KEY];    /* the current member's key */
  char sbuf[64];              /* a short string value */
  char ref_port[16];          /* a port or gate by name */
  char tgt_param[32];         /* a target's parameter by name */
  fm1_rec_t acc;              /* the record a small object (session, voice, cable, view) builds */
  const fm1_engine_t *unit_e[16];      /* engines given: sounds, inserts, master/chain */
  const fm1_mod_kind_t *rack_k[8];     /* kinds given, by position */
  uint32_t unk_hash[64];      /* unresolved keys in open objects, for duplicates */
  uint8_t unk_depth[64];
  uint8_t n_unk;
  uint8_t out_n;
  uint8_t piece_out;          /* a piece of the current text or data has gone out */
  uint8_t pad_;
  char out[64];               /* a filtered text piece, or decoded data bytes */
} fm1_state_json_reader_t;

/* Push-feeding: begin, feed pieces of any size (a SysEx page, a flash read,
 * the whole buffer), end. Each returns 1 while all is well, 0 once refused
 * (rep says why). */
int fm1_state_json_begin(fm1_state_json_reader_t *r, const fm1_state_names_t *nm,
                         fm1_rec_sink_t sink, void *sctx, fm1_state_report_t *rep);
int fm1_state_json_feed(fm1_state_json_reader_t *r, const uint8_t *b, size_t n);
int fm1_state_json_end(fm1_state_json_reader_t *r);
/* The same over a source, read in 256-byte pieces. */
int fm1_state_json_read(const fm1_state_names_t *nm, fm1_src_read_t rd, void *rctx,
                        fm1_rec_sink_t sink, void *sctx, fm1_state_report_t *rep);

/* ---- The canonical JSON writer (§7.2; desktop and simulator only) --------- */
typedef struct fm1_state_writer fm1_state_writer_t;
/* Bytes the JSON writer needs (aligned to 16 by the caller). */
size_t fm1_state_json_writer_size(void);
/* `compact`: no white space (a #lunar= link's form). */
fm1_state_writer_t *fm1_state_json_writer(void *mem, const fm1_state_names_t *nm, int compact,
                                          fm1_put_t put, void *ctx, fm1_state_report_t *rep);
/* A sink: fm1_state_write(w, r) returns 1, or 0 when the writer cannot hold
 * the record (TOO_BIG) or it is malformed (BAD). The document is written at
 * FM1_REC_END. */
int fm1_state_write(void *w, const fm1_rec_t *r);

/* ---- The binary container (§8) ------------------------------------------------ */
#define FM1_STATE_BIN_DEFLATE 0x01u   /* writer: deflate a chunk when that saves a quarter */
#define FM1_STATE_WRITER_SIM 1u
#define FM1_STATE_WRITER_FIRMWARE 2u
#define FM1_STATE_WRITER_DESKTOP 3u
size_t fm1_state_bin_writer_size(void);
fm1_state_writer_t *fm1_state_bin_writer(void *mem, unsigned flags, unsigned writer,
                                         const uint8_t version[3], fm1_put_t put, void *ctx,
                                         fm1_state_report_t *rep);
int fm1_state_bin_write(void *w, const fm1_rec_t *r);   /* a sink; the file goes out at END */

/* Reads a binary file from a source; total is its length. A file shorter
 * than its header says, a CRC that does not match, an unknown critical
 * chunk or any length past its cap refuses it before a record is given
 * for that chunk; earlier chunks' records may have gone to the sink, so
 * appliers run pass 1 first (§10.1). `skip_crc` is for the fuzz build only. */
int fm1_state_bin_read(fm1_src_read_t rd, void *rctx, uint32_t total, fm1_rec_sink_t sink,
                       void *sctx, fm1_state_report_t *rep, int skip_crc);

/* Which encoding the bytes start with: 1 binary, 2 JSON (after white
 * space), 3 a movy1 set, 4 DX7 SysEx or a raw bank, 0 none (§11). */
int fm1_state_sniff(const uint8_t *b, size_t n);

/* CRC-32, zlib's (reflected 0xEDB88320), continued from crc (0 to start). */
uint32_t fm1_state_crc32(uint32_t crc, const uint8_t *b, size_t n);

/* ---- Records as text (fm1-state records; tests compare it with P1's) -------- */
/* One JSON object a line, pieces joined; floats as their bits in hex. */
typedef struct fm1_state_printer {
  fm1_put_t put;
  void *ctx;
  uint8_t in_piece;
  uint8_t pad_[3];
} fm1_state_printer_t;
void fm1_state_printer_init(fm1_state_printer_t *p, fm1_put_t put, void *ctx);
int fm1_state_print(void *p, const fm1_rec_t *r);   /* a sink */

/* A record sink that forwards to two (a reader feeding a writer and a printer). */
typedef struct fm1_state_tee {
  fm1_rec_sink_t a, b;
  void *actx, *bctx;
} fm1_state_tee_t;
int fm1_state_tee(void *t, const fm1_rec_t *r);

#ifdef __cplusplus
}
#endif

#endif /* FM1_STATE_H_ */
