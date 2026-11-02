/* SPDX-License-Identifier: MIT */
ENTRY(_start)
MEMORY { ram (rx) : ORIGIN = 0x01c02000, LENGTH = 512 }
SECTIONS {
    .witness_return : { KEEP(*(.witness_return)) __image_end = .; } > ram
    .forbidden : { *(.text*) *(.data*) *(.bss*) *(.rodata*) } > ram
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
ASSERT(_start == 0x01c02000, "Fixed ROM entry required")
ASSERT(SIZEOF(.witness_return) == 2, "Exactly one two-byte return required")
ASSERT(SIZEOF(.forbidden) == 0, "No other code or data permitted")
