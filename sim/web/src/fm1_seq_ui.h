/* fm1_seq_ui.h -- the sequencer's panel UI on the virtual FM-1 (docs/15 §2.5,
 * §3): the state of SEQ mode and the gesture machine that turns panel edges
 * into typed sequencer commands.
 *
 * Pure: its inputs are panel edges, stamped with the app's frame clock, and
 * a const view of the sequencer (read once per block by fm1_seq_ui_sync, and
 * at an edge where a gesture depends on what a step holds now); its outputs
 * are fm1_seq_cmd_t records, handed one at a time to the caller's emitter
 * (the app's fm1_app_seq_cmd), and the state the screen (fm1_seq_view.h)
 * and the LEDs show. It never writes to the sequencer and keeps no copy of
 * its notes beyond the bits the screen and the LEDs draw, read again
 * whenever the clip may have changed.
 *
 * Stage S3 put PLAY/STOP and a read-only Track view here; S4 adds step
 * entry (docs/15 §5 S4). In SEQ mode:
 *
 *   white keys     the 16 steps of the bar on the keys. A tap toggles the
 *                  step on release (`tog`, with the last chord played, each
 *                  pitch with its velocity, else note 60 at 100: owner
 *                  decision O5). A hold of ceil(0.3 x rate) frames or more
 *                  opens the Step pages and toggles nothing. Hold A (with a
 *                  note) and press B after it: A's length up to B's end
 *                  (`slen`), B again: to B's start. More steps held: the
 *                  edits apply to each.
 *   F#3, A#3       the bar on the keys, back and on (the loop's bars and one
 *                  empty bar after them, as Movy); with steps held, nudge
 *                  them 2 ticks earlier or later (`enudge`), 1 with SHIFT
 *   other black    roles of later stages; inert
 *   SEL            SHIFT, outside FX mode (O2). With no step held, SHIFT +
 *                  white key N is Movy's shortcut N (10: full velocity, the
 *                  rest come with later stages). With steps held, SHIFT
 *                  makes the white keys pitches in the current octave, each
 *                  press adding one to every held step (`addp`; O22, as the
 *                  owner changed it on 2026-10-02: pitches are only added),
 *                  and SHIFT pressed and released with nothing else touched
 *                  clears the held steps' notes (`del`). Held step + SHIFT +
 *                  a knob detent is kept for `aclrs` (stage S8): on the Step
 *                  pages it does nothing.
 *   OCT-, OCT+     with steps held: transpose them a semitone (`etrn`), an
 *                  octave with SHIFT; otherwise the octave, as stock
 *   SELECT         with steps held: Step page 1/2 or 2/2, remembered (O21)
 *   KNOB1..4       with steps held, on Step page 1: VEL (`evel`, 4 per
 *                  detent), LEN (`slen`, Movy's 21 lengths, 1/32 to 16
 *                  bars), PROB (`eprob`, 100 % to 10 %), COND (`econd`, the
 *                  36 A:B pairs up to 8); on page 2: INV (`einv`), and the
 *                  nudge and note as read-outs
 *   PLAY/STOP      `play` or `stop` in every mode; SHIFT + PLAY while
 *                  playing restarts (`play`, D12's Stop and Start)
 *   MIDI IN        with steps held, each note adds its pitch (`addp`);
 *                  otherwise notes from MIDI IN and from the keys outside
 *                  SEQ mode are the chord a tap writes
 *
 * S5 adds record and Capture (docs/15 §5 S5, owner decisions O7-O9):
 *
 *   REC            `rec` on the focused track, in every mode: stopped, a
 *                  bar's count-in; playing on an empty clip, a take from the
 *                  next bar; over notes, an overdub at once; recording or
 *                  counting in, off again. In SEQ mode with the transport
 *                  stopped it acts on release, as Movy's Rec does: a quick
 *                  untouched tap records, and held it is step record (O8)
 *   step record    REC held, stopped, in SEQ mode (Movy's step-rec.ts at
 *                  9190e79): each white key enters its pitch, in the
 *                  current octave, at the record head (`del` on a fresh
 *                  step, `addp`, and `clen` while an empty clip grows to what
 *                  is played), and sounds; keys held together are a chord on
 *                  one step, and the head moves on when the last is let go.
 *                  A#3 (the bar-on key) leaves a rest, or with keys down ties
 *                  the chord into the next step; F#3 steps back, or unties.
 *                  SHIFT + white key moves the head to that step, clearing
 *                  it. MIDI IN notes enter as the keys do. Letting go of REC
 *                  ends it; nothing latches
 *   SHIFT + REC    Capture (O7): `cap` on the focused track, outside FX
 *                  mode. Played, a toast; stopped, the core may open its
 *                  tempo picker (SELECT or KNOB1 send `capsel`) or its fitted
 *                  tempo, held on the screen until any press, which sends
 *                  `capdone` and does nothing else (Movy's overlay)
 *   notes          a note played on the keys outside SEQ mode or at MIDI IN
 *                  that no step takes is live input (fm1_app_seq_note_in),
 *                  for recording and Capture
 *
 * S6 adds tracks, mute and the Set, Clip and Track pages (docs/15 §5 S6,
 * owner decisions O3, O10-O12: 8 tracks, routed to the sound units, a
 * metronome click, no solo):
 *
 *   SEQ + white key 1-8   focuses track 1-8 (`watch t`, which empties
 *                  Capture: a toast says so when it held notes), from any
 *                  mode: SEQ's press opens SEQ mode, and a focus made while
 *                  it is held goes back to the mode it came from on release
 *   C#5, D#5       the previous and next track (MONO, POLY printed)
 *   F#4            MUTE (OP6): a tap mutes or unmutes the focused track
 *                  (`mute t 0|1`); held, white keys 1-8 mute and unmute
 *                  tracks 1-8, lit while they sound. SHIFT changes nothing
 *                  (no solo, O12)
 *   SHIFT + key    2: the Track page, 3: the Clip page, 5, 7, 9: the Set
 *                  page, 6: the metronome (`metro`), 16: the focused clip's
 *                  quantize on to the next of 0, the default, 100 (`cq`),
 *                  as Movy's step-shortcuts.ts; their legend fills the grid
 *                  while SHIFT is held
 *   the pages      KNOB1-4 on the Set page: TEMPO (`bpm`, 1 BPM a detent,
 *                  0.1 with SHIFT), SWING (50-80 %), DEF QUANT (`dq`, Movy's
 *                  0-100 % list), METRO; on the Clip page: SPEED (`cscl`,
 *                  1/8X to 4X), LENGTH (`clen`, 1-256 steps), TRANSPOSE
 *                  (`ctr`, +-36), QUANT (`cq`); on the Track page: ROUTE
 *                  (a sound unit or MIDI out), SOUND 1-4 or CHANNEL 1-16
 *                  (`route`), MUTE; Track page 2 lists the lanes, read only.
 *                  SELECT walks the sound's pages, then Set, Clip, Track
 *                  1/2 and 2/2; SEQ goes back to the Track view, and so does
 *                  a step or bar key
 *
 * S8 adds parameter locks from KNOB1-4 (docs/15 §5 S8, owner decision O14:
 * one 7-bit step a detent, the bins for a list; locked values in the
 * parameter's own units; effect slots not lockable yet). A lock targets the
 * sound unit the focused track routes to (the "lock sound", which the app
 * resolves, fm1_seq_ui_sound_t):
 *
 *   lock pages     with one step held, SELECT walks on past Step 2/2 to the
 *                  lock sound's pages. The first turn of a parameter
 *                  without a lane labels one (`alabel t lane synth:<Name>`,
 *                  a space written '_'), sends its base (`abase`, the
 *                  knob's value on the 7-bit grid, which the app snaps the
 *                  knob to: snap), then every turn moves the step's lock a
 *                  step from the lock, else the base (`aset t lane s v 1`,
 *                  quiet: Movy's held-step lock). A NOLOCK parameter says
 *                  so ("<Name>" / "cannot be locked") and a ninth lane
 *                  "8 lanes used". With several steps held the lock pages
 *                  edit the sound, with no lock
 *   SHIFT + detent on a lock page, a step held: `aclrs`, that lane's lock
 *                  on the step
 *   D#4            CLEAR (OP5): with steps held, `aclrstep` for each with a
 *                  lock; held, a knob detent clears that parameter's lane
 *                  (`aclr`, on a lock page or the sound's page); a tap does
 *                  nothing yet (S9 deletes the clip), nor CLEAR + a step
 *   live take      a knob turned on the lock sound's page (HOME or the
 *                  Track view) while the focused track records: `aset t
 *                  lane step v`, heard (Movy's live take, no quiet flag),
 *                  at the playing step; detents add up until 600 ms pass
 *                  without one, Movy's knob release
 * S9+ adds Session and the Song page (notes/2026-10-06-song-and-scenes.md,
 * every decision adopted: SG1-SG13, D15-D18 in the default mode; the core's
 * compat mode keeps Movy's `song`):
 *
 *   SEQ tap        inside SEQ mode, released with no track focused: the
 *                  Track view and Session swap; any other view goes to the
 *                  Track view
 *   Session        white keys 1-8 the focused track's slots (`launch t s`,
 *                  an empty slot stops it), 9-16 focus tracks 1-8; G#3
 *                  (LOOP) held: keys 1-8 are scenes (D16: one press
 *                  `scene s`; a second `sgnew` of the first and `songadd`,
 *                  later ones `songadd`; compat: `song`, then `songadd`);
 *                  C#4 (COPY) held: a slot with a clip `clipcopy`, then
 *                  `clippaste`; D#4 (CLEAR) held + a slot: the confirm
 *   SHIFT + LOOP   the Song page, from the Track view or Session; again,
 *                  back. Its cursor walks the entries and `+ add` (SELECT,
 *                  F#3, A#3; SHIFT + the arrows `sgmov`); white keys 1-8
 *                  insert a scene after it (`sgins`, or `sgset` for a
 *                  repeat of its own scene), 9-16 set its repeats; KNOB1-4
 *                  its scene, repeats, the scene's name (`sgname`) and the
 *                  end (`sgend`); CLEAR `sgdel`, SHIFT + CLEAR the confirm
 *                  for `sgclr`; SHIFT + PLAY `sgjump` (and `play`, stopped)
 *   the confirm    a CLEAR tap in the Track view (`clipdel`), CLEAR + a
 *                  slot (`clipdelat`), SHIFT + CLEAR on the Song page
 *                  (`sgclr`): CLEAR again sends it; any other press only
 *                  closes it, and knob turns are swallowed (O15, SG9)
 *
 * The knob grid and the lanes' bases with no step held are the app's
 * (fm1_app.c): a laned parameter turns on the 7-bit grid and every lane on
 * it, of every track that plays that sound, follows at once (`abaseq`).
 *
 * C99, no heap, no stdio. MIT licence, like the rest of this repository.
 */
