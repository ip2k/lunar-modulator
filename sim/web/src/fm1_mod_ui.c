/* fm1_mod_ui.c -- modulation on the virtual FM-1's panel (fm1_mod_ui.h).
 * C99, no heap. MIT licence, like the rest of this repository.
 */
#include "fm1_mod_ui.h"

#include <stdio.h>
#include <string.h>

#include "fm1_panel.h"
#include "mod_script.h"

#define NONE FM1_MOD_UI_NONE

/* The sink groups, in list order: a destination code, the prefix a matrix
 * row puts before a parameter (none for the host), and the group's name in
 * full (fm1_mod_ui.h, "Destinations"). */
static const struct {
  uint8_t unit;
  const char *tag;
  const char *name;
} kSinks[] = {
  { FM1_MOD_SOUND, "S1", "S1" },
  { FM1_MOD_INSERT + 0, "S1I1", "S1 In1" },
  { FM1_MOD_INSERT + 1, "S1I2", "S1 In2" },
  { FM1_MOD_SOUND_UNIT + 1, "S2", "S2" },
  { FM1_MOD_INSERT + 4, "S2I1", "S2 In1" },
  { FM1_MOD_INSERT + 5, "S2I2", "S2 In2" },
  { FM1_MOD_SOUND_UNIT + 2, "S3", "S3" },
  { FM1_MOD_INSERT + 8, "S3I1", "S3 In1" },
  { FM1_MOD_INSERT + 9, "S3I2", "S3 In2" },
  { FM1_MOD_SOUND_UNIT + 3, "S4", "S4" },
  { FM1_MOD_INSERT + 12, "S4I1", "S4 In1" },
  { FM1_MOD_INSERT + 13, "S4I2", "S4 In2" },
  { FM1_MOD_FX1, "M1", "M1" },
  { FM1_MOD_FX2, "M2", "M2" },
  { FM1_MOD_HOST, "", "Host" },
};
typedef char fm1_mod_ui_sinks_listed[sizeof kSinks / sizeof kSinks[0] == FM1_MOD_SINKS &&
                                     FM1_MOD_SOUNDS == 4u && FM1_MOD_INSERTS == 2u ? 1 : -1];
#define N_SINKS (sizeof kSinks / sizeof kSinks[0])

/* mod_script.h's names for polarity and curves, and the rows' short ones. */
static const char *const kPol[4] = { "auto", "uni", "bi", "inv" };
static const char *const kPolShort[4] = { "au", "un", "bi", "in" };
static const char *const kCurve[FM1_MOD_CURVE_COUNT] = { "lin", "square", "cube", "root",
                                                         "cbrt", "exp", "log", "s" };
static const char *const kCurveShort[FM1_MOD_CURVE_COUNT] = { "lin", "sqr", "cub", "rt",
                                                              "cbr", "exp", "log", "s" };

static int lower(int c) { return c >= 'A' && c <= 'Z' ? c - 'A' + 'a' : c; }

static int same(const char *a, const char *b) {
  for (; *a && *b; ++a, ++b) {
    if (lower((unsigned char)*a) != lower((unsigned char)*b)) return 0;
  }
  return *a == *b;
}

static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

static int wrapi(int v, int n) { return n > 0 ? ((v % n) + n) % n : 0; }

static const fm1_mod_kind_t *kind_at(const fm1_mod_t *m, unsigned pos) {
  const int k = fm1_mod_kind_at(m, pos);
  return k >= 0 ? fm1_mod_kinds[k] : NULL;
}

static int lfo_kind(void) { return fm1_mod_kind_find("lfo"); }
static int env_kind(void) { return fm1_mod_kind_find("env"); }

void fm1_mod_ui_init(fm1_mod_ui_t *u) {
  unsigned pos;
  memset(u, 0, sizeof *u);
  u->sel_lfo = u->sel_env = NONE;
  u->held = NONE;
  u->field = -1;
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) u->off_kind[pos] = -1;
}

/* ---- names ----------------------------------------------------------------- */

/* At most n characters: lower-case vowels after the first character go
 * first, from the left, then the tail ("Reset" -> "Rset"). */
static void squeeze(const char *s, size_t n, char *out, size_t cap) {
  char b[32];
  size_t len;
  snprintf(b, sizeof b, "%s", s ? s : "");
  len = strlen(b);
  while (len > n) {
    size_t k = 1;
    while (k < len && !strchr("aeiou", b[k])) ++k;
    if (k >= len) {
      b[n] = '\0';
      break;
    }
    memmove(b + k, b + k + 1, len - k);
    --len;
  }
  snprintf(out, cap, "%s", b);
}

void fm1_mod_ui_label(const fm1_mod_t *m, unsigned pos, char *buf, size_t cap) {
  const fm1_mod_kind_t *kd = kind_at(m, pos);
  if (!kd) snprintf(buf, cap, "--");
  else snprintf(buf, cap, "%.3s%u", kd->abbr, pos + 1u);
}

void fm1_mod_ui_title(const fm1_mod_t *m, unsigned pos, char *buf, size_t cap) {
  const fm1_mod_kind_t *kd = kind_at(m, pos);
  if (!kd) snprintf(buf, cap, "Empty %u", pos + 1u);
  else snprintf(buf, cap, "%.12s %u", kd->name, pos + 1u);
}

/* Item i of a kind's destinations, parameters first, then gate inputs:
 * its name for a short form (the abbreviation, or the gate's name). */
static const char *item_name(const fm1_mod_kind_t *kd, unsigned i) {
  if (i < kd->n_params) return kd->params[i].abbr ? kd->params[i].abbr : kd->params[i].name;
  return kd->gate_in[i - kd->n_params].name;
}

/* Names of a list (a kind's items, or an engine's parameters' abbreviations). */
typedef struct names {
  const fm1_mod_kind_t *kd;
  const fm1_engine_t *e;
  unsigned n;
} names_t;

static const char *name_at(const names_t *l, unsigned i) {
  if (l->kd) return item_name(l->kd, i);
  return l->e->params[i].abbr ? l->e->params[i].abbr : l->e->params[i].name;
}

/* The most items a list has: a kind's parameters and gate inputs, or the
 * parameters of a sink a cable can name. */
#define SHORT_ITEMS (FM1_MOD_MAX_PARAMS + FM1_MOD_MAX_GATES)
typedef char fm1_mod_ui_short_items[SHORT_ITEMS >= FM1_MOD_UNIT_PARAMS ? 1 : -1];

/* Item i's form in w (1..7) characters, unique among the list's earlier
 * items: its name squeezed (vowels out, then the tail); or, when an earlier
 * item already has that form, the first character and the last w - 1
 * ("Accept" after "Accel", in 3: "Apt"); or the first w - 2 and the item's
 * number. The forms are built in order, each against those before it, so
 * a name costs O(item^2) comparisons (a form defined by recursion over the
 * earlier ones costs 2^item: 4,096 calls for a 13-item kind, every row of
 * every redraw). */
static void short_of(const names_t *l, unsigned item, size_t w, char out[8]) {
  char form[SHORT_ITEMS][8];
  unsigned k, c, j;
  if (item >= SHORT_ITEMS) {
    snprintf(out, 8, "?");
    return;
  }
  for (k = 0; k <= item; ++k) {
    char mine[3][8];
    const char *name = name_at(l, k);
    const size_t len = strlen(name);
    squeeze(name, w, mine[0], sizeof mine[0]);
    snprintf(mine[1], sizeof mine[1], "%c%.6s", name[0], len > w ? name + len - (w - 1) : name + (len ? 1 : 0));
    snprintf(mine[2], sizeof mine[2], "%.*s%02u", (int)(w > 2 ? w - 2 : 0), name, (k + 1u) % 100u);
    for (c = 0; c < 3; ++c) {
      int taken = 0;
      for (j = 0; j < k && !taken; ++j) taken = strcmp(form[j], mine[c]) == 0;
      if (!taken) break;
    }
    snprintf(form[k], sizeof form[k], "%s", mine[c < 3 ? c : 2]);
  }
  snprintf(out, 8, "%s", form[item]);
}

static void item_short(const fm1_mod_kind_t *kd, unsigned item, char out[8]) {
  names_t l;
  l.kd = kd;
  l.e = NULL;
  l.n = kd->n_params + kd->n_gate_in;
  short_of(&l, item, 3, out);
}

