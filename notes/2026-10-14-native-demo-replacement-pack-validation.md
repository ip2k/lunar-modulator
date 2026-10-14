# Replacement demo pack and dependency validation (2026-10-14)

## Result

At source revision c083ec72a2170e6a9a0026f73e606c123c214ed1, the production prepare_demo_selection.py controller accepted the four pinned replacement showcase candidate IDs, staged their catalogued sources, packed them with the native fm1-state codec, and decoded/checked all four outputs. All exact source SHA-256 values matched the exporter pins; every project dependency was present in the full production-55 module selection. Combined packed project bytes: 20,896.

This validates these four offline build inputs only. It does not promote any candidate to an approved showcase/default, establish complete sequence semantics, prove firmware link or target RAM fit, or establish installability or device playback.

## Reproducibility and source evidence

- Isolated Hera worktree: /home/claude/mvave-fm1/native-replacement-pack-decode-20261014; branch feature/2026-10-14@replacement-pack-decode; HEAD/base c083ec72a2170e6a9a0026f73e606c123c214ed1.
- Toolchain image: lunar-recovery-pytest:20261011, image ID and RepoDigest sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d, Linux/amd64. Container ran with network none, one CPU, 2,048 MiB memory and matching swap cap, using docker-batch.slice and project/task labels.
- Fresh native collector build used: make --no-print-directory BUILD=/out/fm1-state-build FM1_GPL_MODS=1 FM1_MODULES=all /out/fm1-state-build/fm1-state. Compiler g++ 12.2.0 (Debian 12.2.0-14+deb12u1). Binary SHA-256 7a3cf4155c6642bd14fb69de25e2c1415b423ce9fa193006a3ef70f55d55fb77; fm1-state meta JSON SHA-256 cda87a7d44517a0e60a9f2013717c46c72abf23ec20b3711e633e7e1f0b5278a. Metadata identifies a GPL-enabled all-modules collector build with 58 IDs, including three test-only modules.
- Request was generated from export_catalogue() and selected only the four replacement-showcase-candidate IDs, retaining production groups: 13 engines, 24 audio effects, 2 MIDI effects, 16 modulation modules (55 selected IDs). Startup points to Afterglow Relay at index 0. The exporter marks these as candidate / owner musical acceptance pending and default_candidate false (tools/native/export_image_catalogue.py:20-23,33-60).
- The controller stages selected IDs, invokes profile preparation, verifies the prepared manifest and records exact source/content hashes (tools/native/prepare_demo_selection.py:22-71). Profile preparation packs the source, reads native records, rejects dependencies outside the selected modules, and marks project dependency scans complete (tools/native/prepare_image_profile.py:87-122).
- Machine-readable details are in notes/2026-10-14-native-demo-replacement-pack-validation/receipt.json, including hashes, bytes, independent check output, decoded record type counts, dependency differences and acceptance flags.

## Packed results

| Candidate | Source bytes / SHA-256 | Packed bytes / SHA-256 | Check and decoded counts | Missing production dependencies |
| --- | --- | --- | --- | --- |
| Afterglow Relay | 22,903 / 53373bf4c508d360eccdf2751fd4242f23478d575adf893a703e6179dcd9c77f | 5,348 / 4992a4cdb17163b40426b54f3bcfd478abf0d7b35572ed3b856ec8b02b081988 | OK; 18 units, 362 params, 1 DX7 voice; 496 records | none |
| Event Horizon | 24,610 / 0d5d871bd31db1e628efbf291fd306671b81c93bef254a950291bf95f5413d1c | 5,108 / 3bd6347eaf8e01a7e89b474a2627cd23b2a0b241d935fd5438decd89b8cd7e12 | OK; 18 units, 334 params, 1 DX7 voice; 519 records | none |
| Packet Bloom | 18,937 / eb55a36129ef3db02136b2ed0859fafcad94e3b2cbc3fa42761383d380249731 | 4,168 / 11ca03e383dfc98e437ae63efbec786b2b31be304ed568bbc110c86800e9b3df | OK; 18 units, 412 params; 562 records | none |
| Satellite Hearts | 31,610 / 090996484a125f5bde3fe4fb0a6dc3284cf7a260d6c6603298206921e78ed5d6 | 6,272 / 04de81e9459baeb1e45fab771ac09fed1ceef69a2563cabd521692a42fbc1278 | OK; 18 units, 320 params; 487 records | none |

All native desktop RAM estimates were below the tool's 387,924-byte estimate budget (244,640, 114,816, 249,856 and 316,816 bytes respectively). These are desktop collector estimates, not target runtime RAM proof. Independent fm1-state records decoding confirmed the displayed record counts and dependencies.

## Checks and limits

- Fresh exact-revision native fm1-state build: passed. Compiler warnings included a state-tool snprintf truncation warning and a sequence scene maybe-uninitialized warning; warnings were not errors.
- Production controller invocation for all four candidates: passed and emitted status prepared-build-inputs; packed output total 20,896 bytes.
- Independent fm1-state check and records for all four packed outputs: passed.
- Pytest was not run: /tmp/check-venv/bin/python was absent, and system Python plus /tmp/lunar-receipt-adapter-venv/bin/python lacked pytest. The production controller and codec were directly exercised.
- The controller receipt leaves installable, native_link_verified, native_ram_verified and hardware_tested false; each project retains sequence_semantics_verified false. The original examples remain legacy rejected showcases; candidate metadata remains pending owner musical acceptance. The full-song default remains pending.
- No hardware, USB, MIDI, flash, power, or reboot operation occurred. No production source was modified.

## Next dependency

A reviewer can decide whether these four candidates are compositionally acceptable and authorize any default selection. Separately, native link/content embed and device-specific RAM gates must pass before claiming installable or full playback.
