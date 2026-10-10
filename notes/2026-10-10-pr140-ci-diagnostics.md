# Combined candidate CI diagnostics

This note preserves observed failures and limitations outside the candidate
branch. It does not authorize a merge, retry, changed acceptance threshold,
or device operation.

## Initial exact-head Pages result

[verified] PR [#140](https://github.com/ip2k/lunar-modulator/pull/140), head
`5d9fa46f2ae27f12d26c472813b1f4b0d3716b0c`, ran Pages
[38033498860, job 114159082740](https://github.com/ip2k/lunar-modulator/actions/runs/38033498860/job/114159082740).
The job concluded SUCCESS, with deployment skipped for the pull request.
The actual strict manual step reported:

```text
2026-10-10T07:13:56.7898116Z warning: warble (Warble) has no section in the manual; 06-effects.md lists it with its generated table only
2026-10-10T07:13:56.7906799Z warning: repeat (Repeat) has no section in the manual; 06-effects.md lists it with its generated table only
2026-10-10T07:13:56.7908386Z manual: 17 chapters, 42 engines and effects, sequencer in the build, 0 outline boxes; 0 errors, 2 warnings
```

[verified] This combined result is different from the earlier documentation
bundle's 40-entry, zero-warning manual receipt. The two missing usage
sections are a real documentation omission. The owner assigned their
correction to the documentation stream; the candidate remains unmerged.
A documentation correction requires a fresh exact-head CI result even
when engine and simulator source hashes remain unchanged.

[verified] After normal integration of the approved usage sections and
CI diagnostic changes, PR140 head `9a5fb72a54f5117169840f331fd1f756071e6fd5`
passed [Pages 38034115529, job 114160893087](https://github.com/ip2k/lunar-modulator/actions/runs/38034115529/job/114160893087).
Its actual strict manual log at 07:22:20.5392672 UTC reports 17 chapters,
42 engines and effects, 0 outline boxes, 0 errors and 0 warnings; the PDF
has 275 pages. The separate Actions Node20 deprecation warning remains an
environment warning. Full [CI 38034115528](https://github.com/ip2k/lunar-modulator/actions/runs/38034115528)
is still pending; Pages success alone does not authorize a merge.

## Observation and remaining gates

[verified] A read-only monitor records changes to PR140 checks and stops
if the exact head changes. It never reruns, cancels, or mutates a check.
Initial CI run: [38033498813](https://github.com/ip2k/lunar-modulator/actions/runs/38033498813).
At 07:14:25 UTC, Pages had succeeded, deployment was skipped, three checks
were running and ten were queued; no functional failure had been observed.
That snapshot is not a final CI acceptance.

The prior owner report that Sound 2 A crackled during a swap remains an
unresolved listening failure. Browser, native and offline parity receipts
do not establish a human listening pass or device readiness.

## PR132 pre-browser timeout

[verified] PR132 head `c6db9587c1d8d1ca6f993d8f433875761f3b2b6e`, CI
[38028605340, Chromium job 114144633913](https://github.com/ip2k/lunar-modulator/actions/runs/38028605340/job/114144633913),
was cancelled at its 45-minute job deadline. The Node helper command printed
9 passing tests, 0 failures and duration 73.156207 ms at 06:33:50.9782178 UTC.
The next log output was cancellation at 07:18:02.3731023 UTC. No browser
was launched. The same step completed in under one second for Firefox and
WebKit; the semantic reviewer also retained a passing bounded LAN receipt.

[verified] The step ran two commands. The second, editor-unit, discarded
stdout and printed its report only after its checks. The log cannot prove
whether the helper parent had exited or whether the second process stalled
in imports, Wasm compilation/initialization or later checks. Source review
found explicit final process exit and cleaned/unreferenced fixture timers;
no deterministic source cause was established. This is a lifecycle/module
test timeout, not an observed audio assertion failure.

[verified] Owner-approved CI-only correction on PR140 separates these
commands into named steps, gives each a five-minute timeout and retains the
editor-unit JSON output. No test content, assertion, automatic retry or audio
tolerance changed. The manual correction and this diagnostic change were
pushed together at `9a5fb72a54f5117169840f331fd1f756071e6fd5`. Engine and simulator
source hashes, and actual Wasm bytes, remained unchanged. Fresh exact-head
CI is required; this does not turn the cancelled PR132 job into a pass.

## PR134 old-sink WebKit failure

[verified] PR134 head `67cc933c10552f44f5f6707c89155be785848a9f`,
[run 38029909928, WebKit job 114148477223](https://github.com/ip2k/lunar-modulator/actions/runs/38029909928/job/114148477223),
failed the unchanged panel-follow latency gate: 32 frames, 519 ms for
`s2:2` / S2 Harmonics. Audio time stayed at 0.7198185941043084 from the
initial observation through frame 31 at 498 ms. During that interval the
editor was not loading, no changes were pending and no edits were inflight.
The changes message arrived at 511 ms; the value was correct at 515 ms.
The observer explicitly labels timing perturbation. This matches the
previous frozen-clock signature under the old default sink configuration;
it establishes delayed worklet delivery in this observation, not an
independent firmware or effect defect. The failed gate is preserved.

## PR141 Chromium storm failure

[verified] PR141 head `9ecd5ad2373ad0bd15106f31a44f50d68bc9c28e`,
[CI38034613510, Chromium job114162364372](https://github.com/ip2k/lunar-modulator/actions/runs/38034613510/job/114162364372),
failed its 30-second editor storm with one browser-reported underrun,
11.609 ms. The duration equals one 512-frame output buffer at 44,100 Hz
when rounded to three decimals. There were 7,262 edits, zero refused codes,
zero resyncs and 905 telemetry messages. The earlier external loopback
passed with zero silence, nonfinite samples or bad periods and eight A/B
swaps. Panel-follow passed at three frames / 32.1 ms; map 41/41 and editor
v1 99/99 passed. This is an audio counter failure, not a panel-follow or
pre-browser timeout. Zero-underrun acceptance remains unchanged.

[verified] Failure artifact `editor-page-test-output-chromium` (11663670965)
contains 33 one-second resource samples and a complete 86,962-event audio
trace with zero events dropped. Four CPUs were available. Visible cgroup
`cpu.max` was `max 100000`; throttled periods and microseconds remained
zero. CPU pressure `some avg10` peaked at 1.65% in the cgroup and 2.03%
system-wide. Total pressure increments were 153,992 and 171,199 microseconds
over the approximately 32-second capture. These samples do not establish
CPU saturation or quota throttling as the cause. Hidden ancestors and short
scheduling delays are not excluded by one-second observations.

[verified] The largest 128-frame render duration was 1.241 ms, below the
2.902 ms quantum; the largest destination wait was 5.757 ms. The largest
worklet render-start gap was 16.048 ms near the end of the trace. Captured
categories contain no explicit timestamp for the counted underrun, so these
gaps cannot be assigned as its cause. Tracing/resource sampling explicitly
perturb timing. The cause is unresolved; no rerun, tolerance change or
candidate mutation was performed. The bounded extracted receipt and hashes
of the original JSON artifacts are in
[data/pr141-9ecd5ad-chromium-failure.json](data/pr141-9ecd5ad-chromium-failure.json).
The full original artifact remains downloadable from the CI run.

## Opt-in startup, loop and drain counter diagnostic

[verified] Exact Chromium 153.0.8010.12 source limits publication of accumulated
playback statistics to once per second, on a successful audio-graph try-lock.
The getter transfers published statistics under the graph lock; it does not
force pending render statistics to publish. Getter values are cached within
a JavaScript task. Source: Chromium's
[audio_context.cc](https://raw.githubusercontent.com/chromium/chromium/153.0.8010.12/third_party/blink/renderer/modules/webaudio/audio_context.cc)
(`StatsUpdateRestrictor`, `HandlePreRenderTasks`, `TransferAudioFrameStatsTo`)
and [audio_playback_stats.cc](https://raw.githubusercontent.com/chromium/chromium/153.0.8010.12/third_party/blink/renderer/modules/webaudio/audio_playback_stats.cc).
[inferred] A pre-baseline glitch can therefore publish after the baseline.
That is a candidate mechanism, not proof of the original PR141 cause.

[verified] The diagnostic uses `FM1_STORM_PHASE_DIAGNOSTIC=storm|idle` with a
1–60 second bound. It traces before navigation/power-on and adds user-timing
markers for power-on, PLAY, the original baseline, loop beginning/end,
snapshot drain/end and trace finish. One-second raw samples retain cumulative
integer events, duration in seconds, total published duration, page/audio
clocks and unavailable/error states. Sample times describe publication
observations, not exact glitch times. Chromium getters take the graph lock;
these reads and tracing can perturb scheduling.

[verified] The baseline remains after PLAY/editor-port/subscription setup;
the final counter remains after the 1,500 ms snapshot drain. The complete
original pass expression, including zero browser underrun events, is retained.
Neither startup events nor drain events are subtracted. Idle runs the same
powered/playing page, telemetry, timers and snapshot drain without edit
messages; it is explicitly a control observation, not an acceptance run.
The default CI storm does not enable phase observation or earlier tracing.

[verified] The trace classifier counts exact named `SyncReader::Read timed out`,
`Glitch!`, FIFO pull/earmarked shortages and FIFO overruns separately and
retains phase markers. A zero FIFO occupancy counter is not treated as a
shortage: Chromium emits it after successful pulls too. Exact source:
[push_pull_fifo.cc](https://raw.githubusercontent.com/chromium/chromium/153.0.8010.12/third_party/blink/renderer/platform/audio/push_pull_fifo.cc).
Trace completeness, truncation and capped event extracts remain explicit;
absence of these events does not establish universal glitch observability.

[verified] Focused regressions cover delayed publication without erasing a
single baseline-delta event, missing/error counters, bounded samples, exact
phase-boundary assignment, empty-FIFO separation and final trace-batch drain.
This diagnostic changes simulator test inputs, so the committed build record's
simulator hash is not a fresh record for the diagnostic tree. It changes no
DSP/runtime source or Wasm bytes. PR141 and this probe use the same Wasm SHA256
`c88938845cd93e52f5cb99c53a650b4eaf559833e5f39fb58ecc0f0c4ab09502`.
The original failed CI is preserved and is not rerun. A bounded paired LAN
observation and root review remain pending; no production correction is implied.
