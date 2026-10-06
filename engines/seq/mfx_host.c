/* mfx_host.c -- MIDI effects on the host bridge (fm1_mfx_host.h): the
 * chains, their clock, the live notes they take and the block they run.
 * C99, no heap, no stdio, no libm. MIT licence. */
#include "fm1_mfx_host.h"

#include <string.h>

#define TPS_DIV 6000u                 /* bpm_x100 x 96 per (rate x 6000): ticks a frame */

/* ---- set-up ------------------------------------------------------------------ */

void fm1_mfx_init(fm1_mfx_t *m, uint32_t rate) {
  memset(m, 0, sizeof(*m));
  m->rate = rate ? rate : 1u;
  m->bpm_x100 = 12000u;
  m->key_root = 0;
  m->key_scale = FM1_KEY_MAJOR;
}

void fm1_mfx_set_tempo(fm1_mfx_t *m, uint32_t bpm_x100) {
  if (bpm_x100 < FM1_SEQ_BPM_X100_MIN) bpm_x100 = FM1_SEQ_BPM_X100_MIN;
  if (bpm_x100 > FM1_SEQ_BPM_X100_MAX) bpm_x100 = FM1_SEQ_BPM_X100_MAX;
  m->bpm_x100 = bpm_x100;
}

void fm1_mfx_set_key(fm1_mfx_t *m, unsigned root, unsigned scale) {
  m->key_root = (uint8_t)(root % 12u);
  m->key_scale = (uint8_t)(scale <= FM1_KEY_CHROMATIC ? scale : FM1_KEY_MAJOR);
}

static fm1_mfx_chain_t *chain_of(fm1_mfx_t *m, unsigned c) {
  return c < FM1_MFX_CHAINS ? &m->chain[c] : NULL;
}

int fm1_mfx_active(const fm1_mfx_t *m, unsigned c) {
  unsigned s;
  if (c >= FM1_MFX_CHAINS) return 0;
  for (s = 0; s < FM1_MFX_SLOTS; ++s) {
    if (m->chain[c].slot[s].fx && m->chain[c].slot[s].on) return 1;
  }
  return 0;
}

int fm1_mfx_is_on(const fm1_mfx_t *m, unsigned c, unsigned s) {
  return c < FM1_MFX_CHAINS && s < FM1_MFX_SLOTS && m->chain[c].slot[s].fx &&
         m->chain[c].slot[s].on;
}

const fm1_mfx_slot_t *fm1_mfx_slot(const fm1_mfx_t *m, unsigned c, unsigned s) {
  return c < FM1_MFX_CHAINS && s < FM1_MFX_SLOTS ? &m->chain[c].slot[s] : NULL;
}

/* ---- flushing between blocks --------------------------------------------------- */

static void put(fm1_midi_ev_t *buf, uint32_t *n, uint16_t frame, uint8_t kind, uint8_t a,
                uint16_t b) {
  fm1_midi_ev_t *e = &buf[(*n)++];
  e->frame = frame;
  e->kind = kind;
  e->a = a;
  e->b = b;
}


/* The context of a call between blocks: no ticks, the transport as it was. */
static void quiet_ctx(const fm1_mfx_t *m, fm1_midi_fx_ctx_t *ctx) {
  memset(ctx, 0, sizeof(*ctx));
  ctx->bpm_x100 = m->bpm_x100;
  ctx->running = m->running;
  ctx->key_root = m->key_root;
  ctx->key_scale = m->key_scale;
}

/* Now, between blocks: the effects of chain c that are on, from slot
 * `first`, each given the one before's output; slot `first` (when `only`)
 * or every one (else) first gets `kind`, FLUSH or PANIC, at frame 0. The
 * note-offs that come out of the last go to the sink. (Only note-offs: an
 * effect given note-offs and a flush has no note to start.) */
static void run_quiet(fm1_mfx_t *m, unsigned c, unsigned first, uint8_t kind, int only,
                      const fm1_mfx_sink_t *sink) {
  fm1_mfx_chain_t *ch = &m->chain[c];
  fm1_midi_fx_ctx_t ctx;
  uint32_t n = 0, i;
  unsigned s;
  int started = 0;
  quiet_ctx(m, &ctx);
  for (s = first; s < FM1_MFX_SLOTS; ++s) {
    fm1_mfx_slot_t *sl = &ch->slot[s];
    if (!sl->fx || !sl->on) continue;
    if (!started || !only) {             /* the flush, ahead of what came out before */
      memmove(m->a + 1, m->a, n * sizeof(m->a[0]));
      m->a[0].frame = 0;
      m->a[0].kind = kind;
      m->a[0].a = 0;
      m->a[0].b = 0;
      ++n;
    }
    started = 1;
    n = sl->fx->process(sl->self, m->a, n, &ctx, m->b, FM1_MFX_OUT);
    if (n > FM1_MFX_OUT) n = FM1_MFX_OUT;
    memcpy(m->a, m->b, n * sizeof(m->a[0]));
  }
  for (i = 0; started && i < n; ++i) {
    if (m->a[i].kind != FM1_MIDI_EV_NOTE_OFF) continue;
    if (sink && sink->note_off) sink->note_off(sink->ctx, c, m->a[i].a);
    ++m->stats.notes_out;
  }
}

