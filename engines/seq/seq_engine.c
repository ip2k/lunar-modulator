/* seq_engine.c -- transport, clock, launches, song, recording and the
 * per-tick scheduler of the sequencer core (fm1_seq.h).
 *
 * Derived from Movy's seq-core engine.rs, clock.rs and track.rs (commit
 * 9190e79, MIT, Copyright (c) 2026 megadake). Rule numbers R1-R14 and
 * deviations D1-D13 are docs/13 §3. Line numbers in comments are engine.rs's.
 *
 * Left out, being specific to the Ableton Move: the MovePlay inject and the
 * linked Play that waits for Move (`minject` is accepted and ignored, so
 * `play` and `stop` always act at once), the undo ring (stage M4), status
 * strings and labels' read-back (the getters replace them).
 */
#include "seq_int.h"

/* ---- Layout -------------------------------------------------------------- */

#define ALIGN8(x) (((x) + 7u) & ~(size_t)7u)

static int limits_ok(const fm1_seq_limits_t *l) {
  return l && l->tracks >= 1 && l->tracks <= FM1_SEQ_MAX_TRACKS && l->notes >= 1 &&
         l->locks >= 1 && l->trigs >= 1 && l->gates >= 1 && l->rec_notes >= 1 &&
         l->clip_notes >= 1 && l->clip_locks >= 1 && l->clip_trigs >= 1;
}

/* Region offsets, in the order they sit in the block. */
typedef struct {
  size_t tracks, pmutes, clips, notes, locks, trigs, gates, song, pend, tail, cap, total;
} sq_layout_t;

static void layout(const fm1_seq_limits_t *l, sq_layout_t *o) {
  size_t at = ALIGN8(sizeof(struct fm1_seq));
  const size_t clips = (size_t)l->tracks * FM1_SEQ_SLOTS + 2u;
  o->tracks = at; at = ALIGN8(at + (size_t)l->tracks * sizeof(sq_track_t));
  o->pmutes = at; at = ALIGN8(at + (size_t)l->tracks * l->pad_mutes);
  o->clips = at;  at = ALIGN8(at + clips * sizeof(sq_clip_t));
  o->notes = at;  at = ALIGN8(at + (size_t)l->notes * sizeof(sq_note_t));
  o->locks = at;  at = ALIGN8(at + (size_t)l->locks * sizeof(sq_lock_t));
  o->trigs = at;  at = ALIGN8(at + (size_t)l->trigs * sizeof(sq_trig_t));
  o->gates = at;  at = ALIGN8(at + (size_t)l->gates * sizeof(sq_gate_t));
  o->song = at;   at = ALIGN8(at + l->song);
  o->pend = at;   at = ALIGN8(at + (size_t)l->rec_notes * sizeof(sq_rec_t));
  o->tail = at;   at = ALIGN8(at + (size_t)l->rec_notes * sizeof(sq_rec_t));
  o->cap = at;    at = ALIGN8(at + (size_t)l->capture * sizeof(sq_cap_t));
  o->total = at;
}

void fm1_seq_limits_default(fm1_seq_limits_t *lim, uint8_t tracks) {
  memset(lim, 0, sizeof(*lim));
  if (tracks < 1) tracks = 1;
  if (tracks > FM1_SEQ_MAX_TRACKS) tracks = FM1_SEQ_MAX_TRACKS;
  lim->tracks = tracks;
  lim->compat = 0;
  lim->gates = 64;
  lim->song = 64;
  lim->rec_notes = 16;
  lim->pad_mutes = 16;
  lim->notes = (uint16_t)(192u * tracks);
  lim->locks = (uint16_t)(192u * tracks);
  lim->trigs = (uint16_t)(32u * tracks);
  lim->clip_notes = 512;
  lim->clip_locks = 1024;
  lim->clip_trigs = 1024;
  lim->capture = 256;
}

size_t fm1_seq_size(const fm1_seq_limits_t *lim) {
  sq_layout_t l;
  if (!limits_ok(lim)) return 0;
  layout(lim, &l);
  return l.total;
}

static void track_init(sq_track_t *t, unsigned index) {
  memset(t, 0, sizeof(*t));
  t->active = 0;
  t->playing = t->queued = t->pending_select = SQ_NONE;
  t->pad_solo = SQ_NONE;
  t->last_auto_step = -1;
  memset(t->auto_cur, 0xFF, sizeof(t->auto_cur));  /* -1 */
  t->cycle = 1;
  t->route_kind = FM1_SEQ_ROUTE_MIDI;
  t->route_index = (uint8_t)(index % 16u + 1u);
}

fm1_seq_t *fm1_seq_create(void *mem, const fm1_seq_limits_t *lim, uint32_t sample_rate) {
  sq_layout_t l;
  fm1_seq_t *s = (fm1_seq_t *)mem;
  unsigned k;
  if (!mem || !limits_ok(lim) || ((uintptr_t)mem & 7u) || sample_rate == 0) return NULL;
  layout(lim, &l);
  memset(mem, 0, l.total);
  s->magic = SQ_MAGIC;
  s->size = (uint32_t)l.total;
  s->lim = *lim;
  s->lim.compat = lim->compat > FM1_SEQ_COMPAT_MOVY_FRAMES ? FM1_SEQ_COMPAT_MOVY : lim->compat;
  s->sample_rate = sample_rate;
  s->threshold = (uint64_t)sample_rate * 60u * 100u;
  s->bpm_x100 = 12000;
  s->swing_pct = 50;
  s->rng = 0x9E3779B97F4A7C15ull;
  s->watch_lane = -1;
  s->held_track = -1;
  s->held_step = -1;
  s->song_armed_launch = SQ_NONE;
  s->n_tracks = lim->tracks;
  s->n_clips = (uint8_t)(lim->tracks * FM1_SEQ_SLOTS + 2u);
  s->off_tracks = (uint32_t)l.tracks;
  s->off_pmutes = (uint32_t)l.pmutes;
  s->off_clips = (uint32_t)l.clips;
  s->off_notes = (uint32_t)l.notes;
  s->off_locks = (uint32_t)l.locks;
  s->off_trigs = (uint32_t)l.trigs;
  s->off_gates = (uint32_t)l.gates;
  s->off_song = (uint32_t)l.song;
  s->off_pend = (uint32_t)l.pend;
  s->off_tail = (uint32_t)l.tail;
  s->off_cap = (uint32_t)l.cap;
  for (k = 0; k < s->n_tracks; ++k) track_init(&sq_tracks(s)[k], k);
  for (k = 0; k < s->n_clips; ++k) {
    sq_clip_t *c = &sq_clips(s)[k];
    c->scale_num = c->scale_den = 1;
  }
  return s;
}

void fm1_seq_rng_seed(fm1_seq_t *s, uint64_t seed) { s->rng = seed; }

/* ---- Emission ------------------------------------------------------------ */

/* The caller's buffer keeps room for the note-off of every sounding gate,
 * so a full buffer never leaves a note hanging: a note-on that does not fit
 * is dropped whole (the caller pushes no gate for it), a lock is not marked
 * as sent (the latch sends it at a later step), and a clock tick or click is
 * lost; each is counted in dropped_events. A note-off needs only its own
 * slot. With cap >= limits.gates + 8 (fm1_seq_min_events) every note-off,
 * Start and Stop fits. */
int sq_emit(sq_out_t *o, uint8_t kind, uint8_t track, uint8_t a, fm1_seq_val_t b) {
  fm1_seq_ev_t *e;
  uint32_t need = 1u;
  if (kind != FM1_SEQ_EV_NOTE_OFF) need += o->s->n_gates;
  if (kind == FM1_SEQ_EV_NOTE_ON) need += 1u;    /* and its own note-off later */
  if (!o->out || o->n > o->cap || need > o->cap - o->n) {
    ++o->s->stats.dropped_events;
    return 0;
  }
  e = &o->out[o->n++];
  e->tick = o->tick;
  e->frame = o->s->lim.compat == FM1_SEQ_COMPAT_MOVY ? 0 : o->frame;
  e->kind = kind;
  e->track = track;
  e->a = a;
  e->b = b;
  return 1;
}

static void out_init(sq_out_t *o, fm1_seq_t *s, fm1_seq_ev_t *out, uint32_t cap) {
  o->s = s;
  o->out = out;
  o->cap = out ? cap : 0;
  o->n = 0;
  o->tick = (uint32_t)s->master_tick;
  o->frame = 0;
}

/* ---- Clock (clock.rs, R1) -------------------------------------------------- */

void sq_set_bpm(fm1_seq_t *s, uint32_t bpm_x100) {
  if (bpm_x100 < FM1_SEQ_BPM_X100_MIN) bpm_x100 = FM1_SEQ_BPM_X100_MIN;
  if (bpm_x100 > FM1_SEQ_BPM_X100_MAX) bpm_x100 = FM1_SEQ_BPM_X100_MAX;
  s->bpm_x100 = bpm_x100;
}

static void clock_reset(fm1_seq_t *s) {
  s->accum = 0;
  s->clock_tick = 0;
}

/* ---- Small helpers --------------------------------------------------------- */

static int track_ok(const fm1_seq_t *s, unsigned t) { return t < s->n_tracks; }

/* engine.rs 326-342: clip transpose, none on a drum track. */
static int clip_transpose(const fm1_seq_t *s, unsigned t, unsigned slot) {
  if (!track_ok(s, t) || sq_ctracks(s)[t].drum || slot >= FM1_SEQ_SLOTS) return 0;
  return sq_cclip(s, t, slot)->transpose;
}

