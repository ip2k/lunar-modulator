/* seq_host.c -- the sequencer's per-block host contract (fm1_seq_host.h):
 * commands into a shared event buffer, advance, and the split renders that
 * hand engine-routed notes and locks to a sound engine at their own frame.
 * Extracted from fm1-render (engines/host/render.cc) without a change in
 * behaviour; lane labels resolve to parameter uids (engine API v2) when they
 * are set, and locks on NOLOCK parameters are refused. Dispatch can run a
 * control-rate hook (the modulation tick, docs/16 MG1) at its own frames,
 * splitting a render only where a tick writes, and MIDI effects in front of
 * the sounds (fm1_mfx_host.h), whose output joins the block's events. C99,
 * no heap, no stdio. MIT licence. */
#include "fm1_seq_host.h"

#include <string.h>

#include "fm1_mfx_host.h"

static char lower(char c) { return c >= 'A' && c <= 'Z' ? (char)(c - 'A' + 'a') : c; }

/* Whether a lane label's name (`label`, the text after its last ':') names
 * the parameter called `name`: strcasecmp in the C locale, which is what
 * fm1-render had, except that '_' in the label stands for a space in the
 * name. A label is one token of a verb script or a `movy1` set, so it
 * cannot hold a space: `synth:Env_Pitch` names Env Pitch (docs/15 S8). */
static int same_name(const char *name, const char *label) {
  for (; *name && *label; ++name, ++label) {
    if (lower(*name) != lower(*label) && !(*name == ' ' && *label == '_')) return 0;
  }
  return *name == *label;
}

/* What a lane label names: the part after its last ':' ("synth:Timbre"). */
static const char *label_name(const char *label) {
  const char *name = label;
  const char *p;
  for (p = label; *p; ++p) {
    if (*p == ':') name = p + 1;
  }
  return name;
}

void fm1_seq_host_init(fm1_seq_host_t *h, fm1_seq_t *seq, fm1_seq_ev_t *ev, uint32_t cap) {
  h->seq = seq;
  h->ev = ev;
  h->cap = ev ? cap : 0u;
  h->n = 0;
  h->max_n = 0;
  h->notes_to_engine = 0;
  h->locks_to_engine = 0;
  h->locks_refused = 0;
  h->splits = 0;
  h->engine = NULL;
  memset(h->lane_uid, 0, sizeof(h->lane_uid));
  h->cmd_n = 0;
  memset(h->dest, FM1_SEQ_HOST_NO_DEST, sizeof(h->dest));
  memset(&h->clock, 0, sizeof(h->clock));
  h->mfx = NULL;
}

/* Every lane of track t, from the core's labels, against the bound engine.
 * Out-of-range tracks read as unlabelled (fm1_seq_lane_label gives ""). */
static void resolve_track(fm1_seq_host_t *h, unsigned t) {
  unsigned lane;
  for (lane = 0; lane < FM1_SEQ_LANES; ++lane) {
    h->lane_uid[t][lane] =
        h->seq ? fm1_seq_lane_uid(h->engine, fm1_seq_lane_label(h->seq, (uint8_t)t, (uint8_t)lane))
               : 0u;
  }
}

static void resolve_all(fm1_seq_host_t *h) {
  unsigned t;
  for (t = 0; t < FM1_SEQ_MAX_TRACKS; ++t) resolve_track(h, t);
}

void fm1_seq_host_bind(fm1_seq_host_t *h, const fm1_engine_t *e) {
  h->engine = e;
  resolve_all(h);
}

int fm1_seq_host_import(fm1_seq_host_t *h, const char *txt, size_t len) {
  const int ok = fm1_seq_import_movy1(h->seq, txt, len);
  resolve_all(h);
  return ok;
}

/* The uid a lane's locks go to on engine e: the stored one while its
 * parameter on e has the name the label gives, else the label resolved on e
 * afresh. Against the bound engine this is fm1_seq_host_lane_uid; another
 * sound unit's engine (dispatch_slots) gets the same rule. */
static uint16_t lane_uid_on(const fm1_seq_host_t *h, const fm1_engine_t *e, uint8_t track,
                            uint8_t lane) {
  const char *label;
  uint16_t uid;
  int i;
  if (track >= FM1_SEQ_MAX_TRACKS || lane >= FM1_SEQ_LANES || !h->seq) return 0;
  /* A lane the core has released since (aclr, a deleted clip...) is
   * unlabelled now. */
  label = fm1_seq_lane_label(h->seq, track, lane);
  if (!label[0]) return 0;
  /* The stored uid, while its parameter still has the name the label gives:
   * every `alabel` and import through the bridge keeps it so. A label set on
   * the core directly, past the bridge, resolves afresh here instead, so its
   * locks still reach the parameter it names. Engine names are unique
   * without case (tests/test_engine_params.py), so the two agree. */
  uid = h->lane_uid[track][lane];
  i = fm1_param_index(e, uid);
  if (i >= 0 && same_name(e->params[i].name, label_name(label))) return uid;
  return fm1_seq_lane_uid(e, label);
}

