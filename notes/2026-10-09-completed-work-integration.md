# Automatic integration and demo prerequisites

Owner, 2026-10-09: merge all completed work automatically from now on and
start the demo songs if prerequisite work is out of the way. The identical
policy is saved in AGENTS.md and CLAUDE.md. No CI/review gate is waived.

Integration starts from remote main c35dbadc39bd77f182c1bd34599cc1717394a477,
the verified merge of resampler CLI bounds PR106. The primary historical
editor checkout is left untouched; current integration uses the managed
completed-work-integration worktree and branch
chore/2026-10-09@completed-work-integration.

Pending: merge green reviewed audit/firmware preparatory branches in their
dependency order; integrate the delayed-envelope graph and Warble effect;
resolve browser test failures for the information dialogs, native screen
preview, Picks history and semantic configuration; open/integrate the held-note
A/B correction; reconcile stale documentation PRs without restoring old state.
Rebuild and validate combined generated simulator artifacts after engine
changes rather than selecting conflicting binaries arbitrarily.

The demo brief and original Voltage-inspired transition plans are in PR121.
Four completed demo assets do not yet exist. Composition implementation starts
after its prerequisite streams are integrated. Offline firmware diagnostics
are preparation: no Lunar application has run on the FM-1, and no installable
release is claimed. Full-image/broken-app recovery remains a separate gate.

Recovery: use live PR state and exact-head checks, not this dated snapshot;
fetch origin/main before integration and preserve pushed source branches.
