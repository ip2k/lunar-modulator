/* SPDX-License-Identifier: MIT. 16 KiB RAM-only M5 image at 0x01c02000, the
 * entry Codex's MIT firmware/ram-recovery/probe.ld (installable-firmware
 * branch) asserts for a ROM RAM upload [reported, not re-checked here]; this
 * script is adapted from it. It is also the window firmware/diagnostic and
 * firmware/handover reserve, and it overlaps the stock SPL body's load range
 * 0x01c02000..0x01c05820 (firmware/diagnostic/README.md). A link budget, not
 * a verified ROM/SPL RAM-ownership contract
 * (notes/2026-11-08-fm1-board-layer.md). */
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
