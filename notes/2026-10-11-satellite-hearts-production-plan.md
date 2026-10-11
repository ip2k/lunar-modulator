# Satellite Hearts composition plan — 2026-10-11

## Owner direction

Create a new electropop showcase song named **Satellite Hearts**. The previous
Neon Transit and the other three first-round projects remain preserved as
legacy example sequences; they are not the four showcase demos. Do not rename,
delete, or quietly promote the legacy assets.

The owner supplied these references (titles verified earlier through YouTube
oEmbed metadata):

- Justice vs Simian — “We Are Your Friends”
- Justice — “Neverender” (with Tame Impala)
- Eurythmics — “Sweet Dreams”
- Robyn — “Dancing On My Own” (Rex The Dog Remix)

That metadata verifies identity only. It does not establish that the audio was
heard or that the future composition resembles a recording. Keep the melody,
chord progressions, patches and sound design original; use no samples.

## Collection-level acceptance constraints

The four eventual showcase songs must sound **vastly different** from one
another, not like four parameter variants of a common template. Compare and
separate tempo and feel, drum source and pattern, engine/preset/timbre, register
and articulation, hook rhythm, harmony, section topology, and transition
behavior. Each song still needs at least four distinct chained scenes and a
complete beginning-to-ending arc. Preserve song-specific phrase writing,
scene lengths and chain order rather than inheriting the same eight-scene form
by default.

When this plan was first written, `origin/main` did not contain the shared
`tools/demo_songs.py` generator, canonical demo assets, or manifest. This
branch now contains them through a normal merge of the Event Horizon candidate
(`22640a4`), but they remain absent from `origin/main`. The four configured
projects are legacy examples, not the replacement showcase set. Do not extend
the generator's four-song assumptions to Satellite Hearts: coordinate the
legacy/showcase split in the collection manifest and checks first.

## Initial direction, superseded by the implementation freeze

Satellite Hearts should read as rhythmic electropop: a short, unmistakable
instrumental hook with clear phrase endpoints; a steady dance pulse; a verse
that leaves room for the hook; and a contrasting middle section that introduces
a new function rather than only removing tracks. Its final palette, tempo,
groove and form remain unselected until the other three replacement-showcase
palettes are known. This avoids another shared-template collision. The design
must fit the real engine/voice and four-sound-slot budgets and be accepted by
the canonical native/Wasm state and full-chain harness before it is called
runtime-ready.

## Validation boundary

Source and structural checks can verify scene chains, event timing, state
round-trips, parameter admission, memory estimates and finite full-length
renders. They cannot establish musical resemblance or owner approval. Final
release wording must separate those checks from owner listening.

## Code-navigation setup

Serena was activated on this exact absolute worktree and its Python overview
matched the canonical state-schema test at `tests/test_state_schema.py`.
Rarefaction remains rooted at `/Users/likwid/Developer/mvave-fm1-firmware`;
it rejected this worktree as outside its configured workspace. Its bounded
orientation of the same state-schema test matched the local file hash, but it
does not index this Satellite branch. Recheck Rarefaction against the actual
worktree before relying on it for implementation navigation; the initial orientation happened before source changes; the later Packet
symbol/caller and diagnostics check is recorded below.

## Source milestone, 2026-10-11

The contrast matrix is now frozen as implementation targets. Satellite uses
Comet Classic drums, Drawbar Bass, Shapes Saw/Sqr and Drawbar Mellow; Sophie is
reserved for Packet. Its 124 BPM C-major form is six unique scenes of
4/12/8/16/8/12 bars (60 total). The borrowed F-minor window and written C
cadence provide harmonic contrast; the independent clipped melody avoids
simply transposing a contour over chord roots. Two organ instances have
separate registers/envelopes. No reference audio was heard.

`tools/showcase_songs.py` generates this asset independently of the legacy
four-demo generator. Originals are untouched. Source invariants check actual
registry parameter bounds/enums, clip endpoints, same-pitch overlap across
tracks sharing a pitched slot, and the metadata cap. These pass. Native/Wasm
admission, canonical runtime round-trip, full render and owner listening are
pending; this checkpoint is WIP, not musical acceptance. Single-song runtime
manifest: `sim/web/test/satellite-hearts.json`. Root owns generic harness and
catalog integration. Rarefaction still indexes the main checkout; Serena was
selected on this absolute worktree and its `build` symbol bounds matched the
actual generator source. No shared Rarefaction reconfiguration was attempted.

## Source critique response

Independent review of `442861a4` found that the 16-bar Hearts refrain repeated
its four-bar orchestration unchanged, and Window did not yet develop a new
melodic function. Hearts now withdraws the end of bar 8 and the chord/lead in
bar 12, returns with an upward answer at bars 10/14, and writes a final
statement into Return. Window has a distinct lower four-bar countermelody,
with its second phrase ending on B to resolve into Return's C harmony. Verse
phrase ends omit the last kick and introduce quiet rim pickups; refrain
phrase breaks remove clap/hat endpoints rather than using generic rolls.
The F-minor borrowing is an established verse color, not falsely described as
first revealed in Window. Source invariants still pass; listening remains
pending, and aeon runtime remains blocked by `Host is down`.
