# Optional target SDK checks in host-native pytest fixtures

Native project/save/workspace/content/sequence fixtures now separate their host checks from optional pi32v2 target compilation. Ordinary host CI still executes the host behavior; target-only checks skip only when `FM1_NATIVE_TOOLCHAIN` is absent. A configured path is used unchanged, so a missing compiler or invalid configured SDK fails instead of silently skipping. `test_native_content_embedding.py` now keeps host pack/embed checks unconditional and separately compiles the generated target catalogue across counts 0/1/2/4, text/binary inputs, and `-Os`/`-Oz`. `test_native_project_save_app.py` retains host SAVE checks and makes only its ABI compile target-dependent.

The target checks cover the production translation units formerly compiled incidentally during host fixture setup, plus the `lunar_project_units_t` target layout assertion. Helper contract tests verify absent SDK skip behavior and configured-but-missing path behavior. Linux/macOS host compile/link flags are in portability ancestor `4263126b`.

## Validation

Pinned Hera container `lunar-preload-tests@sha256:1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313`, 4 CPUs, 6 GiB memory/swap, no network, `/tmp` executable tmpfs. `FM1_STATE_TOOL` points to `/work/engines/build/fm1-state`. SDK-present checks mount the pinned local V1.2.13 toolchain read-only. Full host-suite runs also mount pytest dependencies and the existing PIO test library read-only.

- Historical SDK-absent full run before the two test expansions: 576 passed, 13 target-only skips, exit 0 (`sdk-absent-final.log`).
- After final changes, focused configured-SDK target checks: 30 passed, exit 0. This includes the 16 new content catalogue compiler combinations and the prior target compilation/layout cases. Earlier full SDK-present run failed two content-set target cases because the split had omitted `sim/web/src`; that include was restored. The earlier failure remains in `sdk-present-final.log` and is not considered a pass.
- Final expanded SDK-absent full suite is running in the bounded container; current receipt is `sdk-absent-expanded-final.log`. It has progressed beyond 17% without reported failures. The command initially run without the PIO library mount failed collection (`adafruit_pioasm` missing); that is an invocation setup error, not a code result. The corrected run mounts `/home/claude/mvave-fm1/midi-automation-20261011/pytest-lib` read-only.
- An earlier invocation without `FM1_STATE_TOOL` failed because state tests require the built executable; its receipt `sdk-absent.log` is not reported as a pass.

No target execution, device test, installation or physical acceptance is established by these host/cross-compile checks.
