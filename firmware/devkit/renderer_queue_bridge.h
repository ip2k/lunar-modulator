/* SPDX-License-Identifier: MIT. Timing experiment only; no SDK/device calls. */
#ifndef LUNAR_RENDERER_QUEUE_BRIDGE_H
#define LUNAR_RENDERER_QUEUE_BRIDGE_H
#include "fm1_engine.h"
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum lunar_renderer_queue_kind {
    LUNAR_QUEUE_RENDER, LUNAR_QUEUE_NOTE_ON, LUNAR_QUEUE_NOTE_OFF,
    LUNAR_QUEUE_SET_PARAM, LUNAR_QUEUE_BEND, LUNAR_QUEUE_SET_NOTE
};
/* CPU0 initializes once BEFORE CPU1 starts. No destructor or reinitialization:
 * all command, instance and output storage must survive a late CPU1 write.
 * This does not establish independence of any engine/model combination. */
int lunar_renderer_queue_init(uint32_t (*clock)(void), uint32_t budget_ticks);
/* CPU0 only. Failure is permanent; stop the diagnostic and retain its arena. */
int lunar_renderer_queue_begin(void);
int lunar_renderer_queue_push(unsigned sound, const fm1_engine_t *engine, void *instance,
    unsigned kind, float *output, unsigned frames, unsigned index,
    unsigned key, unsigned velocity, float value);
#ifdef LUNAR_QUEUE_POST
int lunar_renderer_queue_post(unsigned sound, void (*callback)(void *, unsigned), void *context);
#endif
int lunar_renderer_queue_dispatch(void);
unsigned lunar_renderer_queue_completed(void);
unsigned lunar_renderer_queue_error(void);
unsigned lunar_renderer_queue_peak(unsigned sound);
#ifdef LUNAR_QUEUE_PROFILE
/* Once per successful block, same clock domain as init. CPU0 only.
 * before / recording / caller / wait / after; overlapping worker is sixth. */
int lunar_renderer_queue_profile_read(uint32_t start, uint32_t end, uint32_t ticks[6]);
#endif
#ifdef LUNAR_QUEUE_DETAIL
#ifndef LUNAR_QUEUE_PROFILE
#error Queue detail requires queue profile
#endif
enum { LUNAR_QUEUE_DETAILS = 10 };
/* CPU0 only, non-nested intervals; reset once before each outer render.
 * These are subsets of the outer regions, never additional audio time. */
void lunar_renderer_queue_detail_reset(void);
void lunar_renderer_queue_detail_mark(unsigned region, int entering);
int lunar_renderer_queue_detail_read(uint32_t ticks[LUNAR_QUEUE_DETAILS]);
#endif
#ifdef LUNAR_QUEUE_MICRO
#ifndef LUNAR_QUEUE_DETAIL
#error Queue micro timing requires queue detail
#endif
/* Six recording command kinds, fourteen shared-app unit indices, then six
 * control hooks (begin, event, lock, tick, lock_slot, note_on).
 * Sparse: unused effects/command kinds legitimately have zero calls/ticks.
 * CPU0 only, non-nested within this bank; overlaps the enclosing DETAIL bank. */
enum { LUNAR_QUEUE_MICROS = 26 };
void lunar_renderer_queue_micro_reset(void);
void lunar_renderer_queue_micro_mark(unsigned region, int entering);
int lunar_renderer_queue_micro_read(uint32_t ticks[LUNAR_QUEUE_MICROS],
                                   uint32_t calls[LUNAR_QUEUE_MICROS]);
#endif
/* CPU1 only, after init/publication: -1 unavailable, 0 idle, 1 completed. */
int lunar_renderer_queue_worker_step(void);
#ifdef __cplusplus
}
#endif
#endif
