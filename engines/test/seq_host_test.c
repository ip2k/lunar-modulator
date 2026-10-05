/* seq_host_test.c -- fm1-seq-host-test: the host bridge (fm1_seq_host.h)
 * where fm1-render does not reach it.
 *
 *   - Typed commands (host_cmd), realtime input (host_realtime) and live
 *     notes (host_note_in) give the same events and the same set as the
 *     text lines fm1-render applies (host_line).
 *   - Dispatch hands a sink every engine-routed note and lock at its own
 *     frame, in emission order, renders every frame of the block once (no
 *     empty pieces), and counts a split for each piece that starts inside
 *     it. A MIDI-routed track's notes and locks never reach it, even when
 *     the lane names a parameter.
 *   - A hand-made buffer: a frame past the block is clamped to its end.
 *   - The room figures, the realtime-line parser (length-bounded), lane
 *     labels, and every lock value on ranges other than 0..1 (where the
 *     expression's parenthesisation shows).
 *   - A control-rate hook (dispatch_ticks, docs/16 MG1): ticks at their
 *     frames, docs/16's M6 order at one frame (note-offs and locks, the
 *     tick's writes, then note-ons), a lock's value from the hook, a render
 *     split only where a tick writes, every event fed in order, ticks with
 *     no sink, and a bridge with no sequencer.
 *   - Several sound units (dispatch_slots): each slot's sink gets only its
 *     own tracks' events, split only at their frames; a track routed to an
 *     empty slot or past the last reaches nothing and splits nothing; a
 *     lock resolves on its slot's engine, and slot 0's engine is bound.
 *   - The hook over several slots (dispatch_slots_ticks, docs/16 MG3): every
 *     event fed once, to_engine for any slot's; a tick's writes go to the
 *     slot they name, split there; a slot's locks go through lock_slot with
 *     its number; at one frame each slot keeps M6's order; no hook is plain
 *     dispatch_slots.
 *   - Engine API v2: every lane's uid equals a fresh resolution of its label
 *     after every block, through text and typed commands alike; a lock goes
 *     to its uid's parameter, whose index is not uid - 1; a NOLOCK
 *     parameter's locks are refused, counted and split nothing; a new
 *     engine, an import and a released lane re-resolve; and a label set
 *     on the core directly, past the bridge, still reaches its parameter.
 *   - The lock UI's grid (docs/15 S8): fm1_seq_value7 inverts every lock
 *     value, a knob step moves one 7-bit value or one list entry, and the
 *     label a UI writes for a parameter, a space as '_', resolves to it.
 *
 * Prints one JSON line of counts; exits 1 after the first failed check is
 * reported. Desktop test code (stdio); the bridge itself has none. MIT
 * licence. */
#include "fm1_seq_host.h"

#include <stdio.h>
#include <string.h>

static int failed;

#define CHECK(c)                                                          \
  do {                                                                    \
    if (!(c)) {                                                           \
      fprintf(stderr, "%s:%d: check failed: %s\n", __FILE__, __LINE__, #c); \
      failed = 1;                                                         \
    }                                                                     \
  } while (0)

/* A pretend engine: a FLOAT and an ENUM of 8 values, then FLOATs on ranges
 * like Sophie's (Tune, Decay, Sweep), where min + range * v / 127 and
 * min + range * (v / 127) round differently, and a NOLOCK ENUM. Uids are
 * deliberately not index + 1. */
#define CONT FM1_PARAM_CONTINUOUS
static const fm1_param_t kParams[] = {
  { "Timbre", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 40, CONT, FM1_UNIT_NONE, "Timbre" },
  { "Model", FM1_PARAM_ENUM, 0.0f, 7.0f, 0.0f, NULL, 0, 7, FM1_PARAM_LATCH, FM1_UNIT_NONE, "Model" },
  { "Tune", FM1_PARAM_FLOAT, -24.0f, 24.0f, 0.0f, NULL, 0, 3, CONT, FM1_UNIT_SEMI, "Tune" },
  { "Decay", FM1_PARAM_FLOAT, 0.03f, 4.0f, 0.28f, NULL, 0, 12, CONT, FM1_UNIT_NONE, "Decay" },
  { "Sweep", FM1_PARAM_FLOAT, -100.0f, 100.0f, 55.0f, NULL, 0, 1, CONT, FM1_UNIT_PCT, "Sweep" },
  { "Bank", FM1_PARAM_ENUM, 0.0f, 3.0f, 0.0f, NULL, 1, 2, FM1_PARAM_NOLOCK, FM1_UNIT_NONE, "Bank" },
};
#define N_PARAMS (sizeof(kParams) / sizeof(kParams[0]))
static const fm1_engine_t kEngine = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND, "fake", "Fake", "", kParams,
  (uint16_t)N_PARAMS, 8, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
};
/* A second engine that names Timbre and Bank too, at other uids and with
 * Bank lockable: a lane follows the engine it plays. */
static const fm1_param_t kOtherParams[] = {
  { "Bank", FM1_PARAM_ENUM, 0.0f, 3.0f, 0.0f, NULL, 0, 9, 0, FM1_UNIT_NONE, "Bank" },
  { "Timbre", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 5, CONT, FM1_UNIT_NONE, "Timbre" },
};
static const fm1_engine_t kOther = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND, "other", "Other", "", kOtherParams,
  2, 8, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
};
#undef CONT

/* Every lane of h resolves as its label does now, against e, and every
 * labelled lane's stored uid already is that (the getter alone would
 * re-resolve a stale one, so it cannot show that the bridge kept it). */
static int lanes_match(const fm1_seq_host_t *h, const fm1_engine_t *e) {
  unsigned t, lane;
  for (t = 0; t < FM1_SEQ_MAX_TRACKS; ++t) {
    for (lane = 0; lane < FM1_SEQ_LANES; ++lane) {
      const char *label = fm1_seq_lane_label(h->seq, (uint8_t)t, (uint8_t)lane);
      const uint16_t fresh = fm1_seq_lane_uid(e, label);
      if (fm1_seq_host_lane_uid(h, (uint8_t)t, (uint8_t)lane) != fresh) return 0;
      if (label[0] && h->lane_uid[t][lane] != fresh) return 0;
    }
  }
  return 1;
}

/* What the sink was asked to do, with the frame the block had reached. */
enum { C_ON = 1, C_OFF, C_PARAM, C_BEND };
typedef struct {
  uint8_t kind, a, b;
  uint16_t index;
  float value;
  uint32_t at;
} call_t;

typedef struct {
  uint32_t rendered;                   /* frames rendered in this block */
  uint32_t pieces, inside;             /* render calls; those starting past 0 */
  call_t calls[512];
  uint32_t n;
  float *block;                        /* the block being rendered */
  int bad_piece;                       /* a piece not where the last one ended */
} trace_t;

static void t_render(void *ctx, float *lr, uint32_t frames) {
  trace_t *t = (trace_t *)ctx;
  if (lr != t->block + 2u * t->rendered || frames == 0) t->bad_piece = 1;
  if (t->rendered) ++t->inside;
  t->rendered += frames;
  ++t->pieces;
}
static void t_call(trace_t *t, uint8_t kind, uint8_t a, uint8_t b, uint16_t index, float v) {
  if (t->n < sizeof(t->calls) / sizeof(t->calls[0])) {
    call_t *c = &t->calls[t->n++];
    c->kind = kind;
    c->a = a;
    c->b = b;
    c->index = index;
    c->value = v;
    c->at = t->rendered;
  }
}
static void t_on(void *ctx, uint8_t note, uint8_t vel) { t_call((trace_t *)ctx, C_ON, note, vel, 0, 0); }
static void t_off(void *ctx, uint8_t note) { t_call((trace_t *)ctx, C_OFF, note, 0, 0, 0); }
static void t_param(void *ctx, uint16_t index, float v) { t_call((trace_t *)ctx, C_PARAM, 0, 0, index, v); }
static void t_bend(void *ctx, float v) { t_call((trace_t *)ctx, C_BEND, 0, 0, 0, v); }

