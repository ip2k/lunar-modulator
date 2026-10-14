#include "project_start.h"
#include <string.h>
#include <math.h>
#include "fm1_modules.h"
#include "project_mod.h"

#if FM1_APP_EXTERNAL_ARENAS
typedef char parameter_capacity_match[
    FM1_APP_MAX_PARAMS == LUNAR_PROJECT_ENGINE_PARAMS ? 1 : -1];

typedef struct {
    const uint8_t *bytes;
    uint32_t size;
    fm1_state_report_t *report;
    float level[FM1_APP_SOUNDS];
    uint8_t levels, session;
    int8_t current, octave, transpose;
} scalar_load_t;

static int scalar_refuse(scalar_load_t *load, const char *why) {
    load->report->code = FM1_STATE_BAD;
    strncpy(load->report->what, why, sizeof load->report->what - 1u);
    load->report->what[sizeof load->report->what - 1u] = 0;
    return 0;
}

static uint32_t scalar_read(void *ctx, uint32_t off, uint8_t *buf, uint32_t n) {
    scalar_load_t *load = ctx;
    if (off > load->size || n > load->size - off) return 0;
    memcpy(buf, load->bytes + off, n);
    return n;
}

static int scalar_record(void *ctx, const fm1_rec_t *r) {
    scalar_load_t *load = ctx;
    if (r->type == FM1_REC_HEAD)
        return r->u.head.kind == FM1_STATE_PROJECT ||
               scalar_refuse(load, "expected a binary project");
    if (r->type == FM1_REC_LEVEL) {
        float value;
        if (r->sound >= FM1_APP_SOUNDS || (load->levels & (1u << r->sound)))
            return scalar_refuse(load, "invalid or duplicate sound level");
        if ((r->u.level & 0x7f800000u) == 0x7f800000u)
            return scalar_refuse(load, "nonfinite sound level");
        memcpy(&value, &r->u.level, sizeof value);
        if (value < 0.0f || value > FM1_APP_LEVEL_MAX)
            return scalar_refuse(load, "sound level would be clamped");
        load->level[r->sound] = value;
        load->levels |= (uint8_t)(1u << r->sound);
    } else if (r->type == FM1_REC_SESSION) {
        if (load->session || r->u.session.current < 0 ||
            r->u.session.current >= FM1_APP_SOUNDS ||
            r->u.session.octave < -3 || r->u.session.octave > 3 ||
            r->u.session.transpose < -12 || r->u.session.transpose > 12)
            return scalar_refuse(load, "invalid or duplicate project session");
        load->session = 1;
        load->current = r->u.session.current;
        load->octave = r->u.session.octave;
        load->transpose = r->u.session.transpose;
    }
    return 1;
}

static int scalar_overlap(const void *a, size_t an, const void *b, size_t bn) {
    uintptr_t al = (uintptr_t)a, bl = (uintptr_t)b;
    uintptr_t ah = al + an, bh = bl + bn;
    return ah < al || bh < bl || (al < bh && bl < ah);
}

int lunar_project_restore_scalars(fm1_app_t *app,
                                  const uint8_t *bytes, uint32_t size,
                                  fm1_state_report_t *report) {
    scalar_load_t load;
    /* Check output aliasing before even initializing the report. */
    if (!report || (app && scalar_overlap(app, sizeof *app, report, sizeof *report)) ||
        (bytes && scalar_overlap(bytes, size, report, sizeof *report))) return 0;
    fm1_state_report_init(report);
    if (!app || !bytes || app->frames || size > FM1_STATE_BIN_MAX ||
        scalar_overlap(app, sizeof *app, bytes, size)) {
        report->code = size > FM1_STATE_BIN_MAX ? FM1_STATE_TOO_BIG : FM1_STATE_BAD;
        return 0;
    }
    memset(&load, 0, sizeof load);
    load.bytes = bytes; load.size = size; load.report = report;
    if (!fm1_state_bin_read(scalar_read, &load, size, scalar_record, &load, report, 0))
        return 0;
    /* The complete reader/CRC succeeded; no operation below can refuse. */
    for (unsigned k = 0; k < FM1_APP_SOUNDS; ++k)
        if (load.levels & (1u << k)) fm1_app_unit_set_level(app, (int)k, load.level[k]);
    if (load.session) {
        fm1_app_unit_set_current(app, load.current);
        app->octave = load.octave; app->transpose = load.transpose;
        app->dirty = app->leds_changed = 1;
    }
    return 1;
}

