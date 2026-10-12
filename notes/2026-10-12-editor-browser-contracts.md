# Editor browser contracts and native popover Escape

[verified] The editor shell test originally opened the module Files menu while
`first-orbit.lunar` had automatically selected Song / MIDI. The Song Files menu
has a separate integration gate. The module shell test now selects Flow through
the sidebar before checking its module menus.

[verified] The Song shortcut harness used a retired `play` callback. The current
Play/Pause button calls `playPause`. Its focused Space assertion now checks that
callback increments exactly once, preserving detection of duplicate Song/native
keyboard activation.

[verified] Engine information uses the browser's native auto popover. Its queued
`toggle` event updates `aria-expanded` and positions the popover. Browser tests
now wait for those updates before asserting the state. This revealed a real
Escape defect: the editor's global handler cancelled Escape and switched to PLAY
before native popover dismissal. A Chromium reproduction recorded an open
popover, `aria-expanded=true`, keys in PLAY, and `defaultPrevented=true` after
Escape. The handler now leaves Escape to the browser while an editor auto
popover is open. Tests check dismissal retains EDIT, the next Escape switches
to PLAY, and menu dismissal retains EDIT and returns focus.

## Verification and remaining layout failures

[verified] `node --test sim/web/test/song-shortcuts.test.mjs`: 6/6 passed.
`git diff --check` passed. Hera ran three isolated 3-CPU/3-GiB containers with
`lunar-playwright-audio:1.63.0`, the existing Playwright cache, and a PulseAudio
null sink. All three `song-shortcuts-ui.mjs` runs passed. All editor Files,
popover, menu, and keyboard-mode checks passed with no console/page errors.

[verified] The complete editor test remains red because its layout gates expose
separate issues. Chromium passed 109/116 checks; Firefox and WebKit 106/116.
All browsers report the RAM control overflowing at 375 px and the title's
intentional ellipsis being reported as clipping by its ancestor `.ed-title`.
Firefox and WebKit also report RAM overflow in Workbench at 1440 px; Firefox
reports the CPU percentage overlapping the RAM label. These assertions have
not been weakened. The parent stream owns the remaining layout/probe work.

[verified] Tests used parent runtime source at
`bdc7ca81aca5aa3fc32b2f9eb060b86721922d51`, its pending MIDI clipping change,
and this branch's editor.js and two test changes. Parent editor.css SHA256:
`dd66889026b0f4413eef4bdcae51e7fb7d967e6a25d11efe668cc6654319d822`.
The branch begins at `8ff54529c6fbc2b341e389b22108ffba7d707aef`; it contains no
parent layout/MIDI changes and is ready for a focused cherry-pick.

[verified] Durable receipts are under this worktree's ignored
`scratch/browser-contracts/`: `results-base8ff/`,
`results-current4f8-before-escape/popover-proof/`, and
`results-with-escape-fix/` contain reports and screenshots. The same receipts
remain on Hera in `/home/claude/mvave-fm1/editor-browser-contracts-20261012`.
`handoff.md` records the runner and recovery details. These browser checks do
not establish owner listening or physical MIDI/FM-1 acceptance.

## Resource layout and bounded ellipsis repair

[verified] The follow-up repair keeps RAM/CPU values from shrinking below their
content width and applies compact toolbar controls to the actual editor column
through an inline-size container query. This covers Workbench columns inside a
wide viewport as well as phones. Narrow header padding and spacing retain all
controls at 375 px with CPU `100.0 %` and RAM `100 %`. Menu glyphs use the parent's
`data-menu` identity rather than child position, preserving Simulator / Files /
Changes icons after the action reorder. No further editor.js changes are in
this repair.

[verified] The text probe now bounds only effective horizontal ellipsis text to
its own rendered box. Ancestor containment, vertical clipping, ineffective
ellipsis and actual controls remain checked. Native fixtures prove an intentional
title and its neighbor do not produce false clipping/overlap while oversized,
vertically clipped and ineffective ellipsis still fail.

[verified] Compact checks cover 20 layout/view/size cases per browser: Song and
Flow at 1440x900, 1024x768, 844x390, 667x375 in Editor and Workbench; 390x844 and
375x812 in Editor. Every case stresses peak resource text and checks contents
inside meter controls, all toolbar controls inside the header, a single action
row, title/sidebar/Keys separation, viewport width and menu containment.
Screenshots were inspected at 375 px and narrow Workbench at 1440 px in Firefox
and WebKit. The earlier containment assertion only checked values within their
controls; screenshot review exposed controls escaping the header at 375 px.
Both the actual spacing and the stronger header-containment assertion are fixed.

