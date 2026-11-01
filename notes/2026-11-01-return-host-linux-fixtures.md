# Return-only host Linux fixture correction — 2026-11-01

[verified] PR169 Linux job 41348455625 reported 71 failures, 7368 passes and 135 skips. All 71 failures belong to `tests/test_rom_return_once.py`. The module used pytest's `tmp_path` under `/tmp`; the unchanged production directory walker correctly rejects that world-writable ancestor. Tests depending on reaching later protocol, persistence and fault phases consequently failed before their intended assertions.

[verified] This test-only correction adds a function-scoped `private_tmp_path` fixture using standard-library `TemporaryDirectory` beneath the actual project's `ROOT/scratch`. It cleans each test's invented inputs and spent campaign records on exit. Both the main inputs and the deliberately modified synthetic source tree use it. The checkout and its ancestors must still satisfy the real production ownership/write policy. The fixture does not change permissions on shared directories or replace the production filesystem guard.

[verified] Existing test cases and assertions are unchanged: explicit writable ancestors (0720, 0702 and 1777), foreign ownership, final symlink/FIFO refusal, the four causal ancestor-swap injections, retained-directory descriptor cleanup, persistence faults, concurrent/crashed processes and actual signal interruption remain exercised. No skip, production mock, trusted-pin override change or host source change was introduced. Production's reviewed-image pin remains UNSET.

## Checks and causal proof

[verified] The exact 7847dcdf932a2ad6e3aa21a7071a94279e59bf9b selected source bundle plus the original test module reproduced **71 failed, 36 passed** on Aeon Linux (Python 3.14.4, pytest 9.1.1). Its failed-node set exactly equals the saved CI log's 71 nodes. Replacing only the test module produced **107 passed in 1.12s**, with pytest's own `--basetemp` still deliberately under `/tmp`. All fixture directories were removed at test teardown. The corrected module also passed **107 tests in 1.31s** on macOS.

The Linux runner used one CPU (`taskset -c 0`), 1 GiB virtual-memory limit, 30 CPU seconds, a 45-second outer timeout and matching `FM1_TEST_CPU_SECONDS=30`. Pytest was installed cache-disabled into a disposable owned venv at the currently used project version, 9.1.1; transitive versions were recorded. No other project requirements were installed.

[verified] Linux source/venv/fixtures were staged only under the new private `/home/claude/lunar-tests-return-host-linux-fixtures-20261101`, with each ancestor checked. The initially proposed dataset and `.local/share` paths had writable ancestors and were not used for valid fixture input. One initial extracted-stage run inherited group-writable directory modes; a second runner setup used an incompatible child CPU limit. Both failed runs are retained and identified separately. Corrected runs made only their newly created isolated source directories private and aligned the existing subprocess guard's configured CPU limit. No shared directory permissions were changed.

Small logs, exact source hashes, dependency versions, complete CI failure list and RED/GREEN commands are retained privately in `audit-20261101/rom-return-host-linux-fixtures` under the performance worktree. Reproducible source bundle, venv and test directories are removed after evidence retention; the feature worktree remains until integration. The Aeon coordination claim is released only after its durable handoff is saved.

## Semantic tooling and limits

Rarefaction status reports the primary checkout's Python/Pyright profile ready; external absolute worktree orient/scope requests are rejected by its workspace boundary. Serena's current configuration is the primary Lunar checkout; exact absolute-path `find_symbol` recovered this worktree's `inputs` fixture and matched direct source. No shared project activation or restart occurred. Exact Git/source inspection and the two host operating-system runs establish this fixture correction. These are synthetic fake-serial tests; no real serial connection, device, service, container, native build or hardware acceptance occurred. Independent review and required CI remain integration gates.
