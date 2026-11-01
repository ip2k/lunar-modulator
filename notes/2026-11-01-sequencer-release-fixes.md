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

## SS-02: queued lock target survives lane release/relabel

[verified] The original host regression reproduced missing base resets for four
release operations (`aclr`, `aclrs`, `aclrstep`, `clipdel`), text and typed
commands, and single/alternate sound-slot dispatch. The host resolved those
queued events through the already-erased current lane label.

Every emitted LOCK now carries its exact 24-byte label and 7-bit base value.
The host resolves that snapshot against the destination engine. Current-lane
UID getters retain their current-state meaning. Non-lock metadata is zeroed,
including MFX-created temporary notes. No serialized set/state schema changes.
Handmade LOCK events must initialize label/base as well as kind/track/lane/value.

[verified] The focused host test also queues an older audition, release/reset,
a different label and audition, another release, and reuse of the original
label with a different base, all before one dispatch. All four writes retain
emission order and original targets despite an empty final lane. It covers
text/typed inputs and single/alternate-slot dispatch with/without a real hook.
The alternate engine intentionally uses different UIDs/indices. Existing host
bridge regressions continue to pass. The two release-audit tests plus the native
track-name/arena persistence test pass under C99 warnings-as-errors (3 pytest
tests, each compiling only bounded sequencer/state sources).

[verified] `sizeof(fm1_seq_ev_t)` is now 36 instead of 12 bytes. The 272-event
buffer is 9,792 bytes (+6,528). Instance size stays 32,080 at eight tracks and
fits its unchanged 32,768-byte arena. Shared instance/events/command/UI/click
allocation is 43,156 bytes. The coordinator approved a 44 KiB (45,056-byte)
sequencer budget on 2026-11-01. Inline labels were selected over interning:
worst-case pending distinct labels require similar storage plus interning
lifecycle/overflow handling. Per-lane caches and UID/hash shortcuts cannot
preserve exact targets across repeated relabels or different engine slots.

App integration is intentionally pending: the coordinator owns `fm1_app.c/h`
and its handmade automation-test event constructor. This core branch updates
size expectations, but app aggregate/native-fit and app automation acceptance
must run after that adaptation. The private integration delta is under this
lane's `scratch/seq-release/`; this branch does not modify app.c/h.

[verified] Source storage review found no new event arrays on production stacks.
The existing private pipeline's two static PipelineSlot objects each grow by
6,528 bytes. Host render uses a vector and seq_tool uses malloc. Host walk_t's
existing temporary event grows by 24 bytes. Apple clang `-O2 -fstack-usage`
reports unchanged play_sink (240 B) and slots_ticks dispatch (320 B); sq_emit
remains 0 B. Optimization changes increase some core helper frames by at most
64 B (delete/paste/range: 48→112 B); fm1_seq_advance drops 480→464 B. This is
host compiler evidence, not pi32v2 stack/code-generation acceptance.

[verified] Follow-up validation: the first-bind case also dispatches a queued
lock correctly after release with no prior engine bind/target cache. Both
Capture and the full host bridge harness pass AddressSanitizer +
UndefinedBehaviorSanitizer with `-O1 -DSQ_CHECK_INDEX`. A negative control that
restores only the old current-label host lookup fails as expected. The exact
36-byte event layout is asserted in the focused arena test.

[verified] `make -C engines -j2 build/fm1-seq build/fm1-seq-check` passes without
building the DSP engines. Fifteen selected existing core tests pass: memory,
linear layout, D6 release behavior, native/compat block-size event identity,
and Movy fixture roundtrips. Their session fixture was replaced in-process
with the already-built CLI path to avoid its unrelated default all-DSP build;
the selected test bodies and expectations were unchanged. The command record
and logs are retained privately under `scratch/seq-release/checks/`.

[verified] A native header-only sizeof probe measures app size
4,953,584 → 4,960,112 B (+6,528), host bridge unchanged at 400 B, and event
arena 3,264 → 9,792 B. The new app size exceeds the existing 4,960,000-byte
host test guard by 112 B; the coordinator must review that guard when adapting
the app. This is the desktop app's large arena layout, not FM-1 RAM use.
The two PipelineSlot static objects mentioned above exist only with
`FM1_APP_RENDER_PIPELINE`; their combined growth is 13,056 B.

Remaining acceptance: coordinator app snapshot dispatch/handmade constructor,
app FX/mix chronology regressions, intentional desktop guard update, native
aggregate RAM fit, full CI/review/integration. No builds were flashed and no
USB, MIDI, device reset/power or audio/listening acceptance was attempted.
