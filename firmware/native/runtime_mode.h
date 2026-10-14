/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_RUNTIME_MODE_H
#define LUNAR_RUNTIME_MODE_H
#include <stdint.h>

/* Diagnostic remains the default. Continuous operation does not disable the
 * platform's USB recovery request, watchdog or boot-failure guard. */
#ifndef LUNAR_RETURN_TO_ROM_SECONDS
#define LUNAR_RETURN_TO_ROM_SECONDS 20
#endif
#if LUNAR_RETURN_TO_ROM_SECONDS != 0 && LUNAR_RETURN_TO_ROM_SECONDS != 20 && LUNAR_RETURN_TO_ROM_SECONDS != 120
#error "Runtime must be an explicit diagnostic or explicit continuous mode"
#endif

/* Milliseconds permit the two-minute song diagnostic without overflowing the
 * high-resolution hardware counter. Unsigned subtraction also handles a
 * millisecond-counter wrap during either bounded diagnostic. */
static inline int lunar_runtime_expired(uint32_t now_ms, uint32_t start_ms)
{
#if LUNAR_RETURN_TO_ROM_SECONDS != 0
    return (uint32_t)(now_ms - start_ms) >= LUNAR_RETURN_TO_ROM_SECONDS * 1000u;
#else
    (void)now_ms; (void)start_ms;
    return 0;
#endif
}
#endif
