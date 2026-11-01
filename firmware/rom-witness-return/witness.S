/* SPDX-License-Identifier: MIT
 * Offline return-only candidate. Inherited RETS/ROM ABI is not qualified.
 */
.section .witness_return,"ax",@progbits
.global _start
.type _start,@function
_start:
    rts
.size _start, .-_start