void fm1_mod_ui_source(const fm1_mod_t *m, unsigned src, int full, char *buf, size_t cap) {
  if (src < FM1_MOD_SRC_SYSTEM) {
    const fm1_mod_source_info_t *si = fm1_mod_system_source(src);
    snprintf(buf, cap, "%s", si ? si->name : "?");
  } else if (src < FM1_MOD_SRC_MODULE + 8u * FM1_MOD_POSITIONS) {
    const unsigned pos = (src - FM1_MOD_SRC_MODULE) / 8u, port = (src - FM1_MOD_SRC_MODULE) % 8u;
    const fm1_mod_kind_t *kd = kind_at(m, pos);
    char l[8];
    if (!kd || port >= kd->n_out) {
      snprintf(buf, cap, "?");
      return;
    }
    fm1_mod_ui_label(m, pos, l, sizeof l);
    if (full) snprintf(buf, cap, "%s %.5s", l, kd->out[port].name);
    else if (port) snprintf(buf, cap, "%s.%u", l, port + 1u);
    else snprintf(buf, cap, "%s", l);
  } else {
    snprintf(buf, cap, "?");
  }
}

/* The engine bound to a sink's code, or NULL. */
static const fm1_engine_t *unit_engine(const fm1_mod_ui_env_t *env, unsigned unit) {
  const int si = unit == FM1_MOD_HOST ? -1 : fm1_mod_sink_index(unit);
  return si >= 0 ? env->unit[si] : NULL;
}

/* The parameters of a destination unit, n of them (a sink's first
 * FM1_MOD_UNIT_PARAMS, as the runtime binds them). */
static const fm1_param_t *unit_params(const fm1_mod_ui_env_t *env, unsigned unit, unsigned *n) {
  *n = 0;
  if (unit == FM1_MOD_HOST) {
    *n = FM1_MOD_HOST_PARAMS;
    return fm1_mod_host_params;
  }
  if (unit_engine(env, unit)) {
    const fm1_engine_t *e = unit_engine(env, unit);
    *n = e->n_params < FM1_MOD_UNIT_PARAMS ? e->n_params : FM1_MOD_UNIT_PARAMS;
    return e->params;
  }
  if (unit >= FM1_MOD_MODULE && unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS) {
    const fm1_mod_kind_t *kd = kind_at(env->m, unit - FM1_MOD_MODULE);
    if (kd) {
      *n = kd->n_params;
      return kd->params;
    }
  }
  return NULL;
}

static int sink_group(unsigned unit) {
  unsigned g;
  for (g = 0; g < N_SINKS; ++g) {
    if (kSinks[g].unit == unit) return (int)g;
  }
  return -1;
}

int fm1_mod_ui_slot_dest(const fm1_mod_ui_env_t *env, const fm1_mod_slot_t *s, fm1_mod_dest_t *d) {
  unsigned n, i;
  const fm1_param_t *ps;
  memset(d, 0, sizeof *d);
  d->unit = s->dst_unit;
  d->dst = s->dst;
  d->index = -1;
  if (s->flags & FM1_MOD_SLOT_GATE_DST) {
    const fm1_mod_kind_t *kd =
        s->dst_unit >= FM1_MOD_MODULE && s->dst_unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS
            ? kind_at(env->m, s->dst_unit - FM1_MOD_MODULE)
            : NULL;
    d->gate = 1;
    if (kd && s->dst < kd->n_gate_in) {
      d->index = (int16_t)s->dst;
      return 1;
    }
    return 0;
  }
  if (!s->dst) return 0;
  ps = unit_params(env, s->dst_unit, &n);
  for (i = 0; ps && i < n; ++i) {
    if (ps[i].uid == s->dst) {
      d->index = (int16_t)i;
      return 1;
    }
  }
  return 0;
}

const fm1_param_t *fm1_mod_ui_dest_param(const fm1_mod_ui_env_t *env, const fm1_mod_dest_t *d) {
  unsigned n;
  const fm1_param_t *ps;
  if (d->gate || d->index < 0) return NULL;
  ps = unit_params(env, d->unit, &n);
  return ps && (unsigned)d->index < n ? &ps[d->index] : NULL;
}

void fm1_mod_ui_dest_name(const fm1_mod_ui_env_t *env, const fm1_mod_dest_t *d, int full,
                          char *buf, size_t cap) {
  char sq[16];
  if (d->unit >= FM1_MOD_MODULE && d->unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS) {
    const unsigned pos = d->unit - FM1_MOD_MODULE;
    const fm1_mod_kind_t *kd = kind_at(env->m, pos);
    const fm1_param_t *p = fm1_mod_ui_dest_param(env, d);
    const char *name;
    char l[8];
    if (!kd || d->index < 0 || (d->gate && d->index >= kd->n_gate_in) || (!d->gate && !p)) {
      snprintf(buf, cap, "?");
      return;
    }
    name = d->gate ? kd->gate_in[d->index].name : (full ? p->name : p->abbr);
    fm1_mod_ui_label(env->m, pos, l, sizeof l);
    if (full) {
      snprintf(buf, cap, "%s %.12s", l, name);
    } else {                           /* "ENV3Atk", "CHN5Trg": the label, then 3 */
      char it[8];
      item_short(kd, d->gate ? kd->n_params + (unsigned)d->index : (unsigned)d->index, it);
      snprintf(buf, cap, "%s%s", l, it);
    }
  } else {
    const int g = sink_group(d->unit);
    const fm1_param_t *p = fm1_mod_ui_dest_param(env, d);
    if (g < 0 || !p) {
      snprintf(buf, cap, "?");
      return;
    }
    if (full) {
      snprintf(buf, cap, "%s %.12s", kSinks[g].name, p->name);
    } else if (d->unit == FM1_MOD_HOST) {
      squeeze(p->abbr, FM1_MOD_UI_DST_CHARS, sq, sizeof sq);
      snprintf(buf, cap, "%s", sq);
    } else {                           /* the tag, then the parameter, unique in its engine */
      names_t l;
      l.kd = NULL;
      l.e = unit_engine(env, d->unit);
      l.n = l.e->n_params;
      short_of(&l, (unsigned)d->index, FM1_MOD_UI_DST_CHARS - strlen(kSinks[g].tag), sq);
      snprintf(buf, cap, "%s%s", kSinks[g].tag, sq);
    }
  }
}

/* ---- lists ------------------------------------------------------------------- */

int fm1_mod_ui_sources(const fm1_mod_t *m, uint8_t *out, int cap) {
  int n = 0;
  unsigned id, pos, port;
  for (id = 0; id < FM1_MOD_SRC_SYSTEM; ++id) {
    if (fm1_mod_system_source(id) && n < cap) out[n++] = (uint8_t)id;
  }
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const fm1_mod_kind_t *kd = kind_at(m, pos);
    for (port = 0; kd && port < kd->n_out && n < cap; ++port) {
      out[n++] = (uint8_t)(FM1_MOD_SRC_MODULE + 8u * pos + port);
    }
  }
  return n;
}

static int takes(const fm1_param_t *p) {
  return !(p->flags & FM1_PARAM_NOLOCK) && ((p->flags & FM1_PARAM_INPUT) || fm1_param_modulatable(p));
}

static void add_dest(fm1_mod_dest_t *out, int cap, int *n, unsigned unit, int gate, unsigned dst,
                     unsigned index) {
  if (*n >= cap) return;
  memset(&out[*n], 0, sizeof out[*n]);
  out[*n].unit = (uint8_t)unit;
  out[*n].gate = (uint8_t)gate;
  out[*n].dst = (uint16_t)dst;
  out[*n].index = (int16_t)index;
  ++*n;
}

int fm1_mod_ui_dests(const fm1_mod_ui_env_t *env, fm1_mod_dest_t *out, int cap) {
  int n = 0;
  unsigned g, i, pos;
  for (g = 0; g < N_SINKS; ++g) {
    unsigned cnt;
    const fm1_param_t *ps = unit_params(env, kSinks[g].unit, &cnt);
    for (i = 0; ps && i < cnt; ++i) {
      if (fm1_param_modulatable(&ps[i])) add_dest(out, cap, &n, kSinks[g].unit, 0, ps[i].uid, i);
    }
  }
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const fm1_mod_kind_t *kd = kind_at(env->m, pos);
    if (!kd) continue;
    for (i = 0; i < kd->n_params; ++i) {
      if (takes(&kd->params[i])) add_dest(out, cap, &n, FM1_MOD_MODULE + pos, 0, kd->params[i].uid, i);
    }
    for (i = 0; i < kd->n_gate_in; ++i) add_dest(out, cap, &n, FM1_MOD_MODULE + pos, 1, i, i);
  }
  return n;
}

/* ---- slots -------------------------------------------------------------------- */

int fm1_mod_ui_has_dst(const fm1_mod_slot_t *s) {
  return (s->flags & FM1_MOD_SLOT_GATE_DST) || s->dst != 0;
}

int fm1_mod_ui_empty(const fm1_mod_ui_t *u, const fm1_mod_t *m, unsigned i) {
  fm1_mod_slot_t s;
  if (!fm1_mod_get_slot(m, i, &s)) return 1;
  return !fm1_mod_ui_has_dst(&s) && !((u->srcset >> i) & 1u);
}

