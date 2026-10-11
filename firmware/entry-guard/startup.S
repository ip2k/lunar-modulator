/* SPDX-License-Identifier: MIT
 * Independently authored, instruction-only ordinary XIP entry prerequisite.
 * r0 is preserved; no stack, RAM, MMIO, call, return or board output.
 * CLI/cnum privilege and actual dispatch remain unverified. An accepted input
 * is NOT activation: both paths stop until ownership premises are resolved.
 */
.section .entry,"ax",@progbits
.global _start
.global lunar_entry_accepted_stop
.global lunar_entry_rejected_stop
.type _start,@function
_start:
    cli
    r1 = cnum;
    if (r1 != 0) goto lunar_entry_rejected_stop;
    r2 = 0x01c7fe08;
    if (r0 != r2) goto lunar_entry_rejected_stop;
lunar_entry_accepted_stop:
    cli
    goto lunar_entry_accepted_stop;
lunar_entry_rejected_stop:
    cli
    goto lunar_entry_rejected_stop;
.size _start, .-_start
