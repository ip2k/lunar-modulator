# Hall feedback gain cache — 2026-10-15

[verified: source and host tests] Reviewed worker commits
`84084c07a9ea3198f55ed8f884b999224cbb57ad` and
`66c95bb2d413242d30dfdef0175156cb66bebbba`, integrated as `b94f3c36`
and `7b373489` on `feature/2026-10-11@installable-firmware`.
Remote feature SHA independently matched
`7b3734892f6f7758a13e88125813f4e205e99251` after push.

`Instance::Coefficients()` now caches each line's `g-h` in the former DC
gain slot. `Start()` calls it before rendering, and `Update()` refreshes it
when size, decay, damping or freeze changes. The render loop has eight fewer
source-level subtractions per sample; multiplication/addition order and
instance storage size are unchanged. No other production readers of the old
DC gain field were found. The old calculation is retained only behind a
test-reference define.

Root independently ran:

```sh
/Users/likwid/Developer/mvave-fm1-firmware/.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_engines_hall.py tests/test_engines_hall_inline_equivalence.py
```

All 43 checks passed. Differential O0/O2 tests compare output bytes and full
instance bytes at three sample rates, with parameter transitions, edge inputs,
silent spans and resumed input. Reference snapshots convert their DC gain
slots to `g-h` before comparison, then restore them, so the candidate's cache
itself is checked rather than omitted. Host tests disable fast math and FP
contraction. They do not establish pi32v2 instruction equivalence or speed.

Serena selected this absolute worktree and found `Instance::Coefficients()`.
Rarefaction still selected the primary checkout, lacked a compilation database,
and returned no meaningful call edges for the position query. Its result was
not treated as proof of absent callers; exact source inspection supplied the
initialization/update check. Shared server selection was not changed.

## Next evidence and unchanged gates

A bounded Hera target build/code-generation review is assigned to
`demo_controller_review`, using exact worker head `66c95bb2` (same source tree
as integrated `7b373489`). Verify instruction placement, FP contraction,
linked application/RAM fit and source receipts before considering a physical
campaign. No speed or hardware acceptance is claimed for this change.

No device commands were issued for this integration. Installed reference
remains `28483c411f23d7d5fba09b4770dd29b3c66b1a154138e493e6e079e54dcf400f`;
latest physical throughput remains 498.453 versus required 689.344 blocks/s.
Cold-boot listening failed; SAVE and autoplay remain off. The complete
thirteen-engine/default-song/persistence/recovery/web release goal is active.
