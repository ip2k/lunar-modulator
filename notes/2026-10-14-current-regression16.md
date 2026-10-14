# Current native/install/save/recovery regression (16-way)

Date: 2026-10-14. This is an offline source regression receipt, not device or release acceptance.

## Exact-base run

[verified] Source was clean commit `43a5a8d77721e58011a00cec782cb64df73a9f86` in `/home/claude/.local/share/codex-worktrees/lunar-current-regression16`; 100 selected test files collected to 2,762 node IDs. `shards/manifest.json` records the exact node-ID and per-shard SHA-256 values. The 16 shard node-ID lists were disjoint and covered the collected set: shards 00–09 had 173 IDs each; 10–15 had 172 each. The intentionally long parameter ID in shard 14 is one test ID, not duplicate coverage.

[verified] The run used pinned image `sha256:1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313`, pytest 9.1.1 from the read-only `usb-cdc-status-replay-20261014` venv mount, and the pi32v2 SDK toolchain mounted read-only at `/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1`. Each container used network none, one CPU, 2 GiB memory/equal swap, 256 pids, `docker-batch.slice`, and a unique `codex.task` label. `FM1_STATE_TOOL` was the clean-archive host utility with SHA-256 `17f377d9966aac0efab705e6a10b900cb8d47dfebdbea8650bf00793b10bceb2`; generated scratch copies were freshly created from the exact source archive and did not reuse stale engine objects.

[verified] All 2,762 selected IDs reached pytest completion: 2,593 passed, 107 skipped, 18 failed, and 44 errored. Logs are retained at `/home/claude/mvave-fm1/native-current-regression-16-20261014/evidence/shard-00.log` through `shard-15.log`; the manifest is at `.../shards/manifest.json` (SHA-256 `4aa2e12fa19924926aee2d2abbf69a12e6452ab34302d3b2f3103a2aa922d3af9`). The full admitted 16-way run is not green.

[verified] Failure classification is concrete:

- Sixteen `test_target_compiled_content` failures exercised the old assertion that the linked catalogue uses `16 * max(1, count)` bytes. The actual pi32v2 link emitted 20 bytes per catalogue entry: for example count 2 yielded 40 bytes against the old expected 32. The corrected expectation was later committed by the coordinator at `968b5f5e` and included in the focused follow-up below.
- Two preload-catalogue tests failed because Git rejected the scratch path `/src` as dubious ownership. This was test-container Git configuration, not a source assertion. Re-running those exact tests with only `safe.directory=/src` passed 2/2; log: `/home/claude/mvave-fm1/native-current-regression-16-20261014/evidence/safe-directory-rerun/preload-confirmed.log` (SHA-256 `99db33d5c94c6f7da021687c7391181685cc33299c5435b1c861e2db3be3ec87`).
- All 44 setup errors were linker failures for missing `lunar_content_load_set_checked` in the test fixtures explicit source list. They affected compressed single-engine/full-app startup, demo app startup, full-song sequence and scene-label adaptation selectors. The coordinator added `content_set.c` to the compressed fixture at commit `f25d96d6`; the remaining fixture repairs were subsequently integrated at `dab9daae`. The 43a5 run therefore records the baseline failures, not current green status.

## Focused follow-up on corrected source

[verified] On a fresh isolated checkout at f25d96d6fa83810fe016db12e9eb8a09f1f2a958, the selected 16 target-compiled catalogue cases and three compressed-startup cases completed with exit code 0. Pytest reported 33 passed and 13 skipped. The 13 skips are the individual-engine cases under the 12-voice profile; the equivalent 8-voice individual-engine cases ran. The three startup cases covered the 8-voice single-engine path, full Event Horizon with a 165,376-byte arena, and Satellite Hearts. Receipt log: /home/claude/mvave-fm1/native-current-regression-16-20261014/evidence/f25d-focused/pytest.log (SHA-256 3a714632f8fb6a7252224b15be9a2beb3179858d55bf76c6b7de458492c60ec7); exit-code.txt contains 0. This follow-up did not rerun sibling-owned arenas, uncompressed startup, sequence, or scene-label fixtures.

## Scope and next dependency

[verified] These runs were offline host/native tests only. They do not establish full suite success, device startup, physical playback, flash/install safety, or release admission. The 43a5 baseline still has outstanding fixture-source errors outside the compressed fixture and requires a fresh integrated-head CI run after all fixture repairs land. The coordinator should combine the separate fixture repairs, run current-head CI, and report the complete unfiltered result.

## Reproduction evidence

[verified] The full run manifest and shard receipts are in /home/claude/mvave-fm1/native-current-regression-16-20261014/evidence. The corrected focused follow-up used the exact f25d source in a separate clean checkout and a fresh bounded container with the same pinned image and read-only SDK mount. The original omitted-toolchain attempt is kept separately under evidence-invalid-omitted-toolchain and is excluded from all counts.
