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

[verified: private pinned-SDK IR, corrected after first boot below] The DAC
handler supplies a writable ring window, in bytes. `dac_on()` sets
`DAC_PNS=sr_points/3`; the initial probe incorrectly assumed division by four.
The corrected configuration uses 192 ring frames for 64-frame refill windows.
The new opt-in probe supplies a ramped 997 Hz
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

## Physical audio-probe installation

[verified: dev board, owner-confirmed hardware download entry] The reviewed
fixed loader identified WL82/UBOOT1.00. Two fresh 8 MiB reads both matched
the expected v6 image, SHA-256
`e77ee8af309fc57d1a8eddaac95dec253dda031f269021382c9cb1e977baa103`.
The bounded v6 restore then passed complete-flash verification against the
original factory SHA-256
`127b2ebbef9da3469f0bf7ea3841a5515d01721ebac9bbdc7fc739032d7b5ec1`.
The subsequent audio-v2 installation passed every sector check and the full
8 MiB readback matched its pinned `5cba22f0…` image. Neither transaction sent
a reset. Private receipts are on bench01 under
`/home/claude/fm1-devkit-backups/`, in
`current-v6-before-audio-20261023-2042`,
`restore-v6-before-audio-20261023-2045` and
`install-audio-v2-20261023-2050`.

[verified] Receive-only UART capture and a bounded ten-minute KA6 six-channel
48 kHz PCM32 capture are running before the first boot. The owner has been
prompted for one normal Reset without Update. Installation verification is
not boot acceptance or an audio result; no instrument or dropout-free
playback claim follows from these readbacks.

## First boot: refill-contract failure and correction

[verified: receive-only UART after owner Reset] The probe boots and services
the DAC IRQ, but v2 reports zero valid callbacks and approximately 519 invalid
buffers per second. The KA6 30-second post-reset capture completes without
an ALSA error; inputs 1/2 measure approximately -70.95/-70.74 dBFS after
the first two seconds and fail the reference-tone screening. This is a
failed tone baseline, not evidence of successful audio or instrument timing.
The original pre-boot captures had expired before the owner's reply; a fresh
UART capture receives the running probe's counters. Initial boot messages
were not captured. Private artifacts are
`/home/claude/fm1-devkit-captures/audio-v2-postreset-20261024*` on bench01.

[verified: pinned SDK IR] `dac_on()` reinitializes `DAC_PNS` to
`sr_points / 3`, and `dac_irq_handler()` passes `DAC_PNS * ch_num * 2` bytes
to the callback. V2's 256-frame ring therefore supplies 85-frame windows,
which its strict 64-frame check correctly refuses. The earlier division-by-four
claim above was wrong. The correction reserves 192 frames, giving three
complete 64-frame windows, and logs callback bytes plus the actual PNS/ring
registers outside the IRQ. No vendor implementation is copied into source.

[verified: host regression] A mock of that SDK callback contract exercises
the actual probe's initialization and all three refill windows, checks DDS
continuity across them, equal interleaved channels, ramped amplitude and
buffer guards, and confirms malformed windows remain silent. ASan/UBSan
passes. Reintroducing the old four-window configuration makes the test fail.
All 87 focused tests pass. Corrected v3 is being built offline; it has not
been installed or validated on hardware at this checkpoint.

[verified: corrected v3 private build] ELF SHA-256
`e05323ab1b98743f6c1d51c50d6bea0b55231bf3dc9bcf6b3a6b6d7f38711c59`;
app 170,544 bytes, SHA-256
`32a47b00a2733d6671aa77d16817450d0e16a535ade625b00a40067a908d5788`.
Independent ELF extraction matches vendor objcopy exports. Full-image SHA-256
`cfa6afbe0b3ff60f11760dff72c2b2b25221a7af555007eca8c188bb9349dd32`.
Independent cipher decoding validates directory/app CRCs and the unchanged
cfg-tool payload. The same 42 application sectors change; bytes before
0x4000 and after app end 0x2db50 remain identical to factory.

[verified: exact vendor disassembly] Link audit has zero failures. Manual
sign-off covers the two pending items: `uartx_read`'s call at 0x020066d2
resolves to `strcmp` at 0x02019dec, rather than accessing the apparent SFR
operand. `sdk_meky_check` at 0x02026014 retains its two IRQ-123 registrations
with `isr_check_key`, unchanged enable-bit clearing and 8000-tick scheduling
of `_mkey_check`, without extra key registration. Listing SHA-256
`9b4de0365be44debc549c0b93ee896780adab6f8cdb0fb64c05025121afac7bd`.
The emitted audio handler preserves its interrupt prologue/epilogue and calls
the SDK handler. The exact new image passes the private NOR install, factory
restore and interrupted-page recovery model. Its hash is separately admitted
by the transaction tool; v2 remains admitted for restoring the installed image.
The owner has been prompted for hardware download entry. No v3 installation
or successful tone result is claimed yet.