int sq_active_transpose(const fm1_seq_t *s, unsigned t) {
  if (!track_ok(s, t)) return 0;
  return clip_transpose(s, t, sq_ctracks(s)[t].active);
}

/* track.rs pad_voice_silent: solo decides alone, else the mute set. */
int sq_pad_voice_silent(fm1_seq_t *s, unsigned t, uint8_t pitch) {
  const sq_track_t *tr = &sq_tracks(s)[t];
  const uint8_t *pm = sq_pmutes(s, t);
  unsigned i;
  if (tr->pad_solo != SQ_NONE) return tr->pad_solo != pitch;
  for (i = 0; i < tr->n_pad_mutes; ++i) {
    if (pm[i] == pitch) return 1;
  }
  return 0;
}

/* track.rs set_pad_mute: an ordered set, removal keeps the order. */
void sq_set_pad_mute(fm1_seq_t *s, unsigned t, uint8_t note, int muted) {
  sq_track_t *tr = &sq_tracks(s)[t];
  uint8_t *pm = sq_pmutes(s, t);
  unsigned i;
  for (i = 0; i < tr->n_pad_mutes; ++i) {
    if (pm[i] == note) break;
  }
  if (muted && i == tr->n_pad_mutes) {
    if (tr->n_pad_mutes >= s->lim.pad_mutes) {
      ++s->stats.refused;
      return;
    }
    pm[tr->n_pad_mutes++] = note;
  } else if (!muted && i < tr->n_pad_mutes) {
    memmove(pm + i, pm + i + 1, (size_t)(tr->n_pad_mutes - i - 1u));
    --tr->n_pad_mutes;
  }
}

/* xorshift64* -> 0..99 (engine.rs 393-398, R7). */
static uint8_t roll_pct(fm1_seq_t *s) {
  uint64_t x = s->rng;
  x ^= x >> 12;
  x ^= x << 25;
  x ^= x >> 27;
  s->rng = x;
  return (uint8_t)(((x * 0x2545F4914F6CDD1Dull) >> 33) % 100u);
}

/* trig condition (clip.rs 74-78). */
static int condition_plays(uint8_t a, uint8_t b, uint8_t invert, uint32_t cycle) {
  const uint32_t bb = b ? b : 1u;
  const int plays = ((cycle - 1u) % bb) + 1u == a;
  return plays ^ (invert ? 1 : 0);
}

/* anchor_step (engine.rs 377-390): the step whose swung position is nearest,
 * ties to the later one. */
uint16_t sq_anchor_step(const fm1_seq_t *s, uint32_t tick, uint8_t num, uint8_t den) {
  const uint16_t straight = (uint16_t)(tick / SQ_TPS);
  uint16_t cands[3], best = straight;
  uint32_t best_d = 0xFFFFFFFFu;
  int i;
  cands[0] = straight ? (uint16_t)(straight - 1u) : 0;
  cands[1] = straight;
  cands[2] = (uint16_t)(straight + 1u);
  for (i = 0; i < 3; ++i) {
    const uint32_t pos = (uint32_t)cands[i] * SQ_TPS + sq_swing_delay(s, cands[i], num, den);
    const uint32_t d = pos > tick ? pos - tick : tick - pos;
    if (d <= best_d) {
      best_d = d;
      best = cands[i];
    }
  }
  return best;
}

void sq_reseed_empty_clips(fm1_seq_t *s) {
  unsigned t, k;
  for (t = 0; t < s->n_tracks; ++t) {
    for (k = 0; k < FM1_SEQ_SLOTS; ++k) {
      sq_clip_t *c = sq_clip(s, t, k);
      if (!sq_exists(c) && c->quant != s->default_quant) {
        c->quant = s->default_quant;
        sq_clip_invalidate(s, sq_clip_no(t, k));
      }
    }
  }
}

/* ---- Gates ------------------------------------------------------------------- */

static void gate_swap_remove(fm1_seq_t *s, unsigned i) {
  sq_gate_t *g = sq_gates(s);
  g[i] = g[s->n_gates - 1u];
  --s->n_gates;
}

/* D7: with every gate in use, the oldest sounding note ends to make room.
 * Called before the new note-on, so its note-off comes first. */
static void gate_make_room(fm1_seq_t *s, sq_out_t *o) {
  sq_gate_t *g = sq_gates(s);
  unsigned i, oldest = 0;
  if (s->n_gates < s->lim.gates) return;
  for (i = 1; i < s->n_gates; ++i) {
    if ((int16_t)(uint16_t)(g[i].serial - g[oldest].serial) < 0) oldest = i;
  }
  sq_emit(o, FM1_SEQ_EV_NOTE_OFF, g[oldest].track, g[oldest].pitch, 0);
  gate_swap_remove(s, oldest);
  ++s->stats.gates_evicted;
}

static void gate_push(fm1_seq_t *s, uint8_t track, uint8_t pitch, uint16_t ticks) {
  sq_gate_t *g = sq_gates(s);
  g[s->n_gates].track = track;
  g[s->n_gates].pitch = pitch;
  g[s->n_gates].left = ticks ? ticks : 1u;
  g[s->n_gates].serial = s->gate_serial++;
  ++s->n_gates;
}

static void flush_gates(fm1_seq_t *s, sq_out_t *o) {
  const sq_gate_t *g = sq_gates(s);
  unsigned i;
  for (i = 0; i < s->n_gates; ++i) sq_emit(o, FM1_SEQ_EV_NOTE_OFF, g[i].track, g[i].pitch, 0);
  s->n_gates = 0;
}

void sq_flush_track_gates(fm1_seq_t *s, unsigned t, sq_out_t *o) {
  unsigned i = 0;
  while (i < s->n_gates) {
    const sq_gate_t g = sq_gates(s)[i];
    if (g.track == t) {
      gate_swap_remove(s, i);
      sq_emit(o, FM1_SEQ_EV_NOTE_OFF, g.track, g.pitch, 0);
      continue;
    }
    ++i;
  }
}

void sq_flush_silenced_pad_gates(fm1_seq_t *s, unsigned t, sq_out_t *o) {
  unsigned i = 0;
  while (i < s->n_gates) {
    const sq_gate_t g = sq_gates(s)[i];
    if (g.track == t && sq_pad_voice_silent(s, t, g.pitch)) {
      gate_swap_remove(s, i);
      sq_emit(o, FM1_SEQ_EV_NOTE_OFF, g.track, g.pitch, 0);
      continue;
    }
    ++i;
  }
}

/* ---- Clip operations (engine.rs 411-570) ----------------------------------- */

/* D6 (FM-1 default): a lane last sent a value other than its base goes back
 * to the base, so no parameter is left at a value no lock asks for any more.
 * Movy does neither on Stop, on a track stop nor on a lane's release. */
static void revert_lane(fm1_seq_t *s, unsigned t, unsigned lane, sq_out_t *o) {
  const sq_track_t *tr = &sq_tracks(s)[t];
  if (s->lim.compat || !(tr->lanes_assigned & (1u << lane))) return;
  if (tr->auto_cur[lane] >= 0 && tr->auto_cur[lane] != tr->base[lane]) {
    sq_emit(o, FM1_SEQ_EV_LOCK, (uint8_t)t, (uint8_t)lane, tr->base[lane]);
  }
}

/* The reset free_unused_lanes gives a lane: unassigned, unlabelled, base 0,
 * nothing carried. The FM-1 sends it back to its base first (D6). */
void sq_release_lane(fm1_seq_t *s, unsigned t, unsigned lane, sq_out_t *o) {
  sq_track_t *tr = &sq_tracks(s)[t];
  revert_lane(s, t, lane, o);
  tr->lanes_assigned &= (uint8_t)~(1u << lane);
  tr->label[lane][0] = '\0';
  tr->base[lane] = 0;
  tr->auto_cur[lane] = -1;
}

/* free_unused_lanes: a lane no clip on the track locks is released. */
void sq_free_unused_lanes(fm1_seq_t *s, unsigned t, sq_out_t *o) {
  sq_track_t *tr;
  unsigned lane, k;
  if (!track_ok(s, t)) return;
  tr = &sq_tracks(s)[t];
  for (lane = 0; lane < FM1_SEQ_LANES; ++lane) {
    int used = 0;
    if (!(tr->lanes_assigned & (1u << lane))) continue;
    for (k = 0; k < FM1_SEQ_SLOTS && !used; ++k) {
      used = sq_clip_has_lock_on_lane(s, sq_clip_no(t, k), (uint8_t)lane);
    }
    if (!used) sq_release_lane(s, t, lane, o);
  }
}

static void drop_rec_notes_for(fm1_seq_t *s, unsigned t, unsigned slot);

void sq_duplicate_clip(fm1_seq_t *s, unsigned t) {
  sq_track_t *tr;
  unsigned off;
  if (!track_ok(s, t)) return;
  tr = &sq_tracks(s)[t];
  for (off = 1; off <= FM1_SEQ_SLOTS; ++off) {
    const unsigned i = (tr->active + off) % FM1_SEQ_SLOTS;
    if (!sq_exists(sq_clip(s, t, i))) {
      if (sq_clip_copy(s, sq_clip_no(t, i), sq_clip_no(t, tr->active))) tr->active = (uint8_t)i;
      return;
    }
  }
}

void sq_delete_clip_at(fm1_seq_t *s, unsigned t, unsigned slot, sq_out_t *o) {
  if (!track_ok(s, t) || slot >= FM1_SEQ_SLOTS) return;
  sq_clip_clear(s, sq_clip_no(t, slot));
  drop_rec_notes_for(s, t, slot);
  sq_free_unused_lanes(s, t, o);
}

