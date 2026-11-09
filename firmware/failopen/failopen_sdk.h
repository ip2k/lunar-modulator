/* SPDX-License-Identifier: MIT. Lunar fail-open boot: AC79 SDK glue API. */
#ifndef LUNAR_FAILOPEN_SDK_H
#define LUNAR_FAILOPEN_SDK_H

/* setup_arch(), in place of its system_reset_reason_get() call: reads the raw
 * reset registers, then the SDK's reason, hashes the image, counts the boot
 * and, on FALLBACK, tries mask-ROM entry once at this early stage. */
void lunar_failopen_early(void);
/* First statement of app_main(), before any task is created: honours the
 * key-combination hook, enters ROM when the early attempt was already used,
 * and otherwise starts the heartbeat supervisor. The image must then register
 * exactly LUNAR_FAILOPEN_EXPECTED_SLOTS slots before the healthy time. */
void lunar_failopen_app_start(void);

/* A task that must keep running registers once and beats more often than
 * `timeout_ms` (at least LUNAR_FAILOPEN_MIN_TIMEOUT_MS). Returns the slot, or
 * -1 when it was refused; a refusal resets the board at the healthy time. */
int lunar_failopen_watch(unsigned timeout_ms);
void lunar_failopen_beat(int slot);

/* Boots since the last healthy mark, including this one. */
unsigned lunar_failopen_boot_count(void);
/* Boots since the record was (re)started, including this one. */
unsigned lunar_failopen_boots(void);
/* The record's checksum, read under the lock (test images). */
int lunar_failopen_record_ok(void);
/* Record a fault code just before a deliberate reset (test images). */
void lunar_failopen_note(unsigned fault);

/* Weak hook, returns 0 here. The FM-1 build overrides it with a read of the
 * key matrix (docs/07 section 4 rule 4: key combination -> USB update mode). */
int lunar_failopen_key_requested(void);

#endif
