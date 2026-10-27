/* SPDX-License-Identifier: MIT. Finite native renderer pipeline. */
#ifndef LUNAR_RENDERER_PIPELINE_SDK_H
#define LUNAR_RENDERER_PIPELINE_SDK_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LUNAR_PIPELINE_WORK_SLOTS 2u
#define LUNAR_PIPELINE_OUTPUT_SLOTS 8u
#define LUNAR_PIPELINE_OUTPUT_SAMPLES 256u
#define LUNAR_PIPELINE_PROTOCOL_TICKS 2400000u
/* No shared uint64 fields. Callback results are immutable per output tag. */
typedef struct {
    uint32_t tag, case_index, case_block;
    uint32_t invalid, clipped, hash, case_total;
    uint32_t user[4];
} lunar_pipeline_result_t;
typedef struct {
    uint32_t tag, p_start, p_end, published, c_start, c_end;
    uint32_t p_ticks, c_ticks, ready_wait_ticks;
    lunar_pipeline_result_t result;
} lunar_pipeline_completion_t;
typedef int (*lunar_pipeline_consume_fn)(void *work, uint32_t tag,
                         int16_t out[LUNAR_PIPELINE_OUTPUT_SAMPLES], lunar_pipeline_result_t *result);
/* Exactly once on CPU0 after DONE acquire. Return 1; failure is permanent. */
typedef int (*lunar_pipeline_retire_fn)(void *work);
/* Opt-in lifecycle; do not link the older whole-engine worker at the same time. */
int lunar_pipeline_sdk_start(uint32_t (*clock)(void));
void lunar_pipeline_sdk_parent_block(void);
void lunar_pipeline_sdk_report(unsigned test_case);
int lunar_pipeline_sdk_finish(void);
/* Bind once on CPU0 after app initialization; arenas/callbacks live forever. */
int lunar_pipeline_bind(void *work0, void *work1, lunar_pipeline_consume_fn consume, lunar_pipeline_retire_fn retire);
/* Polling APIs: 1 success, 0 unavailable, -1 permanent refusal. CPU0 only.
 * reserve precedes ALL block controls; no controls may run on return 0. */
int lunar_pipeline_reserve_work(uint32_t tag, void **work);
int lunar_pipeline_publish(uint32_t tag, uint32_t p_start, uint32_t p_end);
int lunar_pipeline_harvest(lunar_pipeline_completion_t *completion);
/* acquire grants a lease, valid through matching retire. Reacquire is an error.
 * Result and PCM pointers refer only to this immutable output lease. */
int lunar_pipeline_output_acquire(uint32_t expected_tag, const int16_t **pcm,
                                const lunar_pipeline_result_t **result);
int lunar_pipeline_output_retire(uint32_t expected_tag);
/* Nonzero code; callable from native guard on either core. No trap/free/replay.
 * Callback must stop executing immediately after refusal and return failure. */
void lunar_pipeline_refuse(uint32_t code);
uint32_t lunar_pipeline_error(void);
/* Diagnostic guard for nested APIs that cannot propagate failure safely.
 * Permanently poisons, then parks ONLY calling task; UART/IRQs remain live. */
void lunar_pipeline_fail_park(uint32_t code) __attribute__((noreturn));
/* Native task wake protocol. CPU0 driver uses cpu=0; CPU1 worker uses cpu=1.
 * Drain tokens BEFORE checking progress predicates; wait only if no progress is
 * possible, then recheck. A token is a hint, never proof of published work.
 * These task APIs must not be called by an ISR. */
int lunar_pipeline_wake_drain(unsigned cpu);
int lunar_pipeline_wake_wait(unsigned cpu);
/* Single-writer CPU0 DAC drain notification; may post/yield. Native IRQ use
 * requires the reviewed pinned SDK ISR-post/yield path and adapter handoff.
 * This is not a generic ISR-safe API; host tests do not establish IRQ legality.
 * It never grants or retires an output lease. */
void lunar_pipeline_wake_drain_done(void);
/* Advisory count for the sole CPU0 output owner (task prefill, then native IRQ
 * after explicit handoff). Never concurrent task/IRQ readers. This is not an
 * output lease or authorization to read PCM. */
unsigned lunar_pipeline_ready_outputs(void);
/* Driver must call while retrying unavailable resources; finite clock budget.
 * ticket initialized to zero before EACH new wait episode. No sleeping here. */
int lunar_pipeline_wait_check(uint32_t *ticket);
#ifdef __cplusplus
}
#endif
#endif
