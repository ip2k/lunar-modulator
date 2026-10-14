/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_REALTIME_READOUT_H
#define LUNAR_REALTIME_READOUT_H
#include <stdint.h>

/* R/D are maximum measured microseconds; U is missing 64-frame blocks.
 * Full uint32 decimal fields never truncate or wrap the displayed value.
 * The 35-character line fits the diagnostic's 232-pixel content width. */
static inline void lunar_realtime_readout(char line[36], uint32_t render_us,
    uint32_t draw_us, uint32_t underruns)
{
    const char label[] = "R0000000000 D0000000000 U0000000000";
    uint32_t values[3] = {render_us, draw_us, underruns};
    for (unsigned i = 0; i < sizeof label; ++i) line[i] = label[i];
    for (unsigned field = 0; field < 3u; ++field) {
        uint32_t value = values[field];
        for (unsigned digit = 10; digit; --digit) {
            line[field * 12u + digit] = (char)('0' + value % 10u);
            value /= 10u;
        }
    }
}
#endif
