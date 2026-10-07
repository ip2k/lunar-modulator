/* fm1_edit.c -- the edit layer (fm1_edit.h; notes/2026-10-06-web-editor.md
 * §5, stage ED1): records and verbs applied live through the panel's own
 * calls, the change ring the hooks in fm1_app.c fill, the telemetry block
 * (include/fm1_tele.h), the view record with its knob map, and the
 * parameter text parser (fm1_param_parse, fm1_look.h).
 * C99. MIT licence, like the rest of this repository.
 */
#include "fm1_edit.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "fm1_app_state.h"
#include "fm1_comp.h"
#include "fm1_look.h"
#include "fm1_refusal.h"

/* ---- small helpers ------------------------------------------------------------- */

static uint16_t rd16(const uint8_t *b) { return (uint16_t)(b[0] | (b[1] << 8)); }
static uint32_t rd32(const uint8_t *b) {
  return (uint32_t)b[0] | ((uint32_t)b[1] << 8) | ((uint32_t)b[2] << 16) | ((uint32_t)b[3] << 24);
}
static void wr16(uint8_t *b, uint16_t v) { b[0] = (uint8_t)v; b[1] = (uint8_t)(v >> 8); }
static void wr32(uint8_t *b, uint32_t v) {
  b[0] = (uint8_t)v; b[1] = (uint8_t)(v >> 8); b[2] = (uint8_t)(v >> 16); b[3] = (uint8_t)(v >> 24);
}
static uint32_t fbits(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }
static float bitsf(uint32_t u) { float f; memcpy(&f, &u, 4); return f; }

/* An app unit from a record's role, sound and slot; -1 for none. */
static int unit_of(unsigned role, unsigned sound, unsigned slot) {
  switch (role) {
    case FM1_ROLE_SOUND: return sound < FM1_APP_SOUNDS ? fm1_app_sound_unit((int)sound) : -1;
    case FM1_ROLE_INSERT:
      return sound < FM1_APP_SOUNDS && slot < FM1_APP_INSERTS ? fm1_app_insert_unit((int)sound, (int)slot) : -1;
    case FM1_ROLE_MASTER: return slot < FM1_APP_FX_SLOTS ? 1 + (int)slot : -1;
    default: return -1;
  }
}

/* ... and back. */
static void where(int unit, uint8_t *role, uint8_t *sound, uint8_t *slot) {
  *role = FM1_ROLE_NONE;
  *sound = *slot = 0;
  if (unit >= 1 && unit <= FM1_APP_FX_SLOTS) {
    *role = FM1_ROLE_MASTER;
    *slot = (uint8_t)(unit - 1);
    return;
  }
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    if (fm1_app_sound_unit(k) == unit) {
      *role = FM1_ROLE_SOUND;
      *sound = (uint8_t)k;
      return;
    }
    for (int j = 0; j < FM1_APP_INSERTS; ++j) {
      if (fm1_app_insert_unit(k, j) == unit) {
        *role = FM1_ROLE_INSERT;
        *sound = (uint8_t)k;
        *slot = (uint8_t)j;
        return;
      }
    }
  }
}

static int is_effect_unit(int unit) {
  uint8_t role, sound, slot;
  where(unit, &role, &sound, &slot);
  return role == FM1_ROLE_INSERT || role == FM1_ROLE_MASTER;
}

const fm1_param_t *fm1_edit_find_param(const char *id, uint16_t uid) {
  const fm1_param_t *ps = NULL;
  unsigned n = 0, i;
  const fm1_engine_t *e;
  const fm1_midi_fx_t *fx;
  int k;
  if (!id) return NULL;
  if ((e = fm1_engine_find(id)) != NULL) {
    ps = e->params, n = e->n_params;
  } else if ((fx = fm1_midi_fx_find(id)) != NULL) {
    ps = fx->engine.params, n = fx->engine.n_params;
  } else if (strcmp(id, "host") == 0) {
    ps = fm1_mod_host_params, n = FM1_MOD_HOST_PARAMS;
  } else if ((k = fm1_mod_kind_find(id)) >= 0 && strcmp(fm1_mod_kinds[k]->id, id) == 0) {
    ps = fm1_mod_kinds[k]->params, n = fm1_mod_kinds[k]->n_params;
  }
  for (i = 0; ps && i < n; ++i) {
    if (ps[i].uid == uid) return &ps[i];
  }
  return NULL;
}

/* ---- fm1_param_parse ------------------------------------------------------------ */

static int lower(int c) { return c >= 'A' && c <= 'Z' ? c + 32 : c; }

static int eq_word(const char *a, size_t n, const char *b) {
  size_t i;
  for (i = 0; i < n && b[i]; ++i) {
    if (lower((unsigned char)a[i]) != lower((unsigned char)b[i])) return 0;
  }
  return i == n && !b[i];
}

int fm1_param_parse(const fm1_param_t *p, const char *text, float *out) {
  char buf[48];
  size_t n = 0, len;
  const char *s = text, *w;
  char *end;
  double v, scale = 1.0;
  if (!p || !text || !out) return 0;
  /* Copy, trimmed, with the typographic minus (U+2212) as '-'. */
  while (*s == ' ' || *s == '\t') ++s;
  while (*s && n + 1 < sizeof buf) {
    if ((unsigned char)s[0] == 0xE2 && (unsigned char)s[1] == 0x88 && (unsigned char)s[2] == 0x92) {
      buf[n++] = '-';
      s += 3;
    } else {
      buf[n++] = *s++;
    }
  }
  if (*s) return 0;                      /* longer than any value */
  while (n && (buf[n - 1] == ' ' || buf[n - 1] == '\t')) --n;
  buf[n] = 0;
  if (!n) return 0;
  if (p->type == FM1_PARAM_ENUM) {
    const int count = (int)(p->max - p->min) + 1;
    long k;
    for (int i = 0; p->enum_names && i < count; ++i) {
      if (p->enum_names[i] && eq_word(buf, n, p->enum_names[i])) {
        *out = p->min + (float)i;
        return 1;
      }
    }
    k = strtol(buf, &end, 10);          /* the screen's number when it has no names */
    if (end == buf || *end || (float)k < p->min || (float)k > p->max) return 0;
    *out = (float)k;
    return 1;
  }
  v = strtod(buf, &end);
  if (end == buf || !isfinite(v)) return 0;
  w = end;
  while (*w == ' ') ++w;
  len = strlen(w);
  if ((*w == 'k' || *w == 'K') && (len == 1 || eq_word(w, len, "khz"))) {
    scale = 1000.0;                     /* "1.2k", "1.2 kHz" */
    if (len == 1 && p->unit != FM1_UNIT_HZ && p->unit != FM1_UNIT_NONE) return 0;
    if (len > 1 && p->unit != FM1_UNIT_HZ) return 0;
  } else if (len) {
    int ok = 0;
    switch (p->unit) {
      case FM1_UNIT_HZ: ok = eq_word(w, len, "hz"); break;
      case FM1_UNIT_MS:
        if (eq_word(w, len, "s") || eq_word(w, len, "sec")) ok = 1, scale = 1000.0;
        else ok = eq_word(w, len, "ms");
        break;
      case FM1_UNIT_DB: ok = eq_word(w, len, "db"); break;
      case FM1_UNIT_PCT: ok = eq_word(w, len, "%"); break;
      case FM1_UNIT_SEMI: ok = eq_word(w, len, "st") || eq_word(w, len, "semi") || eq_word(w, len, "semitones"); break;
      case FM1_UNIT_DEG: ok = eq_word(w, len, "deg") || eq_word(w, len, "\xc2\xb0"); break;
      default: ok = eq_word(w, len, "x"); break;
    }
    if (!ok) return 0;
  }
  v *= scale;
  if (!isfinite(v)) return 0;
  *out = fm1_param_clamp(p, (float)v);
  return 1;
}

