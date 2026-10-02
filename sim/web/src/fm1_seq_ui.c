/* fm1_seq_ui.c -- the sequencer's panel UI (fm1_seq_ui.h). C99, no heap.
 *
 * The gestures follow Movy's step editing (src/seq/step-edit.ts,
 * router-steps.ts and step-shortcuts.ts at 9190e79, MIT, megadake): a tap
 * toggles on release, a 300 ms hold edits instead, hold A and press B sets
 * A's length, steps pressed together are each entered, and an edit is one
 * command per held step, in press order. MIT licence, like the rest of
 * this repository.
 */
#include "fm1_seq_ui.h"

#include <string.h>

/* What a key's press did, so its release does the matching thing. */
enum {
  ROLE_NONE = 0,
  ROLE_STEP,                        /* a held step (fm1_seq_ui_t.held) */
  ROLE_LENGTH,                      /* hold A, press B: B's press set A's length */
  ROLE_PITCH,                       /* SHIFT + white key with steps held: addp */
  ROLE_SHORTCUT,                    /* SHIFT + white key, nothing held */
  ROLE_BLACK                        /* a black key's role, or none yet */
};

#define VEL_PER_DETENT 4            /* Movy's VEL_STEP */
#define NUDGE_COARSE 2              /* Movy's LEN_STEP, round(24 / 10) ticks */
#define NUDGE_FINE 1
#define DEFAULT_PITCH 60            /* O5: a tap with nothing played */
#define DEFAULT_VEL 100

const uint16_t fm1_seq_ui_length_ticks[FM1_SEQ_UI_LENGTHS] = {
  12, 24, 48, 96, 192,                                              /* 1/32 .. 1/2 */
  384, 768, 1152, 1536, 1920, 2304, 2688, 3072, 3456, 3840, 4224,   /* 1 .. 11 bars */
  4608, 4992, 5376, 5760, 6144,                                     /* 12 .. 16 bars */
};
const char *const fm1_seq_ui_length_names[FM1_SEQ_UI_LENGTHS] = {
  "1/32", "1/16", "1/8", "1/4", "1/2", "1 bar", "2 bars", "3 bars", "4 bars", "5 bars", "6 bars",
  "7 bars", "8 bars", "9 bars", "10 bars", "11 bars", "12 bars", "13 bars", "14 bars", "15 bars",
  "16 bars",
};
const uint8_t fm1_seq_ui_probs[FM1_SEQ_UI_PROBS] = { 100, 90, 80, 70, 60, 50, 40, 30, 20, 10 };

int fm1_seq_ui_length_index(uint32_t ticks) {
  int best = 0;
  uint32_t best_d = 0xFFFFFFFFu;
  for (int i = 0; i < FM1_SEQ_UI_LENGTHS; ++i) {
    const uint32_t v = fm1_seq_ui_length_ticks[i];
    const uint32_t d = v > ticks ? v - ticks : ticks - v;
    if (d < best_d) best_d = d, best = i;      /* the first of two equally near */
  }
  return best;
}

int fm1_seq_ui_prob_index(unsigned pct) {
  int best = 0;
  unsigned best_d = ~0u;
  for (int i = 0; i < FM1_SEQ_UI_PROBS; ++i) {
    const unsigned v = fm1_seq_ui_probs[i];
    const unsigned d = v > pct ? v - pct : pct - v;
    if (d < best_d) best_d = d, best = i;
  }
  return best;
}

/* B from 1 to 8, A from 1 to B: index b(b-1)/2 + a - 1. */
int fm1_seq_ui_cond_index(unsigned a, unsigned b) {
  if (b < 1 || b > 8 || a < 1 || a > b) return 0;
  return (int)(b * (b - 1u) / 2u + a - 1u);
}

void fm1_seq_ui_cond_pair(int index, unsigned *a, unsigned *b) {
  unsigned bb = 1;
  if (index < 0) index = 0;
  if (index >= FM1_SEQ_UI_CONDS) index = FM1_SEQ_UI_CONDS - 1;
  while ((int)(bb * (bb + 1u) / 2u) <= index) ++bb;
  *b = bb;
  *a = (unsigned)index - bb * (bb - 1u) / 2u + 1u;
}

