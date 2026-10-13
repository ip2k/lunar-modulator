# LLVM compiler-rt builtins

[verified] Unmodified portable arithmetic sources from LLVM 21.1.0, commit
`3623fe661ae35c6c80ac221f14d85be76aa870f1`, at
https://github.com/llvm/llvm-project/tree/3623fe661ae35c6c80ac221f14d85be76aa870f1/compiler-rt/lib/builtins.
The license is Apache-2.0 WITH LLVM-exception; retain `LICENSE.TXT` and
individual source notices. `inventory.json` records SHA-256 for each file.

Purpose: replace compiler-generated arithmetic calls without linking JieLi SDK
archives. No modifications, architecture assembly, sanitizer runtime or SDK
code are included. The generic `fp_mode.c` selects round-to-nearest, ties-to-even;
it does not maintain floating-point exception flags.

[verified] Sixteen arithmetic sources compiled in sixteen Hera containers using
the pi32v2 toolchain on 2026-10-12. The integrated build adds `fp_mode.c` and resolves all of the probe's
compiler-generated helper references with no named undefined symbols. This is compilation
and linkage evidence, not physical numerical or audio acceptance. See
`notes/2026-10-12-native-runtime-baseline.md`.
