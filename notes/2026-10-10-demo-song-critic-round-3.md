# Demo-song critique — round 3

Frozen asset `cdf8d8fcc0bd89518f3fe28ec1a6661a827c19bc`. **No scene passes all six categories strictly above8.** Honest scores span6–8. Earlier reports are preserved.

Programmatic review of exact saved project assets and generator/proposals: all32 scenes and56 ordered occurrences, notes/gates/velocities, locks, sound/FX/arp and modulation routing. No by-ear perception; all perceptual judgments provisional. Runtime receipt pending independently.

## Round 2 disposition

- **R2-A** — implemented mechanically: reversed payload now maps onto new onsets; later peak adds5 semitones after MIDI calculation and preserves the first half. Eight-bar phrase development remains incomplete.
- **R2-B** — overlap repaired for peak/build main and reply; generic gap selection repeats a high interval from final motif note and does not establish two distinct four-bar sentences.
- **R2-C** — implemented: Event arp off, 4/5 simultaneous tones,192-tick peak holds; chord voice-leading and expressive rhythmic envelope still limited.
- **R2-D** — partly implemented: Neon continuous eight-bar exit fixed; Afterglow nearest_voicing skips all alternating-cardinality transitions in scenes0–6, and looks back to root-position templates rather than previous emitted voicing.
- **R2-E** — partly implemented: staged intro lead and better Event payoff; Packet interruption/chromatic resolution, Afterglow drift and distinct recurring modulation signatures still limited.
- **R2-F** — implemented: crossing note gates truncated at build cutoffs; effect tails may continue by design.

## Round 4 targets

- **R3-A** — Compose actual second four-bar sentences in peak scenes. Every song still repeats bass/chord/main/reply events from bars1–4 in5–8; source phrase identity verified after normalizing bar offsets. Keep the hook head but change response contour, rests and final destination in the second phrase. No occurrence-level automation is required.
- **R3-B** — Compose reply pitches from harmony/scale and an intended melodic destination. Repeated Afterglow F#5 and Event D6 are outside the written natural-minor material without a resolving gesture. High Event C7 and Packet Bb6 replies need intentional register roles. A gap-finding algorithm alone does not make a response.
- **R3-C** — Use actual emitted voicings/common tones, including changing chord cardinality. Afterglow nearest_voicing leaves scenes0–6 chord clips identical to Round2 because5/4/5/4-note changes all bypass it. Explicit per-song voicing tables may be simpler than generic optimization.
- **R3-D** — Finish distinct scene identity: a held drifting bridge for Afterglow, harmonically prepared wide Event release, short whole-ensemble interruption/resolving chromatic approach for Packet, sung ending/cadential suspension resolution for Neon. Intros repeated twice should have a purposeful eight-bar entrance, and low tonic endings need register preparation.

## Afterglow Relay

[verified] 92 BPM, 76 bars; SHA256 `d60c8c331d06cb964b5df0e7eca3847683cc6c1a473255527594db2d6a116927`. No complete event/lock-identical scenes remain.

| Scene | M | C | G | L | S | N |
| --- | --- | --- | --- | --- | --- | --- |
| Intro | 7 | 6 | 7 | 6 | 6 | 6 |
| Verse | 7 | 6 | 7 | 6 | 6 | 6 |
| Lift | 7 | 6 | 7 | 7 | 6 | 6 |
| Hook | 6 | 6 | 7 | 6 | 6 | 6 |
| Bridge | 7 | 6 | 7 | 6 | 7 | 6 |
| Vrs2 | 7 | 7 | 7 | 6 | 6 | 6 |
| Hook2 | 7 | 7 | 7 | 7 | 7 | 6 |
| Outro | 7 | 6 | 7 | 6 | 6 | 6 |

M musicality; C creativity; G genre/proposal; L Lunar features; S space/project feel; N novelty. Novelty is relative to these four demos and their common template; no world-first claim.

**0 Intro.** [verified] 4 bars; bass gates 8–12 ticks; lead gates 18–24 ticks; main/answer simultaneous onsets 0. [inferred] The staged lead entrance now has silence, answer, identity and pickup. Preserve that improvement and sustain a low/chord common tone so the opening establishes drift rather than only adding note count.

