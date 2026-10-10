# Demo-song independent critic ledger

## Scope and acceptance

The owner requests up to five writer/critic rounds, with every section scoring
strictly above 8/10 in all six categories. A 9 or 10 passes; an average does
not. Evaluate the 32 named scenes, each occurrence in its full chain, boundary
transitions, and whole-song pacing. Review the frozen asset commit before
reading the writer's self-assessment. Do not score unfinished drafts.

Scores are independent, subjective **source-level musical judgments** until
perceptual evidence is available. This critic has no exposed audio-perception
interface and does not claim to listen. Audio measurements can identify signal
defects or verify timing/contrast, but cannot certify compelling music. Owner
listening remains separate. A source-score pass must never be described as a
listening pass or proof of world novelty.

## Rubric

| Category | Evidence required for 9–10 | Common shortfall |
| --- | --- | --- |
| Musicality | Coherent motif, voice leading, rhythm and phrase direction; space and arrival serve each scene's function | Correct notes repeated without development; accompaniment masks or contradicts the hook |
| Creativity | Specific, purposeful transformations or surprising relationships that strengthen the composition | Generic density changes, arbitrary extra notes, scene labels substituting for compositional differences |
| Genre/proposal adherence | Actual note lengths, rhythmic feel, palette, harmony and sectional behavior realize the agreed proposal | BPM/name alone; harmony or bridge/build behavior contradicts the production sheet |
| Lunar feature usage | Supported modulation, locks, routing and scene/song behavior make musically necessary gestures, appropriate to the section | Feature counting; static settings; unverified parameter meaning; cross-track interference |
| Project feel/space theme | A recognizable musical identity evokes distance, orbit, transmission, weightlessness or related space ideas through contrast and gesture | Titles and reverb alone; interchangeable synth soundtrack |
| Novelty | Distinctive local identity and non-obvious development relative to the other three demos and their own repeats | Same generic template in a new key; global originality claims unsupported by evidence |

Anchors: 1–2 fundamentally fails its musical role; 3–4 substantial mismatch;
5 functional sketch with significant undeveloped material; 6 promising but
generic or inconsistent; 7 convincing foundations with substantial refinements;
8 strong yet a concrete material weakness remains; 9 excellent within stated
review scope; 10 exceptional and unusually integrated. No automatic penalty for
simplicity, conventional harmony, grid alignment or repeated hooks. The question
is whether that choice works for this particular section and song.

Owner clarification, 2026-10-10: inspect the project in the simulator or
programmatically inspect the actual project files across every category;
waveforms alone are insufficient. This review uses decoded project events,
generator logic, routing, modulation/locks/effect settings, supported voice
behavior and parent runtime acceptance as its primary evidence.

## Evidence procedure

Record exact asset SHA, authoritative file hashes, production proposal version,
render identity (or pending), decoded pitches/durations/event roles, feature
semantics and source locations. Trace the full song chain with one-based bar
ranges. Repeated occurrences inherit the scene score only when their musical
role and transition context remain equally convincing; otherwise identify the
occurrence and cap its category score explicitly. State transitions and pacing
separately. Every material shortfall gets a concrete edit target and musical
reason, not a request to add features indiscriminately.

For later rounds retain all earlier reports. Mark each request implemented,
partly implemented, rejected with reason, or unresolved; rescore changed and
unchanged scenes against the same rubric. Stop early only for an honest full
matrix pass, or conclude with remaining misses at round five.

## Approved guidance and tools

[verified] Read the local approved production-guidance, mc-arrangement-arch,
mc-rhythm-groove and mc-style-edm skills and their SOURCES.md on 2026-10-10.
They supply advisory prompts about phrase development, entry/exit, subtractive
arrangement, backbeat relationships and build/drop contrast. Their corpus claims
and prescriptive heuristics are not treated as universal musical laws. No
third-party song, sample, score or quoted book material is copied into assets.

[verified] Rarefaction status selects
`/Users/likwid/Developer/mvave-fm1-firmware`, with C, TypeScript and Python
profiles but fallback build/import configuration. Serena initial instructions
and configuration also select that primary checkout, with cpp active. Neither
selects the frozen writer worktree. Concurrent agents are active, so this critic
does not retarget or restart shared servers; exact frozen-source inspection is
the authoritative fallback for new demo assets. No semantic-index completeness
or device playback claim follows from this setup.

[verified] A bounded primary-checkout query of `sq_scene_launch` found the
same definition through both tools. Rarefaction found its two direct callees
but missed the known caller at `engines/seq/seq_cmd.c:639` and represented
`fm1_seq_t *` as `int *` under fallback flags. Serena located the correct
definition. These are navigation successes with demonstrated reference/type
coverage limits, not validation of the writer worktree.

## Round ledger

| Round | Frozen asset SHA | Report | Disposition |
| --- | --- | --- | --- |
| 1 | Pending writer correction checkpoint | Pending | No scores assigned |
| 2–5 | Not started | — | — |

Critic branch: `chore/2026-10-10@demo-music-critic`.
Writer branch: `feature/2026-10-10@demo-songs`.
Parent integration owns rendering, runtime acceptance and final packaging.

## Round 1 checkpoint

[verified] Reviewed frozen `9a2d099d77f5dc5903453079d08e059014e480cd`: all 32 scenes, 57 ordered chain occurrences, event pitch/onset/gate/velocity, routes, locks, sound and effect parameters, modulation rack and proposal. Reports: `2026-10-10-demo-song-critic-round-1.{md,json}`. Every scene has six integer scores; none passes. [inferred] Highest-priority revisions are scene development, intentional build/bridge/ending transitions, phrase articulation, voice-leading and genre-specific modulation identity. Gate lengths are intentionally raw ticks; bass-octave and chord-quality fixes are accepted before Round 1. No listening claim; render receipts pending.
