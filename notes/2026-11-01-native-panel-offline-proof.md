# Offline native panel proof

[verified] Base e267d7cd58efef29afb2c0c38562f4878e8106f5. This is a host-only proof,
not a target image, default-profile change, hardware admission or product claim.
The unchanged native fit remains the separately measured frozen diagnostic.

The sole main owner calls the existing app APIs. New owner accessors only exist
under LUNAR_DIAGNOSTIC_OFFLINE_PROOF; the old HOME-only diagnostic interface is
unchanged. Unit 0 remains DX7; its existing budget API reapplies eight voices
after control/selection and before each render. Other arrangements fail closed.
SAVE has no store. No USB, MIDI transport, persistence, ADC or CPU1 was added.

Display uses the app's one permanent 115200-byte RGB565 framebuffer plus one
480-byte wire-order row. It invokes the real app draw only with no active frame
lease, preserving the app's quarter-rate draw/scope policy. Completion is an
explicit host mock; non-mock binding refuses. Delay retains row bytes; wrong,
failed or timed-out completion poisons the object and retains both leases.
There is no DMA cancellation, recovery, reset or timed-out-buffer reuse.

Transport is host-proof-only and uses C11 acquire/release SPSC publication.
Input records retain capture order (timestamps do not reorder); physical IDs
0..13 map to app buttons and 14..40 to app keys. All seven encoder IDs retain
detents. Complete 64-frame stereo PCM words are published once. The IRQ surface
only copies published words or zeroes; it has no app/render/draw calls.
Overflow and publication/app errors are sticky and silence queued audio.
PCM full is backpressure. Queue sizes are caller-owned offline parameters.
Host atomics do not prove pi32v2 lock freedom, ISR priority or latency.

## Checks in progress

[verified] First display-only suite passed normal and ASan/UBSan on Aeon
CPUs12–15 (4 CPUs/6GiB, docker-batch.slice, --rm task labels).
[verified] Expanded actual-app controls/PCM suite passed normal: 189 ordered
panel events, every matrix/encoder ID, recreation, SAVE refusal, sample-for-sample
PCM and framebuffer comparison with direct app baseline. Guard cases cover
RGB565 byte order, delayed/error/timeout/wrong completion, display ticket wrap,
PCM/input counter wrap, unpublished PCM silence, full PCM backpressure, input
full fault, duplicate/wrong leases, render failure and queued-audio suppression.
Remaining: expanded sanitizer run, concurrency stress/coverage hardening,
independent review and final resource/closure accounting.

The fixture's reference app/framebuffer, pattern and fault objects are test-only.
Initial 64-bit host sizeof: app241520, display528 (row480 included), transport64,
input16*8=128, PCM4*512=2048. Runtime proof storage before descriptors/arena is
app + display + transport + input + PCM; no extra full framebuffer or IRQ staging
buffer is supplied by transport. Target object sizes/text/stack are unmeasured.
No current target budget or profile is increased.

Logs/stage lifecycle: unique Aeon project stage
/home/likwid/datasets/lunar/native-panel-offline-20261101. Keep only small logs
and notes after final gates; remove reproducible stage/build products, archives
and task claim after saved handoff. No existing shared cache changed.
