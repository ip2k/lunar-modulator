# Automatic integration and demo prerequisites

Owner, 2026-10-09: merge all completed work automatically from now on and
start the demo songs if prerequisite work is out of the way. The identical
policy is saved in AGENTS.md and CLAUDE.md. No CI/review gate is waived.

Integration starts from remote main c35dbadc39bd77f182c1bd34599cc1717394a477,
the verified merge of resampler CLI bounds PR106. The primary historical
editor checkout is left untouched; current integration uses the managed
completed-work-integration worktree and branch
chore/2026-10-09@completed-work-integration.

Merged and verified on remote main: PR106, PR108, PR115, PR119, PR122,
PR124, PR111, PR101, PR112 and PR116. The latest verified remote main is
67d5e12dee561abca5d0a2256fec85d75522a806. This includes the delayed-envelope
graph and curves, offline firmware preparation, and bounded audit fixes.

Pending: integrate the combined Warble effect build;
resolve browser test failures for the information dialogs, native screen
preview, Picks history and semantic configuration; integrate the held-note
A/B correction (PR128); reconcile stale documentation PRs without restoring old state.
Rebuild and validate combined generated simulator artifacts after engine
changes rather than selecting conflicting binaries arbitrarily.

The demo brief and original Voltage-inspired transition plans are in PR121.
Four completed demo assets do not yet exist. Composition implementation starts
after its prerequisite streams are integrated. Offline firmware diagnostics
are preparation: no Lunar application has run on the FM-1, and no installable
release is claimed. Full-image/broken-app recovery remains a separate gate.

Recovery: use live PR state and exact-head checks, not this dated snapshot;
fetch origin/main before integration and preserve pushed source branches.

Active checkpoints: Warble PR123 requires a real combined Wasm/metadata
rebuild after PR101; A/B PR128 then needs the same integration. Information
dialog PR120 has the short-landscape control-size fix at f8d70df96e4ecd3b458018ed4c7f36a28d776d39,
awaiting exact-head CI. PR117 integration is pushed at a973087d3eab736e25b487ab8011f69d882fb6a1.
PR109 ledger reconciliation and the shared WebKit frozen-audio-clock
investigation remain active. No completed demo songs are claimed.
