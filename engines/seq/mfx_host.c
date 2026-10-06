/* mfx_host.c -- MIDI effects on the host bridge (fm1_mfx_host.h): the
 * chains, their clock, the live notes they take and the block they run.
 * C99, no heap, no stdio, no libm. MIT licence. */
#include "fm1_mfx_host.h"

#include <string.h>

#define TPS_DIV 6000u                 /* bpm_x100 x 96 per (rate x 6000): ticks a frame */

/* The scales the stage takes are the sequencer's (its `key` verb). */
typedef char key_scales_match[FM1_KEY_SCALES == FM1_SEQ_KEY_SCALES ? 1 : -1];

#define SEQ_ON(vel) FM1_MIDI_EV_B(vel, FM1_MIDI_SRC_SEQ)   /* a sequencer note's b */

/* ---- set-up ------------------------------------------------------------------ */

void fm1_mfx_init(fm1_mfx_t *m, uint32_t rate) {
  memset(m, 0, sizeof(*m));
  m->rate = rate ? rate : 1u;
  m->bpm_x100 = 12000u;
  m->key_root = 0;
  m->key_scale = FM1_KEY_MAJOR;
  m->swing = 50u;
}

void fm1_mfx_set_swing(fm1_mfx_t *m, unsigned pct) {
  m->swing = (uint8_t)(pct < 50u ? 50u : pct > 80u ? 80u : pct);
}

void fm1_mfx_set_tempo(fm1_mfx_t *m, uint32_t bpm_x100) {
  if (bpm_x100 < FM1_SEQ_BPM_X100_MIN) bpm_x100 = FM1_SEQ_BPM_X100_MIN;
  if (bpm_x100 > FM1_SEQ_BPM_X100_MAX) bpm_x100 = FM1_SEQ_BPM_X100_MAX;
  m->bpm_x100 = bpm_x100;
}

void fm1_mfx_set_key(fm1_mfx_t *m, unsigned root, unsigned scale) {
  m->key_root = (uint8_t)(root % 12u);
  m->key_scale = (uint8_t)(scale < FM1_KEY_SCALES ? scale : FM1_KEY_MAJOR);
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
  ctx->swing = m->swing;
}

/* Now, between blocks: m->a[0..n) into the effects of chain c that are on,
 * from slot `first`, each given the one before's output; each of them in
 * slots [kind_from, kind_to) first gets `kind` (FLUSH or PANIC; 0: none) at
 * frame 0, ahead of what it is given. The note-offs that come out of the
 * last go to the sink. (Only note-offs: an effect given note-offs and a
 * flush has no note to start.) */
