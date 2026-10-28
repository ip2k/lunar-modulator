/* SPDX-License-Identifier: MIT. Bounded arithmetic comparison before rendering. */
#include "arithmetic_probe.h"
#include <string.h>

/* Volatile reads prevent constant folding or replacing the loop with a
 * closed-form expression. Each timed batch starts from the same seed.
 * All four loops include one operand load and a dependent operation. */
static volatile uint32_t integer_step = 1u;
static volatile float add_step = 1.0f / 1024.0f;
static volatile float factor = 1.0f + 1.0f / 1024.0f;

#define ITERATIONS 1024u
#define BATCHES 8u
#define NOINLINE __attribute__((noinline))
static NOINLINE uint32_t integer_add(void) {
    uint32_t x = 1u;
    for (unsigned i = 0; i < ITERATIONS; ++i) x += integer_step;
    return x;
}
static NOINLINE uint32_t float_add(void) {
    float x = 1.0f;
    uint32_t bits;
    for (unsigned i = 0; i < ITERATIONS; ++i) x += add_step;
    memcpy(&bits, &x, sizeof bits);
    return bits;
}
static NOINLINE uint32_t float_multiply(void) {
    float x = 1.0f;
    uint32_t bits;
    for (unsigned i = 0; i < ITERATIONS; ++i) x *= factor;
    memcpy(&bits, &x, sizeof bits);
    return bits;
}
static NOINLINE uint32_t float_divide(void) {
    float x = 1.0f;
    uint32_t bits;
    for (unsigned i = 0; i < ITERATIONS; ++i) x /= factor;
    memcpy(&bits, &x, sizeof bits);
    return bits;
}

int lunar_devkit_arithmetic_probe(uint32_t (*now)(void), void (*yield)(void),
    void (*emit)(const struct lunar_arithmetic_result *)) {
    uint32_t (*const kernels[])(void) = {
        integer_add, float_add, float_multiply, float_divide
    };
    if (!now || !yield || !emit) return 0;
    for (unsigned op = 0; op < 4; ++op) {
        struct lunar_arithmetic_result r = {0};
        r.operation = op;
        r.iterations = ITERATIONS;
        r.min_ticks = UINT32_MAX;
        for (unsigned b = 0; b < BATCHES; ++b) {
            uint32_t start = now();
            uint32_t bits = kernels[op]();
            uint32_t elapsed = now() - start;
            if (b && bits != r.result_bits) return 0;
            r.result_bits = bits;
            r.ticks += elapsed;
            if (elapsed < r.min_ticks) r.min_ticks = elapsed;
            if (elapsed > r.max_ticks) r.max_ticks = elapsed;
            ++r.batches;
            yield();
        }
        emit(&r);
    }
    return 1;
}
