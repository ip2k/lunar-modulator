/* fm1_meta.c -- the parameter metadata export (fm1_meta.h): the build's
 * registries as one JSON document in the canonical layout of
 * tests/state_canon.py, written as it goes, with no heap and no tree.
 *
 * Member order is engines/state/schema/metadata.schema.json's, which is the
 * canonical order; tests/test_engine_metadata.py checks that the output is
 * canonical byte for byte, fits the schema and agrees with fm1-render
 * --list and --list-mod. Our own code. MIT licence, like the rest of this
 * repository. */
#include "fm1_meta.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "fm1_dx7.h"
#include "fm1_engine.h"
#include "fm1_engine_meta.h"
#include "fm1_known.h"
#include "fm1_mod.h"
#include "fm1_num.h"
#include "fm1_refusal.h"
#include "fm1_state_caps.h"
#include "fm1_tele.h"
#include "../host/mod_script.h"

/* ---- A canonical JSON writer -----------------------------------------------
 * Two spaces of indent, ": " after a key, one member or item a line, LF; an
 * inline container (the `made` and `data` records here) on one line with ", "
 * between members; an empty one as {} or []. */
#define JW_DEPTH 12

typedef struct jw {
  fm1_meta_put_t put;
  void *ctx;
  size_t bytes;
  int depth;
  int after_key;                 /* a key was written: the value follows it */
  uint8_t inl[JW_DEPTH];
  uint32_t count[JW_DEPTH];
  char close[JW_DEPTH];
} jw_t;

static void jw_raw(jw_t *w, const char *s, size_t n) {
  w->put(w->ctx, s, n);
  w->bytes += n;
}

static void jw_text(jw_t *w, const char *s) { jw_raw(w, s, strlen(s)); }

static void jw_indent(jw_t *w, int depth) {
  int k;
  for (k = 0; k < depth; ++k) jw_raw(w, "  ", 2);
}

/* Before a value or a member: the separator and the indent its container
 * wants, or nothing right after a key. */
static void jw_sep(jw_t *w) {
  if (w->after_key) {
    w->after_key = 0;
    return;
  }
  if (!w->depth) return;
  if (w->inl[w->depth]) {
    if (w->count[w->depth]) jw_raw(w, ", ", 2);
  } else {
    jw_text(w, w->count[w->depth] ? ",\n" : "\n");
    jw_indent(w, w->depth);
  }
  ++w->count[w->depth];
}

static void jw_string(jw_t *w, const char *s) {
  static const char kHex[] = "0123456789abcdef";
  const char *run = s;
  jw_raw(w, "\"", 1);
  for (; *s; ++s) {
    const unsigned char c = (unsigned char)*s;
    char esc[7];
    size_t n = 0;
    if (c == '"' || c == '\\') {
      esc[0] = '\\';
      esc[1] = (char)c;
      n = 2;
    } else if (c < 0x20) {
      static const char kShort[] = "btnvfr";     /* \b \t \n, (\v), \f \r */
      esc[0] = '\\';
      if (c >= 8 && c <= 13 && c != 11) {
        esc[1] = kShort[c - 8];
        n = 2;
      } else {
        esc[1] = 'u';
        esc[2] = '0';
        esc[3] = '0';
        esc[4] = kHex[c >> 4];
        esc[5] = kHex[c & 15u];
        n = 6;
      }
    } else {
      continue;
    }
    jw_raw(w, run, (size_t)(s - run));
    jw_raw(w, esc, n);
    run = s + 1;
  }
  jw_raw(w, run, strlen(run));
  jw_raw(w, "\"", 1);
}

static void jw_key(jw_t *w, const char *key) {
  jw_sep(w);
  jw_string(w, key);
  jw_raw(w, ": ", 2);
  w->after_key = 1;
}

static void jw_open(jw_t *w, char open, char close, int inline_) {
  const char o[2] = { open, 0 };
  jw_sep(w);
  jw_text(w, o);
  ++w->depth;
  w->inl[w->depth] = (uint8_t)inline_;
  w->count[w->depth] = 0;
  w->close[w->depth] = close;
}

static void jw_obj(jw_t *w) { jw_open(w, '{', '}', 0); }
static void jw_arr(jw_t *w) { jw_open(w, '[', ']', 0); }

static void jw_end(jw_t *w) {
  const char c[2] = { w->close[w->depth], 0 };
  if (w->count[w->depth] && !w->inl[w->depth]) {
    jw_raw(w, "\n", 1);
    jw_indent(w, w->depth - 1);
  }
  jw_text(w, c);
  --w->depth;
}

static void jw_str(jw_t *w, const char *s) {
  jw_sep(w);
  jw_string(w, s ? s : "");
}

static void jw_int(jw_t *w, long long v) {
  char b[24];
  jw_sep(w);
  snprintf(b, sizeof(b), "%lld", v);
  jw_text(w, b);
}

