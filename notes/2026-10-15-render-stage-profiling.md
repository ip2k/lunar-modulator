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

[verified] Tick totals and maxima are unsigned 32-bit values. Totals wrap
modulo 2^32; consumers should use differences between reports for interval
estimates. Profile samples reset only after the complete frame is enqueued.
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