#define TRACKS 4
#define BLOCK 64u
#define CAP 512u

/* Instance memory, 8-byte aligned. */
static uint64_t mem_text[4096], mem_typed[4096];
static fm1_seq_ev_t ev_text[CAP], ev_typed[CAP];
static char set_text[16384], set_typed[16384];

/* One op per entry, applied at the start of block `at`; "rt XX" is realtime
 * input and "non"/"nof" live notes on the typed side. Track 0's notes are
 * long, so the external Start at block 1000 (while playing) ends sounding
 * notes from inside fm1_seq_realtime_in; MIDI clock follows it. Track 1 is
 * routed to the engine; track 2 stays on MIDI, with a note and a lane that
 * names Timbre, none of which may reach the sink. */
typedef struct {
  uint32_t at;
  const char *op;
} step_t;

static const step_t kScript[] = {
  { 0, "tog 0 0 60 100 64 90" }, { 0, "tog 0 3 67 100" }, { 0, "tog 0 6 72 80" },
  { 0, "slen 0 0 15 -1 300" }, { 0, "tog 1 2 48 100" }, { 0, "route 1 1 0" },
  { 0, "tog 2 1 55 100" }, { 0, "route 2 0 3" }, { 0, "alabel 2 0 synth:Timbre" },
  { 0, "aset 2 0 1 99 1" }, { 0, "aset 2 0 5 7 1" },
  { 0, "alabel 0 0 synth:Timbre" }, { 0, "alabel 0 1 x:MODEL" },
  { 0, "alabel 0 2 synth:Nothing" }, { 0, "abase 0 0 10" }, { 0, "aset 0 0 2 90 1" },
  { 0, "aset 0 1 5 40 1" }, { 0, "aset 0 2 3 70 1" }, { 0, "swing 62" }, { 0, "play" },
  { 300, "rec 0" }, { 330, "non 0 62 87" }, { 370, "nof 0 62" },
  { 700, "alabel 0 3 synth:bank" }, { 700, "aset 0 3 4 100 1" },        /* NOLOCK */
  { 800, "alabel 0 2 synth:sweep" },                                   /* relabelled */
  { 1000, "rt FA" }, { 1200, "aclr 0 3" },                             /* released */
  { 1500, "rt FC" }, { 2000, "stop" }, { 2600, "play" }, { 3800, "stop" },
};
#define BLOCKS 4000u
#define CLOCK_FROM 1001u   /* rt F8 every 16 blocks (1,024 frames) up to 1500 */
#define CLOCK_TO 1500u

/* Applies one op to both hosts: text on `a`, typed on `b`. */
static void apply_both(fm1_seq_host_t *a, fm1_seq_host_t *b, const char *op) {
  const size_t len = strlen(op);
  const uint32_t before = a->n;
  const uint32_t got = fm1_seq_host_line(a, op, len);
  CHECK(a->n == before + got && fm1_seq_host_room(a) == CAP - a->n);
  if (strncmp(op, "rt ", 3) == 0) {
    fm1_seq_host_realtime(b, (uint8_t)fm1_seq_realtime_status(op, len));
  } else if (strncmp(op, "non ", 4) == 0 || strncmp(op, "nof ", 4) == 0) {
    fm1_seq_cmd_t c;
    fm1_seq_parse(op, len, &c);
    fm1_seq_host_note_in(b, (uint8_t)c.arg[0], (uint8_t)c.arg[1],
                         op[2] == 'n' ? (uint8_t)c.arg[2] : 0u);
  } else {
    fm1_seq_cmd_t c;
    CHECK(fm1_seq_parse(op, len, &c) == 1);
    fm1_seq_host_cmd(b, &c);
  }
}

static fm1_seq_t *make(uint64_t *mem) {
  fm1_seq_limits_t lim;
  fm1_seq_limits_default(&lim, TRACKS);
  CHECK(fm1_seq_size(&lim) <= sizeof(mem_text));
  return fm1_seq_create(mem, &lim, 44118u);
}

/* The same script through text lines and through typed inputs: identical
 * events, block by block, and the same set at the end. Dispatches the text
 * side into a tracing sink and checks each block's calls against its events. */
static void inputs_and_dispatch(uint64_t *n_events, uint64_t *n_calls, uint64_t *n_inside) {
  fm1_seq_host_t a, b;
  fm1_seq_sink_t sink;
  static trace_t tr;
  static float block[2 * BLOCK];
  static fm1_seq_ev_t seen[CAP];
  uint32_t k, i, rt_events = 0, midi_ons = 0, midi_locks = 0, nolock = 0;
  size_t next = 0;
  fm1_seq_host_init(&a, make(mem_text), ev_text, CAP);
  fm1_seq_host_init(&b, make(mem_typed), ev_typed, CAP);
  CHECK(a.seq && b.seq && a.n == 0 && a.max_n == 0 && a.splits == 0);
  sink.ctx = &tr;
  sink.engine = &kEngine;
  sink.render = t_render;
  sink.note_on = t_on;
  sink.note_off = t_off;
  sink.set_param = t_param;
  sink.pitch_bend = NULL;
  fm1_seq_set_route(a.seq, 0, FM1_SEQ_ROUTE_ENGINE, 0);
  fm1_seq_set_route(b.seq, 0, FM1_SEQ_ROUTE_ENGINE, 0);
  fm1_seq_host_bind(&b, &kEngine);   /* b never dispatches into a sink */
  *n_events = *n_calls = *n_inside = 0;
  for (k = 0; k < BLOCKS; ++k) {
    uint32_t na, nb;
    for (; next < sizeof(kScript) / sizeof(kScript[0]) && kScript[next].at == k; ++next) {
      apply_both(&a, &b, kScript[next].op);
    }
    if (k >= CLOCK_FROM && k < CLOCK_TO && (k - CLOCK_FROM) % 16u == 0) apply_both(&a, &b, "rt F8");
    if (k == 1000) rt_events = a.n;
    CHECK(k == 0 || lanes_match(&a, &kEngine));   /* resolved at alabel, before dispatch */
    CHECK(lanes_match(&b, &kEngine));
    na = fm1_seq_host_advance(&a, BLOCK);
    nb = fm1_seq_host_advance(&b, BLOCK);
    CHECK(na == a.n && nb == b.n && na == nb);
    CHECK(na == 0 || memcmp(a.ev, b.ev, na * sizeof(*a.ev)) == 0);
    *n_events += na;
    memcpy(seen, a.ev, na * sizeof(*a.ev));
    memset(&tr, 0, sizeof(tr));
    tr.block = block;
    fm1_seq_host_dispatch(&a, BLOCK, block, &sink);
    fm1_seq_host_dispatch(&b, BLOCK, NULL, NULL);
    CHECK(a.n == 0 && b.n == 0 && fm1_seq_host_room(&a) == CAP);
    CHECK(tr.rendered == BLOCK && !tr.bad_piece);
    {
      /* What the sink must have received, in order: the block's notes and
       * locks of engine-routed tracks, a lock only if its label names a
       * parameter, each at its own frame. */
      uint32_t c = 0;
      for (i = 0; i < na; ++i) {
        const fm1_seq_ev_t *e = &seen[i];
        fm1_seq_track_info_t ti;
        int p = 0;
        if (e->kind != FM1_SEQ_EV_NOTE_ON && e->kind != FM1_SEQ_EV_NOTE_OFF &&
            e->kind != FM1_SEQ_EV_LOCK) continue;
        fm1_seq_get_track(a.seq, e->track, &ti);
        if (ti.route_kind != FM1_SEQ_ROUTE_ENGINE) {
          if (e->track == 2 && e->kind == FM1_SEQ_EV_NOTE_ON) ++midi_ons;
          if (e->track == 2 && e->kind == FM1_SEQ_EV_LOCK) ++midi_locks;
          continue;
        }
        if (e->kind == FM1_SEQ_EV_LOCK) {
          p = fm1_seq_lane_param(&kEngine, fm1_seq_lane_label(a.seq, e->track, e->a));
          if (p < 0) continue;
          if (kParams[p].flags & FM1_PARAM_NOLOCK) {
            ++nolock;
            continue;
          }
        }
        CHECK(c < tr.n);
        if (c >= tr.n) break;
        CHECK(tr.calls[c].at == (e->frame < BLOCK ? e->frame : BLOCK));
        if (e->kind == FM1_SEQ_EV_NOTE_ON) {
          CHECK(tr.calls[c].kind == C_ON && tr.calls[c].a == e->a && tr.calls[c].b == e->b);
        } else if (e->kind == FM1_SEQ_EV_NOTE_OFF) {
          CHECK(tr.calls[c].kind == C_OFF && tr.calls[c].a == e->a);
        } else {
          CHECK(tr.calls[c].kind == C_PARAM && tr.calls[c].index == (uint16_t)p &&
                tr.calls[c].value == fm1_seq_lock_value(&kParams[p], e->b));
        }
        ++c;
      }
      CHECK(c == tr.n);
      *n_calls += tr.n;
    }
    *n_inside += tr.inside;
  }
  CHECK(a.splits == *n_inside && *n_inside > 0);
  CHECK(a.max_n == b.max_n && a.max_n > 0);
  CHECK(a.notes_to_engine > 0 && a.locks_to_engine > 0);
  CHECK(a.locks_refused == nolock && nolock > 0);    /* Bank's locks, every one */
  CHECK(b.notes_to_engine == 0 && b.splits == 0);    /* a NULL sink plays nothing */
  CHECK(b.locks_refused == 0);
  CHECK(midi_ons > 0 && midi_locks > 0);             /* track 2 played, to MIDI only */
  {
    const size_t la = fm1_seq_export_movy1(a.seq, set_text, sizeof(set_text));
    const size_t lb = fm1_seq_export_movy1(b.seq, set_typed, sizeof(set_typed));
    CHECK(la < sizeof(set_text) && la == lb && memcmp(set_text, set_typed, la) == 0);
    CHECK(strstr(set_text, ":62:87:") != NULL);      /* the live note, as played */
  }
  CHECK(rt_events > 0);                              /* the Start's note-offs */
}

