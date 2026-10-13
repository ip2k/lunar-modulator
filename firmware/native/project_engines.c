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
                  !e->create || !e->destroy || (e->n_params && (!e->params || !e->set_param))))
            return refuse(report, FM1_STATE_BAD, "invalid engine constructor descriptor");
    }
    out->pool = pool;
    /* Reserve the complete candidate before the first constructor. */
    for (i = 0; i < LUNAR_PROJECT_UNITS; ++i) {
        lunar_project_instance_t *u = &out->unit[i];
        u->engine = plan.engine[i];
        if (!u->engine) continue;
        u->memory = lunar_instance_pool_alloc(pool, plan.size[i]);
        if (!u->memory) {
            refuse(report, FM1_STATE_RAM, "candidate engines cannot coexist with live allocations");
            goto failed;
        }
    }
    for (i = 0; i < LUNAR_PROJECT_UNITS; ++i) {
        lunar_project_instance_t *u = &out->unit[i];
        if (!u->engine) continue;
        memset(u->memory, 0, plan.size[i]);
        u->self = u->engine->create(u->memory, host);
        if (!u->self) {
            refuse(report, FM1_STATE_BAD, "candidate engine refused host");
            goto failed;
        }
    }
    return 1;
failed:
    lunar_project_engines_release(out);
    return 0;
}
