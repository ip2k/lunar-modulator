# MIDI and Song workspace implementation

Owner-authorized endpoint: standard MIDI import, native clip/scene/song editing,
parameter-lock automation, sound/master mixing, `.lunar` and `.movy1` exchange,
and actual-engine stereo master, sound stems and eight-channel WAV export,
tested, reviewed, merged and deployed to GitHub Pages. Four stereo sound stems
form the multichannel file; eight sequencer-track stems are also offered.

Branch: `feature/2026-10-11@midi-sequencer-workspace`, starting at `b335dc2`.
Managed checkout: `~/.codex/worktrees/midi-sequencer-workspace/mvave-fm1-firmware`.
This is a work-in-progress checkpoint, not acceptance or a deployment.

The Song workspace edits the native Movy sequencer model: eight tracks routed
to four sounds, eight scene columns, 64 scene presses, and 96 ticks per quarter
note. MIDI type 0/1 imports preview instrument mappings and unsupported data;
capacity overflow, unsupported meters and unknown set extensions are refused
instead of silently dropping events. Native shadow import/export is compared
before an editor transaction replaces the running project.

Evidence so far [verified]: 23 parser/model tests pass, including native Wasm
round trips. Offline Wasm render tests on Hera pass deterministic finite song
length, unused-stem silence, track isolation, exact eight-channel interleave,
FM6/inserts/arp/modulation and separate master-effect processing, cancellation,
and WAV header/PCM/bounds checks. The complete existing container build passes
108 Wasm/native parity scenarios and the 30-second edit storm with zero late
quanta. These checks do not establish browser UI or owner listening acceptance.

Further evidence [verified]: real Chromium/Wasm integration passes native
note/gate/microtiming/probability edits, lock serialization, routing/repeat
undo/redo, clip-matrix transport, MIDI batch preview/refusal/replacement, text
and binary project reopen, set reopen, stale-document/atomic-hash refusals and
six real Worker WAV downloads. Five stereo files and one eight-channel file
have matching 44,118 Hz, 24-bit headers and one-pass frame counts. Desktop and
390-pixel mobile screenshots have been inspected; internal matrix/piano-roll
scrolling is deliberate. This is browser automation, not physical touch testing.

Native insert/master/mixer automation and its focused test are implemented.
Correct RAM accounting exposed an existing near-budget modulation fixture;
Room replaces Plate in that fixture while keeping its routing coverage and the
strict budget. The final rebuilt module has SHA-256
`b98e8e3295dba072a65d2d49bd5e1b3d57afc63ce2b2aa33027202e1d7c8c258`.
It passes 108 parity scenarios (all identical to JavaScript and musl), plus the
30-second edit storm: zero late blocks, p99 0.1402 ms, maximum 0.3050 ms.
Native web/mod/multi/automation regression: 281 passed, with two staging-only
asset/staleness checks excluded and covered separately by the complete rebuild.
Chromium, Firefox and WebKit real-module workflows pass; exact final-module
browser reruns, independent review, required CI, merge and deployed deep-link
proof remain outstanding. Current source checkpoints are not deployment proof.

Device boundary: `.lunar` and `.movy1` remain the same portable native formats.
The owner's FM-1_092 does not run Lunar; direct device project exchange requires
a running Lunar firmware and transport implementation. No device load or flash
operation belongs to this editor checkpoint.

Orientation: Rarefaction's bounded TypeScript query of `startEditor` and Serena's
C symbol lookup succeeded on the primary checkout. Serena had no TypeScript
backend, reference results were incomplete, and the managed feature worktree
was inspected directly rather than retargeting another active shared session.

Design references: [Ableton Arrangement](https://www.ableton.com/en/manual/arrangement-view/),
[MIDI editing](https://www.ableton.com/en/manual/editing-midi/),
[Bitwig arranger clips](https://www.bitwig.com/userguide/latest/arranger_clips_and_the_browser_panel/),
[Standard MIDI Files](https://midi.org/standard-midi-files).
The UI and importer are original MIT code; these references inform the workflow.
