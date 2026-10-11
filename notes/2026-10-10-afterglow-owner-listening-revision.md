# Afterglow owner-listening revision

This is an owner-directed revision of **Afterglow Relay only**, based on the
frozen Round 5 song snapshot. The owner described its prior listening result as
1980s/Casio-like, with excessive reverb, shrill/discordant chords and a basic
drum pattern. The owner then confirmed that master Hall Mix `0.05` materially
improved clarity. The owner supplied [Neon Indian's “Polish Girl”](https://www.youtube.com/watch?v=GuPGZZgNFsU)
and [Tycho's “Awake”](https://www.youtube.com/watch?v=6XJBDX3Z0BY) as genre
references. These links are recorded as target references; this revision does
not claim to have analyzed or matched their audio.

The parent task also supplied [Reverb Machine's reconstruction](https://reverbmachine.com/blog/neon-indian-synth-sounds/)
as a secondary source, not an artist session or primary recording analysis.
Its described ingredients are a short six-note square-wave hook with subtle
noise pitch modulation, rhythmic analog chord plucks, gliding leads, and delay
and reverb concentrated on arpeggio layers. These are interpretive directions,
not copied notes, presets or assets. This focused cleanup improves the chord
timbre and wet/dry balance, but it does not yet implement or establish a match
to those rhythmic plucks, modulation or glide gestures. The owner needs to
compare the revised project by listening before any resemblance claim.

## Changes in this checkpoint

- The first source edit replaced the chord sound's VA Pair with the Shapes
  `Sine/Tri` voice. The actual combined Wasm rejected that candidate at
  `394,696` bytes against a `387,924`-byte budget (102%); it is not a usable
  revision. The current candidate keeps the lighter Macro engine and selects
  its `VA+Filter` model as a low-register filtered pluck. It uses Harmonics
  `0.5` (unison), restrained Timbre envelope amount `0.12`, and a ping LPG.
  This is a source-informed alternative, not a claim of approved sound.
  The prior VA Pair Harmonics `0.35` puts its second oscillator about 7.26
  semitones below the first, while its Timbre modulation could enter the
  variant's hard-sync range; that is a plausible explanation for the reported
  dissonance, not a measured listening result.
- Changed the first and third progression qualities from Am9/Cmaj9 to Am7/Cmaj7
  and moved Afterglow's chord voicings down one octave. The root progression,
  scene chain, tempo and form are unchanged.
- Set master Hall Mix to `0.05`, with a shorter decay (`0.42`) and size (`0.58`).
  The other sound slots have no Hall insert to retune. The chord slot has no
  insert; its old chord sound was not made less discordant by wet effects.
- Reduced the chord Timbre cable amount from `40` to `8`. The filtered pluck is
  intended to restore rhythmic articulation at lower memory cost; it still
  needs the owner's listening comparison.
- Retuned Punch kit pads by their MIDI mapping in `engines/src/drums.cc`:
  note 36 is pad 1/kick, note 38 is pad 3/snare and note 42 is pad 7/closed
  hat. The engine is the Punch kit in `drums.cc`; pad patches, rather than MIDI
  note-off gates, set the one-shot tails.
- Re-authored a four-bar kick phrase, varied the backbeat accent by bar, and
  added quiet sixteenth-note hat pickups. Small timing nudges are stored beside
  their original step anchors so the sequencer can still apply swing from the
  authored grid. `offset_event` uses that preserve-anchor path for Afterglow
  only; the other three song files remain unchanged.

## Verification and limits

`python3 -m py_compile tools/demo_songs.py` passed. `python3
tools/demo_songs.py --check` passed all generated-file, song-chain, groove,
instrument and owner-setting assertions. After generation, the other songs'
source and browser files matched the frozen parent commit byte-for-byte:

| Song | SHA-256 (both copies) |
| --- | --- |
| Event Horizon | `5b92ad3d8e6448855b9cde032a935437331620819becbb206212f32845414897` |
| Packet Bloom | `7d755fd777f1b0534c2518717e4bded475872db57f9596fe410d75606765e349` |
| Neon Transit | `e19152d0747d6d2a69cc61eaabeed6d083f89fbecdfa7e1d85ba7f9911f6e251` |

The first Shapes candidate failed the actual Wasm memory gate above. The
current Macro variant has passed generator checks, but native/Wasm playback,
fresh browser load/save and owner re-listening remain pending. The local
`pytest` command is unavailable (`No module named pytest`), and checked-in
example metadata is not a matching full engine registry. A bounded
native/Wasm/browser receipt against the actual combined build is the next
gate. There is no hardware or device claim here.

The requested Rarefaction/Serena practical evaluation was limited by shared
project selection: Rarefaction reported the primary checkout rather than this
worktree; Serena reported a primary checkout with only its C++ profile. I did
not retarget either shared project. The code review used direct source reads,
including the Punch pad table and Shapes parameter registry, and the bounded
generator checks above.
