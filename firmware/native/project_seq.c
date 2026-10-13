#include "project_seq.h"
#include "fm1_seq_host.h"
#include <string.h>

typedef struct {
    const uint8_t *bytes;
    uint32_t size;
    unsigned lines;
    fm1_seq_import_t importer;
} seq_load_t;

static uint32_t read_bytes(void *ctx, uint32_t off, uint8_t *buf, uint32_t n) {
    seq_load_t *load = (seq_load_t *)ctx;
    if (off > load->size || n > load->size - off) return 0;
    memcpy(buf, load->bytes + off, n);
    return n;
}

static int sequence_record(void *ctx, const fm1_rec_t *r) {
    seq_load_t *load = (seq_load_t *)ctx;
    if (r->type != FM1_REC_LINE) return 1;
    if (r->u.line.which != FM1_LINES_SET) return 0;
    if (!fm1_seq_import_feed(&load->importer, r->u.line.s, r->u.line.n)) return 0;
    if (r->piece & FM1_REC_LAST) {
        ++load->lines;
        return fm1_seq_import_feed(&load->importer, "\n", 1);
    }
    return 1;
}

static int refuse(fm1_state_report_t *report, const char *why) {
    report->code = FM1_STATE_BAD;
    strncpy(report->what, why, sizeof report->what - 1u);
    report->what[sizeof report->what - 1u] = 0;
    return 0;
}

int lunar_project_seq_stage(const uint8_t *bytes, uint32_t size,
                            const fm1_state_names_t *names, const fm1_host_t *host,
                            fm1_seq_t *scratch, unsigned *has_set,
                            fm1_state_report_t *report) {
    lunar_project_units_t plan;
    seq_load_t load;
    fm1_seq_info_t info;
    unsigned t;
    if (!report) return 0;
    fm1_state_report_init(report);
    if (!scratch || !has_set) return refuse(report, "invalid sequence staging output");
    if (!lunar_project_units_plan(bytes, size, names, host, &plan, report)) return 0;
    memset(&load, 0, sizeof load);
    load.bytes = bytes; load.size = size;
    fm1_seq_import_begin(&load.importer, scratch);
    if (!fm1_state_bin_read(read_bytes, &load, size, sequence_record, &load, report, 0)) return 0;
    if (!load.lines) { *has_set = 0; return 1; }
    if (!fm1_seq_import_end(&load.importer) || load.importer.loss_flags)
        return refuse(report, "project sequence importer refused content or observed loss");
    fm1_seq_get_info(scratch, &info);
    for (t = 0; t < info.tracks; ++t) {
        fm1_seq_track_info_t track;
        const fm1_engine_t *e;
        unsigned lane;
        if (!fm1_seq_get_track(scratch, (uint8_t)t, &track))
            return refuse(report, "project sequence track unavailable");
        if (track.route_kind == FM1_SEQ_ROUTE_MIDI) {
            if (!track.route_index || track.route_index > 16u)
                return refuse(report, "invalid project MIDI route");
            continue;
        }
        if (track.route_kind != FM1_SEQ_ROUTE_ENGINE || track.route_index >= 4u ||
            !(e = plan.engine[track.route_index]))
            return refuse(report, "project sequence route has no selected sound");
        if (e->n_params && !e->params)
            return refuse(report, "sound has no sequence parameter metadata");
        for (lane = 0; lane < FM1_SEQ_LANES; ++lane) {
            int index;
            if (!((track.lanes_assigned >> lane) & 1u)) continue;
            index = fm1_seq_lane_param(e, fm1_seq_lane_label(scratch, (uint8_t)t, (uint8_t)lane));
            if (index < 0 || !e->params[index].uid || !fm1_param_lockable(&e->params[index]))
                return refuse(report, "project sequence lane cannot bind a lockable parameter");
        }
    }
    *has_set = 1;
    return 1;
}