int lunar_project_restore_mod(fm1_app_t *app, const uint8_t *bytes, uint32_t size,
                              fm1_state_report_t *report) {
    fm1_state_names_t names;
    lunar_project_units_t plan;
    fm1_mod_t *mod;
    uint32_t seed;
    if (!report || (app && scalar_overlap(app, sizeof *app, report, sizeof *report)) ||
        (bytes && scalar_overlap(bytes, size, report, sizeof *report))) return 0;
    fm1_state_report_init(report);
    if (!app || !bytes || app->frames || size > FM1_STATE_BIN_MAX ||
        scalar_overlap(app, sizeof *app, bytes, size)) {
        report->code = size > FM1_STATE_BIN_MAX ? FM1_STATE_TOO_BIG : FM1_STATE_BAD;
        return 0;
    }
    fm1_state_names_default(&names);
    if (!lunar_project_units_plan(bytes, size, &names, &app->host, &plan, report)) return 0;
    for (unsigned i = 0; i < LUNAR_PROJECT_UNITS; ++i) {
        const fm1_engine_t *installed;
        if (i < 14u) {
            int slot = i < 4u ? fm1_app_sound_unit((int)i) :
                       i < 12u ? fm1_app_insert_unit((int)((i - 4u) / 2u), (int)((i - 4u) % 2u)) :
                       1 + (int)(i - 12u);
            installed = app->unit[slot].e;
        } else {
            const fm1_mfx_slot_t *slot = fm1_mfx_slot(&app->mfx, i - 14u, 0);
            installed = slot && slot->fx ? &slot->fx->engine : NULL;
        }
        if (installed != plan.engine[i]) {
            report->code = FM1_STATE_BAD;
            strncpy(report->what, "project engines differ from installed app", sizeof report->what - 1u);
            return 0;
        }
    }
    if (!fm1_app_mod_prepare_cold(app)) { report->code = FM1_STATE_BAD; return 0; }
    mod = lunar_project_mod_stage_seeded(bytes, size, &names, &app->host,
                                         app->mod_mem, sizeof app->mod_mem, report, &seed);
    if (!mod) return 0;
    if (fm1_app_mod_adopt_cold(app, mod, seed)) return 1;
    fm1_mod_destroy(mod);
    report->code = FM1_STATE_BAD;
    return 0;
}

typedef struct {
    scalar_load_t input;
    lunar_project_dx7_scratch_t *scratch;
    int available;
} dx7_load_t;

static int dx7_record(void *ctx, const fm1_rec_t *r) {
    dx7_load_t *load = ctx;
    if (r->type == FM1_REC_HEAD)
        return r->u.head.kind == FM1_STATE_PROJECT ||
               scalar_refuse(&load->input, "expected a binary project");
    if (r->type != FM1_REC_DX7) return 1;
    if (!load->available || r->slot >= FM1_DX7_USER_SLOTS ||
        (load->scratch->seen & (1u << r->slot)))
        return scalar_refuse(&load->input, "missing FM6 or invalid duplicate voice slot");
    /* state_bin validates all 145 field ranges and ten printable name bytes
     * before emitting this record. Keep the codec as the validation authority. */
    memcpy(load->scratch->voice[r->slot], r->u.dx7.vced, FM1_DX7_VCED_BYTES);
    load->scratch->seen |= 1u << r->slot;
    return 1;
}

