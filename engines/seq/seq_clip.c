/* seq_clip.c -- the global item pools and Movy's Clip methods.
 *
 * Derived from Movy's seq-core clip.rs (commit 9190e79, MIT, Copyright (c)
 * 2026 megadake). Movy keeps each clip's notes, locks and trig rows in its
 * own Vec; here they live in three global pools, each clip owning one packed
 * slice of each (docs/13 §5, D7). Insertion order is kept exactly, because
 * Movy's scan order, swap_remove order and `movy1` output depend on it.
 *
 * Deviations, active only without limits.compat (docs/13 §3.3):
 *   D5  length caps and nudge limits use the loop end, not the length;
 *   D7  a full pool refuses the edit, whole, and counts it
 *       (fm1_seq_stats_t.refused);
 *   D8  clip speed within 1/8X-4X;
 *   D10 performed notes store their tick without their anchor's swing;
 *   D11 notes anchored outside the loop window stay silent.
 */
#include "seq_int.h"

static const uint16_t kItemSize[SQ_K_COUNT] = {
  (uint16_t)sizeof(sq_note_t), (uint16_t)sizeof(sq_lock_t), (uint16_t)sizeof(sq_trig_t)
};

static uint8_t *pool_base(fm1_seq_t *s, int kind) {
  if (kind == SQ_K_NOTES) return (uint8_t *)sq_notes(s);
  if (kind == SQ_K_LOCKS) return (uint8_t *)sq_locks(s);
  return (uint8_t *)sq_trigs(s);
}

static uint16_t pool_cap(const fm1_seq_t *s, int kind) {
  if (kind == SQ_K_NOTES) return s->lim.notes;
  if (kind == SQ_K_LOCKS) return s->lim.locks;
  return s->lim.trigs;
}

static uint16_t clip_cap(const fm1_seq_t *s, int kind) {
  if (kind == SQ_K_NOTES) return s->lim.clip_notes;
  if (kind == SQ_K_LOCKS) return s->lim.clip_locks;
  return s->lim.clip_trigs;
}

/* D7 (FM-1 default): an edit that adds several items to one pool is applied
 * whole or not at all. If the pool cannot take everything it would add,
 * nothing changes and the edit counts as refused, as a whole-clip copy is.
 * Movy's per-clip caps still drop what is past them silently, as in Movy, so
 * `need` is what the edit adds within its clip's cap. */
int sq_pool_room(fm1_seq_t *s, int kind, unsigned need, unsigned freed) {
  if (s->lim.compat || need <= freed) return 1;
  if ((unsigned)s->used[kind] + (need - freed) <= pool_cap(s, kind)) return 1;
  ++s->stats.refused;
  return 0;
}

/* Items one clip can still take under Movy's per-clip cap. */
unsigned sq_clip_room(const fm1_seq_t *s, unsigned clip, int kind) {
  const unsigned len = sq_cclips(s)[clip].seg[kind].len, cap = clip_cap(s, kind);
  return len < cap ? cap - len : 0u;
}

static unsigned min_u(unsigned a, unsigned b) { return a < b ? a : b; }

void sq_clip_invalidate(fm1_seq_t *s, unsigned clip) {
  sq_clips(s)[clip].flags &= (uint8_t)~SQ_C_INDEX_OK;
}

void sq_invalidate_all(fm1_seq_t *s) {
  unsigned k;
  for (k = 0; k < s->n_clips; ++k) sq_clip_invalidate(s, k);
}

/* Moves every slice after `clip` by `delta` items (the pool contents have
 * already been shifted). */
static void shift_offsets(fm1_seq_t *s, unsigned clip, int kind, int delta) {
  sq_clip_t *c = sq_clips(s);
  unsigned k;
  for (k = clip + 1; k < s->n_clips; ++k) c[k].seg[kind].off = (uint16_t)(c[k].seg[kind].off + delta);
}

/* Grows or shrinks a clip's slice at its end. Returns 0 if the pool is full. */
static int seg_resize(fm1_seq_t *s, unsigned clip, int kind, unsigned newlen) {
  sq_seg_t *g = &sq_clips(s)[clip].seg[kind];
  const size_t isz = kItemSize[kind];
  uint8_t *base = pool_base(s, kind);
  const unsigned end = (unsigned)g->off + g->len;
  const unsigned used = s->used[kind];
  if (newlen == g->len) return 1;
  if (newlen > g->len) {
    const unsigned grow = newlen - g->len;
    if (used + grow > pool_cap(s, kind)) return 0;
    memmove(base + (end + grow) * isz, base + end * isz, (used - end) * isz);
    memset(base + end * isz, 0, grow * isz);
    s->used[kind] = (uint16_t)(used + grow);
    shift_offsets(s, clip, kind, (int)grow);
  } else {
    const unsigned cut = g->len - newlen;
    memmove(base + (end - cut) * isz, base + end * isz, (used - end) * isz);
    s->used[kind] = (uint16_t)(used - cut);
    shift_offsets(s, clip, kind, -(int)cut);
  }
  g->len = (uint16_t)newlen;
  if (kind == SQ_K_NOTES) sq_clip_invalidate(s, clip);
  return 1;
}