static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

void fm1_seq_ui_init(fm1_seq_ui_t *u, float rate) {
  memset(u, 0, sizeof *u);
  u->view = FM1_SEQ_VIEW_TRACK;
  u->knob = -1;
  u->rate = rate > 1.0f ? (uint32_t)(rate + 0.5f) : 1u;
  u->hold_frames = (u->rate * 3u + 9u) / 10u;      /* ceil(0.3 x rate): 13,236 at 44,118 Hz */
}

void fm1_seq_ui_enter(fm1_seq_ui_t *u) { u->view = FM1_SEQ_VIEW_TRACK; }

/* ---- commands ------------------------------------------------------------------ */

static void emit(const fm1_seq_ui_emit_t *out, uint16_t verb, unsigned argc, const int64_t *arg) {
  fm1_seq_cmd_t c;
  fm1_seq_cmd_make(&c, verb, argc, arg);
  if (out && out->cmd) out->cmd(out->ctx, &c);
}

/* `verb t s s -1 v...` for every held step, in press order (Movy's forEach
 * over the held ranges, each one step). */
static void emit_held(fm1_seq_ui_t *u, const fm1_seq_ui_emit_t *out, uint16_t verb, unsigned n,
                      const int64_t *v) {
  for (int k = 0; k < u->held_n; ++k) {
    int64_t arg[8] = { u->track, u->held[k].step, u->held[k].step, -1, 0, 0, 0, 0 };
    for (unsigned i = 0; i < n && i < 4; ++i) arg[4 + i] = v[i];
    emit(out, verb, 4u + n, arg);
    u->held[k].flags |= FM1_SEQ_UI_HELD_GESTURED;
  }
  u->hold_valid = 0;
}

/* The steps held are edited: their releases toggle nothing, and the Step
 * page shows. */
static void gesture(fm1_seq_ui_t *u) {
  for (int k = 0; k < u->held_n; ++k) u->held[k].flags |= FM1_SEQ_UI_HELD_GESTURED;
  if (u->held_n) u->view = FM1_SEQ_VIEW_STEP;
}

/* The focused clip as the core holds it now. */
static int clip_now(const fm1_seq_ui_t *u, const fm1_seq_t *s, fm1_seq_clip_info_t *c) {
  fm1_seq_track_info_t tr;
  memset(c, 0, sizeof *c);
  if (!s || !fm1_seq_get_track(s, u->track, &tr) || tr.active >= FM1_SEQ_SLOTS) return -1;
  fm1_seq_get_clip(s, u->track, tr.active, c);
  return tr.active;
}

static int step_notes(const fm1_seq_ui_t *u, const fm1_seq_t *s, uint16_t step) {
  fm1_seq_clip_info_t c;
  fm1_seq_step_info_t p;
  const int slot = clip_now(u, s, &c);
  if (slot < 0 || !fm1_seq_get_page(s, u->track, (uint8_t)slot, step, 1, &p)) return 0;
  return p.notes;
}

/* A tap: `tog t s p1 v1 ...` with the chord last played, else note 60 at
 * velocity 100 (O5); every velocity 127 with full velocity. A step in the
 * hidden rest of a clip's last bar takes nothing, as Movy's toggleStep: the
 * core would refuse it, but the edit would still empty Capture. */
static void toggle(fm1_seq_ui_t *u, const fm1_seq_t *s, uint16_t step,
                   const fm1_seq_ui_emit_t *out) {
  int64_t arg[2 + 2 * FM1_SEQ_CHORD_MAX];
  unsigned n = 0;
  fm1_seq_clip_info_t c;
  const int slot = clip_now(u, s, &c);
  const unsigned end = (unsigned)c.loop_start + c.length_steps;
  if (slot >= 0 && c.length_steps && step >= end && step < (end + 15u) / 16u * 16u &&
      !step_notes(u, s, step)) {
    return;
  }
  arg[0] = u->track;
  arg[1] = step;
  for (unsigned k = 0; k < u->chord_n; ++k) {
    arg[2 + 2 * n] = u->chord[2 * k];
    arg[3 + 2 * n] = u->full_vel ? 127 : u->chord[2 * k + 1];
    ++n;
  }
  if (!n) {
    arg[2] = DEFAULT_PITCH;
    arg[3] = u->full_vel ? 127 : DEFAULT_VEL;
    n = 1;
  }
  emit(out, FM1_SEQ_V_TOG, 2u + 2u * n, arg);
}

