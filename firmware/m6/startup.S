/* SPDX-License-Identifier: MIT. Non-returning RAM entry for the M6 images,
 * as firmware/m5/startup.S (adapted from Codex's MIT
 * firmware/ram-recovery/startup.S). M6_ENTRY names the C entry:
 * lunar_m6_main (FM-1) or lunar_m6_kit_main (dev kit). Interrupts stay
 * masked throughout; the M6 core polls ALNK0. */
#ifndef M6_ENTRY
#define M6_ENTRY lunar_m6_main
#endif
.section .entry,"ax",@progbits
.global _start
.type _start,@function
_start:
    cli
    r1 = __stack_top;
    sp = r1;
    r1 = __ssp_top;
    ssp = r1;
    call M6_ENTRY;
1:
    goto 1b;
.size _start, .-_start
