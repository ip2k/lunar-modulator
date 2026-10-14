/* SPDX-License-Identifier: MIT. Offline copy of Dinghy crt0 with verifier before C runtime. */
.section .text.crt0,"ax",@progbits
.globl _start
_start:
 goto 1f
 rts
1: r1 = icfg
 r2 = psr
 cli
 r3 = 0x1C07F00
 [r3 + 0x20] = r1
 [r3 + 0x24] = r2
 [r3 + 0x28] = r0
 r1 = sp
 [r3 + 0x2C] = r1
 r1 = ssp
 [r3 + 0x30] = r1
 sp = _ustack_top
 ssp = _sstack_top
 call lunar_validate_mutable
 if (r0 != 0) goto 2f
 call fm1_cstart
1: goto 1b
2: cli
 goto 2b
.section .text.mutable,"ax",@progbits
.globl fm1_cstart
fm1_cstart:
 goto fm1_cstart
