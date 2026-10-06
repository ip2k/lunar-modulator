/* fm1_seq.h -- the step sequencer core of the open FM-1 firmware
 * (docs/13 §6, stage M1).
 *
 * A C99 rewrite of the sequencer logic of Movy's seq-core
 * (github.com/DimaDake/schwung-movy, engine/crates/seq-core, commit 9190e79,
 * MIT, Copyright (c) 2026 megadake; engines/third_party/movy/). It replays
 * Movy's event stream tick for tick when `limits.compat` is set; without it
 * the deviations D1-D13 of docs/13 §3.3 and D15-D18 of the song
 * (notes/2026-10-06-song-and-scenes.md) are on. engines/seq.md has the
 * design.
 *
 * No heap: the host asks fm1_seq_size() for the bytes one instance needs
 * under a set of limits, provides that memory (8-byte aligned, contents
 * irrelevant), and fm1_seq_create() builds the instance inside it. Every pool
 * is a fixed slice of that block. The instance holds no pointers, so its size
 * is the same on 32- and 64-bit builds.
 *
 * Threads: everything runs on the audio task. The UI queues fm1_seq_cmd_t
 * records and the audio task applies them at the start of a block, as Movy
 * applies its `cmd` batches between blocks.
 *
 * MIT licence, like the rest of this repository.
 */
#ifndef FM1_SEQ_H_
#define FM1_SEQ_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The grid, as Movy's lib.rs: 96 PPQN, 1/16 steps, 4/4 bars. */
#define FM1_SEQ_PPQN 96u
#define FM1_SEQ_TICKS_PER_STEP 24u
#define FM1_SEQ_STEPS_PER_BAR 16u
#define FM1_SEQ_TICKS_PER_BAR 384u
#define FM1_SEQ_MAX_STEPS 256u              /* 16 bars per clip */
#define FM1_SEQ_MAX_TRACKS 16u
#define FM1_SEQ_SLOTS 8u                    /* clip slots per track */
#define FM1_SEQ_LANES 8u                    /* lock lanes per track */
#define FM1_SEQ_LABEL_MAX 24u               /* lane label bytes, NUL included */
#define FM1_SEQ_CHORD_MAX 12u               /* pitches in one `tog` */
#define FM1_SEQ_CMD_ARGS (2u + 2u * FM1_SEQ_CHORD_MAX)
#define FM1_SEQ_BPM_X100_MIN 2000u
#define FM1_SEQ_BPM_X100_MAX 30000u
#define FM1_SEQ_LOCK_CC 102u                /* Movy sends lane L as CC 102+L */
#define FM1_SEQ_NONE 0xFFu                  /* no slot, no track, no pitch */

/* Lock and lane-base values. Movy's are 7-bit (0..127). They stay 7-bit for
 * now, behind this one typedef, so widening them later (to 14 bits, say) is a
 * change of type and of FM1_SEQ_VAL_MAX, plus the `movy1` value range. */
typedef uint8_t fm1_seq_val_t;
#define FM1_SEQ_VAL_MAX 127u

/* Sizes of everything that has no fixed bound in Movy (docs/13 §5, D7). */
typedef struct fm1_seq_limits {
  uint8_t tracks;        /* 1..16; the FM-1 build uses 4..8 */
  uint8_t compat;        /* FM1_SEQ_COMPAT_*: 0 the FM-1 default, deviations
                            D1-D13, D15-D18 on; 1 Movy 9190e79's behaviour exactly, for
                            tests; 2 the same with D1's frames, to compare with
                            Movy run one frame at a time */
  uint8_t gates;         /* sounding sequenced notes; D7 frees the oldest */
  uint8_t song;          /* song presses (Movy's flat list; SG3: 64) */
  uint8_t rec_notes;     /* notes held while recording, and their tails */
  uint8_t pad_mutes;     /* muted drum voices per track */
  uint16_t notes;        /* the global note pool, shared by all clips */
  uint16_t locks;        /* the global lock pool */
  uint16_t trigs;        /* the global pool of trig condition/probability rows */
  uint16_t clip_notes;   /* per-clip caps, Movy's: 512 notes, */
  uint16_t clip_locks;   /*   1,024 locks */
  uint16_t clip_trigs;   /*   and 1,024 trig rows */
  uint16_t capture;      /* Capture (retroactive record) ring, in events of
                            12 bytes; 0 leaves Capture out and its bytes
                            with it */
} fm1_seq_limits_t;

