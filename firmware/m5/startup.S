/* SPDX-License-Identifier: MIT. Non-returning RAM entry for the M5 test
 * pattern; adapted from Codex's MIT firmware/ram-recovery/startup.S
 * (installable-firmware branch). Interrupts stay masked throughout. */
.section .entry,"ax",@progbits
.global _start
.type _start,@function
_start:
    cli
    r1 = __stack_top;
    sp = r1;
    r1 = __ssp_top;
    ssp = r1;
    call lunar_m5_main;
1:
    goto 1b;
.size _start, .-_start
