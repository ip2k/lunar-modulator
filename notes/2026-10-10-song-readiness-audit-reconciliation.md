# Song readiness and audit reconciliation — 2026-10-10

This is a bounded status reconciliation of the audit findings relevant to
writing, loading, saving and rendering the four demo songs. It is not a repeat
of the full-code audit and does not close every P3 or legacy test gap.
The source dispositions below were checked against the named main baseline;
this pass did not rerun their individual test suites.

## Baselines and gate status

- `origin/main` was `40c94300428acfc5688a203c2c928723ed98270a` when checked.
- PR #142 remains separate at exact head
  `ef39b23869a9d06b19ad4478554792508d186d29`. Its GitHub workflow
  `38035944467` completed **failure**: Chromium editor page tests reported one
  playback underrun lasting 11.609 ms during the storm. The other jobs passed,
  including ASan/UBSan, 32-bit, GPL-on/off, macOS, Ubuntu, Firefox, WebKit and
  the Pages build. This failed gate is preserved; it is not waived. PR #142 is
  not part of `main`, and these notes do not claim its fixes are integrated.
- The fixes in #142 address unusual-input DSP robustness and the Gate delay
  contract. Their failing Chromium gate does not establish a defect in a
  normal-rate song or block composition using the effects currently on main.
  Keep #142 out of final song evidence until its exact CI gate is resolved.

## Previously blocking findings checked against current source

The following audit findings are resolved on the current main baseline, with
their regression coverage still present in source:

| Finding | Current evidence | Song relevance |
| --- | --- | --- |
| False IndexedDB “saved” result after durable-write failure | `sim/web/www/files.js` marks failed persistence as memory-only; the browser test suite covers file-save/library behavior. PR #103 is merged. | Resolved user-data risk. |
| Picks undo/redo restoring the wrong selection | `sim/web/www/editor/project.js` and `sim/web/test/editor-unit.mjs` cover two loads inside the history window and exact undo/redo state. | Resolved editor-history risk. |
| Search cable batch acting on a replaced target | `sim/web/test/editor-v1.mjs` retains the stale-target replacement regression; PR #99's correction is integrated. | Resolved editor-edit risk. |
| Malformed sequencer lane and non-finite modulation-script values | `engines/seq/seq_persist.c` initializes parsed lane state; `engines/host/mod_script.c::number()` rejects non-finite values before position/UID/seed/version conversions. The modulation view also rejects non-finite values before display/use. | Resolved malformed-input cases. |
| Comet kit change altering an active hit | `engines/src/comet_kit.cc` snapshots `hit_kit` per pad hit and reads that snapshot in `Apply()`. | Resolved playback-state risk. |
| Output truncation, manual path overlap and remote frame/path arguments | Bounded writer checks, manual path guards and the oracle-runner validation remain in their respective tools/tests. | Developer-tool safety, not song composition. |
| JieLi compile/IRQ guard false success | `tools/jieli/in-container.sh` exits nonzero for profile compile failures; `tools/jieli/audit_link.py` rejects unproven IRQ arguments. | Firmware build safety; no effect on song assets. |

Other targeted audit corrections already merged include unknown-MFX state-load
handling, DEFLATE completion/trailing-data validation, duplicate binary state
fields/UIDs, test-server traversal containment, Compare MID crossing pulses,
Movy run-length bounds, and room-oracle input bounds. Their historical audit
writeups remain useful for provenance but are not evidence that these old
findings are still open. This reconciliation does not certify every parser,
tool, vendored body, or P3 candidate as defect-free.

## Remaining work and its boundary

- No confirmed remaining audit finding in this bounded review blocks authoring
  original song assets against the already integrated project/editor schema.
  The four songs are not yet authored or accepted.
- When assets are added, generalize `tests/test_state_schema.py`'s current
  `first-orbit` filename assumption to validate each project stem while
  preserving `.sound`, `.fx` and `.rack` suffix rules. Bundle this with the
  demo assets; it is not a reason to postpone composition.
- Per-song acceptance still needs canonical browser project load, play/stop,
  save, reload and scene-chain checks, plus complete native/Wasm render
  evidence and listening. Existing `project-load-play` scenario coverage is a
  useful starting point; a rendered scenario alone does not prove the browser
  library workflow or a listening pass. The Sound2 crackle/A-B listening
  retest remains unresolved.
- Full-image recovery, broken-app recovery, FM-1 firmware installation and
  device runtime/audio/resource measurements remain hardware-readiness work.
  None is established by desktop/browser tests, and none is needed to compose
  or test the simulator songs.
- The full audit's other P3 candidates and stated vendor/provenance exclusions
  remain tracked in `notes/2026-10-07-full-code-audit.md` and its coverage
  ledger. This note narrows song readiness; it does not declare blanket audit
  closure.

The adopted text-only music production guidance is recorded separately in
[`2026-10-10-demo-music-skills.md`](2026-10-10-demo-music-skills.md). It is
preparation only, not a claim of completed or auditioned songs.
