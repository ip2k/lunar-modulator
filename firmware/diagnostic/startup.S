/* Independently authored MIT diagnostic entry; no SDK or board HAL. */
.section .entry,"ax",@progbits
.global _start
.type _start,@function
_start:
    cli
    r1 = __stack_top;
    sp = r1;
    call lunar_diag_start;
1:
    goto 1b;
.size _start, .-_start
