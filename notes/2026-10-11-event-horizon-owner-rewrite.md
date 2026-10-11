# Event Horizon owner-directed rewrite

Status: rewritten source and generated state are checkpoint-ready for review;
runtime and owner-listening acceptance have not been run for this revision.

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

## Rewrite checkpoint

The current generator keeps the original 144 BPM, 116-bar eight-scene chain
and rewrites the arrangement, engine palette and emitted clips. It uses Deep
drums, Six-Op E.PIANO 1 for the chord bed, Trio Saw x3 for the lead, and Acid
Bass Square for the bass. The progression is Fm9–Dbmaj7–Abmaj7–Eb6. A new
six-attack hook is stated in the opening and developed in the drops; the bass
uses long held roots/fifths; the drums use a half-time backbeat, varied pickup
kicks, quieter hats and restrained deterministic timing/velocity variation.
The four-bar build and break thin the texture before the drop. Hall mix is
0.05; echo and insert FX are disabled.

The source description calls this an original arrangement informed by the
owner-supplied tracks; it does not claim to reproduce them. The four URLs and
artist/title metadata are recorded above. No source was listened to in this
work session, so genre resemblance is unverified. The remaining three song
files and their browser copies were SHA-identical before and after generation.
The regenerated native and browser Event Horizon project files are byte-equal.

Checks run: `python3 tools/demo_songs.py --check` (nine generated files,
four project chains current), `python3 -m py_compile tools/demo_songs.py`,
`git diff --check`, and standard-library canonical parse/serialize of the
Event Horizon project. The configured system Python has neither `pytest` nor
`jsonschema`, so `tests/test_state_schema.py` could not run here. This is not a
substitute for the full project/schema tests, native or Wasm render, memory
admission, browser Save/Open, or owner listening. No hardware was used.

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

## Runtime and browser acceptance follow-up — 2026-10-11

The canonical four-project native/Wasm and Chromium file-flow checks now pass
for exact branch head `8efb1b72978d25f960beb1d6988bb2237b315a90`. See
[the bounded receipts](2026-10-11-event-horizon-acceptance-final-8efb1b7/README.md)
for artifact hashes and all results. This is not owner listening, hardware
execution, or musical/showcase approval. The original four songs remain legacy
examples; the owner's collection-wide distinctness requirement remains open.
The exact source review at critic commit
`74ffc412a14d9b115b06ac3f98070ac660a32c8d` identifies the remaining Event
arrangement issues, including Vrs2 duplicate Trio G4 attacks, shortened later
Acid drop gates, overlaps and inherited eight-scene topology. Keep these as
musical revision work rather than treating runtime success as closure.
