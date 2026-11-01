# Offline ROM execution witness candidate

Lunar Modulator is open firmware for the M-VAVE FM-1. This directory holds
an SDK-free **offline candidate**, not an admitted hardware experiment.
`hardware_admitted` stays false even when every audit passes. No device driver,
serial/USB command, ROM upload/jump, soft key, loader, flash, reset or recovery
operation is implemented by `tools/jieli/rom_witness.py` [verified: source].

The entry is `0x01c02000`; the plaintext upload footprint would be exactly
`[0x01c02000,0x01c02200)`: 202 linked code bytes and 310 zero bytes [verified:
pinned native link]. Only that flat padded payload describes the candidate;
ELF program headers are not a device loading interface.

The primary-core path disables local interrupts, checks `cnum`, drives PA2
inactive high before clearing only DIR bit 2, waits three units, then emits
active-low widths **1, 3, 1, 2, 3, 2**, separated by five inactive one-unit
gaps. It finishes inactive high, PA2 configured as output, in a terminal local
loop. Nonzero `cnum` reaches a separate terminal loop before any MMIO.
The two permitted MMIO addresses are PORTA OUT `0x50000` and DIR `0x50008`;
all changes mask only bit 2. Every RMW preserves the other current bits, but
this is not proof against simultaneous writers. No incoming register is used
as a pointer. No explicit stack/SSP, call/return, data/BSS/heap, SDK or ROM call,
watchdog, clock, reset, power, vector or core-release operation exists in the
71-instruction native listing [verified]. Inherited exceptions, current-core
privilege and another core's activity remain unresolved.

Each unit is 1,048,576 bounded register decrements and conditional branches.
Twelve delay loops sum to 20 units: 20,971,520 decrements and 20,971,520
conditional branches [verified: native listing and bounded symbolic model].
These are **instruction counts, not elapsed time**. No native cycle cost or
cold-ROM clock range was established. The roughly two-second ROM watchdog is
only historically reported, not a guaranteed budget. Therefore useful optical
capture timing and full-pattern completion cannot yet be justified; do not
admit this candidate or change clock/watchdog settings to hide that blocker.
A later coordinator must establish a credible timing/capture window or review
a different shorter signature/delay mechanism with a newly pinned artifact.
Ordinary video may alias the sequence. A single bright screen, USB effect,
transport error or reconnect cannot establish this signature executed.

## Frozen build and audit

In a bounded Linux build container with only the existing licensed pinned
compiler/binutils mounted, run:

```sh
python3 tools/jieli/rom_witness.py build --toolchain /opt/jieli \
  --out /out/new-private-witness
python3 tools/jieli/rom_witness.py audit /out/new-private-witness
```

Use a new ignored output directory; never use a device path. The builder pins
all four tool executables and the two source inputs, uses `-Werror`, links only
one assembly object with orphan rejection and no libraries, pads with zeros,
then audits the exact bytes, native operations/branch targets, entry, sections
and symbols. The manifest is itself hash pinned in the auditor; any change
requires explicit independent review and repinning. A hash is an identity check,
not proof of safe hardware behavior. The native build's ELF/code/payload
receipts belong in private ignored storage. Retain source, manifest and reports;
remove the reproducible stage/object when results are saved.

Focused checks:

```sh
LUNAR_ROM_WITNESS_NATIVE_DIR=<private-output> python -m pytest tests/test_rom_witness.py
```

These include every single-byte payload mutation, native listing/MMIO/branch
changes, wrong ELF entry/machine/sections, manifest tampering, source/tool pins,
and a bounded symbolic control-flow/GPIO model. They do not emulate silicon.

## Provenance and unresolved admission

The assembly, linker and auditor are MIT, independently authored here. The
fixed RAM linker and `cli`/`cnum` guard concepts follow the project's MIT
`firmware/core-reset/` and `firmware/entry-guard/` at historical installable
commit `cccd21cc5dc82859ed8a5d84f0a7a40646d07353`; no reset write or SPL `r0`
comparison is carried over. The native listing audit concept follows its MIT
`tools/jieli/entry_guard_audit.py`; the current MIT `audit_link.Elf` parser is
reused read-only. No existing guard or pinned historical receipt is changed.

PORTA addresses/offsets were verified directly against JieLi AC79 SDK
`WL82.h` at `e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d`: port base
`0x50000`, OUT word 0 and DIR word 2 [verified: unprotected source]. PA2's active-low backlight role is reported by
hugelton's Felucca/Dinghy HAL (GPL-3.0-only); that pin fact informed this
independent program, with no GPL implementation copied. It remains physically
unverified on the owner's unit. No SDK archive/header or vendor image is a
build input, and no protected binary analysis was performed.

Hardware admission additionally requires fresh identity, cold-ROM/Pico binding
and exclusive ownership, PA2 physical visibility/ownership confirmation, strict
transport completion and exact one-shot pre-submit latching, and an independent
optical capture begun before the single jump. Upload plaintext padded bytes to
the Pico layer, never wire ciphertext that it would encrypt again. Do not use
generic `ramrun`, auto-softkey, loader, post-jump readback, retries after ambiguous
jump, or historical consumed adapters. Owner cold-cycle and any separate docs17
fallback stay coordinator-owned. No preparation state machine was added: without
an admitted artifact or transport driver it would provide no additional gate.
