/* SPDX-License-Identifier: GPL-3.0-only
 * Derived from Dinghy d44df7d crt0.S; Leo Kuroshita, Hügelton Instruments.
 * Diagnostic only: no debug-area saves, ROM calls or CPU1 entry. */
	.section .text.crt0,"ax",@progbits
	.globl _start
_start:
	goto 1f
	rts
1:	cli
	r1 = cnum
	if (r1 != 0) goto lunar_diagnostic_rejected
	r1 = 0x01C7FE08
	if (r0 != r1) goto lunar_diagnostic_rejected
	sp = _ustack_top
	ssp = _sstack_top
	call lunar_diagnostic_cstart
lunar_diagnostic_rejected:
	goto lunar_diagnostic_rejected