static void parsers_and_figures(void) {
  fm1_seq_limits_t lim;
  fm1_seq_limits_default(&lim, 8);
  CHECK(fm1_seq_cmd_max_events(&lim) == 129u);       /* 64 gates + 8 x 8 lanes + Stop */
  fm1_seq_limits_default(&lim, 4);
  CHECK(fm1_seq_cmd_max_events(&lim) == 97u);
  CHECK(fm1_seq_realtime_status("rt FA", 5) == 0xFAu);
  CHECK(fm1_seq_realtime_status("rt\t f8 \t", 8) == 0xF8u);
  CHECK(fm1_seq_realtime_status("rt FBxx", 5) == 0xFBu);   /* only len bytes count */
  CHECK(fm1_seq_realtime_status("rt FC", 4) == 0);
  CHECK(fm1_seq_realtime_status("rt F9", 5) == 0);
  CHECK(fm1_seq_realtime_status("rt FA x", 7) == 0);
  CHECK(fm1_seq_realtime_status("rtFA", 4) == 0);
  CHECK(fm1_seq_realtime_status("play", 4) == 0);
  CHECK(fm1_seq_lane_param(&kEngine, "synth:Timbre") == 0);
  CHECK(fm1_seq_lane_param(&kEngine, "TIMBRE") == 0);
  CHECK(fm1_seq_lane_param(&kEngine, "a:b:model") == 1);
  CHECK(fm1_seq_lane_param(&kEngine, "model:x") == -1);
  CHECK(fm1_seq_lane_param(&kEngine, "Timbre:") == -1);
  CHECK(fm1_seq_lane_param(&kEngine, "Timbr") == -1);
  CHECK(fm1_seq_lane_param(NULL, "Timbre") == -1);
  CHECK(fm1_seq_lock_value(&kParams[0], 0) == 0.0f);
  CHECK(fm1_seq_lock_value(&kParams[0], 127) == 1.0f);
  CHECK(fm1_seq_lock_value(&kParams[0], 64) == 64.0f / 127.0f);
  CHECK(fm1_seq_lock_value(&kParams[1], 15) == 0.0f);
  CHECK(fm1_seq_lock_value(&kParams[1], 16) == 1.0f);
  CHECK(fm1_seq_lock_value(&kParams[1], 127) == 7.0f);
  {
    /* Every 7-bit value on every parameter: FLOAT is min + range * v / 127,
     * evaluated left to right as fm1-render's LockValue was; ENUM is min +
     * floor(v * n / 128). The pinned values are where min + range * (v /
     * 127) would round to a neighbouring float. */
    unsigned q, v;
    for (q = 0; q < N_PARAMS; ++q) {
      const fm1_param_t *p = &kParams[q];
      for (v = 0; v <= FM1_SEQ_VAL_MAX; ++v) {
        const float want = p->type == FM1_PARAM_ENUM
            ? p->min + (float)(v * ((unsigned)(p->max - p->min) + 1u) / 128u)
            : p->min + (p->max - p->min) * (float)v / (float)FM1_SEQ_VAL_MAX;
        CHECK(fm1_seq_lock_value(p, v) == want);
      }
    }
    CHECK(fm1_seq_lock_value(&kParams[2], 6) == -21.732282638549805f);
    CHECK(fm1_seq_lock_value(&kParams[3], 9) == 0.3113385736942291f);
    CHECK(fm1_seq_lock_value(&kParams[4], 9) == -85.82677459716797f);
  }
}

/* docs/15 S8: the 7-bit grid a lock UI turns on. FLOAT: value7 inverts
 * lock_value at every v; ENUM: every entry's lowest v, so lock_value of it
 * is the entry, and value7 of any v in a bin is that bin's lowest. A knob
 * step moves one v (FLOAT) or one entry (ENUM), clamped. Labels: '_'
 * stands for a space, in either case, and the UI's label for a parameter
 * resolves to it. */
static const fm1_param_t kSpaced[] = {
  { "Env Pitch", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 0, 21, FM1_PARAM_CONTINUOUS,
    FM1_UNIT_NONE, "EnvP" },
  { "Filter Type", FM1_PARAM_ENUM, 0.0f, 4.0f, 0.0f, NULL, 0, 22, 0, FM1_UNIT_NONE, "FltTyp" },
  { "Patch", FM1_PARAM_ENUM, 0.0f, 95.0f, 32.0f, NULL, 0, 23, 0, FM1_UNIT_NONE, "Patch" },
  { "Wide", FM1_PARAM_ENUM, 0.0f, 127.0f, 0.0f, NULL, 0, 24, 0, FM1_UNIT_NONE, "Wide" },
  { "Flat", FM1_PARAM_FLOAT, 2.0f, 2.0f, 2.0f, NULL, 0, 25, 0, FM1_UNIT_NONE, "Flat" },
};
static const fm1_engine_t kSpacedEngine = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND, "spaced", "Spaced", "", kSpaced,
  (uint16_t)(sizeof(kSpaced) / sizeof(kSpaced[0])), 8, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
  NULL, NULL
};

