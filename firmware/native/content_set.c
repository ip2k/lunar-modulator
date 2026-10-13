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

int lunar_content_load_set(const uint8_t *bytes, uint32_t size,
                           fm1_seq_t *scratch, fm1_state_report_t *report) {
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
    return 1;
}
