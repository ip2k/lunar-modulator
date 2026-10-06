/* state_mod.c -- the modulation records and the runtime (fm1_mod.h): one
 * applier and one collector (notes/2026-10-06-state-files.md §6, "The mod
 * records have one applier"), for fm1-render's --load and --save now and
 * the app's state stage (A1) next. C99, no heap, no stdio. MIT licence.
 *
 * Pattern data (FM1_REC_DATA) reaches a kind's set_data through mod API
 * v2's fm1_mod_set_data, and leaves through fm1_mod_get_data. SEAM(A1):
 * the mod script parser produces these records too, so --mod, the replay
 * log and a file reach fm1_mod_set_slot through this one function. */
#include "fm1_state_mod.h"

#include <string.h>

void fm1_state_mod_init(fm1_state_mod_t *a, fm1_mod_t *m, const fm1_state_names_t *nm,
                        const fm1_engine_t *const units[FM1_MOD_SINKS], fm1_state_report_t *rep) {
  memset(a, 0, sizeof(*a));
  a->m = m;
  a->nm = nm;
  if (units) memcpy(a->units, units, sizeof(a->units));
  a->rep = rep;
}

static void skip(fm1_state_mod_t *a, const char *what) {
  if (a->rep && !a->rep->skipped++) {
    size_t n = strlen(what);
    if (n >= sizeof(a->rep->first_skip)) n = sizeof(a->rep->first_skip) - 1u;
    memcpy(a->rep->first_skip, what, n);
    a->rep->first_skip[n] = '\0';
  }
}

/* The parameters a cable unit code reaches: an engine bound at a sink, a
 * module's kind, or the host. */
static const fm1_param_t *unit_params(const fm1_state_mod_t *a, unsigned code, unsigned *n,
                                      unsigned *owner_kind, const char **owner) {
  *owner_kind = 0;
  *owner = NULL;
  if (code >= FM1_MOD_MODULE && code < FM1_MOD_MODULE + FM1_MOD_POSITIONS) {
    const int k = fm1_mod_kind_at(a->m, code - FM1_MOD_MODULE);
    if (k < 0) return NULL;
    *n = fm1_mod_kinds[k]->n_params;
    *owner_kind = FM1_ALIAS_MOD;
    *owner = fm1_mod_kinds[k]->id;
    return fm1_mod_kinds[k]->params;
  }
  if (code == FM1_MOD_HOST) {
    *n = FM1_MOD_HOST_PARAMS;
    return fm1_mod_host_params;
  }
  {
    const int si = fm1_mod_sink_index(code);
    const fm1_engine_t *e = si >= 0 ? a->units[si] : NULL;
    if (!e) return NULL;
    *n = e->n_params;
    *owner_kind = FM1_ALIAS_ENGINE;
    *owner = e->id;
    return e->params;
  }
}

int fm1_state_mod_sink(void *ctx, const fm1_rec_t *r) {
  fm1_state_mod_t *a = (fm1_state_mod_t *)ctx;
  switch (r->type) {
    case FM1_REC_SEED:
      a->seed = r->u.seed;
      a->has_seed = 1;
      return 1;
    case FM1_REC_MODULE: {
      const int k = fm1_mod_kind_find(r->u.unit.id);
      if (k < 0 || strcmp(fm1_mod_kinds[k]->id, r->u.unit.id) != 0) {
        skip(a, "a modulation kind this build does not have");
        return 1;
      }
      if (fm1_mod_set_kind(a->m, r->slot, k) < 0) skip(a, "a module the rack refused");
      return 1;
    }
    case FM1_REC_PARAM: {
      int k;
      unsigned i;
      if (r->role != FM1_ROLE_MODULE) return 1;
      k = fm1_mod_kind_at(a->m, r->slot);
      if (k < 0) return 1;
      for (i = 0; i < fm1_mod_kinds[k]->n_params; ++i) {
        if (fm1_mod_kinds[k]->params[i].uid == r->u.param.uid) {
          const float v = r->u.param.vtype == FM1_VAL_INDEX
                              ? fm1_mod_kinds[k]->params[i].min + (float)r->u.param.bits
                              : 0.0f;
          float f;
          memcpy(&f, &r->u.param.bits, sizeof(f));
          fm1_mod_set_param(a->m, r->slot, i, r->u.param.vtype == FM1_VAL_INDEX ? v : f);
          return 1;
        }
      }
      skip(a, "a module parameter this build does not have");
      return 1;
    }
    case FM1_REC_DATA:
      if (r->piece & FM1_REC_FIRST) {
        a->data_pos = r->slot;
        a->data_version = r->u.data.version;
        a->data_n = 0;
        a->data_over = 0;
      }
      if (r->u.data.n > FM1_MOD_DATA_MAX - a->data_n) {
        a->data_over = 1;
      } else if (r->u.data.n) {
        memcpy(a->data + a->data_n, r->u.data.b, r->u.data.n);
        a->data_n = (uint16_t)(a->data_n + r->u.data.n);
      }
      if (r->piece & FM1_REC_LAST) {
        if (a->data_over) skip(a, "pattern data longer than any kind keeps");
        else if (!fm1_mod_set_data(a->m, a->data_pos, a->data, a->data_n, a->data_version))
          skip(a, "pattern data its module does not take");
      }
      return 1;
    case FM1_REC_CABLE: {
      fm1_mod_slot_t s = r->u.cable.s;
      if (!s.dst && r->u.cable.name[0] && !(s.flags & FM1_MOD_SLOT_GATE_DST)) {
        unsigned n = 0, ok_kind;
        const char *owner;
        const fm1_param_t *p = unit_params(a, s.dst_unit, &n, &ok_kind, &owner);
        const int i = p ? fm1_state_param_find(a->nm, ok_kind, owner, p, n, r->u.cable.name, strlen(r->u.cable.name))
                        : -1;
        if (i < 0) {
          skip(a, "a cable to a parameter its unit does not have");
          return 1;
        }
        s.dst = p[i].uid;
      }
      fm1_mod_set_slot(a->m, r->slot, &s);
      return 1;
    }
    default:
      return 1;
  }
}

