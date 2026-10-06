/* fm1_seq_view.c -- the sequencer's screens (fm1_seq_view.h). C99, no heap.
 * MIT licence, like the rest of this repository.
 */
#include "fm1_seq_view.h"

#include <stdio.h>
#include <string.h>

#include "fm1_look.h"
#include "fm1_panel.h"
#include "fm1_seq_host.h"

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
#define BRACKET_W 2                    /* the bar on the keys: a mark at each end */
#define BOX_X (GRID_X - 2 - BRACKET_W - 1)
#define BOX_W (GRID_W + 2 * (2 + BRACKET_W + 1))
#define TICK_H 3                       /* a trig row's tick under the cell */
#define STRIP_Y 168
#define STRIP_H 8
#define STRIP_GAP 4
#define STRIP_W ((GRID_W - 3 * STRIP_GAP) / 4)
#define HINT_Y 190
/* The Step pages: HOME's rows, and the bar's steps where HOME has its scope. */
#define STEPS_Y 192
#define STEPS_H 20
/* The tempo on the status line: a whole one in MAIN ("120 BPM", at most
 * 82 px), one with decimals in MID ("117.65 BPM", at most 80 px), so the
 * tracks always have from TRACKS_L to TRACKS_R: 7 px clear of the tempo and
 * of the transport (4 characters, 46 px to RIGHT). The tracks are tiles of
 * TRACK_W in the colour of the sound each plays, centred there, each with
 * that sound's number on it in SMALL (audit L3: the number is the cue that
 * needs no colour), TRACK_PAD clear of the tile's sides and 2 px of its top
 * and bottom; the focused one the line's full height, the others TRACK_H; a
 * muted one unlit: its number alone, in the sound's colour (focused, with
 * the TRACK_EXTRA bars a focused tile adds above and below it). */
#define TEMPO_W FM1_TFT_MAIN_W(7)                          /* "300 BPM" */
#define TRACKS_L (MARGIN + TEMPO_W + 7)
#define TRACKS_R (RIGHT - FM1_TFT_MAIN_W(4) - 7)
#define TRACK_PAD 2
#define TRACK_INK_W 5                  /* SMALL's digits and 'M': 5 px of ink from the cell's left */
#define TRACK_W (TRACK_PAD + TRACK_INK_W + TRACK_PAD)
#define TRACK_GAP 2
#define TRACK_H (FM1_TFT_SMALL_CAP_H + 4)
#define TRACKS_SPAN (8 * TRACK_W + 7 * TRACK_GAP)
#define TRACKS_X (TRACKS_L + (TRACKS_R - TRACKS_L - TRACKS_SPAN) / 2)
#define TRACKS_Y STATUS_Y
#define TRACKS_FULL 18                                     /* the line's height */
#define TRACK_EXTRA ((TRACKS_FULL - TRACK_H) / 2)          /* a focused tile's, above and below */
/* The numbers' run: its box's top, so a digit's ink is centred on the line. */
#define TRACKS_TEXT_Y \
  (TRACKS_Y + (TRACKS_FULL - FM1_TFT_SMALL_CAP_H) / 2 - (FM1_TFT_SMALL_BASELINE - FM1_TFT_SMALL_CAP_H))
#define LEGEND_PITCH 22                /* SHIFT's legend, from GRID_Y, in MID */
#define LANE_PITCH 20                  /* Track page 2: eight lanes, in MID, under its heading */
#define LOCK_DOT 3                     /* a step with a lock: a dot in the cell's corner */
/* The lock pages (S8): HOME's bar, shortened for the lane dot after it. */
#define DOT_W 6
#define LOCK_BAR_W (FM1_TFT_W - 2 * MARGIN - DOT_W - 4)
#define LOCK_INSET 2                   /* the lock's bar inside its base's, top and bottom */

typedef char fm1_seq_view_lanes_fit[CONTEXT_NEXT_Y + 7 * LANE_PITCH + MID_LINE_H + 4 <= BOTTOM_Y ? 1 : -1];
typedef char fm1_seq_view_legend_fits[GRID_Y + 5 * LEGEND_PITCH + MID_LINE_H + 4 <= HINT_Y ? 1 : -1];
typedef char fm1_seq_view_tracks_fit[TRACKS_X >= TRACKS_L && TRACKS_X + TRACKS_SPAN <= TRACKS_R &&
                                     FM1_TFT_MID_W(10) <= TEMPO_W && TRACKS_L - (MARGIN + TEMPO_W) >= 4 &&
                                     TRACKS_TEXT_Y >= TRACKS_Y && TRACKS_FULL == TRACK_H + 2 * TRACK_EXTRA &&
                                     TRACKS_TEXT_Y + FM1_TFT_SMALL_H <= TRACKS_Y + TRACKS_FULL &&
                                     TRACK_W + TRACK_GAP >= FM1_TFT_SMALL_ADVANCE &&
                                     TRACK_INK_W <= FM1_TFT_SMALL_INK_W ? 1 : -1];

typedef char fm1_seq_view_grid_fits[BOX_X >= 0 && BOX_X + BOX_W <= FM1_TFT_W &&
                                    GRID_Y + GRID_H < STRIP_Y ? 1 : -1];

static int col_x(unsigned col) {
  return GRID_X + (int)(col * (CELL_W + CELL_GAP) + (col / 4u) * (BEAT_GAP - CELL_GAP));
}

void fm1_seq_view_bpm(uint32_t bpm_x100, char *buf, size_t size) {
  const unsigned whole = (unsigned)(bpm_x100 / 100u), frac = (unsigned)(bpm_x100 % 100u);
  if (!frac) snprintf(buf, size, "%u BPM", whole);
  else if (frac % 10u == 0) snprintf(buf, size, "%u.%u BPM", whole, frac / 10u);
  else snprintf(buf, size, "%u.%02u BPM", whole, frac);
}

/* A track on the strip: the number of the sound it plays ('1' to '4') and
 * that sound's colour; 'M' in subtle for MIDI out. */
static char track_tag(const fm1_seq_view_sound_t *snd, unsigned k, uint16_t *colour) {
  fm1_seq_track_info_t tr;
  *colour = C_LABEL;
  if (!snd->seq) return 'M';
  memset(&tr, 0, sizeof tr);
  fm1_seq_get_track(snd->seq, k, &tr);
  if (tr.route_kind != FM1_SEQ_ROUTE_ENGINE || tr.route_index >= FM1_SEQ_UI_SOUNDS) return 'M';
  *colour = fm1_sound_colour(tr.route_index);
  return (char)('1' + tr.route_index);
}

/* The transport on the right: REC while the focused track records (gold
 * through its count-in or while the take waits for the bar), STEP in step
 * record, else PLAY or STOP. */
