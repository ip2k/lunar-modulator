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