int sq_seg_insert(fm1_seq_t *s, unsigned clip, int kind, unsigned pos, const void *item) {
  sq_seg_t *g = &sq_clips(s)[clip].seg[kind];
  const size_t isz = kItemSize[kind];
  uint8_t *base = pool_base(s, kind);
  const unsigned at = (unsigned)g->off + pos;
  const unsigned used = s->used[kind];
  if (used >= pool_cap(s, kind)) {
    ++s->stats.refused;
    return 0;
  }
  memmove(base + (at + 1) * isz, base + at * isz, (used - at) * isz);
  memcpy(base + at * isz, item, isz);
  ++g->len;
  s->used[kind] = (uint16_t)(used + 1);
  shift_offsets(s, clip, kind, 1);
  if (kind == SQ_K_NOTES) sq_clip_invalidate(s, clip);
  return 1;
}

/* Vec::remove: order-preserving. */
void sq_seg_remove(fm1_seq_t *s, unsigned clip, int kind, unsigned pos) {
  sq_seg_t *g = &sq_clips(s)[clip].seg[kind];
  const size_t isz = kItemSize[kind];
  uint8_t *base = pool_base(s, kind);
  const unsigned at = (unsigned)g->off + pos;
  const unsigned used = s->used[kind];
  memmove(base + at * isz, base + (at + 1) * isz, (used - at - 1) * isz);
  --g->len;
  s->used[kind] = (uint16_t)(used - 1);
  shift_offsets(s, clip, kind, -1);
  if (kind == SQ_K_NOTES) sq_clip_invalidate(s, clip);
}

/* Vec::swap_remove: the last item takes the removed one's place. */
void sq_seg_swap_remove(fm1_seq_t *s, unsigned clip, int kind, unsigned pos) {
  sq_seg_t *g = &sq_clips(s)[clip].seg[kind];
  const size_t isz = kItemSize[kind];
  uint8_t *base = pool_base(s, kind);
  const unsigned last = g->len - 1u;
  if (pos != last) memcpy(base + (g->off + pos) * isz, base + (g->off + last) * isz, isz);
  sq_seg_remove(s, clip, kind, last);
}

void sq_seg_clear(fm1_seq_t *s, unsigned clip, int kind) {
  seg_resize(s, clip, kind, 0);
}

/* The clip as Clip::new(): empty, scale 1/1, no transpose, quantise 0. */
void sq_clip_reset(fm1_seq_t *s, unsigned clip) {
  sq_clip_t *c;
  int k;
  for (k = 0; k < SQ_K_COUNT; ++k) sq_seg_clear(s, clip, k);
  c = &sq_clips(s)[clip];
  c->length_steps = 0;
  c->loop_start = 0;
  c->scale_num = c->scale_den = 1;
  c->transpose = 0;
  c->quant = 0;
  c->flags = 0;
}

/* Clip::clear(): as new, except that the quantise strength survives. */
void sq_clip_clear(fm1_seq_t *s, unsigned clip) {
  const uint8_t q = sq_clips(s)[clip].quant;
  sq_clip_reset(s, clip);
  sq_clips(s)[clip].quant = q;
}

/* `*dst = src.clone()`. All-or-nothing: if the pools cannot hold the copy,
 * nothing changes and the edit is refused. */
int sq_clip_copy(fm1_seq_t *s, unsigned dst, unsigned src) {
  int k;
  sq_clip_t *c;
  const sq_clip_t *from;
  if (dst == src) return 1;
  for (k = 0; k < SQ_K_COUNT; ++k) {
    const unsigned need = sq_clips(s)[src].seg[k].len;
    const unsigned have = sq_clips(s)[dst].seg[k].len;
    if (need > have && s->used[k] + (need - have) > pool_cap(s, k)) {
      ++s->stats.refused;
      return 0;
    }
  }
  for (k = 0; k < SQ_K_COUNT; ++k) {
    const size_t isz = kItemSize[k];
    uint8_t *base = pool_base(s, k);
    seg_resize(s, dst, k, sq_clips(s)[src].seg[k].len);
    /* The source's slice may have moved; read its offset afterwards. */
    memcpy(base + (size_t)sq_clips(s)[dst].seg[k].off * isz,
           base + (size_t)sq_clips(s)[src].seg[k].off * isz,
           (size_t)sq_clips(s)[src].seg[k].len * isz);
  }
  c = &sq_clips(s)[dst];
  from = &sq_clips(s)[src];
  c->length_steps = from->length_steps;
  c->loop_start = from->loop_start;
  c->scale_num = from->scale_num;
  c->scale_den = from->scale_den;
  c->transpose = from->transpose;
  c->quant = from->quant;
  c->flags = 0;
  return 1;
}

/* ---- The fire-tick index (docs/13 §5) ----------------------------------- */

/* swing_delay (engine.rs 351-362, R6): delay of a step that lands on an
 * off-beat real 1/16 under the clip's playback scale. */
uint32_t sq_swing_delay(const fm1_seq_t *s, uint16_t step, uint8_t scale_num, uint8_t scale_den) {
  uint32_t num, den, numer;
  if (s->swing_pct <= 50) return 0;
  num = scale_num ? scale_num : 1u;
  den = scale_den ? scale_den : 1u;
  numer = (uint32_t)step * den;
  if (numer % num != 0 || (numer / num) % 2u == 0) return 0;
  return (s->swing_pct - 50u) * (num * SQ_TPS / den) / 60u;
}

/* D10 (FM-1 default): a note placed from a performance (live recording,
 * Capture) anchors to the nearest *swung* step, but Movy stores the played
 * tick, so playback, which adds the swing again (R5), puts an off-beat late
 * by the swing at quantise below 100. Storing the tick less its anchor's
 * swing makes quantise 0 replay what was played. */
uint32_t sq_unswing(const fm1_seq_t *s, uint32_t tick, uint16_t step, uint8_t num, uint8_t den) {
  uint32_t sw;
  if (s->lim.compat) return tick;
  sw = sq_swing_delay(s, step, num, den);
  return tick > sw ? tick - sw : 0u;
}

