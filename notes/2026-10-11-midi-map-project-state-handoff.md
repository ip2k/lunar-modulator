# Native MIDI map project metadata

Active task: native/schema/format preservation of browser.midiMap v1; no device MIDI dispatch. Branch feature/2026-10-11@midi-map-project-state from cd55bc60.

WIP: 64 bindings, target 192/source 128 UTF-8 bytes, unique string pool 4096 bytes including terminators. App map 4612 bytes outside sequencer allocation; app RAM accounting/preflight include it. New typed records and project-only critical BROW binary chunk, bounded parser/writer, atomic maps-only setter exported as fm1w_midi_map_set(len), success 1. Setter input is minimal project envelope {lunar:"1.0",kind:"project",browser:{midiMap:{version:1,bindings:[]}}}. It refuses other project records. Mappings participate in native project hash.

Pending: Hera native compilation/tests, Python independent codec parity, malformed/bounds/reload tests and final push receipt. JS/worklet/files owner song_shortcuts must await setter ACK before snapshots. Root owns combined Wasm/browser/integration. Shared Rarefaction/Serena selected root checkout; no retarget of concurrent sessions, isolated edits use file fallback.
