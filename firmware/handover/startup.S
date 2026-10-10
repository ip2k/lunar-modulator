/* Independently authored MIT handover preparation. No board output. */
.section .entry,"ax",@progbits
.global _start
.type _start,@function
_start:
    cli
    r1 = __stack_top;
    sp = r1;
    r1 = __ssp_top;
    ssp = r1;
    call lunar_handover_start;
1:
    goto 1b;
.size _start, .-_start
