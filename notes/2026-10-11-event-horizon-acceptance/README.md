# Event Horizon e608 acceptance receipt

This receipt is for the frozen `e608ad855fd4934d25fc55c4df6985fe8d2422a8`
source snapshot. Native/Wasm used the recorded renderer and module hashes in
`receipt.json`; browser checks used the integration worktree's read-only
Playwright harness and those same committed web artifacts.

The browser harness passed for all four projects: each was listed, played,
downloaded as a `.lunar`, and reopened in a fresh browser context. Its detailed
result is copied to `browser-demo-files.json`; screenshots and downloaded
files remain in the dated aeon scratch path recorded in the JSON.

Native/Wasm execution passed the full Afterglow Relay render and then stopped
on Event Horizon because its source needs one load-save repair. The Wasm loader
reported status `ok` and 39% estimated RAM; a source/runtime diff showed the
runtime inserting its disabled default `arp` MIDI effect where each sound had
an empty `midi_fx` list. The harness expected zero repairs, so this remains a
failed canonical-state gate, not a pass. The other three song renders were not
reached. The WAV files and browser screenshots remain in aeon scratch under
`/home/claude/mvave-fm1/demo-event-e608ad8-20261011/lunar-event-e608ad8-20261011`;
their hashes and paths are recorded in the JSON. This repository note does not
claim native/Wasm completion, hardware execution, or listening approval.

The result is diagnostic for the old eight-scene Event rewrite only. It does
not make that arrangement a showcase candidate: the current collection brief
requires four showcase songs with distinctly different tempo/feel, drums,
instrumentation, hooks, harmony and scene topology. The independent critic's
source review also found a repeated Trio G4 retrigger, shortened Acid gates in
the later halves of the drops, and deliberate overlap details needing musical
review. Preserve these findings; do not waive them to call the track accepted.