int lunar_project_restore_dx7(fm1_app_t *app, const uint8_t *bytes, uint32_t size,
                              lunar_project_dx7_scratch_t *scratch,
                              fm1_state_report_t *report) {
    dx7_load_t load;
    if (!report || (app && scalar_overlap(app, sizeof *app, report, sizeof *report)) ||
        (bytes && scalar_overlap(bytes, size, report, sizeof *report)) ||
        (scratch && scalar_overlap(scratch, sizeof *scratch, report, sizeof *report))) return 0;
    fm1_state_report_init(report);
    if (!app || !bytes || !scratch || app->frames || size > FM1_STATE_BIN_MAX ||
        scalar_overlap(app, sizeof *app, bytes, size) ||
        scalar_overlap(app, sizeof *app, scratch, sizeof *scratch) ||
        scalar_overlap(bytes, size, scratch, sizeof *scratch) || ((uintptr_t)scratch & 3u)) {
        report->code = size > FM1_STATE_BIN_MAX ? FM1_STATE_TOO_BIG : FM1_STATE_BAD;
        return 0;
    }
    memset(&load, 0, sizeof load);
    load.input.bytes = bytes; load.input.size = size; load.input.report = report;
    load.scratch = scratch;
    load.available = FM1_WITH_DX7 && app->dx7.index >= 0;
    memset(scratch, 0, sizeof *scratch);
    if (!fm1_state_bin_read(scalar_read, &load.input, size, dx7_record, &load, report, 0))
        return 0;
    for (unsigned k = 0; k < FM1_DX7_USER_SLOTS; ++k)
        if (scratch->seen & (1u << k))
            if (fm1_app_dx7_put(app, k, scratch->voice[k]) != 0) return 0;
    return 1;
}

int lunar_project_restore_midi_units(fm1_app_t *app,
                                    const lunar_project_engines_t *candidate,
                                    const uint8_t on[FM1_APP_SOUNDS]) {
    const fm1_midi_fx_t *fx[FM1_APP_SOUNDS] = {0};
    size_t ram, old = 0, next = 0;
    if (!app || !candidate || !on || app->frames) return FM1_APP_SELECT_BAD;
    uintptr_t al = (uintptr_t)app, ah = al + sizeof *app;
    uintptr_t cl = (uintptr_t)candidate, ch = cl + sizeof *candidate;
    uintptr_t ol = (uintptr_t)on, oh = ol + FM1_APP_SOUNDS;
    if (ah < al || ch < cl || oh < ol || (al < ch && cl < ah) ||
        (al < oh && ol < ah)) return FM1_APP_SELECT_BAD;
    for (unsigned k = 0; k < FM1_APP_SOUNDS; ++k) {
        const lunar_project_instance_t *from = &candidate->unit[14u + k];
        const fm1_mfx_slot_t *prior = fm1_mfx_slot(&app->mfx, k, 0);
        if (prior && prior->fx && prior->on)
            old += prior->fx->engine.instance_size(&app->ram_host);
        if (on[k] > 1u) return FM1_APP_SELECT_BAD;
        if (!from->engine) {
            if (on[k] || from->memory || from->self || from->bytes)
                return FM1_APP_SELECT_BAD;
            continue;
        }
        for (size_t i = 0; i < fm1_midi_fx_count; ++i)
            if (&fm1_midi_fxs[i]->engine == from->engine) fx[k] = fm1_midi_fxs[i];
        if (!fx[k]) return FM1_APP_SELECT_BAD;
        const fm1_engine_t *e = &fx[k]->engine;
        if (e->magic != FM1_ENGINE_MAGIC || e->api_version != FM1_ENGINE_API_VERSION ||
            e->kind != FM1_KIND_MIDI_FX || !fx[k]->process || !e->create || !e->destroy ||
            !e->instance_size || !e->set_param || e->n_params > FM1_APP_ARP_PARAMS ||
            (e->n_params && !e->params)) return FM1_APP_SELECT_BAD;
        size_t bytes = e->instance_size(&app->host);
        if (!bytes || bytes > FM1_APP_MFX_BYTES) return FM1_APP_SELECT_ARENA;
        for (unsigned i = 0; i < e->n_params; ++i) {
            float v = from->value[i]; const fm1_param_t *p = &e->params[i];
            if (!isfinite(v) || v < p->min || v > p->max ||
                (p->type == FM1_PARAM_ENUM && v != floorf(v))) return FM1_APP_SELECT_BAD;
        }
        if (on[k]) next += e->instance_size(&app->ram_host);
    }
    if (old) old += sizeof app->mfx;
    if (next) next += sizeof app->mfx;
    ram = fm1_app_ram(app);
    if (old > ram || next > FM1_APP_RAM_BUDGET ||
        ram - old > FM1_APP_RAM_BUDGET - next) return FM1_APP_SELECT_RAM;
    for (unsigned k = 0; k < FM1_APP_SOUNDS; ++k) {
        const fm1_mfx_slot_t *prior = fm1_mfx_slot(&app->mfx, k, 0);
        const fm1_engine_t *e = prior && prior->fx ? &prior->fx->engine : NULL;
        void *self = prior ? prior->self : NULL;
        fm1_mfx_set(&app->mfx, k, 0, NULL, NULL, 0, NULL);
        if (self && e && e->destroy) e->destroy(self);
        memset(app->mfx_mem[k], 0, FM1_APP_MFX_BYTES);
        memset(app->arp_value[k], 0, sizeof app->arp_value[k]);
        if (!fx[k]) continue;
        e = &fx[k]->engine;
        self = e->create(app->mfx_mem[k], &app->host);
        if (!self) return FM1_APP_SELECT_RATE;
        for (unsigned i = 0; i < e->n_params; ++i) {
            app->arp_value[k][i] = candidate->unit[14u + k].value[i];
            e->set_param(self, (uint16_t)i, app->arp_value[k][i]);
        }
        fm1_mfx_set(&app->mfx, k, 0, fx[k], self, on[k], NULL);
    }
    app->seq_host.mfx = &app->mfx;
    app->dirty = app->leds_changed = 1;
    return FM1_APP_SELECT_OK;
}

