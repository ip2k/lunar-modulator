/* SPDX-License-Identifier: MIT. Explicit timing-only SDK experiment. */
#ifndef LUNAR_RENDERER_QUEUE_SDK_H
#define LUNAR_RENDERER_QUEUE_SDK_H
#include <stdint.h>
/* CPU0 only, after UART recovery/preflight and before renderer allocation.
 * Never combine with the FM6 kernel worker. Storage is never reclaimed. */
int lunar_renderer_queue_sdk_start(uint32_t (*clock)(void));
void lunar_renderer_queue_sdk_parent_block(void);
void lunar_renderer_queue_sdk_report(unsigned test_case);
int lunar_renderer_queue_sdk_finish(void);
#endif
