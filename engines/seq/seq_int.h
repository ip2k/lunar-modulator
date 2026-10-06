/* seq_int.h -- internal state of the sequencer core (fm1_seq.h).
 *
 * Derived from Movy's seq-core (engine/crates/seq-core/src/, commit 9190e79,
 * MIT, Copyright (c) 2026 megadake): track.rs, clip.rs and engine.rs's Engine
 * struct, re-laid out as fixed pools inside one caller-provided block.
 *
 * Layout rules, so the block has the same size on 32- and 64-bit targets:
 * no pointers in the state (regions are byte offsets from the instance),
 * 8-byte fields first, every struct padded explicitly.
 */
#ifndef FM1_SEQ_INT_H_
#define FM1_SEQ_INT_H_

#include "fm1_seq.h"

#include <stdint.h>
#include <string.h>

#define SQ_MAGIC 0x53314D46u            /* "FM1S" */
#define SQ_NONE FM1_SEQ_NONE
#define SQ_TPS FM1_SEQ_TICKS_PER_STEP
#define SQ_BAR_STEPS FM1_SEQ_STEPS_PER_BAR
#define SQ_TPB FM1_SEQ_TICKS_PER_BAR
#define SQ_MAX_STEPS FM1_SEQ_MAX_STEPS

/* A note. `step` carries two pass flags in its top bits and one scratch bit
 * pair used only inside one step_tick. `fire` caches the tick the note fires
 * on (R5, R6); `ix` is this clip's fire-tick index, one entry per note slot:
 * the clip's note numbers sorted by (fire, insertion order). */
typedef struct {
  uint16_t tick;     /* absolute start tick in the clip */
  uint16_t gate;     /* ticks, >= 1 */
  uint16_t step;     /* anchor, 0..256, plus the flags below */
  uint16_t fire;     /* cached fire tick; SQ_FIRE_NEVER when out of reach */
  uint16_t ix;       /* fire-tick index entry */
  uint8_t pitch;     /* stored without clip transpose */
  uint8_t vel;
} sq_note_t;

#define SQ_STEP_MASK 0x01FFu
#define SQ_N_SUPPRESS 0x8000u   /* just recorded: skip until the clip wraps */
#define SQ_N_FIRED 0x4000u      /* sounded (or rolled) this pass */
#define SQ_N_DECIDED 0x2000u    /* scratch: trig decided in this step_tick */
#define SQ_N_PLAYS 0x1000u      /* scratch: ...and the decision was "play" */
#define SQ_FIRE_NEVER 0xFFFFu

#define SQ_NSTEP(n) ((uint16_t)((n)->step & SQ_STEP_MASK))

/* A parameter lock: (lane, step) -> value. */
typedef struct {
  uint8_t step;
  uint8_t lane;
  fm1_seq_val_t val;
} sq_lock_t;

/* A trig row: (step, pitch or whole step) -> probability and condition. */
typedef struct {
  uint8_t step;
  uint8_t lane;      /* pitch 0..127, or SQ_NONE for the whole step */
  uint8_t prob_inv;  /* bits 0..6 probability 0..100, bit 7 invert */
  uint8_t a, b;      /* condition A:B */
} sq_trig_t;

enum { SQ_K_NOTES = 0, SQ_K_LOCKS = 1, SQ_K_TRIGS = 2, SQ_K_COUNT = 3 };

typedef struct {
  uint16_t off, len;
} sq_seg_t;

/* A clip's items live in a slice of each global pool. Slices are packed in
 * clip order, so growing one shifts the clips after it. */
typedef struct {
  sq_seg_t seg[SQ_K_COUNT];
  uint16_t length_steps;   /* 0 = no clip */
  uint8_t loop_start;      /* steps */
  uint8_t scale_num, scale_den;
  int8_t transpose;
  uint8_t quant;
  uint8_t flags;           /* SQ_C_INDEX_OK */
} sq_clip_t;

