# CI refresh/control preservation review

Date: 2026-10-11. Independent read-only review of the refresh fix and deterministic regressions on branch `feature/2026-10-11@midi-sequencer-workspace`, HEAD `069333cddd3dde8fbe0b73797f97add8a0a28ae4`. No source edits were made by this reviewer.

## Review result

The fix addresses the reproduced interaction race and preserves the prior test assertions. `readRevision` is captured before each awaited project read; invalidation during that read makes the loop fetch again rather than publish an older snapshot. Ordinary refresh skips DOM reconstruction only when the fetched document equals the last document successfully rendered. `force=true` retains redraw behavior after local edits and rollback. Fetches remain tied to explicit refresh/render or invalidation; hidden views invalidate and read on reopen. I found no lost invalidation, autonomous polling, or view-selection/state-edit regression.

I found and reported one malformed-snapshot recovery issue during review: the first draft cleared `dirty` before parsing and published `state.doc` before parsing succeeded. The final draft fixes both by leaving dirty set on parse failure and parsing into a local model before publishing `doc`, `model`, or `readText`. The added recovery regression verifies the error clears on retry and then opens Mixer to check the original instrument name, covering partial document publication.

The deterministic regression exercises pointer-down / unchanged refresh / pointer-up and select-all / unchanged refresh / type. It also delays an old snapshot, commits a native note, invalidates, releases the stale read, and checks the latest notes are rendered. The original undo/redo, native acknowledgement and visible/hidden synchronization checks remain intact.

## Validation and provenance

- `midi_model` reports all six sync checks passing in Chromium, Firefox, and WebKit against Wasm SHA-256 `2a2ad121431f6e7fac5aa186d00eb0b75848187441ffe0d4ec4222451ed65cc3`.
- Firefox native's 11 checks passed on the preceding dirty-state fix; a rerun against the final atomic parse edit was still running when this review ended. The final parse change is covered by the reported three-browser sync runs.
- I did not independently rerun Hera; its test runner is owned by `midi_model`.
- Final SHA-256: `sim/web/www/editor/sequencer.js` `2e18fff230c86ed8a771552b6969a2d7729268dcd45390d99ebed3fc2f30a0de`; `sim/web/test/sequencer-sync.mjs` `d4e0650314ebf282533c5a91fbe735aa127659c23087cb66d842249324ba54e1`.
- Prior actual-module reproduction is documented in `scratch/CI_FAILURE_HANDOFF.md` and `scratch/ci-sync-review/repro-results.json`: interrupted Automation click remained on Scenes and typing after refresh produced invalid `10072`.

## Next step

The refresh change and deterministic regressions are ready to checkpoint. Capture the pending Firefox native rerun result for final acceptance before declaring the browser matrix complete; root owns release and broader CI acceptance.