/* D8 (FM-1 default): clip speed within Movy's UI range, 1/8X to 4X
 * (src/seq/clip-scale.ts). Movy's core takes 1/255 to 255X, which runs up to
 * 255 step_ticks per master tick per track. */
void sq_scale_limit(const fm1_seq_t *s, uint8_t *num, uint8_t *den) {
  if (s->lim.compat) return;
  if (*num > 4u * *den) *num = (uint8_t)(4u * *den);       /* then den < 64 */
  if (*den > 8u * *num) *den = (uint8_t)(8u * *num);       /* then num < 32 */
}

/* The fire tick of R5 (engine.rs 2151-2166), computed as step_tick does.
 * D11 (FM-1 default): a note anchored outside the loop window stays silent,
 * and one inside it never fires before the loop start. Movy folds a note
 * anchored up to one window length past the loop end back into the window
 * (after `clen` or `loop` shrinks a clip under its notes), and drops a note
 * of the window's first step nudged or played early when the window does not
 * start at step 0 (at step 0 it clamps such a note to tick 0). */
static uint16_t note_fire(const fm1_seq_t *s, const sq_clip_t *c, const sq_note_t *n) {
  const uint32_t clip_end = sq_end_ticks(c);
  const uint32_t span = sq_len_ticks(c) ? sq_len_ticks(c) : 1u;
  const int64_t quant = c->quant > 100 ? 100 : c->quant;
  const uint16_t step = SQ_NSTEP(n);
  const int64_t anchor = (int64_t)step * SQ_TPS;
  const int64_t dev = (int64_t)n->tick - anchor;
  const int64_t half = dev >= 0 ? 50 : -50;
  const int64_t pulled = dev - (dev * quant + half) / 100;
  int64_t fire = anchor + pulled + (int64_t)sq_swing_delay(s, step, c->scale_num, c->scale_den);
  uint32_t f;
  if (!s->lim.compat) {
    if (step < c->loop_start || (uint32_t)step >= (uint32_t)c->loop_start + c->length_steps) {
      return (uint16_t)SQ_FIRE_NEVER;
    }
    if (fire < (int64_t)sq_start_ticks(c)) fire = (int64_t)sq_start_ticks(c);
  }
  if (fire < 0) fire = 0;
  f = (uint32_t)fire;
  if (f >= clip_end) f -= span;
  return f >= SQ_FIRE_NEVER ? (uint16_t)SQ_FIRE_NEVER : (uint16_t)f;
}

static int ix_less(const sq_note_t *n, uint16_t a, uint16_t b) {
  if (n[a].fire != n[b].fire) return n[a].fire < n[b].fire;
  return a < b;
}

static void sift_down(sq_note_t *n, unsigned root, unsigned count) {
  for (;;) {
    unsigned child = 2u * root + 1u;
    uint16_t tmp;
    if (child >= count) return;
    if (child + 1u < count && ix_less(n, n[child].ix, n[child + 1u].ix)) ++child;
    if (!ix_less(n, n[root].ix, n[child].ix)) return;
    tmp = n[root].ix;
    n[root].ix = n[child].ix;
    n[child].ix = tmp;
    root = child;
  }
}

/* Recomputes the clip's fire ticks and sorts its index by (fire, insertion
 * order), so step_tick visits exactly the notes due, in Movy's scan order.
 * Heapsort: in place and O(n log n); the composite key is unique, so the
 * sort's instability cannot reorder anything. */
void sq_clip_index(fm1_seq_t *s, unsigned clip) {
  sq_clip_t *c = &sq_clips(s)[clip];
  sq_note_t *n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
  const unsigned count = c->seg[SQ_K_NOTES].len;
  unsigned i;
  if (c->flags & SQ_C_INDEX_OK) return;
  for (i = 0; i < count; ++i) {
    n[i].fire = note_fire(s, c, &n[i]);
    n[i].ix = (uint16_t)i;
  }
  if (count > 1) {
    for (i = count / 2u; i-- > 0;) sift_down(n, i, count);
    for (i = count - 1u; i > 0; --i) {
      const uint16_t tmp = n[0].ix;
      n[0].ix = n[i].ix;
      n[i].ix = tmp;
      sift_down(n, 0, i);
    }
  }
  c->flags |= SQ_C_INDEX_OK;
}

#ifdef SQ_CHECK_INDEX
/* The checking build (fm1-seq-check) verifies, before every scan, that the
 * cached fire ticks are what Movy would compute now and that the index is
 * sorted: a missed invalidation shows up as a trap, not a wrong note. */
void sq_check_index(fm1_seq_t *s, unsigned clip) {
  const sq_clip_t *c = &sq_clips(s)[clip];
  const sq_note_t *n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
  const unsigned count = c->seg[SQ_K_NOTES].len;
  unsigned i;
  for (i = 0; i < count; ++i) {
    if (n[i].fire != note_fire(s, c, &n[i]) || n[i].ix >= count) __builtin_trap();
  }
  for (i = 1; i < count; ++i) {
    if (!ix_less(n, n[i - 1].ix, n[i].ix)) __builtin_trap();
  }
}
#endif

/* ---- Locks --------------------------------------------------------------- */

int sq_clip_lock_at(fm1_seq_t *s, unsigned clip, uint8_t lane, uint16_t step, fm1_seq_val_t *val) {
  const sq_clip_t *c = &sq_clips(s)[clip];
  const sq_lock_t *l = &sq_locks(s)[c->seg[SQ_K_LOCKS].off];
  unsigned i;
  for (i = 0; i < c->seg[SQ_K_LOCKS].len; ++i) {
    if (l[i].lane == lane && l[i].step == step) {
      if (val) *val = l[i].val;
      return 1;
    }
  }
  return 0;
}

