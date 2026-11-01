# PR151 offline review and WebKit pause fix

Personal Lunar Modulator work. This is host/browser validation only: no device,
SDK, protected analysis, vendor binaries, owner captures or upstream contact.

## Outcome and exact sources

[verified] Reviewed PR151 source head
`689031c09992538cbc0e9cac5ce7930b8d448b7d`, independently equal to its remote
branch SHA. Its 15-file offline Workbench delta has no blocking conversion,
licensing or privacy finding. The adapter preserves DX7 integer voice fields,
refuses silent repair and unapproved losses, and performs no device transport.
Vendor project/timbre/sample formats remain structural inspection only.
Inventory hashes are provenance, not firmware redistribution clearance.

[verified] The sole failing PR check was WebKit run `41002300468`, job
`123889276610`. It tested synthetic merge
`165f65b6cfdeb80d08d3051dac8ce8a1d350b73c` (head689031c into then-main
`9f6b3d0c6022dd1448c8f83a7080207d56b3ff9f`). Pairwise diff of that base and
head for `sim`, `engines`, `.github` is empty. Base push CI `40848092825`,
including WebKit job `123360459504`, passed. Current main at review start
`a1b7823ba768d7657474f9be432d7584998b1501` has later engine/Wasm changes;
it is not byte-equivalent to the PR head.

## Demonstrated click suppression

[verified] CI artifact `compact-toolbar-failure.json` says phase **pause**,
not resume: the second click did not produce the expected Resume label.
Audio was running, ticks continued, controls were enabled/not busy, and no
page error was recorded. This was not evidence of stalled audio.

[verified] The unmodified full compact-toolbar check passed independently.
A diagnostic using the same real page then reproduced the lost pause click
on fresh-page cycle 4. Its capture listener and wrapped worklet postMessage
show pointerdown/mousedown and pointerup/mouseup on the same enabled Pause
button, with no click and no outgoing pause command. No button replacement
occurred. The small retained trace is
[evidence/workbench151-20261101/baseline-click-trace.json](evidence/workbench151-20261101/baseline-click-trace.json).
An earlier 16-cycle run passed, so one green run does not disprove this race.

[verified] A reduced WebKit page used a fieldset/button and the same handler
sequence: disable fieldset, await a synchronous result, enable fieldset.
Out of 100 Playwright locator clicks, 3 emitted pointer/mouse down/up but no
click. Without the transient disable, all 100 emitted click. The page also
updated its button label at 32 ms intervals to match transport telemetry.
The experiment log and source are retained beside the trace.

[verified] `action` previously disabled the fieldset even for synchronous
transport postMessage callbacks. It now invokes the callback and locks only
when its result is thenable. Promise-returning work remains locked until
settlement, rejects overlapping actions, announces refusals, and unlocks in
finally. Synchronous actions can follow one another without a transient
native disabled state. Synchronous throws remain caught and announced.

[verified source review] Callers include synchronous transport/navigation
postMessage operations, file-picker and export-dialog creation, async text
export, and async MIDI parsing. The async functions return their promise in
the same JavaScript turn; no input event can interleave before the lock is
set. File-picker change events manage their later transaction independently.
No current synchronous callback recursively invokes `action`.

## Regression and validation

[verified] The mock-host sequencer UI test now asserts immediate transport
actions do not disable or block each other; pending actions lock/exclude a
second action; success/rejection release the lock; async/sync refusals are
announced; and an action after refusal still runs. The deterministic enabled
control assertion fails against the old source. No transport assertion,
wait timeout or browser actionability check was relaxed.

[verified] Python review: 24 focused Workbench tests pass (C parser acceptance
excluded to avoid a local native build); all 16 synthetic probes behaved as
expected (12 accepted, 4 malformed/future inputs refused). Existing CI covers
the C parser.

[verified] Pinned Playwright 1.63.0 validation exited zero: the new regression
failed against baseline source with the intended immediate-action assertion;
fixed `sequencer-ui.mjs` and unchanged full `compact-toolbar-check.mjs` passed
in WebKit, Chromium and Firefox. The host/shortcut Node suites passed all 19
tests. The fixed real-page rapid-cycle diagnostic passed 48 fresh-page cycles.
`node --check` on both changed JavaScript files and `git diff --check` pass.
The browser test checklist labels were added after this run; its executable
assertions are the same as the tested copy.

[verified] Evidence is retained under `notes/evidence/workbench151-20261101/`.
`validation.sh` records the container commands (prepare `baseline-sequencer.js`
from head689031c and `fixed-sequencer.js` from this branch at stage root first).
The diagnostic sources run from their retained folder with `BROWSER=webkit`
and `PLAYWRIGHT_DIR` pointing to the pinned Playwright install. They use only
synthetic local pages/data. A passing local run does not replace required CI
on the parent-reviewed integration head. Because this source cause was
reproduced, prefer integrating the fix and running that head through normal
required checks over spending a failed-job rerun on the unchanged head.

## Tool and operational limits

Rarefaction/Serena selected the absolute primary checkout and were not switched
over concurrent sessions. Rarefaction orient/scope on `action` matched unchanged
source, found toolbar callers and named sequencer UI/native/playback tests;
Serena's bounded package-guard declaration matched source and its known main
caller. Branch-specific checks used the exact isolated worktree, not an assumed
shared index. No native ABI, audible quality or physical acceptance is claimed.

Experiments used Aeon, pinned Playwright `1.63.0-noble`, a PulseAudio null sink
with `norewinds=1`, `docker-batch.slice`, CPUs8-11, 4 CPUs and 6 GiB memory/swap.
Own staging path: `/datasets/lunar-modulator/workbench151-pause-20261101`.
Containers use --rm; source/diagnostic copies and screenshots are removed after
small logs/results are collected. Owned Aeon staging was removed after collecting evidence; no container with
this session label remains. Mac free space at final checkpoint:1119 GiB.
The isolated Mac worktree remains for parent review and should be removed once
integrated; its small tracked evidence is durable.

Branch: `fix/2026-11-01@workbench151`, from the exact PR head. Parent coordinates
review, PR update and integration; this task does not merge or blindly rerun CI.
