/* SPDX-License-Identifier: MIT. Opt-in two-core app pipeline. */
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
 * Any arrangement the UI can make: each block's first after a change admits
 * it (kinds, arenas, shared state), and Sound 2's engine and inserts run on
 * CPU1 unless they share state with a unit on CPU0. No editor/observer. An
 * arrangement changed while a block is pending, or one that cannot be split
 * safely, fails closed. Engines, inserts and effect order change only at a
 * drained barrier (fm1_app_select and fm1_app_swap_units need !busy).
 * Once used, do not reinitialize the bound app. Draw only at a drained barrier.
 * CPU0 produces after reserving a free backend work slot. CPU1 consumes only
 * after publication; CPU0 retires only after DONE acquire. Never reuse before
 * retirement, or free pending storage on failure. No tasking is enabled here. */
void *fm1_app_pipeline_work(unsigned index);
/* 1 while a block is produced or not yet retired (CPU0 state only). Every
 * panel path (key, button, encoder, bend, panic, sound 2's notes) needs 0. */
int fm1_app_pipeline_busy(void);
/* 1 while the arrangement a block admitted is unchanged; 0 after a change
 * of engine, an emptied unit or an effect swap, until the next block. */
int fm1_app_pipeline_sealed(void);
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
