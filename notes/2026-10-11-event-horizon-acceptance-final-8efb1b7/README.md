# Four-project runtime and browser acceptance — 2026-10-11

This is a bounded runtime/file-flow check for the exact source branch head
`8efb1b72978d25f960beb1d6988bb2237b315a90` (`feature/2026-10-11@event-horizon-rewrite`).
The run was performed on aeon in a fresh scratch directory:
`/home/claude/mvave-fm1/demo-event-final-8efb1b7-20261011`.

The native renderer was
`/home/claude/mvave-fm1/worklet-ready-final-c44a808/src/sim/web/build/native/fm1-sim-render`
with SHA-256 `a17a9a3255dc80a88a528f4ba24ecf85d14852fb310cb8fc831314285ce4dda2`.
The Wasm module was SHA-256
`4667498f919529ba0f1059f127ea02e60c2c2a76ee5bc16983cfeabbb96b76ec`.
The harness receipt is [demo-songs.json](demo-songs.json); its manifest SHA-256
is `1c1e003dbb4f25f61209a93600eeaa4659af689900d3c55103c933a475619730`.

All four native/Wasm arrangements passed: finite audible output, persisted
stop-at-end, expected duration, no dropped/refused sequencer events, canonical
load/save/load with zero repairs or skipped content, and RAM estimates below
100%. Native and Wasm reports each show their expected runtime; the Wasm load
percentages were 67/39/54/67 and native 73/40/61/73 for Afterglow Relay,
Event Horizon, Packet Bloom, and Neon Transit, respectively. The harness
confirmed the project round trip and produced retained raw WAVs and native
screen captures under the aeon scratch path above. These checks establish
runtime/state behavior, not sound quality or device fit.

Chromium 153.0.8010.12 passed the preloaded example listing, play, project
Save/download, and Open in a fresh browser context for all four files, with no
page exceptions. The browser receipt is [demo-files.json](demo-files.json).
The saved Event Horizon download SHA-256 is
`30abe6e6144712e3e2d022dc483d642de16a85bbab9ea7fc6ca304fb6f2e75b3`; its
screenshot SHA-256 is
`693411c5a39b890f9fee578b3210004da3ac8aabb342329a8d6f017d86adc6c0`.
All four screenshots and downloads remain in the remote scratch `browser/`
directory.

The original e608 run's single repair was initially attributed to the omitted
disabled Arp records; that attribution was not isolated. The intermediate
13fa0ce run serialized those records but still had one repair. Source inspection
found the actual independent mismatch: project `about` text is capped at 240
code points by the state JSON reader (`engines/state/state_json_read.c`), while
Event Horizon's description was 314 characters. This revision uses 233
characters and the generator now guards that limit. The current exact Wasm
load-save-load receipt reports `repaired=0`, `skipped=0`, and identical
successive saves. See the historical [e608 receipt](../2026-10-11-event-horizon-acceptance/README.md)
for the preserved first attempt.

These are the original example songs. The owner rejected them as showcase
demos; this receipt does not promote them, claim musical approval, or claim
hardware execution or listening acceptance. The independent source critique's
open Event Horizon arrangement concerns remain documented in
`notes/2026-10-11-event-horizon-listening-critic.md` (critic branch).
