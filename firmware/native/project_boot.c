/* SPDX-License-Identifier: MIT */
#include "project_boot.h"
#include "project_seq.h"
#include <string.h>
#if FM1_APP_EXTERNAL_ARENAS
static int overlap(const void *a, size_t an, const void *b, size_t bn) {
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    return an > UINTPTR_MAX - x || bn > UINTPTR_MAX - y ||
           (x < y + bn && y < x + an);
}
static int bad(fm1_state_report_t *r, const char *why) {
    r->code = FM1_STATE_BAD;
    strncpy(r->what, why, sizeof r->what - 1u);
    r->what[sizeof r->what - 1u] = 0;
    return 0;
}
typedef struct {
    const uint8_t *bytes;
    uint32_t size;
    unsigned seen;
    fm1_rec_t view;
} view_load_t;
static uint32_t read_bytes(void *ctx, uint32_t off, uint8_t *buf, uint32_t n) {
    view_load_t *v = ctx;
    if (off > v->size || n > v->size - off) return 0;
    memcpy(buf, v->bytes + off, n);
    return n;
}
static int view_record(void *ctx, const fm1_rec_t *r) {
    view_load_t *v = ctx;
    if (r->type == FM1_REC_HEAD) return r->u.head.kind == FM1_STATE_PROJECT;
    if (r->type == FM1_REC_VIEW) { if (v->seen++) return 0; v->view = *r; }
    return 1;
}
int lunar_project_restore_view(fm1_app_t *app, const uint8_t *bytes, uint32_t size,
                               fm1_state_report_t *report) {
    view_load_t v;
    uint16_t has;
    uint8_t *x;
    if (!report || (app && overlap(app, sizeof *app, report, sizeof *report)) ||
        (bytes && overlap(bytes, size, report, sizeof *report))) return 0;
    fm1_state_report_init(report);
    if (!app || !bytes || app->frames || overlap(app, sizeof *app, bytes, size))
        return bad(report, "invalid cold view input");
    memset(&v, 0, sizeof v); v.bytes = bytes; v.size = size;
    if (!fm1_state_bin_read(read_bytes, &v, size, view_record, &v, report, 0)) return 0;
    if (!v.seen) return 1;
    has = v.view.u.view.has; x = v.view.u.view.v;
    /* The file schema's panel zero means no panel override. */
    if (!x[FM1_VK_PANEL]) has &= (uint16_t)~(1u << FM1_VK_PANEL);
    /* A file FX view defaults to Mix, independently of the previous screen. */
    if (v.view.u.view.mode == FM1_VIEW_FX && !(has & (1u << FM1_VK_UNIT)) &&
        !(has & (1u << FM1_VK_ENTRY))) {
        has |= 1u << FM1_VK_ENTRY; x[FM1_VK_ENTRY] = 3;
    }
    if (fm1_app_show(app, v.view.u.view.mode, has, x))
        return bad(report, "saved view dependencies unavailable");
    if (v.view.u.view.mode == FM1_VIEW_SESSION)
        fm1_seq_ui_open(&app->ui, FM1_SEQ_VIEW_SESSION);
    else if (v.view.u.view.mode == FM1_VIEW_SONG)
        fm1_seq_ui_open_song(&app->ui, has & (1u << FM1_VK_ENTRY) ?
                              x[FM1_VK_ENTRY] - 1u : FM1_SEQ_UI_SONG_MAX);
    return 1;
}
int lunar_project_start(fm1_app_t *app, lunar_instance_pool_t *pool,
                         const uint8_t *bytes, uint32_t size, uint32_t rate,
                         fm1_state_report_t *report) {
    lunar_project_units_t plan;
    lunar_project_engines_t candidate;
    fm1_state_names_t names;
    void *arena;
    fm1_seq_t *scratch;
    size_t need;
    unsigned has_set = 0;
    int ok;
    if (!report || (app && overlap(app, sizeof *app, report, sizeof *report)) ||
        (bytes && overlap(bytes, size, report, sizeof *report)) ||
        (pool && (overlap(pool, sizeof *pool, report, sizeof *report) ||
                  (pool->hi >= pool->lo && overlap((void *)pool->lo, pool->hi - pool->lo, report, sizeof *report))))) return 0;
    fm1_state_report_init(report);
    if (!app || !pool || !bytes || !rate || app->frames || !app->seq ||
        !pool->allocator || pool->hi <= pool->lo || pool->live_allocations ||
        app->host.sample_rate != (float)rate ||
        overlap((void *)pool->lo, pool->hi - pool->lo, pool, sizeof *pool) ||
        app->storage_ctx != pool || !app->storage_alloc || !app->storage_free ||
        overlap(app, sizeof *app, bytes, size) || overlap(app, sizeof *app, pool, sizeof *pool) ||
        overlap(bytes, size, pool, sizeof *pool) ||
        overlap((void *)pool->lo, pool->hi - pool->lo, app, sizeof *app) ||
        overlap((void *)pool->lo, pool->hi - pool->lo, bytes, size))
        return bad(report, "invalid cold project startup ownership");
    for (unsigned i = 0; i < FM1_APP_UNITS; ++i)
        if (app->unit[i].e || app->unit[i].self || app->unit[i].mem || app->unit[i].cap)
            return bad(report, "project startup requires empty audio units");
    fm1_state_names_default(&names);
    if (!lunar_project_units_plan(bytes, size, &names, &app->host, &plan, report)) return 0;
    need = fm1_seq_size(&app->seq_lim);
    arena = lunar_instance_pool_alloc(pool, need);
    if (!arena) return bad(report, "project sequence scratch does not fit");
    scratch = fm1_seq_create(arena, &app->seq_lim, rate);
    ok = scratch && lunar_project_seq_stage(bytes, size, &names, &app->host,
                                             scratch, &has_set, report);
    if (ok && has_set) ok = fm1_app_seq_activate(app, scratch);
    if (lunar_instance_pool_free(pool, arena)) return bad(report, "sequence scratch ownership lost");
    if (!ok) { if (!report->code) bad(report, "sequence startup refused"); return 0; }
    arena = lunar_instance_pool_alloc(pool, sizeof(lunar_project_dx7_scratch_t));
    if (!arena) return bad(report, "project DX7 scratch does not fit");
    ok = lunar_project_restore_dx7(app, bytes, size, arena, report);
    if (lunar_instance_pool_free(pool, arena)) return bad(report, "DX7 scratch ownership lost");
    if (!ok) return 0;
    memset(&candidate, 0, sizeof candidate);
    if (!lunar_project_engines_stage(bytes, size, &names, &app->host, pool, &candidate, report)) return 0;
    ok = lunar_project_engines_apply(bytes, size, &names, &app->host, &candidate, report);
    if (ok) ok = lunar_project_adopt_audio_units(app, &candidate) == FM1_APP_SELECT_OK;
    if (ok) ok = lunar_project_restore_midi_units(app, &candidate, plan.midi_on) == FM1_APP_SELECT_OK;
    lunar_project_engines_release(&candidate);
    if (!ok) { if (!report->code) bad(report, "engine startup adoption refused"); return 0; }
    return lunar_project_restore_scalars(app, bytes, size, report) &&
           lunar_project_restore_mod(app, bytes, size, report) &&
           lunar_project_restore_view(app, bytes, size, report);
}
#endif
