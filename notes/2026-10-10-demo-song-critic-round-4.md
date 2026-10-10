# Demo-song critique — round 4

Frozen asset `75e029dcb4416c3b0381d0f6665fac0a6c0c3160`. **No scene passes all six categories strictly above8.** Scores span6–9; improvements earn higher scores where the emitted music supports them. Earlier reports remain unchanged.

Programmatic inspection of exact serialized projects, generator and production sheet across all32 scenes and54 ordered occurrences, note pitches/onsets/gates/velocities, locks, sound/FX, routes and modulation. No by-ear perception; perceptual judgments remain provisional. Exact runtime receipt pending.

## Round 3 disposition

- **R3-A** — implemented: both peak scenes in every song change all five pitched-role streams between their first and second four-bar halves; distinct harmonic orders, bass rhythms and melodic contours emitted.
- **R3-B** — implemented for replies: actual chord/lead answers use in-key chord tones and controlled register; main fourth-up phrases remain subject to musical judgment rather than an automatic key-membership ban.
- **R3-C** — implemented for Afterglow: varying-cardinality voicings retain exact common tones and refer to successive emitted choices; other songs retain largely root-position stacks.
- **R3-D** — partly implemented: continuous eight-bar Event/Neon intros, Packet whole-ensemble note-on interruption and C#4→D4 resolution, full-bar closing sustains and Neon upper-tonic descent. Afterglow Warble claim is not realized; its lead remains Echo. Bridges remain short-stab templates except Packet interruption.

## Final-round targets

- **R4-A** — Make Afterglow actual lead processing match the intended drift and production sheet: the Warble tuple is unused because lead_fx still selects Echo. Verify the serialized engine/params, not only the source tuple.
- **R4-B** — Consolidate same-pitch same-onset chord-answer triggers into one authored event. Exact duplicates at tick1488 occur in Afterglow Hook B4, Event Drop G4, Event Drop2 Ab4 and Neon Chorus F#4, with gates24/54. Preserve intended long endpoint; avoid competing releases.
- **R4-C** — For remaining musical quality, choose deliberate sustained articulation and local resolutions: Afterglow bridge common tone, Event evolving chord swells, Neon sung hook/suspension release, and intermediate register handoffs in A/E/P endings. These are compositional recommendations, not new feature quotas. The fifth round is final even if the strict all9 threshold remains unmet.

## Afterglow Relay

[verified] 92 BPM, 76 bars; SHA256 `354b547955953eb4ac47cf58d5e0bb568dad160949e2a940bba926b1614d1b0d`. No complete event/lock-identical scenes remain.

| Scene | M | C | G | L | S | N |
| --- | --- | --- | --- | --- | --- | --- |
| Intro | 7 | 6 | 7 | 6 | 6 | 6 |
| Verse | 8 | 7 | 8 | 7 | 7 | 6 |
| Lift | 7 | 7 | 7 | 7 | 7 | 6 |
| Hook | 7 | 7 | 8 | 7 | 7 | 7 |
| Bridge | 7 | 7 | 7 | 7 | 7 | 7 |
| Vrs2 | 8 | 7 | 8 | 7 | 7 | 7 |
| Hook2 | 8 | 8 | 8 | 7 | 7 | 7 |
| Outro | 8 | 7 | 8 | 7 | 7 | 7 |

M musicality; C creativity; G genre/proposal; L Lunar features; S space/project feel; N novelty. Novelty is relative to these four demos and their common template; no world-first claim.

**0 Intro.** [verified] 4 bars; bass gates 8–12 ticks; lead gates 18–24 ticks; main/answer simultaneous onsets 0. [inferred] The staged pickup establishes the hook economically, and common-tone harmony now supports it. Actual lead processing remains Echo despite the new Warble claim; make the intended slow drift part of the emitted sound. A longer common-tone lead rest would distinguish this opening from the shared staged template.

**1 Verse.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 12–12 ticks; main/answer simultaneous onsets 0. [inferred] Actual voicings retain two to four exact common tones across successive changes. This materially improves the warm harmonic bed. The two-note lead fragment still repeats each ordinary bar; give its second two-bar unit a deliberate destination rather than only the fourth-bar scale shift.

