/* Stream export equivalence and every-callback failure, without live mutation. */
#include "fm1_seq.h"
#include "state_seq_export.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static char expected[262144], actual[262144], input[262144];
typedef struct { size_t len, calls, fail; int mode; } output_t;
static int output(void *ctx, const char *data, size_t size) {
    output_t *o = ctx;
    ++o->calls;
    if (o->calls == o->fail) {
        size_t partial = o->mode == 0 ? 0 : o->mode == 1 ? size / 2 : size;
        if (partial > sizeof actual - o->len) abort();
        memcpy(actual + o->len, data, partial); o->len += partial;
        return -7;
    }
    if (size > sizeof actual - o->len) abort();
    memcpy(actual + o->len, data, size); o->len += size;
    return 0;
}
static int records_mode;
typedef struct { fm1_seq_export_sink_t write; void *ctx; size_t len; unsigned open; } bridge_t;
static int record_output(void *ctx, const fm1_rec_t *r) {
    bridge_t *b = ctx;
    if (r->type != FM1_REC_LINE || r->u.line.which != FM1_LINES_SET ||
        (r->piece & ~(FM1_REC_FIRST | FM1_REC_LAST)) ||
        (!!(r->piece & FM1_REC_FIRST) == !!b->open)) abort();
    if (memchr(r->u.line.s, '\n', r->u.line.n)) abort();
    if (r->u.line.n && b->write(b->ctx, r->u.line.s, r->u.line.n)) return 0;
    b->len += r->u.line.n;
    b->open = 1;
    if (r->piece & FM1_REC_LAST) {
        if (b->write(b->ctx, "\n", 1)) return 0;
        ++b->len; b->open = 0;
    }
    return 1;
}
static int export_api(const fm1_seq_t *seq, fm1_seq_export_sink_t sink,
                       void *ctx, size_t *length) {
    if (!records_mode) return fm1_seq_export_movy1_stream(seq, sink, ctx, length);
    if (length) *length = 0;
    if (!seq || !sink || !length) return -1;
    bridge_t b = { sink, ctx, 0, 0 };
    if (!fm1_state_seq_export(seq, record_output, &b) || b.open) return -1;
    *length = b.len;
    return 0;
}
/* Actual codec parity and every random-access write refusal. */
static uint8_t binary[2][FM1_STATE_BIN_MAX];
typedef struct { unsigned index, calls, fail, header; } binary_sink_t;
static int binary_write(void *ctx, uint32_t off, const void *p, uint32_t n) {
    binary_sink_t *b = ctx;
    if (++b->calls == b->fail) return -1;
    if (off > FM1_STATE_BIN_MAX || n > FM1_STATE_BIN_MAX - off) abort();
    memcpy(binary[b->index] + off, p, n);
    if (!off) ++b->header;
    return 0;
}
static uint32_t binary_read(void *ctx, uint32_t off, uint8_t *p, uint32_t n) {
    uint32_t total = *(uint32_t *)ctx;
    if (off > total || n > total - off) return 0;
    memcpy(p, binary[1] + off, n); return n;
}
static int discard_record(void *ctx, const fm1_rec_t *r) {
    (void)ctx; (void)r; return 1;
}
static uint32_t binary_size(const uint8_t *p) {
    return (uint32_t)p[20] | ((uint32_t)p[21] << 8) |
           ((uint32_t)p[22] << 16) | ((uint32_t)p[23] << 24);
}
static int encode_set(const fm1_seq_t *seq, void *mem, binary_sink_t *b, int fragmented) {
    fm1_state_report_t report; fm1_rec_t r;
    fm1_state_report_init(&report);
    memset(binary[b->index], 255, FM1_STATE_BIN_MAX);
    fm1_state_writer_t *w = fm1_state_bin_stream_writer(mem, 0, NULL,
        binary_write, b, FM1_STATE_BIN_MAX, &report);
    if (!w) abort();
    memset(&r, 0, sizeof r); r.type = FM1_REC_HEAD;
    r.u.head.kind = FM1_STATE_SET; r.u.head.major = FM1_STATE_MAJOR;
    if (!fm1_state_bin_write(w, &r)) return 0;
    if (fragmented) {
        if (!fm1_state_seq_export(seq, fm1_state_bin_write, w)) return 0;
    } else {
        const char *p = expected;
        while (*p) {
            const char *end = strchr(p, '\n'); if (!end) abort();
            memset(&r, 0, sizeof r); r.type = FM1_REC_LINE;
            r.piece = FM1_REC_FIRST | FM1_REC_LAST;
            r.u.line.which = FM1_LINES_SET; r.u.line.s = p;
            r.u.line.n = (uint32_t)(end - p);
            if (!fm1_state_bin_write(w, &r)) return 0;
            p = end + 1;
        }
    }
    memset(&r, 0, sizeof r); r.type = FM1_REC_END;
    int ok = fm1_state_bin_write(w, &r);
    unsigned calls = b->calls;
    if (fm1_state_bin_write(w, &r) || b->calls != calls) abort();
    return ok;
}
static void codec_check(const fm1_seq_t *seq) {
    void *mem = malloc(fm1_state_bin_writer_size()); if (!mem) abort();
    binary_sink_t a = {0,0,0,0}, b = {1,0,0,0};
    if (!encode_set(seq, mem, &a, 0) || !encode_set(seq, mem, &b, 1)) abort();
    uint32_t total = binary_size(binary[0]);
    if (total != binary_size(binary[1]) || memcmp(binary[0], binary[1], total) ||
        a.header != 1 || b.header != 1) abort();
    fm1_state_report_t report; fm1_state_report_init(&report);
    if (!fm1_state_bin_read(binary_read, &total, total, discard_record, NULL, &report, 0)) abort();
    unsigned calls = b.calls;
    for (unsigned cut = 1; cut <= calls; ++cut) {
        b = (binary_sink_t){1,0,cut,0};
        if (encode_set(seq, mem, &b, 1) || b.calls != cut || b.header) abort();
    }
    printf("binary_bytes=%u binary_write_failures=%u\n", total, calls);
    free(mem);
}
int main(int argc, char **argv) {
    fm1_seq_limits_t limits; fm1_seq_t *s;
    size_t bytes, need, count, callbacks;
    void *mem, *before;
    FILE *f;
    if (argc != 3 && argc != 4 && argc != 5) return 1;
    records_mode = argc == 5 ? atoi(argv[4]) : 0;
    if (fm1_state_seq_export(NULL, record_output, NULL) || fm1_state_seq_export(NULL, NULL, NULL)) return 15;
    f = fopen(argv[1], "rb"); if (!f) return 2;
    count = fread(input, 1, sizeof input, f); fclose(f);
    if (count == sizeof input) return 3;
    fm1_seq_limits_default(&limits, 8); limits.compat = (uint8_t)atoi(argv[2]);
    bytes = fm1_seq_size(&limits); mem = calloc(1, bytes); before = malloc(bytes);
    if (!mem || !before) return 4;
    s = fm1_seq_create(mem, &limits, 44118);
    if (!s || !fm1_seq_import_movy1(s, input, count)) return 5;
    if (fm1_state_seq_export(s, NULL, NULL)) return 16;
    memcpy(before, mem, bytes);
    need = fm1_seq_export_movy1(s, expected, sizeof expected);
    if (need >= sizeof expected || need != fm1_seq_export_movy1(s, NULL, 0)) return 6;
    /* Existing truncation and terminating-NUL behavior must stay intact. */
    for (size_t cap = 0; cap < 16; ++cap) {
        memset(actual, 0x5a, 32);
        if (fm1_seq_export_movy1(s, actual, cap) != need) return 7;
        if (cap && (actual[cap - 1] != 0 || memcmp(actual, expected, cap - 1))) return 8;
        if ((unsigned char)actual[cap] != 0x5a) return 9;
    }
    output_t o = {0, 0, 0, 0}; size_t length = 123;
    if (export_api(s, output, &o, &length) ||
        length != need || o.len != need || memcmp(actual, expected, need) ||
        memcmp(before, mem, bytes)) return 10;
    if (records_mode) codec_check(s);
    callbacks = o.calls;
    size_t failures = 0;
    for (size_t fail = 1; fail <= callbacks; ++fail) {
        if (argc >= 4 && atoi(argv[3]) && fail != 1 && fail != callbacks && fail % 1024) continue;
        for (int mode = 0; mode < 3; ++mode) {
            ++failures;
            o = (output_t){0, 0, fail, mode}; length = 123;
            if (export_api(s, output, &o, &length) != -1 ||
                length || o.calls != fail || memcmp(actual, expected, o.len) ||
                memcmp(before, mem, bytes)) return 11;
        }
    }
    o = (output_t){0,0,0,0}; length = 123;
    if (export_api(NULL, output, &o, &length) != -1 || length || o.calls) return 12;
    length = 123;
    if (export_api(s, NULL, &o, &length) != -1 || length || o.calls) return 13;
    if (export_api(s, output, &o, NULL) != -1 || o.calls) return 14;
    printf("bytes=%zu callbacks=%zu injected_failures=%zu compat=%u records=%d\n", need, callbacks, failures, limits.compat, records_mode);
    free(mem); free(before); return 0;
}
