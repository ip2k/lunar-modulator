# Whole-song acceptance work

Branch: `chore/2026-10-10@demo-song-acceptance`, based on PR #142's
`ef39b23869a9d06b19ad4478554792508d186d29`. Work in progress; this is not
a completed-song or passing integration receipt.

The project filename check now accepts named projects instead of assuming
that every project is `first-orbit.lunar`. Schema, canonical layout,
parameter resolution and file-kind checks remain in place.

`sim/web/test/demo-songs.mjs` runs complete arrangements against the actual
browser Wasm module. It checks state save/load/save, RAM admission, tempo,
finite samples, nonzero audio, automatic stopping at the planned duration,
zero dropped sequencer events and zero host imports. It records peak, RMS
and second-by-second energy for subsequent mix/listening review.

[verified] JavaScript syntax and Python compilation checks pass. A bounded
four-case synthetic smoke test, derived from First orbit with a four-bar
stop-at-end chain at 240 BPM, passed against the unchanged PR #142 Wasm.
Each stopped at four seconds and produced peak 0.5380 / RMS 0.0849. These
synthetic cases only evaluate the harness, not the demo songs.

Pending: authored four-song manifest/assets, full-length renders on aeon,
native transport/event checks, browser example selection/save/reload,
listening review and final integration CI. Adding the test changes the
simulator source fingerprint; regenerate the actual Wasm/build record
before integration. Do not claim the existing build record covers this head.

Semantic tools: [verified] Rarefaction's root is the original checkout,
not this worktree; its bounded JavaScript orient query failed in the
TypeScript backend. Serena is active in another worktree and was not
retargeted because selection is shared. This work used direct source/API
inspection and actual-Wasm smoke testing; it does not claim successful
semantic navigation in this worktree.
