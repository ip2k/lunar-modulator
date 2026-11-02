/* SPDX-License-Identifier: MIT. No hardware operations and no runnable CPU1.
 * These single-core placeholders only allow compiling the refused adapter.
 * They are NOT a target memory model, IRQ implementation, timer or stack proof. */
#ifndef LUNAR_NATIVE_PIPELINE_DISABLED_H
#define LUNAR_NATIVE_PIPELINE_DISABLED_H
#include <stdint.h>
typedef volatile uint32_t lunar_pipeline_word_t;
#define LUNAR_PIPELINE_PORT_DEFINED 1
#define LUNAR_PIPELINE_CORE_COLD
static void port_fence(void) { }
static unsigned native_cpu(void) { return 0; }
static uint32_t native_ms(void) { return 0; }
static unsigned native_irq_save(void) { return 0; }
static void native_irq_restore(unsigned flags) { (void)flags; }
static void native_delay(unsigned ticks) { (void)ticks; }
static int native_launch_allowed(void) { return 0; }
static int native_launch(void (*entry)(void *), void *arg) {
    (void)entry; (void)arg; return -1;
}
static int native_worker_setup(void) { return 0; }
static uint32_t native_stack_unused(void) { return 0; }
#endif