**1 Verse.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 12–12 ticks; main/answer simultaneous onsets 0. [inferred] Bass foundations are sound, but the chord track is unchanged from Round2: alternating five/four-note stacks bypass nearest_voicing. Write explicit voicings retaining common tones and give the two-note fragment a destination.

**2 Lift.** [verified] 4 bars; bass gates 5–72 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] Build silence and evolving locks are implemented. The new answer repeats a high interval from the final motif note; compose a resolving reply rather than mechanically selecting an available gap, and lead the harmonic top toward Hook.

**3 Hook.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] Answers now occupy real gaps but repeat MIDI78 F#5 twice in ordinary bars over the written A-natural-minor loop. This can imply Dorian colour, yet it is neither prepared nor resolved here. Choose an intentional chord-tone/diatonic answer, then give bars5–8 a complementary sentence.

**4 Bridge.** [verified] 8 bars; bass gates 8–12 ticks; lead gates 12–16 ticks; main/answer simultaneous onsets 0. [inferred] The drum subtraction remains successful. Chord voicing still bypasses the new nearest-voice routine, and regular two-stab bars remain under the sparse drums. Retain one common tone with slower harmonic articulation and stage the return.

**5 Vrs2.** [verified] 8 bars; bass gates 6–96 ticks; lead gates 8–8 ticks; main/answer simultaneous onsets 0. [inferred] Timestamp-aware reversal now works. The changed two-note fragment should develop across the eight bars and lead its last two bars into Hook2; unchanged parallel harmony still limits the promised drift.

**6 Hook2.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] Register fold and answer overlap are repaired. The whole first four-bar event phrase still repeats in bars5–8; a brightness lift is not a new melodic sentence. Write a later reply/cadence and common-tone chords while preserving the hook head.

**7 Outro.** [verified] 4 bars; bass gates 40–144 ticks; lead gates 16–96 ticks; main/answer simultaneous onsets 1. [inferred] The cadence has one newly adjusted same-size voicing transition and a held A. Prepare the upper-to-low lead landing and sustain the final harmonic colour so the intended soft exit follows from the phrase.

**Every occurrence and outgoing transition.** Scores in the JSON apply to each listed occurrence; the scene scores already incorporate its longest repeated span and transition role. No occurrence is treated as independently varied merely because effects continue. Repetition itself is permitted.

- Bars 1–4: Intro → Verse. First occurrence; role and next-scene arrival inspected.
- Bars 5–12: Verse → Verse. First occurrence; role and next-scene arrival inspected.
- Bars 13–20: Verse → Lift. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 21–24: Lift → Hook. First occurrence; role and next-scene arrival inspected.
- Bars 25–32: Hook → Hook. First occurrence; role and next-scene arrival inspected.
- Bars 33–40: Hook → Bridge. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 41–48: Bridge → Vrs2. First occurrence; role and next-scene arrival inspected.
- Bars 49–56: Vrs2 → Hook2. First occurrence; role and next-scene arrival inspected.
- Bars 57–64: Hook2 → Hook2. First occurrence; role and next-scene arrival inspected.
- Bars 65–72: Hook2 → Outro. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 73–76: Outro → Stop. First occurrence; role and next-scene arrival inspected.

**Whole-song pacing.** [inferred] The staged opener, real bridge and changed returns work. Repeated peak halves, unprepared F-sharp replies and unchanged bridge voicings still limit the warm drifting narrative.


## Event Horizon

[verified] 144 BPM, 116 bars; SHA256 `265ada7b63e88c013826475aea717ee1336e924e9cd1e899b316908034b1f6b6`. No complete event/lock-identical scenes remain.

| Scene | M | C | G | L | S | N |
| --- | --- | --- | --- | --- | --- | --- |
| Intro | 6 | 6 | 6 | 6 | 6 | 6 |
| Verse | 7 | 6 | 7 | 6 | 6 | 6 |
| Build | 7 | 6 | 8 | 7 | 7 | 6 |
| Drop | 6 | 7 | 8 | 7 | 7 | 6 |
| Break | 7 | 6 | 7 | 6 | 7 | 6 |
| Vrs2 | 7 | 7 | 7 | 6 | 6 | 6 |
| Drop2 | 7 | 7 | 8 | 7 | 7 | 7 |
| Outro | 7 | 6 | 7 | 6 | 6 | 6 |

