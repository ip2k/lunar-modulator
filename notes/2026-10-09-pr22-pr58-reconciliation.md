# PR #22 and #58 reconciliation

Checked 2026-10-09 against `origin/main` at `9cfc46dc35c2fb859f22a1f5315f6990c415a099`, PR heads, and primary source metadata. This is a narrow disposition of the two old documentation PRs, not a new full documentation audit.

## Simulator dialogs

PR #120 (`f8d70df96e4ecd3b458018ed4c7f36a28d776d39`) merged into main at the recorded base above. Its CI was green across Ubuntu/macOS, Chromium/Firefox/WebKit editor-page tests, site/manual, engine variants and dongle firmware. No dialog-specific claims need porting from the old documentation PRs; the current simulator README/product claims were left untouched.

## PR #22 — do not merge the snapshot

PR #22 remains open at `82f4235c5caaed327be77e2942a551c233f1928b`, based on `64209e3`. Its 528-line HANDOFF rewrite describes the repository through PR #98 and a 2026-10-05 state. It includes obsolete work/status, hardware policy, test counts, branch names and open questions; it is not a safe merge unit.

There is a newer replacement in PR #109 (`c69f9af06cbf977d26285f724d8f8604976d7221`), which updates HANDOFF and the audit-remediation record and adds a current remaining-work ledger. PR #109 was still open when checked, and current main still had the older HANDOFF. Therefore #22 is superseded in intent, but it cannot be described as fully superseded in the integrated tree until #109 (or an equivalent current HANDOFF update) lands. Keep #22 open or close it only after that integration is confirmed; do not merge it wholesale.

## PR #58 — retain only current corrections

PR #58 remains open at `3629a358340ba120fb42e2acb6e0297c7a7b17b`, also based on `64209e3`; it edits 19 files and mixes useful historical corrections with October-5 counts, stage snapshots and recovery wording that have since changed. Its branch should not be merged or cherry-picked wholesale.

Two still-useful corrections were verified and ported here:

- `docs/06-movy-and-schwung.md` now distinguishes the inspected Movy commit `5627d51` from the v0.31.0 tag `675054f`. GitHub reports the inspected commit 38 commits ahead of that tag; `module.json` at `5627d51` says version 0.31.0. The same file now describes the FM-1's seven encoders and one MASTER pot, consistent with `docs/01` §3 and the named Felucca/fm1-nes sources.
- `docs/13-movy-port.md` now states both Movy tag/commit relationships explicitly: `5627d51` is 38 commits after v0.31.0's tag, and `9190e79` is 299 commits after v0.34.0's tag `7539028`.

PR #58's changed files were checked against current main. The old engine/reference-render and screen counts, CI snapshots and recovery/roadmap status are dated and were not copied. The old one-rule language in `docs/12-sequencer.md` still needs a separately scoped update to point to the current staged hardware policy; PR #58's version retains the obsolete blanket full-image-restore precondition, so it is not suitable. No changes were made to that policy here.

## Evidence and limits

- GitHub PR API: #22/#58 open, both based on `64209e3`; #109 open at the head above; #120 merged.
- GitHub Actions for #120 exact head: all required listed checks passed; Pages deploy was skipped as expected for a PR.
- GitHub API for `DimaDake/schwung-movy`: tag refs and compare endpoints confirm both commit distances; `module.json` at `5627d51` confirms version metadata.
- No hardware activity or build/test run was needed for these documentation-only edits.
