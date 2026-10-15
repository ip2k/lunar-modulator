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

/* Supplemental schema-4 PLL inputs for the stock CLK_CON2 selector case 6.
 * These ordinary volatile reads are raw evidence only; they do not decode a
 * clock rate and do not alter clock configuration. */
static inline void lunar_pll_snapshot(uint32_t values[4], uint32_t uptime)
{
    values[0] = uptime;
    values[1] = LUNAR_CLOCK_LOAD(0x119a0u); /* oscillator selector */
    values[2] = LUNAR_CLOCK_LOAD(0x119a8u); /* predivider */
    values[3] = LUNAR_CLOCK_LOAD(0x119acu); /* multiplier */
}
#endif
