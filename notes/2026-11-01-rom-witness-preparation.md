# ROM witness offline preparation — 2026-11-01

## File plan and bounded contract

Base: `b831724fcf413720aaa036dac742a382cdfaa93c`.
Branch: `feature/2026-11-01@rom-execution-witness`.
Worktree: `/Users/likwid/.codex/worktrees/lunar-rom-witness-20261101`.

Planned owned files:
- `firmware/rom-witness/witness.S`: independently authored MIT stackless primary-core-only PA2 finite optical signature.
- `firmware/rom-witness/witness.ld`: one RAM code section at `0x01c02000`, max 512 bytes, no writable sections.
- `firmware/rom-witness/README.md`: source provenance, exact limits, signature, pending admission gates.
- `tools/jieli/rom_witness.py`: offline build/audit/manifest only; no device imports or commands.
- `tests/test_rom_witness.py`: rejection tests for exact bytes, native listing/geometry, padding and immutable manifest.
- This note: evidence, checks, handoff and cleanup.

No hardware traffic, PR or merge. No changes to existing device/reset/installer/engine/simulator paths. Native compilation uses only the pinned compiler/linker/binutils (no SDK archive or firmware input). Build products stay in ignored `scratch/rom-witness-20261101/`; remote staging is uniquely `/home/likwid/datasets/lunar/rom-witness-20261101`, removed after results are retained. Preserve small logs/listing/manifest; never commit binary/toolchain. Mac initial free space: 1117 GiB [verified].

Candidate admission is false. PA2 physical role and exclusive cold-ROM ownership, clocks/watchdog/capture timing, ROM entry ABI/cache/exception behavior, strict transport completion and fresh identity/optical capture remain later coordinator gates. The signature is pulse order/relative loop width, not claimed milliseconds. A USB effect alone cannot establish execution.

## Offline result

[verified] Independently authored MIT assembly linked at the fixed RAM entry with no libraries. Pinned vendor listing contains 71 instructions / 202 bytes. Only two MMIO addresses occur; primary-core rejection precedes all MMIO, output inactive is established before direction, and all 14 MMIO operations mask PA2 alone. Signature W01 widths are 1,3,1,2,3,2, with preamble3 and five gaps1. Twelve bounded loops total20 units =20,971,520 decrements plus20,971,520 conditional branches. Terminal leaves PA2 inactive high and output enabled; nonprimary path touches no MMIO. No explicit stack/SSP/data-memory/foreign calls/reset/flash/loader/core release/clock/watchdog use. This does not establish inherited exception/core/cache safety or physical visibility.

[verified] Existing compiler archive hash matched `f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958`; its unpacked directory is named `jieli-linux-toolchains-20250324.1` despite the archive filename `20250805.1`. All four actual compiler/binutils hashes are pinned in the manifest; no toolchain download/unpacking occurred. Build container ID `sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495`, no network, CPU12-15 /4CPU/6GiB memory+swap, docker-batch.slice, --rm, project/session labels. Only candidate assembly/linker and the existing MIT ELF parser were source inputs; zero SDK archives, SDK headers, vendor images or loaders. Two native builds (initial commands and final audited builder) produced identical ELF/code bytes.

Frozen identities [verified]:
- manifest SHA256 `f6bc573b17825f024aac7145699c909e79d5a0493f56ca264b76c6181ee2b8ca`
- ELF SHA256 `d6aae309a28712d8c011dd3c61a6dfe018a2c008ad6fcc209bb28759c101f75c`
- code SHA256 `77cface4e17a3761eb31c4995aeff246610acdebcf9b36b792db00473fcedbd0`
- padded plaintext512 SHA256 `f45330e5f5428260750c1863ae485a5504587323b8c23af2e2017df0c38b55f4`

[verified] Checks: 30 focused tests, including the actual native bundle and a bounded instruction-operation model;42 existing `test_audit_link.py` tests; standalone audit CLI; `git diff --check`. The tests mutate every payload byte and reject wrong code/padding, entry/machine/allocated sections, native branch/MMIO/stack/call listing changes, source/tool/manifest drift. Host symbolic checks are not ISA emulation, target timing or device acceptance. Initial system `python3` had no pytest; used existing primary-checkout `.venv/bin/python` without dependency installation. No unrelated suite or hardware tests were run.

[verified] Rarefaction status and Serena initial instructions/config selected primary absolute checkout `/Users/likwid/Developer/mvave-fm1-firmware`. Did not activate another shared project. Bounded Rarefaction `package_guard.py:43:5` matched direct `_sha256` source and known `check_package` caller; Serena found `main` at matching lines117-136. New external worktree cannot be selected with relative project under the fixed root; its files were read directly. No claim of semantic indexing of this external tree or pi32v2 ABI validation; no graph was built. Native listing and actual compiler, not host clangd, establish the exact emitted instructions. Old MIT sources were checked at exact historical commit `cccd21cc5dc82859ed8a5d84f0a7a40646d07353`, with no owned source modifications there. Pinned SDK header source was verified directly for port geometry only; no protected binary analysis.

## Remaining gate and next dependency

`hardware_admitted=false`. Cold-ROM clock range, branch/csync costs and watchdog budget are unresolved, so no honest elapsed capture window can be promised for the41,943,040 loop instructions. Standard video may alias the signature. Stop at offline prepared rather than disabling watchdog/changing clocks or reducing the contract. Coordinator should independently audit frozen bytes/control flow, settle PA2 physical visibility/exclusivity and optical capture timing, then design the exact one-shot strict transport wrapper under a separate reviewed hardware admission. No protocol/state machine was added absent that artifact admission and driver. Generic `ramrun`/auto-softkey, loader/reset/full-flash routines, post-jump reads and ambiguous retries remain excluded. This lane closes no physical RAM execution or formal I11 requirement.

Private retained bundle: `scratch/rom-witness-20261101/native/` contains ELF, raw code, padded plaintext, vendor listing, receipt and standalone audit JSON; all ignored. These small exact candidate artifacts remain needed for coordinator review. Reproducible staging/object/archive and test caches are removed after result capture; no remote build cache created. Initial available1117GiB, final1120GiB [verified]. No device operation, PR or merge performed. Feature branch checkpoint `ef58b0fb8307e1a1ca04fcdc6f4edcf7cc2219df` was pushed and remote verified; final delivery is the subsequent branch head identified in the coordinator handoff.
