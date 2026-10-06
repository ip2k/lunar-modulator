/* state_json_write.c -- the canonical JSON writer (fm1_state.h;
 * notes/2026-10-06-state-files.md §7.2-§7.3; tests/state_canon.py states
 * the layout as code, and this writer must match it byte for byte).
 *
 * A record sink that holds the document (any record order) and writes it at
 * FM1_REC_END: members in the schemas' order, parameters by name in uid
 * order with every value written (a missing one gets its default, counted
 * in rep->defaulted), a pad kit's every pad, `null` for an empty unit, and
 * numbers as fm1_num.h writes them. Desktop and simulator only: it holds a
 * whole document in the caller's memory (fm1_state_json_writer_size()).
 * C99, no heap, no stdio. MIT licence. */
#include "fm1_state.h"
#include "fm1_num.h"

#include <string.h>

#define W_UNITS 40            /* sounds 0-3, inserts 4-11, MIDI effects 12-27, master/chain 28-31,
                                 modules 32-39 (parameters only) */
#define W_PARAMS 8192
#define W_LINES 8192
#define W_TEXT (256u * 1024u)
#define W_INFO 1024
#define W_OUT 1024

typedef struct {
  uint8_t unit;
  uint8_t focus;
  uint8_t vtype;
  uint8_t pad_;
  uint16_t uid;
  uint16_t pad2_;
  uint32_t bits;
} w_param_t;

typedef struct {
  uint8_t present;            /* a UNIT (or MODULE) record came */
  uint8_t has_on, on;
  uint8_t pad_;
  char id[16];
} w_unit_t;

typedef struct {
  uint8_t present, version;
  uint16_t n;
  uint8_t b[FM1_STATE_DATA_ONE];
} w_data_t;

typedef struct {
  uint8_t present;
  uint8_t pad_[3];
  fm1_mod_slot_t s;
  char name[25];
} w_cable_t;

struct fm1_state_writer {
  const fm1_state_names_t *nm;
  fm1_put_t put;
  void *ctx;
  fm1_state_report_t *rep;
  int compact;
  int err;
  uint8_t has_head, kind, minor;
  uint8_t has_session, has_mod, has_seed, has_view;
  uint8_t level_has[4];
  uint32_t level[4];
  uint32_t seed;
  fm1_rec_t session, view;
  uint16_t info_n[FM1_INFO_KEYS];
  uint8_t info_has[FM1_INFO_KEYS];
  char info[FM1_INFO_KEYS][W_INFO];
  uint8_t set_has[FM1_SET_KEYS];
  uint8_t set_bool[FM1_SET_KEYS];
  int32_t set_val[FM1_SET_KEYS];
  w_unit_t unit[W_UNITS];
  uint32_t n_params;
  w_param_t params[W_PARAMS];
  uint32_t dx7_mask;
  uint8_t dx7[32][155];
  w_data_t data[8];
  w_cable_t cable[32];
  uint8_t lines_which, line_open;
  uint32_t n_lines;
  uint32_t line_off[W_LINES];
  uint32_t line_len[W_LINES];
  uint32_t text_n;
  char text[W_TEXT];
  /* output */
  int sp;
  uint8_t inl[16], first[16];
  size_t outn;
  char out[W_OUT];
};

size_t fm1_state_json_writer_size(void) { return sizeof(struct fm1_state_writer); }

fm1_state_writer_t *fm1_state_json_writer(void *mem, const fm1_state_names_t *nm, int compact,
                                          fm1_put_t put, void *ctx, fm1_state_report_t *rep) {
  fm1_state_writer_t *w = (fm1_state_writer_t *)mem;
  if (!w) return NULL;
  memset(w, 0, sizeof(*w));
  w->nm = nm;
  w->compact = compact;
  w->put = put;
  w->ctx = ctx;
  w->rep = rep;
  return w;
}

static int werr(fm1_state_writer_t *w, unsigned code, const char *what) {
  if (!w->err) {
    w->err = 1;
    if (w->rep && w->rep->code == FM1_STATE_OK) {
      size_t n = strlen(what);
      w->rep->code = (uint8_t)code;
      if (n >= sizeof(w->rep->what)) n = sizeof(w->rep->what) - 1u;
      memcpy(w->rep->what, what, n);
      w->rep->what[n] = '\0';
    }
  }
  return 0;
}

static void wskip(fm1_state_writer_t *w, const char *what) {
  if (w->rep && !w->rep->skipped++) {
    size_t n = strlen(what);
    if (n >= sizeof(w->rep->first_skip)) n = sizeof(w->rep->first_skip) - 1u;
    memcpy(w->rep->first_skip, what, n);
    w->rep->first_skip[n] = '\0';
  }
}

/* Unit table index of a record's unit, or -1. */
static int w_unit_index(unsigned role, unsigned sound, unsigned slot) {
  switch (role) {
    case FM1_ROLE_SOUND: return sound < 4u ? (int)sound : -1;
    case FM1_ROLE_INSERT: return sound < 4u && slot < 2u ? (int)(4u + 2u * sound + slot) : -1;
    case FM1_ROLE_MFX: return sound < 4u && slot < 4u ? (int)(12u + 4u * sound + slot) : -1;
    case FM1_ROLE_MASTER: return slot < 4u ? (int)(28u + slot) : -1;
    case FM1_ROLE_MODULE: return slot < 8u ? (int)(32u + slot) : -1;
    default: return -1;
  }
}

