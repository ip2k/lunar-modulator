# Browser MIDI learn and project mappings

The piano icon opens a translucent learn overlay over the simulator and
advanced editor. Choose an actionable control, then send a controller note or
CC. The next matching message assigns it; learning consumes MIDI silently.
Assignments show a clear button beside the control when space permits and in
the Saved assignments list. Close learning to use the controller normally.
Connect MIDI uses the existing explicit browser permission request. Browsers
without Web MIDI can inspect and clear saved assignments.

## Dispatch and identities

The mapping core and actual Web MIDI handler share one dispatcher. Exact input
ID, MIDI channel, note/CC kind and number identify an address. An address and a
target each have at most one assignment; learning an occupied address moves it.
Note-on holds native panel keys/buttons until note-off (including velocity
zero). CC buttons trigger on crossing 64, and release below 64. Absolute CC
values scale numeric parameters, sliders and selects. Panel encoders use
changes between successive absolute CC values; the first message establishes
a baseline. A mapped note nudges an encoder once. This is not a configurable
relative-CC dialect decoder.

All 27 panel keys, 14 buttons, seven encoders, MASTER and POWER have explicit
semantic IDs and native handlers. Parameter sliders and typed numeric fields
share an explicit parameter identity and the editor's existing edit/history
path; cable amount has its own numeric adapter. Real buttons, selects, ranges,
numeric inputs, checkboxes, radios and details disclosures use their existing
handlers. This includes mixer faders, transport and native automation buttons.
Context attributes identify track, scene, step, lane, sound and inspector
controls across redraws. Stable test IDs also identify transport controls
whose caption changes. No text, disabled/read-only element or unadapted custom
slider becomes a cosmetic fake target. Canvas drawing and free text are not
controller targets. Browser permission/file-picker actions retain their
browser gesture requirements.

Mapped MIDI is consumed even when its target is hidden/missing or editing is
blocked by a text field or dialog. Unassigned messages follow the existing
note, bend, CC7 volume and CC123 panic behavior. Blur, disconnect, learning,
layout/keyboard-mode changes and power changes release held mapped actions.

## Project contract and save ordering

Browser preferences use `lunar.midi-map.v1`. Project metadata is top-level
`browser.midiMap`, with `version: 1` and `bindings` containing
`{target, source, channel, kind, number}`. Channel is zero-based; kind is
`note` or `cc`. Targets are nonempty printable ASCII (including spaces), at
most 192 bytes. Sources are nonempty UTF-8 input IDs of at most 128 bytes,
without NUL. The maximum is 64 bindings and 4096 bytes of unique target/source
strings including terminators. There is no wildcard input. Input IDs can
change between browsers/devices; reassign on a different controller identity.

The native codec integration preserves this metadata in canonical JSON and
binary project records. Older projects without mappings clear the assignment
table; partial sound/clip loads retain the project table. A successful project
load reads its canonical mapping table back into the browser. Browser defaults
are installed before startup autosave restoration; restored project maps win.

Learning/clearing queues the bounded native maps-only setter. It cannot reload
engines, sounds, session or transport. Exports, autosaves and project snapshots
wait for every queued acknowledgement. A refused or missing acknowledgement
remains a save error until a successful mapping update or project load. A
missing response times out after five seconds. On successful acknowledgement
the editor invalidates cached Song documents; canonical hashes also refuse
stale Song edits which would overwrite newer maps. Editor snapshots wait for
the queue so a project hash includes acknowledged metadata.

## Verification and outstanding gates

[verified] Seven pure dispatcher tests pass: consumption, collision/clear,
held release, CC edges/values, source/channel separation, reload/redraw and
typing guards, shared bounds/atomic refusal, and synchronous mode-change edges.

[verified] Mock Web MIDI tests run against the real app DOM on Hera with
bounded two-CPU/two-GiB containers. Chromium 153.0.8010.12, Firefox 155.0 and
WebKit 26.6 passed the queue/cache/refusal tests. Chromium also passed the
five-second missing-ACK timeout/save refusal test. Tests cover actual panel registrations, silent learning,
native-message traces, unassigned MIDI, disconnect/blur, ordinary control and
custom adapter callbacks, typing/disabled protections, clear, reload and
unavailable Web MIDI. Rendered overlay screenshots were inspected for spacing
and label collisions.

`sim/web/test/midi-map-project-ui.mjs` is the combined real-native gate. It
requires a rebuilt module exposing `fm1w_midi_map_set`. It checks maps-only
state changes, stale cached Song refusal, learn → native Song edit → save,
caption IDs containing spaces, old-project clearing, JSON/binary canonical
roundtrip, actual editor slider/native undo and binary autosave. This gate is
pending the parent integration's single combined Wasm build. No real controller
or FM-1 mapping acceptance is claimed.

Rarefaction and Serena selected the primary checkout shared by another active
agent, rather than this worktree. They were not retargeted. Source inspection
and bounded browser tests are the fallback; no semantic-index success is
claimed for this checkout.
