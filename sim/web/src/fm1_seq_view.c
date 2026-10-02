/* fm1_seq_view.c -- the sequencer's screens (fm1_seq_view.h). C99, no heap.
 * MIT licence, like the rest of this repository.
 */
#include "fm1_seq_view.h"

#include <stdio.h>
#include <string.h>

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
/* The tracks on the status line, centred between the tempo (at most
 * "300.00 BPM", 118 px from MARGIN) and the transport (4 characters, 46 px
 * to RIGHT), with 8 px clear on each side. */
#define TRACKS_X 132
#define TRACKS_Y (STATUS_Y + 2)
#define TRACK_W 5
#define TRACK_H 14
#define LEGEND_PITCH 22                /* SHIFT's legend, from GRID_Y */
#define LANE_PITCH 23                  /* Track page 2: eight lanes */

typedef char fm1_seq_view_tracks_fit[TRACKS_X >= MARGIN + 118 + 8 &&
                                     TRACKS_X + 8 * TRACK_W + 7 + 8 <= RIGHT - 46 ? 1 : -1];

typedef char fm1_seq_view_grid_fits[BOX_X >= 0 && BOX_X + BOX_W <= FM1_TFT_W &&
                                    GRID_Y + GRID_H < STRIP_Y ? 1 : -1];

static int col_x(unsigned col) {
  return GRID_X + (int)(col * (CELL_W + CELL_GAP) + (col / 4u) * (BEAT_GAP - CELL_GAP));
}

/* The transport on the right: REC while the focused track records (gold
 * through its count-in or while the take waits for the bar), STEP in step
 * record, else PLAY or STOP. */
static void draw_status(fm1_tft_t *t, const fm1_seq_ui_t *u) {
  char bpm[24];
  const int mine = u->rec_track == u->track;
  const int rec = mine && u->recording, count = mine && !u->recording && u->counting_in;
  const char *state = rec || count ? "REC" : u->srec ? "STEP" : u->playing ? "PLAY" : "STOP";
  snprintf(bpm, sizeof bpm, "%u.%02u BPM", (unsigned)(u->bpm_x100 / 100u),
           (unsigned)(u->bpm_x100 % 100u));
  fm1_tft_text(t, MARGIN, STATUS_Y, bpm, 10, SCALE, C_TEXT);
  fm1_tft_text(t, RIGHT - fm1_tft_text_width(state, 4, SCALE), STATUS_Y, state, 4, SCALE,
               rec || u->srec ? C_WARN : count ? C_MODEL : u->playing ? C_PLAY : C_DIM);
  /* The tracks (S6): the focused one gold, a muted one an outline. */
  if (u->tracks) {
    const unsigned n = u->tracks < 8u ? u->tracks : 8u;
    fm1_tft_graphic(t, TRACKS_X, TRACKS_Y, (int)n * (TRACK_W + 1) - 1, TRACK_H);
    for (unsigned k = 0; k < n; ++k) {
      const int x = TRACKS_X + (int)k * (TRACK_W + 1);
      const uint16_t c = k == u->track ? C_MODEL : C_ACCENT;
      if ((u->muted >> k) & 1u) fm1_tft_frame(t, x, TRACKS_Y, TRACK_W, TRACK_H, c);
      else fm1_tft_paint(t, x, TRACKS_Y, TRACK_W, TRACK_H, c);
    }
  }
}

/* One step's cell: a note filled, inside the loop or outlined outside it,
 * the playhead inverted; a muted track's notes dim. */