/* ---- the ring ------------------------------------------------------------------- */

static void push(fm1_app_t *a, const uint8_t rec[FM1_EDIT_REC_BYTES]) {
  fm1_edit_t *e = a->edit;
  fm1_change_t *c;
  if (!e || e->src == FM1_EDIT_LOAD) return;   /* a load is one LOADED entry */
  c = &e->ring[e->gen % FM1_EDIT_RING];
  c->gen = ++e->gen;
  c->src = e->src;
  c->pad_ = 0;
  c->tag = e->src == FM1_EDIT_EDITOR ? e->tag : 0;
  memcpy(c->rec, rec, FM1_EDIT_REC_BYTES);
}

static void push_rec(fm1_app_t *a, const fm1_rec_t *r) {
  uint8_t b[FM1_EDIT_REC_BYTES];
  if (fm1_edit_pack(r, b)) push(a, b);
}

static fm1_rec_t blank(unsigned type) {
  fm1_rec_t r;
  memset(&r, 0, sizeof r);
  r.type = (uint8_t)type;
  return r;
}

uint32_t fm1_edit_gen(const fm1_app_t *a) { return a->edit ? a->edit->gen : 0u; }

uint32_t fm1_edit_changes(const fm1_app_t *a, uint32_t gen, fm1_change_t *out, uint32_t max) {
  const fm1_edit_t *e = a->edit;
  uint32_t n = 0, g;
  if (!e || gen >= e->gen) return 0;
  if (e->gen - gen > FM1_EDIT_RING) return FM1_EDIT_RESYNC;
  for (g = gen + 1; g <= e->gen && n < max; ++g) out[n++] = e->ring[(g - 1) % FM1_EDIT_RING];
  return n;
}

int fm1_edit_enter(fm1_app_t *a, uint8_t src) {
  int was;
  if (!a->edit) return -1;
  was = a->edit->src;
  a->edit->src = src;
  ++a->edit->depth_;
  return was;
}

void fm1_edit_leave(fm1_app_t *a, int was) {
  if (!a->edit || was < 0) return;
  if (--a->edit->depth_ == 0) fm1_edit_mod_scan(a);   /* the outermost leave only */
  a->edit->src = (uint8_t)was;
}

void fm1_edit_note_param(fm1_app_t *a, int unit, int index) {
  const fm1_app_unit_t *u;
  fm1_rec_t r = blank(FM1_REC_PARAM);
  if (!a->edit || unit < 0 || unit >= FM1_APP_UNITS) return;
  u = &a->unit[unit];
  if (!u->e || index < 0 || index >= u->e->n_params) return;
  where(unit, &r.role, &r.sound, &r.slot);
  r.u.param.uid = u->e->params[index].uid;
  r.u.param.focus = FM1_FOCUS_NONE;
  r.u.param.vtype = FM1_VAL_F32;
  r.u.param.bits = fbits(u->value[index]);
  push_rec(a, &r);
}

void fm1_edit_note_unit(fm1_app_t *a, int unit) {
  fm1_rec_t r = blank(FM1_REC_UNIT);
  if (!a->edit || unit < 0 || unit >= FM1_APP_UNITS) return;
  where(unit, &r.role, &r.sound, &r.slot);
  if (a->unit[unit].e) snprintf(r.u.unit.id, sizeof r.u.unit.id, "%s", a->unit[unit].e->id);
  push_rec(a, &r);
}

void fm1_edit_note_level(fm1_app_t *a, int sound) {
  fm1_rec_t r = blank(FM1_REC_LEVEL);
  if (!a->edit || sound < 0 || sound >= FM1_APP_SOUNDS) return;
  r.sound = (uint8_t)sound;
  r.u.level = fbits(a->level[sound]);
  push_rec(a, &r);
}

void fm1_edit_note_mfx(fm1_app_t *a, int sound, int param) {
  const fm1_engine_t *e = fm1_app_mfx_engine(a, sound);
  fm1_rec_t r;
  if (!a->edit || !e) return;
  if (param == -1) {
    r = blank(FM1_REC_ON);
    r.u.on = (uint8_t)fm1_app_arp_on(a, sound);
  } else if (param == -2) {
    r = blank(FM1_REC_UNIT);
    snprintf(r.u.unit.id, sizeof r.u.unit.id, "%s", e->id);
  } else {
    if (param < 0 || param >= e->n_params) return;
    r = blank(FM1_REC_PARAM);
    r.u.param.uid = e->params[param].uid;
    r.u.param.focus = FM1_FOCUS_NONE;
    r.u.param.vtype = FM1_VAL_F32;
    r.u.param.bits = fbits(a->arp_value[sound][param]);
  }
  r.role = FM1_ROLE_MFX;
  r.sound = (uint8_t)sound;
  push_rec(a, &r);
}

void fm1_edit_note_current(fm1_app_t *a) {
  fm1_edit_verb_t v;
  uint8_t b[FM1_EDIT_REC_BYTES];
  if (!a->edit) return;
  memset(&v, 0, sizeof v);
  v.verb = FM1_EDIT_CURRENT;
  v.sound[0] = (uint8_t)a->sound;
  fm1_edit_verb_pack(&v, b);
  push(a, b);
}

void fm1_edit_note_swap(fm1_app_t *a, int ua, int ub) {
  fm1_edit_verb_t v;
  uint8_t b[FM1_EDIT_REC_BYTES];
  if (!a->edit) return;
  memset(&v, 0, sizeof v);
  v.verb = FM1_EDIT_SWAP;
  where(ua, &v.role[0], &v.sound[0], &v.slot[0]);
  where(ub, &v.role[1], &v.sound[1], &v.slot[1]);
  fm1_edit_verb_pack(&v, b);
  push(a, b);
  fm1_edit_mod_scan(a);                  /* the cables that followed them */
}

/* The modulation now, into the snapshot; with `log`, each difference as an
 * entry: a kind first, then its parameters' bases, then the slots. */
