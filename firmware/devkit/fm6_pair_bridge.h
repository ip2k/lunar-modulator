/* SPDX-License-Identifier: MIT. Offline bridge; no SDK task/device operations. */
#ifndef LUNAR_FM6_PAIR_BRIDGE_H
#define LUNAR_FM6_PAIR_BRIDGE_H
#include "fm1_dx7_kernel.h"
#ifdef __cplusplus
extern "C" {
#endif
/* CPU0-owned snapshot. first_ticks includes publication and the caller kernel;
 * elapsed also includes waiting. A visible completion can still miss deadline. */
enum lunar_fm6_pair_failure {
  LUNAR_FM6_PAIR_OK = 0, LUNAR_FM6_PAIR_CALLER = 1,
  LUNAR_FM6_PAIR_DEADLINE = 2, LUNAR_FM6_PAIR_POLLS = 3,
  LUNAR_FM6_PAIR_WORKER = 4, LUNAR_FM6_PAIR_CONFIG = 5
};
struct lunar_fm6_pair_diagnostic {
  unsigned reason, elapsed_ticks, polls, first_ticks, request, done;
};
void lunar_fm6_pair_diagnostics(struct lunar_fm6_pair_diagnostic *out);
/* Initialize once before starting the worker or attaching to a renderer.
 * Static storage survives rejection, timeout, detach and engine destruction.
 * Never reinitialize it while a late worker may still be executing. */
int lunar_fm6_pair_init(uint32_t (*clock)(void), uint32_t budget_ticks);
/* CPU1 only after init: -1 uninitialized, 0 idle, 1 completed a copied job. */
int lunar_fm6_pair_worker_step(void);
/* Audio owner only. The immutable adapter outlives every attachment. */
const fm1_dx7_kernel_adapter_t *lunar_fm6_pair_adapter(void);
unsigned lunar_fm6_pair_completed(void);
int lunar_fm6_pair_disabled(void);
#ifdef __cplusplus
}
#endif
#endif
