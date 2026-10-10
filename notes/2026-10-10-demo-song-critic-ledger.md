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

## Round ledger

| Round | Frozen asset SHA | Report | Disposition |
| --- | --- | --- | --- |
| 1 | Pending writer correction checkpoint | Pending | No scores assigned |
| 2–5 | Not started | — | — |

Critic branch: `chore/2026-10-10@demo-music-critic`.
Writer branch: `feature/2026-10-10@demo-songs`.
Parent integration owns rendering, runtime acceptance and final packaging.