int fm1_mod_ui_pct(int16_t q14) {
  const int32_t v = (int32_t)q14 * 100;
  return v >= 0 ? (int)((v + 8192) / 16384) : -(int)((-v + 8192) / 16384);
}

static int16_t q14_of_pct(int pct) { return fm1_mod_q14((float)pct / 100.0f); }

void fm1_mod_ui_row(const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u, unsigned i, int page,
                    char out[FM1_MOD_UI_ROW_CHARS + 1]) {
  fm1_mod_slot_t s;
  char src[16], dst[16], amt[16];
  char mark = 0;
  fm1_mod_dest_t d;
  if (fm1_mod_ui_empty(u, env->m, i) || !fm1_mod_get_slot(env->m, i, &s)) {
    snprintf(out, FM1_MOD_UI_ROW_CHARS + 1, "--");
    return;
  }
  /* The character between the source and the rest says the slot's state:
   * '-' off, '!' refused (on, but an end missing or a target that takes
   * no modulation), 'v' per voice; else '~' for a cable a tick late and
   * '>' on page A, '*' (scaled by VIA) on page B. */
  if (!(s.flags & FM1_MOD_SLOT_ON)) mark = '-';
  else if ((u->plan.refused >> i) & 1u) mark = '!';
  else if (s.flags & FM1_MOD_SLOT_VOICE) mark = 'v';
  fm1_mod_ui_source(env->m, s.src, 0, src, sizeof src);
  if (page == 0) {
    if (!mark) mark = ((u->plan.delayed >> i) & 1u) ? '~' : '>';
    if (!fm1_mod_ui_has_dst(&s)) snprintf(dst, sizeof dst, "--");
    else if (fm1_mod_ui_slot_dest(env, &s, &d)) fm1_mod_ui_dest_name(env, &d, 0, dst, sizeof dst);
    else snprintf(dst, sizeof dst, "?");
    snprintf(amt, sizeof amt, "%+d", fm1_mod_ui_pct(s.amount));
    snprintf(out, FM1_MOD_UI_ROW_CHARS + 1, "%-6.6s%c%-7.7s %4.4s", src, mark, dst, amt);
  } else {
    char via[16];
    if (!mark) mark = '*';
    if (s.via == FM1_MOD_NONE) snprintf(via, sizeof via, "--");
    else fm1_mod_ui_source(env->m, s.via, 0, via, sizeof via);
    snprintf(out, FM1_MOD_UI_ROW_CHARS + 1, "%-6.6s%c%-5.5s %-3.3s %-2.2s", src, mark, via,
             kCurveShort[(s.flags & FM1_MOD_SLOT_CURVE_MASK) >> FM1_MOD_SLOT_CURVE_SHIFT],
             kPolShort[(s.flags & FM1_MOD_SLOT_POL_MASK) >> FM1_MOD_SLOT_POL_SHIFT]);
  }
}

/* A full name, or the short one when the full one would not fit `room`. */
static void dest_fit(const fm1_mod_ui_env_t *env, const fm1_mod_dest_t *d, size_t room, char *buf,
                     size_t cap) {
  fm1_mod_ui_dest_name(env, d, 1, buf, cap);
  if (strlen(buf) > room) fm1_mod_ui_dest_name(env, d, 0, buf, cap);
}

void fm1_mod_ui_hint(const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u, uint64_t now,
                     char *buf, size_t cap) {
  fm1_mod_slot_t s;
  fm1_mod_dest_t d;
  char name[32];
  const unsigned i = u->slot;
  const int empty = fm1_mod_ui_empty(u, env->m, i);
  const int has = fm1_mod_get_slot(env->m, i, &s) && fm1_mod_ui_has_dst(&s);
  const int known = has && fm1_mod_ui_slot_dest(env, &s, &d);
  if (u->field >= 0 && now < u->field_until) {
    switch (u->field) {
      case FM1_MOD_F_SRC:
        if (empty) snprintf(buf, cap, "Source: none");
        else fm1_mod_ui_source(env->m, s.src, 1, name, sizeof name), snprintf(buf, cap, "From %s", name);
        return;
      case FM1_MOD_F_DST:
        if (known) dest_fit(env, &d, 16, name, sizeof name), snprintf(buf, cap, "To %s", name);
        else snprintf(buf, cap, "To: none");
        return;
      case FM1_MOD_F_AMT: snprintf(buf, cap, "Amount %+d%%", fm1_mod_ui_pct(s.amount)); return;
      case FM1_MOD_F_OFS: snprintf(buf, cap, "Offset %+d%%", fm1_mod_ui_pct(s.offset)); return;
      case FM1_MOD_F_VIA:
        if (s.via == FM1_MOD_NONE) snprintf(buf, cap, "Via: none");
        else fm1_mod_ui_source(env->m, s.via, 1, name, sizeof name), snprintf(buf, cap, "Via %s", name);
        return;
      case FM1_MOD_F_CURVE:
        snprintf(buf, cap, "Curve %s",
                 kCurve[(s.flags & FM1_MOD_SLOT_CURVE_MASK) >> FM1_MOD_SLOT_CURVE_SHIFT]);
        return;
      case FM1_MOD_F_POL:
        snprintf(buf, cap, "Polarity %s",
                 kPol[(s.flags & FM1_MOD_SLOT_POL_MASK) >> FM1_MOD_SLOT_POL_SHIFT]);
        return;
      case FM1_MOD_F_ON:
        snprintf(buf, cap, "%s", !has ? "Off: no target" : (s.flags & FM1_MOD_SLOT_ON) ? "On" : "Off");
        return;
      default: break;
    }
  }
  if (empty) snprintf(buf, cap, "Empty: KNOB1, KNOB2");
  else if (!has) snprintf(buf, cap, "No target: KNOB2");
  else if (!known) snprintf(buf, cap, "Its target is gone");
  else dest_fit(env, &d, 16, name, sizeof name), snprintf(buf, cap, "To %s", name);
}

int fm1_mod_ui_value(const fm1_mod_ui_env_t *env, unsigned pos, unsigned index, float v, char *buf,
                     size_t cap) {
  const fm1_mod_kind_t *kd = kind_at(env->m, pos);
  float hz;
  if (!kd || !(env->rate > 0.0f) || index >= kd->n_params || strcmp(kd->id, "filter") != 0 ||
      strcmp(kd->params[index].name, "Cutoff") != 0) {
    return 0;
  }
  hz = fm1_mod_filter_hz(v, env->rate);
  if (hz < 9.995f) snprintf(buf, cap, "%.2f Hz", (double)hz);
  else if (hz < 99.95f) snprintf(buf, cap, "%.1f Hz", (double)hz);
  else snprintf(buf, cap, "%.0f Hz", (double)hz);
  return 1;
}

int fm1_mod_ui_routes(const fm1_mod_t *m, unsigned unit, uint16_t dst, int gate, float *depth) {
  unsigned i;
  int n = 0;
  float d = 0.0f;
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t s;
    fm1_mod_get_slot(m, i, &s);
    if (!(s.flags & FM1_MOD_SLOT_ON) || s.dst_unit != unit || s.dst != dst ||
        ((s.flags & FM1_MOD_SLOT_GATE_DST) != 0) != (gate != 0)) {
      continue;
    }
    ++n;
    d += (float)(s.amount < 0 ? -s.amount : s.amount) * (1.0f / 16384.0f);
  }
  if (depth) *depth = d;
  return n;
}

/* ---- script lines -------------------------------------------------------------------- */

static int token_ok(const char *t) {
  if (!t || !*t) return 0;
  for (; *t; ++t) {
    if (*t == ' ' || *t == '\t' || *t == '#' || *t == '=' || *t == ':' || *t == '.') return 0;
  }
  return 1;
}

/* mod_script.c's lookup: the first parameter whose name or abbreviation
 * matches, ignoring ASCII case. */
static int find_param(const fm1_param_t *ps, unsigned n, const char *name) {
  unsigned i;
  for (i = 0; i < n; ++i) {
    if (same(ps[i].name, name) || (ps[i].abbr && same(ps[i].abbr, name))) return (int)i;
  }
  return -1;
}

/* A word that names parameter i and nothing before it: its abbreviation,
 * else its name. 0 if neither does. */
static int param_token(const fm1_param_t *ps, unsigned n, unsigned i, char *buf, size_t cap) {
  const char *c[2] = { ps[i].abbr, ps[i].name };
  int k;
  for (k = 0; k < 2; ++k) {
    if (token_ok(c[k]) && find_param(ps, n, c[k]) == (int)i) {
      snprintf(buf, cap, "%s", c[k]);
      return 1;
    }
  }
  return 0;
}

