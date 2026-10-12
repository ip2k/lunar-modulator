/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_SDK_RECOVERY_TRACE_H
#define LUNAR_SDK_RECOVERY_TRACE_H
#include <stdint.h>

#define LUNAR_SDK_RECOVERY_TRACE_MAGIC 0x4c525431u
#define LUNAR_SDK_RECOVERY_TRACE_UNAVAILABLE 0xffffffffu
enum lunar_sdk_recovery_phase {
    LUNAR_TRACE_INITIALIZED = 1,
    LUNAR_TRACE_BEFORE_LOCK = 2,
    LUNAR_TRACE_ACQUIRED = 3,
    LUNAR_TRACE_MAILBOX_VERIFIED = 4,
    LUNAR_TRACE_FINAL_START_INTENT = 5,
    LUNAR_TRACE_RETURNED_SUCCESS = 6,
    LUNAR_TRACE_RETURNED_FAILURE = 7
};
/* Fixed little-endian wire layout, one owned RAM object, never the mailbox.
 * The nonce identifies an image/campaign, not a unique boot or authenticity. */
struct lunar_sdk_recovery_trace {
    uint32_t magic;
    uint16_t version, length;
    uint32_t nonce[4];
    uint32_t phase, phase_complement, mailbox_verified;
    int32_t panel_result;
    uint32_t elapsed_ms, heartbeat, startup_reason, sys_hz, lsb_hz;
    uint32_t publication_sequence;
};
extern volatile struct lunar_sdk_recovery_trace lunar_sdk_recovery_trace_record;
/* Required strong definitions when the diagnostic switch is enabled. */
void lunar_sdk_recovery_trace_init(void);
void lunar_sdk_recovery_trace_before_lock(int32_t panel_result, uint32_t elapsed_ms,
                                         uint32_t heartbeat, uint32_t sys_hz,
                                         uint32_t lsb_hz);
void lunar_sdk_recovery_trace_phase(uint32_t phase);
void lunar_sdk_recovery_trace_mailbox_verified(void);
void lunar_sdk_recovery_trace_final_start_intent(void);
#endif
