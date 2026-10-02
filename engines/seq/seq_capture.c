/* seq_capture.c -- Capture: retroactive recording of what was just played.
 *
 * Derived from Movy's seq-core capture.rs and the capture functions of
 * engine.rs (lines 1185-1618), commit 9190e79, MIT, Copyright (c) 2026
 * megadake.
 *
 * On by default (limits.capture: 256 events, 3,072 bytes); with
 * limits.capture == 0 the ring has no bytes and every entry point here
 * returns at once. Three changes from Movy, all for the FM-1:
 *   - each event is packed into 12 bytes (Movy's CapEvent takes 24) without
 *     losing anything Movy reads from it (below);
 *   - the tempo search and the frame-to-tick conversion run in float, not
 *     f64 (pi32v2 has a single-precision FPU [inferred]); a candidate can
 *     differ from Movy's only where two scores tie to within float rounding;
 *   - the frozen take of a stopped capture lives in the ring's own storage
 *     (Movy copies it to a second Vec). The ring is idle while a take is
 *     frozen, because input is refused while the selector is up.
 * Scratch on the stack during a stopped capture: about 1.3 KB.
 *
 * The packed event (seq_int.h sq_cap_t), and why no width loses anything:
 *   - pitch and velocity, 7 bits each: `non`, `nof` and fm1_seq_note_in take
 *     pitches 0..127 only and clamp a note-on's velocity to 1..127, and a
 *     note-off carries 0, so the velocity tells Movy's `on` too (as in MIDI).
 *   - track, 4 bits: input for a track past the instance's (at most 16) is
 *     refused before it is stamped.
 *   - clip tick, 14 bits: a playhead stays below its clip's loop end, at most
 *     (255 + 256) steps of 24 ticks, 12,264.
 *   - frame, 25 bits from a base: every use is a difference between two
 *     events of the ring (or of a frozen take), and the 8-bar window keeps
 *     those within 8 bars at the slowest tempo: 96 s at 20 BPM, 4,235,328
 *     frames at 44,118 Hz, below 2^25 at any rate up to 349,525 Hz. The base
 *     moves to the oldest event when the newest would not fit, and the
 *     newest event's frame stands in for Movy's `last_frame`.
 *   - master tick, 16 bits and a flag: a tick below 2^16 as it is, a larger
 *     one as an offset from a base. The ring's ticks above 2^16 all come
 *     from one transport run (a run takes 2^16 ticks to reach them, more
 *     than the ring spans), so they lie within the ring's span in ticks: 96 s
 *     at 300 BPM is 46,080. After a restart that keeps the ring (MIDI Start
 *     while playing) the new ticks are small again and stored as they are.
 *   - cycle, its low 20 bits and a flag for 2^20 or more: its one use is
 *     `e.cycle != cycle` while playing, against the track's cycle now, and
 *     only for events the gap rule has not dropped, at most window + gap
 *     (104 s) old. In 104 s a 1-step loop at Movy's 255X and 300 BPM wraps
 *     530,400 times, below 2^20 - 1, so the low bits tell two cycles of one
 *     run apart, and the flag tells a cycle that ran for hours before a
 *     launch or a restart reset it to 1 from any cycle reached since.
 *   - used, 1 bit: a commit's scratch (Movy's `used` vector), set on the
 *     note-off that ends a note.
 * Outside those ranges (a sample rate above 349,525 Hz at the slowest
 * tempos; a clock that drives more than 65,535 master ticks through one
 * window, which only an external clock above about 426 BPM can) the ring
 * drops its oldest events until the new one packs, a deviation from Movy,
 * and the checking build (SQ_CHECK_INDEX), which also keeps every value
 * unpacked, traps.
 */
#include "seq_int.h"

#include <math.h>

#define CAP_MAX_BARS 8u
#define BPM_MIN 40u
#define BPM_MAX 250u
#define N_BPM (BPM_MAX - BPM_MIN + 1u)

enum { CAP_NONE = 0, CAP_SELECT = 1, CAP_FIXED = 2 };
enum { WHY_NONE = 0, WHY_EXT = 1, WHY_NOTES = 2 };

/* ---- The packed event ----------------------------------------------------- */