void sq_copy_clip(fm1_seq_t *s, unsigned t, unsigned slot) {
  if (!track_ok(s, t) || slot >= FM1_SEQ_SLOTS) return;
  if (sq_clip_copy(s, SQ_CLIP_CLIPCB(s), sq_clip_no(t, slot))) s->clip_clipboard = 1;
}

void sq_paste_clip(fm1_seq_t *s, unsigned t, unsigned slot, sq_out_t *o) {
  if (!track_ok(s, t) || slot >= FM1_SEQ_SLOTS || !s->clip_clipboard) return;
  if (sq_clip_copy(s, sq_clip_no(t, slot), SQ_CLIP_CLIPCB(s))) {
    sq_tracks(s)[t].active = (uint8_t)slot;
    sq_free_unused_lanes(s, t, o);
  }
}

void sq_delete_range(fm1_seq_t *s, unsigned t, uint16_t s0, uint16_t s1, int lane, sq_out_t *o) {
  if (!track_ok(s, t)) return;
  sq_clip_delete_range(s, sq_clip_no(t, sq_tracks(s)[t].active), s0, s1, lane);
  sq_free_unused_lanes(s, t, o);
}

/* copy_steps (engine.rs 507-533): notes and locks relative to s0, kept in the
 * step-clipboard pseudo-clip. Movy computes the span as u16 s1 - s0 + 1, which
 * wraps (release) or panics (debug) when s0 > s1. */
void sq_copy_steps(fm1_seq_t *s, unsigned t, uint16_t s0, uint16_t s1) {
  const unsigned cb = SQ_CLIP_STEPCB(s);
  const uint32_t base_tick = (uint32_t)s0 * SQ_TPS;
  unsigned i, n, src;
  if (!track_ok(s, t)) return;
  src = sq_clip_no(t, sq_tracks(s)[t].active);
  if (s0 > s1) {
    ++s->stats.movy_faults;   /* release wraps (replayed in compat), debug panics */
    if (!s->lim.compat) return;
  }
  if (!s->lim.compat) {
    /* D7: the clipboard is replaced whole or not at all. */
    const sq_clip_t *c = &sq_clips(s)[src];
    unsigned nn = 0, nl = 0;
    for (i = 0; i < c->seg[SQ_K_NOTES].len; ++i) {
      const uint16_t st = SQ_NSTEP(sq_cnote(s, c, i));
      nn += st >= s0 && st <= s1;
    }
    for (i = 0; i < c->seg[SQ_K_LOCKS].len; ++i) {
      const uint8_t st = sq_clock(s, c, i)->step;
      nl += st >= s0 && st <= s1;
    }
    if (!sq_pool_room(s, SQ_K_NOTES, nn, sq_clips(s)[cb].seg[SQ_K_NOTES].len) ||
        !sq_pool_room(s, SQ_K_LOCKS, nl, sq_clips(s)[cb].seg[SQ_K_LOCKS].len)) return;
  }
  s->clipboard_span = (uint16_t)(s1 - s0 + 1u);
  sq_seg_clear(s, cb, SQ_K_NOTES);
  sq_seg_clear(s, cb, SQ_K_LOCKS);
  n = sq_clips(s)[src].seg[SQ_K_NOTES].len;
  for (i = 0; i < n; ++i) {
    sq_note_t x = *sq_cnote(s, &sq_clips(s)[src], i);
    const uint16_t st = SQ_NSTEP(&x);
    if (st < s0 || st > s1) continue;
    x.step = (uint16_t)(st - s0);
    x.tick = (uint16_t)(x.tick > base_tick ? x.tick - base_tick : 0u);
    x.fire = SQ_FIRE_NEVER;
    if (!sq_seg_insert(s, cb, SQ_K_NOTES, sq_clips(s)[cb].seg[SQ_K_NOTES].len, &x)) break;
  }
  n = sq_clips(s)[src].seg[SQ_K_LOCKS].len;
  for (i = 0; i < n; ++i) {
    sq_lock_t l = *sq_clock(s, &sq_clips(s)[src], i);
    if (l.step < s0 || l.step > s1) continue;
    l.step = (uint8_t)(l.step - s0);
    if (!sq_seg_insert(s, cb, SQ_K_LOCKS, sq_clips(s)[cb].seg[SQ_K_LOCKS].len, &l)) break;
  }
}

/* paste_steps (engine.rs 535-565): replace the destination span. */
void sq_paste_steps(fm1_seq_t *s, unsigned t, uint16_t dest) {
  const unsigned cb = SQ_CLIP_STEPCB(s);
  unsigned dst, i, n;
  uint16_t span, end;
  uint32_t base_tick, st;
  if (!track_ok(s, t) || s->clipboard_span == 0) return;
  span = s->clipboard_span;
  dst = sq_clip_no(t, sq_tracks(s)[t].active);
  end = (uint16_t)(dest + span);
  if (!s->lim.compat) {
    /* D7: the paste replaces its span whole or not at all. Count what it
     * removes (notes anchored in the span, its steps' locks) and adds (the
     * clipboard's items that land before step 256, within the clip cap). */
    const sq_clip_t *c = &sq_clips(s)[dst];
    const sq_clip_t *k = &sq_clips(s)[cb];
    const uint16_t last = (uint16_t)(dest + span - 1u);
    unsigned dn = 0, dl = 0, an = 0, al = 0;
    for (i = 0; i < c->seg[SQ_K_NOTES].len; ++i) {
      const uint16_t st = SQ_NSTEP(sq_cnote(s, c, i));
      dn += st >= dest && st <= last;
    }
    for (i = 0; i < c->seg[SQ_K_LOCKS].len; ++i) {
      const uint8_t st = sq_clock(s, c, i)->step;
      dl += st >= dest && st < end;
    }
    for (i = 0; i < k->seg[SQ_K_NOTES].len; ++i) {
      an += (unsigned)dest + SQ_NSTEP(sq_cnote(s, k, i)) < SQ_MAX_STEPS;
    }
    for (i = 0; i < k->seg[SQ_K_LOCKS].len; ++i) al += (unsigned)dest + sq_clock(s, k, i)->step < SQ_MAX_STEPS;
    an = an < s->lim.clip_notes - (c->seg[SQ_K_NOTES].len - dn) ? an
                                                                : s->lim.clip_notes - (c->seg[SQ_K_NOTES].len - dn);
    al = al < s->lim.clip_locks - (c->seg[SQ_K_LOCKS].len - dl) ? al
                                                                : s->lim.clip_locks - (c->seg[SQ_K_LOCKS].len - dl);
    if (!sq_pool_room(s, SQ_K_NOTES, an, dn) || !sq_pool_room(s, SQ_K_LOCKS, al, dl)) return;
  }
  /* u16 arithmetic as Movy's; a range whose end wrapped below its start is
   * empty, as Rust's `a..b` is. */
  sq_clip_delete_range(s, dst, dest, (uint16_t)(dest + span - 1u), -1);
  for (st = dest; st < end; ++st) sq_clip_clear_step_locks(s, dst, (uint16_t)st);
  base_tick = (uint32_t)dest * SQ_TPS;
  n = sq_clips(s)[cb].seg[SQ_K_NOTES].len;
  for (i = 0; i < n; ++i) {
    const sq_note_t x = *sq_cnote(s, &sq_clips(s)[cb], i);
    sq_clip_add_raw(s, dst, (uint16_t)(dest + SQ_NSTEP(&x)), base_tick + x.tick, x.gate, x.pitch,
                    x.vel);
  }
  n = sq_clips(s)[cb].seg[SQ_K_LOCKS].len;
  for (i = 0; i < n; ++i) {
    const sq_lock_t l = *sq_clock(s, &sq_clips(s)[cb], i);
    sq_clip_set_lock(s, dst, l.lane, (uint16_t)(dest + l.step), l.val);
  }
}

void sq_clear_clipboard(fm1_seq_t *s) {
  sq_seg_clear(s, SQ_CLIP_STEPCB(s), SQ_K_NOTES);
  sq_seg_clear(s, SQ_CLIP_STEPCB(s), SQ_K_LOCKS);
}

/* ---- Transport (R10) ----------------------------------------------------- */

static void start_transport(fm1_seq_t *s) {
  unsigned t;
  for (t = 0; t < s->n_tracks; ++t) {
    sq_track_t *tr = &sq_tracks(s)[t];
    tr->pos_tick = 0;
    if (tr->playing != SQ_NONE) {
      tr->pos_tick = (uint16_t)sq_start_ticks(sq_clip(s, t, tr->playing));
      sq_clip_release_pass(s, sq_clip_no(t, tr->playing));
    }
    tr->last_auto_step = -1;
    memset(tr->auto_cur, 0xFF, sizeof(tr->auto_cur));
    tr->cycle = 1;
    tr->scale_acc = 0;
  }
  clock_reset(s);
  s->master_tick = 0;
  s->bar_tick = 0;
  s->playing = 1;
}

/* song_entry_at: (scene, repeats) of the entry starting at raw index i. */
static int song_entry_at(const fm1_seq_t *s, unsigned i, unsigned *scene, unsigned *reps) {
  const uint8_t *song = sq_csong(s);
  unsigned j;
  if (i >= s->song_len) return 0;
  *scene = song[i];
  for (j = i; j < s->song_len && song[j] == song[i]; ++j) {}
  *reps = j - i;
  return 1;
}

static unsigned song_next_pos(const fm1_seq_t *s, unsigned i) {
  unsigned scene, reps;
  if (!song_entry_at(s, i, &scene, &reps)) return 0;
  return i + reps >= s->song_len ? 0 : i + reps;
}

