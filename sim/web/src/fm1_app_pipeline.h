/* SPDX-License-Identifier: MIT. Opt-in fixed-arrangement app pipeline. */
#ifndef FM1_APP_PIPELINE_H
#define FM1_APP_PIPELINE_H
#include "fm1_app.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Platform hooks: first refusal is permanent. fail must not return; retain all
 * app/slot/engine storage while a worker may still use it. */
uint32_t fm1_app_pipeline_error(void);
void fm1_app_pipeline_fail(uint32_t code) __attribute__((noreturn));
/* Two static slots, bound once to a single app. Fixed 64-frame stereo blocks.
 * Supported fixture only: dx7/macro(model0)/drums/dx7, Filter/Drive inserts,
 * Echo/Comp masters, no editor/observer. Unsupported or changed layout fails closed.
 * Once used, do not reinitialize the bound app. Draw only at a drained barrier.
 * CPU0 produces after reserving a free backend work slot. CPU1 consumes only
 * after publication; CPU0 retires only after DONE acquire. Never reuse before
 * retirement, or free pending storage on failure. No tasking is enabled here. */
void *fm1_app_pipeline_work(unsigned index);
int fm1_app_pipeline_produce(fm1_app_t *app, void *work);
const float *fm1_app_pipeline_consume(void *work);
int fm1_app_pipeline_retire(void *work);
#ifdef __cplusplus
}
#endif
#endif
