/* MIT. Conservative private 16 KiB window, outside the SDK's optional 8 KiB TLB.
 * This is a link-time diagnostic budget, not a verified SPL RAM contract. */
ENTRY(_start)
MEMORY {
    flash (rx) : ORIGIN = 0x02000120, LENGTH = 16K
    ram (rw) : ORIGIN = 0x01c02000, LENGTH = 16K
}
SECTIONS {
    .entry : { KEEP(*(.entry)) } > flash
    .text : { *(.text*) *(.rodata*) } > flash
    .data : ALIGN(4) {
        __data_begin = .; *(.data*) . = ALIGN(4); __data_end = .;
    } > ram AT > flash
    __data_load = LOADADDR(.data);
    __flash_end = LOADADDR(.data) + SIZEOF(.data);
    .bss (NOLOAD) : ALIGN(4) {
        __bss_begin = .; *(.bss*) *(COMMON) . = ALIGN(4); __bss_end = .;
    } > ram
    .stack (NOLOAD) : ALIGN(16) {
        __stack_guard = .; . += 16; __stack_bottom = .;
        . += 4096; __stack_top = .;
    } > ram
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
ASSERT(_start == 0x02000120, "entry must match stock application entry")
ASSERT(__flash_end <= ORIGIN(flash) + LENGTH(flash), "diagnostic flash budget")
ASSERT(__stack_top <= ORIGIN(ram) + LENGTH(ram), "diagnostic RAM budget")
ASSERT((__stack_top & 15) == 0, "stack alignment")
