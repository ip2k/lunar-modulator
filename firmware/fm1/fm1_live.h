/* SPDX-License-Identifier: MIT
 * The FM-1 application's audio adapter: the pipelined shared app
 * (sim/web/src/fm1_app.c with FM1_APP_RENDER_PIPELINE) in the dev-kit
 * pipeline's fixed arrangement, free-running at the FM-1's rate, with the
 * panel and MIDI events applied between blocks. No SDK calls, no logging and
 * no allocation in this translation unit; fm1_sdk_main.c is the SDK glue.
 */
#ifndef LUNAR_FM1_LIVE_H
#define LUNAR_FM1_LIVE_H
#include <stdint.h>
#include "fm1_input.h"
#include "renderer_pipeline_sdk.h"
#ifdef __cplusplus
extern "C" {
#endif

/* About 44,118 Hz: Felucca times 44,117.6 Hz and AL-255 reads stock's as
 * 44,118 [reported]. The app's host rate; the 51/47 resampler fast path
 * engages within 10 ppm of 47,872.34 * 47/51 (fm1_resampler.h) [inferred:
 * -7.9 ppm, prepare-pipeline-devkit.py]. */
#define LUNAR_FM1_RATE 44118u
#define LUNAR_FM1_BLOCK 64u

/* 1: the panel and MIDI reach the app's whole UI (keys, 14 buttons, 7
 * encoders, bend, panic, sound 2's notes), applied at a drained barrier. It
 * links the app's key, button and encoder handlers and everything they reach,
 * which does not fit V15's slot with the current engine set
 * (notes/2026-11-09-controls.md), so the image default is 0: the fenced
 * subset of the first app image. */
#ifndef LUNAR_FM1_FULL_UI
#define LUNAR_FM1_FULL_UI 0
#endif

struct lunar_fm1_live_status {
    uint32_t init_error, blocks, events, applied, deferred, ignored, dropped;
    uint32_t invalid, clipped, dx7_voices;
    uint32_t barrier_events, barrier_holds, services; /* full UI */
};

/* Arenas, the fixed arrangement, eight voices per DX7 (cap8) and the
 * immutable control plan. Once; 1 on success. */
int lunar_fm1_live_init(void);
/* Bind the app's two work slots to the native pipeline. Once, after init. */
int lunar_fm1_live_bind(void);
/* The panel/MIDI task's queue (single producer). */
struct lunar_fm1_queue *lunar_fm1_live_queue(void);
/* BEFORE lunar_pipeline_reserve_work: 1 when the producer must not reserve
 * this pass because the next event (or the UI's own timer work) needs the
 * pipeline drained and a block is still in flight. The caller harvests and
 * asks again; nothing is lost, the 8-block output buffer covers the wait.
 * Always 0 unless LUNAR_FM1_FULL_UI. */
int lunar_fm1_live_barrier_hold(void);
/* After lunar_pipeline_reserve_work returned 1 for `work`: drain the queue
 * into the app's safe controls, then produce the block. 1 on success. */
int lunar_fm1_live_produce(void *work);
/* The app's 41 LED states (keys 0..26, then the buttons; nonzero = lit),
 * read by the panel task without a lock: a torn read shows one stale LED for
 * one scan. NULL-safe before init (all off). */
void lunar_fm1_live_leds(uint8_t led[41]);
void lunar_fm1_live_status(struct lunar_fm1_live_status *out);

#ifdef __cplusplus
}
#endif
#endif
