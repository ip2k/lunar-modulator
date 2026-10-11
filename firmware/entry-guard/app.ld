/* SPDX-License-Identifier: MIT. No RAM region or exception dispatch installed. */
ENTRY(_start)
MEMORY { flash (rx) : ORIGIN = 0x02000120, LENGTH = 64 }
PHDRS { entry PT_LOAD FLAGS(5); }
SECTIONS {
    .entry : { KEEP(*(.entry)) } > flash :entry
    __flash_end = .;
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
ASSERT(_start == 0x02000120, "ordinary stock XIP entry required")
ASSERT(SIZEOF(.entry) <= 64, "bounded instruction-only entry")