static void jw_bool(jw_t *w, int v) {
  jw_sep(w);
  jw_text(w, v ? "true" : "false");
}

static void jw_null(jw_t *w) {
  jw_sep(w);
  jw_text(w, "null");
}

/* A float32 as the shortest decimal (at most 9 significant digits) that
 * reads back to its bits, in ECMAScript's Number::toString format: 0.41,
 * 420, 0.0000015, 5e-7, 1e+21; -0 is 0. Never NaN or an infinity (a
 * parameter's range has neither). The state files' own formatter
 * (fm1_num.h, exact, no libc), so the export and every saved file write a
 * number alike. */
static void f32_text(float v, char out[40]) {
  if (v != v || v - v != 0.0f) v = 0.0f;
  (void)fm1_num_f32_text(fm1_num_bits(v), out);
}

static void jw_f32(jw_t *w, float v) {
  char b[40];
  jw_sep(w);
  f32_text(v, b);
  jw_text(w, b);
}

/* ---- The document -------------------------------------------------------------- */

static const char *unit_name(uint8_t u) {
  static const char *const kUnits[] = { "none", "semi", "ms", "hz", "pct", "deg", "db" };
  return u < sizeof(kUnits) / sizeof(kUnits[0]) ? kUnits[u] : "none";
}

static const char *port_kind(uint8_t k) {
  return k == FM1_PORT_CV_UNI ? "cv_uni" : k == FM1_PORT_GATE ? "gate" : "cv_bi";
}

/* The flags by name, in bit order (metadata.schema.json's `flag`). */
static void flags(jw_t *w, uint16_t f) {
  static const struct { uint16_t bit; const char *name; } kFlags[] = {
    { FM1_PARAM_LATCH, "latch" }, { FM1_PARAM_SMOOTH, "smooth" }, { FM1_PARAM_NOLOCK, "nolock" },
    { FM1_PARAM_MOD, "mod" }, { FM1_PARAM_INPUT, "input" }, { FM1_PARAM_POLY, "poly" },
    { FM1_PARAM_LOG, "log" }, { 0x80u, "keysrc" }, { FM1_PARAM_FOCUS, "focus" },
    { FM1_PARAM_PER_FOCUS, "per_focus" },
  };
  size_t k;
  jw_key(w, "flags");
  jw_arr(w);
  for (k = 0; k < sizeof(kFlags) / sizeof(kFlags[0]); ++k) {
    if (f & kFlags[k].bit) jw_str(w, kFlags[k].name);
  }
  jw_end(w);
}

/* A parameter table, the array: each hidden (INPUT, or every one of the
 * host's) or on its page's next knob; with its entries and, from
 * fm1_known.h, its aliases. */
static void params(jw_t *w, const fm1_param_t *ps, unsigned n, int all_hidden, uint8_t owner,
                   const char *id) {
  unsigned knobs[256];
  unsigned i;
  size_t a;
  memset(knobs, 0, sizeof(knobs));
  jw_arr(w);
  for (i = 0; i < n; ++i) {
    const fm1_param_t *p = &ps[i];
    const int hidden = all_hidden || (p->flags & FM1_PARAM_INPUT);
    int any = 0;
    jw_obj(w);
    jw_key(w, "uid");
    jw_int(w, p->uid);
    jw_key(w, "name");
    jw_str(w, p->name);
    jw_key(w, "abbr");
    jw_str(w, p->abbr);
    jw_key(w, "type");
    jw_str(w, p->type == FM1_PARAM_ENUM ? "enum" : "float");
    jw_key(w, "min");
    jw_f32(w, p->min);
    jw_key(w, "max");
    jw_f32(w, p->max);
    jw_key(w, "def");
    jw_f32(w, p->def);
    jw_key(w, "step");                               /* 1.1: the knob's detent */
    jw_f32(w, fm1_param_is_log(p) ? FM1_PARAM_LOG_DETENT : fm1_param_detent(p));
    jw_key(w, "unit");
    jw_str(w, unit_name(p->unit));
    jw_key(w, "page");
    jw_int(w, p->page + 1);
    if (hidden) {
      jw_key(w, "hidden");
      jw_bool(w, 1);
    } else {
      jw_key(w, "knob");
      jw_int(w, ++knobs[p->page]);
    }
    flags(w, p->flags);
    if (p->type == FM1_PARAM_ENUM && p->enum_names) {
      const int entries = (int)(p->max - p->min + 0.5f) + 1;
      int k;
      jw_key(w, "entries");
      jw_arr(w);
      for (k = 0; k < entries; ++k) jw_str(w, p->enum_names[k]);
      jw_end(w);
    }
    for (a = 0; a < fm1_alias_count; ++a) {          /* old names of the parameter */
      const fm1_alias_t *al = &fm1_aliases[a];
      if (al->owner != owner || strcmp(al->id, id) || al->uid != p->uid || al->entry != -1) continue;
      if (!any++) {
        jw_key(w, "aliases");
        jw_arr(w);
      }
      jw_str(w, al->name);
    }
    if (any) jw_end(w);
    any = 0;
    for (a = 0; a < fm1_alias_count; ++a) {          /* old names of its entries */
      const fm1_alias_t *al = &fm1_aliases[a];
      if (al->owner != owner || strcmp(al->id, id) || al->uid != p->uid || al->entry < 0) continue;
      if (!any++) {
        jw_key(w, "entry_aliases");
        jw_obj(w);
      }
      jw_key(w, al->name);
      jw_int(w, al->entry);
    }
    if (any) jw_end(w);
    jw_end(w);
  }
  jw_end(w);
}

