/* SPDX-License-Identifier: MIT.
 * Real common-core adapter with a permanent, one-shot launch handshake.
 * No SDK code, launch register recipe or primary/secondary IRQ initializer.
 * Production execution remains disabled. A separate offline stock-SPL candidate
 * has explicit compile access only; host tests use atomic words and mocked HW.
 */
#include "renderer_pipeline_native.h"
#if defined(LUNAR_NATIVE_PIPELINE_ENABLE) && LUNAR_NATIVE_PIPELINE_ENABLE
#error Native CPU1 reset/cache/IRQ/stack contracts have not been admitted
#endif
#if (defined(LUNAR_CPU1_CANDIDATE_STOCK_SPL) || defined(LUNAR_CPU1_CANDIDATE_PI32V2)) && !defined(LUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE)
#error Candidate route/target flags require explicit offline candidate selection
#endif
#if defined(LUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE)
#if LUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE != 1 || !defined(LUNAR_CPU1_CANDIDATE_STOCK_SPL) || LUNAR_CPU1_CANDIDATE_STOCK_SPL != 1
#error Offline CPU1 candidate requires explicit value 1 and stock SPL route value 1
#endif
#ifdef LUNAR_NATIVE_PIPELINE_TEST_PLATFORM_HEADER
#error Select either host test hooks or the offline target candidate
#endif
#endif
#ifdef LUNAR_NATIVE_PIPELINE_TEST_PLATFORM_HEADER
#if !defined(__unix__) && !defined(__APPLE__)
#error The native pipeline test backend is host-only
#endif
#include LUNAR_NATIVE_PIPELINE_TEST_PLATFORM_HEADER
#elif defined(LUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE)
#include "cpu1_candidate_platform.h"
#else
#include "renderer_pipeline_native_disabled.h"
#endif

/* CPU0 alone writes command. CPU1 alone writes entered/ready acknowledgements.
 * Both may set aborted=1; nobody ever clears it. No CAS/RMW assumption is added
 * to the common port contract. Exactly one CPU1 entry context is permitted.
 * The future backend must give words acquire/release semantics and validate
 * the actual stack, exception, visibility and core identity before returning
 * success from worker_setup. It must not run the primary IRQ initializer.
 */
enum { N_IDLE, N_PUBLISHED, N_RUN, N_REFUSED };
enum { N_START=0x4e01, N_SETUP, N_ORDER, N_RESTART, N_ENTRY };
static struct {
    lunar_pipeline_word_t command, entered, ready, aborted;
    uint32_t attempted, irq_ready, published;
    void (*entry)(void *);
    void *argument;
} launch_context __attribute__((aligned(64)));
/* This is ordinary permanent SRAM, NOT the temporary IRQ126 boot-pointer slot.
 * No target stacks are fabricated here: a future linker/entry backend owns
 * permanent user/supervisor stacks with reviewed bounds and exception setup. */

static unsigned port_cpu(void) { return native_cpu(); }
static uint32_t port_ms(void) { return native_ms(); }
static unsigned port_irq_save(void) { return native_irq_save(); }
static void port_irq_restore(unsigned flags) { native_irq_restore(flags); }
static void port_delay(unsigned ticks) { native_delay(ticks); }
static uint32_t port_stack_unused(void) { return native_stack_unused(); }
static int port_wake_init(uint32_t (*clock)(void)) { return clock != 0; }
static int port_wake_drain(unsigned cpu) {
    (void)cpu; return launch_context.aborted ? -1 : 1;
}
static int port_wake_wait(unsigned cpu) {
    (void)cpu; native_delay(1); return launch_context.aborted ? -1 : 1;
}
static void port_signal(unsigned cpu, unsigned source) { (void)cpu; (void)source; }
/* Core also calls this for normal finish. Polling needs no wake token. */
static void port_wake_abort(void) { }

