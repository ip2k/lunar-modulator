/* fm1_seq_view.c -- the sequencer's screens (fm1_seq_view.h). C99, no heap.
 * MIT licence, like the rest of this repository.
 */
#include "fm1_seq_view.h"

#include <stdio.h>

#include "fm1_look.h"

/* The Track view's geometry (docs/15 §4): the status line at CONTENT_Y, the
 * grid under it, the knob strip, then the hint line above the bottom bar. */
#define STATUS_Y CONTENT_Y
#define GRID_X MARGIN
#define GRID_Y 50
#define CELL_W 12
#define CELL_H 22
#define CELL_GAP 2                     /* between steps of one beat */
#define BEAT_GAP 4                     /* between beats */
#define ROW_GAP 6
#define GRID_W (16 * CELL_W + 12 * CELL_GAP + 3 * BEAT_GAP)
#define GRID_H (4 * CELL_H + 3 * ROW_GAP)
#define STRIP_Y 168
#define STRIP_H 8
#define STRIP_GAP 4
#define STRIP_W ((GRID_W - 3 * STRIP_GAP) / 4)
#define HINT_Y 190

typedef char fm1_seq_view_grid_fits[GRID_X + GRID_W <= RIGHT && GRID_Y + GRID_H < STRIP_Y ? 1 : -1];

static void draw_status(fm1_tft_t *t, const fm1_seq_ui_t *u) {
  char bpm[24];
  const char *state = u->playing ? "PLAY" : "STOP";
  snprintf(bpm, sizeof bpm, "%u.%02u BPM", (unsigned)(u->bpm_x100 / 100u),
           (unsigned)(u->bpm_x100 % 100u));
  fm1_tft_text(t, MARGIN, STATUS_Y, bpm, 10, SCALE, C_TEXT);
  fm1_tft_text(t, RIGHT - fm1_tft_text_width(state, 4, SCALE), STATUS_Y, state, 4, SCALE,
               u->playing ? C_PLAY : C_DIM);
}

static void draw_grid(fm1_tft_t *t, const fm1_seq_ui_t *u) {
  const unsigned end = (unsigned)u->loop_start + u->length;
  fm1_tft_graphic(t, GRID_X, GRID_Y, GRID_W, GRID_H);
  for (unsigned step = 0; step < FM1_SEQ_UI_GRID_STEPS; ++step) {
    const unsigned col = step % 16u, row = step / 16u;
    const int x = GRID_X + (int)(col * (CELL_W + CELL_GAP) + (col / 4u) * (BEAT_GAP - CELL_GAP));
    const int y = GRID_Y + (int)(row * (CELL_H + ROW_GAP));
    const int note = (int)((u->notes >> step) & 1u);
    const int head = u->clip_playing && u->step == step;
    if (u->length && step >= u->loop_start && step < end) {
      uint16_t c = note ? (head ? C_TEXT : C_ACCENT) : (head ? C_DIM : C_BAR_BG);
      fm1_tft_paint(t, x, y, CELL_W, CELL_H, c);
    } else {                           /* outside the loop: an outline */
      fm1_tft_frame(t, x, y, CELL_W, CELL_H, C_BAR_BG);
      if (note) fm1_tft_paint(t, x + 3, y + 3, CELL_W - 6, CELL_H - 6, C_BAR_BG);
    }
  }
}

void fm1_seq_view_track(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd) {
  draw_status(t, u);
  draw_grid(t, u);
  /* The knob strip: four bars, no text (O23 b). */
  for (int k = 0; snd->e && k < snd->n; ++k) {
    const fm1_param_t *p = &snd->e->params[snd->idx[k]];
    fm1_look_bar(t, GRID_X + k * (STRIP_W + STRIP_GAP), STRIP_Y, STRIP_W, STRIP_H, p,
                 snd->value[snd->idx[k]], k == u->knob ? C_TEXT : C_ACCENT);
  }
  /* The hint line: the knob being turned, else the sound's model. */
  if (snd->e && u->knob >= 0 && u->knob < snd->n) {
    const fm1_param_t *p = &snd->e->params[snd->idx[u->knob]];
    char v[24];
    fm1_look_value(p, snd->value[snd->idx[u->knob]], v, sizeof v);
    fm1_look_row(t, HINT_Y, p->name, v, C_TEXT);
  } else if (snd->e && snd->model >= 0) {
    char v[24];
    fm1_look_value(&snd->e->params[snd->model], snd->value[snd->model], v, sizeof v);
    fm1_tft_text(t, MARGIN, HINT_Y, v, LINE_CHARS, SCALE, C_MODEL);
  }
}

void fm1_seq_view_bottom(const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd, char *buf,
                         size_t size) {
  snprintf(buf, size, "%d/%d Seq T%u", snd->page + 1, snd->pages, (unsigned)u->track + 1u);
}
