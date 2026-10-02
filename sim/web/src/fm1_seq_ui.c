/* fm1_seq_ui.c -- the sequencer's panel UI (fm1_seq_ui.h). C99, no heap.
 * MIT licence, like the rest of this repository.
 */
#include "fm1_seq_ui.h"

#include <string.h>

void fm1_seq_ui_init(fm1_seq_ui_t *u) {
  memset(u, 0, sizeof *u);
  u->view = FM1_SEQ_VIEW_TRACK;
  u->knob = -1;
}

void fm1_seq_ui_enter(fm1_seq_ui_t *u) { u->view = FM1_SEQ_VIEW_TRACK; }

/* The focused clip's steps 0..63 that hold a note: one pass over its notes. */
static uint64_t read_notes(const fm1_seq_t *s, uint8_t track, uint8_t slot, uint16_t count) {
  uint64_t m = 0;
  fm1_seq_note_info_t n;
  for (uint16_t i = 0; i < count; ++i) {
    if (fm1_seq_get_note(s, track, slot, i, &n) && n.step < FM1_SEQ_UI_GRID_STEPS) {
      m |= (uint64_t)1 << n.step;
    }
  }
  return m;
}

int fm1_seq_ui_sync(fm1_seq_ui_t *u, const fm1_seq_t *s, uint32_t gen) {
  fm1_seq_info_t i;
  fm1_seq_track_info_t tr;
  fm1_seq_clip_info_t c;
  const fm1_seq_ui_t was = *u;
  fm1_seq_get_info(s, &i);
  u->playing = i.playing;
  u->recording = i.recording;
  u->counting_in = i.counting_in;
  u->following = i.following;
  u->bpm_x100 = i.bpm_x100;
  u->master_tick = i.master_tick;
  if (u->track >= i.tracks) u->track = 0;
  memset(&tr, 0, sizeof tr);
  memset(&c, 0, sizeof c);
  tr.active = FM1_SEQ_NONE;
  tr.playing = FM1_SEQ_NONE;
  fm1_seq_get_track(s, u->track, &tr);
  u->slot = tr.active;
  if (tr.active < FM1_SEQ_SLOTS) fm1_seq_get_clip(s, u->track, tr.active, &c);
  u->length = c.length_steps;
  u->loop_start = c.loop_start;
  u->clip_playing = (uint8_t)(i.playing && c.length_steps && tr.playing == tr.active);
  u->step = u->clip_playing ? (uint16_t)(tr.pos_tick / FM1_SEQ_TICKS_PER_STEP) : 0;
  if (!u->notes_valid || u->notes_gen != gen || u->notes_track != u->track ||
      u->notes_slot != u->slot || u->notes_count != c.notes) {
    u->notes = u->slot < FM1_SEQ_SLOTS ? read_notes(s, u->track, u->slot, c.notes) : 0;
    u->notes_gen = gen;
    u->notes_track = u->track;
    u->notes_slot = u->slot;
    u->notes_count = c.notes;
    u->notes_valid = 1;
  }
  return was.playing != u->playing || was.recording != u->recording ||
         was.counting_in != u->counting_in || was.following != u->following ||
         was.bpm_x100 != u->bpm_x100 || was.slot != u->slot ||
         was.clip_playing != u->clip_playing || was.step != u->step ||
         was.loop_start != u->loop_start || was.length != u->length || was.notes != u->notes;
}

int fm1_seq_ui_button(fm1_seq_ui_t *u, int button, int down, uint64_t frame, int mode,
                      fm1_seq_cmd_t *out) {
  (void)frame;
  (void)mode;                       /* PLAY/STOP works in every mode */
  if (!down) return 0;
  if (button == FM1_BTN_PLAY) {
    fm1_seq_cmd_make(out, u->playing ? FM1_SEQ_V_STOP : FM1_SEQ_V_PLAY, 0, NULL);
    /* Until the next block's sync reads the core: a second press before
     * then is the other command, not the same one again. */
    u->playing = (uint8_t)!u->playing;
    return 1;
  }
  return 0;
}

void fm1_seq_ui_knob(fm1_seq_ui_t *u, int knob, uint64_t until) {
  if (knob < 0 || knob > 3) return;
  u->knob = (int8_t)knob;
  u->knob_until = until;
}

uint16_t fm1_seq_ui_key_leds(const fm1_seq_ui_t *u) {
  uint16_t m = 0;
  for (unsigned n = 0; n < FM1_APP_WHITE_KEYS; ++n) {
    const unsigned step = u->bar * 16u + n;
    int on = step < FM1_SEQ_UI_GRID_STEPS && ((u->notes >> step) & 1u) &&
             step >= u->loop_start && step < (unsigned)u->loop_start + u->length;
    if (u->clip_playing && u->step == step) on = !on;
    if (on) m = (uint16_t)(m | (1u << n));
  }
  return m;
}

void fm1_seq_cmd_make(fm1_seq_cmd_t *c, uint16_t verb, unsigned argc, const int64_t *arg) {
  memset(c, 0, sizeof *c);
  c->verb = verb;
  if (argc > FM1_SEQ_CMD_ARGS) argc = FM1_SEQ_CMD_ARGS;
  c->argc = (uint8_t)argc;
  for (unsigned k = 0; k < argc; ++k) {
    c->arg[k] = arg[k];
    c->valid |= 1u << k;
  }
  if (argc > 2) {
    /* fm1_seq_parse keeps the third token's text: its decimal digits here. */
    char digits[24];
    int n = 0, len = 0;
    uint64_t v = arg[2] < 0 ? (uint64_t)0 - (uint64_t)arg[2] : (uint64_t)arg[2];
    do {
      digits[n++] = (char)('0' + (int)(v % 10u));
      v /= 10u;
    } while (v);
    if (arg[2] < 0) c->text[len++] = '-';
    while (n && len < (int)FM1_SEQ_LABEL_MAX - 1) c->text[len++] = digits[--n];
    c->text[len] = '\0';
  }
}
