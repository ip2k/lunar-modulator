# Satellite Hearts independent source critique — 2026-10-11

Qualitative follow-up under the replacement-showcase brief; no additional numerical scoring round, owner approval, or listening claim. Reviewed writer worktree `satellite-hearts-rewrite`, head `442861a46194d9062ace423fdeafca3f5320e987`. No reference recording or rendered song was auditioned. Runtime work is separately pending on the parent/writer paths.

## Exact evidence

[verified] Parsed `engines/state/examples/satellite-hearts.lunar` through the repository canonical loader; compared it with `build_satellite()` in `tools/showcase_songs.py` without writing the writer tree. Canonical documents equal; web mirror bytes equal. SHA-256: `c065e98aa0137417c2baf4f1e2dac357651bc117476604b554e8713371814d69`. Generator assertions ran as part of the read-only build. This verifies source consistency and authoring invariants, not native/Wasm playback.

[verified] Four slots: Comet Classic, Drawbar Bass, Shapes Saw/Sqr, Drawbar Mellow. 124 BPM straight pulse; six uniquely authored scenes 4/12/8/16/8/12 bars, 60 total. All arpeggiators disabled; modulation cables empty; master reverb Mix .07. Lead register in Hearts C5–A5 with C6 answering notes; chords B3–A4, bass C2–A2. Return lowers the main lead one octave in its last four bars and ends on a written C note. Window removes hats/claps completely and removes kick in its first four bars.

## Musical judgement from composition, not sound

[inferred] The short stop-start melody has a credible electropop identity: E–G–E–D statement, upward C–D–E–G answer, A peak, descent toward C. Its irregular sixteenth placement and short gates separate it from an arpeggiator. Low organ bass, midrange organ stabs and high synth melody create a deliberate register plan; the dry direct kit and asymmetric six-scene arc distinguish it from the rejected legacy shared template. That is a promising composition, not a perceptual pass.

[inferred] C-major brightness, recurring borrowed iv and clipped Shapes lead support an optimistic, mechanical dance identity. Source space-theme evidence is modest: an isolated pickup, wide-register answer, sparse Window and dry articulation rather than another washed chord bed. A space name alone does not supply musical novelty. Actual Shapes sharpness, two-organ balance, bass weight, kick/clap sound and perceived space require listening.

## Actionable revision requests sent to writer

1. **Hearts needs development within its 16 bars.** [verified] All eight tracks' bars 4–15 exactly match the immediately preceding four-bar cycle. [inferred] Repetition is valid dance vocabulary, but four identical orchestration cycles make this showcase's longest scene read as a loop demonstration. Preserve the signature cell; withdraw the lead or one backing layer near bar 7/11, then return an altered answer or rhythm. Prefer one authored event to arbitrary note proliferation.
2. **Window needs the promised new melodic function.** [verified] Its eight bars contain only four Shapes notes, alternating Ab4/G4 in bars 1/3; bass and chords remain intermittent root/stack roles. [inferred] The subtraction is useful, but this is a texture hinge rather than the plan's contrasting instrumental melody. Write a short lower-register countermelody with a shaped endpoint leading into Return, keeping the exposed space.
3. **Mark phrase endings with drum behavior.** [verified] Four-on-floor kick, two claps and offbeat hats recur with the same within-bar accents; the last Lift bar adds one snare note. [inferred] The straight quantized feel should remain; add a few purposeful stop/pickup gestures at selected 4/8-bar boundaries instead of generic rolls or globally humanizing the kit.
4. **Describe borrowed-color timing accurately.** [verified] Fm already appears every fourth Verse bar, before Window. [inferred] Keep it as a recurrent emotional color if intended, but do not describe Window as its first reveal; development of the color matters more than moving it solely for a label.

## Collection contrast

[verified from current matrix and Satellite asset] Satellite avoids Afterglow's Punch/Macro/FM6 foreground, Event's Deep/SixOp/Trio/Acid palette and Packet's reserved Crater/Phase Bend/Heavy Modal/Sophie texture. Its 124 BPM straight dance pulse and major hook contrast with the 92 chillwave, 144 half-time future bass and 82 fractured modal targets. [inferred] This is substantive source contrast, but the four songs must still be compared by ear; preset-family separation cannot guarantee perceptual separation.

## Tools and limits

Approved `production-guidance`, `mc-arrangement-arch`, `mc-rhythm-groove`, and `mc-style-edm` skills informed the review. Read Rarefaction status and Serena initial instructions/config: both selected the main checkout; Serena reported cpp only. Rarefaction rejected the actual absolute Satellite generator path as outside its root. No shared server selection was changed during concurrent writer work. File inspection and canonical parsing are the practical fallback; neither MCP indexed this reviewed Python branch.

## Active handoff

Writer received the four source findings directly. Revision review remains active; append the returned exact head and asset hash below before concluding this subtask. Parent owns full render, canonical runtime admission, generic catalog integration, CI/review/merge, and owner listening. The original five scored rounds remain closed. This document does not authorize hardware activity or acceptance.

## Packet extended source review

Reviewed `build_packet()` at writer committed head `1cbe4e7078529272d337f14445c4ab99c5cc38f3`; Satellite revisions were in progress, so this is not a new exact-Satellite receipt. [verified] Packet source defines Crater / Phase Bend Double Sine / Macro Heavy Modal / Sophie, 82 BPM, 8/10/6/12/4-bar form. Modal calls use uneven entries and a fully empty third bar; percussion and Modal have authored positive/negative tick nudges. Hinge removes bass and Crater tracks, leaving two sustained Modal calls and one Sophie accent. Tail uses two single Modal notes with one bass/kick entrance. These are substantial structural differences from Satellite and the inherited legacy arrangement.

[inferred] Exposed resonant calls and sparse tuned percussion offer a better novelty/space vocabulary than a shrill chord bed. The slow broken drum placement, absence of harmonic stacks, and open intervals should create different motion from Afterglow; whether resonance actually avoids the rejected harshness remains a listening question.

[verified] Packets and Bloom retain the same alternating kick/hat/backbeat patterns and Sophie placements; Bloom first eight bars repeat the four-bar call twice, then its last four bars lower it one octave. [inferred] Ask for one transformed percussion relationship or answer-only bass/drum bar in Bloom to distinguish the main return from the accumulating passage. Keep silence and the recognizable modal call; random busyness would damage its identity.

[verified] Pitched voices use E/A/B bass, B/D/E/F#/A call, F# hinge, and A/D answering notes; no C# establishes the characteristic Dorian sixth. [inferred] Either describe this as E-modal material or deliberately introduce that color in a short answer. A sequencer scale declaration alone does not create Dorian harmonic identity. Sophie pad Tune settings do not prove concert-pitch tuning or perceived harmony; actual resonant pad output needs auditioning. These points were sent directly to writer.
