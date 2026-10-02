/* fm1_seq_view.h -- the sequencer's screens on the virtual FM-1 (docs/15 §4).
 *
 * S3 draws the Track view, between the app's title and bottom bars:
 *   status line   the tempo on the left; PLAY or STOP on the right
 *   grid          the focused track's first 4 bars, a row of 16 steps each,
 *                 one logged graphic: filled for a note, outlined outside the
 *                 loop, the playhead inverted
 *   knob strip    four bars, KNOB1..4 on the current sound page, no text
 *                 (owner decision O23, option b)
 *   hint line     the knob last turned, its full name and value as HOME's
 *                 rows show them, for two seconds; otherwise the sound's
 *                 model, as HOME's first line
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

/* The Track view's content, from CONTENT_Y down to the bottom bar. */
void fm1_seq_view_track(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd);

/* The bottom bar's left text in SEQ mode: "1/3 Seq T1". */
void fm1_seq_view_bottom(const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd, char *buf,
                         size_t size);

#ifdef __cplusplus
}
#endif

#endif /* FM1_SEQ_VIEW_H_ */