static int add_piece(fm1_state_writer_t *w, const char *s, size_t n) {
  if (w->text_n + n > W_TEXT) return werr(w, FM1_STATE_TOO_BIG, "the set is larger than the writer holds");
  memcpy(w->text + w->text_n, s, n);
  w->text_n += (uint32_t)n;
  w->line_len[w->n_lines - 1u] += (uint32_t)n;
  return 1;
}

static int write_doc(fm1_state_writer_t *w);

int fm1_state_write(void *wv, const fm1_rec_t *r) {
  fm1_state_writer_t *w = (fm1_state_writer_t *)wv;
  int ix;
  if (w->err) return 0;
  switch (r->type) {
    case FM1_REC_HEAD:
      w->has_head = 1;
      w->kind = r->u.head.kind;
      w->minor = r->u.head.minor;
      return 1;
    case FM1_REC_INFO: {
      const unsigned k = r->u.info.key;
      if (k == 0 || k >= FM1_INFO_KEYS) return werr(w, FM1_STATE_BAD, "an unknown info key");
      if (r->piece & FM1_REC_FIRST) { w->info_n[k] = 0; w->info_has[k] = 1; }
      if (w->info_n[k] + r->u.info.n > W_INFO) return werr(w, FM1_STATE_TOO_BIG, "info text too long");
      memcpy(w->info[k] + w->info_n[k], r->u.info.s, r->u.info.n);
      w->info_n[k] = (uint16_t)(w->info_n[k] + r->u.info.n);
      return 1;
    }
    case FM1_REC_SESSION:
      w->session = *r;
      w->has_session = 1;
      return 1;
    case FM1_REC_UNIT:
    case FM1_REC_MODULE:
      ix = w_unit_index(r->type == FM1_REC_MODULE ? FM1_ROLE_MODULE : r->role, r->sound, r->slot);
      if (ix < 0) return werr(w, FM1_STATE_BAD, "a unit out of range");
      if (w->unit[ix].present) return werr(w, FM1_STATE_BAD, "a unit given twice");
      w->unit[ix].present = 1;
      memcpy(w->unit[ix].id, r->u.unit.id, sizeof(w->unit[ix].id));
      w->unit[ix].id[15] = '\0';
      return 1;
    case FM1_REC_ON:
      ix = w_unit_index(r->role, r->sound, r->slot);
      if (ix < 0) return werr(w, FM1_STATE_BAD, "a unit out of range");
      w->unit[ix].has_on = 1;
      w->unit[ix].on = r->u.on ? 1 : 0;
      return 1;
    case FM1_REC_PARAM: {
      w_param_t *p;
      uint32_t i;
      ix = w_unit_index(r->role, r->sound, r->slot);
      if (ix < 0) return werr(w, FM1_STATE_BAD, "a parameter's unit out of range");
      for (i = 0; i < w->n_params; ++i) {    /* a later value replaces an earlier one */
        p = &w->params[i];
        if (p->unit == ix && p->uid == r->u.param.uid && p->focus == r->u.param.focus) break;
      }
      if (i == w->n_params) {
        if (w->n_params >= W_PARAMS) return werr(w, FM1_STATE_TOO_BIG, "too many parameters");
        ++w->n_params;
      }
      p = &w->params[i];
      p->unit = (uint8_t)ix;
      p->uid = r->u.param.uid;
      p->focus = r->u.param.focus;
      p->vtype = r->u.param.vtype;
      p->bits = r->u.param.bits;
      if (p->vtype == FM1_VAL_F32 && (p->bits & 0x7FFFFFFFu) >= 0x7F800000u) {
        return werr(w, FM1_STATE_BAD, "a value that is not a finite float");
      }
      return 1;
    }
    case FM1_REC_LEVEL:
      if (r->sound >= 4u) return werr(w, FM1_STATE_BAD, "a level out of range");
      w->level_has[r->sound] = 1;
      w->level[r->sound] = r->u.level;
      return 1;
    case FM1_REC_DX7:
      if (r->slot >= 32u) return werr(w, FM1_STATE_BAD, "an FM6 slot out of range");
      w->dx7_mask |= 1u << r->slot;
      memcpy(w->dx7[r->slot], r->u.dx7.vced, 155);
      return 1;
    case FM1_REC_MOD:
      w->has_mod = 1;
      return 1;
    case FM1_REC_SEED:
      w->has_mod = 1;
      w->has_seed = 1;
      w->seed = r->u.seed;
      return 1;
    case FM1_REC_DATA: {
      w_data_t *d;
      if (r->slot >= 8u) return werr(w, FM1_STATE_BAD, "a rack position out of range");
      d = &w->data[r->slot];
      if (r->piece & FM1_REC_FIRST) { d->present = 1; d->n = 0; }
      d->version = r->u.data.version;
      if (d->n + r->u.data.n > FM1_STATE_DATA_ONE) return werr(w, FM1_STATE_TOO_BIG, "too much pattern data");
      memcpy(d->b + d->n, r->u.data.b, r->u.data.n);
      d->n = (uint16_t)(d->n + r->u.data.n);
      return 1;
    }
    case FM1_REC_CABLE:
      if (r->slot >= 32u) return werr(w, FM1_STATE_BAD, "a matrix slot out of range");
      w->cable[r->slot].present = 1;
      w->cable[r->slot].s = r->u.cable.s;
      memcpy(w->cable[r->slot].name, r->u.cable.name, sizeof(w->cable[r->slot].name));
      w->cable[r->slot].name[24] = '\0';
      return 1;
    case FM1_REC_LINE:
      if (r->piece & FM1_REC_FIRST) {
        if (w->n_lines >= W_LINES) return werr(w, FM1_STATE_TOO_BIG, "too many lines");
        w->lines_which = r->u.line.which;
        w->line_off[w->n_lines] = w->text_n;
        w->line_len[w->n_lines] = 0;
        ++w->n_lines;
        w->line_open = 1;
      } else if (!w->line_open) {
        return werr(w, FM1_STATE_BAD, "a line piece without its first");
      }
      if (!add_piece(w, r->u.line.s, r->u.line.n)) return 0;
      if (r->piece & FM1_REC_LAST) w->line_open = 0;
      return 1;
    case FM1_REC_VIEW:
      w->view = *r;
      w->has_view = 1;
      return 1;
    case FM1_REC_SETTING:
      if (r->u.setting.key == 0 || r->u.setting.key >= FM1_SET_KEYS) {
        wskip(w, "an unknown setting");
        return 1;
      }
      w->set_has[r->u.setting.key] = 1;
      w->set_bool[r->u.setting.key] = r->u.setting.is_bool;
      w->set_val[r->u.setting.key] = r->u.setting.value;
      return 1;
    case FM1_REC_END:
      return write_doc(w);
    default:
      return werr(w, FM1_STATE_BAD, "an unknown record");
  }
}

