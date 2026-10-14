# Continuous FM-1_500 D7000 package model

This adds a separate, private structural composer for the retained continuous FM-1_500 target. It reuses the reviewed FM-1_092 FWSC nested parser/relocation model and its bounds; it does not alter the existing diagnostic composer or its exact target pins. The output is a local research candidate only. It does not establish updater acceptance, boot/recovery safety, physical installation, or runtime/perceptual acceptance.

## Exact target binding

The continuous link receipt is distinct from the diagnostic image. Its app is 845,336 bytes with SHA-256 `5c923197629121ce90a33919b516ced23ef8edbaa1943ea1e9568b596b6557ee`; the ELF is 978,248 bytes with SHA-256 `4b8ae5a1f68550bcbedc2442d98f03f5af85daa88fcfbb69af37985b3d9f0120`. The artifact receipt SHA-256 is `501c690e8d2c927ac79e45de617195b734f838bb6652aa6c43e62928419a5604`; the full verification receipt SHA-256 is `d1ec99dd5c45862a921b6579949ee6b71cc16eef2391eabaff5f2e57a578083f`. Runtime policy digest is `fe457ad4056aeb8e6b3ec9df606ac79ab757adc142bd2db9780357fb72f1e905`.

The exact private link artifacts are under `/home/claude/mvave-fm1/continuous500-link-20261014/out3/build/`: `artifact/app.bin`, `lunar-app-probe.elf`, `artifact/artifact.json`, and `verification.json`. The authoritative target-link note is `notes/2026-10-14-continuous500-target-link.md`; it reports source commit `b7998a28ea1d6805c52fbbf69cc8ab45a9764c20`, expanded-d7000 profile, Shapes8, all 13 sound engines and all 55 production module IDs. The 55 selections are 13 sound, 24 audio-FX, 2 MIDI-FX, and 16 modulation modules; three test-only modules are excluded. The module header digest is `eef6dabe417ebdb03c5ab510f7b4a3733aed331bf656ae26e7535f87276e861e`.

The receipt is bound to continuous mode: `-DLUNAR_RETURN_TO_ROM_SECONDS=0`, `runtime_mode=continuous`, and `return_to_rom_seconds=null`. It has no diagnostic return timer. The build reports 860,644 bytes of application budget, leaving 15,308 bytes for this 845,336-byte app. SAVE code is linked but storage admission, flash binding, and service arming are false. Runtime, hardware, installability, and package/updater acceptance fields remain false. None of these link facts constitute hardware or listening evidence.

## Composer and result

`tools/jieli/compose_500_continuous_d7000_candidate.py` pins the app, ELF, artifact receipt, verification receipt, module-header digest, and continuous runtime policy. It rejects a diagnostic-mode receipt, wrong module selection, a test module, modified artifacts, and any target that arms or admits SAVE or installation. Its CLI emits only to the distinct private path `/home/claude/mvave-fm1/private-package500-continuous-candidate/lunar-FM-1_500-continuous-d7000.fwsc`; that binary is not in Git.

The composer reuses `tools/jieli/model_092_app_replacement.py` under the existing serialized, exception-safe target-app pin context. Verification normalizes only the outer identity marker for strict 092 nested-model verification, reopens the FWSC header/entry/payload CRCs, confirms the app and nested D7000 boundary, and compares the result to the exact modeled package. Protected decoded SPL/config/CFG/key data are checked for identity preservation; no protected content is included in this note.

The emitted private package is 978,484 bytes, SHA-256 `8968c1e709529ba5f1d9a0eb42c07f31ebced9d24cd6ad8a2fd7dec0b7296355`. Its modeled app is 845,336 bytes, ending at `0xD2A18`; the strict model reports 14,344 bytes to its D7000 stage boundary. This is a container/model result only: outer payload re-encoding and address transforms are not proof that a stock updater or device accepts the package.

The existing diagnostic composer remains unchanged and separately pinned to its older 845,272-byte target. Its test suite passes alongside the continuous suite, which prevents accidental replacement of the diagnostic artifact or output binding.

## Navigation tools

Serena instructions were loaded, and Rarefaction Python status was ready for the active Mac checkout. The bounded orient request for `_bound_target_app_pin` returned no symbol because that index is not the seeded Hera worktree and does not contain this new module. I left the shared semantic-tool root unchanged; the exact-source inspection was performed against the isolated Hera checkout. This is a root/index coverage limit, not evidence that the symbol is absent from this branch.

## Validation and limits

On Hera, using the already-present `wave-receipt-validation-20261014` pytest environment:

- `pytest -q tests/test_package500_d7000_candidate.py tests/test_package500_continuous_d7000_candidate.py` — 10 passed.
- `git diff --check` — passed.
- Continuous tests exercised the retained source/build artifacts, CRC and identity corruption rejection, exact input-hash rejection, continuous-mode and exact module-selection rejection, and restoration of the shared model app pin even when verification raises.

This is an offline package-composition milestone only. The source FWSC and unpacked reference remain private inputs; no owner stock bytes or vendor binary were added to Git. No device, USB, MIDI, flash, power, reset, updater, or recovery operation was performed. The package remains `installable=false`, `hardware_admitted=false`, `hardware_tested=false`, and `release_admitted=false`. Next required work is independent review and coordinator integration, followed by separately authorized updater/recovery and hardware validation; this composer must not be treated as admission.
