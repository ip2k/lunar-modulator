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
