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
