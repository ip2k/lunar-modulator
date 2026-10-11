# Afterglow: new composition review

## Reset and evidence boundary

[reported] The owner rejected Afterglow after the focused sound/groove repair and requested a fresh composition using the supplied references, with **FM6 LUNAR LEAD as the main voice**. The repair candidate `25383aed0e22283a772e21029cd53661982672a4` and its runtime pass remain historical evidence, not acceptance of the music. This new review does not reopen or raise the five-round scores.

[verified] The critic has no exposed audio-perception interface. Reading event data, patches, engine source and runtime receipts can test composition and implementation, but does not establish how either reference or the new song sounds. Owner listening is the perceptual gate. No reference notes, recordings, samples or presets are to be imported.

## Reference-derived design brief

Owner targets: [Neon Indian — Polish Girl](https://www.youtube.com/watch?v=GuPGZZgNFsU) and [Tycho — Awake](https://www.youtube.com/watch?v=6XJBDX3Z0BY).

[reported] Scott Hansen's first-person [official Song Exploder transcript](https://songexploder.net/transcripts/tycho-transcript.pdf) describes Awake beginning with Zac Brown's guitar fragment, then a driving bass line. He describes precise editing beneath less mechanical material, a muted picked guitar layer, round midrange synth sounds, and filtering/processing as part of the record's identity. He also discusses the influence of an instrumental passage that changes the song's direction. These are artist-described construction choices; this critic has not heard the isolated stems or the recording through an analysis interface.

[reported] [Reverb Machine's Neon Indian reconstruction](https://reverbmachine.com/blog/neon-indian-synth-sounds/) describes a short percussive synth sequence, rhythmic filtered chord plucks, gliding lead gestures and separate spatial arpeggio layers. It is the author's reconstruction, not an original session account or proof of the artist's settings.

[inferred] Translate these roles into an original Lunar composition: a memorable FM6 foreground phrase, bass with forward motion, rhythmically complementary chord attacks, a restrained answering layer and a bridge that changes phrase function. The references support specific interactions between parts, not a generic slow pad with large reverb. Keep the owner's clearer Hall Mix 0.05 as an audition starting point; reference research does not override the owner's direct preference.

## Review targets for the frozen draft

1. **Hook identity.** Decode the lead's pitches, onset pattern, durations and rests. Identify a recognizable contour and rhythmic fingerprint, then an answer or altered ending that makes repetition purposeful. A six-note count alone proves nothing. Check the hook against changing bass/chord tones and determine whether held non-chord notes resolve deliberately.
2. **Instrument identity.** Confirm the actual track routes to FM6, selects the embedded User 1 LUNAR LEAD voice, and receives no unexpected transpose, pitch modulation or competing foreground part. Trace carrier/modulator behavior where relevant; the earlier correctly written chords still sounded through an unintended detuned oscillator pair.
3. **Rhythmic articulation.** Inspect actual sounding envelopes and model behavior as well as MIDI gates. Eighth-note chords should leave useful gaps and complementary accents rather than mask the main voice. Check bass/kick alignment, backbeat hierarchy, drum pad decay and explicit timing plus runtime swing. Precision can be intentional; random offsets are not a substitute for a coherent groove.
4. **Harmony and development.** Check voice leading, register separation and phrase arrivals. A bridge must change the listener's expectation through harmonic, melodic or rhythmic function, not merely mute the same accompaniment. Inspect both hook returns and every repeated scene in chain context; eight scene labels do not establish eight musical functions.
5. **Feasibility and clarity.** Verify emitted project identity, browser copy equality, engine/effect compatibility, polyphony, RAM and event/lock limits. Runtime rendering must load without repair/drop, retain finite nonzero audio and stop correctly. Those checks do not certify tonal balance, compelling melody or a reference match.

[reported] Writer's initial concept retains A minor, 92 BPM and eight scenes, with a newly composed FM6 hook, eighth-note chord pulses, a counterline, driving bass/drums and a subtractive bridge. Frozen source is pending. The review will judge the emitted project rather than treat this proposal as implementation evidence.

## Tool and handoff state

[verified] This continues the previously documented skill adoption and semantic-tool evaluation in `2026-10-10-demo-song-critic-ledger.md`. Shared MCP roots are not retargeted during other active sessions. Exact Git source/project inspection is the fallback for the writer's frozen checkout. Critic owns this report only; writer owns assets; parent/writer own full runtime renders. No hardware test or by-ear acceptance is claimed.

The frozen-source reviews below supersede this initial pending handoff. Runtime and owner listening remain separate gates.


## First new-composition freeze: 7ff52ac (reviewed 2026-10-11)

[verified] Reviewed exact `7ff52ac873f38d13077e56b61e3511fb2f912bd3`, especially `tools/demo_songs.py` and decoded `engines/state/examples/afterglow-relay.lunar` (SHA-256 `48e5288259358123b16d9a3886628d9dc850b833c3f0f7fb1a070357f4f00e66`). This is a fresh composition review, with no sixth numeric scoring round and no reuse of earlier musical acceptance.

[verified] The first freeze contained concrete pitch-generation defects, sent directly to the writer and parent before acceptance:

- Bass quality detection used `chord_quality(label).startswith("m")`, treating `maj7` as minor. Fmaj7 received Ab2 pickups and Cmaj7 received Eb2 pickups.
- The verse applied fixed minor intervals to every chord. Fmaj7's lead became F4–C5–Eb5–Ab4; Cmaj7's became C5–G5–Bb5–Eb5. The lift had the same fixed-minor problem.
- The early bridge tested `label.startswith("m")` against `Am7`, selecting C#5 above A. Later bridge contours were degree-like small integers added as semitones: examples include C5–D5–Eb5–C#5 and A4–B4–C#5–Bb4.
- Verse 2 introduced C# over Am, and Hook 2's late ending subtracted two semitones from a minor third, producing an unresolved Bb4 held for 48 ticks over Am.
- C-root hook phrases received an extra octave, reaching B5 while F-root phrases began at F4. This contradicted the compact-register description and risked repeating the owner's shrillness complaint.

[inferred] Out-of-key notes are not inherently errors. These were flagged because source operations contradicted the named chord quality or applied undirected semitone edits without a composed preparation/resolution. Making all notes diatonic is a repair guard, not a sufficient musical-quality test.

## Corrected freeze: 28266aab

[verified] Reviewed `28266aab9dba17567608a72cdb2d515df7db2990`. Emitted project SHA-256 is `fe5b515119aca60405c13e21b92c68f7a6c17a14acdd4480c5abfeb81633ccae`; source and browser copies are byte-identical. Git diff confirms quality-aware bass thirds, diatonic contour mapping, chord-tone replies/endings and removal of the special C-root octave. The previously identified unintended chromatic notes are corrected.

### Hook, accompaniment and form

[verified] The six-note hook uses steps 0/3/5/8/11/14, gates 42/30/42/30/30/48 ticks, with an A-minor opening A4–E5–G5–E5–D5–C5. Its rise to the seventh followed by descent gives it an identifiable contour; the second four-bar sentence substitutes chord thirds and tonic endings. Hook 2 retains this identity over a changed progression. F and C phrases use major sevenths consistent with the written harmony. The last note's 48 ticks reaches the next bar boundary; envelope/reverb tails may extend farther.

[verified] Hook chords attack at steps 2/6/10/14: four offbeat, quarter-spaced pulses per bar. They are not eight consecutive eighth-note attacks. The corrected production sheet now calls this accurately. At 92 BPM, each 30-tick gate is approximately 204 ms, followed by roughly 448 ms to the next chord attack, before release tails. Lead and chord attacks interlock except at the final step 14. Short replies at step 13 sit between the lead's step-11 release and final attack in note-event time; this does not guarantee acoustic separation.

[inferred] This is a materially more reference-informed arrangement than the rejected sustained chord blocks: foreground hook, pulsing support and a bridge with a new broken-chord/lead gesture have explicit roles. It still needs the owner's judgment of memorability. A repeating arpeggio contour and more note attacks alone do not establish a compelling hook.

[verified] The chain remains 76 bars: Intro 1–4; Verse 5–12 repeated identically at 13–20; Lift 21–24; Hook 25–32 repeated at 33–40; Bridge 41–48; Verse 2 49–56; Hook 2 57–64 repeated at 65–72; Outro 73–76. The bridge's first half removes/thins parts; its second half adds a four-note lead contour and quarter-note broken chords. The outro writes C–F–G–Am and a long final tonic. Internal eight-bar variation exists, but the repeated scene occurrences have no extra authored changes.

[inferred] The repeated 16-bar verse/hook spans are listening checkpoints: if momentum stalls, shorten a repeat or alter its last two bars rather than add constant ornament. The bridge is structurally distinct; its new contour should feel like a related answer, not an unrelated exercise.

### Instrument and rhythm behavior

[verified] Tracks 3 and 7 route to sound slot 4: DX7 User 1, embedded name `LUNAR LEAD`. It is polyphonic, glide off, Brightness .50, Env Time .46, Feedback 0, Volume .70; lead insert Echo has Mix .08. Master Hall Mix is .05, Decay .36, Size .52. These are actual emitted parameters, not merely a proposal.

[verified] Chords use Macro VA+Filter, Harmonics .50, Timbre .30, Morph .25, Decay .28, Colour .32, Volume .62, Env Timbre .08 and LPG Gate. The external envelope-to-Timbre cable is amount 6 rather than the rejected amount 40. This avoids the earlier VA Pair detuned second oscillator and gives held note gates a sustaining role. It does not prove that the new chord timbre is pleasing. The bass retains its triangle-LFO cutoff movement and filtered/driven VA+Filter voice; FM patch identity alone does not describe the complete mix.

[verified] The inherited four-bar drum sentence has different kick placements and velocities, ghost hats on odd steps, and small backbeat offsets. Unlike the original all-even hats, these odd anchors respond to swing 56. Drum one-shot decay, not event gate length, determines ringing: effective kick/snare/hat decays from the repaired kit are .24948/.3612/.118272. No claim that arbitrary timing variation equals a convincing live groove is made.

### Remaining register decision and listening limits

[verified] A new discrepancy was sent to the writer: `afterglow_scale_pitch(root, degree)` receives the raw root, while hooks, replies and early bridge use `root + 12`. Verse Am now reads A3–E4–G4–C4, with its reply at C5. Early bridge Am is A4/C5 but its later contour is A3/C4/E4/B3. This can be an intentional lower verse and lifted hook, but it is an octave change beyond the stated consistent-root fix. Chord triads sit above much of the verse lead, contrary to the code comment that they stay below it. Decide this as orchestration and document it; do not mechanically raise every note merely to satisfy the old comment.

[inferred] Owner audition should decide three concrete questions: does the low verse-to-high hook register change make the FM6 motif feel like the same voice; do the short chord pulses leave the lead intelligible without the old harsh chord impression; and do the repeated 16-bar sections sustain interest before/after the bridge? Check the low verse and both hook returns at normal playback level, not just the loudest eight bars.

[verified] Source inspection cannot certify tonal balance, enjoyment, reference similarity by ear, hardware feasibility or runtime success. No audio perception was available and no by-ear comparison is claimed. Any runtime render of `7ff52ac` is stale for `28266aab`; attach exact new native/Wasm/browser receipts separately. The two supplied recordings remain research references, not copied melodies, patches or samples.


## Register-corrected freeze: c9f30bc — current source disposition

[verified] Rechecked exact `c9f30bc113952f056733550e8a0879d74c864889`. Project SHA-256: `762441f46b06c067d35ad41b500ec80086c54a5acb826de7cd729d9fa6c4d76b`; browser and source assets match. The writer chose consistent lead register and lowered the chord foundation. Scale-mapped phrases now receive `afterglow_pitch_base(root)`; chord triads use the written root rather than root + 12. Decoding all pitched clips (tracks 1/2/3/5/7, all eight scenes) finds no pitches outside A natural minor. The embedded User 1 voice is byte-for-byte equivalent as decoded JSON to the template's `LUNAR LEAD` definition.

[verified] Verse, lift and hook lead ranges are C4–G5; the second verse starts at D4 and reaches G5. The bridge spans C4–E5. Chord material spans C3–E4 normally and reaches G4 at selected hook extensions. The final outro intentionally descends to A3. Local chord and lead roles are separated by register more consistently; the formerly accidental octave split between verse and reply is closed. This resolves the specific register observation above and supersedes its listening question about a low verse versus high hook.

[inferred] **Current source disposition: ready for a fresh owner audition once exact runtime gates pass; no remaining definite pitch-generation blocker identified in this inspection.** This does not certify compelling music. The hook's repeated upward fifth and seventh followed by descent supplies a recognizable identity, but it remains arpeggio-derived. The owner should judge whether it is memorable after one hook cycle. Lower chord placement reduces competition with the FM foreground but creates a new low-mid balance question alongside the bass. The unchanged scene repeats remain a pacing question. Do not add random ornament or more wet effects simply to answer those concerns.

[verified] The review messages and findings were sent to the writer and parent against each exact freeze. No source/assets were edited by the critic. Earlier five-round scores remain historical and unchanged. Runtime receipts must identify this freeze or a later explicit successor; earlier successful playback does not validate these changed notes/registers. No direct hearing of the new composition or owner reference recordings is claimed.
