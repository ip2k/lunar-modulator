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

## Render settlement checkpoint

[verified] Repair `4e178cc1b48f292b838804ce71d880d0741f92e4` is pushed and
remote SHA verified on `fix/2026-10-12@browser-render-settlement`.
The release guard now handles a non-Node Window target. UI contracts wait for
MIDI pitch visibility, rendered note step/gate plus idle before measuring the
next drag handle, and rendered automation lock value plus idle before keyboard
editing. Canonical assertions remain unchanged. No pre-blur, fixed delay or
navigation settlement was added to the native race regression.

[verified] Candidate native, fit-grid, playback and three MIDI harnesses passed
all three browsers (18 gates). UI passed the former edit failures, then all
three reached the compact-cell assertion and failed107/107/111px. These are
retained in `results-settlement`; final21 acceptance awaits the layout owner's
CSS correction and an exact combined-source rerun. The Wasm binary hash and
both source hashes exactly match its metadata record.

## Final combined acceptance

[verified] Combined product/test candidate `65a55fdd98c1d40e5390822118bd7a3e750b36bc`
incorporates the compact track header and full summary tooltip. Its `sim/web/www`
and `sim/web/test` diff against integrated root
`7fc4267b3888504009ca7bb1d62f463a1880af8c` is empty. The preceding compact
candidate `dd8263cb0c679e21f38f5b6b3e0b10320d12c830` passed all 21 canonical
browser gates. The tooltip candidate passed 20/21; WebKit playback measured
before the dynamically injected sequencer stylesheet loaded.

[verified] A bounded diagnostic delaying that stylesheet 150 ms reproduced the
same strict fill assertion: position `static`, opacity 1, z-index `auto`, fill
17 px high and zero width, versus styled `absolute`, opacity .18, z-index 0,
56 px height and 50% width. An ordinary diagnostic also observed the initial
clock baseline moving as styles arrived. This is initial mock-fixture readiness;
production geometry below uses the loaded real editor. Repair
`5adcd5ba6fa111673dd27cbb8a988626a8e2ebea` waits for the injected link's sheet,
font readiness and two initial animation frames before measuring the baseline.
It changes no product source or assertions. All three impacted playback gates
and the 150 ms delayed-style WebKit regression pass after that repair.

[verified] Final acceptance is the 20 unchanged tooltip-candidate gate passes
plus the three repaired playback reruns. Each of Chromium, Firefox and WebKit
passes these seven canonical harnesses:

| Gate | Chromium | Firefox | WebKit |
| --- | --- | --- | --- |
| sequencer-native (14 cases) | PASS | PASS | PASS |
| sequencer-fit-grid | PASS | PASS | PASS |
| sequencer-ui | PASS | PASS | PASS |
| sequencer-playback-ui | PASS | PASS | PASS |
| midi-transport-ui | PASS | PASS | PASS |
| midi-map-ui | PASS | PASS | PASS |
| midi-map-project-ui | PASS | PASS | PASS |

The native gate retains the held-pointer resize/refresh regression and cleanup
assertions. Neither the rendered-edit waits nor stylesheet readiness pre-blurs
or settles the navigation interaction that exposed the production Firefox race.
Canonical note, automation, focus, geometry and MIDI assertions remain strict.

[verified] Powered Chromium with actual Wasm/audio worklet and native document
playback was separately measured at viewport widths 1440, 844 and 667. Every
cell and track header is 56 px high, clip-body control 48 px, pencil 28 px and
live translucent progress 56 px. Document width equals viewport width and no
page errors occurred. All three full-page screenshots were visually inspected:
scene summaries, routing fields and pencils have separate space; short landscape
views use the matrix's ordinary vertical scrolling. This proves real rendered
compactness rather than relying on the mock-host UI fixture. It does not imply
all matrix rows fit simultaneously in a 375 px-high viewport.

[verified] All 108 repository asset/test hashes match the isolated Hera stage.
Final local manifest SHA-256:
`93c2e11a7b5d94895f8fc9e7b90c439229c7c12cc2a4693ba3334b07d85a5421`.
Wasm metadata matches actual engine source hash
`1d4a8474ed97cdf99bbbdd810cf873de63db04130a6383d88431315c0eb87ab1`,
simulator source hash
`8488d3287b8c9da8624c0f73693e5e184de4fb1b757b7a50b52d4db2420bc20c`
and binary SHA-256
`761b18d3e9a676494a02e2d87867aa0eeab45bad6ab82062fad385a2f8bc2ebc`.
No native inputs changed during these browser repairs.

Receipts are retained locally under
`scratch/combined-browser-gates/results-final`, including
`matrix-final-accept/results.json` and `matrix-{1440,844,667}.png`; historical
failures remain in `results-dd8263`, `results-settlement` and initial `results`.
The stylesheet delayed failure log is `playback-style-delay.log`; the positive
receipt is `playback-style-delay-ready.log`. Isolated remote stage:
`/home/claude/mvave-fm1/editor-combined-final-20261012` on Hera. Tests used the
existing `lunar-playwright-audio:1.63.0` image and read-only dependency cache;
no infrastructure changes. The source/receipt branch is
`fix/2026-10-12@browser-render-settlement` and every checkpoint is pushed with
remote SHA verification.

Limits and next dependency: browser/native runtime proof is not owner listening,
physical touch or FM-1 hardware proof, GitHub CI, merge, deployment or deployed
reload acceptance. Independent identity review and final GitHub CI remain root
integration gates. Integrate the fixture repair and this receipt, compare exact
source/test hashes, then continue those gates before merge/deployment.
