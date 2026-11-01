/* SPDX-License-Identifier: MIT. Finite native renderer pipeline. */
#ifndef LUNAR_RENDERER_PIPELINE_SDK_H
#define LUNAR_RENDERER_PIPELINE_SDK_H
#include "../common/renderer_pipeline_core.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Opt-in lifecycle; do not link the older whole-engine worker at the same time. */
int lunar_pipeline_sdk_start(uint32_t (*clock)(void));
void lunar_pipeline_sdk_parent_block(void);
void lunar_pipeline_sdk_report(unsigned test_case);
int lunar_pipeline_sdk_finish(void);
/* Native task wake protocol. CPU0 driver uses cpu=0; CPU1 worker uses cpu=1.
 * Drain tokens BEFORE checking progress predicates; wait only if no progress is
 * possible, then recheck. A token is a hint, never proof of published work.
 * These task APIs must not be called by an ISR. */
int lunar_pipeline_wake_drain(unsigned cpu);
int lunar_pipeline_wake_wait(unsigned cpu);
/* Single-writer CPU0 DAC drain notification; may post/yield. Native IRQ use
 * requires the reviewed pinned SDK ISR-post/yield path and adapter handoff.
 * This is not a generic ISR-safe API; host tests do not establish IRQ legality.
 * It never grants or retires an output lease. */
void lunar_pipeline_wake_drain_done(void);
#ifdef __cplusplus
}
#endif
#endif