static int emit(fm1_rec_sink_t sink, void *ctx, fm1_rec_t *r) { return sink(ctx, r); }

int fm1_state_mod_collect(const fm1_mod_t *m, uint32_t seed, int with_seed, fm1_rec_sink_t sink, void *ctx) {
  fm1_rec_t r;
  unsigned pos, i;
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_MOD;
  if (!emit(sink, ctx, &r)) return 0;
  if (with_seed) {
    r.type = FM1_REC_SEED;
    r.u.seed = seed;
    if (!emit(sink, ctx, &r)) return 0;
  }
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const int k = fm1_mod_kind_at(m, pos);
    const fm1_mod_kind_t *kd;
    if (k < 0) continue;
    kd = fm1_mod_kinds[k];
    memset(&r, 0, sizeof(r));
    r.type = FM1_REC_MODULE;
    r.role = FM1_ROLE_MODULE;
    r.slot = (uint8_t)pos;
    strncpy(r.u.unit.id, kd->id, sizeof(r.u.unit.id) - 1u);
    if (!emit(sink, ctx, &r)) return 0;
    for (i = 0; i < kd->n_params; ++i) {
      const fm1_param_t *p = &kd->params[i];
      float v = fm1_mod_param_base(m, pos, i);
      memset(&r, 0, sizeof(r));
      r.type = FM1_REC_PARAM;
      r.role = FM1_ROLE_MODULE;
      r.slot = (uint8_t)pos;
      r.u.param.uid = p->uid;
      r.u.param.focus = FM1_FOCUS_NONE;
      if (p->type == FM1_PARAM_ENUM) {
        const float idx = v - p->min;
        r.u.param.vtype = FM1_VAL_INDEX;
        r.u.param.bits = idx > 0.0f ? (uint32_t)(idx + 0.5f) : 0u;
      } else {
        if (v == 0.0f) v = 0.0f;
        r.u.param.vtype = FM1_VAL_F32;
        memcpy(&r.u.param.bits, &v, sizeof(v));
      }
      if (!emit(sink, ctx, &r)) return 0;
    }
    {
      uint8_t buf[FM1_MOD_DATA_MAX], version = 0;
      const uint16_t n = fm1_mod_get_data(m, pos, buf, (uint16_t)sizeof(buf), &version);
      if (n) {
        memset(&r, 0, sizeof(r));
        r.type = FM1_REC_DATA;
        r.slot = (uint8_t)pos;
        r.piece = FM1_REC_FIRST | FM1_REC_LAST;
        r.u.data.version = version;
        r.u.data.n = n;
        r.u.data.b = buf;
        if (!emit(sink, ctx, &r)) return 0;
      }
    }
  }
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t s;
    if (!fm1_mod_get_slot(m, i, &s)) continue;
    if (!s.dst && !(s.flags & FM1_MOD_SLOT_GATE_DST)) continue;       /* empty */
    memset(&r, 0, sizeof(r));
    r.type = FM1_REC_CABLE;
    r.slot = (uint8_t)i;
    r.u.cable.s = s;
    if (!emit(sink, ctx, &r)) return 0;
  }
  return 1;
}
