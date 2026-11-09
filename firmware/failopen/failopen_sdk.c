/* SPDX-License-Identifier: MIT.
 * Lunar fail-open boot: AC79 SDK V1.2.13 glue around failopen_core.c.
 *
 * - The record is 64 bytes carved from the top of the heap by the linker
 *   script (lunar_failopen_record, tools/jieli/prepare-failopen-devkit.py),
 *   which also asserts its placement at link time; neither .bss clearing nor
 *   the allocator touches it, and boot_info and the UPDATA mailbox above it
 *   are left where the SDK puts them.
 * - The image id is FNV-1a over the application exactly as the flash holds
 *   it (.text through the load image of .cache_ram_data, read through XIP),
 *   so any change to code, data or an SDK library starts a new record.
 * - ROM entry is the same cpu.a path as the dev-kit UART control
 *   (nvram_set_boot_state(2): RAM USB-download marker, then P33 reset). It
 *   needs no eFuse, key or loader command, and links no V1.2.x boot code.
 * - The SDK's own watchdog (wdt_init(0xc) in setup_arch) is cleared on every
 *   task switch (CPU_TASK_SW), so it only catches a core that stops
 *   switching. The heartbeat supervisor catches tasks that stop working
 *   while the scheduler still runs, slots that were never registered, and
 *   (through the record's cycle count) builds that crash after healthy.
 * - The lock is CPU_CRITICAL_ENTER: interrupts off on this core plus the
 *   cross-core `lockset` lock; it nests [verified: disassembly]. It is live
 *   from lunar_failopen_app_start on (see lock_live).
 */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "asm/p33.h"
#include "failopen_core.h"
#include "failopen_sdk.h"

#ifndef LUNAR_FAILOPEN_EXPECTED_SLOTS
#error "LUNAR_FAILOPEN_EXPECTED_SLOTS must name the heartbeat slots the image registers"
#endif
#ifndef LUNAR_FAILOPEN_LIMIT
#define LUNAR_FAILOPEN_LIMIT 3
#endif
#ifndef LUNAR_FAILOPEN_HEALTHY_MS
#define LUNAR_FAILOPEN_HEALTHY_MS 30000
#endif
#ifndef LUNAR_FAILOPEN_STABLE_MS
#define LUNAR_FAILOPEN_STABLE_MS 300000
#endif
#if LUNAR_FAILOPEN_STABLE_MS < LUNAR_FAILOPEN_HEALTHY_MS
#error "LUNAR_FAILOPEN_STABLE_MS must not be shorter than LUNAR_FAILOPEN_HEALTHY_MS"
#endif
#define SUPERVISOR_PRIORITY 26
#define SUPERVISOR_PERIOD_TICKS 10      /* 100 ms at the SDK's 10 ms tick */
/* asm/system_reset_reason.h numbering, repeated so the raw bits map onto it. */
#define REASON_PWR_ON (1u << 8)
#define REASON_LOW_PWR (1u << 9)

extern struct lunar_failopen_record lunar_failopen_record;   /* linker */
extern char text_begin[], cache_ram_data_lma[], cache_ram_data_size[];  /* linker */
extern void nvram_set_boot_state(u32 state);

static enum lunar_failopen_decision decision;
static enum lunar_failopen_start start;
static uint32_t image_id;
static struct lunar_failopen_monitor monitor;

static void barrier(void) { __asm__ volatile("csync;" ::: "memory"); }

/* setup_arch runs on one core with no task or interrupt that touches the
 * record, and its interrupt state is not ours to change: CPU_CRITICAL_EXIT
 * executes `sti` when its nesting count returns to 0 [verified: disassembly
 * of __local_irq_enable, notes/2026-11-08-failopen-hardening.md]. So the
 * lock is live from lunar_failopen_app_start on, before the supervisor or
 * any worker task exists. */
static volatile int lock_live;

void lunar_failopen_lock(void)
{
    if (lock_live)
        CPU_CRITICAL_ENTER();
}

void lunar_failopen_unlock(void)
{
    if (lock_live)
        CPU_CRITICAL_EXIT();
}

static void __attribute__((section(".volatile_ram_code"), noinline)) failopen_enter_rom(void)
{
    CPU_CRITICAL_ENTER();
    nvram_set_boot_state(2);
    for (;;) {}
}

static void print_record(const char *stage)
{
    const struct lunar_failopen_record *r = &lunar_failopen_record;
    printf("LUNAR_FAILOPEN stage=%s record=0x%08x image=%08x count=%u boots=%u cycles=%u "
           "last_reason=0x%x fault=0x%x flags=0x%x valid=%d\n", stage,
           (unsigned)(uintptr_t)r, (unsigned)r->image_id, (unsigned)r->count,
           (unsigned)r->boots, (unsigned)r->cycles, (unsigned)r->last_reason,
           (unsigned)r->fault, (unsigned)r->flags, lunar_failopen_valid(r));
}

