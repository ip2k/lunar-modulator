/* SPDX-License-Identifier: MIT. Private AC79 dev-kit fail-open test worker.
 *
 * Replaces sdk_worker.c in images prepared by
 * tools/jieli/prepare-failopen-devkit.py. The record's boot number (boots
 * since this image's record started) chooses the action:
 *
 *   LUNAR_FAILOPEN_TEST_CYCLE (1 slot)
 *     1: CPU exception attempt (misaligned read, divide by zero)
 *     2: interrupts off, spin (hardware watchdog)
 *     3: heartbeat stops, scheduler keeps running (only the supervisor sees it)
 *     4: never reached; the glue enters UBOOT at the early stage
 *   LUNAR_FAILOPEN_TEST_ESCALATE (2 slots)
 *     1: the second slot asks for a 100 ms timeout, below the minimum, and is
 *        refused; the supervisor resets at the healthy time (UNREGISTERED)
 *     2-4: both slots registered, healthy, then a deliberate reset at 12 s,
 *        before the stable time, so the record's cycle count climbs
 *     5: never reached; the glue enters UBOOT at the early stage
 *   LUNAR_FAILOPEN_TEST_RECOVER (4 slots, registered by 4 racing tasks)
 *     1: interrupts off, spin (hardware watchdog)
 *     2: two tasks also rewrite the record for 2 s and check it under the lock
 *     2+: healthy, stable, and stays up
 *
 * Every deliberate fault has a software backstop that resets through P33 and
 * prints why, so a fault that the hardware does not catch still ends in a
 * reset instead of a hung board. No flash, eFuse or USB access.
 */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "failopen_core.h"
#include "failopen_sdk.h"

#define BEAT_TIMEOUT_MS 6000u      /* longer than the SDK's 4 s watchdog */
#define SHORT_TIMEOUT_MS 100u      /* below LUNAR_FAILOPEN_MIN_TIMEOUT_MS */
#define CRASH_AFTER_MS 12000u      /* escalate: after healthy (10 s), before stable */
#define CRASH_CAP_MS 30000u
#define BACKSTOP_SPINS 2000000000u  /* >= 6.25 s even at one spin per 320 MHz cycle */
#define RACE_TASKS 4
#define HAMMER_TASKS 2
#define HAMMER_MS 2000u

enum action { HEALTHY = 0, EXCEPTION, IRQ_HANG, STALL, REFUSED, LATE_CRASH, RACE };

static enum action choose(unsigned boots)
{
#if defined(LUNAR_FAILOPEN_TEST_CYCLE)
    return boots == 1 ? EXCEPTION : boots == 2 ? IRQ_HANG : boots == 3 ? STALL : HEALTHY;
#elif defined(LUNAR_FAILOPEN_TEST_ESCALATE)
    return boots == 1 ? REFUSED : boots <= 1 + LUNAR_FAILOPEN_LIMIT ? LATE_CRASH : HEALTHY;
#elif defined(LUNAR_FAILOPEN_TEST_RECOVER)
    return boots == 1 ? IRQ_HANG : boots == 2 ? RACE : HEALTHY;
#else
#error "Select LUNAR_FAILOPEN_TEST_CYCLE, _ESCALATE or _RECOVER"
#endif
}

static void backstop(const char *what)
{
    printf("LUNAR_FAILOPEN_TEST backstop=%s action=p33_reset\n", what);
    cpu_reset();
}

static void spin_irq_off(void)
{
    volatile unsigned spins = 0;
    CPU_CRITICAL_ENTER();
    while (spins < BACKSTOP_SPINS)
        spins = spins + 1;
    backstop("wdt_missed");
}

#if defined(LUNAR_FAILOPEN_TEST_RECOVER)
#define PENDING (-2)   /* each task writes only its own entries */
static volatile int race_slot[RACE_TASKS] = {PENDING, PENDING, PENDING, PENDING};
static volatile int race_core[RACE_TASKS];
static volatile unsigned hammer_rounds[HAMMER_TASKS], hammer_bad[HAMMER_TASKS];
static volatile int hammer_finished[HAMMER_TASKS];

static int finished(const volatile int *flags, int n, int pending)
{
    int i, done = 0;
    for (i = 0; i < n; ++i)
        done += flags[i] != pending;
    return done;
}

static void registrar(void *arg)
{
    int id = (int)(uintptr_t)arg;
    int slot = lunar_failopen_watch(BEAT_TIMEOUT_MS);
    race_core[id] = current_cpu_id();
    __asm__ volatile("csync;" ::: "memory");
    race_slot[id] = slot;
    for (;;) {
        lunar_failopen_beat(slot);
        os_time_dly(50);
    }
}

static void hammer(void *arg)
{
    int id = (int)(uintptr_t)arg;
    unsigned start = (unsigned)sys_timer_get_ms(), rounds = 0, bad = 0;
    while ((unsigned)sys_timer_get_ms() - start < HAMMER_MS) {
        lunar_failopen_note(0xc0u | (unsigned)id);
        bad += !lunar_failopen_record_ok();
        ++rounds;
        if (!(rounds & 0xff))
            os_time_dly(1);
    }
    hammer_rounds[id] = rounds;
    hammer_bad[id] = bad;
    printf("LUNAR_FAILOPEN_TEST hammer=%d rounds=%u bad=%u core=%d\n", id, rounds, bad,
           current_cpu_id());
    __asm__ volatile("csync;" ::: "memory");
    hammer_finished[id] = 1;
    for (;;)
        os_time_dly(100);
}

