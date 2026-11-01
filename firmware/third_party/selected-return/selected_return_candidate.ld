/* SPDX-License-Identifier: GPL-3.0-only
 * Derived from Dinghy d44df7d app.ld; Leo Kuroshita, Hügelton Instruments.
 * Stock-sized XIP ceiling. No flash writer, retained bootguard or expanded
 * layout. Selected offline return-binding candidate; no installation admission. */
ENTRY(_start)
MEMORY {
 XIP (rx) : ORIGIN = 0x02000120, LENGTH = 0x8DFBC
 RAM (rw) : ORIGIN = 0x01C08000, LENGTH = 0x6C000
 NOINIT (rw) : ORIGIN = 0x01C7C000, LENGTH = 0x3D50
 MAILBOX (rw) : ORIGIN = 0x01C7FD80, LENGTH = 16
}
PHDRS { xip PT_LOAD FLAGS(5); globals PT_LOAD FLAGS(6); retained PT_LOAD FLAGS(6); mailbox PT_LOAD FLAGS(6); }
SECTIONS {
 .text : { KEEP(*(.text.crt0)) *(.text*) *(.rodata*) . = ALIGN(4); } > XIP :xip
 .data : { . = ALIGN(16); _data_start = .; *(.data*) *(.sdata*) . = ALIGN(4); _data_end = .; } > RAM AT > XIP :globals
 _data_load = LOADADDR(.data);
 .bss (NOLOAD) : { . = ALIGN(16); _bss_start = .; *(.bss*) *(.sbss*) *(COMMON) . = ALIGN(16); _bss_end = .; } > RAM :globals
 .noinit (NOLOAD) : { *(.noinit*) _noinit_end = .; } > NOINIT :retained
 .selected_return_mailbox (NOLOAD) : { KEEP(*(.selected_return_mailbox)) } > MAILBOX :mailbox
 _guard0 = 0x01C74000; _ustack_lo = 0x01C74100; _ustack_top = 0x01C7A000;
 _guard1 = 0x01C7A000; _sstack_lo = 0x01C7A100; _sstack_top = 0x01C7C000;
 /DISCARD/ : { *(.comment) *(.note*) }
}
ASSERT(_bss_end <= _guard0, "diagnostic globals/arenas overlap stack guard")
ASSERT(_noinit_end <= 0x01C7FD50, "diagnostic retained state overlaps boot mailbox")

ASSERT(ADDR(.selected_return_mailbox) == 0x01C7FD80, "exact return mailbox address")
ASSERT(SIZEOF(.selected_return_mailbox) == 16, "exact return mailbox extent")
ASSERT(ADDR(.selected_return_mailbox) + SIZEOF(.selected_return_mailbox) == 0x01C7FD90, "mailbox end")
ASSERT(ADDR(.selected_return_mailbox) >= 0x01C7FD50 && ADDR(.selected_return_mailbox) + SIZEOF(.selected_return_mailbox) <= 0x01C7FE00, "mailbox outside retained state and vectors")
