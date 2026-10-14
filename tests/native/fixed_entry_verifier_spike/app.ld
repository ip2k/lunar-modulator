ENTRY(_start)
MEMORY { XIP (rx) : ORIGIN = 0x02000120, LENGTH = 0x000D2EE0 }
PHDRS { app PT_LOAD FLAGS(5); }
SECTIONS {
 .immutable_entry 0x02000120 : { KEEP(*(.text.crt0)) KEEP(*(.text.immutable)) KEEP(*(.rodata.immutable)) . = ALIGN(4); __immutable_end = .; } > XIP :app
 ASSERT(_start == 0x02000120, "entry must remain stock XIP entry")
 ASSERT(__immutable_end <= 0x02001000, "immutable entry exceeds one 4-KiB sector")
 .mutable 0x02001000 : { __mutable_start = .; *(.text.mutable*) *(.rodata.mutable*) . = ALIGN(4); __mutable_manifest = .; KEEP(*(.mutable.manifest)) . = ALIGN(4); __mutable_end = .; } > XIP :app
 ASSERT(__mutable_start == 0x02001000, "mutable body must begin at raw offset 0x5000")
 ASSERT(__mutable_end <= 0x020D3000, "body exceeds candidate D7000 boundary")
 _ustack_top = 0x01C7A000; _sstack_top = 0x01C7C000;
 /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
