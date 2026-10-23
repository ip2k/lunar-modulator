# Dev-board audio-performance campaign

## Goal and acceptance

Owner, 2026-10-23: pursue dropout-free Lunar playback on the dev board,
research the other FM-1 firmwares, and transfer measured optimizations to
the FM-1. This is ongoing; PR #154 completed only isolated resampler timing.

Acceptance requires real instrument/effect rendering, measured worst-case
deadline margin and underrun counters, and an actual analog capture under
a documented workload and control activity. Establish a 30-minute sustained
soak per admitted representative workload, with no missed buffers or detected
audio discontinuities; do not generalize this to arbitrary unlimited loads.
Host tests or a clean synthetic tone alone do not satisfy the goal. The dev
board's internal DAC and the FM-1's external I2S codec need separate validation.

## Audio return

[reported: owner, 2026-10-23] The dev board's green audio output is connected
to Komplete Audio 6 inputs 1 and 2 on bench01. The earlier MIDI-to-MIC cable
was disconnected. Tigard remains receive-only on PB3, with VTGT and GND.

[verified: ALSA on bench01] `hw:K6,0` accepts six interleaved S32_LE capture
channels at 48 kHz. Capture all six and analyze channels 1–2; do not request
an unsupported stereo hardware format. Direct monitoring is off and the
interface selects its internal clock. No mixer settings were changed.

[verified] A five-second baseline capture succeeded, 240,000 frames, before
any new board audio firmware was installed. Private file:
`/home/claude/fm1-devkit-captures/line-return-baseline-20261023.wav`, SHA-256
`13047fc63b12972956d51c78a8d269af5f5de34fcd0c2334b0db7d9528274267`.
Input 1 RMS -46.51 dBFS, peak 0.04684; input 2 RMS -46.31 dBFS, peak 0.04596.
This is the connected baseline, not a calibrated noise-floor measurement or
proof that the board is producing valid audio. Establish gain/clipping and
channel routing with a low-level diagnostic tone before judging instruments.

## Implementation sequence

1. Verify SDK internal-DAC buffer ownership and callback semantics from the
   pinned headers/library before selecting an API; the existing hello app
   initializes no audio device. Do not assume a data callback supplies samples.
2. Build a low-level output/capture diagnostic with counters and deterministic
   reference; verify ELF placement and the exact private image before install.
3. Measure real producers and conversion, then full rendering under live DMA.
4. Optimize the measured critical path, preserve DSP comparisons, and repeat
   analog capture plus deadline/underrun soak before declaring success.

## Tool coverage

[verified] Rarefaction is rooted at the primary checkout and rejects this
external worktree as outside its root. Its name fallback misses the devkit
worker. Serena is also on the primary checkout; no other session's shared
activation was changed. Use bounded primary-source queries where identical,
and inspect this worktree and SDK/build artifacts directly for new code.
Neither clangd nor host tests verify pi32v2 code generation or DAC behavior.

## Reference-tone checkpoint

[verified: private pinned-SDK IR] The DAC handler supplies a writable ring
window, in bytes. `sr_points=256`, four channels and `DAC_PNS=sr_points/4`
yield 64-frame refill windows. The new opt-in probe supplies a ramped 997 Hz
reference with a digital peak of 1024/32768, logs callback/full-IRQ timing
outside the IRQ, and leaves unknown PA-mute GPIOs untouched. It uses temporary
DAC calibration (`trim_en=1`), which skips the SDK's trim-setting flash write.
This does not yet count every hardware underrun; gaps, timing and captured
continuity must be evaluated together. No instrument is rendered in this mode.

[verified: local tests] 73 focused tests pass across link audit, diagnostic
preparation, bounded flash transaction and boot compatibility. An ambiguous
pi32v2 relative-call operand is now pending manual vendor-objdump review,
never silently accepted as proof of no eFuse access. Unresolved patterns,
ordinary immediate loads, relocatable objects and real extra references fail.
The SDK build is private and has not been installed at this checkpoint.

## Exact offline audio-probe image, v2

[verified] Pinned SDK build on Aeon succeeds. ELF SHA-256
`2e6e208d1099882a32118074cca5ee2dae5819c27cec27f237ad2c694aa2aa88`;
app 170,512 bytes, SHA
`f82de9b59419e7b21be36088893d9dbd04a88fa081b1d0343e429d49a4d240ab`.
Vendor objcopy section exports match independently extracted ELF sections in
the SDK's documented concatenation order. Private full-image SHA
`5cba22f0b0b19bda0847a303eee033f7a2b31a7bef5255ef1d98ca27f796c7b2`.
Exactly 42 application sectors change (0x4000 through 0x2d000); raw bytes
before 0x4000 and from application end 0x2db30 remain identical to factory.
Independent reference-cipher decoding validates all directory/application CRCs,
exact app and unchanged cfg-tool payload. Private scripts/evidence live in
`scratch/devkit-20261023/`; never publish vendor blobs or listings.

