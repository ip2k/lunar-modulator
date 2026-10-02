/* seq_capture.c -- Capture: retroactive recording of what was just played.
 *
 * Derived from Movy's seq-core capture.rs and the capture functions of
 * engine.rs (lines 1185-1618), commit 9190e79, MIT, Copyright (c) 2026
 * megadake.
 *
 * Optional: with limits.capture == 0 the ring has no bytes and every entry
 * point here returns at once. Two changes from Movy, both for the FM-1:
 *   - the tempo search and the frame-to-tick conversion run in float, not
 *     f64 (pi32v2 has a single-precision FPU [inferred]); a candidate can
 *     differ from Movy's only where two scores tie to within float rounding;
 *   - the frozen take of a stopped capture lives in the ring's own storage
 *     (Movy copies it to a second Vec). The ring is idle while a take is
 *     frozen, because input is refused while the selector is up.
 * Scratch on the stack during a stopped capture: about 1.3 KB.
 */
#include "seq_int.h"

#include <math.h>

#define CAP_MAX_BARS 8u
#define BPM_MIN 40u
#define BPM_MAX 250u
#define N_BPM (BPM_MAX - BPM_MIN + 1u)

enum { CAP_NONE = 0, CAP_SELECT = 1, CAP_FIXED = 2 };
enum { WHY_NONE = 0, WHY_EXT = 1, WHY_NOTES = 2 };

static sq_cap_t *ring_at(fm1_seq_t *s, unsigned i) {
  return &sq_cap(s)[(s->cap_head + i) % s->lim.capture];
}

void sq_capture_clear(fm1_seq_t *s) {
  s->cap_head = 0;
  s->cap_len = 0;
}

static uint64_t bar_frames(const fm1_seq_t *s) {
  return (uint64_t)s->sample_rate * 60u * 4u * 100u / (s->bpm_x100 ? s->bpm_x100 : 1u);
}

static uint64_t gap_frames(const fm1_seq_t *s) {
  const uint64_t g = 2u * bar_frames(s), sr = s->sample_rate;
  return g < 2u * sr ? 2u * sr : (g > 8u * sr ? 8u * sr : g);
}

/* CaptureRing::push: a gap ends the phrase, the window bounds its age. */
static void ring_push(fm1_seq_t *s, const sq_cap_t *ev, uint64_t gap, uint64_t window) {
  const unsigned cap = s->lim.capture;
  if (s->cap_len > 0 && (uint64_t)(uint32_t)(ev->frame - s->cap_last_frame) > gap) {
    sq_capture_clear(s);
  }
  s->cap_last_frame = ev->frame;
  while (s->cap_len > 0 && (uint64_t)(uint32_t)(ev->frame - sq_cap(s)[s->cap_head].frame) > window) {
    s->cap_head = (uint16_t)((s->cap_head + 1u) % cap);
    --s->cap_len;
  }
  sq_cap(s)[(s->cap_head + s->cap_len) % cap] = *ev;
  if (s->cap_len == cap) s->cap_head = (uint16_t)((s->cap_head + 1u) % cap);
  else ++s->cap_len;
}

/* capture_push (engine.rs 1203-1248). */
void sq_capture_push(fm1_seq_t *s, unsigned t, uint8_t pitch, uint8_t vel, int on, uint64_t frame) {
  const sq_track_t *tr;
  sq_cap_t ev;
  unsigned i;
  if (s->lim.capture == 0) return;
  if (t >= s->n_tracks || s->count_in_left > 0) return;
  if (s->cap_mode != CAP_NONE) return;
  if (s->recording && t == s->rec_track) return;
  tr = &sq_tracks(s)[t];
  if (on && s->playing) {
    for (i = 0; i < s->cap_len; ++i) {
      const sq_cap_t *e = ring_at(s, i);
      const uint32_t d = e->clip_tick > tr->pos_tick ? (uint32_t)(e->clip_tick - tr->pos_tick)
                                                     : (uint32_t)(tr->pos_tick - e->clip_tick);
      if (e->on && e->track == t && e->cycle != tr->cycle && d < SQ_TPS) {
        sq_capture_clear(s);
        break;
      }
    }
  }
  memset(&ev, 0, sizeof(ev));
  ev.frame = (uint32_t)frame;
  ev.abs_tick = (uint32_t)s->master_tick;
  ev.clip_tick = tr->pos_tick;
  ev.cycle = tr->cycle;
  ev.track = (uint8_t)t;
  ev.on = on ? 1 : 0;
  ev.pitch = pitch;
  ev.vel = vel;
  ring_push(s, &ev, gap_frames(s), (uint64_t)CAP_MAX_BARS * bar_frames(s));
}

