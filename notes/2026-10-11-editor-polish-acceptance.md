# Advanced editor polish evidence — 2026-10-11

This note records the documentation checkpoint against root branch
`fix/2026-10-11@editor-workspace-polish`, pushed at
`6744d3bf5eaf27cca4025a4d776b3f09765be36` when reviewed. It also covers the
startup snapshot fix at `1567a460`. These are source and automated-test
receipts; they do not establish final integrated browser, live audio,
physical-device or by-ear acceptance.

The Advanced editor manual and Unreleased changelog now describe the current
shell and Song workspace: Files & export in the app bar before Undo/Redo,
Changes history popover, remembered sidebar visibility, engine credit and
licence popovers, Panel-only footer controls, quiet Arrangement section
insertion, horizontal timeline navigation, first-sounding-note framing,
native clip progress and automation playheads, native transport telemetry,
Song view tabs below the active work area, and context-aware Song shortcuts.
The user-facing detail is in `manual/chapters/15-the-advanced-editor.md`;
the keyboard map and shortcut test boundaries are in
`notes/2026-10-11-song-keyboard.md`.

The startup read race fix retries a project snapshot when native content
generation changes during the read, up to three reads. It refuses if the
simulator restarts and reports continued generation changes without writing
the stale document. The three regression cases cover one retry, bounded
retries, and restart refusal; the parent reports 11 sequencer-host tests pass.
The earlier combined Chromium/Firefox run at head `069333` failed during the
initial Song snapshot. The diagnosed generation-change race is the reason for
this fix. That failed run remains part of the history; no passing rerun of the
combined browser gate is claimed here.

The Song transport uses native tick position and elapsed audio-frame
telemetry, with Play/Pause/Stop, tempo, metronome, song-end choice, master
output meter and bar/clip/scene navigation. The standalone transport stream
reported a successful native build, 218 native/simulator-web checks, and 14
focused JavaScript tests; its broader run had 412 passes, one skipped Node
check and two known failures. Parent integration reported 17 combined
sequencer-host and transport tests passing. Shortcut checks reported six
focused tests and 36 existing editor-unit checks passing, plus a Chromium,
Firefox and WebKit harness against a canonical mock host. Those mock-host
results do not substitute for final integrated browser and rebuilt-Wasm
acceptance.

No FM-1 device run, physical control check, live-audio listening check or
owner by-ear acceptance is claimed here. Root owns final merged-Wasm and
browser acceptance. The next documentation dependency is the pending MIDI
learn implementation; once it lands, review its mapping coverage and then
update this note with its actual tests and limits.

Documentation validation on this checkpoint: `tools/manual/build.py --strict
--only-manual` completed with zero errors. It printed four warnings for
sequencer verbs without manual entries (`pause`, `resume`, `rewind` and
`seekbar`). `git diff --check` also passed. No product or acceptance tests were
added or inferred from this documentation build.
