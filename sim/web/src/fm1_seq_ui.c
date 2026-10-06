/* fm1_seq_ui.c -- the sequencer's panel UI (fm1_seq_ui.h). C99, no heap.
 *
 * The gestures follow Movy's step editing (src/seq/step-edit.ts,
 * router-steps.ts and step-shortcuts.ts at 9190e79, MIT, megadake): a tap
 * toggles on release, a 300 ms hold edits instead, hold A and press B sets
 * A's length, steps pressed together are each entered, and an edit is one
 * command per held step, in press order. The pages and shortcuts of S6
 * follow its main-page.ts, clip-page.ts, step-shortcuts.ts and quant.ts,
 * and its mute (router-buttons.ts, router-steps.ts), without solo (owner
 * decision O12). MIT licence, like the rest of this repository.
 */
#include "fm1_seq_ui.h"

#include <string.h>

#include "fm1_seq_host.h"

/* What a key's press did, so its release does the matching thing. */
enum {
  ROLE_NONE = 0,
  ROLE_STEP,                        /* a held step (fm1_seq_ui_t.held) */
  ROLE_LENGTH,                      /* hold A, press B: B's press set A's length */
  ROLE_PITCH,                       /* SHIFT + white key with steps held: addp */
  ROLE_SHORTCUT,                    /* SHIFT + white key, nothing held */
  ROLE_BLACK,                       /* a black key's role, or none yet */
  ROLE_SREC,                        /* step record: a pitch at the head */
  ROLE_MUTE,                        /* MUTE: a tap mutes the focused track on release */
  ROLE_CLEAR                        /* CLEAR (S8): held, a knob detent clears a lane */
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
const uint8_t fm1_seq_ui_speeds[FM1_SEQ_UI_SPEEDS][2] = {
  { 1, 8 }, { 1, 4 }, { 1, 2 }, { 3, 4 }, { 1, 1 }, { 3, 2 }, { 2, 1 }, { 4, 1 },
};
const uint8_t fm1_seq_ui_quants[FM1_SEQ_UI_QUANTS] = { 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100 };

int fm1_seq_ui_speed_index(unsigned num, unsigned den) {
  for (int i = 0; i < FM1_SEQ_UI_SPEEDS; ++i) {
    if (fm1_seq_ui_speeds[i][0] == num && fm1_seq_ui_speeds[i][1] == den) return i;
  }
  return FM1_SEQ_UI_SPEED_1X;
}

int fm1_seq_ui_quant_index(unsigned pct) {
  int best = 0;
  unsigned best_d = ~0u;
  for (int i = 0; i < FM1_SEQ_UI_QUANTS; ++i) {
    const unsigned v = fm1_seq_ui_quants[i];
    const unsigned d = v > pct ? v - pct : pct - v;
    if (d < best_d) best_d = d, best = i;            /* the first of two equally near */
  }
  return best;
}

/* Movy's quantCandidates and nextQuantCandidate: 0, the default, 100 (two
 * when the default is an end), the next above `pct`, wrapping. */
unsigned fm1_seq_ui_next_quant(unsigned pct, unsigned def) {
  const unsigned d = def > 100u ? 100u : def;
  if (pct < d && d != 100u) return d;
  if (pct < 100u) return 100u;
  return 0u;
}

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
  u->tap_frames = (u->rate + 1u) / 2u;             /* ceil(0.5 x rate): 22,059 */
  u->take_idle = (u->rate * 3u + 4u) / 5u;         /* ceil(0.6 x rate): 26,471 */
  u->snap = -1;
  u->take_param = -1;
}

void fm1_seq_ui_enter(fm1_seq_ui_t *u) { u->view = FM1_SEQ_VIEW_TRACK; }

static int is_page(int view) {
  return view == FM1_SEQ_VIEW_SET || view == FM1_SEQ_VIEW_CLIP || view == FM1_SEQ_VIEW_TRACKPG;
}

void fm1_seq_ui_open(fm1_seq_ui_t *u, int view) {
  u->view = (uint8_t)(is_page(view) ? view : FM1_SEQ_VIEW_TRACK);
  u->hint = FM1_SEQ_HINT_NONE;
  u->knob = -1;
}

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

/* The held steps go with no toggle; keys still down stay the UI's until
 * released, so their releases do nothing. */
static void let_go_of_steps(fm1_seq_ui_t *u) {
  drop_all_held(u);
  for (int k = 0; k < FM1_APP_KEYS; ++k) {
    if (u->key_role[k] == ROLE_STEP) u->key_role[k] = ROLE_NONE;
  }
}

/* ---- step record (O8; Movy's step-rec.ts and step-rec-head.ts) --------------------- */

/* Leave step record (REC up, PLAY, leaving SEQ mode). Keys still down as
 * pitches keep sounding until released; their releases enter nothing. REC's
 * release after this is no tap. */
static void srec_end(fm1_seq_ui_t *u) {
  if (!u->srec) return;
  u->srec = 0;
  u->srec_open = 0;
  u->srec_chord_n = 0;
  u->srec_midi_n = 0;
  u->srec_keys = 0;
  u->srec_tie = 0;
  u->rec_touched = 1;
}

void fm1_seq_ui_leave(fm1_seq_ui_t *u) {
  let_go_of_steps(u);
  srec_end(u);
  u->hint = FM1_SEQ_HINT_NONE;
  u->mute_held = 0;                          /* MUTE's release then does nothing */
  u->clear_held = 0;                         /* nor CLEAR's */
}

/* The head moves (Movy's setHead): a fresh step, and the bar on the keys
 * follows it. */
static void srec_set_head(fm1_seq_ui_t *u, unsigned step) {
  if (step > FM1_SEQ_MAX_STEPS - 1u) step = FM1_SEQ_MAX_STEPS - 1u;
  u->srec_head = (uint16_t)step;
  u->srec_fresh = 1;
  u->bar = (uint8_t)(step / 16u);
}

/* Grow mode only (Movy's growTo): the clip takes in `step`. The core rounds
 * a clip up to its bar when a note lands past it, so this goes after the
 * write that caused it and trims the clip back to what was played; it never
 * shrinks it. */
static void srec_grow_to(fm1_seq_ui_t *u, unsigned step, const fm1_seq_ui_emit_t *out) {
  unsigned want = step + 1u;
  int64_t arg[2];
  if (!u->srec_grow) return;
  if (want > FM1_SEQ_MAX_STEPS) want = FM1_SEQ_MAX_STEPS;
  if (want <= u->srec_grown) return;
  u->srec_grown = (uint16_t)want;
  arg[0] = u->track;
  arg[1] = want;
  emit(out, FM1_SEQ_V_CLEN, 2, arg);
}

/* One step on (Movy's advanceHead): a new clip grows to take the step left;
 * an existing one wraps to its loop's start at its loop's end. Movy compares
 * the head with the loop's length instead, the same for a loop on bar 1. */