M musicality; C creativity; G genre/proposal; L Lunar features; S space/project feel; N novelty. Novelty is relative to these four demos and their common template; no world-first claim.

**0 Intro.** [verified] 4 bars; bass gates 8–12 ticks; lead gates 18–24 ticks; main/answer simultaneous onsets 0. [inferred] Lead staging improves the opening. The four-bar intro is still relaunched once, including its retreat to lead silence; encode a continuous eight-bar entrance or make that reset a deliberate question/answer in the score. Establish the half-time snare placement purposefully.

**1 Verse.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 8–12 ticks; main/answer simultaneous onsets 0. [inferred] The un-arpeggiated harmony improves continuity with the drop, and roots anchor the groove. Give the two-note pickup a longer response and more harmonic voice-leading so it anticipates the refrain.

**2 Build.** [verified] 4 bars; bass gates 5–72 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] Full note-off withdrawal and broad chord support now fit the proposal. Add a phrase-specific chord-envelope/register trajectory so the payoff follows from the harmonic tension, not only the shared two-lane curve.

**3 Drop.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] The simultaneous 4/5-note two-beat chords realize the earlier missing harmonic bed. However the repeated answer D6 (86) lies outside F natural minor and against the Db-based harmony without a resolving target. Write a deliberate scale/chord-aware answer and distinct second four-bar sentence.

**4 Break.** [verified] 4 bars; bass gates 8–12 ticks; lead gates 8–12 ticks; main/answer simultaneous onsets 0. [inferred] Kickless subtraction and held chord colour form a reset. Expose one longer common tone or lone reply, and prepare the final bar into Vrs2 rather than restoring all layers together.

**5 Vrs2.** [verified] 8 bars; bass gates 5–84 ticks; lead gates 8–8 ticks; main/answer simultaneous onsets 0. [inferred] The reversal now alters chronological pitches. Develop its last two bars into a pickup and retain a connecting common tone in the harmony so it does more than swap a two-note fragment.

**6 Drop2.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] The original high hook head is preserved and later pitches lift without wrapping. The gap-selected upper reply reaches C7 (96); choose its register and melodic purpose explicitly rather than derive it from the last note. Compose bars5–8 as a new answer within the four repeated launches.

**7 Outro.** [verified] 4 bars; bass gates 40–144 ticks; lead gates 8–96 ticks; main/answer simultaneous onsets 0. [inferred] The written F-minor cadence works structurally. Connect the high motif to low F with a deliberate descending handoff and let the final chord resolve over a proportionate tail.

**Every occurrence and outgoing transition.** Scores in the JSON apply to each listed occurrence; the scene scores already incorporate its longest repeated span and transition role. No occurrence is treated as independently varied merely because effects continue. Repetition itself is permitted.

- Bars 1–4: Intro → Intro. First occurrence; role and next-scene arrival inspected.
- Bars 5–8: Intro → Verse. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 9–16: Verse → Verse. First occurrence; role and next-scene arrival inspected.
- Bars 17–24: Verse → Build. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 25–28: Build → Drop. First occurrence; role and next-scene arrival inspected.
- Bars 29–36: Drop → Drop. First occurrence; role and next-scene arrival inspected.
- Bars 37–44: Drop → Drop. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 45–52: Drop → Drop. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 53–60: Drop → Break. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 61–64: Break → Vrs2. First occurrence; role and next-scene arrival inspected.
- Bars 65–72: Vrs2 → Vrs2. First occurrence; role and next-scene arrival inspected.
- Bars 73–80: Vrs2 → Drop2. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 81–88: Drop2 → Drop2. First occurrence; role and next-scene arrival inspected.
- Bars 89–96: Drop2 → Drop2. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 97–104: Drop2 → Drop2. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 105–112: Drop2 → Outro. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 113–116: Outro → Stop. First occurrence; role and next-scene arrival inspected.

**Whole-song pacing.** [inferred] The broad chord bed now makes the build/drop architecture credible. Two 32-bar spans still depend on repeated four-bar phrases; writing a complementary second sentence and harmonically intentional reply is the priority.


## Packet Bloom