static void ports(jw_t *w, const char *key, const fm1_port_t *ps, unsigned n, int gates) {
  unsigned i;
  jw_key(w, key);
  jw_arr(w);
  for (i = 0; i < n; ++i) {
    jw_obj(w);
    jw_key(w, "name");
    jw_str(w, ps[i].name);
    jw_key(w, "kind");
    jw_str(w, port_kind(ps[i].kind));
    jw_key(w, "unit");
    jw_str(w, unit_name(ps[i].unit));
    if (gates) {
      const fm1_mod_source_info_t *si =
          ps[i].normal != FM1_MOD_NONE ? fm1_mod_system_source(ps[i].normal) : NULL;
      jw_key(w, "normal");
      if (si) jw_str(w, si->name); else jw_null(w);
    }
    jw_end(w);
  }
  jw_end(w);
}

/* 1.1: a module's knob pages, by name where the panel names them, else
 * null (the panel shows the page's number). */
static void page_names(jw_t *w, const char *id, const fm1_param_t *ps, unsigned n) {
  const unsigned pages = fm1_param_pages(ps, n);
  unsigned k;
  jw_key(w, "page_names");
  jw_arr(w);
  for (k = 0; k < pages; ++k) {
    const char *name = fm1_page_name(id, k);
    if (name) jw_str(w, name); else jw_null(w);
  }
  jw_end(w);
}

/* 1.1: the licence of the code a module links (an SPDX expression) and
 * whether it is a GNU licence, which the GPL switch keeps out of a shared
 * build. */
static void licence(jw_t *w, const char *spdx) {
  jw_key(w, "licence");
  jw_str(w, spdx);
  jw_key(w, "gpl");
  jw_bool(w, fm1_licence_is_gpl(spdx));
}

static void engine(jw_t *w, const fm1_engine_t *e, const fm1_host_t *host) {
  static const struct { uint32_t bit; const char *name; } kWants[] = {
    { FM1_FX_WANT_KEY, "key" }, { FM1_FX_WANT_TEMPO, "tempo" },
    { FM1_FX_WANT_TRANSPORT, "transport" },
  };
  size_t k;
  jw_obj(w);
  jw_key(w, "id");
  jw_str(w, e->id);
  jw_key(w, "name");
  jw_str(w, e->name);
  jw_key(w, "kind");
  jw_str(w, e->kind == FM1_KIND_SOUND ? "sound" : e->kind == FM1_KIND_AUDIO_FX ? "audio_fx" : "midi_fx");
  if (e->kind == FM1_KIND_AUDIO_FX) {                /* 1.1: the group the page lists it under */
    const fm1_fx_group_t *g = fm1_fx_group_of(e->id);
    jw_key(w, "group");
    if (g) jw_str(w, g->id); else jw_null(w);
  }
  jw_key(w, "credits");
  jw_str(w, e->credits);
  /* The code's licences (fm1_engine_licence, an SPDX expression: MIT unless
   * the licence table says otherwise), so an editor can show a GPL module's
   * terms as the virtual FM-1's page does; from 1.1 with `gpl` beside it. */
  licence(w, fm1_engine_licence(e));
  jw_key(w, "max_voices");
  jw_int(w, e->max_voices);
  jw_key(w, "per_note");
  jw_bool(w, e->set_param_note != NULL);
  jw_key(w, "pads");
  if (e->pad_count) {
    jw_obj(w);
    jw_key(w, "first");
    jw_int(w, e->pad_first_note);
    jw_key(w, "count");
    jw_int(w, e->pad_count);
    jw_end(w);
  } else {
    jw_null(w);
  }
  jw_key(w, "fx_wants");
  jw_arr(w);
  for (k = 0; k < sizeof(kWants) / sizeof(kWants[0]); ++k) {
    if (e->fx_wants & kWants[k].bit) jw_str(w, kWants[k].name);
  }
  jw_end(w);
  jw_key(w, "ram");
  jw_int(w, (long long)e->instance_size(host));
  page_names(w, e->id, e->params, e->n_params);
  jw_key(w, "params");
  params(w, e->params, e->n_params, 0, FM1_ALIAS_ENGINE, e->id);
  {                                                 /* removed parameters' last names */
    size_t a;
    int any = 0;
    for (a = 0; a < fm1_alias_count; ++a) {
      const fm1_alias_t *al = &fm1_aliases[a];
      if (al->owner != FM1_ALIAS_ENGINE || strcmp(al->id, e->id) || al->entry != FM1_ALIAS_RETIRED) continue;
      if (!any++) {
        jw_key(w, "retired");
        jw_obj(w);
      }
      jw_key(w, al->name);
      jw_int(w, al->uid);
    }
    if (any) jw_end(w);
  }
  jw_end(w);
}