/* ---- held steps ---------------------------------------------------------------- */

static int held_index(const fm1_seq_ui_t *u, uint16_t step) {
  for (int k = 0; k < u->held_n; ++k) {
    if (u->held[k].step == step) return k;
  }
  return -1;
}

static void hold_step(fm1_seq_ui_t *u, uint16_t step, int key, uint64_t frame) {
  fm1_seq_ui_held_t *h;
  if (u->held_n >= FM1_SEQ_UI_MAX_HELD || held_index(u, step) >= 0) return;
  h = &u->held[u->held_n++];
  memset(h, 0, sizeof *h);
  h->press = frame;
  h->step = step;
  h->key = (uint8_t)key;
  if (u->held_n >= 2) {
    /* Steps held together are each entered on release (Movy's co-press):
     * a time-only promotion of the first is undone; edits are not. */
    int edited = 0;
    for (int k = 0; k < u->held_n; ++k) {
      u->held[k].flags |= FM1_SEQ_UI_HELD_CO;
      edited |= u->held[k].flags & FM1_SEQ_UI_HELD_GESTURED;
    }
    if (!edited) u->view = FM1_SEQ_VIEW_TRACK;
  }
  u->hold_valid = 0;
}

static void drop_all_held(fm1_seq_ui_t *u) {
  u->held_n = 0;
  u->len_valid = 0;
  u->hold_valid = 0;
  u->view = FM1_SEQ_VIEW_TRACK;
}

void fm1_seq_ui_leave(fm1_seq_ui_t *u) {
  drop_all_held(u);
  for (int k = 0; k < FM1_APP_KEYS; ++k) {
    if (u->key_role[k] == ROLE_STEP) u->key_role[k] = ROLE_NONE;   /* releases do nothing */
  }
  u->hint = FM1_SEQ_HINT_NONE;
}

/* ---- sync ------------------------------------------------------------------------ */

/* The grid's bits for steps first..first+63: one pass of the page getter per
 * 16 steps, so the stack holds 16 step records. */
static void read_grid(fm1_seq_ui_t *u, const fm1_seq_t *s) {
  fm1_seq_step_info_t p[16];
  u->notes = 0;
  u->trigs = 0;
  if (u->slot >= FM1_SEQ_SLOTS) return;
  for (unsigned q = 0; q < FM1_SEQ_UI_GRID_STEPS; q += 16u) {
    if (!fm1_seq_get_page(s, u->track, u->slot, (uint16_t)(u->grid_first + q), 16, p)) return;
    for (unsigned k = 0; k < 16u; ++k) {
      if (p[k].notes) u->notes |= (uint64_t)1 << (q + k);
      if (p[k].trig) u->trigs |= (uint64_t)1 << (q + k);
    }
  }
}

/* The first held step: its first note (the lowest index, the one Movy shows)
 * and its trig row. */
static void read_hold(fm1_seq_ui_t *u, const fm1_seq_t *s) {
  fm1_seq_ui_hold_t *h = &u->hold;
  fm1_seq_clip_info_t c;
  fm1_seq_step_info_t p;
  const int slot = clip_now(u, s, &c);
  memset(h, 0, sizeof *h);
  h->step = u->held[0].step;
  h->prob = 100;
  h->cond_a = h->cond_b = 1;
  if (slot >= 0 && fm1_seq_get_page(s, u->track, (uint8_t)slot, h->step, 1, &p)) {
    h->prob = p.prob;
    h->cond_a = p.cond_a;
    h->cond_b = p.cond_b;
    h->inv = (p.trig & FM1_SEQ_TRIG_INV) != 0;
  }
  for (uint16_t i = 0; slot >= 0 && i < c.notes; ++i) {
    fm1_seq_note_info_t n;
    if (!fm1_seq_get_note(s, u->track, (uint8_t)slot, i, &n) || n.step != h->step) continue;
    if (!h->notes) {
      h->tick = n.tick;
      h->gate = n.gate;
      h->vel = n.vel;
      h->pitch = n.pitch;
    } else if (n.gate != h->gate) {
      h->gate_mixed = 1;
    }
    if (h->notes < 255) ++h->notes;
  }
  u->hold_valid = 1;
}

