# Render-stage profiling diagnostic

## Scope and implementation

[verified] Render profiling is opt-in through `--render-stage-profile`; the
builder accepts it only with explicit diagnostic telemetry and the bounded
`diagnostic` or `song-diagnostic` runtime. The default desktop, browser and
native builds compile profiling calls out through the shared MIT header
`sim/web/src/render_stage_profile.h`.

[verified] Telemetry schema 2 reports a millisecond timestamp and nine
`(ticks, maximum, calls)` triples: sequencer dispatch; sound slots 0–3; master
FX 0–1; postmix; display strip. `sound_k` aggregates the engine render and
all insert-effect calls belonging to slot k. Its `calls` count is timed render
segments plus insert invocations, not 64-frame audio blocks. Sequencer
dispatch is inclusive of callbacks into sound slots, so stage totals overlap
and must not be added. Postmix covers render work after engines/inserts and
master FX; display-strip timing is separate.

[verified] Profile window totals and maxima are unsigned 32-bit values. A
window total is the accumulated ticks since the prior successfully emitted
profile frame; it wraps modulo 2^32 if necessary. These are interval values,
not cumulative counters, so consumers should use each report's window value
directly. Profile samples reset only after the complete frame is enqueued.
When the USB-MIDI ring lacks room, the report is skipped and the sample window
is retained. The reporter snapshots in the main loop, not in the DMA audio
callback.

## Scheduling and packet budget

[verified] Schema 1 contains 27 USB-MIDI packets and schema 2 contains 50;
the ring holds 64. Calling both reporters independently each second allowed
the 27-packet compatibility frame to leave too little capacity for profiling
every time. In profiling builds, `diagnostic_reports()` therefore assigns
alternating one-second slots: schema 2 on odd slots and schema 1 on even
slots. Each report is still attempted only if its whole frame fits. This
spaces each schema's reports about two seconds apart and prevents one schema
from permanently starving the other. Builds without profiling retain the
schema-1 one-second schedule.

[verified] `test_profile_and_compatibility_reports_alternate_on_64_packet_ring`
compiles the production reporter functions against a 64-packet ring, drains
between slots, and checks both complete frames are emitted repeatedly. Other
focused tests cover compile-out behavior, opt-in validation, C encoder
round-trips, recorder acceptance, mixed captures and analyzer output.

## Limits

[verified] The focused host suite passed 113 tests on 2026-10-15:

```text
pytest tests/test_native_diagnostic_telemetry.py \
  tests/test_native_diagnostic_telemetry_build.py \
  tests/test_record_diagnostic_telemetry.py \
  tests/test_analyze_diagnostic_telemetry.py \
  tests/test_native_catalogue_receipts.py
113 passed
```

[inferred] Stage timing should help distinguish expensive engine/effect work
from display and residual work, but the instrumentation itself adds timer
reads and counter updates. This change has not yet been linked with the
pi32v2 toolchain, measured for flash/stack overhead, or captured on hardware.
It does not change renderer behavior intentionally, and it does not establish
that the measured full-song workload meets its realtime deadline.

## Linked candidate checkpoint

[verified] Hera rebuilt 16 shards from source `7036765028d42488e5f353cd0f3e74fd98a70226`;
all containers exited 0 without OOM, and all 167 object paths/hashes verified.
The first private receipt collector failed after compilation with `KeyError: 15`;
a separate verifier captured the retained inspections/logs and checked all outputs
before container removal. Its verification receipt SHA-256 is
`88b6acaa28e9a25d64aa139f31d11f595e1974e83c2408ee04fa4aafb554382d`.

[verified] The frozen link at Hera
`/home/claude/mvave-fm1/render-profile-link-70367650-20261015` produced an
849,700-byte app (10,944 bytes under the D7000 limit), SHA-256
`ce7d7dd838d54ca9b860b90d20937f2faf0f56cad500fc31f4f7e5a08c18ce28`.
ELF SHA-256 is `ad76441f849a01409dc025621515a2777709ecc0193443c4504ce104f07bbdc4`;
frozen receipt SHA-256 is
`08e7c209a0871c122ad47976fb253924acbc2db8d0d6d2969c5d97aa74c596af`.
The source tree is `83355e03a27e2de3981a20e9c755d2c2bdf78770` and the
private frozen runner SHA-256 is
`be1095cc0357d327830fe36bab57ef870d31949267ccb5eaaab770ecf17ed9fe`.

[verified] Offline construction against retained stock backups produced target
`52d6846a1a57c253caa6b4ab4dc927761928271a603be13383961936f8b2420b`,
with 208 changed sectors relative to installed target `0903762167a1dd9877c190e3b67e6657cfe4c5f7227af65d327456f73f8ba4fe`.
The prospective input template SHA-256 is
`9417371ddb2a1fc23df9d0679d25ed6e90cb591b9c303f6967c91fe6cf18b5b5`.
The coordinator adds an exact enabled schema-2/nine-stage receipt check because
the generic song diagnostic policy alone also permits non-profiled builds.
This checkpoint has not installed or booted the profiling image. SAVE remains
disarmed and performance, physical transport acceptance and release gates remain open.
