/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_CPU_RATE_CALIBRATION_H
#define LUNAR_CPU_RATE_CALIBRATION_H

#include <stdint.h>
#include "fm1_time.h"

#define LUNAR_CPU_RATE_ITERATIONS 4096u
#define LUNAR_CPU_RATE_TRIALS 4u

typedef struct {
    uint32_t uptime_ms;
    uint32_t iterations;
    uint32_t trials;
    uint32_t xip_ticks;
    uint32_t ram_ticks;
    uint32_t xip_checksum;
    uint32_t ram_checksum;
    uint32_t status;
} lunar_cpu_rate_result_t;

enum {
    LUNAR_CPU_RATE_TIMINGS_VALID = 1u,
    LUNAR_CPU_RATE_CHECKSUMS_MATCH = 2u
};

#ifndef LUNAR_CPU_RATE_READ_TICKS
#define LUNAR_CPU_RATE_READ_TICKS() FM1_T4_CNT
#endif
#ifndef LUNAR_CPU_RATE_RAM_SECTION
#define LUNAR_CPU_RATE_RAM_SECTION __attribute__((section(".ram_text")))
#endif

typedef uint32_t (*lunar_cpu_rate_kernel_t)(uint32_t, uint32_t);

/* Deliberately use the same fixed integer program in XIP and ordinary SRAM.
 * It makes no calls and reads no tables. This is a relative raw-tick probe,
 * not an instruction counter or calibrated CPU-frequency measurement. */
#define LUNAR_CPU_RATE_KERNEL(name, section_attr) \
    static uint32_t name(uint32_t x, uint32_t rounds) \
        __attribute__((noinline, used)) section_attr; \
    static uint32_t name(uint32_t x, uint32_t rounds) \
    { \
        for (uint32_t i = 0; i < rounds; ++i) { \
            x ^= x << 13; \
            x ^= x >> 17; \
            x ^= x << 5; \
            x += 0x9e3779b9u + i; \
        } \
        return x; \
    }

LUNAR_CPU_RATE_KERNEL(lunar_cpu_rate_xip_kernel, )
LUNAR_CPU_RATE_KERNEL(lunar_cpu_rate_ram_kernel, LUNAR_CPU_RATE_RAM_SECTION)
#undef LUNAR_CPU_RATE_KERNEL

static lunar_cpu_rate_result_t lunar_cpu_rate_result;

static uint32_t lunar_cpu_rate_measure(lunar_cpu_rate_kernel_t volatile *kernel,
                                      uint32_t seed, uint32_t *checksum)
{
    uint32_t start = LUNAR_CPU_RATE_READ_TICKS();
    uint32_t value = (*kernel)(seed, LUNAR_CPU_RATE_ITERATIONS);
    uint32_t elapsed = LUNAR_CPU_RATE_READ_TICKS() - start;
    *checksum ^= value;
    return elapsed;
}

static void lunar_cpu_rate_calibrate(void)
{
    lunar_cpu_rate_kernel_t volatile xip = lunar_cpu_rate_xip_kernel;
    lunar_cpu_rate_kernel_t volatile ram = lunar_cpu_rate_ram_kernel;
    lunar_cpu_rate_result_t result = {0};

    /* Warm both instruction paths before timed samples. */
    (void)(*xip)(0x12345678u, 8u);
    (void)(*ram)(0x12345678u, 8u);
    for (uint32_t trial = 0; trial < LUNAR_CPU_RATE_TRIALS; ++trial) {
        uint32_t seed = 0x6d2b79f5u ^ (trial * 0x9e3779b9u);
        if (trial & 1u) {
            result.ram_ticks += lunar_cpu_rate_measure(&ram, seed, &result.ram_checksum);
            result.xip_ticks += lunar_cpu_rate_measure(&xip, seed, &result.xip_checksum);
        } else {
            result.xip_ticks += lunar_cpu_rate_measure(&xip, seed, &result.xip_checksum);
            result.ram_ticks += lunar_cpu_rate_measure(&ram, seed, &result.ram_checksum);
        }
    }
    result.uptime_ms = fm1_ms;
    result.iterations = LUNAR_CPU_RATE_ITERATIONS;
    result.trials = LUNAR_CPU_RATE_TRIALS;
    if (result.xip_ticks != 0u && result.ram_ticks != 0u)
        result.status |= LUNAR_CPU_RATE_TIMINGS_VALID;
    if (result.xip_checksum == result.ram_checksum)
        result.status |= LUNAR_CPU_RATE_CHECKSUMS_MATCH;
    lunar_cpu_rate_result = result;
}

#endif
