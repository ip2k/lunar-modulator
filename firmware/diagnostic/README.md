# Inert startup diagnostic

Independently authored MIT startup and RAM diagnostic, with no SDK libraries,
HAL, ROM services, device traffic or MMIO. This is the first linked firmware
artifact, not an installable or device-verified Lunar build.

The entry disables interrupts, sets a private stack and calls C. C copies
`.data`, clears `.bss`, records the incoming `r0` without dereferencing it,
checks initialization cookies, then increments a RAM counter and checks a
16-byte stack guard. State is exposed as `lunar_diagnostic` in the ELF map:
status 1 means initialization cookies matched, 2 means a mismatch, 3 means a
guard mismatch. No current transport reads that state from a device.

The linker reserves 16 KiB flash at the stock application entry `0x02000120`
and a private 16 KiB RAM window at `0x01c02000`. This avoids the SDK's optional
8 KiB TLB window and its upper boot-info/update reservations [verified: SDK
V1.2.13 `cpu/wl82/sdk_ld_sfc.c`]. The chosen private window and 4 KiB stack
are conservative link budgets [inferred], not a measured SPL ownership
contract. The diagnostic has no watchdog service, clock/power/cache setup,
exception setup, secondary-core synchronization or peripheral initialization.
Those handover prerequisites must be established before a device experiment.
The stock SPL body is loaded at `0x01c02000..0x01c05820` (end exclusive),
excluding its separate 16-byte file header [verified:
`notes/2026-10-09-stock-app-mapping.md`]. This overlaps the diagnostic's RAM
reservation. The current nonreturning loop calls no SPL services, but the
window's ownership and inherited exception stack remain unproven; "private"
describes this link's reservation, not established SPL handover ownership.

## Reproduce the link

Use the preapproved LAN compute workflow and the existing bounded Docker
image/cache; this script neither installs a toolchain nor changes a host:

```sh
bash tools/jieli/link-diagnostic.sh claude@192.168.1.25 \
  /home/claude/mvave-fm1/sdk-v1213/toolchain/current \
  /home/claude/mvave-fm1/codex-board-diagnostic-20261009
```

The acquisition pin is `jieli-linux-toolchains-20250805.1.tar.xz`, SHA-256
`f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958`,
the same pin as `tools/jieli/compile-check.sh`. Validate the cache provenance
through that existing acquisition workflow when establishing a new host.
The inspected existing aeon `toolchain/current` symlink instead resolves to
`jieli-linux-toolchains-20250324.1` [verified 2026-10-09]; prior target evidence
uses that cache and is not proof the newer acquisition pin was installed.
Outputs are ignored under `build/jieli-diagnostic/`: ELF, map, vendor
disassembly, raw application, exported load sections, link audit and memory
report. No vendor binaries enter Git.

`audit_link.py --runtime sdk-free` requires a linked executable with no SDK
key-check/initcall machinery and no mailbox/IRQ/eFuse exemptions. The SDK
policy remains the default and still requires its dormant check unchanged.
`diagnostic_report.py` rejects unresolved symbols, wrong entry, out-of-budget
or unexpected sections, writable code, stack overlap and ELF/flat-image
differences. It does not prove runtime execution or recovery.

## Stage beside stock components

With an unpacked stock V15 reference including its byte-exact `ota.bin`:

```sh
python3 tools/jieli/stage-diagnostic.py \
  --stock build/jieli-diagnostic/stock-v15-reference \
  --elf build/jieli-diagnostic/diagnostic.elf \
  --app build/jieli-diagnostic/diagnostic.bin \
  --out build/jieli-diagnostic/staged-v15-inert
```

The destination must be new. The script repeats the link/layout checks,
copies the stock SPL, configuration and OTA loader unchanged, runs the
existing package guard and records SHA-256 hashes in a staging manifest.
It creates no installable container, version header or flash image. An
unknown inherited watchdog may reset the inert loop, and there is currently
no debugger or device transport to observe its RAM state.

See [the linked result and remaining gates](../../notes/2026-10-09-linked-diagnostic.md).

The separate [handover preparation variant](../handover/README.md) reserves
its own supervisor stack and captures six boot words in RAM. It requires an
explicit build/report profile and remains outside this inert staging path.
