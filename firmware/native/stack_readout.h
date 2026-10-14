/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_STACK_READOUT_H
#define LUNAR_STACK_READOUT_H
#include <stdint.h>

/* Fixed-width decimal avoids pulling a formatter into the diagnostic path.
 * Five digits cover the reviewed stack reservations; ten cover sample count. */
static inline void lunar_stack_decimal(char *dst, unsigned digits, uint32_t value)
{
    while (digits) {
        dst[--digits] = (char)('0' + value % 10u);
        value /= 10u;
    }
}
static inline void lunar_stack_readout(char margins[20], char samples[19],
    uint32_t user, uint32_t system, uint32_t count)
{
    const char a[] = "OBS U ----- S -----";
    const char b[] = "SAMPLES 0000000000";
    for (unsigned i = 0; i < sizeof a; ++i) margins[i] = a[i];
    for (unsigned i = 0; i < sizeof b; ++i) samples[i] = b[i];
    if (user <= 24320u) lunar_stack_decimal(margins + 6, 5, user);
    if (system <= 7936u) lunar_stack_decimal(margins + 14, 5, system);
    lunar_stack_decimal(samples + 8, 10, count);
}
#endif
