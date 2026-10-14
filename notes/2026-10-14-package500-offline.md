# Private FM-1_500 D7000 package candidate

This offline step produced a private structural FWSC candidate from the reviewed 092 container model and the exact FM-1_500 native link. It does not establish stock-updater acceptance, device boot, installation safety, release eligibility, or musical acceptance.

## Exact inputs and result

Pinned source container: /home/claude/.local/share/codex-worktrees/092-package-model/scratch/092-package-model/FM-1_092.fwsc, SHA-256 ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80. Target app: 27600a10bae2ec177699ae2a1e3794b739e6085f61d088c47307db7a0eb515e4 (845272 bytes). ELF: 335c448e67919e2bc52e7421164033ddd505956016531897aebe73f15772a4d1. Artifact receipt SHA-256: 7b28bc74cd250c2f21ca96c2dd8b86efc03550a28bedc569385ea043f8c02129. Build receipt SHA-256: eca3d6d0f2575af44712a6fc6ce32f4b104dd0b6202b7c58df53a0729c79f3ea. The receipts bind explicit application identity FM-1_500, recovery identity FM-1_000, and disarmed/unadmitted SAVE status.

Private output: /home/claude/mvave-fm1/private-package500-candidate/lunar-FM-1_500-d7000.fwsc, 978484 bytes, SHA-256 04eff46e475b54678be580269f0a1683410048b636ea53fc871e7c4a391cb38d. Expanded flash extent is D7000; app space is 845272 bytes with 14408 bytes remaining before the preserved 092 tail limit. No package binary is tracked in Git.

## What was checked

The new composer has fixed input and output paths and accepts no arbitrary path or identity overrides. It verifies exact source, app, ELF, and receipt hashes and receipt semantics, then reuses the strict 092 model under a lock-scoped FM-1_500 app-hash pin. The legacy model is unchanged. After producing the strict nested model, the only byte mutation is the outer physical identity marker. The output is reopened by the generic FWSC reader for outer identity and header/list/payload CRC checks, then checked by the strict nested 092 model after identity normalization for nested app bytes, relocation boundaries, and protected stock payload hashes. The persisted file was verified again after writing.

Protected decoded elements are the stock SPL, isd_config.ini, cfg_tool.bin, cfg, and key MAC descriptor. The strict model compares the complete normalized outer candidate against its modeled output, preserving outer ota.bin and other container entries; it does not decode or exercise OTA-loader behavior. Structural checks do not prove that the proprietary loader accepts the expanded extent or performs relocation safely. The independent check here is the generic FWSC reader plus the strict nested model; no upstream stock updater or physical loader was run.

Focused Hera checks:

- python3 -m py_compile tools/jieli/compose_500_d7000_candidate.py tests/test_package500_d7000_candidate.py — passed.
- /home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/python -m pytest -q tests/test_package500_d7000_candidate.py — 4 passed.
- Tests reject mutated source, app, ELF, artifact/build receipts, outer identity, truncation, and outer CRC corruption.
- git diff --check — passed.

## Acceptance boundary and handoff

The report sets installable, hardware_admitted, hardware_tested, updater_acceptance_verified, and release_admitted to false. Stock updater version/identity policy, expanded-container parsing, proprietary loader behavior, physical flash boundaries, recovery, settings migration, SAVE/runtime, and owner hardware/perceptual approval remain open. This is a private format/correspondence candidate only, not a releasable image.

Branch codex/2026-10-14-package500-offline is based on 450b1f47b715a6ef937e919d9062e3497b4e689a. The implementation, focused tests, and this note are the only intended repository changes. Hera bare-branch backup and final handoff are recorded separately; GitHub backup remains for the Mac coordinator.