/* A chain that has no effect on any more forgets what it took: its notes'
 * offs go straight to the sound from now on. */
static void forget_if_idle(fm1_mfx_t *m, unsigned c) {
  fm1_mfx_chain_t *ch = &m->chain[c];
  if (fm1_mfx_active(m, c)) return;
  memset(ch->held, 0, sizeof(ch->held));
  memset(ch->owed, 0, sizeof(ch->owed));
  ch->n_live = 0;
}

void fm1_mfx_flush(fm1_mfx_t *m, unsigned c, int panic, const fm1_mfx_sink_t *sink) {
  fm1_mfx_chain_t *ch = chain_of(m, c);
  if (!ch) return;
  run_quiet(m, c, 0, panic ? FM1_MIDI_EV_PANIC : FM1_MIDI_EV_FLUSH, 0, sink);
  if (panic) {
    memset(ch->held, 0, sizeof(ch->held));
    memset(ch->owed, 0, sizeof(ch->owed));
    ch->n_live = 0;
  }
}

/* Slot s of chain c ends its notes and forgets its keys, as it is bypassed,
 * replaced or removed; the effects after it hear its note-offs. */
static void retire(fm1_mfx_t *m, unsigned c, unsigned s, const fm1_mfx_sink_t *sink) {
  const fm1_mfx_slot_t *sl = &m->chain[c].slot[s];
  if (sl->fx && sl->on) run_quiet(m, c, s, FM1_MIDI_EV_PANIC, 1, sink);
}

int fm1_mfx_set(fm1_mfx_t *m, unsigned c, unsigned s, const fm1_midi_fx_t *fx, void *self, int on,
                const fm1_mfx_sink_t *sink) {
  fm1_mfx_slot_t *sl;
  if (c >= FM1_MFX_CHAINS || s >= FM1_MFX_SLOTS) return 0;
  if (fx && (fx->engine.kind != FM1_KIND_MIDI_FX || !fx->process || !self)) return 0;
  retire(m, c, s, sink);
  sl = &m->chain[c].slot[s];
  sl->fx = fx;
  sl->self = fx ? self : NULL;
  sl->on = fx && on ? 1u : 0u;
  forget_if_idle(m, c);
  return 1;
}

int fm1_mfx_set_on(fm1_mfx_t *m, unsigned c, unsigned s, int on, const fm1_mfx_sink_t *sink) {
  fm1_mfx_slot_t *sl;
  if (c >= FM1_MFX_CHAINS || s >= FM1_MFX_SLOTS || !m->chain[c].slot[s].fx) return 0;
  sl = &m->chain[c].slot[s];
  if (!on && sl->on) retire(m, c, s, sink);
  sl->on = on ? 1u : 0u;
  forget_if_idle(m, c);
  return 1;
}

/* ---- live notes ------------------------------------------------------------- */

int fm1_mfx_live_note(fm1_mfx_t *m, unsigned c, uint8_t key, uint8_t velocity) {
  fm1_mfx_chain_t *ch = chain_of(m, c);
  fm1_midi_ev_t *e;
  if (!ch || key > 127u) return 0;
  if (velocity) {
    if (!fm1_mfx_active(m, c) || ch->n_live >= FM1_MFX_LIVE || ch->held[key] == 255u) {
      if (fm1_mfx_active(m, c)) ++m->stats.direct;
      return 0;
    }
    ++ch->held[key];
  } else {
    if (!ch->held[key]) return 0;          /* not the chain's: the host's to end */
    --ch->held[key];
    if (ch->n_live >= FM1_MFX_LIVE) {      /* no room: first thing next block */
      ch->owed[key >> 3] |= (uint8_t)(1u << (key & 7u));
      ++m->stats.deferred_offs;
      return 1;
    }
  }
  e = &ch->live[ch->n_live++];
  e->frame = 0;
  e->kind = velocity ? FM1_MIDI_EV_NOTE_ON : FM1_MIDI_EV_NOTE_OFF;
  e->a = key;
  e->b = velocity;
  ++m->stats.notes_in;
  return 1;
}

