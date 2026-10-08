/* fm1_edit_check.c -- fm1-sim-render's checks of the edit layer
 * (sim/web/src/fm1_edit.h, stage ED1; notes/2026-10-06-web-editor.md §17):
 *
 *   --edit-check        every parameter's text round trip (fm1_param_parse
 *                       of fm1_look_value, every knob step of every engine,
 *                       effect, MIDI effect, modulation kind and the host);
 *                       every refusal code an edit can meet, with the state
 *                       hash and the ring unchanged by each but a cable's;
 *                       the change ring's sources and its overflow; the
 *                       panel's gestures replayed from the ring as editor
 *                       ops to the same state; the verbs; the view and knob
 *                       map; telemetry's layout, rate and rows, and that it
 *                       leaves the audio alone. One JSON line; exit 0 when
 *                       all of it holds.
 *   --edit-run S DIR    a script of timed edits and panel gestures, as
 *                       test/edit.mjs plays it to the WebAssembly module:
 *                       DIR/edit.txt (each line's verdicts, then the ring,
 *                       the view and the state hash), DIR/screen.raw and
 *                       DIR/audio.f32.
 *
 * C99. MIT licence, like the rest of this repository.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "fm1_app.h"
#include "fm1_app_state.h"
#include "fm1_edit.h"
#include "fm1_engine_meta.h"
#include "fm1_look.h"
#include "fm1_modules.h"
#include "fm1_panel.h"
#include "fm1_refusal.h"

void fm1_edit_check_put(void *ctx, const char *b, size_t n);
const char *fm1_edit_check_buf(void);

static fm1_app_t g_a;
static fm1_edit_t g_e;
static int g_failed;
static char g_why[2048];

#define CHECK(c) do { if (!(c)) fail(__LINE__, #c); } while (0)
static void fail(int line, const char *what) {
  size_t n = strlen(g_why);
  if (!g_failed) snprintf(g_why + n, sizeof g_why - n, "line %d: %s", line, what);
  fprintf(stderr, "fm1_edit_check.c:%d: %s\n", line, what);
  ++g_failed;
}

static void fresh(float rate) {
  fm1_app_init(&g_a, rate);
  fm1_edit_attach(&g_a, &g_e, 0);
  fm1_app_default_chain(&g_a);
}

static void render(int blocks) {
  for (int k = 0; k < blocks; ++k) fm1_app_render(&g_a, FM1_APP_MAX_FRAMES);
}

static int edit_line(const char *line, uint16_t tag, int8_t *code) {
  uint8_t b[FM1_EDIT_REC_BYTES];
  int8_t c = -1;
  if (!fm1_edit_parse_text(line, b)) return -1;
  fm1_edit_packed(&g_a, b, 1, FM1_EDIT_EDITOR, tag, &c);
  if (code) *code = c;
  return c;
}

/* ---- the text round trip -------------------------------------------------------- */

static float step(const fm1_param_t *p, float v) {
  if (fm1_param_is_log(p)) {
    float u = fm1_param_pos(p, v);
    u = u + 0.01f;
    return fm1_param_at(p, u);
  }
  v = v + fm1_param_detent(p);
  if (p->type == FM1_PARAM_ENUM) v = floorf(v + 0.5f);
  return fm1_param_clamp(p, v);
}

static unsigned g_rt_params, g_rt_steps, g_rt_same, g_rt_bad;
static char g_rt_first[160];

static void round_trip(const char *id, const fm1_param_t *ps, unsigned n) {
  for (unsigned i = 0; i < n; ++i) {
    const fm1_param_t *p = &ps[i];
    char prev[48] = "";
    float v = p->min;
    if (!(p->max >= p->min)) continue;
    ++g_rt_params;
    for (unsigned k = 0; k < 2000; ++k) {
      char t[48], t2[48];
      float back = NAN;
      double tol;
      const char *dot;
      fm1_look_value(p, v, t, sizeof t);
      if (!fm1_param_parse(p, t, &back)) {
        t2[0] = 0;
      } else {
        fm1_look_value(p, back, t2, sizeof t2);
      }
      ++g_rt_steps;
      /* The same value as the screen shows it: a list's entry exactly, a
       * number to within half of its last printed digit (a step the
       * screen rounds to "100.0" reads back as 100, which prints "100"). */
      dot = strchr(t, '.');
      tol = 0.5 * pow(10.0, -(dot ? (double)strlen(dot + 1) : 0.0)) * 1.0001 + 1e-6 * fabs((double)v);
      if (p->type == FM1_PARAM_ENUM ? strcmp(t, t2) != 0 || back != floorf(v + 0.5f)
                                    : !(fabs((double)back - (double)v) <= tol) || back != fm1_param_clamp(p, back)) {
        if (!g_rt_bad) snprintf(g_rt_first, sizeof g_rt_first, "%s %s: %s -> %s", id, p->name, t, t2);
        ++g_rt_bad;
      }
      if (strcmp(t, prev) == 0) ++g_rt_same;   /* two knob steps the screen cannot tell apart */
      snprintf(prev, sizeof prev, "%s", t);
      if (v >= p->max) break;
      {
        const float next = step(p, v);
        if (!(next > v)) break;
        v = next;
      }
    }
  }
}

static void check_parse(void) {
  float v;
  const fm1_param_t *hz = NULL, *ms = NULL;
  for (size_t k = 0; k < fm1_engine_count; ++k) round_trip(fm1_engines[k]->id, fm1_engines[k]->params, fm1_engines[k]->n_params);
  for (size_t k = 0; k < fm1_midi_fx_count; ++k) {
    round_trip(fm1_midi_fxs[k]->engine.id, fm1_midi_fxs[k]->engine.params, fm1_midi_fxs[k]->engine.n_params);
  }
  for (size_t k = 0; k < fm1_mod_kind_count; ++k) round_trip(fm1_mod_kinds[k]->id, fm1_mod_kinds[k]->params, fm1_mod_kinds[k]->n_params);
  round_trip("host", fm1_mod_host_params, FM1_MOD_HOST_PARAMS);
  CHECK(g_rt_bad == 0);
  /* Typed forms the screen does not print: units, "k", the typographic
   * minus; and what is refused. */
  for (size_t k = 0; k < fm1_engine_count && (!hz || !ms); ++k) {
    for (unsigned i = 0; i < fm1_engines[k]->n_params; ++i) {
      const fm1_param_t *p = &fm1_engines[k]->params[i];
      if (!hz && p->unit == FM1_UNIT_HZ && p->max >= 2000.0f && p->min <= 1200.0f) hz = p;
      if (!ms && p->unit == FM1_UNIT_MS && p->max >= 1500.0f && p->min <= 1000.0f) ms = p;
    }
  }
  CHECK(hz && ms);
  if (hz) {
    CHECK(fm1_param_parse(hz, "1.2k", &v) && v == 1200.0f);
    CHECK(fm1_param_parse(hz, "1.2 kHz", &v) && v == 1200.0f);
    CHECK(fm1_param_parse(hz, " 1200 Hz ", &v) && v == 1200.0f);
    CHECK(!fm1_param_parse(hz, "12 dB", &v) && !fm1_param_parse(hz, "abc", &v) && !fm1_param_parse(hz, "", &v));
    CHECK(fm1_param_parse(hz, "1e9", &v) && v == hz->max);
    CHECK(!fm1_param_parse(hz, "nan", &v) && !fm1_param_parse(hz, "inf", &v));
  }
  if (ms) CHECK(fm1_param_parse(ms, "1 s", &v) && v == 1000.0f && fm1_param_parse(ms, "1000ms", &v) && v == 1000.0f);
  {
    static const fm1_param_t db = { "Gain", FM1_PARAM_FLOAT, -24.0f, 24.0f, 0.0f, NULL, 0, 1, 0, FM1_UNIT_DB, "GAIN" };
    CHECK(fm1_param_parse(&db, "\xe2\x88\x92" "6 dB", &v) && v == -6.0f);
    CHECK(fm1_param_parse(&db, "-6", &v) && v == -6.0f && fm1_param_parse(&db, "+3.5dB", &v) && v == 3.5f);
  }
}