static void mod_take(fm1_app_t *a, int log) {
  fm1_edit_t *e = a->edit;
  const fm1_mod_t *m = a->mod;
  unsigned pos, i;
  if (!e) return;
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const int kind = m ? fm1_mod_kind_at(m, pos) : -1;
    const fm1_mod_kind_t *kd = kind >= 0 ? fm1_mod_kinds[kind] : NULL;
    if (log && kind != e->kind[pos]) {
      fm1_rec_t r = blank(FM1_REC_MODULE);
      r.role = FM1_ROLE_MODULE;
      r.slot = (uint8_t)pos;
      if (kd) snprintf(r.u.unit.id, sizeof r.u.unit.id, "%s", kd->id);
      push_rec(a, &r);
    }
    e->kind[pos] = (int8_t)kind;
    for (i = 0; i < FM1_MOD_MAX_PARAMS; ++i) {
      const uint32_t bits = kd && i < kd->n_params ? fbits(fm1_mod_param_base(m, pos, i)) : 0u;
      if (log && kd && i < kd->n_params && bits != e->base[pos][i]) {
        fm1_rec_t r = blank(FM1_REC_PARAM);
        r.role = FM1_ROLE_MODULE;
        r.slot = (uint8_t)pos;
        r.u.param.uid = kd->params[i].uid;
        r.u.param.focus = FM1_FOCUS_NONE;
        r.u.param.vtype = FM1_VAL_F32;
        r.u.param.bits = bits;
        push_rec(a, &r);
      }
      e->base[pos][i] = bits;
    }
  }
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t s;
    memset(&s, 0, sizeof s);
    if (m) fm1_mod_get_slot(m, i, &s);
    if (log && memcmp(&s, &e->slot[i], sizeof s) != 0) {
      fm1_rec_t r = blank(FM1_REC_CABLE);
      r.slot = (uint8_t)i;
      r.u.cable.s = s;
      push_rec(a, &r);
    }
    e->slot[i] = s;
  }
  e->mod_known = 1;
}

void fm1_edit_mod_scan(fm1_app_t *a) {
  if (a->edit) mod_take(a, a->edit->mod_known);
}

void fm1_edit_note_loaded(fm1_app_t *a) {
  fm1_edit_t *e = a->edit;
  fm1_change_t *c;
  if (!e) return;
  c = &e->ring[e->gen % FM1_EDIT_RING];
  memset(c, 0, sizeof *c);
  c->gen = ++e->gen;
  c->src = e->src;
  c->rec[0] = FM1_EDIT_LOADED;
  mod_take(a, 0);
}

void fm1_edit_attach(fm1_app_t *a, fm1_edit_t *e, int keep) {
  a->edit = e;
  if (!e) return;
  if (!keep) {
    memset(e, 0, sizeof *e);
    e->tele_at = ~(uint64_t)0;
  }
  e->src = FM1_EDIT_HOST;
  e->mod_known = 0;
  fm1_edit_note_loaded(a);
}

/* ---- packing -------------------------------------------------------------------- */

static void id_out(uint8_t *b, const char *id) {
  size_t n = strlen(id);
  if (n > 15) n = 15;
  memcpy(b, id, n);
}

int fm1_edit_pack(const fm1_rec_t *r, uint8_t out[FM1_EDIT_REC_BYTES]) {
  memset(out, 0, FM1_EDIT_REC_BYTES);
  out[0] = r->type;
  out[1] = r->role;
  out[2] = r->sound;
  out[3] = r->slot;
  switch (r->type) {
    case FM1_REC_PARAM:
      wr16(out + 4, r->u.param.uid);
      out[6] = r->u.param.focus;
      out[7] = r->u.param.vtype;
      wr32(out + 8, r->u.param.bits);
      return 1;
    case FM1_REC_UNIT:
    case FM1_REC_MODULE: id_out(out + 4, r->u.unit.id); return 1;
    case FM1_REC_ON: out[4] = r->u.on; return 1;
    case FM1_REC_LEVEL: wr32(out + 4, r->u.level); return 1;
    case FM1_REC_CABLE: {
      const fm1_mod_slot_t *s = &r->u.cable.s;
      out[4] = s->src;
      out[5] = s->via;
      out[6] = s->dst_unit;
      out[7] = s->flags;
      wr16(out + 8, s->dst);
      wr16(out + 10, (uint16_t)s->amount);
      wr16(out + 12, (uint16_t)s->offset);
      wr16(out + 14, s->uid);
      return 1;
    }
    default: return 0;
  }
}

void fm1_edit_verb_pack(const fm1_edit_verb_t *v, uint8_t out[FM1_EDIT_REC_BYTES]) {
  memset(out, 0, FM1_EDIT_REC_BYTES);
  out[0] = v->verb;
  if (v->verb == FM1_EDIT_VIEW) {
    out[4] = v->mode;
    wr16(out + 6, v->has);
    memcpy(out + 8, v->v, FM1_VIEW_KEYS);
    return;
  }
  out[1] = v->role[0];
  out[2] = v->sound[0];
  out[3] = v->slot[0];
  out[4] = v->role[1];
  out[5] = v->sound[1];
  out[6] = v->slot[1];
}

int fm1_edit_unpack(const uint8_t in[FM1_EDIT_REC_BYTES], fm1_rec_t *r, fm1_edit_verb_t *v) {
  const uint8_t type = in[0];
  if (type >= FM1_EDIT_SWAP && type <= FM1_EDIT_VIEW) {
    memset(v, 0, sizeof *v);
    v->verb = type;
    if (type == FM1_EDIT_VIEW) {
      v->mode = in[4];
      v->has = rd16(in + 6);
      memcpy(v->v, in + 8, FM1_VIEW_KEYS);
    } else {
      v->role[0] = in[1], v->sound[0] = in[2], v->slot[0] = in[3];
      v->role[1] = in[4], v->sound[1] = in[5], v->slot[1] = in[6];
    }
    return 2;
  }
  *r = blank(type);
  r->role = in[1];
  r->sound = in[2];
  r->slot = in[3];
  switch (type) {
    case FM1_REC_PARAM:
      r->u.param.uid = rd16(in + 4);
      r->u.param.focus = in[6];
      r->u.param.vtype = in[7];
      r->u.param.bits = rd32(in + 8);
      return 1;
    case FM1_REC_UNIT:
    case FM1_REC_MODULE:
      memcpy(r->u.unit.id, in + 4, 15);
      r->u.unit.id[15] = 0;
      return 1;
    case FM1_REC_ON: r->u.on = in[4]; return 1;
    case FM1_REC_LEVEL: r->u.level = rd32(in + 4); return 1;
    case FM1_REC_CABLE: {
      fm1_mod_slot_t *s = &r->u.cable.s;
      s->src = in[4];
      s->via = in[5];
      s->dst_unit = in[6];
      s->flags = in[7];
      s->dst = rd16(in + 8);
      s->amount = (int16_t)rd16(in + 10);
      s->offset = (int16_t)rd16(in + 12);
      s->uid = rd16(in + 14);
      return 1;
    }
    default: return 0;
  }
}

/* ---- applying ------------------------------------------------------------------- */

static int select_code(int r) {
  switch (r) {
    case 0: return 0;
    case FM1_APP_SELECT_ARENA: return FM1_REFUSE_ARENA;
    case FM1_APP_SELECT_RATE: return FM1_REFUSE_RATE;
    case FM1_APP_SELECT_RAM: return FM1_REFUSE_RAM;
    default: return FM1_REFUSE_BAD;
  }
}

/* A record's value for p: 1, or 0 for a bad one. */
static int rec_value(const fm1_param_t *p, const fm1_rec_t *r, float *v) {
  if (r->u.param.vtype == FM1_VAL_INDEX) {
    if (p->type != FM1_PARAM_ENUM || r->u.param.bits > (uint32_t)(p->max - p->min)) return 0;
    *v = p->min + (float)r->u.param.bits;
    return 1;
  }
  if (r->u.param.vtype != FM1_VAL_F32) return 0;
  *v = bitsf(r->u.param.bits);
  return isfinite(*v) ? 1 : 0;
}

