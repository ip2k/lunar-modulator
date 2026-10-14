# Combined companion SET regression validation

[verified: exact Hera source and test run] The combined coordinator source at
`071cf726c71d80f4416e805a87f6108380323b8c` passed the four-file companion SET
regression suite. From a fresh native build, pytest ran 104 cases: 86 passed
and 18 skipped. The skips are the expected pi32v2-only compile checks because
`FM1_NATIVE_TOOLCHAIN` was not mounted; the test helper explicitly skips only
when that environment variable is absent.

The exact source checkout was `/home/claude/worktrees/set-combined-regression-validation`, branch
`codex/2026-10-14-set-combined-regression-validation`. Test source SHA-256 values
are retained at
`/home/claude/.local/share/codex-coordination/receipts/lunar-set-combined-regression-20261014/test-hashes.txt`.
The test log is `.../receipts/lunar-set-combined-regression-20261014/run.log`
(SHA-256 `2f66c96550cbbaf8e8cc0c3e28267aae4121f5b6c376021fef85e17d2e7d2d32`);
source commit is in `source-commit.txt`. No repository files other than this
note were changed.

The Hera run used the pinned `lunar-recovery-pytest` image, image ID
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`
(linux/amd64), no network, a read-only source mount, four CPUs, 8 GiB memory
and swap, 512 pids, and `docker-batch.slice`. It mounted the existing pytest
dependencies read-only and built a fresh state tool from this exact checkout:

```sh
make -C engines BUILD=/tmp/state FM1_GPL_MODS=1 -j4 /tmp/state/fm1-state
FM1_STATE_TOOL=/tmp/state/fm1-state python3 -m pytest -q -ra -p no:cacheprovider \
  --basetemp=/tmp/lunar-pytest \
  tests/test_companion_selection.py \
  tests/test_native_content_embedding.py \
  tests/test_native_preload_selector.py \
  tests/test_native_project_sequences.py
```

The first test output line represented 72 cases (54 passed, 18 skipped) at
69%; the final line completed the remaining 32, for 86 passed and 18 skipped
total. The state-tool build emitted existing compiler warnings but
completed and the requested binary linked. This is host/mock regression
coverage; the skipped target-only compiler checks, native link/runtime and
hardware acceptance are not covered by this run.

## Portability finding

The Mac failure caused by an absent `FM1_STATE_TOOL` is an environment setup
failure: the suite expects that executable and the Hera run built it freshly.
The Darwin linker failure is a separate test portability issue, not an
intentional Linux-only test boundary. In
`tests/test_native_project_sequences.py`, the host probe links with literal
`-Wl,--gc-sections` rather than using the shared `native_host_flags()` helper;
`tests/native_test_flags.py` already selects `-Wl,-dead_strip` on Darwin.
Therefore that host test is not portable as written. This task was validation
only, so no test/code change was made. Target compile checks are explicitly
optional when no target compiler is configured and were correctly reported as
skipped on Hera.

No device, USB, MIDI, flash, power or reboot operations were performed. The
Mac attempt is not counted as a passing run, and this result is not full CI.
