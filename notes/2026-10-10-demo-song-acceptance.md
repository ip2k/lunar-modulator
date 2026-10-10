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
listening review and final integration CI. These JavaScript harness files are outside the simulator C source fingerprint.
Final integration still requires the actual build and full CI; matching source
hashes alone do not establish that the final tree passes.

Semantic tools: [verified] Rarefaction's root is the original checkout,
not this worktree; its bounded JavaScript orient query failed in the
TypeScript backend. Serena is active in another worktree and was not
retargeted because selection is shared. This work used direct source/API
inspection and actual-Wasm smoke testing; it does not claim successful
semantic navigation in this worktree.

The subsequent harness revision also checks distinct song titles, the
actual number of unique chained scenes and persisted stop-at-end behavior.
[verified] Its revised synthetic four-scene cases pass at four seconds,
peak 0.5380 / RMS 0.0760. Optional `--native HARNESS --work DIR` runs the
native simulator, retains WAV/PPM/JSON receipts and checks load acceptance,
audible output, zero dropped events and final stopped transport. That
native leg has not yet been executed for this checkpoint.

`sim/web/test/demo-files.mjs` is the separate Playwright acceptance path:
exact browser mirrors and preloaded registry entries, URL load/play,
stop, Save download, and Open into a clean context followed by state
comparison. [verified] Syntax checks pass; browser execution awaits the
authored files and container integration. These scripts do not claim a
full CI pass or musical quality approval.

The optional `--audio-dir DIR` records the same inspected Wasm samples as
stereo IEEE-float WAV files, without normalization or clipping. Existing
files are refused so a new render cannot overwrite a prior review round.
[verified] All four synthetic four-second fixtures passed with capture:
each WAV contains 2,118,188 bytes including its header, rate 44,118 Hz,
finite samples throughout and measured peak 0.537982583. Header/data lengths
match. Full authored-song audio remains pending.

## First authored round, 2026-10-10

[verified] Assets at `27939c784be6d8bacb19bc8b5eaba6bb34583ea2` (a
serialization-only repair of critic snapshot `9a2d099`) rendered in full
against the PR #142 Wasm in an isolated aeon container, limited to 2 CPUs
and 2 GiB. All four save/load/save checks passed; the arrangements stopped
within 0.1 seconds of their expected 188.57–208-second durations, with zero
dropped sequencer events, non-finite samples or host imports. Peaks were
0.7532–0.8684 and RMS 0.0694–0.0776. Exact samples were captured as float
stereo WAV without normalization. File/audio hashes and per-second RMS
are in `notes/data/2026-10-10-demo-song-round-1-wasm.json`.

This is runtime evidence, not musical approval. The critic scored all 32
scenes 3–6 using actual decoded project/source evidence; round 2 revisions
are underway. Native full-song and browser file acceptance remain pending.
The acceptance harness now rejects repaired or skipped project content and
records Wasm, manifest and project hashes directly in future receipts.