/* A modulation kind's licence: its row in the licence table (fm1_engine.h),
 * else MIT, the repository's. */
static const char *kind_licence(const char *id) {
  size_t i;
  for (i = 0; i < fm1_licence_count; ++i) {
    if (strcmp(fm1_licences[i].id, id) == 0) return fm1_licences[i].spdx;
  }
  return "MIT";
}

static void mod_kind(jw_t *w, const fm1_mod_kind_t *k, const fm1_host_t *host) {
  const char guid[5] = { (char)(k->guid >> 24), (char)(k->guid >> 16), (char)(k->guid >> 8),
                         (char)k->guid, 0 };
  jw_obj(w);
  jw_key(w, "id");
  jw_str(w, k->id);
  jw_key(w, "guid");
  jw_str(w, guid);
  jw_key(w, "name");
  jw_str(w, k->name);
  jw_key(w, "abbr");
  jw_str(w, k->abbr);
  jw_key(w, "credits");
  jw_str(w, k->credits);
  licence(w, kind_licence(k->id));
  jw_key(w, "flags");
  jw_arr(w);
  if (k->flags & FM1_MOD_KIND_TRANSPORT) jw_str(w, "transport");
  if (k->flags & FM1_MOD_KIND_POLY_OK) jw_str(w, "poly_ok");
  if (k->flags & FM1_MOD_KIND_AUDIO_TAP) jw_str(w, "audio_tap");
  jw_end(w);
  jw_key(w, "ram");
  jw_int(w, (long long)k->instance_size(host));
  jw_key(w, "data");
  if (k->data_bytes) {
    jw_open(w, '{', '}', 1);
    jw_key(w, "bytes");
    jw_int(w, k->data_bytes);
    jw_key(w, "version");
    jw_int(w, k->data_version);
    jw_end(w);
  } else {
    jw_null(w);
  }
  page_names(w, k->id, k->params, k->n_params);
  jw_key(w, "params");
  params(w, k->params, k->n_params, 0, FM1_ALIAS_MOD, k->id);
  ports(w, "gates", k->gate_in, k->n_gate_in, 1);
  ports(w, "outs", k->out, k->n_out, 0);
  jw_end(w);
}

static int in_build(const char *id) {
  size_t i;
  if (fm1_engine_find(id) || fm1_midi_fx_find(id)) return 1;
  for (i = 0; i < fm1_mod_kind_count; ++i) {
    if (!strcmp(fm1_mod_kinds[i]->id, id)) return 1;
  }
  return 0;
}

/* 1.2: how a patch bay groups the system sources, in the order it lists
 * them (the editor's Map and its search). The sound group is one per sound:
 * a source's `sound` says which, and {sound} in the name is that number. */
static const struct { const char *id; const char *name; } kSourceGroups[] = {
  { "notes", "Notes, clock and chance" },
  { "sound", "Sound {sound}'s notes" },
  { "lanes", "Sequencer lanes" },
  { "lane_values", "Lane values" },
};

static const char *source_group(unsigned id) {
  if (id >= FM1_MOD_SRC_S_NOTE) return "sound";                        /* S1NOTE ... S4RTRG */
  if (id >= FM1_MOD_SRC_SEQ_VEL && id < FM1_MOD_SRC_SEQ_VEL + 8u) return "lane_values";   /* SQV1-8 */
  if (id >= FM1_MOD_SRC_SEQ_GATE && id < FM1_MOD_SRC_SEQ_GATE + 8u) return "lanes";       /* SEQ1-8 */
  return "notes";
}