static int apply_param(fm1_app_t *a, const fm1_rec_t *r) {
  const uint16_t uid = r->u.param.uid;
  float v;
  if (r->role == FM1_ROLE_MFX) {
    const fm1_engine_t *e = r->sound < FM1_APP_SOUNDS ? fm1_app_mfx_engine(a, r->sound) : NULL;
    const int idx = e ? fm1_param_index(e, uid) : -1;
    if (idx < 0 || r->slot != 0 || r->u.param.focus != FM1_FOCUS_NONE) return FM1_REFUSE_BAD;
    if (!rec_value(&e->params[idx], r, &v)) return FM1_REFUSE_BAD;
    fm1_app_arp_set_param(a, r->sound, idx, v);
    return 0;
  }
  if (r->role == FM1_ROLE_MODULE) {
    const int kind = a->mod && r->slot < FM1_MOD_POSITIONS ? fm1_mod_kind_at(a->mod, r->slot) : -1;
    const fm1_mod_kind_t *kd = kind >= 0 ? fm1_mod_kinds[kind] : NULL;
    int idx = -1;
    for (unsigned i = 0; kd && i < kd->n_params && idx < 0; ++i) {
      if (kd->params[i].uid == uid) idx = (int)i;
    }
    if (idx < 0 || r->u.param.focus != FM1_FOCUS_NONE) return FM1_REFUSE_BAD;
    if (!rec_value(&kd->params[idx], r, &v)) return FM1_REFUSE_BAD;
    return fm1_app_mod_edit_param(a, r->slot, (unsigned)idx, v) ? 0 : FM1_REFUSE_BAD;
  }
  {
    const int unit = unit_of(r->role, r->sound, r->slot);
    const fm1_engine_t *e = unit >= 0 ? a->unit[unit].e : NULL;
    const int idx = e ? fm1_param_index(e, uid) : -1;
    if (idx < 0 || idx >= FM1_APP_MAX_PARAMS || !rec_value(&e->params[idx], r, &v)) return FM1_REFUSE_BAD;
    if (r->u.param.focus != FM1_FOCUS_NONE) {
      /* A pad's own value (API v4): the focus moves to the pad for the
       * write and back, so the panel stays where it was. */
      const int f = fm1_engine_focus(e);
      float was;
      if (f < 0 || !(e->params[idx].flags & FM1_PARAM_PER_FOCUS) ||
          (float)r->u.param.focus > e->params[f].max - e->params[f].min) {
        return FM1_REFUSE_BAD;
      }
      was = a->unit[unit].value[f];
      fm1_app_set_param(a, unit, f, e->params[f].min + (float)r->u.param.focus);
      fm1_app_set_param(a, unit, idx, v);
      fm1_app_set_param(a, unit, f, was);
      return 0;
    }
    fm1_app_set_param(a, unit, idx, v);
    return 0;
  }
}

static int apply_unit(fm1_app_t *a, const fm1_rec_t *r) {
  const char *id = r->u.unit.id;
  if (r->role == FM1_ROLE_MFX) {
    if (r->sound >= FM1_APP_SOUNDS || r->slot != 0 || !id[0]) return FM1_REFUSE_BAD;
    if (!fm1_midi_fx_find(id)) return fm1_engine_find(id) ? FM1_REFUSE_BAD : FM1_REFUSE_UNKNOWN;
    return select_code(fm1_app_mfx_select(a, r->sound, id));
  }
  {
    const int unit = unit_of(r->role, r->sound, r->slot);
    int index;
    if (unit < 0) return FM1_REFUSE_BAD;
    if (!id[0]) return unit > 0 ? select_code(fm1_app_select(a, unit, -1)) : FM1_REFUSE_BAD;
    index = fm1_app_find(id);
    if (index < 0) return fm1_midi_fx_find(id) ? FM1_REFUSE_BAD : FM1_REFUSE_UNKNOWN;
    if (a->unit[unit].index == index) return 0;   /* as a picker left on its entry: no reload */
    return select_code(fm1_app_select(a, unit, index));
  }
}

static int apply_module(fm1_app_t *a, const fm1_rec_t *r) {
  unsigned pos = r->slot;
  int kind = -1;
  if (!a->mod || r->role != FM1_ROLE_MODULE) return FM1_REFUSE_BAD;
  if (r->u.unit.id[0]) {
    kind = fm1_mod_kind_find(r->u.unit.id);
    if (kind < 0 || strcmp(fm1_mod_kinds[kind]->id, r->u.unit.id) != 0) return FM1_REFUSE_UNKNOWN;
  }
  if (pos == FM1_EDIT_ANY) {
    for (pos = 0; pos < FM1_MOD_POSITIONS && fm1_mod_kind_at(a->mod, pos) >= 0; ++pos) {}
    if (pos == FM1_MOD_POSITIONS) return FM1_REFUSE_NO_ROOM;
  } else if (pos >= FM1_MOD_POSITIONS) {
    return FM1_REFUSE_BAD;
  }
  if (fm1_mod_kind_at(a->mod, pos) == kind) return 0;
  return fm1_app_mod_edit_kind(a, pos, kind) < 0 ? FM1_REFUSE_ARENA : 0;
}

static int apply_cable(fm1_app_t *a, const fm1_rec_t *r) {
  unsigned i = r->slot;
  if (!a->mod) return FM1_REFUSE_BAD;
  if (i == FM1_EDIT_ANY) {
    for (i = 0; i < FM1_MOD_SLOTS && !fm1_mod_ui_empty(&a->mui, a->mod, i); ++i) {}
    if (i == FM1_MOD_SLOTS) return FM1_REFUSE_NO_ROOM;
  } else if (i >= FM1_MOD_SLOTS) {
    return FM1_REFUSE_BAD;
  }
  if (!fm1_app_mod_edit_slot(a, i, &r->u.cable.s)) return FM1_REFUSE_BAD;
  /* Written; when it is on but the planner leaves it out, the panel's
   * MATRIX marks it so, and this says why. */
  return (r->u.cable.s.flags & FM1_MOD_SLOT_ON) ? (int)fm1_mod_slot_refusal(a->mod, i) : 0;
}

static int apply_one(fm1_app_t *a, const fm1_rec_t *r) {
  switch (r->type) {
    case FM1_REC_PARAM: return apply_param(a, r);
    case FM1_REC_UNIT: return apply_unit(a, r);
    case FM1_REC_ON:
      if (r->role != FM1_ROLE_MFX || r->sound >= FM1_APP_SOUNDS || r->slot != 0 || r->u.on > 1) return FM1_REFUSE_BAD;
      return select_code(fm1_app_arp_set_on(a, r->sound, r->u.on));
    case FM1_REC_LEVEL: {
      const float v = bitsf(r->u.level);
      if (r->sound >= FM1_APP_SOUNDS || !isfinite(v)) return FM1_REFUSE_BAD;
      fm1_app_unit_set_level(a, r->sound, v);
      return 0;
    }
    case FM1_REC_MODULE: return apply_module(a, r);
    case FM1_REC_CABLE: return apply_cable(a, r);
    default: return FM1_REFUSE_BAD;
  }
}