uint16_t fm1_seq_host_lane_uid(const fm1_seq_host_t *h, uint8_t track, uint8_t lane) {
  return lane_uid_on(h, h->engine, track, lane);
}

static int is_blank(char c) { return c == ' ' || c == '\t'; }

static unsigned hex_digit(char c) {
  return c >= '0' && c <= '9' ? (unsigned)(c - '0')
         : c >= 'a' && c <= 'f' ? (unsigned)(c - 'a' + 10)
         : c >= 'A' && c <= 'F' ? (unsigned)(c - 'A' + 10) : 16u;
}

unsigned fm1_seq_realtime_status(const char *ops, size_t len) {
  unsigned v = 0;
  size_t i;
  int k;
  if (len < 3 || ops[0] != 'r' || ops[1] != 't' || !is_blank(ops[2])) return 0;
  i = 3;
  while (i < len && is_blank(ops[i])) ++i;
  for (k = 0; k < 2; ++k, ++i) {
    const unsigned d = i < len ? hex_digit(ops[i]) : 16u;
    if (d > 15) return 0;
    v = v * 16u + d;
  }
  while (i < len && is_blank(ops[i])) ++i;
  if (i < len) return 0;
  return v == 0xF8 || v == 0xFA || v == 0xFB || v == 0xFC ? v : 0;
}

uint32_t fm1_seq_apply_line(fm1_seq_t *s, const char *ops, size_t len, fm1_seq_ev_t *out,
                            uint32_t cap) {
  const unsigned rt = fm1_seq_realtime_status(ops, len);
  if (rt) return fm1_seq_realtime_in(s, 0, (uint8_t)rt, out, cap);
  return fm1_seq_apply_text(s, ops, len, out, cap);
}

uint32_t fm1_seq_host_room(const fm1_seq_host_t *h) {
  return h->n < h->cap ? h->cap - h->n : 0u;
}

/* The free part of the buffer; NULL when there is no buffer (the core then
 * counts every event as dropped). */
static fm1_seq_ev_t *tail(const fm1_seq_host_t *h) {
  return h->ev ? h->ev + h->n : NULL;
}

uint32_t fm1_seq_cmd_max_events(const fm1_seq_limits_t *lim) {
  return (uint32_t)lim->gates + 8u * (uint32_t)lim->tracks + 1u;
}

/* Whether a line may label a lane: it holds "alabel" anywhere. Rare (lane
 * set-up), and re-resolving an unchanged label is harmless, so a crude test
 * is enough; a resent batch the core suppresses resolves to what it had. */
static int mentions_alabel(const char *ops, size_t len) {
  static const char w[] = "alabel";
  size_t i, k;
  for (i = 0; i + (sizeof(w) - 1u) <= len; ++i) {
    for (k = 0; k < sizeof(w) - 1u && ops[i + k] == w[k]; ++k) {
    }
    if (k == sizeof(w) - 1u) return 1;
  }
  return 0;
}

uint32_t fm1_seq_host_line(fm1_seq_host_t *h, const char *ops, size_t len) {
  const uint32_t k = fm1_seq_apply_line(h->seq, ops, len, tail(h), fm1_seq_host_room(h));
  h->n += k;
  if (mentions_alabel(ops, len)) resolve_all(h);
  return k;
}

uint32_t fm1_seq_host_cmd(fm1_seq_host_t *h, const fm1_seq_cmd_t *c) {
  const uint32_t k = fm1_seq_apply(h->seq, c, tail(h), fm1_seq_host_room(h));
  h->n += k;
  if (c->verb == FM1_SEQ_V_ALABEL && (c->valid & 1u) && c->arg[0] >= 0 &&
      c->arg[0] < (int64_t)FM1_SEQ_MAX_TRACKS) {
    resolve_track(h, (unsigned)c->arg[0]);
  }
  return k;
}

uint32_t fm1_seq_host_realtime(fm1_seq_host_t *h, uint8_t status) {
  const uint32_t k = fm1_seq_realtime_in(h->seq, 0, status, tail(h), fm1_seq_host_room(h));
  h->n += k;
  return k;
}

void fm1_seq_host_note_in(fm1_seq_host_t *h, uint8_t track, uint8_t pitch, uint8_t vel) {
  fm1_seq_note_in(h->seq, 0, track, pitch, vel);
}

