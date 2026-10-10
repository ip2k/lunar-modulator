# Four complete factory demo songs — owner brief

Owner, 2026-10-09: **after the editor, panel, effects/module expansion and
firmware work above lands**, generate and preload four musically compelling
sets, one each for chillwave, future bass, vapor twitch and electropop. Each
must contain at least four distinct scenes chained into a complete song,
using genre-appropriate sounds, tempo, beats and structure, and demonstrating
many Lunar features. This is authorized implementation deferred until those
streams land, not a request for four short unconnected patterns.

## Proposed composition direction

These are original creative starting points, not a finalized genre survey or
rendered compositions. Adjust by listening and the eventual effect shortlist.

| Set working title | Tempo / feel | Harmony and sound direction | Arrangement emphasis |
| --- | --- | --- | --- |
| Afterglow Relay — chillwave | 92 BPM, gently swung sixteenths | A minor; Am9–Fmaj7–Cmaj9–G6, warm drifting chords, muted bass, wistful melodic motif, restrained soft drums | Evolving texture and voicing, a contrasting bridge, gradual release |
| Event Horizon — future bass | 144 BPM, half-time backbeat | F minor; Fm9–Dbmaj7–Ab–Eb, wide rhythmic chord swells, sub bass, syncopated lead fragments, sharp drum accents | A clear tension/build/drop arc, drop variation, stripped breakdown |
| Packet Bloom — vapor twitch | 112 BPM, broken syncopation | D minor with brief chromatic passing tones; glassy stabs, playful plucked fragments, elastic bass, glitching drums | Call/response, offbeat rests, small fills and chopped motifs with a stable hook |
| Neon Transit — electropop | 120 BPM, straight dance pulse | E minor; Em–C–G–D, bright hook, bass ostinato, tight drums, contrasting chord voicings | Recognizable verse/pre-chorus/chorus, contrasting bridge and final chorus lift |

Target approximately 3–4 minutes per set; use eight distinct scene slots
where feasible: intro, verse/A, build/pre-chorus, chorus/drop, breakdown/bridge,
verse/B, final chorus/drop, outro. Reuse scenes with deliberate repeat counts
and fills to create a full arrangement; do not count repeated copies as four
distinct scenes. Final durations and scene lengths follow the musical result.
No borrowed melodies, commercial recordings or unlicensed assets.

## Implementation path after prerequisites land

1. Re-check the actual integrated parameter/module registry and public build
   profile. Pick contrasting palettes that fit the real four-sound and memory
   constraints; do not assume future effects already exist.
2. Build original sounds and clips as deterministic generated assets, with
   seeds and a reproducible authoring script. Use a drum kit sound shared by
   separate drum tracks, leaving sounds for bass, harmony and lead/texture.
   Eight tracks need not mean eight independently configured sound engines.
3. Use native session scenes/song entries. See `engines/seq.md` and
   `notes/2026-10-06-song-and-scenes.md`; scene changes launch clips, and any
   sound/effect changes must use supported persistent state/locks. Do not
   invent scene-specific engine snapshots or silently conflict parameters on
   tracks sharing a sound.
4. Include intentional parameter locks, envelopes/delay/curves, modulation,
   variation/probability/conditions where musically useful, mute/space and
   coherent scene transitions. Compose a strong hook first; features serve it.
5. Package complete `.lunar` projects with chained scenes, descriptive metadata,
   and brief performance notes: what to listen for, useful live controls, and
   safe variations. Preload into the existing examples/library with one clear
   action per song; never overwrite a user's saved project on first visit.
6. Keep authoritative and browser example bytes identical, as existing
   `tests/test_sim_files.py` requires. Label GPL-only dependencies and use the
   eventual distribution profile correctly; author permissive alternatives if
   the public firmware profile needs them.

## Acceptance evidence

- Exactly four complete, loadable demo sets; each >=4 distinct named scenes,
  a valid song chain and a definite ending or explicitly documented restart.
- Verify notes, routes, scene transitions and parameter locks across the full
  arrangement; no stuck notes, truncated load or unintentional sustained tail.