static void mod(jw_t *w, const fm1_host_t *host) {
  static const char *const kPolarities[] = { "auto", "uni", "bi", "inv" };
  static const char *const kCurves[] = { "lin", "square", "cube", "root", "cbrt", "exp", "log", "s" };
  unsigned i;
  jw_key(w, "mod");
  jw_obj(w);
  jw_key(w, "positions");
  jw_int(w, FM1_MOD_POSITIONS);
  jw_key(w, "slots");
  jw_int(w, FM1_MOD_SLOTS);
  jw_key(w, "tick");
  jw_int(w, FM1_MOD_TICK);
  /* 1.3: how ids are laid out, and the chain's shape: a module's outputs are
   * source_base + source_stride x position + port, its parameters and gate
   * inputs unit_base + position; the app's chain is `sounds` sound units
   * with `inserts` insert slots each and `masters` master effect slots. */
  jw_key(w, "source_base");
  jw_int(w, FM1_MOD_SRC_MODULE);
  jw_key(w, "source_stride");
  jw_int(w, FM1_MOD_MAX_OUTS);
  jw_key(w, "unit_base");
  jw_int(w, FM1_MOD_MODULE);
  jw_key(w, "sounds");
  jw_int(w, FM1_MOD_SOUNDS);
  jw_key(w, "inserts");
  jw_int(w, FM1_MOD_INSERTS);
  jw_key(w, "masters");
  jw_int(w, FM1_MOD_MASTERS);
  jw_key(w, "kinds");
  jw_arr(w);
  for (i = 0; i < fm1_mod_kind_count; ++i) mod_kind(w, fm1_mod_kinds[i], host);
  jw_end(w);
  jw_key(w, "sources");
  jw_arr(w);
  for (i = 0; i < FM1_MOD_SRC_SYSTEM; ++i) {
    const fm1_mod_source_info_t *si = fm1_mod_system_source(i);
    if (!si) continue;
    jw_obj(w);
    jw_key(w, "id");
    jw_int(w, i);
    jw_key(w, "name");
    jw_str(w, si->name);
    jw_key(w, "kind");
    jw_str(w, port_kind(si->kind));
    jw_key(w, "unit");
    jw_str(w, unit_name(si->unit));
    jw_key(w, "group");                                        /* 1.2 */
    jw_str(w, source_group(i));
    if (i >= FM1_MOD_SRC_S_NOTE && i < FM1_MOD_SRC_SYSTEM) {   /* S1NOTE ... S4RTRG */
      jw_key(w, "sound");
      jw_int(w, (i - FM1_MOD_SRC_S_NOTE) % 4u + 1u);
    }
    jw_end(w);
  }
  jw_end(w);
  jw_key(w, "source_groups");        /* 1.2: how a patch bay lists the sources */
  jw_arr(w);
  for (i = 0; i < sizeof kSourceGroups / sizeof kSourceGroups[0]; ++i) {
    jw_obj(w);
    jw_key(w, "id");
    jw_str(w, kSourceGroups[i].id);
    jw_key(w, "name");
    jw_str(w, kSourceGroups[i].name);
    jw_end(w);
  }
  jw_end(w);
  jw_key(w, "curve_points");         /* 1.2: each curve (`curves`, in order) at s = -1 .. 1 in 33 steps */
  jw_arr(w);
  for (i = 0; i < FM1_MOD_CURVE_COUNT; ++i) {
    unsigned k;
    jw_open(w, '[', ']', 1);           /* an array of numbers is written on one line (state_canon.py) */
    for (k = 0; k < 33u; ++k) jw_f32(w, fm1_mod_curve(i, -1.0f + (float)k * (1.0f / 16.0f)));
    jw_end(w);
  }
  jw_end(w);
  jw_key(w, "units");
  jw_arr(w);
  for (i = 0; i < FM1_MOD_SINKS; ++i) {
    const unsigned code = fm1_mod_sink_unit(i);
    const char *name = fm1_mod_script_unit_name(code);
    jw_obj(w);
    jw_key(w, "name");
    jw_str(w, name && !strcmp(name, "snd") ? "snd1" : name);   /* files say snd1 */
    jw_key(w, "code");
    jw_int(w, code);
    jw_end(w);
  }
  jw_end(w);
  jw_key(w, "host");                 /* not on a knob page: every one hidden */
  params(w, fm1_mod_host_params, FM1_MOD_HOST_PARAMS, 1, 0, "host");
  jw_key(w, "polarities");
  jw_arr(w);
  for (i = 0; i < 4u; ++i) jw_str(w, kPolarities[i]);
  jw_end(w);
  jw_key(w, "curves");
  jw_arr(w);
  for (i = 0; i < FM1_MOD_CURVE_COUNT; ++i) jw_str(w, kCurves[i]);
  jw_end(w);
  jw_end(w);
}

static void byte_fields(jw_t *w, const char *key, const fm1_dx7_field_t *f, unsigned n) {
  unsigned i;
  jw_key(w, key);
  jw_arr(w);
  for (i = 0; i < n; ++i) {
    jw_obj(w);
    jw_key(w, "name");
    jw_str(w, f[i].name);
    jw_key(w, "max");
    jw_int(w, f[i].max);
    jw_end(w);
  }
  jw_end(w);
}

void fm1_meta_build_default(fm1_meta_build_t *b) {
  memset(b, 0, sizeof(*b));
  b->by = "desktop";
#ifdef FM1_BUILD_VERSION
  b->version = FM1_BUILD_VERSION;
#else
  b->version = "0.0.0";
#endif
#ifdef FM1_BUILD_COMMIT
  b->commit = FM1_BUILD_COMMIT;
#else
  b->commit = "0000000";
#endif
  b->rate = FM1_META_RATE;
  b->ram_budget = FM1_META_RAM_BUDGET;
  /* The registry's switch (fm1_engine.h): this file is built without the
   * generated fm1_gpl_mods.h, so an #ifdef here always read it as off. */
  b->gpl = fm1_gpl_mods ? 1 : 0;
}

