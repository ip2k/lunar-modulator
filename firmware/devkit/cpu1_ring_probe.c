/* SPDX-License-Identifier: MIT. Target-specific finite FPU and paced SRAM ring.
 * No DAC, flash, IRQ installation, task cancellation or mailbox reuse.
 * csync + volatile is a reviewed pi32v2 experiment, not portable C atomics.
 */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "arithmetic_probe.h"

#define BLOCKS 413607u /* 600.001088 s at 64 frames / 44118 Hz. */
#define CAPACITY 16u
#define FRAMES 64u
#define RATE 44118u
#define PERIOD 34815u
#define REMAINDER 31830u /* 24000000 * 64 == PERIOD * RATE + REMAINDER. */
#define BUDGET_MS 625000u
struct ring_slot { unsigned sequence, crc, data[FRAMES]; };
struct ring_state {
    volatile unsigned published, consumed, abort, exited, fpu_done, go;
    volatile unsigned bad_crc, bad_data, bad_sequence, core0, core1, other;
    volatile unsigned stack_unused, started_ms;
    struct lunar_arithmetic_result fpu[2][4];
    struct ring_slot slots[CAPACITY];
} __attribute__((aligned(64)));
static struct ring_state state;
static unsigned now(void) { return JL_TIMER4->CNT; }
static unsigned millis(void) { return timer_get_ms(); }
static void fence(void) { __asm__ volatile("csync;" ::: "memory"); }
static void yield_once(void) { os_time_dly(1); }
static int expired(void) { return (unsigned)(millis() - state.started_ms) >= BUDGET_MS; }
static void parent_result(const struct lunar_arithmetic_result *r) { state.fpu[0][r->operation] = *r; }
static void worker_result(const struct lunar_arithmetic_result *r) { state.fpu[1][r->operation] = *r; }
static unsigned sample(unsigned sequence, unsigned frame) {
    return (sequence * 2654435761u + frame * 2246822519u) ^ 0x6c756e61u;
}
static unsigned crc_word(unsigned crc, unsigned word) {
    for (unsigned byte = 0; byte < 4; ++byte) {
        crc ^= word & 255u;
        word >>= 8;
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
    }
    return crc;
}
static int wait_change(volatile unsigned *word, unsigned old) {
    unsigned start = millis();
    while (*word == old) {
        if (state.abort || expired() || (unsigned)(millis() - start) >= 1000u) return 0;
    }
    fence();
    return 1;
}
static void cpu1_worker(void *unused) {
    (void)unused;
    unsigned ok = lunar_devkit_arithmetic_probe(now, yield_once, worker_result);
    fence();
    state.fpu_done = ok ? 1u : 2u;
    if (!ok || !wait_change(&state.go, 0)) { state.abort = 1; goto done; }
    for (unsigned n = 0; n < BLOCKS; ++n) {
        if (state.abort || expired()) { state.abort = 1; goto done; }
        if (!wait_change(&state.published, n)) { state.abort = 1; goto done; }
        volatile struct ring_slot *slot = &state.slots[n % CAPACITY];
        int cpu = current_cpu_id();
        if (cpu == 0) ++state.core0; else if (cpu == 1) ++state.core1; else ++state.other;
        unsigned sequence = n + 1u, crc = 0xffffffffu;
        if (slot->sequence != sequence) ++state.bad_sequence;
        for (unsigned frame = 0; frame < FRAMES; ++frame) {
            unsigned word = slot->data[frame];
            if (word != sample(sequence, frame)) ++state.bad_data;
            crc = crc_word(crc, word);
        }
        if (~crc != slot->crc) ++state.bad_crc;
        fence();
        state.consumed = sequence;
    }
done:
    state.stack_unused = (unsigned)uxTaskGetStackHighWaterMark(NULL);
    fence();
    state.exited = 1;
    for (;;) os_time_dly(100);
}
void lunar_devkit_worker(void *unused) {
    unsigned completed = 0, parent0 = 0, parent1 = 0, other = 0;
    unsigned peak = 0, late = 0, max_late = 0, next = 0, fraction = 0;
    unsigned stream_started_ms = 0, elapsed_ms = 0;
    (void)unused;
    os_time_dly(100);
    puts("LUNAR_CONTROL recovery_window_ticks=200\n");
    os_time_dly(200);
    if (JL_TIMER4->CON & 3u) { puts("LUNAR_CPU1_RING error=timer_busy\n"); goto idle; }
    JL_TIMER4->CON = 1u << 14;
    JL_TIMER4->CNT = 0;
    JL_TIMER4->PRD = 0xffffffffu;
    JL_TIMER4->CON = 9u;
    fence();
    unsigned first = now();
    os_time_dly(10);
    unsigned calibration = now() - first;
    printf("LUNAR_CPU1_RING timer_check_ticks=%u delay_os_ticks=10 blocks=%u frames=%u rate=%u capacity=%u budget_ms=%u\n",
           calibration, BLOCKS, FRAMES, RATE, CAPACITY, BUDGET_MS);
    if (calibration < 2000000u || calibration > 3000000u || current_cpu_id() != 0) {
        puts("LUNAR_CPU1_RING error=timer_or_parent\n"); goto idle;
    }
    state.started_ms = millis();
    fence();
    int status = os_task_create(cpu1_worker, NULL, 10, 1024, 0, "#C1lunar_worker");
    if (status) { printf("LUNAR_CPU1_RING error=task_create status=%d\n", status); goto idle; }
    if (!lunar_devkit_arithmetic_probe(now, yield_once, parent_result) ||
        !wait_change(&state.fpu_done, 0) || state.fpu_done != 1u) {
        state.abort = 1; goto done;
    }
    for (unsigned op = 0; op < 4; ++op) {
        const struct lunar_arithmetic_result *a = &state.fpu[0][op], *b = &state.fpu[1][op];
        printf("LUNAR_CPU1_RING fpu_op=%u parent_bits=%u worker_bits=%u parent_batches=%u worker_batches=%u iterations=%u parent_ticks=%llu worker_ticks=%llu\n",
               op, a->result_bits, b->result_bits, a->batches, b->batches, a->iterations,
               (unsigned long long)a->ticks, (unsigned long long)b->ticks);
        if (a->result_bits != b->result_bits || a->batches != 8u || b->batches != 8u ||
            a->iterations != 1024u || b->iterations != 1024u ||
            (op && (a->result_bits & 0x7f800000u) == 0x7f800000u) ||
            (op == 0 && a->result_bits != 1025u) || (op == 1 && a->result_bits != 0x40000000u)) {
            state.abort = 1; goto done;
        }
    }
    stream_started_ms = millis();
    next = now();
    fence();
    state.go = 1;
    for (unsigned n = 0; n < BLOCKS; ++n) {
        if (state.abort || expired()) { state.abort = 1; goto done; }
        while ((int)(now() - next) < 0) {
            if (state.abort || expired()) { state.abort = 1; goto done; }
        }
        unsigned start = millis();
        while ((unsigned)(n - state.consumed) >= CAPACITY) {
            if (state.abort || expired() || (unsigned)(millis() - start) >= 1000u) {
                state.abort = 1; goto done;
            }
        }
        fence();
        int cpu = current_cpu_id();
        if (cpu == 0) ++parent0; else if (cpu == 1) ++parent1; else ++other;
        volatile struct ring_slot *slot = &state.slots[n % CAPACITY];
        unsigned crc = 0xffffffffu;
        slot->sequence = n + 1u;
        for (unsigned frame = 0; frame < FRAMES; ++frame) {
            unsigned word = sample(n + 1u, frame);
            slot->data[frame] = word;
            crc = crc_word(crc, word);
        }
        slot->crc = ~crc;
        unsigned lag = now() - next;
        if (lag > max_late) max_late = lag;
        if (lag >= PERIOD) ++late;
        fence();
        state.published = n + 1u;
        completed = n + 1u;
        unsigned depth = completed - state.consumed;
        if (depth > peak) peak = depth;
        next += PERIOD;
        fraction += REMAINDER;
        if (fraction >= RATE) { fraction -= RATE; ++next; }
    }
    /* Include the final block interval: the run represents all BLOCKS * 64 frames. */
    while ((int)(now() - next) < 0) {
        if (state.abort || expired()) { state.abort = 1; goto done; }
    }
done:
    elapsed_ms = stream_started_ms ? millis() - stream_started_ms : 0;
    {
        unsigned start = millis();
        while (!state.exited && (unsigned)(millis() - start) < 1000u) {}
        fence();
        printf("LUNAR_CPU1_RING complete=%u consumed=%u bad_crc=%u bad_data=%u bad_sequence=%u abort=%u exited=%u elapsed_ms=%u parent0=%u parent1=%u parent_other=%u worker0=%u worker1=%u worker_other=%u peak_depth=%u late_blocks=%u max_late_ticks=%u worker_stack_unused_words=%u stack_unused_words=%u\n",
               completed, state.consumed, state.bad_crc, state.bad_data, state.bad_sequence,
               state.abort, state.exited, elapsed_ms, parent0, parent1, other,
               state.core0, state.core1, state.other, peak, late, max_late,
               state.stack_unused, (unsigned)uxTaskGetStackHighWaterMark(NULL));
    }
idle:
    /* Permanent mailbox and running timer remain valid for any late worker. */
    for (;;) os_time_dly(100);
}