static void draw_status(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd) {
  char bpm[24];
  const int mine = u->rec_track == u->track;
  const int rec = mine && u->recording, count = mine && !u->recording && u->counting_in;
  /* A song followed reads SONG, and END once parked (SG11). */
  const int song = u->playing && u->song_len && u->song_follow;
  const char *state = rec || count ? "REC" : u->srec ? "STEP"
                    : song ? (u->song_parked ? "END" : "SONG") : u->playing ? "PLAY" : "STOP";
  fm1_seq_view_bpm(u->bpm_x100, bpm, sizeof bpm);
  if (fm1_tft_text_width(bpm, 10, SCALE) <= TEMPO_W) {
    fm1_tft_text(t, MARGIN, STATUS_Y, bpm, 10, SCALE, C_TEXT);
  } else {                               /* decimals: MID, on MAIN's baseline */
    fm1_tft_font_text(t, MARGIN, STATUS_Y + FM1_TFT_MAIN_BASELINE - FM1_TFT_MID_BASELINE, bpm, 10,
                      FM1_TFT_MID, C_TEXT);
  }
  fm1_tft_text(t, RIGHT - fm1_tft_text_width(state, 4, SCALE), STATUS_Y, state, 4, SCALE,
               rec || u->srec ? C_REFUSE : count ? C_HELD
               : song && u->song_parked ? C_LABEL : u->playing ? C_LIVE : C_LABEL);
  /* The tracks (S6): each a tile in its sound's colour with the sound's
   * number on it, the focused one the line's full height; a muted one
   * unlit, its number alone in the sound's colour (focused, between the
   * bars a focused tile adds).
   * The tiles are the numbers' ground, as the selection's bar is a row's:
   * the numbers are the one logged run. */
  if (u->tracks) {
    const unsigned n = u->tracks < 8u ? u->tracks : 8u;
    char tag[8][2];
    fm1_tft_span_t sp[8];
    uint8_t lead[8];
    for (unsigned k = 0; k < n; ++k) {
      const int x = TRACKS_X + (int)k * (TRACK_W + TRACK_GAP);
      const int focused = k == u->track, muted = (u->muted >> k) & 1u;
      const int y = focused ? TRACKS_Y : TRACKS_Y + TRACK_EXTRA;
      const int h = focused ? TRACKS_FULL : TRACK_H;
      uint16_t c;
      tag[k][0] = track_tag(snd, k, &c);
      tag[k][1] = '\0';
      if (!muted) {
        fm1_tft_paint(t, x, y, TRACK_W, h, c);
      } else if (focused) {              /* what a focused tile adds, above and below */
        fm1_tft_paint(t, x, TRACKS_Y, TRACK_W, TRACK_EXTRA, c);
        fm1_tft_paint(t, x, TRACKS_Y + TRACKS_FULL - TRACK_EXTRA, TRACK_W, TRACK_EXTRA, c);
      }
      sp[k].s = tag[k];
      sp[k].color = muted ? c : C_BG;
      lead[k] = (uint8_t)(TRACK_W + TRACK_GAP - FM1_TFT_SMALL_ADVANCE);
    }
    fm1_tft_span_text_lead(t, TRACKS_X + TRACK_PAD, TRACKS_TEXT_Y, sp, lead, (int)n, 8, FM1_TFT_SMALL);
  }
}

/* One step's cell: a note filled, inside the loop or outlined outside it,
 * the playhead inverted; a muted track's notes dim. */
static void draw_cell(fm1_tft_t *t, int x, int y, int w, int h, int in_loop, int note, int head,
                      int muted) {
  if (in_loop) {
    const uint16_t c = note ? (head ? C_TEXT : (muted ? C_LABEL : C_SELECT))
                            : (head ? C_LABEL : C_BAR_BG);
    fm1_tft_paint(t, x, y, w, h, c);
  } else {
    fm1_tft_frame(t, x, y, w, h, C_BAR_BG);
    if (note) fm1_tft_paint(t, x + 3, y + 3, w - 6, h - 6, C_BAR_BG);
  }
}

static int focused_muted(const fm1_seq_ui_t *u) {
  return u->track < 16u && ((u->muted >> u->track) & 1u);
}

static void draw_grid(fm1_tft_t *t, const fm1_seq_ui_t *u) {
  const unsigned end = (unsigned)u->loop_start + u->length;
  const uint16_t held = fm1_seq_ui_held_mask(u);
  const int muted = focused_muted(u);
  fm1_tft_graphic(t, BOX_X, GRID_Y, BOX_W, GRID_H);
  for (unsigned g = 0; g < FM1_SEQ_UI_GRID_STEPS; ++g) {
    const unsigned step = u->grid_first + g, col = g % 16u, row = g / 16u;
    const int x = col_x(col);
    const int y = GRID_Y + (int)(row * (CELL_H + ROW_GAP));
    draw_cell(t, x, y, CELL_W, CELL_H, u->length && step >= u->loop_start && step < end,
              (int)((u->notes >> g) & 1u), u->clip_playing && u->step == step, muted);
    if ((u->trigs >> g) & 1u) fm1_tft_paint(t, x + 2, y + CELL_H - TICK_H - 2, CELL_W - 4, TICK_H, C_LIVE);
    if ((u->locks >> g) & 1u) {             /* a lock (S8): a gold dot in the corner */
      fm1_tft_paint(t, x + CELL_W - LOCK_DOT - 1, y + 1, LOCK_DOT, LOCK_DOT, C_HELD);
    }
    if (step / 16u == u->bar && ((held >> col) & 1u)) {
      fm1_tft_frame(t, x - 1, y - 1, CELL_W + 2, CELL_H + 2, C_HELD);
    }
    if (u->srec && step == u->srec_head) {   /* step record's head */
      fm1_tft_frame(t, x - 1, y - 1, CELL_W + 2, CELL_H + 2, C_REFUSE);
    }
  }
  {
    const int y = GRID_Y + (int)((u->bar % 4u) * (CELL_H + ROW_GAP));
    fm1_tft_paint(t, BOX_X, y, BRACKET_W, CELL_H, C_SELECT);   /* the bar the keys edit */
    fm1_tft_paint(t, BOX_X + BOX_W - BRACKET_W, y, BRACKET_W, CELL_H, C_SELECT);
  }
}

/* A line in the MID face: a subtle label on the left, its value
 * right-aligned in `color`. */
static void mid_row(fm1_tft_t *t, int y, const char *label, const char *value, uint16_t color) {
  const int lw = fm1_tft_font_width(label, MID_LINE_CHARS, FM1_TFT_MID);
  const int room = fm1_tft_font_fit(RIGHT - (MARGIN + lw + 4), FM1_TFT_MID);
  fm1_tft_font_text(t, MARGIN, y, label, MID_LINE_CHARS, FM1_TFT_MID, C_LABEL);
  fm1_tft_font_text(t, RIGHT - fm1_tft_font_width(value, room, FM1_TFT_MID), y, value, room,
                    FM1_TFT_MID, color);
}

/* SHIFT held with no step held (S6): what SHIFT + white key N does, in the
 * grid's place, as Movy's step-shortcuts.ts has them, in words: MID's 28
 * characters a line leave room for them. */
static void draw_legend(fm1_tft_t *t, const fm1_seq_ui_t *u) {
  char v[32];
  int y = GRID_Y;
  mid_row(t, y, "Key 2", "Track page", C_TEXT); y += LEGEND_PITCH;
  mid_row(t, y, "Key 3", "Clip page", C_TEXT); y += LEGEND_PITCH;
  mid_row(t, y, "Keys 5 7 9", "Set page", C_TEXT); y += LEGEND_PITCH;
  mid_row(t, y, "Key 6", u->metro ? "Metronome on" : "Metronome off", C_TEXT); y += LEGEND_PITCH;
  mid_row(t, y, "Key 10", u->full_vel ? "Full velocity on" : "Full velocity off", C_TEXT);
  y += LEGEND_PITCH;
  snprintf(v, sizeof v, "Clip quantize %u%%", (unsigned)u->clip_quant);
  mid_row(t, y, "Key 16", v, C_TEXT);
}