/* ---- refusals ------------------------------------------------------------------- */

static unsigned g_codes[64];

static void reached(int code) {
  if (code > 0 && code < 64) g_codes[code] = 1;
}

/* A refusal changes nothing: the state's hash and the ring stay. */
static int refused_cleanly(const char *line, int want) {
  const uint32_t h = fm1_edit_state_hash(&g_a), gen = fm1_edit_gen(&g_a);
  int8_t code = 0;
  const int r = edit_line(line, 7, &code);
  const int ok = r == want && fm1_edit_state_hash(&g_a) == h && fm1_edit_gen(&g_a) == gen;
  if (ok) reached(want);
  else fprintf(stderr, "refusal: %s -> %d (want %d)\n", line, r, want);
  return ok;
}

static int biggest_sound(size_t *ram) {
  int best = -1;
  *ram = 0;
  for (size_t k = 0; k < fm1_engine_count; ++k) {
    const size_t r = fm1_engines[k]->kind == FM1_KIND_SOUND ? fm1_app_ram_of(fm1_engines[k]) : 0u;
    if (r > *ram) *ram = r, best = (int)k;
  }
  return best;
}

static void check_refusals(void) {
  char line[160];
  size_t ram;
  int big;
  fresh(44118.0f);
  render(4);
  CHECK(refused_cleanly("unit sound 0 0 no-such-engine", FM1_REFUSE_UNKNOWN));
  CHECK(refused_cleanly("unit mfx 0 0 no-such-effect", FM1_REFUSE_UNKNOWN));
  CHECK(refused_cleanly("module 0 no-such-kind", FM1_REFUSE_UNKNOWN));
  CHECK(refused_cleanly("unit sound 0 0 -", FM1_REFUSE_BAD));           /* Sound 1 is never empty */
  CHECK(refused_cleanly("unit sound 7 0 macro", FM1_REFUSE_BAD));
  CHECK(refused_cleanly("unit insert 0 0 macro", FM1_REFUSE_BAD));      /* a sound into an insert */
  CHECK(refused_cleanly("param sound 0 0 4000 0.5", FM1_REFUSE_BAD));   /* no such uid */
  CHECK(refused_cleanly("param sound 1 0 1 0.5", FM1_REFUSE_BAD));      /* an empty unit */
  CHECK(refused_cleanly("param sound 0 0 1 nan", FM1_REFUSE_BAD));
  CHECK(refused_cleanly("level 0 nan", FM1_REFUSE_BAD));
  CHECK(refused_cleanly("level 9 50", FM1_REFUSE_BAD));
  CHECK(refused_cleanly("on 0 2", FM1_REFUSE_BAD));
  CHECK(refused_cleanly("view rack pos=9", FM1_REFUSE_BAD));
  CHECK(refused_cleanly("view home sound=5", FM1_REFUSE_BAD));
  CHECK(refused_cleanly("swap sound 0 0 master 0 0", FM1_REFUSE_BAD));
  CHECK(refused_cleanly("swap master 0 0 master 0 0", FM1_REFUSE_BAD));
  CHECK(refused_cleanly("current 4", FM1_REFUSE_BAD));
  CHECK(refused_cleanly("cable 40 0 255 0 1 1 100 0", FM1_REFUSE_BAD));
  {
    /* A packed record of a type the layer does not take. */
    uint8_t b[FM1_EDIT_REC_BYTES] = { FM1_REC_DX7 };
    int8_t c = 0;
    const uint32_t h = fm1_edit_state_hash(&g_a);
    fm1_edit_packed(&g_a, b, 1, FM1_EDIT_EDITOR, 1, &c);
    CHECK(c == FM1_REFUSE_BAD && fm1_edit_state_hash(&g_a) == h);
  }
  /* RAM: the largest sound engine twice, and the arpeggiator past it. */
  big = biggest_sound(&ram);
  CHECK(big >= 0 && 2u * ram > FM1_APP_RAM_BUDGET);
  snprintf(line, sizeof line, "unit sound 0 0 %s", fm1_engines[big]->id);
  CHECK(edit_line(line, 2, NULL) == 0);
  snprintf(line, sizeof line, "unit sound 1 0 %s", fm1_engines[big]->id);
  CHECK(refused_cleanly(line, FM1_REFUSE_RAM));
  /* NO_ROOM: the rack's eight positions and the matrix's 32 slots. */
  for (int k = 0; k < 9; ++k) edit_line("module any lfo", 3, NULL);
  CHECK(refused_cleanly("module any lfo", FM1_REFUSE_NO_ROOM));
  for (int k = 0; k < 33; ++k) edit_line("cable any 64 255 0 0 1 0 0", 4, NULL);   /* off cables */
  CHECK(refused_cleanly("cable any 64 255 0 1 1 1000 0", FM1_REFUSE_NO_ROOM));
  /* RATE: at 96 kHz the Plaits-based engines refuse the host. */
  fresh(96000.0f);
  CHECK(refused_cleanly("unit sound 1 0 macro", FM1_REFUSE_RATE));
  /* ARENA: a module that does not fit the runtime's arena, if any kind is
   * that large; an effect larger than an insert's arena at 96 kHz. */
  for (size_t k = 0; k < fm1_engine_count && !g_codes[FM1_REFUSE_ARENA]; ++k) {
    if (fm1_engines[k]->kind != FM1_KIND_AUDIO_FX) continue;
    snprintf(line, sizeof line, "unit insert 0 0 %s", fm1_engines[k]->id);
    if (edit_line(line, 5, NULL) == FM1_REFUSE_ARENA) reached(FM1_REFUSE_ARENA);
  }
}

/* A cable's verdicts: every reason the planner gives, from the layer. */
static void check_cable_codes(void) {
  char line[160];
  fresh(44118.0f);
  CHECK(edit_line("cable 0 200 255 0 1 1 1000 0", 1, NULL) == FM1_REFUSE_NO_SOURCE);   /* past the sources */
  reached(FM1_REFUSE_NO_SOURCE);
  CHECK(edit_line("cable 0 0 255 4 1 1 1000 0", 1, NULL) == FM1_REFUSE_UNIT_RESERVED);
  reached(FM1_REFUSE_UNIT_RESERVED);
  CHECK(edit_line("cable 0 0 255 0 1 4000 1000 0", 1, NULL) == FM1_REFUSE_NO_DEST);
  reached(FM1_REFUSE_NO_DEST);
  /* Every engine and effect, every parameter, a cable from LFO1 into it,
   * plain and per voice. */
  const fm1_engine_t *poly = NULL;
  unsigned poly_n = 0;
  for (size_t k = 0; k < fm1_engine_count; ++k) {
    const fm1_engine_t *e = fm1_engines[k];
    const int sound = e->kind == FM1_KIND_SOUND;
    unsigned voice_ok = 0;
    snprintf(line, sizeof line, sound ? "unit sound 0 0 %s" : "unit insert 0 0 %s", e->id);
    if (edit_line(line, 1, NULL) != 0) continue;
    for (unsigned i = 0; i < e->n_params; ++i) {
      for (int voice = 0; voice < 2; ++voice) {
        int8_t c = 0;
        snprintf(line, sizeof line, "cable 1 64 255 %u %d %u 8192 0", sound ? 0u : 20u,
                 voice ? 0x81 : 0x01, e->params[i].uid);
        edit_line(line, 1, &c);
        reached(c);
        voice_ok += voice && c == 0;
      }
    }
    if (voice_ok > poly_n) poly = e, poly_n = voice_ok;
    edit_line("cable 1 64 255 0 0 0 0 0", 1, NULL);
    if (!sound) edit_line("unit insert 0 0 -", 1, NULL);
  }
  /* Every modulation kind at position 2, every parameter, from LFO1. */
  for (size_t k = 0; k < fm1_mod_kind_count; ++k) {
    snprintf(line, sizeof line, "module 1 %s", fm1_mod_kinds[k]->id);
    if (edit_line(line, 1, NULL) != 0) continue;
    for (unsigned i = 0; i < fm1_mod_kinds[k]->n_params; ++i) {
      int8_t c = 0;
      snprintf(line, sizeof line, "cable 1 64 255 9 1 %u 8192 0", fm1_mod_kinds[k]->params[i].uid);
      edit_line(line, 1, &c);
      reached(c);
    }
  }
  edit_line("cable 1 64 255 0 0 0 0 0", 1, NULL);
  /* VOICE_FULL: more per-voice destinations than the runtime takes, on the
   * engine with the most. */
  CHECK(poly != NULL);
  if (poly) {
    snprintf(line, sizeof line, "unit sound 0 0 %s", poly->id);
    CHECK(edit_line(line, 1, NULL) == 0);
  }
  {
    const fm1_engine_t *e = fm1_app_unit_engine(&g_a, 0);
    unsigned n = 0;
    for (unsigned i = 0; e && i < e->n_params && n < 32; ++i) {
      int8_t c = 0;
      snprintf(line, sizeof line, "cable %u 64 255 0 129 %u 8192 0", 2 + n, e->params[i].uid);
      edit_line(line, 1, &c);
      reached(c);
      if (c == 0 || c == FM1_REFUSE_VOICE_FULL) ++n;
    }
  }
}

