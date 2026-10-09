# Delayed envelope graph — 2026-10-09

Owner requested a real time-domain envelope graph, nonlinear curves, a vertical
playhead and a faint output waveform, and explicitly requested a delay stage.
Branch: `feature/2026-10-09@envelope-graph`, managed full-code-audit checkout.

Implemented in source: D–A–D–S–R, Delay default zero, added Log and Smooth
curves without renumbering existing parameters or curves. Graph reads the DSP
segment/phase and newest active polyphonic voice. Sustain is an unbounded hold
region; the recent mixed audio has a separate labelled short time window.
This is simulator/panel code; no linked Lunar firmware or device verification.

Native kind/core tests pass, including zero-delay sample compatibility,
monotonic curves, delay retrigger/release and ADR loop exit. Screen sweep first
caught 3px row gaps; corrected to at least 4px. Remaining checkpoint work:
repeat layout sweep, inspect saved images, rebuild Wasm/metadata, run browser
parity and focused tests, update measured instance sizes and finish docs.
Firmware bring-up remains the independent minimal diagnostic application in
`2026-10-08-device-bringup-plan.md`; this feature does not complete that gate.
