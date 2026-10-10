# Resampler measurement CLI bounds — 2026-10-09

Audit batch 122 found three developer-tool defects: negative `--outputs`
became a huge unsigned allocation; an overflowing peak-window sum could
hang the power-of-two loop; and `--from -inf` could hang a frequency sweep.
The audio resampler itself is unaffected by this change.

The CLI now parses unsigned frame counts strictly, rejects non-finite
numeric inputs, checks benchmark counts against the process API's uint32
lengths before floating conversion/allocation, computes available WAV
samples by subtraction, and bounds FFT doubling by division. Sweep steps
must advance the current frequency. The same safe window clamp covers the
related `tones` mode [verified: source and focused regression tests].

Validation: 14 focused pytest cases pass in a CPU/memory-limited Debian
container on aeon, including the original malformed invocations, a valid
SIZE_MAX window on a short WAV, and a normal benchmark. `git diff --check`
passes. Rarefaction orientation used the original checkout with fallback
clangd flags; Serena found Peaks in the audit-tool worktree before edits.
No device traffic, firmware packaging, or DSP behavior change.