/* ---- the ring ------------------------------------------------------------------- */

static fm1_change_t g_ch[FM1_EDIT_RING];

static void check_ring(void) {
  uint32_t gen, n;
  int8_t c;
  fresh(44118.0f);
  render(2);
  gen = fm1_edit_gen(&g_a);
  fm1_app_encoder(&g_a, FM1_ENC_KNOB1, 3);                  /* the panel */
  edit_line("level 2 40", 77, &c);                          /* the editor */
  fm1_app_select(&g_a, 1, fm1_app_find("comp"));            /* the page's menu */
  n = fm1_edit_changes(&g_a, gen, g_ch, FM1_EDIT_RING);
  CHECK(n == 3);
  if (n == 3) {
    CHECK(g_ch[0].src == FM1_EDIT_PANEL && g_ch[0].tag == 0 && g_ch[0].rec[0] == FM1_REC_PARAM);
    CHECK(g_ch[1].src == FM1_EDIT_EDITOR && g_ch[1].tag == 77 && g_ch[1].rec[0] == FM1_REC_LEVEL);
    CHECK(g_ch[2].src == FM1_EDIT_HOST && g_ch[2].rec[0] == FM1_REC_UNIT);
    CHECK(g_ch[0].gen == gen + 1 && g_ch[2].gen == gen + 3);
  }
  /* A load: one LOADED entry, source LOAD, whatever it changed. */
  {
    static uint8_t buf[FM1_STATE_BIN_MAX];
    uint32_t len = 0;
    fm1_app_state_mem_t mem;
    fm1_app_state_report_t rep;
    fm1_app_load_opts_t o;
    fm1_state_report_t r;
    /* the project as it is, saved and loaded back */
    CHECK(fm1_app_state_save(&g_a, FM1_STATE_PROJECT, 0, 1, fm1_edit_check_put, &len, &r));
    CHECK(len <= sizeof buf);
    memcpy(buf, fm1_edit_check_buf(), len);
    mem.b = buf;
    mem.n = len;
    fm1_app_load_opts_init(&o);
    o.flags = FM1_APP_LOAD_QUIET;
    gen = fm1_edit_gen(&g_a);
    CHECK(fm1_app_state_load(&g_a, fm1_app_state_mem_read, &mem, len, &o, &rep) == 1);
    n = fm1_edit_changes(&g_a, gen, g_ch, FM1_EDIT_RING);
    CHECK(n == 1 && g_ch[0].src == FM1_EDIT_LOAD && g_ch[0].rec[0] == FM1_EDIT_LOADED);
  }
  /* Overflow: a reader more than a ring behind resyncs; one inside reads. */
  gen = fm1_edit_gen(&g_a);
  for (int k = 0; k < (int)FM1_EDIT_RING + 20; ++k) {
    char line[64];
    snprintf(line, sizeof line, "level 0 %d", k % 2 ? 50 : 60);
    edit_line(line, (uint16_t)k, NULL);
  }
  CHECK(fm1_edit_changes(&g_a, gen, g_ch, FM1_EDIT_RING) == FM1_EDIT_RESYNC);
  n = fm1_edit_changes(&g_a, fm1_edit_gen(&g_a) - 10, g_ch, FM1_EDIT_RING);
  CHECK(n == 10 && g_ch[9].gen == fm1_edit_gen(&g_a) && g_ch[9].tag == FM1_EDIT_RING + 19);
  CHECK(fm1_edit_changes(&g_a, fm1_edit_gen(&g_a), g_ch, FM1_EDIT_RING) == 0);
}

/* ---- parity of hands: the panel's changes, replayed as editor ops ---------------- */

static void normal_view(void) { edit_line("view home sound=1 page=1", 0, NULL); }

static unsigned g_hands;
static unsigned g_lock_blocks, g_sweeps;

static void hands(void (*gesture)(void)) {
  static fm1_change_t panel[FM1_EDIT_RING], editor[FM1_EDIT_RING];
  uint32_t gen, np, ne, h_panel, h_editor;
  fresh(44118.0f);
  render(2);
  gen = fm1_edit_gen(&g_a);
  gesture();
  render(80);                                   /* a picker commits after a second */
  np = fm1_edit_changes(&g_a, gen, panel, FM1_EDIT_RING);
  normal_view();
  h_panel = fm1_edit_state_hash(&g_a);
  fresh(44118.0f);
  render(2);
  gen = fm1_edit_gen(&g_a);
  for (uint32_t i = 0; i < np && np != FM1_EDIT_RESYNC; ++i) {
    int8_t c = 0;
    CHECK(panel[i].src == FM1_EDIT_PANEL);
    fm1_edit_packed(&g_a, panel[i].rec, 1, FM1_EDIT_EDITOR, (uint16_t)i, &c);
    CHECK(c == 0);
  }
  render(80);
  ne = fm1_edit_changes(&g_a, gen, editor, FM1_EDIT_RING);
  normal_view();
  h_editor = fm1_edit_state_hash(&g_a);
  if (!(np > 0 && np != FM1_EDIT_RESYNC && ne == np && h_panel == h_editor)) {
    fprintf(stderr, "hands %u: panel %u entries, editor %u, hashes %08x %08x\n", g_hands, np, ne, h_panel, h_editor);
    for (uint32_t i = 0; i < np && np != FM1_EDIT_RESYNC; ++i) {
      char t[160];
      fm1_edit_rec_text(panel[i].rec, t, sizeof t);
      fprintf(stderr, "  panel %s\n", t);
    }
    for (uint32_t i = 0; i < ne && ne != FM1_EDIT_RESYNC; ++i) {
      char t[160];
      fm1_edit_rec_text(editor[i].rec, t, sizeof t);
      fprintf(stderr, "  editor %s\n", t);
    }
  }
  CHECK(np > 0 && np != FM1_EDIT_RESYNC && ne == np && h_panel == h_editor);
  for (uint32_t i = 0; i < np && ne == np; ++i) {
    CHECK(editor[i].src == FM1_EDIT_EDITOR && memcmp(editor[i].rec, panel[i].rec, FM1_EDIT_REC_BYTES) == 0);
  }
  ++g_hands;
}

