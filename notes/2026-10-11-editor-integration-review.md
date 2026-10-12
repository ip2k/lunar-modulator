# Editor integration review and CI coverage

Independent integration subtask, 2026-10-11. Review base is parent native
integration `9af24db8`, offline export correction `3b8e7db2` and resource display
`0175ffde`. The latter two were imported into review branch
`chore/2026-10-11@editor-integration-ci` as `85fcfc47` and `725ea218`.
Only the subsequent CI/harness/report commit needs integrating into the parent;
these imported commits duplicate work already present there.

## Outcome

No additional confirmed product defect found in the focused review [verified].
Two test assumptions prevented the real native MIDI project gate from executing:
Workbench hides panel connection buttons in the Simulator disclosure, which
closes after each activation; and the caption-ID fixture inherited semantic
layout attributes from the Workbench body. The harness now reopens the disclosure
for each control and puts its deliberately caption-derived button in an isolated
`main` scope. No product behavior was changed.

CI now runs the pure MIDI mapping checks and audio-budget helper, plus fit-grid,
mock MIDI UI, actual native MIDI project UI and editor resource UI in the existing
Chromium/Firefox/WebKit matrix. Existing CI already covers transport/shortcuts/
playback helpers and UI, native offline WAV regression checks, and the native
page's actual downloads. The main Python suite already collects
`tests/test_midi_map_state.py`; no duplicate Python step was added [verified].

## Review boundaries and reasoning

- Mapping metadata: `state_names.c`, the state codecs, `fm1_app_state.c`, host
  renderer and browser `files.js` stage and validate metadata before committing
  it. Targets require printable ASCII (including spaces); exact UTF-8 source IDs
  remain bounded. Duplicate targets/addresses and the shared string pool are
  checked before mutation. The live maps-only setter cannot alter engines,
  transport or the sequencer document. The browser waits for the native ACK,
  rejects stale Song snapshots after mapping edits, and refuses save/export
  while the latest mapping mutation has failed [verified by source and the
  three-browser native project gate].
- RAM: the fixed 4,612-byte map allocation is counted even for empty mappings in
  native preflight, actual app usage and host render preflight. This is a real
  budget change. Shipping examples still require the parent's exact-module
  budget/render checks; this subtask did not rerun those checks [verified source;
  remaining acceptance dependency].
- Offline duration: the song stop bound derives from the native 96-PPQN clock,
  one stop-observation interval and rounding to 64-frame processing blocks.
  Arrangement repeats, slow tempo and the tail enter the same capacity bound.
  Each export uses an isolated native instance and finite one-pass transport
  [verified source]. The parent reports all four full-arrangement regressions,
  20-BPM stop, FX/arp/modulation/stem checks passing with the combined module
  [reported by parent; not independently executed here].
- Download lifetime: each emitted file has a retained retry link, the aggregate
  retained-byte cap is checked before URL allocation, repeated rendering and
  dialog disposal revoke URLs, and cancellation terminates the worker. The
  per-file acknowledgement supplies backpressure; a sink exception ends the
  export. The existing native page harness checks six real downloads, WAV
  channel/PCM/frame headers, repeat rendering and cancellation [verified source;
  parent owns execution of its repaired harness].
- Paging/follow: the capacity calculation covers full scene/song/clip/automation
  ranges. Manual paging disables follow; native playback drives follow. Pointer,
  text edit and transaction guards defer redraw or resizing, with a pending
  resize applied after interaction. Grid capacity uses the stable workspace.
  Chromium fit-grid exercises all entries/steps, four viewport sizes, native
  position/wrap and interaction deferral [verified source and execution].
  Parent's fit agent is separately repairing transport teardown; that later
  change is outside this review snapshot.
- Notifications/transport: restore failures remain visible and successful
  autosave restore is quiet. Native transport commands and shortcut filters
  preserve input/IME/modifier handling. The resource display updates existing
  nodes, exposes coarse/unavailable timing honestly, permits overload, and orders
  Shared/Master before S1–S4 without changing native indices [verified source and
  helper/UI execution]. This measures browser DSP budget, not device CPU.

## Checks and receipts

All checks below were executed on Hera (`claude@192.168.1.48`) in bounded
2-CPU/3-GiB Playwright containers under `docker-batch.slice` [verified]. Real
worklet gates used an installed PulseAudio null sink and monitor. The native
project/resource tests used the parent's combined module:
`34389dab09a86ed845ca2efc4b71bb3250e77ddf1e0529b4a011c94b6245b8c8`.
The generated module is a local test dependency here, not part of this commit.

| Check | Result |
| --- | --- |
| Existing CI Node helper set plus audio-budget | 53 passed |
| `midi-map.mjs` | 7 passed |
| `midi-map-ui.mjs` | Chromium 153.0.8010.12, Firefox 155.0, WebKit 26.6 passed |
| `midi-map-project-ui.mjs`, real native module | Same three browsers passed, no page errors |
| `sequencer-fit-grid.mjs` | Chromium passed |
| `editor-resources.mjs`, real native module | Chromium passed at widths 1440/1024/844/667 |
| Resource screenshot, width 667 | Visually inspected; resource labels/values/bars do not overlap |
| `git diff --check` | Passed |

Small machine receipts are committed in
`notes/2026-10-11-editor-integration-review/`. Screenshots and complete local
browser artifacts are preserved under this worktree's ignored
`scratch/integration-review/`; the remote copy is
`/home/claude/mvave-fm1/editor-integration-ci-20261011/src/scratch/integration-review/`.
An initial stale-module resource run and missing-disclosure/caption failures
were superseded by the corrected runs above; they are not counted as passes.

Rarefaction status and Serena instructions/config were checked. Both selected
the primary checkout, rather than this review worktree. Because concurrent
agents use that shared selection, it was not retargeted. This review used direct
source inspection; no reliable worktree-specific semantic caller/index coverage
is claimed. Native source review cannot prove pi32v2 ABI or hardware behavior.

## Remaining integration gate

Parent must cherry-pick only this CI/harness/report commit, incorporate the
remaining fit/native harness repairs and generated module, and run final review
and required CI against the resulting exact head before merging. This subtask
does not establish GitHub CI, listening acceptance or hardware acceptance. No
hardware commands or writes were performed.