#define SQ_C_INDEX_OK 0x01u

typedef struct {
  uint32_t cycle;          /* A:B play count, from 1 */
  uint16_t pos_tick;
  uint16_t scale_acc;
  int16_t last_auto_step;
  int16_t auto_cur[FM1_SEQ_LANES];
  uint8_t active, playing, queued, pending_select;
  uint8_t pending_stop, muted, drum, lanes_assigned;
  uint8_t pad_solo, n_pad_mutes, route_kind, route_index;
  fm1_seq_val_t base[FM1_SEQ_LANES];
  char label[FM1_SEQ_LANES][FM1_SEQ_LABEL_MAX];
} sq_track_t;

typedef struct {
  uint8_t track, pitch;
  uint16_t left;           /* ticks until note-off */
  uint16_t serial;         /* age, for D7's oldest-first eviction */
} sq_gate_t;

/* A recorded note still held (engine.rs RecPending). */
typedef struct {
  uint32_t start_cycle;
  int16_t start_tick;      /* negative: inside the count-in's pre-roll */
  uint8_t pitch, vel, track, slot;
  uint16_t pad;
} sq_rec_t;

/* Capture input (capture.rs CapEvent), packed into three 32-bit words; only
 * seq_capture.c reads or writes them, through its cap_* accessors, which
 * also give the widths their reasons:
 *
 *   w[0]  bits  0-24  frame, as an offset from fm1_seq.cap_base_frame
 *         bits 25-31  pitch, 0..127
 *   w[1]  bits  0-15  master tick: the tick itself, or (bit 16 set) an
 *                     offset from fm1_seq.cap_base_tick
 *         bit  16     the tick is an offset from the base
 *         bits 17-30  the track's playhead (clip tick), 0..16,383
 *         bit  31     scratch of a commit: this note-off already ends a note
 *   w[2]  bits  0-19  the track's loop cycle, modulo 2^20
 *         bit  20     the cycle is 2^20 or more
 *         bits 21-24  track, 0..15
 *         bits 25-31  velocity: 1..127 for a note-on, 0 for a note-off
 *
 * The checking build (SQ_CHECK_INDEX) also keeps every value unpacked and
 * traps if one ever decodes, or compares, differently. */
typedef struct {
  uint32_t w[3];
#ifdef SQ_CHECK_INDEX
  uint32_t chk_frame, chk_tick, chk_cycle;
  uint16_t chk_clip_tick, chk_pad;
#endif
} sq_cap_t;

struct fm1_seq {
  /* 8-byte fields */
  uint64_t accum, threshold;    /* clock.rs */
  uint64_t clock_tick;
  uint64_t master_tick;
  uint64_t rng;
  uint64_t frame_now;
  uint64_t ext_ticks, ext_last_frame, ext_base;
  uint64_t song_start_bar;

  /* 4-byte fields */
  uint32_t magic, size, sample_rate, bpm_x100;
  uint16_t swing_pct;           /* 50..80 */
  uint8_t key_root, key_scale;  /* the project key (fm1_seq.h), in what was swing's
                                   upper half: the instance's size is unchanged */
  uint32_t count_in_left;
  uint32_t off_tracks, off_pmutes, off_clips, off_notes, off_locks, off_trigs;
  uint32_t off_gates, off_song, off_pend, off_tail, off_cap;
  uint32_t last_cmd_seq;
  float ext_interval;
  uint32_t cap_base_frame, cap_base_tick;  /* Capture's packed offsets count from these */
  uint32_t capture_gen;
  int32_t held_track, held_step;
  fm1_seq_stats_t stats;        /* 4-byte aligned, 24 bytes */

