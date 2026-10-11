/* SPDX-License-Identifier: MIT. Private 16 KiB RAM-only experiment. */
ENTRY(_start)
MEMORY { ram (rwx) : ORIGIN = 0x01c02000, LENGTH = 16K }
SECTIONS {
    .probe : {
        KEEP(*(.entry)) *(.text*) *(.rodata*) *(.data*) . = ALIGN(4);
        __image_end = .;
    } > ram
    .bss (NOLOAD) : ALIGN(4) {
        __bss_begin = .; *(.bss*) *(COMMON) . = ALIGN(4); __bss_end = .;
    } > ram
    .stack (NOLOAD) : ALIGN(16) { . += 4096; __stack_top = .; } > ram
    .ssp (NOLOAD) : ALIGN(16) { . += 4096; __ssp_top = .; } > ram
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
ASSERT(_start == 0x01c02000, "ROM upload entry must match audited loader address")
ASSERT(__ssp_top <= 0x01c06000, "16 KiB RAM reservation exceeded")
ASSERT(__image_end <= __bss_begin, "initialized/BSS overlap")
ASSERT((__stack_top & 15) == 0, "stack alignment")
ASSERT((__ssp_top & 15) == 0, "SSP alignment")
