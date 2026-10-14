# Demo preload candidate inventory — 2026-10-14

This is a source inventory, not production catalogue admission. The standard
library tool `tools/native/demo_preload_catalogue.py` reads pinned Git blobs,
hashes the exact `.lunar` bytes, extracts raw project-engine identifiers, checks runtime
receipt hashes, and reports whether matching bytes are materialized in the
current checkout. It does not write the image catalogue or select a default.
Run it from the repository with `python3 tools/native/demo_preload_catalogue.py`.

## Decision boundary

The owner rejected the four Round-5 originals as showcases and directed that
they remain legacy example sequences (`notes/2026-10-11-showcase-diversity-matrix.md`).
The four later replacement compositions have runtime evidence, but their owner
musical acceptance remains pending (`notes/2026-10-11-four-showcase-integration.md`).
The corrected Packet Bloom and Satellite Hearts serialization hashes differ
from their older runtime receipt hashes (`notes/2026-10-11-showcase-ci-canonical-repair/README.md`).
The originals must not be represented as accepted showcases; the replacements
must not be represented as musically approved.

The structural timing estimate is `bars * 4 beats/bar * 60 / BPM`; it is
metadata-derived and is not a human duration assessment. The Round-5 runtime
receipt records full native/Wasm render and browser preload/play/stop/save/fresh
open checks for its exact project SHA, but also says no human listening and no
hardware execution. The replacement runtime receipt records native/Wasm
integration checks for the source hashes it names, but does not establish owner
listening or FM-1 behavior. Packet/Satellite's repaired current hashes do not
match the prior receipt and therefore receive no current exact-asset duration
receipt in the generated catalogue.

No minimum numerical duration defines “full-length” in the repository's
requirement. The originals are 76–116 bars and about 189–208 seconds by their
exact Round-5 receipts; the replacements are 40–68 bars and about 102–117
seconds by their pinned manifests. Do not silently call the shorter replacement
set full-length, or substitute the musically rejected originals into the default
image. The default choice remains release-gated on an owner-approved composition
and exact native acceptance.

## Exact candidates and dependency sets

The generated inventory contains eight unique IDs. Every entry records the
source branch, manifest commit/path, asset commit/path and SHA-256. Dependencies
come from the project itself: `sounds[].engine`, each sound's `inserts[].engine`
and `midi_fx[].engine`, project `master[].engine`, and `mod.rack[].kind`. These are identifiers, not a
claim that the current installable image links those modules.

| Candidate ID | BPM / bars / scenes | Runtime receipt | Sound engines | Audio FX | MIDI FX | Master FX |
| --- | --- | --- | --- | --- | --- | --- |
| `legacy-example-afterglow-relay` | 92 / 76 / 8 | exact, 198.260870 s | `drums`, `dx7`, `macro` | `drive`, `filter`, `warble` | `arp` | `hall`, `limit` |
| `legacy-example-event-horizon` | 144 / 116 / 8 | exact, 193.333333 s | `drums`, `dx7`, `macro` | `crush`, `echo`, `filter` | `arp` | `hall`, `limit` |
| `legacy-example-packet-bloom` | 112 / 88 / 8 | exact, 188.571429 s | `drums`, `dx7`, `macro` | `drive`, `filter`, `warble` | `arp` | `hall`, `limit` |
| `legacy-example-neon-transit` | 120 / 104 / 8 | exact, 208.000000 s | `drums`, `dx7`, `macro` | `drive`, `echo`, `filter` | `arp` | `hall`, `limit` |
| `replacement-showcase-candidate-afterglow-relay` | 104 / 44 / 4 | exact, 101.538462 s | `drums`, `dx7`, `macro` | `drive`, `echo`, `filter` | `arp` | `hall`, `limit` |
| `replacement-showcase-candidate-event-horizon` | 150 / 68 / 7 | exact, 108.800000 s | `acid-bass`, `drums`, `sixop`, `trio` | — | `arp` | `hall`, `limit` |
| `replacement-showcase-candidate-packet-bloom` | 82 / 40 / 5 | stale hash; no duration attached | `crater`, `macro-heavy`, `phase-bend`, `sw-sophie` | — | `arp` | `hall`, `limit` |
| `replacement-showcase-candidate-satellite-hearts` | 124 / 60 / 6 | stale hash; no duration attached | `comet`, `drawbar`, `shapes` | — | `arp` | `hall`, `limit` |

The modulation rack dependencies `chance`, `env`, and `lfo` are also present in
every candidate and remain separately listed in generated JSON.

The script output is the machine-readable source of the exact SHA values and
reports current materialization. At the time of this inventory, the four legacy
assets were present byte-for-byte in the installable checkout; the replacement
assets were available only through their pinned source revision. That makes the
four old projects selectable-source candidates, not release-admitted defaults.

## What remains before preload/default admission

Root is responsible for integrating the original example assets and production
image catalogue. The next work must bind every chosen entry to exact embedded
kind/bytes/SHA receipt identity, verify module dependencies and fresh linked
flash/RAM fit, then perform full-song playback and save/reload on native FM-1.
The musical owner must separately decide which composition can be the default.
The tool intentionally reports all candidates with `default_candidate: false`
and all four admission gates pending; it makes no UI, build-service, installer,
shipping, or hardware-acceptance claim.

## Verification and limits

`python3 tools/native/demo_preload_catalogue.py` emitted eight candidates from
the pinned source commits. In the replacement group, Afterglow Relay and Event
Horizon receipt hashes match; Packet Bloom and Satellite Hearts do not. The
catalogue also confirmed the four original project hashes against the frozen
Round-5 receipt. `python3 -m unittest tests/test_native_demo_preload_catalogue.py -v`
passes three focused checks for dependency extraction (including master slots),
receipt hash gating, stable IDs, and explicit incomplete/raw dependency status. These tests validate inventory behavior only. No production
catalogue, image, linked app, device, or hardware state changed in this task.

The Rarefaction Python status and Serena project context pointed at the primary
checkout `/Users/likwid/Developer/mvave-fm1-firmware`, not this installable
worktree. Neither semantic server was redirected because the project guidance
prohibits changing another active shared root. Bounded file/Git inspection and
standard-library tests were used instead.