static void native_refuse(uint32_t code) {
    launch_context.aborted=1; port_fence();
    lunar_pipeline_refuse(code);
}
static void native_worker_entry(void *arg) {
    uint32_t first;
    /* Never dereference an untrusted/stale entry argument. Context is static.
     * A late entry observes permanent refusal before touching worker inputs. */
    if(arg != &launch_context || native_cpu()!=1) {
        native_refuse(N_ENTRY); return;
    }
    port_fence();
    if(launch_context.command!=N_PUBLISHED || launch_context.aborted ||
       launch_context.entered) { native_refuse(N_ENTRY); return; }
    launch_context.entered=1; port_fence();
    if(!native_worker_setup()) { native_refuse(N_SETUP); return; }
    if(launch_context.aborted || launch_context.command!=N_PUBLISHED)return;
    launch_context.ready=1; port_fence();
    first=native_ms();
    while(launch_context.command==N_PUBLISHED && !launch_context.aborted &&
          (uint32_t)(native_ms()-first)<LUNAR_NATIVE_STARTUP_MS)native_delay(1);
    port_fence();
    if(launch_context.command!=N_RUN || launch_context.aborted) {
        native_refuse(N_START); return;
    }
    /* Only CPU0 can grant RUN; a timed-out launch can never grant it later.
     * Core also checks permanent poison before invoking any bound callback. */
    launch_context.entry(launch_context.argument);
    native_refuse(N_ENTRY); /* Common worker parks after exit; return is invalid. */
}
static int port_launch(void (*entry)(void *), void *arg) {
    uint32_t first;
    if(!launch_context.irq_ready || !native_launch_allowed() ||
       launch_context.entered || launch_context.ready || lunar_pipeline_error())return -1;
    launch_context.entry=entry; launch_context.argument=arg;
    launch_context.published=1; port_fence();
    launch_context.command=N_PUBLISHED; port_fence();
    first=native_ms();
    if(native_launch(native_worker_entry,&launch_context))goto refused;
    for(;;) {
        port_fence();
        /* Timeout wins even when READY arrives on the deadline. */
        if(launch_context.aborted ||
           (uint32_t)(native_ms()-first)>=LUNAR_NATIVE_STARTUP_MS)goto refused;
        if(launch_context.ready && launch_context.entered) {
            /* The clock hook above may synchronously latch abort/poison after
             * the timeout expression's first aborted read. Recheck before RUN.
             * This is not an atomic grant against arbitrary concurrent faults. */
            if(launch_context.aborted || lunar_pipeline_error())goto refused;
            launch_context.command=N_RUN; port_fence(); return 0;
        }
        native_delay(1);
    }
refused:
    launch_context.command=N_REFUSED; native_refuse(N_START); return -1;
}
#include "../common/renderer_pipeline_core.c"

int lunar_pipeline_native_primary_irq_ready(void) {
    if(native_cpu()!=0 || launch_context.attempted || launch_context.irq_ready ||
       launch_context.aborted || lunar_pipeline_error()) {
        native_refuse(N_ORDER); return 0;
    }
    launch_context.irq_ready=1; return 1;
}
int lunar_pipeline_native_start(uint32_t (*clock)(void)) {
    if(native_cpu()!=0) { native_refuse(N_ORDER); return 0; }
    if(launch_context.attempted) { native_refuse(N_RESTART); return 0; }
    launch_context.attempted=1;
    if(!clock || !launch_context.irq_ready || launch_context.aborted || lunar_pipeline_error() ||
       !native_launch_allowed() || !lunar_pipeline_core_start(clock)) {
        launch_context.command=N_REFUSED; native_refuse(N_START); return 0;
    }
    return 1;
}
int lunar_pipeline_native_finish(void) {
    if(!lunar_pipeline_core_finish())return 0;
    lunar_pipeline_stats_t stats; lunar_pipeline_core_stats(&stats);
    return !launch_context.aborted && !lunar_pipeline_error() && !stats.parent_wrong;
}
int lunar_pipeline_native_hardware_admitted(void) { return 0; }
void lunar_pipeline_native_status(lunar_pipeline_native_status_t *out) {
    if(!out || native_cpu()!=0)return;
    out->attempted=launch_context.attempted; out->primary_irq_ready=launch_context.irq_ready;
    out->published=launch_context.published; out->entered=launch_context.entered;
    out->ready=launch_context.ready; out->granted=launch_context.command==N_RUN;
    out->refused=launch_context.aborted || lunar_pipeline_error(); port_fence();
}