/* Movy's navigable bars: the loop's own, and one empty bar after it. */
static void bar_bounds(fm1_seq_ui_t *u) {
  if (!u->length) {
    u->bar_min = u->bar_max = 0;
  } else {
    const unsigned last = ((unsigned)u->loop_start + u->length - 1u) / 16u;
    u->bar_min = (uint8_t)(u->loop_start / 16u);
    u->bar_max = (uint8_t)(last + 1u < 15u ? last + 1u : 15u);
  }
  u->bar = (uint8_t)clampi(u->bar, u->bar_min, u->bar_max);
}

int fm1_seq_ui_sync(fm1_seq_ui_t *u, const fm1_seq_t *s, uint32_t gen, uint64_t frame) {
  fm1_seq_info_t i;
  fm1_seq_track_info_t tr;
  fm1_seq_clip_info_t c;
  const fm1_seq_ui_t was = *u;
  fm1_seq_get_info(s, &i);
  u->playing = i.playing;
  u->recording = i.recording;
  u->counting_in = i.counting_in;
  u->following = i.following;
  u->rec_track = i.rec_track;
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
  if (!u->held_n) bar_bounds(u);        /* a hold keeps its bar while the clip grows */
  u->grid_first = (uint16_t)(u->bar / 4u * FM1_SEQ_UI_GRID_STEPS);
  if (!u->notes_valid || u->notes_gen != gen || u->notes_track != u->track ||
      u->notes_slot != u->slot || u->notes_first != u->grid_first) {
    read_grid(u, s);
    u->notes_gen = gen;
    u->notes_track = u->track;
    u->notes_slot = u->slot;
    u->notes_first = u->grid_first;
    u->notes_valid = 1;
    u->hold_valid = 0;
  }
  if (u->held_n && !u->hold_valid) read_hold(u, s);
  /* One step held alone past the threshold opens its Step page. */
  if (u->held_n == 1 && !(u->held[0].flags & FM1_SEQ_UI_HELD_CO) &&
      frame - u->held[0].press >= u->hold_frames) {
    u->view = FM1_SEQ_VIEW_STEP;
  }
  if (u->hint != FM1_SEQ_HINT_NONE && frame >= u->hint_until) {
    u->hint = FM1_SEQ_HINT_NONE;
    u->knob = -1;
  }
  return was.playing != u->playing || was.recording != u->recording ||
         was.counting_in != u->counting_in || was.following != u->following ||
         was.bpm_x100 != u->bpm_x100 || was.slot != u->slot ||
         was.clip_playing != u->clip_playing || was.step != u->step ||
         was.loop_start != u->loop_start || was.length != u->length || was.notes != u->notes ||
         was.trigs != u->trigs || was.view != u->view || was.bar != u->bar ||
         was.hint != u->hint || was.knob != u->knob || was.rec_track != u->rec_track ||
         memcmp(&was.hold, &u->hold, sizeof u->hold) != 0;
}

/* ---- buttons ------------------------------------------------------------------- */

/* A SHIFT tap during a hold: the held steps' notes go (`del t s s -1`);
 * steps with nothing on them send nothing. */
static void clear_held(fm1_seq_ui_t *u, const fm1_seq_t *s, const fm1_seq_ui_emit_t *out) {
  for (int k = 0; k < u->held_n; ++k) {
    if (step_notes(u, s, u->held[k].step)) {
      int64_t arg[4] = { u->track, u->held[k].step, u->held[k].step, -1 };
      emit(out, FM1_SEQ_V_DEL, 4, arg);
    }
  }
  gesture(u);
  u->hold_valid = 0;
}