uint32_t fm1_seq_host_advance(fm1_seq_host_t *h, uint32_t frames) {
  h->cmd_n = h->n;                      /* the inputs' events end here */
  fm1_seq_get_clock(h->seq, &h->clock); /* after the inputs: a `play` resets it */
  h->n += fm1_seq_advance(h->seq, frames, tail(h), fm1_seq_host_room(h));
  if (h->n > h->max_n) h->max_n = h->n;
  return h->n;
}

/* The index of the parameter a lock reaches on engine e, or -1: its lane
 * names nothing there (or nothing any more), or the parameter is NOLOCK,
 * which is counted. */
static int lock_target(fm1_seq_host_t *h, const fm1_engine_t *e, const fm1_seq_ev_t *ev) {
  const int i = fm1_param_index(e, lane_uid_on(h, e, ev->track, ev->a));
  if (i < 0) return -1;
  if (!fm1_param_lockable(&e->params[i])) {
    ++h->locks_refused;
    return -1;
  }
  return i;
}

/* A track's route as a destination: its engine slot, or 0x80 | its MIDI
 * channel. */
static uint8_t dest_of(const fm1_seq_track_info_t *ti) {
  return ti->route_kind == FM1_SEQ_ROUTE_ENGINE ? ti->route_index
                                                : (uint8_t)(0x80u | ti->route_index);
}

/* Where event k goes: the track's route now, except that a note-off from
 * the block's inputs goes where the track's notes went at the last
 * dispatch (Rerouting, fm1_seq_host.h). 0xFF: nowhere (no such track). */
static uint8_t dest_of_event(const fm1_seq_host_t *h, uint32_t k) {
  const fm1_seq_ev_t *e = &h->ev[k];
  fm1_seq_track_info_t ti;
  if (!fm1_seq_get_track(h->seq, e->track, &ti)) return FM1_SEQ_HOST_NO_DEST;
  if (e->kind == FM1_SEQ_EV_NOTE_OFF && k < h->cmd_n && e->track < FM1_SEQ_MAX_TRACKS &&
      h->dest[e->track] != FM1_SEQ_HOST_NO_DEST) {
    return h->dest[e->track];
  }
  return dest_of(&ti);
}

uint8_t fm1_seq_host_dest(const fm1_seq_host_t *h, uint32_t k) {
  return h->seq && k < h->n ? dest_of_event(h, k) : FM1_SEQ_HOST_NO_DEST;
}

/* ---- the block's events in dispatch order ----------------------------------
 * The buffer's, and with MIDI effects each chain's output, merged by frame:
 * at one frame, the buffer's events but its note-ons (offs, locks, the
 * transport...), the chains' note-offs, the buffer's note-ons, the chains'
 * note-ons; chains in order. Each source keeps its own order. */
typedef struct {
  const fm1_seq_ev_t *e;        /* the event, its kind without FM1_MFX_TAKEN */
  int32_t k;                    /* its index in the buffer, or -1 for a chain's */
  uint8_t dest;                 /* a chain's: the chain, as a slot */
  uint8_t taken;                /* a buffer note a chain took: no engine gets it */
} walk_ev_t;

typedef struct {
  const fm1_seq_host_t *h;
  uint32_t frames;
  uint32_t k;                   /* the buffer's next event */
  uint32_t j[FM1_MFX_CHAINS];   /* each chain's next output */
  fm1_seq_ev_t tmp;             /* the event handed out last */
} walk_t;

static void walk_init(walk_t *w, const fm1_seq_host_t *h, uint32_t frames) {
  memset(w, 0, sizeof(*w));
  w->h = h;
  w->frames = frames;
}

static uint32_t clamp_frame(uint32_t f, uint32_t frames) { return f < frames ? f : frames; }

/* A rank at one frame: 0 a buffer event but a note-on, 1 a chain's note-off,
 * 2 a buffer note-on, 3 a chain's note-on. */
