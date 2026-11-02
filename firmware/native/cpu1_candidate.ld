/* SPDX-License-Identifier: MIT. Separate, small, unadmitted witness only.
 * No app, DSP, HAL, installer or production diagnostic layout is included. */
ENTRY(_candidate_start)
MEMORY {
 XIP (rx) : ORIGIN = 0x02000120, LENGTH = 0x8dfbc
 RAM (rw) : ORIGIN = 0x01c08000, LENGTH = 0x6c000
}
PHDRS { xip PT_LOAD FLAGS(5); storage PT_LOAD FLAGS(6); }
SECTIONS {
 .text : {
  _candidate_text_lo = .;
  KEEP(*(.text.candidate_crt)) *(.text*) *(.rodata*)
  . = ALIGN(4); _candidate_text_hi = .;
 } > XIP :xip
 .data : {
  . = ALIGN(64); _candidate_data_lo = .; *(.data*) *(.sdata*)
  . = ALIGN(4); _candidate_data_hi = .;
 } > RAM AT > XIP :storage
 _candidate_data_load = LOADADDR(.data);
 .bss (NOLOAD) : {
  . = ALIGN(64); _candidate_bss_lo = .;
  *(.bss*) *(.sbss*) *(COMMON)
  . = ALIGN(64); KEEP(*(.candidate_state))
  . = ALIGN(64); KEEP(*(.candidate_fault))
  . = ALIGN(64); _candidate_bss_hi = .;
 } > RAM :storage
 .stacks (NOLOAD) : {
  . = ALIGN(64);
  _cpu0_guard_lo = .; . += 64;
  _cpu0_user_lo = .; . += 8192; _cpu0_user_top = .;
  _cpu0_guard_middle = .; . += 64;
  _cpu0_super_lo = .; . += 2048; _cpu0_super_top = .;
  _cpu0_guard_hi = .; . += 64;
  _cpu0_fault_lo = .; . += 1024; _cpu0_fault_top = .;
  _cpu0_fault_guard = .; . += 64;
  _cpu1_guard_lo = .; . += 64;
  _cpu1_user_lo = .; . += 8192; _cpu1_user_top = .;
  _cpu1_guard_middle = .; . += 64;
  _cpu1_super_lo = .; . += 2048; _cpu1_super_top = .;
  _cpu1_guard_hi = .; . += 64;
  _cpu1_fault_lo = .; . += 1024; _cpu1_fault_top = .;
  _cpu1_fault_guard = .; . += 64;
  _candidate_ram_hi = .;
 } > RAM :storage
 /DISCARD/ : { *(.comment) *(.note*) }
}
ASSERT(_candidate_start == 0x02000120, "wrong stock-SPL entry")
ASSERT(_candidate_ram_hi <= 0x01c74000, "candidate overlaps reserved upper RAM")
ASSERT(_candidate_bss_hi <= _cpu0_guard_lo, "candidate storage overlaps stacks")
ASSERT(_cpu0_fault_top < _cpu1_user_lo, "candidate stacks overlap")
ASSERT(_cpu1_fault_top <= _candidate_ram_hi, "candidate fault stack not reserved")
ASSERT((_cpu0_user_top % 8) == 0 && (_cpu1_user_top % 8) == 0, "unaligned user stacks")
ASSERT((_cpu0_super_top % 8) == 0 && (_cpu1_super_top % 8) == 0, "unaligned supervisor stacks")
