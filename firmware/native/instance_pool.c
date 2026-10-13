/* SPDX-License-Identifier: MIT */
#include "instance_pool.h"
#include "tlsf.h"

typedef struct {
    uintptr_t owner;
    size_t bytes;
    uint32_t magic;
} allocation_t;
#define HEADER_BYTES ((sizeof(allocation_t) + 15u) & ~(size_t)15u)
#define ALLOCATION_MAGIC 0x4c554e41u

int lunar_instance_pool_init(lunar_instance_pool_t *pool, void *buffer, size_t bytes)
{
    uintptr_t start = (uintptr_t)buffer, object = (uintptr_t)pool;
    if (!pool || !buffer || (start & 15u) || bytes > UINTPTR_MAX - start ||
        object > UINTPTR_MAX - sizeof *pool ||
        (object < start + bytes && start < object + sizeof *pool) ||
        bytes < tlsf_size() + tlsf_pool_overhead() + tlsf_block_size_min() ||
        bytes - tlsf_size() - tlsf_pool_overhead() > tlsf_block_size_max()) return -1;
    void *allocator = tlsf_create_with_pool(buffer, bytes);
    if (!allocator) return -1;
    pool->allocator = allocator;
    pool->lo = start;
    pool->hi = start + bytes;
    pool->live_bytes = 0;
    pool->live_allocations = 0;
    return 0;
}

void *lunar_instance_pool_alloc(lunar_instance_pool_t *pool, size_t bytes)
{
    if (!pool || !pool->allocator || !bytes || bytes > SIZE_MAX - HEADER_BYTES ||
        bytes > pool->hi - pool->lo || pool->live_bytes > SIZE_MAX - bytes ||
        pool->live_allocations == (unsigned)-1) return NULL;
    allocation_t *allocation = tlsf_memalign(pool->allocator, 16u, bytes + HEADER_BYTES);
    if (!allocation) return NULL;
    allocation->owner = (uintptr_t)pool;
    allocation->bytes = bytes;
    allocation->magic = ALLOCATION_MAGIC;
    pool->live_bytes += bytes;
    pool->live_allocations++;
    return (unsigned char *)allocation + HEADER_BYTES;
}

int lunar_instance_pool_free(lunar_instance_pool_t *pool, void *memory)
{
    if (!memory) return 0;
    uintptr_t address = (uintptr_t)memory;
    if (!pool || !pool->allocator || (address & 15u) || address < pool->lo ||
        address >= pool->hi || address - pool->lo < HEADER_BYTES) return -1;
    allocation_t *allocation = (allocation_t *)(address - HEADER_BYTES);
    if (allocation->magic != ALLOCATION_MAGIC || allocation->owner != (uintptr_t)pool ||
        !allocation->bytes || allocation->bytes > pool->hi - address ||
        allocation->bytes > pool->live_bytes || !pool->live_allocations) return -1;
    pool->live_bytes -= allocation->bytes;
    pool->live_allocations--;
    allocation->magic = 0;
    tlsf_free(pool->allocator, allocation);
    return 0;
}

int lunar_instance_pool_can_fit(lunar_instance_pool_t *pool,
                                const size_t *sizes, unsigned count)
{
    void *trial[LUNAR_INSTANCE_PREFLIGHT_MAX];
    unsigned allocated = 0;
    uintptr_t input = (uintptr_t)sizes;
    size_t span;
    int ok;
    if (!pool || !pool->allocator || count > LUNAR_INSTANCE_PREFLIGHT_MAX ||
        (count && !sizes)) return 0;
    span = count * sizeof *sizes;
    if (count && (input > UINTPTR_MAX - span ||
        (input < pool->hi && pool->lo < input + span))) return 0;
    for (; allocated < count; ++allocated) {
        trial[allocated] = lunar_instance_pool_alloc(pool, sizes[allocated]);
        if (!trial[allocated]) break;
    }
    ok = allocated == count;
    while (allocated) {
        if (lunar_instance_pool_free(pool, trial[--allocated])) ok = 0;
    }
    return ok;
}
