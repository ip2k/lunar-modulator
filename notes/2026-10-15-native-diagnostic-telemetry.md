# Native diagnostic MIDI telemetry — 2026-10-15

[verified: source and host tests] The opt-in `LUNAR_DIAGNOSTIC_TRIO_PULSE`
application now emits a private schema-1 diagnostic SysEx report at most once
per second. Default/release builds do not compile this report. No new inbound
command, flash access or device-control operation is introduced.

The wire format is `F0 7D 4C 55 4E 41 52 01`, fourteen unsigned 32-bit values
encoded as five little-endian seven-bit digits each, then `F7`: 79 bytes,
27 USB-MIDI event packets (26 CIN 4 and one CIN 5). Fields in order:

1. uptime in milliseconds;
2. maximum render ticks;
3. maximum draw ticks;
4. audio queue underruns;
5. dequeued USB MIDI messages;
6. consumed UART MIDI bytes;
7. accepted MIDI note-ons;
8. rejected MIDI messages;
9. MASTER ADC raw value;
10. sampled user stack margin;
11. sampled system stack margin;
12. stack sample count;
13. initial engine result;
14. produced audio blocks.

Ticks are raw existing timer measurements, not microseconds. Missing stack
instrumentation is represented by `UINT32_MAX` margins and zero samples.
Counters are individually sampled; this is not an atomic cross-counter snapshot.

[verified: source review] This application's main loop is the only MIDI output
producer. Admission requires USB configuration and enough of the 64 ring slots
for all 27 packets. Insufficient space drops that report and waits another
second; there is no busy retry. The USB consumer can only free capacity during
publication. A USB reset clears configuration and the queued prefix; subsequent
packet sends are dropped. Delivery is not guaranteed across disconnect/reset.
The decoder rejects incomplete captures rather than interpreting them as zero
measurements. This admission argument depends on retaining a single producer.

`python3 tools/native/diagnostic_telemetry.py capture.syx` decodes a saved raw
MIDI capture without opening any device. It permits realtime bytes within and
between frames, and rejects unknown schema, noncanonical integers, empty or
truncated input. It deliberately rejects unrelated MIDI messages: capture this
private diagnostic output separately. Bind capture timestamps and device
identity to the exact image/build and boot receipt; counters alone do not prove
which firmware ran or establish hardware acceptance.

[verified: host tests] Tests compile the actual encoder and extracted report
with C99 warnings-as-errors and address/undefined-behavior sanitizers. They cover
integer boundaries, packet termination/padding, decoder rejection, interleaved
realtime bytes, disconnected/full queue admission, exact-capacity admission,
ring-counter wrap and uptime wrap. Independent review found no blocking framing
or concurrency defect. Host tests do not establish pi32 ABI, stack usage or
hardware delivery. Approximate simultaneous local arrays total 243 bytes before
compiler reuse; the fresh Hera target build must check actual resource use.

No image containing this telemetry has yet been installed or hardware-tested.
It is an investigation aid for the unresolved silent external MIDI and audio
timing failures, not evidence that either problem is fixed. SAVE and release
admission remain disarmed.

## Passive recorder and joined ingress verification

[verified: host tests] `tools/native/record_diagnostic_telemetry.py` opens only
one exact named MIDI input, never a MIDI output. It records complete validated
frames in `raw.syx`, timestamped observations in `events.jsonl`, and hashes both
in a success receipt. The output directory must be new; zero valid frames is a
failure without a success receipt. The supplied image hash is an operator
expectation, not measured device identity. Hardware acceptance remains false.

Recording is limited to 180 seconds, 4,096 frames and 8,192 events. Every yielded
message checks the deadline, including continuous traffic; payload length is
checked before copying SysEx. Backend enumeration/opening or an individual
iterator advance can still block: this is a capture-loop deadline, not a hard
process deadline. A supervising physical-cycle helper must enforce its own
process timeout and preserve failed captures. Tests exercise continuous input
and an oversized payload that must be rejected without iteration.

[verified: host tests] The joined ingress regression uses the actual USB packet
decoder/ring reader, UART drain/parser and common application event handler.
USB note-on/velocity-zero note-off, UART running status and channel rejection
pass. Synth callbacks are deliberately stubbed; this does not prove voice
activation or audible output. The coordinator reran recorder, diagnostic,
joined ingress and existing MIDI suites: **56 passed**. No target or device
acceptance follows from these host checks.

[verified: bench preparation] A private environment at
`/home/claude/.cache/lunar-venvs/telemetry-capture-20261015` on bench01 uses
extracted Debian arm64 packages rather than system package installation:
python3-rtmidi 1.5.8-3+b3, python3-mido 1.3.3-0.1, python3-packaging 25.0-1,
and libjack-jackd2-0 1.9.22~dfsg-4. Imports pass with `PYTHONPATH` pointing at
`packages/usr/lib/python3/dist-packages` and `LD_LIBRARY_PATH` pointing at
`packages/usr/lib/aarch64-linux-gnu`. The virtualenv interpreter is `bin/python`.
No MIDI port was opened for this dependency check. Passive inventory still
showed FM1 ROM device 057, KA6 device 051 and Pico device 038. A fresh identity
and paired flash reads remain required before any new installation.
