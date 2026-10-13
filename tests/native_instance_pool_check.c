/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "instance_pool.h"
#include "tlsf.h"

static struct {
    unsigned char before[16];
    unsigned char data[196608];
    unsigned char after[16];
} arena __attribute__((aligned(16)));

int main(int argc, char **argv)
{
    assert(argc == 2);
    unsigned shard = (unsigned)atoi(argv[1]);
    assert(shard < 16);
    lunar_instance_pool_t pool = {0}, other = {0};
    memset(&arena, 0xa5, sizeof arena);
    assert(lunar_instance_pool_init(NULL, arena.data, sizeof arena.data) == -1);
    assert(lunar_instance_pool_init(&pool, arena.data + 1, sizeof arena.data - 1) == -1);
    assert(lunar_instance_pool_init(&pool, arena.data, 16) == -1);
    assert(lunar_instance_pool_init(&pool, arena.data, SIZE_MAX) == -1);
    assert(lunar_instance_pool_init((lunar_instance_pool_t *)arena.data,
                                   arena.data, sizeof arena.data) == -1);
    assert(lunar_instance_pool_init(&pool, arena.data, sizeof arena.data) == 0);
    assert(!lunar_instance_pool_alloc(&pool, 0));
    assert(!lunar_instance_pool_alloc(&pool, SIZE_MAX));
    assert(!lunar_instance_pool_alloc(&pool, sizeof arena.data));
    assert(lunar_instance_pool_free(&pool, arena.after) == -1);
    assert(lunar_instance_pool_free(&pool, NULL) == 0);
    /* Sizes from actual pi32v2 inspection, plus boundary/fragmentation cases. */
    static const size_t sizes[] = {1, 15, 16, 17, 1248, 5984, 7648, 11224,
                                  16188, 19872, 41184, 65648, 65744, 71392, 206904};
    void *memory[14] = {0};
    size_t bytes[14] = {0};
    unsigned char pattern[14] = {0};
    uint32_t random = 0x31415926u ^ (shard + 1u);
    for (unsigned iteration = 0; iteration < 8192; ++iteration) {
        random = random * 1664525u + 1013904223u;
        unsigned slot = random % 14;
        size_t request = sizes[(random >> 8) % (sizeof sizes / sizeof sizes[0])];
        /* Reserve replacement before releasing old storage. OOM preserves it. */
        void *replacement = lunar_instance_pool_alloc(&pool, request);
        if (replacement) {
            assert(!((uintptr_t)replacement & 15u));
            assert(lunar_instance_pool_free(&other, replacement) == -1);
            if (memory[slot]) assert(lunar_instance_pool_free(&pool, memory[slot]) == 0);
            memory[slot] = replacement;
            bytes[slot] = request;
            pattern[slot] = (unsigned char)(iteration + shard);
            memset(replacement, pattern[slot], request);
        } else if ((random >> 31) && memory[slot]) {
            assert(lunar_instance_pool_free(&pool, memory[slot]) == 0);
            memory[slot] = NULL;
            bytes[slot] = 0;
        }
        size_t live_bytes = 0;
        unsigned live_allocations = 0;
        for (unsigned i = 0; i < 14; ++i) {
            if (!memory[i]) continue;
            const unsigned char *p = memory[i];
            for (size_t j = 0; j < bytes[i]; ++j) assert(p[j] == pattern[i]);
            live_bytes += bytes[i]; live_allocations++;
            for (unsigned k = i + 1; k < 14; ++k) {
                if (!memory[k]) continue;
                uintptr_t x = (uintptr_t)memory[i], y = (uintptr_t)memory[k];
                assert(x + bytes[i] <= y || y + bytes[k] <= x);
            }
        }
        assert(pool.live_bytes == live_bytes && pool.live_allocations == live_allocations);
        assert(tlsf_check(pool.allocator) == 0);
        assert(tlsf_check_pool(tlsf_get_pool(pool.allocator)) == 0);
        for (unsigned i = 0; i < 16; ++i)
            assert(arena.before[i] == 0xa5 && arena.after[i] == 0xa5);
    }
    for (unsigned i = 0; i < 14; ++i)
        if (memory[i]) assert(lunar_instance_pool_free(&pool, memory[i]) == 0);
    assert(pool.live_allocations == 0 && pool.live_bytes == 0);
    /* Adjacent free blocks must coalesce, rather than leaking capacity. */
    void *large = lunar_instance_pool_alloc(&pool, 180000);
    assert(large);
    memset(large, 0x5a, 180000);
    assert(lunar_instance_pool_free(&pool, large) == 0);
    assert(lunar_instance_pool_free(&pool, large) == -1);
    return 0;
}
