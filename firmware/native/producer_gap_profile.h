/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_PRODUCER_GAP_PROFILE_H
#define LUNAR_PRODUCER_GAP_PROFILE_H

#include <stdint.h>

/* Main-loop-only observations. This helper is absent from ordinary builds and
 * never runs in the audio interrupt. Timestamps use unsigned subtraction so
 * one uint32 timer wrap is handled naturally. Queue depth is a best-effort
 * sample: the audio interrupt may advance `read` between the two loads. */
typedef struct {
    uint32_t refill_entry_calls;
    uint32_t max_refill_entry_gap_ticks;
    uint32_t max_render_call_ticks;
    uint32_t published_blocks;
    uint32_t max_publish_gap_ticks;
    uint32_t min_queue_depth;
    uint32_t max_display_wait_ticks;
    uint32_t max_display_work_ticks;
    uint32_t display_calls;
    uint32_t previous_refill_entry;
    uint32_t previous_publish;
    uint8_t have_refill_entry;
    uint8_t have_publish;
} lunar_producer_gap_profile_t;

static inline void lunar_producer_gap_reset_window(lunar_producer_gap_profile_t *p)
{
    p->refill_entry_calls = 0;
    p->max_refill_entry_gap_ticks = 0;
    p->max_render_call_ticks = 0;
    p->published_blocks = 0;
    p->max_publish_gap_ticks = 0;
    p->min_queue_depth = UINT32_MAX;
    p->max_display_wait_ticks = 0;
    p->max_display_work_ticks = 0;
    p->display_calls = 0;
}

static inline void lunar_producer_gap_init(lunar_producer_gap_profile_t *p)
{
    p->previous_refill_entry = 0;
    p->previous_publish = 0;
    p->have_refill_entry = 0;
    p->have_publish = 0;
    lunar_producer_gap_reset_window(p);
}

static inline void lunar_producer_gap_refill_entry(
    lunar_producer_gap_profile_t *p, uint32_t now)
{
    if (p->have_refill_entry) {
        uint32_t gap = now - p->previous_refill_entry;
        if (gap > p->max_refill_entry_gap_ticks) p->max_refill_entry_gap_ticks = gap;
    }
    p->previous_refill_entry = now;
    p->have_refill_entry = 1;
    ++p->refill_entry_calls;
}

static inline void lunar_producer_gap_render(lunar_producer_gap_profile_t *p,
                                              uint32_t elapsed)
{
    if (elapsed > p->max_render_call_ticks) p->max_render_call_ticks = elapsed;
}

static inline void lunar_producer_gap_queue(lunar_producer_gap_profile_t *p,
                                             uint32_t depth)
{
    if (depth < p->min_queue_depth) p->min_queue_depth = depth;
}

static inline void lunar_producer_gap_published(lunar_producer_gap_profile_t *p,
                                                 uint32_t now)
{
    if (p->have_publish) {
        uint32_t gap = now - p->previous_publish;
        if (gap > p->max_publish_gap_ticks) p->max_publish_gap_ticks = gap;
    }
    p->previous_publish = now;
    p->have_publish = 1;
    ++p->published_blocks;
}

static inline void lunar_producer_gap_display(lunar_producer_gap_profile_t *p,
                                               uint32_t wait_ticks,
                                               uint32_t work_ticks)
{
    if (wait_ticks > p->max_display_wait_ticks) p->max_display_wait_ticks = wait_ticks;
    if (work_ticks > p->max_display_work_ticks) p->max_display_work_ticks = work_ticks;
    ++p->display_calls;
}

static inline void lunar_producer_gap_snapshot(
    lunar_producer_gap_profile_t *p, uint32_t uptime_ms, uint32_t values[10])
{
    values[0] = uptime_ms;
    values[1] = p->refill_entry_calls;
    values[2] = p->max_refill_entry_gap_ticks;
    values[3] = p->max_render_call_ticks;
    values[4] = p->published_blocks;
    values[5] = p->max_publish_gap_ticks;
    values[6] = p->min_queue_depth;
    values[7] = p->max_display_wait_ticks;
    values[8] = p->max_display_work_ticks;
    values[9] = p->display_calls;
    lunar_producer_gap_reset_window(p);
}

#endif