/* ---- The emitter: canonical layout or compact ------------------------------------------ */
static void flush(fm1_state_writer_t *w) {
  if (w->outn) w->put(w->ctx, w->out, w->outn);
  w->outn = 0;
}

static void raw(fm1_state_writer_t *w, const char *s, size_t n) {
  while (n) {
    size_t k = W_OUT - w->outn;
    if (k > n) k = n;
    memcpy(w->out + w->outn, s, k);
    w->outn += k;
    s += k;
    n -= k;
    if (w->outn == W_OUT) flush(w);
  }
}

static void rawz(fm1_state_writer_t *w, const char *s) { raw(w, s, strlen(s)); }

static void indent(fm1_state_writer_t *w, int levels) {
  int i;
  raw(w, "\n", 1);
  for (i = 0; i < levels; ++i) raw(w, "  ", 2);
}

/* Before a member or an item of the open container. */
static void sep(fm1_state_writer_t *w) {
  const int s = w->sp - 1;
  if (w->compact) {
    if (!w->first[s]) raw(w, ",", 1);
  } else if (w->inl[s]) {
    if (!w->first[s]) raw(w, ", ", 2);
  } else {
    if (!w->first[s]) raw(w, ",", 1);
    indent(w, w->sp);
  }
  w->first[s] = 0;
}

static void open_c(fm1_state_writer_t *w, char c, int inl) {
  raw(w, &c, 1);
  w->inl[w->sp] = (uint8_t)(inl || (w->sp > 0 && w->inl[w->sp - 1]));
  w->first[w->sp] = 1;
  ++w->sp;
}

static void close_c(fm1_state_writer_t *w, char c) {
  --w->sp;
  if (!w->compact && !w->inl[w->sp] && !w->first[w->sp]) indent(w, w->sp);
  raw(w, &c, 1);
}

static void jstr(fm1_state_writer_t *w, const char *s, size_t n) {
  static const char hex[] = "0123456789abcdef";
  size_t i, run = 0;
  raw(w, "\"", 1);
  for (i = 0; i < n; ++i) {
    const unsigned char c = (unsigned char)s[i];
    const char *esc = NULL;
    char u[7];
    if (c == '"') esc = "\\\"";
    else if (c == '\\') esc = "\\\\";
    else if (c < 0x20u) {
      switch (c) {
        case 8: esc = "\\b"; break;
        case 9: esc = "\\t"; break;
        case 10: esc = "\\n"; break;
        case 12: esc = "\\f"; break;
        case 13: esc = "\\r"; break;
        default:
          u[0] = '\\'; u[1] = 'u'; u[2] = '0'; u[3] = '0'; u[4] = hex[c >> 4]; u[5] = hex[c & 15u]; u[6] = '\0';
          esc = u;
          break;
      }
    }
    if (esc) {
      if (run) raw(w, s + i - run, run);
      run = 0;
      rawz(w, esc);
    } else {
      ++run;
    }
  }
  if (run) raw(w, s + n - run, run);
  raw(w, "\"", 1);
}

static void jstrz(fm1_state_writer_t *w, const char *s) { jstr(w, s, strlen(s)); }

static void key(fm1_state_writer_t *w, const char *k) {
  sep(w);
  jstrz(w, k);
  raw(w, w->compact ? ":" : ": ", w->compact ? 1u : 2u);
}