static void capture_reset_on_transport(fm1_seq_t *s) { sq_capture_clear(s); }

void sq_play(fm1_seq_t *s) {
  unsigned scene, reps, t;
  if (song_entry_at(s, 0, &scene, &reps)) {
    s->song_pos = 0;
    s->song_has_start = 0;
    s->song_armed = 0;
    s->song_armed_launch = SQ_NONE;
    for (t = 0; t < s->n_tracks; ++t) {
      sq_track_t *tr = &sq_tracks(s)[t];
      tr->active = (uint8_t)scene;
      tr->playing = sq_exists(sq_clip(s, t, scene)) ? (uint8_t)scene : SQ_NONE;
      tr->queued = SQ_NONE;
      tr->pending_stop = 0;
    }
    capture_reset_on_transport(s);
    start_transport(s);
    return;
  }
  for (t = 0; t < s->n_tracks; ++t) {
    sq_track_t *tr = &sq_tracks(s)[t];
    tr->playing = sq_exists(sq_clip(s, t, tr->active)) ? tr->active : SQ_NONE;
    tr->queued = SQ_NONE;
    tr->pending_stop = 0;
  }
  capture_reset_on_transport(s);
  start_transport(s);
}

void sq_ensure_selected_playing(fm1_seq_t *s, unsigned t) {
  sq_track_t *tr;
  if (!s->playing || !track_ok(s, t)) return;
  tr = &sq_tracks(s)[t];
  if (tr->playing == tr->active) {
    tr->pending_stop = 0;
    return;
  }
  tr->queued = tr->active;
  tr->pending_stop = 0;
}

void sq_clear_song(fm1_seq_t *s) {
  s->song_len = 0;
  s->song_pos = 0;
  s->song_has_start = 0;
  s->song_armed = 0;
  s->song_armed_launch = SQ_NONE;
}

/* launch_clip (engine.rs 657-684, R11). */
void sq_launch_clip(fm1_seq_t *s, unsigned t, unsigned slot) {
  sq_track_t *tr;
  int exists;
  if (!track_ok(s, t) || slot >= FM1_SEQ_SLOTS) return;
  sq_clear_song(s);
  tr = &sq_tracks(s)[t];
  tr->active = (uint8_t)slot;
  tr->pending_select = SQ_NONE;
  exists = sq_exists(sq_clip(s, t, slot));
  if (s->playing) {
    if (exists) {
      tr->queued = (uint8_t)slot;
      tr->pending_stop = 0;
    } else {
      tr->pending_stop = 1;
      tr->queued = SQ_NONE;
    }
  } else if (exists) {
    tr->playing = (uint8_t)slot;
    start_transport(s);
  } else {
    tr->playing = SQ_NONE;
  }
}

static uint32_t scene_bars(const fm1_seq_t *s, unsigned slot) {
  uint32_t bars = 1;
  unsigned t;
  if (slot >= FM1_SEQ_SLOTS) return 1;
  for (t = 0; t < s->n_tracks; ++t) {
    const sq_clip_t *c = sq_cclip(s, t, slot);
    if (sq_exists(c)) {
      const uint32_t b = (c->length_steps + SQ_BAR_STEPS - 1u) / SQ_BAR_STEPS;
      if (b > bars) bars = b;
    }
  }
  return bars;
}

static int scene_is_empty(const fm1_seq_t *s, unsigned slot) {
  unsigned t;
  if (slot >= FM1_SEQ_SLOTS) return 1;
  for (t = 0; t < s->n_tracks; ++t) {
    if (sq_exists(sq_cclip(s, t, slot))) return 0;
  }
  return 1;
}

/* launch_scene (engine.rs 724-763). */
void sq_launch_scene(fm1_seq_t *s, unsigned slot) {
  unsigned t;
  int any = 0;
  const int playing = s->playing;
  if (slot >= FM1_SEQ_SLOTS) return;
  for (t = 0; t < s->n_tracks; ++t) {
    sq_track_t *tr = &sq_tracks(s)[t];
    const int exists = sq_exists(sq_clip(s, t, slot));
    any |= exists;
    if (playing) {
      if (exists) {
        tr->queued = (uint8_t)slot;
        tr->pending_stop = 0;
      } else {
        tr->pending_stop = 1;
        tr->queued = SQ_NONE;
        tr->pending_select = (uint8_t)slot;
      }
    } else {
      tr->active = (uint8_t)slot;
      tr->playing = exists ? (uint8_t)slot : SQ_NONE;
      tr->queued = SQ_NONE;
      tr->pending_stop = 0;
    }
  }
  if (!playing && any) start_transport(s);
}

/* song_try_arm (engine.rs 909-944). */
static void song_try_arm(fm1_seq_t *s, uint64_t bar) {
  unsigned scene, reps, next, next_scene, next_reps;
  uint64_t start, total;
  if (s->song_armed) return;
  if (!song_entry_at(s, s->song_pos, &scene, &reps)) return;
  if (scene_is_empty(s, scene)) return;
  start = s->song_has_start ? s->song_start_bar : bar;
  total = (uint64_t)scene_bars(s, scene) * reps;
  if ((uint32_t)(bar > start ? bar - start : 0) + 1u < total) return;
  next = song_next_pos(s, s->song_pos);
  if (song_entry_at(s, next, &next_scene, &next_reps)) {
    if (next_scene != scene) {
      sq_launch_scene(s, next_scene);
      s->song_armed_launch = (uint8_t)next_scene;
    } else {
      s->song_armed_launch = SQ_NONE;
    }
    s->song_armed = 1;
  }
}

/* song_bar (engine.rs 869-899), after the queue has resolved. */
static void song_bar(fm1_seq_t *s) {
  uint64_t bar, start;
  unsigned scene, reps;
  if (s->song_len == 0 || !s->playing) return;
  bar = s->master_tick / SQ_TPB;
  if (!s->song_has_start) {
    s->song_start_bar = bar;
    s->song_has_start = 1;
  }
  start = s->song_start_bar;
  if (song_entry_at(s, s->song_pos, &scene, &reps)) {
    if (scene_is_empty(s, scene)) return;
    if (s->song_armed && (uint32_t)(bar - start) >= scene_bars(s, scene) * reps) {
      s->song_pos = (uint16_t)song_next_pos(s, s->song_pos);
      s->song_start_bar = bar;
      s->song_has_start = 1;
      s->song_armed = 0;
      s->song_armed_launch = SQ_NONE;
    }
  }
  song_try_arm(s, bar);
}

void sq_song_start(fm1_seq_t *s, unsigned slot) {
  if (slot >= FM1_SEQ_SLOTS) return;
  sq_clear_song(s);
  if (s->lim.song == 0) {
    ++s->stats.refused;
    return;
  }
  sq_song(s)[s->song_len++] = (uint8_t)slot;
  sq_launch_scene(s, slot);
}

/* song_add (engine.rs 824-862). */
void sq_song_add(fm1_seq_t *s, unsigned slot) {
  if (slot >= FM1_SEQ_SLOTS || s->song_len == 0) return;
  if (s->song_len >= s->lim.song) {
    ++s->stats.refused;
    return;
  }
  sq_song(s)[s->song_len++] = (uint8_t)slot;
  if (s->song_armed && s->song_armed_launch == SQ_NONE) {
    unsigned cur, reps, nxt, nreps;
    const int has_cur = song_entry_at(s, s->song_pos, &cur, &reps);
    const unsigned next = song_next_pos(s, s->song_pos);
    const int has_nxt = song_entry_at(s, next, &nxt, &nreps);
    if (has_cur && (!has_nxt || nxt != cur)) {
      s->song_armed = 0;
      s->song_armed_launch = SQ_NONE;
    }
  }
  if (s->playing && s->song_has_start) song_try_arm(s, s->master_tick / SQ_TPB);
}

void sq_stop_track(fm1_seq_t *s, unsigned t) {
  if (!track_ok(s, t)) return;
  if (s->playing) sq_tracks(s)[t].pending_stop = 1;
  else sq_tracks(s)[t].playing = SQ_NONE;
}

/* ---- Recording (engine.rs 1101-1164, 1620-1803, R12) ---------------------- */

static void commit_rec_note(fm1_seq_t *s, sq_rec_t p, int tail);

/* `for p in take(&mut rec_tail)`: the list is emptied first; committing a
 * note never adds to it, so its entries can be read in place. */
static void commit_rec_tail(fm1_seq_t *s) {
  unsigned i;
  const unsigned n = s->n_tail;
  s->n_tail = 0;
  for (i = 0; i < n; ++i) commit_rec_note(s, sq_tail(s)[i], 1);
}

/* rec_tail.append(&mut rec_pending). */
static void pending_to_tail(fm1_seq_t *s) {
  unsigned i;
  for (i = 0; i < s->n_pend; ++i) {
    if (s->n_tail >= s->lim.rec_notes) {
      ++s->stats.refused;
      continue;
    }
    sq_tail(s)[s->n_tail++] = sq_pend(s)[i];
  }
  s->n_pend = 0;
}

static void drop_rec_notes_for(fm1_seq_t *s, unsigned t, unsigned slot) {
  unsigned r, w = 0;
  sq_rec_t *p = sq_pend(s);
  for (r = 0; r < s->n_pend; ++r) {
    if (p[r].track == t && p[r].slot == slot) continue;
    p[w++] = p[r];
  }
  s->n_pend = (uint8_t)w;
  p = sq_tail(s);
  w = 0;
  for (r = 0; r < s->n_tail; ++r) {
    if (p[r].track == t && p[r].slot == slot) continue;
    p[w++] = p[r];
  }
  s->n_tail = (uint8_t)w;
}