int fm1_edit_apply(fm1_app_t *a, const fm1_rec_t *r, uint32_t n, uint8_t src, uint16_t tag, int8_t *codes) {
  int applied = 0;
  const int was = fm1_edit_enter(a, src);
  if (a->edit) a->edit->tag = tag;
  if (n > FM1_EDIT_MAX_RECS) n = FM1_EDIT_MAX_RECS;
  for (uint32_t i = 0; i < n; ++i) {
    const int code = apply_one(a, &r[i]);
    if (codes) codes[i] = (int8_t)code;
    if (code == 0 || code >= 32) ++applied;
    if (a->edit) {
      if (code == 0 || code >= 32) ++a->edit->applied;
      else ++a->edit->refused;
    }
  }
  fm1_edit_leave(a, was);
  return applied;
}

static int verb_unit(const fm1_edit_verb_t *v, int k) { return unit_of(v->role[k], v->sound[k], v->slot[k]); }

int fm1_edit_verb(fm1_app_t *a, const fm1_edit_verb_t *v, uint8_t src, uint16_t tag) {
  int code = 0;
  const int was = fm1_edit_enter(a, src);
  if (a->edit) a->edit->tag = tag;
  switch (v->verb) {
    case FM1_EDIT_SWAP:
    case FM1_EDIT_MOVE:
      if (v->verb == FM1_EDIT_MOVE && v->role[0] == FM1_ROLE_MODULE && v->role[1] == FM1_ROLE_MODULE) {
        if (!a->mod || v->slot[0] >= FM1_MOD_POSITIONS || v->slot[1] >= FM1_MOD_POSITIONS) code = FM1_REFUSE_BAD;
        else if (v->slot[0] != v->slot[1] && !fm1_app_mod_edit_move(a, v->slot[0], v->slot[1])) code = FM1_REFUSE_BAD;
        break;
      }
      {
        const int ua = verb_unit(v, 0), ub = verb_unit(v, 1);
        if (!is_effect_unit(ua) || !is_effect_unit(ub) || ua == ub) code = FM1_REFUSE_BAD;
        else if (fm1_app_swap_units(a, ua, ub) != 0) code = FM1_REFUSE_BAD;
      }
      break;
    case FM1_EDIT_CURRENT:
      code = v->sound[0] < FM1_APP_SOUNDS && fm1_app_unit_set_current(a, v->sound[0]) == 0 ? 0 : FM1_REFUSE_BAD;
      break;
    case FM1_EDIT_VIEW:
      code = fm1_app_show(a, v->mode, v->has, v->v) == 0 ? 0 : FM1_REFUSE_BAD;
      break;
    default: code = FM1_REFUSE_BAD; break;
  }
  if (a->edit) {
    if (code) ++a->edit->refused;
    else ++a->edit->applied;
  }
  fm1_edit_leave(a, was);
  return code;
}

int fm1_edit_packed(fm1_app_t *a, const uint8_t *b, uint32_t n, uint8_t src, uint16_t tag, int8_t *codes) {
  int applied = 0;
  /* One source for the batch, so the safety scan of the modulation runs
   * once (each modulation edit is found as it is emitted anyway). */
  const int was = fm1_edit_enter(a, src);
  if (n > FM1_EDIT_MAX_RECS) n = FM1_EDIT_MAX_RECS;
  for (uint32_t i = 0; i < n; ++i) {
    fm1_rec_t r;
    fm1_edit_verb_t v;
    int8_t code;
    const int what = fm1_edit_unpack(b + (size_t)i * FM1_EDIT_REC_BYTES, &r, &v);
    if (what == 1) {
      applied += fm1_edit_apply(a, &r, 1, src, tag, &code);
    } else if (what == 2) {
      code = (int8_t)fm1_edit_verb(a, &v, src, tag);
      applied += code == 0;
    } else {
      code = FM1_REFUSE_BAD;
      if (a->edit) ++a->edit->refused;
    }
    if (codes) codes[i] = code;
  }
  fm1_edit_leave(a, was);
  return applied;
}

/* ---- telemetry ------------------------------------------------------------------ */

static int bit(const uint32_t *mask, unsigned k) { return (int)((mask[k / 32u] >> (k % 32u)) & 1u); }

static int section_on(const uint32_t *mask, unsigned s) {
  const fm1_tele_section_t *sec = fm1_tele_section(s);
  for (unsigned r = 0; sec && r < sec->rows; ++r) {
    if (bit(mask, sec->mask + r)) return 1;
  }
  return 0;
}

void fm1_edit_subscribe(fm1_app_t *a, const uint32_t *mask) {
  fm1_edit_t *e = a->edit;
  if (!e) return;
  for (unsigned k = 0; k < FM1_TELE_MASK_WORDS; ++k) e->mask[k] = mask ? mask[k] : 0u;
  if (fm1_tele_mask_bits() % 32u) e->mask[fm1_tele_mask_bits() / 32u] &= (1u << (fm1_tele_mask_bits() % 32u)) - 1u;
  e->meters_on = (uint8_t)section_on(e->mask, FM1_TELE_METERS);
  e->outs_on = (uint8_t)section_on(e->mask, FM1_TELE_OUTS);
  for (unsigned p = 0; p < FM1_TELE_POINTS; ++p) e->peak[p] = e->sq[p] = 0.0f, e->n[p] = 0;
  e->out_seen = 0;
}

void fm1_edit_meter(fm1_app_t *a, unsigned point, const float *lr, uint32_t n) {
  fm1_edit_t *e = a->edit;
  float peak, sq = 0.0f;
  if (!e || !e->meters_on || point >= FM1_TELE_POINTS) return;
  peak = e->peak[point];
  for (uint32_t i = 0; i < 2u * n; ++i) {
    const float x = fabsf(lr[i]);
    if (x > peak) peak = x;
    sq += lr[i] * lr[i];
  }
  e->peak[point] = peak;
  e->sq[point] += sq;
  e->n[point] += 2u * n;
}

void fm1_edit_block_end(fm1_app_t *a) {
  fm1_edit_t *e = a->edit;
  if (!e) return;
  e->gen_rendered = e->gen;
  if (!e->outs_on || !a->mod) return;
  for (unsigned pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    if (fm1_mod_kind_at(a->mod, pos) < 0) continue;
    for (unsigned port = 0; port < 8u; ++port) {
      const float v = fm1_mod_out(a->mod, pos, port);
      if (!((e->out_seen >> pos) & 1u) || v < e->omin[pos][port]) e->omin[pos][port] = v;
      if (!((e->out_seen >> pos) & 1u) || v > e->omax[pos][port]) e->omax[pos][port] = v;
    }
    e->out_seen = (uint8_t)(e->out_seen | (1u << pos));
  }
}

