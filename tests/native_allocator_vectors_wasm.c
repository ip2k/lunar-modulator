/* SPDX-License-Identifier: MIT */
/* Run unmodified production instance-pool/TLSF code under WASM32. This checks
 * allocator geometry and ordered reservations only: not engine constructors,
 * pi32v2 code generation, audio, or FM-1 hardware behavior. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "instance_pool.h"
#include "tlsf.h"

#define POOL_BYTES 216064u
static unsigned char arena[POOL_BYTES] __attribute__((aligned(16)));

static int fits(const size_t *requests, unsigned count)
{
    lunar_instance_pool_t pool = {0};
    assert(lunar_instance_pool_init(&pool, arena, sizeof arena) == 0);
    int result = lunar_instance_pool_can_fit(&pool, requests, count);
    assert(pool.live_allocations == 0 && pool.live_bytes == 0);
    assert(tlsf_check(pool.allocator) == 0);
    assert(tlsf_check_pool(tlsf_get_pool(pool.allocator)) == 0);
    return result;
}

int main(void)
{
    assert(sizeof(void *) == 4);
    assert(sizeof(size_t) == 4);
    assert(tlsf_align_size() == 4);
    assert(tlsf_block_size_min() == 12);
    assert(tlsf_block_size_max() == (1u << 30));
    assert(tlsf_size() == 3188);
    assert(tlsf_pool_overhead() == 8);
    assert(tlsf_alloc_overhead() == 4);

    /* Canonical unit order from project_units.c: sound engines by slot,
     * inserts by sound/slot, then master FX by slot. Payload bytes are
     * target compiler measurements; TLSF and the pool add their own costs. */
    static const size_t replacement_event_horizon_showcase[] = {
        7648, 11224, 4240, 1248, 49888, 11952
    };
    static const size_t neon_transit[] = {
        7648, 19872, 19872, 16188, 656, 240, 65744, 49888, 11952
    };
    static const size_t packet_bloom_showcase[] = {
        5972, 4240, 71392, 78608, 49888, 11952
    };
    static const size_t afterglow_relay_showcase[] = {
        7648, 19872, 19872, 16188, 656, 240, 65744, 49888, 11952
    };
    assert(fits(replacement_event_horizon_showcase,
                sizeof replacement_event_horizon_showcase /
                sizeof replacement_event_horizon_showcase[0]));
    assert(fits(neon_transit, sizeof neon_transit / sizeof neon_transit[0]));
    assert(!fits(packet_bloom_showcase,
                 sizeof packet_bloom_showcase / sizeof packet_bloom_showcase[0]));
    assert(fits(afterglow_relay_showcase,
                sizeof afterglow_relay_showcase / sizeof afterglow_relay_showcase[0]));

    puts("WASM32 allocator geometry matched; Event Horizon, Neon Transit, and Afterglow Relay Showcase fit; Packet Bloom Showcase rejects");
    return 0;
}
