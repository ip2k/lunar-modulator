# Opt-in stage-1 resampler RAM placement

The opt-in `FM1_HOT_DSP_RAM` ELF profile now places the trusted stage-1 FIR helper `fm1_resampler_intermediate_` in `.ram_dsp`, alongside the existing ready-pop path. This addresses the remaining XIP call path identified in the exact `20f9ae8f` ELF. The normal profile and non-ELF builds keep the helper's existing placement. No FIR arithmetic, coefficient data, sample rate, or public API changed.

The helper remains `static inline` and is only outlined with `noinline, section(".ram_dsp")` when it is referenced. No `used` attribute was added, so including the header without using the helper does not retain an extra RAM copy.

Focused checks:

```text
.venv/bin/python -m pytest -q -o addopts= \
  tests/test_resampler_stage1_placement.py \
  tests/test_engines_resampler_ready_path.py \
  tests/test_resampler_table_placement.py
7 passed
```

The new ELF32 test compiles an active caller with Clang and verifies the emitted helper section with the repository ELF parser. It also compiles an unused translation unit with the hot-DSP define under `-Wall -Wextra -Werror`, and checks default ELF placement remains outside `.ram_dsp`. The existing ready-path differential test verifies the checked and trusted APIs still match bit-for-bit in default and hot-DSP host builds.

A fresh exact-source Hera link remains required to verify the five target LTO copies, their caller targets, `.ram_dsp` extent against `0x01c06000`, flat app budget, startup copy, and PC guard. Placement alone does not demonstrate a realtime or audio improvement. No device was accessed.
