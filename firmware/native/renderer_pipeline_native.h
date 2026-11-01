/* SPDX-License-Identifier: MIT. SDK-free adapter; target launch is disabled. */
#ifndef LUNAR_RENDERER_PIPELINE_NATIVE_H
#define LUNAR_RENDERER_PIPELINE_NATIVE_H
#include "../common/renderer_pipeline_core.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LUNAR_NATIVE_STARTUP_MS 1000u
/* CPU0 only, once AFTER primary shared-vector initialization. No IRQ writes.
 * Must never be called by CPU1 or used to repeat/reset that initialization. */
int lunar_pipeline_native_primary_irq_ready(void);
/* One attempt per boot, task context only. Failure permanently retains context,
 * callbacks, work arenas and any late worker; there is no reset/free/retry API.
 * Use the common bind/reserve/publish/output API only after successful start.
 * Work arenas and clock/callback code must have image lifetime. */
int lunar_pipeline_native_start(uint32_t (*clock)(void));
int lunar_pipeline_native_finish(void);
/* Always zero in this slice, including host tests. A test launch is not admission. */
int lunar_pipeline_native_hardware_admitted(void);
typedef struct {
    uint32_t attempted, primary_irq_ready, published, entered, ready, granted, refused;
} lunar_pipeline_native_status_t;
/* CPU0 diagnostic snapshot, not an atomic multiword transaction. */
void lunar_pipeline_native_status(lunar_pipeline_native_status_t *out);
#ifdef __cplusplus
}
#endif
#endif
