/* SPDX-License-Identifier: MIT. Dev-board internal DAC only, not FM-1 I2S. */
#ifndef LUNAR_RENDERER_PIPELINE_DAC_H
#define LUNAR_RENDERER_PIPELINE_DAC_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* CPU0 task, one invocation per boot, AFTER the UART recovery interval.
 * Pinned SDK scheduler correction/IRQ path and native placement are required.
 * Starts finite CPU1 backend before renderer allocation. On success DAC stays
 * clocked in static zero-idle. Failure never authorizes reusing worker storage.
 * Build opt-in only; fixed12 default. Adaptive-three needs its explicit define.
 * Return success requires measured p/c deadlines and DAC transport checks;
 * independent PCM/analog acceptance is still required. */
int lunar_pipeline_dac_run(uint32_t (*clock)(void));
int lunar_pipeline_dac_idle(void);
#ifdef __cplusplus
}
#endif
#endif
