/* SPDX-License-Identifier: MIT.
 * Lunar fail-open boot: the portable core (no SDK, no hardware access).
 *
 * A record kept in SRAM that survives a warm reset counts the boots that did
 * not reach "healthy", and the healthy boots that did not stay up long enough
 * to be "stable". After `limit` of either kind the decision becomes FALLBACK
 * and the platform glue enters mask-ROM UBOOT, so a boot-looping, hanging or
 * crash-after-healthy build ends up in a mode a USB host can recover without
 * a dongle (docs/07 section 4, rule 4). The record starts again on a
 * power-on, on a different image, and the cycle count when a boot is stable.
 *
 * Every function that changes the record or the monitor's slot table runs
 * between lunar_failopen_lock() and lunar_failopen_unlock(), which the
 * platform must define (no weak default, so a build without a lock does not
 * link). The heartbeat takes the same lock: it is a few stores, and a beat
 * from any core or interrupt then never races the supervisor's poll.
 *
 * SDK glue: firmware/failopen/failopen_sdk.c. Desktop tests:
 * tests/test_failopen_core.py. Evidence: notes/2026-11-08-failopen-watchdog.md
 * and notes/2026-11-08-failopen-hardening.md.
 */
#ifndef LUNAR_FAILOPEN_CORE_H
#define LUNAR_FAILOPEN_CORE_H

#include <stdint.h>

#define LUNAR_FAILOPEN_MAGIC 0x324f464cu          /* "LFO2" little-endian */

/* Reset-reason bits as AC79 SDK V1.2.13 asm/system_reset_reason.h numbers
 * them: VDDIO_PWR_ON = BIT(8), VDDIO_LOW_PWR = BIT(9). Either one means the
 * SRAM contents cannot be trusted, so the record starts again. The SDK glue
 * also sets them from the raw P3_RST_SRC bits it reads before the SDK does. */
#define LUNAR_FAILOPEN_REASON_COLD ((1u << 8) | (1u << 9))

#define LUNAR_FAILOPEN_FLAG_HEALTHY     0x1u  /* this boot reached healthy */
#define LUNAR_FAILOPEN_FLAG_EARLY_TRIED 0x2u  /* an early ROM entry was tried */
#define LUNAR_FAILOPEN_FLAG_KEY         0x4u  /* a key combination asked for ROM */
#define LUNAR_FAILOPEN_FLAG_STABLE      0x8u  /* this boot stayed up stable_ms */

/* The shortest heartbeat timeout a slot may register. A flash sector or block
 * erase stalls every core that executes from flash while the millisecond
 * clock keeps counting, so a timeout shorter than the longest erase would
 * report a healthy task as stalled. Bound: the dev kit's ZB25VQ64C 64 KB
 * block erase is 2 s at most [reported: Zbit datasheet V0.0, tBE2], the
 * FM-1's erases are 20 ms at most on either part it ships with: Puya P25Q80H
 * 20 ms [reported: Puya datasheet V1.7], UCUN UC25HQ80 10 ms [reported: UCUN
 * datasheet V1.2] (tools/fm1_flash_parts.py), plus one 100 ms supervisor
 * period and margin. Firmware issues sector or
 * block erases only, never a chip erase (tCE up to 100 s on the kit), and
 * yields between them (notes/2026-11-08-failopen-hardening.md). */
#ifndef LUNAR_FAILOPEN_MIN_TIMEOUT_MS
#define LUNAR_FAILOPEN_MIN_TIMEOUT_MS 3000u
#endif

/* Fault codes recorded just before a deliberate reset. */
enum lunar_failopen_fault {
    LUNAR_FAILOPEN_FAULT_NONE = 0,
    LUNAR_FAILOPEN_FAULT_STALL = 0x10,       /* + slot: a heartbeat stopped */
    LUNAR_FAILOPEN_FAULT_UNREGISTERED = 0x20,/* slots missing or refused */
    LUNAR_FAILOPEN_FAULT_SUPERVISOR = 0x30,  /* the supervisor task was not created */
    LUNAR_FAILOPEN_FAULT_TEST = 0x80         /* + case: deliberate test fault */
};

struct lunar_failopen_record {
    uint32_t magic;
    uint32_t image_id;     /* lunar_failopen_image_id of the running image */
    uint32_t count;        /* boots since the last healthy mark */
    uint32_t boots;        /* boots since the record was (re)started, saturating */
    uint32_t cycles;       /* healthy marks since the last stable mark, saturating */
    uint32_t last_reason;  /* reset-reason bits seen by the latest boot */
    uint32_t fault;        /* enum lunar_failopen_fault, set before a reset */
    uint32_t flags;        /* LUNAR_FAILOPEN_FLAG_* */
    uint32_t check;        /* FNV-1a over the eight words above */
};

enum lunar_failopen_decision {
    LUNAR_FAILOPEN_RUN = 0,
    LUNAR_FAILOPEN_FALLBACK = 1
};

