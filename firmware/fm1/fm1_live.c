/* SPDX-License-Identifier: MIT
 * The FM-1 application's audio adapter (fm1_live.h). Derived from the
 * dev-kit adapter firmware/devkit/renderer_live.c (same arrangement, arenas,
 * cap8 and conversion), without its fixed four-case test pattern: nothing
 * plays until a key or a MIDI note does.
 */
#include "fm1_live.h"
#include "fm1_app.h"
#include "fm1_app_pipeline.h"
#include "fm1_dx7_budget.h"
#include "fm1_mod.h"
#include <string.h>

#if !FM1_APP_RENDER_PIPELINE && !defined(LUNAR_FM1_HOST_REFERENCE)
#error The FM-1 application needs the pipelined app (FM1_APP_RENDER_PIPELINE)
#endif
#if !FM1_APP_EXTERNAL_ARENAS
#error The FM-1 application requires caller-owned arenas in every translation unit
#endif

#define DX7_VOICES 8u   /* owner, 2026-10-29: eight guaranteed, twelve a goal */
#ifndef LUNAR_RENDERER_POOL_BYTES
#define LUNAR_RENDERER_POOL_BYTES (148u * 1024u)
#endif
#define FADE_FRAMES 2205u

static fm1_app_t app;
static unsigned char pool[LUNAR_RENDERER_POOL_BYTES] FM1_APP_ALIGN16;
static struct lunar_fm1_queue queue;
static struct lunar_fm1_router router;
static struct lunar_fm1_live_status state;
static int ready, bound;
static int units[8];

/* Consumer-only (CPU1 worker): never read by the producer while it runs. */
static uint32_t consume_next, fade, invalid, clipped;

uint32_t fm1_app_pipeline_error(void) { return lunar_pipeline_error(); }
void fm1_app_pipeline_fail(uint32_t code) { lunar_pipeline_fail_park(code); }

int lunar_fm1_live_init(void)
{
    static const char *const ids[8] = {"dx7", "macro", "drums", "dx7", "filter", "drive", "echo", "comp"};
    const fm1_host_t host = {FM1_ENGINE_API_VERSION, (float)LUNAR_FM1_RATE, LUNAR_FM1_BLOCK};
    fm1_app_arena_t arenas[FM1_APP_UNITS];
    size_t used = 0;
    unsigned i;
    if (ready) return 0;
    units[0] = fm1_app_sound_unit(0); units[1] = fm1_app_sound_unit(1);
    units[2] = fm1_app_sound_unit(2); units[3] = fm1_app_sound_unit(3);
    units[4] = fm1_app_insert_unit(0, 0); units[5] = fm1_app_insert_unit(1, 0);
    units[6] = 1; units[7] = 2;
    memset(arenas, 0, sizeof arenas);
    memset(&state, 0, sizeof state);
    for (i = 0; i < 8u; ++i) {
        const fm1_engine_t *e = fm1_engine_find(ids[i]);
        size_t bytes;
        if (!e) { state.init_error = 1; return 0; }
        bytes = e->instance_size(&host);
        if (!bytes || bytes > sizeof pool || used > sizeof pool - bytes) { state.init_error = 2; return 0; }
        arenas[units[i]].mem = pool + used;
        arenas[units[i]].bytes = bytes;
        used = (used + bytes + 15u) & ~(size_t)15u;
        if (used > sizeof pool) { state.init_error = 2; return 0; }
    }
    if (fm1_app_init_arenas(&app, (float)LUNAR_FM1_RATE, arenas)) { state.init_error = 3; return 0; }
    for (i = 0; i < 8u; ++i)
        if (fm1_app_select(&app, units[i], fm1_app_find(ids[i]))) { state.init_error = 4 + i; return 0; }
    for (i = 0; i < 8u; ++i)
        if (!strcmp(ids[i], "dx7") && !fm1_dx7_set_voice_limit(app.unit[units[i]].self, DX7_VOICES)) {
            state.init_error = 23; return 0;
        }
    state.dx7_voices = DX7_VOICES;
    /* The dev-kit pipeline's patches, models and wet levels. Sound 2's model
     * must stay 0 (VA): the pipelined Macro path refuses any other. */
    fm1_app_set_param(&app, units[0], 0, 19);   /* WARM PAD */
    fm1_app_set_param(&app, units[1], 0, 0);    /* VA model */
    fm1_app_set_param(&app, units[3], 0, 25);   /* SAW LEAD */
    fm1_app_set_param(&app, units[5], 3, .15f); /* Drive */
    fm1_app_set_param(&app, units[4], 1, LUNAR_FM1_CUTOFF_START);
    fm1_app_set_param(&app, units[4], 2, LUNAR_FM1_RESONANCE_START);
    fm1_app_set_param(&app, 1, 3, .12f);        /* Echo */
    for (i = 0; i < 4u; ++i) {
        fm1_app_unit_set_level(&app, (int)i, i == 2u ? 45.f : 55.f);
        if (fm1_app_unit_route(&app, (int)i, (int)i) < 0) { state.init_error = 20; return 0; }
    }
    /* The immutable control plan before any live voice and the first block. */
    if (fm1_mod_voice_count(app.mod)) { state.init_error = 22; return 0; }
    {
        fm1_mod_plan_info_t plan;
        fm1_mod_get_plan(app.mod, &plan);
    }
    lunar_fm1_queue_reset(&queue);
    lunar_fm1_router_reset(&router);
    lunar_fm1_router_set_full(&router, LUNAR_FM1_FULL_UI);
    ready = 1;
    return 1;
}