static int src_token(unsigned src, char *buf, size_t cap) {
  if (src < FM1_MOD_SRC_SYSTEM) {
    const fm1_mod_source_info_t *si = fm1_mod_system_source(src);
    size_t k;
    if (!si) return 0;
    for (k = 0; si->name[k] && k + 1 < cap; ++k) buf[k] = (char)lower((unsigned char)si->name[k]);
    buf[k] = '\0';
    return 1;
  }
  if (src >= FM1_MOD_SRC_MODULE + 8u * FM1_MOD_POSITIONS) return 0;
  snprintf(buf, cap, "mod%u.%u", (src - FM1_MOD_SRC_MODULE) / 8u + 1u, (src - FM1_MOD_SRC_MODULE) % 8u + 1u);
  return 1;
}

static int dst_token(const fm1_mod_ui_env_t *env, const fm1_mod_slot_t *s, char *buf, size_t cap) {
  char t[32];
  unsigned n, i;
  const fm1_param_t *ps;
  if (s->dst_unit >= FM1_MOD_MODULE && s->dst_unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS) {
    const unsigned pos = s->dst_unit - FM1_MOD_MODULE;
    const fm1_mod_kind_t *kd = kind_at(env->m, pos);
    if (!kd) return 0;
    if (s->flags & FM1_MOD_SLOT_GATE_DST) {
      unsigned g;
      if (s->dst >= kd->n_gate_in) return 0;
      if (!token_ok(kd->gate_in[s->dst].name) ||
          find_param(kd->params, kd->n_params, kd->gate_in[s->dst].name) >= 0) {
        return 0;
      }
      for (g = 0; g < s->dst; ++g) {
        if (same(kd->gate_in[g].name, kd->gate_in[s->dst].name)) return 0;
      }
      snprintf(buf, cap, "mod%u:%s", pos + 1u, kd->gate_in[s->dst].name);
      return 1;
    }
    for (i = 0; i < kd->n_params; ++i) {
      if (kd->params[i].uid == s->dst && s->dst && param_token(kd->params, kd->n_params, i, t, sizeof t)) {
        snprintf(buf, cap, "mod%u:%s", pos + 1u, t);
        return 1;
      }
    }
    return 0;
  }
  if (s->flags & FM1_MOD_SLOT_GATE_DST) return 0;
  ps = unit_params(env, s->dst_unit, &n);
  for (i = 0; ps && i < n; ++i) {
    if (ps[i].uid == s->dst && s->dst) {
      /* mod_script.c looks a sink's name up among all of its engine's
       * parameters; the first FM1_MOD_UNIT_PARAMS are all a sink has. */
      const unsigned all = s->dst_unit == FM1_MOD_HOST ? n : unit_engine(env, s->dst_unit)->n_params;
      const char *unit = fm1_mod_script_unit_name(s->dst_unit);
      if (!unit || !param_token(ps, all, i, t, sizeof t)) return 0;
      snprintf(buf, cap, "%s:%s", unit, t);
      return 1;
    }
  }
  return 0;
}

int fm1_mod_ui_slot_line(const fm1_mod_ui_env_t *env, unsigned i, char *buf, size_t cap) {
  fm1_mod_slot_t s;
  char src[24], dst[48], via[24] = "";
  if (!fm1_mod_get_slot(env->m, i, &s) || !fm1_mod_ui_has_dst(&s)) return 0;
  /* What the format cannot say yet: per-voice scope (MG9), a lock uid (MG6). */
  if ((s.flags & FM1_MOD_SLOT_VOICE) || s.uid) return 0;
  if (!src_token(s.src, src, sizeof src) || !dst_token(env, &s, dst, sizeof dst)) return 0;
  if (s.via != FM1_MOD_NONE && !src_token(s.via, via, sizeof via)) return 0;
  /* amt and ofs exactly: Q1.14 x 100 / 16384 is exact in a double, and
   * mod_script.c's fm1_mod_q14(v / 100) gives the same Q1.14 back. */
  snprintf(buf, cap, "slot %u %s > %s amt=%.12g ofs=%.12g%s%s pol=%s curve=%s%s", i + 1u, src, dst,
           (double)s.amount * 100.0 / 16384.0, (double)s.offset * 100.0 / 16384.0,
           via[0] ? " via=" : "", via,
           kPol[(s.flags & FM1_MOD_SLOT_POL_MASK) >> FM1_MOD_SLOT_POL_SHIFT],
           kCurve[(s.flags & FM1_MOD_SLOT_CURVE_MASK) >> FM1_MOD_SLOT_CURVE_SHIFT],
           (s.flags & FM1_MOD_SLOT_ON) ? "" : " off");
  return 1;
}

static void emit(const fm1_mod_ui_env_t *env, const char *line) {
  if (env->emit) env->emit(env->ctx, line);
}

static int param_line(const fm1_mod_ui_env_t *env, unsigned pos, unsigned index, char *buf,
                      size_t cap) {
  const fm1_mod_kind_t *kd = kind_at(env->m, pos);
  char t[32];
  if (!kd || index >= kd->n_params || !param_token(kd->params, kd->n_params, index, t, sizeof t)) {
    return 0;
  }
  snprintf(buf, cap, "set %u %s=%.9g", pos + 1u, t, (double)fm1_mod_param_base(env->m, pos, index));
  return 1;
}

static void kind_line(const fm1_mod_ui_env_t *env, unsigned pos, char *buf, size_t cap) {
  const fm1_mod_kind_t *kd = kind_at(env->m, pos);
  snprintf(buf, cap, "mod %u %s", pos + 1u, kd ? kd->id : "none");
}

static uint32_t float_bits(float x) {
  uint32_t u;
  memcpy(&u, &x, sizeof u);
  return u;
}

int fm1_mod_ui_dump(const fm1_mod_ui_env_t *env, uint32_t seed) {
  char line[FM1_MOD_UI_LINE];
  unsigned pos, i;
  int ok = 1;
  snprintf(line, sizeof line, "seed %u", (unsigned)seed);
  emit(env, line);
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const fm1_mod_kind_t *kd = kind_at(env->m, pos);
    kind_line(env, pos, line, sizeof line);
    emit(env, line);
    for (i = 0; kd && i < kd->n_params; ++i) {
      if (float_bits(fm1_mod_param_base(env->m, pos, i)) == float_bits(kd->params[i].def)) continue;
      if (param_line(env, pos, i, line, sizeof line)) emit(env, line);
      else ok = 0;
    }
  }
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t s;
    fm1_mod_get_slot(env->m, i, &s);
    if (fm1_mod_ui_slot_line(env, i, line, sizeof line)) emit(env, line);
    else if (fm1_mod_ui_has_dst(&s)) ok = 0;
  }
  return ok;
}

/* ---- edits ---------------------------------------------------------------------------- */

/* A source that exists: a system source, or an output of a module in the
 * rack. */
static int source_exists(const fm1_mod_t *m, unsigned src) {
  if (src < FM1_MOD_SRC_SYSTEM) return fm1_mod_system_source(src) != NULL;
  if (src >= FM1_MOD_SRC_MODULE + 8u * FM1_MOD_POSITIONS) return 0;
  {
    const fm1_mod_kind_t *kd = kind_at(m, (src - FM1_MOD_SRC_MODULE) / 8u);
    return kd && (src - FM1_MOD_SRC_MODULE) % 8u < kd->n_out;
  }
}

/* Both ends of a cable exist (and its VIA, if it has one). */
static int cable_exists(const fm1_mod_ui_env_t *env, const fm1_mod_slot_t *s) {
  fm1_mod_dest_t d;
  return fm1_mod_ui_has_dst(s) && fm1_mod_ui_slot_dest(env, s, &d) && source_exists(env->m, s->src) &&
         (s->via == FM1_MOD_NONE || source_exists(env->m, s->via));
}

static int touches(const fm1_mod_slot_t *s, unsigned pos) {
  const unsigned lo = FM1_MOD_SRC_MODULE + 8u * pos, hi = lo + 8u;
  return (s->src >= lo && s->src < hi) || (s->via != FM1_MOD_NONE && s->via >= lo && s->via < hi) ||
         s->dst_unit == FM1_MOD_MODULE + pos;
}

int fm1_mod_ui_set_slot(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, unsigned i,
                        const fm1_mod_slot_t *s) {
  char line[FM1_MOD_UI_LINE];
  fm1_mod_slot_t old;
  unsigned pos;
  if (!fm1_mod_get_slot(env->m, i, &old) || !fm1_mod_set_slot(env->m, i, s)) return 0;
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) u->off_slots[pos] &= ~(1u << i);
  if (fm1_mod_ui_slot_line(env, i, line, sizeof line)) {
    emit(env, line);
  } else if (fm1_mod_ui_has_dst(s) && (s->flags & FM1_MOD_SLOT_ON)) {
    u->unloggable = 1;                 /* a cable no line can say */
  } else if (!fm1_mod_ui_has_dst(s) && fm1_mod_ui_has_dst(&old)) {
    snprintf(line, sizeof line, "slot %u clear", i + 1u);
    emit(env, line);
  }
  /* A slot with no destination, or one that is off with an end gone, has
   * no line: it runs as nothing, as the replay's older record does, and is
   * written whole when it can be again. */
  return 1;
}