static int walk_next(walk_t *w, walk_ev_t *out) {
  const fm1_seq_host_t *h = w->h;
  const fm1_mfx_t *m = h->mfx;
  uint32_t bf = 0xFFFFFFFFu;
  int br = 4, best = -1, bestr = 4;
  uint32_t bestf = 0xFFFFFFFFu;
  unsigned c;
  if (w->k < h->n) {
    const fm1_seq_ev_t *e = &h->ev[w->k];
    bf = clamp_frame(e->frame, w->frames);
    br = (e->kind & ~FM1_MFX_TAKEN) == FM1_SEQ_EV_NOTE_ON ? 2 : 0;
  }
  for (c = 0; m && c < FM1_MFX_CHAINS; ++c) {
    const fm1_mfx_chain_t *ch = &m->chain[c];
    if (w->j[c] < ch->n_out) {
      const fm1_midi_ev_t *x = &ch->out[w->j[c]];
      const uint32_t f = clamp_frame(x->frame, w->frames);
      const int r = x->kind == FM1_MIDI_EV_NOTE_ON ? 3 : 1;
      if (f < bestf || (f == bestf && r < bestr)) {
        best = (int)c;
        bestf = f;
        bestr = r;
      }
    }
  }
  if (best < 0 && w->k >= h->n) return 0;
  if (best < 0 || bf < bestf || (bf == bestf && br < bestr)) {
    const fm1_seq_ev_t *e = &h->ev[w->k];
    out->k = (int32_t)w->k++;
    out->taken = (e->kind & FM1_MFX_TAKEN) != 0;
    out->dest = 0;
    if (out->taken) {
      w->tmp = *e;
      w->tmp.kind = (uint8_t)(e->kind & ~FM1_MFX_TAKEN);
      out->e = &w->tmp;
    } else {
      out->e = e;
    }
    return 1;
  }
  {
    const fm1_midi_ev_t *x = &m->chain[best].out[w->j[best]++];
    w->tmp.tick = 0;
    w->tmp.frame = x->frame;
    w->tmp.kind = x->kind == FM1_MIDI_EV_NOTE_ON && x->b ? FM1_SEQ_EV_NOTE_ON : FM1_SEQ_EV_NOTE_OFF;
    w->tmp.track = (uint8_t)(FM1_MFX_TRACK + (unsigned)best);
    w->tmp.a = x->a;
    w->tmp.b = (fm1_seq_val_t)(w->tmp.kind == FM1_SEQ_EV_NOTE_ON ? x->b : 0u);
    out->e = &w->tmp;
    out->k = -1;
    out->dest = (uint8_t)best;
    out->taken = 0;
  }
  return 1;
}

/* Where a walked event goes: a chain's to its slot, a buffer event as
 * dest_of_event says; 0xFF for a note a chain took. */
static uint8_t walk_dest(const fm1_seq_host_t *h, const walk_ev_t *x) {
  if (x->taken) return FM1_SEQ_HOST_NO_DEST;
  return x->k < 0 ? x->dest : dest_of_event(h, (uint32_t)x->k);
}

/* The MIDI effects' share of a dispatch, before any render. */
static void mfx_begin(fm1_seq_host_t *h, uint32_t frames, int single) {
  if (h->mfx) fm1_mfx_block(h->mfx, h, frames, single);
}

/* After a dispatch: each track's route, for the next block's note-offs. */
static void dispatched(fm1_seq_host_t *h) {
  unsigned t;
  uint32_t k;
  for (k = 0; h->mfx && k < h->n; ++k) h->ev[k].kind &= (uint8_t)~FM1_MFX_TAKEN;
  for (t = 0; t < FM1_SEQ_MAX_TRACKS; ++t) {
    fm1_seq_track_info_t ti;
    h->dest[t] = h->seq && fm1_seq_get_track(h->seq, (uint8_t)t, &ti) ? dest_of(&ti)
                                                                      : FM1_SEQ_HOST_NO_DEST;
  }
  h->cmd_n = 0;
  h->n = 0;
}

/* One hook write into a sink: a bend, a per-voice offset or a parameter. */
static void apply_write(const fm1_seq_sink_t *sink, const fm1_seq_hook_write_t *w) {
  if (w->note) {
    if (sink->set_param_note) sink->set_param_note(sink->ctx, w->key, w->index, w->value);
  } else if (w->bend) {
    if (sink->pitch_bend) sink->pitch_bend(sink->ctx, w->value);
  } else if (sink->engine && w->index < sink->engine->n_params) {
    sink->set_param(sink->ctx, w->index, w->value);
  }
}

/* The hook's tick at frame tf: when it writes to the sink, the render up to
 * tf first, then the writes. Returns the next tick's frame. */
static uint32_t run_tick(fm1_seq_host_t *h, const fm1_seq_hook_t *hk, uint32_t tf, uint32_t *cur,
                         float *block, const fm1_seq_sink_t *sink) {
  const fm1_seq_hook_write_t *w = NULL;
  uint32_t next = tf, i;
  const uint32_t n = hk->tick(hk->ctx, tf, &w, &next);
  if (n && w && sink) {
    if (tf > *cur) {
      sink->render(sink->ctx, block + 2u * *cur, tf - *cur);
      if (*cur) ++h->splits;
      *cur = tf;
    }
    for (i = 0; i < n; ++i) {
      if (w[i].slot) continue;            /* another sound unit's: none here */
      apply_write(sink, &w[i]);
    }
  }
  return next > tf ? next : tf + 1u;   /* always forward */
}