static void draw_cell(fm1_tft_t *t, int x, int y, int w, int h, int in_loop, int note, int head,
                      int muted) {
  if (in_loop) {
    const uint16_t c = note ? (head ? C_TEXT : (muted ? C_DIM : C_ACCENT))
                            : (head ? C_DIM : C_BAR_BG);
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
    if ((u->trigs >> g) & 1u) fm1_tft_paint(t, x + 2, y + CELL_H - TICK_H - 2, CELL_W - 4, TICK_H, C_SCOPE);
    if (step / 16u == u->bar && ((held >> col) & 1u)) {
      fm1_tft_frame(t, x - 1, y - 1, CELL_W + 2, CELL_H + 2, C_MODEL);
    }
    if (u->srec && step == u->srec_head) {   /* step record's head */
      fm1_tft_frame(t, x - 1, y - 1, CELL_W + 2, CELL_H + 2, C_WARN);
    }
  }
  {
    const int y = GRID_Y + (int)((u->bar % 4u) * (CELL_H + ROW_GAP));
    fm1_tft_paint(t, BOX_X, y, BRACKET_W, CELL_H, C_MODEL);
    fm1_tft_paint(t, BOX_X + BOX_W - BRACKET_W, y, BRACKET_W, CELL_H, C_MODEL);
  }
}

/* SHIFT held with no step held (S6): what SHIFT + white key N does, in the
 * grid's place, as Movy's step-shortcuts.ts has them. */
static void draw_legend(fm1_tft_t *t, const fm1_seq_ui_t *u) {
  char v[24];
  int y = GRID_Y;
  fm1_look_row(t, y, "Key 2", "Track page", C_TEXT); y += LEGEND_PITCH;
  fm1_look_row(t, y, "Key 3", "Clip page", C_TEXT); y += LEGEND_PITCH;
  fm1_look_row(t, y, "5 7 9", "Set page", C_TEXT); y += LEGEND_PITCH;
  fm1_look_row(t, y, "Key 6", u->metro ? "Metro on" : "Metro off", C_TEXT); y += LEGEND_PITCH;
  fm1_look_row(t, y, "Key 10", u->full_vel ? "Full vel on" : "Full vel off", C_TEXT);
  y += LEGEND_PITCH;
  snprintf(v, sizeof v, "Quant %u%%", (unsigned)u->clip_quant);
  fm1_look_row(t, y, "Key 16", v, C_TEXT);
}