int sq_clip_has_lock_on_lane(fm1_seq_t *s, unsigned clip, uint8_t lane) {
  const sq_clip_t *c = &sq_clips(s)[clip];
  const sq_lock_t *l = &sq_locks(s)[c->seg[SQ_K_LOCKS].off];
  unsigned i;
  for (i = 0; i < c->seg[SQ_K_LOCKS].len; ++i) {
    if (l[i].lane == lane) return 1;
  }
  return 0;
}

/* Upsert (clip.rs 198-206). A lock past step 255 cannot be stored here; Movy
 * keeps it, where it is inert (no playhead reaches it). */
void sq_clip_set_lock(fm1_seq_t *s, unsigned clip, uint8_t lane, uint16_t step, fm1_seq_val_t val) {
  sq_clip_t *c = &sq_clips(s)[clip];
  sq_lock_t *l = &sq_locks(s)[c->seg[SQ_K_LOCKS].off];
  sq_lock_t item;
  unsigned i;
  for (i = 0; i < c->seg[SQ_K_LOCKS].len; ++i) {
    if (l[i].lane == lane && l[i].step == step) {
      l[i].val = val;
      return;
    }
  }
  if (step >= SQ_MAX_STEPS || c->seg[SQ_K_LOCKS].len >= clip_cap(s, SQ_K_LOCKS)) {
    ++s->stats.refused;
    return;
  }
  item.step = (uint8_t)step;
  item.lane = lane;
  item.val = val;
  sq_seg_insert(s, clip, SQ_K_LOCKS, c->seg[SQ_K_LOCKS].len, &item);
}

/* Vec::retain over a clip's locks: compact in place, then cut the slice once. */
typedef int (*lock_pred)(const sq_lock_t *l, unsigned a, unsigned b);

static void retain_locks(fm1_seq_t *s, unsigned clip, lock_pred drop, unsigned a, unsigned b) {
  sq_clip_t *c = &sq_clips(s)[clip];
  sq_lock_t *l = &sq_locks(s)[c->seg[SQ_K_LOCKS].off];
  unsigned r, w = 0;
  for (r = 0; r < c->seg[SQ_K_LOCKS].len; ++r) {
    if (drop(&l[r], a, b)) continue;
    if (w != r) l[w] = l[r];
    ++w;
  }
  seg_resize(s, clip, SQ_K_LOCKS, w);
}

static int drop_lane(const sq_lock_t *l, unsigned lane, unsigned unused) {
  (void)unused;
  return l->lane == lane;
}
static int drop_lane_step(const sq_lock_t *l, unsigned lane, unsigned step) {
  return l->lane == lane && l->step == step;
}
static int drop_step(const sq_lock_t *l, unsigned step, unsigned unused) {
  (void)unused;
  return l->step == step;
}

void sq_clip_clear_lane(fm1_seq_t *s, unsigned clip, uint8_t lane) {
  retain_locks(s, clip, drop_lane, lane, 0);
}

void sq_clip_clear_lock(fm1_seq_t *s, unsigned clip, uint8_t lane, uint16_t step) {
  retain_locks(s, clip, drop_lane_step, lane, step);
}

void sq_clip_clear_step_locks(fm1_seq_t *s, unsigned clip, uint16_t step) {
  retain_locks(s, clip, drop_step, step, 0);
}

void sq_clip_set_lock_range(fm1_seq_t *s, unsigned clip, uint8_t lane, uint16_t s0, uint16_t s1,
                            fm1_seq_val_t val) {
  uint32_t step;
  unsigned fresh = 0;
  for (step = s0; step <= s1 && step < SQ_MAX_STEPS; ++step) {
    fresh += !sq_clip_lock_at(s, clip, lane, (uint16_t)step, NULL);
  }
  if (!sq_pool_room(s, SQ_K_LOCKS, min_u(fresh, sq_clip_room(s, clip, SQ_K_LOCKS)), 0)) return;
  for (step = s0; step <= s1; ++step) sq_clip_set_lock(s, clip, lane, (uint16_t)step, val);
}

/* ---- Trig rows ----------------------------------------------------------- */

static sq_props_t props_of(const sq_trig_t *t) {
  sq_props_t p;
  p.prob = (uint8_t)(t->prob_inv & 0x7Fu);
  p.inv = (uint8_t)(t->prob_inv >> 7);
  p.a = t->a;
  p.b = t->b;
  return p;
}

static sq_props_t props_default(void) {
  sq_props_t p;
  p.prob = 100;
  p.a = 1;
  p.b = 1;
  p.inv = 0;
  return p;
}

static int props_is_default(sq_props_t p) {
  return p.prob == 100 && p.a == 1 && p.b == 1 && !p.inv;
}

static int find_trig(fm1_seq_t *s, unsigned clip, uint16_t step, uint8_t lane) {
  const sq_clip_t *c = &sq_clips(s)[clip];
  const sq_trig_t *t = &sq_trigs(s)[c->seg[SQ_K_TRIGS].off];
  unsigned i;
  for (i = 0; i < c->seg[SQ_K_TRIGS].len; ++i) {
    if (t[i].step == step && t[i].lane == lane) return (int)i;
  }
  return -1;
}

int sq_clip_has_trig_row(fm1_seq_t *s, unsigned clip, uint16_t step, uint8_t lane) {
  return find_trig(s, clip, step, lane) >= 0;
}