unsigned sq_capture_pending(fm1_seq_t *s, unsigned t) {
  unsigned i, n = 0;
  if (s->lim.capture == 0) return 0;
  for (i = 0; i < s->cap_len; ++i) {
    const sq_cap_t *e = ring_at(s, i);
    n += e->track == t && e->on;
  }
  return n;
}

static float ratio(uint32_t a, uint32_t b) {
  const float x = (float)a, y = (float)(b ? b : 1u);
  return x > y ? x / y : y / x;
}

/* estimate_tempos (capture.rs 150-241), in float. Returns the number of
 * candidates (0 when there are fewer than three onsets). */
static unsigned estimate_tempos(fm1_seq_t *s, const sq_cap_t *take, unsigned n_take,
                                uint32_t first, uint32_t span_frames, uint16_t cands[3],
                                uint8_t *best_ix) {
  float score[N_BPM];
  uint8_t minima[N_BPM], distinct[N_BPM], picked[3];
  unsigned n_on = 0, i, j, n_min = 0, n_dis = 0, n_pick, best;
  const float sr = (float)s->sample_rate;
  const float span = (float)(span_frames ? span_frames : 1u);
  for (i = 0; i < n_take; ++i) n_on += take[i].on;
  if (n_on < 3) return 0;
  for (i = 0; i < N_BPM; ++i) {
    const float bpm = (float)(BPM_MIN + i);
    const float fpb = sr * 60.0f / bpm;
    float fit = 0.0f, bars;
    for (j = 0; j < n_take; ++j) {
      float beats;
      if (!take[j].on) continue;
      beats = (float)(uint32_t)(take[j].frame - first) / fpb;
      fit += fabsf(beats - roundf(beats * 4.0f) / 4.0f);
    }
    fit /= (float)n_on;
    bars = span / fpb / 4.0f;
    score[i] = fit + 0.02f * fabsf(bars - roundf(bars)) + 0.02f * fabsf(logf(bpm / 120.0f));
  }
  /* Local minima, best first (a stable insertion sort, like Rust's sort_by). */
  for (i = 0; i < N_BPM; ++i) {
    const int lo = i == 0 || score[i - 1] >= score[i];
    const int hi = i + 1 == N_BPM || score[i + 1] > score[i];
    if (lo && hi) {
      j = n_min++;
      while (j > 0 && score[minima[j - 1]] > score[i]) {
        minima[j] = minima[j - 1];
        --j;
      }
      minima[j] = (uint8_t)i;
    }
  }
  /* Tempos within 5 % of a better one are the same tempo heard twice. */
  for (i = 0; i < n_min; ++i) {
    const uint32_t bpm = BPM_MIN + minima[i];
    int ok = 1;
    for (j = 0; j < n_dis && ok; ++j) ok = ratio(BPM_MIN + distinct[j], bpm) >= 1.05f;
    if (ok) distinct[n_dis++] = minima[i];
  }
  if (n_dis == 0) return 0;
  best = BPM_MIN + distinct[0];
  picked[0] = distinct[0];
  n_pick = 1;
  {
    const uint32_t partners[2] = { best / 2u, best * 2u };
    for (i = 0; i < 2; ++i) {
      int ok = partners[i] >= BPM_MIN && partners[i] <= BPM_MAX;
      for (j = 0; j < n_pick && ok; ++j) ok = ratio(BPM_MIN + picked[j], partners[i]) >= 1.05f;
      if (ok) picked[n_pick++] = (uint8_t)(partners[i] - BPM_MIN);
    }
  }
  for (i = 0; i < n_dis && n_pick < 3; ++i) {
    int ok = 1;
    for (j = 0; j < n_pick && ok; ++j) ok = ratio(BPM_MIN + picked[j], BPM_MIN + distinct[i]) >= 1.05f;
    if (ok) picked[n_pick++] = distinct[i];
  }
  /* Ascending, and where the winner ended up. */
  for (i = 1; i < n_pick; ++i) {
    const uint8_t v = picked[i];
    for (j = i; j > 0 && picked[j - 1] > v; --j) picked[j] = picked[j - 1];
    picked[j] = v;
  }
  *best_ix = 0;
  for (i = 0; i < n_pick; ++i) {
    cands[i] = (uint16_t)(BPM_MIN + picked[i]);
    if (cands[i] == best) *best_ix = (uint8_t)i;
  }
  return n_pick;
}

