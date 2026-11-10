/* SPDX-License-Identifier: MIT. RAM-only M6 images at 0x01c02000: the M5
 * layout (firmware/m5/app.ld) over the whole 24,064-byte window
 * 0x01c02000..0x01c07e00, where the mask ROM accepted JieLi's 24,064-byte
 * loader and ran it [verified on the dev kit, M4:
 * notes/2026-11-08-ram-runner-devkit.md; tools/ram_runner.py WINDOW_SIZE].
 * M5's 16 KiB does not hold M6 (about 9.6 KB of image plus 1.5 KB of BSS and
 * two 4 KiB stacks, for the FM-1 build). Only .image is uploaded; .bss and both stacks are used at
 * run time but never written by the loader. A link budget, not a verified
 * ROM/SPL RAM-ownership contract. */
ENTRY(_start)
MEMORY { ram (rwx) : ORIGIN = 0x01c02000, LENGTH = 24064 }
SECTIONS {
    .image : {
        KEEP(*(.entry)) *(.text*) *(.rodata*) *(.data*) . = ALIGN(4);
        __image_end = .;
    } > ram
    .bss (NOLOAD) : ALIGN(32) {
        __bss_begin = .; *(.bss*) *(COMMON) . = ALIGN(4); __bss_end = .;
    } > ram
    .stack (NOLOAD) : ALIGN(16) {
        __stack_guard = .; . += 16; __stack_bottom = .;
        . += 4096; __stack_top = .;
    } > ram
    .ssp_stack (NOLOAD) : ALIGN(16) {
        __ssp_guard = .; . += 16; __ssp_bottom = .;
        . += 4096; __ssp_top = .;
    } > ram
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
ASSERT(_start == 0x01c02000, "RAM entry must be 0x01c02000")
ASSERT(__ssp_top <= 0x01c07e00, "ROM window 0x01c02000..0x01c07e00 exceeded")
ASSERT(__image_end <= __bss_begin, "initialized/BSS overlap")
ASSERT((__stack_top & 15) == 0, "stack alignment")
ASSERT((__ssp_top & 15) == 0, "SSP alignment")