enum {
  FM1_SEQ_COMPAT_OFF = 0,          /* the FM-1 default */
  FM1_SEQ_COMPAT_MOVY = 1,         /* Movy exactly: every event at its block's start */
  FM1_SEQ_COMPAT_MOVY_FRAMES = 2   /* Movy exactly, but each tick at its own frame */
};

/* Fills *lim with the FM-1 defaults for `tracks` tracks: 192 notes, 192 locks
 * and 32 trig rows per track in the global pools, 64 gates, 64 song entries,
 * 16 recording notes, 16 pad mutes per track, Movy's per-clip caps, a
 * Capture ring of 256 events (3,072 bytes; the owner's choice, 2026-10-01),
 * compat off. */
void fm1_seq_limits_default(fm1_seq_limits_t *lim, uint8_t tracks);

typedef struct fm1_seq fm1_seq_t;

/* Output events. The order within a block is emission order: at one frame,
 * note-offs, then locks of a step that starts there (D2), then note-ons. */
enum {
  FM1_SEQ_EV_NOTE_ON = 1,   /* a = pitch, b = velocity */
  FM1_SEQ_EV_NOTE_OFF = 2,  /* a = pitch */
  FM1_SEQ_EV_LOCK = 3,      /* a = lane 0..7, b = value; Movy's CC 102+lane */
  FM1_SEQ_EV_CLICK = 4,     /* metronome; a = 1 on the downbeat */
  FM1_SEQ_EV_START = 5,     /* MIDI realtime FA */
  FM1_SEQ_EV_STOP = 6,      /* FC */
  FM1_SEQ_EV_CLOCK = 7      /* F8, 24 PPQN */
};

typedef struct fm1_seq_ev {
  uint32_t tick;            /* the master tick being serviced (logs, tests) */
  uint16_t frame;           /* offset in the block: the tick's own sample (D1);
                               0 in compat mode, where Movy has no offsets */
  uint8_t kind;
  uint8_t track;            /* 0-based; FM1_SEQ_NONE for transport and clicks */
  uint8_t a;
  fm1_seq_val_t b;
} fm1_seq_ev_t;

/* One Movy `cmd` op as a typed record: the verb and its integer arguments as
 * Movy's command.rs parses them (i64, a token that does not parse is absent).
 * fm1_seq_parse() builds one from text; a UI builds them directly. */
