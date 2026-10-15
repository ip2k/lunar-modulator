/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_IRQ_PROFILE_H
#define LUNAR_IRQ_PROFILE_H

#include <stdint.h>

/*
 * IRQ occupancy accounting core. This header deliberately has no hardware
 * register access; callers supply a free-running uint32 timestamp.
 *
 * Integration contract:
 * - Call enter/leave in strict ISR nesting order. Serialize each short state
 *   mutation against preemption by another tracked IRQ (for example, by
 *   briefly masking the higher-priority tracked source around the mutation).
 *   Sample the timestamp inside that serialization window, immediately before
 *   the mutation. Sampling before masking permits preemption to make the
 *   timestamp older than a nested interval and double-count busy time.
 * - Main-loop snapshots must be copied while all tracked IRQs are quiesced.
 *   The counters are multiword and a plain concurrent copy can tear. No helper
 *   here disables interrupts or claims an atomic snapshot.
 * - Durations use modulo-2^32 subtraction and are unambiguous when each
 *   measured interval is shorter than one timer wrap. Cumulative counters
 *   themselves wrap modulo 2^32.
 *
 * Per-source durations are inclusive: nested ALNK0/timer-5 time appears in
 *   each relevant source's diagnostic total. `busy_ticks` is different: it
 *   accumulates only outermost intervals and therefore never double-counts
 *   nested work.
 */

#define LUNAR_IRQ_PROFILE_MAX_DEPTH 8u

typedef enum {
    LUNAR_IRQ_PROFILE_ALNK0 = 0,
    LUNAR_IRQ_PROFILE_TIMER5 = 1,
    LUNAR_IRQ_PROFILE_INPUT = 2,
    LUNAR_IRQ_PROFILE_USB = 3,
    LUNAR_IRQ_PROFILE_UAC = 4,
    LUNAR_IRQ_PROFILE_SOURCE_COUNT = 5
} lunar_irq_profile_source_t;

typedef struct {
    uint32_t count;
    uint32_t total_ticks;
    uint32_t max_ticks;
} lunar_irq_profile_source_stats_t;

typedef struct {
    uint8_t source;
    uint32_t start_ticks;
} lunar_irq_profile_frame_t;

typedef struct {
    lunar_irq_profile_source_stats_t source[LUNAR_IRQ_PROFILE_SOURCE_COUNT];
    lunar_irq_profile_frame_t stack[LUNAR_IRQ_PROFILE_MAX_DEPTH];
    uint32_t busy_count;
    uint32_t busy_ticks;
    uint32_t max_busy_ticks;
    uint32_t overflow_count;
    uint32_t mismatch_count;
    uint32_t outer_start_ticks;
    uint8_t depth;
} lunar_irq_profile_t;

#if defined(LUNAR_DIAGNOSTIC_IRQ_PROFILE) && LUNAR_DIAGNOSTIC_IRQ_PROFILE

static inline void lunar_irq_profile_init(volatile lunar_irq_profile_t *profile)
{
    uint32_t i;
    for (i = 0; i < (uint32_t)LUNAR_IRQ_PROFILE_SOURCE_COUNT; ++i) {
        profile->source[i].count = 0;
        profile->source[i].total_ticks = 0;
        profile->source[i].max_ticks = 0;
    }
    profile->busy_count = 0;
    profile->busy_ticks = 0;
    profile->max_busy_ticks = 0;
    profile->overflow_count = 0;
    profile->mismatch_count = 0;
    profile->outer_start_ticks = 0;
    profile->depth = 0;
}

/* Returns nonzero when a matching leave call is required. */
static inline int lunar_irq_profile_enter(volatile lunar_irq_profile_t *profile,
                                          lunar_irq_profile_source_t source,
                                          uint32_t now)
{
    uint8_t depth = profile->depth;
    if ((uint32_t)source >= (uint32_t)LUNAR_IRQ_PROFILE_SOURCE_COUNT ||
        depth >= LUNAR_IRQ_PROFILE_MAX_DEPTH) {
        ++profile->overflow_count;
        return 0;
    }
    if (depth == 0u) profile->outer_start_ticks = now;
    profile->stack[depth].source = (uint8_t)source;
    profile->stack[depth].start_ticks = now;
    profile->depth = (uint8_t)(depth + 1u);
    return 1;
}

/* Returns nonzero when the leave matched and was accounted. */
static inline int lunar_irq_profile_leave(volatile lunar_irq_profile_t *profile,
                                          lunar_irq_profile_source_t source,
                                          uint32_t now)
{
    uint8_t depth = profile->depth;
    uint32_t elapsed;
    volatile lunar_irq_profile_source_stats_t *stats;
    if (depth == 0u ||
        (uint32_t)source >= (uint32_t)LUNAR_IRQ_PROFILE_SOURCE_COUNT ||
        profile->stack[depth - 1u].source != (uint8_t)source) {
        ++profile->mismatch_count;
        return 0;
    }
    elapsed = now - profile->stack[depth - 1u].start_ticks;
    stats = &profile->source[(uint32_t)source];
    ++stats->count;
    stats->total_ticks += elapsed;
    if (elapsed > stats->max_ticks) stats->max_ticks = elapsed;
    profile->depth = (uint8_t)(depth - 1u);
    if (profile->depth == 0u) {
        uint32_t busy = now - profile->outer_start_ticks;
        ++profile->busy_count;
        profile->busy_ticks += busy;
        if (busy > profile->max_busy_ticks) profile->max_busy_ticks = busy;
    }
    return 1;
}

#else

/* Ordinary builds retain the type/API for simple conditional integration,
 * while all calls compile to no work and enter always declines recording. */
static inline void lunar_irq_profile_init(volatile lunar_irq_profile_t *profile)
{
    (void)profile;
}

static inline int lunar_irq_profile_enter(volatile lunar_irq_profile_t *profile,
                                          lunar_irq_profile_source_t source,
                                          uint32_t now)
{
    (void)profile;
    (void)source;
    (void)now;
    return 0;
}

static inline int lunar_irq_profile_leave(volatile lunar_irq_profile_t *profile,
                                          lunar_irq_profile_source_t source,
                                          uint32_t now)
{
    (void)profile;
    (void)source;
    (void)now;
    return 0;
}

#endif

#endif
