# Bound native diagnostic and ROM witness rebuild — 2026-11-01

Personal, non-commercial. Parent-authorized offline validation only. No hardware, USB/MIDI, transport, ROM jump, flash/reset, service listener or admission change is authorized by this lane.

## Saved plan

Build exact frozen source `9440b08191b50f1ab8f75dd6a8fba2a2dc558160`, exported by `git archive`, from evidence branch `chore/2026-11-01@native-bound-rebuild` in `/Users/likwid/.codex/worktrees/lunar-native-bound-rebuild-20261101`. Source remains frozen; only this note changes unless a concrete compatibility defect requires a separately reviewed correction.

[verified] Read prior native/ROM build notes and private native handoff plus LAN skill/README/CLUSTER/HANDOFF and shared Hera coordination README. Existing Aeon account is `claude` (UID/GID 1003), route uses bond0. Existing image `lunar-jieli-check:bookworm` resolves to `sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495`. Archive is existing `sdk-v1213/dl/jieli-linux-toolchains-20250805.1.tar.xz`; extracted tree is `sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1`. The differing archive/internal names are historical documented identities, not grounds to override the content pin. Original libc++ headers come from `sdk-v1213/sdk/include_lib/c++/include`; SDK worktree identity is `e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d` and its `__config` matches the earlier receipt.

Use only existing archive/toolchain/header inputs, mounted read-only; no download, new unpacking or protected-target analysis. Validate through the new full-tree binding before actual diagnostic compile; independently build/audit the frozen ROM candidate using its existing executable pins. Preserve original `tools/jieli/audit_link.py` and all false admission/release flags. Inspect exact source/binding/object/ELF/app/ROM manifests and audit rows. No cache/object reuse.

Aeon private unique stage: `/home/likwid/datasets/lunar/native-bound-20261101t111401z`. Container: `lunar-native-bound-20261101t111401z`; network none, unprivileged UID/GID, read-only root/source/toolchain/header mounts, private writable outputs and bounded tmpfs. Parent reserved CPU8–11, at most4 CPUs, memory/swap6 GiB, `docker-batch.slice`, project/session labels and capped per-container logs. One foreground command with an outer timeout and exact-name cleanup trap; no daemon startup or infrastructure changes.

Lifecycle: synthetic/test fixtures, exported source tar/stage, objects and copied/configured headers are reproducible intermediates and removed once evidence is captured. Keep only small private logs, receipts/maps/listings and exact candidate artifacts needed for offline audit; no vendor bytes or binaries enter Git. Local evidence stays under `scratch/native-bound-rebuild-20261101/`, remote retained evidence under the named stage's `evidence/`. Tests use existing venv read-only, bytecode/cache disabled and isolated finally-cleaned basetemp. Shared claim `lunar--native-bound-rebuild-20261101` is released after durable handoff. Built-in free space at start:1120 GiB; Aeon dataset filesystem free:4.5 TiB. Worktree remains until coordinator notes integration/abandonment, then normal worktree removal.

Code tools: Rarefaction and Serena were rechecked and remain on the primary absolute checkout; their known external-worktree scope limitations remain. No shared root switch/restart and no fresh pi32v2 semantic-index/ABI claim. Prior focused independent binding review remains the source-review basis; this lane adds actual archive/build evidence only.

## Actual result

[verified] The existing pinned archive and extracted tree are compatible with the new binding, without any source correction. Archive SHA-256 is `f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958`; internal root is `jieli-linux-toolchains-20250324.1`. All **694 entries** match (599 files,51 directories,44 internal symlinks), including bytes/executable bits/link identity. Canonical tree SHA-256: `851733550499eca33cd737b2343bf48a1c846e0fe7246054d8372d43e7cfa066`. Actual read-only container mounts and final input snapshot were checked. No vendor archive was newly extracted; only our own committed Git source export was unpacked into the private stage.

[verified] Exact Git source export SHA-256: `78329d6bcf856b8654e3557f6982a2369c8caf95b6612105d52590872acf8b5c`. The build's **738-file source manifest** matches this checkout and differs from the prior native receipt only at `tools/native/build_diagnostic.py`. Canonical sorted/minified-JSON source-manifest SHA-256 is `de0c86456d53bd34a95588e92801d745d19daef19627352117798d2e8bf9a07e`. All127 objects compiled fresh and their recorded hashes were independently checked before removal. Original189 libc++ hashes match the earlier receipt; configured189 hashes differ only at the documented generated `__config` pthread selection. No SDK archive or device-header closure was linked.