/* governing_trig (clip.rs 161-168): (step, pitch), else (step, whole), else
 * the defaults. */
sq_props_t sq_clip_governing_trig(fm1_seq_t *s, unsigned clip, uint16_t step, uint8_t pitch) {
  int i = find_trig(s, clip, step, pitch);
  if (i < 0) i = find_trig(s, clip, step, SQ_NONE);
  if (i < 0) return props_default();
  return props_of(sq_ctrig(s, &sq_clips(s)[clip], (unsigned)i));
}

/* edit_trig (clip.rs 170-185): a row that returns to the defaults is
 * swap_removed; a new row past the cap is dropped. */
void sq_clip_edit_trig(fm1_seq_t *s, unsigned clip, uint16_t s0, uint16_t s1, uint8_t lane,
                       int what, uint8_t v1, uint8_t v2) {
  uint32_t step;
  /* A new row is made only where none exists and the change leaves the
   * defaults; an edit that removes rows (one back to the defaults) adds none. */
  const int adds = what == SQ_TRIG_PROB ? v1 < 100 : (what == SQ_TRIG_COND ? (v1 > 1 || v2 > 1) : v1 != 0);
  if (adds && s0 < s1) {
    unsigned fresh = 0;
    for (step = s0; step <= s1 && step < SQ_MAX_STEPS; ++step) {
      fresh += find_trig(s, clip, (uint16_t)step, lane) < 0;
    }
    if (!sq_pool_room(s, SQ_K_TRIGS, min_u(fresh, sq_clip_room(s, clip, SQ_K_TRIGS)), 0)) return;
  }
  for (step = s0; step <= s1; ++step) {
    const int idx = find_trig(s, clip, (uint16_t)step, lane);
    sq_props_t p = idx >= 0 ? props_of(sq_ctrig(s, &sq_clips(s)[clip], (unsigned)idx))
                            : props_default();
    if (what == SQ_TRIG_PROB) {
      p.prob = v1 > 100 ? 100 : v1;
    } else if (what == SQ_TRIG_COND) {
      p.a = v1 ? v1 : 1;
      p.b = v2 ? v2 : 1;
    } else {
      p.inv = v1 ? 1 : 0;
    }
    if (idx >= 0) {
      if (props_is_default(p)) {
        sq_seg_swap_remove(s, clip, SQ_K_TRIGS, (unsigned)idx);
      } else {
        sq_trig_t *t = sq_ctrig(s, &sq_clips(s)[clip], (unsigned)idx);
        t->prob_inv = (uint8_t)(p.prob | (p.inv << 7));
        t->a = p.a;
        t->b = p.b;
      }
    } else if (!props_is_default(p)) {
      if (step >= SQ_MAX_STEPS ||
          sq_clips(s)[clip].seg[SQ_K_TRIGS].len >= clip_cap(s, SQ_K_TRIGS)) {
        ++s->stats.refused;
      } else {
        sq_trig_t t;
        t.step = (uint8_t)step;
        t.lane = lane;
        t.prob_inv = (uint8_t)(p.prob | (p.inv << 7));
        t.a = p.a;
        t.b = p.b;
        sq_seg_insert(s, clip, SQ_K_TRIGS, sq_clips(s)[clip].seg[SQ_K_TRIGS].len, &t);
      }
    }
  }
}

/* ---- Notes and the loop window -------------------------------------------- */

int sq_clip_has_notes_at(fm1_seq_t *s, unsigned clip, uint16_t step) {
  const sq_clip_t *c = &sq_clips(s)[clip];
  const sq_note_t *n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
  unsigned i;
  for (i = 0; i < c->seg[SQ_K_NOTES].len; ++i) {
    if (SQ_NSTEP(&n[i]) == step) return 1;
  }
  return 0;
}

void sq_clip_ensure_exists(fm1_seq_t *s, unsigned clip) {
  sq_clip_t *c = &sq_clips(s)[clip];
  if (c->length_steps == 0) {
    c->length_steps = SQ_BAR_STEPS;
    sq_clip_invalidate(s, clip);
  }
}

/* set_loop (clip.rs 286-293): bar-aligned start, at least one bar. */
void sq_clip_set_loop(fm1_seq_t *s, unsigned clip, uint16_t start_steps, uint16_t len_steps) {
  sq_clip_t *c = &sq_clips(s)[clip];
  uint16_t start = (uint16_t)((start_steps / SQ_BAR_STEPS) * SQ_BAR_STEPS);
  uint16_t len = len_steps < SQ_BAR_STEPS ? (uint16_t)SQ_BAR_STEPS : len_steps;
  if (start > SQ_MAX_STEPS - SQ_BAR_STEPS) start = SQ_MAX_STEPS - SQ_BAR_STEPS;
  c->loop_start = (uint8_t)start;
  c->length_steps = len < SQ_MAX_STEPS - start ? len : (uint16_t)(SQ_MAX_STEPS - start);
  sq_clip_invalidate(s, clip);
}

/* set_clip_length (clip.rs 298-301): step-granular, start kept. */
void sq_clip_set_length(fm1_seq_t *s, unsigned clip, uint16_t steps) {
  sq_clip_t *c = &sq_clips(s)[clip];
  const uint16_t max = (uint16_t)(SQ_MAX_STEPS - c->loop_start);
  c->length_steps = steps < 1 ? 1 : (steps > max ? max : steps);
  sq_clip_invalidate(s, clip);
}