/* After the rack changed under the selection: the selected modules are
 * whatever their positions hold now (fm1_mod_ui_selected resolves them). */
static void note_shown(fm1_mod_ui_t *u, const fm1_mod_t *m) {
  const int k = fm1_mod_kind_at(m, u->pos);
  if (k >= 0 && k == lfo_kind()) u->sel_lfo = u->pos;
  if (k >= 0 && k == env_kind()) u->sel_env = u->pos;
}

int fm1_mod_ui_set_kind(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, unsigned pos, int kind) {
  char line[FM1_MOD_UI_LINE];
  uint32_t before = 0, after = 0, off, back = 0;
  unsigned i;
  int r;
  const int old = fm1_mod_kind_at(env->m, pos);
  if (pos >= FM1_MOD_POSITIONS || old == kind) return 0;
  /* The cables a change back to `kind` brings back, read before this
   * change remembers its own (a module that got cables of its own before
   * the change back must not make the first kind's cables forgotten). */
  if (kind >= 0 && kind == u->off_kind[pos]) back = u->off_slots[pos];
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t s;
    fm1_mod_get_slot(env->m, i, &s);
    if (s.flags & FM1_MOD_SLOT_ON) before |= 1u << i;
  }
  r = fm1_mod_set_kind(env->m, pos, kind);
  if (r < 0) {
    if (fm1_mod_kind_at(env->m, pos) != old) u->unloggable = 1;   /* create failed: emptied */
    return r;
  }
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t s;
    fm1_mod_get_slot(env->m, i, &s);
    if (s.flags & FM1_MOD_SLOT_ON) after |= 1u << i;
  }
  off = before & ~after;
  if (off && old >= 0) {               /* this change's cables, for a change back */
    u->off_kind[pos] = (int8_t)old;
    u->off_slots[pos] = off;
  } else if (back) {                   /* restored below: nothing left to remember */
    u->off_kind[pos] = -1;
    u->off_slots[pos] = 0;
  }
  kind_line(env, pos, line, sizeof line);
  emit(env, line);
  if (back) {
    for (i = 0; i < FM1_MOD_SLOTS; ++i) {
      fm1_mod_slot_t s;
      if (!((back >> i) & 1u)) continue;
      fm1_mod_get_slot(env->m, i, &s);
      /* Only a cable whose other end is still there comes back. */
      if ((s.flags & FM1_MOD_SLOT_ON) || !touches(&s, pos) || !cable_exists(env, &s)) continue;
      s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_ON);
      fm1_mod_ui_set_slot(env, u, i, &s);
    }
  }
  if (pos == u->pos) {
    u->page = 0;
    note_shown(u, env->m);
  }
  return r;
}

int fm1_mod_ui_set_param(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, unsigned pos,
                         unsigned index, float value) {
  char line[FM1_MOD_UI_LINE];
  if (!fm1_mod_set_param(env->m, pos, index, value)) return 0;
  if (param_line(env, pos, index, line, sizeof line)) emit(env, line);
  else u->unloggable = 1;
  return 1;
}

/* Where position p goes when the module at `from` moves to `to`
 * (fm1_mod_move's shift). */
static unsigned moved(unsigned p, unsigned from, unsigned to) {
  if (p == from) return to;
  if (from < to && p > from && p <= to) return p - 1u;
  if (from > to && p >= to && p < from) return p + 1u;
  return p;
}

int fm1_mod_ui_move(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, unsigned from, unsigned to) {
  char line[FM1_MOD_UI_LINE];
  int8_t ok[FM1_MOD_POSITIONS];
  uint32_t os[FM1_MOD_POSITIONS];
  unsigned p;
  if (from >= FM1_MOD_POSITIONS || to >= FM1_MOD_POSITIONS || from == to) return 0;
  if (!fm1_mod_move(env->m, from, to)) return 0;
  snprintf(line, sizeof line, "move %u %u", from + 1u, to + 1u);
  emit(env, line);
  memcpy(ok, u->off_kind, sizeof ok);
  memcpy(os, u->off_slots, sizeof os);
  for (p = 0; p < FM1_MOD_POSITIONS; ++p) {
    u->off_kind[moved(p, from, to)] = ok[p];
    u->off_slots[moved(p, from, to)] = os[p];
  }
  u->pos = (uint8_t)moved(u->pos, from, to);
  if (u->sel_lfo != NONE) u->sel_lfo = (uint8_t)moved(u->sel_lfo, from, to);
  if (u->sel_env != NONE) u->sel_env = (uint8_t)moved(u->sel_env, from, to);
  return 1;
}

static int nth_of(const fm1_mod_t *m, int kind, int nth) {
  unsigned p;
  for (p = 0; kind >= 0 && p < FM1_MOD_POSITIONS; ++p) {
    if (fm1_mod_kind_at(m, p) == kind && nth-- == 0) return (int)p;
  }
  return -1;
}

void fm1_mod_ui_default(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u) {
  int k;
  fm1_mod_default_rack(env->m);
  for (k = 0; k < 2; ++k) {
    const int e = nth_of(env->m, env_kind(), k);
    fm1_mod_slot_t s;
    if (e < 0) continue;
    memset(&s, 0, sizeof s);
    s.src = FM1_MOD_SRC_RTRG;            /* every note restarts it (owner, 2026-10-05) */
    s.via = FM1_MOD_NONE;
    s.dst_unit = (uint8_t)(FM1_MOD_MODULE + (unsigned)e);
    s.flags = FM1_MOD_SLOT_ON | FM1_MOD_SLOT_GATE_DST;
    s.dst = 0;                                  /* the Envelope's one gate input, GATE */
    s.amount = FM1_MOD_Q14;
    fm1_mod_set_slot(env->m, (unsigned)k, &s);
  }
  k = nth_of(env->m, lfo_kind(), 0);
  u->sel_lfo = k >= 0 ? (uint8_t)k : NONE;
  k = nth_of(env->m, env_kind(), 0);
  u->sel_env = k >= 0 ? (uint8_t)k : NONE;
  u->pos = u->sel_lfo != NONE ? u->sel_lfo : 0;
  u->page = 0;
}

/* ---- the pages --------------------------------------------------------------------- */

int fm1_mod_ui_rack_pages(const fm1_mod_t *m, unsigned pos) {
  const fm1_mod_kind_t *kd = kind_at(m, pos);
  int pages = 1;
  unsigned i;
  for (i = 0; kd && i < kd->n_params; ++i) {
    if (!(kd->params[i].flags & FM1_PARAM_INPUT) && kd->params[i].page + 1 > pages) {
      pages = kd->params[i].page + 1;
    }
  }
  return pages;
}

int fm1_mod_ui_rack_params(const fm1_mod_t *m, unsigned pos, unsigned page, int idx[4]) {
  const fm1_mod_kind_t *kd = kind_at(m, pos);
  int n = 0;
  unsigned i;
  for (i = 0; kd && i < kd->n_params && n < 4; ++i) {
    if (!(kd->params[i].flags & FM1_PARAM_INPUT) && kd->params[i].page == page) idx[n++] = (int)i;
  }
  return n;
}

int fm1_mod_ui_selected(const fm1_mod_ui_t *u, const fm1_mod_t *m, int kind) {
  const uint8_t s = kind < 0 ? NONE : kind == lfo_kind() ? u->sel_lfo : kind == env_kind() ? u->sel_env : NONE;
  if (s < FM1_MOD_POSITIONS && fm1_mod_kind_at(m, s) == kind) return s;
  return nth_of(m, kind, 0);
}

int fm1_mod_ui_open_rack(fm1_mod_ui_t *u, const fm1_mod_t *m, int kind, int in_rack) {
  int target = -1;
  unsigned d;
  if (in_rack && kind >= 0 && fm1_mod_kind_at(m, u->pos) == kind) {
    for (d = 1; d <= FM1_MOD_POSITIONS && target < 0; ++d) {
      const unsigned p = (u->pos + d) % FM1_MOD_POSITIONS;
      if (fm1_mod_kind_at(m, p) == kind) target = (int)p;
    }
  } else {
    target = fm1_mod_ui_selected(u, m, kind);
  }
  u->page = 0;
  u->grab = 0;
  if (target < 0) {
    for (d = 0; d < FM1_MOD_POSITIONS && target < 0; ++d) {
      if (fm1_mod_kind_at(m, d) < 0) target = (int)d;
    }
    if (target >= 0) u->pos = (uint8_t)target;
    return 0;
  }
  u->pos = (uint8_t)target;
  note_shown(u, m);
  return 1;
}