void sq_toggle_record(fm1_seq_t *s, unsigned t) {
  sq_track_t *tr;
  unsigned a;
  int was_playing;
  if (!track_ok(s, t)) return;
  if (s->recording || s->count_in_left > 0 || s->pending_rec) {
    if (s->pending_rec) sq_tracks(s)[s->rec_track].queued = SQ_NONE;
    s->recording = 0;
    s->count_in_left = 0;
    s->pending_rec = 0;
    pending_to_tail(s);
    return;
  }
  commit_rec_tail(s);
  s->rec_track = (uint8_t)t;
  s->watch_track = (uint8_t)t;
  tr = &sq_tracks(s)[t];
  s->rec_empty_start = sq_clip(s, t, tr->active)->seg[SQ_K_NOTES].len == 0;
  was_playing = s->playing;
  a = tr->active;
  sq_clip_ensure_exists(s, sq_clip_no(t, a));
  tr->pending_stop = 0;
  if (!was_playing) {
    tr->playing = (uint8_t)a;
    tr->queued = SQ_NONE;
    sq_play(s);
    s->count_in_left = SQ_TPB;
  } else if (s->rec_empty_start) {
    tr->queued = (uint8_t)a;
    s->pending_rec = 1;
  } else {
    tr->playing = (uint8_t)a;
    if (s->song_len == 0) tr->queued = SQ_NONE;
    s->recording = 1;
  }
}

/* preroll_offset (engine.rs 1634-1646). */
static int preroll_offset(const fm1_seq_t *s, int32_t *off) {
  uint32_t left;
  if (s->pending_rec) {
    left = SQ_TPB - s->bar_tick;
  } else {
    left = s->count_in_left;
  }
  if (left > 0 && left <= SQ_TPS / 2u) {
    *off = -(int32_t)left;
    return 1;
  }
  return 0;
}

static int64_t rec_gate_limit(const sq_rec_t *p, int tail, int64_t span, int64_t end) {
  int64_t v;
  if (!tail) return span;
  v = end - (p->start_tick > 0 ? p->start_tick : 0);
  return v < 1 ? 1 : (v > span ? span : v);
}

/* commit_rec_note (engine.rs 1652-1690). D4: outside a growing first take, a
 * note whose anchor falls on the loop end is clamped to the last step rather
 * than growing the clip by a bar. */
static void commit_rec_note(fm1_seq_t *s, sq_rec_t p, int tail) {
  const sq_track_t *tr;
  const sq_clip_t *c;
  int64_t now, span, end, laps, limit, g;
  uint32_t cycle, tick;
  uint16_t step;
  uint8_t stored;
  int32_t pitch;
  if (p.track >= s->n_tracks || p.slot >= FM1_SEQ_SLOTS) return;
  c = sq_clip(s, p.track, p.slot);
  if (!sq_exists(c)) return;
  tr = &sq_tracks(s)[p.track];
  now = tr->pos_tick;
  cycle = tr->cycle;
  span = (int64_t)(sq_len_ticks(c) ? sq_len_ticks(c) : 1u);
  end = (int64_t)sq_end_ticks(c);
  laps = (int64_t)((cycle - p.start_cycle) < 64u ? (cycle - p.start_cycle) : 64u);
  limit = rec_gate_limit(&p, tail, span, end);
  g = laps * span + now - p.start_tick;
  if (g < 1) g = 1;
  if (g > limit) g = limit;
  pitch = (int32_t)p.pitch - clip_transpose(s, p.track, p.slot);
  stored = (uint8_t)(pitch < 0 ? 0 : (pitch > 127 ? 127 : pitch));
  tick = (uint32_t)(p.start_tick > 0 ? p.start_tick : 0);
  step = sq_anchor_step(s, tick, c->scale_num, c->scale_den);
  if (!s->lim.compat) {
    /* A first take keeps Movy's anchor on the loop end, and record_note grows
     * the clip a bar to hold it, unless the clip is already 16 bars long:
     * then the anchor (256) could not be reached, and Movy's fold-back (R5)
     * is what plays it, which D11 leaves out. */
    const uint32_t last = (uint32_t)c->loop_start + c->length_steps - 1u;
    const int growing = s->recording && s->rec_empty_start && p.track == s->rec_track &&
                        tr->playing == p.slot && last + 1u < SQ_MAX_STEPS;
    if (!growing && step > last) step = (uint16_t)last;
  }
  tick = sq_unswing(s, tick, step, c->scale_num, c->scale_den);   /* D10 */
  sq_clip_record_note(s, sq_clip_no(p.track, p.slot), step, tick, (uint32_t)g, stored, p.vel,
                      cycle == p.start_cycle);
}

static void expire_rec_tail(fm1_seq_t *s, unsigned t) {
  unsigned i = 0;
  const sq_track_t *tr = &sq_tracks(s)[t];
  while (i < s->n_tail) {
    const sq_rec_t p = sq_tail(s)[i];
    const sq_clip_t *c;
    int64_t span, end, laps;
    if (p.track != t || p.slot >= FM1_SEQ_SLOTS) {
      ++i;
      continue;
    }
    c = sq_clip(s, t, p.slot);
    span = (int64_t)(sq_len_ticks(c) ? sq_len_ticks(c) : 1u);
    end = (int64_t)sq_end_ticks(c);
    laps = (int64_t)((tr->cycle - p.start_cycle) < 64u ? (tr->cycle - p.start_cycle) : 64u);
    if (laps * span + tr->pos_tick - p.start_tick >= rec_gate_limit(&p, 1, span, end)) {
      sq_tail(s)[i] = sq_tail(s)[s->n_tail - 1u];
      --s->n_tail;
      commit_rec_note(s, p, 1);
    } else {
      ++i;
    }
  }
}

void sq_live_note_on(fm1_seq_t *s, unsigned t, uint8_t pitch, uint8_t vel, uint64_t frame) {
  int32_t start;
  sq_rec_t *p;
  sq_capture_push(s, t, pitch, vel, 1, frame);
  if (!track_ok(s, t) || t != s->rec_track) return;
  if (s->recording) {
    start = sq_tracks(s)[t].pos_tick;
  } else if (!preroll_offset(s, &start)) {
    return;
  }
  if (s->n_pend >= s->lim.rec_notes) {
    ++s->stats.refused;
    return;
  }
  p = &sq_pend(s)[s->n_pend++];
  memset(p, 0, sizeof(*p));
  p->pitch = pitch;
  p->vel = vel;
  p->start_tick = (int16_t)start;
  p->track = (uint8_t)t;
  p->slot = sq_tracks(s)[t].active;
  p->start_cycle = sq_tracks(s)[t].cycle;
}

void sq_live_note_off(fm1_seq_t *s, unsigned t, uint8_t pitch, uint64_t frame) {
  unsigned i;
  sq_capture_push(s, t, pitch, 0, 0, frame);
  if (!track_ok(s, t) || t != s->rec_track) return;
  for (i = s->n_pend; i-- > 0;) {
    if (sq_pend(s)[i].pitch == pitch) {
      const sq_rec_t p = sq_pend(s)[i];
      sq_pend(s)[i] = sq_pend(s)[s->n_pend - 1u];
      --s->n_pend;
      commit_rec_note(s, p, 0);
      return;
    }
  }
  for (i = s->n_tail; i-- > 0;) {
    if (sq_tail(s)[i].pitch == pitch) {
      const sq_rec_t p = sq_tail(s)[i];
      sq_tail(s)[i] = sq_tail(s)[s->n_tail - 1u];
      --s->n_tail;
      commit_rec_note(s, p, 1);
      return;
    }
  }
}

/* stop (engine.rs 960-981). D6: lanes whose last value differs from their
 * base are sent back to it, after the note-offs. */
void sq_stop(fm1_seq_t *s, sq_out_t *o) {
  unsigned t, lane;
  s->playing = 0;
  s->recording = 0;
  s->count_in_left = 0;
  s->pending_rec = 0;
  pending_to_tail(s);
  commit_rec_tail(s);
  sq_capture_clear(s);
  s->song_pos = 0;
  s->song_has_start = 0;
  s->song_armed = 0;
  s->song_armed_launch = SQ_NONE;
  flush_gates(s, o);
  for (t = 0; t < s->n_tracks; ++t) {
    sq_track_t *tr = &sq_tracks(s)[t];
    for (lane = 0; lane < FM1_SEQ_LANES; ++lane) revert_lane(s, t, lane, o);
    tr->last_auto_step = -1;
    memset(tr->auto_cur, 0xFF, sizeof(tr->auto_cur));
  }
}

/* ---- The scheduler (R2-R8) --------------------------------------------------- */

/* emit_automation (engine.rs 2263-2285, R8): the step's lock, else the base if
 * a note is anchored there, else the carried value; sent only on change. */
static void emit_automation(fm1_seq_t *s, unsigned t, unsigned slot, uint16_t step, sq_out_t *o) {
  sq_track_t *tr = &sq_tracks(s)[t];
  const unsigned clip = sq_clip_no(t, slot);
  int has_notes = -1;
  unsigned lane;
  for (lane = 0; lane < FM1_SEQ_LANES; ++lane) {
    fm1_seq_val_t v;
    if (!(tr->lanes_assigned & (1u << lane))) continue;
    if (!sq_clip_lock_at(s, clip, (uint8_t)lane, step, &v)) {
      if (has_notes < 0) has_notes = sq_clip_has_notes_at(s, clip, step);
      if (has_notes) {
        v = tr->base[lane];
      } else {
        v = tr->auto_cur[lane] >= 0 ? (fm1_seq_val_t)tr->auto_cur[lane] : tr->base[lane];
      }
    }
    if ((int16_t)v != tr->auto_cur[lane] && sq_emit(o, FM1_SEQ_EV_LOCK, (uint8_t)t, (uint8_t)lane, v)) {
      tr->auto_cur[lane] = (int16_t)v;
    }
  }
}

