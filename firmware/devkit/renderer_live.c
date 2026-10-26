/* SPDX-License-Identifier: MIT
 * Actual shared renderer workload, replayable unchanged on host and dev kit.
 * No SDK, logging, allocation or DAC dependency in this translation unit. */
#include "renderer_live.h"
#include "fm1_app.h"
#include "fm1_dx7_kernel.h"
#ifdef LUNAR_DEVKIT_ENGINE_QUEUE
#include "renderer_queue_bridge.h"
#if LUNAR_RENDERER_WORKLOAD != 0
#error Whole-engine queue requires the fixed mixed arrangement
#endif
#endif
#include <string.h>

#if !FM1_APP_EXTERNAL_ARENAS
#error The dev-kit renderer requires caller-owned arenas in every translation unit
#endif
#define RATE 44100u
#define BLOCK 64u
#define CASE_BLOCKS ((8u * RATE + BLOCK - 1u) / BLOCK)
#ifndef LUNAR_RENDERER_POOL_BYTES
#define LUNAR_RENDERER_POOL_BYTES (148u * 1024u)
#endif
#define POOL_BYTES LUNAR_RENDERER_POOL_BYTES
static fm1_app_t app;
static unsigned char pool[POOL_BYTES] FM1_APP_ALIGN16;
static struct lunar_renderer_status state;
static uint32_t case_block, startup_frames, hash;
static int ready;
static const fm1_dx7_kernel_adapter_t *kernel_adapter;
int lunar_devkit_renderer_kernel_adapter(const fm1_dx7_kernel_adapter_t *adapter) {
    if (ready || (adapter && !adapter->render_pair)) return 0;
    kernel_adapter = adapter;
    return 1;
}
static const unsigned voices[] = {1, 4, 8, 12};
static int units[8];
static unsigned active_units;

#ifdef LUNAR_RENDERER_PROFILE
#ifndef FM1_APP_RENDER_PROFILE
#error Renderer profiling requires the shared app observer
#endif
static struct lunar_renderer_profile profile[FM1_APP_UNITS + FM1_APP_PROFILE_STAGES];
static uint32_t profile_start[FM1_APP_UNITS + FM1_APP_PROFILE_STAGES];
static uint32_t (*profile_now)(void);
typedef char lunar_stage_count_check[
    LUNAR_RENDERER_PROFILE_STAGES == FM1_APP_PROFILE_STAGES ? 1 : -1];
