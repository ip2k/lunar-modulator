# Sequencer release fixes — 2026-11-01

Personal, non-commercial Lunar work. No hardware/device interaction.

## SS-01: playing Capture in an offset loop

[verified] The focused native regression failed before the fix at the captured
note tick assertion. An existing loop beginning at step 16 folded its absolute
playhead modulo the loop length, storing notes before the loop start. D11 then
silenced those notes. The default path now folds relative to the loop origin;
both Movy compatibility modes keep the previous expression.

[verified] `tests/test_seq_release_audit.py` compiles only the five sequencer
core sources and its small C harness. It passes 27 combinations of three offset
windows (including a non-bar length), three scales, and native/both compatibility
modes. Native cases also assert playback of the captured note on a later lap.
Command: `.venv/bin/python -m pytest -q tests/test_seq_release_audit.py
--basetemp=scratch/seq-release-pytest` (the project venv from the primary checkout
was used; system Python has no pytest). `git diff --check` passes.

[verified] Source edits and tests are isolated in
`~/.codex/worktrees/lunar-sequencer-fixes-20261101`, branch
`fix/2026-11-01@sequencer-capture-release`, based on `b831724f`.
This is a host correctness regression, not pi32v2 code generation, physical
performance, audio/listening or device acceptance.

Lifecycle: native test executables and pytest data stay under this lane's
`scratch/`; remove them after recording results. Keep this note and the private
audit/handoff records. Remove the worktree after coordinator integration and
verified GitHub backup, using ordinary git worktree removal.