  /* 2-byte fields */
  uint16_t used[SQ_K_COUNT];    /* items in each pool */
  uint16_t clipboard_span;
  uint16_t gate_serial;
  uint16_t cap_head, cap_len, cap_take_len;
  uint16_t song_pos;
  int16_t watch_lane;           /* -1: melodic view */
  uint16_t cap_cands[3];
  uint16_t bar_tick;            /* master_tick % 384: the per-tick path needs no
                                   64-bit modulo on a 32-bit core */

  /* 1-byte fields */
  fm1_seq_limits_t lim;         /* 20 bytes, alignment 2 */
  uint8_t n_tracks, n_clips;    /* clips: tracks * 8 + the two clipboards */
  uint8_t playing, recording, rec_track, rec_empty_start, pending_rec, metronome;
  uint8_t default_quant, emitting_clock, watch_track, clip_clipboard;
  uint8_t song_len, song_has_start, song_armed, song_armed_launch;
  uint8_t ext_running, ext_awaiting_first, ext_base_set, was_following;
  uint8_t resume_anchor_pending, link_enabled, move_inject_ok, has_cmd_seq;
  uint8_t dirty, n_gates, n_pend, n_tail;
  uint8_t cap_mode, cap_why, cap_track, cap_sel, cap_n, cap_best, cap_has_guess;
  uint8_t panicked;             /* compat: this op hit one of Movy's panics, so the
                                   rest of its batch is lost (movy-dsp's catch_unwind) */
};

/* Clip numbers: track t, slot k is t*8+k; then the step clipboard (copy_steps
 * notes and locks, relative to the copy start) and the clip clipboard. */
#define SQ_CLIP_STEPCB(s) ((uint8_t)((s)->n_tracks * FM1_SEQ_SLOTS))
#define SQ_CLIP_CLIPCB(s) ((uint8_t)((s)->n_tracks * FM1_SEQ_SLOTS + 1u))

#define SQ_AT(s, off, T) ((T *)(void *)((uint8_t *)(s) + (off)))
#define SQ_CAT(s, off, T) ((const T *)(const void *)((const uint8_t *)(s) + (off)))

static inline sq_track_t *sq_tracks(fm1_seq_t *s) { return SQ_AT(s, s->off_tracks, sq_track_t); }
static inline const sq_track_t *sq_ctracks(const fm1_seq_t *s) { return SQ_CAT(s, s->off_tracks, sq_track_t); }
static inline sq_clip_t *sq_clips(fm1_seq_t *s) { return SQ_AT(s, s->off_clips, sq_clip_t); }
static inline const sq_clip_t *sq_cclips(const fm1_seq_t *s) { return SQ_CAT(s, s->off_clips, sq_clip_t); }
static inline sq_note_t *sq_notes(fm1_seq_t *s) { return SQ_AT(s, s->off_notes, sq_note_t); }
static inline const sq_note_t *sq_cnotes(const fm1_seq_t *s) { return SQ_CAT(s, s->off_notes, sq_note_t); }
static inline sq_lock_t *sq_locks(fm1_seq_t *s) { return SQ_AT(s, s->off_locks, sq_lock_t); }
static inline const sq_lock_t *sq_clocks(const fm1_seq_t *s) { return SQ_CAT(s, s->off_locks, sq_lock_t); }
static inline sq_trig_t *sq_trigs(fm1_seq_t *s) { return SQ_AT(s, s->off_trigs, sq_trig_t); }
static inline const sq_trig_t *sq_ctrigs(const fm1_seq_t *s) { return SQ_CAT(s, s->off_trigs, sq_trig_t); }
static inline sq_gate_t *sq_gates(fm1_seq_t *s) { return SQ_AT(s, s->off_gates, sq_gate_t); }
static inline uint8_t *sq_song(fm1_seq_t *s) { return SQ_AT(s, s->off_song, uint8_t); }
static inline const uint8_t *sq_csong(const fm1_seq_t *s) { return SQ_CAT(s, s->off_song, uint8_t); }
static inline sq_rec_t *sq_pend(fm1_seq_t *s) { return SQ_AT(s, s->off_pend, sq_rec_t); }
static inline sq_rec_t *sq_tail(fm1_seq_t *s) { return SQ_AT(s, s->off_tail, sq_rec_t); }
static inline sq_cap_t *sq_cap(fm1_seq_t *s) { return SQ_AT(s, s->off_cap, sq_cap_t); }
static inline uint8_t *sq_pmutes(fm1_seq_t *s, unsigned t) {
  return SQ_AT(s, s->off_pmutes, uint8_t) + (size_t)t * s->lim.pad_mutes;
}
static inline const uint8_t *sq_cpmutes(const fm1_seq_t *s, unsigned t) {
  return SQ_CAT(s, s->off_pmutes, uint8_t) + (size_t)t * s->lim.pad_mutes;
}

