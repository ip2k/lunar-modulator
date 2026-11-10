"""Fail-open boot core (firmware/failopen) and its dev-kit preparer, on the desktop."""
from pathlib import Path
import hashlib
import importlib.util
import json
import platform
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
#include "failopen_core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

#define WARM 0x10u            /* SYS_RST_SOFT */
#define WDT 0x4u              /* SYS_RST_WDT */
#define POWER_ON 0x100u       /* SYS_RST_VDDIO_PWR_ON */
#define LOW_POWER 0x200u      /* SYS_RST_VDDIO_LOW_PWR */
#define MIN LUNAR_FAILOPEN_MIN_TIMEOUT_MS

/* The platform lock, instrumented: every core entry point must take it and
 * leave it balanced. */
static int depth, taken;
void lunar_failopen_lock(void) { assert(depth == 0); ++depth; ++taken; }
void lunar_failopen_unlock(void) { assert(depth == 1); --depth; }
#define LOCKED(call) do { int before = taken; call; assert(depth == 0 && taken > before); } while (0)

static enum lunar_failopen_decision boot(struct lunar_failopen_record *r, uint32_t image,
                                         uint32_t reason, enum lunar_failopen_start expect) {
    enum lunar_failopen_start start = (enum lunar_failopen_start)99;
    enum lunar_failopen_decision d = LUNAR_FAILOPEN_RUN;
    LOCKED(d = lunar_failopen_boot(r, image, reason, 3, &start));
    assert(start == expect);
    assert(lunar_failopen_valid(r));
    assert(r->image_id == image && r->last_reason == reason);
    return d;
}

static void healthy(struct lunar_failopen_record *r) { LOCKED(lunar_failopen_mark_healthy(r)); }
static void stable(struct lunar_failopen_record *r) { LOCKED(lunar_failopen_mark_stable(r)); }

