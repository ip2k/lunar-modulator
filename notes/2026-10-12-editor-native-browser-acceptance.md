# Native Song editor browser receipts

**Snapshot:** 2026-10-12, saved-transport integration build.  
**Wasm SHA-256:** `34389dab09a86ed845ca2efc4b71bb3250e77ddf1e0529b4a011c94b6245b8c8`.

The real AudioWorklet, native Wasm state, browser history and offline render
passed in Chromium 153.0.8010.12, Firefox 155.0 and WebKit 26.6 under
Playwright. Each browser's native editor receipt has 14 checks and no reported
errors. The native workflow covers project and set roundtrips, MIDI import and
replacement, panel/editor state synchronization, mixer and meters, transport
and clip launch, responsive views, and six actual WAV downloads.

The separate synchronization receipt passed six checks in each browser. It
covers pointer and number-input continuity during refresh, snapshot invalidation,
undo/redo, native panel edits, hidden-view invalidation and stale-history refusal.
The panel path is exercised through native `seq-line` commands; physical
controls are outside the scope.

Each native browser receipt reports the same six downloadable WAVs: a stereo
master, four stereo sound stems, and one eight-channel sound-stem file. All are
24-bit PCM at 44,118 Hz and contain 35,392 frames. The export integration is
browser-automated against the stated Wasm module; it is not owner listening,
physical touch, device, GitHub CI, merge or deployed Pages acceptance.

The saved JSON receipts were inspected under
`scratch/runtime-gates-evidence/fixed-startup/` in the
`sequencer-runtime-gates` worktree. The checked-in summary here preserves the
browser versions, exact module hash, check counts, WAV formats and scope even
though those scratch artifacts are ignored by Git.
