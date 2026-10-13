/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_INSTANCE_POOL_H
#define LUNAR_INSTANCE_POOL_H
#include <stddef.h>
#include <stdint.h>

/* Main-loop ownership only; audio interrupts never allocate or free.
 * Buffer remains alive for the entire pool lifetime. No live allocation moves. */
typedef struct {
    void *allocator;
    uintptr_t lo, hi;
    size_t live_bytes;
    unsigned live_allocations;
} lunar_instance_pool_t;

int lunar_instance_pool_init(lunar_instance_pool_t *pool, void *buffer, size_t bytes);
void *lunar_instance_pool_alloc(lunar_instance_pool_t *pool, size_t bytes);
/* NULL is a no-op. Invalid ranges/ownership are refused; returns 0 on success.
 * Callers must only pass pointers originally returned by this pool. */
int lunar_instance_pool_free(lunar_instance_pool_t *pool, void *memory);
/* Main-task allocation preflight only: try this order, then release all trial
 * blocks. Existing allocations remain alive. Does not initialize engines or
 * reserve capacity for a later commit; ownership must remain exclusive.
 * Sizes are nonzero, immutable and outside the pool; at most 32 requests. */
#define LUNAR_INSTANCE_PREFLIGHT_MAX 32u
int lunar_instance_pool_can_fit(lunar_instance_pool_t *pool,
                                const size_t *sizes, unsigned count);
#endif