static float reduction(fm1_app_t *a, unsigned r) {
  int unit = -1;
  if (r < FM1_TELE_SOUNDS * FM1_TELE_INSERTS) {
    unit = fm1_app_insert_unit((int)(r / FM1_TELE_INSERTS), (int)(r % FM1_TELE_INSERTS));
  } else if (r < FM1_TELE_SOUNDS * FM1_TELE_INSERTS + FM1_TELE_MASTERS) {
    unit = 1 + (int)(r - FM1_TELE_SOUNDS * FM1_TELE_INSERTS);
  } else {                              /* the output limiter */
    const fm1_mix_limiter_t *l = &a->limiter;
    return l->envelope > l->ceiling ? 20.0f * log10f(l->envelope / l->ceiling) : 0.0f;
  }
  /* Comp says what it took (fm1_comp.h); Limiter and Squash have no such
   * read-out yet, and every other effect reduces nothing. */
  if (a->unit[unit].e && strcmp(a->unit[unit].e->id, "comp") == 0) return fm1_comp_reduction_db(a->unit[unit].self);
  return 0.0f;
}

/* Slot i's destination now: a sink's value as sent, a module parameter's
 * effective value; NaN when the slot does not run or reaches a gate. */
static float dest_value(fm1_app_t *a, unsigned i) {
  fm1_mod_slot_t s;
  fm1_mod_sink_info_t info;
  /* Only as the last block ran it: reading sinks builds a pending plan,
   * which must wait for the next tick, as fm1-render's does. */
  if (!a->mod || a->edit->gen != a->edit->gen_rendered || !((a->mui.plan.active >> i) & 1u)) return NAN;
  fm1_mod_get_slot(a->mod, i, &s);
  if (s.flags & (FM1_MOD_SLOT_GATE_DST | FM1_MOD_SLOT_VOICE)) return NAN;
  if (s.dst_unit >= FM1_MOD_MODULE && s.dst_unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS) {
    const unsigned pos = s.dst_unit - FM1_MOD_MODULE;
    const int kind = fm1_mod_kind_at(a->mod, pos);
    for (unsigned k = 0; kind >= 0 && k < fm1_mod_kinds[kind]->n_params; ++k) {
      if (fm1_mod_kinds[kind]->params[k].uid == s.dst) return fm1_mod_param(a->mod, pos, k);
    }
    return NAN;
  }
  for (unsigned k = 0; fm1_mod_sink(a->mod, k, &info); ++k) {
    if (info.uid == s.dst && fm1_mod_sink_index(info.unit) == fm1_mod_sink_index(s.dst_unit)) return info.value;
  }
  return NAN;
}

static void fill_row(fm1_app_t *a, unsigned s, unsigned r, float *o) {
  fm1_edit_t *e = a->edit;
  const fm1_tele_section_t *sec = fm1_tele_section(s);
  const unsigned items = sec->items, fields = sec->fields;
  switch (s) {
    case FM1_TELE_METERS:
      o[0] = e->peak[r];
      o[1] = e->n[r] ? sqrtf(e->sq[r] / (float)e->n[r]) : 0.0f;
      e->peak[r] = e->sq[r] = 0.0f;
      e->n[r] = 0;
      break;
    case FM1_TELE_REDUCTION: o[0] = reduction(a, r); break;
    case FM1_TELE_VOICES: {
      fm1_mod_voice_info_t vi;
      if (a->mod && fm1_mod_voice(a->mod, r, &vi)) o[0] = (float)(vi.sound + 1), o[1] = (float)vi.key;
      else o[0] = o[1] = 0.0f;
      break;
    }
    case FM1_TELE_OUTS:
      for (unsigned port = 0; port < items; ++port) {
        const int on = a->mod && fm1_mod_kind_at(a->mod, r) >= 0;
        const float v = on ? fm1_mod_out(a->mod, r, port) : 0.0f;
        const int seen = on && ((e->out_seen >> r) & 1u);
        o[port * fields + 0] = v;
        o[port * fields + 1] = seen && e->omin[r][port] < v ? e->omin[r][port] : v;
        o[port * fields + 2] = seen && e->omax[r][port] > v ? e->omax[r][port] : v;
      }
      e->out_seen = (uint8_t)(e->out_seen & ~(1u << r));
      break;
    case FM1_TELE_VOICE_OUTS:
      for (unsigned port = 0; port < items; ++port) {
        for (unsigned v = 0; v < fields; ++v) o[port * fields + v] = a->mod ? fm1_mod_voice_out(a->mod, v, r, port) : 0.0f;
      }
      break;
    case FM1_TELE_DESTS: o[0] = dest_value(a, r); break;
    default:
      /* voice_dests: the runtime keeps each voice's offsets but has no
       * read-out for them yet (a later stage), so the rows say "none". */
      for (unsigned f = 0; f < items * fields; ++f) o[f] = NAN;
      break;
  }
}

uint32_t fm1_edit_telemetry(fm1_app_t *a, float *out, uint32_t max) {
  fm1_edit_t *e = a->edit;
  const uint32_t nf = fm1_tele_floats();
  uint64_t gap;
  int any = 0;
  if (!e || !out || max < nf) return 0;
  for (unsigned k = 0; k < FM1_TELE_MASK_WORDS; ++k) any |= e->mask[k] != 0u;
  if (!any) return 0;
  gap = (uint64_t)ceilf(a->host.sample_rate / (float)FM1_TELE_HZ);
  if (e->tele_at != ~(uint64_t)0 && a->frames - e->tele_at < gap) return 0;
  e->tele_at = a->frames;
  for (unsigned s = 0; s < FM1_TELE_SECTIONS; ++s) {
    const fm1_tele_section_t *sec = fm1_tele_section(s);
    for (unsigned r = 0; r < sec->rows; ++r) {
      if (bit(e->mask, sec->mask + r)) fill_row(a, s, r, out + sec->offset + (size_t)r * sec->items * sec->fields);
    }
  }
  return nf;
}

/* ---- the view ------------------------------------------------------------------- */

void fm1_edit_view(const fm1_app_t *a, fm1_view_t *v) {
  int kind[4], unit[4], index[4];
  memset(v, 0, sizeof *v);
  v->sound = (uint8_t)a->sound;
  switch (a->mode) {
    case FM1_MODE_FX: v->mode = FM1_VIEW_FX, v->page = (uint8_t)a->fx_page, v->slot = (uint8_t)a->fx_slot; break;
    case FM1_MODE_GLOBAL: v->mode = FM1_VIEW_GLO, v->page = (uint8_t)a->glo_page; break;
    case FM1_MODE_SEQ: v->mode = FM1_VIEW_SEQ, v->page = (uint8_t)a->page; break;
    case FM1_MODE_RACK: v->mode = FM1_VIEW_RACK, v->page = a->mui.page, v->slot = a->mui.pos; break;
    case FM1_MODE_MATRIX: v->mode = FM1_VIEW_MATRIX, v->slot = a->mui.slot; break;
    case FM1_MODE_CHAIN: v->mode = FM1_VIEW_CHAIN; break;
    case FM1_MODE_ARP: v->mode = FM1_VIEW_HOME, v->arp = 1, v->page = (uint8_t)a->arp_page; break;
    default: v->mode = FM1_VIEW_HOME, v->page = (uint8_t)a->page; break;
  }
  fm1_app_knobs(a, kind, unit, index);
  for (int k = 0; k < 4; ++k) {
    fm1_view_knob_t *kn = &v->knob[k];
    switch (kind[k]) {
      case 1:
        kn->kind = 1;
        where(unit[k], &kn->role, &kn->sound, &kn->slot);
        kn->uid = a->unit[unit[k]].e->params[index[k]].uid;
        break;
      case 2: kn->kind = 2, kn->sound = (uint8_t)unit[k]; break;
      case 3:
        kn->kind = 1, kn->role = FM1_ROLE_MFX, kn->sound = (uint8_t)unit[k];
        kn->uid = fm1_app_mfx_engine(a, unit[k])->params[index[k]].uid;
        break;
      case 4: {
        const fm1_mod_kind_t *kd = fm1_mod_kinds[fm1_mod_kind_at(a->mod, (unsigned)unit[k])];
        kn->kind = 1, kn->role = FM1_ROLE_MODULE, kn->slot = (uint8_t)unit[k];
        kn->uid = kd->params[index[k]].uid;
        break;
      }
      default: break;
    }
  }
}