static inline sq_clip_t *sq_clip(fm1_seq_t *s, unsigned t, unsigned slot) {
  return &sq_clips(s)[t * FM1_SEQ_SLOTS + slot];
}
static inline const sq_clip_t *sq_cclip(const fm1_seq_t *s, unsigned t, unsigned slot) {
  return &sq_cclips(s)[t * FM1_SEQ_SLOTS + slot];
}
static inline unsigned sq_clip_no(unsigned t, unsigned slot) { return t * FM1_SEQ_SLOTS + slot; }

static inline sq_note_t *sq_cnote(fm1_seq_t *s, const sq_clip_t *c, unsigned i) {
  return &sq_notes(s)[c->seg[SQ_K_NOTES].off + i];
}
static inline sq_lock_t *sq_clock(fm1_seq_t *s, const sq_clip_t *c, unsigned i) {
  return &sq_locks(s)[c->seg[SQ_K_LOCKS].off + i];
}
static inline sq_trig_t *sq_ctrig(fm1_seq_t *s, const sq_clip_t *c, unsigned i) {
  return &sq_trigs(s)[c->seg[SQ_K_TRIGS].off + i];
}

static inline int sq_exists(const sq_clip_t *c) { return c->length_steps > 0; }
static inline uint32_t sq_len_ticks(const sq_clip_t *c) { return (uint32_t)c->length_steps * SQ_TPS; }
static inline uint32_t sq_start_ticks(const sq_clip_t *c) { return (uint32_t)c->loop_start * SQ_TPS; }
static inline uint32_t sq_end_ticks(const sq_clip_t *c) { return sq_start_ticks(c) + sq_len_ticks(c); }

/* Emission context: where one call's events go. Kept off the instance so the
 * instance holds no pointers. */
typedef struct {
  fm1_seq_t *s;
  fm1_seq_ev_t *out;
  uint32_t cap, n;
  uint32_t tick;
  uint16_t frame;
} sq_out_t;

/* 1 if the event went out; 0 if the buffer had no room for it (seq_engine.c). */
int sq_emit(sq_out_t *o, uint8_t kind, uint8_t track, uint8_t a, fm1_seq_val_t b);

/* seq_clip.c: pools and Movy's Clip methods. */
int sq_seg_insert(fm1_seq_t *s, unsigned clip, int kind, unsigned pos, const void *item);
void sq_seg_remove(fm1_seq_t *s, unsigned clip, int kind, unsigned pos);
void sq_seg_swap_remove(fm1_seq_t *s, unsigned clip, int kind, unsigned pos);
void sq_seg_clear(fm1_seq_t *s, unsigned clip, int kind);
int sq_clip_copy(fm1_seq_t *s, unsigned dst, unsigned src);
void sq_clip_reset(fm1_seq_t *s, unsigned clip);   /* Clip::new() */
void sq_clip_clear(fm1_seq_t *s, unsigned clip);   /* Clip::clear() */
void sq_clip_invalidate(fm1_seq_t *s, unsigned clip);
int sq_pool_room(fm1_seq_t *s, int kind, unsigned need, unsigned freed);
unsigned sq_clip_room(const fm1_seq_t *s, unsigned clip, int kind);
void sq_invalidate_all(fm1_seq_t *s);
void sq_clip_index(fm1_seq_t *s, unsigned clip);
#ifdef SQ_CHECK_INDEX
void sq_check_index(fm1_seq_t *s, unsigned clip);  /* traps if the index is stale */
#endif

