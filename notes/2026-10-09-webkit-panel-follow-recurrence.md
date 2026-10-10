# Recurring WebKit panel-follow failures

2026-10-09. Read-only inspection of the original exact-head CI reports [verified].
This is a shared panel-follow failure; it does not establish a regression in
the envelope or Picks changes.

| PR / head | CI run / WebKit job | Observed follow | Failed checks |
| --- | --- | --- | --- |
| #101 / `506b764` | `37985450550` / `114006185119` | `s2:2`, 24 frames / 375 ms, correct panel history/from/flash | Latency only (92/93 pass) |
| #118 / `1e0b9cd` | `37986887716` / `114010991455` | `s2:2`, 60 frames / 961 ms, no panel history/from/flash | Latency and panel history (91/93 pass) |

The compact original receipts are in
`data/2026-10-09-webkit-panel-follow-recurrence.json`. Both reports have no
console/page errors. Both jobs pass reach, Map (41 checks), editor-v1
(99 checks), and the edit storm [verified: downloaded job logs/artifacts].
WebKit supplies no playback underrun API in these reports; passing the
storm does not establish the absence of underruns.

These uninstrumented reports cannot distinguish late worklet processing,
message-channel delivery, editor snapshot deferral, replacement of the
original row, or an event never applied. The initial mirror/view wait and
400 ms delay do not prove the absence of a later overlapping snapshot
[inferred from the snapshot/change handler]. No causal correction follows
from these receipts alone.

Both branches now use the test-only observer originally validated for PR99
(`7809c0c`), described in `2026-10-09-webkit-panel-follow-latency.md`. It
records bounded frame/audio-clock/loading/row and main-thread before/after
message observations. **Acceptance remains at most 12 animation frames**,
with the identical encoder input, original-row value predicate and
60-frame observation maximum. No retry, readiness delay, or production
worklet change was added. Main-thread observation can perturb timing and
cannot establish when a worklet received an event.

The four observer regressions pass locally on both branches. Existing
editor unit checks pass: 34 on #101 and 35 on #118, including the Picks
undo/redo regression. This tests integration; it does not solve or reproduce
the original delay. The next exact-head CI supplies useful diagnostics if
the failure recurs. A passing run would not identify the earlier cause.

Rarefaction oriented the shared `onChanges` path at the main workspace;
Serena navigated that symbol in the actual Picks worktree. Exact branch
source was inspected directly. No hardware traffic or repeated LAN browser
run was performed.
