/* SPDX-License-Identifier: MIT.
 * Lunar fail-open boot: the portable core (no SDK, no hardware access).
 *
 * A record kept in SRAM that survives a warm reset counts the boots that did
 * not reach "healthy". After `limit` such boots the decision becomes FALLBACK
 * and the platform glue enters mask-ROM UBOOT, so a boot-looping or hanging
 * build ends up in a mode a USB host can recover without a dongle (docs/07
 * section 4, rule 4). The record starts again on a power-on, on a different
 * build, and when the running build reports itself healthy.
 *
 * SDK glue: firmware/failopen/failopen_sdk.c. Desktop tests:
 * tests/test_failopen_core.py.
 */
#ifndef LUNAR_FAILOPEN_CORE_H
#define LUNAR_FAILOPEN_CORE_H

#include <stdint.h>

#define LUNAR_FAILOPEN_MAGIC 0x314f464cu          /* "LFO1" little-endian */

/* Reset-reason bits as AC79 SDK V1.2.13 asm/system_reset_reason.h numbers
 * them: VDDIO_PWR_ON = BIT(8), VDDIO_LOW_PWR = BIT(9). Either one means the
 * SRAM contents cannot be trusted, so the counter starts again. */
#define LUNAR_FAILOPEN_REASON_COLD ((1u << 8) | (1u << 9))

#define LUNAR_FAILOPEN_FLAG_HEALTHY     0x1u  /* this boot reached healthy */
#define LUNAR_FAILOPEN_FLAG_EARLY_TRIED 0x2u  /* an early ROM entry was tried */
#define LUNAR_FAILOPEN_FLAG_KEY         0x4u  /* a key combination asked for ROM */

/* Fault codes recorded just before a deliberate reset. */
enum lunar_failopen_fault {
    LUNAR_FAILOPEN_FAULT_NONE = 0,
    LUNAR_FAILOPEN_FAULT_STALL = 0x10,       /* + slot: a heartbeat stopped */
    LUNAR_FAILOPEN_FAULT_TEST = 0x80         /* + case: deliberate test fault */
};

struct lunar_failopen_record {
    uint32_t magic;
    uint32_t build_id;
    uint32_t count;        /* boots since the last healthy mark, saturating */
    uint32_t boots;        /* boots since the record was (re)started */
    uint32_t last_reason;  /* reset-reason bits seen by the latest boot */
    uint32_t fault;        /* enum lunar_failopen_fault, set before a reset */
    uint32_t flags;        /* LUNAR_FAILOPEN_FLAG_* */
    uint32_t check;        /* FNV-1a over the seven words above */
};

enum lunar_failopen_decision {
    LUNAR_FAILOPEN_RUN = 0,
    LUNAR_FAILOPEN_FALLBACK = 1
};

/* What lunar_failopen_boot found before it changed anything. */
enum lunar_failopen_start {
    LUNAR_FAILOPEN_CONTINUED = 0,   /* valid record of this build, warm reset */
    LUNAR_FAILOPEN_FRESH_INVALID,   /* no valid record (first boot, corrupted) */
    LUNAR_FAILOPEN_FRESH_COLD,      /* power-on or brown-out reset */
    LUNAR_FAILOPEN_FRESH_BUILD      /* the record belonged to another build */
};

uint32_t lunar_failopen_check(const struct lunar_failopen_record *r);
int lunar_failopen_valid(const struct lunar_failopen_record *r);
void lunar_failopen_seal(struct lunar_failopen_record *r);

/* Called once per boot, as early as possible. `limit` boots in a row that do
 * not reach healthy are allowed to run; the next one returns FALLBACK, and so
 * does every later warm boot of the same build (sticky until a power-on, a new
 * build or a healthy mark). A limit of 0 is treated as 1. `start` may be NULL. */
enum lunar_failopen_decision lunar_failopen_boot(struct lunar_failopen_record *r,
        uint32_t build_id, uint32_t reason, uint32_t limit,
        enum lunar_failopen_start *start);

/* Returns 1, and records the attempt, when no early ROM entry has been tried
 * since the counter last started; returns 0 when one was tried already. The
 * glue then defers the entry to a later context known to work. */
int lunar_failopen_claim_early(struct lunar_failopen_record *r);

void lunar_failopen_mark_healthy(struct lunar_failopen_record *r);
void lunar_failopen_note_fault(struct lunar_failopen_record *r, uint32_t fault);
void lunar_failopen_note_key(struct lunar_failopen_record *r);

/* Heartbeat supervisor, pure logic. The glue polls it from a high-priority
 * task with a millisecond clock; all time arithmetic is wrap-safe. */
#define LUNAR_FAILOPEN_SLOTS 4u

enum lunar_failopen_verdict {
    LUNAR_FAILOPEN_WAIT = 0,
    LUNAR_FAILOPEN_HEALTHY,          /* reported once per boot */
    LUNAR_FAILOPEN_STALLED
};

struct lunar_failopen_monitor {
    uint32_t start_ms;
    uint32_t healthy_ms;
    volatile uint32_t slots;
    int healthy_reported;
    /* 0 marks a slot that is still being registered; poll skips it. */
    volatile uint32_t timeout_ms[LUNAR_FAILOPEN_SLOTS];
    volatile uint32_t last_ms[LUNAR_FAILOPEN_SLOTS];
    volatile uint32_t beats[LUNAR_FAILOPEN_SLOTS];
};

void lunar_failopen_monitor_init(struct lunar_failopen_monitor *m, uint32_t now_ms,
                                 uint32_t healthy_ms);
/* Returns the slot number, or -1 when all slots are taken or timeout is 0. */
int lunar_failopen_monitor_add(struct lunar_failopen_monitor *m, uint32_t timeout_ms,
                               uint32_t now_ms);
void lunar_failopen_monitor_beat(struct lunar_failopen_monitor *m, int slot, uint32_t now_ms);
/* HEALTHY needs healthy_ms elapsed since init, at least one slot, and every
 * slot beaten at least once since it was added. STALLED wins over HEALTHY and
 * is reported for the lowest stalled slot. */
enum lunar_failopen_verdict lunar_failopen_monitor_poll(struct lunar_failopen_monitor *m,
        uint32_t now_ms, int *stalled_slot);

#endif