[verified: subsequent physical transaction] After the owner entered hardware
download mode again, two fresh complete reads matched installed v2 (`5cba22f0…`).
The bounded factory restore passed its full-image comparison (`127b2ebb…`),
and the v3 install passed every sector and full 8 MiB readback (`cfa6afbe…`).
Private receipt directories on bench01 are
`current-audio-v2-before-v3-20261024`,
`restore-audio-v2-before-v3-20261024` and `install-audio-v3-20261024`, under
`/home/claude/fm1-devkit-backups/`. UART capture remains active and a fresh
ten-minute KA6 capture is armed. The owner has been prompted for normal Reset;
v3 boot and audio acceptance remain pending at this checkpoint.

## Reducing physical button intervention

Owner asks whether download entry can be automated. [verified: pinned SDK
source] `apps/common/usb/device/msd_upgrade.c` provides
`go_mask_usb_updata()`: run from `.volatile_ram_code`, disable interrupts,
close RAM protection/MMU, call `nvram_set_boot_state(2)`, then request a
core reset using clock `PWR_CON` bit 4. The existing recovery note identifies
fm1-nes using this path through a CDC command [reported: docs/07 §2.3].
This establishes a candidate mechanism, not proof that a new diagnostic link
has the right helper implementations or RAM placement. The source contains
weak empty helper definitions: verify strong resolved implementations before
relying on them. No ROM-entry command has been sent in this campaign.

[verified: current SDK board configuration] Debug UART2 transmits on PB3
but has `rx_pin = -1`. Tigard is wired receive-only. A diagnostic command
channel needs an enabled, verified free board RX pin, one additional Tigard TX
wire, a bounded parser and a reviewed transition routine; that is the next
candidate to avoid repeated manual download entry. It does not recover a
hung application. Isolated control of physical Update/Reset could provide
that fallback but needs a separately verified electrical interface. Neither
change is part of the installed v3 image; no wiring modification is requested
until the pin/driver and electrical checks are complete.

### Opt-in UART command implementation, offline checkpoint

[verified: source, host tests and actual vendor link] Added an optional
`--boot-control` preparation mode. It registers UART1 RX on exposed carrier
PA5, with TX disabled, leaving UART2/PB3 logging unchanged. The current minimal
hello board source registers no other PA5 owner. Physical wiring and reception
are not yet validated. The installed v3 image does not contain this feature.

The receiver runs in its own task with a fixed 128-byte DMA ring and a bounded
32-byte parser. `LUNAR PING` queries it. `LUNAR ARM UBOOT` followed by
`LUNAR ENTER UBOOT` within five seconds requests entry once. Invalid/overlong
input, receive errors and expiry disarm it. This physical diagnostic protocol
is not authentication and exposes no memory, flash or eFuse commands. The host
tool `tools/devkit_boot_control.py` defaults to PING, requires each response
before the next command, opens only the named Tigard UART exclusively and
keeps DTR/RTS low. No host command has been sent to the board.

[verified: pinned V1.2.13 private library IR and new linked vendor disassembly]
The strong `nvram_set_boot_state` implementation itself copies the 16-byte
USB-download marker to RAM `0x01C7FD80`, calls P33 reset and spins. Its `state`
argument is optimized away in this library. Thus the later clock-register
reset in the USB demo wrapper is unreachable with this implementation. The
new code calls this real library implementation directly, without importing
the demo's empty weak helper definitions. It requests no flash write.

Private offline build: `build-sdk-audio-control-v1` on Aeon; local evidence
under ignored `scratch/devkit-20261023/build-audio-control-v1/`.
ELF SHA256 `4735de904f67025c974e42421c06331aeea3ec540085ec498d7ccf180a430b32`;
vendor listing SHA256
`cce0ea6c7afd3c1c6bc30d1aaddb3a2b12079809dac7934cd01bae52de553246`.
`enter_rom` is in copied `.ram0_data` at `0x01C01096`, disables interrupts and
enters the critical section, then calls the nonempty library function at
`0x02001FFC`. Its actual 34-byte body copies the marker and calls RAM
`P33_CON_SET` at `0x01C0106E` with `(0xA0,4,1,1)`, then spins. No weak fallback
survives this path. Automated link audit: zero failures, one scheduling item
requiring manual review. [verified: new vendor listing] That item is signed
off: `sdk_meky_check` at `0x0202638E` registers IRQ123 on both cores, clears
the enable bits and schedules `_mkey_check` at 8000 as in the prior image.

90 focused local tests pass, including actual C parser ASan/UBSan checks for
noise, malformed commands, overflow, timeout, timer wrap and one-shot entry;
host handshake/default-no-reset tests; preparation and existing probe,
transaction, link-audit, boot and tone-analysis tests. The offline vendor build
also succeeds with the downloader disabled and no USB passed to its container.
This is not a packaged/admitted flash image or proof of bootloader entry.
Next: finish v3 normal-boot/tone acceptance, verify the extra UART wire and
candidate pin electrically, then package/review/admit the control-enabled
diagnostic and validate PING before any entry command. A hung application
still needs physical Update/Reset or separately reviewed isolated control.
