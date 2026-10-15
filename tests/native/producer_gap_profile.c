/* SPDX-License-Identifier: GPL-3.0-only */
#include <assert.h>
#include <stdint.h>
#include "diagnostic_telemetry.h"
#include "producer_gap_profile.h"

int main(void)
{
    lunar_producer_gap_profile_t p;
    uint32_t values[LUNAR_PRODUCER_GAP_FIELDS];
    lunar_producer_gap_init(&p);
    assert(p.min_queue_depth == UINT32_MAX);

    /* First timestamp establishes a baseline; later subtraction wraps safely. */
    lunar_producer_gap_refill_entry(&p, 0xfffffff0u);
    lunar_producer_gap_refill_entry(&p, 0x00000014u);
    lunar_producer_gap_render(&p, 31u);
    lunar_producer_gap_render(&p, 47u);
    lunar_producer_gap_queue(&p, 7u);
    lunar_producer_gap_queue(&p, 2u);
    lunar_producer_gap_published(&p, 0xfffffff8u);
    lunar_producer_gap_published(&p, 0x00000020u);
    lunar_producer_gap_display(&p, 100u, 250u);
    lunar_producer_gap_display(&p, 80u, 400u);
    /* A full queue must not be reported as a publication by the caller. */
    lunar_producer_gap_snapshot(&p, 1234u, values);
    assert(values[0] == 1234u);
    assert(values[1] == 2u);
    assert(values[2] == 36u);
    assert(values[3] == 47u);
    assert(values[4] == 2u);
    assert(values[5] == 40u);
    assert(values[6] == 2u);
    assert(values[7] == 100u);
    assert(values[8] == 400u);
    assert(values[9] == 2u);

    /* Reporting resets interval data but retains timestamp continuity. */
    lunar_producer_gap_refill_entry(&p, 0x00000028u);
    lunar_producer_gap_published(&p, 0x00000030u);
    lunar_producer_gap_snapshot(&p, 2000u, values);
    assert(values[1] == 1u && values[2] == 20u);
    assert(values[4] == 1u && values[5] == 16u);
    assert(values[6] == UINT32_MAX);
    assert(values[9] == 0u);
    return 0;
}
