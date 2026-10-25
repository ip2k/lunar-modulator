/* SPDX-License-Identifier: MIT. pi32v2-only finite copied-kernel experiment.
 * No DAC, IRQ changes, task cancellation or storage reuse. */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "fm6_pair_sdk.h"
#include "fm6_pair_bridge.h"
#include "renderer_live.h"

#ifdef LUNAR_DEVKIT_SCHEDULING_PROBE
#define WORKER_PRIORITY 16
#else
#define WORKER_PRIORITY 10
#endif

#define LIFETIME_MS 120000u
#define PAIR_BUDGET_TICKS (24000000u * 64u / 44100u)
/* SDK static-task contract: TCB followed by 1024 four-byte stack words.
 * Permanent storage survives worker exit; queue size is zero. */
static unsigned char worker_memory[sizeof(StaticTask_t) + 1024u * 4u]
    __attribute__((aligned(4)));
static struct {
    volatile unsigned ready, stop, exited, error, jobs, wrong_core, stack_unused;
    unsigned started_ms, parent_blocks, parent_wrong_core, invoked;
} state;
static void fence(void) { __asm__ volatile("csync;" ::: "memory"); }
static int expired(void) { return (unsigned)(timer_get_ms() - state.started_ms) >= LIFETIME_MS; }
static void worker(void *unused) {
    (void)unused;
    if (current_cpu_id() != 1) { state.error = 1; goto done; }
    fence();
    state.ready = 1;
    for (;;) {
        if (state.stop) break;
        if (expired()) { state.error = 2; break; }
        int result = lunar_fm6_pair_worker_step();
        if (result < 0) { state.error = 3; break; }
        if (result) {
            if (current_cpu_id() != 1) ++state.wrong_core;
            ++state.jobs;
        }
    }
done:
    state.stack_unused = (unsigned)uxTaskGetStackHighWaterMark(NULL);
    fence();
    state.exited = 1;
    /* Permanent mailbox/stack lifetime, including after timeout. */
    for (;;) os_time_dly(100);
}
int lunar_fm6_sdk_start(uint32_t (*clock)(void)) {
    if (state.invoked || current_cpu_id() != 0) return 0;
    state.invoked = 1;
    if (!lunar_fm6_pair_init(clock, PAIR_BUDGET_TICKS)) return 0;
    state.started_ms = timer_get_ms();
    fence();
    int status = os_task_create_static(worker, NULL, WORKER_PRIORITY, 1024, 0, "#C1lunar_fm6", worker_memory);
    if (status) {
        printf("LUNAR_FM6_PAIR error=create status=%d\n", status);
        return 0;
    }
    unsigned first = timer_get_ms();
    while (!state.ready && !state.exited && (unsigned)(timer_get_ms() - first) < 1000u)
        os_time_dly(1);
    fence();
    if (!state.ready || state.exited || state.error ||
        !lunar_devkit_renderer_kernel_adapter(lunar_fm6_pair_adapter())) {
        state.stop = 1;
        fence();
        return 0;
    }
    printf("LUNAR_FM6_PAIR ready=1 budget_ticks=%u lifetime_ms=%u stack_words=1024 priority=%u\n",
           PAIR_BUDGET_TICKS, LIFETIME_MS, WORKER_PRIORITY);
    return 1;
}
void lunar_fm6_sdk_parent_block(void) {
    ++state.parent_blocks;
    if (current_cpu_id() != 0) ++state.parent_wrong_core;
}
void lunar_fm6_sdk_report(unsigned test_case) {
    struct lunar_fm6_pair_diagnostic d;
    lunar_fm6_pair_diagnostics(&d);
    printf("LUNAR_FM6_REFUSAL case=%u reason=%u elapsed_ticks=%u polls=%u first_ticks=%u request=%u done=%u\n",
           test_case, d.reason, d.elapsed_ticks, d.polls, d.first_ticks, d.request, d.done);
    /* Only jobs/errors may still change; a final fenced row follows exit. */
    printf("LUNAR_FM6_PAIR case=%u completed=%u disabled=%d parent_blocks=%u parent_wrong=%u worker_jobs=%u worker_wrong=%u error=%u exited=%u\n",
           test_case, lunar_fm6_pair_completed(), lunar_fm6_pair_disabled(),
           state.parent_blocks, state.parent_wrong_core, state.jobs,
           state.wrong_core, state.error, state.exited);
}
int lunar_fm6_sdk_finish(void) {
    state.stop = 1;
    fence();
    unsigned first = timer_get_ms();
    while (!state.exited && (unsigned)(timer_get_ms() - first) < 1000u) os_time_dly(1);
    if (!state.exited) return 0;
    fence();
    lunar_fm6_sdk_report(4);
    printf("LUNAR_FM6_PAIR final=1 stack_unused_words=%u word_bytes=4\n", state.stack_unused);
    return !state.error && !state.wrong_core && !state.parent_wrong_core &&
           state.jobs && state.jobs == lunar_fm6_pair_completed() && !lunar_fm6_pair_disabled();
}