static void value7_and_labels(void) {
  volatile float zero = 0.0f;
  const float nan = zero / zero;
  unsigned q, v;
  const fm1_param_t *all[N_PARAMS + 4];
  unsigned n = 0;
  char label[FM1_SEQ_LABEL_MAX];
  for (q = 0; q < N_PARAMS; ++q) all[n++] = &kParams[q];
  for (q = 0; q < 4; ++q) all[n++] = &kSpaced[q];
  for (q = 0; q < n; ++q) {
    const fm1_param_t *p = all[q];
    unsigned prev = 0;
    for (v = 0; v <= FM1_SEQ_VAL_MAX; ++v) {
      const float x = fm1_seq_lock_value(p, v);
      const unsigned w = fm1_seq_value7(p, x);
      if (p->type == FM1_PARAM_FLOAT) {
        CHECK(w == v);
        CHECK(fm1_seq_value7_step(p, v, 1) == (v < 127u ? v + 1u : 127u));
        CHECK(fm1_seq_value7_step(p, v, -3) == (v >= 3u ? v - 3u : 0u));
      } else {
        CHECK(w <= v && fm1_seq_lock_value(p, w) == x);           /* the bin's lowest */
        CHECK(w == 0 || fm1_seq_lock_value(p, w - 1u) != x);
        CHECK(v == 0 || w == prev || w == v);                   /* bins are runs */
        CHECK(fm1_seq_lock_value(p, fm1_seq_value7_step(p, v, 1)) ==
              (x < p->max ? x + 1.0f : p->max));
        CHECK(fm1_seq_lock_value(p, fm1_seq_value7_step(p, v, -1)) ==
              (x > p->min ? x - 1.0f : p->min));
      }
      prev = w;
    }
    if (p->type == FM1_PARAM_ENUM) {
      float e;
      for (e = p->min; e <= p->max; e += 1.0f) {
        CHECK(fm1_seq_lock_value(p, fm1_seq_value7(p, e)) == e);
      }
    }
    /* Out of range, NaN and the halfway point. */
    CHECK(fm1_seq_value7(p, p->min - 1000.0f) == 0u);
    CHECK(fm1_seq_value7(p, p->max + 1000.0f) ==
          (p->type == FM1_PARAM_ENUM ? fm1_seq_value7(p, p->max) : 127u));
    CHECK(fm1_seq_value7(p, nan) == fm1_seq_value7(p, p->def));
  }
  CHECK(fm1_seq_value7(&kParams[0], 0.5f) == 64u);              /* 63.5 rounds up (Movy's norm7) */
  CHECK(fm1_seq_value7(&kParams[0], 63.0f / 127.0f + 0.001f) == 63u);
  CHECK(fm1_seq_value7(&kSpaced[3], 5.0f) == 5u);               /* 128 entries: v == entry */
  CHECK(fm1_seq_value7(&kSpaced[4], 2.0f) == 0u);               /* an empty range */
  CHECK(fm1_seq_value7_step(&kSpaced[1], 127u, 1) == fm1_seq_value7(&kSpaced[1], 4.0f));
  CHECK(fm1_seq_lane_label_for(&kSpaced[0], label, sizeof label) == 15u);
  CHECK(strcmp(label, "synth:Env_Pitch") == 0);
  CHECK(fm1_seq_lane_param(&kSpacedEngine, label) == 0);
  CHECK(fm1_seq_lane_param(&kSpacedEngine, "synth:env_PITCH") == 0);
  CHECK(fm1_seq_lane_param(&kSpacedEngine, "synth:Env Pitch") == 0);
  CHECK(fm1_seq_lane_param(&kSpacedEngine, "synth:EnvPitch") == -1);
  CHECK(fm1_seq_lane_param(&kSpacedEngine, "synth:Env__Pitch") == -1);
  CHECK(fm1_seq_lane_label_for(&kSpaced[1], label, sizeof label) == 17u);
  CHECK(fm1_seq_lane_param(&kSpacedEngine, label) == 1);
  CHECK(fm1_seq_lane_uid(&kSpacedEngine, label) == 22u);
  CHECK(fm1_seq_lane_label_for(&kSpaced[1], label, 8) == 7u && strcmp(label, "synth:F") == 0);
  for (q = 0; q < N_PARAMS; ++q) {                              /* the UI's label round-trips */
    CHECK(fm1_seq_lane_label_for(&kParams[q], label, sizeof label) > 6u);
    CHECK(fm1_seq_lane_param(&kEngine, label) == (int)q);
  }
}

/* A buffer the host filled itself. The core never puts an event past the
 * block, so only a hand-made buffer reaches the clamp: such an event plays
 * at the block's end, and no empty piece follows it. A lock on a
 * MIDI-routed track (whose lane names a parameter) and one whose label names
 * none are skipped without a split. */
static void hand_made_block(void) {
  static trace_t tr;
  static float block[2 * BLOCK];
  static const char setup[] =
      "alabel 0 0 synth:Timbre;alabel 0 1 x:Nothing;alabel 1 0 synth:Tune;route 1 0 2";
  fm1_seq_ev_t ev[16], scratch[16];
  fm1_seq_host_t h;
  fm1_seq_sink_t sink;
  fm1_seq_t *s = make(mem_text);
  uint32_t n = 0;
  sink.ctx = &tr;
  sink.engine = &kEngine;
  sink.render = t_render;
  sink.note_on = t_on;
  sink.note_off = t_off;
  sink.set_param = t_param;
  sink.pitch_bend = NULL;
  CHECK(fm1_seq_apply_text(s, setup, sizeof(setup) - 1u, scratch, 16) == 0);
  fm1_seq_set_route(s, 0, FM1_SEQ_ROUTE_ENGINE, 0);
  fm1_seq_host_init(&h, s, ev, 16);
#define EV(fr, k, t, aa, bb)                                                  \
  do {                                                                        \
    ev[n].tick = 0; ev[n].frame = (fr); ev[n].kind = (k); ev[n].track = (t);  \
    ev[n].a = (aa); ev[n].b = (bb); ++n;                                      \
  } while (0)
  EV(0, FM1_SEQ_EV_NOTE_OFF, 0, 60, 0);
  EV(0, FM1_SEQ_EV_LOCK, 0, 0, 127);       /* Timbre 1 */
  EV(0, FM1_SEQ_EV_NOTE_ON, 0, 62, 90);
  EV(10, FM1_SEQ_EV_NOTE_ON, 1, 50, 100);  /* MIDI */
  EV(10, FM1_SEQ_EV_LOCK, 1, 0, 64);       /* MIDI, though its lane names Tune */
  EV(12, FM1_SEQ_EV_CLICK, FM1_SEQ_NONE, 1, 0);
  EV(12, FM1_SEQ_EV_LOCK, 0, 1, 5);        /* names no parameter */
  EV(20, FM1_SEQ_EV_LOCK, 0, 0, 0);        /* Timbre 0 */
  EV(70, FM1_SEQ_EV_NOTE_OFF, 0, 62, 0);   /* past the 64-frame block */
#undef EV
  h.n = n;
  memset(&tr, 0, sizeof(tr));
  tr.block = block;
  fm1_seq_host_dispatch(&h, BLOCK, block, &sink);
  CHECK(h.n == 0 && tr.rendered == BLOCK && !tr.bad_piece && tr.pieces == 2u);
  CHECK(h.splits == 1u && tr.inside == 1u && h.notes_to_engine == 1u && h.locks_to_engine == 2u);
  CHECK(tr.n == 5u);
  if (tr.n == 5u) {
    CHECK(tr.calls[0].kind == C_OFF && tr.calls[0].a == 60 && tr.calls[0].at == 0);
    CHECK(tr.calls[1].kind == C_PARAM && tr.calls[1].index == 0 && tr.calls[1].value == 1.0f &&
          tr.calls[1].at == 0);
    CHECK(tr.calls[2].kind == C_ON && tr.calls[2].a == 62 && tr.calls[2].b == 90 &&
          tr.calls[2].at == 0);
    CHECK(tr.calls[3].kind == C_PARAM && tr.calls[3].index == 0 && tr.calls[3].value == 0.0f &&
          tr.calls[3].at == 20);
    CHECK(tr.calls[4].kind == C_OFF && tr.calls[4].a == 62 && tr.calls[4].at == BLOCK);
  }
}

