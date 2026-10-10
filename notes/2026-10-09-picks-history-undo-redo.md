# Picks-load history boundaries — 2026-10-09

The editor recorded repeated **Make B from the picks** project loads as one
history entry when they targeted the same A/B scope within 600 ms. A picks
entry carries a structural undo snapshot and a `reload` file for redo. History
coalescing updated the merged entry's after label, while the caller replaced
its snapshot with the state before the second load; the reload payload remained
the first selection. Undo therefore stopped at the first selection, and redo
reloaded that same first selection.

The `editor-unit.mjs` regression reproduces two picks loads 500 ms apart on the
same project scope. It checks the two undo boundaries (state before the second
load, then state before the first) and each redo payload, including the exact
second selection. It failed before the fix with one entry and both redo steps
loading the first selection.

`History.record` now keeps structural entries separate whenever either the
incoming or preceding entry is structural. This preserves their per-operation
snapshots and redo records; value edits retain their existing 600 ms merging.

Verification: `node sim/web/test/editor-unit.mjs sim/web/www` passes all
checks. No browser run was performed; this regression exercises the history
contract directly, and the existing Playwright editor suite requires the LAN
container documented in `sim/web/build-on-aeon.sh`.

Integration checkpoint, 2026-10-09: merged current main 67d5e12d into this
branch without conflicts. The combined editor unit suite passes with zero
failures, including the repeated-Picks regression and the panel-follow changes.
PR118 now targets main. Full exact-head CI is required before automatic merge;
the previous WebKit frozen-clock failure is not waived by this unit result.
