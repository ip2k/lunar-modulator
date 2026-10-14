# CI fixture portability repairs

This branch repairs six affected test files without changing production modules or frozen authority pins. The target was the Python/native test portability failures reported by CI run 38612995337 at `c79527a5`.

The test-only changes bind synthetic fixtures to the exact copied rehearsal source they exercise, while leaving production `REHEARSAL_SHA` values intact. The historical source-drift expectation was replaced by an assertion that the currently reviewed source set matches its pins; mutation tests still exercise fail-closed drift. The admitted-stock-restore test keeps the old policy pin and explicitly records that current policy bytes differ, so it does not silently reauthorize the newer source. The retained V1 proof test skips only when the private Hera evidence directory is absent; its local negative test still requires the verifier to reject a missing input. For macOS native startup compilation, the generated expected wavetable header now uses the same `__USER_LABEL_PREFIX__` stringify mechanism as `tools/native/prepare_wavetables.py`, instead of emitting an unprefixed asm alias.

## Verification

On Hera, the exact six-file selection collected 321 tests and completed successfully: 250 passed and 71 skipped. Skips were limited to private bench/backup/rehearsal/device38 evidence not mounted in the offline runner and the existing 13-case individual-engine matrix that requires the 8-voice Shapes profile. No failures or xfails were reported. The native startup tests ran on Hera/Linux; the prefix change specifically addresses Darwin symbol spelling and still needs the coordinator's Mac run.

The run used the pinned `lunar-recovery-pytest:20261011` image (`sha256:7e32dd6d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`), with 4 CPUs, 8 GiB memory and swap, 512 PID limit, no network, read-only root, and the project mounted read-only. Pytest dependencies were mounted from `/home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/lib/python3.12/site-packages`.

## Limits / next check

This is a focused Hera test result, not a rerun of GitHub Actions. The private evidence cases remain unexecuted here because their private inputs were not mounted. The macOS native linker failure is not directly reproducible on Hera/Linux; coordinator should run the exact branch on Mac and then dispatch fresh CI. No firmware, hardware, or installability claim is made.
