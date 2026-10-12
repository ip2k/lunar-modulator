# Firefox native editor pointer settlement

[verified] CI source `86facf5639c0d144537cd28501db7aadeac6e88c`
failed the native matrix/playhead check in Firefox editor job:
https://github.com/ip2k/lunar-modulator/actions/runs/38229072223/job/114744119719
The 20-second `data-roll-playhead` timeout followed a fader ArrowUp and
Clip click. Failure screenshot shows Mixer selected and Clip focused;
Clip content never rendered. Native model/meter/fader and storm checks passed.
Downloaded logs/artifact11737953270 are in the arrangement-browser-review
worktree's scratch/firefox-final-ci folder.

## Cause and rejected approaches

[verified] Eight held real mouse presses spanning two resize RAFs and thirty
focused-resize clicks passed unchanged production. Adding a fresh fader key
edit/native mirror acknowledgement reproduced a lost natural click at trial28:
pointerdown/focusout27215, pointerup27226, detached target/RAF27229,
Mixer still selected, no document click. This is a product race, not merely a
playhead or running-scene mismatch. Pre-blurring the fader made all three
native suites pass but concealed the interaction; that harness patch is rejected.

[verified] Keeping the resize pointer guard until click alone was insufficient.
A second diagnostic recorded distinct down/up node identities and replacement
stack: host onSettled → refresh → draw replaced tabs at11801, between
pointerdown node5 at11796 and pointerup node7 at11810. The refresh redraw
bypassed the resize guard. Raw failed timelines remain separate from acceptance.

## Bounded repair

A pointer gesture now survives pointerup until click dispatch. Pointercancel
and release outside the workspace finish immediately. Release without a click
has a250ms fallback; a new pointerdown cancels the old fallback. Destruction
removes the listeners and timer. Asynchronous native refresh updates the model
but defers its redraw while the gesture is active, then flushes pending refresh
and resize after the gesture. Intentional view actions still draw immediately.
No native/Wasm, tab identity, MIDI identity or Clip-body changes.

The native test retains the focused edit and real mouse navigation. It forces
refresh during the held press and deterministically dispatches pointerup before
two RAFs, asserting the old target remains connected, then uses actual mouse
release/click and checks Clip selected. Cancellation, release outside, no-click
cleanup and a new press outliving the old release timer also exercise cleanup.
This is not a retry, forced click, threshold change or removed assertion.

## Receipts and next dependency

Hera isolated stage: /home/claude/mvave-fm1/firefox-native-settlement-20261012.
Playwright1.63 containers,2CPU/2GiB each, Pulse null sink, real native Wasm.
[verified] Final Chromium, Firefox and WebKit native suites pass14/14 each,
including target connection, actual click, all four release paths, and pending
refresh-only flush without resize. The same deterministic test on old86facf56
fails at “resize keeps the released target until click” (old source red).
[verified] Corrected source passed60/60 actual Firefox fresh-edit/mirror/ordinary
click trials, with no explicit pre-blur or layout settlement in the stress path.
Local receipts: scratch/firefox-final-ci/results/{chromium,firefox,webkit}-release,
results/navigation-final/navigation-timeline.json, and baseline.log. Rejected
pre-blur and first guard-only outputs retain their distinct names. Static Node
syntax and git diff --check pass. touch-action:manipulation applies to buttons;
real browser mouse and synthetic cleanup events cover the guard, not physical
touchscreen acceptance. No framework/dependency/runtime build changed.
Semantic MCPs select another active checkout; no session was switched. Source
inspection and actual browser events were used. Native/Wasm unchanged.

Parent must integrate the focused patch with the separate Clip-body stream,
review the combined exact head and rerun CI. Runtime browser success does not
establish deployed reload, owner listening, touch hardware or FM-1 acceptance.
