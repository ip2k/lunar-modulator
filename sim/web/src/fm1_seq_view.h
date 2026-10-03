/* fm1_seq_view.h -- the sequencer's screens on the virtual FM-1 (docs/15 §4).
 *
 * The Track view (S3, marks in S4), between the app's title and bottom bars:
 *   status line   the tempo on the left; PLAY, STOP, REC (gold through a
 *                 count-in or a take waiting for its bar) or STEP (step
 *                 record) on the right
 *   grid          the focused track's four bars round the bar on the keys,
 *                 a row of 16 steps each, one logged graphic: filled for a
 *                 note, outlined outside the loop, the playhead inverted, a
 *                 tick under a step with a trig row (probability,
 *                 condition or invert), held steps framed, step record's
 *                 head framed red, and a bracket at both ends of the row
 *                 on the keys
 *   knob strip    four bars, KNOB1..4 on the current sound page, no text
 *                 (owner decision O23, option b)
 *   hint line     in step record, the head's step (and a tied chord's
 *                 span), or with SEL held that the keys move it; the knob
 *                 last turned, its full name and value as HOME's rows show
 *                 them, or the bar the keys moved to, for two seconds;
 *                 SHIFT's shortcuts while SEL is held; otherwise the
 *                 sound's model, as HOME's first line
 * The Step pages (S4), while steps are held: HOME's geometry, the held
 * step on the first line, four rows of label, value and bar (page 1:
 * Velocity, Length, Prob, Condition; page 2: Invert, and the Nudge and Note
 * as read-outs), and the bar's 16 steps in a strip where HOME has its
 * scope, the held steps and the steps under the first one's note marked.
 * With SHIFT held there, the first line and the strip say what SHIFT does.
 *
 * S6: the status line's middle holds the tracks, one cell each (the
 * focused one gold, a muted one an outline); a muted focused track's notes
 * are dim; with SHIFT held (no step held) the shortcuts' legend takes the
 * grid's place, and with MUTE or SEQ held the hint line says what the
 * white keys do. The Set, Clip and Track pages use HOME's rows, the page's
 * subject on the first line; Track page 2 lists the focused track's eight
 * lanes, each label's text after its last ':' and its 7-bit base, at a
 * 23 px pitch.
 * S8: the grid marks a step with a lock with a gold dot in its corner, as
 * the Step pages' strip does. The lock pages, past Step 2/2 with one step
 * held, are the lock sound's pages in HOME's rows: a parameter locked on the
 * step shows its lock in its own units, in gold, as a narrow gold bar over
 * the dim bar of its base; one with a lane but no lock here shows the base,
 * dim; one with no lane the knob's value, dim; a NOLOCK one "no lock". A
 * dot after the bar marks a lane: filled where the step has a lock, an
 * outline where it has none. With several steps held the pages show the
 * sound's values, which their knobs edit. The hint line follows a live
 * take's value while its knob turns, and with CLEAR held says a knob clears
 * its lane. Track page 2 writes a label's '_' as
 * the space it stands for.
 * Every text run keeps the app's 4 px gap and 2x text; the layout sweep
 * (fm1-sim-render --screens) checks each state.
 *
 * C99, no heap. MIT licence, like the rest of this repository.
 */
#ifndef FM1_SEQ_VIEW_H_
#define FM1_SEQ_VIEW_H_

#include <stddef.h>

#include "fm1_engine.h"
#include "fm1_seq_ui.h"
#include "fm1_tft.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The sound the knobs turn, as the app resolves it, and what the Track
 * page names. */
typedef struct fm1_seq_view_sound {
  const fm1_engine_t *e;       /* NULL: no sound loaded */
  const float *value;          /* its parameters' values */
  int page, pages;             /* the page KNOB1..4 turn, of how many */
  int n, idx[4];               /* that page's parameters, KNOB1 first */
  int model;                   /* its first list parameter (ALGORITHM's), or -1 */
  const fm1_seq_t *seq;        /* the sequencer, for Track page 2's lanes (or NULL) */
  const char *unit_name[FM1_SEQ_UI_SOUNDS];   /* each sound unit's engine, NULL: empty */
  /* The lock pages' sound (S8): the sound unit the focused track routes to. */
  const fm1_engine_t *lock_e;  /* NULL: none (a MIDI route, an empty sound) */
  const float *lock_value;     /* its values: the knobs' */
  int lock_sound;              /* its index, 0-based, or -1 */
  int lock_current;            /* it is the current sound (the title's) */
} fm1_seq_view_sound_t;

/* SEQ mode's content, from CONTENT_Y down to the bottom bar: the Track view
 * or, while steps are held, their Step page (u->view). */
void fm1_seq_view_draw(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd);

/* The bottom bar's left text in SEQ mode: "1/3 Seq T1", "1/2 Step T1",
 * "1/3 Lock T1", "1/1 Set", "1/1 Clip T1" or "1/2 Track 1": at most 11
 * characters, so it keeps its gap from the RAM meter. */
void fm1_seq_view_bottom(const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd, char *buf,
                         size_t size);

/* A MIDI note as the Step page names it: "C4" for 60, "F#-1" for 6. */
void fm1_seq_view_note_name(int note, char *buf, size_t size);

#ifdef __cplusplus
}
#endif

#endif /* FM1_SEQ_VIEW_H_ */
