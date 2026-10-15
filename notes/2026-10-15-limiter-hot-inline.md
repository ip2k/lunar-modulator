# Limiter tiny-helper inline trial

[verified: source review] `Abs`, `Guard`, and `Aim` now receive `always_inline` only for the opt-in `FM1_HOT_DSP_RAM` profile on GCC/Clang. Default builds retain ordinary inline behavior. Arithmetic expressions, order and state transitions are unchanged. The host differential candidate uses a separate object define to exercise the attribute without applying an ELF RAM section to Mach-O.

[verified: host tests] The worker reports O0, O2 and UBSan runs passing 112 scenarios each with bitwise-equal audio and complete instance state. The coordinator independently reran the focused pytest successfully and checked the diff. Negative-zero input joins NaN, infinity, out-of-range samples, mode/lookahead changes and stereo cases. The separately compiled reference uses the same production source with this and prior limiter optimizations disabled; it is not an independent algorithm implementation.

[verified: limits] No target fit, code generation or physical timing result exists for this trial yet. Forced inlining can grow the render body. Review app size, RAM section and generated calls before hardware use. SAVE remains disarmed; the goal and failed cold-boot performance acceptance remain open.
