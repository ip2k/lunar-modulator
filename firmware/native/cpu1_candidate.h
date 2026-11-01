/* SPDX-License-Identifier: MPL-2.0. Offline, unadmitted stock-SPL candidate. */
#ifndef LUNAR_CPU1_CANDIDATE_H
#define LUNAR_CPU1_CANDIDATE_H
#include <stdint.h>
#include <stddef.h>
#if defined(LUNAR_CPU1_CANDIDATE_HOST) && LUNAR_CPU1_CANDIDATE_HOST != 1
#error Select host atomics explicitly with value 1
#endif
#ifdef LUNAR_CPU1_CANDIDATE_HOST
#include <stdatomic.h>
typedef _Atomic uint32_t cpu1_word;
#else
/* Target extension awaiting SRAM/compiler qualification; NOT C11 thread proof. */
typedef volatile uint32_t cpu1_word;
#endif
#define CPU1_CANDIDATE_POLLS 1000000u
#define CPU1_CANDIDATE_BOOT_TICKS 480000u
#define CPU1_CANDIDATE_MARK 0x43314d4bu
enum {
 C1_CON=0x01eee004u, C1_DIV=0x10008u, C1_ACCESS=0x01eee240u,
 C1_DBG_MSG=0x01eee244u, C1_DBG_CLR=0x01eee248u, C1_DBG_EN=0x01eee340u,
 C1_TOP=0x01eee348u, C1_PC_H0=0x01eee380u, C1_PC_L0=0x01eee384u,
 C1_PC_H1=0x01eee388u, C1_PC_L1=0x01eee38cu,
 C1_VECTORS=0x01c7fe00u, C1_ENTRY=0x01c7fff8u,
 C1_IRQ0=0x01eef100u, C1_IRQ1=0x01eef300u,
 C1_PENDING0=0x01eef1a4u, C1_PENDING1=0x01eef3a4u,
 C1_EMU_CON=0x01eef2d0u, C1_SSP_H=0x01eef2d8u,
 C1_SSP_L=0x01eef2dcu, C1_USP_H=0x01eef2e0u, C1_USP_L=0x01eef2e4u
};
typedef struct { uint32_t sp,usp,ssp,icfg; } cpu1_registers;
typedef struct {
 void *context;
 int (*read)(void *,uint32_t,uint32_t *);
 int (*write)(void *,uint32_t,uint32_t);
 unsigned (*cpu)(void *);
 uint32_t (*ticks)(void *);
 void (*fence)(void *);
 void (*pause)(void *);
 int (*irq_get)(void *,uint32_t *);
 int (*irq_set)(void *,uint32_t);
 int (*registers)(void *,cpu1_registers *);
} cpu1_ops;
typedef struct {
 uint32_t entry,exception,unexpected,user_lo,user_hi,super_lo,super_hi;
 uint32_t executable_lo,executable_hi,nonce;
} cpu1_layout;
typedef struct {
 uint32_t cpu,vector,reti,rete,sp,usp,ssp,icfg,emu,debug;
 cpu1_word valid;
 uint32_t reserved[5];
} cpu1_fault_record __attribute__((aligned(64)));
typedef struct {
 uint32_t last,ms,remainder,reserved[13];
} cpu1_clock __attribute__((aligned(64)));
typedef struct {
 const cpu1_ops *ops;
 cpu1_layout layout;
 cpu1_word prepared,vectors,attempted,failed,setup_nonce,launch_ok,held;
 uint32_t saved[8],saved_mask,cleanup_failed,prior_debug,prior_debug_valid;
 void (*entry)(void *);
 void *argument;
 cpu1_clock clocks[2] __attribute__((aligned(64)));
 cpu1_fault_record faults[2] __attribute__((aligned(64)));
} cpu1_candidate;
/* All storage is permanent. No reset/retry/free API, including after failure. */
int cpu1_candidate_early_hold(const cpu1_ops *);
int cpu1_candidate_early_hold_record(const cpu1_ops *,uint32_t *);
int cpu1_candidate_prepare(cpu1_candidate *,const cpu1_ops *,const cpu1_layout *);
int cpu1_candidate_install_vectors(cpu1_candidate *);
int cpu1_candidate_launch(cpu1_candidate *,void (*)(void *),void *);
int cpu1_candidate_worker_setup(cpu1_candidate *);
void cpu1_candidate_secondary(cpu1_candidate *);
uint32_t cpu1_candidate_ms(cpu1_candidate *);
int cpu1_candidate_delay(cpu1_candidate *,unsigned);
int cpu1_candidate_irq_save(cpu1_candidate *,uint32_t *);
int cpu1_candidate_irq_restore(cpu1_candidate *,uint32_t);
/* Terminal CPU0-only hold, separate from normal wake/finish. No restart follows. */
int cpu1_candidate_hold(cpu1_candidate *);
void cpu1_candidate_fault(cpu1_candidate *,uint32_t,uint32_t,uint32_t,uint32_t,
                          uint32_t,uint32_t);
#endif
