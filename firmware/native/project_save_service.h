/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_PROJECT_SAVE_SERVICE_H
#define LUNAR_PROJECT_SAVE_SERVICE_H
#include "project_save_app.h"
typedef struct {
    lunar_project_io io;
    uint32_t slot_bytes, seen_gen;
    int storage_admitted;
    void *pause_ctx;
    int (*pause)(void *); /* 1 paused, 0 defer, negative refusal */
    void (*resume)(void *);
} lunar_project_save_service;

static int lunar_project_save_service_ready(const lunar_project_save_service *s)
{
    return s && s->storage_admitted == 1 && s->pause && s->resume &&
        s->io.read && s->io.erase && s->io.program && s->io.validate &&
        s->slot_bytes >= LP_SECTOR && !(s->slot_bytes % LP_SECTOR) &&
        s->slot_bytes <= LP_MAX + LP_SECTOR;
}

/* Core-0 main-loop poll, exclusively owning app state/drawing. No platform_poll
 * or callback that dispatches app events may run inside pause/SAVE/resume.
 * I/O must service watchdog and safely permit unrelated interrupts itself.
 * 0 idle, 1 deferred for display completion, 2 handled (success OR refusal).
 * Each handled generation is consumed even on failure: never retry NOR writes
 * implicitly. The caller installs an admitted physical binding separately. */
static int lunar_project_save_service_poll(lunar_project_save_service *s,
                                           fm1_app_t *app)
{
    fm1_state_report_t report;
    int paused, rc;
    if (!s || !app || s->seen_gen == app->save_gen) return 0;
    if (!lunar_project_save_service_ready(s)) {
        s->seen_gen = app->save_gen;
        fm1_app_saved(app, 0, "storage not admitted");
        return 2;
    }
    paused = s->pause(s->pause_ctx);
    if (!paused) return 1;
    s->seen_gen = app->save_gen;
    if (paused != 1) {
        fm1_app_saved(app, 0, "pause refused");
        return 2;
    }
    fm1_state_report_init(&report);
    rc = lunar_project_save_app(app, &s->io, s->slot_bytes, 1, 1, 1, 1, &report);
    fm1_app_saved(app, rc == 0, report.what[0] ? report.what : "store refused");
    /* Release invalidates pixels on failure too. Rebuild the UI before DMA
     * readers or audio are allowed back; workspace bytes never reach the TFT. */
    fm1_app_draw(app, 0);
    s->resume(s->pause_ctx);
    return 2;
}
#endif
