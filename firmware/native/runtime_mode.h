/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_RUNTIME_MODE_H
#define LUNAR_RUNTIME_MODE_H
#include <stdint.h>

/* Diagnostic remains the default. Continuous operation does not disable the
 * platform's USB recovery request, watchdog or boot-failure guard. */
#ifndef LUNAR_RETURN_TO_ROM_SECONDS
#define LUNAR_RETURN_TO_ROM_SECONDS 20
#endif
#if LUNAR_RETURN_TO_ROM_SECONDS != 0 && LUNAR_RETURN_TO_ROM_SECONDS != 20
#error "Runtime must be the twenty-second diagnostic or explicit continuous mode"
#endif

static inline int lunar_runtime_expired(uint32_t now, uint32_t start,
                                        uint32_t ticks_per_us)
{
#if LUNAR_RETURN_TO_ROM_SECONDS == 20
    return (uint32_t)(now - start) >= 20u * 1000000u * ticks_per_us;
#else
    (void)now; (void)start; (void)ticks_per_us;
    return 0;
#endif
}
#endif
