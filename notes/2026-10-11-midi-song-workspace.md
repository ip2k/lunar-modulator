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

Outstanding: integrated Chromium/Firefox/WebKit/mobile interactions and visual
inspection; browser Worker downloads; native effect/master automation; docs and
CI wiring; independent review, required CI, merge, deployed deep-link proof.

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
