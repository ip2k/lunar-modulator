/* SPDX-License-Identifier: MPL-2.0.
 * Secondary RTI sequence adapted from felucca-bsp d6b8f771 chip/fm1_cpu1.S.
 * Contributors and grant are recorded in third_party/felucca-cpu1-candidate.
 * Separate OFFLINE stock-SPL profile. Inherited RTI status remains unqualified.
 */
#include "cpu1_candidate_selection.h"
    .section .text.candidate_crt,"ax",@progbits
    .globl _candidate_start
_candidate_start:
    goto 1f
    rts
1:
    cli
    r1 = cnum
    if (r1 != 0) goto candidate_park
    r1 = 0x01c7fe08
    if (r0 != r1) goto candidate_park
    icfg = 0
    usp = _cpu0_user_top
    sp = _cpu0_user_top
    ssp = _cpu0_super_top
    [--sp] = {r0}
    r0 = 0
    [--sp] = {r0}
    r0 = sp
    call lunar_cpu1_candidate_target_early_hold
    if (r0 == 0) goto candidate_park
    r1 = [sp++]
    r0 = [sp++]
    call lunar_cpu1_candidate_cstart
candidate_park:
    csync
    goto candidate_park

    .section .text.candidate_secondary,"ax",@progbits
    .globl lunar_cpu1_entry
lunar_cpu1_entry:
    cli
    icfg = 0
    usp = _cpu1_user_top
    sp = _cpu1_super_top
    ssp = _cpu1_super_top
    reti = lunar_cpu1_candidate_secondary
    csync
    rti

    .section .text.candidate_fault,"ax",@progbits
    .globl lunar_cpu1_exception
    .globl lunar_cpu1_unexpected
lunar_cpu1_exception:
    r0 = 1
    goto candidate_fault_entry
lunar_cpu1_unexpected:
    r0 = -1
candidate_fault_entry:
    r1 = reti
    r2 = rete
    r3 = sp
    r4 = usp
    r5 = ssp
    r6 = icfg
    cli
    r7 = cnum
    if (r7 > 1) goto candidate_park
    r8 = lunar_cpu1_raw_fault
    if (r7 == 0) goto 2f
    r8 += 64
2:
    r9 = [r8]
    if (r9 != 0) goto candidate_park
    r9 = 1
    [r8++] = r9
    [r8++] = r0
    [r8++] = r1
    [r8++] = r2
    [r8++] = r3
    [r8++] = r4
    [r8++] = r5
    [r8++] = r6
    csync
    if (r7 == 0) goto 3f
    sp = _cpu1_fault_top
    ssp = _cpu1_fault_top
    goto 4f
3:
    sp = _cpu0_fault_top
    ssp = _cpu0_fault_top
4:
    call lunar_cpu1_candidate_fault_c
    goto candidate_park