#define CAP_FRAME_MAX 0x01FFFFFFu   /* w[0] bits 0-24 */
#define CAP_TICK_MAX 0x0000FFFFu    /* w[1] bits 0-15 */
#define CAP_TICK_REL 0x00010000u    /* w[1] bit 16: an offset from cap_base_tick */
#define CAP_CLIP_MAX 0x3FFFu        /* w[1] bits 17-30 */
#define CAP_USED 0x80000000u        /* w[1] bit 31 */
#define CAP_CYCLE_LOW 0x000FFFFFu   /* w[2] bits 0-19 */
#define CAP_CYCLE_HIGH 0x00100000u  /* w[2] bit 20 */

#ifdef SQ_CHECK_INDEX
#define CAP_CHECK(cond) do { if (!(cond)) __builtin_trap(); } while (0)
#else
#define CAP_CHECK(cond) ((void)0)
/* Three words, on 32- and 64-bit targets alike (C99 has no static_assert). */
typedef char sq_cap_is_12_bytes[sizeof(sq_cap_t) == 12u ? 1 : -1];
#endif

/* One input event, unpacked: CapEvent's fields, `on` being vel > 0. */
typedef struct {
  uint32_t frame, tick, cycle;
  uint16_t clip_tick;
  uint8_t track, pitch, vel;
} cap_in_t;

static unsigned cap_on(const sq_cap_t *e) { return (e->w[2] >> 25) != 0u; }
static uint8_t cap_pitch(const sq_cap_t *e) { return (uint8_t)(e->w[0] >> 25); }
static unsigned cap_track(const sq_cap_t *e) { return (unsigned)((e->w[2] >> 21) & 0xFu); }
static uint8_t cap_vel(const sq_cap_t *e) { return (uint8_t)(e->w[2] >> 25); }
static unsigned cap_used(const sq_cap_t *e) { return (e->w[1] & CAP_USED) != 0u; }

static void cap_set_used(sq_cap_t *e, int used) {
  e->w[1] = used ? (e->w[1] | CAP_USED) : (e->w[1] & ~CAP_USED);
}

static uint32_t cap_frame(const fm1_seq_t *s, const sq_cap_t *e) {
  const uint32_t frame = s->cap_base_frame + (e->w[0] & CAP_FRAME_MAX);
  CAP_CHECK(frame == e->chk_frame);
  return frame;
}

static uint32_t cap_tick(const fm1_seq_t *s, const sq_cap_t *e) {
  const uint32_t v = e->w[1] & CAP_TICK_MAX;
  const uint32_t tick = (e->w[1] & CAP_TICK_REL) ? s->cap_base_tick + v : v;
  CAP_CHECK(tick == e->chk_tick);
  return tick;
}

static uint16_t cap_clip_tick(const sq_cap_t *e) {
  const uint16_t clip_tick = (uint16_t)((e->w[1] >> 17) & CAP_CLIP_MAX);
  CAP_CHECK(clip_tick == e->chk_clip_tick);
  return clip_tick;
}

static uint32_t cycle_key(uint32_t cycle) {
  return (cycle & CAP_CYCLE_LOW) | (cycle > CAP_CYCLE_LOW ? CAP_CYCLE_HIGH : 0u);
}

/* Movy's `e.cycle == cycle`. */
static int cap_same_cycle(const sq_cap_t *e, uint32_t cycle) {
  const int same = (e->w[2] & (CAP_CYCLE_LOW | CAP_CYCLE_HIGH)) == cycle_key(cycle);
  CAP_CHECK(same == (e->chk_cycle == cycle));
  return same;
}

/* The offset fields, against the bases as they stand. */
static void cap_put_frame(const fm1_seq_t *s, sq_cap_t *e, uint32_t frame) {
  const uint32_t off = frame - s->cap_base_frame;
  CAP_CHECK(off <= CAP_FRAME_MAX);
  e->w[0] = (e->w[0] & ~CAP_FRAME_MAX) | (off & CAP_FRAME_MAX);
}

static void cap_put_tick(const fm1_seq_t *s, sq_cap_t *e, uint32_t tick) {
  uint32_t v = tick, rel = 0;
  if (tick > CAP_TICK_MAX) {
    v = tick - s->cap_base_tick;
    rel = CAP_TICK_REL;
  }
  CAP_CHECK(v <= CAP_TICK_MAX);
  e->w[1] = (e->w[1] & ~(CAP_TICK_MAX | CAP_TICK_REL)) | (v & CAP_TICK_MAX) | rel;
}

