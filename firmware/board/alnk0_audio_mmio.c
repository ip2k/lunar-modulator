/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Lunar Modulator contributors
 *
 * Register accessors for lunar_alnk0_ops on the chip itself: volatile loads
 * and stores at the SFR addresses, and pi32v2's `csync` as the barrier.
 * The interrupt and delay callbacks belong to the runtime that links this.
 * Compile-checked with JieLi's pi32v2 clang; not yet run on a chip.
 */
#include "alnk0_audio.h"

#if defined(__pi32v2__) || defined(__GCC_PI32V2__)

uint32_t lunar_alnk0_mmio_read(void *context, uint32_t address, unsigned bytes)
{
    (void)context;
    if (bytes == 1u)
        return *(volatile uint8_t *)(uintptr_t)address;
    if (bytes == 2u)
        return *(volatile uint16_t *)(uintptr_t)address;
    return *(volatile uint32_t *)(uintptr_t)address;
}

void lunar_alnk0_mmio_write(void *context, uint32_t address, unsigned bytes, uint32_t value)
{
    (void)context;
    if (bytes == 1u)
        *(volatile uint8_t *)(uintptr_t)address = (uint8_t)value;
    else if (bytes == 2u)
        *(volatile uint16_t *)(uintptr_t)address = (uint16_t)value;
    else
        *(volatile uint32_t *)(uintptr_t)address = value;
}

void lunar_alnk0_mmio_sync(void *context)
{
    (void)context;
    __asm__ volatile("csync;" ::: "memory");
}

#else
/* Host builds have no SFRs; keep the translation unit non-empty. */
typedef int lunar_alnk0_mmio_host_unused;
#endif
