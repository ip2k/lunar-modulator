# WebKit frozen audio clock investigation — 2026-10-09

Current result: CI's private PulseAudio null sink now uses supported
`norewinds=1`, limiting its idle clock buffer to 50 ms. The retained default
clock was reproduced independently and an original-worklet cold-start pair
reproduced the WebKit failure. All three browsers pass full editor UI and
30-second external audio acceptance with the setting; WebKit needs the four-CPU
LAN quota matching public CI capacity. The failed two-CPU recording is retained.
Production runtime and every latency/audio assertion remain unchanged. Exact-head
GitHub CI is still pending; local acceptance does not establish CI success.

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

## Shorter CI startup stall on PR #109

[verified: CI log] PR #109 head `c69f9af06cbf977d26285f724d8f8604976d7221`,
run `38023500969`, WebKit job `114129336959`, fails the unchanged panel-follow
latency assertion at 16 frames / 261 ms. Frames 1–15 and the initial sample
hold `currentTime = 0.7111111111111111`; context remains running, the connected
row stays at 0.30, and loading, pending changes and inflight are all clear.
The first state arrives at 252 ms; editor changes arrive at 255 ms and the
handler updates generation 4 to 5 and row 0.30 to 0.33 by 258 ms. The panel
history check passes. This is the same early frozen-clock signature with a
shorter plateau, rather than evidence of a slow editor handler [inferred].
The [complete follow trace and failed check](evidence/2026-10-09-webkit-audio-lifecycle/pr109-ci.json)
retain log hash and exact identities. Original log: `/tmp/lunar-pr109-webkit.log`.


## Exact module and causal null-sink experiment

[verified: bounded LAN experiment] The module committed at the failing PR #129
head `ac3d9571b8a2db6860db60b1afb5f10246134e26` is now used directly, SHA-256
`2ff8cfa92f34a9c023088838477b9d53fb565edcd7f6922b084b40c21c48851f`.
All `sim/web/` sources are from that exact Git head. No rebuild or vendor binary
is committed. The private LAN directory is
`/home/claude/mvave-fm1/webkit-exact129-probe-20261009/`; dependency mount and
container limits remain the same as above. The original 30-second WebKit
loopback passes. Six fixed ordinary startups with the default null sink and
six with `norewinds=1` each pass the original 12-frame check. Half have the
original worklet; half have optional ten-per-second clock/receipt markers.
Passing ordinary starts alone cannot establish the cause or fix [inferred].

[verified: native backend isolation] PulseAudio 16.1 alone, with no browser,
UI or Wasm, exposes the clock mismatch. Load a fresh default null sink then
start `pacat` requesting 100 ms buffering: configured sink latency becomes
30 ms while actual sink latency is 1,956.652 ms. It falls to 1,903.112 ms,
1,854.850 ms, 1,704.752 ms, 1,453.345 ms, 953.606 ms and 454.460 ms at the
fixed 50, 100, 250, 500, 1,000 and 1,500 ms observations, before reaching
13.055 ms at 2,000 ms. With supported `norewinds=1`, idle configured latency
is 50 ms, first client actual latency is 36.822 ms and every later sample is
10.666–28.140 ms. Both native clients report no error.