int lunar_project_adopt_audio_units(fm1_app_t *app,
                                    lunar_project_engines_t *candidate) {
    fm1_app_unit_t units[FM1_APP_UNITS];
    int result;
    if (!app || !candidate || !candidate->pool ||
        app->storage_ctx != candidate->pool) return FM1_APP_SELECT_BAD;
    /* Metadata/input must survive until every transfer has completed. */
    uintptr_t lo = (uintptr_t)candidate, hi = lo + sizeof *candidate;
    uintptr_t al = (uintptr_t)app, ah = al + sizeof *app;
    if (hi < lo || ah < al || (lo < ah && al < hi) ||
        (lo < candidate->pool->hi && candidate->pool->lo < hi))
        return FM1_APP_SELECT_BAD;
    memset(units, 0, sizeof units);
    for (int i = 0; i < FM1_APP_UNITS; ++i) units[i].index = -1;
    for (unsigned i = 0; i < 14u; ++i) {
        const lunar_project_instance_t *from = &candidate->unit[i];
        int slot = i < 4u ? fm1_app_sound_unit((int)i) :
                   i < 12u ? fm1_app_insert_unit((int)((i - 4u) / 2u), (int)((i - 4u) % 2u)) :
                   1 + (int)(i - 12u);
        fm1_app_unit_t *to = &units[slot];
        if (!from->engine) {
            if (from->memory || from->self || from->bytes) return FM1_APP_SELECT_BAD;
            continue;
        }
        size_t index;
        for (index = 0; index < fm1_engine_count; ++index)
            if (fm1_engines[index] == from->engine) break;
        if (index == fm1_engine_count) return FM1_APP_SELECT_BAD;
        to->e = from->engine; to->index = (int)index;
        to->mem = from->memory; to->self = from->self;
        to->bytes = to->cap = from->bytes;
        memcpy(to->value, from->value, sizeof to->value);
    }
    result = fm1_app_adopt_start_units(app, units);
    if (result != FM1_APP_SELECT_OK) return result;
    /* No operation after app transfer may refuse. */
    memset(candidate->unit, 0, 14u * sizeof candidate->unit[0]);
    return FM1_APP_SELECT_OK;
}
#endif
