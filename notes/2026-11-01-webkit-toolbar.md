# WebKit Pause click loss — 2026-11-01

Scope: PR #165 exact head `bb9187f393f5c5b48ae782ef31a137928f91c167`.
Personal, non-commercial Lunar project. No hardware traffic or WASM rebuild.

## Finding and fix

[verified] CI run 41302493347 WebKit artifact 13081799750 records phase
`pause`: the button stays enabled with label `Pause`, the AudioContext is
running, native ticks keep advancing for 30 seconds, and there are no page
errors. The actual job log is `124836168406.log`. The failure is at the
Resume-label wait following the second Play/Pause click, not initial readiness.

[verified] `makeSequencer/updateTransport` unconditionally replaced the button
text node on each native transport publication, even while its icon was
unchanged. In Playwright 1.63.0 WebKit 26.6, replacing identical button text
between pointer press and release suppresses the subsequent click. A reduced
30-click case loses 30/30 with text replacement and 0/30 with no writes,
`disabled=false` writes alone, or aria-label/title writes alone. The tiny reproducer
and raw reduced result remain in private scratch; real-app evidence is in
`notes/evidence/webkit-toolbar-20261101/`.

[verified] The exact committed app reproduces this: Pause pointerdown/mousedown
at 1380 ms, pointerup/mouseup at 1532 ms, intervening icon child-list mutations,
and no click or `seq-line pause`. The only transport command is `resume` from
the preceding Play click. Audio and ticks continue. `held-red.json` retains
this event chronology and final state. A first deterministic test also failed
its unchanged-icon assertion before the fix (`regression-red.log` in private
scratch). The final regression tests behavior: hold the Pause press across an
actual advancing native tick, release, and require Resume without retries.

[inferred] This browser event-loss mechanism explains the matching CI phase
and state. CI did not capture pointer events, so the exact timing of its lost
click cannot be reconstructed independently from its artifact.

The fix assigns the icon text only when it changes. Transport labels, command
selection, asynchronous locks, audio scheduling, and test timeouts are unchanged.
No new dependency or custom event dispatcher is needed; preserve native DOM
identity with an ordinary conditional assignment.

## Validation and tool limits

[verified] The strengthened complete compact toolbar test passes in WebKit,
Chromium and Firefox using Playwright 1.63.0. It includes Play/Pause/Resume/Stop
and 22 layout/view/viewport combinations per browser (320–1440 px widths).
WebKit `sequencer-ui.mjs` also passes its mock-host desktop/mobile, Verse note
visibility and offset-loop navigation checks. `git diff --check` passes.
[verified] The final behavioral regression fails against the unfixed exact
source at the Resume-label wait after 30 seconds (`final-red.log/json`), with
AudioContext running and label Pause. The fixed version passes without changing
this timeout.
Small logs and browser test summaries are retained in the evidence folder;
full geometry reports are private scratch.

The committed WASM used for the offline reproduction is SHA256
`609d4f4c9344ed210ef8797f02634b3d891d30e5e46e67e2fd9dc0356dd57fca`.
It is not a new source-equivalent C/WASM build and does not replace release CI.

Rarefaction status selected the shared main checkout, not this isolated exact
head. A test-position query returned an uninformative module result; the main
sequencer position mapped to different code. Absolute worktree scope was
rejected as outside its fixed workspace. Serena initial instructions/config
were checked without changing its shared project; an absolute find_symbol
located isolated `makeSequencer/updateTransport` correctly (lines 430–464).
Pinned-source inspection and caller searches supplied the authoritative context.
No graph was present or built. Actual Chrome UI access and owner visual
acceptance remain outside this offline Playwright check.

All jobs use Aeon CPUs 4–7, max 4 CPU/6 GiB, docker-batch.slice, unique session
labels and --rm. Source staging and npm dependencies are reproducible and will
be removed after logs are retained. The isolated source worktree stays for the
coordinator until integration; it must be removed after merge.

## Contribution candidate

The reduced WebKit case is a candidate browser-engine report: updating a button
with identical text during a native pointer press suppresses click delivery in
WebKit 26.6 (Playwright 1.63.0 Linux noble image). Private `reduced.mjs/log`
preserve the five control variants and exact outcomes. No upstream issue,
comment, PR, or other message has been posted. Any contribution needs the
owner's sign-off and the oss-contributions workflow; local release repair is
the current scope.