static void extend_to_step(fm1_seq_t *s, unsigned clip, uint16_t step) {
  sq_clip_t *c;
  uint16_t end_of_bar, len;
  sq_clip_ensure_exists(s, clip);
  c = &sq_clips(s)[clip];
  if (step < (uint32_t)c->loop_start + c->length_steps) return;
  end_of_bar = (uint16_t)((step / SQ_BAR_STEPS + 1u) * SQ_BAR_STEPS);
  len = (uint16_t)(end_of_bar - c->loop_start);
  if (len > SQ_MAX_STEPS - c->loop_start) len = (uint16_t)(SQ_MAX_STEPS - c->loop_start);
  c->length_steps = len;
  sq_clip_invalidate(s, clip);
}

static uint16_t sat16(uint32_t v) { return v > 0xFFFFu ? (uint16_t)0xFFFFu : (uint16_t)v; }

static int push_note_raw(fm1_seq_t *s, unsigned clip, uint16_t step, uint32_t tick, uint32_t gate,
                         uint8_t pitch, uint8_t vel, int suppress) {
  sq_note_t n;
  n.tick = sat16(tick);
  n.gate = sat16(gate);
  n.step = (uint16_t)((step & SQ_STEP_MASK) | (suppress ? SQ_N_SUPPRESS : 0u));
  n.fire = SQ_FIRE_NEVER;
  n.ix = 0;
  n.pitch = pitch;
  n.vel = vel;
  return sq_seg_insert(s, clip, SQ_K_NOTES, sq_clips(s)[clip].seg[SQ_K_NOTES].len, &n);
}

/* Room for one more note in this clip: Movy's per-clip cap drops silently;
 * a full global pool is refused before the clip is touched (D7). */
static int note_room(fm1_seq_t *s, unsigned clip) {
  if (sq_clips(s)[clip].seg[SQ_K_NOTES].len >= s->lim.clip_notes) {
    ++s->stats.refused;
    return 0;
  }
  if (!s->lim.compat && s->used[SQ_K_NOTES] >= s->lim.notes) {
    ++s->stats.refused;
    return 0;
  }
  return 1;
}

/* The tick a gate or nudge may not reach: the loop end (D5), or Movy's
 * length_ticks, which is wrong when the loop does not start at step 0. */
static uint32_t cap_end(const fm1_seq_t *s, const sq_clip_t *c) {
  return s->lim.compat ? sq_len_ticks(c) : sq_end_ticks(c);
}

/* max_gate_at (clip.rs 606-614). */
static uint32_t max_gate_at(fm1_seq_t *s, unsigned clip, uint32_t tick, uint8_t pitch) {
  const sq_clip_t *c = &sq_clips(s)[clip];
  const sq_note_t *n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
  const uint32_t end = cap_end(s, c);
  uint32_t cap = end > tick ? end - tick : 0;
  unsigned i;
  for (i = 0; i < c->seg[SQ_K_NOTES].len; ++i) {
    if (n[i].pitch == pitch && n[i].tick > tick && n[i].tick - tick < cap) cap = n[i].tick - tick;
  }
  return cap ? cap : 1u;
}

/* push_note (clip.rs 367-387). */
static void push_note(fm1_seq_t *s, unsigned clip, uint16_t step, uint8_t pitch, uint8_t vel,
                      int inherit) {
  uint32_t tick = (uint32_t)step * SQ_TPS, gate = SQ_TPS;
  if (!note_room(s, clip)) return;
  extend_to_step(s, clip, step);
  if (inherit) {
    /* step_footprint: the span every note anchored here occupies. */
    const sq_clip_t *c = &sq_clips(s)[clip];
    const sq_note_t *n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
    uint32_t start = 0, end = 0;
    int any = 0;
    unsigned i;
    for (i = 0; i < c->seg[SQ_K_NOTES].len; ++i) {
      if (SQ_NSTEP(&n[i]) != step) continue;
      if (!any || n[i].tick < start) start = n[i].tick;
      if ((uint32_t)n[i].tick + n[i].gate > end) end = (uint32_t)n[i].tick + n[i].gate;
      any = 1;
    }
    if (any) {
      const uint32_t g = end > start ? end - start : 1u;
      const uint32_t m = max_gate_at(s, clip, start, pitch);
      tick = start;
      gate = g < m ? g : m;
    }
  }
  push_note_raw(s, clip, step, tick, gate, pitch, vel, 0);
}

static int in_hidden_tail(const sq_clip_t *c, uint16_t step) {
  uint32_t end;
  if (c->length_steps == 0) return 0;
  end = (uint32_t)c->loop_start + c->length_steps;
  return step >= end && step < (end + SQ_BAR_STEPS - 1u) / SQ_BAR_STEPS * SQ_BAR_STEPS;
}

typedef int (*note_pred)(const sq_note_t *n, int a, int b, int c);

static void retain_notes(fm1_seq_t *s, unsigned clip, note_pred drop, int a, int b, int lane) {
  sq_clip_t *c = &sq_clips(s)[clip];
  sq_note_t *n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
  unsigned r, w = 0;
  for (r = 0; r < c->seg[SQ_K_NOTES].len; ++r) {
    if (drop(&n[r], a, b, lane)) continue;
    if (w != r) n[w] = n[r];
    ++w;
  }
  seg_resize(s, clip, SQ_K_NOTES, w);
  sq_clip_invalidate(s, clip);
}

/* Clip::note_matches: anchor in [s0, s1], and the pitch when a lane is given. */
static int note_matches(const sq_note_t *n, int s0, int s1, int lane) {
  const int st = SQ_NSTEP(n);
  return st >= s0 && st <= s1 && (lane < 0 || n->pitch == lane);
}