int fm1_seq_ui_button(fm1_seq_ui_t *u, const fm1_seq_t *s, int button, int down, uint64_t frame,
                      int mode, const fm1_seq_ui_emit_t *out) {
  (void)frame;
  if (button == FM1_BTN_SEL) {
    if (down && mode != FM1_MODE_FX) {
      u->shift = 1;
      u->shift_clean = 1;
      u->shift_on_hold = mode == FM1_MODE_SEQ && u->held_n > 0;
      if (u->shift_on_hold) u->view = FM1_SEQ_VIEW_STEP;   /* its legend shows there */
      return 1;
    }
    if (!down && u->shift) {
      if (u->shift_clean && u->shift_on_hold && u->held_n && mode == FM1_MODE_SEQ) {
        clear_held(u, s, out);
      }
      u->shift = 0;
      return 1;
    }
    return 0;
  }
  if (down) u->shift_clean = 0;              /* SHIFT was used for something else */
  if (!down) return 0;
  if (button == FM1_BTN_PLAY) {
    /* SHIFT + PLAY while playing restarts (D12 makes it a Stop and a Start). */
    const int restart = u->playing && u->shift;
    fm1_seq_cmd_t c;
    fm1_seq_cmd_make(&c, restart || !u->playing ? FM1_SEQ_V_PLAY : FM1_SEQ_V_STOP, 0, NULL);
    if (out && out->cmd) out->cmd(out->ctx, &c);
    /* Until the next block's sync reads the core: a second press before
     * then is the other command, not the same one again. */
    if (!restart) u->playing = (uint8_t)!u->playing;
    return 0;
  }
  if ((button == FM1_BTN_OCT_DOWN || button == FM1_BTN_OCT_UP) && mode == FM1_MODE_SEQ &&
      u->held_n) {
    const int64_t d = (button == FM1_BTN_OCT_UP ? 1 : -1) * (u->shift ? 12 : 1);
    emit_held(u, out, FM1_SEQ_V_ETRN, 1, &d);
    gesture(u);
    return 1;
  }
  return 0;
}

/* ---- keys ---------------------------------------------------------------------- */

static int white_index(int key) {
  for (int n = 0; n < FM1_APP_WHITE_KEYS; ++n) {
    if (fm1_white_key(n) == key) return n;
  }
  return -1;
}

int fm1_seq_ui_has_key(const fm1_seq_ui_t *u, int key) {
  return key >= 0 && key < FM1_APP_KEYS && ((u->keys_down >> key) & 1u);
}

/* Hold A (with a note) and press B after it: A's note ends with B (B - A + 1
 * steps); B again: with B's start (B - A steps), and so on (Movy's
 * setLengthTo). B at or before A: nothing. */
static void length_to(fm1_seq_ui_t *u, uint16_t b, const fm1_seq_ui_emit_t *out) {
  const uint16_t a = u->held[0].step;
  int at_end = 1;
  int64_t arg[5];
  if (b <= a) return;
  if (u->len_valid && u->len_a == a && u->len_b == b) at_end = !u->len_at_end;
  u->len_valid = 1;
  u->len_a = a;
  u->len_b = b;
  u->len_at_end = (uint8_t)at_end;
  arg[0] = u->track;
  arg[1] = a;
  arg[2] = a;
  arg[3] = -1;
  arg[4] = (int64_t)((at_end ? b - a + 1 : b - a) * FM1_SEQ_TICKS_PER_STEP);
  emit(out, FM1_SEQ_V_SLEN, 5, arg);
  gesture(u);
  u->hold_valid = 0;
}

static void black_down(fm1_seq_ui_t *u, int key, uint64_t frame, const fm1_seq_ui_emit_t *out) {
  const int dir = key == FM1_SEQ_UI_KEY_BAR_BACK ? -1 : (key == FM1_SEQ_UI_KEY_BAR_ON ? 1 : 0);
  if (!dir) return;                          /* LOOP, COPY, CLEAR ...: later stages */
  if (u->held_n) {
    const int64_t d = dir * (u->shift ? NUDGE_FINE : NUDGE_COARSE);
    emit_held(u, out, FM1_SEQ_V_ENUDGE, 1, &d);
    gesture(u);
    return;
  }
  u->bar = (uint8_t)clampi(u->bar + dir, u->bar_min, u->bar_max);
  u->hint = FM1_SEQ_HINT_BAR;
  u->knob = -1;
  u->hint_until = frame + 2u * u->rate;
}

