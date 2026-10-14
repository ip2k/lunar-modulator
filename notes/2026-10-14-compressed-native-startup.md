# Compressed native startup and one-engine reservation check

[verified in the bounded host harness; not target or hardware acceptance]

Source base: `4887528d1b2841431dceb95fbe9a835c36c790f9`.
Branch: `codex/2026-10-14-compressed-native-startup`.

The fixture compiles the production native project-start path and TLSF pool with
ASan/UBSan. It substitutes exact source-derived compressed Plaits and Braids
resource objects, runs their cold decoder, and compares every decoded table
byte against the raw upstream arrays. The allocator arena is explicitly
165,376 bytes; Shapes voice cap is varied only in this test build. Production
sources, project content, chooser admission, and release flags are unchanged.

The exact compressed resources are Plaits 50,688 to 32,513 bytes and Braids
33,024 to 24,159 bytes. The full Event Horizon Showcase starts at both
12- and 8-voice Shapes settings: 12 allocation calls, zero failures, six active
units, peak TLSF live bytes 90,912, ending live bytes 87,968. Eight sequencer
tracks require 31,944 of 32,768 bytes. Compressed decoded tables are byte-equal
to their source arrays. This verifies host cold-start and pool behavior only.

The full Satellite Hearts project does not fit. At 12 Shapes voices it fails
the 207,728-byte Shapes request (arena 165,376). At 8 voices, Shapes itself
fits, but a later 5,072-byte allocation fails with 154,352 live bytes; startup
cleans the pool back to zero and leaves zero active units. This arrangement
therefore remains unavailable under this profile; individual engine fit is
not project fit.

At the proposed 8-voice profile, one-engine cold-start candidates for all 13
catalogue engines pass without allocation failures. The fixture derives each
one-sound project from an existing candidate project's actual serialized
sound, clears unrelated master/modulation/MIDI effects, retains the valid
`movy1` set marker, and packs through the real state packer. All cases use the
same 165,376-byte arena and compressed tables. Observed peak live/request bytes:

| Engine | Largest request | Peak live bytes |
| --- | ---: | ---: |
| acid-bass | 31,944 | 31,944 |
| comet | 31,944 | 31,944 |
| crater | 31,944 | 31,944 |
| drawbar | 31,944 | 31,944 |
| drums | 31,944 | 31,944 |
| dx7 | 31,944 | 32,652 |
| macro | 32,736 | 33,632 |
| macro-heavy | 71,600 | 71,600 |
| phase-bend | 31,944 | 31,944 |
| shapes | 139,024 | 139,024 |
| sixop | 31,944 | 31,944 |
| sw-sophie | 79,344 | 79,344 |
| trio | 31,944 | 31,944 |

The harness shows host startup reservation only. It does not prove target
pi32v2 ABI/code generation, runtime audio stability, physical memory layout,
polyphonic quality at eight Shapes voices, complete-project compatibility, or
owner musical/release acceptance. The 8-voice profile is a measured candidate,
not a changed default or shipment decision. Satellite Hearts' complete project
still fails at this cap. Event Horizon's successful host start is not a claim
of musical acceptance.

Reproduce in the pinned Hera image with the bounded, network-disabled
`docker-batch.slice` command recorded in
`/home/claude/.local/share/codex-coordination/receipts/lunar-compressed-native-startup-matrix.log`.
The run passed the focused compressed startup matrix (including sanitizer
instrumentation); see that receipt for exact source/packed/resource hashes and
per-run allocation telemetry.
