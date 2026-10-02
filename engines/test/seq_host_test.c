/* seq_host_test.c -- fm1-seq-host-test: the host bridge (fm1_seq_host.h)
 * where fm1-render does not reach it.
 *
 *   - Typed commands (host_cmd), realtime input (host_realtime) and live
 *     notes (host_note_in) give the same events and the same set as the
 *     text lines fm1-render applies (host_line).
 *   - Dispatch hands a sink every engine-routed note and lock at its own
 *     frame, in emission order, renders every frame of the block once, and
 *     counts a split for each piece that starts inside it.
 *   - The room figures, the realtime-line parser (length-bounded), lane
 *     labels and lock values.
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

/* A pretend engine: one FLOAT and one ENUM of 8 values. */
static const fm1_param_t kParams[] = {
  { "Timbre", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0 },
  { "Model", FM1_PARAM_ENUM, 0.0f, 7.0f, 0.0f, NULL, 0 },
};
static const fm1_engine_t kEngine = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND, "fake", "Fake", "", kParams, 2, 8,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
};

/* What the sink was asked to do, with the frame the block had reached. */
enum { C_ON = 1, C_OFF, C_PARAM };
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
  if (lr != t->block + 2u * t->rendered) t->bad_piece = 1;
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
 * notes from inside fm1_seq_realtime_in; MIDI clock follows it. */
typedef struct {
  uint32_t at;
  const char *op;
} step_t;

static const step_t kScript[] = {
  { 0, "tog 0 0 60 100 64 90" }, { 0, "tog 0 3 67 100" }, { 0, "tog 0 6 72 80" },
  { 0, "slen 0 0 15 -1 300" }, { 0, "tog 1 2 48 100" }, { 0, "route 1 1 0" },
  { 0, "alabel 0 0 synth:Timbre" }, { 0, "alabel 0 1 x:MODEL" },
  { 0, "alabel 0 2 synth:Nothing" }, { 0, "abase 0 0 10" }, { 0, "aset 0 0 2 90 1" },
  { 0, "aset 0 1 5 40 1" }, { 0, "aset 0 2 3 70 1" }, { 0, "swing 62" }, { 0, "play" },
  { 300, "rec 0" }, { 330, "non 0 62 87" }, { 370, "nof 0 62" }, { 1000, "rt FA" },
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
  uint32_t k, i, rt_events = 0;
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
  fm1_seq_set_route(a.seq, 0, FM1_SEQ_ROUTE_ENGINE, 0);
  fm1_seq_set_route(b.seq, 0, FM1_SEQ_ROUTE_ENGINE, 0);
  *n_events = *n_calls = *n_inside = 0;
  for (k = 0; k < BLOCKS; ++k) {
    uint32_t na, nb;
    for (; next < sizeof(kScript) / sizeof(kScript[0]) && kScript[next].at == k; ++next) {
      apply_both(&a, &b, kScript[next].op);
    }
    if (k >= CLOCK_FROM && k < CLOCK_TO && (k - CLOCK_FROM) % 16u == 0) apply_both(&a, &b, "rt F8");
    if (k == 1000) rt_events = a.n;
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
        if (ti.route_kind != FM1_SEQ_ROUTE_ENGINE) continue;
        if (e->kind == FM1_SEQ_EV_LOCK) {
          p = fm1_seq_lane_param(&kEngine, fm1_seq_lane_label(a.seq, e->track, e->a));
          if (p < 0) continue;
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
  CHECK(b.notes_to_engine == 0 && b.splits == 0);    /* a NULL sink plays nothing */
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
  inputs_and_dispatch(&events, &calls, &inside);
  no_buffer();
  printf("{\"ok\":%s,\"events\":%llu,\"sink_calls\":%llu,\"splits\":%llu}\n", failed ? "false" : "true",
         (unsigned long long)events, (unsigned long long)calls, (unsigned long long)inside);
  return failed ? 1 : 0;
}
