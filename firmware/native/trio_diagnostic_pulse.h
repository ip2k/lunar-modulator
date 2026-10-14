/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_TRIO_DIAGNOSTIC_PULSE_H
#define LUNAR_TRIO_DIAGNOSTIC_PULSE_H
#include <stdint.h>

/* Diagnostic-only C4 pulse: emit once in [3s, 5s), then one note-off at
 * the first poll at/after 5s. If startup misses the window, emit nothing. */
static inline int lunar_trio_diagnostic_pulse_poll(uint32_t elapsed_ms,
                                                    uint8_t *state)
{
    if (!state) return 0;
    if (*state == 0u) {
        if (elapsed_ms >= 3000u && elapsed_ms < 5000u) {
            *state = 1u;
            return 1;
        }
        if (elapsed_ms >= 5000u) *state = 2u;
        return 0;
    }
    if (*state == 1u && elapsed_ms >= 5000u) {
        *state = 2u;
        return -1;
    }
    return 0;
}
#endif
