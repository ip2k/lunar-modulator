# Native Song transport handoff (2026-10-11)

Active branch `feature/2026-10-11@song-transport`, worktree `/Users/likwid/.codex/worktrees/song-transport/mvave-fm1-firmware`, baseline `e397a4eced2436a939eef8adeba4f1d4f9b524a6`. Parent integrates; do not merge independently.

Implemented native pause/resume/rewind/seekbar verbs, preserved legacy Movy IDs and play/stop behavior, elapsed running audio frames and versioned extended Wasm telemetry. UI renders native transport first and Song view tabs after tool content. Measured output meter subscribes in every Song view. File tools use parent-provided `ctx.fileToolsHost` (editor appbar). Shared keyboard APIs are `toggleTransport()` / `restartTransport()`.

Native core costs eight extra bytes: own baseline eight-track 31952 / no Capture 28880; with parent track names 32080 / no Capture 29008; combined ancillary estimate 36628/36864 (236 spare). Native snapshot grows for paused flag/frame counter; Wasm static telemetry grows five words. No saved browser transport state.

Checks: local Node focused transport+host 14/14 pass. Hera native build passes. Native transport/core/song/Movy oracle and simulator edit/multi/mod suite: 412 passed, one skipped (Node absent on Hera), two known Movy undo/render-compat xfails. Final transport/host bridge/simulator-web suite: 218 passed; the committed Wasm source-record check warns that rebuilding is required, as expected before parent's combined build. Native edit-check covers paused project load, phase/frame resume and persisted BPM/metronome/Song end settings; legacy project defaults and old 56-word telemetry compatibility pass. Hera isolated stage `/home/claude/mvave-fm1/song-transport-20261011` with `.test-venv`.

Final event reservation correction: running `seekbar` can emit Stop plus Continue, so `fm1_seq_cmd_max_events` is gates + 8 × tracks + 2 (130 with eight tracks), and the app's command+advance need is 202 of its existing 272 events. This adds no RAM. Standalone simulator budget is 36500/36864; parent track names make that 36628/36864. Parent must preserve those combined figures when resolving overlapping memory assertions in `tests/test_sim_web.py`.

Root and playback agent own final merged Wasm/browser rendering and visual acceptance; no device firmware or by-ear validation performed. Shared Rarefaction/Serena roots checked, not retargeted during concurrent work; file inspection fallback used in isolated worktree.

Backup checkpoint `ee28a4ce8293cc615cd8c81b9a720a5ddd475400` was pushed and remote SHA verified. Final validation/event-bound followup is the commit containing this note; resolve its SHA with `git rev-parse HEAD` after checkout. Parent has already integrated the checkpoint; cherry-pick the followup next, then build combined Wasm and verify landscape transport spacing, bottom tabs, appbar file menu and native telemetry. Root resolves names-related RAM assertion/doc overlaps. No standalone merge is authorized.