static uint32_t last_stage[LUNAR_RENDERER_PROFILE_STAGES];
static uint32_t last_unit[FM1_APP_UNITS];
static struct lunar_renderer_profile detail[LUNAR_RENDERER_DETAIL_REGIONS];
static uint32_t last_detail[LUNAR_RENDERER_DETAIL_REGIONS];
void lunar_devkit_renderer_detail_read(unsigned region, struct lunar_renderer_profile *out) {
    if (region < LUNAR_RENDERER_DETAIL_REGIONS) *out = detail[region];
    else memset(out, 0, sizeof *out);
}
uint32_t lunar_devkit_renderer_detail_last(unsigned region) {
    return region < LUNAR_RENDERER_DETAIL_REGIONS ? last_detail[region] : 0;
}
#ifdef LUNAR_RENDERER_PREP_PROFILE
static struct lunar_renderer_profile prep[LUNAR_RENDERER_PREP_REGIONS];
static uint32_t prep_start[LUNAR_RENDERER_PREP_REGIONS];
static uint32_t last_prep[LUNAR_RENDERER_PREP_REGIONS];
static int prep_active;
void lunar_devkit_prep_profile(unsigned region, int entering) {
    if (!prep_active) return; /* Exclude setup before the measured render. */
    if (region >= LUNAR_RENDERER_PREP_REGIONS) { ++state.invalid; return; }
    uint32_t tick = profile_now ? profile_now() : 0;
    if (entering) prep_start[region] = tick;
    else {
        uint32_t elapsed = tick - prep_start[region];
        struct lunar_renderer_profile *p = &prep[region];
        p->ticks += elapsed; ++p->calls;
        last_prep[region] += elapsed;
        if (elapsed > p->max_ticks) p->max_ticks = elapsed;
    }
}
void lunar_devkit_renderer_prep_read(unsigned region, struct lunar_renderer_profile *out) {
    if (region < LUNAR_RENDERER_PREP_REGIONS) *out = prep[region];
    else memset(out, 0, sizeof *out);
}
uint32_t lunar_devkit_renderer_prep_last(unsigned region) {
    return region < LUNAR_RENDERER_PREP_REGIONS ? last_prep[region] : 0;
}
#define PREP(region, entering) lunar_devkit_prep_profile(region, entering)
#else
#define PREP(region, entering) ((void)0)
#endif
#ifdef LUNAR_RENDERER_ENGINE_PROFILE
static struct lunar_renderer_profile engine_profile[LUNAR_RENDERER_ENGINE_REGIONS];
static uint32_t engine_start[LUNAR_RENDERER_ENGINE_REGIONS];
void lunar_devkit_engine_profile(unsigned region, uint32_t frames, int entering) {
    if (region >= LUNAR_RENDERER_ENGINE_REGIONS) { ++state.invalid; return; }
    uint32_t tick = profile_now ? profile_now() : 0;
    if (entering) engine_start[region] = tick;
    else {
        uint32_t elapsed = tick - engine_start[region];
        struct lunar_renderer_profile *p = &engine_profile[region];
        p->ticks += elapsed;
        ++p->calls; p->frames += frames;
        if (elapsed > p->max_ticks) p->max_ticks = elapsed;
    }
}
void lunar_devkit_renderer_engine_read(unsigned region, struct lunar_renderer_profile *out) {
    if (region < LUNAR_RENDERER_ENGINE_REGIONS) *out = engine_profile[region];
    else memset(out, 0, sizeof *out);
}
#endif
void lunar_devkit_renderer_profile_clock(uint32_t (*now)(void)) { profile_now = now; }
void lunar_devkit_renderer_profile_read(unsigned unit, struct lunar_renderer_profile *out) {
    if (unit < active_units) *out = profile[units[unit]];
    else memset(out, 0, sizeof *out);
}
uint32_t lunar_devkit_renderer_unit_last(unsigned unit) {
    return unit < active_units ? last_unit[units[unit]] : 0;
}
void lunar_devkit_renderer_profile_reset(void) {
    memset(profile, 0, sizeof profile);
    memset(last_stage, 0, sizeof last_stage);
    memset(last_unit, 0, sizeof last_unit);
    memset(detail, 0, sizeof detail);
    memset(last_detail, 0, sizeof last_detail);
#ifdef LUNAR_RENDERER_PREP_PROFILE
    memset(prep, 0, sizeof prep);
    memset(prep_start, 0, sizeof prep_start);
    memset(last_prep, 0, sizeof last_prep);
#endif
#ifdef LUNAR_RENDERER_ENGINE_PROFILE
    memset(engine_profile, 0, sizeof engine_profile);
#endif
}
unsigned lunar_devkit_renderer_profile_stages(void) { return FM1_APP_PROFILE_STAGES; }
void lunar_devkit_renderer_stage_read(unsigned stage, struct lunar_renderer_profile *out) {
    if (stage < FM1_APP_PROFILE_STAGES) *out = profile[FM1_APP_UNITS + stage];
    else memset(out, 0, sizeof *out);
}
uint32_t lunar_devkit_renderer_stage_last(unsigned stage) {
    return stage < LUNAR_RENDERER_PROFILE_STAGES ? last_stage[stage] : 0;
}
void fm1_app_render_profile(unsigned unit, uint32_t frames, int entering) {
    if (unit >= FM1_APP_UNITS + FM1_APP_PROFILE_STAGES) { ++state.invalid; return; }
    uint32_t tick = profile_now ? profile_now() : 0;
    if (entering) profile_start[unit] = tick;
    else {
        uint32_t elapsed = tick - profile_start[unit];
        if (unit >= FM1_APP_UNITS) last_stage[unit - FM1_APP_UNITS] = elapsed;
        else last_unit[unit] += elapsed;
        struct lunar_renderer_profile *p = &profile[unit];
        p->ticks += elapsed;
        ++p->calls; p->frames += frames;
        if (elapsed > p->max_ticks) p->max_ticks = elapsed;
    }
}
#endif

#ifndef LUNAR_RENDERER_PROFILE
#define PREP(region, entering) ((void)0)
#endif
static int line(const char *ops) {
    size_t n = strlen(ops);
    return fm1_app_seq_line(&app, ops, n) == n;
}

static int mod(const char *ops) {
    char error[96];
    return fm1_app_mod_line(&app, ops, error, sizeof error);
}

