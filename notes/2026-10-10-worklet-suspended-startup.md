# Suspended startup investigation

[verified] PR143 at `aff83ab804497b0724f7e5d8ba13b115cfcdd28a`
failed its Chromium storm zero-underrun gate in run 38040392775, job
114179304229: one 11.609 ms event, 7,319 edits, zero non-OK codes and
resyncs. The separate loopback passed. Firefox and WebKit passed. This is
a failed acceptance receipt, not a listening pass or an accepted retry.

[verified] The trace began before power-on. Its SyncReader timeout and
three propagated records of the same 11,609 us glitch occur during
power-on, about 332 ms before the edit loop. The baseline counter was
still zero; the event first appeared at the second one-second sample.
The publication delay explains how this startup event entered the storm
counter window. The strict baseline and zero-event assertion remain intact.

[verified] The affected output callback waited about 18 ms before worklet
render began; the first active render took 7.134 ms wall time / 3.877 ms
thread CPU time. The context was already running. Connection on ready
does not isolate initialization from a running context's worklet thread.
[inferred] Suspended-context initialization is a candidate lifecycle
correction, conditional on proving that initialization messages finish
while suspended and that gesture wake remains usable across browsers.
These intervals do not by themselves identify a particular init instruction.

The compact receipt, exact anchors, raw counter samples and downloaded
artifact JSON hashes are in
`data/2026-10-10-pr143-chromium-startup-failure.json`. Raw CI artifacts remain
on GitHub artifact 11665552341 and locally under
`/tmp/lunar-pr143-aff83-chromium`. Tracing and counter reads perturb
scheduling. Earlier failed CI events remain unassigned.

Next gate: a bounded comparison using an isolated copy of the actual
page/worklet/Wasm, with explicit finite initialization timeout. No hardware,
no original-CI retry, no threshold change, and no production claim yet.

## Bounded probe result

[verified] Probe source `d6a1f545` ran once per variant/browser on aeon,
4 CPUs / 2 GiB, private Pulse 48 kHz stereo `norewinds=1`. An isolated
copy suspended context creation, suppressed wake until ready, connected
then resumed. Chromium, Firefox and WebKit all delivered ready while
suspended at currentTime/frame zero, then resumed and produced 64–66
screens. Suspended instantiate/setup times were 3/6 ms, 11/4 ms and
5/5 ms respectively (integer Date.now resolution). No suspended-message
deadlock occurred within the 20-second finite wait. The running variants
initialized on an advancing clock. Both Chromium traces were complete
and recorded zero explicit glitch/timeout events; neither reproduced the
CI failure. This establishes the feasibility of ordered initialization,
not failure-rate proof, a strict storm pass, native Safari acceptance or
human listening success. Observers/tracing, fixed pair order and warm
browser cache can influence timing. Full compact results are in
`data/2026-10-10-suspended-startup-probe.json`.

## Proposed runtime correction

The `fix/2026-10-10@worklet-suspended-init` stream retains the diagnostic
history and applies suspended initialization to the actual page. Contexts
are created in the power-on gesture and explicitly suspended before
loading a worklet. Global gesture wake is suppressed until the current
node reports ready. Ready connects both outputs, marks initialization
ready and requests resume; future gestures can retry a browser-held
resume. Power-off resets readiness; old or closed nodes cannot connect
or resume. Resume rejection is handled without waiting indefinitely for
autoplay permission. The existing held-status hint remains available.

The worklet ready/catalog/refused/state message order is preserved. The
measured costly instantiate/default-chain/catalog work precedes ready;
its pending-message/state tail is not newly isolated or independently
measured here. No edit loop baseline, assertion or tolerance is changed.

[verified] Focused local checks: seven startup lifecycle regressions,
20 total helper regressions, and 36 editor-unit checks pass. Browser
startup smoke now verifies a suspended context and unchanged audio time
from node construction to ready on both power cycles. Actual new-source
three-browser storm/loopback and exact-head CI remain pending. These
browser-only files are outside `source_hash.py` engine/SIM inputs; the
existing Wasm is unchanged, not a new DSP artifact claim. Native Safari
and the owner's by-ear retest remain pending.