static void srec_advance(fm1_seq_ui_t *u, const fm1_seq_ui_emit_t *out) {
  unsigned next = u->srec_head + 1u;
  srec_grow_to(u, u->srec_head, out);
  if (u->srec_grow) {
    if (next >= FM1_SEQ_MAX_STEPS) next = 0;
  } else if (next >= (unsigned)u->loop_start + u->length) {
    next = u->loop_start;
  }
  srec_set_head(u, next);
}

/* REC down, stopped, in SEQ mode (Movy's headBegin): an empty clip grows to
 * what is played, a clip with a length wraps. The head starts on the loop's
 * first step (Movy parks it on step 1 whatever the loop; the same for every
 * loop that starts there). */
static void srec_begin(fm1_seq_ui_t *u) {
  let_go_of_steps(u);
  u->mute_held = 0;
  u->srec = 1;
  u->rec_touched = 0;
  u->srec_open = 0;
  u->srec_chord_n = 0;
  u->srec_midi_n = 0;
  u->srec_keys = 0;
  u->srec_tie = 0;
  u->srec_grow = u->length == 0;
  u->srec_grown = u->length;
  u->hint = FM1_SEQ_HINT_NONE;
  u->knob = -1;
  srec_set_head(u, u->srec_grow ? 0u : u->loop_start);
}

/* A pitch played (Movy's stepRecPad): onto the open chord's step, or a new
 * chord at the head. Its first pitch on a fresh step replaces what is there
 * (a melodic track's rule); a tied chord's later pitches take its length. */
static void srec_note_on(fm1_seq_ui_t *u, int pitch, int vel, const fm1_seq_ui_emit_t *out) {
  unsigned step;
  int64_t arg[5];
  u->rec_touched = 1;
  if (!u->srec_open) {
    u->srec_open = 1;
    u->srec_chord_n = 0;
    u->srec_anchor = u->srec_head;
    u->srec_tie = 0;
  }
  if (u->srec_chord_n >= FM1_SEQ_CHORD_MAX) return;   /* a `tog`'s 12 at most */
  step = u->srec_anchor;
  arg[0] = u->track;
  arg[1] = step;
  arg[2] = step;
  if (u->srec_chord_n == 0 && u->srec_fresh) {
    arg[3] = -1;
    emit(out, FM1_SEQ_V_DEL, 4, arg);
  }
  u->srec_fresh = 0;
  arg[3] = pitch;
  arg[4] = vel;
  emit(out, FM1_SEQ_V_ADDP, 5, arg);
  srec_grow_to(u, step, out);
  if (u->srec_tie) {
    arg[4] = (int64_t)(u->srec_tie + 1u) * FM1_SEQ_TICKS_PER_STEP;
    emit(out, FM1_SEQ_V_SLEN, 5, arg);
  }
  u->srec_chord[u->srec_chord_n++] = (uint8_t)pitch;
}

/* A key or note let go (Movy's stepRecPadRelease): when the last is up, the
 * chord closes and the head moves on by itself. */
static void srec_maybe_advance(fm1_seq_ui_t *u, const fm1_seq_ui_emit_t *out) {
  if (!u->srec || !u->srec_open || u->srec_keys || u->srec_midi_n) return;
  u->srec_open = 0;
  u->srec_chord_n = 0;
  u->srec_tie = 0;
  srec_advance(u, out);
}

/* A#3 (dir +1) and F#3 (-1) (Movy's stepRecArrow): with a chord open, tie it
 * into the next step or untie it, the head riding to the tied note's end;
 * with none, a rest, or a step back. */
static void srec_arrow(fm1_seq_ui_t *u, int dir, const fm1_seq_ui_emit_t *out) {
  u->rec_touched = 1;
  if (u->srec_open) {
    unsigned end;
    if (dir > 0 && u->srec_anchor + u->srec_tie + 1u < FM1_SEQ_MAX_STEPS) ++u->srec_tie;
    else if (dir < 0 && u->srec_tie > 0) --u->srec_tie;
    else return;
    for (unsigned k = 0; k < u->srec_chord_n; ++k) {
      const int64_t arg[5] = { u->track, u->srec_anchor, u->srec_anchor, u->srec_chord[k],
                               (int64_t)(u->srec_tie + 1u) * FM1_SEQ_TICKS_PER_STEP };
      emit(out, FM1_SEQ_V_SLEN, 5, arg);
    }
    end = (unsigned)u->srec_anchor + u->srec_tie;
    srec_grow_to(u, end, out);
    srec_set_head(u, end);                   /* the chord stays open */
    return;
  }
  if (dir > 0) srec_advance(u, out);
  else srec_set_head(u, u->srec_head ? u->srec_head - 1u : 0u);
}

/* SHIFT + white key (Movy's stepRecStepTap, its step buttons): the head goes
 * to that step of the bar, which is cleared if it had notes; past a clip's
 * end only while it grows. */
static void srec_jump(fm1_seq_ui_t *u, const fm1_seq_t *s, unsigned step,
                      const fm1_seq_ui_emit_t *out) {
  u->rec_touched = 1;
  if (!u->srec_grow && step >= (unsigned)u->loop_start + u->length) return;
  if (step_notes(u, s, (uint16_t)step)) {
    const int64_t arg[4] = { u->track, step, step, -1 };
    emit(out, FM1_SEQ_V_DEL, 4, arg);
  }
  srec_grow_to(u, step, out);
  srec_set_head(u, step);
}

int fm1_seq_ui_srec_can_go_back(const fm1_seq_ui_t *u) {
  return u->srec && (u->srec_open ? u->srec_tie > 0 : u->srec_head > 0);
}

/* ---- Capture (O7) ----------------------------------------------------------------- */

/* A press while the overlay is up closes it (`capdone`) and does nothing
 * else, as Movy's: a key that both closed it and wrote into the take just
 * captured is not worth the risk without undo. */
static int close_overlay(fm1_seq_ui_t *u, const fm1_seq_ui_emit_t *out) {
  emit(out, FM1_SEQ_V_CAPDONE, 0, NULL);
  u->capture_mode = FM1_SEQ_UI_CAPTURE_NONE;     /* until the next sync reads it */
  return 1;
}

/* SHIFT + REC: the notes buffered go into the focused track's clip; with
 * none, a toast (Movy's captureButton). The next sync says what it did. */
static void capture(fm1_seq_ui_t *u, const fm1_seq_ui_emit_t *out) {
  int64_t arg[1];
  if (!u->capture_pending) {
    u->toast = FM1_SEQ_TOAST_NOTHING;
    return;
  }
  arg[0] = u->track;
  emit(out, FM1_SEQ_V_CAP, 1, arg);
  u->cap_sent = 1;
  u->cap_gen_sent = u->capture_gen;
  u->capture_pending = 0;
}

int fm1_seq_ui_rec_led(const fm1_seq_ui_t *u, uint64_t frame, int held) {
  const uint32_t fast = u->rate / 4u ? u->rate / 4u : 1u;
  if (u->recording || u->srec) return 1;
  if (u->counting_in) return (frame % fast) < fast / 2u;
  if (u->capture_pending) return (frame % u->rate) < u->rate / 2u;
  return held != 0;
}

/* ---- tracks and mute (S6) -------------------------------------------------------- */

