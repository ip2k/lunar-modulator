/* SPDX-License-Identifier: MIT. Compile-time port contract, no default target. */
#ifndef LUNAR_RENDERER_PIPELINE_PORT_H
#define LUNAR_RENDERER_PIPELINE_PORT_H
#ifndef LUNAR_PIPELINE_PORT_DEFINED
#error Supply an explicit pipeline port before including renderer_pipeline_core.c
#endif
#ifndef LUNAR_PIPELINE_CORE_COLD
#error Supply the pipeline port code-placement boundary
#endif
/* Adapter defines lunar_pipeline_word_t and port_fence(): host words MUST be
 * C11 atomic (ordinary operations are seq_cst); a target must separately prove
 * aligned word accesses, ordering and visibility/cache ownership. Volatile is
 * not a portable C thread primitive. No shared non-atomic 64-bit words.
 * LUNAR_PIPELINE_CORE_COLD restores the adapter's default code section before
 * lifecycle/reporting functions (empty on the host).
 * Include the core once in the adapter TU so these hot-path hooks inline. */
static unsigned port_cpu(void);
static uint32_t port_ms(void);
static unsigned port_irq_save(void);
static void port_irq_restore(unsigned flags);
static void port_delay(unsigned ticks);
static int port_launch(void (*entry)(void *),void *arg);
static uint32_t port_stack_unused(void);
static int port_wake_init(uint32_t (*clock)(void));
static int port_wake_drain(unsigned cpu);
static int port_wake_wait(unsigned cpu);
static void port_signal(unsigned cpu,unsigned source);
static void port_wake_abort(void);
/* Waits are hints: queue states remain authoritative; callbacks and stacks
 * remain alive even on timeout/poison. delay is permitted only outside ISR.
 * irq_save/restore preserve the caller's exact prior interrupt state. */
#endif
