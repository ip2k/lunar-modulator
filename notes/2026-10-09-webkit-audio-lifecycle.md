# WebKit frozen audio clock investigation — 2026-10-09

[verified: GitHub logs] PR #125 head `540ed3cf0008cc2c3a01e0eaf913339d7827319c`,
CI run `38016847016`, WebKit job `114108904554`, fails the panel-follow
latency and panel history checks. Its observer reports 60 frames / 960 ms,
`AudioContext.currentTime` fixed at `0.7169160997732427`, state `running`,
no main/editor port observations, loading false, no pending changes or
inflight work, and the original/current row still connected and unchanged.
Reach, Map and editor-v1 subsequently pass. This is shared browser/audio
path evidence, not proof of a CSS, Picks or semantic configuration regression.

[verified: source] The ordinary worklet returns true from every `process()`
path and connects to the context destination. Encoder input is handled by
its main port, while change publication occurs in render callbacks. The page
resumes a held context on input only when its reported state is not running.
A frozen clock with a running state does not establish why callbacks or
message delivery paused. No production fix is justified by these observations
alone; the 12-frame acceptance, 60-frame observation maximum and zero-event
storm gate are preserved.

[reported: upstream] WebKit [bug 296843](https://bugs.webkit.org/show_bug.cgi?id=296843)
records GStreamer/PulseAudio silent-buffer playback failures and was fixed in
September 2025. It is a candidate comparison, not identification of this
October 2026 failure; its original idle duration and symptom differ.

[verified: tooling] Rarefaction oriented `start` at the primary workspace,
with `powerOn` and the expected context/worklet helpers; Serena found the
same symbol. Shared project selection was not changed. Exact investigation
worktree source was read directly; those MCP results do not prove this
worktree's index or coverage.

## Reproduction checkpoint

Baseline is main `67d5e12dee561abca5d0a2256fec85d75522a806` on
`fix/2026-10-09@webkit-audio-lifecycle`. A bounded independent run uses aeon's
existing Playwright 1.63.0 installation and image
`mcr.microsoft.com/playwright@sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27`,
a private container and PulseAudio null sink at 48 kHz, two CPU quota,
4 GiB memory and `docker-batch.slice`. It runs the unchanged 30-second
external audio test followed by the unchanged editor UI test. GStreamer
category diagnostics are enabled for the UI run. Files persist at
`/home/claude/mvave-fm1/webkit-lifecycle-20261009/`; both containers finished
and were removed normally.
No hardware, shared service restart, MCP activation or upstream posting occurs.

## Bounded result and next useful evidence

[verified: independent LAN run] The unchanged full editor UI test passes all
93 checks and produces 37 screenshots, with no console/page errors. Its panel
observation receives state/screen/changes, updates `s2:2` in one frame / 18 ms,
records the KNOB2 history entry, and advances the audio clock from 0.6182313
to 0.6356463 seconds. The preceding unchanged external audio test passes:
3,756 storm batches/replies, no refusal/resync, zero nonfinite samples,
channel mismatches, zero runs or bad periods; musical A/B playback peak 0.2602.

[verified: bounded startup probes] Eight separate fresh browsers then run
only the original editor UI setup and panel-follow checks, under the same
private 48 kHz sink and two-CPU quota. The probe is the exact `editor-ui.mjs`
prefix ending immediately before `// ---- follow, editor to panel`, followed
by report output and normal browser/server cleanup. Each invocation has a
45-second external timeout. All eight pass within one to three frames
(12–153 ms); every observed audio clock advances and messages arrive. This
is additional passing evidence, not a reproduction of the CI failure or a
new millisecond acceptance threshold. These probes do not include the
preceding loopback test; the full UI run above does.

The compact [machine-readable results](evidence/2026-10-09-webkit-audio-lifecycle/results.json)
retain the complete follow traces, check verdicts, audio report and probe
source SHA-256. The copied probe source remains in the unique LAN directory;
no test or production source changed in this branch.

[limitation] None of these nine observations reproduces the frozen clock.
The GStreamer category environment used for the full UI run produced no
additional backend diagnostics in its log; lack of such messages is not
proof of backend health. No resume/retry, extra readiness wait, silent audio
source, backend swap or changed assertion is justified. A failing CI run
needs contemporaneous WebKit/GStreamer/Pulse diagnostics and worklet
receipt/render timing to distinguish scheduling starvation, audio backend
stall and message dispatch. Existing main-thread traces cannot identify
which of those occurred. The 12-frame check, 60-frame maximum and zero-event
external audio gate stay unchanged.


## Second CI failure — PR #129

[verified: GitHub job log] PR #129 head
`ac3d9571b8a2db6860db60b1afb5f10246134e26`, run `38023499052`, WebKit job
`114129330510`, reports the same panel latency/history failure. The 60-frame
observation lasts 962 ms: `currentTime` stays at `0.7111111111111111` for frames
1–59, then advances to `0.7314285714285714` on frame 60. A single main-port
state message arrives at 961 ms with audio time `0.7169160997732427`; the row
remains 0.30 and history is absent. Every recorded frame says running, loading
false, pending changes/inflight zero, and the row remains connected. The late
clock movement is important: this is a temporary stall, not proof that the audio
thread died permanently.

The preceding external loopback in the same job passes its unchanged 30-second
storm: 3,756 batches and replies, zero refusal/resync, nonfinite or channel
mismatch, zero bad periods, and musical peak 0.2659912. A later editor storm
also succeeds. A passing different browser process and audible workload does
not prove the silent startup of editor-ui is healthy [inferred]. The loopback
closes its browser in a finally block; editor-ui launches a fresh browser and
context. No shared production AudioContext passes between these Node processes
[verified: launch.mjs and audio-loopback.mjs cleanup].

The [extracted CI evidence](evidence/2026-10-09-webkit-audio-lifecycle/pr129-ci.json)
preserves the complete failing trace, both failed check messages, loopback report,
exact run/head/job and downloaded log SHA-256. The original log is retained at
`/tmp/lunar-pr129-webkit.log`; no credentials or unrelated logs are copied.

Next bounded run will compare fresh editor startup immediately after loopback
with standalone starts under the same private Pulse sink. Backend stderr must
actually be captured: the prior GST_DEBUG-only run emitted no backend diagnostics,
so it cannot exclude a Pulse/GStreamer startup or silence-related stall.

## Backend capture and silent startup comparison

[verified: bounded LAN experiment] The private follow-up uses the same recorded
baseline module (SHA-256 `9562448e742836a4571ebd04ad303c72d0125a8054483dffbee9d5c6240ed4e1`),
Playwright 1.63.0 / WebKit 26.6 (`webkit-2359`, WPE in headless mode), PulseAudio
16.1 and host-container GStreamer 1.24.2. Sources `app.js`, `worklet.js`,
`editor-ui.mjs` and `launch.mjs` match PR #129's failing head; the engine sources
and rebuilt CI module differ. This is a comparison of startup behavior, not an
exact-head binary reproduction. The existing `/pw` dependency mount is read-only.
Each own container uses the same private 48 kHz null sink, two CPU quota,
4 GiB memory and batch cgroup, and exits normally; no shared service is changed.

The unchanged 30-second loopback again passes 3,756 batches/replies, zero
refusal/resync, nonfinite or channel mismatch, and zero bad periods; musical
peak is 0.2676697. Six fixed fresh startup probes pass within one to four
frames (19–97 ms): four immediately after loopback, then two after a five-second
idle. `DEBUG=pw:browser` and `GST_DEBUG_FILE` now retain actual backend output.
The logs identify `autoaudiosink0-actual-sink-pulse`; every passing startup has
Pulse underflow warnings (3–11 per trial). Underflow warnings alone cannot
identify the failing assertion [inferred]. Pulse observations and cgroup CPU
counters are retained; quota throttling also occurs in passing trials.

[verified: diagnostic clock observation] Three further fresh browsers run the
same startup prefix, then sample `currentTime` and context state on animation
frames for five seconds **before** the original encoder/follow probe. This
changes observation timing and is not the unchanged acceptance run. One trial
holds `currentTime = 0.748843537414966` for 23 consecutive sampled frames,
spanning 347 ms (sample offsets 131–478 ms), while state remains running.
The next samples advance to 0.8097959 and then 1.2306576 seconds. Animation
frames continue during the plateau. The other trials' longest repeats are
0 and 26 ms. All three later encoder probes pass in one or two frames.

Two fixed comparison trials remove verbose GStreamer output while retaining
the same clock sampler, Pulse debug log, 100 ms Pulse/cgroup polling and CPU
quota. The first again holds a running clock, this time at 0.7546485260770975
for 43 sampled frames / 673 ms (offsets 130–803 ms), then catches up to
0.9839456 and 1.4860771 seconds. The second has a 61 ms two-sample repeat.
Both later encoder probes pass. Verbose GStreamer output is therefore not
necessary for the observed plateau [inferred]; the remaining instrumentation
and CPU quota can still perturb timing. No retries convert a failing result
into a pass: the six, three and two observations are separate fixed experiments.

[verified: backend correlation, not causation] Both long-plateau trials record
initial Pulse sink latency near 1.9 seconds, descending over subsequent polls.
The three shorter silent trials peak at roughly 0.29–0.50 seconds. The verbose
plateau trial records a burst of GStreamer clock-skew corrections and underflow
around backend elapsed 1.19 seconds. These observations strengthen the startup
backend/clock hypothesis, but do not prove whether sink startup, worklet/engine
initialization or scheduling pressure caused the CI failure. A running context
and an uncorked Pulse input do not establish uninterrupted worklet processing.

The [complete compact capture](evidence/2026-10-09-webkit-audio-lifecycle/backend-probes.json)
contains all clock and follow samples, selected Pulse/cgroup observations,
browser stderr, backend warning excerpts, full probe/runner sources and exact
raw-file hashes. Raw backend logs remain at
`/home/claude/mvave-fm1/webkit-backend-probe-20261009/{out,silent-out,silent-quiet-out}`;
local copies are `/tmp/lunar-webkit-backend-results/`. Host/machine identifiers
and Pulse cookies are omitted from the committed observations. No vendor binary
or audio capture is committed. The raw logs remain local/LAN recovery data;
the evidence extraction is the GitHub-backed record.

[limitation and next step] Temporary early running-clock plateaus are now
observed locally, including without verbose GStreamer logging. The unchanged
initial panel-follow failure remains unreproduced, and no causal runtime fix is
established. The next useful comparison is a failing exact-head rebuilt module
with clock samples tied to wall-clock timestamps, actual worklet receipt/render
markers, and contemporaneous Pulse/GStreamer/cgroup records; first reduce
observer overhead. Preserve the 12-frame check, 60-frame maximum and zero-event
external audio gate. No extra readiness wait, resume/retry, silent oscillator,
backend substitution or assertion change is justified by this checkpoint.
