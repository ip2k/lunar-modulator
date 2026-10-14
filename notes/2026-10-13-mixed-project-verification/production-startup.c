/* SPDX-License-Identifier: MIT. Host acceptance probe; not target timing proof. */
#include "fm1_app.h"
#include "project_boot.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static fm1_app_t app;
static unsigned char memory[216064] FM1_APP_ALIGN16;
static void *allocate(void *ctx, size_t bytes) {
    return lunar_instance_pool_alloc(ctx, bytes);
}
static void deallocate(void *ctx, void *ptr) { assert(lunar_instance_pool_free(ctx, ptr) == 0); }
typedef struct { const unsigned char *bytes; uint32_t size; fm1_state_names_t names;
    const fm1_engine_t *units[LUNAR_PROJECT_UNITS];
    const fm1_mod_kind_t *modules[FM1_MOD_POSITIONS]; unsigned missing;
} diagnostic_t;
static uint32_t pull(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
    diagnostic_t *d = ctx;
    if (off > d->size || n > d->size - off) return 0;
    memcpy(out, d->bytes + off, n); return n;
}
static int inspect_record(void *ctx, const fm1_rec_t *r) {
    diagnostic_t *d = ctx; int index = lunar_project_unit_index(r);
    if (r->type == FM1_REC_UNIT && index >= 0)
        d->units[index] = fm1_state_engine(&d->names, r->role, r->u.unit.id);
    if (r->type == FM1_REC_MODULE && r->slot < FM1_MOD_POSITIONS)
        d->modules[r->slot] = fm1_state_kind(&d->names, r->u.unit.id);
    if (r->type == FM1_REC_PARAM) {
        const fm1_param_t *params = NULL; unsigned count = 0; const char *id = "absent";
        if (r->role == FM1_ROLE_MODULE && r->slot < FM1_MOD_POSITIONS && d->modules[r->slot]) {
            const fm1_mod_kind_t *k = d->modules[r->slot]; params = k->params; count = k->n_params; id = k->id;
        } else if (index >= 0 && d->units[index]) {
            const fm1_engine_t *e = d->units[index]; params = e->params; count = e->n_params; id = e->id;
        }
        unsigned found = 0;
        for (unsigned i = 0; i < count; ++i) found |= params[i].uid == r->u.param.uid;
        if (!found) {
            ++d->missing;
            fprintf(stderr, "missing uid=%u owner=%s role=%u sound=%u slot=%u focus=%u\n",
                r->u.param.uid, id, r->role, r->sound, r->slot, r->u.param.focus);
        }
    }
    return 1;
}
int main(int argc, char **argv) {
    assert(argc == 2);
    FILE *file = fopen(argv[1], "rb"); assert(file);
    assert(fseek(file, 0, SEEK_END) == 0);
    long size = ftell(file); assert(size > 0 && size <= FM1_STATE_BIN_MAX);
    rewind(file); unsigned char *bytes = malloc((size_t)size); assert(bytes);
    assert(fread(bytes, 1, (size_t)size, file) == (size_t)size); fclose(file);
    diagnostic_t diagnostic = {0};
    diagnostic.bytes = bytes; diagnostic.size = (uint32_t)size;
    fm1_state_names_default(&diagnostic.names);
    fm1_state_report_t diagnostic_report;
    fm1_state_report_init(&diagnostic_report);
    assert(fm1_state_bin_read(pull, &diagnostic, diagnostic.size, inspect_record,
        &diagnostic, &diagnostic_report, 0));
    lunar_instance_pool_t pool;
    fm1_state_report_t report;
    fm1_app_init(&app, 44118);
    assert(lunar_instance_pool_init(&pool, memory, sizeof memory) == 0);
    assert(fm1_app_set_storage(&app, &pool, allocate, deallocate) == 0);
    int ok = lunar_project_start(&app, &pool, bytes, (uint32_t)size, 44118, &report);
    if (!ok) fprintf(stderr, "production startup: %u %s\n", report.code, report.what);
    assert(ok && report.code == FM1_STATE_OK);
    free(bytes);
    for (int sound = 0; sound < FM1_APP_SOUNDS; ++sound)
        assert(app.unit[fm1_app_sound_unit(sound)].e);
    fm1_seq_info_t info; fm1_seq_get_info(app.seq, &info); assert(!info.playing);
    assert(fm1_app_seq_line(&app, "play", 4) == 4);
    double energy = 0;
    for (unsigned block = 0; block < 4096; ++block) {
        const float *samples = fm1_app_render(&app, 64);
        for (unsigned n = 0; n < 128; ++n) {
            assert(isfinite(samples[n])); energy += samples[n] * samples[n];
        }
    }
    assert(energy > 0.0001 && fm1_app_seq_dropped(&app) == 0);
    assert(fm1_app_seq_line(&app, "stop", 4) == 4);
    fm1_app_all_notes_off(&app);
    unsigned allocations = pool.live_allocations;
    size_t live_bytes = pool.live_bytes;
    for (int unit = 0; unit < FM1_APP_UNITS; ++unit) {
        if (app.unit[unit].e) app.unit[unit].e->destroy(app.unit[unit].self);
        if (app.unit[unit].mem) deallocate(&pool, app.unit[unit].mem);
    }
    assert(!pool.live_allocations && !pool.live_bytes);
    printf("{\"passed\":true,\"energy\":%.9g,\"pool_bytes\":%zu,\"allocations\":%u,\"target_timing_verified\":false}\n", energy, live_bytes, allocations);
    return 0;
}