**2 Lift.** [verified] 4 bars; bass gates 5–72 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] The build retains a genuine final note-off gap and brighter movement. Chord-aware replies improve coherence. The unchanged clipped lead articulation still makes tension mostly density/brightness-led; one lengthened suspension into the gap would add harmonic purpose.

**3 Hook.** [verified] 8 bars; bass gates 5–84 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] Bars5–8 now change bass, chords, main and both answers, ending the second sentence on A4. Replies no longer inject unexplained F-sharp. However bar4 track5 triggers B4 twice at tick1488 with gates24/54; replace this pair with one authored endpoint. The warm drift remains limited by actual Echo processing.

**4 Bridge.** [verified] 8 bars; bass gates 8–12 ticks; lead gates 12–16 ticks; main/answer simultaneous onsets 0. [inferred] Common tones and the eight-bar lock drift are present. Two chord attacks of78 ticks per bar still make this a clipped bridge despite the drift curve; expose a held common tone in at least one full bar and stage the final pickup. Warble is not active in this snapshot.

**5 Vrs2.** [verified] 8 bars; bass gates 6–96 ticks; lead gates 8–8 ticks; main/answer simultaneous onsets 0. [inferred] The reversed fragment, changed bass and newly smooth chords distinguish the return. Its two-note cell remains repeated rather than becoming a longer second-verse sentence; a final two-bar pickup could connect it more deliberately to Hook2.

**6 Hook2.** [verified] 8 bars; bass gates 5–84 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] The later peak has its own harmonic order and second sentence, with the hook head intact and replies in a controlled register. This is a substantive compositional improvement. Give the last answer a clearer long/short rhythmic contrast; the same reply algorithm and shared synth envelope still constrain its personality.

**7 Outro.** [verified] 4 bars; bass gates 40–384 ticks; lead gates 72–384 ticks; main/answer simultaneous onsets 0. [inferred] The complete last-bar A-minor sustain closes the arrangement once. The lead drops from B4 to A3 (14 semitones); that is an intentional-looking register handoff but not a stepwise resolution. A brief connecting E4 or upper A before the low landing would make the gentle exit less abrupt.

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

**Whole-song pacing.** [inferred] The common-tone harmony and new second peak sentences materially improve direction. The bridge still articulates short stabs, actual Echo contradicts the claimed Warble, and the closing register leap remains abrupt in the score.


## Event Horizon

[verified] 144 BPM, 116 bars; SHA256 `3b4d9bab39f4d2da01a2fc7eca99f60ac9131164595efebfa61f2f72da51f0d7`. No complete event/lock-identical scenes remain.

| Scene | M | C | G | L | S | N |
| --- | --- | --- | --- | --- | --- | --- |
| Intro | 7 | 7 | 7 | 6 | 7 | 6 |
| Verse | 7 | 6 | 7 | 6 | 6 | 6 |
| Build | 7 | 6 | 8 | 7 | 7 | 6 |
| Drop | 7 | 8 | 8 | 7 | 7 | 7 |
| Break | 7 | 6 | 7 | 6 | 7 | 6 |
| Vrs2 | 7 | 7 | 7 | 6 | 6 | 6 |
| Drop2 | 7 | 8 | 8 | 7 | 7 | 7 |
| Outro | 8 | 7 | 8 | 7 | 7 | 7 |

M musicality; C creativity; G genre/proposal; L Lunar features; S space/project feel; N novelty. Novelty is relative to these four demos and their common template; no world-first claim.

**0 Intro.** [verified] 8 bars; bass gates 8–12 ticks; lead gates 18–48 ticks; main/answer simultaneous onsets 0. [inferred] The single eight-bar intro now progresses continuously instead of relaunching its lead silence. The high fragment is revealed in stages, but the same broad staging recipe as Neon remains apparent; use one distinctive half-time anticipation before Verse.

