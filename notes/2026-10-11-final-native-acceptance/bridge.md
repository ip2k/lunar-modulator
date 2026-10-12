# Fresh sequencer generation bridge acceptance

[verified] Exact module `2a2ad121431f6e7fac5aa186d00eb0b75848187441ffe0d4ec4222451ed65cc3` passed the fresh offline export, metadata and meter checks. Current MIDI tests passed **30/30** and host tests **8/8**. The generation bridge browser regression passed **4/4 in each of Chromium, Firefox and WebKit**, with zero page errors. Exact hashes, summaries and browser check names are in [bridge-results.json](bridge-results.json).

[verified] The offline export run exercised real FM6, inserts, MIDI arpeggiation, modulation and master processing; a deterministic 37,598-frame song; silent unused sound stems; track routing; automation isolation; sample-exact 8-channel interleaving against four stereo stems; cancellation, stream backpressure and oversized export refusal. The current source and test files copied into Hera match the managed checkout hashes.

[verified] Module metadata `fbd3d320` is byte-identical to static `meta.json` (SHA-256 `73fdc3e2189e5bbe16c357f7e25be8c5b57062a864cf9ed4db43a6059f32a948`). Querying metadata preserves audio. The 2,048-frame meter check validates actual peak/RMS, post-fader/final gain, silent sounds and empty-slot identity; enabled versus disabled telemetry produces bit-identical audio.

[verified] Fresh g build records show **108 parity cases passed, zero failed**, with all 108 identical to JS and musl (105 identical to glibc; exact-scenario maximum one LSB). The recorded 30-second incremental edit storm has zero late quanta, and the native edit check has zero failures. These build records were inspected, not regenerated during this bounded follow-on.

[verified] Hera stage: `/home/claude/mvave-fm1/final-native-acceptance-bridge-2a2ad`, Node 22 image digest and 2 CPU / 2 GiB resource limits recorded in JSON. Raw new logs are under `scratch/final-native-acceptance/bridge-stage/`. Browser sync receipts are under `scratch/final-native-acceptance/sync-browser/`; the durable review and resolution are in [../2026-10-11-daw-sync-review.md](../2026-10-11-daw-sync-review.md). No source edits, rebuilds, device writes or commits were made for this follow-on.

[verified] Branch `feature/2026-10-11@midi-sequencer-workspace`, tested checkout HEAD and verified remote branch SHA `6958d6415dfe99b4c2edeb54350085e4dbf515a7`. Provenance JSON snapshot SHA `8a209d7f3fe1340a94bf7435aed7e8454c655a3abcb332c348efed70268894fe` was copied after root refreshed source/image provenance without recompiling the module. Its aggregate source hashes and pinned image references are preserved in JSON.

The earlier f163 acceptance receipt and README remain untouched. Previous four-demo RAM budget measurements belong to that separate snapshot; this getter-only bridge change adds no instance state. Runtime checks do not establish owner listening or physical FM-1 acceptance. Root must checkpoint these new notes and finish exact-head CI and merge.
