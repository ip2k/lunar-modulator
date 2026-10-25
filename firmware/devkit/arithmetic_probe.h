/* SPDX-License-Identifier: MIT. Worker-only diagnostic; no device access. */
#ifndef LUNAR_DEVKIT_ARITHMETIC_PROBE_H
#define LUNAR_DEVKIT_ARITHMETIC_PROBE_H
#include <stdint.h>
struct lunar_arithmetic_result {
    uint32_t operation, iterations, batches, min_ticks, max_ticks, result_bits;
    uint64_t ticks;
};
/* Operations: 0 uint32 add, 1 float add, 2 float multiply, 3 float divide.
 * Times include loop/control/operand loads and interrupts: not instruction
 * latency or renderer acceptance. Operands stay finite and nonzero. */
int lunar_devkit_arithmetic_probe(uint32_t (*now)(void), void (*yield)(void),
    void (*emit)(const struct lunar_arithmetic_result *));
#endif