/* toggle_step (clip.rs 447-469): clear an occupied step, or place the chord. */
int sq_clip_toggle_step(fm1_seq_t *s, unsigned clip, uint16_t step, const uint8_t *pv, unsigned n) {
  unsigned i;
  if (step >= SQ_MAX_STEPS) return 0;
  if (sq_clip_has_notes_at(s, clip, step)) {
    retain_notes(s, clip, note_matches, step, step, -1);
    return 0;
  }
  if (in_hidden_tail(&sq_clips(s)[clip], step)) return 0;
  if (n == 0) return 0;
  if (!sq_pool_room(s, SQ_K_NOTES, min_u(n, sq_clip_room(s, clip, SQ_K_NOTES)), 0)) return 0;
  for (i = 0; i < n; ++i) push_note(s, clip, step, pv[2 * i], pv[2 * i + 1], 0);
  return 1;
}

/* toggle_step_pitch (clip.rs 474-487). */
int sq_clip_toggle_pitch(fm1_seq_t *s, unsigned clip, uint16_t step, uint8_t pitch, uint8_t vel,
                         int inherit) {
  const sq_clip_t *c = &sq_clips(s)[clip];
  const sq_note_t *n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
  unsigned i;
  if (step >= SQ_MAX_STEPS) return 0;
  for (i = 0; i < c->seg[SQ_K_NOTES].len; ++i) {
    if (SQ_NSTEP(&n[i]) == step && n[i].pitch == pitch) {
      sq_seg_remove(s, clip, SQ_K_NOTES, i);
      return 0;
    }
  }
  if (in_hidden_tail(c, step)) return 0;
  push_note(s, clip, step, pitch, vel, inherit);
  return 1;
}

/* record_note (clip.rs 400-409). The anchor may be 256 (a note in the last
 * half-step of a 16-bar clip); the length grows to cover step 240 at most. */
void sq_clip_record_note(fm1_seq_t *s, unsigned clip, uint16_t step, uint32_t tick, uint32_t gate,
                         uint8_t pitch, uint8_t vel, int suppress) {
  if (!note_room(s, clip)) return;
  extend_to_step(s, clip, step < SQ_MAX_STEPS - SQ_BAR_STEPS ? step
                                                             : (uint16_t)(SQ_MAX_STEPS - SQ_BAR_STEPS));
  push_note_raw(s, clip, step, tick, gate ? gate : 1u, pitch, vel, suppress);
}

/* add_note_raw (clip.rs 640-646): paste and load. */
void sq_clip_add_raw(fm1_seq_t *s, unsigned clip, uint16_t step, uint32_t tick, uint32_t gate,
                     uint8_t pitch, uint8_t vel) {
  if (step >= SQ_MAX_STEPS) return;
  if (!note_room(s, clip)) return;
  extend_to_step(s, clip, step);
  push_note_raw(s, clip, step, tick, gate, pitch, vel, 0);
}

void sq_clip_release_pass(fm1_seq_t *s, unsigned clip) {
  const sq_clip_t *c = &sq_clips(s)[clip];
  sq_note_t *n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
  unsigned i;
  for (i = 0; i < c->seg[SQ_K_NOTES].len; ++i) {
    n[i].step &= (uint16_t)~(SQ_N_SUPPRESS | SQ_N_FIRED);
  }
}

/* double_loop (clip.rs 305-338). */
void sq_clip_double(fm1_seq_t *s, unsigned clip) {
  sq_clip_t *c = &sq_clips(s)[clip];
  const uint16_t len = c->length_steps, start = c->loop_start;
  const uint32_t span = (uint32_t)len * SQ_TPS;
  const unsigned count = c->seg[SQ_K_NOTES].len;
  unsigned i;
  if (len == 0) return;
  if ((uint32_t)start + 2u * len > SQ_MAX_STEPS) return;
  if (!s->lim.compat) {
    unsigned in_window = 0;
    for (i = 0; i < count; ++i) {
      const uint16_t st = SQ_NSTEP(sq_cnote(s, c, i));
      in_window += st >= start && st < start + len;
    }
    if (!sq_pool_room(s, SQ_K_NOTES, min_u(in_window, sq_clip_room(s, clip, SQ_K_NOTES)), 0)) return;
  }
  for (i = 0; i < count; ++i) {
    sq_note_t n = *sq_cnote(s, &sq_clips(s)[clip], i);
    const uint16_t st = SQ_NSTEP(&n);
    if (st < start || st >= start + len) continue;
    if (sq_clips(s)[clip].seg[SQ_K_NOTES].len >= s->lim.clip_notes) break;
    if (!push_note_raw(s, clip, (uint16_t)(st + len), (uint32_t)n.tick + span, n.gate, n.pitch,
                       n.vel, 0)) break;
  }
  sq_clips(s)[clip].length_steps = (uint16_t)(len * 2u);
  sq_clip_invalidate(s, clip);
}

/* Wrapping 32-bit add, as Movy's release build does `x as i32 + delta`. */
static int32_t wrap_add(int32_t a, int32_t b) {
  return (int32_t)(uint32_t)((uint32_t)a + (uint32_t)b);
}

static int32_t clamp32(int32_t v, int32_t lo, int32_t hi) {
  return v < lo ? lo : (v > hi ? hi : v);
}

/* The hold-step edits (clip.rs 526-614, 665-676): velocity, transpose,
 * length (relative or absolute) and nudge over notes anchored in [s0, s1]. */