enum {
  FM1_SEQ_V_UNKNOWN = 0,
  FM1_SEQ_V_PLAY, FM1_SEQ_V_STOP, FM1_SEQ_V_LINK, FM1_SEQ_V_MINJECT, FM1_SEQ_V_BPM,
  FM1_SEQ_V_SWING, FM1_SEQ_V_WATCH, FM1_SEQ_V_WLANE, FM1_SEQ_V_TDRUM, FM1_SEQ_V_MUTE,
  FM1_SEQ_V_PMUTE, FM1_SEQ_V_PSOLO, FM1_SEQ_V_TOG, FM1_SEQ_V_EVEL, FM1_SEQ_V_ELEN,
  FM1_SEQ_V_ENUDGE, FM1_SEQ_V_ETRN, FM1_SEQ_V_HOLD, FM1_SEQ_V_SLEN, FM1_SEQ_V_CLEN,
  FM1_SEQ_V_CSCL, FM1_SEQ_V_CTR, FM1_SEQ_V_EPROB, FM1_SEQ_V_ECOND, FM1_SEQ_V_EINV,
  FM1_SEQ_V_REC, FM1_SEQ_V_CAP, FM1_SEQ_V_CAPCLR, FM1_SEQ_V_CAPSEL, FM1_SEQ_V_CAPDONE,
  FM1_SEQ_V_METRO, FM1_SEQ_V_CQ, FM1_SEQ_V_DQ, FM1_SEQ_V_NON, FM1_SEQ_V_NOF,
  FM1_SEQ_V_DEL, FM1_SEQ_V_CLIPDUP, FM1_SEQ_V_CLIPDEL, FM1_SEQ_V_CLIPSEL,
  FM1_SEQ_V_LAUNCH, FM1_SEQ_V_SONG, FM1_SEQ_V_SONGADD, FM1_SEQ_V_STOPTRK,
  FM1_SEQ_V_CLIPCOPY, FM1_SEQ_V_CLIPPASTE, FM1_SEQ_V_CLIPDELAT, FM1_SEQ_V_CPY,
  FM1_SEQ_V_PST, FM1_SEQ_V_CPYCLR, FM1_SEQ_V_ADDP, FM1_SEQ_V_LOOP, FM1_SEQ_V_DBL,
  FM1_SEQ_V_LTOG, FM1_SEQ_V_ALABEL, FM1_SEQ_V_ABASE, FM1_SEQ_V_ABASEQ, FM1_SEQ_V_ASET,
  FM1_SEQ_V_ACLR, FM1_SEQ_V_ACLRS, FM1_SEQ_V_ACLRSTEP, FM1_SEQ_V_ASETR,
  FM1_SEQ_V_USNAP, FM1_SEQ_V_USWAP, FM1_SEQ_V_UCOMMIT, FM1_SEQ_V_UDROP, FM1_SEQ_V_UCLR,
  FM1_SEQ_V_ROUTE,          /* FM-1 only: route <track> <0 midi|1 engine> <channel|slot> */
  /* FM-1 only, the song on whole entries (notes/2026-10-06-song-and-scenes.md
   * §5.5; engines/seq.md, "The song"). An entry is a run of equal scene
   * presses; indices are 0-based. Movy ignores these verbs. */
  FM1_SEQ_V_SGINS,          /* sgins <entry> <scene> [presses]: insert before the entry
                               (entry = the count appends); creates a song, launching nothing */
  FM1_SEQ_V_SGDEL,          /* sgdel <entry> */
  FM1_SEQ_V_SGSET,          /* sgset <entry> <scene> <presses> */
  FM1_SEQ_V_SGMOV,          /* sgmov <entry> <places>: move it, negative for earlier */
  FM1_SEQ_V_SGCLR,          /* sgclr: clear the list, launching nothing */
  FM1_SEQ_V_SGEND,          /* sgend <FM1_SEQ_SONG_*>: what happens after the last entry */
  FM1_SEQ_V_SGJUMP,         /* sgjump <entry>: playing, it falls in on the next bar,
                               relaunched; stopped, the next play starts there */
  FM1_SEQ_V_SCENE,          /* scene <slot>: launch a scene by hand; the song is
                               detached (D16), or cleared in compat mode (Movy) */
  FM1_SEQ_V_SGNEW,          /* sgnew <slot>: the song becomes [slot], followed from that
                               scene playing or queued, with no relaunch */
  FM1_SEQ_V_SGNAME,         /* sgname <slot> <k>: scene name k of fm1_seq_scene_name_pick
                               (1..FM1_SEQ_SCENE_PICKS), 0 for none */
  FM1_SEQ_V_COUNT
};

/* What the song does after its last entry (sgend; the `movy1` line `se`). */
enum {
  FM1_SEQ_SONG_LOOP = 0,    /* back to the first entry: Movy's only behaviour */
  FM1_SEQ_SONG_PARK = 1,    /* every track stops on the bar after it; the transport runs */
  FM1_SEQ_SONG_STOP = 2     /* the transport stops on the bar after it (D6's reverts and all) */
};