static void g_knobs(void) {
  for (int k = 0; k < 4; ++k) fm1_app_encoder(&g_a, FM1_ENC_KNOB1 + k, 5 - 3 * k);
  fm1_app_encoder(&g_a, FM1_ENC_SELECT, 1);
  fm1_app_encoder(&g_a, FM1_ENC_KNOB2, 7);
}
static void g_preset(void) { fm1_app_encoder(&g_a, FM1_ENC_PRESETS, 2); }
static void g_mix(void) {
  fm1_app_button(&g_a, FM1_BTN_FX, 1), fm1_app_button(&g_a, FM1_BTN_FX, 0);
  fm1_app_encoder(&g_a, FM1_ENC_SELECT, -1);                                /* M1 to the Mix */
  fm1_app_encoder(&g_a, FM1_ENC_KNOB1, -20);
  fm1_app_encoder(&g_a, FM1_ENC_KNOB3, -5);
}
static void g_swap(void) {
  fm1_app_button(&g_a, FM1_BTN_FX, 1), fm1_app_button(&g_a, FM1_BTN_FX, 0);   /* M1 */
  fm1_app_encoder(&g_a, FM1_ENC_ALGORITHM, 2);                              /* an effect */
  fm1_app_button(&g_a, FM1_BTN_SEL, 1), fm1_app_button(&g_a, FM1_BTN_SEL, 0);
  fm1_app_encoder(&g_a, FM1_ENC_SELECT, 1);                                 /* to M2 */
}
static void g_current(void) {
  fm1_app_button(&g_a, FM1_BTN_SEQ, 1);
  fm1_app_encoder(&g_a, FM1_ENC_PRESETS, 1);
  fm1_app_button(&g_a, FM1_BTN_SEQ, 0);
}
static void g_arp(void) {
  fm1_app_button(&g_a, FM1_BTN_ARP, 1), fm1_app_button(&g_a, FM1_BTN_ARP, 0);
  fm1_app_encoder(&g_a, FM1_ENC_KNOB1, 2);
  fm1_app_encoder(&g_a, FM1_ENC_KNOB2, 1);
}
static void g_rack(void) {
  fm1_app_button(&g_a, FM1_BTN_LFO, 1), fm1_app_button(&g_a, FM1_BTN_LFO, 0);
  fm1_app_encoder(&g_a, FM1_ENC_KNOB1, 9);
  fm1_app_encoder(&g_a, FM1_ENC_KNOB2, -4);
}

/* A sweep: runs of the families above with random deltas, in random order
 * (the note's §17 "parity of hands": the editor's op and the panel gesture
 * give the same state hash and the same ring entries). The seed is the
 * sweep's number, so a failure names the run that found it. */
static uint32_t g_sweep_seed, g_srng;
static uint32_t srnd(void) {                       /* its own stream: the fuzz below keeps its own */
  g_srng = g_srng * 1664525u + 1013904223u;
  return g_srng >> 8;
}
static int g_d(int span) { return (int)(srnd() % (unsigned)(2 * span + 1)) - span; }
static void g_sweep(void) {
  g_srng = 0x9E3779B9u * (g_sweep_seed + 1u);
  fm1_app_encoder(&g_a, FM1_ENC_KNOB1, 1 + (int)(srnd() % 9));          /* at least one change */
  for (int n = 1 + (int)(srnd() % 3); n > 0; --n) {
    switch (srnd() % 6) {
      case 0:
        for (int k = 0; k < 4; ++k) fm1_app_encoder(&g_a, FM1_ENC_KNOB1 + k, g_d(8));
        break;
      case 1:
        fm1_app_encoder(&g_a, FM1_ENC_SELECT, g_d(1));
        fm1_app_encoder(&g_a, FM1_ENC_KNOB2, g_d(9));
        break;
      case 2:
        fm1_app_button(&g_a, FM1_BTN_FX, 1), fm1_app_button(&g_a, FM1_BTN_FX, 0);
        fm1_app_encoder(&g_a, FM1_ENC_KNOB1, g_d(20));
        fm1_app_encoder(&g_a, FM1_ENC_KNOB3, g_d(6));
        break;
      case 3:
        fm1_app_button(&g_a, FM1_BTN_ARP, 1), fm1_app_button(&g_a, FM1_BTN_ARP, 0);
        fm1_app_encoder(&g_a, FM1_ENC_KNOB1, g_d(3));
        fm1_app_encoder(&g_a, FM1_ENC_KNOB2, g_d(2));
        break;
      case 4:
        fm1_app_button(&g_a, FM1_BTN_LFO, 1), fm1_app_button(&g_a, FM1_BTN_LFO, 0);
        fm1_app_encoder(&g_a, FM1_ENC_KNOB1, g_d(9));
        fm1_app_encoder(&g_a, FM1_ENC_KNOB2, g_d(5));
        break;
      default:
        fm1_app_encoder(&g_a, FM1_ENC_KNOB4, g_d(12));
        fm1_app_encoder(&g_a, FM1_ENC_KNOB3, g_d(12));
        break;
    }
  }
}

/* ---- a lock playing moves no base ------------------------------------------------ */

/* The note's §7 ("heard, not set") and §17 (sync): the start chain's demo
 * pattern locks a parameter; played for a few bars, every unit's every
 * parameter reads the value it had, and the ring holds no parameter write. */
static float g_base[FM1_APP_UNITS][64];
static void check_locks(void) {
  static fm1_change_t ring[FM1_EDIT_RING];
  uint32_t gen, n, writes = 0;
  float peak = 0.0f;
  fresh(44118.0f);
  render(4);
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    const fm1_engine_t *e = fm1_app_unit_engine(&g_a, u);
    for (unsigned i = 0; e && i < e->n_params && i < 64u; ++i) g_base[u][i] = fm1_app_get_param(&g_a, u, (int)i);
  }
  gen = fm1_edit_gen(&g_a);
  fm1_app_button(&g_a, FM1_BTN_PLAY, 1), fm1_app_button(&g_a, FM1_BTN_PLAY, 0);
  for (int k = 0; k < 900; ++k) {                          /* about 5 s: a bar and more of the demo */
    const float *o = fm1_app_render(&g_a, FM1_APP_MAX_FRAMES);
    for (unsigned j = 0; j < 2u * FM1_APP_MAX_FRAMES; ++j) peak = fabsf(o[j]) > peak ? fabsf(o[j]) : peak;
  }
  CHECK(peak > 0.01f);                                      /* it did play */
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    const fm1_engine_t *e = fm1_app_unit_engine(&g_a, u);
    for (unsigned i = 0; e && i < e->n_params && i < 64u; ++i) CHECK(fm1_app_get_param(&g_a, u, (int)i) == g_base[u][i]);
  }
  n = fm1_edit_changes(&g_a, gen, ring, FM1_EDIT_RING);
  for (uint32_t i = 0; i < n && n != FM1_EDIT_RESYNC; ++i) writes += ring[i].rec[0] == FM1_REC_PARAM;
  CHECK(n != FM1_EDIT_RESYNC && writes == 0);
  g_lock_blocks = 900;
}

/* ---- a project load that goes on playing (A/B) ----------------------------------- */

/* The editor's A/B puts the other project in while the transport runs; with FM1_APP_LOAD_KEEP_TRANSPORT
 * the transport is where it was (playing, the master tick, each track's clip and playhead), and
 * without it a project load starts from a stopped sequencer, as it always did. A stopped transport
 * stays stopped. */