static void jint(fm1_state_writer_t *w, long long v) {
  char t[24];
  int n = 0;
  unsigned long long a = v < 0 ? 0ull - (unsigned long long)v : (unsigned long long)v;
  if (v < 0) raw(w, "-", 1);
  do { t[n++] = (char)('0' + a % 10u); a /= 10u; } while (a);
  while (n) { --n; raw(w, &t[n], 1); }
}

static void jf32(fm1_state_writer_t *w, uint32_t bits) {
  char t[24];
  const size_t n = fm1_num_f32_text(bits, t);
  raw(w, t, n);
}

static void jbool(fm1_state_writer_t *w, int b) { rawz(w, b ? "true" : "false"); }

/* ---- Parameters ------------------------------------------------------------------------------ */
static const w_param_t *find_param(const fm1_state_writer_t *w, int unit, uint16_t uid, uint8_t focus) {
  uint32_t i;
  for (i = 0; i < w->n_params; ++i) {
    const w_param_t *p = &w->params[i];
    if (p->unit == unit && p->uid == uid && p->focus == focus) return p;
  }
  return NULL;
}

static void param_val(fm1_state_writer_t *w, const fm1_param_t *p, uint8_t vtype, uint32_t bits) {
  if (p && p->type == FM1_PARAM_ENUM && vtype == FM1_VAL_INDEX) {
    const int count = (int)(p->max - p->min) + 1;
    if (p->enum_names && (int)bits < count) { jstrz(w, p->enum_names[bits]); return; }
    jint(w, (long long)bits);
    return;
  }
  if (vtype == FM1_VAL_INDEX) { jint(w, (long long)bits); return; }
  jf32(w, bits);
}

static void param_default(fm1_state_writer_t *w, const fm1_param_t *p) {
  if (w->rep) ++w->rep->defaulted;
  if (p->type == FM1_PARAM_ENUM) param_val(w, p, FM1_VAL_INDEX, (uint32_t)(int)p->def);
  else jf32(w, fm1_num_bits(p->def));
}

static void uid_key(fm1_state_writer_t *w, uint16_t uid) {
  char t[8];
  int n = 0, k = 0;
  unsigned v = uid;
  char d[6];
  do { d[n++] = (char)('0' + v % 10u); v /= 10u; } while (v);
  t[k++] = '#';
  while (n) t[k++] = d[--n];
  t[k] = '\0';
  key(w, t);
}

/* A params object: `focus` 0xFF (the unit's) or a pad. With a table, every
 * parameter that belongs here (per_focus: the per-pad ones, else the
 * others), with records not in the table as #UID, all in uid order. */
static void params_obj(fm1_state_writer_t *w, int unit, const fm1_engine_t *e, const fm1_param_t *table,
                       unsigned n, uint8_t focus) {
  uint16_t last = 0;
  open_c(w, '{', 0);
  for (;;) {
    /* The next uid above `last`, from the table or the records. */
    uint32_t best = 0x10000u, i;
    const fm1_param_t *bp = NULL;
    const w_param_t *br = NULL;
    for (i = 0; i < n; ++i) {
      const fm1_param_t *p = &table[i];
      const int fk = e ? fm1_state_param_focus(e, i) : 0;
      if (p->uid <= last || p->uid >= best) continue;
      if (focus == FM1_FOCUS_NONE ? fk == 2 : fk != 2) continue;
      best = p->uid;
      bp = p;
    }
    for (i = 0; i < w->n_params; ++i) {
      const w_param_t *r = &w->params[i];
      if (r->unit != unit || r->focus != focus || r->uid <= last || r->uid > best) continue;
      if (r->uid < best) bp = NULL;
      best = r->uid;
    }
    if (best == 0x10000u) break;
    last = (uint16_t)best;
    br = find_param(w, unit, (uint16_t)best, focus);
    if (bp && br) {
      key(w, bp->name);
      param_val(w, bp, br->vtype, br->bits);
    } else if (bp) {
      key(w, bp->name);
      param_default(w, bp);
    } else if (br) {
      /* A record no table names: if the uid is in the table but on the
       * other side of the pad split, it was put there by the source. */
      const fm1_param_t *tp = NULL;
      for (i = 0; i < n; ++i) {
        if (table[i].uid == best) tp = &table[i];
      }
      if (tp) {
        key(w, tp->name);
        param_val(w, tp, br->vtype, br->bits);
      } else {
        uid_key(w, (uint16_t)best);
        param_val(w, NULL, br->vtype, br->bits);
      }
    }
  }
  close_c(w, '}');
}

/* ---- Units ------------------------------------------------------------------------------------ */
static const fm1_engine_t *unit_engine(const fm1_state_writer_t *w, int ix) {
  unsigned role;
  if (ix < 0 || !w->unit[ix].present || !w->unit[ix].id[0]) return NULL;
  role = ix < 4 ? FM1_ROLE_SOUND : (ix < 12 ? FM1_ROLE_INSERT : (ix < 28 ? FM1_ROLE_MFX : FM1_ROLE_MASTER));
  return fm1_state_engine(w->nm, role, w->unit[ix].id);
}

static void unit_obj(fm1_state_writer_t *w, int ix, int role);