**1 Verse.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 8–12 ticks; main/answer simultaneous onsets 0. [inferred] The bass and simultaneous harmonic bed provide useful preparation. The main fragment remains a repeated short cell, with little common-tone treatment between root-position chord stacks. Develop a held answer or harmonic top-line into the build.

**2 Build.** [verified] 4 bars; bass gates 5–72 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] Wide support and the final note-off withdrawal suit the proposed build/drop relationship. Its timbral ramp still follows the common two-lane design; a chord-envelope or harmonic-register change tied to the last two bars would distinguish this build.

**3 Drop.** [verified] 8 bars; bass gates 5–84 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] Both four-bar halves now have different bass/harmony/lead responses, and the formerly unexplained D6 reply is corrected. The bar4 G4 chord answer double-triggers at tick1488 with competing24/54 gates. Consolidate it, and vary at least one chord-swell attack length within the second sentence to avoid a uniform two-beat bed.

**4 Break.** [verified] 4 bars; bass gates 8–12 ticks; lead gates 8–12 ticks; main/answer simultaneous onsets 0. [inferred] The kickless break remains a real energy reset. Its78-tick repeated chord stabs and repeated C5 fragment still resemble the same template used by other contrast scenes. Expose a sustained colour tone or a single delayed response before re-entry.

**5 Vrs2.** [verified] 8 bars; bass gates 5–84 ticks; lead gates 8–8 ticks; main/answer simultaneous onsets 0. [inferred] The chronological reversal and altered bass differentiate the second verse. Its short fragment still lacks an eight-bar destination; a held common tone followed by a syncopated pickup would give the break a stronger consequence.

**6 Drop2.** [verified] 8 bars; bass gates 5–84 ticks; lead gates 12–48 ticks; main/answer simultaneous onsets 0. [inferred] Peak2 now changes its second half harmonically and melodically, and reply range is controlled. Bar4 Ab4 chord answer is duplicated at tick1488. Also assess the inherited first-half chromatic transposition as a melody, not just a mathematical fourth: the Gb5 at tick1416 is a conspicuous colour before C6 and the lower F4 restart.

**7 Outro.** [verified] 4 bars; bass gates 40–384 ticks; lead gates 72–384 ticks; main/answer simultaneous onsets 0. [inferred] The final full-bar F-minor sustain now supports the closing low F. The Ab4-to-F3 lead drop is15 semitones; bridge the registers if the desired effect is a graceful landing. The root-position harmonic movement still leaves the outro less distinctive than its formal closure.

**Every occurrence and outgoing transition.** Scores in the JSON apply to each listed occurrence; the scene scores already incorporate its longest repeated span and transition role. No occurrence is treated as independently varied merely because effects continue. Repetition itself is permitted.

- Bars 1–8: Intro → Verse. First occurrence; role and next-scene arrival inspected.
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

**Whole-song pacing.** [inferred] The continuous entrance and developed eight-bar drops improve pacing across both32-bar peak spans. Uniform chord-swell durations and sparse repeated verse/break cells still constrain development; no additional repeated-occurrence feature is required.


## Packet Bloom

[verified] 112 BPM, 88 bars; SHA256 `a015448cd7a9740650d32db526e5bffabb2d48c83531da54d8dae86becf3348b`. No complete event/lock-identical scenes remain.

| Scene | M | C | G | L | S | N |
| --- | --- | --- | --- | --- | --- | --- |
| Intro | 7 | 7 | 7 | 7 | 7 | 7 |
| A-side | 7 | 6 | 7 | 7 | 7 | 6 |
| Build | 7 | 6 | 7 | 7 | 7 | 6 |
| Bloom | 8 | 8 | 8 | 7 | 8 | 7 |
| Glitch | 8 | 8 | 9 | 8 | 8 | 8 |
| B-side | 7 | 7 | 7 | 7 | 7 | 7 |
| Bloom2 | 8 | 8 | 8 | 7 | 8 | 7 |
| Outro | 8 | 7 | 8 | 7 | 8 | 7 |

