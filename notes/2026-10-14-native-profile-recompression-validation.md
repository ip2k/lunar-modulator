# Native profile recompression validation (2026-10-14)

Offline validation passed at source base `c083ec72a2170e6a9a0026f73e606c123c214ed1` with a four-file, uncommitted overlay copied from the Mac review worktree. No tracked production source was edited in this isolated checkout.

The run exercised 39 tests: four `test_native_profile_recompression.py` cases, 16 image-profile cases, 16 prepared-profile integrity cases, and three demo-selection cases. Pytest exited 0. Recompression tests compare actual native record streams from the real `fm1-state` codec before and after zlib compression, preserve selected demo order/startup selection, verify project and set behavior (including `dependency_scan_complete=false` for sets), refuse altered native records without leaving an output, and keep promotion flags false. Existing profile and selection rejection/integrity checks also passed.

Run environment: Hera, `lunar-recovery-pytest:20261011`, image ID `sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`; container `lunar-profile-recompression-20261014-a`; `--network none`, `--cgroup-parent=docker-batch.slice`, `--cpus=1`, `--memory=2048m`, `--memory-swap=2048m`. The source was mounted read-only. Reused codec binary SHA-256: `7a3cf4155c6642bd14fb69de25e2c1415b423ce9fa193006a3ef70f55d55fb77`. Its metadata reports all modules, engine API 4, mod API 2, GPL enabled, 44,118 Hz; embedded metadata commit is `0000000`, so that metadata alone is not source-revision provenance. The coordinator’s preceding validation identifies it as the exact-base codec build.

The complete pytest output is at `/home/claude/.local/share/codex-coordination/receipts/lunar-profile-recompression-validation-20261014/pytest.log`, SHA-256 `cc8e811ba7d6b89c1825de705bac41ff615f2bd79371952232af462071538cb8`. Pytest emitted one cache warning because its default cache directory was on the read-only source mount; it did not affect the passing assertions.

Overlay SHA-256 values:

- `tools/native/prepare_image_profile.py`: `d77bdf0e1ad599142c8670667817f25a2800eaa8c3ee70cc9616a5dc7b0d3149`
- `tools/native/prepare_demo_selection.py`: `e11c451fac2a40c3cfb6f097e446641ffc02fdac206b0f2ac655c241f36bbd1b`
- `tests/test_native_profile_recompression.py`: `44a0d2f71fd96f02e29d77369b10fc2070be1fab00528c512bbf738819d2a1f0`
- `tools/native/recompress_project.py`: `43b9513a863f93721fc94f02b8cf32e58409163abf141a1e207d8f0fff543337`

This validates the host preparation/recompression and integrity tests only. It does not establish sequence semantic preservation, firmware/module-link compatibility, native RAM fit, physical slot fit, installability, or hardware behavior. `sequence_semantics_verified`, `installable`, `native_link_verified`, `native_ram_verified`, and `hardware_tested` remain false. The new code/test files are overlays, not committed or GitHub-backed.
