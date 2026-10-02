/* fm1_seq_ui.h -- the sequencer's panel UI on the virtual FM-1 (docs/15 §2.5,
 * §3): the state of SEQ mode and the gesture machine that turns panel edges
 * into typed sequencer commands.
 *
 * Pure: its inputs are panel edges, stamped with the app's frame clock, and
 * a const view of the sequencer read once per block (fm1_seq_ui_sync); its
 * outputs are fm1_seq_cmd_t records, which the app sends through
 * fm1_app_seq_cmd, and the state the screen (fm1_seq_view.h) and the LEDs
 * show. It never writes to the sequencer and keeps no copy of its notes
 * beyond the step mask the Track view draws, rebuilt whenever the clip may
 * have changed.
 *
 * Stage S3 has the Track view, read-only: PLAY/STOP and what it shows. Step
 * entry, the Step pages and SHIFT come in S4.
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

/* The views of SEQ mode; S3 has the first. */
enum { FM1_SEQ_VIEW_TRACK = 0 };

#define FM1_SEQ_UI_MAX_CMDS 2       /* the most commands one panel edge emits */
#define FM1_SEQ_UI_GRID_STEPS 64u   /* the Track view's grid: 4 bars of 16 */

typedef struct fm1_seq_ui {
  uint8_t view;                     /* FM1_SEQ_VIEW_* */
  uint8_t track;                    /* the focused track, 0-based */
  uint8_t bar;                      /* the bar on the white keys (0 in S3) */
  int8_t knob;                      /* KNOB1..4 as 0..3 while its name and value
                                       are on the hint line, else -1 */
  uint64_t knob_until;              /* frame at which the hint line goes back */

  /* Read from the core once per block (fm1_seq_ui_sync). */
  uint8_t playing, recording, counting_in, following;
  uint32_t bpm_x100;
  uint64_t master_tick;
  uint8_t slot;                     /* the focused track's active clip slot */
  uint8_t clip_playing;             /* that clip is the one playing */
  uint16_t step;                    /* its playhead, while clip_playing */
  uint16_t loop_start, length;      /* its loop, in steps; length 0: no clip */
  uint64_t notes;                   /* steps 0..63 of that clip with a note */

  /* What `notes` was read for: rebuilt when any of it changes. */
  uint32_t notes_gen;
  uint16_t notes_count;
  uint8_t notes_track, notes_slot, notes_valid;
} fm1_seq_ui_t;

/* Track 1 focused, the Track view, bar 1, no hint, nothing read yet. */
void fm1_seq_ui_init(fm1_seq_ui_t *u);

/* SEQ pressed: the Track view (from S9 a press inside SEQ mode goes to
 * Session; in S3 it stays). */
void fm1_seq_ui_enter(fm1_seq_ui_t *u);

/* Reads the transport and the focused track's clip, once per block, after
 * the sequencer's advance. `gen` changes whenever the app gave the sequencer
 * input (a line, a command, a reset, an import), so the step mask is read
 * again. Returns 1 when anything the Track view or the LEDs show changed. */
int fm1_seq_ui_sync(fm1_seq_ui_t *u, const fm1_seq_t *s, uint32_t gen);

/* A button edge at `frame` (fm1_app_button_t; down 1 or 0) in panel mode
 * `mode` (fm1_app_mode_t). Writes up to FM1_SEQ_UI_MAX_CMDS commands to out
 * and returns how many. S3: PLAY/STOP pressed sends `play` when the
 * transport is stopped and `stop` when it runs, in any mode. */
int fm1_seq_ui_button(fm1_seq_ui_t *u, int button, int down, uint64_t frame, int mode,
                      fm1_seq_cmd_t *out);

/* KNOB1..4 (0..3) turned: its name and value take the hint line until
 * frame `until`. */
void fm1_seq_ui_knob(fm1_seq_ui_t *u, int knob, uint64_t until);

/* The white keys' LEDs in SEQ mode, bit n for white key n: the viewed bar's
 * steps with a note inside the loop, the playhead's inverted. */
uint16_t fm1_seq_ui_key_leds(const fm1_seq_ui_t *u);

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