/* Engine API v2 in one block each: a lock goes to the parameter its uid
 * names (index 3 for uid 12), a NOLOCK one is refused before any split, a
 * new engine moves the lane to its own uid for the same name (and its Bank
 * is lockable), an import resolves, and a released lane resolves to none. */
static void uids_and_refusals(void) {
  static trace_t tr;
  static float block[2 * BLOCK];
  static const char setup[] = "alabel 0 0 synth:decay;alabel 0 1 synth:Bank;alabel 0 2 Timbre";
  static const char set[] = "movy1\nbpm 12000\ntk 0 0 0\nau 0 0 64 synth:sweep\n";
  fm1_seq_ev_t ev[16];
  fm1_seq_host_t h;
  fm1_seq_sink_t sink;
  uint32_t n = 0;
  sink.ctx = &tr;
  sink.engine = &kEngine;
  sink.render = t_render;
  sink.note_on = t_on;
  sink.note_off = t_off;
  sink.set_param = t_param;
  sink.pitch_bend = NULL;
  fm1_seq_host_init(&h, make(mem_text), ev, 16);
  CHECK(h.engine == NULL && h.locks_refused == 0);
  fm1_seq_set_route(h.seq, 0, FM1_SEQ_ROUTE_ENGINE, 0);
  CHECK(fm1_seq_host_line(&h, setup, sizeof(setup) - 1u) == 0);
  CHECK(fm1_seq_host_lane_uid(&h, 0, 0) == 0);           /* no engine bound yet */
  fm1_seq_host_bind(&h, &kEngine);
  CHECK(fm1_seq_host_lane_uid(&h, 0, 0) == 12 && fm1_seq_host_lane_uid(&h, 0, 1) == 2 &&
        fm1_seq_host_lane_uid(&h, 0, 2) == 40 && fm1_seq_host_lane_uid(&h, 0, 3) == 0);
  CHECK(fm1_seq_host_lane_uid(&h, 16, 0) == 0 && fm1_seq_host_lane_uid(&h, 0, 8) == 0);
  CHECK(fm1_param_index(&kEngine, 12) == 3 && fm1_param_index(&kEngine, 0) == -1 &&
        fm1_param_index(&kEngine, 99) == -1 && fm1_param_index(NULL, 12) == -1);
  {
    /* The flag helpers: NOLOCK wins over MOD, and an ENUM without MOD
     * takes locks but no route. */
    fm1_param_t both = kParams[0];
    both.flags = FM1_PARAM_NOLOCK | FM1_PARAM_MOD;
    CHECK(fm1_param_lockable(&kParams[0]) && fm1_param_modulatable(&kParams[0]));
    CHECK(fm1_param_lockable(&kParams[1]) && !fm1_param_modulatable(&kParams[1]));
    CHECK(!fm1_param_lockable(&kParams[5]) && !fm1_param_modulatable(&kParams[5]));
    CHECK(!fm1_param_lockable(&both) && !fm1_param_modulatable(&both));
  }
  CHECK(fm1_seq_lane_uid(&kEngine, "x:SWEEP") == 1 && fm1_seq_lane_uid(&kEngine, "") == 0 &&
        fm1_seq_lane_uid(&kEngine, "Nothing") == 0 && fm1_seq_lane_uid(NULL, "Tune") == 0);
#define EV(fr, k, t, aa, bb)                                                  \
  do {                                                                        \
    ev[n].tick = 0; ev[n].frame = (fr); ev[n].kind = (k); ev[n].track = (t);  \
    ev[n].a = (aa); ev[n].b = (bb); ++n;                                      \
  } while (0)
  EV(5, FM1_SEQ_EV_LOCK, 0, 1, 127);       /* Bank: NOLOCK, refused */
  EV(9, FM1_SEQ_EV_LOCK, 0, 0, 127);       /* Decay, index 3 */
  EV(9, FM1_SEQ_EV_LOCK, 0, 1, 64);        /* Bank again */
#undef EV
  h.n = n;
  memset(&tr, 0, sizeof(tr));
  tr.block = block;
  fm1_seq_host_dispatch(&h, BLOCK, block, &sink);
  CHECK(h.locks_refused == 2 && h.locks_to_engine == 1 && h.splits == 1 && tr.pieces == 2u);
  CHECK(tr.n == 1u && tr.calls[0].kind == C_PARAM && tr.calls[0].index == 3 &&
        tr.calls[0].value == fm1_seq_lock_value(&kParams[3], 127) && tr.calls[0].at == 9);
  /* Another engine: Timbre moves to its uid there, Bank becomes lockable. */
  n = 0;
  ev[0].tick = 0; ev[0].frame = 0; ev[0].kind = FM1_SEQ_EV_LOCK; ev[0].track = 0;
  ev[0].a = 1; ev[0].b = 127;
  ev[1] = ev[0];
  ev[1].a = 2;
  h.n = 2;
  sink.engine = &kOther;
  memset(&tr, 0, sizeof(tr));
  tr.block = block;
  fm1_seq_host_dispatch(&h, BLOCK, block, &sink);
  CHECK(h.engine == &kOther && fm1_seq_host_lane_uid(&h, 0, 2) == 5 &&
        fm1_seq_host_lane_uid(&h, 0, 0) == 0);
  CHECK(h.locks_refused == 2 && h.locks_to_engine == 3 && tr.n == 2u);
  CHECK(tr.n == 2u && tr.calls[0].index == 0 && tr.calls[0].value == 3.0f &&
        tr.calls[1].index == 1 && tr.calls[1].value == 1.0f);
  /* An import through the bridge resolves; a released lane resolves to none. */
  fm1_seq_host_bind(&h, &kEngine);
  CHECK(fm1_seq_host_import(&h, set, sizeof(set) - 1u) == 1);
  CHECK(fm1_seq_host_lane_uid(&h, 0, 0) == 1 && fm1_seq_host_lane_uid(&h, 0, 1) == 0 &&
        lanes_match(&h, &kEngine));
  CHECK(fm1_seq_host_line(&h, "aclr 0 0", 8) <= 1u);
  CHECK(fm1_seq_host_lane_uid(&h, 0, 0) == 0 && lanes_match(&h, &kEngine));
  h.n = 0;
  {
    /* A typed alabel resolves its track. */
    fm1_seq_cmd_t c;
    CHECK(fm1_seq_parse("alabel 0 5 a:tune", 17, &c) == 1);
    fm1_seq_host_cmd(&h, &c);
    CHECK(fm1_seq_host_lane_uid(&h, 0, 5) == 3 && lanes_match(&h, &kEngine));
  }
  {
    /* Labels set on the core directly, past the bridge: the stored uids are
     * stale (lane 5 still holds Tune's, lane 6 none), yet the getter and a
     * lock follow the labels, Sweep (index 4) and Decay (index 3). */
    static const char relabel[] = "alabel 0 5 synth:SWEEP;alabel 0 6 synth:decay";
    CHECK(fm1_seq_apply_text(h.seq, relabel, sizeof(relabel) - 1u, NULL, 0) == 0);
    CHECK(h.lane_uid[0][5] == 3 && h.lane_uid[0][6] == 0);
    CHECK(fm1_seq_host_lane_uid(&h, 0, 5) == 1 && fm1_seq_host_lane_uid(&h, 0, 6) == 12);
    ev[0].tick = 0; ev[0].frame = 0; ev[0].kind = FM1_SEQ_EV_LOCK; ev[0].track = 0;
    ev[0].a = 5; ev[0].b = 0;
    ev[1] = ev[0];
    ev[1].a = 6;
    ev[1].b = 127;
    h.n = 2;
    sink.engine = &kEngine;
    fm1_seq_set_route(h.seq, 0, FM1_SEQ_ROUTE_ENGINE, 0);   /* the import reset it */
    memset(&tr, 0, sizeof(tr));
    tr.block = block;
    fm1_seq_host_dispatch(&h, BLOCK, block, &sink);
    CHECK(tr.n == 2u && tr.calls[0].index == 4 &&
          tr.calls[0].value == fm1_seq_lock_value(&kParams[4], 0) && tr.calls[1].index == 3 &&
          tr.calls[1].value == fm1_seq_lock_value(&kParams[3], 127));
    /* And an import on the core: Sweep on lane 0, where Bank was bound. */
    fm1_seq_host_bind(&h, &kEngine);
    CHECK(fm1_seq_host_line(&h, "alabel 0 0 synth:Bank", 21) == 0 && h.lane_uid[0][0] == 2);
    CHECK(fm1_seq_import_movy1(h.seq, set, sizeof(set) - 1u) == 1);
    CHECK(h.lane_uid[0][0] == 2 && fm1_seq_host_lane_uid(&h, 0, 0) == 1);
    fm1_seq_host_bind(&h, &kEngine);
    CHECK(h.lane_uid[0][0] == 1 && lanes_match(&h, &kEngine));
  }
}

