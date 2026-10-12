# Lunar Modulator · independent DAW design review

2026-10-11 · read-only critic · feature/2026-10-11@midi-sequencer-workspace · PR146

The redesigned mixer is ready for integration on the tested browser runtime. No remaining P0/P1 defect was observed. The density polish resolves the earlier Scenes, selected-note and inspector hierarchy findings. One first-screen landscape presentation refinement remains; it does not block tested functionality. Subsequent copy-only source review confirms the Arrangement singular-bar correction.

Eight MIDI tracks share four sound engines, insert chains and levels, plus Master. This review requests no unsupported per-track audio gain, pan or sends.

## Scores

Editorial scores from rendered interfaces; baseline → final, out of 10.

| Criterion | Baseline | Final | Reason |
| --- | ---: | ---: | --- |
| Clarity | 6 | 8 | Shared sound channels and distinct scene edit/launch actions are explicit. |
| Hierarchy and spacing | 4 | 8 | Essential note values and primary device parameters precede secondary controls; scenes use compact rows. |
| DAW familiarity | 5 | 8 | Five aligned vertical strips, gain readouts, device stages and measured meters form a recognizable mixer. |
| Interaction and accessibility | 6 | 8 | Keyboard faders, persistent disclosures, named meters and a focused dismissible inspector work in the tested runtime. |
| Mobile usability | 2 | 7 | The working landscape panels are usable; first-screen chrome still requires scrolling to faders and the roll. |
| Project identity | 7 | 7 | Audiowide headings and the restrained space palette remain coherent; the sequencer is primarily utilitarian. |

## Remaining findings

### P2 · First-screen chrome still delays the working controls

At 844×390, Mixer begins at y218 and Clip at y295. Full fader bottoms and the piano roll require page scrolling. The working mixer fits all five 140px faders after scrolling, and the refined Clip shows its essential note controls together with the roll starting at y232 in the working capture. This is a remaining presentation limitation, not an unreachable-control defect.

Next refinement: Consider moving the working panel into view on explicit landscape tab activation, with a compact persistent transport/navigation row. Preserve the 44px fader hit area and avoid making labels smaller.

Source: `sim/web/www/editor/sequencer.js:642; sim/web/www/editor/sequencer.js:672; sim/web/www/editor/sequencer.css:101`. [Screenshot](final/landscape-mixer-first.png).

## Resolved during the iteration

- Landscape task panels previously started around y463. Final panel positions: Scenes/Arrangement y226, Clip y295, Automation y293, Mixer y218. Scenes/Arrangement no longer duplicate the global scene selector row.
- Four form cards plus a detached Master became five aligned vertical strips. Desktop exposes eight MIDI routes and each sound/master insert input/output; the short-screen Routing & FX disclosure makes the working faders visible.
- Oversized Clip fields and orphaned scene tools were replaced with compact fields and a secondary scene/clip tools disclosure.
- Quiet sound-color stripes and previews distinguish routing identity from lavender selection and the active-playback outline.
- Compact scene rows now show two full tracks in the working landscape grid. Essential selected-note controls stay together; Microtiming and Probability are disclosed. Song inspector parameters precede credits/tools, and Files & export remains accessible inside the modal and returns on close.
- Arrangement entry header singular/plural copy was corrected after the captured native run; the one-line diff was reviewed against that exact snapshot.
- Offscreen inspector navigation became a bounded native dialog. The audit found Escape interception; root fixed it and this final run confirms dismissal and focus return.

## Checks actually run

- Actual native Wasm/AudioWorklet UI in isolated Chromium on Hera; 1440×1100 desktop, 844×390 landscape, 390×844 portrait. All five views rendered and visually inspected. No page errors or document horizontal overflow in the ten desktop/landscape combinations.
- 25 named peak/RMS meter elements sampled during sustained-note playback. Values change over time. Sound 1 post-level meter becomes Silent at gain 0 while its pre-effect and insert meters remain active; other sounds remain active. Master final-output meter becomes Silent at master gain 0 while master effects remain active.
- Sound 1 ArrowUp changes 50→51 and native fetchProject returns level 51; Home saves 0 (−∞ dB); End reaches 100 (0.0 dB). Master Home/End reach 0/100. Keyboard End on the view tabs selects Mixer.
- Routing & FX is collapsed by default in short landscape and reveals the devices when opened; aria-expanded becomes true. After scrolling the working mixer panel into view, all five full faders and meters fit in the captured landscape viewport.
- Inspector fits desktop and landscape (landscape top 16px, bottom 374px). Focus moves to Close; Escape dismisses, returns focus to the originating device and resets aria-expanded to false and restores Files & export to the toolbar.
- Selected-note Pitch/Step/Gate/Velocity remain visible while Advanced defaults closed. Enter opens Advanced; Probability55 native edit preserves disclosure state and field focus. Keyboard Enter on a scene edit opens Clip, focuses its tab and does not start playback.
- Focused read-only JS/CSS review found and implementation corrected footer reparenting, redraw focus and responsive disclosure state issues. Final Escape restores Files & export to the toolbar; resize synchronizes aria-expanded; the Routing & FX button retains focus. Resize and breakpoint listeners are removed on destroy; compact inspector behavior is scoped to Song.
- Portrait rotate instruction is visible in the first screen; the hidden hardware preview no longer precedes it. No playback/state-loss claim is inferred from a screenshot.