[verified: vendor objdump for that ELF] Manual audit sign-off: the sole raw
eFuse-address pattern is the relative operand of `uartx_read`'s call at
0x020066b8 to `strcmp` at 0x02019dd2, not an SFR access. The preserved
`sdk_meky_check` at 0x02025ff4 registers IRQ 123 on the two cores with
`isr_check_key`, clears the same IRQ-enable bits, and schedules `_mkey_check`
with 8000 through `__sys_timer_add`, as previously reviewed. No extra calls
or key registration are introduced. Automated report: zero failures, these
two manual items marked pending by design. Listing SHA
`9f54eb8cf62f61d220aa143111a61909359d6a4f78cd981958e820ab31cd54f6`.
Probe state is in SRAM, code in XIP; the emitted handler has an interrupt
prologue/epilogue and calls the pinned SDK DAC handler.

[verified: offline NOR model] Actual private images pass install, exact
factory restore, and an interrupted page followed by restore. Metadata is
written last. The transaction tool admits this hash with its own fixed
42-sector plan; the older v6 hash retains its 40-sector plan. 74 focused
host tests pass. No physical installation or audio-output result yet.

## Capture screening prepared

`tools/devkit_tone_analysis.py` reads PCM16/PCM32 using Python's standard
WAV reader in bounded chunks, including the KA6's six-channel PCM32 format.
It checks channels independently, skips a stated startup interval, and reports
cycle irregularity, missing cycles, signal level and clipping. The default
997 Hz period tolerance is two capture samples with a 2% overall frequency
bound. This is reference-tone screening, not a general click/distortion or
music-quality certificate; combine it with device timing and listening.

[verified] Ten synthetic tests accept slight clock drift/noise and reject
silence, held blocks, skipped samples, repeated blocks, clipping, noise-only,
missing channel and short capture. All 84 focused tests pass. No extra Python
packages are required on Bench01. The existing connected no-tone baseline
is rejected, as expected. After excluding its first two seconds, measured
RMS is -68.00/-64.91 dBFS on inputs 1/2; this differs from the full-capture
RMS reported above and must not be confused with a calibrated noise floor.
Exact probe/tools are staged privately on Bench01. Owner download-entry
confirmation remains pending; no new device protocol command has been sent.

## Real-engine offline checkpoint

[verified: pinned vendor compiler] The opt-in `--fm6-benchmark` preparation
links the actual FM6 engine and its eight Apache-2.0 msfa translation units,
without enabling SDK C++ startup support or the DAC. The diagnostic records
12 cases (TINE EP, WARM PAD, SAW LEAD at 1/4/8/12 voices), first/cold renders,
release at block 192, render minima/maxima/totals, separate note-on/off batch
costs, finite/nonzero sample checks and PCM-bit checksums. Logs/checksums are
outside timing; creation/table initialization is excluded. It deliberately
uses no mixer, effects or sequencer and cannot establish audio continuity.

[verified: desktop and source tests] All 12 real-engine fixture hashes match
an independently built private host driver. A wrapping synthetic timer checks
the measurement boundaries, and AddressSanitizer checks the host workload.
The 44.1 kHz instance requires 20,288 bytes on this desktop; the diagnostic
reserves a separate fixed 65,536-byte capacity. All 86 focused tests pass.

[verified: private ELF] The reproducible SDK FM6 build succeeds, ELF SHA-256
`cae24a7d553581b00199031599a7a6fb737e37ba0f31ec48a007a11c559ed610`.
Its diagnostic arena/output are in `.ram0_bss` at 0x01c04950/0x01c14950;
code/constants are in XIP. Automated link audit has zero failures and one
manual item. Vendor disassembly confirms `sdk_meky_check` at 0x0202ee1a
retains its two IRQ-123 registrations and 8000-tick `_mkey_check` scheduling,
with no new key registration; this signs off that exact pending item.
Private listing SHA-256
`c648bf99a5d63530ba06dd18b397e34cf7882b80ec7598f10e2764f5b99ccb9c`.
No FM6 flash image has been packaged/admitted or installed, and no target
FM6 timing/checksum or analog result exists yet. The earlier quiet audio-v2
image remains the separately reviewed next hardware baseline.
