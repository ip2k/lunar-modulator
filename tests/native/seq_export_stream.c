/* Stream export equivalence and every-callback failure, without live mutation. */
#include "fm1_seq.h"
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
int main(int argc, char **argv) {
    fm1_seq_limits_t limits; fm1_seq_t *s;
    size_t bytes, need, count, callbacks;
    void *mem, *before;
    FILE *f;
    if (argc != 3 && argc != 4) return 1;
    f = fopen(argv[1], "rb"); if (!f) return 2;
    count = fread(input, 1, sizeof input, f); fclose(f);
    if (count == sizeof input) return 3;
    fm1_seq_limits_default(&limits, 8); limits.compat = (uint8_t)atoi(argv[2]);
    bytes = fm1_seq_size(&limits); mem = calloc(1, bytes); before = malloc(bytes);
    if (!mem || !before) return 4;
    s = fm1_seq_create(mem, &limits, 44118);
    if (!s || !fm1_seq_import_movy1(s, input, count)) return 5;
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
    if (fm1_seq_export_movy1_stream(s, output, &o, &length) ||
        length != need || o.len != need || memcmp(actual, expected, need) ||
        memcmp(before, mem, bytes)) return 10;
    callbacks = o.calls;
    size_t failures = 0;
    for (size_t fail = 1; fail <= callbacks; ++fail) {
        if (argc == 4 && fail != 1 && fail != callbacks && fail % 1024) continue;
        for (int mode = 0; mode < 3; ++mode) {
            ++failures;
            o = (output_t){0, 0, fail, mode}; length = 123;
            if (fm1_seq_export_movy1_stream(s, output, &o, &length) != -1 ||
                length || o.calls != fail || memcmp(actual, expected, o.len) ||
                memcmp(before, mem, bytes)) return 11;
        }
    }
    o = (output_t){0,0,0,0}; length = 123;
    if (fm1_seq_export_movy1_stream(NULL, output, &o, &length) != -1 || length || o.calls) return 12;
    length = 123;
    if (fm1_seq_export_movy1_stream(s, NULL, &o, &length) != -1 || length || o.calls) return 13;
    if (fm1_seq_export_movy1_stream(s, output, &o, NULL) != -1 || o.calls) return 14;
    printf("bytes=%zu callbacks=%zu injected_failures=%zu compat=%u\n", need, callbacks, failures, limits.compat);
    free(mem); free(before); return 0;
}
