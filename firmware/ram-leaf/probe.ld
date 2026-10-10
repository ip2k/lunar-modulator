/* MIT. One exact 512-byte RAM block; no flash or loader integration. */
ENTRY(ram_leaf)
MEMORY { PROBE (rwx) : ORIGIN = 0x01c02000, LENGTH = 512 }
SECTIONS {
    .probe : { KEEP(*(.probe)) } > PROBE
    /DISCARD/ : { *(.comment) *(.note*) }
}
ASSERT(ADDR(.probe) == 0x01c02000, "unexpected probe base")
ASSERT(SIZEOF(.probe) == 512, "probe must be exactly one block")
ASSERT(ram_leaf_mailbox == 0x01c021e0, "unexpected mailbox address")