[verified] 112 BPM, 88 bars; SHA256 `a9f1722dc475c7d5cf60f30c3be0157c6e2e10b2bc77b59256407f8893d5556c`. No complete event/lock-identical scenes remain.

| Scene | M | C | G | L | S | N |
| --- | --- | --- | --- | --- | --- | --- |
| Intro | 7 | 7 | 7 | 6 | 7 | 6 |
| A-side | 7 | 6 | 7 | 6 | 6 | 6 |
| Build | 7 | 6 | 7 | 7 | 7 | 6 |
| Bloom | 7 | 7 | 7 | 6 | 7 | 6 |
| Glitch | 7 | 7 | 7 | 6 | 7 | 7 |
| B-side | 7 | 7 | 7 | 6 | 7 | 6 |
| Bloom2 | 7 | 7 | 7 | 7 | 7 | 7 |
| Outro | 7 | 6 | 7 | 6 | 7 | 6 |

M musicality; C creativity; G genre/proposal; L Lunar features; S space/project feel; N novelty. Novelty is relative to these four demos and their common template; no world-first claim.

**0 Intro.** [verified] 4 bars; bass gates 6–10 ticks; lead gates 18–24 ticks; main/answer simultaneous onsets 0. [inferred] The staged high/low fragment now gives the introduction direction. Anchor one low root and shape its final rest as a cue into A-side; keep the warble movement tied to this phrase.

**1 A-side.** [verified] 8 bars; bass gates 4–72 ticks; lead gates 4–6 ticks; main/answer simultaneous onsets 0. [inferred] The asymmetric groove and held root remain useful. Develop the call/answer over two bars; the promised brief chromatic approach still needs an intentional semitone resolution, not an incidental out-of-key note.

**2 Build.** [verified] 4 bars; bass gates 4–72 ticks; lead gates 6–48 ticks; main/answer simultaneous onsets 0. [inferred] The final note gap and build curve work. Distinguish this build through one short pitch/decay or register interruption at a specific phrase boundary, with an unmistakable restart.

**3 Bloom.** [verified] 8 bars; bass gates 4–72 ticks; lead gates 6–48 ticks; main/answer simultaneous onsets 0. [inferred] Answer collisions are removed, and the new reply fits clear sixteenth windows. The first four-bar lead/answer pattern exactly repeats in the second half: compose a register exchange or lower answering phrase, then one held ending.

**4 Glitch.** [verified] 4 bars; bass gates 6–10 ticks; lead gates 4–4 ticks; main/answer simultaneous onsets 0. [inferred] Sparse drum edits are present, but the harmonic/lead pattern continues through them. Compose a brief whole-ensemble rest and displaced return, or a singular pitch/decay interruption, to make Glitch an audible structural event by design.

**5 B-side.** [verified] 8 bars; bass gates 5–84 ticks; lead gates 6–10 ticks; main/answer simultaneous onsets 0. [inferred] Timestamp remapping repairs the reversed fragment. The requested high/low role exchange is still underdeveloped; switch who leads for one phrase and prepare the Bloom return with a clear rhythmic cue.

**6 Bloom2.** [verified] 8 bars; bass gates 4–72 ticks; lead gates 6–48 ticks; main/answer simultaneous onsets 0. [inferred] The corrected fourth-up phrase and non-overlapping reply are better. Both four-bar halves still repeat the same events, and the upper reply reaches MIDI94 Bb6. Write an intentional lower answer/register exchange and a distinct eighth-bar finish.

**7 Outro.** [verified] 4 bars; bass gates 40–144 ticks; lead gates 6–96 ticks; main/answer simultaneous onsets 0. [inferred] The D-minor cadence is purposeful. Shape the high-to-low handoff and progressively expose the warble tail; sustain the final harmonic colour enough to support the closing low D.

**Every occurrence and outgoing transition.** Scores in the JSON apply to each listed occurrence; the scene scores already incorporate its longest repeated span and transition role. No occurrence is treated as independently varied merely because effects continue. Repetition itself is permitted.

