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
 * entry (docs/15 §5 S4). In SEQ mode, with the lab switch on:
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
 * C99, no heap, no stdio. MIT licence, like the rest of this repository.
 */
#ifndef FM1_SEQ_UI_H_
#define FM1_SEQ_UI_H_

#include <stdint.h>

#include "fm1_panel.h"
#include "fm1_seq.h"

#ifdef __cplusplus
extern "C" {
#endif

/* What the screen shows in SEQ mode. */
enum {
  FM1_SEQ_VIEW_TRACK = 0,           /* the Track view: grid, knob strip, hint */
  FM1_SEQ_VIEW_STEP = 1             /* the held steps' Step page (step_page) */
};

/* What the Track view's hint line holds instead of the model line. */
enum { FM1_SEQ_HINT_NONE = 0, FM1_SEQ_HINT_KNOB, FM1_SEQ_HINT_BAR };

/* A one-off message for the app's popup (fm1_seq_ui_t.toast). */
enum { FM1_SEQ_TOAST_NONE = 0, FM1_SEQ_TOAST_FULL_VEL_ON, FM1_SEQ_TOAST_FULL_VEL_OFF };

#define FM1_SEQ_UI_GRID_STEPS 64u   /* the Track view's grid: 4 bars of 16 */
#define FM1_SEQ_UI_MAX_HELD 16      /* steps held at once: every white key */
#define FM1_SEQ_UI_STEP_PAGES 2     /* Step 1/2 (VEL LEN PROB COND), 2/2 (INV) */
#define FM1_SEQ_UI_KEY_BAR_BACK 1   /* F#3: the previous bar; nudge earlier */
#define FM1_SEQ_UI_KEY_BAR_ON 5     /* A#3: the next bar; nudge later */
#define FM1_SEQ_UI_FULL_VEL_KEY 9   /* SHIFT + white key 10: full velocity */

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
  uint64_t master_tick;
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
} fm1_seq_ui_t;

/* Track 1 focused, the Track view, bar 1, Step page 1, no hint, nothing
 * read yet; holds of ceil(0.3 x rate) frames. */
void fm1_seq_ui_init(fm1_seq_ui_t *u, float rate);

/* SEQ pressed: the Track view (from S9 a press inside SEQ mode goes to
 * Session; in S4 it stays). */
void fm1_seq_ui_enter(fm1_seq_ui_t *u);

/* SEQ mode left (HOME, FX, GLO, the lab switch off): the held steps are let
 * go without toggling, and the Track view comes back next time. Keys still
 * down stay the UI's until released, so their releases do nothing. */
void fm1_seq_ui_leave(fm1_seq_ui_t *u);

/* Reads the transport, the focused track's clip and the held step, once per
 * block, after the sequencer's advance, and opens the Step page for a step
 * held past the threshold at `frame`. `gen` changes whenever the app gave the
 * sequencer input (a line, a command, a reset, an import), so the steps are
 * read again. Returns 1 when anything the screen or the LEDs show changed. */
int fm1_seq_ui_sync(fm1_seq_ui_t *u, const fm1_seq_t *s, uint32_t gen, uint64_t frame);

/* A button edge at `frame` (fm1_app_button_t; down 1 or 0) in panel mode
 * `mode` (fm1_app_mode_t). Returns 1 when the UI took it and the app must
 * not act on it as well: SEL as SHIFT, OCT with steps held; PLAY/STOP's
 * command is sent here, and the app only keeps its LED. */
int fm1_seq_ui_button(fm1_seq_ui_t *u, const fm1_seq_t *s, int button, int down, uint64_t frame,
                      int mode, const fm1_seq_ui_emit_t *out);

/* A key edge (0..26): a press in SEQ mode (`mode`), or the release of a key
 * the UI took (fm1_seq_ui_has_key). `base_note` is the note key 0 plays now
 * (53 + 12 x octave + transpose), for SHIFT's pitches. Returns 1 if the UI
 * took it; 0 leaves the key to the app, which plays it. */
int fm1_seq_ui_key(fm1_seq_ui_t *u, const fm1_seq_t *s, int key, int down, int velocity,
                   uint64_t frame, int mode, int base_note, const fm1_seq_ui_emit_t *out);
int fm1_seq_ui_has_key(const fm1_seq_ui_t *u, int key);

/* An encoder turned (fm1_app_encoder_t) in SEQ mode: 1 when the UI took it
 * (SELECT and KNOB1..4 with steps held); 0 leaves it to the app. */
int fm1_seq_ui_encoder(fm1_seq_ui_t *u, const fm1_seq_t *s, int encoder, int delta,
                       uint64_t frame, int mode, const fm1_seq_ui_emit_t *out);

/* A note played on the sound, from MIDI IN or from a key outside SEQ mode
 * (velocity 0 releases it). With steps held in SEQ mode it adds its pitch to
 * them; otherwise it builds the chord a step tap writes: every note held
 * when one goes down. */
void fm1_seq_ui_note(fm1_seq_ui_t *u, int pitch, int velocity, int mode,
                     const fm1_seq_ui_emit_t *out);

/* Every note released at once (a change of sound, the page's panic): none
 * held any more; the chord stays. */
void fm1_seq_ui_notes_off(fm1_seq_ui_t *u);

/* KNOB1..4 (0..3) turned on the sound in the Track view: its name and value
 * take the hint line until frame `until`. */
void fm1_seq_ui_knob(fm1_seq_ui_t *u, int knob, uint64_t until);

/* The keys' LEDs in SEQ mode at `frame`, bit per key index: white keys show
 * the bar's steps with a note inside the loop, the playhead inverted, held
 * keys lit and the steps under the held step's note blinking slowly; F#3
 * and A#3 are lit while their role is available. */
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