/* The notes of this clip due at `pos`, in insertion order (R4 b, R7). Movy
 * scans every note and recomputes its fire tick; the index visits only the
 * due ones, in the same order, so the RNG is consumed identically. */
static void scan_notes(fm1_seq_t *s, unsigned t, unsigned slot, uint16_t pos, sq_out_t *o) {
  const unsigned clip = sq_clip_no(t, slot);
  sq_clip_t *c;
  sq_note_t *n;
  unsigned count, lo, hi, j, k;
  const int transpose = clip_transpose(s, t, slot);
  const uint32_t cycle = sq_tracks(s)[t].cycle;
  sq_clip_index(s, clip);
  c = &sq_clips(s)[clip];
  n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
  count = c->seg[SQ_K_NOTES].len;
#ifdef SQ_CHECK_INDEX
  sq_check_index(s, clip);
#endif
  lo = 0;
  hi = count;
  while (lo < hi) {                     /* first index entry with fire >= pos */
    const unsigned mid = (lo + hi) / 2u;
    if (n[n[mid].ix].fire < pos) lo = mid + 1u;
    else hi = mid;
  }
  for (j = lo; j < count && n[n[j].ix].fire == pos; ++j) {
    sq_note_t *x = &n[n[j].ix];
    const uint16_t step = SQ_NSTEP(x);
    uint8_t key;
    int play = -1;
    int32_t emit;
    if (x->step & (SQ_N_SUPPRESS | SQ_N_FIRED)) continue;
    x->step |= SQ_N_FIRED;
    /* A chord on one trig shares one decision, keyed by (step, lane key). */
    key = sq_clip_has_trig_row(s, clip, step, x->pitch) ? x->pitch : SQ_NONE;
    for (k = lo; k < j && play < 0; ++k) {
      const sq_note_t *y = &n[n[k].ix];
      if (!(y->step & SQ_N_DECIDED) || SQ_NSTEP(y) != step) continue;
      if ((sq_clip_has_trig_row(s, clip, step, y->pitch) ? y->pitch : SQ_NONE) != key) continue;
      play = (y->step & SQ_N_PLAYS) ? 1 : 0;
    }
    if (play < 0) {
      const sq_props_t tp = sq_clip_governing_trig(s, clip, step, x->pitch);
      play = condition_plays(tp.a, tp.b, tp.inv, cycle) && (tp.prob >= 100 || roll_pct(s) < tp.prob);
    }
    x->step |= (uint16_t)(SQ_N_DECIDED | (play ? SQ_N_PLAYS : 0u));
    if (!play) continue;
    emit = (int32_t)x->pitch + transpose;
    emit = emit < 0 ? 0 : (emit > 127 ? 127 : emit);
    if (sq_pad_voice_silent(s, t, (uint8_t)emit)) continue;
    gate_make_room(s, o);
    if (sq_emit(o, FM1_SEQ_EV_NOTE_ON, (uint8_t)t, (uint8_t)emit, x->vel)) {
      gate_push(s, (uint8_t)t, (uint8_t)emit, x->gate);
    }
  }
  for (k = lo; k < j; ++k) n[n[k].ix].step &= (uint16_t)~(SQ_N_DECIDED | SQ_N_PLAYS);
}

/* D9: the locks of a step just entered lead its notes by one clip tick. If a
 * bar launch or stop already queued for this track falls before the track's
 * next step_tick, that step never plays, and Movy's look-ahead would send a
 * value for nothing (and then, D2, the new clip's own). Called inside
 * step_tick, where master_tick and bar_tick already count the tick being
 * serviced and scale_acc holds what is left after this step_tick. */
static int replaced_before_next_step(const fm1_seq_t *s, unsigned t) {
  const sq_track_t *tr = &sq_ctracks(s)[t];
  const sq_clip_t *c = sq_cclip(s, t, tr->playing);
  const uint32_t num = c->scale_num ? c->scale_num : 1u, den = c->scale_den ? c->scale_den : 1u;
  uint32_t to_bar, wait;
  if (tr->queued == SQ_NONE && !tr->pending_stop) return 0;
  if (tr->scale_acc >= den) return 0;                     /* another step_tick this tick */
  to_bar = s->bar_tick ? SQ_TPB - s->bar_tick : 0u;      /* service ticks before the bar's */
  wait = (den - tr->scale_acc + num - 1u) / num;          /* service ticks to the next step_tick */
  return wait > to_bar;
}

/* step_tick (engine.rs 2100-2255, R4): offs, (D2 locks), ons, advance and
 * wrap, then the locks of the step just entered (unless D9 drops them). */
static void step_tick(fm1_seq_t *s, unsigned t, sq_out_t *o) {
  sq_track_t *tr = &sq_tracks(s)[t];
  const unsigned slot = tr->playing;
  sq_clip_t *c;
  unsigned i;
  uint32_t start, end;
  int16_t cur;
  if (slot == SQ_NONE) return;
  c = sq_clip(s, t, slot);
  if (!sq_exists(c)) return;
  i = 0;
  while (i < s->n_gates) {
    sq_gate_t *g = &sq_gates(s)[i];
    if (g->track == t) {
      if (--g->left == 0) {
        const sq_gate_t done = *g;
        gate_swap_remove(s, i);
        sq_emit(o, FM1_SEQ_EV_NOTE_OFF, done.track, done.pitch, 0);
        continue;
      }
    }
    ++i;
  }
  if (!s->lim.compat && tr->last_auto_step == -1) {
    /* D2: the first step after Play or a launch gets its locks before its
     * notes, as every later step does. */
    tr->last_auto_step = (int16_t)(tr->pos_tick / SQ_TPS);
    emit_automation(s, t, slot, (uint16_t)tr->last_auto_step, o);
  }
  if (!tr->muted) scan_notes(s, t, slot, tr->pos_tick, o);
  c = sq_clip(s, t, slot);
  start = sq_start_ticks(c);
  end = sq_end_ticks(c);
  ++tr->pos_tick;
  if (tr->pos_tick >= end) {
    const int recording_here = s->recording && t == s->rec_track;
    if (recording_here && s->rec_empty_start && c->length_steps % SQ_BAR_STEPS == 0 &&
        (uint32_t)c->loop_start + c->length_steps + SQ_BAR_STEPS <= SQ_MAX_STEPS) {
      sq_clip_set_loop(s, sq_clip_no(t, slot), c->loop_start,
                       (uint16_t)(c->length_steps + SQ_BAR_STEPS));
    } else {
      tr->pos_tick = (uint16_t)start;
      sq_clip_release_pass(s, sq_clip_no(t, slot));
      ++tr->cycle;
    }
  }
  expire_rec_tail(s, t);
  cur = (int16_t)(tr->pos_tick / SQ_TPS);
  if (cur != tr->last_auto_step && !(!s->lim.compat && replaced_before_next_step(s, t))) {
    tr->last_auto_step = cur;
    emit_automation(s, t, slot, (uint16_t)cur, o);
  }
}

/* service_tick (engine.rs 1994-2095, R3). */
static void service_tick(fm1_seq_t *s, sq_out_t *o) {
  unsigned t, i;
  int skip_steps = 0;
  uint32_t stopped = 0;            /* tracks stopping at this bar (D6) */
  if (s->bar_tick % FM1_SEQ_PPQN == 0 && (s->count_in_left > 0 || s->metronome)) {
    sq_emit(o, FM1_SEQ_EV_CLICK, SQ_NONE, s->bar_tick == 0 ? 1 : 0, 0);
  }
  if (s->bar_tick == 0) {
    for (t = 0; t < s->n_tracks; ++t) {
      sq_track_t *tr = &sq_tracks(s)[t];
      if (tr->queued != SQ_NONE) {
        const unsigned slot = tr->queued;
        tr->queued = SQ_NONE;
        tr->playing = (uint8_t)slot;
        tr->active = (uint8_t)slot;
        tr->pos_tick = (uint16_t)sq_start_ticks(sq_clip(s, t, slot));
        sq_clip_release_pass(s, sq_clip_no(t, slot));
        tr->last_auto_step = -1;
        memset(tr->auto_cur, 0xFF, sizeof(tr->auto_cur));
        tr->cycle = 1;
      }
      if (tr->pending_stop) {
        tr->pending_stop = 0;
        tr->playing = SQ_NONE;
        stopped |= 1u << t;
      }
      if (tr->pending_select != SQ_NONE) {
        tr->active = tr->pending_select;
        tr->pending_select = SQ_NONE;
      }
    }
    if (s->pending_rec) {
      const uint32_t cycle = sq_tracks(s)[s->rec_track].cycle;
      s->pending_rec = 0;
      s->recording = 1;
      for (i = 0; i < s->n_pend; ++i) {
        if (sq_pend(s)[i].track == s->rec_track) sq_pend(s)[i].start_cycle = cycle;
      }
    }
    song_bar(s);
  }
  i = 0;
  while (i < s->n_gates) {
    const sq_gate_t g = sq_gates(s)[i];
    const sq_track_t *tr = &sq_tracks(s)[g.track];
    if (tr->playing != SQ_NONE && sq_exists(sq_clip(s, g.track, tr->playing))) {
      ++i;
    } else {
      gate_swap_remove(s, i);
      sq_emit(o, FM1_SEQ_EV_NOTE_OFF, g.track, g.pitch, 0);
    }
  }
  /* D6: a track that stopped at the bar sends its lanes back to their base,
   * after its note-offs, as Stop does; Movy leaves them. */
  for (t = 0; stopped && t < s->n_tracks; ++t) {
    sq_track_t *tr = &sq_tracks(s)[t];
    unsigned lane;
    if (!(stopped & (1u << t)) || s->lim.compat) continue;
    for (lane = 0; lane < FM1_SEQ_LANES; ++lane) revert_lane(s, t, lane, o);
    tr->last_auto_step = -1;
    memset(tr->auto_cur, 0xFF, sizeof(tr->auto_cur));
  }
  ++s->master_tick;
  if (++s->bar_tick == SQ_TPB) s->bar_tick = 0;
  if (s->count_in_left > 0) {
    if (--s->count_in_left == 0) {
      s->recording = 1;
      /* D3: Movy plays step 0 on this tick, one before the bar. */
      if (!s->lim.compat) skip_steps = 1;
    }
  }
  if (s->count_in_left == 0 && !skip_steps) {
    for (t = 0; t < s->n_tracks; ++t) {
      sq_track_t *tr = &sq_tracks(s)[t];
      const sq_clip_t *c;
      uint32_t num, den;
      if (tr->playing == SQ_NONE) continue;
      c = sq_clip(s, t, tr->playing);
      if (!sq_exists(c)) continue;
      num = c->scale_num ? c->scale_num : 1u;
      den = c->scale_den ? c->scale_den : 1u;
      tr->scale_acc = (uint16_t)(tr->scale_acc + num);
      while (tr->scale_acc >= den) {
        tr->scale_acc = (uint16_t)(tr->scale_acc - den);
        step_tick(s, t, o);
      }
    }
  }
}

