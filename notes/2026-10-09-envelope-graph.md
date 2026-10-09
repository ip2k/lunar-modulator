# Delayed envelope graph — 2026-10-09

Owner requested a real time-domain envelope graph, nonlinear curves, a vertical
playhead and a faint output waveform, and explicitly requested a delay stage.
Branch: `feature/2026-10-09@envelope-graph`, managed full-code-audit checkout.

Implemented in source: D–A–D–S–R, Delay default zero, added Log and Smooth
curves without renumbering existing parameters or curves. Graph reads the DSP
segment/phase and newest active polyphonic voice. Sustain is an unbounded hold
region; the recent mixed audio has a separate labelled short time window.
This is simulator/panel code; no linked Lunar firmware or device verification.

Native kind/core tests pass (1,245,943 kind checks), including zero-delay sample compatibility,
monotonic curves, delay retrigger/release and ADR loop exit. Screen sweep first
caught 3px row gaps; corrected to at least 4px.
4621-screen layout sweep now has zero faults; saved stage/curve contact sheet
was visually inspected. Wasm/metadata rebuilt; all 104 parity scenarios, DX7
import, metadata and edit checks pass; 30-second edit storm has zero late
quanta. Envelope instance is 128 B; existing aligned rack/block sizes unchanged.
All 164 focused modulation pytest tests pass. Independent review found and
verified the fix for stale delay state when configuring custom segments, then
passed 27,000 exact zero-delay comparisons across modes, curves and retriggers.
No remaining actionable findings in that focused review. Final CI remains
required before merge.
Firmware bring-up is tracked independently in PR #104 and its linked
diagnostic note; this feature does not establish device execution.

First CI caught an omitted curve-name pin and absent container digests in the
direct build record. Both are corrected: the pinned fixture includes Log and Smooth, and the
build records the actual container digests and musl reference. All 104
scenarios match JavaScript and musl exactly; seven focused CI regression
tests pass. Chromium CI reported one 10 ms underrun (the test incorrectly labelled
0.01 seconds as milliseconds); the same
report occurred on the docs-only baseline branch. The bounded LAN Chromium
page storm passes with zero reported underruns; CI must still pass before merge.


The second CI checkpoint exposed three stale generated state examples. The
new Delay parameter must appear with its zero default in the canonical project
and modulation examples; the metadata example must also include the new curve
names, third page and 128-byte instance. Regenerated these through
`tools/state_examples.py --write` against the rebuilt default registry on aeon.
The state schema, codec and application-state suites pass in the Emscripten
container on aeon. This changes fixtures, not reader compatibility or DSP.
PR #103's durable browser-save correction merged at `ebc6690` after full CI.
PR #99 must merge before this branch, followed by a combined Wasm rebuild.