/* capture_write_take (engine.rs 1378-1450): the frozen take at grid_bpm. */
static int write_take(fm1_seq_t *s, uint32_t grid_bpm, int set_tempo, int keep_length) {
  const unsigned t = s->cap_track;
  const unsigned a = sq_tracks(s)[t].active;
  const unsigned clip = sq_clip_no(t, a);
  sq_cap_t *take = sq_cap(s);
  const unsigned n = s->cap_take_len;
  const float fpt = (float)s->sample_rate * 60.0f / ((float)(grid_bpm ? grid_bpm : 1u) * 96.0f);
  const int transpose = sq_active_transpose(s, t);
  uint32_t span_ticks, loop_start, span_end = 0;
  uint16_t len_steps;
  uint8_t snum, sden;
  unsigned i, j;
  int wrote = 0;
  sq_clip_ensure_exists(s, clip);
  span_ticks = sq_len_ticks(&sq_clips(s)[clip]);
  if (span_ticks == 0) span_ticks = 1;
  loop_start = sq_start_ticks(&sq_clips(s)[clip]);
  len_steps = sq_clips(s)[clip].length_steps;
  snum = sq_clips(s)[clip].scale_num;
  sden = sq_clips(s)[clip].scale_den;
  if (!keep_length) sq_clip_delete_range(s, clip, 0, SQ_MAX_STEPS - 1u, -1);
  for (i = 0; i < n; ++i) take[i].pad = 0;
  for (i = 0; i < n; ++i) {
    const sq_cap_t ev = take[i];
    uint32_t start, gate = SQ_TPS, tick;
    uint16_t step;
    int32_t stored;
    if (!ev.on) continue;
    for (j = i + 1; j < n; ++j) {
      if (!take[j].on && take[j].pitch == ev.pitch && !take[j].pad) {
        const uint32_t d = (uint32_t)(take[j].frame - ev.frame);
        const uint32_t g = (uint32_t)roundf((float)d / fpt);
        take[j].pad = 1;
        gate = g ? g : 1u;
        break;
      }
    }
    start = (uint32_t)roundf((float)(uint32_t)(ev.frame - s->cap_take_first) / fpt);
    tick = keep_length ? loop_start + start % span_ticks : start;
    step = sq_anchor_step(s, tick, snum, sden);
    if (keep_length) {
      /* Movy clamps to len_steps - 1, a step before the window when the
       * window starts past step 0 (D5's length-for-end); the FM-1 clamps to
       * the window's last step. */
      const uint32_t last = (s->lim.compat ? 0u : loop_start / SQ_TPS) + (len_steps ? len_steps - 1u : 0u);
      if (step > last) step = (uint16_t)last;
    }
    stored = (int32_t)ev.pitch - transpose;
    sq_clip_add_raw(s, clip, step, sq_unswing(s, tick, step, snum, sden), gate,
                    (uint8_t)(stored < 0 ? 0 : (stored > 127 ? 127 : stored)), ev.vel);
    if (start + gate > span_end) span_end = start + gate;
    wrote = 1;
  }
  if (!keep_length && wrote) {
    uint32_t bars = (span_end + SQ_TPB - 1u) / SQ_TPB, len;
    if (bars < 1) bars = 1;
    len = bars * SQ_BAR_STEPS;
    sq_clips(s)[clip].length_steps = (uint16_t)(len < SQ_MAX_STEPS ? len : SQ_MAX_STEPS);
    sq_clip_invalidate(s, clip);
  }
  if (set_tempo) sq_set_bpm(s, grid_bpm * 100u);
  return wrote;
}

