# Replacement showcase diversity matrix — 2026-10-11

This is a planning snapshot, not a musical approval or a claim that the
replacements are finished. The owner explicitly rejected all four original
songs as showcases; keep them as legacy example sequences. Each replacement
must still be a complete, chained project with at least four distinct scenes.
Across the collection, the songs must be **vastly different** in tempo/feel,
drum source and pattern, sound engines/presets/timbres, register/articulation,
hook rhythm, harmony, section topology and transitions. “Same arrangement with
different parameters” does not satisfy that requirement.

## Historical starting evidence (superseded by current acceptance below)

| Song | Owner brief and references | Current-source evidence | Status |
| --- | --- | --- | --- |
| Afterglow Relay | Chillwave; owner supplied Neon Indian “Polish Girl” and Tycho “Awake” as direction. Only reference titles/metadata and a reconstruction article/transcript were inspected in the cited work; no agent claims to have auditioned either recording. | The reference-informed rewrite is on `feature/2026-10-10@afterglow-reference-rewrite` at `810b5aff`. It uses Punch drums, two Macro voices (VA+Filter), and FM6 User 1 `LUNAR LEAD`; the FM6 is the foreground hook voice. Owner has rejected the prior chord/drum revision and asked for a fresh composition. | Replacement still needs owner listening; its eventual palette and form are not final. |
| Event Horizon | Future bass. Owner references: Disclosure “You & Me (Flume Remix),” San Holo “Light,” The Chainsmokers “Closer,” and Louis The Child “It’s Strange.” Titles were verified from oEmbed; no claim of direct listening. | The candidate in `feature/2026-10-11@event-horizon-rewrite` at `10d7fa98` uses Deep drums, SixOp `2 E.PIANO 1`, Trio Saw x3, and Acid Bass Square. Review found duplicated/retriggered notes, overlapping/short late-drop bass gates, and inherited repeated eight-scene form. | The owner heard and rejected the original Event, not this rewrite. The rewrite passed runtime checks; source-critic findings remain unresolved and owner musical acceptance is pending. |
| Packet Bloom | Vapor/twitch was the old label. Owner rejected the original for sounding too much like Afterglow, specifically calling out shrill Macro chords and the shared Punch / VA+Filter / VA Pair / FM6 palette. New references supplied: INZO “Overthinker,” Medasin “Everytime,” “Flips and Flops, Drips and Drops,” and Alina Baraz & Galimatias “Pretty Thoughts.” Titles verified from oEmbed, not listened to here. | Legacy project uses Punch/Macro/FM6 and remains untouched. Replacement `packet-bloom-showcase.lunar` is authored at source head `aa487f85`, with Crater/Phase Bend/Modal/Sophie, 82 BPM and five asymmetric scenes. | Source critique revised; exact-asset recheck pending. Runtime blocked by aeon connectivity; musical approval pending. |
| Satellite Hearts | New electropop showcase, replacing the rejected Neon Transit. Owner references: Justice vs Simian “We Are Your Friends,” Justice “Neverender,” Eurythmics “Sweet Dreams,” and Robyn “Dancing On My Own (Rex The Dog Remix).” oEmbed metadata verified titles only; no claim of listening. | Replacement `satellite-hearts.lunar` is authored at source head `aa487f85`: Comet/Drawbar Bass/Shapes Saw-Sqr/Drawbar Mellow, 124 BPM, six asymmetric scenes. | Source critique revised; exact-asset recheck pending. Runtime blocked by aeon connectivity; musical approval pending. |

## Contrast targets to hold during composition

| Dimension | Afterglow target | Event target | Packet target | Satellite target |
| --- | --- | --- | --- | --- |
| Energy / pulse | Loose, warm, humanized chillwave; an unhurried pulse with a recognizable short hook. | High-energy future-bass lift with a deliberately different half-time/full-time relationship, not simply a faster four-on-floor. | 82 BPM fractured, sparse pulse; off-grid pickups and silence rather than a steady dance grid. | Forward electropop dance pulse; clear beat, clipped hook rhythm and phrase-ending stops. Avoid both Afterglow's laid-back swing and Event's big half-time drop grammar. |
| Drum identity | Owner requested less masking/reverb and an authored chill groove; do not reuse the original repetitive even-step hats as the replacement identity. | Keep Deep kit while addressing source critique; the new composition has not received owner listening. | Must not inherit Punch as a default. Choose a distinct actual kit/source and a distinct accent/rest pattern. | Comet Classic has a straight pulse, phrase-end stops and small pickups; Packet separately uses Crater and fractured rests. |
| Pitched palette | FM6 `LUNAR LEAD` is the owner's required main voice; compose a memorable original hook around it. | Candidate reference palette: SixOp EP + Trio Saw x3 + Acid Bass Square. Do not copy it into other songs. | Crater drums, Phase Bend rounded bass, Macro Heavy Modal texture, Sophie tuned counter-percussion; no VA chord bed or FM6. | Authored Comet/Drawbar/Shapes set avoids the FM6/Macro/SixOp/Trio/Acid families. Source contrast reviewed; runtime and listening pending. |
| Form | Write the replacement to the reference-informed chillwave brief, not the inherited eight-scene template by default. | Rewrite; old 8-scene / 116-bar plan is not accepted. | Five scenes: 8 / 10 / 6 / 12 / 4 bars; exposed texture opening, accumulating passage, empty hinge, transformed main passage, dissolving tail. | Proposed six scenes with asymmetric lengths; one middle scene introduces a new melodic function, and the ending is composed rather than another loop. |

## Earlier Satellite sketch, superseded by the freeze below

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
2. Use the concrete palette/form freeze below, then resolve Event source critique
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
The original snapshot was documentation-only; subsequent composition milestones are recorded below.

