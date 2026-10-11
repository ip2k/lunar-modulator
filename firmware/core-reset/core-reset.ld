ENTRY(_start)
MEMORY { ram (rwx) : ORIGIN = 0x01c02000, LENGTH = 512 }
SECTIONS {
    .probe : { KEEP(*(.entry)) __image_end = .; } > ram
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
ASSERT(_start == 0x01c02000, "Fixed ROM entry required")
ASSERT(__image_end <= 0x01c02200, "One fixed ROM block only")
