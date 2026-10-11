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

The current `origin/main` checkout does not yet contain the shared
`tools/demo_songs.py` generator, canonical demo assets, or manifest. The Event
Horizon candidate has those files but also a large body of review/runtime
receipts and is not yet this branch's base. Do not duplicate the generator on
main or edit copied `.lunar` data until the shared source branch is integrated
or an explicit asset-base is selected.

## Provisional direction, not a locked palette

Satellite Hearts should read as rhythmic electropop: a short, unmistakable
instrumental hook with clear phrase endpoints; a steady dance pulse; a verse
that leaves room for the hook; and a contrasting middle section that introduces
a new function rather than only removing tracks. Its final palette, tempo,
groove and form remain unselected until the other three current showcase
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
worktree before relying on it for implementation navigation; no source-code
changes have been made in this stream yet.
