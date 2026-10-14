# Native host-test portability

This change gives the focused native C/C++ test fixtures a small platform-aware flag helper. Linux retains the GNU linker section collection and non-PIE sanitizer settings; macOS uses Apple's `-dead_strip` and omits unsupported `-no-pie`, while retaining sanitizer instrumentation. Unsupported host platforms fail explicitly. This keeps test coverage while avoiding Darwin linker/Clang argument errors.

## Validation

On Hera, the focused set ran inside pinned `lunar-preload-tests:20261014` with 4 CPUs, 6 GiB memory and swap, network disabled, executable 3 GiB `/tmp`, read-only JieLi toolchain and pytest dependency mounts. The platform-flag/state/MIDI subset passed 125 tests. The full owned set (the helper test plus ten native test files) also reached 100% with no displayed failures after building the exact worktree's `engines/build/fm1-state` and setting `FM1_NATIVE_TOOLCHAIN=/toolchain`, `FM1_STATE_TOOL=/work/engines/build/fm1-state`, and `PYTHONPATH=/pytest-deps`. The interactive container output did not preserve pytest's trailing count/exit summary, so this records a clean completed progress output, not a durable numeric receipt. Mac CI has not been rerun; the actual Apple toolchain remains the acceptance check.

## Historical receipt correction

The older `lunar--compressed-native-startup-final2.log` is not a clean full-matrix pass. Its `shapes8-dx7` and `shapes8-macro` cases fail the test assertion that exactly one active unit is present; observed active-unit counts were 2 and 3. Those failures are assertion/expectation mismatches, not allocator failures. The older handoff's “passed” wording overstates that receipt. The exact invocation environment for that historical run could not be recovered. The receipt itself is unchanged.
