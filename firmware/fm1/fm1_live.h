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

struct lunar_fm1_live_status {
    uint32_t init_error, blocks, events, applied, deferred, ignored, dropped;
    uint32_t invalid, clipped, dx7_voices;
};

/* Arenas, the fixed arrangement, eight voices per DX7 (cap8) and the
 * immutable control plan. Once; 1 on success. */
int lunar_fm1_live_init(void);
/* Bind the app's two work slots to the native pipeline. Once, after init. */
int lunar_fm1_live_bind(void);
/* The panel/MIDI task's queue (single producer). */
struct lunar_fm1_queue *lunar_fm1_live_queue(void);
/* After lunar_pipeline_reserve_work returned 1 for `work`: drain the queue
 * into the app's safe controls, then produce the block. 1 on success. */
int lunar_fm1_live_produce(void *work);
void lunar_fm1_live_status(struct lunar_fm1_live_status *out);

#ifdef __cplusplus
}
#endif
#endif
