# Demo songs — Round 3 checkpoint

This is a generator/assets checkpoint for independent Round 3 review, not an
accepted musical or listening result. It follows the frozen Round 2 snapshot
`f1887404ce12a53d63ef784178fa37fccec7722e`; the Round 2 critic report remains
historical and unchanged.

## Changes made

- Afterglow Relay's Vrs2 remaps reversed pitch/rhythm payload onto ascending
  onset positions, so chronological serialization no longer undoes the
  reversal. Its later Hook2 uses nearest-register equal-size chord voicings
  and lead replies selected from gaps in the main phrase.
- Event Horizon's chord part is un-arpeggiated. Drop chords are simultaneous
  four- or five-note stacks held for two beats; major chords add an upper
  ninth. Peak tests derive the expected stack size from each written chord.
- Later peak motifs lift the second-half pitches by five semitones without
  wrapping scale degrees across an octave. Peak/build track-7 answers are
  placed only where the corresponding main lead leaves a full 24-tick window.
- Each opening stages its main lead over four bars. The Neon Transit outro is
  one eight-bar exit rather than two repeated four-bar scenes: drums withdraw
  for the final four bars, harmony and bass thin, and the lead settles on E.
- The final half-beat of each build is actual note silence: events crossing
  the cutoff have their gates shortened, as well as attacks at or after it
  being removed. Chord attacks withdraw earlier as annotated in the sheets.
- Updated the production sheets and all four authoritative projects, web
  copies, and the demo manifest from the deterministic generator.

## Verification

- `python3 -m py_compile tools/demo_songs.py` passed.
- `python3 tools/demo_songs.py --write` generated nine files;
  `python3 tools/demo_songs.py --check` passed with four current full chains.
- `git diff --check` passed. Each generated state loaded through
  `engines/build/fm1-state check` with `OK`, zero repaired/skipped/defaulted
  records, and below the reported 387,924-byte project budget:
  Afterglow 244,640; Event Horizon 244,576; Packet Bloom 195,360; Neon Transit
  244,640 bytes. Authoritative and web-copy `.lunar` files compare byte-for-byte.
- Full-chain lengths remain Afterglow 76 bars, Event Horizon 116, Packet Bloom
  88, and Neon Transit 104. No render or human listening acceptance is claimed
  by this source/generator checkpoint; parent-owned native/Wasm/browser review
  and the critic's Round 3 report remain pending.

## Review boundary

The structural checks cover exact second-verse payload remapping, the
non-wrapping later-peak lift, lead/answer non-overlap in both peak scenes,
future-bass chord-stack cardinality and hold, four-bar lock/build shape,
note-end withdrawal, and Neon Transit outro length/drum release. Scores and
the Round 2 findings are not rewritten. A Round 3 review should score every
scene and repeated occurrence against the pushed source identity, and should
distinguish these source-level checks from actual rendered signal or listening.