void fm1_edit_view_pack(const fm1_view_t *v, uint8_t out[FM1_EDIT_VIEW_BYTES]) {
  memset(out, 0, FM1_EDIT_VIEW_BYTES);
  out[0] = v->mode, out[1] = v->sound, out[2] = v->page, out[3] = v->slot, out[4] = v->arp;
  for (int k = 0; k < 4; ++k) {
    uint8_t *b = out + 8 + 8 * k;
    b[0] = v->knob[k].kind, b[1] = v->knob[k].role, b[2] = v->knob[k].sound, b[3] = v->knob[k].slot;
    wr16(b + 4, v->knob[k].uid);
  }
}

/* ---- text ----------------------------------------------------------------------- */

static const char *const kRoles[] = { "none", "sound", "insert", "master", "mfx", "module" };
static const char *const kModes[FM1_VIEW_MODES] = { "home", "fx", "glo", "seq", "session", "song",
                                                    "rack", "matrix", "chain" };
static const char *const kKeys[FM1_VIEW_KEYS] = { "sound", "page", "unit", "track", "bar", "panel",
                                                  "pos", "slot", "entry" };

static int word_index(const char *w, const char *const *list, int n) {
  for (int i = 0; i < n; ++i) {
    if (strcmp(w, list[i]) == 0) return i;
  }
  return -1;
}

/* Up to 12 whitespace-separated words of a line, in place. */
static int split(char *s, char **w, int cap) {
  int n = 0;
  while (*s && n < cap) {
    while (*s == ' ' || *s == '\t' || *s == '\r' || *s == '\n') *s++ = 0;
    if (!*s || *s == '#') break;
    w[n++] = s;
    while (*s && *s != ' ' && *s != '\t' && *s != '\r' && *s != '\n') ++s;
  }
  if (*s == '#') *s = 0;
  return n;
}

static int num(const char *s, long lo, long hi, long *out) {
  char *end;
  long v;
  if (strcmp(s, "any") == 0) { *out = FM1_EDIT_ANY; return 1; }
  v = strtol(s, &end, 0);
  if (end == s || *end || v < lo || v > hi) return 0;
  *out = v;
  return 1;
}

int fm1_edit_parse_text(const char *line, uint8_t out[FM1_EDIT_REC_BYTES]) {
  char buf[200], *w[14];
  long x[12];
  int n, role;
  fm1_rec_t r;
  fm1_edit_verb_t v;
  if (!line || strlen(line) >= sizeof buf) return 0;
  strcpy(buf, line);
  n = split(buf, w, 14);
  if (n < 1) return 0;
  memset(&v, 0, sizeof v);
  if (strcmp(w[0], "swap") == 0 || strcmp(w[0], "move") == 0) {
    if (n != 7) return 0;
    v.verb = w[0][0] == 's' ? FM1_EDIT_SWAP : FM1_EDIT_MOVE;
    for (int k = 0; k < 2; ++k) {
      role = word_index(w[1 + 3 * k], kRoles, 6);
      if (role < 0 || !num(w[2 + 3 * k], 0, 255, &x[0]) || !num(w[3 + 3 * k], 0, 255, &x[1])) return 0;
      v.role[k] = (uint8_t)role, v.sound[k] = (uint8_t)x[0], v.slot[k] = (uint8_t)x[1];
    }
    fm1_edit_verb_pack(&v, out);
    return 1;
  }
  if (strcmp(w[0], "current") == 0) {
    if (n != 2 || !num(w[1], 0, 255, &x[0])) return 0;
    v.verb = FM1_EDIT_CURRENT, v.sound[0] = (uint8_t)x[0];
    fm1_edit_verb_pack(&v, out);
    return 1;
  }
  if (strcmp(w[0], "view") == 0) {
    int mode;
    if (n < 2 || (mode = word_index(w[1], kModes, FM1_VIEW_MODES)) < 0) return 0;
    v.verb = FM1_EDIT_VIEW, v.mode = (uint8_t)mode;
    for (int k = 2; k < n; ++k) {
      char *eq = strchr(w[k], '=');
      int key;
      if (!eq) return 0;
      *eq = 0;
      if ((key = word_index(w[k], kKeys, FM1_VIEW_KEYS)) < 0 || !num(eq + 1, 0, 255, &x[0])) return 0;
      v.v[key] = (uint8_t)x[0];
      v.has = (uint16_t)(v.has | (1u << key));
    }
    fm1_edit_verb_pack(&v, out);
    return 1;
  }
  r = blank(0);
  if (strcmp(w[0], "param") == 0) {
    float f;
    char *end;
    if (n < 6 || (role = word_index(w[1], kRoles, 6)) < 0 || !num(w[2], 0, 255, &x[0]) ||
        !num(w[3], 0, 255, &x[1]) || !num(w[4], 0, 65535, &x[2])) {
      return 0;
    }
    r.type = FM1_REC_PARAM, r.role = (uint8_t)role, r.sound = (uint8_t)x[0], r.slot = (uint8_t)x[1];
    r.u.param.uid = (uint16_t)x[2];
    r.u.param.focus = FM1_FOCUS_NONE;
    r.u.param.vtype = FM1_VAL_F32;
    if (strcmp(w[5], "nan") == 0) f = NAN;
    else if ((f = strtof(w[5], &end)), end == w[5] || *end) return 0;
    r.u.param.bits = fbits(f);
    for (int k = 6; k < n; ++k) {
      if (strcmp(w[k], "index") == 0) {
        r.u.param.vtype = FM1_VAL_INDEX;
        r.u.param.bits = (uint32_t)(f < 0.0f ? 0xFFFFFFFFu : (uint32_t)f);
      } else if (strncmp(w[k], "focus=", 6) == 0 && num(w[k] + 6, 0, 255, &x[3])) {
        r.u.param.focus = (uint8_t)x[3];
      } else {
        return 0;
      }
    }
  } else if (strcmp(w[0], "unit") == 0) {
    if (n != 5 || (role = word_index(w[1], kRoles, 6)) < 0 || !num(w[2], 0, 255, &x[0]) ||
        !num(w[3], 0, 255, &x[1]) || strlen(w[4]) > 15) {
      return 0;
    }
    r.type = FM1_REC_UNIT, r.role = (uint8_t)role, r.sound = (uint8_t)x[0], r.slot = (uint8_t)x[1];
    if (strcmp(w[4], "-") != 0) strcpy(r.u.unit.id, w[4]);
  } else if (strcmp(w[0], "on") == 0) {
    if (n != 3 || !num(w[1], 0, 255, &x[0]) || !num(w[2], 0, 255, &x[1])) return 0;
    r.type = FM1_REC_ON, r.role = FM1_ROLE_MFX, r.sound = (uint8_t)x[0], r.u.on = (uint8_t)x[1];
  } else if (strcmp(w[0], "level") == 0) {
    char *end;
    float f;
    if (n != 3 || !num(w[1], 0, 255, &x[0])) return 0;
    f = strtof(w[2], &end);
    if (end == w[2] || *end) return 0;
    r.type = FM1_REC_LEVEL, r.sound = (uint8_t)x[0], r.u.level = fbits(f);
  } else if (strcmp(w[0], "module") == 0) {
    if (n != 3 || !num(w[1], 0, 255, &x[0]) || strlen(w[2]) > 15) return 0;
    r.type = FM1_REC_MODULE, r.role = FM1_ROLE_MODULE, r.slot = (uint8_t)x[0];
    if (strcmp(w[2], "-") != 0) strcpy(r.u.unit.id, w[2]);
  } else if (strcmp(w[0], "cable") == 0) {
    static const long kLo[8] = { 0, 0, 0, 0, 0, -32768, -32768, 0 };
    static const long kHi[8] = { 255, 255, 255, 255, 65535, 32767, 32767, 65535 };
    if ((n != 9 && n != 10) || !num(w[1], 0, 255, &x[0])) return 0;
    for (int k = 0; k < n - 2; ++k) {
      if (strcmp(w[2 + k], "any") == 0 || !num(w[2 + k], kLo[k], kHi[k], &x[1 + k])) return 0;
    }
    r.type = FM1_REC_CABLE, r.slot = (uint8_t)x[0];
    r.u.cable.s.src = (uint8_t)x[1], r.u.cable.s.via = (uint8_t)x[2];
    r.u.cable.s.dst_unit = (uint8_t)x[3], r.u.cable.s.flags = (uint8_t)x[4];
    r.u.cable.s.dst = (uint16_t)x[5], r.u.cable.s.amount = (int16_t)x[6];
    r.u.cable.s.offset = (int16_t)x[7], r.u.cable.s.uid = (uint16_t)(n == 10 ? x[8] : 0);
  } else {
    return 0;
  }
  return fm1_edit_pack(&r, out);
}

