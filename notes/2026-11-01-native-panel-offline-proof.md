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

## Freeze validation

[verified] Final normal command ran both tests/test_native_display_controls.py
and tests/test_native_diagnostic.py successfully. Final ASan+UBSan command ran
the full actual-app proof successfully (detect_leaks=1, halt_on_error=1).
The replay now covers 201 events, including SEQ/held REC/keys and PLAY/STOP;
PCM, parameter arrays, key state, LEDs, scope values/cadence and framebuffer
match a directly driven app with the same eight-voice admission.
Three real host threads transferred 10000 input records and 10000 PCM blocks,
checking FIFO payloads across uint32 wrap with acquire/release publication.
This checks host concurrency, not hardware IRQ priority or target atomics.

[verified] Existing diagnostic_app.c/.h contents before the proof macro are
byte-identical to e267d7cd. No other existing source/build/profile file changed.
The proof explicitly refuses compilation with FM1_APP_RENDER_PIPELINE: no live
UI work can be combined with pending pipeline work in this proof. A future
pipeline integration must supply a reviewed drained barrier separately.
Transport object's undefined symbols are only memcpy/memset on this host;
there is no transitive app/render/draw call in the IRQ path.

[verified] Host clang -O1 object accounting (not target fit): diagnostic_app.o
text2959/BSS307296, display.o text794/BSS0, transport.o text1713/BSS0.
For one proof owner, caller storage adds display528 + transport64 + input128 +
PCM2048 = 2768 bytes, so counted host static owner storage is 310064 bytes
before any caller IRQ destination or other HAL globals. If the existing HAL
were eventually adapted, its two 64-frame stereo int32 halves add 1024 bytes;
that buffer already exists in the frozen profile and is not added here.
The row480 is included in display528; framebuffer115200 is included in app.
Render writes the reserved PCM slot directly; transport has no extra PCM copy
buffer. IRQ destination storage belongs to the caller (512 bytes per half).

The complete host test ELF has text842010/data20720/BSS812016, including its
second app+arena, synthetic framebuffer, fault-case objects and stress queues.
Those oracle/test objects are not proposed runtime storage. The host link has
no g_default_workspace symbol; external state workspace is explicit and no
persistence workspace is supplied. Test links are not dead-stripped target
closure evidence. Target text, full runtime BSS including imported HAL globals,
stack high-water, display/control/render/IRQ timings and queue latency remain
unmeasured and must pass a separate offline target link/admission review before
any hardware binding or startup change. The current profile is still HOME-only,
black-screen diagnostic; this branch does not advertise a native product.

Reproduction uses existing lunar-asan:ubuntu-24.04 image
sha256:54edd6544fdc41ef5573ae26f7aa8e7d1f594e5e4b9b54e2ad2f427f33e392a1:
`python3 -m pytest -s -q tests/test_native_display_controls.py tests/test_native_diagnostic.py`
with a task-owned --basetemp, then the proof alone with
FM1_SIM_CC=clang FM1_SIM_CXX=clang++
FM1_SIM_EXTRA='-fsanitize=address,undefined -fno-omit-frame-pointer'.
No target compiler, SDK, image, devices, USB/MIDI traffic or browser was used.

Next dependency: independent review of the frozen branch, then target closure
and concrete lock-free/priority/ordering and LCD completion-register proof.
Do not bind the host mock to current lcd_sync: timeout does not establish DMA
quiescence and cannot release a borrowed row/framebuffer. Do not size release
queues from these host test capacities or claim target deadlines from host runs.