static void cap_pack(const fm1_seq_t *s, sq_cap_t *e, const cap_in_t *in) {
  const uint32_t clip_tick = (uint32_t)in->clip_tick < CAP_CLIP_MAX ? in->clip_tick : CAP_CLIP_MAX;
  CAP_CHECK((uint32_t)in->clip_tick <= CAP_CLIP_MAX && (uint32_t)in->pitch <= 127u &&
            (uint32_t)in->vel <= 127u && (uint32_t)in->track <= 15u);
  e->w[0] = (uint32_t)(in->pitch & 0x7Fu) << 25;
  e->w[1] = clip_tick << 17;
  e->w[2] = cycle_key(in->cycle) | ((uint32_t)(in->track & 0xFu) << 21) |
            ((uint32_t)(in->vel & 0x7Fu) << 25);
#ifdef SQ_CHECK_INDEX
  e->chk_frame = in->frame;
  e->chk_tick = in->tick;
  e->chk_cycle = in->cycle;
  e->chk_clip_tick = in->clip_tick;
  e->chk_pad = 0;
#endif
  cap_put_frame(s, e, in->frame);
  cap_put_tick(s, e, in->tick);
}

/* ---- The ring (capture.rs CaptureRing) ------------------------------------ */

static sq_cap_t *ring_at(fm1_seq_t *s, unsigned i) {
  return &sq_cap(s)[(s->cap_head + i) % s->lim.capture];
}

void sq_capture_clear(fm1_seq_t *s) {
  s->cap_head = 0;
  s->cap_len = 0;
}

static void ring_drop_oldest(fm1_seq_t *s) {
  s->cap_head = (uint16_t)((s->cap_head + 1u) % s->lim.capture);
  --s->cap_len;
}

/* Moves the frame base onto the ring's oldest event if every frame, and the
 * new one, then packs. Returns 0, changing nothing, if they would not. */
static int rebase_frames(fm1_seq_t *s, uint32_t frame) {
  const uint32_t base = cap_frame(s, ring_at(s, 0));
  unsigned i;
  if ((uint32_t)(frame - base) > CAP_FRAME_MAX) return 0;
  for (i = 1; i < s->cap_len; ++i) {
    if ((uint32_t)(cap_frame(s, ring_at(s, i)) - base) > CAP_FRAME_MAX) return 0;
  }
  for (i = 0; i < s->cap_len; ++i) {
    sq_cap_t *e = ring_at(s, i);
    const uint32_t off = cap_frame(s, e) - base;
    e->w[0] = (e->w[0] & ~CAP_FRAME_MAX) | off;
  }
  s->cap_base_frame = base;
  return 1;
}

/* The same for the ticks stored as offsets, onto the oldest of them. */
static int rebase_ticks(fm1_seq_t *s, uint32_t tick) {
  uint32_t base = tick;
  unsigned i;
  int any = 0;
  for (i = 0; i < s->cap_len && !any; ++i) {
    const sq_cap_t *e = ring_at(s, i);
    if (e->w[1] & CAP_TICK_REL) {
      base = cap_tick(s, e);
      any = 1;
    }
  }
  if ((uint32_t)(tick - base) > CAP_TICK_MAX) return 0;
  for (i = 0; i < s->cap_len; ++i) {
    const sq_cap_t *e = ring_at(s, i);
    if ((e->w[1] & CAP_TICK_REL) && (uint32_t)(cap_tick(s, e) - base) > CAP_TICK_MAX) return 0;
  }
  for (i = 0; i < s->cap_len; ++i) {
    sq_cap_t *e = ring_at(s, i);
    if (e->w[1] & CAP_TICK_REL) {
      const uint32_t off = cap_tick(s, e) - base;
      e->w[1] = (e->w[1] & ~CAP_TICK_MAX) | off;
    }
  }
  s->cap_base_tick = base;
  return 1;
}

/* Sets the bases so that `in` packs: at `in` itself on an empty ring, else
 * moved only when an offset would overflow. Returns 0 if `in` cannot be
 * packed beside the ring's events, which happens only outside the ranges
 * above. */
static int ring_fit(fm1_seq_t *s, const cap_in_t *in) {
  if (s->cap_len == 0) {
    s->cap_base_frame = in->frame;
    s->cap_base_tick = in->tick;
    return 1;
  }
  if ((uint32_t)(in->frame - s->cap_base_frame) > CAP_FRAME_MAX && !rebase_frames(s, in->frame)) {
    return 0;
  }
  if (in->tick > CAP_TICK_MAX && (uint32_t)(in->tick - s->cap_base_tick) > CAP_TICK_MAX &&
      !rebase_ticks(s, in->tick)) {
    return 0;
  }
  return 1;
}

