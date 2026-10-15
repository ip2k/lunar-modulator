# IRQ occupancy discriminator [inferred until target measurement]

The owner cold-booted Lunar and still heard severe distortion and observed a
very laggy waveform. The completed producer-gap campaign produced 267.96
64-frame blocks/device-second against roughly689 required [verified: retained
schema1 counters]. It auto-started Event Horizon; it does not isolate idle or
single-note behavior. See `2026-10-15-producer-gap-results.md`.

## Measurement design

`LUNAR_DIAGNOSTIC_IRQ_PROFILE=1` adds cumulative schema6 observations. The
register-free core tracks inclusive ALNK0, timer5, input, USB-poll and nested
UAC-service durations, plus their union (`busy_ticks`). The timer may interrupt
ALNK0; inclusive totals must not be summed. Full saved ICFG is restored after
each short mutation, preserving its global-enable state [verified: source
matches the existing flash HAL critical-section contract]. Timestamp sampling
is inside the mask to prevent a preemption gap from double-counting union time.

Render elapsed and concurrent IRQ union ticks are cumulative uint32 counters.
The counter copy is interrupt-quiesced; USB encoding/publication occurs after
restoration. Packet encoding is22 canonical uint32 fields,119 bytes/40 USB-MIDI
packets, reserved as a complete frame. Existing schemas1-5 retain their format.
This is a private diagnostic protocol, not release readiness or an ABI promise.

## Limits and next acceptance

Hooks measure C handler bodies, excluding interrupt entry/exit assembly and
some compiler prologue/epilogue. Short masked accounting adds overhead and
slightly delays pending interrupts. Input still scans10kHz and USB services2kHz;
no service bypass is justified by present evidence. Raw TIMER4 ticks do not
establish CPU frequency. Cumulative counters wrap modulo2^32; captures and
comparisons must use bounded elapsed windows and unsigned deltas.

Host checks validate arithmetic, disabled behavior and wire representation.
They cannot verify pi32v2 code generation or device scheduling. Next: frozen
Hera build with no autoplay and schema6, exact image/recovery admission, then
controlled note capture. Compare a matched profiling-disabled image before
attributing sustained overhead to the original firmware. SAVE remains disarmed;
no new hardware operation is authorized by a host test result alone.