static void race(enum action action)
{
    char name[16];
    unsigned seen = 0, cores = 0, waited, i;
    for (i = 0; i < RACE_TASKS; ++i) {
        sprintf(name, "lfo_reg%u", i);
        os_task_create(registrar, (void *)(uintptr_t)i, 12, 512, 0, name);
    }
    if (action == RACE)
        for (i = 0; i < HAMMER_TASKS; ++i) {
            sprintf(name, "lfo_ham%u", i);
            os_task_create(hammer, (void *)(uintptr_t)i, 11, 512, 0, name);
        }
    for (waited = 0; finished(race_slot, RACE_TASKS, PENDING) < RACE_TASKS && waited < 200; ++waited)
        os_time_dly(1);
    for (i = 0; i < RACE_TASKS; ++i) {
        if (race_slot[i] >= 0 && race_slot[i] < RACE_TASKS)
            seen |= 1u << race_slot[i];
        cores |= 1u << (race_core[i] & 1);
    }
    printf("LUNAR_FAILOPEN_TEST race registered=%d slots=%d,%d,%d,%d unique=%d cores=0x%x\n",
           finished(race_slot, RACE_TASKS, PENDING), race_slot[0], race_slot[1], race_slot[2], race_slot[3],
           seen == (1u << RACE_TASKS) - 1, cores);
    if (action != RACE)
        return;
    for (waited = 0; finished(hammer_finished, HAMMER_TASKS, 0) < HAMMER_TASKS && waited < 600; ++waited)
        os_time_dly(1);
    printf("LUNAR_FAILOPEN_TEST lock rounds=%u bad=%u valid=%d\n",
           hammer_rounds[0] + hammer_rounds[1], hammer_bad[0] + hammer_bad[1],
           lunar_failopen_record_ok());
}
#endif

void lunar_devkit_worker(void *unused)
{
    static const char *const names[] = {"healthy", "exception", "irq_hang", "stall",
                                        "refused", "late_crash", "race"};
    unsigned boots = lunar_failopen_boots();
    enum action action = choose(boots);
    unsigned start = (unsigned)sys_timer_get_ms();
    int slot = -1, second = -1;
    unsigned i;
    (void)unused;
#if defined(LUNAR_FAILOPEN_TEST_RECOVER)
    printf("LUNAR_FAILOPEN_TEST boots=%u count=%u action=%s core=%d\n", boots,
           lunar_failopen_boot_count(), names[action], current_cpu_id());
    race(action);
#else
    slot = lunar_failopen_watch(BEAT_TIMEOUT_MS);
#if defined(LUNAR_FAILOPEN_TEST_ESCALATE)
    second = lunar_failopen_watch(action == REFUSED ? SHORT_TIMEOUT_MS : BEAT_TIMEOUT_MS);
#endif
    printf("LUNAR_FAILOPEN_TEST boots=%u count=%u action=%s slot=%d second=%d core=%d\n",
           boots, lunar_failopen_boot_count(), names[action], slot, second, current_cpu_id());
#endif
    /* Two healthy seconds first: logs drain and UART control is listening. */
    for (i = 0; i < 4; ++i) {
        lunar_failopen_beat(slot);
        lunar_failopen_beat(second);
        os_time_dly(50);
    }
    if (action == EXCEPTION || action == IRQ_HANG || action == STALL) {
        lunar_failopen_note(LUNAR_FAILOPEN_FAULT_TEST + (unsigned)action);
        printf("LUNAR_FAILOPEN_TEST fault=%s core=%d ms=%u\n", names[action],
               current_cpu_id(), (unsigned)sys_timer_get_ms());
    }
    if (action == EXCEPTION) {
        volatile unsigned divisor = 0;
        volatile unsigned *odd = (volatile unsigned *)(uintptr_t)0x01c00002u;
        unsigned value = *odd;                   /* misalign_err expected */
        printf("LUNAR_FAILOPEN_TEST misaligned_read=0x%08x raised=0\n", value);
        value = 1u / divisor;                    /* div0_err as a second try */
        printf("LUNAR_FAILOPEN_TEST div0=0x%08x raised=0\n", value);
        backstop("exception_missed");
    }
    if (action == IRQ_HANG)
        spin_irq_off();
    if (action == STALL)
        for (;;) os_time_dly(10);               /* yields, never beats */
    for (i = 0;; ++i) {
        unsigned ms = (unsigned)sys_timer_get_ms();
        lunar_failopen_beat(slot);
        lunar_failopen_beat(second);
        if (action == LATE_CRASH && ms - start >= CRASH_AFTER_MS &&
                (lunar_failopen_boot_count() == 0 || ms - start >= CRASH_CAP_MS)) {
            lunar_failopen_note(LUNAR_FAILOPEN_FAULT_TEST + (unsigned)action);
            printf("LUNAR_FAILOPEN_TEST fault=late_crash count=%u ms=%u\n",
                   lunar_failopen_boot_count(), ms);
            backstop("late_crash");
        }
        if (!(i % 20))
            printf("LUNAR_FAILOPEN_TEST alive=1 boots=%u count=%u ms=%u\n",
                   lunar_failopen_boots(), lunar_failopen_boot_count(), ms);
        os_time_dly(50);
    }
}
