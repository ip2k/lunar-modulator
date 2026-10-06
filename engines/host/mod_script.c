/* mod_script.c -- fm1-render's text format for the modulation runtime
 * (mod_script.h). Desktop host code. MIT licence. */
#include "mod_script.h"

#include <ctype.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_TOK 24
#define TOK_LEN 64

static int fail(char *err, size_t cap, const char *fmt, ...) {
  va_list ap;
  if (err && cap) {
    va_start(ap, fmt);
    vsnprintf(err, cap, fmt, ap);
    va_end(ap);
  }
  return 0;
}

static int same(const char *a, const char *b) {
  for (; *a && *b; ++a, ++b) {
    if (tolower((unsigned char)*a) != tolower((unsigned char)*b)) return 0;
  }
  return *a == *b;
}

/* Splits on blanks; '#' ends the line. */
static int tokens(const char *line, char tok[MAX_TOK][TOK_LEN]) {
  int n = 0;
  const char *p = line;
  for (;;) {
    size_t k = 0;
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') ++p;
    if (!*p || *p == '#' || n == MAX_TOK) break;
    while (*p && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n' && *p != '#') {
      if (k + 1 < TOK_LEN) tok[n][k++] = *p;
      ++p;
    }
    tok[n++][k] = '\0';
  }
  return n;
}

static int number(const char *s, double *out) {
  char *end = NULL;
  *out = strtod(s, &end);
  return end != s && *end == '\0';
}

/* A position 1..8 written as text. */
static int position(const char *s, unsigned *pos) {
  double v;
  if (!number(s, &v) || v < 1 || v > FM1_MOD_POSITIONS || v != (double)(unsigned)v) return 0;
  *pos = (unsigned)v - 1u;
  return 1;
}

/* A parameter of `params` by name or abbreviation. */
static int find_param(const fm1_param_t *params, unsigned n, const char *name) {
  unsigned i;
  for (i = 0; i < n; ++i) {
    if (same(params[i].name, name) || (params[i].abbr && same(params[i].abbr, name))) return (int)i;
  }
  return -1;
}

/* A value for parameter p: a number, or an ENUM value's name. */
static int param_value(const fm1_param_t *p, const char *s, float *out) {
  double v;
  if (number(s, &v)) {
    *out = (float)v;
    return 1;
  }
  if (p->type == FM1_PARAM_ENUM && p->enum_names) {
    const int n = (int)(p->max - p->min) + 1;
    int k;
    for (k = 0; k < n; ++k) {
      if (same(p->enum_names[k], s)) {
        *out = p->min + (float)k;
        return 1;
      }
    }
  }
  return 0;
}

/* "lfo3" or "mod3": the kind (or "mod") and the position. */
static int module_ref(const fm1_mod_t *m, const char *s, size_t len, unsigned *pos, char *err,
                      size_t cap) {
  char name[TOK_LEN];
  size_t k = 0;
  int kind;
  while (k < len && !isdigit((unsigned char)s[k])) ++k;
  if (k == 0 || k == len || k >= sizeof(name)) return 0;
  memcpy(name, s, k);
  name[k] = '\0';
  {
    char num[TOK_LEN];
    if (len - k >= sizeof(num)) return 0;
    memcpy(num, s + k, len - k);
    num[len - k] = '\0';
    if (!position(num, pos)) return 0;
  }
  if (same(name, "mod")) return 1;
  kind = fm1_mod_kind_find(name);
  if (kind < 0) return 0;
  if (fm1_mod_kind_at(m, *pos) != kind) {
    return fail(err, cap, "position %u holds no %s", *pos + 1u, name);
  }
  return 1;
}

static int parse_src(const fm1_mod_t *m, const char *s, uint8_t *out, char *err, size_t cap) {
  const char *dot = strchr(s, '.');
  const size_t len = dot ? (size_t)(dot - s) : strlen(s);
  unsigned id, pos, port = 0;
  const fm1_mod_kind_t *kd;
  for (id = 0; id < FM1_MOD_SRC_SYSTEM; ++id) {
    const fm1_mod_source_info_t *si = fm1_mod_system_source(id);
    if (si && !dot && same(si->name, s)) {
      *out = (uint8_t)id;
      return 1;
    }
  }
  if (!module_ref(m, s, len, &pos, err, cap)) {
    if (err && cap && !err[0]) fail(err, cap, "unknown source %s", s);
    return 0;
  }
  kd = fm1_mod_kind_at(m, pos) >= 0 ? fm1_mod_kinds[fm1_mod_kind_at(m, pos)] : NULL;
  if (dot) {
    double v;
    if (number(dot + 1, &v) && v >= 1 && v <= FM1_MOD_MAX_OUTS) {
      port = (unsigned)v - 1u;
    } else {
      unsigned k;
      for (k = 0; kd && k < kd->n_out; ++k) {
        if (same(kd->out[k].name, dot + 1)) break;
      }
      if (!kd || k == kd->n_out) return fail(err, cap, "no output %s", s);
      port = k;
    }
  }
  *out = (uint8_t)(FM1_MOD_SRC_MODULE + 8u * pos + port);
  return 1;
}

