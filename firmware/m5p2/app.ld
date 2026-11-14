/* SPDX-License-Identifier: MIT. RAM-only m5-plan-2 image at 0x01c02000: the
 * M5 window and budget, [0x01c02000, 0x01c06000), inside the window where the
 * mask ROM accepted and ran the vendor loader (0x01c02000 + 24,064 bytes
 * [verified: notes/2026-10-22-devkit-uart-bringup.md]). The image, BSS and
 * both stacks end below the breadcrumbs at 0x01c05fc0 (m5p2.h), which take
 * the window's last 64 bytes (48 used) and are written by address, not linked. */
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
__m5p2_crumbs = 0x01c05fc0;
ASSERT(_start == 0x01c02000, "RAM entry must be 0x01c02000")
ASSERT(__ssp_top <= 0x01c06000, "16 KiB RAM reservation exceeded")
ASSERT(__ssp_top <= __m5p2_crumbs, "stacks overlap the breadcrumbs")
ASSERT(__m5p2_crumbs + 48 <= 0x01c06000, "breadcrumbs outside the window")
ASSERT(__image_end <= __bss_begin, "initialized/BSS overlap")
ASSERT((__stack_top & 15) == 0, "stack alignment")
ASSERT((__ssp_top & 15) == 0, "SSP alignment")