M musicality; C creativity; G genre/proposal; L Lunar features; S space/project feel; N novelty. Novelty is relative to these four demos and their common template; no world-first claim.

**0 Intro.** [verified] 4 bars; bass gates 6–10 ticks; lead gates 18–24 ticks; main/answer simultaneous onsets 0. [inferred] The actual stronger Warble now gives the staged fragment a clearer unstable identity. The intro still uses the common silence/one-note/two-note/pickup structure; a deliberate short transmission-like pause before its pickup would make the opening more individual.

**1 A-side.** [verified] 8 bars; bass gates 4–72 ticks; lead gates 4–6 ticks; main/answer simultaneous onsets 0. [inferred] The asymmetric groove and held bass foundation remain credible. The repeated two-note motif could use a two-bar answering rhythm; the new chromatic approach is confined to Glitch and does not by itself develop this scene.

**2 Build.** [verified] 4 bars; bass gates 4–72 ticks; lead gates 6–48 ticks; main/answer simultaneous onsets 0. [inferred] The final note gap and curve work. A brief phrase-specific decay or pitch interruption would connect this build to the later Glitch identity rather than relying on the same increasing-density mechanism as the other songs.

**3 Bloom.** [verified] 8 bars; bass gates 4–84 ticks; lead gates 6–48 ticks; main/answer simultaneous onsets 0. [inferred] The second sentence now changes harmonic order, rhythm and contour, and replies occupy a restrained chord-tone register. The high-low main motif still restates its contour every ordinary bar; one lower answer with a longer gate could further separate call from reply.

**4 Glitch.** [verified] 4 bars; bass gates 6–10 ticks; lead gates 4–18 ticks; main/answer simultaneous onsets 0. [inferred] The third bar has no other new ensemble attacks, no previous event gate crosses into it, and C#4 resolves by semitone to D4 at its end. This directly realizes the interruption and chromatic-resolution brief. Effect tails may continue. Preserve this strong scene; a more distinctive return rhythm could further strengthen its surprise.

**5 B-side.** [verified] 8 bars; bass gates 5–84 ticks; lead gates 6–10 ticks; main/answer simultaneous onsets 0. [inferred] The reversed fragment and distinct bass provide contrast, with stronger Warble now in the actual file. The hoped-for high/low role exchange is still modest: use one lower sustained phrase followed by the original high hook as a pickup into Bloom2.

**6 Bloom2.** [verified] 8 bars; bass gates 4–84 ticks; lead gates 6–48 ticks; main/answer simultaneous onsets 0. [inferred] The second four-bar phrase is now written separately and no longer duplicates the first; replies are controlled and harmonic. The held F5 endpoint over Dm9 is a valid minor-third colour. A clearer handoff between high main and lower reply, using differing durations rather than nearly all short gates, would improve conversation.

**7 Outro.** [verified] 4 bars; bass gates 40–384 ticks; lead gates 72–384 ticks; main/answer simultaneous onsets 0. [inferred] The full closing D-minor chord and bass sustain now support the low D lead. The G4-to-D3 descent spans17 semitones and could use an intermediate A3/F4 gesture. Let the final Warble tail be judged by listening before claiming an especially graceful exit.

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

**Whole-song pacing.** [inferred] The Glitch interruption now creates a decisive structural contrast, and both peak halves develop. Stronger actual Warble supports identity. The ending register handoff and mostly short answering articulations remain the main musical limitations.


## Neon Transit

[verified] 120 BPM, 104 bars; SHA256 `92098c2e3369ad0e17ae069030664df596634a75f1f0ac3d67534ac0b65fbad6`. No complete event/lock-identical scenes remain.

| Scene | M | C | G | L | S | N |
| --- | --- | --- | --- | --- | --- | --- |
| Intro | 7 | 7 | 8 | 6 | 7 | 6 |
| Verse | 7 | 6 | 7 | 6 | 6 | 6 |
| Pre | 7 | 6 | 8 | 7 | 6 | 6 |
| Chorus | 7 | 7 | 8 | 7 | 7 | 7 |
| Bridge | 7 | 6 | 7 | 6 | 7 | 6 |
| Vrs2 | 7 | 7 | 7 | 6 | 6 | 6 |
| Chor2 | 8 | 8 | 8 | 7 | 7 | 7 |
| Outro | 8 | 7 | 9 | 7 | 7 | 7 |