void fm1_edit_rec_text(const uint8_t b[FM1_EDIT_REC_BYTES], char *buf, size_t cap) {
  fm1_rec_t r;
  fm1_edit_verb_t v;
  const int what = fm1_edit_unpack(b, &r, &v);
  const char *role = r.role < 6 ? kRoles[r.role] : "?";
  if (!cap) return;
  buf[0] = 0;
  if (b[0] == FM1_EDIT_LOADED) {
    snprintf(buf, cap, "loaded");
  } else if (what == 2) {
    if (v.verb == FM1_EDIT_CURRENT) {
      snprintf(buf, cap, "current %u", v.sound[0]);
    } else if (v.verb == FM1_EDIT_VIEW) {
      snprintf(buf, cap, "view %s has=%u", v.mode < FM1_VIEW_MODES ? kModes[v.mode] : "?", v.has);
    } else {
      snprintf(buf, cap, "%s %s %u %u %s %u %u", v.verb == FM1_EDIT_SWAP ? "swap" : "move",
               v.role[0] < 6 ? kRoles[v.role[0]] : "?", v.sound[0], v.slot[0],
               v.role[1] < 6 ? kRoles[v.role[1]] : "?", v.sound[1], v.slot[1]);
    }
  } else if (what == 1) {
    switch (r.type) {
      case FM1_REC_PARAM:
        snprintf(buf, cap, "param %s %u %u %u %.9g%s", role, r.sound, r.slot, r.u.param.uid,
                 r.u.param.vtype == FM1_VAL_INDEX ? (double)r.u.param.bits : (double)bitsf(r.u.param.bits),
                 r.u.param.vtype == FM1_VAL_INDEX ? " index" : "");
        break;
      case FM1_REC_UNIT: snprintf(buf, cap, "unit %s %u %u %s", role, r.sound, r.slot, r.u.unit.id[0] ? r.u.unit.id : "-"); break;
      case FM1_REC_MODULE: snprintf(buf, cap, "module %u %s", r.slot, r.u.unit.id[0] ? r.u.unit.id : "-"); break;
      case FM1_REC_ON: snprintf(buf, cap, "on %u %u", r.sound, r.u.on); break;
      case FM1_REC_LEVEL: snprintf(buf, cap, "level %u %.9g", r.sound, (double)bitsf(r.u.level)); break;
      case FM1_REC_CABLE:
        snprintf(buf, cap, "cable %u %u %u %u %u %u %d %d %u", r.slot, r.u.cable.s.src, r.u.cable.s.via,
                 r.u.cable.s.dst_unit, r.u.cable.s.flags, r.u.cable.s.dst, r.u.cable.s.amount,
                 r.u.cable.s.offset, r.u.cable.s.uid);
        break;
      default: break;
    }
  } else {
    snprintf(buf, cap, "type %u", b[0]);
  }
}

/* ---- the dump and the hash -------------------------------------------------------- */

static void hash_put(void *ctx, const char *b, size_t n) {
  uint32_t *crc = (uint32_t *)ctx;
  *crc = fm1_state_crc32(*crc, (const uint8_t *)b, n);
}

uint32_t fm1_edit_state_hash(fm1_app_t *a) {
  uint32_t crc = 0;
  fm1_state_report_t rep;
  if (!fm1_app_state_save(a, FM1_STATE_PROJECT, 0, 2, hash_put, &crc, &rep)) return 0;
  return crc;
}

size_t fm1_edit_dump(fm1_app_t *a, char *buf, size_t cap) {
  size_t n = 0;
  fm1_view_t v;
  char line[160];
  const fm1_edit_t *e = a->edit;
#define PUT(...) do { int k_ = snprintf(buf + n, n < cap ? cap - n : 0, __VA_ARGS__); \
                      if (k_ > 0) n += (size_t)k_; } while (0)
  if (!cap) return 0;
  buf[0] = 0;
  if (e) {
    const uint32_t first = e->gen > FM1_EDIT_RING ? e->gen - FM1_EDIT_RING + 1u : 1u;
    PUT("gen %u applied %u refused %u\n", e->gen, e->applied, e->refused);
    for (uint32_t g = first; g <= e->gen && g; ++g) {
      const fm1_change_t *c = &e->ring[(g - 1) % FM1_EDIT_RING];
      fm1_edit_rec_text(c->rec, line, sizeof line);
      PUT("%u src=%u tag=%u %s\n", c->gen, c->src, c->tag, line);
    }
  }
  fm1_edit_view(a, &v);
  PUT("view mode=%u sound=%u page=%u slot=%u arp=%u", v.mode, v.sound, v.page, v.slot, v.arp);
  for (int k = 0; k < 4; ++k) PUT(" k%d=%u/%u/%u/%u/%u", k + 1, v.knob[k].kind, v.knob[k].role, v.knob[k].sound,
                                  v.knob[k].slot, v.knob[k].uid);
  PUT("\nhash %08x\n", (unsigned)fm1_edit_state_hash(a));
#undef PUT
  return n < cap ? n : cap - 1;
}
