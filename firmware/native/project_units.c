/* MIT: reuse the state codec without browser export or scratch-engine buffers. */
#include "project_units.h"
#include <string.h>

typedef struct {
    const uint8_t *bytes;
    uint32_t size;
    const fm1_state_names_t *names;
    fm1_state_report_t *report;
    lunar_project_units_t plan;
} unit_load_t;

static int refuse(unit_load_t *load, unsigned code, const char *why) {
    load->report->code = (uint8_t)code;
    strncpy(load->report->what, why, sizeof load->report->what - 1u);
    load->report->what[sizeof load->report->what - 1u] = 0;
    return 0;
}

static uint32_t read_bytes(void *ctx, uint32_t off, uint8_t *buf, uint32_t n) {
    unit_load_t *load = (unit_load_t *)ctx;
    if (off > load->size || n > load->size - off) return 0;
    memcpy(buf, load->bytes + off, n);
    return n;
}

static int unit_index(const fm1_rec_t *r) {
    if (r->sound >= 4u) return -1;
    switch (r->role) {
        case FM1_ROLE_SOUND: return r->slot == 0 ? r->sound : -1;
        case FM1_ROLE_INSERT: return r->slot < 2u ? 4 + r->sound * 2 + r->slot : -1;
        case FM1_ROLE_MASTER: return r->sound == 0 && r->slot < 2u ? 12 + r->slot : -1;
        case FM1_ROLE_MFX: return r->slot == 0 ? 14 + r->sound : -1;
        default: return -1;
    }
}

static int parameter(unit_load_t *load, const fm1_rec_t *r) {
    const fm1_param_t *params = NULL, *p = NULL, *focus = NULL;
    unsigned n = 0, i;
    float value;
    if (r->role == FM1_ROLE_MODULE) {
        const fm1_mod_kind_t *k = r->slot < 8u ? load->plan.module[r->slot] : NULL;
        if (k) { params = k->params; n = k->n_params; }
    } else {
        int index = unit_index(r);
        const fm1_engine_t *e = index >= 0 ? load->plan.engine[index] : NULL;
        if (e) { params = e->params; n = e->n_params; }
    }
    if (!params) return refuse(load, FM1_STATE_BAD, "parameter has no selected owner");
    for (i = 0; i < n; ++i) {
        if (params[i].uid == r->u.param.uid) p = &params[i];
        if (params[i].flags & FM1_PARAM_FOCUS) focus = &params[i];
    }
    if (!p) return refuse(load, FM1_STATE_BAD, "parameter uid absent from selected owner");
    if (p->flags & FM1_PARAM_PER_FOCUS) {
        if (!focus || r->u.param.focus == FM1_FOCUS_NONE ||
            (float)r->u.param.focus > focus->max - focus->min)
            return refuse(load, FM1_STATE_BAD, "parameter pad index out of range");
    } else if (r->u.param.focus != FM1_FOCUS_NONE) {
        return refuse(load, FM1_STATE_BAD, "ordinary parameter has a pad index");
    }
    if (r->u.param.vtype == FM1_VAL_INDEX) {
        if (p->type != FM1_PARAM_ENUM)
            return refuse(load, FM1_STATE_BAD, "index value for a continuous parameter");
        value = p->min + (float)r->u.param.bits;
    } else if (r->u.param.vtype == FM1_VAL_F32) {
        /* Inspect the exponent before doing comparisons: NaNs compare false. */
        if ((r->u.param.bits & 0x7f800000u) == 0x7f800000u)
            return refuse(load, FM1_STATE_BAD, "nonfinite parameter value");
        memcpy(&value, &r->u.param.bits, sizeof value);
    } else return refuse(load, FM1_STATE_BAD, "unsupported parameter value type");
    if (value < p->min || value > p->max)
        return refuse(load, FM1_STATE_BAD, "parameter value would be clamped");
    if (p->type == FM1_PARAM_ENUM) {
        /* Enum descriptor values fit this integer range; check before casting. */
        if (value < -32768.0f || value > 32767.0f || value != (float)(int)value)
            return refuse(load, FM1_STATE_BAD, "fractional or unsupported enum value");
    }
    return 1;
}

static int record(void *ctx, const fm1_rec_t *r) {
    unit_load_t *load = (unit_load_t *)ctx;
    if (r->type == FM1_REC_HEAD)
        return r->u.head.kind == FM1_STATE_PROJECT ||
               refuse(load, FM1_STATE_BAD, "expected a binary project");
    if (r->type == FM1_REC_PARAM) return parameter(load, r);
    if (r->type == FM1_REC_UNIT || r->type == FM1_REC_MODULE) {
        if (!memchr(r->u.unit.id, 0, sizeof r->u.unit.id))
            return refuse(load, FM1_STATE_BAD, "unterminated unit id");
        if (r->type == FM1_REC_MODULE) {
            unsigned bit;
            if (r->slot >= 8u) return refuse(load, FM1_STATE_BAD, "unsupported rack position");
            bit = 1u << r->slot;
            if (load->plan.modules_given & bit)
                return refuse(load, FM1_STATE_BAD, "duplicate rack position");
            load->plan.modules_given |= (uint8_t)bit;
            if (!r->u.unit.id[0]) return 1;
            load->plan.module[r->slot] = fm1_state_kind(load->names, r->u.unit.id);
            if (load->plan.module[r->slot]) return 1;
        } else {
            int index = unit_index(r);
            uint32_t bit;
            if (index < 0) return refuse(load, FM1_STATE_BAD, "unsupported native unit position");
            bit = 1u << (unsigned)index;
            if (load->plan.given & bit)
                return refuse(load, FM1_STATE_BAD, "duplicate unit position");
            load->plan.given |= bit;
            if (!r->u.unit.id[0]) return 1;
            load->plan.engine[index] = fm1_state_engine(load->names, r->role, r->u.unit.id);
            if (load->plan.engine[index]) return 1;
        }
        fm1_state_note_unknown(load->names, r, load->report);
        return refuse(load, FM1_STATE_UNKNOWN, "unit absent from selected catalogue");
    }
    return 1;
}

int lunar_project_units_plan(const uint8_t *bytes, uint32_t size,
                             const fm1_state_names_t *names,
                             const fm1_host_t *host,
                             lunar_project_units_t *out,
                             fm1_state_report_t *report) {
    unit_load_t load;
    unsigned i;
    if (!report) return 0;
    fm1_state_report_init(report);
    if (!bytes || !names || !host || !out || size > FM1_STATE_BIN_MAX) {
        report->code = size > FM1_STATE_BIN_MAX ? FM1_STATE_TOO_BIG : FM1_STATE_BAD;
        return 0;
    }
    memset(&load, 0, sizeof load);
    load.bytes = bytes;
    load.size = size;
    load.names = names;
    load.report = report;
    if (!fm1_state_bin_read(read_bytes, &load, size, record, &load, report, 0)) return 0;
    for (i = 0; i < LUNAR_PROJECT_UNITS; ++i) {
        const fm1_engine_t *e = load.plan.engine[i];
        if (!e) continue;
        if (!e->instance_size || !(load.plan.size[i] = e->instance_size(host)))
            return refuse(&load, FM1_STATE_RAM, "engine has no instance allocation size");
    }
    *out = load.plan;
    return 1;
}
