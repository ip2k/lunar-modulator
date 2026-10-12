# Final combined browser gates

[verified] Initial frozen source: `4ea4f304412a43684d6858c2d456c9e808fac86d`.
Hera stage: `/home/claude/mvave-fm1/editor-combined-final-20261012`.
Existing image `lunar-playwright-audio:1.63.0`, image SHA
`33166f11ada16ca296edd49fc5e6771972f0871357c20acf8bc1d1be398c0d5e`;
read-only dependencies from `editor-ci-accessibility-20261012/pw`.
No infrastructure changes or Wasm rebuild. Local receipts:
`scratch/combined-browser-gates/results` in this isolated worktree.

[verified] All 21 canonical runs completed. Native (14 cases), MIDI transport,
MIDI map UI and native MIDI map/project roundtrip passed Chromium, Firefox and
WebKit. Playback UI passed Firefox and WebKit; Chromium timed out waiting for
ArrowDown to update an automation lock after its pointer edit. Fit-grid failed
all three on Follow resuming after synthetic window pointerup. Sequencer UI
failed all three because Add note canonical count was observed before essential
note fields became visible. These failures remain acceptance blockers.

[inferred] Window pointerup passes a non-Node target to `root.contains`, throwing
and retaining pointer state. Add-note and automation edit tests need bounded
rendered settlement as well as canonical state settlement; this must be verified
without hiding the previously proven natural navigation race.

[verified] Supplemental powered native Chromium geometry at 1440, 844 and 667
shows body width contained but populated cells107px high, launch body99px,
corner pencil28px. Native screenshot inspection confirms expanded rows; the
compact56px minimum does not constrain actual shared editor row sizing. This
was sent to the layout owner. Stopped progress is hidden, so its zero rectangle
is not a fill-height failure. Supplemental first attempt used nonexistent
`.sq-matrix`; second attempt correctly found the107px row and failed its compact
assertion. `matrix-final-geometry` retains corrected observational receipts and
screenshots separately from those failed attempts.

Independent reviewer owns the broader131-control stable MIDI identity matrix;
canonical MIDI gates do not substitute that matrix. Browser automation is not
listening, hardware, deployment or GitHub CI acceptance. Next dependency:
coordinate source/contract repairs, obtain a new frozen source SHA and rerun
changed gates plus native navigation regression before final integration.