/* After a note-on reached slot s's sink at its frame: the hook's writes for
 * that note (docs/16 MG9), at the same frame, so nothing renders between. */
static void note_on_writes(const fm1_seq_hook_t *hk, uint32_t f, unsigned s, uint8_t key,
                           const fm1_seq_sink_t *sink) {
  const fm1_seq_hook_write_t *w = NULL;
  uint32_t i, n;
  if (!hk || !hk->note_on) return;
  n = hk->note_on(hk->ctx, f, s, key, &w);
  for (i = 0; w && i < n; ++i) {
    if (w[i].slot == s) apply_write(sink, &w[i]);
  }
}

/* One sink's share of the block: the events of tracks routed to the engine
 * (any slot when `slot` is negative, else that slot only), with its render
 * split at their frames, and the hook's ticks (when there is one) at
 * theirs; the hook sees every event, whatever its route. A NULL sink
 * renders nothing. Leaves the buffer as it is. */
static void play_sink(fm1_seq_host_t *h, uint32_t frames, float *block, const fm1_seq_sink_t *sink,
                      int slot, const fm1_seq_hook_t *hk) {
  uint32_t cur = 0, tf = frames;
  if (hk) {
    uint32_t bpm = 0;
    int playing = 0;
    if (h->seq) {
      fm1_seq_info_t info;
      fm1_seq_get_info(h->seq, &info);
      bpm = info.bpm_x100;
      playing = info.playing;
    }
    tf = hk->begin(hk->ctx, frames, sink ? sink->engine : NULL, bpm, playing);
  }
  walk_t w;
  walk_ev_t x;
  walk_init(&w, h, frames);
  while (walk_next(&w, &x)) {
    const fm1_seq_ev_t *e = x.e;
    const uint32_t f = e->frame < frames ? e->frame : frames;
    int param = -1, to_engine = 0;
    if (sink && (e->kind == FM1_SEQ_EV_NOTE_ON || e->kind == FM1_SEQ_EV_NOTE_OFF ||
                 e->kind == FM1_SEQ_EV_LOCK)) {
      const uint8_t d = walk_dest(h, &x);
      to_engine = !(d & 0x80u) && (slot < 0 || d == (unsigned)slot);   /* not MIDI or nowhere */
    }
    if (hk) {
      /* Ticks before this frame; at this frame, before a note-on but after
       * note-offs and locks (M6). */
      while (tf < frames && (tf < f || (tf == f && e->kind == FM1_SEQ_EV_NOTE_ON))) {
        tf = run_tick(h, hk, tf, &cur, block, sink);
      }
      /* to_engine: 1 plus the slot the event plays (the one sink is 0). */
      hk->event(hk->ctx, f, e, to_engine ? 1 + (slot < 0 ? 0 : slot) : 0);
    }
    if (!to_engine) continue;
    if (e->kind == FM1_SEQ_EV_LOCK) {   /* resolved before any split */
      param = lock_target(h, sink->engine, e);
      if (param < 0) continue;
    }
    if (f > cur) {
      sink->render(sink->ctx, block + 2u * cur, f - cur);
      if (cur) ++h->splits;
      cur = f;
    }
    if (e->kind == FM1_SEQ_EV_NOTE_ON) {
      sink->note_on(sink->ctx, e->a, e->b);
      ++h->notes_to_engine;
      note_on_writes(hk, f, slot < 0 ? 0u : (unsigned)slot, e->a, sink);
    } else if (e->kind == FM1_SEQ_EV_NOTE_OFF) {
      sink->note_off(sink->ctx, e->a);
    } else {
      float v = fm1_seq_lock_value(&sink->engine->params[param], e->b);
      if (hk) v = hk->lock(hk->ctx, (uint16_t)param, v);
      sink->set_param(sink->ctx, (uint16_t)param, v);
      ++h->locks_to_engine;
    }
  }
  if (hk) {
    while (tf < frames) tf = run_tick(h, hk, tf, &cur, block, sink);
  }
  if (sink && cur < frames) {
    sink->render(sink->ctx, block + 2u * cur, frames - cur);
    if (cur) ++h->splits;
  }
}

void fm1_seq_host_dispatch(fm1_seq_host_t *h, uint32_t frames, float *block,
                           const fm1_seq_sink_t *sink) {
  fm1_seq_host_dispatch_ticks(h, frames, block, sink, NULL);
}

void fm1_seq_host_dispatch_ticks(fm1_seq_host_t *h, uint32_t frames, float *block,
                                 const fm1_seq_sink_t *sink, const fm1_seq_hook_t *hk) {
  if (sink && sink->engine != h->engine) fm1_seq_host_bind(h, sink->engine);
  mfx_begin(h, frames, 1);
  if (sink || hk) play_sink(h, frames, block, sink, -1, hk);
  dispatched(h);
}

