/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_RECOVERY_REQUEST_H
#define LUNAR_RECOVERY_REQUEST_H

enum lunar_recovery_register { LUNAR_P33_CON, LUNAR_P33_DAT };
struct lunar_recovery_io {
    void *context;
    unsigned (*read)(void *, enum lunar_recovery_register);
    void (*write)(void *, enum lunar_recovery_register, unsigned);
    void (*sync)(void *);
    void (*mailbox_write)(void *, unsigned, unsigned char);
    unsigned char (*mailbox_read)(void *, unsigned);
};
struct lunar_recovery {
    struct lunar_recovery_io io;
    unsigned poll_limit, attempted, failed;
};
/* Fresh/quiescent storage only. Binding has no hardware effects. */
int lunar_recovery_bind(struct lunar_recovery *, const struct lunar_recovery_io *, unsigned);
/* One attempt per binding. Caller must establish current-core/IRQ policy,
 * exclusive P33 ownership, writable retained mailbox and clock/power readiness.
 * Writes exactly 16 mailbox bytes; verifies them before requesting chip reset.
 * 1 means request transmitted, NOT reset/recovery observed. 0 means failure.
 * On failure after mailbox writes, the marker may remain; never blindly retry.
 * No flash, core-release, write-guard disabling or arbitrary P33 operation. */
int lunar_recovery_request(struct lunar_recovery *);
#ifdef LUNAR_PI32V2
/* Target-only factory; includes an actual CSYNC barrier. No access on binding. */
void lunar_recovery_native_io(struct lunar_recovery_io *);
#endif
#endif