static void white_down(fm1_seq_ui_t *u, const fm1_seq_t *s, int key, int n, int velocity,
                       uint64_t frame, int base_note, const fm1_seq_ui_emit_t *out) {
  const uint16_t step = (uint16_t)(u->bar * 16u + (unsigned)n);
  if (u->shift && u->held_n) {
    /* A pitch for every held step, in the octave the keys play now. */
    const int pitch = base_note + key;
    if (pitch >= 0 && pitch <= 127) {
      const int64_t v[2] = { pitch, u->full_vel ? 127 : clampi(velocity, 1, 127) };
      for (int k = 0; k < u->held_n; ++k) {
        const int64_t arg[5] = { u->track, u->held[k].step, u->held[k].step, v[0], v[1] };
        emit(out, FM1_SEQ_V_ADDP, 5, arg);
      }
      gesture(u);
      u->hold_valid = 0;
    }
    u->key_role[key] = ROLE_PITCH;
    return;
  }
  if (u->shift) {                            /* Movy's SHIFT + step shortcuts */
    if (n == FM1_SEQ_UI_FULL_VEL_KEY) {
      u->full_vel = (uint8_t)!u->full_vel;
      u->toast = u->full_vel ? FM1_SEQ_TOAST_FULL_VEL_ON : FM1_SEQ_TOAST_FULL_VEL_OFF;
    }
    u->key_role[key] = ROLE_SHORTCUT;
    return;
  }
  if (u->held_n == 1 && u->held[0].step != step && step_notes(u, s, u->held[0].step)) {
    length_to(u, step, out);                 /* B is never held, so never entered */
    u->key_role[key] = ROLE_LENGTH;
    return;
  }
  hold_step(u, step, key, frame);
  u->key_role[key] = ROLE_STEP;
}

static void white_up(fm1_seq_ui_t *u, const fm1_seq_t *s, int key, uint64_t frame,
                     const fm1_seq_ui_emit_t *out) {
  int k;
  for (k = 0; k < u->held_n && u->held[k].key != key; ++k) {}
  if (k == u->held_n) return;
  {
    const fm1_seq_ui_held_t h = u->held[k];
    const int tap = !(h.flags & FM1_SEQ_UI_HELD_GESTURED) &&
                    ((h.flags & FM1_SEQ_UI_HELD_CO) || frame - h.press < u->hold_frames);
    memmove(&u->held[k], &u->held[k + 1], (size_t)(u->held_n - k - 1) * sizeof u->held[0]);
    --u->held_n;
    u->len_valid = 0;                        /* Movy: a held step's release ends the toggle */
    u->hold_valid = 0;
    if (!u->held_n) u->view = FM1_SEQ_VIEW_TRACK;
    if (tap) toggle(u, s, h.step, out);
  }
}

int fm1_seq_ui_key(fm1_seq_ui_t *u, const fm1_seq_t *s, int key, int down, int velocity,
                   uint64_t frame, int mode, int base_note, const fm1_seq_ui_emit_t *out) {
  if (key < 0 || key >= FM1_APP_KEYS) return 0;
  if (!down) {
    const int role = u->key_role[key];
    if (!fm1_seq_ui_has_key(u, key)) return 0;
    u->keys_down &= ~(1u << key);
    u->key_role[key] = ROLE_NONE;
    if (role == ROLE_STEP) white_up(u, s, key, frame, out);
    return 1;
  }
  if (mode != FM1_MODE_SEQ || fm1_seq_ui_has_key(u, key)) return mode == FM1_MODE_SEQ;
  u->keys_down |= 1u << key;
  u->shift_clean = 0;
  {
    const int n = white_index(key);
    if (n < 0) {
      u->key_role[key] = ROLE_BLACK;
      black_down(u, key, frame, out);
    } else {
      white_down(u, s, key, n, velocity, frame, base_note, out);
    }
  }
  return 1;
}

