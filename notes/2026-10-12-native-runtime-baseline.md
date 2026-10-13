# SDK-free native runtime baseline

[verified] Hera (`claude@192.168.1.48`) built Dinghy revision
`d44df7db09b98ccad2f1233b8f83f5f09c04829e` using its upstream application-only
build. No loader build, firmware packaging or device installation was performed.
The application links without JieLi SDK archives. Its upstream checker reported
no errors: 55,076 image bytes; 12,368 data/BSS bytes; 30,720 pool bytes; 901
RAM-text instructions with no calls. These are Dinghy results, not Lunar results.
Do not reuse its loader/package: its SPL differs from Lunar's required stock SPL.

[verified] The pi32v2 arithmetic probe requires eleven runtime symbols, including
single/double precision arithmetic, integer conversion and signed 64-bit division.
Unmodified LLVM compiler-rt 21.1.0 sources at
`3623fe661ae35c6c80ac221f14d85be76aa870f1` supply these helpers. Their source,
license and SHA-256 inventory are under `firmware/third_party/compiler-rt/`.
The pinned license is Apache-2.0 WITH LLVM-exception. Generic `fp_mode.c` uses
round-to-nearest, ties-to-even and does not maintain floating-point exception flags.

[verified] Sixteen arithmetic translation units compiled in sixteen simultaneous
Hera containers. All exited zero, with no OOM. The integrated Makefile compiles
seventeen units including `fp_mode.c`, partially links the arithmetic probe, checks
source hashes and rejects any named undefined symbols. Its corrected run passed.
An initial checker falsely matched across the blank undefined table entry;
restricting whitespace to a single line corrected that checker. An earlier
parallel harness accidentally included macOS AppleDouble files; those were excluded
before the successful sixteen-source run. All task containers were inspected and
removed. Image: `lunar-jieli-check:bookworm`, SHA
`0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`.
Toolchain: existing Hera `sdk-v1213/toolchain/current`, clang 4.0.1, target pi32v2.
No SDK archive appears in the arithmetic link command.

Reproduce on a toolchain-equipped host:

```sh
make -C tools/native -j16 JIELI_TOOLCHAIN=/path/to/toolchain
```

[verified] Private receipts and symbols are in local
`build/native-baseline-20261012/` and Hera
`/home/claude/mvave-fm1/native-baseline-20261012/`. Vendor binaries remain ignored.
The semantic servers select the primary checkout rather than this worktree;
target ABI and code generation were checked with the real pi32v2 toolchain.

Limits and next work: this probe does not establish numerical accuracy on hardware,
realtime cost, full-engine helper coverage, libm/C++ support, panel operation, audio,
USB recovery or web installation. Integrate the engine core and open HAL next,
resolve the actual link's remaining dependencies, preserve stock package safeguards,
and validate the resulting application on the FM1.

[reported: owner] V8 diagnostic display was dark on both observations. A repeat
boot is requested. [verified: passive sysfs] USB remains 4c4a:8057 on bench01
port 1-1, bus 1/device 13. No fresh FM1 command was issued during this native
baseline work. Whether the owner physically cycled power is pending clarification;
do not execute the previously prepared restore packet after a power cycle.
