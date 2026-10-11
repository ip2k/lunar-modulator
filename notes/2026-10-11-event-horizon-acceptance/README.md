# Event Horizon e608 acceptance receipt

This receipt is for the frozen `e608ad855fd4934d25fc55c4df6985fe8d2422a8`
source snapshot. Native/Wasm used the recorded renderer and module hashes in
`receipt.json`; browser checks used the integration worktree's read-only
Playwright harness and those same committed web artifacts.

The browser harness passed for all four projects: each was listed, played,
downloaded as a `.lunar`, and reopened in a fresh browser context. Its detailed
result is copied to `browser-demo-files.json`; screenshots and downloaded
files remain in the dated aeon scratch path recorded in the JSON.

This historical e608 native/Wasm attempt passed the full Afterglow Relay render
and then stopped on Event Horizon after reporting one load-save repair. The
initial Arp-default explanation was not isolated and should not be treated as
confirmed. A later run with explicit disabled Arp records still reported one
repair. Source inspection then found Event Horizon's 314-character `about`
text exceeded the state format's 240-code-point limit; truncating that field to
233 characters eliminated the repair. The complete follow-up run is recorded in
[the final acceptance receipt](../2026-10-11-event-horizon-acceptance-final-8efb1b7/README.md).
The original WAV files and browser screenshots remain in the e608 aeon scratch
path; the first attempt remains preserved here as a historical failure.

The result is diagnostic for the old eight-scene Event rewrite only. It does
not make that arrangement a showcase candidate: the current collection brief
requires four showcase songs with distinctly different tempo/feel, drums,
instrumentation, hooks, harmony and scene topology. A later source critique
found a repeated Trio G4 retrigger, shortened Acid gates in the later halves of
the drops, and deliberate overlap details needing musical review. Preserve
these findings; do not waive them to call the track accepted.
