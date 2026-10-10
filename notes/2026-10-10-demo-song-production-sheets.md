# Lunar Modulator demo-song production sheets

These four original, sample-free sequencer projects are arranged as complete
instrumental sketches for the browser simulator. The checked-in `.lunar`
files are authoritative; `tools/demo_songs.py` deterministically generates
them, their web copies, and `sim/web/test/demo-songs.json`. The source uses the
existing four sound slots and eight sequencer tracks. These sheets describe
the intended arrangement; they do not claim listening acceptance, FM-1 RAM
fit, or hardware playback.

## Afterglow Relay — chillwave, 92 BPM, A minor, 76 bars

The four-bar loop is Am9–Fmaj7–Cmaj9–G6, one chord per bar. A six-note
descending/turning hook starts on A4 and returns to A before its last pickup.
The kick and snare sit on a slow straight pulse, with sparse offbeat hats;
the bass alternates held roots and short fifth responses. Wide chord voicings,
longer DX envelope and the restrained echo/hall keep the upper register soft.

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
1×8; Vrs2 1×8; Hook2 2×8; Outro 1×4. The lock role sequence is edge, verse,
build, peak, contrast, verse, peak, edge. Melody density follows that same
role: opening/ending use the first or last two motif notes, verses alternate
the first four notes, the lift uses the middle four, hooks play all six, and
the bridge plays two interior notes. Bass Timbre and lead Brightness each have
four locks per bar at sixteenth steps 0/4/8/12; the chillwave/vapor role curves
are edge 31/27, verse 45/41, build 70/66, peak 88/84, contrast 55/51 (bass /
lead center values), with lock values center−5, center, center+10, center.

## Event Horizon — future bass, 144 BPM, F minor, 116 bars

The drums imply a 72 BPM half-time pocket, while the four-bar harmony
Fm9–Dbmaj7–Ab–Eb and short syncopated bass keep the 144 BPM grid moving. A
six-note upward pickup resolves down into the drop; the answer track enters
late and above the chord stack. The slot-2 arpeggiator is enabled at an eighth
rate for the chord rhythm. The drop adds kick anticipation, steady bar-three
snare, brighter hats, and a three-tone chord bed without using audio samples.

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
1×4; Vrs2 2×8; Drop2 4×8; Outro 1×4. Roles are edge, verse, build, peak,
contrast, verse, peak, edge. The lead moves from two-note edge fragments, to
alternating verse notes, to a four-note build pickup, then the full six-note
motif in each drop; the answer voice enters only in build/drop. The slot-2
arp is eighth-rate with 68% gate; slot-1 Crush is a restrained insert. Bass
Timbre and lead Brightness lock centers are edge 38/42, verse 52/56, build
77/81, peak 95/99, contrast 62/66, with values center−5, center, center+10,
center at steps 0/4/8/12 of every bar.

## Packet Bloom — vapor twitch, 112 BPM, D minor, 88 bars

The harmony Dm9–Bbmaj7–Fmaj7–Cadd9 cycles under a syncopated D bass line.
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
| Outro | 4 bars | Sparse pulse and a descending tail |

Scene chain: `0,1,1,2,3,3,3,4,5,5,6,6,7` (88 bars, about 3:09). Swing is
set to 59; the step patterns still use the ordinary sequencer grid, and the
groove comes from event placement rather than a hidden timing process.

Scene pass map: Intro 1×4 bars; A-side 2×8; Build 1×4; Bloom 3×8; Glitch
1×4; B-side 2×8; Bloom2 2×8; Outro 1×4. Roles are edge, verse, build, peak,
contrast, verse, peak, edge. The seven-note motif opens with its high pickup;
verses use alternating early notes, the build uses its middle four, blooms
play the full motif, and the glitch scene uses two interior notes. The lead
slot's Warble is set to Wow .58, Flutter .34, Mix .24; the bass has Filter and
Drive, and the master hall is wider/longer than the other sketches. Bass
Timbre and lead Brightness lock centers follow the chillwave/vapor curve above.

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
| Outro | 4 bars | Two final passes, reduced drums and hook resolution |

Scene chain: `0,0,1,1,2,3,3,3,4,5,5,6,6,6,7,7` (104 bars, about 3:28).

Scene pass map: Intro 2×4 bars; Verse 2×8; Pre 1×4; Chorus 3×8; Bridge
1×4; Vrs2 2×8; Chor2 3×8; Outro 2×4. Roles are edge, verse, build, peak,
contrast, verse, peak, edge. The seven-note refrain uses two-note previews,
alternating verse notes, a four-note pre-chorus lift, and the full motif in
the choruses; the answer enters in chorus and pre-chorus. Chorus chords repeat
on beats 1 and 3, while the bridge reduces the kick. Bass Timbre and lead
Brightness lock centers use the future/electro curve above.

For all four projects the per-bar lock sequence is `[center−5, center,
center+10, center]` at sixteenth steps 0, 4, 8 and 12. Thus each repeated
scene retains a small, deterministic Timbre/Brightness contour, while section
role changes the center. Every section replays its own clip from the beginning;
the scene chain's repeated indexes are deliberate full-section repeats, not
one-bar variations. Durations above assume four quarter-note beats per bar.

## File and playback contract

Each project stores eight named scenes and a raw `sg` press chain ending with
`se 2` (stop after the last scene). The manifest records the expected BPM,
full-chain bars and scene count. Browser copies are byte-identical to the
authoritative state examples. Parent acceptance work will load, save, render,
and inspect these projects in native and actual Wasm paths. The project
author has not accepted them by ear yet.