/* ---- encoders ------------------------------------------------------------------ */

/* Step page 1: VEL, LEN, PROB, COND; page 2: INV (KNOB1). One command per
 * held step, as Movy's editStepPageKnob; the values a detent moves from are
 * the first held step's, read now. */
static void step_knob(fm1_seq_ui_t *u, const fm1_seq_t *s, int knob, int delta,
                      const fm1_seq_ui_emit_t *out) {
  int64_t v[2];
  if (!u->hold_valid) read_hold(u, s);
  if (u->step_page == 1) {
    if (knob == 0) {                         /* INV: on with a turn up, off down */
      v[0] = delta > 0;
      emit_held(u, out, FM1_SEQ_V_EINV, 1, v);
    }
    return;                                  /* the nudge and note are read-outs */
  }
  switch (knob) {
    case 0:                                  /* VEL: relative, so a chord keeps its spread */
      v[0] = (int64_t)delta * VEL_PER_DETENT;
      emit_held(u, out, FM1_SEQ_V_EVEL, 1, v);
      break;
    case 1:                                  /* LEN: the next length on Movy's list */
      v[0] = fm1_seq_ui_length_ticks[clampi(fm1_seq_ui_length_index(u->hold.gate) + delta, 0,
                                            FM1_SEQ_UI_LENGTHS - 1)];
      emit_held(u, out, FM1_SEQ_V_SLEN, 1, v);
      break;
    case 2:                                  /* PROB: the list descends, so up is - */
      v[0] = fm1_seq_ui_probs[clampi(fm1_seq_ui_prob_index(u->hold.prob) - delta, 0,
                                     FM1_SEQ_UI_PROBS - 1)];
      emit_held(u, out, FM1_SEQ_V_EPROB, 1, v);
      break;
    default: {                               /* COND */
      unsigned a, b;
      fm1_seq_ui_cond_pair(fm1_seq_ui_cond_index(u->hold.cond_a, u->hold.cond_b) + delta, &a, &b);
      v[0] = a;
      v[1] = b;
      emit_held(u, out, FM1_SEQ_V_ECOND, 2, v);
      break;
    }
  }
}

int fm1_seq_ui_encoder(fm1_seq_ui_t *u, const fm1_seq_t *s, int encoder, int delta,
                       uint64_t frame, int mode, const fm1_seq_ui_emit_t *out) {
  (void)frame;
  u->shift_clean = 0;
  if (mode != FM1_MODE_SEQ || !u->held_n || delta == 0) return 0;
  if (encoder == FM1_ENC_SELECT) {
    u->step_page = (uint8_t)clampi(u->step_page + (delta > 0 ? 1 : -1), 0,
                                   FM1_SEQ_UI_STEP_PAGES - 1);
    gesture(u);
    return 1;
  }
  if (encoder >= FM1_ENC_KNOB1 && encoder <= FM1_ENC_KNOB4) {
    /* Held step + SHIFT + a detent is `aclrs` on the lock pages (S8); the
     * Step pages have no lanes, so it does nothing here. */
    if (!u->shift) step_knob(u, s, encoder - FM1_ENC_KNOB1, delta, out);
    gesture(u);
    return 1;
  }
  return 0;                                  /* PRESETS and ALGORITHM: the sound */
}

/* ---- notes --------------------------------------------------------------------- */

static void sounding_remove(fm1_seq_ui_t *u, int pitch) {
  for (int k = 0; k < u->sounding_n; ++k) {
    if (u->sounding[2 * k] == pitch) {
      memmove(&u->sounding[2 * k], &u->sounding[2 * k + 2], (size_t)(u->sounding_n - k - 1) * 2u);
      --u->sounding_n;
      return;
    }
  }
}