#define FM1_SEQ_SCENES FM1_SEQ_SLOTS    /* a scene is a column of slots */
#define FM1_SEQ_SCENE_NAME_MAX 6u       /* characters of a scene name (SG6) */
#define FM1_SEQ_SCENE_PICKS 10u         /* names the panel picks from */

typedef struct fm1_seq_cmd {
  uint16_t verb;            /* FM1_SEQ_V_* */
  uint8_t argc;             /* tokens after the verb, at most FM1_SEQ_CMD_ARGS */
  uint8_t reserved;
  uint32_t valid;           /* bit i set: arg[i] parsed as an integer */
  int64_t arg[FM1_SEQ_CMD_ARGS];
  char text[FM1_SEQ_LABEL_MAX]; /* `alabel`: its third token, the label */
} fm1_seq_cmd_t;

/* Lane routing (docs/13 §10, answer 2): a track drives a sound engine slot,
 * or goes out on a USB-MIDI channel. The sequencer stores the choice and the
 * host acts on it; events are the same either way. */
enum { FM1_SEQ_ROUTE_MIDI = 0, FM1_SEQ_ROUTE_ENGINE = 1 };

/* Bytes one instance needs under *lim, or 0 if the limits are out of range. */
size_t fm1_seq_size(const fm1_seq_limits_t *lim);

/* Builds an instance in mem (fm1_seq_size(lim) bytes, 8-byte aligned). Tempo
 * 120.00 BPM, stopped, every clip empty. NULL on bad limits or alignment. */
fm1_seq_t *fm1_seq_create(void *mem, const fm1_seq_limits_t *lim, uint32_t sample_rate);

/* The smallest event buffer that keeps every note-off, Start and Stop: one
 * slot per gate and a few more. A call's events beyond its buffer are
 * dropped and counted (fm1_seq_stats_t.dropped_events), but room is always
 * kept for the note-off of every sounding note: a note-on that does not fit
 * is dropped whole, a lock that does not fit goes out at a later step, a
 * clock tick or click is lost. */
static inline uint32_t fm1_seq_min_events(const fm1_seq_limits_t *lim) {
  return (uint32_t)lim->gates + 8u;
}

/* Runs one audio block of `frames` frames and writes its events to out[].
 * Returns the number written (see fm1_seq_min_events for a full buffer). */
uint32_t fm1_seq_advance(fm1_seq_t *s, uint32_t frames, fm1_seq_ev_t *out, uint32_t cap);

/* Applies one command at the start of the next block (frame 0). Returns the
 * events it caused (note-offs of a stop, an auditioned lock...). */
uint32_t fm1_seq_apply(fm1_seq_t *s, const fm1_seq_cmd_t *c, fm1_seq_ev_t *out, uint32_t cap);

/* Parses one op ("tog 0 4 60 100"). Returns 0 for an empty op, else 1; an
 * unknown verb parses to FM1_SEQ_V_UNKNOWN, which Movy also accepts and
 * ignores. */
int fm1_seq_parse(const char *op, size_t len, fm1_seq_cmd_t *c);

/* Movy's apply_batch: ops separated by ';', an optional leading "#<seq>;" tag
 * that suppresses a resent batch. */
uint32_t fm1_seq_apply_text(fm1_seq_t *s, const char *batch, size_t len,
                            fm1_seq_ev_t *out, uint32_t cap);

/* Live input for recording and Capture (Movy's `non`/`nof`), velocity 0 for
 * a note-off. `frame` is the offset in the coming block. */
void fm1_seq_note_in(fm1_seq_t *s, uint16_t frame, uint8_t track, uint8_t pitch, uint8_t vel);

/* External MIDI realtime: 0xF8 clock, 0xFA start, 0xFB continue, 0xFC stop.
 * Returns the events it caused (a stop's note-offs). */
uint32_t fm1_seq_realtime_in(fm1_seq_t *s, uint16_t frame, uint8_t status,
                             fm1_seq_ev_t *out, uint32_t cap);