static int convert(void *work, uint32_t tag, int16_t out[LUNAR_PIPELINE_OUTPUT_SAMPLES],
                   lunar_pipeline_result_t *result)
{
    const float *samples;
    unsigned i, ch;
    if (!out || !result || tag != consume_next) return 0;
    samples = fm1_app_pipeline_consume(work);
    if (!samples) return 0;
    for (i = 0; i < LUNAR_FM1_BLOCK; ++i) for (ch = 0; ch < 2u; ++ch) {
        float x = samples[2 * i + ch];
        uint32_t bits;
        memcpy(&bits, &x, sizeof bits);
        if ((bits & 0x7f800000u) == 0x7f800000u) { ++invalid; x = 0; }
        x *= 4096.f;
        if (fade + i < FADE_FRAMES) x *= (float)(fade + i + 1u) / (float)FADE_FRAMES;
        if (x > 32767.f) { ++clipped; x = 32767.f; }
        if (x < -32768.f) { ++clipped; x = -32768.f; }
        /* Four int16 words a frame, as the pipeline's outputs are shaped:
         * L, R, then the same pair again. */
        out[4 * i + ch] = out[4 * i + ch + 2] = (int16_t)x;
    }
    if (fade < FADE_FRAMES) fade += LUNAR_FM1_BLOCK;
    /* The worker cleared the result and set its tag before this call, and
     * refuses the block (E_TAG) unless the tag comes back unchanged
     * (renderer_pipeline_sdk.c worker_step). Never clear it here. */
    result->tag = tag;
    result->invalid = invalid;
    result->clipped = clipped;
    result->case_total = tag + 1u;
    ++consume_next;
    return 1;
}

int lunar_fm1_live_bind(void)
{
    if (!ready || bound) return 0;
    if (lunar_pipeline_bind(fm1_app_pipeline_work(0), fm1_app_pipeline_work(1),
                            convert, fm1_app_pipeline_retire) != 1) return 0;
    bound = 1;
    return 1;
}

struct lunar_fm1_queue *lunar_fm1_live_queue(void) { return &queue; }

void lunar_fm1_live_leds(uint8_t led[41])
{
    unsigned i;
    for (i = 0; i < 41u; ++i) led[i] = LUNAR_FM1_FULL_UI ? app.led[i] : 0;
}

static void apply(void *ctx, const struct lunar_fm1_action *a)
{
    (void)ctx;
    switch (a->kind) {
    case LUNAR_FM1_ACT_NOTE_ON:
        fm1_app_unit_note_on(&app, a->sound, a->note, a->velocity);
        break;
    case LUNAR_FM1_ACT_NOTE_OFF:
        fm1_app_unit_note_off(&app, a->sound, a->note);
        break;
    case LUNAR_FM1_ACT_MASTER:
        /* The popup only in full-UI mode, where popups are serviced at a barrier. */
        fm1_app_master(&app, a->value, LUNAR_FM1_FULL_UI ? a->velocity : 0);
        break;
    case LUNAR_FM1_ACT_CUTOFF:
        fm1_app_set_param(&app, units[4], 1, a->value);
        break;
    case LUNAR_FM1_ACT_RESONANCE:
        fm1_app_set_param(&app, units[4], 2, a->value);
        break;
#if LUNAR_FM1_FULL_UI
    /* The panel's own paths, as sim/web/src/fm1_web.c calls them. */
    case LUNAR_FM1_ACT_UI_KEY:
        fm1_app_key(&app, a->note, a->down, a->velocity);
        break;
    case LUNAR_FM1_ACT_UI_BUTTON:
        fm1_app_button(&app, a->note, a->down);
        break;
    case LUNAR_FM1_ACT_UI_ENCODER:
        fm1_app_encoder(&app, a->note, (int)a->value);
        break;
    case LUNAR_FM1_ACT_BEND:
        fm1_app_pitch_bend(&app, a->value);
        break;
    case LUNAR_FM1_ACT_PANIC:
        fm1_app_all_notes_off(&app);
        break;
#endif
    default:
        break;
    }
}

int lunar_fm1_live_barrier_hold(void)
{
    struct lunar_fm1_event e;
    if (!LUNAR_FM1_FULL_UI || !bound || !fm1_app_pipeline_busy()) return 0;
    if ((lunar_fm1_queue_peek(&queue, &e) && lunar_fm1_event_barrier(&router, &e)) ||
        fm1_app_pipeline_service_due(&app)) {
        ++state.barrier_holds;
        return 1;
    }
    return 0;
}

int lunar_fm1_live_produce(void *work)
{
    struct lunar_fm1_event e;
    unsigned budget = LUNAR_FM1_QUEUE_SIZE;
    if (!bound || lunar_pipeline_error()) return 0;
    /* Between reserve and produce: the only window controls may run. */
    while (budget-- && lunar_fm1_queue_peek(&queue, &e)) {
        if (lunar_fm1_event_barrier(&router, &e) && fm1_app_pipeline_busy()) break; /* in order */
        if (lunar_fm1_event_barrier(&router, &e)) ++state.barrier_events;
        lunar_fm1_queue_pop(&queue, &e);
        ++state.events;
        lunar_fm1_route(&router, &e, apply, 0);
    }
#if LUNAR_FM1_FULL_UI
    if (fm1_app_pipeline_service_due(&app) && fm1_app_pipeline_service(&app)) ++state.services;
#endif
    if (!fm1_app_pipeline_produce(&app, work)) return 0;
    ++state.blocks;
    return 1;
}

void lunar_fm1_live_status(struct lunar_fm1_live_status *out)
{
    if (!out) return;
    *out = state;
    out->applied = router.applied;
    out->deferred = router.deferred;
    out->ignored = router.ignored;
    out->dropped = queue.dropped;
    out->invalid = invalid;
    out->clipped = clipped;
}
