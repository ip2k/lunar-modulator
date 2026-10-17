# Offline audio resampler bottleneck study

Scope: read-only trace on base `6457d01ce823abd5eacc3862109d80e5f2712202`.
No firmware changes, target builds, Hera, device access, or new timing claims.

## Source schedule and work

Both native engines generate at 47,872.34 Hz and resample to the FM-1's
44,118 Hz output. For each 64-frame host block, that rate ratio requires about
69.45 input frames (phase and startup alter exact per-block counts). Drums
renders input in 12-frame `RenderBlock()` chunks, about six calls per output
block; SixOp uses 16-frame chunks, about five. Each output frame recomputes
`fm1_resampler_needed()`, pulls any required input through `push_ready_()`, then
calls `pop_ready_()` (`engines/src/drums.cc:511-532`,
`engines/src/mi_sixop.cc:338-359`). `needed()` is constant-size fixed-point
arithmetic (`fm1_resampler.h:341-347`); push updates duplicated-ring slots,
nonzero counts and relative phase per input (`:352-367`).

For a converted output, ready-pop either takes the empty-history shortcut or
generates exactly two intermediate samples, updates the 123-cell intermediate
ring, and if that ring has any nonzero values applies the symmetric low-pass
(`fm1_resampler.h:420-465`). At this rate the stage-1 table advances about 236
entries per input sample through a 768-entry half-kernel: roughly 3-4 taps on
each side per intermediate, with exact count dependent on phase. That is
roughly 12-16 stage-1 products per output, plus phase/ring work. The stage-2
low-pass executes 61 symmetric-pair products and one center product for every
output while `mid_nonzero != 0`. Thus stage-2 decimation is the strongest
source-level candidate for dominant active-audio resampler work; this operation
count is not a target timing measurement. The previous inlining experiment
removed two stage-1 calls but retained this 61-pair loop.

The zero-history path (`in_nonzero == 0 && mid_nonzero == 0`) advances phase
and writes two zeros without either FIR. A nonzero input history with exhausted
tail, or a mid-ring tail after input becomes zero, follows different paths.
Idle-only samples can therefore make average pop cost look much smaller than
active notes. A diagnostic must count these path classes, not interpret idle
time as active-note cost.

## Existing measurement boundaries and limitations

Schema 7 times only whole Drums/SixOp `Render()` and nested `RenderBlock()`;
the subtraction combines readiness, render-loop control, push, pop, output
copy, timing hooks and asynchronous interruptions. The reported outer-minus-
nested shares (82.4% Drums, 87.3% SixOp) cannot distinguish those components
(`notes/2026-10-15-engine-render-profile-results.md:41-50`). Its clock is
`fm1_ticks()` / TIMER4, documented as a 24 MHz oscillator timebase, not CPU
cycles or a calibrated core-frequency measurement
(`firmware/native/app_probe.c:65-75`,
`notes/2026-10-15-native-clock-frequency-review.md:24-31`).

Schema 7 does not coexist with IRQ-profile or producer-gap instrumentation;
`firmware/native/app_probe.c:21-27` rejects those combinations. Render timing
therefore includes any preempting interrupt in its elapsed ticks and cannot
subtract the interrupt union. Existing IRQ profiling tracks inclusive handler
durations and a nested busy-time union, but enabling it requires a distinct
profile/cadence. Timer reads and per-stage bookkeeping also perturb the path.

The matched Aeon candidate fit proves the relevant linked calls and RAM section
budget at that candidate: ready-pop is in `.ram_dsp`, no separate intermediate
symbol remains, `.ram_dsp` is 15,700 bytes with 7,528 bytes reported slack.
It does not prove all callees/tables are RAM-resident or runtime speed. The
receipt explicitly leaves full RAM residency, physical stack high-water and
runtime performance unverified (`notes/2026-10-16-resampler-inline-fullfit-handoff.md:125-156`).
Header blob at adopted commit `393acb1c` matches the Aeon candidate's header;
current HEAD after that commit changes documentation only.

## Concrete next change proposal

Add an opt-in schema-9 diagnostic stage breakdown in the existing
`engine_render_profile` path, and keep normal builds compiled out. Accumulate
raw TIMER4 ticks and call/sample counts separately for (1) needed/loop control,
(2) input push, (3) the two stage-1 intermediate calculations, and (4) stage-2
low-pass; also count empty-history, active-stage-1, and low-pass executions.
Retain current whole-Render and RenderBlock totals for a cross-check. Prefer
sampling a bounded fraction of output frames or measuring a controlled grouped
window to limit per-sample timer overhead; expose sampled counts so averages
are interpretable. A schema-9 profile should pair or integrate the IRQ busy
union rather than silently treating wall-tick elapsed as CPU work. The current
schema-7/IRQ exclusion must be updated deliberately, including builder and
receipt validation, and telemetry packet capacity/cadence must be checked.

Before using it, compare instrumented and profiling-disabled aggregate render
elapsed/underrun rates on the same diagnostic workload to bound profiler
overhead. Report raw TIMER4 ticks only; do not convert to CPU cycles. No code
change or build is made by this note.

Confidence: source-level operation schedule and existing profile boundaries
are high confidence; stage-2 dominance is a workload-dependent hypothesis
based on arithmetic counts. Exact target path costs, interrupt share, active
versus tail frequencies, audio causality and perceptual acceptance remain
unproven. Next dependency is a reviewed schema-9-only code change and fresh
current-profile target fit/codegen before any owner-controlled hardware test.