/* ---- 1.1: what the advanced editor reads besides the parameters ---------------------- */

static void effect_groups(jw_t *w) {
  size_t i;
  jw_key(w, "effect_groups");
  jw_arr(w);
  for (i = 0; i < fm1_fx_group_count; ++i) {
    jw_obj(w);
    jw_key(w, "id");
    jw_str(w, fm1_fx_groups[i].id);
    jw_key(w, "name");
    jw_str(w, fm1_fx_groups[i].name);
    jw_end(w);
  }
  jw_end(w);
}

/* The {fills} a refusal's detail names, in order, each once. */
static void fills(jw_t *w, const char *detail) {
  const char *s = detail;
  char seen[16][16];
  unsigned n = 0, k;
  jw_key(w, "fills");
  jw_arr(w);
  while (s && (s = strchr(s, '{')) != NULL) {
    const char *e = strchr(s, '}');
    char name[16];
    size_t len;
    if (!e) break;
    len = (size_t)(e - s - 1);
    if (len && len < sizeof(name)) {
      memcpy(name, s + 1, len);
      name[len] = 0;
      for (k = 0; k < n && strcmp(seen[k], name); ++k) {}
      if (k == n && n < 16u) {
        memcpy(seen[n++], name, len + 1);
        jw_str(w, name);
      }
    }
    s = e + 1;
  }
  jw_end(w);
}

static void refusals(jw_t *w) {
  static const char *const kReasons[] = { "gpl", "planned", "retired", "list" };
  size_t i;
  jw_key(w, "refusals");
  jw_obj(w);
  jw_key(w, "codes");
  jw_arr(w);
  for (i = 0; i < fm1_refusal_count; ++i) {
    const fm1_refusal_t *r = &fm1_refusals[i];
    const char *of = r->of;
    jw_obj(w);
    jw_key(w, "code");
    jw_int(w, r->code);
    jw_key(w, "name");
    jw_str(w, r->name);
    jw_key(w, "of");
    jw_arr(w);
    while (of && *of) {                            /* "load,unit" -> ["load", "unit"] */
      const char *c = strchr(of, ',');
      const size_t len = c ? (size_t)(c - of) : strlen(of);
      char part[16];
      if (len < sizeof(part)) {
        memcpy(part, of, len);
        part[len] = 0;
        jw_str(w, part);
      }
      of = c ? c + 1 : NULL;
    }
    jw_end(w);
    jw_key(w, "words");
    jw_str(w, r->words);
    jw_key(w, "detail");
    if (r->detail) jw_str(w, r->detail); else jw_null(w);
    fills(w, r->detail);
    if (r->fix) {                                  /* 1.2: the repair offered beside it */
      jw_key(w, "fix");
      jw_obj(w);
      jw_key(w, "id");
      jw_str(w, r->fix);
      jw_key(w, "words");
      jw_str(w, r->fix_words ? r->fix_words : r->fix);
      jw_end(w);
    }
    jw_end(w);
  }
  jw_end(w);
  jw_key(w, "known");                              /* a known id's reason, in words */
  jw_arr(w);
  for (i = 0; i < sizeof(kReasons) / sizeof(kReasons[0]); ++i) {
    jw_obj(w);
    jw_key(w, "reason");
    jw_str(w, kReasons[i]);
    jw_key(w, "words");
    jw_str(w, fm1_refusal_known_words(kReasons[i]));
    jw_end(w);
  }
  jw_end(w);
  jw_end(w);
}

static void names(jw_t *w, const char *key, unsigned s, unsigned n,
                  const char *(*name)(unsigned, unsigned, char *, size_t)) {
  unsigned k;
  char buf[24];
  jw_key(w, key);
  jw_arr(w);
  for (k = 0; k < n; ++k) jw_str(w, name(s, k, buf, sizeof(buf)));
  jw_end(w);
}

/* 1.2: the marks of a matrix row (fm1_marks). */
static void marks(jw_t *w) {
  size_t i;
  jw_key(w, "marks");
  jw_arr(w);
  for (i = 0; i < fm1_mark_count; ++i) {
    const fm1_mark_t *m = &fm1_marks[i];
    char c[2];
    c[0] = m->mark;
    c[1] = 0;
    jw_obj(w);
    jw_key(w, "mark");
    jw_str(w, c);
    jw_key(w, "name");
    jw_str(w, m->name);
    jw_key(w, "words");
    jw_str(w, m->words);
    jw_key(w, "detail");
    if (m->detail) jw_str(w, m->detail); else jw_null(w);
    fills(w, m->detail);
    jw_end(w);
  }
  jw_end(w);
}

