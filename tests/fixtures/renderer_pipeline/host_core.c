/* SPDX-License-Identifier: MIT. Atomic host-only port, no SDK wrapper.
 * Bounded polling deliberately exercises the same core without wake tokens.
 * Reuses pthread/time helpers from the test shim, never vendor code. */
#include "sdk_shim.h"
#include "renderer_pipeline_sdk.h"
static unsigned port_cpu(void) { return host_cpu; }
static uint32_t port_ms(void) { return timer_get_ms(); }
static unsigned port_irq_save(void) { return 0; }
static void port_irq_restore(unsigned flags) { (void)flags; }
static void port_delay(unsigned ticks) { os_time_dly(ticks); }
static int port_launch(void (*entry)(void *),void *arg) {
    return os_task_create_static(entry,arg,0,0,0,"host-only",NULL);
}
static uint32_t port_stack_unused(void) { return uxTaskGetStackHighWaterMark(NULL); }
static int port_wake_init(uint32_t (*clock)(void)) { return clock!=NULL; }
static int port_wake_drain(unsigned cpu) { (void)cpu;return 1; }
static int port_wake_wait(unsigned cpu) { (void)cpu;os_time_dly(1);return 1; }
static void port_signal(unsigned cpu,unsigned source) { (void)cpu;(void)source; }
static void port_wake_abort(void) {}
#include "renderer_pipeline_core.c"
int lunar_pipeline_sdk_start(uint32_t (*clock)(void)) { return lunar_pipeline_core_start(clock); }
void lunar_pipeline_sdk_parent_block(void) { lunar_pipeline_core_parent_block(); }
int lunar_pipeline_sdk_finish(void) {
    if(!lunar_pipeline_core_finish())return 0;
    lunar_pipeline_stats_t r;lunar_pipeline_core_stats(&r);
    return !lunar_pipeline_error() && !r.parent_wrong;
}
int lunar_pipeline_wake_drain(unsigned cpu) { return port_wake_drain(cpu); }
