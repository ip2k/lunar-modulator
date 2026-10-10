# Bounded cleanup audit — 2026-10-07

Snapshot: `64209e3`, compared with the previous audit's base `d781f07`.
All locations below are lines at `64209e3`, before the concurrent editor work.

This was a read-only, single-pass background audit. No source changed; no
build, hardware operation, test suite, commit, push or PR was performed.

## Scope and limits

[verified] Read `AGENTS.md`, `CLAUDE.md` and PR #74's audit findings. Enumerated
the own-source delta in `engines/`, `sim/`, `firmware/`, `tools/` and `tests/`,
excluding `third_party/` and fixtures. Mechanically scanned 331 changed
`.c`, `.cc`, `.h`, `.js`, `.mjs` and `.py` files for static functions/exported
helpers with no lexical consumers and Python imports with no AST loads.
The delta in these extensions is 84,251 added / 3,242 removed lines, net
81,009; this is a narrower extension-based count, **not** the previous
audit's source-line-count convention.

[verified] Rechecked mechanical candidates against snapshot source,
Makefiles, browser imports, tests and documentation. Read the relevant
sections of `editor/model.js`, `editor/chains.js`, `editor/sheets.js`,
`worklet.js`, `fm1-wasm.mjs`, `fm1_web.c`, and Python candidates. The unchanged
vendor-code includes were checked only to disprove false dead-code hits.

This is **not** an end-to-end audit of all 81,009 net new lines. DSP algorithms,
all persistence paths, firmware link guards, every test body and all remaining
old PR #74 owner-decision items were not read end to end. Do not reset the
CLAUDE.md/AGENTS.md full-audit mark on the strength of this pass.

## Definite low-risk removals

Each item below is [verified] unused in snapshot tracked source. Removal is
recommended as a small independent cleanup; none changes a C layout, a pinned
RAM figure or a firmware binary.

| Repository location | Candidate and evidence | Recommended check |
| --- | --- | --- |
| `sim/web/www/editor/model.js:416` | `defaultValue(p)` only returns `p.def`; no import, call, test or documentation names it. Whole-tree text scan found only its declaration. | Existing editor unit and browser suites; confirm the concurrent branch has not introduced a caller. |
| `sim/web/www/editor/sheets.js:14` | Imported `parseBlockKey` has no use in that module. `parseModKey`, `blockTag` and `isModuleSource` are used and must remain. | Existing phone sheets/menu browser coverage. |
| `tools/lunar_state.py:34` | `Fraction` import has no AST load or other reference in this tool. The independent canonical arithmetic in `tests/state_canon.py` still uses its own `Fraction`; do not remove that one. | State codec / whole-state tests. |
| `tests/test_app_state.py:21` | `GPL_MODS` is unused; retain `renderer`, a pytest fixture registration import, and `gpl_only`, which is used. | Existing collection/app-state tests. |
| `tests/test_gpl_switch.py:37` | Imported `GPL_MODS` is unused; tests choose each switch explicitly. | Existing GPL-switch tests for both settings. |
| `tests/test_engine_acid_bass.py:28` | `Path` import is unused. No tracked Python module imports this test module as a helper provider. | Existing Acid Bass tests. |
| `tests/test_engine_drums.py:28` | Imported `rms` helper is unused. The `"rms"` strings later in the file are JSON metric names, not calls to that import. | Existing drums tests. |
| `tests/test_seq_song.py:28` | Imported `run_script` is unused. Retain `seq_tools`, which registers a pytest fixture. | Existing song tests. |
| `tests/test_tools.py:6` | `pytest` import is unused; no marks, fixtures or raises calls depend on it. | Existing tools tests. |

## Concrete refactor candidates, separate from removals

1. [verified] Duplicate percent-to-Q14 conversion in
   `sim/web/www/editor/chains.js:25`
   (`toQ`) and
   `sim/web/www/editor/model.js:617`
   (`q14OfPct`). The production helper is used at chains.js:572–573, 592 and
   868; the exported model helper is currently consumed by editor-unit.mjs.
   [inferred] Consolidating on the model helper would reduce future drift.
   The operation order differs (`pct * Q14 / 100` vs `pct / 100 * Q14`), so
   preserve the production expression when consolidating and run the existing
   cable amount/offset round-trip tests. This is not necessary for the advanced
   editor feature and should not distract its implementation.

2. [verified] The mirror's rack-position bound at
   `sim/web/www/editor/model.js:503`
   hard-codes `8` although `setLayout` requires and sets metadata `POSITIONS`
   and the rest of the model uses that value. [inferred] `r.pos <= POSITIONS`
   expresses the existing layout contract and avoids a latent mismatch if a
   build changes rack size. Current metadata has eight positions, so this is
   behavior-neutral today. Run existing metadata/mirror tests; alternate layout
   support is an optional follow-up, not a reason to introduce a new abstraction.

3. [verified] `postRam` at
   `sim/web/www/worklet.js:204`
   allocates a new seven-word `Uint32Array` before finding the RAM figures are
   unchanged. It is called by `postEditor` at line 186, so there is an avoidable
   allocation on subscribed editor updates even when no RAM message is sent.
   [inferred] Reusing a fixed scratch array could reduce AudioWorklet allocation
   churn; keep the transferred `parts` array fresh and never reuse its detached
   buffer. This is a performance candidate, not proof of a measured dropout or
   grounds to claim an audio improvement. Validate live editor RAM notifications
   and eventually the planned browser audio harness before making such claims.

## False positives and intentional support retained

- [verified] The apparent single-use `rng`, `mod_note`, `mod_voice` and
  `eng_idx` in `engines/test/felucca_oracle.c:63–81` are consumed through
  its `#include "voice.c"` / other source includes. Do not remove oracle stubs.
- [verified] Header `static inline` helpers generally have real callers in
  other translation units; checking only the defining file would falsely mark
  many modulation and engine helpers dead.
- [verified] `renderer` imports in state and engine tests that have no AST
  loads register pytest fixtures and are deliberately marked `noqa: F401`.
  Do not mass-remove AST-only unused-import results.
- [verified] PR #74's previously uncalled `fm1w_get_param` is now called in
  `sim/web/test/editor-unit.mjs:127` and `sim/web/test/sysex.mjs:237`; it is live.
- [verified] `fm1w_unit_set_current`, `fm1w_unit_level` and `fm1w_unit_route`
  still have no tracked JS caller, but are exported by `sim.mk` and documented
  in `sim/web/README.md:280–282`. They are documented public test/host API,
  not automatic-removal candidates. Changing them needs an API decision.
- [verified] The shorter modulation-record fallback at
  `editor/model.js:505` and the `decodeMod` zero fallback for loop masks support
  an older module format. No evidence here establishes that no users or stale
  browser caches need that support. Retain until the supported-format policy
  is decided.
- [verified] The independent Python/C state implementations and independent
  reference renderers are deliberate correctness oracles, not duplicate code
  to consolidate during cleanup.

## Recommendation

[verified: follow-up branch] Applied the nine low-risk removals after
rechecking the concurrent feature branch. The fixture-registration imports
remain. The first two small model refactors can accompany that cleanup
if desired; defer audio allocation work until it has targeted verification.
Schedule a separate complete source audit for the still-overdue full audit,
without presenting this bounded pass as exhaustive.
