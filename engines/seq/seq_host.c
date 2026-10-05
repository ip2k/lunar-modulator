/* seq_host.c -- the sequencer's per-block host contract (fm1_seq_host.h):
 * commands into a shared event buffer, advance, and the split renders that
 * hand engine-routed notes and locks to a sound engine at their own frame.
 * Extracted from fm1-render (engines/host/render.cc) without a change in
 * behaviour; lane labels resolve to parameter uids (engine API v2) when they
 * are set, and locks on NOLOCK parameters are refused. C99, no heap, no
 * stdio. MIT licence. */
#include "fm1_seq_host.h"

#include <string.h>

static char lower(char c) { return c >= 'A' && c <= 'Z' ? (char)(c - 'A' + 'a') : c; }

/* strcasecmp in the C locale, which is what fm1-render had. */
static int same_name(const char *a, const char *b) {
  for (; *a && *b; ++a, ++b) {
    if (lower(*a) != lower(*b)) return 0;
  }
  return *a == *b;
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

/* After a dispatch: each track's route, for the next block's note-offs. */
static void dispatched(fm1_seq_host_t *h) {
  unsigned t;
  for (t = 0; t < FM1_SEQ_MAX_TRACKS; ++t) {
    fm1_seq_track_info_t ti;
    h->dest[t] = h->seq && fm1_seq_get_track(h->seq, (uint8_t)t, &ti) ? dest_of(&ti)
                                                                      : FM1_SEQ_HOST_NO_DEST;
  }
  h->cmd_n = 0;
  h->n = 0;
}

/* One sink's share of the block: the events of tracks routed to the engine
 * (any slot when `slot` is negative, else that slot only), with its render
 * split at their frames. Leaves the buffer as it is. */
static void play_sink(fm1_seq_host_t *h, uint32_t frames, float *block, const fm1_seq_sink_t *sink,
                      int slot) {
  uint32_t k, cur = 0;
  for (k = 0; k < h->n; ++k) {
    const fm1_seq_ev_t *e = &h->ev[k];
    int param = -1;
    uint32_t f;
    uint8_t d;
    if (e->kind != FM1_SEQ_EV_NOTE_ON && e->kind != FM1_SEQ_EV_NOTE_OFF &&
        e->kind != FM1_SEQ_EV_LOCK) continue;
    d = dest_of_event(h, k);
    if (d & 0x80u) continue;                  /* MIDI, or no such track */
    if (slot >= 0 && d != (unsigned)slot) continue;
    if (e->kind == FM1_SEQ_EV_LOCK) {   /* resolved before any split */
      param = lock_target(h, sink->engine, e);
      if (param < 0) continue;
    }
    f = e->frame < frames ? e->frame : frames;
    if (f > cur) {
      sink->render(sink->ctx, block + 2u * cur, f - cur);
      if (cur) ++h->splits;
      cur = f;
    }
    if (e->kind == FM1_SEQ_EV_NOTE_ON) {
      sink->note_on(sink->ctx, e->a, e->b);
      ++h->notes_to_engine;
    } else if (e->kind == FM1_SEQ_EV_NOTE_OFF) {
      sink->note_off(sink->ctx, e->a);
    } else {
      sink->set_param(sink->ctx, (uint16_t)param,
                      fm1_seq_lock_value(&sink->engine->params[param], e->b));
      ++h->locks_to_engine;
    }
  }
  if (cur < frames) {
    sink->render(sink->ctx, block + 2u * cur, frames - cur);
    if (cur) ++h->splits;
  }
}

void fm1_seq_host_dispatch(fm1_seq_host_t *h, uint32_t frames, float *block,
                           const fm1_seq_sink_t *sink) {
  if (sink) {
    if (sink->engine != h->engine) fm1_seq_host_bind(h, sink->engine);
    play_sink(h, frames, block, sink, -1);
  }
  dispatched(h);
}

void fm1_seq_host_dispatch_slots(fm1_seq_host_t *h, uint32_t frames, const fm1_seq_slot_t *slots,
                                 unsigned n) {
  unsigned k;
  if (n && slots[0].sink && slots[0].sink->engine != h->engine) {
    fm1_seq_host_bind(h, slots[0].sink->engine);
  }
  for (k = 0; k < n && k <= 255u; ++k) {
    if (slots[k].sink) play_sink(h, frames, slots[k].block, slots[k].sink, (int)k);
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
  return p->min + (p->max - p->min) * (float)v / (float)FM1_SEQ_VAL_MAX;
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
