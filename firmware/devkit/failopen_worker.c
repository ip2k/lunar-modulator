/* SPDX-License-Identifier: MIT. Private AC79 dev-kit fail-open test worker.
 *
 * Replaces sdk_worker.c in images prepared by
 * tools/jieli/prepare-failopen-devkit.py. The boot count chooses the action:
 *
 *   LUNAR_FAILOPEN_TEST_CYCLE    1: CPU exception (misaligned word read)
 *                                2: interrupts off, spin (hardware watchdog)
 *                                3: heartbeat stops, scheduler keeps running
 *                                   (only the supervisor can see this)
 *                                4: never reached; the glue enters UBOOT
 *   LUNAR_FAILOPEN_TEST_RECOVER  1: interrupts off, spin (hardware watchdog)
 *                                2+: healthy; keeps beating and stays up
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

#define BEAT_TIMEOUT_MS 6000u   /* longer than the SDK's 4 s watchdog */
#define BACKSTOP_SPINS 2000000000u  /* >= 6.25 s even at one spin per 320 MHz cycle */

enum action { HEALTHY = 0, EXCEPTION = 1, IRQ_HANG = 2, STALL = 3 };

static enum action choose(unsigned count)
{
#if defined(LUNAR_FAILOPEN_TEST_CYCLE)
    return count == 1 ? EXCEPTION : count == 2 ? IRQ_HANG : count == 3 ? STALL : HEALTHY;
#elif defined(LUNAR_FAILOPEN_TEST_RECOVER)
    return count == 1 ? IRQ_HANG : HEALTHY;
#else
#error "Select LUNAR_FAILOPEN_TEST_CYCLE or LUNAR_FAILOPEN_TEST_RECOVER"
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

void lunar_devkit_worker(void *unused)
{
    static const char *const names[] = {"healthy", "exception", "irq_hang", "stall"};
    unsigned count = lunar_failopen_boot_count();
    enum action action = choose(count);
    int slot = lunar_failopen_watch(BEAT_TIMEOUT_MS);
    unsigned i;
    (void)unused;
    printf("LUNAR_FAILOPEN_TEST count=%u action=%s slot=%d core=%d\n", count,
           names[action], slot, current_cpu_id());
    /* Two healthy seconds first: logs drain and UART control is listening. */
    for (i = 0; i < 4; ++i) {
        lunar_failopen_beat(slot);
        os_time_dly(50);
    }
    if (action != HEALTHY)
        lunar_failopen_note(LUNAR_FAILOPEN_FAULT_TEST + (unsigned)action);
    printf("LUNAR_FAILOPEN_TEST fault=%s core=%d ms=%u\n", names[action],
           current_cpu_id(), (unsigned)sys_timer_get_ms());
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
        lunar_failopen_beat(slot);
        if (!(i % 20))
            printf("LUNAR_FAILOPEN_TEST alive=1 count=%u ms=%u\n",
                   lunar_failopen_boot_count(), (unsigned)sys_timer_get_ms());
        os_time_dly(50);
    }
}