void fm1_seq_host_dispatch_slots(fm1_seq_host_t *h, uint32_t frames, const fm1_seq_slot_t *slots,
                                 unsigned n) {
  fm1_seq_host_dispatch_slots_ticks(h, frames, slots, n, NULL);
}

/* Slot s's render up to frame f, counting a piece that starts inside the
 * block. */
static void slot_upto(fm1_seq_host_t *h, const fm1_seq_slot_t *sl, uint32_t *cur, uint32_t f) {
  if (f > *cur) {
    sl->sink->render(sl->sink->ctx, sl->block + 2u * *cur, f - *cur);
    if (*cur) ++h->splits;
    *cur = f;
  }
}

/* The hook's tick at frame tf over several slots: each write goes to the
 * slot it names, whose render runs up to tf first. */
static uint32_t run_tick_slots(fm1_seq_host_t *h, const fm1_seq_hook_t *hk, uint32_t tf,
                               uint32_t *cur, const fm1_seq_slot_t *slots, unsigned n) {
  const fm1_seq_hook_write_t *w = NULL;
  uint32_t next = tf, i;
  const uint32_t nw = hk->tick(hk->ctx, tf, &w, &next);
  for (i = 0; w && i < nw; ++i) {
    const unsigned s = w[i].slot;
    const fm1_seq_sink_t *sink = s < n ? slots[s].sink : NULL;
    if (!sink) continue;
    slot_upto(h, &slots[s], &cur[s], tf);
    apply_write(sink, &w[i]);
  }
  return next > tf ? next : tf + 1u;   /* always forward */
}

/* Every slot's share of the block in one pass, with the hook's ticks at
 * their frames: each slot sees its own events and the writes that name it
 * in exactly the order play_sink gives one sink (docs/16's M6 at one
 * frame), so its calls are the same; the slots' calls interleave, which no
 * sink can tell, as each renders its own block. */
static void play_slots_hook(fm1_seq_host_t *h, uint32_t frames, const fm1_seq_slot_t *slots,
                            unsigned n, const fm1_seq_hook_t *hk) {
  uint32_t cur[FM1_SEQ_HOST_HOOK_SLOTS];
  uint32_t tf, bpm = 0;
  unsigned s;
  int playing = 0;
  walk_t w;
  walk_ev_t x;
  if (n > FM1_SEQ_HOST_HOOK_SLOTS) n = FM1_SEQ_HOST_HOOK_SLOTS;
  for (s = 0; s < FM1_SEQ_HOST_HOOK_SLOTS; ++s) cur[s] = 0;
  if (h->seq) {
    fm1_seq_info_t info;
    fm1_seq_get_info(h->seq, &info);
    bpm = info.bpm_x100;
    playing = info.playing;
  }
  tf = hk->begin(hk->ctx, frames, n && slots[0].sink ? slots[0].sink->engine : NULL, bpm, playing);
  walk_init(&w, h, frames);
  while (walk_next(&w, &x)) {
    const fm1_seq_ev_t *e = x.e;
    const uint32_t f = e->frame < frames ? e->frame : frames;
    const fm1_seq_slot_t *sl = NULL;
    int param = -1;
    if (e->kind == FM1_SEQ_EV_NOTE_ON || e->kind == FM1_SEQ_EV_NOTE_OFF || e->kind == FM1_SEQ_EV_LOCK) {
      const uint8_t d = walk_dest(h, &x);
      if (!(d & 0x80u) && d < n && slots[d].sink) sl = &slots[d];
    }
    while (tf < frames && (tf < f || (tf == f && e->kind == FM1_SEQ_EV_NOTE_ON))) {
      tf = run_tick_slots(h, hk, tf, cur, slots, n);
    }
    hk->event(hk->ctx, f, e, sl ? 1 + (int)(sl - slots) : 0);
    if (!sl) continue;
    s = (unsigned)(sl - slots);
    if (e->kind == FM1_SEQ_EV_LOCK) {   /* resolved before any split */
      param = lock_target(h, sl->sink->engine, e);
      if (param < 0) continue;
    }
    slot_upto(h, sl, &cur[s], f);
    if (e->kind == FM1_SEQ_EV_NOTE_ON) {
      sl->sink->note_on(sl->sink->ctx, e->a, e->b);
      ++h->notes_to_engine;
      note_on_writes(hk, f, s, e->a, sl->sink);
    } else if (e->kind == FM1_SEQ_EV_NOTE_OFF) {
      sl->sink->note_off(sl->sink->ctx, e->a);
    } else {
      float v = fm1_seq_lock_value(&sl->sink->engine->params[param], e->b);
      if (hk->lock_slot) v = hk->lock_slot(hk->ctx, s, (uint16_t)param, v);
      else if (s == 0) v = hk->lock(hk->ctx, (uint16_t)param, v);
      sl->sink->set_param(sl->sink->ctx, (uint16_t)param, v);
      ++h->locks_to_engine;
    }
  }
  while (tf < frames) tf = run_tick_slots(h, hk, tf, cur, slots, n);
  for (s = 0; s < n; ++s) {
    if (slots[s].sink) slot_upto(h, &slots[s], &cur[s], frames);
  }
}

