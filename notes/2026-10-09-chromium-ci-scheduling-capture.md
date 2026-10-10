# Chromium CI scheduling capture, 2026-10-09

Scope: offline simulator/CI diagnostics only. No hardware traffic.
This stream depends on [PR #111](https://github.com/ip2k/lunar-modulator/pull/111)
(the seconds-to-milliseconds correction and the controlled scheduling probe),
branched from its main-merge checkpoint `2988bcf`.

## Evidence and remaining question

[verified] PR #105's Chromium job
[113995848002 / run 37982383272](https://github.com/ip2k/lunar-modulator/actions/runs/37982383272/job/113995848002)
reported two integer underrun events, 20 ms total after the unit correction,
zero rejected edits, zero resyncs, and all functional checks passing. Its
worklet had no timing clock (`timed:false`). The existing logs contain neither
CPU pressure counters nor audio-service traces. The source investigation and
bounded pressure experiment are in
[the PR #111 note](2026-10-09-chromium-storm-underruns.md).

[inferred] CPU contention is a plausible cause, but that experiment does not
establish the cause of the original GitHub failures. Dedicated CI resources
would need evidence of pressure during actual failures and a controlled
comparison with headroom on the same workload. No retries, thresholds, or
changes to zero-underrun acceptance are introduced here.

## Capture contract

[verified: source] CI sets `FM1_SCHEDULING_CAPTURE=1` for the existing storm in
all three browser jobs. Manual runs retain their existing uninstrumented
behavior unless opted in. `editor.json` marks the opt-in explicitly.

- `editor-scheduling.json` keeps initial, approximately one-second, and final
  snapshots with UTC and Node monotonic timestamps. Raw cgroup v2 `cpu.max`,
  `cpu.stat`, `cpu.pressure`, host `/proc/pressure/cpu`, CPU lines from
  `/proc/stat` (including steal), load average, affinity, logical CPU count,
  and the process's cgroup/mount context preserve units and provenance.
  Unavailable files carry an explicit error rather than an invented zero.
  The mounted cgroup may represent an ancestor; inspect its context before
  assigning the counters to the browser. `/proc` CPU/pressure counters may
  cover the host rather than only the container. Cgroup v1 CPU counters are
  not translated by this helper and will be reported unavailable.
- Chromium additionally writes `editor-audio-trace.json`, a browser-wide CDP
  trace using `audio,webaudio,disabled-by-default-audio`. A page-only CDP
  session would omit the out-of-process audio service. Trace markers bracket
  `page.evaluate`, including the existing 1.5-second snapshot drain; the
  playback counter window is narrower. The final trace batch is drained
  before writing. A 200,000-event cap and a 10-second completion timeout are
  explicitly reported as truncation/incompleteness; neither changes the
  independent playback counters used for acceptance.
- Initial and periodic resource files are persisted while the storm runs.
  A storm exception also writes a failed editor report and finalizes the
  trace before closing the browser. Missing/failed CDP yields partial
  artifacts with diagnostic errors. Forced process/job termination can
  prevent final trace delivery; initial resource evidence may still remain.

[verified: workflow] The existing `failure()` artifact upload includes these
files in `page-test-output/<browser>` for 14 days. They are written on passing
instrumented runs too, but CI uploads only failed jobs. The storm workload,
its playback counters, and its pass expression are unchanged.

**Perturbation:** CDP tracing, trace delivery, periodic reads and JSON writes
can affect scheduling. Each capture identifies this explicitly. It measures
an instrumented run and cannot retrospectively explain an untraced failure.
Compare markers and playback windows before comparing counts. A
`SyncReader::Read timed out` event supports the missing-buffer mechanism;
pressure deltas support correlation, not automatic proof of causation.

## Validation

[verified] Five Node regressions cover unavailable files, preservation of raw
counter units, browser-wide CDP use/final-batch delivery, bounded truncation,
incomplete drain, unsupported CDP, and resource-only capture for other browsers. The existing 35 editor unit checks
also pass. `git diff --check` passes.

[verified] LAN validation uses the pinned Playwright 1.63.0 image, Chromium
153.0.8010.12, network disabled, the existing batch slice, 2 GiB memory cap,
and isolated test output. A 4-CPU, 30-second instrumented Lunar storm passed
with zero playback events and zero `SyncReader` timeouts. Its trace completed
without truncation/errors: 81,318 events, 14,577,426 bytes, and 33 resource
samples. This checks collection under the actual Lunar workload; it is not
GitHub CI evidence.

[verified] A separate controlled eight-second Lunar storm, with one CPU of
quota and two busy Node workers in the same container, exited 1 under the
unchanged acceptance expression. It reported 246 playback events / 2,460 ms,
zero rejected edits/resyncs, and a valid snapshot. Its complete trace had
22,193 events and 259 `SyncReader` timeouts; all 95 observed quota periods
were throttled (`throttled_usec` delta 22,831,570, an aggregate counter rather
than wall duration). The 11 resource samples and both artifacts survived the
failure, with no capture errors or truncation. Trace and API counts have
different windows/delivery paths and are not asserted to match exactly.

The compact [recorded validation summary](data/2026-10-09-chromium-storm-capture.json)
keeps editor reports, raw first/last resource snapshots, markers and counts.
Full raw artifacts remain in the isolated LAN stage
`/home/claude/mvave-fm1/chromium-tracing-20261009/{baseline,pressure}` on aeon;
large traces are not committed. The pressure harness is an offline validation
fixture in that stage, not part of CI. No GitHub failure has yet been
observed with this instrumentation.

## Integration checkpoint, 2026-10-09

[verified: source] Updated this branch against `main` at
`28697823de827cf989f2673a452dec43060f1917`, after PR #111 merged. The workflow
conflict is resolved by running both panel-follow and scheduling-capture
regressions, retaining the editor unit checks, external audio detector and
browser loopback step, and the isolated Pulse sink/monitor configuration.
The existing storm acceptance expression and browser matrix are unchanged.

[verified: local] The combined nine Node regressions, all 35 editor unit
checks, audio detector fixtures, and `git diff --check` pass. Browser loopback
and the instrumented storm await CI at this updated head; the prior green
head does not verify this integration. Serena/Rarefaction remain connected
to their earlier selected roots, so direct source/diff inspection establishes
this branch's workflow composition; no shared server was restarted or activated.