static void draw_track(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd) {
  const int legend = u->shift && !u->srec && !u->held_n;
  draw_status(t, u);
  if (legend) {
    draw_legend(t, u);
  } else {
    draw_grid(t, u);
  }
  /* The knob strip: four bars, no text (O23 b). */
  for (int k = 0; !legend && snd->e && k < snd->n; ++k) {
    const fm1_param_t *p = &snd->e->params[snd->idx[k]];
    fm1_look_bar(t, GRID_X + k * (STRIP_W + STRIP_GAP), STRIP_Y, STRIP_W, STRIP_H, p,
                 snd->value[snd->idx[k]], k == u->knob ? C_TEXT : C_ACCENT);
  }
  /* The hint line: step record's head (SHIFT's jump while SEL is held),
   * SHIFT's shortcuts, the knob being turned or the bar the keys moved to,
   * else the sound's model. */
  if (u->srec && u->shift) {
    fm1_look_row(t, HINT_Y, "Keys", "move the head", C_MODEL);
  } else if (u->srec) {
    char v[24];
    if (u->srec_open && u->srec_tie) {
      snprintf(v, sizeof v, "%u-%u", (unsigned)u->srec_anchor + 1u,
               (unsigned)u->srec_anchor + u->srec_tie + 1u);
    } else {
      snprintf(v, sizeof v, "%u", (unsigned)u->srec_head + 1u);
    }
    fm1_look_row(t, HINT_Y, "Step rec", v, C_WARN);
  } else if (u->seq_held) {
    fm1_look_row(t, HINT_Y, "Keys 1-8", "pick track", C_MODEL);
  } else if (u->mute_held) {
    fm1_look_row(t, HINT_Y, "Keys 1-8", "mute", C_MODEL);
  } else if (u->hint == FM1_SEQ_HINT_BAR) {
    char v[24];
    const unsigned bars = u->length ? ((unsigned)u->loop_start + u->length + 15u) / 16u : 0u;
    if (u->bar < bars) snprintf(v, sizeof v, "%u of %u", (unsigned)u->bar + 1u, bars);
    else snprintf(v, sizeof v, "%u, empty", (unsigned)u->bar + 1u);
    fm1_look_row(t, HINT_Y, "Bar", v, C_TEXT);
  } else if (snd->e && u->hint == FM1_SEQ_HINT_KNOB && u->knob >= 0 && u->knob < snd->n) {
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

/* ---- the Step pages -------------------------------------------------------------- */

void fm1_seq_view_note_name(int note, char *buf, size_t size) {
  static const char *const kNames[12] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A",
                                          "A#", "B" };
  if (note < 0 || note > 127) {
    snprintf(buf, size, "--");
    return;
  }
  snprintf(buf, size, "%s%d", kNames[note % 12], note / 12 - 1);
}

/* A row as HOME draws one, with a bar for `p` at `v` unless p is NULL. */
static void step_row(fm1_tft_t *t, int row, const char *label, const char *value,
                     const fm1_param_t *p, float v, int known) {
  const int y = CONTENT_Y + LINE_PITCH + row * ROW_PITCH;
  fm1_look_row(t, y, label, value, known ? C_TEXT : C_DIM);
  if (p) {
    fm1_look_bar(t, MARGIN, y + BAR_DY, FM1_TFT_W - 2 * MARGIN, BAR_H, p, known ? v : p->min,
                 known ? C_ACCENT : C_BAR_BG);
  }
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
      fm1_tft_paint(t, x, STEPS_Y, CELL_W, STEPS_H, C_MODEL);
    } else if ((under >> n) & 1u) {
      fm1_tft_paint(t, x, STEPS_Y, CELL_W, STEPS_H, C_ACCENT);
      fm1_tft_paint(t, x, STEPS_Y + STEPS_H / 2 - 1, CELL_W, 2, C_MODEL);
    } else {
      draw_cell(t, x, STEPS_Y, CELL_W, STEPS_H, u->length && step >= u->loop_start && step < end,
                g < FM1_SEQ_UI_GRID_STEPS && ((u->notes >> g) & 1u),
                u->clip_playing && u->step == step, focused_muted(u));
    }
  }
}

static void draw_step(fm1_tft_t *t, const fm1_seq_ui_t *u) {
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
  if (u->shift) {
    fm1_tft_text(t, MARGIN, CONTENT_Y, "Keys add a pitch", LINE_CHARS, SCALE, C_MODEL);
  } else {
    if (u->held_n > 1) snprintf(line, sizeof line, "Step %u +%u", (unsigned)h->step + 1u,
                                (unsigned)u->held_n - 1u);
    else snprintf(line, sizeof line, "Step %u", (unsigned)h->step + 1u);
    fm1_tft_text(t, MARGIN, CONTENT_Y, line, LINE_CHARS, SCALE, C_MODEL);
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
    fm1_tft_text(t, MARGIN, STEPS_Y, "Tap SHIFT: clear", LINE_CHARS, SCALE, C_MODEL);
  } else {
    draw_steps(t, u);
  }
}

/* ---- the Set, Clip and Track pages (S6) ------------------------------------------ */