/* A pretend control-rate hook: ticks every 32 frames from frame 0, the
 * tick at 32 writes Timbre 0.25 and a bend of 1.5 when `write` is set, a lock
 * comes back raised by 0.5, and everything it sees is recorded. */
typedef struct {
  int write;
  uint32_t ticks, begins, events, locks;
  uint32_t ev_frame[32];
  uint8_t ev_kind[32], ev_to_engine[32];
  fm1_seq_hook_write_t w[2];
  trace_t *trace;                      /* where tick calls are noted, if any */
} fake_hook_t;

static uint32_t h_begin(void *ctx, uint32_t frames, const fm1_engine_t *e, uint32_t bpm, int playing) {
  fake_hook_t *f = (fake_hook_t *)ctx;
  (void)frames;
  (void)e;
  (void)bpm;
  (void)playing;
  ++f->begins;
  return 0;
}
static void h_event(void *ctx, uint32_t frame, const fm1_seq_ev_t *e, int to_engine) {
  fake_hook_t *f = (fake_hook_t *)ctx;
  if (f->events < 32) {
    f->ev_frame[f->events] = frame;
    f->ev_kind[f->events] = e->kind;
    f->ev_to_engine[f->events] = (uint8_t)to_engine;
  }
  ++f->events;
}
static float h_lock(void *ctx, uint16_t index, float v) {
  fake_hook_t *f = (fake_hook_t *)ctx;
  (void)index;
  ++f->locks;
  return v + 0.5f;
}
static uint32_t h_tick(void *ctx, uint32_t frame, const fm1_seq_hook_write_t **w, uint32_t *next) {
  fake_hook_t *f = (fake_hook_t *)ctx;
  ++f->ticks;
  *next = frame + 32u;
  f->w[0].index = 0;
  f->w[0].bend = 0;
  f->w[0].value = 0.25f;
  f->w[1].index = 0;
  f->w[1].bend = 1;
  f->w[1].value = 1.5f;
  *w = f->w;
  return f->write && frame == 32u ? 2u : 0u;
}

static void hooked_block(void) {
  static trace_t tr;
  static float block[2 * BLOCK];
  static const char setup[] = "alabel 0 0 synth:Timbre;route 1 0 2";
  fm1_seq_ev_t ev[16], scratch[16];
  fm1_seq_host_t h, bare;
  fm1_seq_sink_t sink;
  fm1_seq_hook_t hook;
  fake_hook_t fh;
  fm1_seq_t *s = make(mem_text);
  uint32_t n = 0, round;
  sink.ctx = &tr;
  sink.engine = &kEngine;
  sink.render = t_render;
  sink.note_on = t_on;
  sink.note_off = t_off;
  sink.set_param = t_param;
  sink.pitch_bend = t_bend;
  hook.ctx = &fh;
  hook.begin = h_begin;
  hook.event = h_event;
  hook.lock = h_lock;
  hook.tick = h_tick;
  CHECK(fm1_seq_apply_text(s, setup, sizeof(setup) - 1u, scratch, 16) == 0);
  fm1_seq_set_route(s, 0, FM1_SEQ_ROUTE_ENGINE, 0);
  fm1_seq_host_init(&h, s, ev, 16);
  for (round = 0; round < 3; ++round) {
    n = 0;
#define EV(fr, k, t, aa, bb)                                                  \
  do {                                                                        \
    ev[n].tick = 0; ev[n].frame = (fr); ev[n].kind = (k); ev[n].track = (t);  \
    ev[n].a = (aa); ev[n].b = (bb); ++n;                                      \
  } while (0)
    EV(0, FM1_SEQ_EV_NOTE_OFF, 0, 60, 0);
    EV(0, FM1_SEQ_EV_LOCK, 0, 0, 127);       /* Timbre 1, sent as 1.5 */
    EV(0, FM1_SEQ_EV_NOTE_ON, 0, 62, 90);
    EV(32, FM1_SEQ_EV_NOTE_OFF, 0, 62, 0);
    EV(32, FM1_SEQ_EV_LOCK, 0, 0, 0);        /* Timbre 0, sent as 0.5 */
    EV(32, FM1_SEQ_EV_NOTE_ON, 0, 64, 80);
    EV(40, FM1_SEQ_EV_NOTE_ON, 1, 50, 100);  /* MIDI: fed, not played */
    EV(40, FM1_SEQ_EV_CLOCK, FM1_SEQ_NONE, 0, 0);
#undef EV
    h.n = n;
    memset(&tr, 0, sizeof(tr));
    memset(&fh, 0, sizeof(fh));
    tr.block = block;
    fh.write = round == 0;
    fm1_seq_host_dispatch_ticks(&h, BLOCK, block, round == 2 ? NULL : &sink, &hook);
    CHECK(h.n == 0 && fh.begins == 1 && fh.ticks == 2 && fh.events == n);
    CHECK(fh.ev_frame[6] == 40 && fh.ev_kind[7] == FM1_SEQ_EV_CLOCK && !fh.ev_to_engine[6]);
    if (round == 2) {                       /* no sink: ticks and feeds only */
      CHECK(tr.n == 0 && tr.pieces == 0 && fh.ev_to_engine[0] == 0 && fh.locks == 0);
      continue;
    }
    CHECK(fh.ev_to_engine[0] && fh.ev_to_engine[1] && fh.locks == 2);
    CHECK(tr.rendered == BLOCK && !tr.bad_piece && tr.pieces == 2u);
    CHECK(tr.n == (round == 0 ? 8u : 6u));
    if (tr.n == 8u) {    /* at 32: off, lock, the tick's writes, then on (M6) */
      CHECK(tr.calls[0].kind == C_OFF && tr.calls[0].at == 0);
      CHECK(tr.calls[1].kind == C_PARAM && tr.calls[1].value == 1.5f && tr.calls[1].at == 0);
      CHECK(tr.calls[2].kind == C_ON && tr.calls[2].a == 62 && tr.calls[2].at == 0);
      CHECK(tr.calls[3].kind == C_OFF && tr.calls[3].a == 62 && tr.calls[3].at == 32);
      CHECK(tr.calls[4].kind == C_PARAM && tr.calls[4].value == 0.5f && tr.calls[4].at == 32);
      CHECK(tr.calls[5].kind == C_PARAM && tr.calls[5].value == 0.25f && tr.calls[5].at == 32);
      CHECK(tr.calls[6].kind == C_BEND && tr.calls[6].value == 1.5f && tr.calls[6].at == 32);
      CHECK(tr.calls[7].kind == C_ON && tr.calls[7].a == 64 && tr.calls[7].at == 32);
    }
  }
  /* A tick that writes splits a block no event splits; one that writes
   * nothing does not. A bridge with no sequencer runs only the hook. */
  fm1_seq_host_init(&bare, NULL, NULL, 0);
  for (round = 0; round < 2; ++round) {
    const uint64_t before = bare.splits;
    memset(&tr, 0, sizeof(tr));
    memset(&fh, 0, sizeof(fh));
    tr.block = block;
    fh.write = round == 0;
    fm1_seq_host_dispatch_ticks(&bare, BLOCK, block, &sink, &hook);
    CHECK(tr.rendered == BLOCK && !tr.bad_piece && fh.ticks == 2 && fh.events == 0);
    CHECK(tr.pieces == (round == 0 ? 2u : 1u) && bare.splits - before == (round == 0 ? 1u : 0u));
  }
}

