/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_PROJECT_SAVE_APP_H
#define LUNAR_PROJECT_SAVE_APP_H
#include "project_save.h"
#include "fm1_app_state.h"

/* The app remains exclusively owned and stable across both SAVE passes.
 * Stop flags describe caller-enforced scheduling, not locks provided here.
 * No flash geometry or physical write permission is established here. */
typedef struct {
    fm1_rec_sink_t sink;
    void *ctx;
} lunar_project_app_sink;

static int lunar_project_app_record(void *ctx, const fm1_rec_t *record) {
    lunar_project_app_sink *out = ctx;
    fm1_rec_t native;
    if (record->type != FM1_REC_INFO || record->u.info.key != FM1_INFO_BY)
        return out->sink(out->ctx, record);
    native = *record;
    native.piece = FM1_REC_FIRST | FM1_REC_LAST;
    native.u.info.s = "firmware";
    native.u.info.n = 8;
    return out->sink(out->ctx, &native);
}

static int lunar_project_app_collect(void *app, fm1_rec_sink_t sink, void *ctx,
                                     fm1_state_report_t *report) {
    lunar_project_app_sink out = {sink, ctx};
    if (!sink) return 0;
    return fm1_app_state_collect_project(app, 1, lunar_project_app_record,
                                         &out, report);
}

static int lunar_project_save_app(fm1_app_t *app, const lunar_project_io *io,
        uint32_t slot_bytes, int storage_admitted, int audio_stopped,
        int drawing_stopped, int display_reads_stopped,
        fm1_state_report_t *report) {
    if (!app) return -2;
    return lunar_project_save(&app->tft, io, slot_bytes,
        lunar_project_app_collect, app, storage_admitted, audio_stopped,
        drawing_stopped, display_reads_stopped, report);
}
#endif