static void draw_track(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd) {
  const int legend = u->shift && !u->srec && !u->held_n;
  draw_status(t, u, snd);
  if (legend) {
    draw_legend(t, u);
  } else {
    draw_grid(t, u);
  }
  /* The knob strip: four bars, no text (O23 b); while a knob turns, its
   * bar alone in the selection's colour (the value being edited), the
   * others subtle. */
  for (int k = 0; !legend && snd->e && k < snd->n; ++k) {
    const fm1_param_t *p = &snd->e->params[snd->idx[k]];
    fm1_look_bar(t, GRID_X + k * (STRIP_W + STRIP_GAP), STRIP_Y, STRIP_W, STRIP_H, p,
                 snd->value[snd->idx[k]], u->knob < 0 || k == u->knob ? C_SELECT : C_LABEL);
  }
  /* The hint line: step record's head (SHIFT's jump while SEL is held),
   * SHIFT's shortcuts, the knob being turned or the bar the keys moved to,
   * else the sound's model. */
  if (u->srec && u->shift) {
    fm1_look_row(t, HINT_Y, "Keys", "move the head", C_HINT);
  } else if (u->srec) {
    char v[24];
    if (u->srec_open && u->srec_tie) {
      snprintf(v, sizeof v, "%u-%u", (unsigned)u->srec_anchor + 1u,
               (unsigned)u->srec_anchor + u->srec_tie + 1u);
    } else {
      snprintf(v, sizeof v, "%u", (unsigned)u->srec_head + 1u);
    }
    fm1_look_row(t, HINT_Y, "Step rec", v, C_REFUSE);
  } else if (u->seq_held) {
    fm1_look_row(t, HINT_Y, "Keys 1-8", "pick track", C_HINT);
  } else if (u->mute_held) {
    fm1_look_row(t, HINT_Y, "Keys 1-8", "mute", C_HINT);
  } else if (u->clear_held) {                /* CLEAR (S8): a knob clears its lane */
    fm1_look_row(t, HINT_Y, "Knob", "clears lane", C_HINT);
  } else if (u->hint == FM1_SEQ_HINT_BAR) {
    char v[24];
    const unsigned bars = u->length ? ((unsigned)u->loop_start + u->length + 15u) / 16u : 0u;
    if (u->bar < bars) snprintf(v, sizeof v, "%u of %u", (unsigned)u->bar + 1u, bars);
    else snprintf(v, sizeof v, "%u, empty", (unsigned)u->bar + 1u);
    fm1_look_row(t, HINT_Y, "Bar", v, C_TEXT);
  } else if (snd->e && u->hint == FM1_SEQ_HINT_KNOB && u->knob >= 0 && u->knob < snd->n) {
    const fm1_param_t *p = &snd->e->params[snd->idx[u->knob]];
    char v[24];
    if (u->take_param == snd->idx[u->knob] && snd->lock_current) {   /* a live take (S8) */
      fm1_look_value(p, fm1_seq_lock_value(p, u->take_v), v, sizeof v);
      fm1_look_row(t, HINT_Y, p->name, v, C_HELD);
    } else {
      fm1_look_value(p, snd->value[snd->idx[u->knob]], v, sizeof v);
      fm1_look_row(t, HINT_Y, p->name, v, C_TEXT);
    }
  } else if (u->playing && u->song_armed && u->song_follow && !u->song_parked && u->song_len) {
    /* The playing entry's last bar (SG11): what falls in next. */
    char v[24];
    if (u->song_next != FM1_SEQ_NONE) fm1_seq_view_scene(snd->seq, u->song_next, v, sizeof v);
    else snprintf(v, sizeof v, "%s", u->song_end == FM1_SEQ_SONG_STOP ? "Stop" : "End");
    fm1_look_row(t, HINT_Y, "Next", v, C_LIVE);
  } else if (snd->e && snd->model >= 0) {
    char v[24];
    /* The model, in the context colour, by its full name where the line
     * holds it (D9: "Phase Distortion", as HOME's context line). */
    const char *full;
    fm1_look_value(&snd->e->params[snd->model], snd->value[snd->model], v, sizeof v);
    full = fm1_look_full_name(v);
    fm1_tft_text(t, MARGIN, HINT_Y, strlen(full) <= LINE_CHARS ? full : v, LINE_CHARS, SCALE, C_CONTEXT);
  }
}

/* ---- the Step pages -------------------------------------------------------------- */

static void draw_lock(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd);

void fm1_seq_view_note_name(int note, char *buf, size_t size) {
  static const char *const kNames[12] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A",
                                          "A#", "B" };
  if (note < 0 || note > 127) {
    snprintf(buf, size, "--");
    return;
  }
  snprintf(buf, size, "%s%d", kNames[note % 12], note / 12 - 1);
}

/* A hint in the context line's place (SHIFT or CLEAR held): MID, as text. */
static void hint_line(fm1_tft_t *t, const char *text) {
  fm1_tft_font_text(t, MARGIN, CONTEXT_Y, text, MID_LINE_CHARS, FM1_TFT_MID, C_HINT);
}

/* A row as HOME draws one, under the context line (CONTEXT_NEXT_Y), with a
 * bar for `p` at `v` unless p is NULL: the
 * value as text and the bar in the selection's colour, or both in `color`
 * when it is not 0 (a sound's). */
static void step_row_c(fm1_tft_t *t, int row, const char *label, const char *value,
                       const fm1_param_t *p, float v, int known, uint16_t color) {
  const int y = CONTEXT_NEXT_Y + row * ROW_PITCH;
  fm1_look_row(t, y, label, value, !known ? C_LABEL : color ? color : C_TEXT);
  if (p) {
    fm1_look_bar(t, MARGIN, y + BAR_DY, FM1_TFT_W - 2 * MARGIN, BAR_H, p, known ? v : p->min,
                 !known ? C_BAR_BG : color ? color : C_SELECT);
  }
}

static void step_row(fm1_tft_t *t, int row, const char *label, const char *value,
                     const fm1_param_t *p, float v, int known) {
  step_row_c(t, row, label, value, p, v, known, 0);
}

/* The bar on the keys: held steps light, the steps under the first held
 * step's note gold, the rest as the grid draws them. */
static void draw_steps(fm1_tft_t *t, const fm1_seq_ui_t *u) {
  const unsigned end = (unsigned)u->loop_start + u->length;
  const uint16_t held = fm1_seq_ui_held_mask(u), under = fm1_seq_ui_under_mask(u);
  fm1_tft_graphic(t, GRID_X, STEPS_Y, GRID_W, STEPS_H);
  for (unsigned n = 0; n < 16u; ++n) {
    const unsigned step = u->bar * 16u + n, g = step - u->grid_first;
    const int x = col_x(n);
    if ((held >> n) & 1u) {
      fm1_tft_paint(t, x, STEPS_Y, CELL_W, STEPS_H, C_HELD);
    } else if ((under >> n) & 1u) {
      fm1_tft_paint(t, x, STEPS_Y, CELL_W, STEPS_H, C_SELECT);
      fm1_tft_paint(t, x, STEPS_Y + STEPS_H / 2 - 1, CELL_W, 2, C_HELD);
    } else {
      draw_cell(t, x, STEPS_Y, CELL_W, STEPS_H, u->length && step >= u->loop_start && step < end,
                g < FM1_SEQ_UI_GRID_STEPS && ((u->notes >> g) & 1u),
                u->clip_playing && u->step == step, focused_muted(u));
    }
    if (g < FM1_SEQ_UI_GRID_STEPS && ((u->locks >> g) & 1u)) {   /* a lock (S8) */
      fm1_tft_paint(t, x + CELL_W - LOCK_DOT - 1, STEPS_Y + 1, LOCK_DOT, LOCK_DOT,
                    (held >> n) & 1u ? C_BG : C_HELD);
    }
  }
}

