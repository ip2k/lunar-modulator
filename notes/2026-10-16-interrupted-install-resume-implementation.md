# Explicit interrupted-install resume: injected diagnostic implementation

[verified: offline synthetic tests] Added `Policy.admit_resume(fresh_read)` and
explicit `resume=` binding to the generic diagnostic policy and injected SG
adapter. No opener, service endpoint, CLI, device operation or public installer
capability is added. Hardware admission flags remain false.

The capability accepts only durable `running`/`recovery_required` install
journals, seals the journal bytes, retains original policy/build/read/baseline/
target/receipt checks, verifies a fresh paired full-image read, and correlates
the stable physical USB port tuple with the original loader hash. This is port
correlation, not device authentication. New devnum and SG mapping are admitted
only from the verified fresh evidence. The transport's complete initial reread
must equal that fresh image SHA, and immutable ranges must match the original
baseline before any mutation. Core recovery rebuilds authorized sectors; it
makes no exact interrupted-operation-prefix attribution claim.

Original-read expiry is bypassed only by this explicit capability. Admission
checks paired-read freshness; each command observes a separate 1800-second
monotonic live-session deadline. Binding consumes the capability even if binding
fails, so reacquisition needs explicit fresh admission. Original and fresh
evidence are checked again at run and before mutation. No command failure
retries the disconnected handle.

Capabilities are frozen, process-local registered objects; dictionaries, copies,
pickle round-trips, other-policy capabilities and repeated binds reject.
No durable policy reopen factory was added: the existing prepare factory creates
a new transaction and requires fresh original inputs. Audit acceptance #6's
complete new-process sealed-policy reopen remains OPEN and needs a separately
reviewed design. This implementation must not be advertised as complete physical
interrupted-install recovery.

Checks: repository .venv Python, only
`tests/test_generic_diagnostic_flash.py` and
`tests/test_generic_diagnostic_sg_adapter.py`: 38 passed. Includes ambiguous
erase/program completion, simulated reconnect/full install/restore, running crash
journal, old-read expiry, stale fresh read/deadline, loader/port mismatch,
changed journal/original and fresh evidence, target/receipt tampering,
full-reread mismatch/immutable changes, forged/cross-policy/serialized capability
and consumed-capability rejection. `git diff --check` passed. No heavy build,
whole-suite run, USB/MIDI/power action or host operation occurred.

Semantic tools: Serena initial manual/current config and Rarefaction Python
status were queried. Both select `/Users/likwid/Developer/mvave-fm1-firmware`,
not this isolated worktree; Serena has only cpp active. Bounded orient and
symbol-overview queries for the relevant Python file both returned missing
file at that shared root. Neither shared project was retargeted or restarted.
File inspection and focused executable tests supplied source verification.

Branch: `codex/2026-10-16-interrupted-resume`; base
`d68f63965d6284113862dad158bba1f6eeed008b`.
Next: coordinator independent review, refresh downstream source allowlists as
appropriate, integrate through required CI/review. No production/hardware or
new-process reopen acceptance is claimed.
