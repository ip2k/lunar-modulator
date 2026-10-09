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