void fm1_seq_ui_note(fm1_seq_ui_t *u, int pitch, int velocity, int mode,
                     const fm1_seq_ui_emit_t *out) {
  if (pitch < 0 || pitch > 127) return;
  if (velocity <= 0) {                       /* a release touches nothing SHIFT does */
    sounding_remove(u, pitch);
    return;
  }
  u->shift_clean = 0;
  velocity = clampi(velocity, 1, 127);
  if (mode == FM1_MODE_SEQ && u->held_n) {
    for (int k = 0; k < u->held_n; ++k) {
      const int64_t arg[5] = { u->track, u->held[k].step, u->held[k].step, pitch,
                               u->full_vel ? 127 : velocity };
      emit(out, FM1_SEQ_V_ADDP, 5, arg);
    }
    gesture(u);
    u->hold_valid = 0;
    return;
  }
  /* The chord a tap writes: every note held as this one goes down. */
  sounding_remove(u, pitch);
  if (u->sounding_n >= FM1_SEQ_CHORD_MAX) {   /* the oldest makes way */
    memmove(&u->sounding[0], &u->sounding[2], (size_t)(FM1_SEQ_CHORD_MAX - 1) * 2u);
    --u->sounding_n;
  }
  u->sounding[2 * u->sounding_n] = (uint8_t)pitch;
  u->sounding[2 * u->sounding_n + 1] = (uint8_t)velocity;
  ++u->sounding_n;
  memcpy(u->chord, u->sounding, sizeof u->chord);
  u->chord_n = u->sounding_n;
}

void fm1_seq_ui_notes_off(fm1_seq_ui_t *u) { u->sounding_n = 0; }

void fm1_seq_ui_knob(fm1_seq_ui_t *u, int knob, uint64_t until) {
  if (knob < 0 || knob > 3) return;
  u->knob = (int8_t)knob;
  u->hint = FM1_SEQ_HINT_KNOB;
  u->hint_until = until;
}

/* ---- LEDs ---------------------------------------------------------------------- */

uint16_t fm1_seq_ui_held_mask(const fm1_seq_ui_t *u) {
  uint16_t m = 0;
  for (int k = 0; k < u->held_n; ++k) {
    const unsigned st = u->held[k].step;
    if (st / 16u == u->bar) m = (uint16_t)(m | (1u << (st % 16u)));
  }
  return m;
}

uint16_t fm1_seq_ui_under_mask(const fm1_seq_ui_t *u) {
  uint16_t m = 0;
  if (!u->held_n || !u->hold_valid || !u->hold.notes) return 0;
  {
    const uint32_t end = (uint32_t)u->hold.tick + u->hold.gate;   /* exclusive, in ticks */
    for (unsigned n = 0; n < 16u; ++n) {
      const uint32_t st = u->bar * 16u + n;
      if (st > u->hold.step && st * FM1_SEQ_TICKS_PER_STEP < end) m = (uint16_t)(m | (1u << n));
    }
  }
  return m;
}

uint32_t fm1_seq_ui_key_leds(const fm1_seq_ui_t *u, uint64_t frame) {
  uint32_t m = 0;
  const uint16_t held = fm1_seq_ui_held_mask(u), under = fm1_seq_ui_under_mask(u);
  const int slow_on = (frame % u->rate) < u->rate / 2u;    /* the 1 s blink */
  for (unsigned n = 0; n < FM1_APP_WHITE_KEYS; ++n) {
    const unsigned step = u->bar * 16u + n, g = step - u->grid_first;
    int on = g < FM1_SEQ_UI_GRID_STEPS && ((u->notes >> g) & 1u) && step >= u->loop_start &&
             step < (unsigned)u->loop_start + u->length;
    if (u->clip_playing && u->step == step) on = !on;
    if ((under >> n) & 1u) on = slow_on;
    if ((held >> n) & 1u) on = 1;
    if (on) m |= 1u << fm1_white_key((int)n);
  }
  if (u->held_n || u->bar > u->bar_min) m |= 1u << FM1_SEQ_UI_KEY_BAR_BACK;
  if (u->held_n || u->bar < u->bar_max) m |= 1u << FM1_SEQ_UI_KEY_BAR_ON;
  return m;
}

/* ---- typed commands -------------------------------------------------------------- */

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
