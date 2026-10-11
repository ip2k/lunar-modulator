/* SPDX-License-Identifier: MIT. Independent fixed core-reset experiment. */
.section .entry,"ax",@progbits
.global _start
.type _start,@function
_start:
    cli
    r0 = 0x10000;
    [r0] |= 0x10;
    csync
1:
    goto 1b;
.size _start, .-_start