/* Rotates the ring so its oldest event sits at index 0 (three reversals). */
static void ring_linearize(fm1_seq_t *s) {
  sq_cap_t *e = sq_cap(s);
  const unsigned cap = s->lim.capture, h = s->cap_head;
  unsigned i, j;
  sq_cap_t tmp;
  if (h == 0) return;
  for (i = 0, j = h - 1u; i < j; ++i, --j) { tmp = e[i]; e[i] = e[j]; e[j] = tmp; }
  for (i = h, j = cap - 1u; i < j; ++i, --j) { tmp = e[i]; e[i] = e[j]; e[j] = tmp; }
  for (i = 0, j = cap - 1u; i < j; ++i, --j) { tmp = e[i]; e[i] = e[j]; e[j] = tmp; }
  s->cap_head = 0;
}

/* capture_commit_stopped (engine.rs 1299-1372). */
static int commit_stopped(fm1_seq_t *s, unsigned t) {
  sq_cap_t *e = sq_cap(s);
  unsigned i, n = 0;
  uint32_t first = 0, last;
  int have_first = 0, clip_has_notes, free_tempo, wrote;
  uint32_t existing, grid;
  ring_linearize(s);
  for (i = 0; i < s->cap_len; ++i) {
    if (e[i].track == t) e[n++] = e[i];
  }
  s->cap_take_len = (uint16_t)n;
  s->cap_len = 0;                       /* the ring now holds the frozen take */
  for (i = 0; i < n && !have_first; ++i) {
    if (e[i].on) {
      first = e[i].frame;
      have_first = 1;
    }
  }
  if (!have_first) return 0;
  last = n ? e[n - 1u].frame : first;
  s->cap_take_first = first;
  s->cap_track = (uint8_t)t;
  s->cap_n = (uint8_t)estimate_tempos(s, e, n, first, (uint32_t)(last - first), s->cap_cands,
                                      &s->cap_best);
  s->cap_has_guess = s->cap_n > 0;
  clip_has_notes = sq_clip(s, t, sq_tracks(s)[t].active)->seg[SQ_K_NOTES].len > 0;
  existing = s->bpm_x100 / 100u;
  if (existing < 1) existing = 1;
  s->cap_why = s->ext_running ? WHY_EXT : (clip_has_notes ? WHY_NOTES : WHY_NONE);
  free_tempo = s->cap_why == WHY_NONE;
  if (s->cap_has_guess && free_tempo) {
    s->cap_sel = s->cap_best;
    grid = s->cap_cands[s->cap_best];
  } else if (s->cap_has_guess) {
    unsigned k = 0;
    for (i = 1; i < s->cap_n; ++i) {
      if (ratio(s->cap_cands[i], existing) < ratio(s->cap_cands[k], existing)) k = i;
    }
    s->cap_sel = (uint8_t)k;
    grid = s->cap_cands[k];
  } else {
    s->cap_sel = 0;
    grid = existing;
  }
  s->cap_stretch_permille = (int32_t)((int64_t)existing * 1000 / (grid ? grid : 1u)) - 1000;
  s->cap_mode = free_tempo && s->cap_n > 1 ? CAP_SELECT : (!free_tempo ? CAP_FIXED : CAP_NONE);
  wrote = write_take(s, grid, free_tempo, clip_has_notes);
  if (wrote) {
    sq_play(s);
  } else {
    s->cap_mode = CAP_NONE;
    s->cap_take_len = 0;
  }
  return wrote;
}

/* capture_commit_playing (engine.rs 1524-1618): the take lands where it was
 * heard; a fresh clip keeps the bar phase and launches on the bar. */