void fm1_mod_ui_rack_select(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int delta) {
  const int dir = delta > 0 ? 1 : -1;
  int k;
  if (u->grab) {                       /* the grabbed module moves one place a detent */
    for (k = 0; k < (delta > 0 ? delta : -delta); ++k) {
      const int to = (int)u->pos + dir;
      if (to < 0 || to >= (int)FM1_MOD_POSITIONS) break;
      fm1_mod_ui_move(env, u, u->pos, (unsigned)to);
    }
    return;
  }
  for (k = 0; k < (delta > 0 ? delta : -delta); ++k) {
    const int page = (int)u->page + dir;
    if (page >= 0 && page < fm1_mod_ui_rack_pages(env->m, u->pos)) {
      u->page = (uint8_t)page;
    } else if ((int)u->pos + dir >= 0 && (int)u->pos + dir < (int)FM1_MOD_POSITIONS) {
      u->pos = (uint8_t)((int)u->pos + dir);
      u->page = (uint8_t)(dir > 0 ? 0 : fm1_mod_ui_rack_pages(env->m, u->pos) - 1);
    }
  }
  note_shown(u, env->m);
}

/* A detent: a hundredth of the range, whole units for a wide integer range
 * (the app's step_of), one entry for a list. */
static float step_of(const fm1_param_t *p) {
  float range;
  if (p->type == FM1_PARAM_ENUM) return 1.0f;
  range = p->max - p->min;
  if (range >= 10.0f && p->min == (float)(int)p->min && p->max == (float)(int)p->max) {
    const float s = (float)(int)(range / 100.0f + 0.5f);
    return s < 1.0f ? 1.0f : s;
  }
  return range / 100.0f;
}

void fm1_mod_ui_rack_knob(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int knob, int delta) {
  const fm1_mod_kind_t *kd = kind_at(env->m, u->pos);
  int idx[4];
  const int n = fm1_mod_ui_rack_params(env->m, u->pos, u->page, idx);
  const fm1_param_t *p;
  float v, base;
  if (!kd || knob < 0 || knob >= n) return;
  p = &kd->params[idx[knob]];
  base = fm1_mod_param_base(env->m, u->pos, (unsigned)idx[knob]);
  v = base + (float)delta * step_of(p);
  if (p->type == FM1_PARAM_ENUM) v = (float)(int)(v + (v >= 0.0f ? 0.5f : -0.5f));
  v = fm1_param_clamp(p, v);
  if (float_bits(v) != float_bits(base)) fm1_mod_ui_set_param(env, u, u->pos, (unsigned)idx[knob], v);
}

static const char *kind_entry(int e) {
  return e <= 0 || (size_t)e > fm1_mod_kind_count ? "Empty" : fm1_mod_kinds[e - 1]->name;
}

void fm1_mod_ui_rack_algorithm(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int delta,
                               fm1_mod_ui_say_t *say) {
  const int count = (int)fm1_mod_kind_count + 1;   /* Empty, then every kind */
  if (u->picker != FM1_MOD_PICK_KIND || u->pick_at != u->pos) {
    fm1_mod_ui_commit(env, u);
    u->picker = FM1_MOD_PICK_KIND;
    u->pick_at = u->pos;
    u->pick = (int16_t)(fm1_mod_kind_at(env->m, u->pos) + 1);
  }
  u->pick = (int16_t)wrapi(u->pick + delta, count);
  say->n = 3;
  say->mark = 1;
  snprintf(say->line[0], sizeof say->line[0], "%s", kind_entry(wrapi(u->pick - 1, count)));
  snprintf(say->line[1], sizeof say->line[1], "%s", kind_entry(u->pick));
  snprintf(say->line[2], sizeof say->line[2], "%s", kind_entry(wrapi(u->pick + 1, count)));
}

void fm1_mod_ui_matrix_select(fm1_mod_ui_t *u, int delta) {
  u->slot = (uint8_t)clampi((int)u->slot + delta, 0, FM1_MOD_SLOTS - 1);
  if (u->slot < u->top) u->top = u->slot;
  if (u->slot >= u->top + FM1_MOD_UI_ROWS) u->top = (uint8_t)(u->slot - FM1_MOD_UI_ROWS + 1);
  u->field = -1;
}

static int index_of_source(const uint8_t *list, int n, unsigned src) {
  int k;
  for (k = 0; k < n; ++k) {
    if (list[k] == src) return k;
  }
  return -1;
}

static int dest_index(const fm1_mod_dest_t *list, int n, const fm1_mod_slot_t *s) {
  const uint8_t gate = (s->flags & FM1_MOD_SLOT_GATE_DST) != 0;
  int k;
  if (!fm1_mod_ui_has_dst(s)) return -1;
  for (k = 0; k < n; ++k) {
    if (list[k].unit == s->dst_unit && list[k].dst == s->dst && list[k].gate == gate) return k;
  }
  return -1;
}

static void say_dest(const fm1_mod_ui_env_t *env, const fm1_mod_dest_t *list, int n, int k,
                     fm1_mod_ui_say_t *say) {
  int r;
  say->n = 3;
  say->mark = 1;
  for (r = 0; r < 3; ++r) {
    const int at = k - 1 + r;
    say->line[r][0] = '\0';
    if (at >= 0 && at < n) {
      char name[32];
      fm1_mod_ui_dest_name(env, &list[at], 1, name, sizeof name);
      snprintf(say->line[r], sizeof say->line[r], "%.18s", name);
    }
  }
}

static int group_of(const fm1_mod_dest_t *d) { return d->unit; }

/* Where the current sound's parameters start in the list (0 if it has
 * none: an empty sound). */
static int current_sound_at(const fm1_mod_ui_env_t *env, const fm1_mod_dest_t *list, int n) {
  const unsigned unit = fm1_mod_sound_unit(env->sound < FM1_MOD_SOUNDS ? env->sound : 0u);
  int k;
  for (k = 0; k < n; ++k) {
    if (list[k].unit == unit && !list[k].gate) return k;
  }
  return 0;
}

/* The source a new cable starts from: the selected LFO's output, else VEL. */
static uint8_t default_source(const fm1_mod_ui_t *u, const fm1_mod_t *m) {
  const int p = fm1_mod_ui_selected(u, m, lfo_kind());
  return p >= 0 ? (uint8_t)(FM1_MOD_SRC_MODULE + 8u * (unsigned)p) : (uint8_t)FM1_MOD_SRC_VEL;
}

void fm1_mod_ui_matrix_knob(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int knob, int delta,
                            uint64_t hint_until, fm1_mod_ui_say_t *say) {
  const unsigned i = u->slot;
  const uint32_t bit = 1u << i;
  fm1_mod_slot_t s;
  if (knob < 0 || knob > 3 || !fm1_mod_get_slot(env->m, i, &s)) return;
  u->field = (int8_t)(knob + 4 * u->mpage);
  u->field_until = hint_until;
  if (u->mpage == 0 && knob == 1) {                /* KNOB2: the destination picker */
    fm1_mod_dest_t list[FM1_MOD_UI_MAX_DESTS];
    const int n = fm1_mod_ui_dests(env, list, FM1_MOD_UI_MAX_DESTS);
    if (!n) return;
    if (u->picker != FM1_MOD_PICK_DEST || u->pick_at != i) {
      fm1_mod_ui_commit(env, u);
      u->picker = FM1_MOD_PICK_DEST;
      u->pick_at = (uint8_t)i;
      u->pick = (int16_t)dest_index(list, n, &s);
      if (u->pick < 0) {                           /* a new cable: at the current sound */
        const int at = current_sound_at(env, list, n);
        u->pick = (int16_t)(delta > 0 ? at - 1 : at);
      }
    }
    u->pick = (int16_t)clampi(u->pick + delta, 0, n - 1);
    say_dest(env, list, n, u->pick, say);
    return;
  }
  if (fm1_mod_ui_empty(u, env->m, i)) {            /* a fresh slot: nothing in it */
    memset(&s, 0, sizeof s);
    s.via = FM1_MOD_NONE;
    s.src = default_source(u, env->m);             /* as the destination picker's commit */
  }
  if (u->mpage == 0) {
    if (knob == 0) {                               /* KNOB1: the source, "--" first */
      uint8_t list[FM1_MOD_UI_MAX_SOURCES];
      const int n = fm1_mod_ui_sources(env->m, list, FM1_MOD_UI_MAX_SOURCES);
      const int cur = fm1_mod_ui_empty(u, env->m, i) ? 0 : 1 + index_of_source(list, n, s.src);
      const int to = clampi(cur + delta, 0, n);
      if (to == cur) return;
      if (to == 0) {
        memset(&s, 0, sizeof s);
        s.via = FM1_MOD_NONE;
        u->srcset &= ~bit;
      } else {
        s.src = list[to - 1];
        u->srcset |= bit;
      }
      fm1_mod_ui_set_slot(env, u, i, &s);
      return;
    }
    {
      int16_t *q = knob == 2 ? &s.amount : &s.offset;
      const int pct = clampi(fm1_mod_ui_pct(*q) + delta, -100, 100);
      if (pct == fm1_mod_ui_pct(*q)) return;
      *q = q14_of_pct(pct);
    }
  } else if (knob == 0) {                          /* VIA, "--" first */
    uint8_t list[FM1_MOD_UI_MAX_SOURCES];
    const int n = fm1_mod_ui_sources(env->m, list, FM1_MOD_UI_MAX_SOURCES);
    const int cur = s.via == FM1_MOD_NONE ? 0 : 1 + index_of_source(list, n, s.via);
    const int to = clampi(cur + delta, 0, n);
    if (to == cur) return;
    s.via = to == 0 ? (uint8_t)FM1_MOD_NONE : list[to - 1];
  } else if (knob == 1 || knob == 2) {             /* curve, polarity */
    const unsigned mask = knob == 1 ? FM1_MOD_SLOT_CURVE_MASK : FM1_MOD_SLOT_POL_MASK;
    const unsigned shift = knob == 1 ? FM1_MOD_SLOT_CURVE_SHIFT : FM1_MOD_SLOT_POL_SHIFT;
    const int top = knob == 1 ? FM1_MOD_CURVE_COUNT - 1 : 3;
    const int cur = (int)((s.flags & mask) >> shift);
    const int to = clampi(cur + delta, 0, top);
    if (to == cur) return;
    s.flags = (uint8_t)((s.flags & ~mask) | ((unsigned)to << shift));
  } else {                                         /* on, off */
    const int on = delta > 0;
    if (on && !fm1_mod_ui_has_dst(&s)) return;     /* the hint line says why */
    if (on == ((s.flags & FM1_MOD_SLOT_ON) != 0)) return;
    s.flags = (uint8_t)(on ? s.flags | FM1_MOD_SLOT_ON : s.flags & ~FM1_MOD_SLOT_ON);
  }
  if (!fm1_mod_ui_has_dst(&s)) u->srcset |= bit;   /* shown from now on */
  fm1_mod_ui_set_slot(env, u, i, &s);
}

