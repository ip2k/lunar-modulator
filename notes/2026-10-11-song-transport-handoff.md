# Native Song transport handoff (2026-10-11)

Active branch `feature/2026-10-11@song-transport`, worktree `/Users/likwid/.codex/worktrees/song-transport/mvave-fm1-firmware`, baseline `e397a4eced2436a939eef8adeba4f1d4f9b524a6`. Parent integrates; do not merge independently.

Implemented native pause/resume/rewind/seekbar verbs, preserved legacy Movy IDs and play/stop behavior, elapsed running audio frames and versioned extended Wasm telemetry. UI renders native transport first and Song view tabs after tool content. Measured output meter subscribes in every Song view. File tools use parent-provided `ctx.fileToolsHost` (editor appbar). Shared keyboard APIs are `toggleTransport()` / `restartTransport()`.

Native core costs eight extra bytes: own baseline eight-track 31952 / no Capture 28880; with parent track names 32080 / no Capture 29008; combined ancillary estimate 36628/36864 (236 spare). Native snapshot grows for paused flag/frame counter; Wasm static telemetry grows five words. No saved browser transport state.

Checks so far: Node focused transport+host 14/14 pass; Hera native build passes. Song+Movy oracle native suite passed except two new fixture errors (missing velocity/empty clip), corrected for rerun. Native edit-check paused project load/settings coverage added and pending. Hera isolated stage `/home/claude/mvave-fm1/song-transport-20261011` with `.test-venv`.

Root and playback agent own final merged Wasm/browser rendering and visual acceptance; no device firmware or by-ear validation performed. Shared Rarefaction/Serena roots checked, not retargeted during concurrent work; file inspection fallback used in isolated worktree.

Remaining: rerun focused native plus memory/edit checks; save final evidence, commit/push and verify remote SHA; parent resolves names-related RAM assertion/doc overlaps and integrated UI/telemetry checks.