static void records(void) {
    struct lunar_failopen_record r;
    unsigned i;
    int claimed = 0;
    memset(&r, 0xa5, sizeof(r));                 /* SRAM garbage */
    assert(!lunar_failopen_valid(&r));
    assert(boot(&r, 7, POWER_ON, LUNAR_FAILOPEN_FRESH_INVALID) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 1 && r.boots == 1 && r.cycles == 0 && r.flags == 0 && r.fault == 0);
    /* Two more failed warm boots still run; the fourth falls back. */
    LOCKED(lunar_failopen_note_fault(&r, LUNAR_FAILOPEN_FAULT_TEST + 1));
    assert(boot(&r, 7, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 2 && r.fault == 0);
    assert(boot(&r, 7, WDT, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 3);
    LOCKED(lunar_failopen_note_fault(&r, LUNAR_FAILOPEN_FAULT_STALL));
    assert(boot(&r, 7, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_FALLBACK);
    assert(r.count == 3 && r.boots == 4);
    assert(r.fault == LUNAR_FAILOPEN_FAULT_STALL);   /* kept for the report */
    /* Early entry is claimed once; a return to this point defers to later. */
    LOCKED(claimed = lunar_failopen_claim_early(&r));
    assert(claimed == 1 && lunar_failopen_valid(&r));
    assert(boot(&r, 7, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_FALLBACK);
    LOCKED(claimed = lunar_failopen_claim_early(&r));
    assert(claimed == 0);
    /* Sticky across many warm resets, and the counters never wrap. */
    for (i = 0; i < 100; ++i)
        assert(boot(&r, 7, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_FALLBACK);
    assert(r.count == 3 && r.boots == 105);
    r.boots = UINT32_MAX;
    lunar_failopen_seal(&r);
    assert(boot(&r, 7, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_FALLBACK);
    assert(r.boots == UINT32_MAX);
    /* A new image starts again, so a fix installed from UBOOT runs. */
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_FRESH_BUILD) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 1 && r.boots == 1 && !(r.flags & LUNAR_FAILOPEN_FLAG_EARLY_TRIED));
    /* Healthy clears the count and the early-entry claim, and counts a cycle. */
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    r.flags |= LUNAR_FAILOPEN_FLAG_EARLY_TRIED;
    healthy(&r);
    assert(lunar_failopen_valid(&r) && r.count == 0 && r.cycles == 1);
    assert(r.flags == LUNAR_FAILOPEN_FLAG_HEALTHY);
    /* Stable clears the cycles; the next boot clears both marks. */
    stable(&r);
    assert(lunar_failopen_valid(&r) && r.cycles == 0);
    assert(r.flags == (LUNAR_FAILOPEN_FLAG_HEALTHY | LUNAR_FAILOPEN_FLAG_STABLE));
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 1 && r.flags == 0);
    /* Power-on and brown-out start again even with a valid record. */
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_FALLBACK);
    assert(boot(&r, 8, POWER_ON | WARM, LUNAR_FAILOPEN_FRESH_COLD) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 1);
    assert(boot(&r, 8, LOW_POWER, LUNAR_FAILOPEN_FRESH_COLD) == LUNAR_FAILOPEN_RUN);
    /* Any single changed bit invalidates the record. */
    for (i = 0; i < 8 * sizeof(r); ++i) {
        struct lunar_failopen_record c = r;
        ((unsigned char *)&c)[i / 8] ^= (unsigned char)(1u << (i % 8));
        assert(!lunar_failopen_valid(&c));
    }
    /* Key request survives in the record until the next boot. */
    LOCKED(lunar_failopen_note_key(&r));
    assert(lunar_failopen_valid(&r) && (r.flags & LUNAR_FAILOPEN_FLAG_KEY));
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(!(r.flags & LUNAR_FAILOPEN_FLAG_KEY));
    /* Limit 0 behaves as 1; limit 1 falls back on the second failed boot. */
    memset(&r, 0, sizeof(r));
    assert(lunar_failopen_boot(&r, 9, WARM, 0, NULL) == LUNAR_FAILOPEN_RUN);
    assert(lunar_failopen_boot(&r, 9, WARM, 0, NULL) == LUNAR_FAILOPEN_FALLBACK);
    assert(sizeof(r) == 36 && sizeof(r) <= 64);
}

/* A build that reaches healthy and then crashes, again and again, falls back
 * after `limit` such boots instead of looping forever (review finding 5). */
static void escalation(void) {
    struct lunar_failopen_record r;
    unsigned i;
    memset(&r, 0, sizeof(r));
    assert(boot(&r, 5, POWER_ON, LUNAR_FAILOPEN_FRESH_INVALID) == LUNAR_FAILOPEN_RUN);
    for (i = 1; i <= 3; ++i) {
        healthy(&r);
        assert(r.count == 0 && r.cycles == i);
        assert(boot(&r, 5, WARM, LUNAR_FAILOPEN_CONTINUED) ==
               (i < 3 ? LUNAR_FAILOPEN_RUN : LUNAR_FAILOPEN_FALLBACK));
    }
    assert(r.cycles == 3 && r.count == 0);     /* FALLBACK raises nothing */
    /* Sticky, and a late healthy mark cannot happen (the glue never starts
     * the supervisor on FALLBACK); power-on starts again. */
    assert(boot(&r, 5, WDT, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_FALLBACK);
    assert(boot(&r, 5, POWER_ON, LUNAR_FAILOPEN_FRESH_COLD) == LUNAR_FAILOPEN_RUN);
    assert(r.cycles == 0);
    /* A stable boot in between resets the cycle count. */
    healthy(&r);
    assert(boot(&r, 5, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    healthy(&r);
    assert(r.cycles == 2);
    stable(&r);
    for (i = 0; i < 10; ++i) {
        assert(boot(&r, 5, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
        healthy(&r);
        stable(&r);
    }
    /* Mixed: failed boots and crash-after-healthy boots are separate limits. */
    assert(boot(&r, 5, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    healthy(&r);
    assert(boot(&r, 5, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(boot(&r, 5, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 2 && r.cycles == 1);
    r.cycles = UINT32_MAX;                       /* saturates */
    lunar_failopen_seal(&r);
    healthy(&r);
    assert(r.cycles == UINT32_MAX);
}

/* A record written by the PR #180 image (LFO1, 32 bytes) is not trusted. */
static void old_record(void) {
    uint32_t words[9] = {0x314f464cu, 0x12345678u, 1, 1, 0x10, 0, 0, 0, 0};
    struct lunar_failopen_record r;
    memcpy(&r, words, sizeof(r));
    assert(!lunar_failopen_valid(&r));
    r.magic = LUNAR_FAILOPEN_MAGIC;
    assert(!lunar_failopen_valid(&r));           /* checksum still wrong */
    assert(boot(&r, 3, WARM, LUNAR_FAILOPEN_FRESH_INVALID) == LUNAR_FAILOPEN_RUN);
}

static void monitor(void) {
    struct lunar_failopen_monitor m;
    int slot = -1, a = -1, b = -1, c = -1;
    enum lunar_failopen_verdict v = LUNAR_FAILOPEN_WAIT;
    uint32_t t0 = 0xfffff000u;                    /* wraps during the test */
    LOCKED(lunar_failopen_monitor_init(&m, t0, 10000, 30000, 2));
    LOCKED(v = lunar_failopen_monitor_poll(&m, t0 + 5000, &slot));
    assert(v == LUNAR_FAILOPEN_WAIT);
    LOCKED(a = lunar_failopen_monitor_add(&m, 6000, t0));
    LOCKED(b = lunar_failopen_monitor_add(&m, MIN, t0 + 100));
    assert(a == 0 && b == 1 && m.refused == 0);
    /* Timeouts below the erase bound are refused and counted. */
    LOCKED(c = lunar_failopen_monitor_add(&m, 0, t0));
    assert(c == -1);
    LOCKED(c = lunar_failopen_monitor_add(&m, MIN - 1, t0));
    assert(c == -1 && m.refused == 2 && m.slots == 2);
    m.refused = 0;                                /* continue as a clean image */
    LOCKED(lunar_failopen_monitor_beat(&m, a, t0 + 500));
    LOCKED(lunar_failopen_monitor_beat(&m, 7, t0 + 500));     /* ignored */
    LOCKED(lunar_failopen_monitor_beat(&m, -1, t0 + 500));    /* ignored */
    /* b has not beaten yet: not healthy, and stalled once its timeout passes. */
    assert(lunar_failopen_monitor_poll(&m, t0 + 3000, &slot) == LUNAR_FAILOPEN_WAIT);
    assert(lunar_failopen_monitor_poll(&m, t0 + 100 + MIN + 1, &slot) == LUNAR_FAILOPEN_STALLED);
    assert(slot == 1);
    for (uint32_t t = t0 + 3500; t < t0 + 10000; t += 500) {
        lunar_failopen_monitor_beat(&m, a, t);
        lunar_failopen_monitor_beat(&m, b, t);
        assert(lunar_failopen_monitor_poll(&m, t, &slot) == LUNAR_FAILOPEN_WAIT);
    }
    lunar_failopen_monitor_beat(&m, a, t0 + 10000);
    lunar_failopen_monitor_beat(&m, b, t0 + 10000);
    assert(lunar_failopen_monitor_poll(&m, t0 + 10000, &slot) == LUNAR_FAILOPEN_HEALTHY);
    assert(lunar_failopen_monitor_poll(&m, t0 + 10100, &slot) == LUNAR_FAILOPEN_WAIT);
    /* Stable is reported once, at stable_ms. */
    for (uint32_t t = t0 + 10500; t < t0 + 30000; t += 500) {
        lunar_failopen_monitor_beat(&m, a, t);
        lunar_failopen_monitor_beat(&m, b, t);
        assert(lunar_failopen_monitor_poll(&m, t, &slot) == LUNAR_FAILOPEN_WAIT);
    }
    lunar_failopen_monitor_beat(&m, a, t0 + 30000);
    lunar_failopen_monitor_beat(&m, b, t0 + 30000);
    assert(lunar_failopen_monitor_poll(&m, t0 + 30000, &slot) == LUNAR_FAILOPEN_STABLE);
    assert(lunar_failopen_monitor_poll(&m, t0 + 30100, &slot) == LUNAR_FAILOPEN_WAIT);
    /* Stall after stable is still reported; the lowest stalled slot wins. */
    assert(lunar_failopen_monitor_poll(&m, t0 + 37000, &slot) == LUNAR_FAILOPEN_STALLED);
    assert(slot == 0);
    /* A slot caught half-registered (published, timeout not yet stored) is
     * neither stalled nor counted as seen, however old its timestamp. */
    lunar_failopen_monitor_init(&m, 0, 1000, 1000, 1);
    m.slots = 1;
    m.last_ms[0] = 0;
    assert(lunar_failopen_monitor_poll(&m, 50000, &slot) == LUNAR_FAILOPEN_WAIT);
    m.timeout_ms[0] = MIN;
    m.last_ms[0] = 50000;
    m.beats[0] = 1;
    assert(lunar_failopen_monitor_poll(&m, 50050, &slot) == LUNAR_FAILOPEN_HEALTHY);
    /* healthy_ms == stable_ms: stable on the next poll. */
    assert(lunar_failopen_monitor_poll(&m, 50060, &slot) == LUNAR_FAILOPEN_STABLE);
    /* Slots are bounded, and the overflow is a refusal. */
    lunar_failopen_monitor_init(&m, 0, 1000, 1000, LUNAR_FAILOPEN_SLOTS);
    for (a = 0; a < (int)LUNAR_FAILOPEN_SLOTS; ++a)
        assert(lunar_failopen_monitor_add(&m, MIN, 0) == a);
    assert(lunar_failopen_monitor_add(&m, MIN, 0) == -1 && m.refused == 1);
}

/* Registration is mandatory (review finding 2): at the healthy time the image
 * must have registered exactly the expected slots, with nothing refused. */
static void registration(void) {
    struct lunar_failopen_monitor m;
    int slot = -1, s;
    /* No slot at all: the old monitor waited forever; now UNREGISTERED. */
    lunar_failopen_monitor_init(&m, 0, 1000, 5000, 1);
    assert(lunar_failopen_monitor_poll(&m, 999, &slot) == LUNAR_FAILOPEN_WAIT);
    assert(lunar_failopen_monitor_poll(&m, 1000, &slot) == LUNAR_FAILOPEN_UNREGISTERED);
    /* Fewer than expected, every registered one beating. */
    lunar_failopen_monitor_init(&m, 0, 1000, 5000, 2);
    s = lunar_failopen_monitor_add(&m, MIN, 0);
    lunar_failopen_monitor_beat(&m, s, 900);
    assert(lunar_failopen_monitor_poll(&m, 1000, &slot) == LUNAR_FAILOPEN_UNREGISTERED);
    /* More than expected. */
    lunar_failopen_monitor_init(&m, 0, 1000, 5000, 1);
    lunar_failopen_monitor_beat(&m, lunar_failopen_monitor_add(&m, MIN, 0), 900);
    lunar_failopen_monitor_beat(&m, lunar_failopen_monitor_add(&m, MIN, 0), 900);
    assert(lunar_failopen_monitor_poll(&m, 1000, &slot) == LUNAR_FAILOPEN_UNREGISTERED);
    /* The expected count, but one more was refused for a short timeout. */
    lunar_failopen_monitor_init(&m, 0, 1000, 5000, 1);
    lunar_failopen_monitor_beat(&m, lunar_failopen_monitor_add(&m, MIN, 0), 900);
    assert(lunar_failopen_monitor_add(&m, 100, 0) == -1);
    assert(lunar_failopen_monitor_poll(&m, 1000, &slot) == LUNAR_FAILOPEN_UNREGISTERED);
    /* Expected 0 never reaches healthy. */
    lunar_failopen_monitor_init(&m, 0, 1000, 5000, 0);
    assert(lunar_failopen_monitor_poll(&m, 1000, &slot) == LUNAR_FAILOPEN_UNREGISTERED);
    /* A stall still wins over the registration check. */
    lunar_failopen_monitor_init(&m, 0, MIN * 2, MIN * 4, 2);
    lunar_failopen_monitor_add(&m, MIN, 0);
    assert(lunar_failopen_monitor_poll(&m, MIN * 2, &slot) == LUNAR_FAILOPEN_STALLED && slot == 0);
    /* The check holds for the rest of the boot (adversarial review): after
     * HEALTHY, a late extra slot, or a late refusal, is UNREGISTERED, before
     * and after STABLE, instead of leaving that task unwatched. */
    lunar_failopen_monitor_init(&m, 0, 1000, 5000, 1);
    s = lunar_failopen_monitor_add(&m, MIN, 0);
    lunar_failopen_monitor_beat(&m, s, 900);
    assert(lunar_failopen_monitor_poll(&m, 1000, &slot) == LUNAR_FAILOPEN_HEALTHY);
    lunar_failopen_monitor_beat(&m, s, 1500);
    assert(lunar_failopen_monitor_poll(&m, 1500, &slot) == LUNAR_FAILOPEN_WAIT);
    assert(lunar_failopen_monitor_add(&m, MIN, 1600) == 1);         /* one too many */
    lunar_failopen_monitor_beat(&m, s, 1700);
    lunar_failopen_monitor_beat(&m, 1, 1700);
    assert(lunar_failopen_monitor_poll(&m, 1700, &slot) == LUNAR_FAILOPEN_UNREGISTERED);
    lunar_failopen_monitor_init(&m, 0, 1000, 5000, 1);
    s = lunar_failopen_monitor_add(&m, MIN, 0);
    lunar_failopen_monitor_beat(&m, s, 900);
    assert(lunar_failopen_monitor_poll(&m, 1000, &slot) == LUNAR_FAILOPEN_HEALTHY);
    lunar_failopen_monitor_beat(&m, s, 2000);
    assert(lunar_failopen_monitor_add(&m, 100, 2000) == -1);        /* refused late */
    assert(lunar_failopen_monitor_poll(&m, 2000, &slot) == LUNAR_FAILOPEN_UNREGISTERED);
    lunar_failopen_monitor_init(&m, 0, 1000, 1000, 1);
    s = lunar_failopen_monitor_add(&m, MIN, 0);
    lunar_failopen_monitor_beat(&m, s, 900);
    assert(lunar_failopen_monitor_poll(&m, 1000, &slot) == LUNAR_FAILOPEN_HEALTHY);
    assert(lunar_failopen_monitor_poll(&m, 1100, &slot) == LUNAR_FAILOPEN_STABLE);
    lunar_failopen_monitor_beat(&m, s, 1200);
    assert(lunar_failopen_monitor_add(&m, MIN, 1200) == 1);         /* after STABLE too */
    lunar_failopen_monitor_beat(&m, 1, 1300);
    assert(lunar_failopen_monitor_poll(&m, 1300, &slot) == LUNAR_FAILOPEN_UNREGISTERED);
    /* Before healthy_ms a refusal or a wrong count is only waited on. */
    lunar_failopen_monitor_init(&m, 0, 1000, 5000, 1);
    assert(lunar_failopen_monitor_add(&m, 100, 0) == -1);
    assert(lunar_failopen_monitor_poll(&m, 999, &slot) == LUNAR_FAILOPEN_WAIT);
}

static void image_id(void) {
    unsigned char data[1000];
    unsigned i;
    for (i = 0; i < sizeof(data); ++i)
        data[i] = (unsigned char)(i * 7 + 3);
    assert(lunar_failopen_image_id(data, 0) == 2166136261u);
    printf("image_id=%08x empty=%08x\n", (unsigned)lunar_failopen_image_id(data, sizeof(data)),
           (unsigned)lunar_failopen_image_id(data, 0));
    data[500] ^= 1;
    printf("flipped=%08x\n", (unsigned)lunar_failopen_image_id(data, sizeof(data)));
}

int main(void) {
    records();
    escalation();
    old_record();
    monitor();
    registration();
    image_id();
    return 0;
}
"""

# Several threads register slots, beat, poll and rewrite the record at once,
# with a pthread mutex as the platform lock. ThreadSanitizer fails the run on
# any data race; built with -DNO_LOCK it must fail (the race is real).
RACE = r"""
#include "failopen_core.h"
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>

#ifndef NO_LOCK
static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
#endif
void lunar_failopen_lock(void) {
#ifndef NO_LOCK
    pthread_mutex_lock(&mutex);
#endif
}
void lunar_failopen_unlock(void) {
#ifndef NO_LOCK
    pthread_mutex_unlock(&mutex);
#endif
}

#define THREADS 6
#define ROUNDS 20000
static struct lunar_failopen_monitor m;
static struct lunar_failopen_record r;
static int slots[THREADS];

static void *worker(void *arg) {
    int id = (int)(long)arg, i;
    int slot = lunar_failopen_monitor_add(&m, LUNAR_FAILOPEN_MIN_TIMEOUT_MS, 0);
    slots[id] = slot;
    for (i = 0; i < ROUNDS; ++i) {
        lunar_failopen_monitor_beat(&m, slot, (uint32_t)i);
        if (id & 1)
            lunar_failopen_note_fault(&r, 0xc0u + (uint32_t)id);
        else
            lunar_failopen_note_key(&r);
    }
    return NULL;
}

static void *supervisor(void *arg) {
    int i, slot;
    (void)arg;
    for (i = 0; i < ROUNDS; ++i) {
        if (lunar_failopen_monitor_poll(&m, 1, &slot) == LUNAR_FAILOPEN_HEALTHY)
            lunar_failopen_mark_healthy(&r);
        if (!(i % 100))
            lunar_failopen_mark_stable(&r);
    }
    return NULL;
}

int main(void) {
    pthread_t t[THREADS + 1];
    int i, seen = 0, refused = 0;
    memset(&r, 0, sizeof(r));
    lunar_failopen_boot(&r, 1, 0x10, 3, NULL);
    lunar_failopen_monitor_init(&m, 0, 0, 0, LUNAR_FAILOPEN_SLOTS);
    for (i = 0; i < THREADS; ++i)
        pthread_create(&t[i], NULL, worker, (void *)(long)i);
    pthread_create(&t[THREADS], NULL, supervisor, NULL);
    for (i = 0; i <= THREADS; ++i)
        pthread_join(t[i], NULL);
    for (i = 0; i < THREADS; ++i) {
        if (slots[i] < 0)
            ++refused;
        else
            seen |= 1 << slots[i];
    }
    printf("slots=%x refused=%d valid=%d monitor_refused=%u\n", seen, refused,
           lunar_failopen_valid(&r), (unsigned)m.refused);
    assert(seen == (1 << LUNAR_FAILOPEN_SLOTS) - 1);
    assert(refused == THREADS - (int)LUNAR_FAILOPEN_SLOTS && m.refused == (uint32_t)refused);
    assert(m.slots == LUNAR_FAILOPEN_SLOTS);
    assert(lunar_failopen_valid(&r));
    return 0;
}
"""

# Bounds behind LUNAR_FAILOPEN_MIN_TIMEOUT_MS (notes/2026-11-08-failopen-hardening.md):
KIT_BLOCK_ERASE_MAX_MS = 2000      # ZB25VQ64C tBE2 (64 KB) max [reported: Zbit datasheet V0.0]
# Every FM-1 flash part's erase bound (tools/fm1_flash_parts.py): Puya P25Q80H
# 20 ms [reported: datasheet V1.7], UCUN UC25HQ80 10 ms [reported: datasheet V1.2].
SUPERVISOR_PERIOD_MS = 100         # failopen_sdk.c SUPERVISOR_PERIOD_TICKS at 10 ms


def compile_run(tmp_path, name, source, flags, check=True):
    harness = tmp_path/(name + '.c')
    harness.write_text(source)
    binary = tmp_path/name
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', *flags,
                    '-I'+str(ROOT/'firmware/failopen'), str(harness),
                    str(ROOT/'firmware/failopen/failopen_core.c'), '-o', str(binary)], check=True)
    return subprocess.run([str(binary)], check=check, capture_output=True, text=True)


def load_tool(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_core(tmp_path):
    result = compile_run(tmp_path, 'core', HARNESS, ['-fsanitize=address,undefined'])
    # The C image id matches the host tool used on app.bin (review finding 1).
    tool = load_tool('failopen_image_id', 'tools/jieli/failopen_image_id.py')
    data = bytearray((i * 7 + 3) & 0xff for i in range(1000))
    lines = result.stdout.split()
    assert 'image_id={:08x}'.format(tool.image_id(bytes(data))) in lines
    data[500] ^= 1
    assert 'flipped={:08x}'.format(tool.image_id(bytes(data))) in lines
    assert tool.image_id(b'') == 2166136261


TSAN_NO_START = 'unexpected memory mapping'


def run_tsan(tmp_path, name, flags):
    """Build and run under ThreadSanitizer. Older TSan runtimes (GCC 12) cannot
    start on kernels with high mmap randomisation; retry with ASLR off, and
    skip only if TSan still cannot start (or ASLR cannot be turned off, as
    under Docker's default seccomp profile), so a real race is never skipped."""
    result = compile_run(tmp_path, name, RACE, ['-pthread', '-fsanitize=thread', '-g', *flags],
                         check=False)
    if TSAN_NO_START in result.stderr and shutil.which('setarch'):
        result = subprocess.run(['setarch', platform.machine(), '-R', str(tmp_path/name)],
                                capture_output=True, text=True)
    if TSAN_NO_START in result.stderr or 'failed to set personality' in result.stderr:
        pytest.skip('ThreadSanitizer cannot start on this kernel: ' + result.stderr.strip()[:120])
    return result


def test_lock_under_thread_sanitizer(tmp_path):
    result = run_tsan(tmp_path, 'race', [])
    assert result.returncode == 0, result.stderr
    assert 'refused=2 valid=1' in result.stdout
    unlocked = run_tsan(tmp_path, 'race_nolock', ['-DNO_LOCK'])
    assert unlocked.returncode != 0
    assert 'data race' in unlocked.stderr


def test_min_timeout_covers_flash_erase():
    header = (ROOT/'firmware/failopen/failopen_core.h').read_text()
    minimum = int(re.search(r'#define LUNAR_FAILOPEN_MIN_TIMEOUT_MS (\d+)u', header).group(1))
    assert minimum >= KIT_BLOCK_ERASE_MAX_MS + SUPERVISOR_PERIOD_MS
    parts = load_tool('fm1_flash_parts', 'tools/fm1_flash_parts.py')
    assert parts.FM1_FLASH_ERASE_MAX_MS == max(
        p.erase_max_ms for p in parts.FM1_FLASH_PARTS.values())
    assert minimum >= parts.FM1_FLASH_ERASE_MAX_MS + SUPERVISOR_PERIOD_MS
    for part in parts.FM1_FLASH_PARTS.values():
        assert minimum >= part.erase_max_ms + SUPERVISOR_PERIOD_MS, part.name
    glue = (ROOT/'firmware/failopen/failopen_sdk.c').read_text()
    assert '#define SUPERVISOR_PERIOD_TICKS 10 ' in glue
    worker = (ROOT/'firmware/devkit/failopen_worker.c').read_text()
    beat = int(re.search(r'#define BEAT_TIMEOUT_MS (\d+)u', worker).group(1))
    short = int(re.search(r'#define SHORT_TIMEOUT_MS (\d+)u', worker).group(1))
    assert beat >= minimum > short


def fake_sdk(tmp_path):
    sdk = tmp_path/'sdk'
    app = sdk/'apps/demo/demo_hello'
    (app/'include').mkdir(parents=True)
    (app/'board/wl82').mkdir(parents=True)
    system_ld = sdk/'include_lib/driver/cpu/wl82/system.ld'
    system_ld.parent.mkdir(parents=True)
    system_ld.write_text('    PROVIDE(syscfg_ops_begin = .);\n'
                         '       *(.syscfg.2.ops)\n       *(.syscfg.1.ops)\n       *(.syscfg.0.ops)\n'
                         '    _syscfg_ops_end = .;\n    PROVIDE(syscfg_ops_end = .);\n')
    (app/'include/app_config.h').write_text('#define __FLASH_SIZE__    (4 * 1024 * 1024)\n'
                                            '#define __SDRAM_SIZE__    (2 * 1024 * 1024)\n'
                                            '#define CONFIG_CXX_SUPPORT\n')
    (app/'app_main.c').write_text('void app_main()\n{\n    os_task_create(hello_demo_task, NULL, 10, 1000, 0, "hello_demo_task");\n}\n')
    (app/'board/wl82/Makefile').write_text('OUT_ELF := sdk.elf\nc_SRC_FILES := \\\n\toriginal.c\n'
                                           'cc_SRC_FILES :=\nall: pre_build $(OUT_ELF)\n'
                                           '\t$(QUITE) $(RUN_POST_SCRIPT) sdk\n')
    (app/'board/wl82/board.c').write_text('UART2_PLATFORM_DATA_BEGIN(uart2_data)\n'
                                          '\t.rx_pin = -1,\nUART2_PLATFORM_DATA_END();\n'
                                          '\t{"uart2", &uart_dev_ops, (void *)&uart2_data },\n')
    (sdk/'cpu/wl82').mkdir(parents=True)
    (sdk/'cpu/wl82/sdk_ld_sfc.c').write_text(
        'RAM0_SIZE = 0x1c7fe00 - 0x1c00000 - TLB_SIZE - BOOT_INFO_SIZE - 128;\n'
        'MEMORY\n{\n    boot_info(rwx) : ORIGIN = 0x1c00000 + TLB_SIZE + RAM0_SIZE, LENGTH = BOOT_INFO_SIZE\n}\n'
        '        *(.text*)\n        *(.rodata*)\n        *(.volatile_ram_code)\n'
        '    _HEAP_END = 0x1c00000 + RAM0_SIZE - 32;\n'
        '    PROVIDE(HEAP_END = 0x1c00000 + RAM0_SIZE - 32);\n'
        '    _MALLOC_SIZE = _HEAP_END - _HEAP_BEGIN;\n'
        '    . =ORIGIN(boot_info);\n')
    (sdk/'cpu/wl82/setup.c').write_text('void setup_arch()\n{\n    wdt_init(0xc);\n'
                                        '    system_reset_reason_get();\n    puts("x");\n}\n')
    return sdk


def load():
    spec = importlib.util.spec_from_file_location('prepare_failopen',
                                                  ROOT/'tools/jieli/prepare-failopen-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preparer(tmp_path):
    module = load()
    sdk = fake_sdk(tmp_path)
    for mode, slots in (('cycle', 1), ('escalate', 2), ('recover', 4)):
        out = tmp_path/mode
        receipt = module.prepare(sdk, ROOT, out, mode)
        app = out/'apps/demo/demo_hello'
        main = (app/'app_main.c').read_text()
        assert main.startswith('#include "failopen_sdk.h"\n')
        # Fail-open runs before UART control and before any worker task.
        assert main.index('lunar_failopen_app_start();') < main.index('lunar_devkit_boot_control_start')
        assert (app/'sdk_worker.c').read_bytes() == (ROOT/'firmware/devkit/failopen_worker.c').read_bytes()
        for name in ('failopen_core.c', 'failopen_core.h', 'failopen_sdk.c', 'failopen_sdk.h'):
            assert (app/name).read_bytes() == (ROOT/'firmware/failopen'/name).read_bytes()
        # The hook replaces the SDK's call and makes it itself, after the raw reads.
        setup = (out/'cpu/wl82/setup.c').read_text()
        assert '        lunar_failopen_early();\n' in setup
        assert 'system_reset_reason_get' not in setup
        assert setup.index('wdt_init(0xc)') < setup.index('lunar_failopen_early')
        linker = (out/'cpu/wl82/sdk_ld_sfc.c').read_text()
        assert '_HEAP_END = 0x1c00000 + RAM0_SIZE - 32 - 64;' in linker
        assert 'PROVIDE(HEAP_END = 0x1c00000 + RAM0_SIZE - 32 - 64);' in linker
        assert 'PROVIDE(lunar_failopen_record = 0x1c00000 + RAM0_SIZE - 32 - 64);' in linker
        assert 'RAM0_SIZE = 0x1c7fe00 - 0x1c00000 - TLB_SIZE - BOOT_INFO_SIZE - 128;' in linker
        # Link-time placement checks (review finding 4).
        for check in ('ASSERT(lunar_failopen_record == 0x1c00000 + RAM0_SIZE - 32 - 64,',
                      'ASSERT(lunar_failopen_record >= _HEAP_END,',
                      'ASSERT(lunar_failopen_record + 64 <= ORIGIN(boot_info),',
                      'ASSERT(_HEAP_BEGIN <= _HEAP_END,',
                      'ASSERT(lunar_failopen_record % 4 == 0,'):
            assert linker.count(check) == 1, check
        assert linker.index('ASSERT(') > linker.index('ORIGIN(boot_info);')
        make = (app/'board/wl82/Makefile').read_text()
        assert 'apps/demo/demo_hello/failopen_core.c' in make
        assert 'apps/demo/demo_hello/failopen_sdk.c' in make
        assert 'BUILD_ID' not in make
        assert ('-DLUNAR_FAILOPEN_EXPECTED_SLOTS={} -DLUNAR_FAILOPEN_LIMIT=3 '
                '-DLUNAR_FAILOPEN_HEALTHY_MS=10000 -DLUNAR_FAILOPEN_STABLE_MS=30000').format(slots) in make
        assert ('-DLUNAR_FAILOPEN_TEST_CYCLE=1' in make) == (mode == 'cycle')
        assert ('-DLUNAR_FAILOPEN_TEST_ESCALATE=1' in make) == (mode == 'escalate')
        assert ('-DLUNAR_FAILOPEN_TEST_RECOVER=1' in make) == (mode == 'recover')
        assert '-DLUNAR_DEVKIT_BOOT_CONTROL=1' in make
        assert 'downloader disabled' in make and '$(RUN_POST_SCRIPT)' not in make
        stored = json.loads((out/'lunar-devkit-input.json').read_text())
        assert stored == receipt
        assert receipt['failopen_mode'] == mode and receipt['failopen_expected_slots'] == slots
        assert receipt['failopen_stable_ms'] == 30000
        assert 'firmware/devkit/sdk_worker.c' not in receipt['inputs']
        worker = ROOT/'firmware/devkit/failopen_worker.c'
        assert receipt['inputs']['firmware/devkit/failopen_worker.c'] == hashlib.sha256(worker.read_bytes()).hexdigest()
        with pytest.raises(ValueError, match='Output must not exist'):
            module.prepare(sdk, ROOT, out, mode)
    with pytest.raises(ValueError, match='mode'):
        module.prepare(sdk, ROOT, tmp_path/'bad', 'healthy')
    with pytest.raises(ValueError, match='Limit'):
        module.prepare(sdk, ROOT, tmp_path/'bad', 'cycle', limit=0)
    with pytest.raises(ValueError, match='Stable'):
        module.prepare(sdk, ROOT, tmp_path/'bad', 'cycle', healthy_ms=10000, stable_ms=9000)
    with pytest.raises(ValueError, match='Escalate'):
        module.prepare(sdk, ROOT, tmp_path/'bad', 'escalate', healthy_ms=15000, stable_ms=30000)
    with pytest.raises(ValueError, match='Escalate'):
        module.prepare(sdk, ROOT, tmp_path/'bad', 'escalate', stable_ms=12000)
    # Expected slots in the preparer match what each worker mode registers.
    text = (ROOT/'firmware/devkit/failopen_worker.c').read_text()
    assert '#define RACE_TASKS 4\n' in text and module.EXPECTED_SLOTS['recover'] == 4
    assert '#define CRASH_AFTER_MS {}u'.format(module.ESCALATE_CRASH_MS) in text


def test_preparer_refuses_unknown_layout(tmp_path):
    module = load()
    sdk = fake_sdk(tmp_path)
    setup = sdk/'cpu/wl82/setup.c'
    setup.write_text(setup.read_text().replace('system_reset_reason_get();', 'reason();'))
    with pytest.raises(ValueError, match='setup_arch'):
        module.prepare(sdk, ROOT, tmp_path/'a', 'cycle')
    sdk2 = fake_sdk(tmp_path/'second')
    linker = sdk2/'cpu/wl82/sdk_ld_sfc.c'
    linker.write_text(linker.read_text().replace('RAM0_SIZE - 32);', 'RAM0_SIZE - 16);'))
    with pytest.raises(ValueError, match='heap layout'):
        module.prepare(sdk2, ROOT, tmp_path/'b', 'cycle')
    sdk3 = fake_sdk(tmp_path/'third')
    linker = sdk3/'cpu/wl82/sdk_ld_sfc.c'
    linker.write_text(linker.read_text().replace('ORIGIN(boot_info)', 'ORIGIN(other)'))
    with pytest.raises(ValueError, match='heap layout'):
        module.prepare(sdk3, ROOT, tmp_path/'c', 'cycle')


def test_sources_avoid_banned_paths():
    """The glue uses the reviewed cpu.a ROM path only: no eFuse, no loader."""
    for name in ('firmware/failopen/failopen_sdk.c', 'firmware/devkit/failopen_worker.c',
                 'firmware/failopen/failopen_core.c', 'tools/jieli/failopen_image_id.py'):
        text = (ROOT/name).read_text().lower()
        for banned in ('efuse_w', 'fc12', '0xa1', 'mkey', 'chip_key', 'norflash_', 'sfc_erase',
                       'flash_write', 'uac_audio'):
            assert banned not in text, (name, banned)
    sdk_glue = (ROOT/'firmware/failopen/failopen_sdk.c').read_text()
    assert sdk_glue.count('nvram_set_boot_state(2);') == 1
    # The SDK's reason is read exactly once, after the raw registers.
    assert sdk_glue.count('= (uint32_t)system_reset_reason_get();') == 1
    early = sdk_glue[sdk_glue.index('void lunar_failopen_early(void)'):]
    assert early.index('p33_rx_1byte(P3_RST_SRC)') < early.index('= (uint32_t)system_reset_reason_get();')
    # A supervisor that could not be created fails the boot (adversarial
    # review): fault recorded, then a reset, so the count climbs to the limit.
    start = sdk_glue[sdk_glue.index('void lunar_failopen_app_start(void)'):]
    start = start[:start.index('\n}\n')]
    failure = start[start.index('if (status) {'):]
    assert failure.index('LUNAR_FAILOPEN_FAULT_SUPERVISOR') < failure.index('cpu_reset();')
    # The expected slot count is range-checked at build time.
    assert ('#if LUNAR_FAILOPEN_EXPECTED_SLOTS < 1 || '
            'LUNAR_FAILOPEN_EXPECTED_SLOTS > LUNAR_FAILOPEN_SLOTS\n#error') in sdk_glue
    # The lock is defined here, with no weak fallback in the core.
    assert 'void lunar_failopen_lock(void)' in sdk_glue
    core = (ROOT/'firmware/failopen/failopen_core.c').read_text()
    assert 'weak' not in core and 'void lunar_failopen_lock(void)\n' not in core
