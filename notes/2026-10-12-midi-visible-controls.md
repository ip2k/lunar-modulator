# MIDI learn visibility and closed menus

The final MIDI transport pass uses the native Wasm sequencer and AudioWorklet;
only the Web MIDI input is mocked as OXI E16 input `431288530` [verified].
CC 29 controls Play/Pause/Resume and CC 30 stops and rewinds. Rising edges,
same-turn redraws, Workbench/Mixer transitions, disabled fieldsets, project
round trips and safe legacy Play resolution are covered. Ambiguous old
ordinal Pause/Stop assignments remain saved and inert until remapped.

Learn highlights intersect the viewport and ancestor scroll/clip boundaries.
Closed disclosure descendants are unavailable, except the disclosure's own
summary. The Files/export menu explicitly hides while closed: its grid CSS
previously left ghost highlight geometry. The native browser regression also
forces that menu's grid display to verify MIDI availability remains false
even when a closed disclosure exposes layout rectangles [verified].

Chromium 153.0.8010.12, Firefox 155.0 and WebKit 26.6 each passed nine native
transport checks, MIDI learn, native mapping project persistence, nine
initial-view cases and the shortcuts guide at four viewport sizes [verified].
All three reported zero page errors. Screenshots were inspected for teal
badges on controls and containment within the Scenes grid.

Receipts: `scratch/midi-closed-menus/<browser>/`; isolated Hera stage
`/home/claude/mvave-fm1/editor-midi-closed-20261012`. This run used the
`34389dab…` Wasm module and saved sources based on `dbf7af99`, before the
subsequent app-bar action reorder. Final combined CI and the rebuilt module
remain separate gates. No physical controller, device firmware, native
Safari or by-ear acceptance is claimed by these automated checks.
