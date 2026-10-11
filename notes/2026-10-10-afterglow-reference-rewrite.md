# Afterglow reference-informed rewrite

Status: composition draft, generated and structurally checked; awaiting exact native/Wasm/browser acceptance and owner listening. No claim of audible resemblance or by-ear approval.

## Request and reference boundary

The owner rejected the prior Afterglow tone repair as musically unconvincing and asked for a new composition using the FM6 Lunar Lead foreground patch, with Neon Indian's “Polish Girl” and Tycho's “Awake” as references. This rewrite retains the existing 92 BPM, A-minor center, eight-scene form, 76-bar runtime and eleven-occurrence scene chain. The other three generated projects are intended to remain byte-identical to the Round 5 integrated baseline.

The owner supplied the official video links for “Polish Girl” and “Awake.” An independent Reverb Machine reconstruction of “Polish Girl” describes a short square-wave hook, rhythmic eighth-note chord plucks and selective effects; it is not artist session evidence. Scott Hansen's official Song Exploder transcript for “Awake” describes building from a guitar fragment with edited, driving bass and describes the contrast between a repeated foundation and freer layers, including a breakdown that becomes a new instrumental idea. These informed arrangement roles only: this note does not claim direct listening, transcription, or reproduction of either recording. No samples, copied notes, presets or recordings are used.

## Arrangement and sound roles

- **Intro (4 bars):** stage the hook as fragments over an entering bass pulse, then add the drum identity.
- **Verse (8):** use a steady bass foundation, a separate four-note FM phrase, and sparse chord calls.
- **Lift (4):** raise the melodic contour and chord-hit density, with the existing final-bar withdrawal preserved.
- **Hook (8):** state a six-note, chord-aware FM6 phrase over four syncopated, quarter-spaced chord pulses per bar; the second four-bar sentence changes its interior landing and cadence.
- **Bridge (8):** first remove drums and thin the lead; in its second half, introduce a new four-note answer and broken-chord figure over the bass pulse.
- **Second verse (8):** keep the same harmonic language while changing the lead contour/onsets.
- **Hook 2 (8):** retain the six-note identity, transpose it with the progression and vary its later sentence.
- **Outro (4):** move through the written cadence and resolve to a sustained A3 ending.

The foreground is sound slot 4, DX7 **User 1** (`LUNAR LEAD` in `tools/state_examples.py`), with Brightness neutral at 0.50 and a restrained echo send. Brightness controls FM modulator output, not a low-pass filter, so its scene locks stay near neutral. The chord layer is a low-volume Macro VA+Filter with Harmonics .50, short attacks, modest cutoff automation and a small filter envelope route; it avoids the old VA Pair's non-unison oscillator interval. Hall Mix is .05, the owner's clarity target; Hall decay/size and lead echo are restrained. The bass preserves downbeat anchors while adding authored fifth/third pickups; the existing chill drum phrase retains varying kick placement, snare accents and small hat nudges with their clip-step anchors preserved.

## Verification at this draft

`python3 -m py_compile tools/demo_songs.py`, `python3 tools/demo_songs.py --write`, `python3 tools/demo_songs.py --check`, and `git diff --check` pass. The generator validates the hook's six onsets, different second hook sentence, distinct second verse, bridge's new second-half figures, FM6 User 1 selection, restrained macro/echo settings, Hall Mix .05, non-overlapping lead answers and the existing drum humanization limits.

The source and web copies of `event-horizon.lunar`, `packet-bloom.lunar`, and `neon-transit.lunar` retain their baseline SHA-256 values: `5b92ad3d…414897`, `7d755fd7…b606e9`, and `e19152d0…6e251` respectively. `tools/demo_songs.py --check` also verifies the generated copies are synchronized. These checks establish deterministic state generation and structure, not sound quality, full runtime, engine-budget fit, or browser save/reopen acceptance. Those gates and owner listening remain outstanding.

An independent source review of the first freeze found accidental chromatic notes in bass and lead phrases: major-chord thirds were treated as minor, and some variations used raw semitone subtraction. The generator now derives bass thirds from chord quality, maps lead contours through A natural minor, uses chord tones for answers and phrase endings, and checks every emitted pitched track for out-of-key pitch classes. All lead contours use one octave above the current chord root; the compact chord voicing sits one octave above bass and below the lead. Generator checks include explicit Fmaj7/Cmaj7 bass-third pickups, the register policy, and the full pitched-track key check. These are structural checks, not claims of perceptual approval. The first freeze SHA `7ff52ac873f38d13077e56b61e3511fb2f912bd3` remains in history; later corrective checkpoints supersede it for acceptance.

## Navigation-tool coverage

The active Serena project still points to the primary checkout, and Rarefaction reported that server was not started for that root. I did not retarget either shared semantic session while other agents were active. This composition pass used direct source, template, state-generator and caller/test inspection; no claim of successful semantic MCP navigation is made.