## Concrete composition freeze — 2026-10-11

These are implementation targets chosen under the owner’s composition authorization,
not musical approvals. Existing Afterglow and Event candidates stay at their current
92 / 144 BPM until their writers intentionally revise them; no tempo-only rewrite
satisfies this matrix.

| Song | Pulse / drums | Four sound slots | Harmonic and hook identity | Form |
| --- | --- | --- | --- | --- |
| Afterglow | 92 BPM loose chillwave; Punch, quiet uneven hats | Drums / Macro VA bass / warm Macro VA chords / FM6 LUNAR LEAD | A-minor warmth, foreground FM hook; avoid arpeggiator-driven identity | Current eight-scene form requires deliberate contrast review |
| Event | 144 BPM energetic half-time; Deep, restrained hats | Drums / SixOp EP / Trio Saw x3 / Acid Square | F-minor lift, per-note Trio filter envelope, long held bass; Acid post-note release capability gap remains explicit | Seven proposed distinct sections 8/12/4/16/8/16/4 bars; repair overlaps before emission |
| Packet | 82 BPM fractured space; Crater, irregular rests | Crater / Phase Bend / Macro Heavy Modal / Sophie | E Dorian modal pedal, dispersed pitched-percussion calls; no repeating chord-stack bed | Five sections 8/10/6/12/4 bars, 40 total |
| Satellite | 124 BPM straight four-on-floor; Comet Classic | Comet / Drawbar Bass / Shapes Saw-Sqr / Drawbar Mellow | C-major pop with borrowed F-minor color; clipped independent hook, low octave bass and midrange chord stabs | Six sections 4/12/8/16/8/12 bars, 60 total |

Satellite drops Sophie from the provisional sketch to reserve its metallic
counter-percussion for Packet. Two Drawbar instances serve different registers and
envelopes. Packet’s Modal model shares Macro lineage with Afterglow but is a
physical-model texture, not its VA oscillator/filter palette; actual collision
review still needs listening. Satellite’s 16-bar longest scene fits the verified
256-step clip limit in `engines/include/fm1_seq.h`. Four-slot admission and exact
asset runtime checks remain required. No reference recording was auditioned.

## Current asset boundary

Composition source head `aa487f85d9603fb7a8183061e73ee52164577b1f` was
pushed and remote-SHA verified. Satellite SHA-256
`b797a827904fd9899c423c9b0719c25d54f53697eff3def1f491053be73dd8a7`;
Packet replacement SHA-256
`d66291ba86df901ea3f8f3897aeeb25ca6c643d29d6841f5bf1d98bd520dab4c`.
Both source/web mirrors match byte-for-byte and regenerate deterministically.
The generator's actual registry bounds/enums, complete per-pad records,
metadata cap, 512-note clip cap, note boundaries and pitched same-key overlap
checks pass. Independent critique prompted authored phrase development and
percussion contrast; exact returned-asset source recheck remains pending.
Native/Wasm admission and full renders are blocked because bounded aeon SSH
returned `Host is down`; browser integration and owner listening remain open.
No merge, reference audition or hardware test has been performed.

## Four new source assets checkpoint

Afterglow now 104 BPM, Porch8 / Relay16 / Drift12 / Home8 (44 bars), FM6 LUNAR LEAD foreground, Macro VA+Filter chord/bass voices and restrained Punch. Event now150 BPM, Air8 / Call12 / Rise4 / Impact16 / Suspense8 / OpenSky16 / Land4 (68 bars), Deep/SixOp EP/TrioSawx3/AcidSquare. OpenSky final half withdraws the main hook for a three-note answer, shifts kick and backbeat, then returns to a composed F landing. Both preserve required patch work while replacing all prior clips/chain. Source guards pass; exact runtime and independent source review pending. Satellite/Packet native/Wasm pair now passed at f09319bf; stale earlier connectivity-blocked statuses are superseded. Owner listening remains pending for every new song.

## Current returned-source and exact runtime status

| New showcase | Tempo / form | Final asset SHA256 | Source/runtime status |
| --- | --- | --- | --- |
| Afterglow Relay |104 BPM,44bars,4scenes|53373bf4c508d360eccdf2751fd4242f23478d575adf893a703e6179dcd9c77f|Independent source critique no blocker; native/Wasm and browser passed exact18a30185.|
| Event Horizon |150 BPM,68bars,7scenes|0d5d871bd31db1e628efbf291fd306671b81c93bef254a950291bf95f5413d1c|Final Fm cadence/lower C6 saw register confirmed by returned critic; native/Wasm/browser passed exact3022009c.|
| Packet Bloom |82 BPM,40bars,5scenes|d66291ba86df901ea3f8f3897aeeb25ca6c643d29d6841f5bf1d98bd520dab4c|Returned source no blocker; native/Wasm/browser passed; independent Hera Docker Wasm also passed.|
| Satellite Hearts |124 BPM,60bars,6scenes|2e714212f88cb7db22dc9041bdfe23dbb33160965a037a43b2a937578ff0f7ee|Window correction confirmed; source critique no blocker; native/Wasm/browser passed exact18a30185.|

Exact receipts: notes/2026-10-11-four-showcase-18a30185 and notes/2026-10-11-event-showcase-3022009c. Critic returned report fa6bbeb3face958e02ac7fb04f1bd1f9a1a099f2. All prior connectivity blocks are superseded. Owner listening remains pending for all four. Acid longer held notes are authored; a new Acid post-note amplitude-release control is not implemented by this composition stream. Final integration/catalog/CI/merge belongs to parent.
