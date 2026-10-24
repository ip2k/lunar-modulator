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
The independently exported app matches vendor objcopy byte-for-byte:
171472 bytes, SHA256
`d855803d41cda5bd88b670883f89104a034837505b9d93524329e72245aae772`.
Static internal data/BSS grow by 168 bytes; the extra task also allocates its
1024 SDK stack units at runtime, outside this static count. The private
full-image candidate SHA256 is
`ba8b03938e0b2a90461a728646a31f7de72975df282e9c1931750400cadaaaa6`.
Independent decoding, directory/app CRCs and unchanged factory configuration
checks pass. Exactly the same 42 application sectors change, through
`0x2D000`, with app end `0x2DEF0`. The exact hash is admitted in the
transaction tool without expanding its bounds. Actual-image NOR install,
factory restore and injected interrupted-page restore models all pass, with
metadata written last. It is not installed or proof of bootloader entry.

Next: finish v3 normal-boot/tone acceptance, verify the extra UART wire and
candidate pin electrically, then install the reviewed control-enabled
diagnostic and validate PING before any entry command. A hung application
still needs physical Update/Reset or separately reviewed isolated control.

## v3 normal boot: refill fixed; analog acceptance fails

[verified: owner Reset confirmation and fresh running captures, Oct 23 Pacific /
Oct 24 UTC] The owner reset v3 normally. Earlier armed recordings had expired;
no additional reset was requested. Fresh receive-only UART and a 30-second KA6
recording captured the running board. UART reports 512-byte refills, PNS 64,
ring 192, zero invalid buffers and zero callback/full-IRQ deadline overruns.
At uptime 6:45: 277803 callbacks, max fill 399 and IRQ 540 oscillator ticks
(16.625 and 22.5 microseconds at the verified 24 MHz timer). These are not
an underrun counter or acceptance of real instrument workloads.

Private Bench evidence is `audio-v3-running-20261024-0650-uart.bin`,
`audio-v3-running-20261024-0650.wav` and `...-analysis-final.json` under
`/home/claude/fm1-devkit-captures/`. KA6 completed with exit 0 and no ALSA
errors. After skipping 2 seconds, channels 1/2 RMS are -60.66/-60.37 dBFS.
Tone screening fails for weak signal and irregular zero crossings. Spectral
correlation finds the intended tone near 997.4 Hz on both channels; the
zero-crossing estimates near 1186 Hz reflect extra noise crossings, not
proof of a wrong oscillator frequency. Channels 3/4 contain only low noise;
5/6 are zero. Analog dropout acceptance remains **failed/inconclusive**.

[verified: pinned V1.2.13 `cpu.a` private LLVM IR versus SDK `asm/dac.h`]
The header documents `dac_set_gain` and `dac_direct_set_gain` in raw 0..31
units, and `dac_set_volume` in 0..16384 units. All three implementations
actually use a percentage lookup. With the default table, index is
`min(floor(argument * 32 / 100), 32)`. Thus gain 8 selected index 2, analog
code 1. Gain 54 selects index 17, analog code 8. Volume 100 selects digital
15920. The old volume 16384 saturated to that same digital value. Even the
"direct" gain API performs the lookup. `dac_on` does not replace these gains.
The weak recording is consistent with the unintended low analog gain;
causation and corrected signal quality require another physical capture.

Corrected the probe to gain 54 percent and digital volume 100 percent;
retained -30 dBFS PCM and startup ramp. New startup telemetry reports actual
DAA_CON1 and DAC_VL0/VL1 so linked behavior can be checked on hardware. The
actual-C host regression checks the percentage-to-index contract rather than
repeating the stale raw arguments. These checks do not replace a target run.
This SDK documentation discrepancy is an upstream contribution candidate;
no third-party report or private vendor IR has been published.

Semantic-tool check: Serena selected this absolute worktree and found
`lunar_devkit_audio_probe` at its actual source location. Rarefaction is
rooted at the primary checkout, has no root compilation database, and refuses
the outside-root worktree scope query. File inspection, actual host C tests
and the vendor target build remain authoritative here; no claim of complete
worktree caller indexing or pi32v2 ABI validation by clangd.