- Bars 1–4: Intro → A-side. First occurrence; role and next-scene arrival inspected.
- Bars 5–12: A-side → A-side. First occurrence; role and next-scene arrival inspected.
- Bars 13–20: A-side → Build. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 21–24: Build → Bloom. First occurrence; role and next-scene arrival inspected.
- Bars 25–32: Bloom → Bloom. First occurrence; role and next-scene arrival inspected.
- Bars 33–40: Bloom → Bloom. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 41–48: Bloom → Glitch. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 49–52: Glitch → B-side. First occurrence; role and next-scene arrival inspected.
- Bars 53–60: B-side → B-side. First occurrence; role and next-scene arrival inspected.
- Bars 61–68: B-side → Bloom2. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 69–76: Bloom2 → Bloom2. First occurrence; role and next-scene arrival inspected.
- Bars 77–84: Bloom2 → Outro. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 85–88: Outro → Stop. First occurrence; role and next-scene arrival inspected.

**Whole-song pacing.** [inferred] Groove and register leaps are distinctive, and reply collisions are repaired. The Glitch passage still lacks a decisive interruption, while identical peak halves weaken the playful call/response promise.


## Neon Transit

[verified] 120 BPM, 104 bars; SHA256 `3d99207507e92df7a8fa2c761450b02e2d1e69d7e34352acf8344315fecb7ac9`. No complete event/lock-identical scenes remain.

| Scene | M | C | G | L | S | N |
| --- | --- | --- | --- | --- | --- | --- |
| Intro | 7 | 6 | 7 | 6 | 6 | 6 |
| Verse | 7 | 6 | 7 | 6 | 6 | 6 |
| Pre | 7 | 6 | 8 | 7 | 6 | 6 |
| Chorus | 7 | 6 | 7 | 6 | 6 | 6 |
| Bridge | 7 | 6 | 7 | 6 | 7 | 6 |
| Vrs2 | 7 | 7 | 7 | 6 | 6 | 6 |
| Chor2 | 7 | 7 | 8 | 7 | 7 | 6 |
| Outro | 8 | 7 | 8 | 7 | 7 | 7 |

M musicality; C creativity; G genre/proposal; L Lunar features; S space/project feel; N novelty. Novelty is relative to these four demos and their common template; no world-first claim.

**0 Intro.** [verified] 4 bars; bass gates 8–10 ticks; lead gates 18–24 ticks; main/answer simultaneous onsets 0. [inferred] Four-bar lead staging improves this scene, but its immediate duplicate redoes the silence-to-pickup rise. Use an eight-bar entrance or write a first-to-second phrase relationship before Verse.

**1 Verse.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 6–12 ticks; main/answer simultaneous onsets 0. [inferred] The bass anchor and hook fragment fit electropop. Build a sung two-bar sentence with a held endpoint, and use closer chord voicings so melody and harmony support one another.

**2 Pre.** [verified] 4 bars; bass gates 5–72 ticks; lead gates 9–48 ticks; main/answer simultaneous onsets 0. [inferred] Note silence at the boundary and the rising curve now make a clear pre-chorus. Add a harmonic top-line suspension/resolution into the main hook; avoid relying exclusively on the generic lock shape.

**3 Chorus.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 9–48 ticks; main/answer simultaneous onsets 0. [inferred] The gap-selected answers avoid collision, but bars5–8 are an exact four-bar event repeat. Give the second phrase a different destination and a restrained eighth-bar fill while keeping E–G–B recognizable.

**4 Bridge.** [verified] 4 bars; bass gates 8–10 ticks; lead gates 6–12 ticks; main/answer simultaneous onsets 0. [inferred] The bridge remains truly kickless. Its lead/chord rhythm still resembles the surrounding sections; expose a longer common tone or different register, then stage the return into Vrs2.

**5 Vrs2.** [verified] 8 bars; bass gates 6–84 ticks; lead gates 6–6 ticks; main/answer simultaneous onsets 0. [inferred] Actual chronological reversal and changed bass now distinguish the verse. A composed concluding pickup and two-bar phrase development would make the bridge have a stronger consequence.

**6 Chor2.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 9–48 ticks; main/answer simultaneous onsets 0. [inferred] The hook head and actual fourth-up continuation are repaired. The held C5 over final Em7 can function as a suspension, but needs an explicit B/E destination; create a second four-bar answer rather than repeat the same unresolved shape under brighter locks.

