/* SPDX-License-Identifier: MIT. Fixed mixed renderer pipeline adapter. */
#ifndef LUNAR_RENDERER_PIPELINE_LIVE_H
#define LUNAR_RENDERER_PIPELINE_LIVE_H
#include "renderer_live.h"
#include "renderer_pipeline_sdk.h"
#ifdef __cplusplus
extern "C" {
#endif
/* After renderer init, once only, 1..57 complete four-case cycles. Fixed
 * polyphony unless a separately labelled budget controller is installed.
 * Backend task must already be started; app/arenas live permanently. */
int lunar_pipeline_live_bind(unsigned cycles);
/* CPU0: reserve backend slot first, then controls + produce, then publish.
 * Unavailable reserve must never advance app controls. */
int lunar_pipeline_live_produce(void *work, uint32_t tag);
/* Sole CPU0 output owner, after output acquire, before matching retire.
 * Metadata only; does not release a PCM lease or invoke any engine. */
int lunar_pipeline_live_output(uint32_t tag, const int16_t *pcm,
                               const lunar_pipeline_result_t *result);
#ifdef __cplusplus
}
#endif
#endif