### Corrected control-v2 offline build

[verified: actual vendor toolchain build, independent ELF export and listing]
Built `build-sdk-audio-control-v2` on Aeon. ELF SHA256
`2a73385ae8c87608be852dc03bccec59b3345d2eb4016ab6dbd6890a7a539300`;
listing `c7c62a8dfd12ea6bf0469c780c786e0dfeb0f21448d0255251b1426de79612d4`.
Independent `.text`/`.data`/`.dynamic_data`/`.ram0_data`/`.cache_ram_data`
concatenation matches vendor objcopy: 171568 bytes, SHA256
`fa73e02ac3cb8e3800c66cc6cc7af1463d5b6b2fb1c7ea7b16ae24a89031f736`.
Linked calls pass volume 100 and gain 54; register telemetry reads match the
pinned WL82 register layout. Audit has zero failures; its one manual item is
signed off in the listing: `sdk_meky_check` at `0x020263EE` registers IRQ123
on both cores, clears enable bits, schedules `_mkey_check` at 8000 as before.
`enter_rom` remains RAM `0x01C01096`, directly calls the nonempty library
`nvram_set_boot_state` at `0x02002014`, whose 16-byte RAM marker copy and
P33 reset at `0x01C0106E` are unchanged. 90 focused host tests pass.

Requested the owner add Tigard UART TX to carrier PA5 with USB disconnected,
VTGT reference selected and existing RX/PB3, VTGT/3.3 V, ground retained;
then reconnect and enter hardware download mode. Official Tigard wiring and
voltage behavior checked against
<https://github.com/tigard-tools/tigard#hardware-hookup>. Current v3 has no
command receiver: this first installation still requires physical entry.
Do not transmit until the new wiring and new image are confirmed. No claim
of physically validated PA5 reception or automatic ROM entry yet.

Control-v2 private full-image SHA256
`1bbaf5ae4ddf6a6fc6289c095f0f4b4361913b436b616f6c1f9e43d7da4cad25`.
Independent decoding, directory/app CRCs and unchanged factory cfg pass.
42 sectors remain `0x4000..0x2D000`, app end `0x2DF50`. The exact hash is
admitted with unchanged bounds. Install, exact factory restore and injected
seventh-page interruption/restore models pass, metadata last; all 16 transaction
tests pass after admission. This is a model result, not a physical install.

## Control-v2 physically installed, awaiting normal boot

[verified: bench receipts, 2026-10-24 UTC] Owner confirmed Tigard TX to PA5,
VTGT mode and hardware download entry. Fresh enumeration: `3-1.2`, devnum 95,
`4c4a:8057`, `/dev/sg0`. Exact fixed-loader and candidate hashes were checked.
Two fresh 8 MiB reads match installed v3 SHA `cfa6afbe...`. Factory restoration
then verified the entire flash SHA `127b2ebb...`. Control-v2 installation
verified the entire 8 MiB SHA
`1bbaf5ae4ddf6a6fc6289c095f0f4b4361913b436b616f6c1f9e43d7da4cad25`.
Private receipts under `/home/claude/fm1-devkit-backups/`:
`current-audio-v3-before-control-v2-20261024`,
`restore-audio-v3-before-control-v2-20261024`, and
`install-audio-control-v2-20261024`. No software reset or UART TX sent yet.

Fresh UART capture PID 3801273 reports armed, and KA6 wrapper 3801274 is
recording six-channel S32LE/48 kHz for ten minutes. Evidence prefix:
`/home/claude/fm1-devkit-captures/audio-control-v2-firstboot-20261024`.
Previous running-v3 UART capture was intentionally terminated before opening
the new exclusive capture. Owner prompted for normal Reset without Update;
verify actual readiness before PING and audio capture after this boot.

## FM6 timing with UART control, offline preparation

