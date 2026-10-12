# MIDI importer and editable sequencer model, 2026-10-11

Outcome: saved `sim/web/www/editor/sequence-model.js`,
`sim/web/www/editor/midi-import.js`, and `sim/web/test/midi-import.mjs`.
Shared branch: `feature/2026-10-11@midi-sequencer-workspace`; parent owns
checkpoint commits, pushes and integration. This subtask made no commits.

[verified] `node sim/web/test/midi-import.mjs`: 23/23 passing. Covers MIDI
formats 0/1, per-instrument/channel/program/bank mapping, source PPQN to
96 PPQN endpoint rounding, running status, repeated notes (including equal
pitch/onset), velocity-zero note-offs, sustain and channel-mode release,
program changes, tempo policy, batch synchronization, scene slicing and
retrigger warnings, deduplicated scene columns, complete metadata/SysEx
payload retention, parser malformed/truncated bounds, native pool refusal,
combined project capacity, and immutable application. Includes actual
`fm1.wasm` project import/export preserving every supported movy1 field
and duplicate note rows. `node --check` passed for both modules.
`git diff --check -- <three owned files>` passed (new files are untracked
until the parent's checkpoint).

[verified] Canonical `.lunar` `set` is a movy1 lines array. Model parses and
writes bpm/swing/link/key/dq/se/sn/sg/tk/pm/ps/au/rt/cl/cp/lk/tg. Note anchors
and hidden-tail data survive JS roundtrip. Unknown extension lines survive
JS write/export; MIDI application refuses unknown-tag models because native
reload drops the extensions. The host independently compares its candidate
native export against the source before replacing the live project.

Bounds: 16 MiB MIDI input, 256 source tracks, 250,000 events, 100,000 notes,
four-byte VLQs, 32-bit source absolute ticks; MIDI type 2/SMPTE refused.
Native planning: eight sequencer tracks, four sound routes, eight distinct
scene columns, 1–16 bars per column (256 steps), 64 song presses, 512 notes
per clip, 1,536 notes and locks, 256 trigs, and 64 simultaneous note gates.
Set write refuses more than the native 256 KiB file buffer. Oversize plans
are invalid and cannot be applied. Longer unmapped destination clips that
would change imported scene duration are refused.

Limits: constant 4/4 only. Tempo changes require explicit `tempoPolicy:
'first'`; notes retain musical positions and warnings explain elapsed-time
changes. Controllers, pitch bend, pressure and SysEx are retained as import
metadata/channel events but not applied as playback automation. Sustain is
baked into note gates. Cross-scene notes are split/retriggered with explicit
warnings; same-pitch overlaps may retrigger/release shared sound-engine
voices. Batch MIDI files start at their original tick zero. The importer
plans notes and engine routes; it does not select or create matching GM
patches. Native live-host checks and user listening remain integration gates.

Semantic tools: Rarefaction and Serena were checked on the existing primary
checkout, with matching bounded C export-symbol navigation. Neither tool
was reselected or restarted because another agent uses the shared session;
the absolute worktree was inspected directly. Rarefaction C navigation had
fallback signatures/zero caller results, so these are not semantic proof of
all callers, worktree freshness, or JieLi ABI.

Next dependency: parent should add the Node test to required web checks,
checkpoint/push the shared branch, review native host roundtrip refusals and
UI mapping/import behavior, then perform browser playback/export acceptance.
Parser/model scope is complete and frozen except requested bug fixes.
