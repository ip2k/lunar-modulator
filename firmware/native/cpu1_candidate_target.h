/* SPDX-License-Identifier: MPL-2.0. Compile access is not hardware authority. */
#ifndef LUNAR_CPU1_CANDIDATE_TARGET_H
#define LUNAR_CPU1_CANDIDATE_TARGET_H
#include "cpu1_candidate_selection.h"
#include "cpu1_candidate.h"
_Static_assert(sizeof(void *) == 4, "pi32v2 pointer ABI required");
extern cpu1_candidate lunar_cpu1_candidate;
unsigned lunar_cpu1_candidate_cpu(void);
uint32_t lunar_cpu1_candidate_ticks(void);
uint32_t lunar_cpu1_candidate_stack_unused(void);
int lunar_cpu1_candidate_target_prepare(void);
int lunar_cpu1_candidate_target_setup(void);
int lunar_cpu1_candidate_target_early_hold(uint32_t *);
int lunar_cpu1_candidate_faulted(void);
void lunar_cpu1_candidate_secondary(void) __attribute__((noreturn));
void lunar_cpu1_candidate_fault_c(void) __attribute__((noreturn));
#endif
