# Playback visuals and native lock lanes

Scope: isolated playback-lanes stream for the editor workspace polish goal.
Branch: `feature/2026-10-11@playback-lanes`, based on `5573b7ff`.
Parent integrates this stream with song transport, shortcuts and editor shell.

## Implementation and native source checks

[verified: source inspection] Native `seq_engine.c` advances each track's
`pos_tick` with its speed ratio, starts at `loopStart * 24`, and wraps at
`(loopStart + length) * 24`. The editor reads each `tracks[].posTick` directly;
it does not reapply the speed ratio or advance a synthetic clock. Scenes have
translucent clip-local sweeps; Arrangement has a note-preview playhead only on
the current grouped song entry (including later repeated presses).

[verified: source inspection] `seq_clip.c` effective-at scans cyclically inside
the loop, taking the nearest lock or resetting to lane base at a note without
a lock. `seq_engine.c` runtime automation takes locks before note resets.
The visual lane plot depicts those cyclic loop values; initial playback can
start at base before the first lock. All assigned native lanes render as rows,
with step blocks, explicit numeric values, dashed note resets and local-tick
playheads. Pointer height sets a 0–127 lock; arrows adjust by 1 (Shift: 8), and
Delete/Backspace clears. Existing numeric lane editors, labels, assignments,
constraints, native codec and canonical refusal handling remain available.
No native fields or host-only saved capabilities were added. Existing Clip
playhead and first-entry note framing remain intact.

## Checks and artifacts

[verified: local checks] `node --test` on sequence-playback, sequence-model and
sequencer-host: 13 passing tests. `node --check` on both edited editor modules;
`git diff --check`: pass. Existing `sequencer-ui.mjs` mock-host desktop/mobile
and real Verse note-navigation tests: pass. New `sequencer-playback-ui.mjs`:
independent phase/wrap/stopped and wrong-scene hiding, grouped repeated-entry
previews, all eight lanes, native note reset, pointer/key/delete edits, focus,
canonical refusal, landscape layout, later-page/fractional playhead: pass.
Both new tests added to existing CI lists; remote CI is not claimed here.

Ignored local results and screenshots:
`scratch/sequencer-playback-ui/results.json`, `scenes-independent.png`,
`arrangement-playing-entry.png`, `automation-desktop.png`,
`automation-landscape.png`, `automation-eight-lanes.png`. All rendered images
were inspected for label/value collisions. Local browser test wrapper uses the
already installed Playwright runtime and Chromium; no dependency added.

Rarefaction status and Serena instructions/config were checked: both select
shared primary checkout, not this managed worktree; Serena config is cpp-only.
Neither shared session was retargeted. Used bounded file inspection instead;
no semantic worktree/index coverage is claimed. No native build, real-Wasm
integration, live audio, listening or physical-device acceptance was attempted.

## Handoff and remaining gate

Parent must integrate the pushed commit, resolve the small sequencer.js update
helper / navigation overlap with song_transport, add root layout-probe test,
run required full integration/CI and live-browser checks, then review/merge.
Playback helper is invoked at the end of update(); transport helper belongs at
the start. Shortcuts must respect defaultPrevented/focused controls so native
lane Delete and Arrow actions do not also edit notes.

No blocker in this stream. Remote SHA verification is recorded in parent exit
report and ignored `scratch/playback-lanes-handoff.md` after push.