static void draw_step(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd) {
  static const fm1_param_t kVel = { "Velocity", FM1_PARAM_FLOAT, 0.0f, 127.0f, 100.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kLen = { "Length", FM1_PARAM_FLOAT, 0.0f, (float)(FM1_SEQ_UI_LENGTHS - 1),
                                    1.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kProb = { "Prob", FM1_PARAM_FLOAT, 0.0f, 100.0f, 100.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kCond = { "Condition", FM1_PARAM_ENUM, 0.0f,
                                     (float)(FM1_SEQ_UI_CONDS - 1), 0.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kInv = { "Invert", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.0f, NULL, 0, 0, 0, 0, "" };
  const fm1_seq_ui_hold_t *h = &u->hold;
  const int notes = u->hold_valid && h->notes;
  char line[24], v[24];
  if (u->step_page >= FM1_SEQ_UI_STEP_PAGES) {   /* the lock pages (S8) */
    draw_lock(t, u, snd);
    if (u->shift) fm1_tft_text(t, MARGIN, STEPS_Y, "Tap SHIFT: clear", LINE_CHARS, SCALE, C_HINT);
    else draw_steps(t, u);
    return;
  }
  if (u->shift) {
    hint_line(t, "Keys add a pitch");
  } else {
    if (u->held_n > 1) snprintf(line, sizeof line, "Step %u +%u", (unsigned)h->step + 1u,
                                (unsigned)u->held_n - 1u);
    else snprintf(line, sizeof line, "Step %u", (unsigned)h->step + 1u);
    fm1_look_context(t, CONTEXT_Y, line, NULL);
  }
  if (u->step_page == 0) {
    snprintf(v, sizeof v, "%u", (unsigned)h->vel);
    step_row(t, 0, kVel.name, notes ? v : "--", &kVel, (float)h->vel, notes);
    {
      const int i = fm1_seq_ui_length_index(h->gate);
      step_row(t, 1, kLen.name, !notes ? "--" : h->gate_mixed ? "..." : fm1_seq_ui_length_names[i],
               &kLen, (float)i, notes && !h->gate_mixed);
    }
    snprintf(v, sizeof v, "%u%%", (unsigned)h->prob);
    step_row(t, 2, kProb.name, v, &kProb, (float)h->prob, 1);
    snprintf(v, sizeof v, "%u:%u", (unsigned)h->cond_a, (unsigned)h->cond_b);
    step_row(t, 3, kCond.name, v, &kCond, (float)fm1_seq_ui_cond_index(h->cond_a, h->cond_b), 1);
  } else {
    step_row(t, 0, kInv.name, h->inv ? "On" : "Off", &kInv, (float)h->inv, 1);
    if (notes) {
      const int nudge = (int)h->tick - (int)h->step * (int)FM1_SEQ_TICKS_PER_STEP;
      if (nudge) snprintf(v, sizeof v, "%+d ticks", nudge);
      else snprintf(v, sizeof v, "0 ticks");
    }
    step_row(t, 1, "Nudge", notes ? v : "--", NULL, 0.0f, notes);
    if (notes) {
      char name[8];
      fm1_seq_view_note_name(h->pitch, name, sizeof name);
      if (h->notes > 1) snprintf(v, sizeof v, "%s +%u", name, (unsigned)h->notes - 1u);
      else snprintf(v, sizeof v, "%s", name);
    }
    step_row(t, 2, "Note", notes ? v : "--", NULL, 0.0f, notes);
  }
  if (u->shift) {
    fm1_tft_text(t, MARGIN, STEPS_Y, "Tap SHIFT: clear", LINE_CHARS, SCALE, C_HINT);
  } else {
    draw_steps(t, u);
  }
}

/* ---- the lock pages (S8) --------------------------------------------------------- */

/* One parameter's row on a lock page: label and value as HOME's, a bar of
 * LOCK_BAR_W and, after it, the lane's dot. */
static void lock_row(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd,
                     int row, int param) {
  const fm1_param_t *p = &snd->lock_e->params[param];
  const int y = CONTEXT_NEXT_Y + row * ROW_PITCH;
  const int one = u->held_n == 1;
  char v[24];
  int lane, locked = 0;
  float base, value;
  fm1_seq_track_info_t tr;
  if (!fm1_param_lockable(p) && one) {      /* NOLOCK: named, with nothing to turn */
    fm1_look_row(t, y, p->name, "no lock", C_LABEL);
    return;
  }
  memset(&tr, 0, sizeof tr);
  if (snd->seq) fm1_seq_get_track(snd->seq, u->track, &tr);
  lane = fm1_seq_ui_lane_of(snd->seq, u->track, snd->lock_e, param);
  base = lane >= 0 ? fm1_seq_lock_value(p, tr.base[lane]) : snd->lock_value[param];
  if (!one) {                               /* several steps held: the sound itself */
    fm1_look_value(p, snd->lock_value[param], v, sizeof v);
    fm1_look_row(t, y, p->name, v, C_TEXT);
    fm1_look_bar(t, MARGIN, y + BAR_DY, LOCK_BAR_W, BAR_H, p, snd->lock_value[param], C_SELECT);
  } else {
    locked = lane >= 0 && u->hold_valid && ((u->hold.lock_mask >> lane) & 1u);
    value = locked ? fm1_seq_lock_value(p, u->hold.lock[lane]) : base;
    fm1_look_value(p, value, v, sizeof v);
    fm1_look_row(t, y, p->name, v, locked ? C_HELD : C_LABEL);
    fm1_look_bar(t, MARGIN, y + BAR_DY, LOCK_BAR_W, BAR_H, p, base, C_LABEL);
    if (locked) {                           /* the lock, over its base */
      fm1_look_fill(t, MARGIN, y + BAR_DY + LOCK_INSET, LOCK_BAR_W, BAR_H - 2 * LOCK_INSET, p,
                    value, C_HELD);
    }
  }
  if (lane >= 0) {                          /* the lane: filled with a lock on the step */
    const int dx = RIGHT - DOT_W;
    fm1_tft_graphic(t, dx, y + BAR_DY, DOT_W, BAR_H);
    if (locked) fm1_tft_paint(t, dx, y + BAR_DY, DOT_W, BAR_H, C_HELD);
    else fm1_tft_frame(t, dx, y + BAR_DY, DOT_W, BAR_H, C_HELD);
  }
}

static void draw_lock(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd) {
  char line[32], tag[16] = "";
  const char *hint = NULL;
  int idx[4], n;
  const int page = u->step_page - FM1_SEQ_UI_STEP_PAGES;
  const fm1_seq_ui_hold_t *h = &u->hold;
  if (u->clear_held) {                      /* CLEAR + a knob clears its lane (aclr): a hint */
    hint = "Knob: clear lane";
  } else if (u->shift && u->held_n == 1) {  /* SHIFT + a knob clears its lock (aclrs) */
    hint = "Knob: clear lock";
  } else if (u->held_n > 1) {
    snprintf(line, sizeof line, "Step %u +%u sound", (unsigned)h->step + 1u, (unsigned)u->held_n - 1u);
  } else {
    snprintf(line, sizeof line, "Lock step %u", (unsigned)h->step + 1u);
    /* Another sound's: its "S<n>" on the right, in its colour (the
     * number for who cannot tell the colours apart). */
    if (!snd->lock_current && snd->lock_sound >= 0) snprintf(tag, sizeof tag, "S%d", snd->lock_sound + 1);
  }
  if (hint) {
    hint_line(t, hint);
  } else {
    fm1_look_context(t, CONTEXT_Y, line, NULL);
    if (tag[0]) {
      fm1_tft_font_text(t, RIGHT - fm1_tft_font_width(tag, 4, FM1_TFT_MID), CONTEXT_Y, tag, 4,
                        FM1_TFT_MID, fm1_sound_colour(snd->lock_sound));
    }
  }
  n = snd->lock_e ? fm1_seq_ui_page_params(snd->lock_e, page, idx) : 0;
  for (int r = 0; r < n; ++r) lock_row(t, u, snd, r, idx[r]);
}

/* ---- the Set, Clip and Track pages (S6) ------------------------------------------ */

static void draw_set(fm1_tft_t *t, const fm1_seq_ui_t *u) {
  static const fm1_param_t kTempo = { "Tempo", FM1_PARAM_FLOAT, 20.0f, 300.0f, 120.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kSwing = { "Swing", FM1_PARAM_FLOAT, 50.0f, 80.0f, 50.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kQuant = { "Def quant", FM1_PARAM_FLOAT, 0.0f, 100.0f, 0.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kMetro = { "Metronome", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.0f, NULL, 0, 0, 0, 0, "" };
  char v[24];
  fm1_look_context(t, CONTEXT_Y, "Set: all tracks", NULL);
  fm1_seq_view_bpm(u->bpm_x100, v, sizeof v);
  step_row(t, 0, kTempo.name, v, &kTempo, (float)u->bpm_x100 / 100.0f, 1);
  snprintf(v, sizeof v, "%u%%", (unsigned)u->swing);
  step_row(t, 1, kSwing.name, v, &kSwing, (float)u->swing, 1);
  snprintf(v, sizeof v, "%u%%", (unsigned)u->dq);
  step_row(t, 2, kQuant.name, v, &kQuant, (float)u->dq, 1);
  step_row(t, 3, kMetro.name, u->metro ? "On" : "Off", &kMetro, (float)(u->metro != 0), 1);
}

static void draw_clip(fm1_tft_t *t, const fm1_seq_ui_t *u) {
  static const fm1_param_t kSpeed = { "Speed", FM1_PARAM_ENUM, 0.0f, (float)(FM1_SEQ_UI_SPEEDS - 1),
                                      (float)FM1_SEQ_UI_SPEED_1X, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kLength = { "Length", FM1_PARAM_FLOAT, 1.0f, (float)FM1_SEQ_MAX_STEPS,
                                       16.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kTrans = { "Transpose", FM1_PARAM_FLOAT, -36.0f, 36.0f, 0.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kQuant = { "Quantize", FM1_PARAM_FLOAT, 0.0f, 100.0f, 0.0f, NULL, 0, 0, 0, 0, "" };
  const int i = fm1_seq_ui_speed_index(u->clip_num, u->clip_den);
  const unsigned num = fm1_seq_ui_speeds[i][0], den = fm1_seq_ui_speeds[i][1];
  char line[24], v[24];
  snprintf(line, sizeof line, "Clip: track %u", (unsigned)u->track + 1u);
  fm1_look_context(t, CONTEXT_Y, line, NULL);
  if (den == 1u) snprintf(v, sizeof v, "%uX", num);
  else snprintf(v, sizeof v, "%u/%uX", num, den);
  step_row(t, 0, kSpeed.name, v, &kSpeed, (float)i, 1);
  if (u->length) snprintf(v, sizeof v, "%u step%s", (unsigned)u->length, u->length == 1 ? "" : "s");
  step_row(t, 1, kLength.name, u->length ? v : "--", &kLength, (float)u->length, u->length != 0);
  if (u->clip_tr) snprintf(v, sizeof v, "%+d", (int)u->clip_tr);
  step_row(t, 2, kTrans.name, u->clip_tr ? v : "0", &kTrans, (float)u->clip_tr, 1);
  snprintf(v, sizeof v, "%u%%", (unsigned)u->clip_quant);
  step_row(t, 3, kQuant.name, v, &kQuant, (float)u->clip_quant, 1);
}

/* A label's name: the text after its last ':', as the bridge resolves it. */
static const char *lane_name(const char *label) {
  const char *name = label;
  for (const char *p = label; *p; ++p) {
    if (*p == ':') name = p + 1;
  }
  return name;
}

static void draw_trackpg(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd) {
  static const fm1_param_t kRoute = { "Route", FM1_PARAM_ENUM, 0.0f, 1.0f, 0.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kSound = { "Sound", FM1_PARAM_ENUM, 0.0f, (float)(FM1_SEQ_UI_SOUNDS - 1),
                                      0.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kChannel = { "Channel", FM1_PARAM_ENUM, 1.0f, 16.0f, 1.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kMute = { "Mute", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.0f, NULL, 0, 0, 0, 0, "" };
  char v[24];
  if (u->track_page) {                       /* the lanes: label and 7-bit base, in MID */
    fm1_seq_track_info_t tr;
    snprintf(v, sizeof v, "Lanes: track %u", (unsigned)u->track + 1u);
    fm1_look_context(t, CONTEXT_Y, v, NULL);
    memset(&tr, 0, sizeof tr);
    if (snd->seq) fm1_seq_get_track(snd->seq, u->track, &tr);
    for (unsigned lane = 0; lane < FM1_SEQ_LANES; ++lane) {
      const int y = CONTEXT_NEXT_Y + (int)lane * LANE_PITCH;
      const char *label = snd->seq ? fm1_seq_lane_label(snd->seq, u->track, (uint8_t)lane) : "";
      char n[8];
      snprintf(n, sizeof n, "%u ", lane + 1u);
      if (label[0]) {
        /* "1 Env Timbre ... 64": the name as long as the line holds
         * beside the number and the base. */
        char b[8], name[40];
        snprintf(b, sizeof b, "%u", (unsigned)tr.base[lane]);
        snprintf(name, sizeof name, "%.*s", MID_LINE_CHARS - 2 - 1 - (int)strlen(b), lane_name(label));
        for (char *c = name; *c; ++c) {     /* '_' stands for a space (S8) */
          if (*c == '_') *c = ' ';
        }
        {
          const fm1_tft_span_t sp[2] = { { n, C_LABEL }, { name, C_TEXT } };
          fm1_tft_span_text(t, MARGIN, y, sp, 2, MID_LINE_CHARS, FM1_TFT_MID);
        }
        fm1_tft_font_text(t, RIGHT - fm1_tft_font_width(b, 3, FM1_TFT_MID), y, b, 3, FM1_TFT_MID, C_TEXT);
      } else {
        const fm1_tft_span_t sp[2] = { { n, C_LABEL }, { "--", C_LABEL } };
        fm1_tft_span_text(t, MARGIN, y, sp, 2, MID_LINE_CHARS, FM1_TFT_MID);
      }
    }
    return;
  }
  snprintf(v, sizeof v, "Track %u of %u", (unsigned)u->track + 1u, (unsigned)u->tracks);
  fm1_look_context(t, CONTEXT_Y, v, NULL);
  if (u->route_kind == FM1_SEQ_ROUTE_ENGINE) {
    const unsigned k = u->route_index;
    const char *name = k < FM1_SEQ_UI_SOUNDS ? snd->unit_name[k] : NULL;
    step_row(t, 0, kRoute.name, "Sound", &kRoute, 0.0f, 1);
    /* The sound in its colour, its number beside it. */
    snprintf(v, sizeof v, "%u %.11s", k + 1u, k >= FM1_SEQ_UI_SOUNDS ? "none" : name ? name : "Empty");
    step_row_c(t, 1, kSound.name, v, &kSound, (float)k, k < FM1_SEQ_UI_SOUNDS,
               k < FM1_SEQ_UI_SOUNDS ? fm1_sound_colour((int)k) : 0);
  } else {
    step_row(t, 0, kRoute.name, "MIDI out", &kRoute, 1.0f, 1);
    snprintf(v, sizeof v, "%u", (unsigned)u->route_index);
    step_row(t, 1, kChannel.name, v, &kChannel, (float)u->route_index, 1);
  }
  {
    const int muted = focused_muted(u);
    step_row(t, 2, kMute.name, muted ? "On" : "Off", &kMute, (float)muted, 1);
  }
}

/* ---- Session (S9) and the Song page (S9+; notes/2026-10-06-song-and-scenes.md §6) ---- */

void fm1_seq_view_scene(const fm1_seq_t *s, unsigned scene, char *buf, size_t size) {
  const char *name = s && scene < FM1_SEQ_SCENES ? fm1_seq_scene_name(s, (uint8_t)scene) : "";
  if (name[0]) snprintf(buf, size, "%u %.6s", scene + 1u, name);
  else snprintf(buf, size, "Scene %u", scene + 1u);
}

/* Session's geometry: the scene header under the status line, the grid of
 * 8 slots a track (columns SESS_COL apart, cells SESS_CELL_W wide; rows 16
 * px apart with cells 12 tall, or 30 and 26 with four tracks or fewer), the
 * tracks' numbers left of it, and the song band above the bottom bar. */
#define SESS_HEAD_Y 50
#define SESS_GRID_X 17
#define SESS_GRID_Y 67
#define SESS_COL 27
#define SESS_CELL_W 24
#define SESS_LABEL_X 5
#define SESS_BAND_Y 194                /* its ground, 20 px, on C_TITLE_BG */
#define SESS_BAND_H 20
#define SESS_BAND_TEXT_Y (SESS_BAND_Y + 3)
#define SESS_BAND_CHARS MID_LINE_CHARS /* "SONG " and 23 more */

typedef char fm1_seq_view_session_fits[SESS_GRID_X + 7 * SESS_COL + SESS_CELL_W + 1 <= RIGHT &&
                                       SESS_LABEL_X + FM1_TFT_SMALL_ADVANCE + 4 <= SESS_GRID_X - 1 &&
                                       SESS_HEAD_Y + FM1_TFT_SMALL_H + 4 <= SESS_GRID_Y - 1 &&
                                       SESS_GRID_Y + 7 * 16 + 12 + 1 + 4 <= SESS_BAND_TEXT_Y &&
                                       SESS_BAND_TEXT_Y + MID_LINE_H + 4 <= BOTTOM_Y ? 1 : -1];

static void sess_rows(const fm1_seq_ui_t *u, int *pitch, int *h) {
  const int few = u->tracks <= 4u;
  *pitch = few ? 30 : 16;
  *h = few ? 26 : 12;
}

/* One slot: empty, a clip (its top edge in the track's colour), playing
 * (filled, its place along the bottom), queued (clip and playing in turn)
 * or stopping (playing and empty in turn), every 0.25 s. */
static void sess_cell(fm1_tft_t *t, int x, int y, int h, int clip, int playing, int queued,
                      int stopping, unsigned pos, uint16_t c, int blink) {
  int look = !clip ? 0 : 1;                  /* 0 empty, 1 clip, 2 playing */
  if (playing) look = stopping ? (blink ? 2 : 0) : 2;
  else if (queued) look = blink ? 2 : 1;
  if (look == 0) {
    fm1_tft_frame(t, x, y, SESS_CELL_W, h, C_BAR_BG);
  } else if (look == 1) {
    fm1_tft_paint(t, x, y, SESS_CELL_W, h, C_BAR_BG);
    fm1_tft_paint(t, x, y, SESS_CELL_W, 2, c);
  } else {
    fm1_tft_paint(t, x, y, SESS_CELL_W, h, c);
    if (playing) fm1_tft_paint(t, x, y + h - 2, (int)((SESS_CELL_W * pos + 128u) / 256u), 2, C_TEXT);
  }
}

static void draw_band(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_t *s);

static void draw_session(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd) {
  const unsigned n = u->tracks < 8u ? u->tracks : 8u;
  int pitch, h;
  sess_rows(u, &pitch, &h);
  draw_status(t, u, snd);
  {                                          /* the scene header, 1-8 */
    const int lit = u->playing && u->song_len && u->song_follow && u->song_now < 8u;
    char d[8][2];
    fm1_tft_span_t sp[8];
    uint8_t lead[8];
    for (unsigned c = 0; c < 8u; ++c) {
      const int boxed = lit && c == u->song_now;
      d[c][0] = (char)('1' + c);
      d[c][1] = '\0';
      sp[c].s = d[c];
      sp[c].color = boxed ? C_BG : u->loop_held ? C_TEXT : C_LABEL;
      lead[c] = (uint8_t)(c ? SESS_COL - FM1_TFT_SMALL_ADVANCE : 0);
      if (boxed) {                           /* the playing scene, on a C_LIVE tile */
        fm1_tft_paint(t, SESS_GRID_X + (int)c * SESS_COL + SESS_CELL_W / 2 - 6, SESS_HEAD_Y - 1, 12,
                      FM1_TFT_SMALL_H + 2, C_LIVE);
      }
    }
    fm1_tft_span_text_lead(t, SESS_GRID_X + SESS_CELL_W / 2 - FM1_TFT_SMALL_ADVANCE / 2, SESS_HEAD_Y,
                           sp, lead, 8, 8, FM1_TFT_SMALL);
  }
  if (n) fm1_tft_graphic(t, SESS_GRID_X - 1, SESS_GRID_Y - 1, 7 * SESS_COL + SESS_CELL_W + 2,
                         (int)(n - 1u) * pitch + h + 2);
  for (unsigned k = 0; k < n; ++k) {
    const int y = SESS_GRID_Y + (int)k * pitch;
    const int focused = k == u->track, muted = (u->muted >> k) & 1u;
    uint16_t c;
    char tag[2];
    tag[0] = (char)('1' + k);
    tag[1] = '\0';
    track_tag(snd, k, &c);
    if (muted) c = C_LABEL;
    if (focused) {
      fm1_tft_paint(t, SESS_LABEL_X - 2, y + (h - FM1_TFT_SMALL_H) / 2 - 1, FM1_TFT_SMALL_ADVANCE + 4,
                    FM1_TFT_SMALL_H + 2, C_SELECT);
    }
    fm1_tft_font_text(t, SESS_LABEL_X, y + (h - FM1_TFT_SMALL_H) / 2, tag, 1, FM1_TFT_SMALL,
                      focused ? C_BG : c);
    for (unsigned sl = 0; sl < 8u; ++sl) {
      const int x = SESS_GRID_X + (int)sl * SESS_COL;
      const int clip = (u->sess_clips >> (8u * k + sl)) & 1u;
      const int playing = u->sess_play[k] == sl;
      sess_cell(t, x, y, h, clip, playing, u->sess_queue[k] == sl, playing && ((u->sess_stop >> k) & 1u),
                u->sess_pos[k], c, u->blink);
      if (u->sess_active[k] == sl) fm1_tft_frame(t, x - 1, y - 1, SESS_CELL_W + 2, h + 2, C_SELECT);
    }
  }
  draw_band(t, u, snd->seq);
}

/* The song band (§6.1): "SONG", one token per entry ("3", "3x2"), the
 * playing one framed in C_LIVE and the armed next one blinking, "END" or
 * "STOP" after the last when the song does not loop; '<' and '>' where
 * entries are out of the window, which keeps the playing and next entries
 * in view. */
static void draw_band(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_t *s) {
  char tok[SESS_BAND_CHARS][8];
  fm1_tft_span_t sp[SESS_BAND_CHARS];
  fm1_tft_paint(t, 0, SESS_BAND_Y, FM1_TFT_W, SESS_BAND_H, C_TITLE_BG);
  if (!u->song_len) {
    const fm1_tft_span_t hint[2] = {
      { "SONG  ", C_LABEL },
      { u->loop_held ? "keys 1-8: scenes" : "hold LOOP: scenes", u->loop_held ? C_HINT : C_LABEL },
    };
    fm1_tft_span_text(t, MARGIN, SESS_BAND_TEXT_Y, hint, 2, SESS_BAND_CHARS, FM1_TFT_MID);
    return;
  }
  {
    const int live = u->playing && u->song_follow && !u->song_parked;
    const unsigned entries = u->song_entries;
    unsigned focus = live && u->song_entry < entries ? u->song_entry : 0u, first, e, ns = 0;
    int chars, frame_at = -1, frame_len = 0, room = SESS_BAND_CHARS - 5;
    const unsigned next = u->song_jump < entries ? u->song_jump : u->song_entry + 1u;
    const char *end = u->song_end == FM1_SEQ_SONG_STOP ? "STOP" : u->song_end == FM1_SEQ_SONG_PARK ? "END" : NULL;
    first = focus ? focus - 1u : 0u;
    sp[ns].s = "SONG ";
    sp[ns++].color = live ? C_LIVE : C_LABEL;
    chars = 5;
    if (first) {
      snprintf(tok[ns], sizeof tok[ns], "< ");
      sp[ns].s = tok[ns];
      sp[ns++].color = C_LABEL;
      chars += 2;
      room -= 2;
    }
    for (e = first; e < entries; ++e) {
      fm1_seq_song_entry_t x;
      unsigned sc, pr;
      const int last = e + 1u == entries;
      char one[8];
      int len, need;
      memset(&x, 0, sizeof x);
      if (!s || !fm1_seq_song_entry(s, (uint8_t)e, &x) || ns + 3u >= SESS_BAND_CHARS) break;
      sc = x.scene;
      pr = x.presses;
      if (pr > 1u) snprintf(one, sizeof one, "%ux%u", sc + 1u, pr);
      else snprintf(one, sizeof one, "%u", sc + 1u);
      len = (int)strlen(one);
      /* room for this token, a space, and " >" if more follow, or the end */
      need = len + 1 + (last ? (end ? (int)strlen(end) : 0) : 2);
      if (need > room && e > focus + 1u) break;
      if (len + 1 > room) break;
      snprintf(tok[ns], sizeof tok[ns], "%s ", one);
      sp[ns].s = tok[ns];
      sp[ns].color = C_TEXT;
      if (live && e == u->song_entry) {
        sp[ns].color = C_LIVE;
        frame_at = chars;
        frame_len = len;
      } else if (live && u->song_armed && e == next) {
        sp[ns].color = u->blink ? C_LIVE : C_TEXT;
      }
      ++ns;
      chars += len + 1;
      room -= len + 1;
    }
    if (e < entries) {
      sp[ns].s = ">";
      sp[ns++].color = C_LABEL;
    } else if (end && room >= (int)strlen(end)) {
      sp[ns].s = end;
      sp[ns++].color = C_LABEL;
    }
    fm1_tft_span_text(t, MARGIN, SESS_BAND_TEXT_Y, sp, (int)ns, SESS_BAND_CHARS, FM1_TFT_MID);
    if (frame_at >= 0) {                     /* the playing entry, framed */
      fm1_tft_frame(t, MARGIN + frame_at * MID_ADVANCE - 3, SESS_BAND_Y + 1,
                    frame_len * MID_ADVANCE + 5, SESS_BAND_H - 2, C_LIVE);
    }
  }
}

/* ---- the Song page --------------------------------------------------------------- */

#define SONG_ROW_CHARS 27
#define SONG_LEGEND_Y 196
#define SONG_MORE_DOWN_Y (LIST_Y + (FM1_SEQ_UI_SONG_ROWS - 1) * LIST_PITCH_MID + MID_LINE_H + 4)

typedef char fm1_seq_view_song_fits[SONG_MORE_DOWN_Y + LIST_MARK_H + 4 <= SONG_LEGEND_Y &&
                                    SONG_LEGEND_Y + FM1_TFT_SMALL_H + 4 <= BOTTOM_Y &&
                                    LIST_X + SONG_ROW_CHARS * MID_ADVANCE <= FM1_TFT_W - LIST_X ? 1 : -1];

/* A time at the tempo: "1:06", from ten minutes "12m". */
static void song_time(uint32_t bars, uint32_t bpm_x100, char *buf, size_t size) {
  const uint64_t secs = bpm_x100 ? ((uint64_t)bars * 48000u + bpm_x100) / (2u * (uint64_t)bpm_x100) : 0u;
  if (secs >= 600u) snprintf(buf, size, "%um", (unsigned)(secs / 60u));
  else snprintf(buf, size, "%u:%02u", (unsigned)(secs / 60u), (unsigned)(secs % 60u));
}

static void song_mark(fm1_tft_t *t, int y, int up) {
  const int cx = FM1_TFT_W / 2;
  fm1_tft_graphic(t, cx - LIST_MARK_W / 2, y, LIST_MARK_W, LIST_MARK_H);
  for (int r = 0; r < LIST_MARK_H; ++r) {
    const int half = r * (LIST_MARK_W / 2) / (LIST_MARK_H - 1);
    fm1_tft_paint(t, cx - half, up ? y + r : y + LIST_MARK_H - 1 - r, 2 * half + 1, 1, C_SELECT);
  }
}

/* The playing entry's mark in the row's first column: a play triangle,
 * 4 px wide, drawn rather than a '>' so a two-digit entry number keeps
 * 4 px of room from it (a '>' glyph sat right against "41"). */
#define SONG_PLAY_W 4
#define SONG_PLAY_H 7
static void song_play_mark(fm1_tft_t *t, int x, int y, uint16_t color) {
  const int y0 = y + (MID_LINE_H - SONG_PLAY_H) / 2;
  fm1_tft_graphic(t, x, y0, SONG_PLAY_W, SONG_PLAY_H);
  for (int r = 0; r < SONG_PLAY_H; ++r) {
    const int w = r <= SONG_PLAY_H / 2 ? r + 1 : SONG_PLAY_H - r;
    fm1_tft_paint(t, x, y0 + r, w, 1, color);
  }
}

static void draw_song(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd) {
  const fm1_seq_t *s = snd->seq;
  const unsigned entries = u->song_entries;
  const int live = u->playing && u->song_follow && !u->song_parked && u->song_entry < entries;
  const unsigned next = u->song_jump < entries ? u->song_jump
                      : u->song_entry + 1u < entries ? u->song_entry + 1u
                      : u->song_end == FM1_SEQ_SONG_LOOP ? 0u : FM1_SEQ_NONE;
  char text[40], place[16], tm[8];
  {                                          /* the context line */
    static const char *const kEnd[3] = { "Loop", "Park", "Stop" };
    uint16_t pc = C_LABEL;
    song_time(s ? fm1_seq_song_bars(s) : 0u, u->bpm_x100, tm, sizeof tm);
    snprintf(text, sizeof text, "Song %s %s", tm, kEnd[u->song_end < 3u ? u->song_end : 0u]);
    place[0] = '\0';
    if (live) {
      snprintf(place, sizeof place, "%u/%u", (unsigned)u->song_entry + 1u, entries);
      pc = C_LIVE;
    } else if (u->song_cur < entries) {
      snprintf(place, sizeof place, "%u/%u", (unsigned)u->song_cur + 1u, entries);
    }
    fm1_tft_font_text(t, LIST_X, LIST_TITLE_Y, text, 18, FM1_TFT_MID, C_CONTEXT);
    if (place[0]) {
      fm1_tft_font_text(t, FM1_TFT_W - LIST_X - fm1_tft_font_width(place, 8, FM1_TFT_MID), LIST_TITLE_Y,
                        place, 8, FM1_TFT_MID, pc);
    }
  }
  if (!entries) {                            /* nothing yet: how to start (MAIN) */
    fm1_tft_text(t, MARGIN, CONTEXT_NEXT_Y + 4, "No song yet", LINE_CHARS, SCALE, C_HINT);
    fm1_tft_text(t, MARGIN, CONTEXT_NEXT_Y + 4 + LINE_PITCH, "Keys 1-8: add", LINE_CHARS, SCALE, C_HINT);
    fm1_tft_text(t, MARGIN, CONTEXT_NEXT_Y + 4 + 2 * LINE_PITCH, "or LOOP in Session", LINE_CHARS, SCALE,
                 C_HINT);
  } else {
    const int total = (int)entries + 1;      /* the entries and `+ add` */
    const int first = fm1_list_first(total, u->song_cur, FM1_SEQ_UI_SONG_ROWS);
    const int rows = total - first < FM1_SEQ_UI_SONG_ROWS ? total - first : FM1_SEQ_UI_SONG_ROWS;
    if (first > 0) song_mark(t, LIST_MORE_Y, 1);
    for (int r = 0; r < rows; ++r) {
      const unsigned e = (unsigned)(first + r);
      const int y = LIST_Y + r * LIST_PITCH_MID;
      const int cursor = e == u->song_cur;
      char f[6][16];
      fm1_tft_span_t sp[6];
      if (cursor) fm1_tft_paint(t, MARGIN, y - 2, RIGHT - MARGIN, LIST_PITCH_MID - 1, C_SELECT);
      if (e == entries) {
        const fm1_tft_span_t add = { "    + add", cursor ? C_BG : C_LABEL };
        fm1_tft_span_text(t, LIST_X, y, &add, 1, SONG_ROW_CHARS, FM1_TFT_MID);
        continue;
      }
      {
        fm1_seq_song_entry_t x;
        const int playing = live && e == u->song_entry;
        char sc[16], rep[8], bars[8];
        memset(&x, 0, sizeof x);
        if (s) fm1_seq_song_entry(s, (uint8_t)e, &x);
        if (x.empty) snprintf(sc, sizeof sc, "%u (end)", (unsigned)x.scene + 1u);
        else fm1_seq_view_scene(s, x.scene, sc, sizeof sc);
        /* The pass and the bar into it count from 1: before the entry's
         * first tick (0 in the core) it is on its first. */
        const unsigned pass = u->song_pass ? u->song_pass : 1u;
        const unsigned bar = u->song_pass_bar ? u->song_pass_bar : 1u;
        if (playing && x.presses > 9u) snprintf(rep, sizeof rep, "%u", pass);
        else if (playing) snprintf(rep, sizeof rep, "%u/%u", pass, (unsigned)x.presses);
        else snprintf(rep, sizeof rep, "x%u", (unsigned)x.presses);
        if (playing) snprintf(bars, sizeof bars, "%u/%u", bar, (unsigned)x.bars);
        else snprintf(bars, sizeof bars, "%ub", (unsigned)x.bars * x.presses);
        song_time(x.start_bar, u->bpm_x100, tm, sizeof tm);
        f[0][0] = '\0';                     /* the first column: song_play_mark */
        snprintf(f[1], sizeof f[1], "%2u ", e + 1u);
        snprintf(f[2], sizeof f[2], "%-8.8s ", sc);
        snprintf(f[3], sizeof f[3], "%-3.3s ", rep);
        snprintf(f[4], sizeof f[4], "%5.5s ", bars);
        snprintf(f[5], sizeof f[5], "%4.4s", tm);
        for (int k = 0; k < 6; ++k) sp[k].s = f[k];
        sp[0].color = C_LIVE;
        sp[1].color = live && u->song_armed && e == next ? (u->blink ? C_LIVE : C_LABEL) : C_LABEL;
        sp[2].color = x.empty ? C_LABEL : C_TEXT;
        sp[3].color = playing ? C_LIVE : C_TEXT;
        sp[4].color = playing ? C_LIVE : C_LABEL;
        sp[5].color = C_LABEL;
        if (cursor) {
          for (int k = 0; k < 6; ++k) sp[k].color = C_BG;
        }
        if (playing) song_play_mark(t, LIST_X, y, sp[0].color);
        fm1_tft_span_text(t, LIST_X + MID_ADVANCE, y, sp + 1, 5, SONG_ROW_CHARS - 1, FM1_TFT_MID);
      }
    }
    if (first + rows < total) song_mark(t, SONG_MORE_DOWN_Y, 0);
  }
  {                                          /* the knob legend, SMALL */
    const fm1_tft_span_t sp[8] = {
      { "K1 ", C_LABEL }, { "SCENE  ", C_HINT }, { "K2 ", C_LABEL }, { "REPEAT  ", C_HINT },
      { "K3 ", C_LABEL }, { "NAME  ", C_HINT }, { "K4 ", C_LABEL }, { "END", C_HINT },
    };
    fm1_tft_span_text(t, MARGIN, SONG_LEGEND_Y, sp, 8, SMALL_LINE_CHARS, FM1_TFT_SMALL);
  }
}

void fm1_seq_view_draw(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd) {
  if (u->view == FM1_SEQ_VIEW_SESSION) draw_session(t, u, snd);
  else if (u->view == FM1_SEQ_VIEW_SONG) draw_song(t, u, snd);
  else if (u->view == FM1_SEQ_VIEW_STEP && u->held_n) draw_step(t, u, snd);
  else if (u->view == FM1_SEQ_VIEW_SET) draw_set(t, u);
  else if (u->view == FM1_SEQ_VIEW_CLIP) draw_clip(t, u);
  else if (u->view == FM1_SEQ_VIEW_TRACKPG) draw_trackpg(t, u, snd);
  else draw_track(t, u, snd);
}

void fm1_seq_view_bottom(const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd, char *buf,
                         size_t size) {
  if (u->view == FM1_SEQ_VIEW_STEP && u->held_n && u->step_page >= FM1_SEQ_UI_STEP_PAGES) {
    snprintf(buf, size, "%d/%d Lock T%u", u->step_page - FM1_SEQ_UI_STEP_PAGES + 1,
             (int)u->lock_pages, (unsigned)u->track + 1u);
  } else if (u->view == FM1_SEQ_VIEW_STEP && u->held_n) {
    snprintf(buf, size, "%d/%d Step T%u", u->step_page + 1, FM1_SEQ_UI_STEP_PAGES,
             (unsigned)u->track + 1u);
  } else if (u->view == FM1_SEQ_VIEW_SET) {
    snprintf(buf, size, "1/1 Set");
  } else if (u->view == FM1_SEQ_VIEW_CLIP) {
    snprintf(buf, size, "1/1 Clip T%u", (unsigned)u->track + 1u);
  } else if (u->view == FM1_SEQ_VIEW_TRACKPG) {
    snprintf(buf, size, "%d/%d Track %u", u->track_page + 1, FM1_SEQ_UI_TRACK_PAGES,
             (unsigned)u->track + 1u);
  } else if (u->view == FM1_SEQ_VIEW_SESSION) {
    snprintf(buf, size, "Session T%u", (unsigned)u->track + 1u);
  } else if (u->view == FM1_SEQ_VIEW_SONG) {
    snprintf(buf, size, "Song T%u", (unsigned)u->track + 1u);
  } else {
    snprintf(buf, size, "%d/%d Seq T%u", snd->page + 1, snd->pages, (unsigned)u->track + 1u);
  }
}
