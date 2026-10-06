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
#include "fm1_known.h"
#include "fm1_mod.h"
#include "fm1_state_caps.h"
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
 * parameter's range has neither). */
static void f32_text(float v, char out[40]) {
  char e[40], digits[16];
  int p, k = 0, n, exp10;
  const char *q;
  char *o = out;
  if (v == 0.0f || v != v || v - v != 0.0f) {
    strcpy(out, "0");
    return;
  }
  for (p = 1; p <= 9; ++p) {
    snprintf(e, sizeof(e), "%.*e", p - 1, (double)v);
    if (strtof(e, NULL) == v) break;
  }
  q = e;
  if (*q == '-') *o++ = *q++;
  for (; *q && *q != 'e'; ++q) {
    if (*q >= '0' && *q <= '9' && k < 15) digits[k++] = *q;
  }
  while (k > 1 && digits[k - 1] == '0') --k;
  digits[k] = '\0';
  exp10 = atoi(q + 1);
  n = exp10 + 1;                                  /* value = 0.digits x 10^n */
  if (k <= n && n <= 21) {
    memcpy(o, digits, (size_t)k);
    o += k;
    for (; n > k; --n) *o++ = '0';
  } else if (0 < n && n <= 21) {
    memcpy(o, digits, (size_t)n);
    o += n;
    *o++ = '.';
    memcpy(o, digits + n, (size_t)(k - n));
    o += k - n;
  } else if (-6 < n && n <= 0) {
    *o++ = '0';
    *o++ = '.';
    for (; n < 0; ++n) *o++ = '0';
    memcpy(o, digits, (size_t)k);
    o += k;
  } else {
    *o++ = digits[0];
    if (k > 1) {
      *o++ = '.';
      memcpy(o, digits + 1, (size_t)(k - 1));
      o += k - 1;
    }
    o += sprintf(o, "e%c%d", exp10 > 0 ? '+' : '-', exp10 > 0 ? exp10 : -exp10);
  }
  *o = '\0';
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
      if (al->owner != owner || strcmp(al->id, id) || al->uid != p->uid || al->entry >= 0) continue;
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
  jw_key(w, "credits");
  jw_str(w, e->credits);
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
  jw_key(w, "params");
  params(w, e->params, e->n_params, 0, FM1_ALIAS_ENGINE, e->id);
  jw_end(w);
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
    if (i >= FM1_MOD_SRC_S_NOTE && i < FM1_MOD_SRC_SYSTEM) {   /* S1NOTE ... S4RTRG */
      jw_key(w, "sound");
      jw_int(w, (i - FM1_MOD_SRC_S_NOTE) % 4u + 1u);
    }
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
#if defined(FM1_GPL_MODS) && (FM1_GPL_MODS + 0)
  b->gpl = 1;
#else
  b->gpl = 0;
#endif
}

size_t fm1_meta_write(const fm1_meta_build_t *b, fm1_meta_put_t put, void *ctx) {
  static const char *const kRoots[12] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A",
                                          "A#", "B" };
  /* The project key's scales, by FM1_KEY_*. */
  static const char *const kScaleIds[] = { "major", "minor", "chromatic" };
  static const char *const kScaleNames[] = { "Major", "Minor", "Chromatic" };
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
  jw_key(&w, "made");
  jw_open(&w, '{', '}', 1);
  jw_key(&w, "by");
  jw_str(&w, b->by);
  jw_key(&w, "version");
  jw_str(&w, b->version);
  jw_key(&w, "commit");
  jw_str(&w, b->commit);
  jw_end(&w);

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
  for (i = 0; i < sizeof(kScaleIds) / sizeof(kScaleIds[0]); ++i) {
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
  for (i = 0; i < fm1_known_id_count; ++i) {
    const fm1_known_id_t *k = &fm1_known_ids[i];
    if (in_build(k->id)) continue;               /* the build has it: nothing to explain */
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

  jw_end(&w);
  jw_raw(&w, "\n", 1);
  return w.bytes;
}
