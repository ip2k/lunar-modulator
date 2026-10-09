# Remaining work ledger — 2026-10-09

Read-only reconciliation against `origin/main` at `3c7b6a0` (PR #100 merged) and the open editor PR #99 at `861b725`. This note is a status ledger, not a new code audit. No tests, builds, or device traffic were performed.

## Done

- **PR #100 / audit remediation is merged.** The full source audit is recorded in `notes/2026-10-07-full-code-audit.md`; `notes/2026-10-08-audit-remediation.md` records the implemented fixes and verification. Target object coverage is 164 unique objects/profile, but there is no linked installable Lunar app. Full-image restore, broken-app recovery and Lunar firmware on the device remain untested.
- **PR #99 implements the four deferred editor decisions** from `notes/2026-10-06-web-editor.md` §29: Enter/Shift+Enter search behavior, Map cable create/reconnect from either end, Squash closed-gate readout, and refusal of effects on engine-less sounds. The branch also fixes the audited repeated-picks undo/redo mismatch by retaining the resulting reload payload. Its notes report native Safari interaction and external loopback captures in Chromium/Firefox/WebKit. These establish UI and signal-path checks, not the owner's by-ear judgement or physical FM-1 controls.
- The cleanup note `notes/2026-10-07-cleanup-audit.md` is a bounded dead-code pass, not the overdue full dead-code audit. PR #100's audit is not a substitute for that separate hygiene audit.

## Prioritized remaining work

1. **Complete public recovery/status documentation.** `README.md` still says the project has never written anything to an FM-1 (lines 31–36) and presents full-image restore as an unchanged installation gate (lines 358–369). The first statement conflicts with the verified bounded sector program/restore recorded in `HANDOFF.md` and the bench note; full-image restore and broken-app recovery are still unproven. `docs/05-open-source-feasibility.md` still calls recovery the unsolved gate in its opening; `docs/08-roadmap.md` still requires two full dump/restore cycles as Phase 2 exit. Update these reader-facing instructions to the current staged policy, and preserve the distinction between bounded-sector evidence and full recovery. `docs/10-usb-key-dongle.md` contains both newer bench references and an old “nothing else may be written” opening / 2026-10-01 “one rule” passage; reconcile or clearly mark that passage historical. Evidence: current `AGENTS.md`/`CLAUDE.md`, `docs/07 §4`, `notes/2026-10-07-fm1-softkey-bench.md`, and audit finding in `notes/2026-10-07-full-code-audit.md` §Batch 149.

2. **Finish and land the editor stream.** PR #99 remains open at `861b725`; its reported owner listening judgment is explicitly pending in `notes/2026-10-07-editor-audio.md`. The current main branch predates those changes, so all four deferred decisions and the repeated-picks fix are not yet in main. The audit's stale Search cable identity issue remains unfixed even in PR #99: `project.js` captures slot labels on Search open, then `applyBatch()` applies to the current slot without confirming it is still the captured cable (`notes/2026-10-07-full-code-audit.md` §Batch 19; PR branch `sim/web/www/editor/project.js`, `applyBatch`). Add a regression and reject/refresh stale cable targets before considering that finding resolved. Physical FM-1 touch/MIDI interaction remains untested.

3. **Resolve the browser persistence P2.** Failed IndexedDB writes can fall back to memory while the UI reports a durable browser save; the item can disappear from the library and be lost on reload. This remains in current `sim/web/www/files.js` on both `origin/main` and PR #99: `idb()` returns `null` on transaction errors, `put()` stores memory-only data, and `all()` returns database rows alone. See `notes/2026-10-07-full-code-audit.md` §Batch 5. Fix the save result/status and add transaction-failure coverage before calling editor persistence reliable.

4. **Keep firmware readiness separate from audit closure.** Next device milestone remains a minimal linked diagnostic application with a measured memory map, call-chain/stack budget, and runtime/audio-resource evidence. Current compile-only checks do not establish this; full-image restore and broken-app recovery remain open. The parent envelope-graph work is separately in progress and is intentionally not duplicated here.

5. **Licensing and mobile are decisions/plans, not missing implementation accidentally omitted.** `notes/2026-10-07-sdk-runtime-evaluation.md` recommends a permissive independent board/runtime if both GPL and permissive profiles matter; `notes/2026-10-08-audit-remediation.md` says runtime choice remains pending and no licence change is authorized. Keep the existing GPL boundary and do not present the recommendation as a decision. `notes/2026-10-07-mobile-advanced-editor.md` explicitly defers an iPhone editor until installable firmware; no app, relay, BLE stack, or hardware protocol has been selected or implemented. Recheck iOS API support and test real-device touch behavior only when resuming that work.

## Verified GitHub state

- `origin/main`: `3c7b6a0ad153eff2f80444af9b2830da2c280538` (PR #100 merged).
- PR #99: open; head `861b725bbe4efadb2d56400853a03b78f695f4cf`.
- This report is based on those snapshots and does not change either branch or merge status.
