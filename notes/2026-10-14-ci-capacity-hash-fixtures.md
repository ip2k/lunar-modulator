# CI fixture repairs: native capacity and rehearsal source hashes

At base `843b33c3bcfd6ffd8d8ce69947ad28aa9a4c0bd4`, two independent test assumptions made the focused CI suite order-sensitive.

`tests/test_native_project_capacity.py` consumed the shared `tools` simulator from `tests/test_sim_web.py`, whose compile flags come from ambient `FM1_SIM_EXTRA`. Capacity tests need the compact firmware writer and indexed TFT regardless of whichever simulator another test or CI job built. The file now builds its own session-scoped host app with those explicit flags, following the isolated SAVE-enabled fixture in `tests/test_native_project_save_app.py`. Both dense capacity/round-trip tests exercise that binary; production or shared simulator defaults are untouched.

`tests/test_sdk_rehearsal.py::test_each_dependency_hash_is_checked` injected one source mutation while retaining all historical pin values. The real `tools/jieli/audit_link.py` has changed since the rehearsal's pinned review hash, so this unrelated existing mismatch masked the selected mutation. The test now computes a local current-byte baseline for every dependency and injects exactly one changed dependency per case. Production `SOURCES` pins remain unchanged. A separate test asserts the real historical `audit_link.py` mismatch still fails closed, so this test repair does not bless or update stale review evidence.

Validation on Hera, exact worktree branch `codex/2026-10-14-ci-capacity-hash-fixtures`, in pinned image `lunar-preload-tests:20261014` (`sha256:1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313`), network disabled, docker-batch slice, 2 CPU, 3 GiB memory/equal swap, pids 256:

`python3 -m pytest -ra tests/test_native_project_capacity.py tests/test_sdk_rehearsal.py`

Result: **103 passed, 32 skipped**, exit 0. The skips are the existing private rehearsal-fixture cases unavailable in this test environment. No device access or hardware operation occurred. This validates host fixture behavior and simulated fail-closed policy only; private physical campaign acceptance is not tested. The unmodified stale pin requires coordinator re-review of the actual dependency before any real rehearsal can pass `check_sources()`.