/* The sinks' names, by code: snd (sound unit 1), snd2-snd4, sndK.fxJ for
 * the inserts, fx1 and fx2 for the master slots, host. */
const char *fm1_mod_script_unit_name(unsigned unit) {
  static const char *const kSounds[] = { "snd", "snd2", "snd3", "snd4" };
  static const char *const kInserts[] = { "snd1.fx1", "snd1.fx2", "snd2.fx1", "snd2.fx2",
                                          "snd3.fx1", "snd3.fx2", "snd4.fx1", "snd4.fx2" };
  const int k = fm1_mod_unit_sound(unit);
  unit = fm1_mod_unit_canonical(unit);
  if (k >= 0) return kSounds[k];
  if (unit == FM1_MOD_FX1) return "fx1";
  if (unit == FM1_MOD_FX2) return "fx2";
  if (unit == FM1_MOD_HOST) return "host";
  if (unit >= FM1_MOD_INSERT && unit < FM1_MOD_INSERT + 4u * FM1_MOD_SOUNDS &&
      (unit - FM1_MOD_INSERT) % 4u < FM1_MOD_INSERTS) {
    return kInserts[(unit - FM1_MOD_INSERT) / 4u * FM1_MOD_INSERTS + (unit - FM1_MOD_INSERT) % 4u];
  }
  return NULL;
}

/* A sink's code from its name (len characters of s), FM1_MOD_NONE for none:
 * the names above, and snd1 and snd.fxJ for sound unit 1. */
static unsigned unit_of_name(const char *s, size_t len) {
  char name[TOK_LEN];
  unsigned i;
  if (len >= sizeof(name)) return FM1_MOD_NONE;
  memcpy(name, s, len);
  name[len] = '\0';
  if (same(name, "snd1")) return FM1_MOD_SOUND;
  if (same(name, "snd.fx1") || same(name, "snd.fx2")) {
    return fm1_mod_insert_unit(0, (unsigned)(name[6] - '1'));
  }
  for (i = 0; i < FM1_MOD_SINKS; ++i) {
    const unsigned u = fm1_mod_sink_unit(i);
    const char *n = fm1_mod_script_unit_name(u);
    if (n && same(n, name)) return u;
  }
  return FM1_MOD_NONE;
}

static int parse_dst(const fm1_mod_t *m, const fm1_engine_t *const units[FM1_MOD_SINKS],
                     const char *s, fm1_mod_slot_t *slot, char *err, size_t cap) {
  const char *sep = strchr(s, ':') ? strchr(s, ':') : strchr(s, '.');
  unsigned pos, unit;
  int i;
  if (!sep) return fail(err, cap, "destination %s wants UNIT:NAME", s);
  unit = unit_of_name(s, (size_t)(sep - s));
  if (unit != FM1_MOD_NONE && unit != FM1_MOD_HOST) {
    const fm1_engine_t *e = units[fm1_mod_sink_index(unit)];
    const char *name = fm1_mod_script_unit_name(unit);
    if (!e) return fail(err, cap, "%s has no engine", name);
    i = find_param(e->params, e->n_params, sep + 1);
    if (i < 0) return fail(err, cap, "%s has no parameter %s", e->id, sep + 1);
    slot->dst_unit = (uint8_t)unit;
    slot->dst = e->params[i].uid;
    return 1;
  }
  if ((size_t)(sep - s) == 4u && strncmp(s, "host", 4) == 0) {
    i = find_param(fm1_mod_host_params, FM1_MOD_HOST_PARAMS, sep + 1);
    if (i < 0) return fail(err, cap, "host has no parameter %s", sep + 1);
    slot->dst_unit = FM1_MOD_HOST;
    slot->dst = fm1_mod_host_params[i].uid;
    return 1;
  }
  if (!module_ref(m, s, (size_t)(sep - s), &pos, err, cap)) {
    if (err && cap && !err[0]) fail(err, cap, "unknown destination %s", s);
    return 0;
  }
  {
    const int k = fm1_mod_kind_at(m, pos);
    const fm1_mod_kind_t *kd = k >= 0 ? fm1_mod_kinds[k] : NULL;
    unsigned g;
    if (!kd) return fail(err, cap, "position %u is empty", pos + 1u);
    slot->dst_unit = (uint8_t)(FM1_MOD_MODULE + pos);
    i = find_param(kd->params, kd->n_params, sep + 1);
    if (i >= 0) {
      slot->dst = kd->params[i].uid;
      return 1;
    }
    for (g = 0; g < kd->n_gate_in; ++g) {
      if (same(kd->gate_in[g].name, sep + 1)) {
        slot->dst = (uint16_t)g;
        slot->flags = (uint8_t)(slot->flags | FM1_MOD_SLOT_GATE_DST);
        return 1;
      }
    }
    return fail(err, cap, "%s has no parameter or gate %s", kd->id, sep + 1);
  }
}

