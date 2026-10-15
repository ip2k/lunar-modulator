/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_CLOCK_SNAPSHOT_H
#define LUNAR_CLOCK_SNAPSHOT_H
#include <stdint.h>

/* Configuration reads only. Snapshot after platform initialization; this does
 * not describe pre-SPL state or establish an MHz value. SDK/SPL selector
 * interpretations differ. Override the load only in a host test harness. */
#ifndef LUNAR_CLOCK_LOAD
#define LUNAR_CLOCK_LOAD(address) (*(volatile const uint32_t *)(uintptr_t)(address))
#endif
static inline void lunar_clock_snapshot(uint32_t values[4], uint32_t uptime)
{
    values[0] = uptime;
    values[1] = LUNAR_CLOCK_LOAD(0x1000cu); /* CLK_CON0 */
    values[2] = LUNAR_CLOCK_LOAD(0x10014u); /* CLK_CON2 */
    values[3] = LUNAR_CLOCK_LOAD(0x10008u); /* SYS_DIV */
}
#endif
