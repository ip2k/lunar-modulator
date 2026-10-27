/* SPDX-License-Identifier: MIT. Finite CPU1 experiment; no DAC/device calls. */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "renderer_queue_sdk.h"
#include "renderer_queue_bridge.h"

#ifdef LUNAR_DEVKIT_FM6_SDK
#error Whole-engine queue must not nest the FM6 worker
#endif
#define WORKER_PRIORITY 16
#define STACK_WORDS 2048u
#define LIFETIME_MS 120000u
/* Protocol refusal bound permits measuring an already-late audio block.
 * Audio acceptance remains 34829 ticks in renderer_timing.c. */
#define PROTOCOL_BUDGET_TICKS (24000000u / 10u)
static unsigned char worker_memory[sizeof(StaticTask_t) + STACK_WORDS * 4u]
    __attribute__((aligned(4)));
static struct {
    volatile unsigned ready, stop, exited, error, jobs, wrong_core, stack_unused;
    unsigned started_ms, parent_blocks, parent_wrong_core, invoked;
} state;
static void fence(void) { __asm__ volatile("csync;" ::: "memory"); }
static void worker(void *unused) {
    (void)unused;
    if (current_cpu_id() != 1) { state.error = 1; goto done; }
    fence();
    state.ready = 1;
    for (;;) {
        if (state.stop) break;
        if ((unsigned)(timer_get_ms() - state.started_ms) >= LIFETIME_MS) {
            state.error = 2;
            break;
        }
        int result = lunar_renderer_queue_worker_step();
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
    /* Never delete/reclaim the task, queue, engine arena or output buffers. */
    for (;;) os_time_dly(100);
}
int lunar_renderer_queue_sdk_start(uint32_t (*clock)(void)) {
    if (state.invoked || current_cpu_id() != 0) return 0;
    state.invoked = 1;
    if (!lunar_renderer_queue_init(clock, PROTOCOL_BUDGET_TICKS)) return 0;
    state.started_ms = timer_get_ms();
    fence();
    int status = os_task_create_static(worker, NULL, WORKER_PRIORITY, STACK_WORDS,
        0, "#C1lunar_queue", worker_memory);
    if (status) {
        printf("LUNAR_QUEUE error=create status=%d\n", status);
        return 0;
    }
    unsigned first = timer_get_ms();
    while (!state.ready && !state.exited && (unsigned)(timer_get_ms() - first) < 1000u)
        os_time_dly(1);
    fence();
    if (!state.ready || state.exited || state.error) {
        state.stop = 1;
        fence();
        return 0;
    }
    printf("LUNAR_QUEUE ready=1 protocol_budget_ticks=%u lifetime_ms=%u stack_words=%u priority=%u\n",
        PROTOCOL_BUDGET_TICKS, LIFETIME_MS, STACK_WORDS, WORKER_PRIORITY);
    return 1;
}
void lunar_renderer_queue_sdk_parent_block(void) {
    ++state.parent_blocks;
    if (current_cpu_id() != 0) ++state.parent_wrong_core;
}
void lunar_renderer_queue_sdk_report(unsigned test_case) {
    printf("LUNAR_QUEUE case=%u completed=%u error=%u parent_blocks=%u parent_wrong=%u worker_jobs=%u worker_wrong=%u worker_error=%u exited=%u\n",
        test_case, lunar_renderer_queue_completed(), lunar_renderer_queue_error(),
        state.parent_blocks, state.parent_wrong_core, state.jobs, state.wrong_core,
        state.error, state.exited);
    for (unsigned s = 0; s < 4; ++s)
        printf("LUNAR_QUEUE_PEAK case=%u sound=%u peak=%u\n", test_case, s, lunar_renderer_queue_peak(s));
}
int lunar_renderer_queue_sdk_finish(void) {
    state.stop = 1;
    fence();
    unsigned first = timer_get_ms();
    while (!state.exited && (unsigned)(timer_get_ms() - first) < 1000u) os_time_dly(1);
    if (!state.exited) return 0;
    fence();
    lunar_renderer_queue_sdk_report(4);
    printf("LUNAR_QUEUE final=1 stack_unused_words=%u word_bytes=4\n", state.stack_unused);
    return !state.error && !state.wrong_core && !state.parent_wrong_core &&
        state.jobs && state.jobs == lunar_renderer_queue_completed() && !lunar_renderer_queue_error();
}