static void run_quiet(fm1_mfx_t *m, unsigned c, unsigned first, uint32_t n, uint8_t kind,
                      unsigned kind_from, unsigned kind_to, const fm1_mfx_sink_t *sink) {
  fm1_mfx_chain_t *ch = &m->chain[c];
  fm1_midi_fx_ctx_t ctx;
  uint32_t i;
  unsigned s;
  int started = 0;
  quiet_ctx(m, &ctx);
  for (s = first; s < FM1_MFX_SLOTS; ++s) {
    fm1_mfx_slot_t *sl = &ch->slot[s];
    if (!sl->fx || !sl->on) continue;
    if (kind && s >= kind_from && s < kind_to) {   /* the flush, ahead of what came out before */
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
static void forget(fm1_mfx_chain_t *ch) {
  memset(ch->held_live, 0, sizeof(ch->held_live));
  memset(ch->held_seq, 0, sizeof(ch->held_seq));
  memset(ch->owed, 0, sizeof(ch->owed));
  memset(ch->owed_live, 0, sizeof(ch->owed_live));
  ch->n_live = 0;
}

static void forget_if_idle(fm1_mfx_t *m, unsigned c) {
  if (!fm1_mfx_active(m, c)) forget(&m->chain[c]);
}

void fm1_mfx_flush(fm1_mfx_t *m, unsigned c, int panic, const fm1_mfx_sink_t *sink) {
  fm1_mfx_chain_t *ch = chain_of(m, c);
  if (!ch) return;
  run_quiet(m, c, 0, 0, panic ? FM1_MIDI_EV_PANIC : FM1_MIDI_EV_FLUSH, 0, FM1_MFX_SLOTS, sink);
  if (panic) forget(ch);
}

/* Slot s of chain c ends its notes and forgets its keys, as it is bypassed,
 * replaced or removed; the effects after it hear its note-offs. */
static void retire(fm1_mfx_t *m, unsigned c, unsigned s, const fm1_mfx_sink_t *sink) {
  const fm1_mfx_slot_t *sl = &m->chain[c].slot[s];
  if (sl->fx && sl->on) run_quiet(m, c, s, 0, FM1_MIDI_EV_PANIC, s, s + 1u, sink);
}

static int key_bit(const uint8_t *bits, unsigned key) { return (bits[key >> 3] >> (key & 7u)) & 1u; }

/* Slot s of chain c, bypassed or empty now, is about to be switched on (or
 * filled with an effect that is on). While other effects of the chain are
 * on, every note-off must still follow its note-on:
 *   - the effects before s end what they sound (FLUSH: their keys stay),
 *     through the chain as it is, since their note-offs would reach s, which
 *     never heard the note-ons;
 *   - when s is to be the first effect on, the chain's keys reach s from now
 *     on, and s holds none of them: the effects after it hear each key the
 *     chain took let go (a latched arp keeps playing them, as a let-go key
 *     does), and the chain forgets them, so their note-offs go to the sound.
 *     A queued live note-on is dropped with them. */
static void before_on(fm1_mfx_t *m, unsigned c, unsigned s, const fm1_mfx_sink_t *sink) {
  fm1_mfx_chain_t *ch = &m->chain[c];
  unsigned k, first = FM1_MFX_SLOTS;
  uint32_t n = 0, i;
  for (k = 0; k < FM1_MFX_SLOTS; ++k) {
    if (ch->slot[k].fx && ch->slot[k].on) {
      first = k;
      break;
    }
  }
  if (first == FM1_MFX_SLOTS) return;              /* nothing else on: nothing sounds */
  if (first < s) {
    run_quiet(m, c, 0, 0, FM1_MIDI_EV_FLUSH, 0, s, sink);
    return;
  }
  for (k = 0; k < 128u; ++k) {                     /* every key the effects may hold, */
    int live = ch->held_live[k] || key_bit(ch->owed_live, k);   /* from either origin */
    for (i = 0; !live && i < ch->n_live; ++i) live = ch->live[i].a == k;
    if (live) put(m->a, &n, 0, FM1_MIDI_EV_NOTE_OFF, (uint8_t)k, 0);
    if (ch->held_seq[k] || key_bit(ch->owed, k)) put(m->a, &n, 0, FM1_MIDI_EV_NOTE_OFF, (uint8_t)k, SEQ_ON(0));
  }
  if (n) run_quiet(m, c, 0, n, 0, 0, 0, sink);
  forget(ch);
}

int fm1_mfx_set(fm1_mfx_t *m, unsigned c, unsigned s, const fm1_midi_fx_t *fx, void *self, int on,
                const fm1_mfx_sink_t *sink) {
  fm1_mfx_slot_t *sl;
  if (c >= FM1_MFX_CHAINS || s >= FM1_MFX_SLOTS) return 0;
  if (fx && (fx->engine.kind != FM1_KIND_MIDI_FX || !fx->process || !self)) return 0;
  retire(m, c, s, sink);
  sl = &m->chain[c].slot[s];
  sl->on = 0;
  forget_if_idle(m, c);
  if (fx && on) before_on(m, c, s, sink);
  sl->fx = fx;
  sl->self = fx ? self : NULL;
  sl->on = fx && on ? 1u : 0u;
  return 1;
}

int fm1_mfx_set_on(fm1_mfx_t *m, unsigned c, unsigned s, int on, const fm1_mfx_sink_t *sink) {
  fm1_mfx_slot_t *sl;
  if (c >= FM1_MFX_CHAINS || s >= FM1_MFX_SLOTS || !m->chain[c].slot[s].fx) return 0;
  sl = &m->chain[c].slot[s];
  if (!on == !sl->on) return 1;
  if (on) {
    before_on(m, c, s, sink);
  } else {
    retire(m, c, s, sink);
  }
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
    if (!fm1_mfx_active(m, c) || ch->n_live >= FM1_MFX_LIVE || ch->held_live[key] == 255u) {
      if (fm1_mfx_active(m, c)) ++m->stats.direct;
      return 0;
    }
    ++ch->held_live[key];
  } else {
    if (!ch->held_live[key]) return 0;     /* not the chain's: the host's to end */
    --ch->held_live[key];
    if (ch->n_live >= FM1_MFX_LIVE) {      /* no room: next block, after the queue */
      ch->owed_live[key >> 3] |= (uint8_t)(1u << (key & 7u));
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
    /* The block's first tick is the one the sequencer services next: its
     * place from Start, on the grid or off it. */
    ctx->tick_pos = c->playing ? c->master_tick : 0u;
    fm1_seq_get_key(h->seq, &m->key_root, &m->key_scale);   /* the set's key */
    fm1_mfx_set_swing(m, fm1_seq_get_swing(h->seq));          /* and its swing */
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
  ctx->swing = m->swing;
  m->running = ctx->running;
}

/* The chain event k of the buffer goes through, or -1. */
static int chain_for(const fm1_seq_host_t *h, uint32_t k, int single) {
  const uint8_t d = fm1_seq_host_dest(h, k);
  if (d & 0x80u) return -1;              /* MIDI, or nowhere */
  if (single) return 0;
  return d < FM1_MFX_CHAINS ? (int)d : -1;
}

/* The block's transport as effect input: RESET at each Start, STOP at
 * each Stop, at its frame. */
static int transport_kind(uint8_t kind) {
  return kind == FM1_SEQ_EV_START ? FM1_MIDI_EV_RESET
                                  : kind == FM1_SEQ_EV_STOP ? FM1_MIDI_EV_STOP : 0;
}

/* A transport event into buf at frame f. A Stop is STOP, and FLUSH after it
 * when the clock is off the grid as the block begins stopped (Movy's compat
 * mode: no tick comes while stopped, so none would end a note sounding).
 * An external clock's Stop is not that: once stopped the sequencer no
 * longer follows, and its clock runs on at the tempo. */
static void put_transport(const fm1_seq_host_t *h, fm1_midi_ev_t *buf, uint32_t *n, uint16_t f,
                          int kind) {
  if (*n < FM1_MFX_IN) put(buf, n, f, (uint8_t)kind, 0, 0);
  if (kind == FM1_MIDI_EV_STOP && h->clock.inc == 0u && *n < FM1_MFX_IN) {
    put(buf, n, f, FM1_MIDI_EV_FLUSH, 0, 0);
  }
}

/* The owed note-offs, at frame 0, while they fit; the rest stay owed. `b`:
 * their origin's mark. */
static void owed_offs(fm1_midi_ev_t *buf, uint32_t *n, uint8_t *owed, uint16_t b) {
  uint32_t key;
  for (key = 0; key < 128u && *n < FM1_MFX_IN; ++key) {
    if (!key_bit(owed, key)) continue;
    put(buf, n, 0, FM1_MIDI_EV_NOTE_OFF, (uint8_t)key, b);
    owed[key >> 3] &= (uint8_t)~(1u << (key & 7u));
  }
}

/* A trig at frame f, after that frame's notes: STEP, once a frame. */
static void step_at(fm1_mfx_t *m, uint32_t *n, int32_t *pending) {
  if (*pending < 0) return;
  if (*n < FM1_MFX_IN) put(m->a, n, (uint16_t)*pending, FM1_MIDI_EV_STEP, 0, 0);
  if (m->n_steps < FM1_MFX_TICKS) m->steps[m->n_steps++] = (uint16_t)*pending;
  *pending = -1;
}

/* Chain c's input for the block in m->a: at frame 0, the sequencer's
 * note-offs owed from the last block, its queued live notes and the live
 * note-offs that came after them with the queue full; then the buffer's
 * transport and the notes for its sound, at their frames, with a STEP
 * after each frame's note-ons (m->steps keeps their frames for the effects
 * after the first). Marks the notes it takes. */
static uint32_t chain_input(fm1_mfx_t *m, fm1_seq_host_t *h, unsigned c, uint32_t frames,
                            int single) {
  fm1_mfx_chain_t *ch = &m->chain[c];
  uint32_t n = 0, k;
  int32_t pending = -1;
  owed_offs(m->a, &n, ch->owed, SEQ_ON(0));                   /* at most 128 */
  for (k = 0; k < ch->n_live; ++k) m->a[n++] = ch->live[k];   /* 64 more */
  ch->n_live = 0;
  owed_offs(m->a, &n, ch->owed_live, 0);
  m->n_steps = 0;
  for (k = 0; k < h->n; ++k) {
    fm1_seq_ev_t *e = &h->ev[k];
    const uint16_t f = (uint16_t)(e->frame < frames ? e->frame : frames);
    const int t = transport_kind(e->kind);
    int on;
    if (t) {
      if (pending >= 0 && f > pending) step_at(m, &n, &pending);
      put_transport(h, m->a, &n, f, t);
      continue;
    }
    if (e->kind != FM1_SEQ_EV_NOTE_ON && e->kind != FM1_SEQ_EV_NOTE_OFF) continue;
    if (chain_for(h, k, single) != (int)c || e->a > 127u) continue;
    if (pending >= 0 && f > pending) step_at(m, &n, &pending);
    on = e->kind == FM1_SEQ_EV_NOTE_ON && e->b > 0;
    if (on) {
      if (n >= FM1_MFX_IN - 1u || ch->held_seq[e->a] == 255u) {   /* to the sound itself */
        ++m->stats.direct;
        continue;
      }
      ++ch->held_seq[e->a];
      put(m->a, &n, f, FM1_MIDI_EV_NOTE_ON, e->a, SEQ_ON(e->b > 127u ? 127u : e->b));
      pending = f;
    } else {
      if (!ch->held_seq[e->a]) continue;  /* its note-on went to the sound */
      --ch->held_seq[e->a];
      if (n < FM1_MFX_IN) {
        put(m->a, &n, f, FM1_MIDI_EV_NOTE_OFF, e->a, SEQ_ON(0));
      } else {
        ch->owed[e->a >> 3] |= (uint8_t)(1u << (e->a & 7u));
        ++m->stats.deferred_offs;
      }
    }
    e->kind |= FM1_MFX_TAKEN;
    ++m->stats.notes_in;
  }
  step_at(m, &n, &pending);
  return n;
}

/* An effect's notes, for the next effect, from m->b (n notes) into m->a,
 * with the block's transport put back in front of each frame's notes and
 * the chain's trigs after them. */
static uint32_t with_transport(fm1_mfx_t *m, const fm1_seq_host_t *h, uint32_t frames, uint32_t n) {
  uint32_t i = 0, k = 0, q = 0, out = 0;
  for (;;) {
    uint32_t tf = 0xFFFFFFFFu, nf = i < n ? m->b[i].frame : 0xFFFFFFFFu;
    const uint32_t sf = q < m->n_steps ? m->steps[q] : 0xFFFFFFFFu;
    /* the next transport event in the buffer */
    while (k < h->n && !transport_kind((uint8_t)(h->ev[k].kind & ~FM1_MFX_TAKEN))) ++k;
    if (k < h->n) tf = h->ev[k].frame < frames ? h->ev[k].frame : frames;
    if (tf == 0xFFFFFFFFu && nf == 0xFFFFFFFFu && sf == 0xFFFFFFFFu) break;
    if (tf <= nf && tf <= sf) {           /* at one frame: transport, notes, trigs */
      put_transport(h, m->a, &out, (uint16_t)tf, transport_kind((uint8_t)(h->ev[k].kind & ~FM1_MFX_TAKEN)));
      ++k;
    } else if (nf <= sf) {
      if (out < FM1_MFX_IN) m->a[out++] = m->b[i];
      ++i;
    } else {
      if (out < FM1_MFX_IN) put(m->a, &out, (uint16_t)sf, FM1_MIDI_EV_STEP, 0, 0);
      ++q;
    }
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
    for (i = 0; i < n; ++i) {             /* the notes, to the sound: the bare velocity */
      const fm1_midi_ev_t *e = &m->a[i];
      if (e->kind != FM1_MIDI_EV_NOTE_ON && e->kind != FM1_MIDI_EV_NOTE_OFF) continue;
      if (ch->n_out >= FM1_MFX_OUT) {
        ++m->stats.dropped;
        continue;
      }
      ch->out[ch->n_out] = *e;
      ch->out[ch->n_out++].b = (uint16_t)FM1_MIDI_EV_VEL(e->b);
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