static int commit_playing(fm1_seq_t *s, unsigned t) {
  const unsigned a = sq_tracks(s)[t].active;
  const unsigned clip = sq_clip_no(t, a);
  uint32_t span, loop_start, first_abs = 0, first_phase, span_end = 0;
  const uint32_t now_abs = (uint32_t)s->master_tick;
  uint8_t snum, sden;
  int fresh, have = 0, wrote = 0;
  const int transpose = sq_active_transpose(s, t);
  unsigned i, j;
  sq_clip_ensure_exists(s, clip);
  fresh = sq_clips(s)[clip].seg[SQ_K_NOTES].len == 0;
  span = sq_len_ticks(&sq_clips(s)[clip]);
  if (span == 0) span = 1;
  loop_start = sq_start_ticks(&sq_clips(s)[clip]);
  snum = sq_clips(s)[clip].scale_num;
  sden = sq_clips(s)[clip].scale_den;
  for (i = 0; i < s->cap_len && !have; ++i) {
    const sq_cap_t *e = ring_at(s, i);
    if (e->track == t && e->on) {
      first_abs = e->abs_tick;
      have = 1;
    }
  }
  if (!have) return 0;
  first_phase = first_abs % SQ_TPB;
  for (i = 0; i < s->cap_len; ++i) ring_at(s, i)->pad = 0;
  for (i = 0; i < s->cap_len; ++i) {
    const sq_cap_t ev = *ring_at(s, i);
    uint32_t end = now_abs, gate, tick;
    uint16_t step;
    int32_t stored;
    if (ev.track != t || !ev.on) continue;
    for (j = i + 1; j < s->cap_len; ++j) {
      sq_cap_t *o = ring_at(s, j);
      if (o->track == ev.track && !o->on && o->pitch == ev.pitch && !o->pad) {
        o->pad = 1;
        end = o->abs_tick;
        break;
      }
    }
    gate = end > ev.abs_tick ? end - ev.abs_tick : 0;
    if (gate < 1) gate = 1;
    tick = fresh ? loop_start + first_phase + (ev.abs_tick > first_abs ? ev.abs_tick - first_abs : 0)
                 : ev.clip_tick % span;
    stored = (int32_t)ev.pitch - transpose;
    step = sq_anchor_step(s, tick, snum, sden);
    sq_clip_add_raw(s, clip, step, sq_unswing(s, tick, step, snum, sden), gate,
                    (uint8_t)(stored < 0 ? 0 : (stored > 127 ? 127 : stored)), ev.vel);
    if (tick + gate > span_end) span_end = tick + gate;
    wrote = 1;
  }
  if (fresh && wrote) {
    uint32_t bars = (span_end + SQ_TPB - 1u) / SQ_TPB, len;
    if (bars < 1) bars = 1;
    len = bars * SQ_BAR_STEPS;
    sq_clips(s)[clip].length_steps = (uint16_t)(len < SQ_MAX_STEPS ? len : SQ_MAX_STEPS);
    sq_clip_invalidate(s, clip);
  }
  if (wrote) {
    if (fresh) {
      sq_tracks(s)[t].queued = (uint8_t)a;
      sq_tracks(s)[t].pending_stop = 0;
    } else {
      sq_ensure_selected_playing(s, t);
    }
  }
  return wrote;
}

/* capture_commit (engine.rs 1262-1289). */
int sq_capture_commit(fm1_seq_t *s, unsigned t) {
  int wrote;
  if (s->lim.capture == 0 || t >= s->n_tracks) return 0;
  if (sq_capture_pending(s, t) == 0) {
    sq_capture_clear(s);
    return 0;
  }
  wrote = s->playing ? commit_playing(s, t) : commit_stopped(s, t);
  sq_capture_clear(s);
  if (wrote) {
    ++s->capture_gen;
    s->dirty = 1;
  }
  return wrote;
}

void sq_capture_select(fm1_seq_t *s, unsigned idx) {
  if (s->lim.capture == 0 || s->cap_mode != CAP_SELECT) return;
  if (!s->cap_has_guess || idx >= s->cap_n) return;
  s->cap_sel = (uint8_t)idx;
  write_take(s, s->cap_cands[idx], 1, 0);
  ++s->capture_gen;
  s->dirty = 1;
}

void sq_capture_done(fm1_seq_t *s) {
  if (s->lim.capture == 0 || s->cap_mode == CAP_NONE) return;
  s->cap_mode = CAP_NONE;
  s->cap_take_len = 0;
  ++s->capture_gen;
}
