#include "irq_profile.h"

#include <assert.h>
#include <stdint.h>

int main(void)
{
    lunar_irq_profile_t profile;
    lunar_irq_profile_init(&profile);

#if defined(LUNAR_DIAGNOSTIC_IRQ_PROFILE) && LUNAR_DIAGNOSTIC_IRQ_PROFILE
    /* ALNK0 is outer; timer-5 nests. Source totals are inclusive, aggregate
       busy time is the outer interval exactly once. */
    assert(lunar_irq_profile_enter(&profile, LUNAR_IRQ_PROFILE_ALNK0, 100u));
    assert(lunar_irq_profile_enter(&profile, LUNAR_IRQ_PROFILE_TIMER5, 120u));
    assert(lunar_irq_profile_leave(&profile, LUNAR_IRQ_PROFILE_TIMER5, 130u));
    assert(lunar_irq_profile_leave(&profile, LUNAR_IRQ_PROFILE_ALNK0, 160u));
    assert(profile.depth == 0u);
    assert(profile.source[LUNAR_IRQ_PROFILE_ALNK0].count == 1u);
    assert(profile.source[LUNAR_IRQ_PROFILE_ALNK0].total_ticks == 60u);
    assert(profile.source[LUNAR_IRQ_PROFILE_TIMER5].count == 1u);
    assert(profile.source[LUNAR_IRQ_PROFILE_TIMER5].total_ticks == 10u);
    assert(profile.busy_count == 1u && profile.busy_ticks == 60u);
    assert(profile.max_busy_ticks == 60u);

    /* uint32 timer wrap is valid for source and outer intervals. */
    assert(lunar_irq_profile_enter(&profile, LUNAR_IRQ_PROFILE_ALNK0,
                                   UINT32_MAX - 4u));
    assert(lunar_irq_profile_enter(&profile, LUNAR_IRQ_PROFILE_TIMER5,
                                   UINT32_MAX - 2u));
    assert(lunar_irq_profile_leave(&profile, LUNAR_IRQ_PROFILE_TIMER5, 1u));
    assert(lunar_irq_profile_leave(&profile, LUNAR_IRQ_PROFILE_ALNK0, 5u));
    assert(profile.source[LUNAR_IRQ_PROFILE_ALNK0].total_ticks == 70u);
    assert(profile.source[LUNAR_IRQ_PROFILE_TIMER5].total_ticks == 14u);
    assert(profile.busy_ticks == 70u);
    assert(profile.max_busy_ticks == 60u);

    /* Other categories share the same accounting and can nest in either order. */
    assert(lunar_irq_profile_enter(&profile, LUNAR_IRQ_PROFILE_USB, 200u));
    assert(lunar_irq_profile_enter(&profile, LUNAR_IRQ_PROFILE_INPUT, 202u));
    assert(lunar_irq_profile_leave(&profile, LUNAR_IRQ_PROFILE_INPUT, 205u));
    assert(lunar_irq_profile_leave(&profile, LUNAR_IRQ_PROFILE_USB, 210u));
    assert(profile.source[LUNAR_IRQ_PROFILE_USB].total_ticks == 10u);
    assert(profile.source[LUNAR_IRQ_PROFILE_INPUT].total_ticks == 3u);
    assert(profile.busy_ticks == 80u);

    /* Bad order is rejected without corrupting the open stack; capacity is
       bounded, and a refused enter must not be followed by a leave. */
    assert(lunar_irq_profile_enter(&profile, LUNAR_IRQ_PROFILE_ALNK0, 300u));
    assert(!lunar_irq_profile_leave(&profile, LUNAR_IRQ_PROFILE_TIMER5, 301u));
    assert(profile.depth == 1u && profile.mismatch_count == 1u);
    assert(lunar_irq_profile_leave(&profile, LUNAR_IRQ_PROFILE_ALNK0, 302u));
    {
        unsigned i;
        for (i = 0; i < LUNAR_IRQ_PROFILE_MAX_DEPTH; ++i)
            assert(lunar_irq_profile_enter(&profile, LUNAR_IRQ_PROFILE_ALNK0, i));
        assert(!lunar_irq_profile_enter(&profile, LUNAR_IRQ_PROFILE_TIMER5, 9u));
        assert(profile.overflow_count == 1u);
        for (i = 0; i < LUNAR_IRQ_PROFILE_MAX_DEPTH; ++i)
            assert(lunar_irq_profile_leave(&profile, LUNAR_IRQ_PROFILE_ALNK0, 20u + i));
    }
#else
    /* Disabled API is safe to link and never mutates its caller-owned state. */
    profile.busy_ticks = 77u;
    assert(!lunar_irq_profile_enter(&profile, LUNAR_IRQ_PROFILE_ALNK0, 1u));
    assert(!lunar_irq_profile_leave(&profile, LUNAR_IRQ_PROFILE_ALNK0, 2u));
    assert(profile.busy_ticks == 77u);
#endif
    return 0;
}
