/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments */
/* Lunar adaptation of the pinned upstream memory map (see LICENSING.md).
 * Globals and engine arenas share one contiguous region so unused global
 * capacity is available to engine instances. No flash or recovery address changes.
 * Code + constants execute in place from XIP (app.bin offset 0 = 0x02000120).
 * 0x01C00000..0x01C06000 holds .ram_text (code that must run while the flash
 * is busy: the flash driver); 0x01C06000..0x01C08000 stays for RAM-run debug.
 * RAM : .data/.bss followed by big zero-initialised .pool buffers (432 KiB)
 * STACKS with 256-byte guard bands; NOINIT survives resets and UBOOT entry.
 * 0x01C7FD50.. is reserved: boot_info, boot-state mailbox, vector table. */
MEMORY
{
    XIP    (rx)  : ORIGIN = 0x02000120, LENGTH = 0x8DFBC
    RAMTEXT (rwx): ORIGIN = 0x01C00000, LENGTH = 0x6000
    RAM    (rwx) : ORIGIN = 0x01C08000, LENGTH = 0x6C000
    NOINIT (rw)  : ORIGIN = 0x01C7C000, LENGTH = 0x3D50
}
/* Do not let ld place an implicit ELF-header segment in the reserved stacks. */
PHDRS
{
    xip PT_LOAD FLAGS(5);
    ramcode PT_LOAD FLAGS(5);
    /* HOT_DSP_RAM_PHDR_BEGIN
    ramdsp PT_LOAD FLAGS(5);
    HOT_DSP_RAM_PHDR_END */
    globals PT_LOAD FLAGS(6);
    arenas PT_LOAD FLAGS(6);
    retained PT_LOAD FLAGS(6);
}
SECTIONS
{
    .text : { KEEP(*(.text.crt0)) *(.text*) *(.rodata*) . = ALIGN(4); _etext = .; } > XIP :xip
    .ram_text : { _rt_start = .; KEEP(*(.ram_text*)) . = ALIGN(4); _rt_end = .; } > RAMTEXT AT > XIP :ramcode
    _rt_load = LOADADDR(.ram_text);
    /* HOT_DSP_RAM_SECTION_BEGIN
    .ram_dsp : { _rd_start = .; KEEP(*(.ram_dsp*)) . = ALIGN(4); _rd_end = .; } > RAMTEXT AT > XIP :ramdsp
    _rd_load = LOADADDR(.ram_dsp);
    HOT_DSP_RAM_SECTION_END */
    .data : { . = ALIGN(4); _data_start = .; *(.data*) *(.sdata*) . = ALIGN(4); _data_end = .; } > RAM AT > XIP :globals
    _data_load = LOADADDR(.data);
    .bss (NOLOAD) : { _bss_start = .; *(.bss*) *(.sbss*) *(COMMON) . = ALIGN(4); _bss_end = .; } > RAM :globals
    .pool (NOLOAD) : { . = ALIGN(16); _pool_start = .; *(.pool*) . = ALIGN(4); _pool_end = .; } > RAM :arenas
    .noinit (NOLOAD) : { *(.noinit*) } > NOINIT :retained
    _guard0 = 0x01C74000; _ustack_lo = 0x01C74100; _ustack_top = 0x01C7A000;
    _guard1 = 0x01C7A000; _sstack_lo = 0x01C7A100; _sstack_top = 0x01C7C000;
    /DISCARD/ : { *(.comment) *(.note*) }
}

/* Boot/recovery and stack bounds are fixed, independent of app size. */
ASSERT(_pool_end <= _guard0, "Lunar globals and arenas overlap stack guard")
ASSERT(_bss_end <= _pool_start, "Lunar globals overlap arenas")
ASSERT(_rt_end <= 0x01C06000, "Lunar RAM code overlaps reserved debug region")
/* HOT_DSP_RAM_ASSERT_BEGIN
ASSERT(_rd_start >= _rt_end && _rd_end <= 0x01C06000,
       "Lunar hot DSP RAM overlaps flash-writer code or reserved debug region")
HOT_DSP_RAM_ASSERT_END */
ASSERT(ORIGIN(NOINIT) + LENGTH(NOINIT) == 0x01C7FD50,
       "Lunar noinit overlaps boot mailbox")
