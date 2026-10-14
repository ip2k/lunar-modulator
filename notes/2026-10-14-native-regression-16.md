# Native/install/save/recovery 16-shard regression

## Result

The exact-base offline regression completed with **2,256 passed, 81 skipped, 0 failed, and 0 errors** across 2,337 unique selected node IDs in 79 test files. Every selected node ID appears in exactly one shard. The machine-readable shard receipt, per-shard node-ID hashes, result counts, container image, and log hashes are in [aggregate.json](2026-10-14-native-regression-16/aggregate.json).

This evidence is for source commit `2863b8dbf4d538bdda87aa970b8cd38d26628a90`, tracked-source manifest SHA-256 `a1b459261aedcf5de3027bb1598ee6dd24f3f2a19de28a38e0e2658d46799398`. The suite deliberately predates the later `test_model_092_app_replacement.py`; that model is outside this regression's coverage.

## Scope and execution

The selected set covers native app/profile/catalogue/project/save/state/settings/preload/runtime/toolchain tests; installer API; event120 campaign, transaction, proof and reset models; expanded and ROM backup/recovery paths; SDK trace/rehearsal; and the Dinghy flash transport simulator. Collection found 2,337 distinct node IDs across 79 files; each was assigned to exactly one of 16 node-ID manifests. The exact selected files and node-ID manifests are recorded in the JSON receipt and retained output directory.

Execution used the pinned Hera image `sha256:1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313` with Python 3.12 and pytest 8.4.2. Each worker was bounded to 1 CPU, 2 GiB memory and swap, 256 PIDs, and ran under `docker-batch.slice` with networking disabled. The state-tool binary was `fm1-state` SHA-256 `7a3cf4155c6642bd14fb69de25e2c1415b423ce9fa193006a3ef70f55d55fb77`; the pinned pi32 toolchain was mounted read-only.

The corrected 16-way run passed 14 shards immediately. Shards 11 and 12 first failed only where their tests needed a read-only bare Git directory and private retained recovery evidence that had not been mounted. They were rerun individually against the same source commit in separate scratch copies, with the state-tool, pi32 toolchain, bare Git directory, and private evidence tree mounted read-only. Each retry exited 0 and covered its exact original node-ID manifest. Those scratch copies were writable only because selected simulator tests create build outputs under the source tree; no tracked files in the assigned checkout were changed.

The run emitted the pinned Starlette `TestClient` deprecation warning about httpx compatibility. It was not treated as a test failure. Quiet-mode shard logs record the aggregate skip count but not per-test skip reasons.

## Limits

These are offline host, target-toolchain-assisted, simulator and mocked recovery checks. They do not demonstrate firmware running on hardware, physical recovery, audible/perceptual acceptance, successful device installation, or a green GitHub Actions run. No device or USB/MIDI/flash/power/reboot operation was performed. No production source was edited for this task.
