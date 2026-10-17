# Workbench source and licensing inventory

Pinned source: M-VAVE `m-vave/fm1_open` commit `b178ac43c25f010c60a878056fb5331fe693fd62`. The Open V13 development kit digest is `2a3b2ede16ac49c867831315714ef9d8c532c70ce28ce1dcf3fc76f0a9f68f57`. Its 150 regular files compare byte-for-byte with the pinned public source archive, and all 65 entries in `sdk/manifest.json`'s internal `files` map pass SHA-256. The offline verification command is in [verify_inventory.py](../../tools/workbench/verify_inventory.py); metadata and hashes are in [inventory.json](inventory.json).

## Source and build split

Public source includes APP, board support, browser/workbench and developer scripts, public SDK headers and configuration. The native firmware links `sdk/lib/libfm1_engine.a`, SHA-256 `6a22c111978c8f36827ca83b5f71828313bcb5a3464109b44754266d9bf55e09`. Existing archive inspection records one native member combining engine, sequencer, startup and platform/service symbols, with no LLVM bitcode or DWARF. Board source can be studied, but this is not a supported source-level platform-only runtime.

The native build expects Windows x64, PowerShell and separately supplied JieLi PI32v2 clang 4.0.1 r3. The manifest hashes external toolchain files that are not included in the kit. The web build uses WASI SDK 27. No build was run for this inventory.

## Licensing and reuse decision

`LICENSE.md` states GPL-3.0-only terms with an additional linking permission for the named FM1 SDK. `THIRD_PARTY.md` contains component-level terms, including terms for the proprietary native engine binary on FM1 devices. Some files have separate notices. The linking permission is scoped to covered APP code; it does not grant an unrelated GPL application permission to combine code with proprietary components. Preserve exact notices and review dependencies for each selected file. This inventory imports no vendor source or binary.

There is no demonstrated supported engine-free platform-only seam compatible with Lunar without the relevant vendor permissions. The native APP links a closed archive with engine/sequencer and platform/startup symbols; exposed APP hooks do not establish Lunar's alternative-engine and timestamped MIDI boundary. Keep Lunar's SDK-free GPL native direction, and selectively reuse public source only after file-level review.

## Limits

The hashes identify inspected bytes; they do not establish licence clearance, successful builds, target behavior, recovery, or image distribution rights. See [recovery assets](recovery-assets.md) for the separate stock FWSC, decoded stock SPL/OTA, Open-build SPL and historical owner full-flash evidence. No vendor executable or device was opened by the verifier.\n