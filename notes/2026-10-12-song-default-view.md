# Song as the initial workspace for sequence projects

Owner request, 2026-10-12: opening Workbench or Editor after loading a song/project with sequence content should initially show Song / MIDI. Explicit choices remain authoritative. This stream is bounded to view selection; no hardware operations or listening acceptance.

## Contract and implementation

[verified] The Editor reads the native project's canonical `set` through its existing snapshot path. An arrangement entry or a defined clip chooses Song / MIDI (`sequencer`); an empty native set chooses Flow and effects. Defined empty clips count as authored sequence content. Sounds alone, default track settings and null clip slots do not count.

[verified] `makeInitialView` settles this default once for each `files.pid`. A successful project load calls `projectLoaded()` after assigning that identity (parent integration commit `de5e020bb15fe58098da1c4f27a5044b94932b85`). Another project prepares its own default without switching the page out of Panel. Same-project sequencer edits, restores and snapshots retain the selected workspace. Snapshot replies from another project identity cannot choose a view or replace the mirror.

[verified] Sidebar selections, CPU/Memory, command-palette view commands and explicit `view=sequencer` or `sel` links mark a choice before a delayed initial snapshot. A plain `view=edit` link remains an Editor-layout request, allowing sequence content to choose Song. Initial panel view telemetry updates chips without overriding that content decision; subsequent panel-follow navigation remains available.

## Verification

[verified] Pure Node checks pass: `initial-view.test.mjs`, `panel-follow.test.mjs`, `sequence-model.test.mjs` (11 tests). The first covers empty/native sequence content, stale identities, same-project settlement and explicit selection during the initial read.

[verified] `initial-view-ui.mjs` runs a real browser and AudioWorklet, with a PulseAudio null sink on Hera. Chromium, Firefox and WebKit checks cover: sequence loaded in Panel before first Workbench entry; explicit sound selection across same-project refresh and layout changes; sound-only Flow; subsequent sequence loaded while Panel remains active; selection link and palette commands racing delayed canonical snapshots; Editor started before a linked native song loads. Final URL-selection coverage is recorded in the companion reports.

Reports are in `notes/2026-10-12-song-default-view/`; raw screenshots remain in ignored `scratch/song-default-view/` and the isolated remote job `/home/claude/mvave-fm1/song-default-20261012/`. The initial Song screenshot was visually inspected: the requested workspace is active and labels in the resulting view are legible. Existing Panel-to-Editor pointer interception in the parent baseline was avoided by activating the layout radio with the keyboard; the parent toolbar stream owns that layout issue.

## Tool coverage and integration handoff

[verified] Rarefaction status/orient and Serena initial instructions/config/find_symbol were attempted. Both select the primary `/Users/likwid/Developer/mvave-fm1-firmware`, rather than this isolated checkout. Rarefaction's JavaScript query resolved to `any` without useful references; Serena rejected the ignored JavaScript file under its current C++ project. The shared active project was left intact; source investigation and edits use actual worktree files. These results are navigation limitations, not semantic verification.

Branch: `fix/2026-10-12@song-default-view`, worktree `/Users/likwid/.codex/worktrees/song-default-view/mvave-fm1-firmware`. The first branch commit `04ecd8b4f66fd6f6167500b4d575904d273affea` cherry-picks the parent's already-integrated load hook and must not be replayed into the parent. Cherry-pick the following implementation commit only. Root owns CI wiring: add `initial-view.test.mjs` to the Node unit list and `initial-view-ui` to the browser test loop. Root continues combined-tree review, CI, integration and Pages publication; this subtask does not claim those gates.