static void check_transport(void) {
  static uint8_t buf[FM1_STATE_BIN_MAX];
  uint32_t len = 0;
  fm1_app_state_mem_t mem;
  fm1_app_state_report_t rep;
  fm1_app_load_opts_t o;
  fm1_state_report_t r;
  fm1_seq_info_t before, after;
  fm1_seq_track_info_t tb[FM1_SEQ_MAX_TRACKS], ta[FM1_SEQ_MAX_TRACKS];
  unsigned tracks, moving = 0;
  fresh(44118.0f);
  render(4);
  fm1_app_button(&g_a, FM1_BTN_PLAY, 1), fm1_app_button(&g_a, FM1_BTN_PLAY, 0);
  render(700);                                              /* a little over a second of the demo pattern */
  fm1_seq_get_info(fm1_app_seq(&g_a), &before);
  CHECK(before.playing && before.master_tick > 100);
  tracks = before.tracks < FM1_SEQ_MAX_TRACKS ? before.tracks : FM1_SEQ_MAX_TRACKS;
  for (unsigned t = 0; t < tracks; ++t) CHECK(fm1_seq_get_track(fm1_app_seq(&g_a), (uint8_t)t, &tb[t]));
  CHECK(fm1_app_state_save(&g_a, FM1_STATE_PROJECT, 0, 1, fm1_edit_check_put, &len, &r));
  CHECK(len <= sizeof buf);
  memcpy(buf, fm1_edit_check_buf(), len);
  mem.b = buf;
  mem.n = len;
  /* With the flag: playing, the same tick and the same clips and playheads, then it goes on. */
  fm1_app_load_opts_init(&o);
  o.flags = FM1_APP_LOAD_QUIET | FM1_APP_LOAD_KEEP_TRANSPORT;
  CHECK(fm1_app_state_load(&g_a, fm1_app_state_mem_read, &mem, len, &o, &rep) == 1);
  fm1_seq_get_info(fm1_app_seq(&g_a), &after);
  CHECK(after.playing == 1 && after.master_tick == before.master_tick);
  for (unsigned t = 0; t < tracks; ++t) {
    CHECK(fm1_seq_get_track(fm1_app_seq(&g_a), (uint8_t)t, &ta[t]));
    CHECK(ta[t].playing == tb[t].playing && ta[t].pos_tick == tb[t].pos_tick && ta[t].cycle == tb[t].cycle);
    moving += ta[t].playing != FM1_SEQ_NONE;
  }
  CHECK(moving > 0);                                        /* something was playing to carry */
  render(200);
  fm1_seq_get_info(fm1_app_seq(&g_a), &after);
  CHECK(after.playing == 1 && after.master_tick > before.master_tick + 20);
  /* Without it a project load leaves the sequencer stopped, as before. */
  o.flags = FM1_APP_LOAD_QUIET;
  CHECK(fm1_app_state_load(&g_a, fm1_app_state_mem_read, &mem, len, &o, &rep) == 1);
  fm1_seq_get_info(fm1_app_seq(&g_a), &after);
  CHECK(after.playing == 0);
  /* Stopped stays stopped, with the flag. */
  o.flags = FM1_APP_LOAD_QUIET | FM1_APP_LOAD_KEEP_TRANSPORT;
  CHECK(fm1_app_state_load(&g_a, fm1_app_state_mem_read, &mem, len, &o, &rep) == 1);
  fm1_seq_get_info(fm1_app_seq(&g_a), &after);
  CHECK(after.playing == 0);
  /* The carried transport laid over a running one, built by hand: a playhead past the clip's loop begins the
   * loop again; a track that was not playing comes in on the next bar (queued), so it keeps the bar's grid;
   * a song the set does not have is not carried. */
  {
    fm1_seq_transport_t tr;
    fm1_seq_info_t i2;
    fm1_seq_track_info_t ti, t0;
    fm1_app_button(&g_a, FM1_BTN_PLAY, 1), fm1_app_button(&g_a, FM1_BTN_PLAY, 0);
    render(300);
    fm1_seq_transport_take(fm1_app_seq(&g_a), &tr);
    CHECK(tr.playing && tr.master_tick > 0);
    CHECK(fm1_seq_get_track(fm1_app_seq(&g_a), 0, &t0) && t0.playing != FM1_SEQ_NONE);   /* the demo plays track 1 */
    for (unsigned t = 0; t < FM1_SEQ_MAX_TRACKS; ++t) tr.track[t].pos_tick = 0xFFFFu;   /* beyond any loop */
    tr.track[0].playing = FM1_SEQ_NONE;                                                 /* track 1 was not playing */
    tr.n_tracks = FM1_SEQ_MAX_TRACKS;
    tr.song_len = 3;                                        /* a song the set does not have: not carried */
    fm1_seq_transport_put(fm1_app_seq(&g_a), &tr);
    fm1_seq_get_info(fm1_app_seq(&g_a), &i2);
    CHECK(i2.playing && i2.master_tick == tr.master_tick);
    CHECK(fm1_seq_get_track(fm1_app_seq(&g_a), 0, &ti));
    CHECK(ti.playing == FM1_SEQ_NONE && ti.queued == t0.playing);
    for (unsigned t = 1; t < tracks; ++t) {
      CHECK(fm1_seq_get_track(fm1_app_seq(&g_a), (uint8_t)t, &ti));
      CHECK(ti.pos_tick != 0xFFFFu);
    }
  }
}

/* ---- verbs and the view --------------------------------------------------------- */

static void check_verbs(void) {
  fm1_view_t v;
  int kind[4], unit[4], index[4];
  char a1[16], a2[16];
  fm1_mod_slot_t s;
  fresh(44118.0f);
  CHECK(edit_line("unit master 0 0 comp", 1, NULL) == 0 && edit_line("unit master 0 1 echo", 1, NULL) == 0);
  CHECK(edit_line("cable 5 64 255 1 1 1 4000 0", 1, NULL) >= 0);    /* LFO1 into M1's first */
  snprintf(a1, sizeof a1, "%s", g_a.unit[1].e->id);
  snprintf(a2, sizeof a2, "%s", g_a.unit[2].e->id);
  CHECK(edit_line("swap master 0 0 master 0 1", 2, NULL) == 0);
  CHECK(strcmp(g_a.unit[1].e->id, a2) == 0 && strcmp(g_a.unit[2].e->id, a1) == 0);
  fm1_mod_get_slot(g_a.mod, 5, &s);
  CHECK(s.dst_unit == FM1_MOD_FX2);                               /* the cable followed */
  CHECK(edit_line("move master 0 0 master 0 1", 3, NULL) == 0 && strcmp(g_a.unit[1].e->id, a1) == 0);
  /* Sound 3 has no engine: no file could hold an effect in its insert, so
   * the swap is refused and nothing moves (stage ED3); with an engine it swaps. */
  CHECK(edit_line("swap insert 2 1 master 0 0", 3, NULL) == FM1_REFUSE_BAD && g_a.unit[1].e != NULL);
  CHECK(edit_line("unit insert 2 0 echo", 3, NULL) == FM1_REFUSE_BAD);
  CHECK(edit_line("unit sound 2 0 macro", 3, NULL) == 0);
  CHECK(edit_line("swap insert 2 1 master 0 0", 3, NULL) == 0 && g_a.unit[1].e == NULL);
  {
    const int k0 = fm1_mod_kind_at(g_a.mod, 0);
    CHECK(edit_line("move module 0 0 module 0 3", 4, NULL) == 0 && fm1_mod_kind_at(g_a.mod, 3) == k0);
  }
  CHECK(edit_line("current 2", 5, NULL) == 0 && g_a.sound == 2);
  /* The view: what the panel shows and the knobs' map. */
  CHECK(edit_line("view home sound=1 page=2", 6, NULL) == 0);
  fm1_edit_view(&g_a, &v);
  fm1_app_knobs(&g_a, kind, unit, index);
  CHECK(v.mode == FM1_VIEW_HOME && v.sound == 0 && v.page == 1 && g_a.mode == FM1_MODE_HOME);
  for (int k = 0; k < 4; ++k) {
    const fm1_engine_t *e = g_a.unit[0].e;
    if (kind[k] == 1) CHECK(v.knob[k].kind == 1 && v.knob[k].role == FM1_ROLE_SOUND && v.knob[k].uid == e->params[index[k]].uid &&
                            e->params[index[k]].page == 1);
  }
  CHECK(edit_line("view fx sound=2 entry=3", 7, NULL) == 0);
  fm1_edit_view(&g_a, &v);
  CHECK(v.mode == FM1_VIEW_FX && v.slot == 2 && v.knob[0].kind == 2 && v.knob[3].kind == 2 && v.knob[3].sound == 3);
  CHECK(edit_line("view rack pos=2", 8, NULL) == 0);
  fm1_edit_view(&g_a, &v);
  CHECK(v.mode == FM1_VIEW_RACK && v.slot == 1);
  CHECK(edit_line("view matrix slot=32", 8, NULL) == 0 && g_a.mui.slot == 31);
  CHECK(edit_line("view glo page=2", 8, NULL) == 0 && g_a.glo_page == 1);
  CHECK(edit_line("view home sound=1 page=99", 8, NULL) == 0 && g_a.page < 99);   /* clamped, as SELECT stops */
  /* The ARP pages (stage ED4): HOME's entry 2 opens them, at a page. */
  if (fm1_app_mfx_engine(&g_a, 0)) {
    CHECK(edit_line("view home sound=1 entry=2 page=1", 8, NULL) == 0 && g_a.mode == FM1_MODE_ARP);
    fm1_edit_view(&g_a, &v);
    CHECK(v.mode == FM1_VIEW_HOME && v.arp == 1 && v.sound == 0 && v.page == 0);
    fm1_app_knobs(&g_a, kind, unit, index);
    CHECK(kind[0] == 3 && unit[0] == 0);                            /* the knobs turn the arpeggiator */
    CHECK(edit_line("view home sound=1 entry=1", 8, NULL) == 0 && g_a.mode == FM1_MODE_HOME);
  } else {
    fail(__LINE__, "sound 1 has no MIDI effect");
  }
  CHECK(refused_cleanly("view home sound=1 entry=3", FM1_REFUSE_BAD));
  /* The state hash leaves the view out (stage ED4): moving the panel moves no hash. */
  {
    const uint32_t h = fm1_edit_state_hash(&g_a);
    CHECK(edit_line("view rack pos=3", 8, NULL) == 0 && fm1_edit_state_hash(&g_a) == h);
    CHECK(edit_line("view home sound=1 entry=2", 8, NULL) == 0 && fm1_edit_state_hash(&g_a) == h);
    CHECK(edit_line("current 2", 8, NULL) == 0 && fm1_edit_state_hash(&g_a) == h);   /* nor the current sound */
    CHECK(edit_line("current 0", 8, NULL) == 0);
    CHECK(edit_line("view home sound=1", 8, NULL) == 0);
  }
  /* A pad's own value (engine API v4): written to that pad, the focus kept. */
  for (size_t k = 0; k < fm1_engine_count; ++k) {
    const fm1_engine_t *e = fm1_engines[k];
    const int f = fm1_engine_focus(e);
    char line[96];
    if (f < 0 || !e->get_param) continue;
    snprintf(line, sizeof line, "unit sound 0 0 %s", e->id);
    if (edit_line(line, 9, NULL) != 0) continue;
    for (unsigned i = 0; i < e->n_params; ++i) {
      const float was = g_a.unit[0].value[f];
      if (!(e->params[i].flags & FM1_PARAM_PER_FOCUS) || e->params[i].type != FM1_PARAM_FLOAT) continue;
      snprintf(line, sizeof line, "param sound 0 0 %u %.9g focus=2", e->params[i].uid, (double)e->params[i].max);
      CHECK(edit_line(line, 9, NULL) == 0);
      CHECK(e->get_param(g_a.unit[0].self, (uint16_t)i, 2) == e->params[i].max && g_a.unit[0].value[f] == was);
      break;
    }
    break;
  }
}

