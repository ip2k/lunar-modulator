/* SPDX-License-Identifier: MIT. Short CPU1 publication/pinning diagnostic.
 * Target-specific volatile SRAM + csync experiment, not portable C atomics.
 * No audio, flash, peripheral reset or worker cancellation. Mailboxes persist.
 */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"

#define ROUNDS 4096u
#define WORDS 64u
#define WAIT_TICKS 24000000u /* one second on the separately checked timer */
struct mailbox {
    volatile unsigned request, response, abort, exited;
    volatile unsigned input[WORDS], output[WORDS];
    volatile unsigned errors, core0, core1, other, stack_unused;
} __attribute__((aligned(64)));
static struct mailbox box;
static unsigned now(void) { return JL_TIMER4->CNT; }
static void barrier(void) { __asm__ volatile("csync;" ::: "memory"); }
static unsigned pattern(unsigned n, unsigned k) {
    return (n * 2654435761u) ^ (k * 2246822519u) ^ 0x6c756e61u;
}
static int wait_word(volatile unsigned *word, unsigned expected) {
    unsigned start = now();
    while (*word != expected) {
        if (box.abort || (unsigned)(now() - start) >= WAIT_TICKS) return 0;
    }
    barrier();
    return 1;
}
static void record_core(void) {
    int cpu = current_cpu_id();
    if (cpu == 0) ++box.core0;
    else if (cpu == 1) ++box.core1;
    else ++box.other;
}
static void cpu1_worker(void *unused) {
    (void)unused;
    for (unsigned n = 1; n <= ROUNDS; ++n) {
        if (!wait_word(&box.request, n)) { box.abort = 1; break; }
        record_core();
        for (unsigned k = 0; k < WORDS; ++k) {
            unsigned value = box.input[k];
            if (value != pattern(n, k)) ++box.errors;
            box.output[k] = value ^ 0xa5a5a5a5u;
        }
        barrier();
        box.response = n;
        /* Let OS/watchdog work run. Timeout includes this deliberate yield. */
        if (!(n % 256u)) os_time_dly(1);
    }
    box.stack_unused = (unsigned)uxTaskGetStackHighWaterMark(NULL);
    barrier();
    box.exited = 1;
    /* Keep task storage stable; do not delete/recreate or reuse the mailbox. */
    for (;;) os_time_dly(100);
}
void lunar_devkit_worker(void *unused) {
    unsigned first, parent0 = 0, parent1 = 0, parent_other = 0, completed = 0;
    int status;
    (void)unused;
    os_time_dly(100);
    puts("LUNAR_CONTROL recovery_window_ticks=200\n");
    os_time_dly(200); /* UART receiver was reserved first by app_main. */
    if (JL_TIMER4->CON & 3u) { puts("LUNAR_CPU1 error=timer_busy\n"); goto idle; }
    JL_TIMER4->CON = (1u << 14);
    JL_TIMER4->CNT = 0;
    JL_TIMER4->PRD = 0xffffffffu;
    JL_TIMER4->CON = 9u;
    barrier();
    first = now();
    os_time_dly(10);
    {
        unsigned ticks = now() - first;
        printf("LUNAR_CPU1 timer_check_ticks=%u delay_os_ticks=10 rounds=%u words=%u\n",
               ticks, ROUNDS, WORDS);
        if (ticks < 2000000u || ticks > 3000000u) {
            puts("LUNAR_CPU1 error=timer_rate\n"); goto idle;
        }
    }
    if (current_cpu_id() != 0) { puts("LUNAR_CPU1 error=parent_core\n"); goto idle; }
    status = os_task_create(cpu1_worker, NULL, 10, 1024, 0, "#C1lunar_worker");
    if (status) { printf("LUNAR_CPU1 error=task_create status=%d\n", status); goto idle; }
    first = now();
    for (unsigned n = 1; n <= ROUNDS; ++n) {
        int cpu = current_cpu_id();
        if (cpu == 0) ++parent0; else if (cpu == 1) ++parent1; else ++parent_other;
        for (unsigned k = 0; k < WORDS; ++k) box.input[k] = pattern(n, k);
        barrier();
        box.request = n;
        if (!wait_word(&box.response, n)) { box.abort = 1; break; }
        for (unsigned k = 0; k < WORDS; ++k)
            if (box.output[k] != (pattern(n, k) ^ 0xa5a5a5a5u)) ++box.errors;
        completed = n;
        if (!(n % 256u)) os_time_dly(1);
    }
    /* On timeout do not reuse storage or stop a timer another core may read.
     * Wait one bounded interval for exit, then report and remain recoverable. */
    box.abort = completed != ROUNDS;
    barrier();
    {
        unsigned elapsed = now() - first;
        unsigned start = now();
        while (!box.exited && (unsigned)(now() - start) < WAIT_TICKS) {}
        barrier();
        int exited = box.exited == 1;
        printf("LUNAR_CPU1 complete=%u errors=%u abort=%u exited=%d ticks=%u parent0=%u parent1=%u parent_other=%u worker0=%u worker1=%u worker_other=%u worker_stack_unused_words=%u stack_unused_words=%u\n",
               completed, box.errors, box.abort, exited, elapsed,
               parent0, parent1, parent_other, box.core0, box.core1, box.other, box.stack_unused,
               (unsigned)uxTaskGetStackHighWaterMark(NULL));
    }
idle:
    for (;;) os_time_dly(100);
}