static void telemetry(jw_t *w) {
  unsigned k;
  jw_key(w, "telemetry");
  jw_obj(w);
  jw_key(w, "version");
  jw_int(w, FM1_TELE_VERSION);
  jw_key(w, "hz");
  jw_int(w, FM1_TELE_HZ);
  jw_key(w, "floats");
  jw_int(w, fm1_tele_floats());
  jw_key(w, "mask_words");
  jw_int(w, FM1_TELE_MASK_WORDS);
  jw_key(w, "sections");
  jw_arr(w);
  for (k = 0; k < FM1_TELE_SECTIONS; ++k) {
    const fm1_tele_section_t *sec = fm1_tele_section(k);
    jw_obj(w);
    jw_key(w, "name");
    jw_str(w, sec->name);
    jw_key(w, "unit");
    jw_str(w, sec->unit);
    jw_key(w, "offset");
    jw_int(w, sec->offset);
    jw_key(w, "mask");
    jw_int(w, sec->mask);
    names(w, "rows", k, sec->rows, fm1_tele_row_name);
    names(w, "items", k, sec->items > 1 ? sec->items : 0u, fm1_tele_item_name);
    names(w, "fields", k, sec->fields, fm1_tele_field_name);
    jw_end(w);
  }
  jw_end(w);
  jw_end(w);
}

/* The document; for_id leaves out `made` and `meta_id` (fm1_meta_id). */
static size_t write_doc(const fm1_meta_build_t *b, fm1_meta_put_t put, void *ctx, int for_id,
                        uint32_t id) {
  static const char *const kRoots[12] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A",
                                          "A#", "B" };
  /* The project key's scales, by FM1_KEY_* (the church modes since
   * 2026-10-06); tests/test_engine_metadata.py holds the list to them. */
  static const char *const kScaleIds[FM1_KEY_SCALES] = {
    "major", "minor", "chromatic", "dorian", "phrygian", "lydian", "mixolydian", "locrian",
  };
  static const char *const kScaleNames[FM1_KEY_SCALES] = {
    "Major", "Minor", "Chromatic", "Dorian", "Phrygian", "Lydian", "Mixolydian", "Locrian",
  };
  fm1_host_t host;
  jw_t w;
  size_t i;
  memset(&w, 0, sizeof(w));
  w.put = put;
  w.ctx = ctx;
  host.api_version = FM1_ENGINE_API_VERSION;
  host.sample_rate = (float)b->rate;
  host.max_frames = 64;

  jw_obj(&w);
  jw_key(&w, "lunar");
  jw_str(&w, FM1_META_LUNAR);
  jw_key(&w, "kind");
  jw_str(&w, "metadata");
  if (!for_id) {
    jw_key(&w, "made");
    jw_open(&w, '{', '}', 1);
    jw_key(&w, "by");
    jw_str(&w, b->by);
    jw_key(&w, "version");
    jw_str(&w, b->version);
    jw_key(&w, "commit");
    jw_str(&w, b->commit);
    jw_end(&w);
  }

  jw_key(&w, "build");
  jw_obj(&w);
  jw_key(&w, "engine_api");
  jw_int(&w, FM1_ENGINE_API_VERSION);
  jw_key(&w, "mod_api");
  jw_int(&w, FM1_MOD_API_VERSION);
  jw_key(&w, "rate");
  jw_int(&w, b->rate);
  jw_key(&w, "ram_budget");
  jw_int(&w, b->ram_budget);
  jw_key(&w, "gpl");
  jw_bool(&w, b->gpl);
  jw_key(&w, "modules");                         /* the module list's name (FM1_MODULES) */
  jw_str(&w, fm1_modules_name);
  jw_end(&w);

  jw_key(&w, "engines");
  jw_arr(&w);
  for (i = 0; i < fm1_engine_count; ++i) engine(&w, fm1_engines[i], &host);
  for (i = 0; i < fm1_midi_fx_count; ++i) engine(&w, &fm1_midi_fxs[i]->engine, &host);
  jw_end(&w);

  mod(&w, &host);

  jw_key(&w, "dx7");
  jw_obj(&w);
  jw_key(&w, "user_slots");
  jw_int(&w, FM1_DX7_USER_SLOTS);
  jw_key(&w, "name_chars");
  jw_int(&w, FM1_DX7_NAME_BYTES);
  byte_fields(&w, "op_fields", fm1_dx7_op_fields, FM1_DX7_OP_FIELDS);
  byte_fields(&w, "voice_fields", fm1_dx7_voice_fields, FM1_DX7_VOICE_FIELDS);
  jw_end(&w);

  jw_key(&w, "keys");
  jw_obj(&w);
  jw_key(&w, "roots");
  jw_arr(&w);
  for (i = 0; i < 12; ++i) jw_str(&w, kRoots[i]);
  jw_end(&w);
  jw_key(&w, "scales");
  jw_arr(&w);
  for (i = 0; i < FM1_KEY_SCALES; ++i) {
    jw_obj(&w);
    jw_key(&w, "id");
    jw_str(&w, kScaleIds[i]);
    jw_key(&w, "name");
    jw_str(&w, kScaleNames[i]);
    jw_end(&w);
  }
  jw_end(&w);
  jw_end(&w);

  jw_key(&w, "known_ids");
  jw_arr(&w);
  /* The modules the list leaves out (reason "list"), then known-ids.json's
   * ids the build lacks for their own reason. */
  for (i = 0; i < fm1_left_out_count + fm1_known_id_count; ++i) {
    const fm1_known_id_t *k = i < fm1_left_out_count ? &fm1_left_out[i]
                                                     : &fm1_known_ids[i - fm1_left_out_count];
    if (in_build(k->id)) continue;               /* the build has it: nothing to explain */
    if (i >= fm1_left_out_count && fm1_absent_find(k->id) != k) continue;   /* said above */
    jw_obj(&w);
    jw_key(&w, "id");
    jw_str(&w, k->id);
    jw_key(&w, "what");
    jw_str(&w, k->what);
    jw_key(&w, "reason");
    jw_str(&w, k->reason);
    if (k->since) {
      jw_key(&w, "since");
      jw_str(&w, k->since);
    }
    jw_end(&w);
  }
  jw_end(&w);

  jw_key(&w, "limits");
  jw_obj(&w);
  jw_key(&w, "bytes");
  jw_obj(&w);
  jw_key(&w, "project");
  jw_int(&w, FM1_STATE_CAP_PROJECT);
  jw_key(&w, "sound");
  jw_int(&w, FM1_STATE_CAP_SOUND);
  jw_key(&w, "fx");
  jw_int(&w, FM1_STATE_CAP_FX);
  jw_key(&w, "mods");
  jw_int(&w, FM1_STATE_CAP_MODS);
  jw_key(&w, "clip");
  jw_int(&w, FM1_STATE_CAP_CLIP);
  jw_key(&w, "settings");
  jw_int(&w, FM1_STATE_CAP_SETTINGS);
  jw_key(&w, "movy1");
  jw_int(&w, FM1_STATE_CAP_MOVY1);
  jw_key(&w, "syx");
  jw_int(&w, FM1_STATE_CAP_SYX);
  jw_end(&w);
  jw_key(&w, "depth");
  jw_int(&w, FM1_STATE_CAP_DEPTH);
  jw_key(&w, "string_bytes");
  jw_int(&w, FM1_STATE_CAP_STRING);
  jw_key(&w, "key_bytes");
  jw_int(&w, FM1_STATE_CAP_KEY);
  jw_key(&w, "number_chars");
  jw_int(&w, FM1_STATE_CAP_NUMBER);
  jw_key(&w, "members");
  jw_int(&w, FM1_STATE_CAP_MEMBERS);
  jw_key(&w, "items");
  jw_int(&w, FM1_STATE_CAP_ITEMS);
  jw_end(&w);

  effect_groups(&w);
  refusals(&w);
  marks(&w);
  telemetry(&w);
  if (!for_id) {
    static const char kHex[] = "0123456789abcdef";
    char hex[9];
    int k;
    for (k = 0; k < 8; ++k) hex[k] = kHex[(id >> (28 - 4 * k)) & 15u];
    hex[8] = 0;
    jw_key(&w, "meta_id");
    jw_str(&w, hex);
  }

  jw_end(&w);
  jw_raw(&w, "\n", 1);
  return w.bytes;
}