static int set_params(fm1_mod_t *m, unsigned pos, char tok[MAX_TOK][TOK_LEN], int from, int n,
                      char *err, size_t cap) {
  const int k = fm1_mod_kind_at(m, pos);
  const fm1_mod_kind_t *kd = k >= 0 ? fm1_mod_kinds[k] : NULL;
  int t;
  if (!kd) return fail(err, cap, "position %u is empty", pos + 1u);
  for (t = from; t < n; ++t) {
    char *eq = strchr(tok[t], '=');
    int i;
    float v;
    if (!eq) return fail(err, cap, "want NAME=VALUE, got %s", tok[t]);
    *eq = '\0';
    i = find_param(kd->params, kd->n_params, tok[t]);
    if (i < 0) return fail(err, cap, "%s has no parameter %s", kd->id, tok[t]);
    if (!param_value(&kd->params[i], eq + 1, &v)) return fail(err, cap, "bad value %s", eq + 1);
    fm1_mod_set_param(m, pos, (unsigned)i, v);
  }
  return 1;
}

static int slot_line(fm1_mod_t *m, const fm1_engine_t *const units[FM1_MOD_SINKS],
                     char tok[MAX_TOK][TOK_LEN], int n, char *err, size_t cap) {
  static const char *const kPol[] = { "auto", "uni", "bi", "inv" };
  static const char *const kCurve[] = { "lin", "square", "cube", "root", "cbrt", "exp", "log", "s" };
  fm1_mod_slot_t s;
  double v;
  unsigned i;
  int t;
  if (n < 3 || !number(tok[1], &v) || v < 1 || v > FM1_MOD_SLOTS || v != (double)(unsigned)v) {
    return fail(err, cap, "slot wants a number 1-%u", FM1_MOD_SLOTS);
  }
  i = (unsigned)v - 1u;
  fm1_mod_get_slot(m, i, &s);
  if (n == 3 && (same(tok[2], "on") || same(tok[2], "off") || same(tok[2], "clear"))) {
    if (same(tok[2], "clear")) {
      memset(&s, 0, sizeof(s));
      s.via = FM1_MOD_NONE;
    } else if (same(tok[2], "on")) {
      s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_ON);
    } else {
      s.flags = (uint8_t)(s.flags & ~FM1_MOD_SLOT_ON);
    }
    fm1_mod_set_slot(m, i, &s);
    return 1;
  }
  if (n < 5 || strcmp(tok[3], ">") != 0) return fail(err, cap, "slot wants SRC > DST");
  memset(&s, 0, sizeof(s));
  s.via = FM1_MOD_NONE;
  s.flags = FM1_MOD_SLOT_ON;
  s.amount = FM1_MOD_Q14;
  if (!parse_src(m, tok[2], &s.src, err, cap)) return 0;
  if (!parse_dst(m, units, tok[4], &s, err, cap)) return 0;
  for (t = 5; t < n; ++t) {
    char *eq = strchr(tok[t], '=');
    if (same(tok[t], "off")) {
      s.flags = (uint8_t)(s.flags & ~FM1_MOD_SLOT_ON);
      continue;
    }
    if (same(tok[t], "voice")) {
      s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_VOICE);
      continue;
    }
    if (!eq) return fail(err, cap, "unknown slot option %s", tok[t]);
    *eq = '\0';
    if (same(tok[t], "amt") || same(tok[t], "ofs")) {
      if (!number(eq + 1, &v)) return fail(err, cap, "bad %s", tok[t]);
      if (same(tok[t], "amt")) s.amount = fm1_mod_q14((float)(v / 100.0));
      else s.offset = fm1_mod_q14((float)(v / 100.0));
    } else if (same(tok[t], "via")) {
      if (!parse_src(m, eq + 1, &s.via, err, cap)) return 0;
    } else if (same(tok[t], "pol") || same(tok[t], "curve")) {
      const int pol = same(tok[t], "pol");
      const char *const *names = pol ? kPol : kCurve;
      const unsigned count = pol ? 4u : (unsigned)FM1_MOD_CURVE_COUNT;
      unsigned k;
      for (k = 0; k < count && !same(names[k], eq + 1); ++k) {
      }
      if (k == count) return fail(err, cap, "bad %s %s", tok[t], eq + 1);
      if (pol) {
        s.flags = (uint8_t)((s.flags & ~FM1_MOD_SLOT_POL_MASK) | (k << FM1_MOD_SLOT_POL_SHIFT));
      } else {
        s.flags = (uint8_t)((s.flags & ~FM1_MOD_SLOT_CURVE_MASK) | (k << FM1_MOD_SLOT_CURVE_SHIFT));
      }
    } else {
      return fail(err, cap, "unknown slot option %s", tok[t]);
    }
  }
  fm1_mod_set_slot(m, i, &s);
  return 1;
}