/* Several sound units (fm1_seq_host_dispatch_slots): tracks 0..3 routed to
 * slots 0, 1, 2 (empty) and 7 (past the last of three). Slot 0 plays
 * kEngine and slot 1 kOther; track 1's Timbre lane, cached on kEngine's uid
 * (40), resolves on kOther to its own (5, index 1). */
static void slots(void) {
  static trace_t ta, tb;
  static float block_a[2 * BLOCK], block_b[2 * BLOCK], block_c[2 * BLOCK];
  static const char setup[] = "alabel 0 0 synth:Timbre;alabel 1 0 synth:Timbre";
  fm1_seq_ev_t ev[16], scratch[16];
  fm1_seq_host_t h;
  fm1_seq_sink_t sa, sb;
  fm1_seq_slot_t slot[3];
  fm1_seq_t *s = make(mem_text);
  uint32_t n = 0;
  memset(&sa, 0, sizeof(sa));               /* pitch_bend NULL: no hook here */
  sa.ctx = &ta;
  sa.engine = &kEngine;
  sa.render = t_render;
  sa.note_on = t_on;
  sa.note_off = t_off;
  sa.set_param = t_param;
  sb = sa;
  sb.ctx = &tb;
  sb.engine = &kOther;
  slot[0].sink = &sa;
  slot[0].block = block_a;
  slot[1].sink = &sb;
  slot[1].block = block_b;
  slot[2].sink = NULL;                     /* an empty sound unit */
  slot[2].block = block_c;
  CHECK(fm1_seq_apply_text(s, setup, sizeof(setup) - 1u, scratch, 16) == 0);
  fm1_seq_set_route(s, 0, FM1_SEQ_ROUTE_ENGINE, 0);
  fm1_seq_set_route(s, 1, FM1_SEQ_ROUTE_ENGINE, 1);
  fm1_seq_set_route(s, 2, FM1_SEQ_ROUTE_ENGINE, 2);
  fm1_seq_set_route(s, 3, FM1_SEQ_ROUTE_ENGINE, 7);
  fm1_seq_host_init(&h, s, ev, 16);
  fm1_seq_host_bind(&h, &kEngine);
  CHECK(h.lane_uid[1][0] == 40);
#define EV(fr, k, t, aa, bb)                                                    do {                                                                            ev[n].tick = 0; ev[n].frame = (fr); ev[n].kind = (k); ev[n].track = (t);      ev[n].a = (aa); ev[n].b = (bb); ++n;                                        } while (0)
  EV(0, FM1_SEQ_EV_NOTE_ON, 0, 60, 100);   /* slot 0 */
  EV(8, FM1_SEQ_EV_NOTE_ON, 1, 64, 90);    /* slot 1 */
  EV(8, FM1_SEQ_EV_LOCK, 1, 0, 127);       /* slot 1: kOther's Timbre, index 1 */
  EV(16, FM1_SEQ_EV_NOTE_ON, 2, 67, 80);   /* slot 2, empty: nothing, no split */
  EV(24, FM1_SEQ_EV_NOTE_ON, 3, 72, 80);   /* slot 7, past the last: nothing */
  EV(32, FM1_SEQ_EV_LOCK, 0, 0, 0);        /* slot 0: kEngine's Timbre, index 0 */
  EV(40, FM1_SEQ_EV_NOTE_OFF, 1, 64, 0);   /* slot 1 */
#undef EV
  h.n = n;
  memset(&ta, 0, sizeof(ta));
  memset(&tb, 0, sizeof(tb));
  ta.block = block_a;
  tb.block = block_b;
  fm1_seq_host_dispatch_slots(&h, BLOCK, slot, 3);
  CHECK(h.n == 0 && h.engine == &kEngine);
  CHECK(ta.rendered == BLOCK && tb.rendered == BLOCK && !ta.bad_piece && !tb.bad_piece);
  CHECK(ta.pieces == 2u && tb.pieces == 3u && h.splits == 3u);
  CHECK(h.notes_to_engine == 2u && h.locks_to_engine == 2u && h.locks_refused == 0u);
  CHECK(ta.n == 2u && tb.n == 3u);
  if (ta.n == 2u) {
    CHECK(ta.calls[0].kind == C_ON && ta.calls[0].a == 60 && ta.calls[0].at == 0);
    CHECK(ta.calls[1].kind == C_PARAM && ta.calls[1].index == 0 && ta.calls[1].value == 0.0f &&
          ta.calls[1].at == 32);
  }
  if (tb.n == 3u) {
    CHECK(tb.calls[0].kind == C_ON && tb.calls[0].a == 64 && tb.calls[0].at == 8);
    CHECK(tb.calls[1].kind == C_PARAM && tb.calls[1].index == 1 && tb.calls[1].value == 1.0f &&
          tb.calls[1].at == 8);
    CHECK(tb.calls[2].kind == C_OFF && tb.calls[2].a == 64 && tb.calls[2].at == 40);
  }
  /* The one-sink dispatch plays every engine-routed track on its sink,
   * whatever the slot: four note-ons and both locks on kEngine. */
  h.n = n;
  memset(&ta, 0, sizeof(ta));
  ta.block = block_a;
  fm1_seq_host_dispatch(&h, BLOCK, block_a, &sa);
  CHECK(h.notes_to_engine == 6u && ta.n == 7u && ta.pieces == 6u);
}

/* dispatch_slots_ticks: slot 0 kEngine, slot 1 kOther, slot 2 empty;
 * tracks 0, 1 and 2 routed to them. The fake hook's tick at 32 writes
 * slot 0's Timbre, a bend on slot 0 and slot 1's index 1. */
typedef struct {
  uint32_t ticks, events, to_engine, locks[3];
  fm1_seq_hook_write_t w[3];
} slots_hook_t;

static uint32_t sh_begin(void *ctx, uint32_t frames, const fm1_engine_t *e, uint32_t bpm, int playing) {
  (void)ctx;
  (void)frames;
  (void)bpm;
  (void)playing;
  CHECK(e == &kEngine);                    /* slot 0's engine */
  return 0;
}
static void sh_event(void *ctx, uint32_t frame, const fm1_seq_ev_t *e, int to_engine) {
  slots_hook_t *f = (slots_hook_t *)ctx;
  (void)frame;
  (void)e;
  ++f->events;
  f->to_engine += (uint32_t)(to_engine != 0);
}
static float sh_lock(void *ctx, uint16_t index, float v) {
  (void)ctx;
  (void)index;
  CHECK(0);                                /* lock_slot is there: never this */
  return v;
}
static float sh_lock_slot(void *ctx, unsigned slot, uint16_t index, float v) {
  slots_hook_t *f = (slots_hook_t *)ctx;
  (void)index;
  if (slot < 3) ++f->locks[slot];
  return v + 0.5f;
}
static uint32_t sh_tick(void *ctx, uint32_t frame, const fm1_seq_hook_write_t **w, uint32_t *next) {
  slots_hook_t *f = (slots_hook_t *)ctx;
  ++f->ticks;
  *next = frame + 32u;
  memset(f->w, 0, sizeof(f->w));
  f->w[0].index = 0;                       /* slot 0: Timbre */
  f->w[0].value = 0.25f;
  f->w[1].bend = 1;                        /* slot 0: a bend */
  f->w[1].value = 2.0f;
  f->w[2].index = 1;                       /* slot 1: kOther's index 1 */
  f->w[2].slot = 1;
  f->w[2].value = 0.75f;
  *w = f->w;
  return frame == 32u ? 3u : 0u;
}