void fm1_seq_host_dispatch_slots_ticks(fm1_seq_host_t *h, uint32_t frames,
                                       const fm1_seq_slot_t *slots, unsigned n,
                                       const fm1_seq_hook_t *hook) {
  unsigned k;
  if (n && slots[0].sink && slots[0].sink->engine != h->engine) {
    fm1_seq_host_bind(h, slots[0].sink->engine);
  }
  mfx_begin(h, frames, 0);
  if (hook) {
    play_slots_hook(h, frames, slots, n, hook);
  } else {
    for (k = 0; k < n && k <= 255u; ++k) {
      if (slots[k].sink) play_sink(h, frames, slots[k].block, slots[k].sink, (int)k, NULL);
    }
  }
  dispatched(h);
}

/* ---- the metronome's click (O11) ----------------------------------------- */

#define CLICK_GAIN 8192             /* 0.25 full scale, in Q15 */
#define CLICK_GAIN_ACCENT 11469     /* 0.35 on a downbeat */

void fm1_seq_click_init(fm1_seq_click_t *c, uint32_t rate) {
  uint32_t h0 = rate / 2000u, h1 = rate / 3200u;
  memset(c, 0, sizeof(*c));
  c->len = rate / 50u ? rate / 50u : 1u;
  c->half[0] = (uint16_t)(h0 < 1u ? 1u : (h0 > 0xFFFFu ? 0xFFFFu : h0));
  c->half[1] = (uint16_t)(h1 < 1u ? 1u : (h1 > 0xFFFFu ? 0xFFFFu : h1));
  c->pos = c->len;
}

/* The click's sample at c->pos, in Q15: a triangle of c->half[accent]
 * frames a half-period under (left / len)^2, times its gain. Integer
 * division truncates toward zero in C99, the same on every target. */
static int32_t click_sample(const fm1_seq_click_t *c) {
  const int64_t half = c->half[c->accent];
  const int64_t period = 2 * half;
  const int64_t t = (int64_t)c->pos % period;
  const int64_t tri = 2 * (t < half ? t : period - t) - half;   /* -half .. half */
  const int64_t w = tri * 32767 / half;
  const uint64_t left = (uint64_t)(c->len - c->pos);
  const int64_t env = (int64_t)(left * left * 32767u / ((uint64_t)c->len * c->len));
  return (int32_t)(w * env / 32768 * (c->accent ? CLICK_GAIN_ACCENT : CLICK_GAIN) / 32768);
}

/* Frames from..to of the voice into lr: exact, since the sample is an
 * integer below 2^24 and 1/32768 a power of two. */
static void click_run(fm1_seq_click_t *c, float *lr, uint32_t from, uint32_t to) {
  uint32_t i;
  for (i = from; i < to && c->pos < c->len; ++i, ++c->pos) {
    const float x = (float)click_sample(c) * (1.0f / 32768.0f);
    lr[2u * i] += x;
    lr[2u * i + 1u] += x;
  }
}

void fm1_seq_click_mix(fm1_seq_click_t *c, const fm1_seq_t *s, const fm1_seq_ev_t *ev, uint32_t n,
                       uint32_t frames, float *lr) {
  uint32_t k, cur = 0;
  int on = -1;                  /* the metronome, read at the block's first click */
  for (k = 0; k < n; ++k) {
    uint32_t f;
    if (ev[k].kind != FM1_SEQ_EV_CLICK) continue;
    if (on < 0) {
      fm1_seq_info_t info;
      on = 0;
      if (s) {
        fm1_seq_get_info(s, &info);
        on = info.metronome != 0;
      }
    }
    if (!on) break;
    f = ev[k].frame < frames ? ev[k].frame : frames;
    if (f > cur) {
      click_run(c, lr, cur, f);
      cur = f;
    }
    c->pos = 0;
    c->accent = ev[k].a != 0;
    ++c->clicks;
  }
  click_run(c, lr, cur, frames);
}

int fm1_seq_lane_param(const fm1_engine_t *e, const char *label) {
  const char *name;
  uint16_t q;
  if (!e || !label) return -1;
  name = label_name(label);
  for (q = 0; q < e->n_params; ++q) {
    if (same_name(e->params[q].name, name)) return q;
  }
  return -1;
}