[verified: actual pinned SDK build and independent export] Built a separate
`--fm6-benchmark --boot-control` image. It times three patches at 1/4/8/12
voices; it does not enable DAC playback. ELF SHA256
`2516235d00805034a5fd9add1c82dd137d434fc75a3bad92474d7968c208bfac`;
listing `2fa0992024bf3e1754e2f1067ab752dc7c8a454c209f5d8d74004ef9afb2fcba`.
Independent app export matches vendor objcopy: 207824 bytes, SHA256
`a6a7255775cd871fe8508091c4d4eb5d8ced57d1e4ce50e8a3d3c17372f516ed`.
Link audit: zero failures; manual scheduling item signed off at
`sdk_meky_check 0x0202F18E` (IRQ123 both cores, clear enables, 8000 timer).
RAM entry remains `0x01C01096`, real marker/reset function `0x02001D36`,
P33 reset `0x01C0106E`. No extra hardware or clock/supply change.

Independent cipher/CRC/factory-cfg checks pass for private full-image SHA256
`79e0cc9bb394415f544f2e9a33ea8e6cfab2ae70120ca9590b1eb32c1d629789`.
App end `0x36CF0`; exactly 51 sectors `0x4000..0x36000` change. A separate
FM6 plan admits that hash/range; older plans retain their smaller limits.
Actual-image install/exact factory restore models pass; interrupted-page
recovery passes both at page 7 and page 663 (inside the additional range),
with metadata untouched until last. This image is not installed. First validate
current control-v2 boot, PING, analog level and automatic ROM entry.

91 focused host tests pass after the separate FM6 admission, including the
new boundary-isolation test. These remain offline checks, not FM6 target data.

## Control-v2 boot and autonomous ROM entry

[verified: 2026-10-24 07:26–07:30 UTC, live UART/USB and private KA6 capture]
Owner pressed normal Reset. UART reports the command receiver ready on PA5
at 1 Mbaud. DAC registers read `DAA_CON1=00042108` and both digital volume
registers `00003E30`, confirming the intended analog gain 8 and digital 15920.
At 103403 callbacks, invalid buffers, fill overruns and IRQ overruns remain
zero; maximum fill 401 ticks and full IRQ 513 ticks of the 24 MHz timer.
These are reference-tone measurements, not instrument acceptance.

A fresh 30-second KA6 capture has channels 1/2 RMS −52.34/−52.15 dBFS,
about 8 dB above v3, with no clipping. The 28-second post-startup screening
still flags 779/786 irregular periods. This does not establish whether the
cause is DAC/routing distortion, capture noise or actual discontinuities;
the analog reference path is not accepted. Private evidence prefix:
`/home/claude/fm1-devkit-captures/audio-control-v2-running-20261024`.

The exclusive receive-only UART capture was deliberately stopped before TX.
Default host-tool PING was acknowledged. The separately invoked ARM/ENTER
handshake was acknowledged, followed by fresh `3-1.2` USB device 96,
`4C4A:8057`; kernel SCSI inquiry identifies `WL82 UBOOT1.00`, `/dev/sg0`.
One initial USB descriptor read returned −71 before successful enumeration.
No owner button press was used for this entry. The acknowledgment alone was
not treated as proof: actual USB enumeration was checked separately.
Private entry log: `audio-control-v2-automatic-entry-20261024.log` in the
same captures directory. This proves application-assisted ROM entry while
the command task runs; it is not recovery from an unresponsive application
or proof of an automatic return from the RAM loader to application execution.

## FM6 install and automatic test-cycle requirement

[verified: bench receipts] Factory restore after automatic entry verified
SHA `127b2ebb...`; FM6-control-v1 installation verified the complete 8 MiB
SHA `79e0cc9bb394415f544f2e9a33ea8e6cfab2ae70120ca9590b1eb32c1d629789`.
Receipts: `restore-control-v2-before-fm6-control-v1-20261024` and
`install-fm6-control-v1-20261024` under the private bench backup directory.
Receive-only capture `fm6-control-v1-firstboot-20261024-uart.bin` armed at
07:34:07 UTC. After the owner reported Reset, capture was still empty and
USB device 96 remained present; no FM6 boot/timing result is claimed.

Owner instruction, 2026-10-24: future dev-board test cycles must not require
physical button presses. Application UART entry is proven; automate and
verify the loader-to-application transition too. Do not ask for repeated
buttons as the routine test procedure. This applies to the dev board, not
the physical FM-1.