int lunar_devkit_renderer_init(void) {
    /* Reinitializing live instances is deliberately unsupported. */
    if (ready) return 0;
#ifdef LUNAR_DEVKIT_ENGINE_QUEUE
    if (kernel_adapter) return 0; /* No nested FM6 worker. */
#endif
    const fm1_host_t host = {FM1_ENGINE_API_VERSION, (float)RATE, BLOCK};
    fm1_app_arena_t arenas[FM1_APP_UNITS];
#if LUNAR_RENDERER_WORKLOAD == 1
    const char *ids[] = {"dx7", "filter", "echo", "comp"};
    const int selected[] = {fm1_app_sound_unit(0), fm1_app_insert_unit(0, 0), 1, 2};
#else
    const char *ids[] = {"dx7", "macro", "drums", "dx7", "filter", "drive", "echo", "comp"};
    const int selected[] = {fm1_app_sound_unit(0), fm1_app_sound_unit(1),
        fm1_app_sound_unit(2), fm1_app_sound_unit(3),
        fm1_app_insert_unit(0, 0), fm1_app_insert_unit(1, 0), 1, 2};
#endif
    active_units = sizeof selected / sizeof selected[0];
    memcpy(units, selected, sizeof selected);
    size_t used = 0;
    memset(arenas, 0, sizeof arenas);
    memset(&state, 0, sizeof state);
    for (unsigned i = 0; i < active_units; ++i) {
        const fm1_engine_t *e = fm1_engine_find(ids[i]);
        if (!e) { state.init_error = 1; return 0; }
        size_t bytes = e->instance_size(&host);
        state.unit_bytes[i] = (uint32_t)bytes;
        state.arena_bytes = (uint32_t)used;
        if (!bytes || bytes > sizeof pool || used > sizeof pool - bytes) { state.init_error = 2; return 0; }
        arenas[units[i]].mem = pool + used;
        arenas[units[i]].bytes = bytes;
        used = (used + bytes + 15u) & ~(size_t)15u;
        if (used > sizeof pool) { state.init_error = 2; return 0; }
    }
    if (fm1_app_init_arenas(&app, (float)RATE, arenas)) { state.init_error = 3; return 0; }
    for (unsigned i = 0; i < active_units; ++i)
        if (fm1_app_select(&app, units[i], fm1_app_find(ids[i]))) { state.init_error = 4 + i; return 0; }
    for (unsigned i = 0; i < active_units; ++i)
        if (!strcmp(ids[i], "dx7"))
            fm1_dx7_set_kernel_adapter(app.unit[units[i]].self, kernel_adapter);
    state.arena_bytes = (uint32_t)used;
    /* Fixed patches/models and modest wet levels for the named arrangement. */
    fm1_app_set_param(&app, units[0], 0, 19); /* electric piano */
#if LUNAR_RENDERER_WORKLOAD == 0
    fm1_app_set_param(&app, units[1], 0, 0);  /* VA model */
    fm1_app_set_param(&app, units[3], 0, 25); /* pad */
    fm1_app_set_param(&app, units[5], 3, .15f);
#endif
    fm1_app_set_param(&app, 1, 3, .12f);
    for (int s = 0; s < (LUNAR_RENDERER_WORKLOAD == 1 ? 1 : 4); ++s) {
        fm1_app_unit_set_level(&app, s, s == 2 ? 45.f : 55.f);
        if (fm1_app_unit_route(&app, s, s) < 0) { state.init_error = 20; return 0; }
    }
    /* Each line is a small bounded setup transaction. No text parser in IRQ. */
    if (!line("tog 0 0 48 100;tog 0 4 55 85;tog 0 8 58 95;tog 0 12 53 80")) {
        state.init_error = 21; return 0;
    }
#if LUNAR_RENDERER_WORKLOAD == 0
    if (!line("tog 1 0 36 100;tog 1 6 43 80;tog 1 8 34 95;tog 1 14 41 75") ||
        !line("tog 2 0 36 100;tog 2 4 37 85;tog 2 8 36 95;tog 2 12 37 90") ||
        !line("tog 3 0 60 75;tog 3 8 58 80")) { state.init_error = 21; return 0; }
    if (!mod("slot 3 lfo1 > snd2:Timbre amt=20") ||
        !mod("slot 4 env3 > snd1.fx1:Cutoff amt=15")) { state.init_error = 22; return 0; }
#else
    if (!mod("slot 3 lfo1 > snd1:Brightness amt=20") ||
        !mod("slot 4 env3 > snd1.fx1:Cutoff amt=15")) { state.init_error = 22; return 0; }
#endif
    fm1_app_button(&app, FM1_BTN_PLAY, 1);
    fm1_app_button(&app, FM1_BTN_PLAY, 0);
    case_block = startup_frames = 0;
    hash = 2166136261u;
    ready = 1;
    return 1;
}