[reported: official implementation] PulseAudio v16.1
[`module-null-sink.c`](https://raw.githubusercontent.com/pulseaudio/pulseaudio/v16.1/src/modules/module-null-sink.c)
uses a two-second default block and a 50 ms block with `norewinds`.
The requested-latency callback changes the block/request/rewind limits;
it does not reset the existing future timestamp. Rendering fills toward that
timestamp, and rewind subtracts only the bounded rewind amount.
[`sink.c`](https://raw.githubusercontent.com/pulseaudio/pulseaudio/v16.1/src/pulsecore/sink.c)
assigns sink implementations responsibility for rewinding buffered data when
the requested latency decreases. Retained idle timestamp plus a newly smaller
rewind limit explains the measured native mismatch [inferred].

[verified: controlled original-worklet reproduction] After the editor loads,
load a fresh private null sink immediately before clicking power-on; this
controls the backend clock phase and changes neither the source runtime nor
any assertion, existing wait, threshold or retry policy. With the original
unmodified PR #129 worklet, default sink startup fails at 34 frames / 549 ms.
Its running clock holds `0.7575510204081632` through frames 1–33; the first
state arrives at 542 ms and the editor updates at 546 ms. The immediately
paired `norewinds=1` trial passes at three frames / 30 ms. This reproduces
the CI failure signature by changing the backend's initial state [inferred].
A second pair with optional worklet markers passes in both modes (two frames);
those markers perturb scheduling and are not regression acceptance evidence.
Complete native, ordinary-start and cold-start observations and exact probe
sources are in [null-sink-startup.json](evidence/2026-10-09-webkit-audio-lifecycle/null-sink-startup.json).

[verified: additional CI signature] PR #118 head `b4234c1`, run `38023559253`,
WebKit job `114129510987`, holds the running clock at
`0.7169160997732427` for all 60 frames / 953 ms, with zero incoming events,
no loading/pending/inflight state and row 0.30. Its full failure trace and
source-log hash are in [pr118-ci.json](evidence/2026-10-09-webkit-audio-lifecycle/pr118-ci.json).
The log was obtained through the completed job's API while the full run was
still active; local source is `/tmp/lunar-pr118-webkit.log`.

[checkpoint and next step] Three fixed additional cold-start pairs with the
original worklet and full unchanged editor UI plus 30-second external loopback
in Chromium, Firefox and WebKit are running. `norewinds=1` is a supported
configuration for the isolated headless null sink; it does not change native
Safari or a production audio backend. Do not alter CI configuration until
that acceptance completes. No latency assertion or audio gate is relaxed.

[potential contribution; no upstream posting authorized] The native default
null-sink requested-latency/retained-timestamp mismatch is a candidate PulseAudio
bug report or upstream fix, supported by the native pair and v16.1 source.
Whether current PulseAudio versions retain it still needs evaluation. Choosing
its existing low-latency null-sink option for our headless tests is a separate
project configuration choice. No third-party code is changed or posted.

## Additional CI receipts and strict acceptance failure

[verified: completed GitHub job logs] PR #128 head
`1c09c5a229dd8c4ec4dd9e725f9c7bdb27f889c5`, run `38024099624`, job
`114131140518`, fails at 57 frames / 909 ms. Its clock holds
`0.7169160997732427` through frame 56; first state arrives at 901 ms and the
row changes at 904 ms. History passes. PR #105 head
`cc43875c7b205fcfbe530c04e4e7950cd6370bae`, run `38023632174`, job
`114129736784`, fails both panel checks at 60 frames / 952 ms, clock
`0.7198185941043084` fixed throughout and zero incoming events. Both say running,
loading false, no pending changes/inflight. They match the earlier clock plateau
[inferred], without identifying either branch's changes as the cause. Complete
traces and log hashes are saved in [pr128-ci.json](evidence/2026-10-09-webkit-audio-lifecycle/pr128-ci.json)
and [pr105-ci.json](evidence/2026-10-09-webkit-audio-lifecycle/pr105-ci.json).

[verified: exact PR #129 module, original unmodified worklet] Three further
fixed cold-start pairs pass the unchanged panel check: default 1/3/1 frames
(121/83/62 ms), `norewinds=1` 2/2/2 frames (85/27/28 ms). The reproduced
default failure is intermittent; these passing trials must not be represented
as deterministic reproduction. Full editor UI acceptance then passes all
93 checks and 37 screenshots in Chromium, Firefox and WebKit; panel follow is
2/1/3 frames respectively. Chromium and Firefox 30-second external loopback
pass with 7,265 and 7,204 batches/replies, zero refusals/resyncs and no audio
faults. WebKit has 3,755 batches/replies and zero refusals/resyncs but FAILS
external audio: 10 bad periods, 1,907-sample / 39.729 ms maximum internal
silence and 1,798.109-sample maximum period error. Its musical A/B phase passes.
No assertion is changed and the candidate sink change has not been applied.

The [full reports](evidence/2026-10-09-webkit-audio-lifecycle/null-sink-acceptance-two-cpu.json)
retain every verdict and cold trace. Native raw recordings, screenshots and Pulse
log stay in the unique LAN `acceptance-out/` directory. Pulse reports failed
realtime/high-priority acquisition; the private two-CPU cgroup at the later UI
observation has 513 throttled periods / 76.572 seconds throttled time. This
is a scheduling-pressure candidate, not proof that it caused the audio gaps
[inferred]. A bounded paired run will record per-test cgroup and timed backend
markers with four CPU quota; CI itself has no CPU quota option. No unchanged
retry or threshold weakening is justified by this failure.

[verified: CI queue policy] Main `9cfc46dc35c2fb859f22a1f5315f6990c415a099`
was merged into this branch, preserving the panel observer, scheduling capture
and modal checks. CI now uses the existing Pages policy: `ci-${{ github.ref }}`
concurrency with cancellation enabled only for `pull_request`. A newer head
supersedes obsolete PR work; main and manual runs are not cancelled by this
expression. The owner observed thirteen obsolete queued jobs per checkpoint.
No matrix, test, threshold or null-sink setting changes in this checkpoint.
Workflow YAML parsed successfully; two pin tests and all nine panel-follow /
scheduling-capture unit tests passed locally.


## Accepted headless sink configuration

[verified: exact PR #129 source and committed Wasm] The bounded four-CPU
controlled pair passes in both modes: unchanged full editor UI is 93/93 checks,
37 captures each, panel follow 2 frames for default and 1 for `norewinds=1`.
Default external audio has 3,755 batches/replies and no zero run or bad periods;
`norewinds=1` has 3,756 batches/replies, zero refusal/resync, zero bad periods,
maximum zero run one sample (0.0208 ms), and maximum period error 0.0082 samples.
Both musical phases pass without transport stops or console/page errors.
Per-test CPU throttling is 35.625 ms for default audio and 1.132 ms for the
fixed sink, compared with the retained earlier heavily throttled two-CPU run.
The fixed sink's Chromium and Firefox full UI and 30-second audio passes are
recorded in the preceding two-CPU acceptance; the four-CPU pair completes
WebKit's strict acceptance without dismissing its earlier failed recording.

[verified: three additional fixed cold pairs] These six browser invocations
remove the entire added AudioWorkletNode diagnostic wrapper, use the original
unmodified worklet and preserve the existing strict panel observer. Default
passes at 2/2/2 frames, `norewinds=1` at 2/2/1 frames. No added per-frame markers,
extra readiness waits, retries or changed assertions are present. All trials
unload/reload only the private test sink immediately before power-on. Passing
unmarked pairs do not erase the earlier intermittent default failure or prove
that every future backend/runner condition is covered.

[verified: backend version and supported option] The same pinned Playwright
Noble image used by CI installs PulseAudio 16.1; `pulseaudio --version` and
`pactl list short modules` record successful `norewinds=1` activation. Official
[v16.1 null-sink source](https://raw.githubusercontent.com/pulseaudio/pulseaudio/v16.1/src/modules/module-null-sink.c)
accepts the option and sets its maximum idle latency to 50 ms instead of 2 s.
The repo is public, its CI container has no CPU quota, and
[GitHub's standard public Ubuntu runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
has four cores [reported: official runner documentation]. The four-CPU LAN
quota is a capacity comparison, not an exact replica of GitHub scheduling.

Complete reports, cgroup counters, module arguments, version/hash receipts and
both bounded runners are saved in
[null-sink-acceptance-four-cpu.json](evidence/2026-10-09-webkit-audio-lifecycle/null-sink-acceptance-four-cpu.json).
The Wasm hash remains `2ff8cfa92f34a9c023088838477b9d53fb565edcd7f6922b084b40c21c48851f`;
the worklet hash is `f3788e723cd22303dfbd95030c8d16cce761ca60be0ac1717b453861872d33cd`.
Raw recordings/screenshots stay in the unique LAN `quota-pair-out/` directory;
all owned containers have exited normally. No shared service was restarted.

[implemented; CI verification pending] `.github/workflows/ci.yml` and the two
headless Pulse examples in `sim/web/README.md` now select `norewinds=1`.
This is an existing backend setting for isolated Linux test sinks; native
Safari, browser application code, firmware and test gates do not change.
No runner resource setting changes. Main documentation through `65367771`
is integrated before this fix. Root reviews/merges after exact-head CI; failed
PR heads should receive this shared workflow fix through normal integration,
not unchanged retries. The retained native mismatch remains a potential
upstream candidate requiring owner sign-off; no third-party posting occurred.

[verified: focused configuration checks] Workflow YAML parses with the project
virtual environment; both `tests/test_ci_pins.py` tests and all nine unchanged
panel-follow/scheduling-capture unit tests pass. `git diff --check` passes.
The Mac's system Python lacks PyYAML/pytest, so validation uses the existing
project `.venv`, without installing packages or changing runtime configuration.


## Preserved PR #102 failure before integration

[verified: completed GitHub job log] PR #102 head
`962e8ba900f7c223b46f7dd058874fabe96ace20`, run `38023635600`, job
`114129747188`, fails the unchanged panel latency check at 43 frames / 694 ms.
Its running clock holds `0.7169160997732427` through frame 42; first state
arrives at 684 ms, changes at 686 ms, and the editor applies them at 690 ms.
History passes and loading/pending/inflight are false/zero throughout. This
matches the retained startup plateau signature [inferred], without proving a
branch regression. The preceding strict 30-second loopback passes with 3,756
replies, no refusal/resync, zero silence or bad periods. Reach, Map, v1 and
30-second editor storm pass. Full follow/audio receipt and source-log hash:
[pr102-ci.json](evidence/2026-10-09-webkit-audio-lifecycle/pr102-ci.json).
Local source log is `/tmp/lunar-pr102-webkit.log`. No integration, rerun or
assertion change was made while preserving this evidence. PR #132 remains
on exact pushed head `c6db9587`; this receipt and the current-head acceptance
below are checkpointed separately on
`chore/2026-10-09@webkit-audio-evidence-checkpoint`, preserving its current CI.


[verified: current fix head LAN acceptance] While exact-head GitHub CI waits
for runners, a new bounded private container tests current source `c6db9587`
with the CI sink command, four CPU quota and `FM1_SCHEDULING_CAPTURE=1`.
It uses the newer committed module (SHA-256
`9562448e742836a4571ebd04ad303c72d0125a8054483dffbee9d5c6240ed4e1`),
not the earlier exact PR #129 module used for causal pairing. The original
worklet hash remains identical. WebKit's strict 30-second loopback passes:
3,756 batches/replies, zero refusal/resync/nonfinite/channel mismatch/bad
periods, one-sample maximum zero run and 0.00882-sample maximum period error.
Musical A/B passes with no transport stops; full editor UI passes all 93
assertions with 37 screenshots and panel follow at three frames / 33 ms.
Complete reports, per-test cgroup snapshots, module/version/hash receipts
and runner are saved in
[pr132-current-head-lan.json](evidence/2026-10-09-webkit-audio-lifecycle/pr132-current-head-lan.json).
This covers the current source integration difference, not the full GitHub
matrix; no retry of an unchanged failed head or assertion relaxation occurred.
The owned container exited normally and shared services were untouched.

## Preserved PR #121 failure before integration

[verified: completed GitHub job log] PR #121 head
`32d4747f900a47de4054618195ffe269f73ccef6`, run `38025766630`, job
`114136164786`, fails only the unchanged panel latency assertion at 18
frames / 281 ms. Its running clock holds `0.7198185941043084` through
frame 17 / 259 ms, then telemetry arrives at 270 ms, state at 272 ms,
changes at 274 ms and the editor applies the value at 278 ms. Loading is
false, pending/inflight zero and the row remains connected. The resulting
history entry and flash are present. This matches the prior backend
startup plateau signature [inferred]; it does not establish a PR #121
source regression. Strict 30-second loopback passes with 3,756 replies,
zero bad periods/silence/refusal/resync and no transport stops; the editor
storm also passes with zero bad codes or resyncs. The full follow/audio/
storm receipt and source-log SHA-256 are in
[pr121-ci.json](evidence/2026-10-09-webkit-audio-lifecycle/pr121-ci.json).
Local log: `/tmp/lunar-pr121-webkit.log`. No rerun, branch integration or
threshold change was made to obtain this receipt. This addition is backed
up on the separate evidence branch, preserving PR #132's reviewed CI head.

## Preserved PR #125 native-preview head failure

[verified: completed GitHub job log] PR #125 head
`7fe4e6cd10e5d4aa895c5df18d0273364788be5d`, run `38025910713`, job
`114136597222`, fails panel latency and its associated history assertion
after the unchanged 60-frame / 960-ms observation. Audio time remains
`0.737233560090703` in every frame while the context reports running;
no port/editor events arrive, loading is false, pending/inflight zero and
the row remains connected at its initial value. This repeats the earlier
long startup plateau signature [inferred], without proving a native-preview
regression. Strict 30-second loopback passes with 3,756 replies, zero bad
periods/silence/refusal/resync and no transport stops; the editor storm
passes with zero bad codes or resyncs. The complete failure/audio/storm
receipt and source-log SHA-256 are in
[pr125-7fe4-ci.json](evidence/2026-10-09-webkit-audio-lifecycle/pr125-7fe4-ci.json).
Local log: `/tmp/lunar-pr125-7fe4-webkit.log`. No unchanged rerun or gate
relaxation was used. This receipt is checkpointed on the separate evidence
branch while PR #132's tested head remains `c6db9587`.

## Preserved PR #131 Chromium underrun failure

[verified] PR #131 exact `78101317052b2eb990d7a24fbe855dbb506ce1eb`, run
`38025899085`, job `114136559601`, failed the unchanged 30-second editor storm:
7,280 edits, 58,240 records, zero refused codes/resyncs, 10,695 quanta, but one
Chromium `playbackStats` underrun lasting 11.609 ms. Earlier external loopback
passed (7,273 replies, zero bad periods/refusals/resyncs). The receipt is
[`pr131-chromium-ci.json`](evidence/2026-10-09-webkit-audio-lifecycle/pr131-chromium-ci.json).
The complete 86,939-event audio trace has no saved `Glitch!` event; the longest
worklet graph render is 3.969 ms wall time versus 0.852 ms thread CPU time.
Thirty-three resource samples show four available CPUs, `cpu.max=max 100000`,
zero recorded throttling, and 155,129 microseconds of cumulative cgroup CPU
pressure (`some`) during the window. Mount/namespace provenance is retained.

[inferred] This is distinct from the frozen WebKit startup clock signature.
Scheduling interruption is a candidate, not a demonstrated cause; the trace
does not localize the counted underrun. Chromium's matching-version
[`AudioPlaybackStats`](https://raw.githubusercontent.com/chromium/chromium/153.0.8010.12/third_party/blink/renderer/modules/webaudio/audio_playback_stats.cc)
reads the context's accumulated glitch count/duration. The trace exhibits
[`AudioDestination`](https://raw.githubusercontent.com/chromium/chromium/153.0.8010.12/third_party/blink/renderer/platform/audio/audio_destination.cc)'s
worklet rendering wait path. Playback statistics span storm plus snapshot drain,
while browser-wide tracing has its own surrounding window. PR #132's null-sink
idle-buffer option must not be presumed to fix this distinct Chromium event.
No assertions, timing thresholds, browser features or source queues were changed.
[verified] Three bounded fresh-browser, exact-source 30-second LAN storms all
passed: 7,252 / 7,269 / 7,196 edits; each produced 10,695 quanta and zero
underruns, refused codes or resyncs. They used the pinned CI image, Pulse 16.1,
the original default sink and four-CPU quota. Full reports, resource deltas,
trace hashes and setup limits are in
[`pr131-chromium-lan.json`](evidence/2026-10-09-webkit-audio-lifecycle/pr131-chromium-lan.json).
The preceding CI tests and GitHub host contention were not replicated; tracing
was enabled as in CI and may perturb scheduling. All outcomes are retained.

[verified: matching Chromium source] The renderer's
[`AudioOutputDeviceThreadCallback`](https://raw.githubusercontent.com/chromium/chromium/153.0.8010.12/media/audio/audio_output_device_thread_callback.cc)
reads shared-memory glitch increments and forwards them to graph rendering.
[`SyncReader`](https://raw.githubusercontent.com/chromium/chromium/153.0.8010.12/services/audio/sync_reader.cc)
waits for a matching renderer buffer index; a missed callback emits silence
and accumulates one platform buffer of glitch duration. At 512 frames / 44.1 kHz,
that duration matches the observed 11.609 ms [inferred]. Neither the timeout
nor `Glitch!` is present in the saved CI trace, so this is a mechanism to inspect,
not a localized cause. No justified runtime source fix was found in this bounded
investigation, and the original CI underrun remains an independent failed gate.

## PR #132 completed Firefox and WebKit acceptance

[verified: completed jobs] Exact reviewed head `c6db9587c1d8d1ca6f993d8f433875761f3b2b6e`
passed both complete browser jobs in run `38028605340`: Firefox job
`114144633961` and WebKit job `114144633999`. Both logs confirm the private
null sink loaded with `norewinds=1`. Strict 30-second loopback passed with
7,224 Firefox replies and 3,756 WebKit replies, zero bad periods, silence,
refusals or resyncs. The unchanged editor storms also passed: 7,239 Firefox
edits and 3,756 WebKit edits, 10,695 quanta each. The full job success includes
the page checks. Reports and log hashes are in
[`pr132-firefox-webkit-ci.json`](evidence/2026-10-09-webkit-audio-lifecycle/pr132-firefox-webkit-ci.json).
Chromium's Node step is still running at this checkpoint, so full CI remains
unconfirmed. The same Node helper/data/history suites passed a separate bounded
LAN check against identical test sources/Wasm in the pinned image; this does not
explain the quiet GitHub runner. Its eventual result must be preserved.

## Preserved PR #136 WebKit startup failure

[verified] PR #136 exact `1299c590408e6d919181294bdadc8c28b4b7503a`, run
`38028091040`, WebKit job `114143127928`, failed strict panel follow: 33 frames /
529 ms. Audio time stays at 0.7140136054 through frame 31 (497 ms), while the
context is running, loading is false and pending/inflight counts are zero.
The state arrives at 514 ms; the editor applies the correct value at 520 ms.
The job uses the original null-sink command without `norewinds=1`. This agrees
with the earlier frozen startup signature [inferred]; it does not establish
a legal-profile source regression.

[verified] The preceding strict 30-second loopback passes with 3,756 replies
and zero bad periods, silence, refused codes or resyncs. The later editor
storm reports 3,757 edits, 10,695 quanta, zero refused codes, **one resync**,
and `pass=true` under its existing predicate. That resync is retained as a
separate observation; it is not proof that the null-sink correction fixes
queue resynchronization. No gate or assertion was changed and no unchanged
rerun was requested. Full reports, decoded frame observations, exact sink
command and log SHA-256 are saved in
[`pr136-webkit-ci.json`](evidence/2026-10-09-webkit-audio-lifecycle/pr136-webkit-ci.json).
The evidence backup leaves PR #132's reviewed head unchanged.