void fm1_mod_ui_matrix_algorithm(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int delta,
                                 fm1_mod_ui_say_t *say) {
  if (u->picker == FM1_MOD_PICK_DEST) {            /* jump between groups */
    fm1_mod_dest_t list[FM1_MOD_UI_MAX_DESTS];
    const int n = fm1_mod_ui_dests(env, list, FM1_MOD_UI_MAX_DESTS);
    int k, at = clampi(u->pick, 0, n - 1);
    if (!n) return;
    for (k = 0; k < (delta > 0 ? delta : -delta); ++k) {
      const int g = group_of(&list[at]);
      if (delta > 0) {
        int j = at;
        while (j < n && group_of(&list[j]) == g) ++j;
        if (j < n) at = j;
      } else {
        int j = at;
        while (j > 0 && group_of(&list[j]) == g) --j;     /* the group before */
        if (group_of(&list[j]) != g) {
          const int pg = group_of(&list[j]);
          while (j > 0 && group_of(&list[j - 1]) == pg) --j;
          at = j;
        } else {
          at = 0;
        }
      }
    }
    u->pick = (int16_t)at;
    say_dest(env, list, n, at, say);
    return;
  }
  if (delta & 1) u->mpage ^= 1u;
  u->field = -1;
}

void fm1_mod_ui_chain_select(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, int delta) {
  const int dir = delta > 0 ? 1 : -1;
  int k, at = u->slot;
  for (k = 0; k < (delta > 0 ? delta : -delta); ++k) {
    int j = at + dir;
    while (j >= 0 && j < (int)FM1_MOD_SLOTS) {
      fm1_mod_slot_t s;
      fm1_mod_get_slot(env->m, (unsigned)j, &s);
      if (fm1_mod_ui_has_dst(&s)) break;
      j += dir;
    }
    if (j < 0 || j >= (int)FM1_MOD_SLOTS) break;
    at = j;
  }
  fm1_mod_ui_matrix_select(u, at - (int)u->slot);
}

int fm1_mod_ui_commit(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u) {
  const uint8_t p = u->picker;
  u->picker = FM1_MOD_PICK_NONE;
  if (p == FM1_MOD_PICK_KIND) {
    const int kind = u->pick - 1;
    return fm1_mod_ui_set_kind(env, u, u->pick_at, kind) >= 0 &&
           fm1_mod_kind_at(env->m, u->pick_at) == kind;
  }
  if (p == FM1_MOD_PICK_DEST) {
    fm1_mod_dest_t list[FM1_MOD_UI_MAX_DESTS];
    const int n = fm1_mod_ui_dests(env, list, FM1_MOD_UI_MAX_DESTS);
    const unsigned i = u->pick_at;
    fm1_mod_slot_t s;
    if (u->pick < 0 || u->pick >= n || !fm1_mod_get_slot(env->m, i, &s)) return 0;
    if (dest_index(list, n, &s) == u->pick) return 0;
    if (!fm1_mod_ui_has_dst(&s)) {                 /* the cable is new: on, at its amount */
      if (fm1_mod_ui_empty(u, env->m, i)) {
        memset(&s, 0, sizeof s);
        s.via = FM1_MOD_NONE;
        s.src = default_source(u, env->m);
      }
      s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_ON);
    }
    s.dst_unit = list[u->pick].unit;
    s.dst = list[u->pick].dst;
    s.flags = (uint8_t)(list[u->pick].gate ? s.flags | FM1_MOD_SLOT_GATE_DST
                                           : s.flags & ~FM1_MOD_SLOT_GATE_DST);
    u->srcset &= ~(1u << i);
    return fm1_mod_ui_set_slot(env, u, i, &s);
  }
  return 0;
}

int fm1_mod_ui_route(const fm1_mod_ui_env_t *env, fm1_mod_ui_t *u, unsigned src_pos,
                     const fm1_mod_dest_t *d, int delta, fm1_mod_ui_say_t *say) {
  const fm1_param_t *p = fm1_mod_ui_dest_param(env, d);
  const uint8_t src = (uint8_t)(FM1_MOD_SRC_MODULE + 8u * src_pos);
  char a[16], b[16];
  fm1_mod_slot_t s;
  int i, found = -1, pct;
  say->n = 0;
  say->mark = -1;
  if (!p || !takes(p)) {
    say->n = 2;
    snprintf(say->line[0], sizeof say->line[0], "%.18s", p ? p->name : "Nothing here");
    snprintf(say->line[1], sizeof say->line[1], "takes no cable");
    return 0;
  }
  for (i = 0; i < (int)FM1_MOD_SLOTS && found < 0; ++i) {      /* this cable, on */
    fm1_mod_get_slot(env->m, (unsigned)i, &s);
    if ((s.flags & FM1_MOD_SLOT_ON) && s.src == src && s.dst_unit == d->unit && s.dst == d->dst &&
        !(s.flags & FM1_MOD_SLOT_GATE_DST)) {
      found = i;
    }
  }
  for (i = 0; i < (int)FM1_MOD_SLOTS && found < 0; ++i) {      /* ...or off */
    fm1_mod_get_slot(env->m, (unsigned)i, &s);
    if (s.src == src && s.dst_unit == d->unit && s.dst == d->dst && fm1_mod_ui_has_dst(&s) &&
        !(s.flags & FM1_MOD_SLOT_GATE_DST)) {
      found = i;
    }
  }
  for (i = 0; i < (int)FM1_MOD_SLOTS && found < 0; ++i) {      /* ...or a new one */
    if (fm1_mod_ui_empty(u, env->m, (unsigned)i)) found = i;
  }
  fm1_mod_ui_source(env->m, src, 0, a, sizeof a);
  fm1_mod_ui_dest_name(env, d, 0, b, sizeof b);
  if (found < 0) {
    say->n = 2;
    snprintf(say->line[0], sizeof say->line[0], "%.6s > %.7s", a, b);
    snprintf(say->line[1], sizeof say->line[1], "Matrix full");
    return 0;
  }
  fm1_mod_get_slot(env->m, (unsigned)found, &s);
  if (!fm1_mod_ui_has_dst(&s)) {
    memset(&s, 0, sizeof s);
    s.via = FM1_MOD_NONE;
    s.src = src;
    s.dst_unit = d->unit;
    s.dst = d->dst;
  }
  pct = clampi(fm1_mod_ui_pct(s.amount) + delta, -100, 100);
  s.amount = q14_of_pct(pct);
  s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_ON);
  u->srcset &= ~(1u << found);
  fm1_mod_ui_set_slot(env, u, (unsigned)found, &s);
  fm1_mod_ui_matrix_select(u, found - (int)u->slot);   /* MATRIX opens on it */
  say->n = 2;
  snprintf(say->line[0], sizeof say->line[0], "%.6s > %.7s", a, b);
  snprintf(say->line[1], sizeof say->line[1], "%+d%%", pct);
  return 1;
}