static void draw_set(fm1_tft_t *t, const fm1_seq_ui_t *u) {
  static const fm1_param_t kTempo = { "Tempo", FM1_PARAM_FLOAT, 20.0f, 300.0f, 120.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kSwing = { "Swing", FM1_PARAM_FLOAT, 50.0f, 80.0f, 50.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kQuant = { "Def quant", FM1_PARAM_FLOAT, 0.0f, 100.0f, 0.0f, NULL, 0, 0, 0, 0, "" };
  static const fm1_param_t kMetro = { "Metronome", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.0f, NULL, 0, 0, 0, 0, "" };
  char v[24];
  fm1_tft_text(t, MARGIN, CONTENT_Y, "Set: all tracks", LINE_CHARS, SCALE, C_MODEL);
  snprintf(v, sizeof v, "%u.%02u BPM", (unsigned)(u->bpm_x100 / 100u), (unsigned)(u->bpm_x100 % 100u));
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
  fm1_tft_text(t, MARGIN, CONTENT_Y, line, LINE_CHARS, SCALE, C_MODEL);
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
  if (u->track_page) {                       /* the lanes: label and 7-bit base */
    fm1_seq_track_info_t tr;
    memset(&tr, 0, sizeof tr);
    if (snd->seq) fm1_seq_get_track(snd->seq, u->track, &tr);
    for (unsigned lane = 0; lane < FM1_SEQ_LANES; ++lane) {
      const int y = CONTENT_Y + (int)lane * LANE_PITCH;
      const char *label = snd->seq ? fm1_seq_lane_label(snd->seq, u->track, (uint8_t)lane) : "";
      if (label[0]) {
        char b[8];
        snprintf(v, sizeof v, "%u %.13s", lane + 1u, lane_name(label));
        snprintf(b, sizeof b, "%u", (unsigned)tr.base[lane]);
        fm1_tft_text(t, MARGIN, y, v, 15, SCALE, C_TEXT);
        fm1_tft_text(t, RIGHT - fm1_tft_text_width(b, 3, SCALE), y, b, 3, SCALE, C_TEXT);
      } else {
        snprintf(v, sizeof v, "%u --", lane + 1u);
        fm1_tft_text(t, MARGIN, y, v, 15, SCALE, C_DIM);
      }
    }
    return;
  }
  snprintf(v, sizeof v, "Track %u of %u", (unsigned)u->track + 1u, (unsigned)u->tracks);
  fm1_tft_text(t, MARGIN, CONTENT_Y, v, LINE_CHARS, SCALE, C_MODEL);
  if (u->route_kind == FM1_SEQ_ROUTE_ENGINE) {
    const unsigned k = u->route_index;
    const char *name = k < FM1_SEQ_UI_SOUNDS ? snd->unit_name[k] : NULL;
    step_row(t, 0, kRoute.name, "Sound", &kRoute, 0.0f, 1);
    snprintf(v, sizeof v, "%u %.11s", k + 1u, k >= FM1_SEQ_UI_SOUNDS ? "none" : name ? name : "Empty");
    step_row(t, 1, kSound.name, v, &kSound, (float)k, k < FM1_SEQ_UI_SOUNDS);
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

void fm1_seq_view_draw(fm1_tft_t *t, const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd) {
  if (u->view == FM1_SEQ_VIEW_STEP && u->held_n) draw_step(t, u);
  else if (u->view == FM1_SEQ_VIEW_SET) draw_set(t, u);
  else if (u->view == FM1_SEQ_VIEW_CLIP) draw_clip(t, u);
  else if (u->view == FM1_SEQ_VIEW_TRACKPG) draw_trackpg(t, u, snd);
  else draw_track(t, u, snd);
}

void fm1_seq_view_bottom(const fm1_seq_ui_t *u, const fm1_seq_view_sound_t *snd, char *buf,
                         size_t size) {
  if (u->view == FM1_SEQ_VIEW_STEP && u->held_n) {
    snprintf(buf, size, "%d/%d Step T%u", u->step_page + 1, FM1_SEQ_UI_STEP_PAGES,
             (unsigned)u->track + 1u);
  } else if (u->view == FM1_SEQ_VIEW_SET) {
    snprintf(buf, size, "1/1 Set");
  } else if (u->view == FM1_SEQ_VIEW_CLIP) {
    snprintf(buf, size, "1/1 Clip T%u", (unsigned)u->track + 1u);
  } else if (u->view == FM1_SEQ_VIEW_TRACKPG) {
    snprintf(buf, size, "%d/%d Track %u", u->track_page + 1, FM1_SEQ_UI_TRACK_PAGES,
             (unsigned)u->track + 1u);
  } else {
    snprintf(buf, size, "%d/%d Seq T%u", snd->page + 1, snd->pages, (unsigned)u->track + 1u);
  }
}