[Native results](final/audit.json) · [Desktop mixer while playing](final/desktop-mixer-playing.png) · [Landscape working mixer](final/landscape-mixer-working.png) · [Portrait](final/portrait-first.png)

## Limits

A subsequent one-line Arrangement bar-label correction was reviewed against the exact native snapshot; screenshots may show the earlier plural form. This is a design judgment and bounded runtime review, not an accessibility conformance certificate. Physical phone touch, screen-reader output, owner listening and FM-1 hardware were not tested. The six-pixel note resize affordance and small grid labels deserve a physical-touch pass; numeric controls provide an alternative. The preceding iteration passed sibling Chromium/Firefox/WebKit mock and native suites, including Firefox with a PulseAudio null sink. Fresh Chromium mock/native checks passed for this polish; sibling Firefox/WebKit reruns were still in progress when this report was saved. This independent report claims native Chromium execution only. Parent-reported build parity/storm and C tests were not rerun here. Nested grid scrolling is intentional; “no document overflow” does not mean every track/scene fits simultaneously.

## Applied guidance

Local Apple skill and cached layout, color, sliders, text fields and accessibility references; all four selected external SKILL.md files and their applicable references were read. HIG informed viewport adaptation, clear labels and keyboard alternatives; frontend-design informed identity; Vercel informed focus, names and responsiveness; UI/UX Pro Max informed density and mobile ergonomics; Bencium supplied the audit rubric. Bitwig provided a canonical mixer comparison. Their generic advice was adapted to the existing plain-JavaScript product and actual shared-engine model. No hooks or packages were installed.

[Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/) · [Bitwig Mix View](https://www.bitwig.com/userguide/latest/the_mix_view/) · [Anthropic frontend-design](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design) · [Vercel current web interface guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md) · [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/67803eac81607188194aea9842a723b89326d90d/.claude/skills/ui-ux-pro-max) · [Bencium design-audit](https://github.com/bencium/bencium-marketplace/tree/5de46a39b4640fa419560cd0b67e4c4b50dac802/design-audit/skills/design-audit)

## Reproducible snapshot

Audited frontend is the saved P2 polish on base d4e0b64019faa668a6eeae685777fe5587881e2f. Base remote SHA was verified earlier; incoming edits and current integration/backup status belong to root. This critic made no commits or pushes. Evidence is scoped to the following hashes in `sim/web/www/`:

- `fm1.wasm`: `f163c1b5799bb6109718993600df4c3f7884ffca055a2e4df558cc8007e65219`
- `editor/sequencer.js`: `8a3ae56a156ae23aa4c126ad3001ac5c3e78a0c83dd57c8dae21a9f8b8637fc6`
- `editor/sequencer.css`: `eac603871cb16dfc295d1f8c911f98f21f636c79bbc52c7202aeda3fad566e84`
- `editor/editor.js`: `9bfe19fdfa91a174f4fe540761a57d325466dbfa3e55b5ccbd3283dd6d4b7774`
- `editor/editor.css`: `c4b58595b95cd6a55a0741b4c21caeac5d102ba179e1d0add3a5bfcdcf0b10f5`

Subsequent copy-only source review: sequencer.js SHA-256 `899cdb0c870d0e8a5750b1b08ee2fe77202d22416620c1e00ff0a19137cf736e` differs only at line 299 to render singular “bar”. Screenshots and runtime evidence remain scoped to the hashes above.

Harness: `audit.mjs`; isolated Hera stage `/home/claude/mvave-fm1/daw-critic-20261011/final/src`; Playwright v1.63.0-noble container capped at 2 CPU/2 GiB, no exposed host ports. Initial stale-stage and old-selector attempts were corrected before the successful final run. `final-before-p2/` preserves the preceding verified iteration; `baseline/` preserves the incumbent captures.

Next dependency: root owns integration, code checks, commit/push/CI and any required owner acceptance. These scratch artifacts are git-ignored; preserve or move the report explicitly if permanent review history is desired.
