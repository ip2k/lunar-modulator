# Chromium storm underruns, 2026-10-09

The failing browser reports describe **10 ms and 20 ms**, not 0.01 ms and
0.02 ms. The integer events are real browser telemetry. A controlled offline
experiment reproduced underruns without Lunar under CPU pressure; the cause
of the original CI failures remains unproven. No hardware was used.

## Report correction and what the counters establish

- [verified] [CI run 37980646770](https://github.com/ip2k/lunar-modulator/actions/runs/37980646770)
  at `275f8b3811d7810c57ab4d5b39d7e4b657b36f8c` failed its Chromium
  30-second storm twice. The first report recorded one event and raw duration
  `0.01`; the second recorded two and `0.02`. Functional checks passed.
- [verified] Exact Chromium **153.0.8010.12**
  [playback statistics implementation](https://github.com/chromium/chromium/blob/153.0.8010.12/third_party/blink/renderer/modules/webaudio/audio_playback_stats.cc)
  returns duration with `InSecondsF()` and event count from the integer glitch
  counter. `MaybeUpdateStats()` caches the statistics for the current task.
  The event count is not a floating-point subtraction artifact or a mismatch
  between the two synchronous getters.
- [verified] `playback-stats.mjs` now converts seconds to milliseconds while
  preserving the event count. Its regression covers the one/two-event reports,
  a nonzero baseline and unavailable statistics. The storm still requires
  `underrun_events === 0`; no tolerance, retry or event suppression was added.
- [verified] The CI worklet report had `timed: false`, with `late`, `maxMs`
  and `editMs` null. `FM1Processor.measure()` counts render quanta and, when
  a clock exists, measures the processor body against its quantum budget.
  It does not measure gaps between scheduled callbacks. Its quantum count
  cannot establish that audio deadlines were met.

## Controlled reproduction on aeon

[verified] `sim/web/test/audio-scheduling.mjs` runs a plain `OscillatorNode`,
without Lunar, its Wasm module or an AudioWorklet. The Playwright 1.63.0
container used Chromium 153.0.8010.12. Each configuration ran a 10-second
idle phase, then a 10-second phase with two busy Node worker threads. A
250 ms drain after each phase allowed cumulative audio-service statistics
to propagate. Browser-wide CDP tracing included the audio utility process;
cgroup counters bracketed each phase.

| Container CPU quota | Phase | Browser events | Browser duration | Reader timeout trace events | Throttled periods |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 CPU | Idle | 0 | 0 ms | 0 | 0 |
| 1 CPU | Two pressure workers | 65 | 650 ms | 67 | 100 |
| 4 CPUs | Idle | 0 | 0 ms | 0 | 0 |
| 4 CPUs | Two pressure workers | 0 | 0 ms | 0 | 0 |

[verified] The one-CPU pressure phase accumulated 12,890,710 microseconds
of cgroup throttling. This counter is aggregated accounting, not the elapsed
wall time or audio silence duration. Full traces contained 2,102 and 2,155
`Worker::DoRead` events respectively. The sink parameters were 441 frames at
44,100 Hz, or 10 ms per buffer.

[verified] Exact-version
[SyncReader](https://github.com/chromium/chromium/blob/153.0.8010.12/services/audio/sync_reader.cc)
waits for renderer data. When the data is unavailable, `Read()` zeroes the
destination and accumulates one buffer duration and one glitch event. Its
timeout path emits `SyncReader::Read timed out`. The controlled trace therefore
shows real missing renderer buffers in the headless audio pipeline, not only
a rounding discrepancy. This is not a measurement of physical audible output.

[verified] The 65 API events and 67 trace events cover different boundaries:
API snapshots surround the trace markers, and counter delivery crosses
processes. They are retained separately. [inferred] Boundary and delivery
timing can explain the difference; this experiment does not establish a
one-to-one correspondence for every event.

[verified] A separate corrected Lunar 30-second storm on aeon passed with
zero events and zero milliseconds, and all 35 editor unit checks passed.
The compact [recorded evidence](data/2026-10-09-chromium-scheduling.json)
contains the storm report, both probe reports, CPU deltas, selected trace
events and hashes of the full traces. Raw traces remain in ignored scratch
and the isolated LAN staging directory.

Reproduce each configuration in a capped LAN container, using the existing
Playwright dependency cache and a staging copy of `sim/web/test/`:

```sh
docker run --rm --cgroup-parent=docker-batch.slice \
  --memory=2g --memory-swap=2g --cpus=1 --ipc=host \
  --label lan.project=lunar-modulator --label lan.session=chromium-underrun \
  -v /path/to/playwright-cache:/pw:ro -v /path/to/staging:/src -w /src \
  mcr.microsoft.com/playwright:v1.63.0-noble \
  bash -c 'PLAYWRIGHT_DIR=/pw node test/audio-scheduling.mjs /src/probe-one 10 2'
```

Repeat with `--cpus=4` and a different output directory. This intentionally
stresses only the bounded container and is a diagnostic, not a CI acceptance
test. Results depend on available host resources.

## CI implication and remaining evidence gap

[verified] The original CI jobs did not capture cgroup pressure, CPU quota
or audio-service traces. Passing Firefox/WebKit storms do not supply the
same Chromium playback counter evidence. [inferred] CPU starvation is a
demonstrated mechanism for the observed 10 ms increments, but assigning it
as the original CI root cause would exceed the evidence.

[inferred] A strict zero-underrun timing gate should have dedicated resources
with measured CPU headroom. Preserve the existing functional tests and
zero-event assertion; capture resource pressure and audio-service traces
on failure so a scheduling failure can be attributed. The four-CPU result
is one controlled observation, not a universal minimum or proof that a
shared four-CPU runner cannot underrun. No workflow or infrastructure
configuration was changed by this investigation.