void sq_clip_edit(fm1_seq_t *s, unsigned clip, uint16_t s0, uint16_t s1, int lane, int what,
                  int32_t v) {
  const sq_clip_t *c = &sq_clips(s)[clip];
  sq_note_t *n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
  const unsigned count = c->seg[SQ_K_NOTES].len;
  const uint32_t clip_end = cap_end(s, c);
  unsigned i, j;
  for (i = 0; i < count; ++i) {
    if (!note_matches(&n[i], s0, s1, lane)) continue;
    if (what == SQ_EDIT_VEL) {
      n[i].vel = (uint8_t)clamp32(wrap_add(n[i].vel, v), 1, 127);
    } else if (what == SQ_EDIT_TRANSPOSE) {
      n[i].pitch = (uint8_t)clamp32(wrap_add(n[i].pitch, v), 0, 127);
    } else if (what == SQ_EDIT_LENGTH || what == SQ_EDIT_SETLEN) {
      uint32_t cap = clip_end > n[i].tick ? clip_end - n[i].tick : 0;
      for (j = 0; j < count; ++j) {
        if (n[j].pitch == n[i].pitch && n[j].tick > n[i].tick &&
            (uint32_t)(n[j].tick - n[i].tick) < cap) {
          cap = (uint32_t)(n[j].tick - n[i].tick);
        }
      }
      if (cap == 0) cap = 1;
      if (what == SQ_EDIT_LENGTH) {
        n[i].gate = (uint16_t)clamp32(wrap_add(n[i].gate, v), 1, (int32_t)cap);
      } else {
        const uint32_t ticks = (uint32_t)v;
        n[i].gate = (uint16_t)(ticks < 1 ? 1 : (ticks > cap ? cap : ticks));
      }
    } else {
      const int32_t anchor = (int32_t)SQ_NSTEP(&n[i]) * (int32_t)SQ_TPS;
      const int32_t lo = anchor - (int32_t)SQ_TPS > 0 ? anchor - (int32_t)SQ_TPS : 0;
      const int32_t end1 = clip_end > 0 ? (int32_t)clip_end - 1 : 0;
      const int32_t hi = anchor + (int32_t)SQ_TPS < end1 ? anchor + (int32_t)SQ_TPS : end1;
      if (lo > hi) {
        /* Movy's `clamp(lo, hi)` panics here (D5, clip.rs 674). movy-dsp
         * catches it, so the notes before this one keep the nudge and the
         * rest of the edit, and of its batch, is lost: compat stops here.
         * The FM-1 default (whose window cannot produce this for a note
         * inside it) skips the note. */
        ++s->stats.movy_faults;
        if (s->lim.compat) {
          s->panicked = 1;
          break;
        }
        continue;
      }
      n[i].tick = (uint16_t)clamp32(wrap_add(n[i].tick, v), lo, hi);
    }
  }
  sq_clip_invalidate(s, clip);
}

void sq_clip_delete_range(fm1_seq_t *s, unsigned clip, uint16_t s0, uint16_t s1, int lane) {
  retain_notes(s, clip, note_matches, s0, s1, lane);
}

/* add_pitch_range (clip.rs 650-660). */
void sq_clip_add_pitch_range(fm1_seq_t *s, unsigned clip, uint16_t s0, uint16_t s1, uint8_t pitch,
                             uint8_t vel, int inherit) {
  uint32_t step;
  const uint32_t last = s1 < SQ_MAX_STEPS - 1u ? s1 : SQ_MAX_STEPS - 1u;
  if (!s->lim.compat && s0 <= last) {
    const sq_clip_t *c = &sq_clips(s)[clip];
    const sq_note_t *n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
    unsigned fresh = 0, i;
    for (step = s0; step <= last; ++step) {
      int present = 0;
      for (i = 0; i < c->seg[SQ_K_NOTES].len && !present; ++i) {
        present = SQ_NSTEP(&n[i]) == step && n[i].pitch == pitch;
      }
      fresh += !present;
    }
    if (!sq_pool_room(s, SQ_K_NOTES, min_u(fresh, sq_clip_room(s, clip, SQ_K_NOTES)), 0)) return;
  }
  for (step = s0; step <= last; ++step) {
    const sq_clip_t *c = &sq_clips(s)[clip];
    const sq_note_t *n = &sq_notes(s)[c->seg[SQ_K_NOTES].off];
    int present = 0;
    unsigned i;
    for (i = 0; i < c->seg[SQ_K_NOTES].len && !present; ++i) {
      present = SQ_NSTEP(&n[i]) == step && n[i].pitch == pitch;
    }
    if (!present) push_note(s, clip, (uint16_t)step, pitch, vel, inherit);
  }
}

/* effective_at (clip.rs 218-236): scan back cyclically inside the loop
 * window; the first lock governs, a note first means base. */
int sq_effective_at(const fm1_seq_t *s, unsigned clip, uint8_t lane, uint16_t step,
                    fm1_seq_val_t base) {
  fm1_seq_t *m = (fm1_seq_t *)(uintptr_t)s;   /* the helpers only read */
  const sq_clip_t *c = &sq_cclips(s)[clip];
  const int32_t len = c->length_steps;
  const int32_t rel = (int32_t)(uint16_t)(step - c->loop_start);
  int32_t d;
  if (len == 0) return base;
  for (d = 0; d < len; ++d) {
    int32_t off = (rel - d) % len;
    uint16_t at;
    fm1_seq_val_t v;
    if (off < 0) off += len;
    at = (uint16_t)(c->loop_start + off);
    if (sq_clip_lock_at(m, clip, lane, at, &v)) return v;
    if (sq_clip_has_notes_at(m, clip, at)) return base;
  }
  return base;
}
