# Audit remediation and firmware resumption — 2026-10-08

Owner authorized resuming firmware work and addressing audit findings.
Branch `fix/2026-10-08@firmware-readiness-audit`, branched from origin/main
64209e3 and integrating the recovery/audit record; firmware has not been
installed. Preserve stock boot/package components and bounded recovery.

Work order: validate and fix target/build guards and parser/bounds defects;
reconcile technical status; then prepare a minimal hardware application.
Remaining editor and P3 findings are tracked in the full audit; no blanket
claim that they are all confirmed or resolved. The platform evaluation
recommends a permissive bare-metal runtime for both GPL/permissive profiles;
no licence change is required or authorized by this implementation work.

## In progress

- Target compile failures: preserve reports but return failure after any profile fails.
- Compile provenance: dirty-input scope must match all staged source directories.
- Sequencer import: initialize the signed lane temporary on parse rejection.
- Modulation script: reject nonfinite numeric tokens before integer conversion.
- X0X exponent bits: define negative exponent shifts with unsigned arithmetic;
  remove corresponding sanitizer exemptions and verify audio parity.
- Manual builder: reject output overlapping source manual before deletion.
- IRQ-123 source guard: reject unverifiable nonliteral IRQ arguments.

Verification pending. Use the original checkout’s .venv Python for focused
Python tests; larger native/target builds use aeon batch containers.
Serena is activated on this worktree; Rarefaction currently indexes the
original checkout, so its orientation is context only and changed code
must be checked in this worktree. Neither index proves target ABI behavior.

Checkpoint: first corrections are saved, not yet accepted as fully tested.
Focused local run: 70 passed, 4 manual dependency skips; shell syntax and diff
checks pass. Added long-edit-output regression and fixed the edit dump’s own
truncation pointer arithmetic. Native sequencer/modulation/manual/edit suites
are running in aeon’s bounded 6 GiB batch container at
`/home/claude/mvave-fm1/codex-audit-20261008/src/audit-checks.log`.
Do not install a firmware from this checkpoint. Remote source contains these
uncommitted-at-staging changes; record final committed digest before target
firmware build. All unresolved findings remain in the full audit report.