int sq_clip_has_notes_at(fm1_seq_t *s, unsigned clip, uint16_t step);
int sq_clip_lock_at(fm1_seq_t *s, unsigned clip, uint8_t lane, uint16_t step, fm1_seq_val_t *val);
int sq_clip_has_lock_on_lane(fm1_seq_t *s, unsigned clip, uint8_t lane);
void sq_clip_set_lock(fm1_seq_t *s, unsigned clip, uint8_t lane, uint16_t step, fm1_seq_val_t val);
void sq_clip_clear_lane(fm1_seq_t *s, unsigned clip, uint8_t lane);
void sq_clip_clear_lock(fm1_seq_t *s, unsigned clip, uint8_t lane, uint16_t step);
void sq_clip_clear_step_locks(fm1_seq_t *s, unsigned clip, uint16_t step);
void sq_clip_set_lock_range(fm1_seq_t *s, unsigned clip, uint8_t lane, uint16_t s0, uint16_t s1,
                            fm1_seq_val_t val);

typedef struct { uint8_t prob, a, b, inv; } sq_props_t;
sq_props_t sq_clip_governing_trig(fm1_seq_t *s, unsigned clip, uint16_t step, uint8_t pitch);
int sq_clip_has_trig_row(fm1_seq_t *s, unsigned clip, uint16_t step, uint8_t lane);
enum { SQ_TRIG_PROB, SQ_TRIG_COND, SQ_TRIG_INV };
void sq_clip_edit_trig(fm1_seq_t *s, unsigned clip, uint16_t s0, uint16_t s1, uint8_t lane,
                       int what, uint8_t v1, uint8_t v2);

void sq_clip_ensure_exists(fm1_seq_t *s, unsigned clip);
void sq_clip_set_loop(fm1_seq_t *s, unsigned clip, uint16_t start, uint16_t len);
void sq_clip_set_length(fm1_seq_t *s, unsigned clip, uint16_t steps);
void sq_clip_double(fm1_seq_t *s, unsigned clip);
int sq_clip_toggle_step(fm1_seq_t *s, unsigned clip, uint16_t step, const uint8_t *pv, unsigned n);
int sq_clip_toggle_pitch(fm1_seq_t *s, unsigned clip, uint16_t step, uint8_t pitch, uint8_t vel,
                         int inherit);
void sq_clip_record_note(fm1_seq_t *s, unsigned clip, uint16_t step, uint32_t tick, uint32_t gate,
                         uint8_t pitch, uint8_t vel, int suppress);
void sq_clip_add_raw(fm1_seq_t *s, unsigned clip, uint16_t step, uint32_t tick, uint32_t gate,
                     uint8_t pitch, uint8_t vel);
void sq_clip_release_pass(fm1_seq_t *s, unsigned clip);
enum { SQ_EDIT_VEL, SQ_EDIT_TRANSPOSE, SQ_EDIT_LENGTH, SQ_EDIT_NUDGE, SQ_EDIT_SETLEN };
void sq_clip_edit(fm1_seq_t *s, unsigned clip, uint16_t s0, uint16_t s1, int lane, int what,
                  int32_t v);
void sq_clip_delete_range(fm1_seq_t *s, unsigned clip, uint16_t s0, uint16_t s1, int lane);
void sq_clip_add_pitch_range(fm1_seq_t *s, unsigned clip, uint16_t s0, uint16_t s1, uint8_t pitch,
                             uint8_t vel, int inherit);