#ifndef FM1_SEQ_UI_H_
#define FM1_SEQ_UI_H_

#include <stdint.h>

#include "fm1_engine.h"
#include "fm1_panel.h"
#include "fm1_seq.h"

#ifdef __cplusplus
extern "C" {
#endif

/* What the screen shows in SEQ mode. */
enum {
  FM1_SEQ_VIEW_TRACK = 0,           /* the Track view: grid, knob strip, hint */
  FM1_SEQ_VIEW_STEP = 1,            /* the held steps' Step page (step_page) */
  FM1_SEQ_VIEW_SET = 2,             /* the Set page: tempo, swing, default quantize, metro */
  FM1_SEQ_VIEW_CLIP = 3,            /* the Clip page: speed, length, transpose, quantize */
  FM1_SEQ_VIEW_TRACKPG = 4,         /* the Track page (track_page 0: route and mute;
                                       1: the lanes) */
  FM1_SEQ_VIEW_SESSION = 5,         /* Session (S9): 8 tracks x 8 slots, the scenes, the band */
  FM1_SEQ_VIEW_SONG = 6             /* the Song page (S9+): the song list's editor */
};

/* The CLEAR confirm (O15, SG9): what CLEAR pressed again deletes. */
enum {
  FM1_SEQ_CONFIRM_NONE = 0,
  FM1_SEQ_CONFIRM_CLIP,             /* a CLEAR tap in the Track view: `clipdel t` */
  FM1_SEQ_CONFIRM_SLOT,             /* CLEAR + a slot in Session: `clipdelat t s` */
  FM1_SEQ_CONFIRM_SONG              /* SHIFT + CLEAR on the Song page: `sgclr` */
};
#define FM1_SEQ_UI_SONG_MAX 64u     /* song presses (SG3; the core's limits.song) */
#define FM1_SEQ_UI_SONG_ROWS 7      /* the Song page's entry rows (MID) */
#define FM1_SEQ_UI_TRACK_PAGES 2

/* What the Track view's hint line holds instead of the model line. */
enum { FM1_SEQ_HINT_NONE = 0, FM1_SEQ_HINT_KNOB, FM1_SEQ_HINT_BAR };

/* A one-off message for the app's popup (fm1_seq_ui_t.toast). */
enum {
  FM1_SEQ_TOAST_NONE = 0, FM1_SEQ_TOAST_FULL_VEL_ON, FM1_SEQ_TOAST_FULL_VEL_OFF,
  FM1_SEQ_TOAST_CAPTURED,           /* a Capture wrote its take */
  FM1_SEQ_TOAST_NOTHING,            /* SHIFT + REC with nothing buffered */
  FM1_SEQ_TOAST_TRACK,              /* a track focused (toast_arg); */
  FM1_SEQ_TOAST_TRACK_EMPTIED,      /* ...and Capture's notes went with the `watch` */
  FM1_SEQ_TOAST_METRO_ON, FM1_SEQ_TOAST_METRO_OFF,
  FM1_SEQ_TOAST_QUANT,              /* SHIFT + 16: the clip's quantize, toast_arg % */
  FM1_SEQ_TOAST_LANES_FULL,         /* a ninth lane (S8) */
  FM1_SEQ_TOAST_NOLOCK,             /* the lock sound's parameter toast_arg is NOLOCK */
  FM1_SEQ_TOAST_LOCK_CLEARED,       /* `aclrs`: parameter toast_arg's lock on the step */
  FM1_SEQ_TOAST_LANE_CLEARED,       /* `aclr`: parameter toast_arg's lane */
  FM1_SEQ_TOAST_LOCKS_CLEARED,      /* `aclrstep` on the held steps */
  FM1_SEQ_TOAST_SONG_FULL,          /* an edit past FM1_SEQ_UI_SONG_MAX presses (S9+) */
  FM1_SEQ_TOAST_ENTRY_DELETED,      /* CLEAR on the Song page: entry toast_arg (0-based) */
  FM1_SEQ_TOAST_JOINED,             /* an edit joined entry toast_arg with a neighbour;
                                       toast_scene and toast_presses say what it is now */
  FM1_SEQ_TOAST_SONG_CLEARED,       /* the confirm's `sgclr` */
  FM1_SEQ_TOAST_CLIP_DELETED,       /* the confirm's `clipdel` or `clipdelat` */
  FM1_SEQ_TOAST_CLIP_COPIED,        /* COPY + a slot in Session: `clipcopy` */
  FM1_SEQ_TOAST_CLIP_PASTED         /* COPY + another slot: `clippaste` */
};

/* What REC's press did, for its release (fm1_seq_ui_t.rec_role). */
enum {
  FM1_SEQ_UI_REC_NONE = 0,
  FM1_SEQ_UI_REC_SENT,              /* `rec` went at the press */
  FM1_SEQ_UI_REC_STEP,              /* stopped in SEQ mode: step record while held,
                                       `rec` on an untouched quick release */
  FM1_SEQ_UI_REC_CAPTURE            /* SHIFT + REC: Capture */
};

/* Capture's modes, as fm1_seq_info_t.capture_mode has them. */
enum { FM1_SEQ_UI_CAPTURE_NONE = 0, FM1_SEQ_UI_CAPTURE_PICK = 1, FM1_SEQ_UI_CAPTURE_FITTED = 2 };

/* fm1_seq_ui_key's answer for a key that step record took: it enters its
 * pitch, and the app plays the key's note on the sound (only there). */
#define FM1_SEQ_UI_KEY_SOUND 2

#define FM1_SEQ_UI_GRID_STEPS 64u   /* the Track view's grid: 4 bars of 16 */
#define FM1_SEQ_UI_MAX_HELD 16      /* steps held at once: every white key */
#define FM1_SEQ_UI_STEP_PAGES 2     /* Step 1/2 (VEL LEN PROB COND), 2/2 (INV) */
#define FM1_SEQ_UI_KEY_BAR_BACK 1   /* F#3: the previous bar; nudge earlier */
#define FM1_SEQ_UI_KEY_BAR_ON 5     /* A#3: the next bar; nudge later */
#define FM1_SEQ_UI_FULL_VEL_KEY 9   /* SHIFT + white key 10: full velocity */
#define FM1_SEQ_UI_KEY_LOOP 3       /* G#3 (OP2): LOOP; held in Session, the scenes (S9) */
#define FM1_SEQ_UI_KEY_COPY 8       /* C#4 (OP4): COPY; held in Session, slots (S9) */
#define FM1_SEQ_UI_KEY_CLEAR 10     /* D#4 (OP5): CLEAR (S8) */
#define FM1_SEQ_UI_KEY_MUTE 13      /* F#4 (OP6): MUTE */
#define FM1_SEQ_UI_KEY_TRACK_PREV 20   /* C#5 (MONO): the previous track */
#define FM1_SEQ_UI_KEY_TRACK_NEXT 22   /* D#5 (POLY): the next track */
#define FM1_SEQ_UI_SOUNDS 4         /* sound units a track can play (the app's FM1_APP_SOUNDS) */

/* The sound a lock targets: the sound unit the focused track routes to, as
 * the app resolves it (docs/15 §3.16), and whether the knobs turn it now. */
typedef struct fm1_seq_ui_sound {
  const fm1_engine_t *e;            /* NULL: the track plays MIDI out or an empty sound */
  const float *value;               /* its parameters' values: the knobs', which the
                                       lanes' bases follow */
  int current;                      /* it is the current sound: HOME's and the Track
                                       view's knobs turn it */
} fm1_seq_ui_sound_t;

/* A sound's knob pages, and the parameters of one: the first four with that
 * page, in index order (the app's own rule). */
int fm1_seq_ui_pages(const fm1_engine_t *e);
int fm1_seq_ui_page_params(const fm1_engine_t *e, int page, int out[4]);

/* The lane of `track` whose label names parameter `param` of e (the bridge's
 * rule, fm1_seq_lane_param), or -1. */
int fm1_seq_ui_lane_of(const fm1_seq_t *s, unsigned track, const fm1_engine_t *e, int param);

/* The Clip page's SPEED, Movy's SCALE_RATIONALS (src/seq/clip-scale.ts at
 * 9190e79), and the quantize list of the Set and Clip pages (quant.ts). */
#define FM1_SEQ_UI_SPEEDS 8
#define FM1_SEQ_UI_SPEED_1X 4
#define FM1_SEQ_UI_QUANTS 11
extern const uint8_t fm1_seq_ui_speeds[FM1_SEQ_UI_SPEEDS][2];
extern const uint8_t fm1_seq_ui_quants[FM1_SEQ_UI_QUANTS];
/* The speed list's index of num/den (1X off the list), the quantize list's
 * nearest, and Movy's SHIFT + 16 cycle: the next of 0, the default and 100
 * above `pct`, wrapping. */
int fm1_seq_ui_speed_index(unsigned num, unsigned den);
int fm1_seq_ui_quant_index(unsigned pct);
unsigned fm1_seq_ui_next_quant(unsigned pct, unsigned def);

/* Movy's Step page values (src/seq/step-page-vm.ts at 9190e79, MIT,
 * megadake): LEN in ticks (24 a step, 384 a bar), PROB in percent. */
#define FM1_SEQ_UI_LENGTHS 21
#define FM1_SEQ_UI_PROBS 10
#define FM1_SEQ_UI_CONDS 36
extern const uint16_t fm1_seq_ui_length_ticks[FM1_SEQ_UI_LENGTHS];
extern const char *const fm1_seq_ui_length_names[FM1_SEQ_UI_LENGTHS];
extern const uint8_t fm1_seq_ui_probs[FM1_SEQ_UI_PROBS];
/* The index of the nearest length, probability and condition (A:B, B up to
 * 8: 1:1, 1:2, 2:2, 1:3 ...), as Movy's lengthIndexForTicks, probIndexForPct
 * and condIndexFor; an A:B off the list is 0 (1:1). */
int fm1_seq_ui_length_index(uint32_t ticks);
int fm1_seq_ui_prob_index(unsigned pct);
int fm1_seq_ui_cond_index(unsigned a, unsigned b);
void fm1_seq_ui_cond_pair(int index, unsigned *a, unsigned *b);

/* Where commands go: the app's fm1_app_seq_cmd, under its event-room rule.
 * The UI ignores the result; a refusal is counted there. */
typedef struct fm1_seq_ui_emit {
  void *ctx;
  int (*cmd)(void *ctx, const fm1_seq_cmd_t *c);
} fm1_seq_ui_emit_t;

/* A step held on a white key, in press order. */
typedef struct fm1_seq_ui_held {
  uint64_t press;                   /* frame of the press */
  uint16_t step;                    /* absolute step, 0..255 */
  uint8_t key;                      /* the white key's key index */
  uint8_t flags;                    /* FM1_SEQ_UI_HELD_* */
  uint8_t reserved[4];
} fm1_seq_ui_held_t;

enum {
  FM1_SEQ_UI_HELD_GESTURED = 1,     /* an edit was made: its release toggles nothing */
  FM1_SEQ_UI_HELD_CO = 2            /* held with another step: it toggles whatever the
                                       hold's length (Movy's multi-step entry) */
};

/* What the first held step holds, for the Step pages and the LEDs. */
typedef struct fm1_seq_ui_hold {
  uint16_t step;
  uint16_t tick, gate;              /* its first note's start and length, in ticks */
  uint8_t notes;                    /* notes anchored on it */
  uint8_t vel, pitch;               /* its first note's */
  uint8_t gate_mixed;               /* its notes differ in length (LEN shows "...") */
  uint8_t prob, cond_a, cond_b, inv;   /* its whole-step trig row, or the defaults */
  uint8_t lock_mask;                /* lanes with a lock on it (S8), */
  fm1_seq_val_t lock[FM1_SEQ_LANES];   /* and their 7-bit values */
} fm1_seq_ui_hold_t;

typedef struct fm1_seq_ui {
  uint8_t view;                     /* FM1_SEQ_VIEW_* */
  uint8_t step_page;                /* the Step page a hold opens on (page memory, O21) */
  uint8_t track;                    /* the focused track, 0-based */
  uint8_t bar;                      /* the bar on the white keys, 0..15 */
  uint8_t bar_min, bar_max;         /* where F#3 and A#3 can take it */
  uint8_t hint;                     /* FM1_SEQ_HINT_* */
  int8_t knob;                      /* KNOB1..4 as 0..3 while its name and value
                                       are on the hint line, else -1 */
  uint64_t hint_until;              /* frame at which the hint line goes back */
  uint32_t rate;                    /* the app's rate, rounded: blinks and holds */
  uint32_t hold_frames;             /* ceil(0.3 x rate): a press this long is a hold */

  /* SHIFT (SEL outside FX mode), full velocity and the remembered chord. */
  uint8_t shift;                    /* SEL is down as SHIFT */
  uint8_t shift_clean;              /* ...and nothing else was touched since */
  uint8_t shift_on_hold;            /* ...and it went down while steps were held */
  uint8_t full_vel;                 /* SHIFT + 10: every step entered at 127 */
  uint8_t toast;                    /* FM1_SEQ_TOAST_*, for the app to show */
  uint8_t chord_n, sounding_n;      /* the chord a tap writes; notes still held */
  uint8_t chord[2 * FM1_SEQ_CHORD_MAX];      /* pitch, velocity pairs */
  uint8_t sounding[2 * FM1_SEQ_CHORD_MAX];

  /* The white and black keys the UI took, and what each press did. */
  uint32_t keys_down;               /* bit per key index */
  uint8_t key_role[FM1_APP_KEYS];   /* FM1_SEQ_UI_ROLE_* (fm1_seq_ui.c) */
  uint8_t held_n;
  uint8_t len_valid, len_at_end;    /* the last hold A + press B, for its toggle */
  uint16_t len_a, len_b;
  fm1_seq_ui_held_t held[FM1_SEQ_UI_MAX_HELD];
  fm1_seq_ui_hold_t hold;           /* read in sync while a step is held */

  /* Read from the core once per block (fm1_seq_ui_sync). */
  uint8_t playing, recording, counting_in, following;
  uint8_t rec_track;
  uint32_t bpm_x100;
  uint8_t slot;                     /* the focused track's active clip slot */
  uint8_t clip_playing;             /* that clip is the one playing */
  uint16_t step;                    /* its playhead, while clip_playing */
  uint16_t loop_start, length;      /* its loop, in steps; length 0: no clip */
  uint16_t grid_first;              /* the grid's first step: the 4 bars round `bar` */
  uint64_t notes;                   /* steps grid_first.. with a note */
  uint64_t trigs;                   /* ...with a trig row (a probability, a
                                       condition or an invert) */

  /* What `notes` was read for: read again when any of it changes. */
  uint32_t notes_gen;
  uint16_t notes_first;
  uint8_t notes_track, notes_slot, notes_valid, hold_valid;

  /* REC (S5): what its press did, and whether anything happened since. */
  uint8_t rec_role;                 /* FM1_SEQ_UI_REC_* */
  uint8_t rec_touched;              /* step record: a key, arrow or note while held */
  uint32_t tap_frames;              /* ceil(0.5 x rate): Movy's Rec tap */
  uint64_t rec_press;               /* frame of REC's press */

  /* Step record (O8), while REC is held. Movy's step-rec.ts and
   * step-rec-head.ts: the head, whether the clip grows to what is played
   * (it was empty) or the head wraps, and the chord under the fingers. */
  uint8_t srec;                     /* active */
  uint8_t srec_grow;                /* the clip was empty when REC went down */
  uint8_t srec_fresh;               /* nothing written at the head since it arrived */
  uint8_t srec_open;                /* a chord is open: keys or notes are down */
  uint8_t srec_chord_n, srec_midi_n;
  uint16_t srec_head;               /* the step the next note goes to */
  uint16_t srec_grown;              /* grow mode: the steps played into so far */
  uint16_t srec_anchor, srec_tie;   /* the open chord's step, and its tie */
  uint32_t srec_keys;               /* keys down as pitches, bit per key index */
  uint8_t srec_chord[FM1_SEQ_CHORD_MAX];   /* the open chord's pitches */
  uint8_t srec_midi[16];            /* MIDI IN notes down */

  /* Capture (O7), read from the core once per block. */
  uint16_t capture_pending;         /* note-ons buffered for the watched track */
  uint8_t capture_mode;             /* FM1_SEQ_UI_CAPTURE_*: the overlay */
  uint8_t capture_n, capture_sel;   /* the picker's candidates and the one taken */
  uint8_t cap_sent;                 /* a `cap` went: the next sync says what it did */
  uint16_t capture_cands[3];        /* candidate tempos, BPM, ascending */
  uint32_t capture_gen, cap_gen_sent;

  /* Tracks, mute and the pages (S6). The set's and the focused track's
   * settings are read once per block, and moved at once by the commands
   * the pages send, so a second detent before the next block counts. */
  uint8_t tracks;                   /* the instance's track count */
  uint8_t track_page;               /* the Track page shown (page memory, O21) */
  uint8_t seq_held, seq_gestured;   /* SEQ is down; a track was focused while it was */
  uint8_t mute_held, mute_gestured; /* MUTE is down; the mute map was used */
  uint8_t follow;                   /* the focused track or its route changed here:
                                       the app makes its sound current */
  uint8_t toast_arg;                /* the toast's number: a track, a quantize */
  uint16_t muted;                   /* bit per track */
  uint16_t swing;                   /* the set's swing, 50..80 % */
  uint8_t dq, metro;                /* its default quantize and metronome */
  uint8_t clip_num, clip_den;       /* the focused clip's speed, */
  uint8_t clip_quant;               /* quantize */
  int8_t clip_tr;                   /* and transpose */
  uint8_t route_kind, route_index;  /* the focused track's route (FM1_SEQ_ROUTE_*) */

  /* Locks (S8). */
  uint64_t locks;                   /* steps grid_first.. with a lock */
  uint8_t lanes;                    /* the focused track's lanes in use, bit per lane */
  uint8_t lock_pages;               /* the lock sound's knob pages (fm1_seq_ui_lock_pages) */
  uint8_t clear_held;               /* CLEAR (D#4) is down */
  int8_t snap;                      /* a lane was made on this parameter of the lock
                                       sound: the app puts the knob on the 7-bit grid
                                       (-1: none) */
  int8_t take_param;                /* a live take's parameter of the lock sound, -1 none */
  uint8_t take_lane, take_v;        /* its lane and its 7-bit value */
  uint32_t take_idle;               /* ceil(0.6 x rate): a pause this long ends the take */
  uint64_t take_frame;              /* its last detent */

  /* Session and the song (S9+; notes/2026-10-06-song-and-scenes.md). The
   * slots, the song and the scene names are read once per block. From
   * sess_clips to song_gen, a run with no padding: sync compares it whole. */
  uint64_t sess_clips;              /* bit 8 t + s: slot s of track t holds a clip */
  uint8_t compat;                   /* the core runs Movy's rules (no D16: `song`) */
  uint8_t back_view;                /* the view SHIFT + LOOP goes back to from the Song page */
  uint8_t loop_held;                /* LOOP is down in Session: the scene row */
  uint8_t loop_scenes, loop_first;  /* scene presses in this hold, and its first scene */
  uint8_t copy_held, copied;        /* COPY is down in Session; a slot was copied in this hold */
  uint8_t clear_gestured;           /* CLEAR did something while down: its release asks nothing */
  uint8_t confirm;                  /* FM1_SEQ_CONFIRM_*: up until the next press */
  uint8_t confirm_track, confirm_slot;
  uint8_t blink;                    /* the 0.25 s blink's phase, read in sync */
  uint8_t sess_active[8];           /* each track's active slot (FM1_SEQ_NONE: none) */
  uint8_t sess_play[8];             /* its playing slot, while the transport runs */
  uint8_t sess_queue[8];            /* its queued slot */
  uint8_t sess_pos[8];              /* the playing clip's place, 0..255 of its length */
  uint8_t sess_stop;                /* bit per track: a pending stop */
  uint8_t song_len;                 /* presses (fm1_seq_info_t) */
  uint8_t song_entries, song_entry, song_armed, song_pass, song_pass_bar;
  uint8_t song_end, song_jump, song_follow, song_parked;
  uint8_t song_cur;                 /* the Song page's cursor: an entry, or song_entries
                                       for the `+ add` row */
  uint8_t song_trail;               /* the cursor follows the playing entry */
  uint8_t toast_scene, toast_presses;   /* a Joined toast's entry, as it is now; a
                                           clip toast's slot */
  uint8_t song_scenes;              /* bit per scene the song uses */
  uint8_t song_now, song_next;      /* the playing entry's scene, and the one armed or
                                       due after it (FM1_SEQ_NONE: none, the end) */
  uint8_t song_cur_presses;         /* the cursor's entry's repeats, as last read */
  uint8_t song_pad;                 /* always 0: no padding before song_gen, so the
                                       run sync compares holds no indeterminate byte */
  uint32_t song_gen;                /* the input generation the song was read at */
} fm1_seq_ui_t;

/* Track 1 focused, the Track view, bar 1, Step page 1, no hint, nothing
 * read yet; holds of ceil(0.3 x rate) frames. */
void fm1_seq_ui_init(fm1_seq_ui_t *u, float rate);

/* SEQ pressed: the Track view (from S9 a press inside SEQ mode goes to
 * Session; in S4 it stays). */
void fm1_seq_ui_enter(fm1_seq_ui_t *u);

/* A page of SEQ mode (FM1_SEQ_VIEW_SET, _CLIP or _TRACKPG, as SELECT
 * reaches it past the sound's last page; _SESSION, or _SONG with its cursor
 * on entry `entry`, 0-based, as a saved view opens them: fm1_seq_ui_open_song);
 * any other view is the Track view. Nothing is sent. */
void fm1_seq_ui_open(fm1_seq_ui_t *u, int view);

void fm1_seq_ui_open_song(fm1_seq_ui_t *u, unsigned entry);

/* SEQ tapped inside SEQ mode (pressed and let go with no track focused while
 * it was down): the Track view goes to Session, any other view to the Track
 * view. */
void fm1_seq_ui_seq_tap(fm1_seq_ui_t *u);

/* SEQ mode left (HOME, FX, GLO, a modulation page): the held steps are let
 * go without toggling, and the Track view comes back next time. Keys still
 * down stay the UI's until released, so their releases do nothing. */
void fm1_seq_ui_leave(fm1_seq_ui_t *u);

/* Reads the transport, Capture, the focused track's clip and the held step,
 * once per block, after the sequencer's advance, and opens the Step page for
 * a step held past the threshold at `frame`. `gen` changes whenever the app
 * gave the sequencer input (a line, a command, a reset, an import), so the
 * steps are read again. A `cap` sent since the last call is answered here: a
 * toast, or the core's overlay. Step record ends if the transport runs.
 * Returns FM1_SEQ_UI_SYNC_SEQ when anything SEQ mode's screen or the LEDs
 * show changed, plus FM1_SEQ_UI_SYNC_OVERLAY when Capture's overlay, drawn
 * over every mode, did. */
#define FM1_SEQ_UI_SYNC_SEQ 1
#define FM1_SEQ_UI_SYNC_OVERLAY 2
int fm1_seq_ui_sync(fm1_seq_ui_t *u, const fm1_seq_t *s, uint32_t gen, uint64_t frame);

/* A button edge at `frame` (fm1_app_button_t; down 1 or 0) in panel mode
 * `mode` (fm1_app_mode_t). Returns 1 when the UI took it and the app must
 * not act on it as well: SEL as SHIFT, OCT with steps held, REC, and any
 * press while Capture's overlay is up (it closes the overlay); PLAY/STOP's
 * command is sent here, and the app only keeps its LED. SEQ's edges are
 * noted (seq_held) and left to the app. */
int fm1_seq_ui_button(fm1_seq_ui_t *u, const fm1_seq_t *s, int button, int down, uint64_t frame,
                      int mode, const fm1_seq_ui_emit_t *out);

/* A key edge (0..26): a press in SEQ mode (`mode`), a press in any mode
 * while Capture's overlay is up, or the release of a key the UI took
 * (fm1_seq_ui_has_key). `pitch` is the note the key plays now, for SHIFT's
 * and step record's pitches: 53 + 12 x octave + transpose + key, or with a
 * pad kit as the sound the pad's note (fm1_app.c, key_note), or -1 when the
 * key plays nothing (a pad kit's black key), which enters no pitch. Returns 1 if
 * the UI took it, FM1_SEQ_UI_KEY_SOUND if step record took it and the app
 * plays its note (on the sound only, not as live input); 0 leaves the key to
 * the app, which plays it. */
int fm1_seq_ui_key(fm1_seq_ui_t *u, const fm1_seq_t *s, int key, int down, int velocity,
                   uint64_t frame, int mode, int pitch, const fm1_seq_ui_emit_t *out);
int fm1_seq_ui_has_key(const fm1_seq_ui_t *u, int key);

/* An encoder turned (fm1_app_encoder_t): 1 when the UI took it (in SEQ
 * mode, SELECT and KNOB1..4 with steps held or on the Set, Clip and Track
 * pages; in any mode while Capture's overlay is up: SELECT and KNOB1 move
 * the picker, and over the fitted tempo do nothing, as Movy's jog; the
 * others close it); 0 leaves it to the app. With steps held SELECT walks
 * the Step pages and then the lock pages of `snd` (S8), and a knob on a
 * lock page locks the held step's parameter; with several steps held a lock
 * page's knob is left to the app (0), which turns the sound's parameter on
 * page step_page - FM1_SEQ_UI_STEP_PAGES, unless CLEAR is held: then it
 * clears that parameter's lane, however many steps are held. `snd` may be
 * NULL: no lock sound. */
int fm1_seq_ui_encoder(fm1_seq_ui_t *u, const fm1_seq_t *s, int encoder, int delta,
                       uint64_t frame, int mode, const fm1_seq_ui_sound_t *snd,
                       const fm1_seq_ui_emit_t *out);

/* The lock sound's page count (0: none, so no lock pages), each block and
 * before an encoder: a remembered lock page past it falls back to the last
 * one, or to Step page 2/2. */
void fm1_seq_ui_lock_pages(fm1_seq_ui_t *u, int pages);

/* A detent of a knob on the current sound's page outside the SEQ pages and
 * held steps (HOME, the Track view): `param` its parameter. The UI takes it
 * (1) with CLEAR held (`aclr` of that parameter's lane on the focused track,
 * when the lock sound is the current one) and for a live take while the
 * focused track records and the lock sound is the current one (a lockable
 * parameter: `aset` at the playing step, heard; the lane made first if
 * needed, or "8 lanes used"); otherwise 0, and the app turns the knob. */
int fm1_seq_ui_sound_knob(fm1_seq_ui_t *u, const fm1_seq_t *s, const fm1_seq_ui_sound_t *snd,
                          int param, int delta, uint64_t frame, const fm1_seq_ui_emit_t *out);

/* A note played on the sound, from MIDI IN or from a key outside SEQ mode
 * (velocity 0 releases it). In step record (SEQ mode) it enters its pitch at
 * the head, as a key does (a pitch already down is entered once, and let go
 * at its first release); with steps held in SEQ mode it adds its pitch to
 * them; otherwise it builds the chord a step tap writes: every note held
 * when one goes down. Returns 1 when the note went into the pattern as an
 * edit (step record, a held step), so it is not live input as well. */
int fm1_seq_ui_note(fm1_seq_ui_t *u, int pitch, int velocity, int mode,
                    const fm1_seq_ui_emit_t *out);

/* Every note released at once (a change of sound, the page's panic): none
 * held any more; the chord stays. */
void fm1_seq_ui_notes_off(fm1_seq_ui_t *u);

/* REC's LED at `frame`, when the sequencer is on the panel: on while
 * recording or step recording; fast (0.25 s) during the count-in or while a
 * take waits for its bar; slow (1 s) while Capture holds notes and nothing
 * records (O7); else as the button. */
int fm1_seq_ui_rec_led(const fm1_seq_ui_t *u, uint64_t frame, int held);

/* Step record's head can step back (F#3's LED): a tie to undo, or a step
 * before it. */
int fm1_seq_ui_srec_can_go_back(const fm1_seq_ui_t *u);

/* KNOB1..4 (0..3) turned on the sound in the Track view: its name and value
 * take the hint line until frame `until`. */
void fm1_seq_ui_knob(fm1_seq_ui_t *u, int knob, uint64_t until);

/* The keys' LEDs in SEQ mode at `frame`, bit per key index: white keys show
 * the bar's steps with a note inside the loop, the playhead inverted, held
 * keys lit and the steps under the held step's note blinking slowly; F#3
 * and A#3, MUTE and the track keys are lit while their role is available.
 * With MUTE held, white keys 1-8 are the mute map, lit while their track
 * sounds; with SEQ held, the focused track's key is lit. */
uint32_t fm1_seq_ui_key_leds(const fm1_seq_ui_t *u, uint64_t frame);

/* The steps of the bar on the keys that are held (bit n for white key n). */
uint16_t fm1_seq_ui_held_mask(const fm1_seq_ui_t *u);

/* The steps of that bar under the first held step's note, after it. */
uint16_t fm1_seq_ui_under_mask(const fm1_seq_ui_t *u);

/* A typed command as fm1_seq_parse would read it from text: the verb, argc
 * integer arguments, all valid, and the third token's text kept as the
 * parser keeps it (the label slot of `alabel`), so the command and its
 * formatted text (fm1_seq_cmd_format, engines/host/seq_script.h) round-trip
 * exactly. argc is at most FM1_SEQ_CMD_ARGS. */
void fm1_seq_cmd_make(fm1_seq_cmd_t *c, uint16_t verb, unsigned argc, const int64_t *arg);

#ifdef __cplusplus
}
#endif

#endif /* FM1_SEQ_UI_H_ */