/* The focused track's route and its clip's settings, and every track's
 * mute, as the core holds them now. */
static void read_track(fm1_seq_ui_t *u, const fm1_seq_t *s) {
  fm1_seq_track_info_t tr;
  fm1_seq_clip_info_t c;
  u->muted = 0;
  for (unsigned t = 0; t < u->tracks && t < 16u; ++t) {
    if (fm1_seq_get_track(s, (uint8_t)t, &tr) && tr.muted) {
      u->muted = (uint16_t)(u->muted | (1u << t));
    }
  }
  memset(&tr, 0, sizeof tr);
  memset(&c, 0, sizeof c);
  tr.active = FM1_SEQ_NONE;
  fm1_seq_get_track(s, u->track, &tr);
  if (tr.active < FM1_SEQ_SLOTS) fm1_seq_get_clip(s, u->track, tr.active, &c);
  u->route_kind = tr.route_kind;
  u->route_index = tr.route_index;
  u->lanes = tr.lanes_assigned;
  u->clip_num = c.scale_num;
  u->clip_den = c.scale_den;
  u->clip_quant = c.quant;
  u->clip_tr = c.transpose;
}

static int track_muted(const fm1_seq_ui_t *u, unsigned t) {
  return t < 16u && ((u->muted >> t) & 1u);
}

/* `mute t 0|1`, and the mirror at once. */
static void set_mute(fm1_seq_ui_t *u, unsigned t, int on, const fm1_seq_ui_emit_t *out) {
  const int64_t arg[2] = { t, on ? 1 : 0 };
  emit(out, FM1_SEQ_V_MUTE, 2, arg);
  if (on) u->muted = (uint16_t)(u->muted | (1u << t));
  else u->muted = (uint16_t)(u->muted & ~(1u << t));
}

/* Focus track t: `watch t` (Capture follows the track, and empties), the
 * Track view of its clip from its first reachable bar, and the toast. The
 * focused track again sends nothing, so it keeps what Capture holds. */
static void focus(fm1_seq_ui_t *u, const fm1_seq_t *s, unsigned t, const fm1_seq_ui_emit_t *out) {
  int64_t arg[1];
  if (t >= u->tracks || t == u->track) return;
  arg[0] = t;
  emit(out, FM1_SEQ_V_WATCH, 1, arg);
  u->toast = u->capture_pending ? FM1_SEQ_TOAST_TRACK_EMPTIED : FM1_SEQ_TOAST_TRACK;
  u->toast_arg = (uint8_t)t;
  u->capture_pending = 0;
  let_go_of_steps(u);
  u->track = (uint8_t)t;
  u->bar = 0;
  u->notes_valid = 0;
  u->hint = FM1_SEQ_HINT_NONE;
  u->knob = -1;
  u->follow = 1;
  u->take_param = -1;
  if (s) read_track(u, s);
}

/* ---- sync ------------------------------------------------------------------------ */

/* The grid's bits for steps first..first+63: one pass of the page getter per
 * 16 steps, so the stack holds 16 step records. */
