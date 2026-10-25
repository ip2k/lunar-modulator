/* SPDX-License-Identifier: MIT. Offline bridge; no SDK task/device operations. */
#ifndef LUNAR_FM6_PAIR_BRIDGE_H
#define LUNAR_FM6_PAIR_BRIDGE_H
#include "fm1_dx7_kernel.h"
#ifdef __cplusplus
extern "C" {
#endif
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