/* ---- telemetry ------------------------------------------------------------------ */

static float g_tele[2048], g_out_a[2 * FM1_APP_MAX_FRAMES * 700], g_out_b[2 * FM1_APP_MAX_FRAMES * 700];
static unsigned g_fills;

static void play(float *out, int blocks, int tele) {
  for (int k = 0; k < blocks; ++k) {
    const float *o;
    if (k == 10) fm1_app_note_on(&g_a, 60, 100);
    if (k == 400) fm1_app_note_off(&g_a, 60);
    o = fm1_app_render(&g_a, FM1_APP_MAX_FRAMES);
    memcpy(out + 2 * FM1_APP_MAX_FRAMES * k, o, sizeof(float) * 2 * FM1_APP_MAX_FRAMES);
    if (tele && fm1_edit_telemetry(&g_a, g_tele, sizeof g_tele / sizeof g_tele[0])) ++g_fills;
  }
}

/* A cable from LFO1 into the first parameter of Sound 1 that takes one, in
 * slot 3 (slots 1 and 2 are the default rack's). */
static void lfo_cable(void) {
  const fm1_engine_t *e = fm1_app_unit_engine(&g_a, 0);
  char line[96];
  for (unsigned i = 0; e && i < e->n_params; ++i) {
    snprintf(line, sizeof line, "cable 3 64 255 0 1 %u 8000 0", e->params[i].uid);
    if (edit_line(line, 1, NULL) == 0) return;
  }
  CHECK(!"a parameter that takes a cable");
}

/* A per-voice cable from LFO1 into the first parameter of Sound 1 that takes
 * one, in slot 5; returns that parameter. */
static const fm1_param_t *g_vparam;
static const fm1_param_t *voice_cable(void) {
  const fm1_engine_t *e = fm1_app_unit_engine(&g_a, 0);
  char line[96];
  for (unsigned i = 0; e && i < e->n_params; ++i) {
    snprintf(line, sizeof line, "cable 5 64 255 0 129 %u 8000 0", e->params[i].uid);
    if (edit_line(line, 1, NULL) == 0) return &e->params[i];
  }
  CHECK(!"a parameter that takes a per-voice cable");
  return NULL;
}

/* Limiter's and Squash's gain read-outs (fm1_dynamics.h): a loud note into
 * each at its extreme setting reads a cut of a decibel or more, finite; the
 * Limiter left alone with no note reads none. */
static void check_gain_readouts(void) {
  static const struct { const char *id, *knob; float hot; } kFx[] = { { "limit", "Drive", 24.0f }, { "squash", "Squash", 1.0f } };
  const fm1_tele_section_t *red = fm1_tele_section(FM1_TELE_REDUCTION);
  uint32_t one[FM1_TELE_MASK_WORDS];
  memset(one, 0, sizeof one);
  one[red->mask / 32] |= 1u << (red->mask % 32);        /* Sound 1's first insert */
  for (size_t k = 0; k < sizeof kFx / sizeof kFx[0]; ++k) {
    const fm1_engine_t *e = NULL;
    char line[96];
    float quiet, loud;
    for (size_t i = 0; i < fm1_engine_count; ++i) if (strcmp(fm1_engines[i]->id, kFx[k].id) == 0) e = fm1_engines[i];
    if (!e) continue;                                    /* a build without that module */
    fresh(44118.0f);
    snprintf(line, sizeof line, "unit insert 0 0 %s", e->id);
    CHECK(edit_line(line, 1, NULL) == 0);
    fm1_edit_subscribe(&g_a, one);
    render(20);
    CHECK(fm1_edit_telemetry(&g_a, g_tele, sizeof g_tele / sizeof g_tele[0]) == fm1_tele_floats());
    quiet = g_tele[red->offset];
    /* Squash's gate, closed over silence, is a cut of its own (the editor
     * shows a read-out only while a signal is present), so only the
     * Limiter's idle reading is held to none. */
    CHECK(isfinite(quiet) && quiet >= 0.0f && (strcmp(e->id, "limit") != 0 || quiet < 0.1f));
    for (unsigned i = 0; i < e->n_params; ++i) {
      if (strcmp(e->params[i].name, kFx[k].knob) != 0) continue;
      snprintf(line, sizeof line, "param insert 0 0 %u %.9g", e->params[i].uid, (double)kFx[k].hot);
      CHECK(edit_line(line, 1, NULL) == 0);
    }
    fm1_app_note_on(&g_a, 60, 127);
    render(80);
    g_a.edit->tele_at = ~(uint64_t)0;                     /* due now */
    CHECK(fm1_edit_telemetry(&g_a, g_tele, sizeof g_tele / sizeof g_tele[0]) == fm1_tele_floats());
    loud = g_tele[red->offset];
    CHECK(isfinite(loud) && loud >= 1.0f && loud < 120.0f);
    fprintf(stderr, "gain read-out %s: %.3f dB quiet, %.3f dB loud\n", e->id, (double)quiet, (double)loud);
  }
}

static void check_empty_sound_insert(void) {
  const int sound = 3, unit = fm1_app_insert_unit(sound, 0);
  fresh(44118.0f);
  CHECK(!g_a.unit[fm1_app_sound_unit(sound)].e);
  const uint32_t hash = fm1_edit_state_hash(&g_a);
  CHECK(fm1_app_select(&g_a, unit, fm1_app_find("comp")) == FM1_APP_SELECT_BAD);
  CHECK(!g_a.unit[unit].e && fm1_edit_state_hash(&g_a) == hash);
  CHECK(edit_line("unit insert 3 0 comp", 1, NULL) == FM1_REFUSE_BAD);
  CHECK(fm1_edit_state_hash(&g_a) == hash);
  CHECK(fm1_app_select(&g_a, unit, -1) == 0);  /* clearing remains harmless */
  CHECK(fm1_app_unit_select(&g_a, sound, fm1_app_find("test-sine")) == 0);
  CHECK(fm1_app_select(&g_a, unit, fm1_app_find("comp")) == 0);
}