/* CRC-32, zlib's (reflected 0xEDB88320), a byte at a time from a table made
 * at the first call: the whole id takes a few milliseconds, once. */
static void crc_put(void *ctx, const char *bytes, size_t n) {
  static uint32_t table[256];
  static int made;
  uint32_t c = ~*(uint32_t *)ctx;
  size_t i;
  if (!made) {
    uint32_t k, b;
    for (k = 0; k < 256u; ++k) {
      uint32_t r = k;
      for (b = 0; b < 8u; ++b) r = (r >> 1) ^ (0xEDB88320u & (0u - (r & 1u)));
      table[k] = r;
    }
    made = 1;
  }
  for (i = 0; i < n; ++i) c = table[(c ^ (uint8_t)bytes[i]) & 0xFFu] ^ (c >> 8);
  *(uint32_t *)ctx = ~c;
}

uint32_t fm1_meta_id_of(const fm1_meta_build_t *b) {
  uint32_t crc = 0;
  (void)write_doc(b, crc_put, &crc, 1, 0);
  return crc;
}

uint32_t fm1_meta_id(void) {
  static uint32_t id;
  static int done;
  if (!done) {
    fm1_meta_build_t b;
    fm1_meta_build_default(&b);
    id = fm1_meta_id_of(&b);
    done = 1;
  }
  return id;
}

size_t fm1_meta_write(const fm1_meta_build_t *b, fm1_meta_put_t put, void *ctx) {
  return write_doc(b, put, ctx, 0, fm1_meta_id_of(b));
}
