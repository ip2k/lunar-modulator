# Demo song Round 5 runtime acceptance

Frozen asset snapshot: `3e6eaa5fea7a38822b60a2a742af4b932856b8cc`. The native/Wasm harness and browser harness came from integration checkout `2af61f7201ec6884299cf2a9b728260c12347809`; the browser startup implementation includes `5805ea9cc0a0d655f66c7d30b9d4584c8a615084`. Wasm SHA-256 is `4667498f919529ba0f1059f127ea02e60c2c2a76ee5bc16983cfeabbb96b76ec`; manifest SHA-256 is `1c1e003dbb4f25f61209a93600eeaa4659af689900d3c55103c933a475619730`. Native renderer SHA-256 is `a17a9a3255dc80a88a528f4ba24ecf85d14852fb310cb8fc831314285ce4dda2`.

All four projects completed the full native/Wasm render at 44,118 Hz on aeon, in the dedicated 2-CPU/2-GiB `docker-batch.slice` container. The Wasm harness verified load reports had no skips, repairs, or omitted content; saved state survived save/load/save; playback reached each project end and stopped; output remained finite with no dropped frames. Native renders also completed with zero sequencer drops/refusals and no sounding voices at end. Per-song duration, peak/RMS, simulated RAM percentage, renderer frame counts, and artifact hashes are in the JSON receipt. These are simulator/runtime and estimated-budget results, not physical-device capacity or safety claims.

Chromium `153.0.8010.12` on the pinned Playwright image loaded each preloaded example, started playback, stopped it, downloaded a project, compared normalized serialized state with the pre-save state, then opened it in a fresh browser context and compared state again. All four passed with no page errors. I visually checked the four saved screenshots; each shows the expected loaded title and Save confirmation. Screenshots, downloaded `.lunar` files, and both native and Wasm raw WAVs are retained under ignored `scratch/demo-song-review/round-5-3e6eaa5f/`; the receipt records their SHA-256 hashes.

## Musical-review boundary

The independent Round 5 source review is recorded at critic commit `0a2ccc17c40c3ef2a7b87da6f0449cbe980ef752`: 32 scenes and 54 occurrences reviewed; 0/32 scenes passed all six score categories, and 190/192 score cells were at most 8/10. The requested five revision rounds are complete; no sixth round was run. No human listening evaluation is claimed.

Round 4 was a source-only critique snapshot; it did not inherit the Round 3 runtime pass. The Round 3 runtime evidence applied to its own frozen assets only. This report is new runtime evidence specifically for the frozen Round 5 asset hash/commit above. The metrics establish loading, state persistence, render completion, and browser save/reopen behavior; they do not establish musical acceptance.

Full machine-readable receipt: [`notes/data/2026-10-10-demo-song-round-5-runtime.json`](data/2026-10-10-demo-song-round-5-runtime.json).
