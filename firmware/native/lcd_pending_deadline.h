/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_LCD_PENDING_DEADLINE_H
#define LUNAR_LCD_PENDING_DEADLINE_H
#include <stdint.h>

/* Main-loop-only observation, never an ownership-release or abort primitive.
 * The caller supplies one free-running uint32 clock and polls at least once per
 * full timer period. Unsigned subtraction handles a wrap. Once reported, a
 * transfer stays latched even over subsequent wraps, until explicitly rearmed. */
typedef struct {
    uint32_t started;
    uint8_t active;
    uint8_t reported;
} lunar_lcd_pending_deadline_t;

/* Diagnostic policy, not a measured transfer limit or a recovery deadline. */
#define LUNAR_LCD_PENDING_DEADLINE_US 100000u

static inline void lunar_lcd_pending_begin(lunar_lcd_pending_deadline_t *p,
                                           uint32_t now)
{
    p->started = now;
    p->active = 1;
    p->reported = 0;
}

static inline void lunar_lcd_pending_complete(lunar_lcd_pending_deadline_t *p)
{
    p->active = 0;
    p->reported = 0;
}

/* Call only after observing DONE low. Completion takes priority at the boundary.
 * Returns one accounting event, at most once per begin/complete cycle. */
static inline int lunar_lcd_pending_expired(lunar_lcd_pending_deadline_t *p,
                                            uint32_t now, uint32_t limit)
{
    if (!p->active || p->reported || (uint32_t)(now - p->started) < limit)
        return 0;
    p->reported = 1;
    return 1;
}
#endif
