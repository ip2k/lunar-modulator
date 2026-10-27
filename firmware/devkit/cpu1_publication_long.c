/* SPDX-License-Identifier: MIT. Bounded target-specific SRAM ordering probe.
 * No audio, flash, worker cancellation or mailbox reuse after failure.
 * The unfenced phase is a comparison, never evidence that csync is optional.
 */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"

#define ROUNDS 100000000u
#define WAIT_TICKS 24000000u
#define TOTAL_TICKS 3840000000u /* 160 s, less than the 24 MHz timer wrap. */
struct publication_box {
    volatile unsigned request, response, input, output, abort, exited;
    volatile unsigned errors[2], core0, core1, other, stack_unused, started;
} __attribute__((aligned(64)));
static struct publication_box box;
static unsigned now(void) { return JL_TIMER4->CNT; }
static void fence(void) { __asm__ volatile("csync;" ::: "memory"); }
static unsigned pattern(unsigned n) { return n * 2654435761u ^ 0x6c756e61u; }
static int expired(void) { return (unsigned)(now() - box.started) >= TOTAL_TICKS; }
static int wait_word(volatile unsigned *word, unsigned expected, unsigned fenced) {
    unsigned start = now();
    while (*word != expected) {
        if (box.abort || expired() || (unsigned)(now() - start) >= WAIT_TICKS) return 0;
    }
    if (fenced) fence();
    return 1;
}
static void cpu1_worker(void *unused) {
    (void)unused;
    for (unsigned phase = 0; phase < 2; ++phase) {
        for (unsigned n = 1; n <= ROUNDS; ++n) {
            unsigned sequence = phase * ROUNDS + n;
            if (!wait_word(&box.request, sequence, phase)) { box.abort = 1; goto done; }
            int cpu = current_cpu_id();
            if (cpu == 0) ++box.core0; else if (cpu == 1) ++box.core1; else ++box.other;
            unsigned value = box.input;
            if (value != pattern(sequence)) ++box.errors[phase];
            box.output = value ^ 0xa5a5a5a5u;
            if (phase) fence();
            box.response = sequence;
            if (!(n % 65536u)) {
                if (expired()) { box.abort = 1; goto done; }
                os_time_dly(1);
            }
        }
    }
done:
    box.stack_unused = (unsigned)uxTaskGetStackHighWaterMark(NULL);
    fence();
    box.exited = 1;
    for (;;) os_time_dly(100);
}
void lunar_devkit_worker(void *unused) {
    unsigned first, parent0 = 0, parent1 = 0, parent_other = 0;
    unsigned completed[2] = {0, 0}, errors[2] = {0, 0};
    int status;
    (void)unused;
    os_time_dly(100);
    puts("LUNAR_CONTROL recovery_window_ticks=200\n");
    os_time_dly(200);
    if (JL_TIMER4->CON & 3u) { puts("LUNAR_CPU1_LONG error=timer_busy\n"); goto idle; }
    JL_TIMER4->CON = 1u << 14;
    JL_TIMER4->CNT = 0;
    JL_TIMER4->PRD = 0xffffffffu;
    JL_TIMER4->CON = 9u;
    fence();
    first = now();
    os_time_dly(10);
    unsigned ticks = now() - first;
    printf("LUNAR_CPU1_LONG timer_check_ticks=%u delay_os_ticks=10 rounds=%u budget_ticks=%u\n",
           ticks, ROUNDS, TOTAL_TICKS);
    if (ticks < 2000000u || ticks > 3000000u) { puts("LUNAR_CPU1_LONG error=timer_rate\n"); goto idle; }
    if (current_cpu_id() != 0) { puts("LUNAR_CPU1_LONG error=parent_core\n"); goto idle; }
    box.started = now();
    fence();
    status = os_task_create(cpu1_worker, NULL, 10, 1024, 0, "#C1lunar_worker");
    if (status) { printf("LUNAR_CPU1_LONG error=task_create status=%d\n", status); goto idle; }
    for (unsigned phase = 0; phase < 2; ++phase) {
        for (unsigned n = 1; n <= ROUNDS; ++n) {
            unsigned sequence = phase * ROUNDS + n;
            int cpu = current_cpu_id();
            if (cpu == 0) ++parent0; else if (cpu == 1) ++parent1; else ++parent_other;
            box.input = pattern(sequence);
            if (phase) fence();
            box.request = sequence;
            if (!wait_word(&box.response, sequence, phase)) { box.abort = 1; goto done; }
            if (box.output != (pattern(sequence) ^ 0xa5a5a5a5u)) ++errors[phase];
            completed[phase] = n;
            if (!(n % 65536u)) {
                if (expired()) { box.abort = 1; goto done; }
                os_time_dly(1);
            }
        }
        printf("LUNAR_CPU1_LONG phase=%u complete=%u errors=%u\n", phase, completed[phase], errors[phase]);
    }
done:
    {
        unsigned elapsed = now() - box.started, start = now();
        while (!box.exited && (unsigned)(now() - start) < WAIT_TICKS) {}
        fence();
        printf("LUNAR_CPU1_LONG complete_unfenced=%u complete_fenced=%u parent_errors_unfenced=%u parent_errors_fenced=%u worker_errors_unfenced=%u worker_errors_fenced=%u abort=%u exited=%u ticks=%u parent0=%u parent1=%u parent_other=%u worker0=%u worker1=%u worker_other=%u worker_stack_unused_words=%u stack_unused_words=%u\n",
               completed[0], completed[1], errors[0], errors[1], box.errors[0], box.errors[1], box.abort, box.exited, elapsed,
               parent0, parent1, parent_other, box.core0, box.core1, box.other, box.stack_unused,
               (unsigned)uxTaskGetStackHighWaterMark(NULL));
    }
idle:
    /* Keep the timer running while a timed-out worker may still read it. */
    for (;;) os_time_dly(100);
}