int sq_effective_at(const fm1_seq_t *s, unsigned clip, uint8_t lane, uint16_t step,
                    fm1_seq_val_t base);
uint32_t sq_swing_delay(const fm1_seq_t *s, uint16_t step, uint8_t num, uint8_t den);
uint32_t sq_unswing(const fm1_seq_t *s, uint32_t tick, uint16_t step, uint8_t num, uint8_t den);
void sq_scale_limit(const fm1_seq_t *s, uint8_t *num, uint8_t *den);

/* seq_engine.c */
void sq_reseed_empty_clips(fm1_seq_t *s);
void sq_set_bpm(fm1_seq_t *s, uint32_t bpm_x100);
void sq_play(fm1_seq_t *s);
void sq_stop(fm1_seq_t *s, sq_out_t *o);
void sq_ensure_selected_playing(fm1_seq_t *s, unsigned t);
void sq_launch_clip(fm1_seq_t *s, unsigned t, unsigned slot);
void sq_launch_scene(fm1_seq_t *s, unsigned slot);
void sq_song_start(fm1_seq_t *s, unsigned slot);
void sq_song_add(fm1_seq_t *s, unsigned slot);
void sq_clear_song(fm1_seq_t *s);
void sq_stop_track(fm1_seq_t *s, unsigned t);
void sq_flush_track_gates(fm1_seq_t *s, unsigned t, sq_out_t *o);
void sq_flush_silenced_pad_gates(fm1_seq_t *s, unsigned t, sq_out_t *o);
void sq_toggle_record(fm1_seq_t *s, unsigned t);
void sq_live_note_on(fm1_seq_t *s, unsigned t, uint8_t pitch, uint8_t vel, uint64_t frame);
void sq_live_note_off(fm1_seq_t *s, unsigned t, uint8_t pitch, uint64_t frame);
void sq_delete_clip_at(fm1_seq_t *s, unsigned t, unsigned slot, sq_out_t *o);
void sq_duplicate_clip(fm1_seq_t *s, unsigned t);
void sq_copy_clip(fm1_seq_t *s, unsigned t, unsigned slot);
void sq_paste_clip(fm1_seq_t *s, unsigned t, unsigned slot, sq_out_t *o);
void sq_delete_range(fm1_seq_t *s, unsigned t, uint16_t s0, uint16_t s1, int lane, sq_out_t *o);
void sq_copy_steps(fm1_seq_t *s, unsigned t, uint16_t s0, uint16_t s1);
void sq_paste_steps(fm1_seq_t *s, unsigned t, uint16_t dest);
void sq_clear_clipboard(fm1_seq_t *s);
void sq_free_unused_lanes(fm1_seq_t *s, unsigned t, sq_out_t *o);
void sq_release_lane(fm1_seq_t *s, unsigned t, unsigned lane, sq_out_t *o);
int sq_active_transpose(const fm1_seq_t *s, unsigned t);
int sq_pad_voice_silent(fm1_seq_t *s, unsigned t, uint8_t pitch);
void sq_set_pad_mute(fm1_seq_t *s, unsigned t, uint8_t note, int muted);
void sq_external_realtime(fm1_seq_t *s, uint8_t status, uint64_t frame, sq_out_t *o);

/* seq_capture.c (Capture; inert when limits.capture is 0) */
void sq_capture_clear(fm1_seq_t *s);
void sq_capture_push(fm1_seq_t *s, unsigned t, uint8_t pitch, uint8_t vel, int on, uint64_t frame);
unsigned sq_capture_pending(fm1_seq_t *s, unsigned t);
int sq_capture_commit(fm1_seq_t *s, unsigned t);
void sq_capture_select(fm1_seq_t *s, unsigned idx);
void sq_capture_done(fm1_seq_t *s);
uint16_t sq_anchor_step(const fm1_seq_t *s, uint32_t tick, uint8_t num, uint8_t den);

#endif /* FM1_SEQ_INT_H_ */