/* The set as Movy's `movy1` text. Returns the length of the whole text; it is
 * written (NUL-terminated) only if that is less than cap. */
size_t fm1_seq_export_movy1(const fm1_seq_t *s, char *buf, size_t cap);

/* Replaces the set from `movy1` text, as Movy's persist::load. Returns 1 if
 * the format tag matched, 0 otherwise (nothing changed). Outside compat
 * mode it also reads the FM-1 lines dq, se and sn and reseeds the RNG
 * (ST11); seq_persist.c has the format. It is fm1_seq_import_begin, one
 * _feed and _end. */
int fm1_seq_import_movy1(fm1_seq_t *s, const char *txt, size_t len);

/* The same import in pieces (the state files' item stream: a set inside a
 * JSON project, a binary set decoded 64 bytes at a time, a SysEx page, a
 * flash read): begin, feed the text in pieces of any size, end. The result
 * is the same set as one fm1_seq_import_movy1 of the whole text, and no line
 * is held: the import keeps sizeof(fm1_seq_import_t) bytes, whatever the
 * line's length. The set is left untouched until the first line has proved
 * to be the tag; _feed returns 0 once it has not (feeding more is then
 * harmless), _end returns 1 if the set was replaced. Its members are the
 * reader's own. */
typedef struct fm1_seq_num {
  uint64_t v;
  uint32_t n;
  uint8_t sign, digits, bad, over;
} fm1_seq_num_t;

typedef struct fm1_seq_import {
  fm1_seq_t *s;
  fm1_seq_num_t num;          /* the word or list field being read */
  uint64_t lv[6];             /* the line's values */
  uint64_t fv[6];             /* a list item's fields */
  uint8_t fok[6];
  uint8_t state, tag, in_word, key, dead, ok_list;
  uint8_t words, wi, keylen, nf, n_tk, text_n;
  uint16_t clip;
  char keybuf[8];
  char text[8];               /* a scene name's first characters */
} fm1_seq_import_t;

void fm1_seq_import_begin(fm1_seq_import_t *im, fm1_seq_t *s);
int fm1_seq_import_feed(fm1_seq_import_t *im, const char *txt, size_t len);
int fm1_seq_import_end(fm1_seq_import_t *im);

/* ---- Reading state (the UI, tests) ------------------------------------- */

typedef struct fm1_seq_info {
  uint64_t master_tick;
  uint32_t bpm_x100;
  uint16_t swing_pct;
  uint8_t playing, recording, counting_in, metronome;
  uint8_t link, following, watch_track, compat;
  uint8_t song_len, song_pos, default_quant, tracks;
  uint8_t song[256];        /* the first song_len entries */
  uint32_t capture_gen;     /* Capture: bumped on every commit or selection */
  uint16_t capture_pending; /* note-ons buffered for the watched track */
  uint8_t capture_mode;     /* 0 none, 1 tempo selector, 2 fitted to the tempo */
  uint8_t capture_n, capture_sel;
  uint16_t capture_cands[3];  /* candidate tempos, BPM, ascending */
  uint8_t rec_track;        /* the track `rec` armed last: the one recording or
                               counting in while either flag is set */
  /* The song as the Song page reads it (song_pos above is the raw index of
   * the playing entry's first press; song_len when parked at the end). */
  uint8_t song_entries;     /* entries: runs of equal presses */
  uint8_t song_entry;       /* the playing entry; song_entries when parked at the end */
  uint8_t song_armed;       /* the playing entry's last bar: what follows is queued */
  uint8_t song_pass;        /* the playing entry's pass, from 1; 0 before it starts */
  uint8_t song_pass_bar;    /* bars into that pass, from 1; 0 before it starts */
  uint8_t song_end;         /* FM1_SEQ_SONG_* */
  uint8_t song_jump;        /* the entry the next play starts at; FM1_SEQ_NONE: the first */
  uint8_t song_follow;      /* 0: detached (D16), the list kept and not followed */
  uint8_t song_parked;      /* playing, followed and parked: at an empty scene (Movy's
                               END) or after the last entry in Park mode */
} fm1_seq_info_t;