void lunar_devkit_renderer_render(int16_t *out) {
#ifdef LUNAR_DEVKIT_ENGINE_QUEUE
    if (lunar_renderer_queue_error()) return;
#endif
    if (!ready) { memset(out, 0, BLOCK * 4u * sizeof *out); return; }
#ifdef LUNAR_RENDERER_PROFILE
    uint32_t boundary[4];
    boundary[0] = profile_now ? profile_now() : 0;
    memset(last_unit, 0, sizeof last_unit);
#endif
#ifdef LUNAR_RENDERER_PREP_PROFILE
    memset(last_prep, 0, sizeof last_prep);
    prep_active = 1;
#endif
    /* Density increases every eight seconds; ongoing sequencer notes and
     * release tails remain active. Control edits use the app's real API. */
    if (!case_block) {
        PREP(0, 1);
        for (unsigned n = 0; n < voices[state.test_case]; ++n)
            fm1_app_unit_note_on(&app, 0, 48 + (int)n, 90);
        state.controls += voices[state.test_case];
        PREP(0, 0);
    }
    if (case_block == (6u * RATE / BLOCK)) {
        PREP(1, 1);
        for (unsigned n = 0; n < voices[state.test_case]; ++n)
            fm1_app_unit_note_off(&app, 0, 48 + (int)n);
        state.controls += voices[state.test_case];
        PREP(1, 0);
    }
    if (!(case_block % 64u)) {
        PREP(2, 1);
        fm1_app_unit_set_level(&app, LUNAR_RENDERER_WORKLOAD == 1 ? 0 : 1,
                               (case_block & 64u) ? 45.f : 55.f);
        PREP(2, 0);
        PREP(3, 1);
        fm1_app_set_param(&app, fm1_app_insert_unit(0, 0), 1,
                          (case_block & 64u) ? 1200.f : 2400.f);
        PREP(3, 0);
        state.controls += 2;
    }
#ifdef LUNAR_RENDERER_PROFILE
    boundary[1] = profile_now ? profile_now() : 0;
#endif
    const float *samples = fm1_app_render(&app, BLOCK);
#ifdef LUNAR_DEVKIT_ENGINE_QUEUE
    if (!samples || lunar_renderer_queue_error()) return;
#endif
#ifdef LUNAR_RENDERER_PROFILE
    boundary[2] = profile_now ? profile_now() : 0;
#endif
    for (unsigned i = 0; i < BLOCK; ++i) for (unsigned ch = 0; ch < 2; ++ch) {
        float x = samples[2 * i + ch];
        uint32_t bits; memcpy(&bits, &x, sizeof bits);
        if ((bits & 0x7f800000u) == 0x7f800000u) { ++state.invalid; x = 0; }
        x *= 4096.f;
        if (startup_frames + i < 2205u) x *= (startup_frames + i + 1) / 2205.f;
        if (x > 32767.f) { ++state.clipped; x = 32767.f; }
        if (x < -32768.f) { ++state.clipped; x = -32768.f; }
        out[4 * i + ch] = out[4 * i + ch + 2] = (int16_t)x;
        uint16_t word = (uint16_t)out[4 * i + ch];
        hash = (hash ^ (word & 255u)) * 16777619u;
        hash = (hash ^ (word >> 8)) * 16777619u;
    }
#ifdef LUNAR_RENDERER_PROFILE
    boundary[3] = profile_now ? profile_now() : 0;
    /* Aggregate after all boundary samples: no accounting work is charged
     * to a subsequent region. Unsigned subtraction handles timer wrap. */
    for (unsigned i = 0; i < LUNAR_RENDERER_DETAIL_REGIONS; ++i) {
        uint32_t elapsed = boundary[i + 1] - boundary[i];
        struct lunar_renderer_profile *p = &detail[i];
        last_detail[i] = elapsed;
        p->ticks += elapsed; ++p->calls; p->frames += BLOCK;
        if (elapsed > p->max_ticks) p->max_ticks = elapsed;
    }
#endif
#ifdef LUNAR_RENDERER_PREP_PROFILE
    prep_active = 0;
#endif
    if (startup_frames < 2205u) startup_frames += BLOCK;
    ++state.blocks;
    if (++case_block == CASE_BLOCKS) {
        state.completed_case = state.test_case;
        state.completed_hash = hash;
        ++state.completed_cases;
        hash = 2166136261u;
        case_block = 0;
        if (++state.test_case == 4) { state.test_case = 0; ++state.cycles; }
    }
}

void lunar_devkit_renderer_status(struct lunar_renderer_status *out) { *out = state; }
