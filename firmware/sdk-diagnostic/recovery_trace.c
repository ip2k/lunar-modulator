/* SPDX-License-Identifier: MIT
 * Only owned RAM stores and barriers; no SDK services or peripheral accesses. */
#include "recovery_trace.h"
#include "recovery_trace_nonce.h"
#include <stddef.h>

#ifndef LUNAR_SDK_RECOVERY_TRACE
#error "Recovery trace is only for the explicitly enabled SDK diagnostic"
#endif
typedef char trace_size_must_be_64[(sizeof(struct lunar_sdk_recovery_trace) == 64) ? 1 : -1];
typedef char trace_phase_offset[(offsetof(struct lunar_sdk_recovery_trace, phase) == 24) ? 1 : -1];
typedef char trace_sequence_offset[(offsetof(struct lunar_sdk_recovery_trace, publication_sequence) == 60) ? 1 : -1];
volatile struct lunar_sdk_recovery_trace lunar_sdk_recovery_trace_record
    __attribute__((aligned(16), used));

static inline void trace_sync(void)
{
#ifdef LUNAR_PI32V2
    __asm__ volatile("csync;" ::: "memory");
#else
    __asm__ volatile("" ::: "memory");
#endif
}
static uint32_t begin_publication(void)
{
    uint32_t sequence = lunar_sdk_recovery_trace_record.publication_sequence + 1u;
    lunar_sdk_recovery_trace_record.publication_sequence = sequence;
    trace_sync();
    return sequence;
}
static void finish_publication(uint32_t sequence, uint32_t phase)
{
    lunar_sdk_recovery_trace_record.phase = phase;
    lunar_sdk_recovery_trace_record.phase_complement = ~phase;
    trace_sync();
    lunar_sdk_recovery_trace_record.publication_sequence = sequence + 1u;
    trace_sync();
}
void lunar_sdk_recovery_trace_init(void)
{
    lunar_sdk_recovery_trace_record.publication_sequence = 1u;
    trace_sync();
    lunar_sdk_recovery_trace_record.magic = LUNAR_SDK_RECOVERY_TRACE_MAGIC;
    lunar_sdk_recovery_trace_record.version = 1u;
    lunar_sdk_recovery_trace_record.length = 64u;
    lunar_sdk_recovery_trace_record.nonce[0] = LUNAR_SDK_RECOVERY_NONCE_0;
    lunar_sdk_recovery_trace_record.nonce[1] = LUNAR_SDK_RECOVERY_NONCE_1;
    lunar_sdk_recovery_trace_record.nonce[2] = LUNAR_SDK_RECOVERY_NONCE_2;
    lunar_sdk_recovery_trace_record.nonce[3] = LUNAR_SDK_RECOVERY_NONCE_3;
    lunar_sdk_recovery_trace_record.mailbox_verified = 0u;
    lunar_sdk_recovery_trace_record.panel_result = 0;
    lunar_sdk_recovery_trace_record.elapsed_ms = 0u;
    lunar_sdk_recovery_trace_record.heartbeat = 0u;
    /* No safe existing cached-reason declaration is established. */
    lunar_sdk_recovery_trace_record.startup_reason = LUNAR_SDK_RECOVERY_TRACE_UNAVAILABLE;
    lunar_sdk_recovery_trace_record.sys_hz = 0u;
    lunar_sdk_recovery_trace_record.lsb_hz = 0u;
    finish_publication(1u, LUNAR_TRACE_INITIALIZED);
}
void lunar_sdk_recovery_trace_before_lock(int32_t panel_result, uint32_t elapsed_ms,
                                         uint32_t heartbeat, uint32_t sys_hz,
                                         uint32_t lsb_hz)
{
    uint32_t sequence = begin_publication();
    lunar_sdk_recovery_trace_record.panel_result = panel_result;
    lunar_sdk_recovery_trace_record.elapsed_ms = elapsed_ms;
    lunar_sdk_recovery_trace_record.heartbeat = heartbeat;
    lunar_sdk_recovery_trace_record.sys_hz = sys_hz;
    lunar_sdk_recovery_trace_record.lsb_hz = lsb_hz;
    finish_publication(sequence, LUNAR_TRACE_BEFORE_LOCK);
}
void lunar_sdk_recovery_trace_phase(uint32_t phase)
{
    uint32_t sequence = begin_publication();
    finish_publication(sequence, phase);
}
void lunar_sdk_recovery_trace_mailbox_verified(void)
{
    uint32_t sequence = begin_publication();
    lunar_sdk_recovery_trace_record.mailbox_verified = 1u;
    finish_publication(sequence, LUNAR_TRACE_MAILBOX_VERIFIED);
}
void lunar_sdk_recovery_trace_final_start_intent(void)
{
    uint32_t sequence = begin_publication();
    finish_publication(sequence, LUNAR_TRACE_FINAL_START_INTENT);
}
