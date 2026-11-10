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
/* 1 while a block is produced or not yet retired (CPU0 state only). Every
 * panel path (key, button, encoder, bend, panic, sound 2's notes) needs 0. */
int fm1_app_pipeline_busy(void);
/* 1 once blocks run: engines, inserts and Macro's model can no longer change
 * (the UI refuses with FM1_APP_SELECT_LOCKED). */
int fm1_app_pipeline_locked(void);
/* The UI's time-driven work (ARP hold, popup expiry, toast/follow/snap): due
 * when it has any, run only when !busy (returns 0 if busy). */
int fm1_app_pipeline_service_due(const fm1_app_t *app);
int fm1_app_pipeline_service(fm1_app_t *app);
int fm1_app_pipeline_produce(fm1_app_t *app, void *work);
const float *fm1_app_pipeline_consume(void *work);
int fm1_app_pipeline_retire(void *work);
/* Opt-in producer stage marks (FM1_APP_PIPELINE_MARKS, off by default). The
 * platform supplies fm1_app_pipeline_mark; it must only read a timer and store,
 * never allocate, log, mutate the app or render. CONTROLS is marked by the
 * caller before fm1_app_pipeline_produce; the rest inside the sealed block. */
enum fm1_app_pipeline_mark_point {
  FM1_APP_PIPELINE_MARK_CONTROLS, FM1_APP_PIPELINE_MARK_PREFLIGHT,
  FM1_APP_PIPELINE_MARK_SEQ, FM1_APP_PIPELINE_MARK_DISPATCH,
  FM1_APP_PIPELINE_MARK_INSERTS, FM1_APP_PIPELINE_MARK_CAPTURE,
  FM1_APP_PIPELINE_MARK_POINTS
};
void fm1_app_pipeline_mark(unsigned point);
#ifdef __cplusplus
}
#endif
#endif