#ifdef SQ_CHECK_INDEX
/* The checking build: after every push, every event of the ring still
 * unpacks to what it was given. */
static void ring_check(fm1_seq_t *s) {
  unsigned i;
  for (i = 0; i < s->cap_len; ++i) {
    const sq_cap_t *e = ring_at(s, i);
    (void)cap_frame(s, e);
    (void)cap_tick(s, e);
    (void)cap_clip_tick(e);
    CAP_CHECK(cap_same_cycle(e, e->chk_cycle));
  }
}
#endif

static uint64_t bar_frames(const fm1_seq_t *s) {
  return (uint64_t)s->sample_rate * 60u * 4u * 100u / (s->bpm_x100 ? s->bpm_x100 : 1u);
}

static uint64_t gap_frames(const fm1_seq_t *s) {
  const uint64_t g = 2u * bar_frames(s), sr = s->sample_rate;
  return g < 2u * sr ? 2u * sr : (g > 8u * sr ? 8u * sr : g);
}

/* CaptureRing::push: a gap ends the phrase, the window bounds its age. */
static void ring_push(fm1_seq_t *s, const cap_in_t *in, uint64_t gap, uint64_t window) {
  if (s->cap_len > 0 &&
      (uint64_t)(uint32_t)(in->frame - cap_frame(s, ring_at(s, s->cap_len - 1u))) > gap) {
    sq_capture_clear(s);
  }
  while (s->cap_len > 0 && (uint64_t)(uint32_t)(in->frame - cap_frame(s, ring_at(s, 0))) > window) {
    ring_drop_oldest(s);
  }
  if (s->cap_len == s->lim.capture) ring_drop_oldest(s);   /* full: the newest replaces it */
  while (!ring_fit(s, in)) {
    CAP_CHECK(0);
    ring_drop_oldest(s);
  }
  cap_pack(s, ring_at(s, s->cap_len), in);
  ++s->cap_len;
#ifdef SQ_CHECK_INDEX
  ring_check(s);
#endif
}

/* capture_push (engine.rs 1203-1248). */
void sq_capture_push(fm1_seq_t *s, unsigned t, uint8_t pitch, uint8_t vel, int on, uint64_t frame) {
  const sq_track_t *tr;
  cap_in_t in;
  unsigned i;
  if (s->lim.capture == 0) return;
  if (t >= s->n_tracks || s->count_in_left > 0) return;
  if (s->cap_mode != CAP_NONE) return;
  if (s->recording && t == s->rec_track) return;
  CAP_CHECK(!on || vel > 0);   /* a note-on's velocity is 1..127: it marks the kind */
  tr = &sq_tracks(s)[t];
  if (on && s->playing) {
    for (i = 0; i < s->cap_len; ++i) {
      const sq_cap_t *e = ring_at(s, i);
      if (cap_on(e) && cap_track(e) == t && !cap_same_cycle(e, tr->cycle)) {
        const uint16_t ct = cap_clip_tick(e);
        const uint32_t d = ct > tr->pos_tick ? (uint32_t)(ct - tr->pos_tick)
                                             : (uint32_t)(tr->pos_tick - ct);
        if (d < SQ_TPS) {
          sq_capture_clear(s);
          break;
        }
      }
    }
  }
  in.frame = (uint32_t)frame;
  in.tick = (uint32_t)s->master_tick;
  in.cycle = tr->cycle;
  in.clip_tick = tr->pos_tick;
  in.track = (uint8_t)t;
  in.pitch = pitch;
  in.vel = on ? vel : 0;
  ring_push(s, &in, gap_frames(s), (uint64_t)CAP_MAX_BARS * bar_frames(s));
}

