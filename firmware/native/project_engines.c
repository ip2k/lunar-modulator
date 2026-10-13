#include "project_engines.h"
#include <string.h>

static int refuse(fm1_state_report_t *report, unsigned code, const char *why) {
    report->code = (uint8_t)code;
    strncpy(report->what, why, sizeof report->what - 1u);
    report->what[sizeof report->what - 1u] = 0;
    return 0;
}

void lunar_project_engines_release(lunar_project_engines_t *candidate) {
    unsigned i;
    if (!candidate || !candidate->pool) return;
    for (i = LUNAR_PROJECT_UNITS; i; --i) {
        lunar_project_instance_t *u = &candidate->unit[i - 1u];
        if (u->self) u->engine->destroy(u->self);
        if (u->memory) lunar_instance_pool_free(candidate->pool, u->memory);
    }
    memset(candidate, 0, sizeof *candidate);
}

int lunar_project_engines_stage(const uint8_t *bytes, uint32_t size,
                                const fm1_state_names_t *names, const fm1_host_t *host,
                                lunar_instance_pool_t *pool,
                                lunar_project_engines_t *out,
                                fm1_state_report_t *report) {
    lunar_project_units_t plan;
    unsigned i;
    if (!report) return 0;
    fm1_state_report_init(report);
    if (!out || !pool || !pool->allocator || !host ||
        host->api_version != FM1_ENGINE_API_VERSION)
        return refuse(report, FM1_STATE_BAD, "invalid engine candidate context");
    /* Refuse overwriting candidate ownership, even if callers forgot release. */
    if (out->pool) return refuse(report, FM1_STATE_BAD, "candidate is not empty");
    for (i = 0; i < LUNAR_PROJECT_UNITS; ++i)
        if (out->unit[i].engine || out->unit[i].memory || out->unit[i].self)
            return refuse(report, FM1_STATE_BAD, "candidate contains stale ownership");
    if (!lunar_project_units_plan(bytes, size, names, host, &plan, report)) return 0;
    for (i = 0; i < LUNAR_PROJECT_UNITS; ++i) {
        const fm1_engine_t *e = plan.engine[i];
        if (e && (e->magic != FM1_ENGINE_MAGIC || e->api_version != FM1_ENGINE_API_VERSION ||
                  !e->create || !e->destroy || e->n_params > LUNAR_PROJECT_ENGINE_PARAMS ||
                  (e->n_params && (!e->params || !e->set_param)) ||
                  (fm1_engine_focus(e) >= 0 && !e->get_param)))
            return refuse(report, FM1_STATE_BAD, "invalid engine constructor descriptor");
    }
    out->pool = pool;
    /* Reserve the complete candidate before the first constructor. */
    for (i = 0; i < LUNAR_PROJECT_UNITS; ++i) {
        lunar_project_instance_t *u = &out->unit[i];
        u->engine = plan.engine[i];
        if (!u->engine) continue;
        u->bytes = plan.size[i];
        u->memory = lunar_instance_pool_alloc(pool, u->bytes);
        if (!u->memory) {
            refuse(report, FM1_STATE_RAM, "candidate engines cannot coexist with live allocations");
            goto failed;
        }
    }
    for (i = 0; i < LUNAR_PROJECT_UNITS; ++i) {
        lunar_project_instance_t *u = &out->unit[i];
        if (!u->engine) continue;
        unsigned p;
        memset(u->memory, 0, u->bytes);
        u->self = u->engine->create(u->memory, host);
        if (!u->self) {
            refuse(report, FM1_STATE_BAD, "candidate engine refused host");
            goto failed;
        }
        for (p = 0; p < u->engine->n_params; ++p)
            u->value[p] = u->engine->get_param
                ? u->engine->get_param(u->self, (uint16_t)p, FM1_FOCUS_CURRENT)
                : u->engine->params[p].def;
    }
    return 1;
failed:
    lunar_project_engines_release(out);
    return 0;
}