uint16_t fm1_seq_lane_uid(const fm1_engine_t *e, const char *label) {
  int i;
  if (!label || !label[0]) return 0;   /* the common case: an unused lane */
  i = fm1_seq_lane_param(e, label);
  return i < 0 ? 0u : e->params[i].uid;
}

float fm1_seq_lock_value(const fm1_param_t *p, unsigned v) {
  if (p->type == FM1_PARAM_ENUM) {
    const unsigned n = (unsigned)(p->max - p->min) + 1u;
    return p->min + (float)(v * n / (FM1_SEQ_VAL_MAX + 1u));
  }
  if (fm1_param_is_log(p)) {   /* the LOG law: position v / 127 (API v3) */
    return fm1_param_at(p, (float)(v > FM1_SEQ_VAL_MAX ? FM1_SEQ_VAL_MAX : v) /
                               (float)FM1_SEQ_VAL_MAX);
  }
  return p->min + (p->max - p->min) * (float)v / (float)FM1_SEQ_VAL_MAX;
}

/* floor(x + 0.5) for x in 0..127, without libm: the same on every build. */
static unsigned round_7(float x) {
  if (!(x > 0.0f)) return 0u;                   /* NaN and below the range too */
  if (x >= (float)FM1_SEQ_VAL_MAX) return FM1_SEQ_VAL_MAX;
  return (unsigned)(x + 0.5f);                  /* truncation of a positive value */
}

unsigned fm1_seq_value7(const fm1_param_t *p, float x) {
  if (!(x == x)) x = p->def;
  if (p->type == FM1_PARAM_ENUM) {
    const unsigned n = (unsigned)(p->max - p->min) + 1u;
    const unsigned e = round_7(x - p->min) < n ? round_7(x - p->min) : n - 1u;
    /* The lowest v with floor(v * n / 128) == e: ceil(e * 128 / n). Every
     * bin holds one at n <= 128; past that an empty bin gives the next. */
    const unsigned v = (e * (FM1_SEQ_VAL_MAX + 1u) + n - 1u) / n;
    return v < FM1_SEQ_VAL_MAX ? v : FM1_SEQ_VAL_MAX;
  }
  if (!(p->max > p->min)) return 0u;
  if (fm1_param_is_log(p)) return round_7(fm1_param_pos(p, x) * (float)FM1_SEQ_VAL_MAX);
  return round_7((x - p->min) / (p->max - p->min) * (float)FM1_SEQ_VAL_MAX);
}

unsigned fm1_seq_value7_step(const fm1_param_t *p, unsigned v, int delta) {
  int to;
  if (v > FM1_SEQ_VAL_MAX) v = FM1_SEQ_VAL_MAX;
  if (p->type == FM1_PARAM_ENUM) {          /* one entry, the bins' grid */
    const int n = (int)(p->max - p->min) + 1;
    const int e = (int)(fm1_seq_lock_value(p, v) - p->min);
    to = e + delta;
    to = to < 0 ? 0 : (to > n - 1 ? n - 1 : to);
    return fm1_seq_value7(p, p->min + (float)to);
  }
  to = (int)v + delta;
  return (unsigned)(to < 0 ? 0 : (to > (int)FM1_SEQ_VAL_MAX ? (int)FM1_SEQ_VAL_MAX : to));
}

size_t fm1_seq_lane_label_for(const fm1_param_t *p, char *buf, size_t size) {
  static const char prefix[] = "synth:";
  size_t n = 0, k;
  if (!size) return 0;
  for (k = 0; prefix[k] && n + 1u < size; ++k) buf[n++] = prefix[k];
  for (k = 0; p->name[k] && n + 1u < size; ++k) buf[n++] = p->name[k] == ' ' ? '_' : p->name[k];
  buf[n] = '\0';
  return n;
}

int fm1_seq_routes_default(const fm1_seq_t *s) {
  fm1_seq_info_t info;
  uint8_t t;
  fm1_seq_get_info(s, &info);
  for (t = 0; t < info.tracks; ++t) {
    fm1_seq_track_info_t ti;
    fm1_seq_get_track(s, t, &ti);
    if (ti.route_kind != FM1_SEQ_ROUTE_MIDI || ti.route_index != t % 16u + 1u) return 0;
  }
  return 1;
}

int fm1_seq_default_route(fm1_seq_t *s, int have_engine) {
  if (!have_engine || !fm1_seq_routes_default(s)) return 0;
  return fm1_seq_set_route(s, 0, FM1_SEQ_ROUTE_ENGINE, 0) ? 1 : 0;
}
