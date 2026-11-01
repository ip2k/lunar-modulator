/* SPDX-License-Identifier: MIT
 * Independently authored ROM execution candidate. No SDK or ROM routines.
 * PA2 physical role, ROM state and elapsed-time bounds remain unverified.
 */
.section .witness,"ax",@progbits
.global _start
.global witness_terminal
.global witness_rejected
.type _start,@function
.macro delay n
    r2 = (1048576 * \n);
.Ldelay\@:
    r2 += -1;
    if (r2 != 0) goto .Ldelay\@;
.endm
.macro pulse n
    [r0] &= -5;
    csync
    delay \n
    [r0] |= 4;
    csync
.endm
_start:
    cli
    r1 = cnum;
    if (r1 != 0) goto witness_rejected;
    r0 = 0x50000;
    [r0] |= 4; /* inactive before enabling output */
    csync
    r1 = 0x50008;
    [r1] &= -5; /* PA2 output; preserve every other direction bit */
    csync
    delay 3
    /* W01 pulse widths: 1,3,1,2,3,2. Five inactive unit gaps. */
    pulse 1
    delay 1
    pulse 3
    delay 1
    pulse 1
    delay 1
    pulse 2
    delay 1
    pulse 3
    delay 1
    pulse 2
witness_terminal:
    goto witness_terminal;
witness_rejected:
    goto witness_rejected;
.size _start, .-_start