/* ---- the block ---------------------------------------------------------------- */

/* The block's ticks: the frames where the running sum accum + (f + 1) inc
 * reaches the next multiple of threshold, as fm1_seq_advance services them. */
static uint32_t grid_ticks(uint16_t *ticks, uint32_t cap, uint64_t accum, uint64_t inc,
                           uint64_t threshold, uint32_t frames) {
  uint64_t need = threshold - accum;   /* > 0 */
  uint32_t n = 0;
  while (n < cap) {
    const uint64_t f = (need + inc - 1u) / inc - 1u;
    if (f >= frames) break;
    ticks[n++] = (uint16_t)f;
    need += threshold;
  }
  return n;
}

static void block_ticks(fm1_mfx_t *m, const fm1_seq_host_t *h, uint32_t frames,
                        fm1_midi_fx_ctx_t *ctx) {
  if (h->seq) {
    const fm1_seq_clock_t *c = &h->clock;
    ctx->bpm_x100 = c->bpm_x100;
    ctx->running = c->playing;
    if (c->inc > 0u && c->threshold > 0u) {
      m->n_ticks = grid_ticks(m->ticks, FM1_MFX_TICKS, c->accum % c->threshold, c->inc,
                              c->threshold, frames);
    } else {
      /* Off the grid: the ticks the block serviced, at its first frame. */
      fm1_seq_clock_t now;
      uint64_t k;
      fm1_seq_get_clock(h->seq, &now);
      k = c->playing && now.master_tick > c->master_tick ? now.master_tick - c->master_tick : 0u;
      if (k > FM1_MFX_TICKS) k = FM1_MFX_TICKS;
      for (m->n_ticks = 0; m->n_ticks < (uint32_t)k; ++m->n_ticks) m->ticks[m->n_ticks] = 0;
    }
  } else {
    const uint64_t inc = (uint64_t)m->bpm_x100 * FM1_MIDI_FX_PPQN;
    const uint64_t threshold = (uint64_t)m->rate * TPS_DIV;
    ctx->bpm_x100 = m->bpm_x100;
    ctx->running = 0;
    m->n_ticks = grid_ticks(m->ticks, FM1_MFX_TICKS, m->accum, inc, threshold, frames);
    m->accum = (m->accum + (uint64_t)frames * inc) % threshold;
  }
  ctx->ticks = m->ticks;
  ctx->n_ticks = m->n_ticks;
  ctx->frames = frames;
  ctx->key_root = m->key_root;
  ctx->key_scale = m->key_scale;
  m->running = ctx->running;
}

/* The chain event k of the buffer goes through, or -1. */
static int chain_for(const fm1_seq_host_t *h, uint32_t k, int single) {
  const uint8_t d = fm1_seq_host_dest(h, k);
  if (d & 0x80u) return -1;              /* MIDI, or nowhere */
  if (single) return 0;
  return d < FM1_MFX_CHAINS ? (int)d : -1;
}

/* The block's transport as effect input: RESET at each Start, FLUSH at
 * each Stop, at its frame. */
static int transport_kind(uint8_t kind) {
  return kind == FM1_SEQ_EV_START ? FM1_MIDI_EV_RESET
                                  : kind == FM1_SEQ_EV_STOP ? FM1_MIDI_EV_FLUSH : 0;
}

/* Chain c's input for the block in m->a: the note-offs owed from the last
 * block and its queued live notes at frame 0, then the buffer's transport
 * and the notes for its sound, at their frames. Marks the notes it takes. */