static void unit_or_null(fm1_state_writer_t *w, int ix, int role) {
  if (ix < 0 || !w->unit[ix].present || !w->unit[ix].id[0]) {
    rawz(w, "null");
    return;
  }
  unit_obj(w, ix, role);
}

static void unit_obj(fm1_state_writer_t *w, int ix, int role) {
  const fm1_engine_t *e = unit_engine(w, ix);
  open_c(w, '{', 0);
  key(w, "engine");
  jstrz(w, w->unit[ix].id);
  if (role == FM1_ROLE_MFX) {
    key(w, "on");
    if (!w->unit[ix].has_on && w->rep) ++w->rep->defaulted;
    jbool(w, w->unit[ix].on);
  }
  key(w, "params");
  params_obj(w, ix, e, e ? e->params : NULL, e ? e->n_params : 0u, FM1_FOCUS_NONE);
  if (role == FM1_ROLE_SOUND) {
    const int sound = ix;
    unsigned npads = e ? e->pad_count : 0u, i, j;
    if (npads > FM1_STATE_PADS) npads = FM1_STATE_PADS;
    if (!e) {
      for (i = 0; i < w->n_params; ++i) {
        const w_param_t *p = &w->params[i];
        if (p->unit == ix && p->focus != FM1_FOCUS_NONE && p->focus + 1u > npads) npads = p->focus + 1u;
      }
    }
    if (npads) {
      key(w, "pads");
      open_c(w, '[', 0);
      for (j = 0; j < npads; ++j) {
        sep(w);
        params_obj(w, ix, e, e ? e->params : NULL, e ? e->n_params : 0u, (uint8_t)j);
      }
      close_c(w, ']');
    }
    key(w, "level");
    if (w->level_has[sound]) jf32(w, w->level[sound]);
    else { if (w->rep) ++w->rep->defaulted; rawz(w, "100"); }
    key(w, "inserts");
    open_c(w, '[', 0);
    for (j = 0; j < 2; ++j) {
      sep(w);
      unit_or_null(w, 4 + 2 * sound + (int)j, FM1_ROLE_INSERT);
    }
    close_c(w, ']');
    key(w, "midi_fx");
    {
      int top = -1;
      for (j = 0; j < FM1_STATE_MFX; ++j) {
        if (w->unit[12 + 4 * sound + (int)j].present) top = (int)j;
      }
      open_c(w, '[', 0);
      for (j = 0; (int)j <= top; ++j) {
        sep(w);
        unit_or_null(w, 12 + 4 * sound + (int)j, FM1_ROLE_MFX);
      }
      close_c(w, ']');
    }
  }
  close_c(w, '}');
}

/* ---- Cables ------------------------------------------------------------------------------------ */
static const fm1_mod_kind_t *rack_kind(const fm1_state_writer_t *w, unsigned pos) {
  if (pos >= 8u || !w->unit[32 + pos].present) return NULL;
  return fm1_state_kind(w->nm, w->unit[32 + pos].id);
}

/* A cable unit code's name in this kind of file, or NULL. */
static const char *code_name(unsigned kind, unsigned code, char out[12]) {
  if (code == FM1_MOD_HOST) return "host";
  if (kind == FM1_STATE_SOUND) {
    if (code == FM1_MOD_SOUND) return "snd";
    if (code == FM1_MOD_INSERT) return "snd.fx1";
    if (code == FM1_MOD_INSERT + 1u) return "snd.fx2";
    return NULL;
  }
  if (kind == FM1_STATE_FX) {
    if (code == FM1_MOD_FX1) return "fx1";
    if (code == FM1_MOD_FX2) return "fx2";
    if (code == FM1_STATE_CHAIN3) return "fx3";
    if (code == FM1_STATE_CHAIN4) return "fx4";
    return NULL;
  }
  if (code == FM1_MOD_FX1) return "fx1";
  if (code == FM1_MOD_FX2) return "fx2";
  if (code == FM1_MOD_SOUND || (code >= 17u && code <= 19u)) {
    memcpy(out, "snd1", 5);
    out[3] = (char)('1' + (code ? code - 16u : 0u));
    return out;
  }
  if (code >= FM1_MOD_INSERT && code < FM1_MOD_INSERT + 16u && ((code - FM1_MOD_INSERT) & 3u) < 2u) {
    memcpy(out, "snd1.fx1", 9);
    out[3] = (char)('1' + (code - FM1_MOD_INSERT) / 4u);
    out[7] = (char)('1' + ((code - FM1_MOD_INSERT) & 3u));
    return out;
  }
  return NULL;
}

/* A code's unit table index (as the reader's code_index), or -1. */
static int code_unit(unsigned code) {
  if (code == FM1_MOD_SOUND) return 0;
  if (code >= 17u && code <= 19u) return (int)(code - 16u);
  if (code >= FM1_MOD_INSERT && code < FM1_MOD_INSERT + 16u && ((code - FM1_MOD_INSERT) & 3u) < 2u) {
    return (int)(4u + 2u * ((code - FM1_MOD_INSERT) / 4u) + ((code - FM1_MOD_INSERT) & 3u));
  }
  if (code == FM1_MOD_FX1) return 28;
  if (code == FM1_MOD_FX2) return 29;
  if (code == FM1_STATE_CHAIN3) return 30;
  if (code == FM1_STATE_CHAIN4) return 31;
  return -1;
}

