# Arrangement controls browser review

Personal project. Review baseline `29029a3f7cb04ca380fba1bfa709723f83103538`,
isolated checkout `/Users/likwid/.codex/worktrees/arrangement-browser-review`,
branch `chore/2026-10-12@arrangement-browser-review`. Product source is parent-owned;
this branch saves validation only.

[verified] Existing `sequencer-fit-grid.mjs` and `sequencer-ui.mjs` pass on
Chromium, Firefox and WebKit on Hera. A supplemental canonical-host probe
passes the same grids with additional Arrangement screenshots and checks:
heading and pager share a row, no Selected label, menus stay horizontally
contained, and direct Song ending edits persist canonically (Stop, then Loop).

[verified] Visual review identified an additional vertical popup problem at
667 by 375: Add section extends below the viewport. Chromium popup bounds are
x322–502, y167.219–499.344; viewport bottom375. Section tools is an inline
expansion, x33–540, y212.109–283.953, fitting this viewport. Desktop1440 Add
popup y134.328–466.453 fits height1100. The existing suites do not check vertical
popup containment, so their green results alone do not establish this acceptance.
Parent is repairing the popup; final acceptance is pending that pushed source
and an affected-check rerun. No source or fixture assertion was weakened.

Receipts are ignored under `scratch/arrangement-review/`; remote stage is
`/home/claude/mvave-fm1/arrangement-review-20261012`, separate from all earlier
build/test stages. Local screenshots include
`results/chromium/arrangement-probe/667-sq-add-section-open.png` and desktop
open Add/Section tools and ending Stop screenshots. Supplemental scripts are
saved beside receipts. Actual app/Workbench and 844 landscape measurements
are in progress at this checkpoint.

Semantic status was checked again: Rarefaction and Serena select the primary
checkout rather than this isolated worktree. Shared selection remains unchanged;
source and actual browsers were used here. Native/Wasm sources are unchanged.
Checks do not establish final-head CI, deployed reload, listening or hardware
acceptance. Next dependency: parent popup repair SHA, then focused validation.

## Actual application measurements [verified]

The actual powered browser app was checked with the default project, using
PulseAudio null sink, in all three browsers. The 1440 by 900 Workbench has an
actual 498 px sequencer region. Its Add popup fits: x1193.7–1373.7,
y258.7–590.9. Section tools remains inline and contained (Firefox/WebKit
x913–1303.9, y303.6–357.4). At editor844 by390 Add spans y218.7–550.9;
at667 by375 it spans y210.6–542.8. Both landscape Add menus overflow the
vertical viewport. Inline Section tools fits at both (approximately
y263.6–316.5 and255.5–308.4). Representative actual Workbench498 and landscape
667 Section tools screenshots were inspected; no horizontal clipping was seen.
One Chromium Workbench tools measurement occurred during layout settling at
1102 px; the matching498 px Firefox/WebKit measurements are the width receipt.

Actual screenshots and bounds are under `results/{browser}/actual/`. The
initial supplemental actual-app script incorrectly combined explicit Power on
with auto-loading and later used an ambiguous layout locator; those probe errors
were corrected (default project and button-only locator). Product source and
existing suites were not changed.

## Final source gates [verified]

Final source under test: `a3ce09864b48ff8911befaca3ecde438caa2a9dc`.
Fresh detached checkout: `/Users/likwid/.codex/worktrees/arrangement-popup-validation`.
Fresh Hera stage: `/home/claude/mvave-fm1/arrangement-final-review-20261012`.
Chromium, Firefox and WebKit each passed `sequencer-fit-grid.mjs`,
`sequencer-ui.mjs`, and all 14 `sequencer-native.mjs` checks, including
real AudioWorklet/Wasm, native edits and responsive scene launch controls.
Local receipts: `scratch/arrangement-review/final/results/{browser}/`.

The supplemental powered probe had errors separate from product gates: raw
Movy snapshot data needed `parseSet`; a snapshot read during an open menu
could redraw it; an idle predicate expected literal aria-busy false instead
of its removal. It now reads snapshots before opening, waits the existing
native suite idle predicate, and uses current data-scene-launch selectors.
Earlier stages and failed attempts are not final-source acceptance.

Section tools is in flow, rather than a popup. With a populated entry,
Firefox/WebKit Workbench498 measures approximately507px toolbar width,
inside the outer panel/viewport. Parent accepts that extension when readable
and scroll-reachable; no redesign is requested. Native sources and Wasm
binary are unchanged. These gates do not prove final CI, deployment reload,
listening, or hardware acceptance. Parent retains those final dependencies.

## Powered final acceptance [verified]

Corrected supplemental probe passes all three actual browsers on final source
`a3ce0986`, at1440x900 Workbench498,844x390 Editor and667x375 Editor.
Add popup bottom is382 at844 and367 at667 (8px viewport inset), with
internal scroll height330–331 and visible height154–162. Scene8 is reached
by Playwright's real scroll/click and appended to native song state at each
size; the direct Song ending selection also reaches native Stop state.
Scene/clip launch icons precede names and clip controls without overlap.
Existing fit-grid confirms heading/pager alignment and horizontal containment.
Section tools controls are readable and scroll-reachable inside outer panel
and viewport; parent explicitly accepts their ~9px extension beyond the
498px inner grid. No product source was edited in this validation stream.

Chromium's supplemental screenshot could allow a pending redraw to close Add;
the final probe rechecks the disclosure and reopens it before clicking when
needed. Its successful native append is recorded separately from earlier
locator timeouts. Firefox/WebKit do not need that recovery in their receipts.
Representative screenshots actually inspected: WebKit1440 Workbench populated
Section tools and Scenes, WebKit667 Add, Firefox844 Scenes; latest final
Chromium667 screenshot also retained. Final JSON/logs and probe are saved in
`scratch/arrangement-review/final/`. Wav/download copies are excluded from
local artifact copy; original native gate artifacts remain on Hera.

Next step: parent integrates this note, performs final exact-head review/CI
and deployed reload after its documentation checkpoint. This receipt covers
only the source SHA above, not later source changes or perceptual/hardware
acceptance.
