/* SPDX-License-Identifier: MIT. Optional FM6 operator-kernel adapter. */
#ifndef FM1_DX7_KERNEL_H_
#define FM1_DX7_KERNEL_H_
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef struct fm1_dx7_kernel_operator {
  int32_t gain[2], freq, phase;
} fm1_dx7_kernel_operator_t;

typedef struct fm1_dx7_kernel_job {
  fm1_dx7_kernel_operator_t op[6];
  int32_t feedback[2];
  int32_t algorithm, feedback_shift;
  int32_t output[64];
} fm1_dx7_kernel_job_t;

/* Compute a copied job, without an engine instance, allocation or rate state.
 * Returns 1, or 0 for an invalid algorithm/feedback shift without changing it.
 * Independent jobs may run concurrently. Sine tables must remain initialized.
 */
int fm1_dx7_compute_kernel(fm1_dx7_kernel_job_t *job);

typedef struct fm1_dx7_kernel_adapter {
  /* Called on the audio task with two prepared jobs in voice order. Return 1
   * with both results, or 0 to discard both and render them sequentially.
   * The call must be bounded. Before returning, stop accessing jobs: an async
   * backend must copy into its own storage and never retain these pointers.
   * A late job must touch only backend-owned storage, never engine state.
   * Do not call engine methods or change rate/tables from this callback.
   */
  int (*render_pair)(void *ctx, fm1_dx7_kernel_job_t jobs[2]);
  void *ctx;
} fm1_dx7_kernel_adapter_t;

/* Audio-task only, with rendering stopped. NULL selects the default renderer.
 * The adapter must outlive its attachment; it is not copied or owned here.
 * No attachment is made by default. Does not change the engine/host ABI.
 */
void fm1_dx7_set_kernel_adapter(void *instance, const fm1_dx7_kernel_adapter_t *adapter);
#ifdef __cplusplus
}
#endif
#endif