/* setup_arch, in place of its system_reset_reason_get() call. */
void lunar_failopen_early(void)
{
    static const char *const starts[] = {"continued", "invalid", "cold", "build"};
    /* Raw reset registers first: system_reset_reason_get() caches its answer,
     * ranks SOFT above power-on, and sets P3_PMU_CON1 bit 6, which its source
     * comments as clearing the power-on mark. */
    unsigned rst_src = (unsigned)JL_SYSTEM->RST_SRC;
    unsigned p3_rst = p33_rx_1byte(P3_RST_SRC);
    unsigned p3_pmu = p33_rx_1byte(P3_PMU_CON1);
    unsigned r3_wkup = p33_rx_1byte(R3_WKUP_SRC);
    uint32_t sdk_reason = (uint32_t)system_reset_reason_get();
    uint32_t reason = sdk_reason;
    uint32_t span = (uint32_t)((uintptr_t)cache_ram_data_lma + (uintptr_t)cache_ram_data_size
                               - (uintptr_t)text_begin);
    if (p3_rst & 0x1u)
        reason |= REASON_PWR_ON;
    if (p3_rst & 0x2u)
        reason |= REASON_LOW_PWR;
    printf("LUNAR_FAILOPEN raw rst_src=0x%x p3_rst_src=0x%x p3_pmu_con1=0x%x r3_wkup_src=0x%x "
           "sdk_reason=0x%x reason=0x%x\n", rst_src, p3_rst, p3_pmu, r3_wkup,
           (unsigned)sdk_reason, (unsigned)reason);
    image_id = lunar_failopen_image_id(text_begin, span);
    printf("LUNAR_FAILOPEN image=%08x begin=0x%08x bytes=%u\n", (unsigned)image_id,
           (unsigned)(uintptr_t)text_begin, (unsigned)span);
    print_record("before");
    decision = lunar_failopen_boot(&lunar_failopen_record, image_id, reason,
                                   LUNAR_FAILOPEN_LIMIT, &start);
    barrier();
    printf("LUNAR_FAILOPEN reason=0x%x start=%s decision=%s count=%u cycles=%u limit=%u\n",
           (unsigned)reason, starts[start], decision ? "fallback" : "run",
           (unsigned)lunar_failopen_record.count, (unsigned)lunar_failopen_record.cycles,
           (unsigned)LUNAR_FAILOPEN_LIMIT);
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
            printf("LUNAR_FAILOPEN healthy=1 count=%u cycles=%u uptime_ms=%u\n",
                   (unsigned)lunar_failopen_record.count, (unsigned)lunar_failopen_record.cycles,
                   (unsigned)sys_timer_get_ms());
            break;
        case LUNAR_FAILOPEN_STABLE:
            lunar_failopen_mark_stable(&lunar_failopen_record);
            barrier();
            printf("LUNAR_FAILOPEN stable=1 cycles=%u uptime_ms=%u\n",
                   (unsigned)lunar_failopen_record.cycles, (unsigned)sys_timer_get_ms());
            break;
        case LUNAR_FAILOPEN_STALLED:
            lunar_failopen_note_fault(&lunar_failopen_record,
                                      LUNAR_FAILOPEN_FAULT_STALL + (uint32_t)slot);
            barrier();
            printf("LUNAR_FAILOPEN stall=1 slot=%d beats=%u action=reset\n", slot,
                   (unsigned)monitor.beats[slot]);
            cpu_reset();
            break;
        case LUNAR_FAILOPEN_UNREGISTERED:
            lunar_failopen_note_fault(&lunar_failopen_record, LUNAR_FAILOPEN_FAULT_UNREGISTERED);
            barrier();
            printf("LUNAR_FAILOPEN unregistered=1 slots=%u expected=%u refused=%u action=reset\n",
                   (unsigned)monitor.slots, (unsigned)monitor.expected, (unsigned)monitor.refused);
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
    printf("LUNAR_FAILOPEN app core=%d expected_slots=%u healthy_ms=%u stable_ms=%u "
           "min_timeout_ms=%u\n", current_cpu_id(), (unsigned)LUNAR_FAILOPEN_EXPECTED_SLOTS,
           (unsigned)LUNAR_FAILOPEN_HEALTHY_MS, (unsigned)LUNAR_FAILOPEN_STABLE_MS,
           (unsigned)LUNAR_FAILOPEN_MIN_TIMEOUT_MS);
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
    lock_live = 1;
    barrier();
    lunar_failopen_monitor_init(&monitor, sys_timer_get_ms(), LUNAR_FAILOPEN_HEALTHY_MS,
                                LUNAR_FAILOPEN_STABLE_MS, LUNAR_FAILOPEN_EXPECTED_SLOTS);
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

unsigned lunar_failopen_boots(void)
{
    return (unsigned)lunar_failopen_record.boots;
}

int lunar_failopen_record_ok(void)
{
    int ok;
    lunar_failopen_lock();
    ok = lunar_failopen_valid(&lunar_failopen_record);
    lunar_failopen_unlock();
    return ok;
}

void lunar_failopen_note(unsigned fault)
{
    lunar_failopen_note_fault(&lunar_failopen_record, fault);
    barrier();
}
