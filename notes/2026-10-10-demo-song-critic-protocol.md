# Independent demo-song critique

Owner request, 2026-10-10: an independent adversarial music critic reviews
every section of the four demo songs and gives actionable feedback to the
writer. Use up to five review rounds, stopping early only when every section
scores strictly above 8 in every category. A remaining shortfall after round
five must be reported, rather than hidden by an average or inflated scores.

Songs: Afterglow Relay (chillwave), Event Horizon (future bass), Packet Bloom
(vapor twitch), and Neon Transit (electropop). Their current proposals contain
eight scenes each; repeated scene occurrences and transitions also need review.

Each report records the exact asset commit and render identity, then scores
musicality, creativity, genre/proposal adherence, Lunar Modulator feature usage,
project feel/space theme, and novelty from 1 to 10 for every section. Integer
scores of 9 or 10 meet the threshold. Include evidence, concrete fixes, and
the next round's disposition of earlier feedback. Whole-song pacing and
transitions need explicit comments even when individual scenes score well.

The critic uses the previously adopted production, arrangement, groove, and
electronic-music guidance. It reviews independently before considering the
writer's self-assessment. It must not substitute feature count for musical
quality or treat space-themed titles as sufficient sonic identity.

Keep round reports, score tables, revision notes, and final unresolved issues
in the repository. Preserve round asset identities so changes can be compared.
The writer owns assets; the critic owns reports; integration owns executable
acceptance tests and final packaging. Reports and coherent revisions receive
focused commits and verified GitHub backups.

Evidence limits: source/score analysis and rendered-signal measurements must
be distinguished from perceptual listening. A critic without an audio
perception interface must say so and cannot claim that it heard a render.
Numerical render acceptance does not establish musical quality. The owner's
final listening evaluation remains separate from the critic's judgment.

Owner clarification, 2026-10-10: the critic can inspect the simulator itself
and analyze project files programmatically. Waveforms are supplementary evidence,
not the sole basis for any category. Inspect decoded notes, pitch/register,
gates, velocity, harmonic movement, rhythmic variation, routing, modulation,
locks, scene order and each repeated occurrence. Check actual browser loading,
playback state and Save/Open preservation against the scored asset identity.
Tie each score and requested revision to concrete project or simulator evidence;
keep observed behavior separate from inferred musical consequences.

Current state: Rounds 1 and 2 have been scored without a passing scene/category
threshold; complete native/Wasm and Chromium Save/Open acceptance passed for
both. Round 3 is frozen at cdf8d8fcc0bd89518f3fe28ec1a6661a827c19bc;
its independent source review and fresh executable acceptance are in progress.
The writer is preparing Round 4 from specific structural findings. No musical
acceptance or perceptual listening has been claimed.
