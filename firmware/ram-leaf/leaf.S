/* MIT. Offline ROM-call candidate, not authorized for device execution.
 * The ROM's argument register and returning-call contract are unverified.
 * No stack, calls, IRQ changes, MMIO, SDK or board initialization.
 */
.section .probe,"ax",@progbits
.global ram_leaf
.type ram_leaf,@function
ram_leaf:
    r1 = 0x01c021e0;
    [r1+4] = r0;
    r2 = 0x1357;
    r2 ^= r0;
    [r1+8] = r2;
    r2 = 0x524e554c; /* little-endian bytes L U N R */
    [r1+0] = r2; /* completion tag last */
    r0 = 0;
    rts;
.size ram_leaf, .-ram_leaf

.org 0x1e0, 0
.global ram_leaf_mailbox
ram_leaf_mailbox:
.space 32, 0