[verified: actual fixed binary] Independently decoded the exact fixed loader
`fe6d1bd3...` and verified decoded SHA
`a228c6fa2dd733802723099dab8216edbfbdfcef1dc155ffcd8ac2b96fd480af`.
Its dispatch `0x01C042C6..0x01C042CE`, FC0C handler
`0x01C0477C..0x01C047EA`, call `0x01C04B6E..0x01C04B72` and reset routine
`0x01C0292C..0x01C02936` have byte-identical span hashes to the private
2026-10-11 fixed-loader native review. The default FC0C argument-1 path
requests core reset via bit 4 at `0x10000`; it does not establish application
boot, nor clear the P33 download marker on its traced direct path.
Private comparison: `scratch/devkit-20261023/loader-fixed-reset-span-check.json`.

Added a separate dev-kit adapter, `tools/devkit_loader_reset.py`, without
expanding backup or flash transaction command allowlists. It accepts a pinned
diagnostic plus matching complete installation receipt/readback, re-reads the
entire live 8 MiB flash, then permits only literal
`FC0C00000001FFFFFFFFFFFFFFFFFFFF`. One attempt is consumed per installation;
disconnect or bad response is recorded without retry or a boot-success claim.
The coordinator must continue its known fixed-loader session on the observed
USB connection. No loader upload, arbitrary command, flash mutation or eFuse
operation is available. 26 focused reset/control/transaction tests pass,
including all-opcode rejection, mismatched live flash/identity, disconnection
and invalid acknowledgment. Physical loader-exit behavior is still pending.

### Software return and FM6 results

[verified: 2026-10-24 07:39 UTC] Complete pre-reset flash readback matched
FM6-control-v1. The one FC0C request interrupted its own USB transfer
(`host=7`, residue 16); the adapter correctly recorded ambiguous transport
completion without retry. Independent UART then captured a fresh `SOFT`
boot, receiver readiness, all twelve cases and `complete=1`. USB download
enumeration disappeared. Thus software application return is demonstrated
on this dev kit despite the interrupted command response. Raw evidence:
`fm6-control-v1-firstboot-20261024-uart.bin` in the private bench captures;
reset evidence: `reset-fm6-control-v1-20261024` in the private backups.
Routine test cycles now use application UART entry and reviewed USB loader
return; no further physical button operation is required for this path.
Recovery from an unresponsive app remains a separate limitation.

All twelve hashes match the real desktop FM6 fixture, with zero nonfinite
samples. Each case uses 256 blocks; instance size is 20288 bytes. At the
measured 24 MHz timer, the 64-frame/44.1 kHz budget is 1451.25 microseconds.

| Patch | Voices | Mean render µs | Maximum render µs |
| --- | ---: | ---: | ---: |
| Tine EP | 1 | 108.9 | 309.5 |
| Tine EP | 4 | 405.0 | 849.6 |
| Tine EP | 8 | 866.6 | 1660.1 |
| Tine EP | 12 | 1642.7 | 2909.8 |
| Warm pad | 1 | 124.2 | 158.2 |
| Warm pad | 4 | 520.2 | 651.2 |
| Warm pad | 8 | 1287.7 | 1527.8 |
| Warm pad | 12 | 2409.0 | 2731.5 |
| Saw lead | 1 | 97.8 | 206.8 |
| Saw lead | 4 | 383.0 | 604.0 |
| Saw lead | 8 | 880.2 | 1369.1 |
| Saw lead | 12 | 1725.6 | 2509.8 |

These are isolated, IRQ-enabled XIP renders without DAC, effects or mixer.
Every twelve-voice case already exceeds the budget on average. Tine EP and
warm-pad eight-voice maxima exceed it too. Whole-case note-on costs range
1167–4871 ticks and note-off 274–1173 ticks; rendering dominates here.
The largest rendering samples include cold calls and interrupt time; this
does not attribute every spike to cache misses. 98 focused tests pass.

