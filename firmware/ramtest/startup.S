/* SPDX-License-Identifier: MIT. Non-returning RAM entry for the M4 RAM test
 * image; the same shape as firmware/m5/startup.S, which is adapted from
 * Codex's MIT firmware/ram-recovery/startup.S (installable-firmware branch).
 * Interrupts stay masked throughout. */
.section .entry,"ax",@progbits
.global _start
.type _start,@function
_start:
    cli
    r1 = __stack_top;
    sp = r1;
    r1 = __ssp_top;
    ssp = r1;
    call lunar_ramtest_main;
1:
    goto 1b;
.size _start, .-_start