- Render entire songs through the integrated native and simulator paths;
  verify memory admission, finite audio, peaks/clipping and transport duration.
- Listen to complete renders and refine composition, mix, transitions and
  melodic development. Passing numerical checks does not prove musical quality.
- Exercise play/load/stop, save/reload and scene takeover from the browser
  library. Capture reproducible evidence and distinguish simulator from device
  playback. Device validation depends on actual firmware readiness.

Status: requirement and authored direction recorded; no demo composition,
preloaded asset, completed listening review or device performance claimed.

## Voltage workflow lessons for the drops — 2026-10-09

Owner requested inspiration from [Oversampled Voltage's official feature
guide](https://oversampled.us/products/voltage). The page was read here
[verified]; its audio examples and video tutorials were not auditioned.
Voltage separates sound, pattern and effect rerolls; locks protect selected
material. It offers per-hit effect values, bounded random offsets, exclusions
by sound type, and drawn or recorded effect automation [reported: official
guide, Main View, Pattern Sequencer, Edit Effects, FX Sequencer and
Randomization Matrix]. These are workflow observations, not evidence that
random generation alone makes a compelling drop.

The following are our original composition proposals [inferred application],
not instructions or compositions supplied by Oversampled:

- Establish a two-bar drum/hook identity first. Preserve the kick and primary
  backbeat; vary quieter hats, ghost hits and end-of-phrase accents within
  narrow velocity, pitch and decay ranges. Author the variation deterministically
  and use supported conditions/locks; a good critical downbeat must not depend
  on an unlucky probability outcome.
- Build tension by increasing rhythm density and opening timbre over a phrase,
  then remove drums and bass for the final beat or half-beat. Shorten lingering
  effect tails enough that the first drop kick/sub has room. Compare the gap by
  ear: longer or louder is not automatically better.
- Make the first drop state a clear hook with space around it. Alternate a
  recognizable two-bar call with a complementary answer. Reserve the largest
  fill or effect gesture for the fourth/eighth bar, rather than every bar.
- Develop the second drop by changing one or two dimensions: bass rhythm,
  chord voicing, response melody or percussion texture. Retain enough of the
  first hook to make the return recognizable.

| Song | Concrete drop / chorus plan |
| --- | --- |
| Event Horizon, future bass | Half-time backbeat; final half-beat gap before kick/sub and a wide chord hook. Alternate sustained and shorter chord swells, with a sparse lead answer. Plan rhythmic chord-level shaping as authored envelopes/locks; do not claim an automatic sidechain compressor exists. Second drop adds a higher response and a changed bass rhythm. |
| Packet Bloom, vapor twitch | Keep a stable backbeat while short plucks and glassy stabs trade offbeat answers. Use deliberate rests and a single phrase-ending pitch/decay gesture; add one controlled percussion variant on later passes. Second drop flips the call/response register. |
| Neon Transit, electropop | A short pre-chorus drum withdrawal leads into a clear four-on-the-floor chorus and repeatable lead hook. Use tighter drum tails and restrained ambience at entry; open the texture over the chorus. Final chorus changes voicing and adds an answering motif. |
| Afterglow Relay, chillwave | Use a gentle release into the fuller refrain, preserving the soft groove and melodic identity. Warm chord voicings, bass entry and subtle hat variation supply the lift; avoid forcing an aggressive EDM drop into this arrangement. |

Implementation bounds: work within Lunar's four sounds/eight tracks and actual
effect-slot/memory admission limits. Several drum tracks can share a kit, so
locks on shared sound parameters must be scheduled without conflicts. Scene
columns launch clips, not arbitrary new engine snapshots. Voltage's larger
effect chains, sample-library machinery and reroll UI are not prerequisites
for these songs. Use original synthesis and patterns; this research introduces
no proprietary sample, preset, melody or code dependency.

Acceptance addition: audition each build-to-drop transition in the full song,
check kick/sub headroom and tails, and compare the first and second drops for
recognizable identity plus development. These plans remain unrendered until
the prerequisite streams are integrated; they are not completed demos.
