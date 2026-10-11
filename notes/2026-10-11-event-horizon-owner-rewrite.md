# Event Horizon owner-directed rewrite

Status: composition in progress; this note records the owner's direct listening
feedback and implementation constraints before changing the generated project.

## Owner direction

The previous Event Horizon was rejected as too similar to Afterglow, overly wet,
shrill/busy in sound slot 3, and unclear in its hook and opening. The requested
rewrite should establish a recognizable hook immediately, make its foreground
voice and rhythm distinct from the other demos, reduce the drum level to about
60% of the previous balance, and make hats quieter. Sound slot 3 should use
Trio's `Saw x3` with a note-triggered filter-opening envelope. Sound slot 4
should use Acid Bass with the Square waveform and longer held notes. The
previous chained scenes, tempo and song form are constraints unless an audible
or state-format issue requires a change.

The owner supplied four reference URLs: Disclosure, “You & Me (Flume Remix)”;
San Holo, “Light”; The Chainsmokers, “Closer” (ft. Halsey); and Louis The
Child, “It's Strange” (ft. K.Flay). The titles were verified from YouTube
metadata. This work has not independently listened to those recordings; the
references are direction, not an asserted sonic match. Do not copy their
recordings, lyrics, MIDI, or presets.

## Source-backed engine constraints

- Trio (Felucca, GPL-3.0-only) has per-voice ADSR and `Env Amt`; NoteOn starts
  that voice's envelope and the bridge adds envelope amount to its filter
  cutoff. This supports note-triggered filter motion without a shared-rack
  retrigger. Set oscillator intervals intentionally. Velocity above 110 adds
  a fixed extra filter-opening accent, so the authored Trio events should stay
  below that unless a marked accent is desired.
- Acid Bass (fm1-x0x, GPL-3.0-only) has `Wave=Square` and a filter-envelope
  `Decay`, but no exposed amp Sustain or Release parameters. Its mono note is
  held by MIDI gate duration; note-off uses the engine's fixed release. A
  longer sequencer gate therefore sustains the held note, not the tail after
  note-off. Do not label its `Decay` as amp release. Both GPL engines must
  remain governed by the existing GPL build switch and must not be claimed as
  part of a shareable SDK-linked binary.
- Hall and per-sound sends will be reduced for clarity; settings will be
  checked in the emitted `.lunar`, not inferred from generator intent.

## Source navigation and validation boundaries

Inspected the generated project schema, `tools/demo_songs.py`, the engine
parameter documentation in `engines/README.md`, and the Felucca bridge and
Acid Bass interface descriptions. The current Rarefaction status was not ready
for a selected worktree and Serena still selected another agent's C++-only
checkout. Neither shared MCP was retargeted; implementation proceeds by direct
source, schema and test inspection, with that navigation limitation retained.

The Round-5 song critic applies to the previous frozen arrangements and is not
an acceptance claim for this owner-directed rewrite. Any updated critic review
must inspect the frozen new Event Horizon only. Runtime, memory admission,
browser save/reopen, and owner listening remain separate checks.
