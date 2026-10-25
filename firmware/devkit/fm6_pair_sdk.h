/* SPDX-License-Identifier: MIT. Finite timing-only SDK worker ownership. */
#ifndef LUNAR_FM6_PAIR_SDK_H
#define LUNAR_FM6_PAIR_SDK_H
#include <stdint.h>
/* One invocation, CPU0, after the UART recovery window and before renderer init.
 * Reserves CPU1 stack before any renderer allocation. No cancellation/reuse. */
int lunar_fm6_sdk_start(uint32_t (*clock)(void));
void lunar_fm6_sdk_parent_block(void);
void lunar_fm6_sdk_report(unsigned test_case);
/* Detaches no live instance; caller must have stopped rendering. Returns only
 * after exit acknowledgement or a bounded failure. On failure retain timer. */
int lunar_fm6_sdk_finish(void);
#endif