M musicality; C creativity; G genre/proposal; L Lunar features; S space/project feel; N novelty. Novelty is relative to these four demos and their common template; no world-first claim.

**0 Intro.** [verified] 8 bars; bass gates 8–10 ticks; lead gates 18–48 ticks; main/answer simultaneous onsets 0. [inferred] The continuous eight-bar entrance fixes the repeated staging reset. It develops the high motif toward Verse. The pattern remains similar to Event intro; a rhythm taken specifically from the E–G–B hook would establish stronger electropop identity.

**1 Verse.** [verified] 8 bars; bass gates 5–72 ticks; lead gates 6–12 ticks; main/answer simultaneous onsets 0. [inferred] The bass ostinato and compact fragment remain coherent. Nearly all lead gates are short, so the promised sung character is still implied more by pitch contour than articulation. Write a held two-bar endpoint and a subsequent contrasting pickup.

**2 Pre.** [verified] 4 bars; bass gates 5–72 ticks; lead gates 9–48 ticks; main/answer simultaneous onsets 0. [inferred] The final withdrawal makes an effective arrival cue. A voiced suspension resolving at the chorus entry would add harmonic direction to its otherwise familiar lock ramp and short-note fragment.

**3 Chorus.** [verified] 8 bars; bass gates 5–84 ticks; lead gates 9–48 ticks; main/answer simultaneous onsets 0. [inferred] The second sentence now changes chords and contour, landing on E4 over Cmaj7. The first sentence chord answer still duplicates F#4 at tick1488. Deduplicate that trigger, and lengthen a defining hook note so the refrain has a recognizable sung rhythmic identity.

**4 Bridge.** [verified] 4 bars; bass gates 8–10 ticks; lead gates 6–12 ticks; main/answer simultaneous onsets 0. [inferred] The kickless bridge does subtract energy, but its repeated short B4/D5 fragments and two78-tick chord attacks still share the generic contrast design. Hold one melodic tone against changing harmony, then use an explicit pickup into Vrs2.

**5 Vrs2.** [verified] 8 bars; bass gates 6–84 ticks; lead gates 6–6 ticks; main/answer simultaneous onsets 0. [inferred] The reversed phrase and new bass help establish the return. Give its last two bars a different articulation and a clear B-to-E or F#-to-E destination; unchanged fragment lengths limit the claimed sung shape.

**6 Chor2.** [verified] 8 bars; bass gates 5–84 ticks; lead gates 9–48 ticks; main/answer simultaneous onsets 0. [inferred] The second sentence now ends on E4 with supporting Cmaj7, improving the earlier unresolved cycle. The first half still holds C5 over Em7 before jumping to E4 over G; an explicit B4 resolution before the handoff would strengthen that suspension. Overall phrase development is materially better.

**7 Outro.** [verified] 8 bars; bass gates 36–384 ticks; lead gates 24–384 ticks; main/answer simultaneous onsets 0. [inferred] The single eight-bar exit now has a B4–G4–F#4–E4 descent and a complete final tonic/chord/bass hold. Drum withdrawal in the last four bars supports the closure. This is a strong match to the ending proposal; a signature closing rhythm or modulation gesture would be needed for exceptional novelty.

**Every occurrence and outgoing transition.** Scores in the JSON apply to each listed occurrence; the scene scores already incorporate its longest repeated span and transition role. No occurrence is treated as independently varied merely because effects continue. Repetition itself is permitted.

- Bars 1–8: Intro → Verse. First occurrence; role and next-scene arrival inspected.
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

**Whole-song pacing.** [inferred] The continuous opening, two-sentence choruses and single descending exit give this the clearest formal closure. Sung articulation and the first-half suspension resolution remain underdeveloped despite the improved harmonic destination.