typedef struct {
    const uint8_t *bytes;
    uint32_t size;
    lunar_project_engines_t *candidate;
    fm1_state_report_t *report;
} engine_load_t;

static uint32_t read_bytes(void *ctx, uint32_t off, uint8_t *buf, uint32_t n) {
    engine_load_t *load = (engine_load_t *)ctx;
    if (off > load->size || n > load->size - off) return 0;
    memcpy(buf, load->bytes + off, n);
    return n;
}

static int parameter_record(void *ctx, const fm1_rec_t *r) {
    engine_load_t *load = (engine_load_t *)ctx;
    lunar_project_instance_t *u;
    const fm1_engine_t *e;
    int unit, index, focus;
    float value;
    if (r->type != FM1_REC_PARAM || r->role == FM1_ROLE_MODULE) return 1;
    unit = lunar_project_unit_index(r);
    if (unit < 0) return refuse(load->report, FM1_STATE_BAD, "invalid candidate parameter unit");
    u = &load->candidate->unit[unit]; e = u->engine;
    if (!e || !u->self || !e->set_param ||
        (index = fm1_param_index(e, r->u.param.uid)) < 0)
        return refuse(load->report, FM1_STATE_BAD, "candidate parameter has no instance binding");
    if (r->u.param.vtype == FM1_VAL_INDEX) value = e->params[index].min + (float)r->u.param.bits;
    else memcpy(&value, &r->u.param.bits, sizeof value);
    focus = fm1_engine_focus(e);
    if (index == focus) {
        u->value[index] = value; /* final focus, restored after all pads */
    } else {
        if (r->u.param.focus != FM1_FOCUS_NONE) {
            if (focus < 0) return refuse(load->report, FM1_STATE_BAD, "candidate has no focus selector");
            e->set_param(u->self, (uint16_t)focus, e->params[focus].min + (float)r->u.param.focus);
        }
        e->set_param(u->self, (uint16_t)index, value);
        u->value[index] = value;
    }
    return 1;
}

int lunar_project_engines_apply(const uint8_t *bytes, uint32_t size,
                                const fm1_state_names_t *names, const fm1_host_t *host,
                                lunar_project_engines_t *candidate,
                                fm1_state_report_t *report) {
    lunar_project_units_t plan;
    engine_load_t load;
    unsigned i;
    if (!report) return 0;
    fm1_state_report_init(report);
    if (!candidate || !candidate->pool)
        return refuse(report, FM1_STATE_BAD, "engine candidate is not owned");
    if (!lunar_project_units_plan(bytes, size, names, host, &plan, report)) return 0;
    for (i = 0; i < LUNAR_PROJECT_UNITS; ++i) {
        const lunar_project_instance_t *u = &candidate->unit[i];
        if (u->engine != plan.engine[i] || u->bytes != plan.size[i] ||
            (u->engine && (!u->memory || !u->self)))
            return refuse(report, FM1_STATE_BAD, "candidate differs from project unit plan");
    }
    load.bytes = bytes; load.size = size; load.candidate = candidate; load.report = report;
    if (!fm1_state_bin_read(read_bytes, &load, size, parameter_record, &load, report, 0)) return 0;
    for (i = 0; i < LUNAR_PROJECT_UNITS; ++i) {
        lunar_project_instance_t *u = &candidate->unit[i];
        const fm1_engine_t *e = u->engine;
        int focus;
        unsigned p;
        if (!e) continue;
        focus = fm1_engine_focus(e);
        if (focus >= 0) {
            e->set_param(u->self, (uint16_t)focus, u->value[focus]);
            for (p = 0; p < e->n_params; ++p)
                if (fm1_param_per_focus(&e->params[p]))
                    u->value[p] = e->get_param(u->self, (uint16_t)p, FM1_FOCUS_CURRENT);
        }
    }
    return 1;
}
