/* fm1_seq_view.h -- the sequencer's screens on the virtual FM-1 (docs/15 §4).
 *
 * The Track view (S3, marks in S4), between the app's title and bottom bars:
 *   status line   the tempo on the left; PLAY, STOP or REC on the right
 *   grid          the focused track's four bars round the bar on the keys,
 *                 a row of 16 steps each, one logged graphic: filled for a
 *                 note, outlined outside the loop, the playhead inverted, a
 *                 tick under a step with a trig row (probability,
 *                 condition or invert), held steps framed, and a bracket
 *                 at both ends of the row on the keys
 *   knob strip    four bars, KNOB1..4 on the current sound page, no text
 *                 (owner decision O23, option b)
 *   hint line     the knob last turned, its full name and value as HOME's
 *                 rows show them, or the bar the keys moved to, for two
 *                 seconds; SHIFT's shortcuts while SEL is held; otherwise
 *                 the sound's model, as HOME's first line
 * The Step pages (S4), while steps are held: HOME's geometry, the held
 * step on the first line, four rows of label, value and bar (page 1:
 * Velocity, Length, Prob, Condition; page 2: Invert, and the Nudge and Note
 * as read-outs), and the bar's 16 steps in a strip where HOME has its
 * scope, the held steps and the steps under the first one's note marked.
 * With SHIFT held there, the first line and the strip say what SHIFT does.
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

/* The sound the knobs turn, as the app resolves it. */
typedef struct fm1_seq_view_sound {
  const fm1_engine_t *e;       /* NULL: no sound loaded */
  const float *value;          /* its parameters' values */
  int page, pages;             /* the page KNOB1..4 turn, of how many */
  int n, idx[4];               /* that page's parameters, KNOB1 first */
  int model;                   /* its first list parameter (ALGORITHM's), or -1 */
} fm1_seq_view_sound_t;

/* SEQ mode's content, from CONTENT_Y down to the bottom bar: the Track view
 * or, while steps are held, their Step page (u->view). */
void fm1_seq_view_draw(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd);

/* The bottom bar's left text in SEQ mode: "1/3 Seq T1", or "1/2 Step T1". */
void fm1_seq_view_bottom(const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd, char *buf,
                         size_t size);

/* A MIDI note as the Step page names it: "C4" for 60, "F#-1" for 6. */
void fm1_seq_view_note_name(int note, char *buf, size_t size);

#ifdef __cplusplus
}
#endif

#endif /* FM1_SEQ_VIEW_H_ */
