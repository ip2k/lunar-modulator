# Lunar Modulator demo-song production sheets

These four original, sample-free sequencer projects are arranged as complete
instrumental sketches for the browser simulator. The checked-in `.lunar`
files are authoritative; `tools/demo_songs.py` deterministically generates
them, their web copies, and `sim/web/test/demo-songs.json`. The source uses the
existing four sound slots and eight sequencer tracks. These sheets describe
the intended arrangement; they do not claim listening acceptance, FM-1 RAM
fit, or hardware playback.

## Afterglow Relay — chillwave, 92 BPM, A minor, 76 bars

The harmonic palette is Am9–Fmaj7–Cmaj9–G6. Later verse/bridge sections begin
on different chords; the four-bar outro moves C–F–G–Am. A six-note
descending/turning hook starts on A4 and returns to A for its final held tone.
The kick and snare sit on a slow straight pulse, with sparse offbeat hats;
selected bass roots sustain under short fifth pickups. The eight-bar bridge
removes the kick and most hats, then restores a single pulse before Vrs2.

| Scene | Length | Role |
| --- | ---: | --- |
| Intro | 4 bars | Sparse kick, two hook fragments, held chord color |
| Verse | 8 bars | Bass pulse and half-density hook answer |
| Lift | 4 bars | Extra chord arrival and a short hat rise |
| Hook | 8 bars | Full six-note hook and open upper response |
| Bridge | 8 bars | Reduced kick, longer harmony, hook fragments |
| Vrs2 | 8 bars | Verse groove with a late answer |
| Hook2 | 8 bars | Full hook returns with small fourth-bar pickups |
| Outro | 4 bars | Kick thins and the last chord/lead phrase settles |

Scene chain: `0,1,1,2,3,3,4,5,6,6,7` (76 bars, about 3:18). The bass is
slot 1; the chord and answer parts share the arpeggiator-capable slot 2 with
its arp off; DX7 slot 3 carries the melody and a low echo send.

Scene pass map: Intro 1×4 bars; Verse 2×8; Lift 1×4; Hook 2×8; Bridge
1×8; Vrs2 1×8; Hook2 2×8; Outro 1×4. Vrs2 reverses the later pitch/rhythm
payload across the original ascending onset slots, changes its bass rhythm,
and keeps the phrase in chronological order. Hook2 voice-leads equal-sized
chord stacks to the nearest register, moves late answers into verified gaps,
and adds a held upper response on phrase endings. The Lift's four lock
bars rise separately, then its last chord stab is withheld. The outro removes
drums in stages and ends with a held A over Am9.

## Event Horizon — future bass, 144 BPM, F minor, 116 bars

The drums imply a 72 BPM half-time pocket, while the four-bar harmony
Fm9–Dbmaj7–Ab–Eb and syncopated bass keep the 144 BPM grid moving. Peak chords
play as simultaneous four- or five-note stacks with the slot-2 arpeggiator
off; each stab holds for 192 raw Movy ticks (two beats) before the next
voicing. The major chords add an upper ninth so the wide stack remains present
through the whole progression rather than serializing into an arp.
The drop adds kick anticipation, steady half-time snare, brighter hats and a
changed upper answer. The build tightens its hats and chord locks, then removes
late attacks before the drop downbeat.

| Scene | Length | Role |
| --- | ---: | --- |
| Intro | 4 bars | Two-pass filtered pulse and a small motif fragment |
| Verse | 8 bars | Half-time backbeat and syncopated bass |
| Build | 4 bars | Increasing chord/hihat activity and rising pickup |
| Drop | 8 bars | Full hook, bass syncopation, and upper chord answers |
| Break | 4 bars | Kick recedes; long harmony opens space |
| Vrs2 | 8 bars | Verse groove with a changed ending pickup |
| Drop2 | 8 bars | Four-pass final drop with fourth-bar drum fills |
| Outro | 4 bars | A final low pulse and shortened motif |

Scene chain: `0,0,1,1,2,3,3,3,3,4,5,5,6,6,6,6,7` (116 bars, about 3:13).
No tempo automation is implied; the half-time feel is in the written kick and
snare placements.

Scene pass map: Intro 2×4 bars; Verse 2×8; Build 1×4; Drop 4×8; Break
1×4; Vrs2 2×8; Drop2 4×8; Outro 1×4. Vrs2 changes bass rhythm and contour;
Drop2 rotates the chord stack, adds an upper answer and raises its late-scene
brightness. The Break removes the kick and reduces the bass to two sparse
attacks to make the second drop an arrival. The outro cadences Ab–Db–Eb–Fm
and settles the upper line on F.
The chord slot's saved Rate/Gate values are inactive while its arp is off;
slot-1 Crush remains a restrained insert. Timbre/Brightness locks rise across the build instead of
repeating one bar shape, and the final build bar clears chord stabs from step
12 onward and other new attacks from step 14 onward.

## Packet Bloom — vapor twitch, 112 BPM, D minor, 88 bars

