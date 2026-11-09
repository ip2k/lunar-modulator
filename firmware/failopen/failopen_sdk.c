/* SPDX-License-Identifier: MIT.
 * Lunar fail-open boot: AC79 SDK V1.2.13 glue around failopen_core.c.
 *
 * - The record is 64 bytes carved from the top of the heap by the linker
 *   script (lunar_failopen_record, tools/jieli/prepare-failopen-devkit.py);
 *   neither .bss clearing nor the allocator touches it, and boot_info and the
 *   UPDATA mailbox above it are left where the SDK puts them.
 * - ROM entry is the same cpu.a path as the dev-kit UART control
 *   (nvram_set_boot_state(2): RAM USB-download marker, then P33 reset). It
 *   needs no eFuse, key or loader command, and links no V1.2.x boot code.
 * - The SDK's own watchdog (wdt_init(0xc) in setup_arch) is cleared on every
 *   task switch (CPU_TASK_SW), so it only catches a core that stops
 *   switching. The heartbeat supervisor catches tasks that stop working
 *   while the scheduler still runs.
 */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "failopen_core.h"
#include "failopen_sdk.h"

#ifndef LUNAR_FAILOPEN_BUILD_ID
#error "LUNAR_FAILOPEN_BUILD_ID must identify the image (preparer sets it)"
#endif
#ifndef LUNAR_FAILOPEN_LIMIT
#define LUNAR_FAILOPEN_LIMIT 3
#endif
#ifndef LUNAR_FAILOPEN_HEALTHY_MS
#define LUNAR_FAILOPEN_HEALTHY_MS 30000
#endif
#define SUPERVISOR_PRIORITY 26
#define SUPERVISOR_PERIOD_TICKS 10      /* 100 ms at the SDK's 10 ms tick */

extern struct lunar_failopen_record lunar_failopen_record;   /* linker */
extern void nvram_set_boot_state(u32 state);

static enum lunar_failopen_decision decision;
static enum lunar_failopen_start start;
static int early_reason;
static struct lunar_failopen_monitor monitor;

static void barrier(void) { __asm__ volatile("csync;" ::: "memory"); }

static void __attribute__((section(".volatile_ram_code"), noinline)) failopen_enter_rom(void)
{
    CPU_CRITICAL_ENTER();
    nvram_set_boot_state(2);
    for (;;) {}
}

static void print_record(const char *stage)
{
    const struct lunar_failopen_record *r = &lunar_failopen_record;
    printf("LUNAR_FAILOPEN stage=%s record=0x%08x build=%08x count=%u boots=%u "
           "last_reason=0x%x fault=0x%x flags=0x%x valid=%d\n", stage,
           (unsigned)(uintptr_t)r, (unsigned)r->build_id, (unsigned)r->count,
           (unsigned)r->boots, (unsigned)r->last_reason, (unsigned)r->fault,
           (unsigned)r->flags, lunar_failopen_valid(r));
}

void lunar_failopen_early(int reason)
{
    static const char *const starts[] = {"continued", "invalid", "cold", "build"};
    early_reason = reason;
    print_record("before");
    decision = lunar_failopen_boot(&lunar_failopen_record, LUNAR_FAILOPEN_BUILD_ID,
                                   (uint32_t)reason, LUNAR_FAILOPEN_LIMIT, &start);
    barrier();
    printf("LUNAR_FAILOPEN reason=0x%x start=%s decision=%s count=%u limit=%u build=%08x\n",
           (unsigned)reason, starts[start], decision ? "fallback" : "run",
           (unsigned)lunar_failopen_record.count, (unsigned)LUNAR_FAILOPEN_LIMIT,
           (unsigned)LUNAR_FAILOPEN_BUILD_ID);
    if (decision == LUNAR_FAILOPEN_FALLBACK && lunar_failopen_claim_early(&lunar_failopen_record)) {
        barrier();
        puts("LUNAR_FAILOPEN entering=uboot stage=early\n");
        failopen_enter_rom();
    }
}

__attribute__((weak)) int lunar_failopen_key_requested(void)
{
    return 0;
}

static void supervisor(void *unused)
{
    (void)unused;
    for (;;) {
        int slot = -1;
        os_time_dly(SUPERVISOR_PERIOD_TICKS);
        switch (lunar_failopen_monitor_poll(&monitor, sys_timer_get_ms(), &slot)) {
        case LUNAR_FAILOPEN_HEALTHY:
            lunar_failopen_mark_healthy(&lunar_failopen_record);
            barrier();
            printf("LUNAR_FAILOPEN healthy=1 count=%u uptime_ms=%u\n",
                   (unsigned)lunar_failopen_record.count, (unsigned)sys_timer_get_ms());
            break;
        case LUNAR_FAILOPEN_STALLED:
            lunar_failopen_note_fault(&lunar_failopen_record,
                                      LUNAR_FAILOPEN_FAULT_STALL + (uint32_t)slot);
            barrier();
            printf("LUNAR_FAILOPEN stall=1 slot=%d beats=%u action=reset\n", slot,
                   (unsigned)monitor.beats[slot]);
            cpu_reset();
            break;
        default:
            break;
        }
    }
}

void lunar_failopen_app_start(void)
{
    int status;
    /* The SDK discards setup_arch's reading; record whether a second call
     * still reports the same bits (not assumed anywhere in this file). */
    printf("LUNAR_FAILOPEN app early_reason=0x%x reason_again=0x%x core=%d\n",
           (unsigned)early_reason, (unsigned)system_reset_reason_get(), current_cpu_id());
    if (lunar_failopen_key_requested()) {
        lunar_failopen_note_key(&lunar_failopen_record);
        barrier();
        puts("LUNAR_FAILOPEN entering=uboot stage=key\n");
        failopen_enter_rom();
    }
    if (decision == LUNAR_FAILOPEN_FALLBACK) {
        puts("LUNAR_FAILOPEN entering=uboot stage=app\n");
        failopen_enter_rom();
    }
    lunar_failopen_monitor_init(&monitor, sys_timer_get_ms(), LUNAR_FAILOPEN_HEALTHY_MS);
    status = os_task_create(supervisor, NULL, SUPERVISOR_PRIORITY, 512, 0, "lunar_failopen");
    if (status)
        printf("LUNAR_FAILOPEN error=supervisor_create status=%d\n", status);
}

int lunar_failopen_watch(unsigned timeout_ms)
{
    return lunar_failopen_monitor_add(&monitor, timeout_ms, sys_timer_get_ms());
}

void lunar_failopen_beat(int slot)
{
    lunar_failopen_monitor_beat(&monitor, slot, sys_timer_get_ms());
}

unsigned lunar_failopen_boot_count(void)
{
    return (unsigned)lunar_failopen_record.count;
}

void lunar_failopen_note(unsigned fault)
{
    lunar_failopen_note_fault(&lunar_failopen_record, fault);
    barrier();
}