static void read_grid(fm1_seq_ui_t *u, const fm1_seq_t *s) {
  fm1_seq_step_info_t p[16];
  u->notes = 0;
  u->trigs = 0;
  u->locks = 0;
  if (u->slot >= FM1_SEQ_SLOTS) return;
  for (unsigned q = 0; q < FM1_SEQ_UI_GRID_STEPS; q += 16u) {
    if (!fm1_seq_get_page(s, u->track, u->slot, (uint16_t)(u->grid_first + q), 16, p)) return;
    for (unsigned k = 0; k < 16u; ++k) {
      if (p[k].notes) u->notes |= (uint64_t)1 << (q + k);
      if (p[k].trig) u->trigs |= (uint64_t)1 << (q + k);
      if (p[k].lock_mask) u->locks |= (uint64_t)1 << (q + k);
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
    h->lock_mask = p.lock_mask;
    memcpy(h->lock, p.lock, sizeof h->lock);
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
  u->capture_pending = i.capture_pending;
  u->capture_mode = i.capture_mode;
  u->capture_n = i.capture_n < 3 ? i.capture_n : 3;
  u->capture_sel = i.capture_sel;
  memcpy(u->capture_cands, i.capture_cands, sizeof u->capture_cands);
  u->capture_gen = i.capture_gen;
  if (u->cap_sent) {
    /* The `cap` sent at SHIFT + REC: a take written opens the core's overlay
     * (a stopped Capture's picker or fitted tempo) or says so. */
    u->cap_sent = 0;
    if (i.capture_gen == u->cap_gen_sent) u->toast = FM1_SEQ_TOAST_NOTHING;
    else if (i.capture_mode == FM1_SEQ_UI_CAPTURE_NONE) u->toast = FM1_SEQ_TOAST_CAPTURED;
  }
  if (u->srec && i.playing) srec_end(u);     /* a stopped-transport mode, as Movy's */
  if (u->track >= i.tracks) u->track = 0;
  u->tracks = i.tracks;
  u->swing = i.swing_pct;
  u->dq = i.default_quant;
  u->metro = i.metronome;
  read_track(u, s);
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
  /* A hold keeps its bar while the clip grows; step record's head takes
   * the bar with it. */
  if (!u->held_n && !u->srec) bar_bounds(u);
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
  /* A live take ends with its knob's pause, or with the recording. */
  if (u->take_param >= 0 &&
      (frame - u->take_frame >= u->take_idle || !u->playing || !u->recording)) {
    u->take_param = -1;
  }
  {
    const int overlay = was.capture_mode != u->capture_mode ||
                        (u->capture_mode && (was.capture_n != u->capture_n ||
                                             was.capture_sel != u->capture_sel ||
                                             was.bpm_x100 != u->bpm_x100 ||
                                             memcmp(was.capture_cands, u->capture_cands,
                                                    sizeof u->capture_cands) != 0));
    const int seq = was.playing != u->playing || was.recording != u->recording ||
                    was.counting_in != u->counting_in || was.following != u->following ||
                    was.bpm_x100 != u->bpm_x100 || was.slot != u->slot ||
                    was.clip_playing != u->clip_playing || was.step != u->step ||
                    was.loop_start != u->loop_start || was.length != u->length ||
                    was.notes != u->notes || was.trigs != u->trigs || was.view != u->view ||
                    was.bar != u->bar || was.hint != u->hint || was.knob != u->knob ||
                    was.rec_track != u->rec_track || was.srec != u->srec ||
                    was.capture_pending != u->capture_pending ||
                    was.tracks != u->tracks || was.muted != u->muted || was.swing != u->swing ||
                    was.dq != u->dq || was.metro != u->metro || was.clip_num != u->clip_num ||
                    was.clip_den != u->clip_den || was.clip_quant != u->clip_quant ||
                    was.clip_tr != u->clip_tr || was.route_kind != u->route_kind ||
                    was.route_index != u->route_index || was.locks != u->locks ||
                    was.lanes != u->lanes || was.take_param != u->take_param ||
                    was.take_v != u->take_v ||
                    memcmp(&was.hold, &u->hold, sizeof u->hold) != 0;
    return (seq ? FM1_SEQ_UI_SYNC_SEQ : 0) | (overlay ? FM1_SEQ_UI_SYNC_OVERLAY : 0);
  }
}

/* ---- locks (S8) ------------------------------------------------------------------ */

int fm1_seq_ui_pages(const fm1_engine_t *e) {
  int pages = 1;
  for (uint16_t i = 0; e && i < e->n_params; ++i) {
    if (e->params[i].page + 1 > pages) pages = e->params[i].page + 1;
  }
  return e ? pages : 0;
}

int fm1_seq_ui_page_params(const fm1_engine_t *e, int page, int out[4]) {
  int n = 0;
  for (uint16_t i = 0; e && i < e->n_params && n < 4; ++i) {
    if (e->params[i].page == page) out[n++] = i;
  }
  return n;
}

int fm1_seq_ui_lane_of(const fm1_seq_t *s, unsigned track, const fm1_engine_t *e, int param) {
  for (unsigned lane = 0; s && e && lane < FM1_SEQ_LANES; ++lane) {
    const char *label = fm1_seq_lane_label(s, (uint8_t)track, (uint8_t)lane);
    if (label[0] && fm1_seq_lane_param(e, label) == param) return (int)lane;
  }
  return -1;
}

void fm1_seq_ui_lock_pages(fm1_seq_ui_t *u, int pages) {
  const int last = FM1_SEQ_UI_STEP_PAGES - 1 + (pages > 0 ? pages : 0);
  u->lock_pages = (uint8_t)(pages > 0 ? (pages < 255 ? pages : 255) : 0);
  if (u->step_page > last) u->step_page = (uint8_t)last;
}

static void toast(fm1_seq_ui_t *u, int what, int arg) {
  u->toast = (uint8_t)what;
  u->toast_arg = (uint8_t)arg;
}

/* `alabel t lane <label>`, as fm1_seq_parse reads it: two integers and the
 * label as the third token's text. */
static void emit_label(const fm1_seq_ui_emit_t *out, unsigned track, unsigned lane,
                       const char *label) {
  fm1_seq_cmd_t c;
  size_t n = strlen(label);
  memset(&c, 0, sizeof c);
  c.verb = FM1_SEQ_V_ALABEL;
  c.argc = 3;
  c.valid = 3u;
  c.arg[0] = track;
  c.arg[1] = lane;
  if (n > FM1_SEQ_LABEL_MAX - 1u) n = FM1_SEQ_LABEL_MAX - 1u;
  memcpy(c.text, label, n);                  /* NUL-terminated by the memset */
  if (out && out->cmd) out->cmd(out->ctx, &c);
}

/* The 7-bit base the core holds for a lane of the focused track. */
static unsigned lane_base(const fm1_seq_ui_t *u, const fm1_seq_t *s, int lane) {
  fm1_seq_track_info_t tr;
  if (!s || lane < 0 || !fm1_seq_get_track(s, u->track, &tr)) return 0;
  return tr.base[lane];
}

/* The held step's lock on a lane, read from the core now: 1 and its value,
 * else 0. */
static int step_lock(const fm1_seq_ui_t *u, const fm1_seq_t *s, uint16_t step, int lane,
                     unsigned *v) {
  fm1_seq_clip_info_t c;
  fm1_seq_step_info_t p;
  const int slot = clip_now(u, s, &c);
  if (lane < 0 || slot < 0 || !fm1_seq_get_page(s, u->track, (uint8_t)slot, step, 1, &p) ||
      !((p.lock_mask >> lane) & 1u)) {
    return 0;
  }
  *v = p.lock[lane];
  return 1;
}

/* A lane for parameter `param` of the lock sound on the focused track: its
 * own, or the first free one, labelled (the bridge resolves the label to
 * the parameter's uid) with the knob's value as its base, which the app then
 * puts on the 7-bit grid (snap) so the base and the knob agree to the bit
 * (Movy's assignLane: `alabel`, `abase`). -1, and the toast, when all 8 are
 * in use. */
static int lane_for(fm1_seq_ui_t *u, const fm1_seq_t *s, const fm1_seq_ui_sound_t *snd,
                    int param, const fm1_seq_ui_emit_t *out) {
  fm1_seq_track_info_t tr;
  const fm1_param_t *p = &snd->e->params[param];
  char label[FM1_SEQ_LABEL_MAX];
  int lane = fm1_seq_ui_lane_of(s, u->track, snd->e, param);
  if (lane >= 0) return lane;
  memset(&tr, 0, sizeof tr);
  fm1_seq_get_track(s, u->track, &tr);
  for (lane = 0; lane < (int)FM1_SEQ_LANES && ((tr.lanes_assigned >> lane) & 1u); ++lane) {}
  if (lane >= (int)FM1_SEQ_LANES) {
    toast(u, FM1_SEQ_TOAST_LANES_FULL, 0);
    return -1;
  }
  fm1_seq_lane_label_for(p, label, sizeof label);
  emit_label(out, u->track, (unsigned)lane, label);
  {
    const int64_t arg[3] = { u->track, lane, fm1_seq_value7(p, snd->value[param]) };
    emit(out, FM1_SEQ_V_ABASE, 3, arg);
  }
  u->lanes = (uint8_t)(u->lanes | (1u << lane));
  u->snap = (int8_t)param;
  return lane;
}

/* CLEAR + a knob detent: the lane of that parameter goes (`aclr`; D13 frees
 * it and D6 sends the parameter back to its base). Movy's clearLaneForKnob:
 * the gesture is CLEAR's whether or not there was a lane. */
static void clear_lane(fm1_seq_ui_t *u, const fm1_seq_t *s, const fm1_seq_ui_sound_t *snd,
                       int param, const fm1_seq_ui_emit_t *out) {
  const int lane = snd && snd->e ? fm1_seq_ui_lane_of(s, u->track, snd->e, param) : -1;
  if (lane >= 0) {
    const int64_t arg[2] = { u->track, lane };
    emit(out, FM1_SEQ_V_ACLR, 2, arg);
    u->lanes = (uint8_t)(u->lanes & ~(1u << lane));
    toast(u, FM1_SEQ_TOAST_LANE_CLEARED, param);
    if (u->take_param == param) u->take_param = -1;
  }
}

/* A knob on a lock page with one step held: KNOB n is the n-th parameter of
 * the lock sound's page. A turn locks it on the step, quietly (Movy's
 * held-step lock, `aset t lane s v 1`): v moves a 7-bit step (a list's
 * entry) a detent from the step's lock, else the lane's base. SHIFT clears
 * the step's lock instead (`aclrs`), CLEAR the whole lane. */
static void lock_knob(fm1_seq_ui_t *u, const fm1_seq_t *s, const fm1_seq_ui_sound_t *snd, int knob,
                      int delta, const fm1_seq_ui_emit_t *out) {
  const uint16_t step = u->held[0].step;
  int idx[4], lane, param;
  unsigned seed = 0;
  gesture(u);
  if (!snd || !snd->e ||
      knob >= fm1_seq_ui_page_params(snd->e, u->step_page - FM1_SEQ_UI_STEP_PAGES, idx)) {
    return;
  }
  param = idx[knob];
  if (u->clear_held) {
    clear_lane(u, s, snd, param, out);
    return;
  }
  lane = fm1_seq_ui_lane_of(s, u->track, snd->e, param);
  if (u->shift) {
    if (step_lock(u, s, step, lane, &seed)) {
      const int64_t arg[3] = { u->track, lane, step };
      emit(out, FM1_SEQ_V_ACLRS, 3, arg);
      toast(u, FM1_SEQ_TOAST_LOCK_CLEARED, param);
      u->hold_valid = 0;
    }
    return;
  }
  if (!fm1_param_lockable(&snd->e->params[param])) {
    toast(u, FM1_SEQ_TOAST_NOLOCK, param);
    return;
  }
  if (lane < 0) {
    lane = lane_for(u, s, snd, param, out);
    if (lane < 0) return;
    seed = fm1_seq_value7(&snd->e->params[param], snd->value[param]);
  } else if (!step_lock(u, s, step, lane, &seed)) {
    seed = lane_base(u, s, lane);
  }
  {
    const int64_t arg[5] = { u->track, lane, step,
                             fm1_seq_value7_step(&snd->e->params[param], seed, delta), 1 };
    emit(out, FM1_SEQ_V_ASET, 5, arg);
  }
  u->hold_valid = 0;
}

int fm1_seq_ui_sound_knob(fm1_seq_ui_t *u, const fm1_seq_t *s, const fm1_seq_ui_sound_t *snd,
                          int param, int delta, uint64_t frame, const fm1_seq_ui_emit_t *out) {
  const int lock_sound = snd && snd->e && snd->current && param >= 0 && param < snd->e->n_params;
  u->shift_clean = 0;
  if (u->clear_held) {                       /* CLEAR + knob is CLEAR's gesture (Movy) */
    if (lock_sound) clear_lane(u, s, snd, param, out);
    return 1;
  }
  if (lock_sound && u->playing && u->recording && u->rec_track == u->track && u->clip_playing &&
      fm1_param_lockable(&snd->e->params[param])) {
    /* A live take (Movy's live record): a lock at the playing step, heard,
     * from the knob's value at the take's first detent on. */
    const fm1_param_t *p = &snd->e->params[param];
    const int lane = lane_for(u, s, snd, param, out);
    unsigned seed;
    if (lane < 0) return 1;
    seed = u->take_param == param && (unsigned)lane == u->take_lane &&
                   frame - u->take_frame < u->take_idle
               ? u->take_v
               : fm1_seq_value7(p, snd->value[param]);
    u->take_param = (int8_t)param;
    u->take_lane = (uint8_t)lane;
    u->take_v = (uint8_t)fm1_seq_value7_step(p, seed, delta);
    u->take_frame = frame;
    {
      const int64_t arg[4] = { u->track, lane, u->step, u->take_v };
      emit(out, FM1_SEQ_V_ASET, 4, arg);
    }
    return 1;
  }
  return 0;
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

/* REC: Capture with SHIFT; stopped in SEQ mode, step record while held and
 * `rec` on a quick untouched release (Movy's router.ts and step-rec.ts);
 * otherwise `rec` at once. */
static int rec_button(fm1_seq_ui_t *u, int down, uint64_t frame, int mode,
                      const fm1_seq_ui_emit_t *out) {
  const int64_t t = u->track;
  if (down) {
    u->rec_press = frame;
    if (u->shift && mode != FM1_MODE_FX) {
      u->rec_role = FM1_SEQ_UI_REC_CAPTURE;
      capture(u, out);
    } else if (!u->playing && mode == FM1_MODE_SEQ) {
      u->rec_role = FM1_SEQ_UI_REC_STEP;
      srec_begin(u);
    } else {
      u->rec_role = FM1_SEQ_UI_REC_SENT;
      emit(out, FM1_SEQ_V_REC, 1, &t);
    }
    return 1;
  }
  if (u->rec_role == FM1_SEQ_UI_REC_STEP) {
    const int tap = !u->rec_touched && frame - u->rec_press < u->tap_frames;
    srec_end(u);
    if (tap) emit(out, FM1_SEQ_V_REC, 1, &t);
  }
  u->rec_role = FM1_SEQ_UI_REC_NONE;
  return 1;
}

int fm1_seq_ui_button(fm1_seq_ui_t *u, const fm1_seq_t *s, int button, int down, uint64_t frame,
                      int mode, const fm1_seq_ui_emit_t *out) {
  if (down && u->capture_mode) {
    if (button == FM1_BTN_REC) u->rec_role = FM1_SEQ_UI_REC_NONE;   /* its release does nothing */
    u->shift_clean = 0;
    return close_overlay(u, out);
  }
  if (button == FM1_BTN_REC) {
    if (down) u->shift_clean = 0;
    return rec_button(u, down, frame, mode, out);
  }
  if (button == FM1_BTN_SEQ) {               /* held, the white keys focus tracks */
    u->seq_held = (uint8_t)(down != 0);
    if (down) {
      u->seq_gestured = 0;
      u->shift_clean = 0;
    }
    return 0;
  }
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
    srec_end(u);                             /* step record is a stopped-transport mode */
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

/* CLEAR (S8) with steps held: their locks go (`aclrstep`, one per held step
 * with a lock, in press order), their notes stay and their toggles are
 * cancelled (Movy's deleteButton with steps held). */
static void clear_held_steps(fm1_seq_ui_t *u, const fm1_seq_t *s, const fm1_seq_ui_emit_t *out) {
  int sent = 0;
  fm1_seq_clip_info_t c;
  const int slot = clip_now(u, s, &c);
  for (int k = 0; k < u->held_n && slot >= 0; ++k) {
    fm1_seq_step_info_t p;
    if (fm1_seq_get_page(s, u->track, (uint8_t)slot, u->held[k].step, 1, &p) && p.lock_mask) {
      const int64_t arg[2] = { u->track, u->held[k].step };
      emit(out, FM1_SEQ_V_ACLRSTEP, 2, arg);
      ++sent;
    }
  }
  gesture(u);
  u->hold_valid = 0;
  if (sent) toast(u, FM1_SEQ_TOAST_LOCKS_CLEARED, 0);
}

static void black_down(fm1_seq_ui_t *u, const fm1_seq_t *s, int key, uint64_t frame,
                       const fm1_seq_ui_emit_t *out) {
  const int dir = key == FM1_SEQ_UI_KEY_BAR_BACK ? -1 : (key == FM1_SEQ_UI_KEY_BAR_ON ? 1 : 0);
  if (key == FM1_SEQ_UI_KEY_CLEAR) {         /* CLEAR: held steps' locks; held, + knob */
    u->key_role[key] = ROLE_CLEAR;
    u->clear_held = 1;
    if (u->held_n) clear_held_steps(u, s, out);
    return;
  }
  if (key == FM1_SEQ_UI_KEY_MUTE) {          /* MUTE: held, the mute map; a tap, on release */
    if (!u->held_n) {
      u->mute_held = 1;
      u->mute_gestured = 0;
      u->key_role[key] = ROLE_MUTE;
    }
    return;
  }
  if (key == FM1_SEQ_UI_KEY_TRACK_PREV || key == FM1_SEQ_UI_KEY_TRACK_NEXT) {
    const int t = (int)u->track + (key == FM1_SEQ_UI_KEY_TRACK_NEXT ? 1 : -1);
    if (!u->held_n && t >= 0) focus(u, s, (unsigned)t, out);
    return;
  }
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
                       uint64_t frame, int pitch, const fm1_seq_ui_emit_t *out) {
  const uint16_t step = (uint16_t)(u->bar * 16u + (unsigned)n);
  if (u->shift && u->held_n) {
    /* A pitch for every held step: the note the key plays now (in the
     * octave the keys play, or a pad kit's pad). */
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
    switch (n) {
      case 1: fm1_seq_ui_open(u, FM1_SEQ_VIEW_TRACKPG); break;
      case 2: fm1_seq_ui_open(u, FM1_SEQ_VIEW_CLIP); break;
      case 4: case 6: case 8: fm1_seq_ui_open(u, FM1_SEQ_VIEW_SET); break;
      case 5: {                              /* the metronome */
        const int64_t v = !u->metro;
        emit(out, FM1_SEQ_V_METRO, 1, &v);
        u->metro = (uint8_t)v;
        u->toast = v ? FM1_SEQ_TOAST_METRO_ON : FM1_SEQ_TOAST_METRO_OFF;
        break;
      }
      case FM1_SEQ_UI_FULL_VEL_KEY:
        u->full_vel = (uint8_t)!u->full_vel;
        u->toast = u->full_vel ? FM1_SEQ_TOAST_FULL_VEL_ON : FM1_SEQ_TOAST_FULL_VEL_OFF;
        break;
      case 15: {                             /* the clip's quantize: 0, the default, 100 */
        const unsigned q = fm1_seq_ui_next_quant(u->clip_quant, u->dq);
        const int64_t arg[2] = { u->track, q };
        emit(out, FM1_SEQ_V_CQ, 2, arg);
        u->clip_quant = (uint8_t)q;
        u->toast = FM1_SEQ_TOAST_QUANT;
        u->toast_arg = (uint8_t)q;
        break;
      }
      default: break;                        /* key 15, double the loop, comes with S9 */
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
                   uint64_t frame, int mode, int pitch, const fm1_seq_ui_emit_t *out) {
  if (key < 0 || key >= FM1_APP_KEYS) return 0;
  if (!down) {
    const int role = u->key_role[key];
    if (!fm1_seq_ui_has_key(u, key)) return 0;
    u->keys_down &= ~(1u << key);
    u->key_role[key] = ROLE_NONE;
    if (role == ROLE_STEP) white_up(u, s, key, frame, out);
    if (role == ROLE_MUTE && u->mute_held) {   /* a tap: the focused track */
      u->mute_held = 0;
      if (!u->mute_gestured) set_mute(u, u->track, !track_muted(u, u->track), out);
    }
    if (role == ROLE_CLEAR) u->clear_held = 0;   /* a tap: the clip's delete comes with S9 */
    if (role == ROLE_SREC) {
      u->srec_keys &= ~(1u << key);
      srec_maybe_advance(u, out);
    }
    return 1;
  }
  if (fm1_seq_ui_has_key(u, key)) return mode == FM1_MODE_SEQ;
  if (u->capture_mode) {                     /* any mode: the press closes the overlay */
    u->keys_down |= 1u << key;
    u->key_role[key] = ROLE_NONE;
    u->shift_clean = 0;
    return close_overlay(u, out);
  }
  if (mode != FM1_MODE_SEQ) return 0;
  u->keys_down |= 1u << key;
  u->shift_clean = 0;
  {
    const int n = white_index(key);
    if (u->seq_held) {                       /* SEQ + white key 1-8: focus that track */
      u->key_role[key] = ROLE_NONE;
      if (n >= 0 && n < 8 && !u->srec) {
        focus(u, s, (unsigned)n, out);
        u->seq_gestured = 1;
      }
      return 1;
    }
    if (u->clear_held) {                     /* CLEAR + a key: S9's (del + aclrstep) */
      u->key_role[key] = ROLE_NONE;
      return 1;
    }
    if (u->mute_held) {                      /* MUTE + white key 1-8: the mute map */
      u->key_role[key] = ROLE_NONE;
      if (n >= 0 && n < 8 && n < u->tracks) {
        set_mute(u, (unsigned)n, !track_muted(u, (unsigned)n), out);
        u->mute_gestured = 1;
      }
      return 1;
    }
    if (u->srec) {
      u->key_role[key] = n < 0 ? ROLE_BLACK : ROLE_SHORTCUT;
      if (n < 0) {
        if (key == FM1_SEQ_UI_KEY_BAR_BACK || key == FM1_SEQ_UI_KEY_BAR_ON) {
          srec_arrow(u, key == FM1_SEQ_UI_KEY_BAR_ON ? 1 : -1, out);
        }
      } else if (u->shift) {
        srec_jump(u, s, u->bar * 16u + (unsigned)n, out);
      } else if (pitch >= 0 && pitch <= 127) {
        u->key_role[key] = ROLE_SREC;
        u->srec_keys |= 1u << key;
        srec_note_on(u, pitch, u->full_vel ? 127 : clampi(velocity, 1, 127), out);
        return FM1_SEQ_UI_KEY_SOUND;
      }
      return 1;
    }
    /* A page gives way to the Track view for a step or a bar key; MUTE, the
     * track keys and SHIFT's shortcuts keep it. */
    if (is_page(u->view) && !u->shift &&
        (n >= 0 || key == FM1_SEQ_UI_KEY_BAR_BACK || key == FM1_SEQ_UI_KEY_BAR_ON)) {
      u->view = FM1_SEQ_VIEW_TRACK;
    }
    if (n < 0) {
      u->key_role[key] = ROLE_BLACK;
      black_down(u, s, key, frame, out);
    } else {
      white_down(u, s, key, n, velocity, frame, pitch, out);
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

/* The pages SELECT walks past the sound's: Set, Clip, Track 1/2, Track 2/2
 * (O21). Below the first, the Track view and the sound's last page. */
static int page_index(const fm1_seq_ui_t *u) {
  if (u->view == FM1_SEQ_VIEW_SET) return 0;
  if (u->view == FM1_SEQ_VIEW_CLIP) return 1;
  return 2 + (u->track_page ? 1 : 0);
}

static void page_walk(fm1_seq_ui_t *u, int delta) {
  const int i = clampi(page_index(u) + delta, -1, 3);
  if (i < 0) {
    fm1_seq_ui_open(u, FM1_SEQ_VIEW_TRACK);
  } else if (i < 2) {
    fm1_seq_ui_open(u, i == 0 ? FM1_SEQ_VIEW_SET : FM1_SEQ_VIEW_CLIP);
  } else {
    fm1_seq_ui_open(u, FM1_SEQ_VIEW_TRACKPG);
    u->track_page = (uint8_t)(i - 2);
  }
}

/* `verb v`, or `verb t v` for the focused track, when v changed. */
static int send_if(fm1_seq_ui_t *u, const fm1_seq_ui_emit_t *out, uint16_t verb, int track_arg,
                   int v, int was) {
  int64_t arg[2];
  unsigned n = 0;
  if (v == was) return 0;
  if (track_arg) arg[n++] = u->track;
  arg[n++] = v;
  emit(out, verb, n, arg);
  return 1;
}

/* `route t kind index` for the focused track; its sound becomes the current
 * one (follow). */
static void set_route(fm1_seq_ui_t *u, int kind, int index, const fm1_seq_ui_emit_t *out) {
  const int64_t arg[3] = { u->track, kind, index };
  if (kind == u->route_kind && index == u->route_index) return;
  emit(out, FM1_SEQ_V_ROUTE, 3, arg);
  u->route_kind = (uint8_t)kind;
  u->route_index = (uint8_t)index;
  u->follow = 1;
}

/* KNOB1..4 on the Set, Clip and Track pages: one command a turn, from the
 * values as last read or sent, so detents between blocks add up (Movy's
 * main-page.ts, clip-page.ts; the Track page is ours). */
static void page_knob(fm1_seq_ui_t *u, int knob, int delta, const fm1_seq_ui_emit_t *out) {
  const int up = delta > 0;
  if (u->view == FM1_SEQ_VIEW_SET) {
    switch (knob) {
      case 0: {                              /* TEMPO: 1 BPM a detent, 0.1 with SHIFT */
        const int v = clampi((int)u->bpm_x100 + delta * (u->shift ? 10 : 100),
                             (int)FM1_SEQ_BPM_X100_MIN, (int)FM1_SEQ_BPM_X100_MAX);
        if (send_if(u, out, FM1_SEQ_V_BPM, 0, v, (int)u->bpm_x100)) u->bpm_x100 = (uint32_t)v;
        break;
      }
      case 1: {                              /* SWING, 50..80 % */
        const int v = clampi((int)u->swing + delta, 50, 80);
        if (send_if(u, out, FM1_SEQ_V_SWING, 0, v, u->swing)) u->swing = (uint16_t)v;
        break;
      }
      case 2: {                              /* DEF QUANT, Movy's list */
        const int v = fm1_seq_ui_quants[clampi(fm1_seq_ui_quant_index(u->dq) + delta, 0,
                                               FM1_SEQ_UI_QUANTS - 1)];
        if (send_if(u, out, FM1_SEQ_V_DQ, 0, v, u->dq)) u->dq = (uint8_t)v;
        break;
      }
      default:                               /* METRO: on with a turn up, off down */
        if (send_if(u, out, FM1_SEQ_V_METRO, 0, up, u->metro != 0)) u->metro = (uint8_t)up;
        break;
    }
  } else if (u->view == FM1_SEQ_VIEW_CLIP) {
    switch (knob) {
      case 0: {                              /* SPEED, 1/8X .. 4X */
        const int i = clampi(fm1_seq_ui_speed_index(u->clip_num, u->clip_den) + delta, 0,
                             FM1_SEQ_UI_SPEEDS - 1);
        const int64_t arg[3] = { u->track, fm1_seq_ui_speeds[i][0], fm1_seq_ui_speeds[i][1] };
        if (fm1_seq_ui_speeds[i][0] != u->clip_num || fm1_seq_ui_speeds[i][1] != u->clip_den) {
          emit(out, FM1_SEQ_V_CSCL, 3, arg);
          u->clip_num = fm1_seq_ui_speeds[i][0];
          u->clip_den = fm1_seq_ui_speeds[i][1];
        }
        break;
      }
      case 1: {                              /* LENGTH, a step a detent; no clip: up makes one */
        const int max = (int)FM1_SEQ_MAX_STEPS - (int)u->loop_start;
        if (!u->length && !up) break;
        {
          const int v = clampi((int)u->length + delta, 1, max);
          if (send_if(u, out, FM1_SEQ_V_CLEN, 1, v, u->length)) u->length = (uint16_t)v;
        }
        break;
      }
      case 2: {                              /* TRANSPOSE, +-36 semitones */
        const int v = clampi((int)u->clip_tr + delta, -36, 36);
        if (send_if(u, out, FM1_SEQ_V_CTR, 1, v, u->clip_tr)) u->clip_tr = (int8_t)v;
        break;
      }
      default: {                             /* QUANT, Movy's list */
        const int v = fm1_seq_ui_quants[clampi(fm1_seq_ui_quant_index(u->clip_quant) + delta, 0,
                                               FM1_SEQ_UI_QUANTS - 1)];
        if (send_if(u, out, FM1_SEQ_V_CQ, 1, v, u->clip_quant)) u->clip_quant = (uint8_t)v;
        break;
      }
    }
  } else if (u->view == FM1_SEQ_VIEW_TRACKPG && u->track_page == 0) {
    const int engine = u->route_kind == FM1_SEQ_ROUTE_ENGINE;
    switch (knob) {
      case 0:                                /* ROUTE: a sound unit, or MIDI out */
        if (engine && up) set_route(u, FM1_SEQ_ROUTE_MIDI, (int)(u->track % 16u) + 1, out);
        else if (!engine && !up) set_route(u, FM1_SEQ_ROUTE_ENGINE, 0, out);
        break;
      case 1:                                /* SOUND 1-4, or CHANNEL 1-16 */
        if (engine) {
          set_route(u, FM1_SEQ_ROUTE_ENGINE,
                    clampi((int)u->route_index + delta, 0, FM1_SEQ_UI_SOUNDS - 1), out);
        } else {
          set_route(u, FM1_SEQ_ROUTE_MIDI, clampi((int)u->route_index + delta, 1, 16), out);
        }
        break;
      case 2:                                /* MUTE: on with a turn up, off down */
        if (up != track_muted(u, u->track)) set_mute(u, u->track, up, out);
        break;
      default:
        break;
    }
  }
}

int fm1_seq_ui_encoder(fm1_seq_ui_t *u, const fm1_seq_t *s, int encoder, int delta,
                       uint64_t frame, int mode, const fm1_seq_ui_sound_t *snd,
                       const fm1_seq_ui_emit_t *out) {
  (void)frame;
  u->shift_clean = 0;
  fm1_seq_ui_lock_pages(u, snd ? fm1_seq_ui_pages(snd->e) : 0);
  if (u->capture_mode && delta) {
    /* SELECT and KNOB1 are the overlay's own control, Movy's jog: in the
     * picker they take the next tempo, heard at once, and over the fitted
     * tempo they do nothing (Movy's captureJog); any other encoder closes
     * the overlay. */
    if (encoder == FM1_ENC_SELECT || encoder == FM1_ENC_KNOB1) {
      const int next = clampi(u->capture_sel + (delta > 0 ? 1 : -1), 0,
                              u->capture_n ? u->capture_n - 1 : 0);
      if (u->capture_mode == FM1_SEQ_UI_CAPTURE_PICK && next != u->capture_sel) {
        const int64_t arg[1] = { next };
        emit(out, FM1_SEQ_V_CAPSEL, 1, arg);
        u->capture_sel = (uint8_t)next;
      }
      return 1;
    }
    return close_overlay(u, out);
  }
  if (mode != FM1_MODE_SEQ || delta == 0) return 0;
  if (!u->held_n && is_page(u->view)) {     /* the Set, Clip and Track pages */
    if (encoder == FM1_ENC_SELECT) {
      page_walk(u, delta);
      return 1;
    }
    if (encoder >= FM1_ENC_KNOB1 && encoder <= FM1_ENC_KNOB4) {
      page_knob(u, encoder - FM1_ENC_KNOB1, delta, out);
      return 1;
    }
    return 0;                                /* PRESETS and ALGORITHM: the sound */
  }
  if (!u->held_n) return 0;
  if (encoder == FM1_ENC_SELECT) {           /* Step 1/2, 2/2, then the lock pages (S8) */
    u->step_page = (uint8_t)clampi(u->step_page + (delta > 0 ? 1 : -1), 0,
                                   FM1_SEQ_UI_STEP_PAGES - 1 + u->lock_pages);
    gesture(u);
    return 1;
  }
  if (encoder >= FM1_ENC_KNOB1 && encoder <= FM1_ENC_KNOB4) {
    if (u->step_page >= FM1_SEQ_UI_STEP_PAGES) {   /* a lock page */
      /* One step held, or CLEAR held with any number: CLEAR + a knob is
       * CLEAR's gesture whatever is held (Movy's router: only its step page
       * owns the knobs before Clear does), so it clears the lane. */
      if (u->held_n == 1 || u->clear_held) {
        lock_knob(u, s, snd, encoder - FM1_ENC_KNOB1, delta, out);
        return 1;
      }
      gesture(u);                            /* several held: the sound, with no lock */
      return 0;
    }
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

/* Step record's MIDI IN notes down: their pitches, in press order. */
static int srec_midi_remove(fm1_seq_ui_t *u, int pitch) {
  for (int k = 0; k < u->srec_midi_n; ++k) {
    if (u->srec_midi[k] == pitch) {
      memmove(&u->srec_midi[k], &u->srec_midi[k + 1], (size_t)(u->srec_midi_n - k - 1));
      --u->srec_midi_n;
      return 1;
    }
  }
  return 0;
}

int fm1_seq_ui_note(fm1_seq_ui_t *u, int pitch, int velocity, int mode,
                    const fm1_seq_ui_emit_t *out) {
  if (pitch < 0 || pitch > 127) return 0;
  if (velocity <= 0) {                       /* a release touches nothing SHIFT does */
    if (srec_midi_remove(u, pitch)) {
      srec_maybe_advance(u, out);
      return 1;
    }
    sounding_remove(u, pitch);
    return 0;
  }
  u->shift_clean = 0;
  velocity = clampi(velocity, 1, 127);
  if (mode == FM1_MODE_SEQ && u->srec) {     /* step record: a pitch at the head, as a key */
    /* A pitch already down is one pad, as Movy's map of held pads: a
     * second note-on enters nothing, and the first release lets it go, so
     * an unbalanced stream cannot hold the chord open. */
    for (int k = 0; k < u->srec_midi_n; ++k) {
      if (u->srec_midi[k] == pitch) return 1;
    }
    if (u->srec_midi_n < (int)sizeof u->srec_midi) {
      u->srec_midi[u->srec_midi_n++] = (uint8_t)pitch;
      srec_note_on(u, pitch, u->full_vel ? 127 : velocity, out);
    }
    return 1;
  }
  if (mode == FM1_MODE_SEQ && u->held_n) {
    for (int k = 0; k < u->held_n; ++k) {
      const int64_t arg[5] = { u->track, u->held[k].step, u->held[k].step, pitch,
                               u->full_vel ? 127 : velocity };
      emit(out, FM1_SEQ_V_ADDP, 5, arg);
    }
    gesture(u);
    u->hold_valid = 0;
    return 1;
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
  return 0;
}

/* A panic: MIDI IN's notes down are gone, so step record's chord closes on
 * its keys alone. */
void fm1_seq_ui_notes_off(fm1_seq_ui_t *u) {
  u->sounding_n = 0;
  u->srec_midi_n = 0;
}

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
  if (u->seq_held) {                         /* SEQ held: the focused track's key */
    if (u->track < 8u) m |= 1u << fm1_white_key(u->track);
    return m;
  }
  if (u->mute_held) {                        /* the mute map: lit while a track sounds */
    for (unsigned t = 0; t < u->tracks && t < 8u; ++t) {
      if (!track_muted(u, t)) m |= 1u << fm1_white_key((int)t);
    }
    return m | 1u << FM1_SEQ_UI_KEY_MUTE;
  }
  const uint16_t held = fm1_seq_ui_held_mask(u), under = fm1_seq_ui_under_mask(u);
  const int slow_on = (frame % u->rate) < u->rate / 2u;    /* the 1 s blink */
  const uint32_t fast = u->rate / 4u ? u->rate / 4u : 1u;
  const int fast_on = (frame % fast) < fast / 2u;          /* the 0.25 s blink */
  for (unsigned n = 0; n < FM1_APP_WHITE_KEYS; ++n) {
    const unsigned step = u->bar * 16u + n, g = step - u->grid_first;
    int on = g < FM1_SEQ_UI_GRID_STEPS && ((u->notes >> g) & 1u) && step >= u->loop_start &&
             step < (unsigned)u->loop_start + u->length;
    if (u->clip_playing && u->step == step) on = !on;
    if ((under >> n) & 1u) on = slow_on;
    if ((held >> n) & 1u) on = 1;
    if (u->srec && u->srec_head == step) on = fast_on;   /* the record head */
    if (on) m |= 1u << fm1_white_key((int)n);
  }
  if (u->srec) {                             /* step record: a rest or tie, and back */
    m |= 1u << FM1_SEQ_UI_KEY_BAR_ON;
    if (fm1_seq_ui_srec_can_go_back(u)) m |= 1u << FM1_SEQ_UI_KEY_BAR_BACK;
    return m;
  }
  if (u->held_n || u->bar > u->bar_min) m |= 1u << FM1_SEQ_UI_KEY_BAR_BACK;
  if (u->held_n || u->bar < u->bar_max) m |= 1u << FM1_SEQ_UI_KEY_BAR_ON;
  if (u->lanes || u->clear_held) m |= 1u << FM1_SEQ_UI_KEY_CLEAR;   /* S8: a lane to clear */
  if (!u->held_n) {                          /* MUTE and the track keys (S6) */
    m |= 1u << FM1_SEQ_UI_KEY_MUTE;
    if (u->track > 0) m |= 1u << FM1_SEQ_UI_KEY_TRACK_PREV;
    if (u->track + 1u < u->tracks) m |= 1u << FM1_SEQ_UI_KEY_TRACK_NEXT;
  }
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