static void hooked_slots(void) {
  static trace_t ta, tb;
  static float block_a[2 * BLOCK], block_b[2 * BLOCK], block_c[2 * BLOCK];
  static const char setup[] = "alabel 1 0 synth:Timbre";
  fm1_seq_ev_t ev[16], scratch[16];
  fm1_seq_host_t h;
  fm1_seq_sink_t sa, sb;
  fm1_seq_slot_t slot[3];
  fm1_seq_hook_t hook;
  slots_hook_t fh;
  fm1_seq_t *s = make(mem_text);
  uint32_t n = 0;
  memset(&sa, 0, sizeof(sa));
  sa.ctx = &ta;
  sa.engine = &kEngine;
  sa.render = t_render;
  sa.note_on = t_on;
  sa.note_off = t_off;
  sa.set_param = t_param;
  sa.pitch_bend = t_bend;
  sb = sa;
  sb.ctx = &tb;
  sb.engine = &kOther;
  slot[0].sink = &sa;
  slot[0].block = block_a;
  slot[1].sink = &sb;
  slot[1].block = block_b;
  slot[2].sink = NULL;
  slot[2].block = block_c;
  memset(&hook, 0, sizeof(hook));
  hook.ctx = &fh;
  hook.begin = sh_begin;
  hook.event = sh_event;
  hook.lock = sh_lock;
  hook.tick = sh_tick;
  hook.lock_slot = sh_lock_slot;
  CHECK(fm1_seq_apply_text(s, setup, sizeof(setup) - 1u, scratch, 16) == 0);
  fm1_seq_set_route(s, 0, FM1_SEQ_ROUTE_ENGINE, 0);
  fm1_seq_set_route(s, 1, FM1_SEQ_ROUTE_ENGINE, 1);
  fm1_seq_set_route(s, 2, FM1_SEQ_ROUTE_ENGINE, 2);
  fm1_seq_host_init(&h, s, ev, 16);
#define EV(fr, k, t, aa, bb)                                                  \
  do {                                                                        \
    ev[n].tick = 0; ev[n].frame = (fr); ev[n].kind = (k); ev[n].track = (t);  \
    ev[n].a = (aa); ev[n].b = (bb); ++n;                                      \
  } while (0)
  EV(0, FM1_SEQ_EV_NOTE_ON, 0, 60, 100);   /* slot 0 */
  EV(8, FM1_SEQ_EV_NOTE_ON, 1, 64, 90);    /* slot 1 */
  EV(16, FM1_SEQ_EV_NOTE_ON, 2, 67, 80);   /* slot 2, empty: fed, not played */
  EV(32, FM1_SEQ_EV_NOTE_OFF, 1, 64, 0);   /* slot 1, at the tick's frame: before it */
  EV(32, FM1_SEQ_EV_LOCK, 1, 0, 127);      /* slot 1: kOther's Timbre (index 1), 1.0 + 0.5 */
  EV(32, FM1_SEQ_EV_NOTE_ON, 0, 62, 90);   /* slot 0: after the tick (M6) */
#undef EV
  h.n = n;
  memset(&ta, 0, sizeof(ta));
  memset(&tb, 0, sizeof(tb));
  memset(&fh, 0, sizeof(fh));
  ta.block = block_a;
  tb.block = block_b;
  fm1_seq_host_dispatch_slots_ticks(&h, BLOCK, slot, 3, &hook);
  CHECK(h.n == 0 && fh.ticks == 2 && fh.events == n && fh.to_engine == 5);
  CHECK(fh.locks[1] == 1 && fh.locks[0] == 0);
  CHECK(ta.rendered == BLOCK && tb.rendered == BLOCK && !ta.bad_piece && !tb.bad_piece);
  CHECK(ta.n == 4u && tb.n == 4u && ta.pieces == 2u && tb.pieces == 3u);
  if (ta.n == 4u) {                       /* on; at 32 the tick's two writes, then the on */
    CHECK(ta.calls[0].kind == C_ON && ta.calls[0].a == 60 && ta.calls[0].at == 0);
    CHECK(ta.calls[1].kind == C_PARAM && ta.calls[1].index == 0 && ta.calls[1].value == 0.25f &&
          ta.calls[1].at == 32);
    CHECK(ta.calls[2].kind == C_BEND && ta.calls[2].value == 2.0f && ta.calls[2].at == 32);
    CHECK(ta.calls[3].kind == C_ON && ta.calls[3].a == 62 && ta.calls[3].at == 32);
  }
  if (tb.n == 4u) {                       /* on at 8; at 32 off, the lock, then the tick's write */
    CHECK(tb.calls[0].kind == C_ON && tb.calls[0].a == 64 && tb.calls[0].at == 8);
    CHECK(tb.calls[1].kind == C_OFF && tb.calls[1].at == 32);
    CHECK(tb.calls[2].kind == C_PARAM && tb.calls[2].index == 1 && tb.calls[2].value == 1.5f &&
          tb.calls[2].at == 32);
    CHECK(tb.calls[3].kind == C_PARAM && tb.calls[3].index == 1 && tb.calls[3].value == 0.75f &&
          tb.calls[3].at == 32);
  }
  /* No hook: dispatch_slots, slot after slot, with nothing of the hook. */
  h.n = n;
  memset(&ta, 0, sizeof(ta));
  memset(&tb, 0, sizeof(tb));
  ta.block = block_a;
  tb.block = block_b;
  fm1_seq_host_dispatch_slots_ticks(&h, BLOCK, slot, 3, NULL);
  CHECK(ta.n == 2u && tb.n == 3u && ta.pieces == 2u && tb.pieces == 3u);
}

/* A buffer of none: every event counted as dropped, nothing written. */
static void no_buffer(void) {
  fm1_seq_host_t h;
  fm1_seq_stats_t st;
  uint32_t k;
  fm1_seq_host_init(&h, make(mem_text), NULL, 100);
  CHECK(h.cap == 0 && fm1_seq_host_room(&h) == 0);
  CHECK(fm1_seq_host_line(&h, "tog 0 0 60 100", 14) == 0);
  CHECK(fm1_seq_host_line(&h, "play", 4) == 0);
  for (k = 0; k < 20; ++k) CHECK(fm1_seq_host_advance(&h, BLOCK) == 0);
  fm1_seq_get_stats(h.seq, &st);
  CHECK(st.dropped_events > 0);
}

int main(void) {
  uint64_t events = 0, calls = 0, inside = 0;
  parsers_and_figures();
  value7_and_labels();
  inputs_and_dispatch(&events, &calls, &inside);
  hand_made_block();
  uids_and_refusals();
  hooked_block();
  slots();
  hooked_slots();
  no_buffer();
  printf("{\"ok\":%s,\"events\":%llu,\"sink_calls\":%llu,\"splits\":%llu}\n", failed ? "false" : "true",
         (unsigned long long)events, (unsigned long long)calls, (unsigned long long)inside);
  return failed ? 1 : 0;
}