Next controlled comparison: optional `--fm6-ram` places only the same FM6
translation units' code/constants in the existing startup-copied
`.ram0_data`. Source, flags, clock, workload, state and other diagnostics stay
unchanged. External SDK/libc callees can remain XIP. Default placement remains
XIP. Actual ELF placement/copy ranges, link audit, matching hashes and private
image admission are required before treating this as a target optimization.
No RAM-comparison image is installed yet. Rarefaction still rejects the
outside-root worktree query; Serena verifies the correct worktree symbols.

### SRAM comparison image reviewed

[verified] The comparison SDK build places all 69 identified FM6 functions
in SRAM and the FM6 vtable at `0x01c04714`; `.ram0_data` is 54928 bytes,
`.ram0_bss` 85868 bytes. Existing startup copy bounds cover the relocated code.
Only the preparation script differs among recorded XIP/RAM source inputs.
External SDK/libc callees may remain in flash. ELF SHA-256:
`a1d78c19887513dfb7f48241caffa52c920e041555287a86a99ea538e3c493a3`.
Vendor listing SHA-256:
`12e2c9387f1e58d6e3a6f77d40110ee775c1ab30885a8f8b1b930ac52195092e`.
Independent ELF concatenation matches vendor section exports byte-for-byte.
App: 207856 bytes, SHA-256
`edede98fa02ca54b431b30490cac2ed5ee21d308f7c7173aa50a003c6bee9fe7`.
Link audit has zero failures; the scheduling item was reviewed in the actual
vendor listing (`sdk_meky_check` at `0x02024782`, unchanged IRQ123 and timer).
The RAM UART entry routine still calls the strong marker/reset implementation.

Private full image SHA-256
`80c455edeea61649e21f1c8c625240da3bfcd1d3682aa31914825ee77e72448f`
is admitted with the existing 51-sector FM6 bounds, not broader write access.
Independent package decoding, CRC/config checks and actual-image NOR install,
restore and interruption-at-pages-7/663 restore models pass. All 99 focused
host tests pass. No RAM target timing or live-audio acceptance yet.

Owner instruction recorded: all routine future dev-board tests must use the
verified UART entry and loader software-return cycle without physical buttons.
Keep the command receiver in future images; fresh boot evidence is mandatory.

### SRAM target result — unattended cycle

[verified: 2026-10-24 07:55 UTC] UART entry acknowledged; fresh ROM connection
was `3-1.2`, device 97. Two complete baseline reads matched `79e0cc9b…`.
Factory restore matched `127b2ebb…`; RAM installation and independent pre-reset
read both matched `80c455ed…`. One software reset interrupted its USB reply
(host 7, residue 16); fresh UART application boot, command receiver readiness,
all twelve results and `complete=1` independently confirm success. No physical
buttons were used. Private receipts: `current-fm6-xip-before-ram-20261024`,
`restore-fm6-xip-before-ram-20261024`, `install-fm6-ram-control-v1-20261024`,
`reset-fm6-ram-control-v1-20261024` in the Bench backup directory. Capture:
`fm6-ram-control-v1-firstboot-20261024-uart.bin`; parsed comparison is private.

Every PCM hash still matches the desktop and XIP references; nonfinite counts
are zero. Same 320 MHz CPU, 80 MHz flash clock and 24 MHz measurement timer;
timer check 2372225 ticks / ten OS ticks. These remain isolated renders.

| Patch | Voices | SRAM mean µs | SRAM max µs | Mean speedup vs XIP |
| --- | ---: | ---: | ---: | ---: |
| Tine EP | 1 | 69.9 | 88.0 | 1.56× |
| Tine EP | 4 | 246.7 | 283.0 | 1.64× |
| Tine EP | 8 | 481.3 | 551.7 | 1.80× |
| Tine EP | 12 | 715.1 | 822.4 | 2.30× |
| Warm pad | 1 | 75.4 | 76.8 | 1.65× |
| Warm pad | 4 | 273.9 | 286.5 | 1.90× |
| Warm pad | 8 | 537.0 | 558.5 | 2.40× |
| Warm pad | 12 | 800.0 | 823.9 | 3.01× |
| Saw lead | 1 | 76.2 | 89.0 | 1.28× |
| Saw lead | 4 | 272.6 | 285.4 | 1.41× |
| Saw lead | 8 | 534.7 | 557.1 | 1.65× |
| Saw lead | 12 | 796.6 | 820.4 | 2.17× |

