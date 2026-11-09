/* SPDX-License-Identifier: MIT. RAM-only M4 test image at 0x01c02000, inside
 * the window where the mask ROM accepted and ran the vendor loader
 * (0x01c02000 + 24,064 bytes [verified: notes/2026-10-22-devkit-uart-bringup.md
 * and tools/fm1_uboot_read.py]). Same layout as firmware/m5/app.ld, held to
 * 16 KiB here so the whole image, BSS and both stacks stay in that window;
 * tools/ram_runner.py refuses any upload outside it. */
ENTRY(_start)
MEMORY { ram (rwx) : ORIGIN = 0x01c02000, LENGTH = 16K }
SECTIONS {
    .image : {
        KEEP(*(.entry)) *(.text*) *(.rodata*) *(.data*) . = ALIGN(4);
        __image_end = .;
    } > ram
    .bss (NOLOAD) : ALIGN(4) {
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
ASSERT(__ssp_top <= 0x01c06000, "16 KiB RAM reservation exceeded")
ASSERT(__image_end <= __bss_begin, "initialized/BSS overlap")
ASSERT((__stack_top & 15) == 0, "stack alignment")
ASSERT((__ssp_top & 15) == 0, "SSP alignment")