[verified] Diagnostic build and a separate original `audit_link` CLI run pass: **12 checks,0 failures,0 pending**. It retains `hardware_admitted=false`, `release_candidate=false`, eight FM6 runtime voices,65536-byte external arena and no CPU1/USB/persistence/fail-open. Current artifact identities:

| Item | SHA-256 |
| --- | --- |
| Diagnostic ELF | `269bd20eba2bcd2b29ca414fc05c381479b0769d3269159489da63bebd193dbc` |
| Diagnostic application | `30d7fdfe5cce6c1c17079ad4356523757c8be3a768e1c8f4d811e450509e5d3f` |
| Frozen ROM manifest | `f6bc573b17825f024aac7145699c909e79d5a0493f56ca264b76c6181ee2b8ca` |
| ROM ELF | `d6aae309a28712d8c011dd3c61a6dfe018a2c008ad6fcc209bb28759c101f75c` |
| ROM202-byte code | `77cface4e17a3761eb31c4995aeff246610acdebcf9b36b792db00473fcedbd0` |
| ROM padded512-byte plaintext | `f45330e5f5428260750c1863ae485a5504587323b8c23af2e2017df0c38b55f4` |

[verified] Diagnostic application hash and complete recorded size dictionary match the prior build: flash210364 bytes (.text210360 + .data4), .bss300240, .noinit64, app232832, arena65536, descriptors112 and142112 bytes to the first stack guard. New ELF hash differs from the earlier ELF; only application/load-byte identity and recorded sizes are claimed equal, not full ELF reproducibility. Both identities remain recorded separately. Reserved stacks do not establish target call-depth safety.

[verified] The new ROM build reproduces all frozen ELF/code/payload hashes. Its exact native listing/geometry audit and a separate unchanged SDK-free `audit_link` run pass (12 checks,0 failures,0 pending). Pure Python tests used the existing read-only venv with `LUNAR_ROM_WITNESS_NATIVE_DIR` set to this actual private bundle: **96 passed,0 skipped,0.68 s** across `test_native_diagnostic.py`, `test_rom_witness.py`, `test_audit_link.py`. Full receipts, all evidence-file SHA-256 values and source export digest were verified after transfer.

[verified] Container inspection confirms the immutable image, CPU8–11/4 CPU,6 GiB memory/swap, docker-batch.slice, unprivileged execution, no devices, network none, read-only root and input mounts. Initial Docker create refused local-log compression with max-file1 before any task ran; setting per-container `compress=false` resolved it without a daemon configuration change. Final builder/ROM/audit statuses all0. The exact owned container is absent and CPU8–11 are released. No hardware or public service operation ran.

## Evidence, cleanup and limits

[verified] Private evidence is retained at `scratch/native-bound-rebuild-20261101/` in this worktree and `/home/likwid/datasets/lunar/native-bound-20261101t111401z/evidence/` on Aeon (about7.6 MB each). It contains source/binding/object receipts, audit JSON, size/map/listings/build commands, runtime bounds and exact small non-admitted artifacts for coordinator review. Raw vendor/header bytes are absent. No binary is committed. No open stage files or owned containers existed before cleanup; owned source tar/tree, object/output/header directories and local bytecode/test temps were removed. Shared archive/toolchain/header inputs and image are untouched. Mac free space after cleanup:1118 GiB. Retain these small evidence bundles until coordinator source/receipt review and the relevant admission decision; source worktree cleanup remains after notes integration/abandonment.

This closes actual archive compatibility and offline rebuild evidence for **exact9440 diagnostic source only**. It does **not** establish aggregate RAM fit for later correction `951ca6eb`, an all13/full-product target, host/browser parity, source-wide audit, runtime deadline/stack/audio behavior, package/install eligibility or ROM/hardware admission. No memory budget was changed. Existing read-only-input/controlled-host assumptions, missing full audit-link helper/admission work and pending-row promotion policy remain in force. Required PR163 CI and parent review remain separate gates; earlier physical/recovery/PA2/entry/transport obligations remain open.

Next dependency: coordinator reviews the notes and private bound receipts, integrates this notes-only branch if useful, and completes PR163's required CI/review. Any corrected aggregate native target requires a separately sized/source-bound build; do not substitute this diagnostic's unchanged sizes. No owner hardware action is requested here.
