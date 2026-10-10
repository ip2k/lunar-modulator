# Demo-song production skills — 2026-10-10

Owner requested loading [Music Production Guidance](https://mcpmarket.com/tools/skills/music-production-guidance) and researching further composition/production skills. This records the adoption for both Codex and Claude; it is preparation, not a claim that demo songs exist.

## Loaded sources [verified]

The listing links to [a5c-ai/babysitter production-guidance](https://github.com/a5c-ai/babysitter/tree/d97a2e46a84cbc3ca4589050a9bddbcbf792a785/library/specializations/domains/social-sciences-humanities/arts-culture/music-album-creation/skills/production-guidance), pinned at `d97a2e46a84cbc3ca4589050a9bddbcbf792a785`. Its SKILL.md was read in full. Use its instrumentation, arrangement, mix-character, effect and era-aesthetic specification/checklist. The upstream LICENSE.md is MIT.

From [jtydhr88/music-composition-skills](https://github.com/jtydhr88/music-composition-skills/tree/7adca0c321db602deb3c94d79b04037cf339e5d2), pinned at `7adca0c321db602deb3c94d79b04037cf339e5d2`, read and adopted these text-only modules:

- `mc-arrangement-arch`: energy arc, instrument entry/exit, subtraction, hook returns, second-section variation and deliberate endings.
- `mc-rhythm-groove`: distinguish tempo from subdivisions/halftime; rests, accents, syncopation and melodic response to the backbeat.
- `mc-style-edm`: build anticipation, reserve low end for the drop, introduce a new element at the drop, and fit section lengths to the listening context.

Local source copies and retained licenses/NOTICE are under `~/.agents/skills/lunar-music-guidance/`, with `SOURCES.md` giving hashes. The four `lunar-*` links in `~/.agents/skills/` expose their standard SKILL.md directories for future Codex sessions. Claude can read the same absolute files; no Claude plugin registration is claimed. Only these four modules were loaded fully; the much broader `mc-workflow` was surveyed, not adopted. Companion book excerpts and the generative-backend workflow are not installed.

The composition project's MIT license covers its original structure and checklists, but its NOTICE explicitly excludes third-party quotations/translations. Keep the source skills as local study material; do not vendor them or copied music into Lunar. Treat upstream corpus percentages and blanket anti-AI rules as unverified heuristics. Do not force irregular bar counts, microtiming or borrowed chords merely to satisfy a checklist.

## Other candidates considered

[SJY051/music-composition](https://github.com/SJY051/music-composition) supplies another modular harmony/melody/form/genre toolkit [reported by its README]; not loaded because it overlaps the selected modules. [sb-dev/music-production-skills](https://github.com/sb-dev/music-production-skills) and [sirruf/music-gen-skill](https://github.com/sirruf/music-gen-skill) center other generation/rendering pipelines [reported by their README/search descriptions]; not adopted for Lunar's own deterministic engine/sequencer renderer. DAW connectors and lyric tools can be reconsidered if the owner requests those workflows.

## Apply to the four original demo songs

Use a per-song production sheet before authoring assets: title/genre, tempo and beat feel, key/chords, memorable original motif, section bars and scene-chain mapping, sound/track roles, entries/exits, section energy, fills, parameter-lock/modulation moves, effects, ending and expected duration. Each song must meet the owner's four-scene minimum and form a complete composition. Repeat hooks with purposeful variations rather than repeating one unchanged loop.

For future bass, plan a halftime groove, brief thinning/bass withdrawal before the drop, then the hook's full chord/bass/drum return; increased density and contrast should create impact without simply increasing output gain. For vapor twitch, use syncopated call-and-response, short fills and timbral/lock variation while preserving a readable pulse. For chillwave, make space for slowly evolving harmony and restrained drums. For electropop, use a clear recurring instrumental hook and verse/chorus contrast. These are proposed directions [inferred], not claims of completed or auditioned music.

Translate musical plans into the current Lunar limits: four sound slots, eight tracks/scenes, scene clips rather than per-scene engine/effect snapshots, available locks/modulation and measured memory/event budgets. Verify these limits against the actual asset schema when authoring. Do not invent unsupported sidechain, arbitrary timing, sample or automation capabilities. Where the preferred technique is absent, compose an equivalent with note lengths, rests, envelopes, locks or arrangement changes and record the adaptation.

Render and audition through Lunar. Whole-song native/actual-Wasm render, reload/admission, finite audio, peaks, complete chain/stop/tail and browser playback remain the technical checks; ear review of groove, hook, balance, transitions and endings remains separate. External AI generation is not the production backend for these demo songs.