static uint32_t chain_input(fm1_mfx_t *m, fm1_seq_host_t *h, unsigned c, uint32_t frames,
                            int single) {
  fm1_mfx_chain_t *ch = &m->chain[c];
  uint32_t n = 0, k, key;
  for (key = 0; key < 128u; ++key) {
    if (ch->owed[key >> 3] & (1u << (key & 7u))) put(m->a, &n, 0, FM1_MIDI_EV_NOTE_OFF, (uint8_t)key, 0);
  }
  memset(ch->owed, 0, sizeof(ch->owed));
  for (k = 0; k < ch->n_live; ++k) m->a[n++] = ch->live[k];   /* n <= 128 + 64 here */
  ch->n_live = 0;
  for (k = 0; k < h->n; ++k) {
    fm1_seq_ev_t *e = &h->ev[k];
    const uint16_t f = (uint16_t)(e->frame < frames ? e->frame : frames);
    const int t = transport_kind(e->kind);
    int on;
    if (t) {
      if (n < FM1_MFX_IN) put(m->a, &n, f, (uint8_t)t, 0, 0);
      continue;
    }
    if (e->kind != FM1_SEQ_EV_NOTE_ON && e->kind != FM1_SEQ_EV_NOTE_OFF) continue;
    if (chain_for(h, k, single) != (int)c || e->a > 127u) continue;
    on = e->kind == FM1_SEQ_EV_NOTE_ON && e->b > 0;
    if (on) {
      if (n >= FM1_MFX_IN || ch->held[e->a] == 255u) {   /* to the sound itself */
        ++m->stats.direct;
        continue;
      }
      ++ch->held[e->a];
      put(m->a, &n, f, FM1_MIDI_EV_NOTE_ON, e->a, e->b);
    } else {
      if (!ch->held[e->a]) continue;      /* its note-on went to the sound */
      --ch->held[e->a];
      if (n < FM1_MFX_IN) {
        put(m->a, &n, f, FM1_MIDI_EV_NOTE_OFF, e->a, 0);
      } else {
        ch->owed[e->a >> 3] |= (uint8_t)(1u << (e->a & 7u));
        ++m->stats.deferred_offs;
      }
    }
    e->kind |= FM1_MFX_TAKEN;
    ++m->stats.notes_in;
  }
  return n;
}

/* An effect's notes, with the block's transport put back in front of each
 * frame's notes, for the next effect: from m->b (n notes) into m->a. */
static uint32_t with_transport(fm1_mfx_t *m, const fm1_seq_host_t *h, uint32_t frames, uint32_t n) {
  uint32_t i = 0, k = 0, out = 0;
  for (;;) {
    /* the next transport event in the buffer */
    while (k < h->n && !transport_kind((uint8_t)(h->ev[k].kind & ~FM1_MFX_TAKEN))) ++k;
    if (k < h->n) {
      const uint16_t f = (uint16_t)(h->ev[k].frame < frames ? h->ev[k].frame : frames);
      if (i >= n || f <= m->b[i].frame) {
        if (out < FM1_MFX_IN) {
          put(m->a, &out, f, (uint8_t)transport_kind(h->ev[k].kind), 0, 0);
        }
        ++k;
        continue;
      }
    }
    if (i >= n) break;
    if (out < FM1_MFX_IN) m->a[out++] = m->b[i];
    ++i;
  }
  return out;
}

void fm1_mfx_block(fm1_mfx_t *m, fm1_seq_host_t *h, uint32_t frames, int single) {
  fm1_midi_fx_ctx_t ctx;
  unsigned c, s;
  memset(&ctx, 0, sizeof(ctx));
  block_ticks(m, h, frames, &ctx);
  for (c = 0; c < FM1_MFX_CHAINS; ++c) {
    fm1_mfx_chain_t *ch = &m->chain[c];
    uint32_t n, i;
    ch->n_out = 0;
    if (!fm1_mfx_active(m, c)) continue;
    ++m->stats.blocks;
    m->stats.ticks += m->n_ticks;
    n = chain_input(m, h, c, frames, single);
    for (s = 0; s < FM1_MFX_SLOTS; ++s) {
      fm1_mfx_slot_t *sl = &ch->slot[s];
      uint32_t got;
      if (!sl->fx || !sl->on) continue;   /* bypassed: everything passes */
      got = sl->fx->process(sl->self, m->a, n, &ctx, m->b, FM1_MFX_OUT);
      if (got > FM1_MFX_OUT) got = FM1_MFX_OUT;
      n = with_transport(m, h, frames, got);
    }
    for (i = 0; i < n; ++i) {             /* the notes, to the sound */
      const fm1_midi_ev_t *e = &m->a[i];
      if (e->kind != FM1_MIDI_EV_NOTE_ON && e->kind != FM1_MIDI_EV_NOTE_OFF) continue;
      if (ch->n_out >= FM1_MFX_OUT) {
        ++m->stats.dropped;
        continue;
      }
      ch->out[ch->n_out++] = *e;
      ++m->stats.notes_out;
    }
  }
}

const fm1_midi_ev_t *fm1_mfx_output(const fm1_mfx_t *m, unsigned c, uint32_t *n) {
  if (c >= FM1_MFX_CHAINS) {
    if (n) *n = 0;
    return NULL;
  }
  if (n) *n = m->chain[c].n_out;
  return m->chain[c].out;
}