static int ref_ok(const fm1_state_writer_t *w, unsigned src) {
  if (src < FM1_MOD_SRC_SYSTEM) return w->nm && w->nm->source && w->nm->source(src);
  return src < FM1_MOD_SRC_MODULE + 64u;
}

static void ref_obj(fm1_state_writer_t *w, unsigned src) {
  open_c(w, '{', 1);
  if (src < FM1_MOD_SRC_SYSTEM) {
    key(w, "source");
    jstrz(w, w->nm->source(src)->name);
  } else {
    const unsigned pos = (src - FM1_MOD_SRC_MODULE) / 8u, port = (src - FM1_MOD_SRC_MODULE) % 8u;
    const fm1_mod_kind_t *k = rack_kind(w, pos);
    key(w, "module");
    jint(w, pos + 1u);
    key(w, "port");
    if (k && port < k->n_out) jstrz(w, k->out[port].name);
    else jint(w, port + 1u);
  }
  close_c(w, '}');
}

static int cable_ok(const fm1_state_writer_t *w, const w_cable_t *c) {
  char tmp[12];
  const fm1_mod_slot_t *s = &c->s;
  if (!ref_ok(w, s->src)) return 0;
  if (s->via != FM1_MOD_NONE && !ref_ok(w, s->via)) return 0;
  if (s->dst_unit >= FM1_MOD_MODULE && s->dst_unit < FM1_MOD_MODULE + 8u) return 1;
  if (s->flags & FM1_MOD_SLOT_GATE_DST) return 0;
  return code_name(w->kind, s->dst_unit, tmp) != NULL;
}

static void target_obj(fm1_state_writer_t *w, const w_cable_t *c) {
  const fm1_mod_slot_t *s = &c->s;
  const fm1_param_t *table = NULL;
  unsigned n = 0, i;
  open_c(w, '{', 1);
  if (s->dst_unit >= FM1_MOD_MODULE && s->dst_unit < FM1_MOD_MODULE + 8u) {
    const unsigned pos = s->dst_unit - FM1_MOD_MODULE;
    const fm1_mod_kind_t *k = rack_kind(w, pos);
    key(w, "module");
    jint(w, pos + 1u);
    if (s->flags & FM1_MOD_SLOT_GATE_DST) {
      key(w, "gate");
      if (k && s->dst < k->n_gate_in) jstrz(w, k->gate_in[s->dst].name);
      else jint(w, s->dst + 1u);
      close_c(w, '}');
      return;
    }
    if (k) { table = k->params; n = k->n_params; }
  } else {
    char tmp[12];
    key(w, "unit");
    jstrz(w, code_name(w->kind, s->dst_unit, tmp));
    if (s->dst_unit == FM1_MOD_HOST) {
      if (w->nm) { table = w->nm->host; n = w->nm->n_host; }
    } else {
      const fm1_engine_t *e = unit_engine(w, code_unit(s->dst_unit));
      if (e) { table = e->params; n = e->n_params; }
    }
  }
  key(w, "param");
  if (!s->dst && c->name[0]) {
    jstrz(w, c->name);
  } else {
    const char *nm = NULL;
    for (i = 0; i < n; ++i) {
      if (table[i].uid == s->dst) nm = table[i].name;
    }
    if (nm) {
      jstrz(w, nm);
    } else {
      char t[8];
      int k = 0, d = 0;
      char dg[6];
      unsigned v = s->dst;
      do { dg[d++] = (char)('0' + v % 10u); v /= 10u; } while (v);
      t[k++] = '#';
      while (d) t[k++] = dg[--d];
      t[k] = '\0';
      jstrz(w, t);
    }
  }
  close_c(w, '}');
}

static void q14(fm1_state_writer_t *w, int q) {
  char t[16];
  const size_t n = fm1_num_q14_text(q, t);
  raw(w, t, n);
}

