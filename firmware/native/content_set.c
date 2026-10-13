/* MIT: connect the checked binary codec to the existing streaming importer. */
#include "content_set.h"
#include <string.h>

typedef struct {
    const uint8_t *bytes;
    uint32_t size;
    fm1_seq_import_t importer;
    unsigned lines;
} set_load_t;

static uint32_t read_bytes(void *ctx, uint32_t off, uint8_t *buf, uint32_t n) {
    set_load_t *load = (set_load_t *)ctx;
    if (off > load->size || n > load->size - off) return 0;
    memcpy(buf, load->bytes + off, n);
    return n;
}

static int set_record(void *ctx, const fm1_rec_t *record) {
    set_load_t *load = (set_load_t *)ctx;
    if (record->type == FM1_REC_HEAD)
        return record->u.head.kind == FM1_STATE_SET;
    if (record->type != FM1_REC_LINE) return 1;
    if (record->u.line.which != FM1_LINES_SET) return 0;
    if (!fm1_seq_import_feed(&load->importer, record->u.line.s,
                             record->u.line.n)) return 0;
    /* The codec gives line contents without their terminating newline. */
    if (record->piece & FM1_REC_LAST) {
        ++load->lines;
        return fm1_seq_import_feed(&load->importer, "\n", 1);
    }
    return 1;
}

static int load_set(const uint8_t *bytes, uint32_t size,
                    fm1_seq_t *scratch, fm1_state_report_t *report, int reject_loss) {
    set_load_t load;
    if (!report) return 0;
    fm1_state_report_init(report);
    if (!bytes || !scratch || size > FM1_STATE_BIN_MAX) {
        report->code = size > FM1_STATE_BIN_MAX ? FM1_STATE_TOO_BIG : FM1_STATE_BAD;
        return 0;
    }
    memset(&load, 0, sizeof(load));
    load.bytes = bytes;
    load.size = size;
    fm1_seq_import_begin(&load.importer, scratch);
    if (!fm1_state_bin_read(read_bytes, &load, size, set_record, &load, report, 0)) return 0;
    if (!load.lines || !fm1_seq_import_end(&load.importer)) {
        report->code = FM1_STATE_BAD;
        return 0;
    }
    if (reject_loss && load.importer.loss_flags) {
        report->code = FM1_STATE_BAD;
        return 0;
    }
    return 1;
}

int lunar_content_load_set(const uint8_t *bytes, uint32_t size,
                           fm1_seq_t *scratch, fm1_state_report_t *report) {
    return load_set(bytes, size, scratch, report, 0);
}

int lunar_content_load_set_checked(const uint8_t *bytes, uint32_t size,
                                   fm1_seq_t *scratch, fm1_state_report_t *report) {
    return load_set(bytes, size, scratch, report, 1);
}

int lunar_content_activate_set(fm1_app_t *app, const uint8_t *bytes, uint32_t size,
                               fm1_seq_t *scratch, fm1_state_report_t *report) {
    if (!report) return 0;
    fm1_state_report_init(report);
    if (!app || !fm1_seq_can_replace(app->seq, scratch)) {
        report->code = FM1_STATE_BAD;
        return 0;
    }
    if (!lunar_content_load_set_checked(bytes, size, scratch, report)) return 0;
    if (!fm1_app_seq_activate(app, scratch)) {
        report->code = FM1_STATE_BAD;
        return 0;
    }
    return 1;
}

int lunar_content_start_set(fm1_app_t *app, lunar_instance_pool_t *pool,
                            const uint8_t *bytes, uint32_t size, uint32_t rate,
                            fm1_state_report_t *report) {
    void *arena;
    fm1_seq_t *scratch;
    size_t arena_bytes;
    int ok;
    if (!report) return 0;
    fm1_state_report_init(report);
    report->code = FM1_STATE_BAD;
    if (!app || !app->seq || !pool || !bytes || !rate ||
        size > FM1_STATE_BIN_MAX) return 0;
    arena_bytes = fm1_seq_size(&app->seq_lim);
    if (!arena_bytes || arena_bytes > sizeof app->seq_mem) return 0;
    arena = lunar_instance_pool_alloc(pool, arena_bytes);
    if (!arena) return 0;
    scratch = fm1_seq_create(arena, &app->seq_lim, rate);
    ok = scratch && lunar_content_activate_set(app, bytes, size, scratch, report);
    /* This is the original allocation, exclusively owned by this main task. */
    lunar_instance_pool_free(pool, arena);
    return ok;
}