static void check_gate_readout(void) {
#if FM1_WITH_SQUASH
  const int index = fm1_app_find("squash");
  if (index < 0) return;
  const fm1_tele_section_t *red = fm1_tele_section(FM1_TELE_REDUCTION);
  uint32_t one[FM1_TELE_MASK_WORDS] = {0};
  fresh(44118.0f);
  CHECK(edit_line("unit insert 0 0 squash", 1, NULL) == 0);
  CHECK(edit_line("param insert 0 0 12 10", 1, NULL) == 0); /* fast gate release */
  one[red->mask / 32] |= 1u << (red->mask % 32);
  fm1_edit_subscribe(&g_a, one);
  render(600);
  g_a.edit->tele_at = ~(uint64_t)0;
  CHECK(fm1_edit_telemetry(&g_a, g_tele, sizeof g_tele / sizeof g_tele[0]) == fm1_tele_floats());
  CHECK(g_tele[red->offset + 1] == 2.0f);             /* silence closes the gate */
  fm1_app_note_on(&g_a, 60, 127);
  render(100);
  g_a.edit->tele_at = ~(uint64_t)0;
  fm1_edit_telemetry(&g_a, g_tele, sizeof g_tele / sizeof g_tele[0]);
  CHECK(g_tele[red->offset + 1] == 0.0f);             /* a note opens it */
  CHECK(edit_line("param insert 0 0 1 1 index", 1, NULL) == 0);
  render(100);
  g_a.edit->tele_at = ~(uint64_t)0;
  fm1_edit_telemetry(&g_a, g_tele, sizeof g_tele / sizeof g_tele[0]);
  CHECK(isnan(g_tele[red->offset + 1]));              /* Mu has no gate */
#endif
}

static void check_telemetry(void) {
  uint32_t all[FM1_TELE_MASK_WORDS], one[FM1_TELE_MASK_WORDS];
  const fm1_tele_section_t *met = fm1_tele_section(FM1_TELE_METERS);
  const int blocks = 690;                       /* 1.0 s at 44,118 Hz */
  CHECK(fm1_tele_floats() == 1454 && fm1_tele_mask_bits() == 119);
  memset(all, 0, sizeof all);
  for (unsigned b = 0; b < fm1_tele_mask_bits(); ++b) all[b / 32] |= 1u << (b % 32);
  /* The audio with everything subscribed is the audio without the layer. */
  fm1_app_init(&g_a, 44118.0f);
  fm1_app_default_chain(&g_a);
  lfo_cable();
  voice_cable();
  play(g_out_a, blocks, 0);
  fresh(44118.0f);
  lfo_cable();
  g_vparam = voice_cable();
  fm1_edit_subscribe(&g_a, all);
  g_fills = 0;
  play(g_out_b, blocks, 1);
  CHECK(memcmp(g_out_a, g_out_b, sizeof(float) * 2 * FM1_APP_MAX_FRAMES * blocks) == 0);
  /* At most FM1_TELE_HZ blocks a second of audio (and the first at once). */
  CHECK(g_fills >= FM1_TELE_HZ - 1 && g_fills <= FM1_TELE_HZ + 1);
  /* Rows: the output's meter alone; nothing else written. */
  for (size_t i = 0; i < sizeof g_tele / sizeof g_tele[0]; ++i) g_tele[i] = 12345.0f;
  memset(one, 0, sizeof one);
  one[(met->mask + met->rows - 1) / 32] |= 1u << ((met->mask + met->rows - 1) % 32);
  fm1_edit_subscribe(&g_a, one);
  fm1_app_note_on(&g_a, 64, 110);
  render(40);
  CHECK(fm1_edit_telemetry(&g_a, g_tele, sizeof g_tele / sizeof g_tele[0]) == fm1_tele_floats());
  {
    const unsigned at = met->offset + (met->rows - 1u) * met->fields;
    unsigned untouched = 0;
    for (unsigned i = 0; i < fm1_tele_floats(); ++i) untouched += i != at && i != at + 1 && g_tele[i] == 12345.0f;
    CHECK(untouched == fm1_tele_floats() - 2);
    CHECK(g_tele[at] > 0.0f && g_tele[at] <= 1.0f && g_tele[at + 1] > 0.0f && g_tele[at + 1] <= g_tele[at]);
  }
  CHECK(fm1_edit_telemetry(&g_a, g_tele, sizeof g_tele / sizeof g_tele[0]) == 0);   /* too soon */
  CHECK(fm1_edit_telemetry(&g_a, g_tele, 100) == 0);                                  /* no room */
  fm1_edit_subscribe(&g_a, NULL);
  render(40);
  CHECK(fm1_edit_telemetry(&g_a, g_tele, sizeof g_tele / sizeof g_tele[0]) == 0);   /* no subscription */
  /* Module outputs and destinations: LFO1 runs, with a cable into Sound 1. */
  fm1_edit_subscribe(&g_a, all);
  render(40);
  CHECK(fm1_edit_telemetry(&g_a, g_tele, sizeof g_tele / sizeof g_tele[0]) == fm1_tele_floats());
  {
    const fm1_tele_section_t *outs = fm1_tele_section(FM1_TELE_OUTS);
    const fm1_tele_section_t *dests = fm1_tele_section(FM1_TELE_DESTS);
    const float *o = g_tele + outs->offset;     /* pos1 out1: value, min, max */
    CHECK(o[1] <= o[0] && o[0] <= o[2] && o[1] < o[2]);
    CHECK(isfinite(g_tele[dests->offset + 3]) && isnan(g_tele[dests->offset + 4]));
  }
  /* The per-voice cable in slot 5: some voice has a value inside the
   * parameter's range, a slot with no such cable has none, and a cable that
   * reaches every voice at once (slot 3) has no per-voice values either. */
  {
    const fm1_tele_section_t *vd = fm1_tele_section(FM1_TELE_VOICE_DESTS);
    const fm1_param_t *p = g_vparam;
    unsigned live = 0, none = 0;
    for (unsigned v = 0; v < vd->fields; ++v) {
      const float x = g_tele[vd->offset + 5u * vd->items * vd->fields + v];
      if (isfinite(x)) {
        ++live;
        CHECK(!p || (x >= p->min - 1e-3f && x <= p->max + 1e-3f));
      }
      none += isnan(g_tele[vd->offset + 3u * vd->items * vd->fields + v]) + isnan(g_tele[vd->offset + v]);
    }
    CHECK(live >= 1 && live <= vd->fields);
    CHECK(none == 2u * vd->fields);
  }
  check_gain_readouts();
  check_empty_sound_insert();
  check_gate_readout();
}

/* ---- hostile input --------------------------------------------------------------- */

static uint32_t g_rng = 0x1234567u;
static uint32_t rnd(void) {
  g_rng = g_rng * 1664525u + 1013904223u;
  return g_rng >> 8;
}

/* Random packed records and verbs, the types the layer takes and others,
 * with fields at random and at their edges: nothing crashes, every verdict
 * is 0 or a code of fm1_refusal.h, and the audio stays finite. */
static unsigned g_fuzz;

