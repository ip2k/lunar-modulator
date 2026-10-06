/* fx_host.c -- engine API v3's effect extension on the host side
 * (fm1_fx_host.h): the tempo, beats and transport events an effect hears,
 * from the sequencer's integer clock, and the split renders that put each
 * event at the first frame of a piece. C99, no heap, no stdio, no libm.
 * MIT licence. */
#include "fm1_fx_host.h"

#include <string.h>

#define BEAT_TICKS ((uint64_t)FM1_SEQ_PPQN)

/* Whether the clock runs on its grid (beats and phases inside a block). */
static int on_grid(const fm1_seq_clock_t *c) {
  return c && c->playing && c->inc > 0u && c->threshold > 0u;
}

/* Ticks serviced up to and including frame f (f = -1: before the block),
 * and the running sum's remainder there. */
static uint64_t done_at(const fm1_seq_clock_t *c, int64_t f, uint64_t *rem) {
  const uint64_t sum = c->accum + (uint64_t)(f + 1) * c->inc;
  if (rem) *rem = sum % c->threshold;
  return c->master_tick + sum / c->threshold;
}

void fm1_fx_block_ext(const fm1_fx_block_t *b, uint32_t frame, fm1_fx_ext_t *ext) {
  const fm1_seq_clock_t *c = b ? b->clock : NULL;
  memset(ext, 0, sizeof(*ext));
  ext->key_lr = NULL;
  if (!c) {
    ext->bpm = b && b->bpm > 0.0f ? b->bpm : 120.0f;
    return;
  }
  ext->bpm = (float)c->bpm_x100 * 0.01f;
  ext->running = c->playing ? 1u : 0u;
  if (!c->playing) return;
  if (on_grid(c)) {
    uint64_t rem;
    const uint64_t done = done_at(c, (int64_t)frame, &rem);
    if (done > 0u) {
      /* Position done - 1 + rem / threshold ticks: beat (done - 1) / 96,
       * and the phase from integers, rounded once to float. */
      const uint64_t t = done - 1u;
      const uint64_t num = (t % BEAT_TICKS) * c->threshold + rem;
      float phase = (float)num / (float)(BEAT_TICKS * c->threshold);
      if (phase >= 1.0f) phase = 0.99999994f;   /* the float below 1 */
      ext->beat = (uint32_t)(t / BEAT_TICKS);
      ext->phase = phase;
    }
  } else if (c->master_tick > 0u) {
    /* Off the grid: the last tick serviced before the block. */
    const uint64_t t = c->master_tick - 1u;
    ext->beat = (uint32_t)(t / BEAT_TICKS);
    ext->phase = (float)(t % BEAT_TICKS) * (1.0f / (float)BEAT_TICKS);
  }
}

uint32_t fm1_fx_block_next_beat(const fm1_fx_block_t *b, uint32_t from, uint32_t to) {
  const fm1_seq_clock_t *c = b ? b->clock : NULL;
  uint64_t d, beat_tick, need, f;
  if (!on_grid(c) || from >= to) return to;
  d = done_at(c, (int64_t)from - 1, NULL);              /* the next tick to service */
  beat_tick = (d + BEAT_TICKS - 1u) / BEAT_TICKS * BEAT_TICKS;
  /* Its frame: the first f with accum + (f + 1) inc >= (beat_tick + 1 -
   * master_tick) threshold. */
  need = (beat_tick + 1u - c->master_tick) * c->threshold - c->accum;
  f = (need + c->inc - 1u) / c->inc - 1u;
  return f < (uint64_t)to ? (uint32_t)f : to;
}

/* The transport events the block holds at frame f, as FM1_FX_EV_* bits,
 * and the first such frame after f (or `to`) in *next. */
static uint8_t transport_at(const fm1_fx_block_t *b, uint32_t f, uint32_t to, uint32_t *next) {
  uint8_t ev = 0;
  uint32_t k;
  for (k = 0; b && b->ev && k < b->n_ev; ++k) {
    const fm1_seq_ev_t *e = &b->ev[k];
    uint32_t at;
    if (e->kind != FM1_SEQ_EV_START && e->kind != FM1_SEQ_EV_STOP) continue;
    at = e->frame < b->frames ? e->frame : b->frames;
    if (at == f) ev |= e->kind == FM1_SEQ_EV_START ? FM1_FX_EV_START : FM1_FX_EV_STOP;
    else if (at > f && at < *next) *next = at;
  }
  (void)to;
  return ev;
}

uint32_t fm1_fx_render(const fm1_engine_t *e, void *self, float *lr, uint32_t from, uint32_t to,
                       const fm1_fx_block_t *b) {
  uint32_t cur = from, calls = 0;
  if (from >= to) return 0;
  if (!e->render_ext) {
    e->render(self, lr + 2u * from, to - from);
    return 1;
  }
  while (cur < to) {
    uint32_t next = to;
    uint8_t events = 0;
    fm1_fx_ext_t ext;
    if (e->fx_wants & FM1_FX_WANT_TRANSPORT) events |= transport_at(b, cur, to, &next);
    if (e->fx_wants & FM1_FX_WANT_TEMPO) {
      const uint32_t beat = fm1_fx_block_next_beat(b, cur, next);
      if (beat == cur) {
        events |= FM1_FX_EV_BEAT;
        /* the next one, past this frame */
        next = fm1_fx_block_next_beat(b, cur + 1u, next);
      } else {
        next = beat;
      }
    }
    fm1_fx_block_ext(b, cur, &ext);
    ext.events = events;
    e->render_ext(self, lr + 2u * cur, next - cur, &ext);
    ++calls;
    cur = next;
  }
  return calls;
}
