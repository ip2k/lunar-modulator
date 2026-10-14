/* SPDX-License-Identifier: GPL-3.0-only */
/* Host-only NOR test adapter; never linked into device firmware. */
#ifndef LUNAR_NATIVE_PROJECT_SAVE_TEST_H
#define LUNAR_NATIVE_PROJECT_SAVE_TEST_H
#include "../../../firmware/native/project_save_app.h"
#include <assert.h>
#define TEST_PROJECT_SLOT 102400u
typedef struct {
    uint8_t bytes[2 * TEST_PROJECT_SLOT];
    unsigned operations;
    uint32_t read_base;
} native_save_test;
static int native_save_read(void *ctx, uint32_t off, void *p, uint32_t n) {
    native_save_test *s = ctx;
    assert(off <= sizeof s->bytes && n <= sizeof s->bytes - off);
    s->operations++;
    memcpy(p, s->bytes + off, n);
    return 0;
}
static int native_save_erase(void *ctx, uint32_t off) {
    native_save_test *s = ctx;
    assert(!(off % LP_SECTOR) && off <= sizeof s->bytes - LP_SECTOR);
    s->operations++;
    memset(s->bytes + off, 255, LP_SECTOR);
    return 0;
}
static int native_save_program(void *ctx, uint32_t off, const void *p, uint32_t n) {
    native_save_test *s = ctx;
    const uint8_t *b = p;
    uint32_t i;
    assert(n <= 256 && (off & 255u) + n <= 256);
    assert(off <= sizeof s->bytes && n <= sizeof s->bytes - off);
    s->operations++;
    for (i = 0; i < n; ++i) {
        assert((s->bytes[off+i] & b[i]) == b[i]);
        s->bytes[off+i] = b[i];
    }
    return 0;
}
static uint32_t native_save_source(void *ctx, uint32_t off, uint8_t *p, uint32_t n) {
    native_save_test *s = ctx;
    if (off > sizeof s->bytes - s->read_base ||
        n > sizeof s->bytes - s->read_base - off) return 0;
    return native_save_read(s, s->read_base + off, p, n) ? 0 : n;
}
static int native_save_discard(void *ctx, const fm1_rec_t *r) {
    (void)ctx; (void)r; return 1;
}
static int native_save_validate(void *ctx, uint32_t off, uint32_t n) {
    native_save_test *s = ctx;
    fm1_state_report_t report;
    s->read_base = off;
    fm1_state_report_init(&report);
    return fm1_state_bin_read(native_save_source, s, n, native_save_discard,
                              NULL, &report, 0) ? 0 : 1;
}
static int native_save_refuse(void *ctx, const fm1_rec_t *r) {
    unsigned *calls = ctx; (void)r; ++*calls; return 0;
}
static int native_project_test_save(FILE *f, fm1_app_t *app, fm1_state_report_t *rep) {
    native_save_test *s = malloc(sizeof *s);
    lunar_project_io io = {s, native_save_read, native_save_erase,
                           native_save_program, native_save_validate};
    lunar_project_store store;
    unsigned calls = 0, before, gate;
    uint32_t generation, length;
    int slot, ok = 0;
    if (!s) return 0;
    memset(s, 0, sizeof *s); memset(s->bytes, 255, sizeof s->bytes);
    /* Refusal must stop the actual collector, including the native adapter. */
    assert(!lunar_project_app_collect(app, native_save_refuse, &calls, rep));
    assert(calls == 1);
    assert(!lunar_project_app_collect(app, NULL, NULL, rep));
    assert(lunar_project_save_app(NULL, &io, TEST_PROJECT_SLOT, 1,1,1,1,rep) < 0);
    for (gate = 0; gate < 4; ++gate) {
        int guards[4] = {1,1,1,1}; guards[gate] = 0;
        assert(lunar_project_save_app(app, &io, TEST_PROJECT_SLOT,
            guards[0],guards[1],guards[2],guards[3],rep) < 0);
        assert(s->operations == 0);
    }
    if (lunar_project_save_app(app, &io, TEST_PROJECT_SLOT, 1,1,1,1,rep)) goto done;
    assert(!fm1_tft_pixels_valid(&app->tft));
    before = s->operations;
    /* Save again through recovery selection and inactive-slot replacement. */
    if (lunar_project_save_app(app, &io, TEST_PROJECT_SLOT, 1,1,1,1,rep)) goto done;
    assert(s->operations > before);
    memset(&store, 0, sizeof store); store.io = io; store.slot_bytes = TEST_PROJECT_SLOT;
    if (lunar_project_scan(&store, &slot, &generation, &length)) goto done;
    assert(slot == 1 && generation == 1);
    assert(lp_word(s->bytes) == LP_MAGIC && lp_word(s->bytes+28) == LP_COMMIT);
    assert(lp_word(s->bytes+TEST_PROJECT_SLOT+28) == LP_COMMIT);
    ok = fwrite(s->bytes + TEST_PROJECT_SLOT + LP_HEADER, 1, length, f) == length;
    fm1_app_draw_checked(app); assert(fm1_tft_pixels_valid(&app->tft));
done:
    free(s); return ok;
}
#endif