**7 Outro.** [verified] 8 bars; bass gates 36–192 ticks; lead gates 24–192 ticks; main/answer simultaneous onsets 0. [inferred] The single eight-bar exit fixes cadence restart and removes drums in its second half. This is the strongest structural improvement. Prepare the final low E from F#4/upper fragments and smooth the chord top through the prolonged D-to-Em resolution; a distinctive closing motif could raise creativity beyond a competent cadence.

**Every occurrence and outgoing transition.** Scores in the JSON apply to each listed occurrence; the scene scores already incorporate its longest repeated span and transition role. No occurrence is treated as independently varied merely because effects continue. Repetition itself is permitted.

- Bars 1–4: Intro → Intro. First occurrence; role and next-scene arrival inspected.
- Bars 5–8: Intro → Verse. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 9–16: Verse → Verse. First occurrence; role and next-scene arrival inspected.
- Bars 17–24: Verse → Pre. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 25–28: Pre → Chorus. First occurrence; role and next-scene arrival inspected.
- Bars 29–36: Chorus → Chorus. First occurrence; role and next-scene arrival inspected.
- Bars 37–44: Chorus → Chorus. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 45–52: Chorus → Bridge. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 53–56: Bridge → Vrs2. First occurrence; role and next-scene arrival inspected.
- Bars 57–64: Vrs2 → Vrs2. First occurrence; role and next-scene arrival inspected.
- Bars 65–72: Vrs2 → Chor2. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 73–80: Chor2 → Chor2. First occurrence; role and next-scene arrival inspected.
- Bars 81–88: Chor2 → Chor2. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 89–96: Chor2 → Outro. Repeated full scene; scores include repetition cost across this complete span. Continuous FX/LFO can vary samples.
- Bars 97–104: Outro → Stop. First occurrence; role and next-scene arrival inspected.

**Whole-song pacing.** [inferred] The continuous eight-bar ending now closes once, and the bridge earns the final chorus. The refrain still needs a sung second sentence and resolution of its final suspended contour across three repeated launches.

## Runtime and simulator adjunct

[verified] Exact asset SHA256 identities match all four files in the full-song native/Wasm receipt. All four stop, save/load/save passes, and sequencer drops, refused events, skipped fields and repairs are zero. Browser Chromium 153.0.8010.12 lists, starts, downloads and freshly reopens all four projects with no recorded exceptions. Receipt hashes: native/Wasm `ed1878fd045c84151b7d13639d73b694f92b391addc6a6c7858f31c80b5ed4ea`; browser `e1e5b59df70a4e6c1568ea2172d8d52f8f2cec92f339db6316fc23427e9fd086`. Complete JSON receipts and all 56 occurrence aggregates are retained in the companion report JSON.

| Song | Duration seconds | Wasm peak | Wasm RMS | Contrast vs first peak dB | Final peak vs first peak dB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Afterglow Relay | 198.26 | 0.8093 | 0.0876 | -3.05 | +0.06 |
| Event Horizon | 193.33 | 0.8624 | 0.0977 | -5.49 | -0.22 |
| Packet Bloom | 188.57 | 0.7425 | 0.0815 | -2.28 | +0.56 |
| Neon Transit | 208.00 | 0.7765 | 0.0849 | -4.98 | -0.10 |

[inferred] Each contrast scene reduces measured energy, while final peaks return near the earlier level. This supports a working large-scale energy arc; it does not resolve repeated four-bar sentences or the identified unprepared pitch choices. Scores remain unchanged.

[verified] Aggregation weights each one-second RMS bin by its overlap with nominal scene time, assuming stationary energy within fractional seconds. These approximate values are not LUFS, perceived loudness or sample-exact transition measurements. Continuous effects and LFO state can change sound between identical event passages. Zero sequencer drops do not establish absence of synth voice stealing or masking, and reported loader RAM is not FM-1 hardware acceptance.

Browser Save default-arp normalization remains explicitly distinguished from byte equality: prior direct inspection established disabled default arp objects and command reordering. [verified] Fresh independent comparison of all four Round3 downloaded projects now confirms the same normalization: `made.by` changes from hand to simulator, command order changes with identical command multisets, and disabled default arp objects appear only in slots 0, 1 and 3. After those explicit normalizations, every decoded field is equal; saved-file SHA256 values are retained in JSON. No screenshots or WAVs were listened to or perceptually evaluated by this critic.
