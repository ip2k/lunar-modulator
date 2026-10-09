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
Firmware bring-up remains the independent minimal diagnostic application in
`2026-10-08-device-bringup-plan.md`; this feature does not complete that gate.