/* What lunar_failopen_boot found before it changed anything. */
enum lunar_failopen_start {
    LUNAR_FAILOPEN_CONTINUED = 0,   /* valid record of this image, warm reset */
    LUNAR_FAILOPEN_FRESH_INVALID,   /* no valid record (first boot, corrupted) */
    LUNAR_FAILOPEN_FRESH_COLD,      /* power-on or brown-out reset */
    LUNAR_FAILOPEN_FRESH_BUILD      /* the record belonged to another image */
};

/* Platform hooks: a lock that excludes every other core and interrupt. */
void lunar_failopen_lock(void);
void lunar_failopen_unlock(void);

/* FNV-1a over `len` bytes; never 0. The glue hashes the application image as
 * the flash holds it, so any change to code or initialised data changes it. */
uint32_t lunar_failopen_image_id(const void *data, uint32_t len);

uint32_t lunar_failopen_check(const struct lunar_failopen_record *r);
int lunar_failopen_valid(const struct lunar_failopen_record *r);
void lunar_failopen_seal(struct lunar_failopen_record *r);

/* Called once per boot, as early as possible. `limit` boots in a row that do
 * not reach healthy are allowed to run; so are `limit` healthy boots in a row
 * that do not reach stable. The next boot returns FALLBACK, and so does every
 * later warm boot of the same image (sticky until a power-on or a new image).
 * A limit of 0 is treated as 1. `start` may be NULL. */
enum lunar_failopen_decision lunar_failopen_boot(struct lunar_failopen_record *r,
        uint32_t image_id, uint32_t reason, uint32_t limit,
        enum lunar_failopen_start *start);

/* Returns 1, and records the attempt, when no early ROM entry has been tried
 * since the counter last started; returns 0 when one was tried already. The
 * glue then defers the entry to a later context known to work. */
int lunar_failopen_claim_early(struct lunar_failopen_record *r);

/* Healthy: count 0, cycles + 1. Stable: cycles 0. */
void lunar_failopen_mark_healthy(struct lunar_failopen_record *r);
void lunar_failopen_mark_stable(struct lunar_failopen_record *r);
void lunar_failopen_note_fault(struct lunar_failopen_record *r, uint32_t fault);
void lunar_failopen_note_key(struct lunar_failopen_record *r);

/* Heartbeat supervisor, pure logic. The glue polls it from a high-priority
 * task with a millisecond clock; all time arithmetic is wrap-safe. */
#define LUNAR_FAILOPEN_SLOTS 4u

enum lunar_failopen_verdict {
    LUNAR_FAILOPEN_WAIT = 0,
    LUNAR_FAILOPEN_HEALTHY,          /* reported once per boot */
    LUNAR_FAILOPEN_STALLED,
    LUNAR_FAILOPEN_UNREGISTERED,     /* from healthy_ms on: a slot is missing, extra or refused */
    LUNAR_FAILOPEN_STABLE            /* reported once, stable_ms after start */
};

struct lunar_failopen_monitor {
    uint32_t start_ms;
    uint32_t healthy_ms;
    uint32_t stable_ms;
    uint32_t expected;     /* slots the image must register */
    uint32_t refused;      /* registrations turned away */
    volatile uint32_t slots;
    int healthy_reported;
    int stable_reported;
    /* 0 marks a slot that is still being registered; poll skips it. */
    volatile uint32_t timeout_ms[LUNAR_FAILOPEN_SLOTS];
    volatile uint32_t last_ms[LUNAR_FAILOPEN_SLOTS];
    volatile uint32_t beats[LUNAR_FAILOPEN_SLOTS];
};

void lunar_failopen_monitor_init(struct lunar_failopen_monitor *m, uint32_t now_ms,
                                 uint32_t healthy_ms, uint32_t stable_ms, uint32_t expected);
/* Returns the slot number, or -1 (and counts a refusal) when all slots are
 * taken or timeout_ms is below LUNAR_FAILOPEN_MIN_TIMEOUT_MS. */
int lunar_failopen_monitor_add(struct lunar_failopen_monitor *m, uint32_t timeout_ms,
                               uint32_t now_ms);
void lunar_failopen_monitor_beat(struct lunar_failopen_monitor *m, int slot, uint32_t now_ms);
/* STALLED wins and is reported for the lowest stalled slot. From healthy_ms
 * on, for the rest of the boot (before and after HEALTHY), a registration
 * count other than `expected` (or `expected` 0) or any refusal is
 * UNREGISTERED; otherwise HEALTHY once every slot has beaten since it was
 * added. STABLE follows once stable_ms has elapsed with HEALTHY already
 * reported. */
enum lunar_failopen_verdict lunar_failopen_monitor_poll(struct lunar_failopen_monitor *m,
        uint32_t now_ms, int *stalled_slot);

#endif
