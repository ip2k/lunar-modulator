#include "project_mod.h"
#include "fm1_state_mod.h"
#include <string.h>

typedef struct {
    const uint8_t *bytes;
    uint32_t size, seed;
    const lunar_project_units_t *plan;
    float focus[LUNAR_PROJECT_UNITS];
    fm1_mod_t *mod;
} mod_load_t;

static uint32_t read_bytes(void *ctx, uint32_t off, uint8_t *buf, uint32_t n) {
    mod_load_t *load = (mod_load_t *)ctx;
    if (off > load->size || n > load->size - off) return 0;
    memcpy(buf, load->bytes + off, n);
    return n;
}

static float parameter_value(const fm1_rec_t *r, const fm1_param_t *p) {
    float value;
    if (r->u.param.vtype == FM1_VAL_INDEX) return p->min + (float)r->u.param.bits;
    memcpy(&value, &r->u.param.bits, sizeof value);
    return value;
}

static int seed_record(void *ctx, const fm1_rec_t *r) {
    mod_load_t *load = (mod_load_t *)ctx;
    if (r->type == FM1_REC_SEED) load->seed = r->u.seed;
    if (r->type == FM1_REC_PARAM && r->role != FM1_ROLE_MODULE) {
        int unit = lunar_project_unit_index(r);
        const fm1_engine_t *e = unit >= 0 ? load->plan->engine[unit] : NULL;
        int focus = e ? fm1_engine_focus(e) : -1;
        if (focus >= 0 && e->params[focus].uid == r->u.param.uid)
            load->focus[unit] = parameter_value(r, &e->params[focus]);
    }
    return 1;
}

static int refuse(fm1_state_report_t *report, unsigned code, const char *why) {
    report->code = (uint8_t)code;
    strncpy(report->what, why, sizeof report->what - 1u);
    report->what[sizeof report->what - 1u] = 0;
    return 0;
}

static int disjoint(const void *a, size_t an, const void *b, size_t bn) {
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    if (an > UINTPTR_MAX - x || bn > UINTPTR_MAX - y) return 0;
    return x + an <= y || y + bn <= x;
}

static const fm1_engine_t *sink_engine(const lunar_project_units_t *plan, unsigned code) {
    int sound = fm1_mod_unit_sound(code);
    if (sound >= 0) return plan->engine[sound];
    if (code == FM1_MOD_FX1 || code == FM1_MOD_FX2)
        return plan->engine[12u + code - FM1_MOD_FX1];
    if (code >= FM1_MOD_INSERT && code < FM1_MOD_INSERT + 16u) {
        unsigned offset = code - FM1_MOD_INSERT;
        if (offset % 4u < 2u) return plan->engine[4u + (offset / 4u) * 2u + offset % 4u];
    }
    return NULL;
}

/* The engine owns all pads; modulation exposes the final current pad only. */
static int base_record(void *ctx, const fm1_rec_t *r) {
    mod_load_t *load = (mod_load_t *)ctx;
    const fm1_engine_t *e;
    int unit, index, focus;
    unsigned code;
    if (r->type != FM1_REC_PARAM || r->role == FM1_ROLE_MODULE || r->role == FM1_ROLE_MFX) return 1;
    unit = lunar_project_unit_index(r);
    e = unit >= 0 ? load->plan->engine[unit] : NULL;
    if (!e || (index = fm1_param_index(e, r->u.param.uid)) < 0) return 0;
    focus = fm1_engine_focus(e);
    if (fm1_param_per_focus(&e->params[index]) &&
        (float)r->u.param.focus != load->focus[unit] - e->params[focus].min) return 1;
    if (r->role == FM1_ROLE_SOUND) code = fm1_mod_sound_unit(r->sound);
    else if (r->role == FM1_ROLE_INSERT) code = fm1_mod_insert_unit(r->sound, r->slot);
    else code = FM1_MOD_FX1 + r->slot;
    fm1_mod_set_base(load->mod, code, (unsigned)index, parameter_value(r, &e->params[index]));
    return 1;
}

fm1_mod_t *lunar_project_mod_stage(const uint8_t *bytes, uint32_t size,
                                  const fm1_state_names_t *names,
                                  const fm1_host_t *host,
                                  void *workspace, size_t workspace_bytes,
                                  fm1_state_report_t *report) {
    lunar_project_units_t plan;
    fm1_state_mod_t apply;
    fm1_mod_plan_info_t info;
    const fm1_engine_t *units[FM1_MOD_SINKS];
    mod_load_t load;
    fm1_mod_t *mod;
    unsigned i;
    size_t need = fm1_mod_size();
    if (!report) return NULL;
    fm1_state_report_init(report);
    if (!bytes || !names || !host || !workspace || workspace_bytes < need ||
        ((uintptr_t)workspace & 15u) ||
        !disjoint(workspace, need, bytes, size) ||
        !disjoint(workspace, need, report, sizeof *report)) {
        refuse(report, FM1_STATE_BAD, "invalid modulation staging workspace");
        return NULL;
    }
    if (!lunar_project_units_plan(bytes, size, names, host, &plan, report)) return NULL;
    /* The shared applier resolves kinds through its compiled global registry.
     * Require identity, not merely matching IDs, before any constructor runs. */
    for (i = 0; i < FM1_MOD_POSITIONS; ++i) {
        const fm1_mod_kind_t *k = plan.module[i];
        int index;
        if (!k) continue;
        index = fm1_mod_kind_find(k->id);
        if (index < 0 || fm1_mod_kinds[index] != k) {
            refuse(report, FM1_STATE_UNKNOWN, "selected module differs from runtime registry");
            return NULL;
        }
    }
    memset(&load, 0, sizeof load);
    load.bytes = bytes; load.size = size; load.plan = &plan;
    for (i = 0; i < LUNAR_PROJECT_UNITS; ++i) {
        const fm1_engine_t *e = plan.engine[i];
        int focus = e ? fm1_engine_focus(e) : -1;
        if (focus >= 0) load.focus[i] = e->params[focus].def;
    }
    if (!fm1_state_bin_read(read_bytes, &load, size, seed_record, &load, report, 0)) return NULL;
    mod = fm1_mod_create(workspace, host, load.seed);
    if (!mod) {
        refuse(report, FM1_STATE_BAD, "modulation runtime construction failed");
        return NULL;
    }
    for (i = 0; i < FM1_MOD_SINKS; ++i) {
        unsigned code = fm1_mod_sink_unit(i);
        const fm1_engine_t *e = sink_engine(&plan, code);
        units[i] = e;
        if (e && e->n_params && !e->params) {
            refuse(report, FM1_STATE_BAD, "engine has no modulation parameter metadata");
            goto failed;
        }
        if (e && fm1_mod_bind(mod, code, e) < 0) {
            refuse(report, FM1_STATE_RAM, "modulation sink metadata exceeds runtime capacity");
            goto failed;
        }
    }
    fm1_state_mod_init(&apply, mod, names, units, report);
    if (!fm1_state_bin_read(read_bytes, &load, size, fm1_state_mod_sink, &apply, report, 0)) goto failed;
    if (report->skipped) {
        refuse(report, FM1_STATE_BAD, "modulation records refused by runtime applier");
        goto failed;
    }
    load.mod = mod;
    if (!fm1_state_bin_read(read_bytes, &load, size, base_record, &load, report, 0)) goto failed;
    fm1_mod_get_plan(mod, &info);
    if (info.refused) {
        refuse(report, FM1_STATE_BAD, "enabled modulation routes refused by runtime planner");
        goto failed;
    }
    return mod;
failed:
    fm1_mod_destroy(mod);
    return NULL;
}