[verified] A preserved Firefox panel-follow failure was a fixture problem:
`results-meter-before-container/firefox/editor-ui.json` records the KNOB2 row
absent before input (rowConnected=false, value=null, no chips), while the change
message arrived at 2 ms, generation advanced 4 to 5, and history recorded
`S2 Harmonics 0.30 → 0.33`. The fixture now selects the current panel sound and
waits at most five seconds for its connected row and settled editor before
starting measurement. The observer resolves the current registered row each
frame, allowing legitimate redraw replacement without treating an absent row as
a successful value update. The <=12-frame delivery acceptance is unchanged.
Synthetic observer checks retain 24-frame late/deferred results, 60-frame missing
delivery, cleanup, replacement, and temporary absence (6/6 pass).

[verified] The current-Wasm matrix used parent source
`ef55216b47b7f55eca96609af347fba31b332a06`, with this repair's CSS patch and test
files applied in the isolated Hera stage. The freshly rebuilt Wasm is 1,584,573
bytes. All three browsers passed the complete editor test (116/116 each), Song
shortcut integration, both layout-probe fixtures and all 20 compact cases.
Panel-follow measured Chromium 3 frames, Firefox 2, WebKit 1. The final editor-only rerun covering the temporary-row-absence guard also passed
116/116 in all three browsers: Chromium 1 frame, Firefox 2, WebKit 1. Reports
are preserved separately in `results-panel-guard/`.

[verified] Exact staged runtime SHA256 values:

| File | SHA256 |
| --- | --- |
| editor/editor.js | 6a60c946026b5f7596634e2aea9778fbc767f5fccc92c18e4d174958e5cb2e24 |
| editor/editor.css | 8d032b49cd0bb1cdb0887a99d8fddda4f9f246b9a04b2e6dd9c5683febac645d |
| midi-map.js | 75ca2b939e03cfc51e17172f41f64a7f6fd73a678ae0622e4fb27a6f243af0f9 |
| fm1.wasm | 761b18d3e9a676494a02e2d87867aa0eeab45bad6ab82062fad385a2f8bc2ebc |

[verified] Final receipts are saved under ignored
`scratch/browser-contracts/results-final/` (reports, logs and compact screenshots)
and on Hera at `/home/claude/mvave-fm1/editor-browser-contracts-20261012/results/`.
Historical failures remain in `results-meter-before-container/`; the intermediate
passing run remains in `results-meter-container/`; the stricter header run in
`results-header-containment-before-panel-fixture/`. The shared Rarefaction/Serena
sessions select the primary checkout rather than this isolated worktree; they
were not switched or restarted. This bounded repair used direct source and native
browser verification. Exact integrated-head review and CI are the parent's next
acceptance gates; these tests do not prove owner listening or physical MIDI/FM-1
acceptance.

[verified] The compact screenshot's former fixed 100 ms delay could capture six
stale scene columns after switching from Editor to Workbench, while the native
mirror/state.busy resize was pending. A bounded WebKit probe measured content
498 px and six columns at 100 ms, then two columns at 1 s with the same content
width. This is a transient screenshot fixture issue, not a persistent source
layout defect. The final compact fixture waits at most five seconds for the
rendered scene-column count to match the existing grid capacity calculation for
actual content width, skipping the hidden portrait editing grid. Original stale
screenshots are preserved; final settled screenshots and bounds are in
`results-settled/`. No sequencer source changes were made.

[verified] Final settled compact reruns passed all 20 cases in Chromium, Firefox
and WebKit. The 1440 px Workbench scene grid renders two 164 px columns in all
three reports. An initial standalone Firefox attempt omitted the required
PulseAudio setup and timed out at the transport Pause precondition, before any
layout measurement; its log is retained on Hera as
`compact-settled-firefox-no-pulse.log`. Rerunning with the same PulseAudio null
sink as the full matrix passed. No assertion or source was changed for that
runner omission.

[verified] Inspected final peak-value screenshots (paths relative to
`scratch/browser-contracts/results-settled/`):

- `webkit/compact/toolbar-editor-sequencer-375x812.png`
- `firefox/compact/toolbar-editor-flow-375x812.png`
- `webkit/compact/toolbar-workbench-sequencer-1440x900.png`
- `firefox/compact/toolbar-workbench-flow-1440x900.png`

[verified] These confirm the narrow header fits and the settled Workbench scene
names/actions have their own space. `scene-width-probe.json` preserves the
100 ms versus 1 s native grid observation. Unit checks for panel follow and Song
shortcuts passed 12/12 together; syntax and `git diff --check` passed.