/* ---- External clock follow (engine.rs 1805-1958) ------------------------------ */

static int follow_active(const fm1_seq_t *s) { return s->playing && s->ext_running; }

void sq_external_realtime(fm1_seq_t *s, uint8_t status, uint64_t frame, sq_out_t *o) {
  switch (status) {
  case 0xFA:
    if (s->link_enabled && !s->playing) sq_play(s);
    s->ext_running = 1;
    s->ext_awaiting_first = 1;
    s->ext_ticks = 0;
    s->ext_base = 0;
    s->ext_base_set = 1;
    s->ext_last_frame = frame;
    if (s->playing) {
      flush_gates(s, o);
      start_transport(s);
    }
    break;
  case 0xFB:
    s->ext_running = 1;
    break;
  case 0xFC:
    if (s->link_enabled && s->playing) sq_stop(s, o);
    s->ext_running = 0;
    break;
  case 0xF8:
    if (!s->ext_running) {
      s->ext_running = 1;
      s->ext_awaiting_first = 1;
    }
    if (s->ext_awaiting_first) {
      s->ext_awaiting_first = 0;
      s->ext_ticks = 0;
    } else {
      const float delta = (float)(frame > s->ext_last_frame ? frame - s->ext_last_frame : 0u);
      const float sr = (float)s->sample_rate;
      ++s->ext_ticks;
      if (delta >= 60.0f * sr / (999.0f * 24.0f) && delta <= 60.0f * sr / (20.0f * 24.0f)) {
        float bpm;
        s->ext_interval = s->ext_interval <= 0.0f ? delta
                                                  : s->ext_interval + 0.25f * (delta - s->ext_interval);
        bpm = 60.0f * 100.0f * sr / (s->ext_interval * 24.0f) + 0.5f;
        sq_set_bpm(s, bpm >= 4294967295.0f ? 0xFFFFFFFFu : (uint32_t)bpm);
      }
    }
    s->ext_last_frame = frame;
    break;
  default:
    break;
  }
}

/* ---- One block (R1, R2, D1) ------------------------------------------------------ */

/* The playhead target while following (engine.rs 1938-1948): Move's ticks at
 * 96 PPQN, plus the fraction of an interval since the last one, measured at
 * `frame_now`. Float where Movy uses f64. */
static uint64_t follow_target(const fm1_seq_t *s, uint64_t frame_now) {
  uint64_t abs = s->ext_ticks * 4u;
  if (s->ext_interval > 0.0f) {
    const uint64_t since = frame_now > s->ext_last_frame ? frame_now - s->ext_last_frame : 0;
    float frac = (float)since / s->ext_interval;
    if (frac > 1.0f) frac = 1.0f;
    abs += (uint64_t)(frac * 4.0f);
  }
  return abs > s->ext_base * 4u ? abs - s->ext_base * 4u : 0;
}

/* D1 while following: the frame of the block (0-based) at which the target,
 * advancing frame by frame from `first` (the block's first frame number
 * after it), first reaches `tick` + 1, which is when Movy fed one frame at a
 * time would fire it. */
static uint16_t follow_frame(const fm1_seq_t *s, uint64_t first, uint32_t frames, uint64_t tick) {
  uint32_t lo = 0, hi = frames ? frames - 1u : 0u;
  while (lo < hi) {
    const uint32_t mid = lo + (hi - lo) / 2u;
    if (follow_target(s, first + mid) > tick) hi = mid;
    else lo = mid + 1u;
  }
  return (uint16_t)lo;
}

uint32_t fm1_seq_advance(fm1_seq_t *s, uint32_t frames, fm1_seq_ev_t *out, uint32_t cap) {
  sq_out_t o;
  uint64_t fired, j, need = 0, inc = 0;
  int following;
  out_init(&o, s, out, cap);
  s->frame_now += frames;

  if (s->ext_running && s->ext_last_frame > 0 && s->frame_now > s->ext_last_frame &&
      s->frame_now - s->ext_last_frame > (uint64_t)s->sample_rate / 2u) {
    s->ext_running = 0;
  }
  following = follow_active(s);
  if (following && !s->was_following) {
    if (s->emitting_clock) {
      s->emitting_clock = 0;
      sq_emit(&o, FM1_SEQ_EV_STOP, SQ_NONE, 0, 0);
    }
    s->resume_anchor_pending = 0;
    if (!s->ext_base_set) {
      s->ext_base = (s->ext_ticks / 96u + 1u) * 96u;
      s->ext_base_set = 1;
      start_transport(s);
    }
  } else if (!following && s->was_following) {
    clock_reset(s);
    s->clock_tick = s->master_tick;
    s->ext_base_set = 0;
    if (s->playing) s->resume_anchor_pending = 1;
  }
  s->was_following = (uint8_t)following;

  if (following) {
    const uint64_t target = follow_target(s, s->frame_now);
    fired = target > s->master_tick ? target - s->master_tick : 0;
    if (fired > 96) fired = 96;
  } else {
    /* clock.advance: whole ticks in this block, by subtraction (at most one
     * at the FM-1's 64-frame blocks; no 64-bit division). For D1, tick j
     * (1-based) falls in the frame where the running sum first reaches j
     * thresholds: `need` is that sum's distance from the block's start. */
    inc = (uint64_t)s->bpm_x100 * FM1_SEQ_PPQN;
    need = s->threshold - s->accum;                          /* > 0 */
    s->accum += (uint64_t)frames * inc;
    fired = 0;
    while (s->accum >= s->threshold) {
      s->accum -= s->threshold;
      ++fired;
    }
    s->clock_tick += fired;
  }

  if (s->playing && !s->emitting_clock && !following && !s->resume_anchor_pending) {
    if (sq_emit(&o, FM1_SEQ_EV_START, SQ_NONE, 0, 0)) s->emitting_clock = 1;
  } else if (!s->playing && s->emitting_clock) {
    if (sq_emit(&o, FM1_SEQ_EV_STOP, SQ_NONE, 0, 0)) s->emitting_clock = 0;
  }
  if (!s->playing) return o.n;
  for (j = 1; j <= fired; ++j, need += s->threshold) {
    if (s->lim.compat == FM1_SEQ_COMPAT_MOVY) {
      o.frame = 0;                       /* Movy: every event at the block start */
    } else if (following) {
      o.frame = follow_frame(s, s->frame_now - frames + 1u, frames, s->master_tick);
    } else {
      /* ceil(need / inc) - 1, in 32 bits whenever it fits (always at the
       * FM-1's block size: 64 frames x 2,880,000 < 2^32). */
      const uint64_t q = need + inc - 1u;
      o.frame = (uint16_t)((q <= 0xFFFFFFFFu ? (uint32_t)q / (uint32_t)inc : q / inc) - 1u);
    }
    o.tick = (uint32_t)s->master_tick;
    if (s->resume_anchor_pending && !following && s->bar_tick == 0 &&
        sq_emit(&o, FM1_SEQ_EV_START, SQ_NONE, 0, 0)) {
      s->resume_anchor_pending = 0;
      s->emitting_clock = 1;
    }
    if (s->emitting_clock && !following && (s->bar_tick & 3u) == 0) {
      sq_emit(&o, FM1_SEQ_EV_CLOCK, SQ_NONE, 0, 0);
    }
    service_tick(s, &o);
  }
  return o.n;
}

uint32_t fm1_seq_realtime_in(fm1_seq_t *s, uint16_t frame, uint8_t status, fm1_seq_ev_t *out,
                             uint32_t cap) {
  sq_out_t o;
  out_init(&o, s, out, cap);
  sq_external_realtime(s, status, s->frame_now + (s->lim.compat ? 0u : frame), &o);
  return o.n;
}

