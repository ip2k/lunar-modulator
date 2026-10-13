# Closed V8 staging verified

[verified] Rebound the prospective partial-recovery path specification and plan
to distinct V8 roots, updated its source-closure dependency pin, and resealed the
108-file main archive. Four activation pins remain None. Main archive SHA256:
64ae3ec7d15cc3bcecec23a4dcc0ffdaa3a1958ee70c568d275caec0fa7491e3.
Recovery archive remains byte-identical, SHA256:
83cb64143b8130f4764e953f7ef15eaca1b12c8803e922555aad12c6af2bce13.
Vendor-containing archives and the preserved-stage fixture remain private.

[verified] Ran actual staging helpers in 16 independent, network-disabled Hera
containers, one CPU and 1 GiB each, no USB devices. All 16 cases passed, terminal
exit 0, no OOM. Terminal inspections/logs retained at
/home/claude/fm1-v8-staging-16-20261012; all owned containers removed afterward.
Cases exercise successful staging, sealed-byte changes, wrong self pin, occupied
and symlink destinations, preserved-source corruption/symlinks/permissions,
archive symlink/directory, changed main tools and occupied recovery destination.
These execute actual file-only helpers; they do not exercise hardware flashing.

[verified] Executed both exclusive file-only stagers on bench01 as root. Main
stager verified 108 files (27 entry, 81 campaign) and 73 preserved original assets;
recovery stager verified 102 files. Actual destinations:
- /home/claude/fm1-sdk-trace-entry-20261012-v8
- /home/claude/fm1-sdk-trace-campaign-20261012-v8
- /home/claude/fm1-sdk-trace-partial-acquire-20261012-v8
- /home/claude/fm1-sdk-trace-partial-restore-20261012-v8

[verified] Separate read-only post-stage check verified all 108 main hashes,
regular files, root ownership and mode 0600, plus absence of fresh binding and
attempt artifacts. Staging receipts retain their original timestamps. No device
identity query, reset, erase, program, campaign execution or capture in this step.
No launch receipt installed; no gate opened. Source-only proposal is not physical
acceptance. Next: exact-head CI/source review, fresh identity binding and the
one-use diagnostic campaign; owner now available to observe the display.

[verified] Earlier CI38329476379 (c5029) macOS failure was a test-harness use of
Linux /proc/self/fd, not a firmware failure. Replaced descriptor identification
with stat identity in one test; all 57 wrapper tests pass locally on macOS.
Linux verification session66805 completed all57 tests in16 chunks, no failures,
errors, skips or OOM. Terminal XML/container inspections retained at
/home/claude/completed-trace-wrapper-portable-16-20261012; owned containers removed.
Receipt portable-wrapper-verification.json records exact tested source pins.
Serena remains cpp-only on the old primary root; actual-worktree Python symbol
query was rejected. Rarefaction also rejected the worktree path outside its root.
Used direct source inspection, without changing shared semantic-tool selection.
