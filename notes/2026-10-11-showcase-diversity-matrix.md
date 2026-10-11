# Replacement showcase diversity matrix — 2026-10-11

This is a planning snapshot, not a musical approval or a claim that the
replacements are finished. The owner explicitly rejected all four original
songs as showcases; keep them as legacy example sequences. Each replacement
must still be a complete, chained project with at least four distinct scenes.
Across the collection, the songs must be **vastly different** in tempo/feel,
drum source and pattern, sound engines/presets/timbres, register/articulation,
hook rhythm, harmony, section topology and transitions. “Same arrangement with
different parameters” does not satisfy that requirement.

## Evidence at this snapshot

| Song | Owner brief and references | Current-source evidence | Status |
| --- | --- | --- | --- |
| Afterglow Relay | Chillwave; owner supplied Neon Indian “Polish Girl” and Tycho “Awake” as direction. Only reference titles/metadata and a reconstruction article/transcript were inspected in the cited work; no agent claims to have auditioned either recording. | The reference-informed rewrite is on `feature/2026-10-10@afterglow-reference-rewrite` at `810b5aff`. It uses Punch drums, two Macro voices (VA+Filter), and FM6 User 1 `LUNAR LEAD`; the FM6 is the foreground hook voice. Owner has rejected the prior chord/drum revision and asked for a fresh composition. | Replacement still needs owner listening; its eventual palette and form are not final. |
| Event Horizon | Future bass. Owner references: Disclosure “You & Me (Flume Remix),” San Holo “Light,” The Chainsmokers “Closer,” and Louis The Child “It’s Strange.” Titles were verified from oEmbed; no claim of direct listening. | The candidate in `feature/2026-10-11@event-horizon-rewrite` at `10d7fa98` uses Deep drums, SixOp `2 E.PIANO 1`, Trio Saw x3, and Acid Bass Square. Review found duplicated/retriggered notes, overlapping/short late-drop bass gates, and inherited repeated eight-scene form. | Owner rejected this rewrite; it must be recomposed. Palette is a reference point, not an accepted identity. |
| Packet Bloom | Vapor/twitch was the old label. Owner rejected the original for sounding too much like Afterglow, specifically calling out shrill Macro chords and the shared Punch / VA+Filter / VA Pair / FM6 palette. New references supplied: INZO “Overthinker,” Medasin “Everytime,” “Flips and Flops, Drips and Drops,” and Alina Baraz & Galimatias “Pretty Thoughts.” Titles verified from oEmbed, not listened to here. | The legacy project uses Punch drums, two Macro voices (VA+Filter and VA Pair), and FM6 User 1 `LUNAR LEAD`; the parent verified the saved file matched all 64 clips and source-defined sounds. | Parent owns a new composition. Palette, tempo, form and genre interpretation are intentionally TBD here. |
| Satellite Hearts | New electropop showcase, replacing the rejected Neon Transit. Owner references: Justice vs Simian “We Are Your Friends,” Justice “Neverender,” Eurythmics “Sweet Dreams,” and Robyn “Dancing On My Own (Rex The Dog Remix).” oEmbed metadata verified titles only; no claim of listening. | No Satellite project or sound palette has been authored. | This branch owns the new composition after the collection's other palettes are coordinated. |

## Contrast targets to hold during composition

| Dimension | Afterglow target | Event target | Packet target | Satellite target |
| --- | --- | --- | --- | --- |
| Energy / pulse | Loose, warm, humanized chillwave; an unhurried pulse with a recognizable short hook. | High-energy future-bass lift with a deliberately different half-time/full-time relationship, not simply a faster four-on-floor. | Parent to choose; avoid reuse of the old shared loop and determine whether “vapor/twitch” still describes the replacement. | Forward electropop dance pulse; clear beat, clipped hook rhythm and phrase-ending stops. Avoid both Afterglow's laid-back swing and Event's big half-time drop grammar. |
| Drum identity | Owner requested less masking/reverb and an authored chill groove; do not reuse the original repetitive even-step hats as the replacement identity. | Candidate uses Deep kit, but owner rejected the composition; any retained source choice must earn its place in the rewrite. | Must not inherit Punch as a default. Choose a distinct actual kit/source and a distinct accent/rest pattern. | A different engine-kit and a direct, mechanically clear pattern are desirable; candidate below is unverified and must not collide with Packet's choice. |
| Pitched palette | FM6 `LUNAR LEAD` is the owner's required main voice; compose a memorable original hook around it. | Candidate reference palette: SixOp EP + Trio Saw x3 + Acid Bass Square. Do not copy it into other songs. | Unassigned. Deliberately reserve/choose a palette that does not resemble FM6 + Macro or SixOp/Trio/Acid. | Provisional disjoint candidate below avoids FM6, Macro, SixOp, Trio and Acid. This is not approved or memory-checked. |
| Form | Write the replacement to the reference-informed chillwave brief, not the inherited eight-scene template by default. | Rewrite; old 8-scene / 116-bar plan is not accepted. | Parent to choose asymmetric scene lengths and a different topology. | Proposed six scenes with asymmetric lengths; one middle scene introduces a new melodic function, and the ending is composed rather than another loop. |

## Satellite candidate for collision review only

If Packet's chosen palette leaves these engines free, test a deliberately
non-overlapping sound-role set: Comet Kit (909-derived percussion), Drawbar
(tonewheel-organ stabs/bass), Shapes (one carefully selected short synth voice),
and Sophie (tuned metallic counter-percussion). This would avoid the known
Afterglow FM6/Macro and Event SixOp/Trio/Acid families and give Satellite a
brighter, more mechanically articulated vocabulary. It is only a candidate:
Comet and Drawbar include GPL-3.0-only code, Shapes has a large reported
instance footprint, and four-sound admission must be demonstrated on the real
state and renderer before keeping the palette. Do not choose it if it collides
with Packet or fails actual slot/RAM admission; do not silently substitute
similar engines and still call it distinct.

For a first form sketch only, test a 124 BPM straight dance pulse and six
asymmetric scenes of 4 / 12 / 8 / 16 / 8 / 12 bars (60 bars total): short
instrumental pickup, verse, lift, long refrain, contrasting instrumental
break, final refrain with a written cadence. The hook should be a short
stop-start cell with a clear answer rather than another arpeggio-derived
six-note line. Let the bass and percussion create forward motion while the
verse leaves room for that hook. These are proposals, not owner-approved
values; revise BPM/form once Packet's plan is known and after actual listening.

## Integration and acceptance sequence

1. Keep old projects preserved and labeled as legacy examples; do not publish
them as the four showcases.
2. Confirm Packet and Event palette/form decisions, then freeze this matrix
   before emitting Satellite assets. Reserve distinct drum sources and actual
   engine families across the four songs.
3. Implement showcases without sharing the legacy generator's fixed-four-song
   assumptions. Root owns generic project-name test support; coordinate any
   manifest/catalog changes rather than silently changing current examples.
4. Verify canonical load/save round trip, parameter admission, four-sound and
   memory limits, scene chaining, and full native/Wasm renders on exact asset
   hashes. Keep runtime acceptance separate from perceptual review.
5. Have the owner compare all four together. A successful render or source
   rubric is not a listening pass, and metadata from reference links is not
   evidence of hearing or resemblance.

## Provenance / limits

The file and palette facts above were read from the named checked-out
`.lunar` assets and branches on 2026-10-11; candidate reviews are not approvals.
The four reference lists are from owner instructions, with titles verified by
metadata in earlier project work. No reference audio was heard in this task.
No code or song assets were changed to produce this matrix.
