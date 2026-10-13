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

[verified] The integrated build now compiles 28 arithmetic units and resolves
all compiler-generated arithmetic references in the 160-object Lunar engine
partial link, including the selected GPL modules. Source hashes pass the pinned
inventory check. Sixteen parallel Hera engine compilation shards passed on
2026-10-12; no SDK archive was linked. This is compilation and linkage evidence,
not physical numerical or audio acceptance. Standard headers in that experiment
still came from the SDK checkout; independent headers remain necessary.
See `notes/2026-10-12-native-engine-link.md` and the earlier
`notes/2026-10-12-native-runtime-baseline.md`.