unsigned sq_capture_pending(fm1_seq_t *s, unsigned t) {
  unsigned i, n = 0;
  if (s->lim.capture == 0) return 0;
  for (i = 0; i < s->cap_len; ++i) {
    const sq_cap_t *e = ring_at(s, i);
    n += cap_track(e) == t && cap_on(e);
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
  for (i = 0; i < n_take; ++i) n_on += cap_on(&take[i]);
  if (n_on < 3) return 0;
  for (i = 0; i < N_BPM; ++i) {
    const float bpm = (float)(BPM_MIN + i);
    const float fpb = sr * 60.0f / bpm;
    float fit = 0.0f, bars;
    for (j = 0; j < n_take; ++j) {
      float beats;
      if (!cap_on(&take[j])) continue;
      beats = (float)(uint32_t)(cap_frame(s, &take[j]) - first) / fpb;
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

/* The frame of the take's first note-on (Movy's cap_take_first). */
static int take_first(const fm1_seq_t *s, const sq_cap_t *take, unsigned n, uint32_t *first) {
  unsigned i;
  for (i = 0; i < n; ++i) {
    if (cap_on(&take[i])) {
      *first = cap_frame(s, &take[i]);
      return 1;
    }
  }
  return 0;
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
  uint32_t span_ticks, loop_start, span_end = 0, first = 0;
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
  take_first(s, take, n, &first);
  for (i = 0; i < n; ++i) cap_set_used(&take[i], 0);
  for (i = 0; i < n; ++i) {
    const sq_cap_t ev = take[i];
    uint32_t start, gate = SQ_TPS, tick, ev_frame;
    uint16_t step;
    int32_t stored;
    if (!cap_on(&ev)) continue;
    ev_frame = cap_frame(s, &ev);
    for (j = i + 1; j < n; ++j) {
      if (!cap_on(&take[j]) && cap_pitch(&take[j]) == cap_pitch(&ev) && !cap_used(&take[j])) {
        const uint32_t d = (uint32_t)(cap_frame(s, &take[j]) - ev_frame);
        const uint32_t g = (uint32_t)roundf((float)d / fpt);
        cap_set_used(&take[j], 1);
        gate = g ? g : 1u;
        break;
      }
    }
    start = (uint32_t)roundf((float)(uint32_t)(ev_frame - first) / fpt);
    tick = keep_length ? loop_start + start % span_ticks : start;
    step = sq_anchor_step(s, tick, snum, sden);
    if (keep_length) {
      /* Movy clamps to len_steps - 1, a step before the window when the
       * window starts past step 0 (D5's length-for-end); the FM-1 clamps to
       * the window's last step. */
      const uint32_t last = (s->lim.compat ? 0u : loop_start / SQ_TPS) + (len_steps ? len_steps - 1u : 0u);
      if (step > last) step = (uint16_t)last;
    }
    stored = (int32_t)cap_pitch(&ev) - transpose;
    sq_clip_add_raw(s, clip, step, sq_unswing(s, tick, step, snum, sden), gate,
                    (uint8_t)(stored < 0 ? 0 : (stored > 127 ? 127 : stored)), cap_vel(&ev));
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
  int clip_has_notes, free_tempo, wrote;
  uint32_t existing, grid;
  ring_linearize(s);
  for (i = 0; i < s->cap_len; ++i) {
    if (cap_track(&e[i]) == t) e[n++] = e[i];
  }
  s->cap_take_len = (uint16_t)n;
  s->cap_len = 0;                       /* the ring now holds the frozen take */
  if (!take_first(s, e, n, &first)) return 0;
  last = n ? cap_frame(s, &e[n - 1u]) : first;
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
    if (cap_track(e) == t && cap_on(e)) {
      first_abs = cap_tick(s, e);
      have = 1;
    }
  }
  if (!have) return 0;
  first_phase = first_abs % SQ_TPB;
  for (i = 0; i < s->cap_len; ++i) cap_set_used(ring_at(s, i), 0);
  for (i = 0; i < s->cap_len; ++i) {
    const sq_cap_t ev = *ring_at(s, i);
    uint32_t end = now_abs, gate, tick, at;
    uint16_t step;
    int32_t stored;
    if (cap_track(&ev) != t || !cap_on(&ev)) continue;
    at = cap_tick(s, &ev);
    for (j = i + 1; j < s->cap_len; ++j) {
      sq_cap_t *o = ring_at(s, j);
      if (cap_track(o) == t && !cap_on(o) && cap_pitch(o) == cap_pitch(&ev) && !cap_used(o)) {
        cap_set_used(o, 1);
        end = cap_tick(s, o);
        break;
      }
    }
    gate = end > at ? end - at : 0;
    if (gate < 1) gate = 1;
    tick = fresh ? loop_start + first_phase + (at > first_abs ? at - first_abs : 0)
                 : cap_clip_tick(&ev) % span;
    stored = (int32_t)cap_pitch(&ev) - transpose;
    step = sq_anchor_step(s, tick, snum, sden);
    sq_clip_add_raw(s, clip, step, sq_unswing(s, tick, step, snum, sden), gate,
                    (uint8_t)(stored < 0 ? 0 : (stored > 127 ? 127 : stored)), cap_vel(&ev));
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