static void mod_obj(fm1_state_writer_t *w) {
  static const char *const kPol[4] = { "auto", "uni", "bi", "inv" };
  static const char *const kCurve[8] = { "lin", "square", "cube", "root", "cbrt", "exp", "log", "s" };
  unsigned p, j;
  key(w, "mod");
  open_c(w, '{', 0);
  if (w->has_seed) {
    key(w, "seed");
    jint(w, w->seed);
  }
  key(w, "rack");
  open_c(w, '[', 0);
  for (p = 0; p < 8u; ++p) {
    const fm1_mod_kind_t *k;
    if (!w->unit[32 + p].present) continue;
    k = rack_kind(w, p);
    sep(w);
    open_c(w, '{', 0);
    key(w, "pos");
    jint(w, p + 1u);
    key(w, "kind");
    jstrz(w, w->unit[32 + p].id);
    key(w, "params");
    params_obj(w, 32 + (int)p, NULL, k ? k->params : NULL, k ? k->n_params : 0u, FM1_FOCUS_NONE);
    if (w->data[p].present) {
      static const char hex[] = "0123456789abcdef";
      uint16_t i;
      key(w, "data");
      open_c(w, '{', 1);
      key(w, "version");
      jint(w, w->data[p].version);
      key(w, "hex");
      raw(w, "\"", 1);
      for (i = 0; i < w->data[p].n; ++i) {
        char h[2];
        h[0] = hex[w->data[p].b[i] >> 4];
        h[1] = hex[w->data[p].b[i] & 15u];
        raw(w, h, 2);
      }
      raw(w, "\"", 1);
      close_c(w, '}');
    }
    close_c(w, '}');
  }
  close_c(w, ']');
  key(w, "cables");
  open_c(w, '[', 0);
  for (j = 0; j < 32u; ++j) {
    const w_cable_t *c = &w->cable[j];
    const fm1_mod_slot_t *s = &c->s;
    if (!c->present) continue;
    if (!cable_ok(w, c)) {
      wskip(w, "a cable this kind of file or build cannot name");
      continue;
    }
    sep(w);
    open_c(w, '{', 0);
    key(w, "slot");
    jint(w, j + 1u);
    key(w, "on");
    jbool(w, (s->flags & FM1_MOD_SLOT_ON) != 0);
    key(w, "from");
    ref_obj(w, s->src);
    key(w, "via");
    if (s->via == FM1_MOD_NONE) rawz(w, "null");
    else ref_obj(w, s->via);
    key(w, "to");
    target_obj(w, c);
    key(w, "amount");
    q14(w, s->amount);
    key(w, "offset");
    q14(w, s->offset);
    key(w, "polarity");
    jstrz(w, kPol[(s->flags & FM1_MOD_SLOT_POL_MASK) >> FM1_MOD_SLOT_POL_SHIFT]);
    key(w, "curve");
    jstrz(w, kCurve[(s->flags & FM1_MOD_SLOT_CURVE_MASK) >> FM1_MOD_SLOT_CURVE_SHIFT]);
    key(w, "voice");
    jbool(w, (s->flags & FM1_MOD_SLOT_VOICE) != 0);
    key(w, "lock");
    jint(w, s->uid);
    close_c(w, '}');
  }
  close_c(w, ']');
  close_c(w, '}');
}

/* ---- The document ------------------------------------------------------------------------------- */
static void info_member(fm1_state_writer_t *w, unsigned k, const char *name) {
  if (!w->info_has[k]) return;
  key(w, name);
  jstr(w, w->info[k], w->info_n[k]);
}

