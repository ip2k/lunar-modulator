/* SPDX-License-Identifier: MIT. Experimental render-owner load feedback.
 * Not enabled by inclusion or by the DX7 engine's default twelve voices.
 */
#ifndef LUNAR_DEVKIT_VOICE_BUDGET_H
#define LUNAR_DEVKIT_VOICE_BUDGET_H
#include <stdint.h>

typedef struct lunar_voice_budget {
    uint32_t deadline, mean, pressure, recover, cooldown;
    uint32_t decreases, increases;
    unsigned limit, failed;
} lunar_voice_budget_t;

typedef int (*lunar_voice_budget_apply_t)(void *context, unsigned limit);

/* The caller owns this state and the target engine. No IRQ, allocation,
 * logging or wall-clock access occurs here. Samples use the same timer as
 * deadline. The measured experiment uses deadline=34829 at 24 MHz.
 */
static inline int lunar_voice_budget_init(lunar_voice_budget_t *s,
                                         uint32_t deadline) {
    if (!s || !deadline || deadline >= 24000000u) return 0;
    *s = (lunar_voice_budget_t){0};
    s->deadline = deadline;
    s->limit = 12;
    return 1;
}

/* Call after publishing block tag, before rendering the next block. Tags
 * below 16 are startup/prefill observations, intentionally ignored. The
 * owner supplies monotonically increasing tags starting at zero or one.
 * ready is the number of already rendered blocks available to playback.
 * Returns 1 for an applied change, 0 for no change, -1 on invalid data or
 * refused application. Failure latches: caller must stop/reinitialize.
 * Changed limits are reported synchronously by the return value and s->limit;
 * callers may collect trace records outside this controller. No finite event
 * buffer can halt long runs, but exact replay still requires a complete trace.
 * Retirement itself costs another full block; this is not a deadline guarantee.
 */
static inline int lunar_voice_budget_feedback(lunar_voice_budget_t *s,
        uint32_t tag, uint32_t ticks, unsigned ready,
        lunar_voice_budget_apply_t apply, void *context) {
    unsigned next;
    if (!s || s->failed) return -1;
    if (!s->deadline || s->deadline >= 24000000u || ticks >= 24000000u || !apply) {
        s->failed = 1;
        return -1;
    }
    if (tag < 16u) return 0;
    if (!s->mean) s->mean = ticks;
    else s->mean = (uint32_t)((int32_t)s->mean +
                     ((int32_t)ticks - (int32_t)s->mean) / 4);
    if (s->cooldown) --s->cooldown;
    next = s->limit;
    if (ticks > s->deadline * 9u / 10u &&
        s->mean > s->deadline * 9u / 10u && ready <= 5u) {
        if (s->pressure < 4u) ++s->pressure;
    } else s->pressure = 0;
    if ((ready <= 1u && ticks >= s->deadline) ||
        (!s->cooldown && s->pressure >= 4u)) {
        s->pressure = 0;
        s->recover = 0;
        if (next > 4u) --next;
    } else if (s->mean < s->deadline * 8u / 10u && ready >= 3u) {
        if (++s->recover >= 1024u) {
            if (next < 12u) ++next;
            s->recover = 0;
        }
    } else s->recover = 0;
    if (next == s->limit) return 0;
    if (apply(context, next) != 1) {
        s->failed = 1;
        return -1;
    }
    if (next < s->limit) {
        if (s->decreases != UINT32_MAX) ++s->decreases;
    } else if (s->increases != UINT32_MAX) ++s->increases;
    s->limit = next;
    s->cooldown = 2;
    return 1;
}
#endif
