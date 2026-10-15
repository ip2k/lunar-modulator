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

## Limits and next step

This establishes host bitwise equivalence and target code-generation for the
primitive, not a full target link or an audio-performance gain. Full target
build is intentionally pending coordinator review. No device, flash, or
hardware acceptance was involved.
