# Explicit `fabsf` fast paths

This experiment replaces the per-sample `fabsf` calls in the mix limiter and
browser postmix helper with `__builtin_fabsf` when compiled by GCC or Clang.
Other compilers keep the standard `fabsf` fallback. It does not change the
limiter guard, math ordering, envelope state transitions, or sample writes.

## Evidence

The exact pi32v2 compiler probe retained at
`/home/claude/mvave-fm1/combined-dsp-profile-20261015/fabs-codegen-probe`
was compiled with the target toolchain and production floating-point flags.
With `-fno-builtin-fabsf`, ordinary `fabsf` remains a call. Explicit
`__builtin_fabsf` lowers to `r0 &= 2147483647; rts`. Probe source SHA256 is
`7f7babcb23ee4446914c1df308a85267eb5acc8a401dc7ffb6d43f2a1366a608`,
assembly SHA256 `e9fbea5f07ed4d98ab1ce47782e3c8ced75c42bd9f2efc0f08a0e4245c43d561`,
and target object disassembly SHA256
`b22fd3d2ac0b53ebb24dcbb988214130d0273314aeee523f38eadccfcb619a21`.

Native equivalence harnesses compare optimized output with retained standard
library reference loops. The limiter test compares every processed float byte
and the complete envelope/release/ceiling state after each chunk across 4,608
cases, including signed zero, NaNs, infinities, subnormals, clamp values, and
randomized inputs. The postmix suite continues to compare output, scope, index,
and peak state.

Command:

```sh
/home/claude/.cache/lunar-host-set-fixtures-venv/bin/pytest -q \
  tests/test_native_mix_limiter_equivalence.py \
  tests/test_native_postmix_equivalence.py
```

Result on Hera: 4 passed, 2 UBSan cases skipped. The installed GCC has no
linkable UBSan runtime (`libubsan.so.1.0.0` is absent), so the `-O0` and `-O2`
checks ran, but this host could not run sanitizer builds. `git diff --check`
passed.

## Integrated build and coordinator checks

[verified] Coordinator integrated the change as `0e02422f6c0fd3aa55bdc7fc50625007bfd8822a` and verified the origin branch SHA. Both equivalence modules passed on the Mac: six tests, including both UBSan variants. Hera's missing sanitizer runtime is therefore a host limitation, with sanitizer coverage supplied separately.

[verified] A fresh full target build used exact source `0e02422f`, tree `57a19bda2f7c4e396136531c4e7694f0ff2d1a67`. All sixteen catalogue shards and the link passed. The app is 854,104 bytes against an 860,644-byte budget, leaving 6,540 bytes. The matched profile retains all thirteen engines, Event Horizon plus companion SET120, schema-7 engine counters, stage/clock counters, disabled autoplay and SAVE, Hall/SixOp at `-Os`, other modules at `-Oz`, LTO and selected DSP in RAM. This is a timed diagnostic, not release firmware.

[verified] Coordinator fetched the private compact archive and verified its external pins, exact byte count, all 26 unique bounded regular members and every member digest before extraction. Archive SHA-256: `0deb0df670ecf2d261996f3b1d7725a7f547e3ffd0511bfae00add641351b028`; pins SHA-256: `2bef13ea928b3ee2bf69238fbcfb862cd125bf7120c803f01bd4051858378fb4`; raw receipt SHA-256: `e9c827c58e57d0a5e748a6ef23cb5c9682bda0fb14041407e5075623f9846a1b`. App SHA-256: `8e511ed0704b3767144d1b780d2ee8f23bd223d9e7fc8727b7e0e480c92464aa`; ELF SHA-256: `33c8a570f97188a40419df34b560eee256977c1c3070550af634fbe9d9a00345`.

[verified] Coordinator independently delimited both functions in the prior combined-profile and new disassemblies: limiter `fabsf` call sites fell from two to zero, and postmix from four to zero. These are static call-site counts, not dynamic invocation counts or physical speed evidence. The worker also reports inline sign masking.

## Limits and next step

No device installation or hardware performance acceptance for this build yet. A separate schema-7 baseline diagnostic is prepared for a fresh guarded backup/install/readback and passive capture. Preserve its distinct source identity when comparing later fabs timing. Musical acceptance remains failed and SAVE stays disarmed.