void fm1_seq_note_in(fm1_seq_t *s, uint16_t frame, uint8_t track, uint8_t pitch, uint8_t vel) {
  const uint64_t at = s->frame_now + (s->lim.compat ? 0u : frame);
  if (pitch > 127) return;
  if (vel) sq_live_note_on(s, track, pitch, vel > 127 ? 127 : vel, at);
  else sq_live_note_off(s, track, pitch, at);
}

/* ---- Getters --------------------------------------------------------------------- */

void fm1_seq_get_info(const fm1_seq_t *s, fm1_seq_info_t *i) {
  memset(i, 0, sizeof(*i));
  i->master_tick = s->master_tick;
  i->bpm_x100 = s->bpm_x100;
  i->swing_pct = (uint16_t)s->swing_pct;
  i->playing = s->playing;
  i->recording = s->recording;
  i->counting_in = s->count_in_left > 0 || s->pending_rec;
  i->metronome = s->metronome;
  i->link = s->link_enabled;
  i->following = (uint8_t)follow_active(s);
  i->watch_track = s->watch_track;
  i->compat = s->lim.compat;
  i->song_len = s->song_len;
  i->song_pos = (uint8_t)s->song_pos;
  i->default_quant = s->default_quant;
  i->tracks = s->n_tracks;
  memcpy(i->song, sq_csong(s), s->song_len);
  i->capture_gen = s->capture_gen;
  i->capture_pending = (uint16_t)sq_capture_pending((fm1_seq_t *)(uintptr_t)s, s->watch_track);
  i->capture_mode = s->cap_mode;
  i->capture_n = s->cap_n;
  i->capture_sel = s->cap_sel;
  memcpy(i->capture_cands, s->cap_cands, sizeof(i->capture_cands));
  i->rec_track = s->rec_track;
}

void fm1_seq_get_clock(const fm1_seq_t *s, fm1_seq_clock_t *o) {
  memset(o, 0, sizeof(*o));
  o->master_tick = s->master_tick;
  o->accum = s->accum;
  o->threshold = s->threshold;
  /* advance's own increment; its ticks fall on this grid unless they follow
   * an external clock or are Movy's, all at the block's start */
  o->inc = follow_active(s) || s->lim.compat == FM1_SEQ_COMPAT_MOVY
               ? 0u : (uint64_t)s->bpm_x100 * FM1_SEQ_PPQN;
  o->bpm_x100 = s->bpm_x100;
  o->playing = s->playing;
}

int fm1_seq_get_track(const fm1_seq_t *s, uint8_t t, fm1_seq_track_info_t *o) {
  const sq_track_t *tr;
  if (t >= s->n_tracks) return 0;
  tr = &sq_ctracks(s)[t];
  memset(o, 0, sizeof(*o));
  o->cycle = tr->cycle;
  o->pos_tick = tr->pos_tick;
  o->last_auto_step = tr->last_auto_step;
  memcpy(o->auto_cur, tr->auto_cur, sizeof(o->auto_cur));
  memcpy(o->base, tr->base, sizeof(o->base));
  o->lanes_assigned = tr->lanes_assigned;
  o->active = tr->active;
  o->playing = tr->playing;
  o->queued = tr->queued;
  o->pending_select = tr->pending_select;
  o->pending_stop = tr->pending_stop;
  o->muted = tr->muted;
  o->drum = tr->drum;
  o->pad_solo = tr->pad_solo;
  o->route_kind = tr->route_kind;
  o->route_index = tr->route_index;
  return 1;
}

const char *fm1_seq_lane_label(const fm1_seq_t *s, uint8_t t, uint8_t lane) {
  if (t >= s->n_tracks || lane >= FM1_SEQ_LANES) return "";
  return sq_ctracks(s)[t].label[lane];
}

int fm1_seq_get_clip(const fm1_seq_t *s, uint8_t t, uint8_t slot, fm1_seq_clip_info_t *o) {
  const sq_clip_t *c;
  if (t >= s->n_tracks || slot >= FM1_SEQ_SLOTS) return 0;
  c = sq_cclip(s, t, slot);
  o->length_steps = c->length_steps;
  o->loop_start = c->loop_start;
  o->scale_num = c->scale_num;
  o->scale_den = c->scale_den;
  o->quant = c->quant;
  o->transpose = c->transpose;
  o->notes = c->seg[SQ_K_NOTES].len;
  o->locks = c->seg[SQ_K_LOCKS].len;
  o->trigs = c->seg[SQ_K_TRIGS].len;
  return 1;
}

int fm1_seq_get_note(const fm1_seq_t *s, uint8_t t, uint8_t slot, uint16_t i,
                     fm1_seq_note_info_t *o) {
  const sq_clip_t *c;
  const sq_note_t *n;
  if (t >= s->n_tracks || slot >= FM1_SEQ_SLOTS) return 0;
  c = sq_cclip(s, t, slot);
  if (i >= c->seg[SQ_K_NOTES].len) return 0;
  n = &sq_cnotes(s)[c->seg[SQ_K_NOTES].off + i];
  o->tick = n->tick;
  o->gate = n->gate;
  o->step = SQ_NSTEP(n);
  o->pitch = n->pitch;
  o->vel = n->vel;
  o->suppress = (n->step & SQ_N_SUPPRESS) ? 1 : 0;
  o->fired = (n->step & SQ_N_FIRED) ? 1 : 0;
  return 1;
}

/* One pass over each of the clip's three lists (docs/15 §2.5): notes counted
 * on their anchor step, each lock on its lane's bit, each trig row on its
 * step's flags, the whole-step row's values kept. Movy keeps at most one
 * lock per (lane, step) and one row per (step, lane), as the core does. */
int fm1_seq_get_page(const fm1_seq_t *s, uint8_t t, uint8_t slot, uint16_t first, uint16_t n,
                     fm1_seq_step_info_t *out) {
  const sq_clip_t *c;
  unsigned i;
  if (t >= s->n_tracks || slot >= FM1_SEQ_SLOTS) return 0;
  c = sq_cclip(s, t, slot);
  for (i = 0; i < n; ++i) {
    memset(&out[i], 0, sizeof(out[i]));
    out[i].prob = 100;
    out[i].cond_a = 1;
    out[i].cond_b = 1;
  }
  {
    const sq_note_t *nt = &sq_cnotes(s)[c->seg[SQ_K_NOTES].off];
    for (i = 0; i < c->seg[SQ_K_NOTES].len; ++i) {
      const unsigned k = (unsigned)SQ_NSTEP(&nt[i]) - first;
      if (SQ_NSTEP(&nt[i]) >= first && k < n && out[k].notes < 255u) ++out[k].notes;
    }
  }
  {
    const sq_lock_t *l = &sq_clocks(s)[c->seg[SQ_K_LOCKS].off];
    for (i = 0; i < c->seg[SQ_K_LOCKS].len; ++i) {
      const unsigned k = (unsigned)l[i].step - first;
      if (l[i].step >= first && k < n && l[i].lane < FM1_SEQ_LANES) {
        out[k].lock_mask = (uint8_t)(out[k].lock_mask | (1u << l[i].lane));
        out[k].lock[l[i].lane] = l[i].val;
      }
    }
  }
  {
    const sq_trig_t *g = &sq_ctrigs(s)[c->seg[SQ_K_TRIGS].off];
    for (i = 0; i < c->seg[SQ_K_TRIGS].len; ++i) {
      const unsigned k = (unsigned)g[i].step - first;
      if (g[i].step < first || k >= n) continue;
      if (g[i].lane == SQ_NONE) {
        out[k].trig = (uint8_t)(out[k].trig | FM1_SEQ_TRIG_STEP |
                                ((g[i].prob_inv & 0x80u) ? FM1_SEQ_TRIG_INV : 0u));
        out[k].prob = (uint8_t)(g[i].prob_inv & 0x7Fu);
        out[k].cond_a = g[i].a;
        out[k].cond_b = g[i].b;
      } else {
        out[k].trig = (uint8_t)(out[k].trig | FM1_SEQ_TRIG_PITCH);
      }
    }
  }
  return 1;
}

void fm1_seq_get_stats(const fm1_seq_t *s, fm1_seq_stats_t *o) {
  *o = s->stats;
  o->notes_used = s->used[SQ_K_NOTES];
  o->locks_used = s->used[SQ_K_LOCKS];
  o->trigs_used = s->used[SQ_K_TRIGS];
}

int fm1_seq_effective_at(const fm1_seq_t *s, uint8_t t, uint8_t slot, uint8_t lane, uint16_t step,
                         fm1_seq_val_t base) {
  if (t >= s->n_tracks || slot >= FM1_SEQ_SLOTS || lane >= FM1_SEQ_LANES) return base;
  return sq_effective_at(s, sq_clip_no(t, slot), lane, step, base);
}

int fm1_seq_set_route(fm1_seq_t *s, uint8_t t, uint8_t kind, uint8_t index) {
  sq_track_t *tr;
  if (t >= s->n_tracks) return 0;
  if (kind == FM1_SEQ_ROUTE_MIDI && (index < 1 || index > 16)) return 0;
  if (kind == FM1_SEQ_ROUTE_ENGINE && index >= 8) return 0;
  if (kind != FM1_SEQ_ROUTE_MIDI && kind != FM1_SEQ_ROUTE_ENGINE) return 0;
  tr = &sq_tracks(s)[t];
  tr->route_kind = kind;
  tr->route_index = index;
  return 1;
}