typedef struct fm1_seq_track_info {
  uint32_t cycle;
  uint16_t pos_tick;
  int16_t last_auto_step;
  int16_t auto_cur[FM1_SEQ_LANES];        /* -1: nothing sent since start */
  fm1_seq_val_t base[FM1_SEQ_LANES];
  uint8_t lanes_assigned;                 /* bit per lane */
  uint8_t active, playing, queued, pending_select;  /* FM1_SEQ_NONE: none */
  uint8_t pending_stop, muted, drum, pad_solo;
  uint8_t route_kind, route_index;        /* FM1_SEQ_ROUTE_*, channel or slot */
} fm1_seq_track_info_t;

typedef struct fm1_seq_clip_info {
  uint16_t length_steps;                  /* 0: no clip in this slot */
  uint8_t loop_start, scale_num, scale_den, quant;
  int8_t transpose;
  uint16_t notes, locks, trigs;
} fm1_seq_clip_info_t;

typedef struct fm1_seq_note_info {
  uint16_t tick, gate, step;
  uint8_t pitch, vel, suppress, fired;
} fm1_seq_note_info_t;

typedef struct fm1_seq_stats {
  uint32_t refused;            /* edits dropped because a pool or cap was full (D7) */
  uint32_t dropped_events;     /* events past the caller's buffer */
  uint32_t gates_evicted;      /* oldest gates freed for new notes (D7) */
  uint32_t movy_faults;        /* inputs on which Movy's code faults: a panic (D5's
                                  nudge) or an overflow only a debug build traps
                                  (`cpy` with s0 > s1). Counted in both modes:
                                  compat replays Movy's release build, panic and
                                  all; the FM-1 default skips the input */
  uint16_t notes_used, locks_used, trigs_used;
} fm1_seq_stats_t;

void fm1_seq_get_info(const fm1_seq_t *s, fm1_seq_info_t *out);

/* One song entry, for the Song page's rows and the song's length. A
 * scene's length is its longest clip rounded up to whole bars, at least one
 * (Movy's); an entry lasts bars x presses. */
typedef struct fm1_seq_song_entry {
  uint16_t start_bar;       /* bars from the song's start to the entry */
  uint8_t scene;            /* 0..7 */
  uint8_t presses;          /* its repeat count */
  uint8_t bars;             /* one pass: the scene's length in bars */
  uint8_t first;            /* raw index of its first press in fm1_seq_info_t.song */
  uint8_t empty;            /* no clip in the scene on any track: Movy's END */
  uint8_t reserved;
} fm1_seq_song_entry_t;

/* Entry e (0-based); 0 past the last, with *out untouched. */
int fm1_seq_song_entry(const fm1_seq_t *s, uint8_t e, fm1_seq_song_entry_t *out);

/* The song's length in bars, every entry once through (the Song page's
 * total: at 116 BPM, 116 bars are 4:00). */
uint32_t fm1_seq_song_bars(const fm1_seq_t *s);

/* A scene's name (SG6; the `movy1` line `sn`): up to
 * FM1_SEQ_SCENE_NAME_MAX printable ASCII characters, "" for none. */
const char *fm1_seq_scene_name(const fm1_seq_t *s, uint8_t scene);

/* The names the panel picks from, k = 1..FM1_SEQ_SCENE_PICKS (Intro, Verse,
 * Pre, Chorus, Drop, Break, Build, Bridge, Fill, Outro); "" otherwise. */
const char *fm1_seq_scene_name_pick(unsigned k);