static void check_fuzz(void) {
  static const uint8_t kTypes[] = { FM1_REC_PARAM, FM1_REC_UNIT, FM1_REC_ON, FM1_REC_LEVEL, FM1_REC_MODULE,
                                    FM1_REC_CABLE, FM1_EDIT_SWAP, FM1_EDIT_MOVE, FM1_EDIT_CURRENT, FM1_EDIT_VIEW,
                                    FM1_REC_DX7, FM1_EDIT_LOADED, 0, 0xFF };
  static const char *const kIds[] = { "macro", "comp", "echo", "lfo", "env", "arp", "", "\xff\xfe", "drive" };
  uint8_t b[FM1_EDIT_MAX_RECS * FM1_EDIT_REC_BYTES];
  int8_t codes[FM1_EDIT_MAX_RECS];
  fresh(44118.0f);
  fm1_app_note_on(&g_a, 60, 100);
  for (int round = 0; round < 400; ++round) {
    const uint32_t n = 1 + rnd() % FM1_EDIT_MAX_RECS;
    for (uint32_t i = 0; i < n; ++i) {
      uint8_t *r = b + i * FM1_EDIT_REC_BYTES;
      for (unsigned k = 0; k < FM1_EDIT_REC_BYTES; ++k) r[k] = (uint8_t)(rnd() % 7 ? rnd() % 9 : rnd());
      r[0] = kTypes[rnd() % (sizeof kTypes / sizeof kTypes[0])];
      if (r[0] == FM1_REC_UNIT || r[0] == FM1_REC_MODULE) {
        const char *id = kIds[rnd() % 9];
        memset(r + 4, 0, 16);
        memcpy(r + 4, id, strlen(id));
        if (rnd() % 5 == 0) memset(r + 4, 'x', 16);       /* no NUL */
      }
      if (r[0] == FM1_REC_PARAM && rnd() % 2) {
        const float edge[] = { NAN, INFINITY, -INFINITY, 1e30f, -1e30f, 0.0f, -0.0f, 1e-30f };
        float f = edge[rnd() % 8];
        memcpy(r + 8, &f, 4);
      }
    }
    fm1_edit_packed(&g_a, b, n + (rnd() % 8 == 0 ? 500u : 0u), FM1_EDIT_EDITOR, (uint16_t)round, codes);
    for (uint32_t i = 0; i < n; ++i) {
      CHECK(codes[i] == 0 || fm1_refusal_find((unsigned)(uint8_t)codes[i]) != NULL);
      ++g_fuzz;
    }
    {
      const float *o = fm1_app_render(&g_a, FM1_APP_MAX_FRAMES);
      for (unsigned k = 0; k < 2u * FM1_APP_MAX_FRAMES; ++k) CHECK(isfinite(o[k]));
    }
    if (round % 50 == 0) fm1_app_draw(&g_a, 0);
  }
}

/* ---- the whole check ------------------------------------------------------------ */

static char g_save[FM1_STATE_BIN_MAX];
void fm1_edit_check_put(void *ctx, const char *b, size_t n) {
  uint32_t *len = (uint32_t *)ctx;
  if (*len + n <= sizeof g_save) memcpy(g_save + *len, b, n);
  *len += (uint32_t)n;
}
const char *fm1_edit_check_buf(void) { return g_save; }

int fm1_edit_check(void) {
  unsigned n_codes = 0;
  check_parse();
  check_refusals();
  check_cable_codes();
  check_ring();
  hands(g_knobs);
  hands(g_preset);
  hands(g_mix);
  hands(g_swap);
  hands(g_current);
  hands(g_arp);
  hands(g_rack);
  for (g_sweep_seed = 0; g_sweep_seed < 40; ++g_sweep_seed, ++g_sweeps) hands(g_sweep);
  check_locks();
  check_transport();
  check_verbs();
  check_telemetry();
  check_fuzz();
  printf("{\"params\":%u,\"steps\":%u,\"text_same\":%u,\"text_bad\":%u,\"text_first_bad\":\"%s\",\"codes\":[",
         g_rt_params, g_rt_steps, g_rt_same, g_rt_bad, g_rt_first);
  for (int c = 1; c < 64; ++c) {
    const fm1_refusal_t *r = g_codes[c] ? fm1_refusal_find((unsigned)c) : NULL;
    if (r) printf("%s\"%s\"", n_codes++ ? "," : "", r->name);
  }
  printf("],\"hands\":%u,\"sweeps\":%u,\"lock_blocks\":%u,\"tele_fills\":%u,\"fuzz\":%u,\"failed\":%d,\"why\":\"%s\"}\n", g_hands, g_sweeps, g_lock_blocks, g_fills, g_fuzz, g_failed, g_why);
  return g_failed ? 1 : 0;
}

/* ---- the script run ------------------------------------------------------------- */

static int button_of(const char *s) {
  static const char *const k[] = { "OCT-", "OCT+", "FX", "SEL", "ENV", "LFO", "EDIT", "GLO",
                                   "HOME", "SAVE", "ARP", "SEQ", "PLAY", "REC" };
  for (int i = 0; i < 14; ++i) {
    if (strcmp(s, k[i]) == 0) return i;
  }
  return -1;
}

static int encoder_of(const char *s) {
  static const char *const k[] = { "SELECT", "PRESETS", "ALGORITHM", "KNOB1", "KNOB2", "KNOB3", "KNOB4" };
  for (int i = 0; i < 7; ++i) {
    if (strcmp(s, k[i]) == 0) return i;
  }
  return -1;
}

static char g_dump[1 << 16];
static float g_audio[2 * FM1_APP_MAX_FRAMES * 4096];

int fm1_edit_run(const char *script, const char *dir) {
  FILE *f = fopen(script, "r"), *out;
  char line[256], path[1024];
  long block = 0, total = 0;
  size_t n = 0;
  uint16_t tag = 0;
  if (!f) return 2;
  fresh(44118.0f);
  while (fgets(line, sizeof line, f)) {
    char verb[16], arg1[160];
    long at;
    int used = 0;
    line[strcspn(line, "\r\n")] = 0;
    if (line[0] == '#' || !line[0]) continue;
    if (sscanf(line, "@%ld %15s %n", &at, verb, &used) < 2) continue;
    if (strcmp(verb, "end") == 0) { total = at; break; }
    for (; block < at && block < 4096; ++block) {
      memcpy(g_audio + 2 * FM1_APP_MAX_FRAMES * block, fm1_app_render(&g_a, FM1_APP_MAX_FRAMES),
             sizeof(float) * 2 * FM1_APP_MAX_FRAMES);
    }
    snprintf(arg1, sizeof arg1, "%s", line + used);
    n += (size_t)snprintf(g_dump + n, sizeof g_dump - n, "B%ld %s ->", block, line);
    if (strcmp(verb, "edit") == 0) {
      uint8_t b[FM1_EDIT_REC_BYTES];
      int8_t c = -1;
      if (fm1_edit_parse_text(arg1, b)) fm1_edit_packed(&g_a, b, 1, FM1_EDIT_EDITOR, ++tag, &c);
      n += (size_t)snprintf(g_dump + n, sizeof g_dump - n, " %d\n", c);
    } else {
      char name[16];
      int x = 0, y = 0;
      sscanf(arg1, "%15s %d %d", name, &x, &y);
      if (strcmp(verb, "button") == 0 && button_of(name) >= 0) fm1_app_button(&g_a, button_of(name), x);
      else if (strcmp(verb, "turn") == 0 && encoder_of(name) >= 0) fm1_app_encoder(&g_a, encoder_of(name), x);
      else if (strcmp(verb, "note") == 0) fm1_app_note_on(&g_a, atoi(name), x);
      else if (strcmp(verb, "off") == 0) fm1_app_note_off(&g_a, atoi(name));
      n += (size_t)snprintf(g_dump + n, sizeof g_dump - n, " .\n");
    }
  }
  fclose(f);
  for (; block < total && block < 4096; ++block) {
    memcpy(g_audio + 2 * FM1_APP_MAX_FRAMES * block, fm1_app_render(&g_a, FM1_APP_MAX_FRAMES),
           sizeof(float) * 2 * FM1_APP_MAX_FRAMES);
  }
  n += fm1_edit_dump(&g_a, g_dump + n, sizeof g_dump - n);
  fm1_app_draw(&g_a, 0);
  snprintf(path, sizeof path, "%s/edit.txt", dir);
  if (!(out = fopen(path, "wb"))) return 2;
  fwrite(g_dump, 1, n, out);
  fclose(out);
  snprintf(path, sizeof path, "%s/screen.raw", dir);
  if (!(out = fopen(path, "wb"))) return 2;
  fwrite(g_a.tft.px, 2, (size_t)FM1_TFT_W * FM1_TFT_H, out);
  fclose(out);
  snprintf(path, sizeof path, "%s/audio.f32", dir);
  if (!(out = fopen(path, "wb"))) return 2;
  fwrite(g_audio, sizeof(float), (size_t)2 * FM1_APP_MAX_FRAMES * (size_t)block, out);
  fclose(out);
  return 0;
}
