# Shapes8 Event Horizon 120-second expanded candidate (offline)

## Result

The guarded `expanded_candidate.construct` path accepted the exact recorded FM-1_092 fixed-loader backup pair and the current Shapes8/Event Horizon link, producing a private raw 1 MiB candidate. The exact candidate target is outside Git at `/home/claude/.local/share/codex-private/shapes8-event120-expanded-candidate-20261014/target.bin` (mode 0600; containing directory mode 0700), SHA-256 `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`. Its candidate receipt is alongside it, SHA-256 `1c53f94ba57001f30901a2f33081f26c223f1789781abaa0f5325e83880684db`.

This is a private raw geometry candidate, **not an OTA package or installable image**. The constructor and independent geometry validator preserve all current admission flags as false. No device, USB, MIDI, flash, power, or reboot operations occurred.

## Exact input correspondence

The link artifact came from `/home/claude/mvave-fm1/shapes8-target-fit-20261014/link/`:

- `artifact/app.bin`: 845,036 bytes, SHA-256 `5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573`.
- `lunar-app-probe.elf`: SHA-256 `db9d800022a4e73e672b049ee1aa350a01858a4baad58ef50eebe732e6d03134`.
- `artifact/disassembly.txt`: SHA-256 `b7169729abd8896937985a0ef9d895b274bafa533d90ac8ce2b7e74e43098b55`.
- `verification.json`: SHA-256 `d448735e1d75f04d959f6da9233108ac9bb8e7fb62124e12b494dc8bd94965f8`.
- `artifact/artifact.json`: SHA-256 `a42d7d1847d9b76a97752b9a910d0cf600982f87169eb07a7a5d1732bc33a059`.

The generated/prepared selection is under `/home/claude/mvave-fm1/shapes8-target-fit-20261014/prepared-selection/`. Its `selection.json` SHA-256 is `6c1734d217bb3fde600d5684d20c4792cb98f49bfd6ee410bb36f7ae0013437e`; prepared `profile.json` SHA-256 is `09e083de657a66d0bee17c2f65d8771d270de9e710ce7e7f896bb83016ce8702`. The selected project list contains only `replacement-showcase-candidate-event-horizon`, startup index 0. Linked embedded-content prepared-profile digest, packed asset digest, kind/size/hash, and startup index match those exact selection inputs. The link uses runtime `song-diagnostic` for 120 seconds; `runtime_hook_linked=false` is expected for the one-project selection.

Link metadata reports 55 selected production module IDs, eight Shapes voices, indexed TFT, 165,376-byte instance pool, and compressed Plaits plus Braids tables. SAVE is linked with `LUNAR_PROJECT_SAVE_SERVICE=1`, but `save_service_armed=false`, `storage_admitted=false`, and `flash_write_range="empty"`. The artifact and verification both keep `installable`, `hardware_admitted`, and `hardware_tested` false. This task does not establish full-song performance, physical runtime, storage admission, or save/reload.

## Backup provenance and target geometry

The two retained baseline dumps are each 1,048,576 bytes and match at SHA-256 `96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`. The backup manifest (SHA-256 `1ab5e38943648080d9fde9fa86197607aa7a0e01c19da62cd20f24e8f11280cf`) explicitly identifies `fm1-fixed-loader-backup`; the identity receipt SHA-256 is `6a585e03a819ada8b10d2ff3618610fbb32136b9fa8b4f0b8027acd6b68ccc2f`. The constructor independently verified paired bytes, retained reference, fixed-loader provenance, ELF reconstruction, SDK-free link audit, and expanded geometry.

The constructed `expanded-d9000-recorded-092` image has 213 changed 4 KiB sectors, offsets `0x4000` through `0xD8000`, with the application directory sector at `0x4000`. The unchanged protected raw prefix is `[0x00000,0x04000)` and protected suffix `[0xD9000,0x100000)`; both equal both retained backups. The independent expanded geometry validator confirmed exact decoded app payload correspondence, preserved configuration contents/tool, and protected ranges. It preserved the stock boot components including `uboot.boot` SHA-256 `730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`. The retained dump pair is provenance only, not a fresh pre-write observation or physical admission.

## Transport-manifest blocker

The existing `tools/native/expanded_transport_manifest.py` requires a linked image receipt that passes `build_demo_image.checked_link_receipt`. That checker rejects this exact link in `checked_wavetable_profile` with `ValueError: Linked image wavetable profile differs from fixed policy/module selection`: its current fixed policy requires 12 Shapes voices and the fixed Plaits-XIP profile, while this link has eight voices and `flash_plaits_wavetables=false` (with the actual compressed Plaits and Braids table rows recorded above). I did not override the verifier, fabricate an image receipt, or emit a transport manifest. Therefore **raw candidate construction is complete, but candidate-to-transport receipt correspondence is not**.

Next bounded implementation: extend the fixed wavetable profile validator and transport-receipt policy only if the current Shapes8 build contract is intended to be supported. Bind exact namespace/table hashes, compression metadata, eight-voice setting and derived pool value from source and link evidence; add positive and tamper tests. Then rerun checked linked-image receipt and `expanded_transport_manifest.build_manifest` against this exact private candidate. Keep all output gates false until separate recovery/migration and fresh-device acceptance.

## Checks and limits

- `tools/native/expanded_candidate.construct(..., baseline_profile="fixed-loader", ram_layout="combined")`: passed with exact input bytes and disassembly.
- `expanded_flash_profile.validate_geometry(...)`: passed; candidate target decodes to the exact linked app and protected/configuration checks pass.
- Link-to-selection correspondence checks: request profile hash, ordered one-project ID/startup index, packed content hashes and sizes match.
- `/home/claude/mvave-fm1/ci-contract-repairs-20261012/.venv/bin/pytest -q tests/test_expanded_transport_manifest.py`: 11 passed.
- A mistakenly requested nonexistent `tests/test_expanded_candidate.py` path was corrected; no test was skipped from the actual transport-manifest suite.
- Transport generation was deliberately blocked by the current fixed Shapes12/Plaits-XIP receipt policy; it was not bypassed.

Private generated files are not committed. This note records offline construction only; there is no claim of OTA compatibility, installability, hardware admission, recovery, settings migration, or playback acceptance.