The harmony uses Dm9–Bbmaj7–Fmaj7–Cadd9 under a syncopated D bass line; the
later B-side and second bloom start on changed chord positions, and the outro
cadences F–Bb–C–Dm.
The seven-event motif has a high opening note, a clipped chromatic-feeling
turn, then a late upward answer; pitches remain in the D natural-minor
collection. Hats and small percussion deliberately offset the expected
straight grid, with short fills on alternating bars. The contrast scene
removes some low-end hits so the returning bloom has room to expand.

| Scene | Length | Role |
| --- | ---: | --- |
| Intro | 4 bars | High motif fragment over a sparse two-hit pulse |
| A-side | 8 bars | Uneven kick/hats and a restrained bass answer |
| Build | 4 bars | Chord lift with increasingly active hats |
| Bloom | 8 bars | Full hook, bright response notes, alternating fills |
| Glitch | 4 bars | Broken kick pattern and short motif fragments |
| B-side | 8 bars | New bass emphasis and quieter melody density |
| Bloom2 | 8 bars | Hook returns with the late answer exposed |
| Outro | 4 bars | Sparse pulse, cadence, and a held D closing tone |

Scene chain: `0,1,1,2,3,3,3,4,5,5,6,6,7` (88 bars, about 3:09). Swing is
set to 59; the step patterns still use the ordinary sequencer grid, and the
groove comes from event placement rather than a hidden timing process.

Scene pass map: Intro 1×4 bars; A-side 2×8; Build 1×4; Bloom 3×8; Glitch
1×4; B-side 2×8; Bloom2 2×8; Outro 1×4. B-side reverses the verse fragments
and changes bass rhythm; Bloom2 turns the upper voicing and adds a different
late answer. Glitch uses isolated kick/rim events and sparse hats. Its build
clears late chord stabs and other attacks before Bloom. The lead-slot Warble is
set to Wow .58, Flutter .34, Mix .24; the bass has Filter and Drive, and the
master hall is wider/longer than the other sketches. The outro thins the pulse
and resolves the lead to D.

## Neon Transit — electropop, 120 BPM, E minor, 104 bars

Em7–Cmaj7–G–D supplies a direct four-bar loop. The seven-note refrain uses
short, repeated eighth-grid phrases and a higher turnaround. Straight
four-on-the-floor kick, backbeat snare, and offbeat hats anchor the track;
the verse bass is clipped while the chorus sustains broader chord hits. A
four-bar pre-chorus raises note density, and the bridge takes the kick away
before the final chorus.

| Scene | Length | Role |
| --- | ---: | --- |
| Intro | 4 bars | Two passes, kick on the main beats, refrain preview |
| Verse | 8 bars | Clipped bass and reduced melody |
| Pre | 4 bars | Rising answer notes and fuller hats |
| Chorus | 8 bars | Full refrain, wide chord stabs and response line |
| Bridge | 4 bars | Half-density pulse and a quieter upper phrase |
| Vrs2 | 8 bars | Verse return with end-of-phrase lift |
| Chor2 | 8 bars | Three chorus passes, fills on the last bar of each |
| Outro | 8 bars | One directional exit; final four bars thin to a held E |

Scene chain: `0,0,1,1,2,3,3,3,4,5,5,6,6,6,7` (104 bars, about 3:28).

Scene pass map: Intro 2×4 bars; Verse 2×8; Pre 1×4; Chorus 3×8; Bridge
1×4; Vrs2 2×8; Chor2 3×8; Outro 1×8. Roles are edge, verse, build, peak,
contrast, verse, peak, edge. The seven-note refrain uses two-note previews,
alternating verse notes, a four-note pre-chorus lift, and the full motif in
the choruses; the answer enters in chorus and pre-chorus. Chorus chords repeat
on beats 1 and 3, while the bridge removes the kick. The Pre lock shape climbs
in three distinct four-bar levels, then falls below its opening center as the
last-bar attacks withdraw; Chor2 raises Timbre and Brightness again after its
fourth bar.

Each scene writes deterministic Bass Timbre and lead Brightness locks at
sixteenth steps 0, 4, 8 and 12. Each song has a different four-bar build
gesture: three rising centers followed by a low release; contrast centers
fall, and each second peak gains its own late lift. Other sections use a
restrained four-point contour around their role center. Repeated chain indexes replay the
same shaped scene, while Vrs2/Hook2, B-side/Bloom2, Drop2 and the ending provide
distinct later material. Durations above assume four quarter-note beats per bar.

The bass line is transposed one octave below each project's melody tonic; chord
and lead pitches remain in their written registers. `cl` note gates are stored
in raw Movy ticks (24 ticks per sixteenth step), not in step units. Pickups and
motif notes remain short; selected bass roots, peak chords and phrase endpoints
hold for longer spans. Gate lengths do not imply tempo automation or swing.

## File and playback contract

Each project stores eight named scenes and a raw `sg` press chain ending with
`se 2` (stop after the last scene). The manifest records the expected BPM,
full-chain bars and scene count. Browser copies are byte-identical to the
authoritative state examples. Parent acceptance work will load, save, render,
and inspect these projects in native and actual Wasm paths. The project
author has not accepted them by ear yet.