int fm1_mod_script_seed(const char *line, uint32_t *seed) {
  char tok[MAX_TOK][TOK_LEN];
  double v;
  const int n = tokens(line, tok);
  if (n != 2 || !same(tok[0], "seed") || !number(tok[1], &v) || v < 0 || v > 4294967295.0) {
    return 0;
  }
  *seed = (uint32_t)v;
  return 1;
}

int fm1_mod_script_line(fm1_mod_t *m, const char *line, const fm1_engine_t *const units[3],
                        char *err, size_t errcap) {
  const fm1_engine_t *all[FM1_MOD_SINKS];
  unsigned i;
  for (i = 0; i < FM1_MOD_SINKS; ++i) all[i] = i < 3u ? units[i] : NULL;
  return fm1_mod_script_apply(m, line, all, err, errcap);
}

int fm1_mod_script_apply(fm1_mod_t *m, const char *line,
                         const fm1_engine_t *const units[FM1_MOD_SINKS], char *err, size_t errcap) {
  char tok[MAX_TOK][TOK_LEN];
  const int n = tokens(line, tok);
  unsigned a, b;
  if (err && errcap) err[0] = '\0';
  if (n == 0) return 1;
  if (same(tok[0], "seed")) {
    uint32_t s;
    return fm1_mod_script_seed(line, &s) ? 1 : fail(err, errcap, "seed wants 0-4294967295");
  }
  if (same(tok[0], "rack") && n == 2 && same(tok[1], "default")) {
    fm1_mod_default_rack(m);
    return 1;
  }
  if (same(tok[0], "reset") && n == 1) {
    fm1_mod_reset(m, FM1_MOD_RESET_PRESET);
    return 1;
  }
  if (same(tok[0], "mod")) {
    int kind = -1;
    if (n < 3 || !position(tok[1], &a)) return fail(err, errcap, "mod wants P KIND");
    if (!same(tok[2], "none") && !same(tok[2], "-")) {
      kind = fm1_mod_kind_find(tok[2]);
      if (kind < 0) return fail(err, errcap, "unknown kind %s", tok[2]);
    }
    if (fm1_mod_set_kind(m, a, kind) < 0) return fail(err, errcap, "%s does not fit", tok[2]);
    return kind < 0 ? 1 : set_params(m, a, tok, 3, n, err, errcap);
  }
  if (same(tok[0], "set")) {
    if (n < 3 || !position(tok[1], &a)) return fail(err, errcap, "set wants P NAME=VALUE...");
    return set_params(m, a, tok, 2, n, err, errcap);
  }
  if (same(tok[0], "slot")) return slot_line(m, units, tok, n, err, errcap);
  if (same(tok[0], "current")) {
    double v;
    if (n != 2 || !number(tok[1], &v) || v < 1 || v > FM1_MOD_SOUNDS || v != (double)(unsigned)v) {
      return fail(err, errcap, "current wants a sound unit 1-%u", FM1_MOD_SOUNDS);
    }
    fm1_mod_set_current(m, (unsigned)v - 1u);
    return 1;
  }
  if (same(tok[0], "move")) {
    if (n != 3 || !position(tok[1], &a) || !position(tok[2], &b)) {
      return fail(err, errcap, "move wants A B (1-8)");
    }
    fm1_mod_move(m, a, b);
    return 1;
  }
  return fail(err, errcap, "unknown line: %s", tok[0]);
}

void fm1_mod_script_source_name(const fm1_mod_t *m, unsigned src, char *buf, size_t cap) {
  const fm1_mod_source_info_t *si = fm1_mod_system_source(src);
  if (si) {
    size_t k;
    for (k = 0; si->name[k] && k + 1 < cap; ++k) buf[k] = (char)tolower((unsigned char)si->name[k]);
    if (cap) buf[k < cap ? k : cap - 1] = '\0';
  } else if (src >= FM1_MOD_SRC_MODULE && src < FM1_MOD_SRC_MODULE + 8u * FM1_MOD_POSITIONS) {
    const unsigned pos = (src - FM1_MOD_SRC_MODULE) / 8u, port = (src - FM1_MOD_SRC_MODULE) % 8u;
    const int k = fm1_mod_kind_at(m, pos);
    snprintf(buf, cap, "%s%u.%u", k >= 0 ? fm1_mod_kinds[k]->id : "mod", pos + 1u, port + 1u);
  } else {
    snprintf(buf, cap, "?%u", src);
  }
}
