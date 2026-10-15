# Telemetry-only project diagnostic builds

[verified] Before this change, `LUNAR_DIAGNOSTIC_TRIO_PULSE` controlled both
the one-shot C4 pulse and the periodic SysEx telemetry in
`firmware/native/app_probe.c`. The builder also required the pulse profile to
be content-free, so a prepared project plus companion SET could not emit the
existing runtime counters.

[verified] The builder now has a separate `--diagnostic-telemetry` option.
Telemetry code is compiled under `LUNAR_DIAGNOSTIC_TELEMETRY`; the one-shot
pulse remains under `LUNAR_DIAGNOSTIC_TRIO_PULSE`. Enabling the old pulse option
still enables telemetry for compatibility. Telemetry-only builds are allowed
for bounded `diagnostic` and `song-diagnostic` runtime modes and rejected for
`continuous`. No telemetry option changes SAVE, flash, installation, or
hardware-admission state.

[verified] The telemetry packet schema and one-second cadence are unchanged.
For a prepared project startup, the existing `initial_engine_result` field is
now populated from the project-start API result (1 means that API succeeded).
For the content-free Trio startup it retains the `fm1_app_select` result (the
Trio selection API uses its existing status enum). Interpret the value with
the corresponding build receipt; its numeric meaning is path-specific. A
failed project startup returns to ROM before the telemetry loop.

[inferred] A useful next timing comparison is a new source-fresh Event Horizon
project-plus-companion-SET build with telemetry enabled and no synthetic pulse.
The exact prepared profile must come from the matching fresh catalogue, list
project `replacement-showcase-candidate-event-horizon` first and companion
`replacement-showcase-event-horizon-companion-set` second, and validate the
SET's parent-project identity. Then link both loaders and use project startup
index 0. Do not reuse the older project-only profile or its SHA as evidence
for this source revision.

[verified] Focused tests cover the telemetry flag/configuration, allowed and
rejected runtime modes, backward compatibility of the pulse option, and the
independent C compile-time gates. The build was not run here; current-catalogue
preparation, target link/disassembly, fresh-source provenance, and physical
audio/performance review remain for the coordinator. No device action or
release/installability claim is part of this change.
