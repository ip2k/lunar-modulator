# Return-only ROM witness candidate

Lunar Modulator is open firmware for the M-VAVE FM-1. This separately named
MIT source candidate contains one explicit `rts` at `0x01c02000` [verified:
source]. It is an **offline candidate only**. The original PA2 W01 source,
manifest, tool and bytes are unchanged. No upload, USB, loader, Pico, reset,
flash, discovery or recovery interface is implemented here.

The prospective code contract is two bytes, `80 00`, followed by 510 zero
padding bytes for an exact plaintext envelope `[0x01c02000,0x01c02200)`.
This encoding is a source hypothesis until the pinned vendor build and its
disassembly are inspected. Host fixtures do not establish native output.
Only the flat envelope describes the proposed upload; ELF program headers
are not a target loading API. No address, code or footprint override exists.

The instruction returns through inherited return state and changes control
flow. There are no explicit unrelated register writes, stack/data accesses,
MMIO, interrupt changes, delays, pointer dereferences, runtime/ROM calls,
hooks, watchdog/clock/power/vector operations or core release [verified:
source]. Nothing initializes or validates RETS, privilege, target dispatch
core, cache or exceptions. Do not add `cli`, a core guard, a refusal loop or
watchdog handling to make an unqualified assumption appear to pass.

## Offline build and structural checks

The independent source freeze and allocated native build are separate gates.
After that build is authorized, in the existing pinned Linux toolchain stage:

```sh
python3 tools/jieli/rom_witness_return.py build --toolchain /opt/jieli \
  --out /out/new-private-return-witness
python3 tools/jieli/rom_witness_return.py audit /out/new-private-return-witness
```

The output directory must be new. The builder checks exact source and tool
hashes, compiles only this assembly with `-Werror`, links with orphan rejection
and no libraries, exports only `.witness_return`, and invokes the vendor
disassembler. The linker requires exactly two code bytes. The auditor checks
one exact return instruction at entry, matching ELF/exported bytes, fixed
sections/symbols, no relocation/BSS/foreign or undefined symbols and every
padding byte. Existing MIT `tools/jieli/audit_link.py::Elf` is reused read-only.
Original W01's four executable pins are reused without downloading anything.
No SDK headers, archives, vendor image or protected input is used.

```sh
python3 -B -m pytest -p no:cacheprovider tests/test_rom_witness_return.py
```

These actual-checker tests use synthetic ELF/listing fixtures and directed
negative mutations. They prove parser refusals, not instruction execution.
An optional `LUNAR_ROM_RETURN_NATIVE_DIR` points to separately authorized
vendor output for the same audit. A structural receipt always says
`hardware_admitted=false`, `rom_abi_qualified=false`,
`fetch_coherence_qualified=false`, and `watchdog_lease_qualified=false`.
Retain native outputs until independent review consumers finish; then keep
small listings/receipts/logs/hashes and delete only owned reproducible products.

## Provenance and remaining limits

The assembly, linker, builder and tests are independently authored MIT source.
The narrow fixed linker/checker approach follows the project's MIT W01 tool;
no optical operations are carried over. The opcode convention is reported by
kagaimiq's local `jielie/cpu/pi32v2.md:35–42,58–74`, pin
`1657d25e6e51df6b2c18cd55cfc576c4a6370c63` [reported]. The vendor tool output
must verify the emitted opcode, not a host ISA substitute or hand encoding.

kagaimiq's `jl-uboot-tool/docs/usb-loader-v2.md:195–253`, pin
`adb3f18889e88ac512ce0a3c4d8cc3d3cb30696a`, reports ROM FB08 replies after
called code returns [reported]. It does not establish this unit's bare RETS
contract, return preservation requirements, fetch coherence or remaining
watchdog lease. A loaded loader can reply before the call, so its response
cannot be substituted for an unbroken cold-ROM chain. No returned register
value or nonce-bearing response is documented. This code implements neither
transport nor a target challenge/response.

Even a native structural pass admits no hardware action. A future separately
reviewed strict transport must bind the exact artifact and cold-ROM/Pico
state, enforce exact BOT completions and durable one-shot intent, and forbid
loader startup, auto-softkey, readback, later commands or replay after an
ambiguous submission. An eventual valid reply would support call-and-return
only under the documented ROM contract [inferred]. No RAM execution, core,
watchdog timing, I11, audio, native startup, install or recovery is proven by
this source or its host checks.