All measured maxima now fit the 1451.25 µs block budget; worst is 56.8%.
The controlled placement change demonstrates a substantial flash-execution
cost for this workload. It does not isolate individual cache behavior or prove
sufficient headroom for four instruments, effects, the mixer and controls.
Next: live FM6 DAC service with note events and explicit buffer/deadline
telemetry, followed by representative full-workload soaks and analog checks.

### Live FM6 playback mode (source/build checkpoint)

Added opt-in `--fm6-audio --fm6-ram --boot-control`. Preparation refuses a
live image without proven SRAM placement or unattended control. It shares the
verified three-window/64-frame internal-DAC transport with the reference tone,
but renders actual FM6 and duplicates stereo onto the four DAC channels. A
quiet fixed -18 dB conversion gain and startup ramp bound the physical output;
nonfinite values become silence and clipping is counted before conversion.
Initialization stays outside the audio IRQ; note/render/conversion work is
inside its measured callback. No callback logging, allocation or sleeping.

The schedule cycles Tine EP, warm pad and saw lead, each at 1/4/8/12 held notes:
six seconds held and two seconds released per case (block-rounded). Release
tails can overlap the next case; the voices field is the requested held chord,
not an engine active-voice measurement. Callback gaps over 1.5 blocks are
counted explicitly as delayed service, not claimed as hardware underruns.

103 focused host tests pass. Real FM6 PCM matches an independent instance
through the DAC bridge, and a bounded mock exercises every schedule transition,
NaN/infinity/clipping guards, initial silence, buffer sentinels and lifecycle.
Both reference and live callback variants pass ASan/UBSan contract tests,
including malformed buffers and injected long gaps. The pinned SDK live build
also passes offline. ELF/pack review and target installation are still pending;
no live FM6 output, effects, or soak acceptance is claimed.

### Live FM6 image review/admission

[verified] SDK ELF SHA-256
`c448a338a3c1db83ea46e1501a1360c6181244dcc244b907a7f88074059b7030`;
actual vendor listing SHA-256
`aff7af2b34a62afb42f2b8b06c284be371a73cb893178ba4dddf919dc3659f5e`.
All 72 identified FM6/bridge functions are in startup-copied SRAM.
`.ram0_data` is 55504 bytes; `.ram0_bss` is 86644 bytes, with no orphan
engine state in SDRAM. Actual app section exports independently match:
216816 bytes, SHA-256
`99cb8165452794586dd95d08743d58631817045c53ca0c72391fc1fd2581b74e`.

Link audit: zero failures, one scheduling item manually reviewed in this
exact vendor listing. `sdk_meky_check` at `0x0202684e` only registers IRQ123
on both cores, clears their enable bits, and schedules `_mkey_check` after
8000. `enter_rom` at `0x01c01096` calls the strong
`nvram_set_boot_state` at `0x0200202e`: 16-byte RAM marker copy followed by
P33 reset, unchanged from the reviewed path. Native DAC IRQ handler calls the
registered refill callback before advancing its software pointer and clearing
the pending interrupt; it exposes no explicit underrun counter on this path.
Callback and full-IRQ timing plus gap/pointer telemetry remain necessary.

Private full image SHA-256
`f9def23ecbd6b5bdaa9861ac2093264cb1c51181f84ffb2ae54a410a4dc96993`:
54 application sectors `0x4000..0x39000`, app end `0x39010`. Independent
reference cipher decode, directory/app CRC and unchanged factory config/boot/
tail checks pass. Exact hash uses its own 54-sector admission; other plans are
unchanged. Actual-image NOR model install and factory restore pass, including
interruptions at pages 7, 663 and 839 followed by exact restore. 23 focused
transaction/reset tests pass after admission; 103 focused tests passed before
this pin. Not installed yet; no live audio or sustained acceptance claimed.