/* ---- CHAIN --------------------------------------------------------------------------- */

typedef struct chain {
  const fm1_mod_ui_env_t *env;
  const fm1_mod_ui_t *u;
  fm1_mod_slot_t s[FM1_MOD_SLOTS];
  uint32_t ok;                         /* cables that are on and whose ends exist */
  uint8_t memo[2][FM1_MOD_POSITIONS], state[2][FM1_MOD_POSITIONS];
} chain_t;

static int src_module(const fm1_mod_slot_t *s) {
  return s->src >= FM1_MOD_SRC_MODULE && s->src < FM1_MOD_SRC_MODULE + 8u * FM1_MOD_POSITIONS
             ? (int)((s->src - FM1_MOD_SRC_MODULE) / 8u)
             : -1;
}

static int dst_module(const fm1_mod_slot_t *s) {
  return s->dst_unit >= FM1_MOD_MODULE && s->dst_unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS
             ? (int)(s->dst_unit - FM1_MOD_MODULE)
             : -1;
}

/* The longest run of module-to-module cables into (dir 0) or out of (dir
 * 1) a module; a loop is cut where it closes. */
static int depth(chain_t *c, int dir, int pos) {
  unsigned j;
  int best = 0;
  if (c->state[dir][pos] == 2) return c->memo[dir][pos];
  if (c->state[dir][pos] == 1) return 0;
  c->state[dir][pos] = 1;
  for (j = 0; j < FM1_MOD_SLOTS; ++j) {
    const int from = src_module(&c->s[j]), to = dst_module(&c->s[j]);
    const int next = dir == 0 ? from : to;
    if (!((c->ok >> j) & 1u) || (dir == 0 ? to : from) != pos || next < 0) continue;
    {
      const int d = 1 + depth(c, dir, next);
      if (d > best) best = d;
    }
  }
  c->state[dir][pos] = 2;
  c->memo[dir][pos] = (uint8_t)best;
  return best;
}

static void cable_text(chain_t *c, unsigned j, char *out) {
  const fm1_mod_slot_t *s = &c->s[j];
  fm1_mod_dest_t d;
  char amt[16], dst[32] = "?";
  snprintf(amt, sizeof amt, "%+d", fm1_mod_ui_pct(s->amount));
  if (fm1_mod_ui_slot_dest(c->env, s, &d)) {
    if (d.unit >= FM1_MOD_MODULE && d.unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS) {
      const fm1_mod_kind_t *kd = kind_at(c->env->m, d.unit - FM1_MOD_MODULE);
      const fm1_param_t *p = fm1_mod_ui_dest_param(c->env, &d);
      char l[8];
      fm1_mod_ui_label(c->env->m, d.unit - FM1_MOD_MODULE, l, sizeof l);
      snprintf(dst, sizeof dst, "%s %.6s", l, d.gate ? kd->gate_in[d.index].name : p->abbr);
    } else {                           /* "S1 Timbre", "S2 In1 Mix", "M1 Mix", "Host Pitch" */
      const fm1_param_t *p = fm1_mod_ui_dest_param(c->env, &d);
      snprintf(dst, sizeof dst, "%s %.6s", kSinks[sink_group(d.unit)].name, p->abbr);
    }
  }
  snprintf(out, FM1_MOD_UI_ROW_CHARS + 1, "%4.4s >%.12s%s", amt, dst,
           ((c->u->plan.delayed >> j) & 1u) ? "~" : "");
}

static void node_text(chain_t *c, unsigned src, const uint32_t on_path, char *out) {
  char name[32];
  fm1_mod_ui_source(c->env->m, src, 1, name, sizeof name);
  if (src >= FM1_MOD_SRC_MODULE) {
    const int pos = (int)((src - FM1_MOD_SRC_MODULE) / 8u);
    unsigned j;
    int more = 0;
    for (j = 0; j < FM1_MOD_SLOTS; ++j) {
      if (((c->ok >> j) & 1u) && !((on_path >> j) & 1u) && src_module(&c->s[j]) == pos) ++more;
    }
    if (more) {                        /* at most 31; the bound lets GCC see it fits */
      snprintf(out, FM1_MOD_UI_ROW_CHARS + 1, "%-13.13s +%d", name, more > 99 ? 99 : more);
      return;
    }
  }
  snprintf(out, FM1_MOD_UI_ROW_CHARS + 1, "%.19s", name);
}

int fm1_mod_ui_chain(const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u, unsigned i,
                     char lines[FM1_MOD_UI_CHAIN_LINES][FM1_MOD_UI_ROW_CHARS + 1], int *hl) {
  chain_t c;
  uint8_t path[FM1_MOD_POSITIONS + 2];
  int n = 0, sel = 0, k, cur, out = 0;
  uint32_t visited = 0, on_path = 0;
  unsigned j;
  *hl = -1;
  memset(&c, 0, sizeof c);
  c.env = env;
  c.u = u;
  for (j = 0; j < FM1_MOD_SLOTS; ++j) {
    fm1_mod_dest_t d;
    fm1_mod_get_slot(env->m, j, &c.s[j]);
    /* A refused cable (MATRIX's `!`) carries nothing, so no path runs on
     * through it; the selected one is still shown. */
    if ((c.s[j].flags & FM1_MOD_SLOT_ON) && !((u->plan.refused >> j) & 1u) &&
        fm1_mod_ui_has_dst(&c.s[j]) && fm1_mod_ui_slot_dest(env, &c.s[j], &d)) {
      char t[8];
      fm1_mod_ui_source(env->m, c.s[j].src, 0, t, sizeof t);
      if (strcmp(t, "?") != 0) c.ok |= 1u << j;
    }
  }
  if (i >= FM1_MOD_SLOTS || !fm1_mod_ui_has_dst(&c.s[i])) {
    snprintf(lines[0], FM1_MOD_UI_ROW_CHARS + 1, "Slot %u: no cable", i + 1u);
    return 1;
  }
  /* The selected cable, then the best cable into its source module and so
   * on up, then the best out of its destination module and so on down:
   * deepest first, the lower slot on a tie. */
  path[n++] = (uint8_t)i;
  on_path |= 1u << i;
  if (src_module(&c.s[i]) >= 0) visited |= 1u << src_module(&c.s[i]);
  if (dst_module(&c.s[i]) >= 0) visited |= 1u << dst_module(&c.s[i]);
  for (cur = src_module(&c.s[i]); cur >= 0 && n < (int)FM1_MOD_POSITIONS + 1;) {
    int best = -1, score = -1;
    for (j = 0; j < FM1_MOD_SLOTS; ++j) {
      const int from = src_module(&c.s[j]);
      int sc;
      if (!((c.ok >> j) & 1u) || dst_module(&c.s[j]) != cur || ((on_path >> j) & 1u)) continue;
      if (from >= 0 && ((visited >> from) & 1u)) continue;
      sc = from >= 0 ? 1 + depth(&c, 0, from) : 0;
      if (sc > score) score = sc, best = (int)j;
    }
    if (best < 0) break;
    memmove(path + 1, path, (size_t)n);
    path[0] = (uint8_t)best;
    ++n;
    ++sel;
    on_path |= 1u << best;
    cur = src_module(&c.s[best]);
    if (cur >= 0) visited |= 1u << cur;
  }
  for (cur = dst_module(&c.s[i]); cur >= 0 && n < (int)FM1_MOD_POSITIONS + 2;) {
    int best = -1, score = -1;
    for (j = 0; j < FM1_MOD_SLOTS; ++j) {
      const int to = dst_module(&c.s[j]);
      int sc;
      if (!((c.ok >> j) & 1u) || src_module(&c.s[j]) != cur || ((on_path >> j) & 1u)) continue;
      if (to >= 0 && ((visited >> to) & 1u)) continue;
      sc = to >= 0 ? 1 + depth(&c, 1, to) : 0;
      if (sc > score) score = sc, best = (int)j;
    }
    if (best < 0) break;
    path[n++] = (uint8_t)best;
    on_path |= 1u << best;
    cur = dst_module(&c.s[best]);
    if (cur >= 0) visited |= 1u << cur;
  }
  for (k = 0; k < n && out + 2 <= FM1_MOD_UI_CHAIN_LINES; ++k) {
    node_text(&c, c.s[path[k]].src, on_path, lines[out++]);
    if (k == sel) *hl = out;
    cable_text(&c, path[k], lines[out++]);
  }
  if (n && dst_module(&c.s[path[n - 1]]) >= 0 && out < FM1_MOD_UI_CHAIN_LINES) {
    fm1_mod_ui_label(env->m, (unsigned)dst_module(&c.s[path[n - 1]]), lines[out++],
                     FM1_MOD_UI_ROW_CHARS + 1);
  }
  return out;
}
