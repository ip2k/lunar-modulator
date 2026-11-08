/* SPDX-License-Identifier: MIT. Lunar fail-open boot: AC79 SDK glue API. */
#ifndef LUNAR_FAILOPEN_SDK_H
#define LUNAR_FAILOPEN_SDK_H

/* setup_arch(), right after the SDK reads the reset reason: counts the boot
 * and, on FALLBACK, tries mask-ROM entry once at this early stage. */
void lunar_failopen_early(int reason);
/* First statement of app_main(), before any task is created: honours the
 * key-combination hook, enters ROM when the early attempt was already used,
 * and otherwise starts the heartbeat supervisor. */
void lunar_failopen_app_start(void);

/* A task that must keep running registers once and beats more often than
 * `timeout_ms`. Returns the slot, or -1 when none is left. */
int lunar_failopen_watch(unsigned timeout_ms);
void lunar_failopen_beat(int slot);

/* Boots since the last healthy mark, including this one. */
unsigned lunar_failopen_boot_count(void);
/* Record a fault code just before a deliberate reset (test images). */
void lunar_failopen_note(unsigned fault);

/* Weak hook, returns 0 here. The FM-1 build overrides it with a read of the
 * key matrix (docs/07 section 4 rule 4: key combination -> USB update mode). */
int lunar_failopen_key_requested(void);

#endif
