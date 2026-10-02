/* seq_host.c -- the sequencer's per-block host contract (fm1_seq_host.h):
 * commands into a shared event buffer, advance, and the split renders that
 * hand engine-routed notes and locks to a sound engine at their own frame.
 * Extracted from fm1-render (engines/host/render.cc) without a change in
 * behaviour. C99, no heap, no stdio. MIT licence. */
#include "fm1_seq_host.h"

void fm1_seq_host_init(fm1_seq_host_t *h, fm1_seq_t *seq, fm1_seq_ev_t *ev, uint32_t cap) {
  h->seq = seq;
  h->ev = ev;
  h->cap = ev ? cap : 0u;
  h->n = 0;
  h->max_n = 0;
  h->notes_to_engine = 0;
  h->locks_to_engine = 0;
  h->splits = 0;
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

uint32_t fm1_seq_host_line(fm1_seq_host_t *h, const char *ops, size_t len) {
  const uint32_t k = fm1_seq_apply_line(h->seq, ops, len, tail(h), fm1_seq_host_room(h));
  h->n += k;
  return k;
}

uint32_t fm1_seq_host_cmd(fm1_seq_host_t *h, const fm1_seq_cmd_t *c) {
  const uint32_t k = fm1_seq_apply(h->seq, c, tail(h), fm1_seq_host_room(h));
  h->n += k;
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
  h->n += fm1_seq_advance(h->seq, frames, tail(h), fm1_seq_host_room(h));
  if (h->n > h->max_n) h->max_n = h->n;
  return h->n;
}

void fm1_seq_host_dispatch(fm1_seq_host_t *h, uint32_t frames, float *block,
                           const fm1_seq_sink_t *sink) {
  uint32_t k, cur = 0;
  if (sink) {
    for (k = 0; k < h->n; ++k) {
      const fm1_seq_ev_t *e = &h->ev[k];
      fm1_seq_track_info_t ti;
      int param = -1;
      uint32_t f;
      if (e->kind != FM1_SEQ_EV_NOTE_ON && e->kind != FM1_SEQ_EV_NOTE_OFF &&
          e->kind != FM1_SEQ_EV_LOCK) continue;
      if (!fm1_seq_get_track(h->seq, e->track, &ti) || ti.route_kind != FM1_SEQ_ROUTE_ENGINE) {
        continue;
      }
      if (e->kind == FM1_SEQ_EV_LOCK) {   /* resolved before any split */
        param = fm1_seq_lane_param(sink->engine, fm1_seq_lane_label(h->seq, e->track, e->a));
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
  h->n = 0;
}

static char lower(char c) { return c >= 'A' && c <= 'Z' ? (char)(c - 'A' + 'a') : c; }

/* strcasecmp in the C locale, which is what fm1-render had. */
static int same_name(const char *a, const char *b) {
  for (; *a && *b; ++a, ++b) {
    if (lower(*a) != lower(*b)) return 0;
  }
  return *a == *b;
}

int fm1_seq_lane_param(const fm1_engine_t *e, const char *label) {
  const char *name = label;
  const char *p;
  uint16_t q;
  if (!e || !label) return -1;
  for (p = label; *p; ++p) {
    if (*p == ':') name = p + 1;
  }
  for (q = 0; q < e->n_params; ++q) {
    if (same_name(e->params[q].name, name)) return q;
  }
  return -1;
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