static int write_doc(fm1_state_writer_t *w) {
  static const char *const kRoots[12] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B" };
  static const char *const kModes[FM1_VIEW_MODES] = { "home", "fx", "glo", "seq", "session", "song",
                                                      "rack", "matrix", "chain" };
  static const char *const kVKeys[FM1_VIEW_KEYS] = { "sound", "page", "unit", "track", "bar", "panel",
                                                     "pos", "slot", "entry" };
  static const char *const kPanels[4] = { "track", "set", "clip", "step" };
  static const char *const kSet[FM1_SET_KEYS] = { NULL, "metronome", "count_in_click", "full_velocity",
                                                  "midi_in_channel" };
  const char *kname;
  unsigned i, j;
  if (!w->has_head) return werr(w, FM1_STATE_BAD, "no head record");
  kname = fm1_state_kind_name(w->kind);
  if (!kname || w->kind == FM1_STATE_SET || w->kind == FM1_STATE_DX7BANK) {
    return werr(w, FM1_STATE_BAD, "this kind has no JSON form");
  }
  if (w->kind == FM1_STATE_SOUND && !w->unit[0].present) return werr(w, FM1_STATE_BAD, "a sound file needs its sound");
  if (w->kind == FM1_STATE_PROJECT && (!w->unit[0].present || !w->unit[0].id[0])) {
    return werr(w, FM1_STATE_BAD, "Sound 1 is never empty");
  }
  w->sp = 0;
  open_c(w, '{', 0);
  key(w, "lunar");
  {
    char lv[8];
    size_t n = 0;
    unsigned m = w->minor;
    char d[4];
    int k = 0;
    lv[n++] = (char)('0' + FM1_STATE_MAJOR);
    lv[n++] = '.';
    do { d[k++] = (char)('0' + m % 10u); m /= 10u; } while (m);
    while (k) lv[n++] = d[--k];
    jstr(w, lv, n);
  }
  key(w, "kind");
  jstrz(w, kname);
  if (w->info_has[FM1_INFO_BY] || w->info_has[FM1_INFO_VERSION] || w->info_has[FM1_INFO_COMMIT]) {
    key(w, "made");
    open_c(w, '{', 1);
    info_member(w, FM1_INFO_BY, "by");
    info_member(w, FM1_INFO_VERSION, "version");
    info_member(w, FM1_INFO_COMMIT, "commit");
    close_c(w, '}');
  }
  info_member(w, FM1_INFO_NAME, "name");
  info_member(w, FM1_INFO_TITLE, "title");
  info_member(w, FM1_INFO_ABOUT, "about");
  info_member(w, FM1_INFO_AUTHOR, "author");
  info_member(w, FM1_INFO_LICENCE, "licence");
  switch (w->kind) {
    case FM1_STATE_PROJECT:
      if (w->has_session) {
        const fm1_rec_t *s = &w->session;
        key(w, "session");
        open_c(w, '{', 0);
        key(w, "current"); jint(w, s->u.session.current + 1);
        key(w, "octave"); jint(w, s->u.session.octave);
        key(w, "transpose"); jint(w, s->u.session.transpose);
        if (s->u.session.has_key) {
          key(w, "key");
          open_c(w, '{', 1);
          key(w, "root"); jstrz(w, kRoots[s->u.session.root % 12u]);
          key(w, "scale"); jstrz(w, s->u.session.scale);
          close_c(w, '}');
        }
        close_c(w, '}');
      }
      key(w, "sounds");
      open_c(w, '[', 0);
      for (i = 0; i < 4u; ++i) {
        sep(w);
        unit_or_null(w, (int)i, FM1_ROLE_SOUND);
      }
      close_c(w, ']');
      key(w, "master");
      open_c(w, '[', 0);
      for (i = 0; i < 2u; ++i) {
        sep(w);
        unit_or_null(w, 28 + (int)i, FM1_ROLE_MASTER);
      }
      close_c(w, ']');
      break;
    case FM1_STATE_SOUND:
      key(w, "sound");
      unit_obj(w, 0, FM1_ROLE_SOUND);
      break;
    case FM1_STATE_FX: {
      int top = -1;
      for (i = 0; i < FM1_STATE_CHAIN; ++i) {
        if (w->unit[28 + i].present) top = (int)i;
      }
      key(w, "chain");
      open_c(w, '[', 0);
      for (i = 0; (int)i <= top; ++i) {
        sep(w);
        unit_or_null(w, 28 + (int)i, FM1_ROLE_MASTER);
      }
      close_c(w, ']');
      break;
    }
    default:
      break;
  }
  if ((w->kind == FM1_STATE_PROJECT || w->kind == FM1_STATE_SOUND) && w->dx7_mask) {
    key(w, "dx7");
    open_c(w, '[', 0);
    for (i = 0; i < 32u; ++i) {
      const uint8_t *v = w->dx7[i];
      int nl = 10;
      if (!((w->dx7_mask >> i) & 1u)) continue;
      sep(w);
      open_c(w, '{', 0);
      key(w, "slot"); jint(w, i + 1u);
      key(w, "name");
      while (nl > 0 && v[145 + nl - 1] == ' ') --nl;
      jstr(w, (const char *)v + 145, (size_t)nl);
      key(w, "ops");
      open_c(w, '[', 0);
      for (j = 0; j < 6u; ++j) {
        unsigned k;
        sep(w);
        open_c(w, '[', 1);
        for (k = 0; k < 21u; ++k) { sep(w); jint(w, v[j * 21u + k]); }
        close_c(w, ']');
      }
      close_c(w, ']');
      key(w, "globals");
      open_c(w, '[', 1);
      for (j = 0; j < 19u; ++j) { sep(w); jint(w, v[126u + j]); }
      close_c(w, ']');
      close_c(w, '}');
    }
    close_c(w, ']');
  }
  if (w->has_mod || w->kind == FM1_STATE_MODS) {
    if (w->kind == FM1_STATE_PROJECT || w->kind == FM1_STATE_SOUND || w->kind == FM1_STATE_FX ||
        w->kind == FM1_STATE_MODS) {
      mod_obj(w);
    }
  }
  if ((w->kind == FM1_STATE_PROJECT && w->lines_which == FM1_LINES_SET && w->n_lines) ||
      (w->kind == FM1_STATE_CLIP && w->lines_which == FM1_LINES_CLIP)) {
    key(w, w->kind == FM1_STATE_CLIP ? "clip" : "set");
    open_c(w, '[', 0);
    for (i = 0; i < w->n_lines; ++i) {
      sep(w);
      jstr(w, w->text + w->line_off[i], w->line_len[i]);
    }
    close_c(w, ']');
  }
  if (w->kind == FM1_STATE_SETTINGS) {
    key(w, "settings");
    open_c(w, '{', 0);
    for (i = 1; i < FM1_SET_KEYS; ++i) {
      if (!w->set_has[i]) continue;
      key(w, kSet[i]);
      if (w->set_bool[i]) jbool(w, w->set_val[i] != 0);
      else jint(w, w->set_val[i]);
    }
    close_c(w, '}');
  }
  if (w->has_view && w->kind != FM1_STATE_SETTINGS) {
    const fm1_rec_t *v = &w->view;
    key(w, "view");
    open_c(w, '{', 1);
    key(w, "mode");
    jstrz(w, kModes[v->u.view.mode % FM1_VIEW_MODES]);
    for (i = 0; i < FM1_VIEW_KEYS; ++i) {
      if (!((v->u.view.has >> i) & 1u)) continue;
      key(w, kVKeys[i]);
      if (i == FM1_VK_UNIT) {
        char tmp[12];
        const char *nm = code_name(FM1_STATE_PROJECT, v->u.view.v[i], tmp);
        jstrz(w, nm ? nm : "host");
      } else if (i == FM1_VK_PANEL) {
        jstrz(w, kPanels[v->u.view.v[i] & 3u]);
      } else {
        jint(w, v->u.view.v[i]);
      }
    }
    close_c(w, '}');
  }
  close_c(w, '}');
  if (!w->compact) raw(w, "\n", 1);
  flush(w);
  return 1;
}