/* The clock as advance runs it, for a host that places things on its grid
 * (the effects' beats, engine API v3; fm1_seq_host.h). While playing, the
 * next block's frame f (0-based) is where the running sum
 * accum + (f + 1) x inc reaches the next multiple of threshold: master tick
 * T is serviced at the first frame where master_tick + (accum + (f + 1) x
 * inc) / threshold > T, the frame advance gives its events. inc is 0 when
 * ticks are not on this grid (following an external clock, or Movy's
 * compat mode, which puts every event at the block's start). */
typedef struct fm1_seq_clock {
  uint64_t master_tick;     /* ticks serviced since Start */
  uint64_t accum;           /* below threshold between blocks */
  uint64_t threshold;       /* sample rate x 6000 */
  uint64_t inc;             /* per frame: bpm_x100 x 96, or 0 (above) */
  uint32_t bpm_x100;
  uint8_t playing;
  uint8_t reserved[3];
} fm1_seq_clock_t;
void fm1_seq_get_clock(const fm1_seq_t *s, fm1_seq_clock_t *out);
int fm1_seq_get_track(const fm1_seq_t *s, uint8_t track, fm1_seq_track_info_t *out);
const char *fm1_seq_lane_label(const fm1_seq_t *s, uint8_t track, uint8_t lane);
int fm1_seq_get_clip(const fm1_seq_t *s, uint8_t track, uint8_t slot, fm1_seq_clip_info_t *out);
int fm1_seq_get_note(const fm1_seq_t *s, uint8_t track, uint8_t slot, uint16_t i,
                     fm1_seq_note_info_t *out);
void fm1_seq_get_stats(const fm1_seq_t *s, fm1_seq_stats_t *out);

/* One step of a clip as a UI draws it (docs/15 §2.5): what fm1_seq_get_page
 * gathers for a run of steps in one pass over the clip's notes, locks and
 * trig rows, where asking step by step would scan every list per step. */
typedef struct fm1_seq_step_info {
  uint8_t notes;            /* notes anchored on the step, saturating at 255 */
  uint8_t lock_mask;        /* bit per lane with a lock on the step */
  uint8_t trig;             /* FM1_SEQ_TRIG_* */
  uint8_t prob;             /* the whole-step trig row's probability, 0..100;
                               100 without one */
  uint8_t cond_a, cond_b;   /* its condition A:B; 1:1 without one */
  uint8_t reserved[2];
  fm1_seq_val_t lock[FM1_SEQ_LANES];   /* the locked values; 0 off the mask */
} fm1_seq_step_info_t;

enum {
  FM1_SEQ_TRIG_STEP = 1,    /* the step has a whole-step trig row (Movy's lane -1) */
  FM1_SEQ_TRIG_PITCH = 2,   /* ...and/or one for a single pitch */
  FM1_SEQ_TRIG_INV = 4      /* the whole-step row inverts its condition */
};

/* Steps first .. first + n - 1 of a clip, in one pass: out[k] is step
 * first + k (locks and trig rows sit on steps 0..255; a note can anchor on
 * 256, Movy's last half-step of a 16-bar clip). Returns 0
 * for a track or slot out of range, with out[] untouched; else 1. Read only,
 * no allocation: a UI calls it on the audio thread whenever the clip may
 * have changed. */
int fm1_seq_get_page(const fm1_seq_t *s, uint8_t track, uint8_t slot, uint16_t first, uint16_t n,
                     fm1_seq_step_info_t *out);

/* Movy's Clip::effective_at, the steady-state oracle of the lock latch. */
int fm1_seq_effective_at(const fm1_seq_t *s, uint8_t track, uint8_t slot, uint8_t lane,
                         uint16_t step, fm1_seq_val_t base);

int fm1_seq_set_route(fm1_seq_t *s, uint8_t track, uint8_t kind, uint8_t index);

/* The probability RNG is free-running from creation, as Movy's; tests reset
 * it. Outside compat mode a set import reseeds it to its value at creation,
 * so a loaded song plays the same each time (ST11). */
void fm1_seq_rng_seed(fm1_seq_t *s, uint64_t seed);

#ifdef __cplusplus
}
#endif

#endif /* FM1_SEQ_H_ */
