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
worker. The current Serena connection selects the absolute performance worktree and
finds its actual `fm1_app_render` body at lines 3565 onward [verified,
2026-10-24]. Rarefaction name queries can return the older primary checkout
body; do not use that position as a worktree edit target. Inspect this worktree
and actual SDK/build artifacts for new code and target behavior.
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
interruptions at pages 7, 663 and 839 followed by exact restore. 24 focused
transaction/reset tests pass after admission; 103 focused tests passed before
this pin. Not installed yet; no live audio or sustained acceptance claimed.

### Live v1 rejected; Make flag snapshot corrected

[verified] v1 installed/read back exactly and returned to the app through
software reset, but target UART showed reference-tone timing and no
`LUNAR_LIVE` records. It is **not** a live FM6 result. The worker's mode label
alone was insufficient: target-specific `CFLAGS :=` for `audio_probe.c` took
its snapshot before the global live-mode definition. That object therefore
compiled the reference branch. This supersedes the earlier v1 intent/placement
claims as evidence of actual instrument execution; no soak acceptance is taken.
The v1 exact plan stays available for its factory restore.

Moved the definition before that immediate assignment. Regression tests now
invoke Make on the actual target-specific variable, checking resolved flags,
not merely the presence of a define somewhere in generated text. All 103
focused tests pass after the fix; 24 transaction/reset tests pass after the new
pin. Private v2 NOR install/restore/interruption-at-7/663/823 models pass.

The v2 vendor listing confirms actual calls from `fill` to the RAM live render,
and from DAC startup/status reporting to the live initializer/snapshot. ELF:
`80984957f3ef26bfae6c25f9e4bd3e5f9f87153f4491fc3cb508fe2f972b6f5a`;
listing: `28ddf6508ce12156e2e42a0435ef8dba3da7a58771baac1cc984a01abb243a3c`.
All 72 FM6/bridge functions remain SRAM; data 55504 bytes, BSS 86100 bytes.
App 213456 bytes, independent vendor exports match SHA-256
`7c7cd00346f3f5227f7b10a1adcafbe2092facbae4859331fc41612cd4646a68`.
Audit zero failures; manual scheduling sign-off at `sdk_meky_check=0x02025b1e`
(two IRQ123 registrations and 8000 timer), same strong UART marker/P33 path
(`enter_rom=0x01c01096`, `nvram_set_boot_state=0x02001fd4`).

Private full v2 image SHA-256
`80f7491493b45a5408214f792066f0da390bb282cdf9a103bbbc9920058a1422`;
53 application sectors `0x4000..0x38000`, end `0x382f0`. Independent cipher,
CRC, factory config, boot and tail preservation checks pass. Own exact plan
uses 53 sectors; v1's 54-sector restore plan stays unchanged. Not installed yet.


### Corrected live v2 first physical cycle

[verified] The full automatic sequence completed without physical buttons:
acknowledged UART entry, fresh ROM enumeration, two matching 8 MiB current
reads, byte-identical factory restore, exact v2 installation/readback, another
full pre-reset match, one reviewed software reset, and fresh application UART
boot with actual `LUNAR_LIVE` records. The v2 target is the hash above.

All twelve patch/chord cases completed and the schedule entered its second
cycle. At 118 seconds from boot, 79,963 callbacks had executed: maximum refill
23,639 timer ticks (985.0 us), maximum complete audio IRQ 23,654 ticks
(985.6 us), versus 34,829 ticks / approximately 1451.2 us per block. Callback
and IRQ deadline misses, malformed buffers, gaps above 1.5 blocks, nonfinite
samples and PCM clipping were all zero. This is a bounded first-cycle result,
not sustained or full-project acceptance.

The KA6 receives the changing instrument signal on inputs 1/2. Spot-checked
one-second RMS levels range roughly -64 to -46 dBFS under the deliberately
quiet conversion gain; the quietest cases are close to the capture noise floor.
A clean timing counter does not rule out analog/capture faults. The initial
240-second capture, subsequent long soak, expected-signal comparison and
representative effect/mixer/control workloads remain to be evaluated. Private
receipts/captures are recorded in the durable campaign handoff.

### Long-stream identity instrumentation (not installed)

The initial exploratory analog template comparison is inconclusive. Stronger
single-note segments correlate well, but quieter cases approach the capture
noise floor, and short-fixture identity does not prove a long evolving stream
is identical. Independent capture and DAC clocks also require alignment.
No analog acceptance is inferred from these preliminary correlations.

The next diagnostic latches a FNV-1a fingerprint after each complete case,
over the converted stereo PCM16 stream with explicit little-endian byte order.
Worker telemetry reads only completed hashes; hashing executes inside the
measured callback. The independent real-engine host test now covers the full
first case including release and verifies its exact PCM and fingerprint.
All 103 focused host checks and the pinned SDK build pass. This source change
has not replaced the v2 image or interrupted its active 30-minute soak; exact
ELF/pack review, image admission and new target evidence remain required.


The fingerprint-enabled v3 SDK image has completed offline review. ELF SHA-256
`53372df8e8bc907b64aac873e1540d1ad42ef8d9868316fa89ddadd44e53e0db`,
vendor listing `88cdac3eb89a56c7d89af63f1dabd0949a9b9f23b46a3d2859340c6bb7b12d4b`,
app 213584 bytes, SHA-256
`438ca8ad0174fff301439b1cc303f8687ac175c5c8fb60dbb31a8008915be92a`.
Independent ELF section extraction equals vendor exports. The 84 functions
at/after the live bridge's SRAM entry are the same named set as v2, all inside
startup-copied `.ram0_data` (55600 bytes); `.ram0_bss` is 86116 bytes. The earlier
72-function count was a narrower identified subset, not the entire region.

Link audit has zero failures; the sole scheduling item is signed off in the
actual vendor listing: `sdk_meky_check=0x02025b3e`, two IRQ123 registrations,
enable-bit clears and timer8000 for `_mkey_check` only. UART entry still calls
strong `nvram_set_boot_state=0x02001fe6` from `enter_rom=0x01c01096`, copying
the 16-byte RAM marker then calling the reviewed P33 reset path.

Private image SHA-256
`f7863aad94f993742140161350edd28c0555a348574c9c01f3bdf253a4204ced`,
53 sectors `0x4000..0x38000`, app end `0x38370`. Independent cipher/CRC and
factory boot/config/tail preservation checks pass; exact NOR install/restore
and interrupted-page7/663/823 recovery models pass; 24 transaction/reset tests
pass after admission. Not installed while the v2 soak runs.

Two-cycle desktop replay produces identical PCM with and without fingerprinting
(raw stereo SHA-256 `47b358780463411148681227f8a9505704abb860356cabe942ffca2a4e599a61`,
8467968 frames). Its 24 completed-case fingerprints are retained privately for
comparison with fresh target records. This proves host instrumentation preserves
output; it is not yet evidence of long-stream target identity.


### Completed-case evidence comparison

[verified: host checks] `tools/devkit_pcm_compare.py` is a read-only comparison
of private independent host replay logs and target UART logs. It requires at
least two complete 12-case cycles, rejects missing/corrupt/reordered/conflicting
records, tolerates repeated worker snapshots, and records both input hashes.
Sixteen synthetic fault/CLI checks pass. These checks validate evidence handling,
not actual target PCM identity, analog continuity or the full workload.

[verified: 64-bit host layout experiment] The current simulator `fm1_app_t` is
4,953,360 bytes; its sound/effect arenas alone occupy 4,718,592 bytes. The TFT
state is 116,368 bytes. These are host layout measurements, not pi32v2 ABI sizes.
The header already documents the fixed arenas as a simulator convenience. A
real full-renderer target must provide per-chain storage within actual linked
SRAM limits; calling a separate miniature mixer would not validate the same
sequencer/modulation/effect render path. Preserve this acceptance distinction.


### Live v2 sustained timing and capture checkpoint

[verified, 2026-10-24] The unattended v2 capture ran from 08:33:40.569 to
09:03:40.481 UTC. KA6 ALSA exited 0 with no error in its capture log. The WAV
contains exactly 86,400,000 six-channel PCM32 frames at 48 kHz (1800 seconds).
Private recording SHA-256
`bbe57313b53a2b128916359caef9e897165cf75cc76a8ff6f8ec865a53b6b09d`
matches on bench01, the Mac private scratch copy and Aeon analysis storage.

The UART capture spans boot through the entire soak: 2,086 cumulative audio
records, all twelve cases repeated, 1,437,960 callbacks at the final snapshot.
Maximum refill 23,639 ticks and complete IRQ 23,654 ticks remain below the
34,829-tick deadline; maximum callback-start interval was 35,265 ticks.
Over-budget callback/IRQ, invalid buffers, gaps over 1.5 blocks, nonfinite
output and clipping counters stayed zero throughout. These are timing and
service observations, not a hardware underrun counter or analog acceptance.
The SDK DAC handler exposes no explicit underrun count on this path.

Analog continuity analysis remains open, particularly the quiet cases near
the capture noise floor. This single FM6 workload does not replace the required
representative instrument/effect/mixer/control campaign. After the recording
finished, UART entry was acknowledged and fresh ROM enumeration observed;
two complete current-flash reads both matched the installed v2 image exactly.
The reviewed v3 fingerprint image subsequently passed the same
factory-restore/full-readback cycle, without physical buttons (below).


### Live v3 target long-stream comparison

[verified, 2026-10-24] The complete v2-to-factory restore, v3 install and
pre-reset read each passed their full 8 MiB checks. One reviewed software reset
returned to a fresh SOFT UART boot with the new image's RAM layout, without
physical buttons. The target's first 24 completed case fingerprints match the
independent desktop replay exactly: two full cycles, no missing, conflicting,
reordered or mismatched records. Six later completed cases were present in that
snapshot and explicitly outside the 24-case comparison.

The compared private UART snapshot SHA-256 is
`c011a81b0dc2a4adcf316acf6daa94e465b6213152267f4fd1cdb3ac49d523a4`;
reference log SHA-256
`c528a9da0241955a0f063687ebaf2445f804e39d05525b418bdb1b64d6b0fd1b`.
FNV hashes provide a diagnostic consistency check, not cryptographic proof.
The measured maximum complete IRQ, including fingerprinting, is 23,747 ticks
(989.5 us), still below 34,829 ticks. Reported deadline, invalid-buffer, long-gap,
nonfinite and clipping counts remain zero.

The six-minute v3 KA6 capture completed with exit 0/no ALSA error and exactly
17,280,000 six-channel PCM32 frames at 48 kHz. Its private SHA-256
`a10e762428f4949e1d83dbcfe22b0c9e6dd0fe7fc4df87275ba0c16a8d57011a`
matches bench01, Mac and Aeon copies. These results establish generated-stream
consistency for this schedule; DAC/analog continuity, representative full
renderer/effect/control workloads and FM-1 transfer remain unaccepted.

### Analog alignment correction

[verified, 2026-10-24] A wider private capture/reference search found a strong
two-second match at reference time 40 seconds and capture time 91.334 seconds
near a DAC rate of 44,118 Hz (absolute correlation 0.930). The inferred start
offset is 51.350 seconds. Earlier searches centered on a guessed 53-second
offset excluded this match; their low correlations must not be interpreted as
DAC faults. Independent DAC and capture clocks require rate correction too.

An exploratory SciPy polyphase comparison using the corrected alignment finds
strong matches in louder passages across both reference cycles (absolute
short-window correlations roughly 0.79–0.99). Quiet decays remain near the
recording noise floor and inconclusive. Periodic signals can produce ambiguous
local offsets; these exploratory measurements have not been validated against
injected faults and do not certify analog continuity or dropout-free playback.

### Compact shared-app storage preparation

[verified, 2026-10-24] The optional external-arena app layout removes exactly
4,718,592 bytes of simulator reserves. Native 64-bit app sizes are 4,953,360
bytes with reserves and 234,768 without them. These are not pi32v2 ABI sizes.
The actual shared renderer matches samples across both layouts while playing
two sound instances, a sequencer pattern, one insert and both master effects,
with note, mixer-level and effect-parameter changes. Storage validation and
guard bytes pass; a project save/load preserves host-owned arenas.

Aeon Ubuntu 24.04 native regression: 214 tests pass (`test_sim_arenas.py` and
`test_sim_web.py`). Both arena layouts also pass Clang AddressSanitizer and
UndefinedBehaviorSanitizer. The browser module was rebuilt: all 108 parity
scenarios pass, identical to the JavaScript/Wasm reference and musl native
reference. The 30-second editor storm reports zero late quanta; build-record
source/hash validation passes. These are host/browser results.

The actual vendor pi32v2 compiler also compiles the external-arena shared app
at `-O2 -ffp-contract=off` against the pinned SDK headers. A compile-only
constant probe in its ELF32-pi32v2 object reports: app 232,704 bytes, TFT
116,368 bytes, unit 160 bytes and pointers 4 bytes. This confirms target
layout and compilation, not linked SRAM fit, execution timing or an ABI-safe
device image. Full link/audit, bounded target installation and representative
analog soaks remain required.

### Shared-renderer workload integration, 2026-10-24

[verified] `firmware/devkit/renderer_live.c` now drives the actual `fm1_app_render`
path with four sound slots (FM6 electric piano, Macro VA, Drums, FM6 pad), four
running sequencer tracks, default modulation plus LFO/ENV parameter cables,
Filter/Drive inserts, Echo/Compressor master slots, mixer edits and filter edits.
All initialization and script parsing happen before rendering. A fixed
148 KiB caller-owned pool binds the engines by their actual instance sizes;
missing modules or insufficient capacity refuse the entire workload.

[verified] On the Aeon Ubuntu 24.04 native replay the chain uses 147,808 bytes
of that pool at 44,100 Hz. Two complete four-case cycles (1/4/8/12 additional
FM6 held notes, six seconds held/two released per case, block rounded) completed
44,104 render blocks and 1,492 note/control operations with no nonfinite samples
or PCM clipping. This is a deterministic integrity/reference workload, not a
musical demo or hardware acceptance result. Release tails and sequencer notes
remain active between cases. The sound slots and effects are not replaced by
test oscillators or gain stubs.

[verified] All 87 objects selected by `tools/jieli/renderer.mk` compiled with
the actual pi32v2 compiler and pinned SDK headers. This includes the modulation
script reader used during setup. Rarefaction still resolves the old primary
checkout, so its stale `fm1_app_render` result was not treated as worktree
coverage; Serena found the current renderer at line 3603. Full SDK linkage,
SRAM/stack/hot-code placement, device timing, analog comparisons and sustained
full-renderer soaks are still pending. No device commands were sent for these
checks; the previous FM6-only diagnostic remains installed.

### Shared renderer SDK/DAC link, 2026-10-24

[verified] The shared-renderer replay also passes Clang ASan/UBSan (two tests).
The DAC transport harness now tests tone, FM6 and shared-renderer modes. Together
with the SDK-preparation tests, 24 tests pass, including Make evaluation of the
callback's effective mode flags and mandatory UART boot-control flag.

[verified] The new offline-only `prepare-renderer-devkit.py` prepares the pinned
private SDK with the shared renderer, actual internal-DAC callback and UART
receiver. A clean prepared build links all 87 renderer objects with the actual
pi32v2 compiler/SDK LTO. Its private ELF SHA-256 is
`c8d9b9748fd5aaba6aabde8187b753a179d8b0dbc96045aa43a8579f00ca8c6c`.
The map reports XIP `.text` 0x84820 bytes, internal `.ram0_data` 0x2cf0 and
`.ram0_bss` 0x62b94; SDRAM `.data` and `.bss` are zero. Remaining linker-region
capacity is not a proven runtime stack or hot-code budget.

The first non-LTO experiment failed because otherwise unreachable desktop
persistence buffers remained linked. SDK-compatible LTO removes these without
changing the shared renderer. A nested-Make prerequisite omission was also
fixed before the clean prepared build. Neither failure involved device traffic.

Full-renderer execution is still pending. Before installation, establish a
bounded timing/liveness test that preserves unattended UART recovery even if
the XIP renderer exceeds the DAC deadline; review actual stack and interrupt
behavior, then complete link/image audits and exact-image admission. Target
PCM comparison, analog fault-validation and full-workload 30-minute soaks remain
required. The previously measured FM6-only image is still installed. No new
hardware performance or dropout-free claim follows from this successful link.

### Worker-context preflight and stack review, 2026-10-24

[verified] The vendor disassembly of the shared SDK/DAC link reserves 6,224
local stack bytes in `fm1_mod_ui_commit` and 4,284 in `fm1_mod_script_apply`,
before saved registers and callees. These are separate frames, not an assertion
that they are nested. The linked CPU0 interrupt stack is 4 KiB. A successful
link therefore does not establish that the app's UI/setup/render call chains
are safe in that interrupt context. No full-renderer image has been installed.

The preparer now provides a 20 KiB worker stack (the SDK documents four-byte
stack units). Its `--timing-only` mode starts the UART receiver, runs the same
full four-case schedule in the worker, yields every 16 blocks, and reports
render/conversion/control/fingerprint timings with stack high-water words.
This preflight does not enable the DAC and cannot prove output continuity.
The host timing-controller test injects timer wrap and late renders and checks
all case counts, totals, scheduling yields and invalid-callback refusal.

[verified] All 28 focused renderer/DAC/SDK-preparation tests pass on Aeon.
The actual pinned SDK links the worker timing build with stack reporting:
private ELF SHA-256
`3da7e539f19c0c94d97cabc924b231c1b092232e230fc2dfc91777fcdd3c8ccc`,
XIP `.text` 0x830a0, `.ram0_data` 0x2cf0 and `.ram0_bss` 0x62ad4, zero SDRAM
`.data`/`.bss`. Task stacks consume the remaining heap at runtime. Target stack
measurements and timing results remain pending exact-image review/admission.

[verified] The worker preflight candidate is now separately admitted by exact
SHA-256 `b8305c69d6ce8ccfe7dabe52f08553369dcaced81b47e7d75d61860d5494bfa3`:
134 application sectors `[0x4000,0x8a000)`, application end 0x89ed0. Independent
reference-cipher decode and all directory/application CRCs match; boot bytes,
configuration and the entire tail after the new app remain factory-identical.
The exact-image NOR model passes install, restore and injected page interruptions
7, 1079 and 2119 followed by exact factory restores; metadata is installed last.
The vendor scheduling review confirms only the two dormant IRQ123 registrations
and the 8000 timer, and the linked UART ROM-entry path retains the reviewed RAM
marker/reset sequence. All 25 transaction/reset tests pass. This admission is
for the no-DAC worker image alone; it does not admit the direct-IRQ renderer or
establish target timing/stack acceptance.

## Full-renderer preflight startup fault and unattended recovery (2026-10-24)

[verified] The timing-v2 worker image installed with an exact full 8 MiB
readback and booted through the reviewed loader reset without a button press.
It then raised CPU0 `div0_err` in `sum_slots`, called by `fm1_mod_tick`, before
completing a timing case. Actual vendor LLVM IR moves `max / min` ahead of the
logarithmic branch. A linear range starting at zero consequently divides by
zero even though the source only requests that division for log parameters.
The correction neutralizes a zero denominator; valid log ranges remain
unchanged. All 28 focused tests pass with Linux replay divide-by-zero traps
enabled, including a build permitting speculative floating-point operations.
Target validation of the correction remains pending.

[inferred] Source call paths place `fm1_mod_tick` in sequenced rendering, so
the fault may be in the first render batch rather than initialization itself.
The capture establishes a startup/early-workload fault before a completed
case; it does not identify the exact initialization/render boundary.

[verified] The crashing image prints UART receiver readiness, but ordinary and
startup-timed acknowledged PING attempts received no acknowledgement; no ARM
or ENTER was sent by those failed handshakes. Temporarily reducing the Tigard
receive latency from 16 to 1 ms did not help, and it was restored to 16 ms.
No loader reset was retried. New diagnostics now reserve 200 OS ticks before
workload initialization for an acknowledged UART recovery handshake. This
window is outside measured rendering. Its actual boot/recovery acceptance is
pending; merely creating the receiver first proved insufficient. Current
crash recovery remains unresolved, separately from future routine tests.

[verified] Another 176 modulation tests pass. Corrected timing-v3 links with
ELF SHA-256 `f5df56721ebc452474a1b58da6c6f6fc850ef4d18683d372ec3ef29f4e7bd961`.
Independent vendor section exports exactly match the 548,336-byte application
SHA-256 `e1cfcd5b7cccce8c21ba5fd0725980e28b4ac5bf91958dd40fc5f8e82482ff21`.
The compiled modulation IR retains a zero comparison and a safe selected
denominator before division. Link audit has zero failures; its pending
scheduling item was checked in actual vendor disassembly: `sdk_meky_check` at
0x02082330 contains only two IRQ123 registrations and the 8000 timer.
Independent cipher/CRC checks pass for private candidate SHA-256
`7478c40947fa308a6ffacba32ab1f109632446b0370dafc2183c091421a93b16`,
134 application sectors `[0x4000,0x8a000)`, application end 0x89f10; factory
boot/configuration/tail preservation passes. At this checkpoint the image was
not yet admitted or installed. Current hardware recovery cannot use the receiver while it crashes
before acknowledging PING; an owner recovery exception has been requested.

[verified] The corrected candidate's offline NOR model also passes exact
install/restore and interrupted pages 7, 1079 and 2119 with factory restoration.
Final vendor disassembly retains `enter_rom` at 0x01c01096 calling the strong
RAM-marker/P33-reset implementation at 0x02001d5a. It creates UART control,
calls `os_time_dly(200)` at 0x020207a4, then enters renderer timing. These are
source/link checks, not proof that the new recovery window works on hardware.
No further hardware command was issued; the board still runs the crashing
timing-v2 image.

[verified] A worker scheduling regression now executes the actual worker and
boot-command parser with SDK hardware and time mocked. It simulates an
initialization crash, then a fresh boot receiving PING/ARM/ENTER during the
recovery window before initialization can run again. It passes on macOS and
Linux; all 29 focused renderer/DAC/preparation tests pass on Linux with
`-fno-trapping-math`. Together with the earlier 176 modulation tests this is
205 focused tests. The test replaces only the target `csync` instruction with
a compiler barrier; it does not verify real UART latency or scheduler behavior.

[verified] The exact corrected candidate is now admitted in the transaction
tool with the same 134-sector boundary. Both old and corrected renderer plans
pass protected boot/tail and older-image boundary tests; all 26 transaction
and loader-reset tests pass locally. This is offline admission only: the image
has not been staged to Bench01 or installed. The pending recovery exception
and hardware startup-window acceptance remain required. Rarefaction's current
project index could not resolve `validate_images`; Serena resolved its actual
worktree definition, supplemented by direct caller/test inspection.

## Full-renderer analog detector sensitivity experiment (2026-10-24)

[verified] A fresh desktop replay of the actual shared renderer reproduced all
8 previously recorded fingerprints, 44,104 blocks and 1,492 control changes,
with no invalid/clipped conversions. Its stereo S16LE PCM has 2,822,656 frames,
SHA-256 `c676e9b496a63e3817428ade9c067d75a2fd81bd786da7c0ad06ee6255c4f81b`.
This is a reference for subsequent analog comparison, not target execution.

[verified] The private sensitivity experiment uses maintained SciPy routines
(`resample_poly`, `butter`, `sosfilt`), not a new resampler/filter implementation:
https://docs.scipy.org/doc/scipy/reference/signal.html . NumPy 2.2.6 and SciPy
1.15.3 were installed only into this task's analysis directory in a bounded
Aeon container. No project runtime dependency or host Python was changed.
The experiment converts a stated synthetic DAC rate of 44,118 to 48,000 Hz,
applies a 12 kHz second-order low-pass, gain 0.7, DC 0.01 and seeded -75 dBFS
noise. The comparator applies a 200–4000 Hz band-pass to both signals and fits
one gain per channel across the complete timeline. Alignment is known; it
never independently retimes short windows. This is a hypothetical transfer,
not a measured model of the board or KA6.

[verified] This **fails as an acceptance detector**. Across 240 injections
(zero/held/repeated/skipped output and right-channel loss; 64/128/256 source
frames at 16 positions), 73 were rejected, 57 were missed in active affected
regions, and 110 were inconclusive because the affected region/channel was
below the stated -55 dBFS activity floor. Residual windows were 96 capture
samples (2 ms), with a 50 ms post-fault inspection interval. The threshold
was the largest clean active-window residual plus 6 dB: -7.0589 dB relative
error. Right-channel loss counts activity only on that channel. The earlier
any-channel exploratory count was corrected before this record. A skipped
segment may affect later playback beyond this local inspection interval;
these counts do not establish its full eventual detectability.

[inferred] A loose global residual threshold tolerating unknown analog phase
and filtering can hide actual block defects. Before using matched music as a
gate, independently calibrate the analog transfer/latency/clock and validate
per-channel coverage and held-out injected faults. Quiet/unobservable regions
must remain inconclusive; they cannot support a clean bill of health. Do not
relax a detector until this experiment passes and call it hardware acceptance.
Timing/true underrun evidence and actual KA6 soaks remain separate requirements.

Private task storage on Mac `scratch/devkit-20261023/` and Aeon
`/home/claude/mvave-fm1/devkit-performance-20261022/` contains
`full-renderer-fault-sensitivity.py` (SHA-256
`76a9f0f467bf825aacc646ead6b0a8f711e517adac4e82c17afeea7f7a4cebb8`)
and `full-renderer-fault-sensitivity.json` (SHA-256
`71a4b49c6ce0ce6dbf625b648dad59dba26d415f1e65f3da58377f6f872d7b91`).
Both declare that they do not certify dropout-free output. No board command,
physical reset, UART transmission or new KA6 capture occurred in this experiment.

## Workload liveness and shared browser rebuild (2026-10-24)

[verified] A separate instrumented desktop build confirms that the four
sequencer tracks stay active during the full replay; nonzero PCM was not used
as a substitute for this check. All 63 approximately one-second samples show
transport playing, ticks advancing from 192 to 12,112, and each track playing
clip index 0 with loop cycles advancing from 1 to 32. All 252 route snapshots
match track-to-corresponding-sound routing. Assertions also verify 16-step
clips containing 4/4/4/2 notes, zero sequencer refusal/event-drop/gate-eviction
counters and zero app sequencer drops at each sample. All eight PCM hashes
remain unchanged. Sampling does not prove behavior between samples, IRQ
headroom or analog continuity. This private probe uses its own build directory
and adds no logging or behavior to the admitted device image. Private log
`renderer-seq-observe-assertions.log` SHA-256:
`6d43b0f0573aa98ffe99bc950229cde727a281e45042a47904c365b1fce1ff7a`.

[verified] CI run 40088632637's MIT/BSD and macOS jobs failed solely because
the committed browser module predated the modulation divide guard. Their
actual logs show 4,493 and 5,398 passing tests respectively. The modulation
runtime is included in the browser's strict source hash. The module was
rebuilt with the existing build/parity pipeline on Aeon, bounded to four CPUs
and 8 GiB; its record was not manually edited. All 108 parity scenarios, DX7,
metadata and edit checks pass. The 30-second edit storm reports 10,341 quanta,
82,728 edits and zero late quanta. The refreshed WASM is 1,585,788 bytes,
SHA-256 `857eb29fa1b72cee61d9706eda9b0aef55b6eb83ec6bfc03d28ea00251b9f329`.
The strict build-record test passes locally with `CI=true`, including current
source hashes and the committed module hash. Complete new-head CI remains
required. No device traffic or new physical audio acceptance occurred here.


## Pinned transport pointer protection (2026-10-24)

[verified] Exact-head CI run 40089502568 passed every job except WebKit,
whose compact-toolbar test timed out waiting for Pause to become Resume
at line 29. The earlier WASM build-record failures are resolved. The
unmodified toolbar check and ten additional transport cycles passed on
Aeon; these local passes do not erase the CI failure or establish its cause.

[verified] A deterministic regression exposes a related defect: changing the
workspace width while holding the external pinned transport replaces its
button before click dispatch. Pointer tracking covered only the Song root,
although the transport is mounted outside it. The shared workspace containment
check now covers pointer release, and both surfaces track pointer presses;
external listeners are removed on destruction. The regression fails before
this fix and passes afterward, including exactly one transport callback and
resumption of deferred grid resizing after the click.

[verified] The complete viewport/follow suite passes in WebKit, Chromium and
Firefox in bounded Aeon containers. WebKit's full compact-toolbar check and
10 native MIDI transport checks pass; all 13 sequencer-host unit tests and the
strict browser build-record check pass locally. No timeouts or assertions
were weakened. Rarefaction is rooted in the primary checkout and cannot
inspect this sibling worktree through an escaping project path; Serena resolves
resizeGrids and updateTransport in the actual absolute worktree, with direct
source inspection covering the pointer lifetime. Complete replacement-head CI
is required. This browser repair provides no new dev-board audio acceptance;
no device commands were sent.


## Timing-v3 startup recovery accepted (2026-10-24)

[verified] The owner authorized and performed one physical Update/Reset
exception to recover the crashing timing-v2 image. Two fresh 8 MiB reads
matched the installed timing-v2 hash. Factory restoration and timing-v3
installation each passed complete flash comparisons; the installed v3 SHA-256
is `7478c40947fa308a6ffacba32ab1f109632446b0370dafc2183c091421a93b16`.

[verified] A capture was armed before the single fixed-loader software reset.
On fresh UART readiness, PING, ARM and ENTER were each acknowledged, and
USB independently re-enumerated as `4c4a:8057` with a new device number.
The handshake completed about 94 ms after readiness, inside the reserved
200-tick startup window. Two subsequent complete reads again matched v3.
This proves the startup recovery path on this image before workload execution;
it does not establish rendering performance, stack margin or audio continuity.
Private UART and transaction captures remain outside Git. Routine subsequent
tests retain the owner's no-button requirement.


## Full shared-renderer XIP timing baseline (2026-10-24)

[verified] After the startup-window check, an entirely automatic restore,
install/full-readback and single software-reset cycle ran timing-v3 through
all four cases. All four target PCM hashes match the desktop first cycle:
`6bcab227`, `46c02687`, `1e2f305d`, `5b7dbc03`. Each case rendered 5,513
64-frame blocks. All samples were finite and unclipped; cumulative control
counts were 176/358/548/746. Target engine arenas total 134,944 bytes.

| Held FM6 notes, in addition to sequence | Mean block, microseconds | Maximum, microseconds | Blocks at/over deadline |
| --- | ---: | ---: | ---: |
| 1 | 5835.08 | 6924.46 | 5513/5513 |
| 4 | 6540.08 | 7907.17 | 5513/5513 |
| 8 | 6967.88 | 8383.88 | 5513/5513 |
| 12 | 7676.29 | 9154.08 | 5513/5513 |

[verified] Times divide measured oscillator ticks by 24 ticks/microsecond;
the 64-frame 44.1 kHz budget is about 1451.25 microseconds. The SDK reports
320 MHz CPU, and the timer sanity check reports 2,368,967 ticks over ten OS
ticks. Every case reports 3,760 unused four-byte worker stack words: 15,040
bytes unused, about 5,440 bytes high-water usage from the 20 KiB allocation.
This does not measure the separate interrupt stack or establish its safety.
The run ends `LUNAR_DEVKIT complete=1`; a subsequent ordinary UART PING is
acknowledged. The owned receive-only capture was stopped afterward.

[verified] This is a **failed deadline baseline**, with no DAC output and no
analog acceptance. PCM agreement establishes workload integrity, not timely
playback. Private raw UART SHA-256:
`a30db617c363d77ba1da603738d49bb1d8ac487e858c2c0869fd199194a9c71e`.
Next isolate per-instrument/effect cost and non-engine residual cost before
selecting hot SRAM placement or other implementation changes.

[inferred, rejected probe] Copying engine descriptors to wrap their callbacks
changed PCM in a desktop regression, so that probe was discarded before any
device build/install. Descriptor identity participates in host behavior.
The replacement diagnostic observes existing call sites without replacing
engine descriptors and must pass complete PCM and frame-coverage checks before
any target use. Profile overhead and XIP cache changes preclude treating its
measurements as final audio acceptance.


[verified, offline] The call-site profiler passes 29 focused tests on Aeon,
including the four known PCM hashes, all eight units' complete frame coverage,
unsigned timer wrap and per-case counter resets. SDK preparation refuses
profiling in the DAC build. An initial target link exposed missing profile
flags in the nested make's immediate snapshot; flags now precede that include,
and tests inspect the actual expanded nested flags. The corrected private
profile-v5 SDK ELF links successfully, SHA-256
`f4a347ce53920e3d205ef8d08eb1286bbcfdfcc689a0856b8db42223a668576a`.
It is not yet admitted, installed or hardware accepted.

[verified] The browser was rebuilt because shared source hashes changed.
All 108 parity scenarios pass, as do DX7 and metadata checks. The diagnostic
hooks compile out: the browser module remains byte-identical at SHA-256
`857eb29fa1b72cee61d9706eda9b0aef55b6eb83ec6bfc03d28ea00251b9f329`.
This rebuild's 30-second edit storm reports 10,341 quanta, 82,728 edits and
two late quanta (maximum 3.176 ms); these are measured host scheduling results,
not a new claim of zero-late playback. The build's assertions pass. Exact-head
repository CI and all target/analog acceptance remain separate gates.

[verified, offline] Profile-v1 application is 549,264 bytes; vendor single-section exports match an independent ELF-byte assembly. The exact private 8 MiB candidate is `a6ce75351236f19c2d517841b7392e58e2ca94197c7255352b62a8f672810870`. The linked audit has zero failures; vendor disassembly confirms the two reserved IRQ registrations and 8000-tick SDK timer, UART task creation before the 200-tick delay, and the unchanged reviewed ROM-entry/P33 reset path. Independent cipher/CRC and factory boot/configuration/tail preservation pass. The 135-sector plan spans `[0x4000,0x8b000)` and is separate from prior images. Offline NOR simulation restores exact factory bytes after application-page and final metadata-page interruptions (pages 7, 1079, 2135, 2151). Twenty-seven transaction/reset tests pass, including rejection of that extra sector for every earlier image. This admits the exact image for a UART-controlled profiling experiment; it is not hardware acceptance.


### Actual per-unit profile and first SRAM comparison

[verified] Profile-v1 installed with matching full 8 MiB readback. Its fresh
startup PING/ARM/ENTER handshake completed in about 94 ms and produced a fresh
ROM enumeration before any workload. A subsequent automatic cycle completed
all four cases and all 32 unit rows; all four PCM hashes match the reference.
Every unit covers 352,832 frames per case. Worker high-water usage is 5,400
bytes. An ordinary PING after completion succeeds. No UART/KA6 capture remains
live. No physical buttons were needed for either profiling cycle.

| Held notes | Total mean us | FM6 EP us | Macro VA us | Drums us | Remaining outside unit calls us |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 5860.54 | 928.79 | 1675.83 | 945.33 | 1277.54 |
| 4 | 6564.17 | 1528.83 | 1774.33 | 947.08 | 1278.04 |
| 8 | 6988.04 | 1948.29 | 1771.50 | 948.00 | 1281.92 |
| 12 | 7696.21 | 2663.08 | 1765.29 | 948.08 | 1286.04 |

[verified] The other mean costs at 12 notes are FM6 pad 76.38 us, Filter
280.83 us, Drive 301.04 us, Echo 221.92 us and Compressor 153.54 us. These
are inclusive unit-call times, with instrument callbacks excluding external
note/control handlers and effect calls including host segmentation. The
residual is an arithmetic difference between rounded mean counters; it
includes shared-app work, workload controls/conversion/hash and profiling
overhead, not an isolated sequencer measurement. Every block still misses
its deadline. Private raw UART SHA-256:
`a27e34edf34c09cfbeeea3d382862d52cc54b16cb023f32f924bd94826a278b9`.

[verified, offline] The pinned vendor compiler identifies as clang 4.0.1.
It ignores modern `#pragma clang section`, but a direct IR probe confirms
`#pragma code_seg(".volatile_ram_code")` under the existing MS extensions
flag. An opt-in `--hot-ram` preparation mode prepends only this directive to
private copies of FM6 wrapper/core, Macro wrapper/VA and Drums sources. It
preserves source bodies, LTO/arithmetic flags and XIP constants, and records
original and prepared hashes. It rejects DAC preparation before writing.
Target linking, actual retained-function placement, SRAM headroom, complete
PCM/timing replay and image/recovery review must pass before drawing any
performance conclusion or admitting a new image. No SRAM optimization is yet
installed or hardware accepted.

[verified, offline] The SRAM comparison links and independent vendor section
exports match the 549,264-byte assembled app. Actual vendor disassembly shows
startup copying all 53,488 bytes of `.ram0_data` before app initialization.
FM6, Macro, Drums, msfa compute and VA render functions reside in SRAM. The
heap span is 65,516 bytes before task allocations; runtime headroom remains
a hardware check. Thirty-one focused Linux tests pass with the original four
PCM fingerprints, and 12 local preparation/rejection checks pass.

The exact private candidate is
`b4fc59a4eca97df13d8ac1fc324da69e3f89b7bf82a6fb8daa57aad664739181`.
Independent cipher/CRC, factory boot/config/tail preservation, actual link and
startup/recovery review pass. Its separate hash admission uses the same
135-sector bounds as profile-v1. NOR modeling proves exact install/restore
and recovery after interrupted pages 7, 1079, 2135 and 2151. It is admitted
for the worker timing comparison only; not installed or hardware accepted.

[verified, hardware] The code-only SRAM image completed a fresh startup
recovery handshake in 94 ms and returned to a fresh ROM enumeration. A second
automatic cycle completed all four cases/32 rows with exact reference hashes
and complete frame coverage, zero invalid/clipped samples, and 5,400 bytes
worker stack high-water usage. PING succeeds afterward; captures are stopped.

| Held notes | SRAM mean us | SRAM max us | Mean speedup vs profiled XIP |
| --- | ---: | ---: | ---: |
| 1 | 5361.04 | 6556.38 | 1.093 |
| 4 | 6015.33 | 6948.42 | 1.091 |
| 8 | 6447.88 | 7516.04 | 1.084 |
| 12 | 7163.92 | 8116.71 | 1.074 |

Every block still exceeds the deadline. Private raw SHA-256:
`5efdd101b7de08c27250a945e654d541ce9b0fcd449e98783d66900a5b1ce01b`.
The outside-unit residual remains about 1.16 ms. This is a useful negative
result: code placement alone is insufficient. Actual ELF still places the
8 KiB sine and 8 KiB exp2 tables in XIP. Unlike this experiment, the earlier
isolated FM6 SRAM build moved code and constants and disabled LTO. These
are candidates for separate comparisons, not established causes.

[verified] Exact-head CI at 28a7f62c exposed the previously recorded browser
edit storm's two late quanta (same assertion in Ubuntu and MIT suites). A real
bounded rebuild with the pinned image digests retains identical module/source
hashes, passes all 108 parity cases, DX7 and metadata checks, and measures
zero late quanta/10,341 quanta, maximum 1.030411 ms, edit cost 9.355 us. Both
strict committed-build and existing zero-late tests pass locally. The previous
two-late observation is retained above; this host result does not accept the
dev board's audio. No assertion was weakened.

[verified, offline] A separate `--sine-ram` comparison retains hot code/LTO
and moves only the unchanged 8 KiB FM6 sine table, recording source provenance.
Preparation refuses missing timing/hot-code prerequisites before writing. The
SDK worker reports allocator statistics outside timed blocks, after the UART
recovery window and after cases. An initial link rejected the SDK header's
unprovided `xPortGetFreeHeapSize`; the build now uses exported `malloc_stats`.
Actual sine-v2 ELF `3ef66c06a5d0b5bd440891229ef63cf24192b3ea91c6078e9118d0184e38061e`
places sine at `0x01c0ce4c`, exp2 in XIP, and leaves 57,356 bytes of linker heap
before task allocation. Thirty-four focused Linux tests pass; current local
guard/recovery tests pass too. Independent vendor exports match a 549,616-byte
app. Runtime heap, exact-image review/admission and target acceptance remain
pending; this image is not installed.

[verified, offline] Sine-v1 private candidate
`734b3995171a778e495bfb870e0be695075adf8580a279e944f7da25e743b8a4`
passes independent cipher/CRC and factory boot/config/tail preservation. The
actual sine and exp2 bytes match the prior ELF; startup copies all 61,648 bytes
of ram0_data before initialization. SDK scheduling, strong ROM entry and UART
before-workload delay pass exact vendor disassembly review. The 135-sector
NOR install/restore model recovers after all four injected interruption points.
Exact hash admission is for a worker comparison only; no target result yet.


### UART reservation failure and corrected startup

[verified, hardware] Sine-v1 installed with an exact full 8 MiB readback but
failed its recovery acceptance: the SDK could not allocate the UART task's
4,096-byte stack. It reported 7,444 bytes total free afterward. Total free
space does not establish a contiguous allocation guarantee. No ready marker
or UART commands occurred. The worker incorrectly continued after the failed
receiver creation. All four workload hashes match, but every block still
misses its deadline; these results do not accept the image or its recovery.
The owned verifier is stopped, and no captures remain live. Private raw SHA:
`ed5060c4825ed412ee5682fc99180dc37d71d5f12bc9cdc87684f3806b293886`.

[verified, offline] Preparation now opens/configures UART and reserves its
4 KiB task from app_main before allocating the workload. Any setup/allocation
failure prevents workload creation; worker allocation failure leaves recovery
allocated. The renderer stack is 12 KiB, over twice its measured 5,400-byte
peak. Runtime tests inject UART-open, each configuration and task-allocation
failure, check workload exclusion, and check retained recovery on worker OOM.
Thirty-five focused Linux tests pass, plus 30 transaction/reset checks.

[verified, offline] The actual vendor link confirms all four UART configuration
calls and receiver task creation precede the conditional renderer allocation;
failure branches bypass that allocation. The 200-tick window still precedes
renderer initialization. Independent five-section exports match the app; sine
and exp2 bytes are unchanged. Link audit has zero failures, with the expected
SDK scheduling item manually checked. Independent cipher/CRC and factory
boot/config/tail checks pass. Exact install/restore and four interrupted-page
restores pass in the NOR model. Candidate
`d1d534f71ed6473046d1f23bedd4c39fe8df8a3ef0874f544c82458766324274`
is admitted offline for the recovery preflight only, not installed or accepted.

[verified] After the owner's latest download-mode reply, passive Bench01 USB
enumeration still shows no dev-board ROM device or SCSI generic node. No loader
or new device command was sent. Fresh ROM enumeration is required before
backup/restore/install, followed by actual UART acknowledgement before workload.

### Recovery-first image: target window and workload results

[verified, hardware] The owner performed a fresh physical recovery exception
for the failed sine-v1 receiver. Fresh ROM identity was checked before the
fixed-loader double backup, factory restore and corrected-image install.
Every full 8 MiB readback matched its intended image. Candidate `d1d534f7…`
created the UART task before the renderer; fresh ready, PING, ARM and ENTER
acknowledgements completed in 78 ms. Linux retained USB device number 109 after
reset; a fresh read-only SCSI INQUIRY returned `WL82 / UBOOT1.00`, establishing
ROM responsiveness rather than inferring it from the transport disconnect.

[verified, hardware] After another verified factory restore/install cycle,
one reviewed loader reset started the workload without a button press. All
four cases completed, all four desktop PCM hashes matched, and all 32 profile
rows covered 352,832 frames each. UART PING succeeded after completion. The
12 KiB worker stack peaked at 5,396 bytes, leaving 6,892 bytes unused; reported
heap free stayed 11,092 bytes before initialization and after every case.
Private raw capture SHA:
`d34f1cae3e9038d476bb1b169cab1ebe40d22fd86bd55a3f7078bdf7a03d77f9`.

| FM6 voices | Mean block, us | Maximum block, us | Over deadline |
| --- | ---: | ---: | ---: |
| 1 | 4660.25 | 5612.75 | 5513 / 5513 |
| 4 | 4960.13 | 5756.83 | 5513 / 5513 |
| 8 | 5081.92 | 5749.29 | 5513 / 5513 |
| 12 | 5283.58 | 5989.00 | 5513 / 5513 |

The receiver correction passes this recovery/workload cycle; the renderer
still fails the approximately 1,451 us deadline. There was no DAC or KA6
capture in this timing-only run. Analog acceptance and sustained soaks remain
incomplete. Exact source head `82c74b3d` passed all 13 CI jobs (40159566208)
and Pages (40159566233); PR #155 remains draft and unmerged.

### Separating the unassigned renderer cost

[verified, offline] Six opt-in enclosing stage timers now separate sound
sequencing/mixing, master effects, amplitude modulation, click/limiter,
scope/gain and UI work. Stage totals include nested unit callbacks and must
not be added to unit totals. Host checks preserve all four PCM hashes and
cover every stage/frame, timer wrap and reset. The 65 focused Linux checks
pass. Rarefaction selects the primary checkout, so its app context is older
than this sibling worktree and its named Python lookup is incomplete; Serena
and bounded actual-source reads establish the worktree changes. Neither
index is evidence for pi32v2 code generation.

[verified, offline] The vendor link has zero audit failures; its expected
SDK scheduling item was independently checked in vendor disassembly. Startup
still reserves UART first, gates worker creation on success and delays the
workload for 200 OS ticks. Strong ROM/P33 entry is retained. Independent five
section exports match the 550,352-byte app; sine/exp2 bytes are unchanged.
The heap budget is 56,972 bytes before tasks, 160 bytes below the prior image.
Candidate `e16931a08a7357b4e2cf97adeee9d4628f89a1de8706b5db3c33e4870e3b54f4`
preserves factory boot/config/tail, passes independent cipher/CRC and the
135-sector install/restore model with four interrupted-page recoveries.
Admission is for a timing preflight; it is not installed or target accepted.
The real browser rebuild passes 108 parity scenarios with identical WASM
bytes; profiling hooks remain absent from that ordinary build.

## Stage profiling on hardware, 2026-10-25

[verified] The stage-profiler image completed its UART recovery preflight:
startup readiness followed by PING, ARM and ENTER acknowledgments in 79 ms,
then a responsive UBOOT inquiry. The uninterrupted measurement installation
matched all 8 MiB before its single software reset. No buttons were required.
All four PCM hashes match the desktop, all 32 instrument and 24 stage rows
cover 352,832 frames per case, and the run reports `complete=1`. A subsequent
ordinary PING succeeded. Worker peak stack use is 5,484 bytes of 12 KiB;
free heap remains 10,932 bytes before initialization and after all four cases.

| FM6 voices | Mean render (us) | Maximum (us) | Sound stage (us) | Master FX (us) | UI stage (us) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 4708.38 | 5432.21 | 3976.79 | 369.62 | 283.42 |
| 4 | 5005.42 | 5765.50 | 4268.08 | 370.42 | 288.08 |
| 8 | 5140.21 | 5784.46 | 4403.71 | 371.50 | 285.83 |
| 12 | 5348.79 | 6097.08 | 4614.92 | 371.08 | 284.33 |

[verified] All 5,513 blocks in every case exceed the approximately 1,451 us
budget. Within the sound stage, Macro VA costs 1,474–1,545 us/block and drums
809–813 us/block; filter and drive inserts cost approximately 269 and 289 us.
The sound stage also contains sequencing, modulation and mixing outside these
nested engine measurements. Do not add instrument totals to their enclosing
stage totals. Amplitude modulation costs about 6 us, click/limiting 26 us,
scope/gain 14 us, and work outside the six stages 32–33 us/block. These measured
costs prioritize hot call-path/code-generation investigation; they do not yet
establish which individual operation causes each cost.

[verified] Private raw capture SHA-256 is
`6753391e334966bae22f21ff03b244058ef745031eb30e9c491e1d9846ca3e00`.
The exact candidate is `e16931a0…`, described above. This is worker-only timing
with the DAC off: deadline acceptance fails, and analog/soak acceptance remains
outstanding. PR #155 stays draft.

### Selected Macro model placement correction (offline)

[verified] The workload sets Macro's model parameter to 0, which is
`MODEL_VA_VCF` (VA+Filter), not `MODEL_VIRTUAL_ANALOG` (VA Pair, model 4).
The previous hot-source list moved the latter engine while the actually
selected `VirtualAnalogVCFEngine::Render` remained at `0x02033810` in XIP.
The next comparison adds only the selected engine's source to the private
SRAM preparation list; it preserves the source bodies, flags, workload and
tables. In the new exact ELF its renderer is at `0x01c051ba` in SRAM.

[verified] Private vendor link succeeds: ELF `cf4eec1d…`, application 550,352
bytes `08053855…`, complete candidate `14c60db2…`. Five vendor section exports
match independent ELF extraction. Startup copies 64,016 bytes to SRAM; heap
before tasks is 54,828 bytes, down 2,144. The UART reservation-before-worker,
200-tick recovery window, strong ROM-entry routine and dormant SDK scheduling
were reviewed in the actual vendor disassembly. Link audit has zero failures;
its one scheduling item was manually resolved. FM6 sine/exp2 table bytes match
the installed stage-profiler ELF. Independent cipher/CRC/boot/config/tail checks
and the 135-sector NOR install/restore model, including interrupted pages
7/1079/2135/2151, pass. Local preparation checks pass (29), focused Linux tests
pass (65), and final transaction/reset checks pass (32).

### VA+Filter SRAM comparison on hardware, 2026-10-25

[verified] Candidate `14c60db2…` passed full 8 MiB installation readback,
fresh startup PING/ARM/ENTER acknowledgments in 79 ms, and a subsequent
responsive WL82/UBOOT1.00 inquiry. Both independent flash reads then matched.
The factory restore and second installation each passed full readback before
one fresh software-reset receipt started the uninterrupted measurement.
No buttons were required.

[verified] All four cases completed with the expected PCM hashes, 32 unit
rows, 24 stage rows and 352,832 frames per case. Free heap stayed 8,788 bytes
before initialization and after every case; peak worker stack remained
5,484 bytes of 12 KiB. A post-workload ordinary PING succeeded.

| FM6 voices | Mean render (us) | Maximum (us) | Mean improvement | VA+Filter (us/block) |
| --- | ---: | ---: | ---: | ---: |
| 1 | 4607.29 | 5333.92 | 2.15% | 1413.13 |
| 4 | 4895.21 | 5585.50 | 2.20% | 1480.83 |
| 8 | 5026.13 | 5672.54 | 2.22% | 1474.00 |
| 12 | 5232.21 | 5918.83 | 2.18% | 1479.46 |

[verified] All 5,513 blocks in every case still exceed the approximately
1,451 us deadline. The selected engine placement fixes a real gap but saves
only about 0.10–0.12 ms per complete block. This evidence does not support
code placement alone as the solution. Arithmetic and data-access costs in
the actual hot call paths need further investigation before selecting the
next change. No analog, live-DAC or sustained-soak acceptance is claimed.
Private raw capture SHA-256 is
`5be01a4ac5afafad5737678e5b09533fbe78d92d6e36f569e7e112ee2288b713`.

### Bounded arithmetic diagnostic (offline)

[verified, offline] Profiled timing builds now run four 1,024-iteration kernels
(integer add, float add, float multiply and float divide), eight batches each,
after the acknowledged recovery window and before renderer initialization.
Every batch yields to the OS. Volatile operands prevent constant folding;
inputs stay finite, positive and away from zero/denormals. Results include
raw float bits and per-batch elapsed timer ticks. Loop control, operand loads
and interrupts are included, so these are not instruction-latency claims.
Ordinary audio builds do not call the probe. DSP source and workload are unchanged.

[verified, offline] The host check validates finite arithmetic, fixed work
bounds, rejection of missing callbacks and unsigned timer-wrap accounting.
The focused Linux suite passes 66 tests; local preparation checks pass 25.
The vendor build succeeds and its disassembly retains one native arithmetic
operation per loop iteration with an exact 1,024-trip bound. The four kernels
are in XIP with their volatile operands in initialized SRAM. Target arithmetic
results, the complete renderer replay and recovery on this new image are still
pending; no new hardware image has been admitted or installed by this change.
Rarefaction cannot see the sibling worktree's new worker path; Serena resolves
the actual worker body, and vendor disassembly remains the code-generation check.

[verified, offline] Exact arithmetic candidate `8d67a77a…` (app 550,512 bytes,
`b80f6261…`; ELF `077f05d7…`) is now admitted for the same 135-sector timing
preflight. Independent section exports, cipher/CRC, factory protection and
four interrupted NOR restores pass. Actual startup copies 63,792 bytes;
heap before tasks is 55,052 bytes. Vendor disassembly confirms UART/task
allocation order, 200-tick window before arithmetic, strong ROM/P33 entry,
and dormant SDK scheduling. The arithmetic function table order and initialized
operand bits match source; sine and exp2 tables match the previous candidate.
A final dependency-only relink leaves the ELF byte-identical. All 34 final
arithmetic/admission/reset checks pass. Hardware installation and results
are still pending.

### Arithmetic comparison on target and next table-placement experiment

[verified] Arithmetic candidate `8d67a77a…` completed startup recovery and the
full four-case renderer replay without buttons. Each of four probe results
matches independently rounded binary32 expectations: `00000401`, `40000000`,
`402de298`, `3ebc7241`. Minimum elapsed time per dependent loop iteration was
31.33 ns integer add, 34.46 ns float add/multiply, and 40.73 ns float divide.
These include volatile SRAM loads, loop control and timing overhead; they are
not isolated instruction latencies. This does not support blaming the several
milliseconds of renderer cost on slow basic floating-point operations alone.

[verified] All four PCM hashes, 32 unit rows, 24 stage rows and 352,832 frames
per case match. Mean blocks are 4,612.25 / 4,897.29 / 5,024.46 / 5,224.13 us;
maxima are 5,372.17 / 5,548.79 / 5,674.04 / 5,863.92 us. All 5,513 blocks
in every case miss the deadline. Heap remains 9,012 bytes across all five
readings; worker peak is 5,544 bytes of 12 KiB. Post-workload PING acknowledged.
Private UART SHA-256 is `1bc8adf533d2554bc591c1d4fe100365a1d5aed8769cdbef3033139e50644877`.
No DAC/analog acceptance is implied.

[inferred] Resampler table access is a candidate cost: both selected Mutable
wrappers resample their mixes, and the exact ELF retains two XIP copies of the
same 3,324 bytes of coefficients. An opt-in preparation-only experiment now
replaces those definitions with one external SRAM copy. It preserves every
coefficient literal and DSP operation, requires the existing timing-only hot
code/sine configuration, and cannot prepare a DAC image. Actual ELF placement,
heap budget, output parity and target speed must be checked before claiming
any benefit. Original engine/header sources remain unchanged. Rarefaction
cannot resolve the sibling's preparer; Serena resolves its actual symbol.

[verified, offline] The resampler placement experiment passes 69 focused Linux
checks (9.33 s), 18 local preparation/rejection cases, and the final 35 local
arithmetic/admission/reset checks. Vendor ELF `ec7afbaa…`, app `747ce4a7…`
(550,480 bytes), candidate `a680a4e8…` pass independent section export,
cipher/CRC, factory protection and the 135-sector interrupted-restore model.
The selected Macro/Drums machine code loads coefficients at SRAM `0x01c0d68c`
and `0x01c0e290`; their bytes match the prior image exactly. A separate C
benchmark retains its XIP copy. Sine and exp2 bytes also match. Startup copies
67,088 bytes; heap before tasks is 51,756 bytes, predicting 5,716 after tasks.
UART-before-worker, the recovery window, ROM marker/P33 entry and dormant SDK
schedule were reviewed in exact vendor machine code. Hardware is pending.

[verified] CI run 40163530243 for `67d08ba7…` passed 12 jobs and failed WebKit
at compact-toolbar-check.mjs:29 waiting for Resume after Pause. This is not the
later Stop-to-Play assertion. Five local traced repetitions of the four
transport transitions passed with the same WebKit/PulseAudio configuration;
the cause is not yet established. Passing CI jobs were not rerun. PR155 remains
draft; no merge or hardware audio acceptance.

### Resampler tables in SRAM: target comparison

[verified] Candidate `a680a4e8…` completed the startup PING/ARM/ENTER
handshake and responsive ROM inquiry, two matching full backups, factory
restore, exact reinstall and the full workload without buttons. Four arithmetic
bit patterns, four PCM hashes, 32 unit rows, 24 stage rows and all 352,832
frames per case match. Heap is 5,716 bytes across five readings; peak worker
stack is 5,544 bytes of 12 KiB. Post-workload PING acknowledged.

| FM6 voices | Mean block, us | Maximum, us | Improvement over arithmetic image | Over deadline |
| --- | ---: | ---: | ---: | ---: |
| 1 | 3928.08 | 4594.17 | 14.83% | 5513/5513 |
| 4 | 4209.50 | 4780.96 | 14.04% | 5513/5513 |
| 8 | 4349.46 | 4996.25 | 13.43% | 5513/5513 |
| 12 | 4555.08 | 5180.92 | 12.81% | 5513/5513 |

[verified] This is a useful placement improvement, still a failed deadline
result with the DAC off. Private UART SHA-256 is
`915103f3923b9f24c87468572300b85660f7c40bbfc2f7ae75e3e2ad29924bec`.
No analog/soak acceptance is claimed.

[verified, offline] The prepared pinned SDK link script reserves seven free
data-cache ways as 28 KiB of `cache_ram(rw)` at `0x01f28000`; current ELF
initialized data there is only 32 bytes. Its existing startup-copy section
is `.cache_ram_data`. A new timing-only `--cache-tables` experiment collects
19,708 bytes of unchanged sine, exp2 and shared resampler data in that region,
without changing cache-way allocation or placing executable code there.
Preparation tests preserve all literals and source provenance. Actual vendor
placement, startup copy, capacity, output parity and timing remain pending;
there is no admitted or installed cache-table candidate yet.

[verified, offline] Cache-table preparation passes 72 focused Linux tests
(9.48 s) and 21 local preparation/rejection cases. The actual vendor build
succeeds with downloader disabled. Its exports are saved for independent
section/table/startup analysis; no cache-table image is admitted or installed.
The first test collection caught a syntax error in the extended test call;
it was corrected before the passing runs. Pytest's cache-directory permission
warning did not affect the Linux test execution.

[verified] Exact-head `80144295…` WebKit log shows compact-toolbar-check **passed**.
Its failure is instead initial-view-ui.mjs:122 during the URL-selection case:
`The project changed while checking. Retry the edit.` Chromium and Firefox
passed; the sanitizer job was still running at the last query. Investigation
must preserve the stale-project protection and establish whether the test
starts before native project loading finishes. Private job log saved; no
browser assertion or product behavior has yet been changed for this failure.

[verified] The initial-view test observed the editor selection before its
native panel-follow edit: `openOnPanel` debounces that edit by 120 ms, and
selection updates before it is sent. The URL-selection case now waits for
acknowledged native Home/Sound 1/Page 1, no arpeggiator view, no in-flight edit
and no pending snapshot before its canonical refresh. This strengthens the
ordering condition; no fixed sleep, write retry, expectedHash bypass or product
code change is introduced. Three WebKit runs, one Chromium and one Firefox
run each pass all nine initial-view checks (45 checks) in the same Playwright
1.63.0/PulseAudio null-sink setup. Exact-head CI remains a separate gate.
Rarefaction cannot address this sibling worktree's new JS paths; source
inspection and Serena are used with that limitation.

[verified, offline] Cache-table ELF `fe954286…` and app `d0372bcd…`
(550,476 bytes) match five independently exported sections. The four data
tables match the preceding ELF byte for byte; `.cache_ram_data` is 19,740
bytes including 32 SDK bytes, within the existing 28 KiB region. Startup's
`cache_way_config` retains zero free instruction ways/seven data ways and
copies exactly 19,740 bytes from `0x02081a50` to `0x01f28000` before main.
Ordinary SRAM startup data drops to 55,568 bytes; heap before tasks is 63,276,
predicting 17,236 at runtime. Remaining exact-image review/model/admission
and all hardware checks are still pending.


[verified, offline] Cache candidate `ea83cfdb…` passes independent reference
cipher decoding and all directory/app CRCs, with factory boot, configuration
and tail bytes unchanged. The 135-sector NOR model passes exact installation,
restoration and interrupted-page recovery at 7, 1079, 2135 and 2151. Actual
vendor instructions confirm both renderer coefficient callers and FM6 sine/
exp2 loads use the cache data addresses. UART control allocation (1,024 words)
precedes and gates the worker (3,072 words); its 200-tick recovery delay remains
before probes. Strong ROM entry, 16-byte boot marker and P33 arguments remain
intact. SDK scheduling is reviewed: two IRQ-123 registrations, 8-second timer,
initial unregistered key state and its dormant return; no key provider/blob.
The exact candidate hash is now admitted with the existing fixed sector bounds.
All 36 transaction/reset/arithmetic guard cases pass locally. This is offline
admission only; cache-table hardware timing, heap and recovery remain unverified.


[verified, hardware] Cache-table comparison completed all four cases with
unchanged PCM hashes, all four arithmetic result bits, 32 unit rows and 24
stage rows at 352,832 frames per case. Free heap stays at 17,236 bytes across
five readings, recovering exactly 11,520 bytes; worker peak remains 5,544 bytes
of 12 KiB. Mean block times for 1/4/8/12 FM6 voices are 3,916.75 / 4,183.875 /
4,316.125 / 4,513.083 microseconds; maxima 4,661.875 / 4,793.083 / 5,000.25 /
5,288.458. The mean differs by only 0.29–0.92% from resampler SRAM, insufficient
to establish a meaningful speed gain from this single comparison. Every one
of 5,513 blocks in every case still misses the approximately 1,451-us deadline.
The demonstrable gain is heap headroom, not deadline acceptance.

[verified] Startup ready plus PING/ARM/ENTER completed in 78.6 ms. Fresh ROM
INQUIRY answered WL82/UBOOT1.00; both full 8 MiB reads matched the candidate.
The factory restore and same-image reinstall each passed full readback before
the measurement reset. The receive-only capture completed and was closed by
matching its exact process command line; ordinary post-workload PING succeeds.
Raw capture SHA-256 `704e500cec67067ba2eb9d4a5e7842625c294244bfb10e07b0360cccd10a09c2`
is retained privately. DAC remains off; no analog or soak acceptance is claimed.


[verified, offline] Actual cache-image symbols still place compressor, drive
and echo render paths in XIP. Their linked functions total approximately
11.5 KiB. The next preparation-only `--fx-ram` comparison applies the existing
vendor code-segment pragma to those three source copies, preserving DSP
bodies, constants, flags and workload. It requires timing-only cache-table
placement and retains recovery-first allocation. All 24 local preparation/
rejection cases pass after correcting a test-call syntax error caught during
collection. Vendor placement, remaining heap, exact-image review and hardware
results remain pending; no image has been admitted for this option.


[verified, offline] The fx-v1 vendor build succeeds with downloader disabled.
All 80 focused Linux checks pass. Five vendor section exports independently
match ELF `a29539be…` and app `12264021…` (550,476 bytes). Compressor, drive
and echo render functions are now in startup-copied SRAM; all four resident
tables retain identical bytes. Heap before tasks is 51,756 bytes, predicting
5,716 at runtime. Actual instructions retain recovery-first task allocation,
the 200-tick pre-workload delay, strong ROM entry and the dormant SDK check.
Independent cipher/CRC and protected factory-region checks pass for candidate
`31690344…`; the 135-sector NOR model restores exactly after interruptions at
pages 7, 1079, 2135 and 2151. Its exact hash is admitted for the existing sector
bounds. Hardware timing, heap and startup recovery remain pending.


[verified, hardware] Resident compressor/drive/echo comparison completed all
four cases, four arithmetic results, 32 unit rows and 24 stage rows, with
352,832 frames per case and all PCM hashes unchanged. Invalid/clipped samples
remain zero. Heap stays at 5,716 bytes across five readings; stack peak stays
5,544 bytes of 12 KiB. Mean block times are 3,676.25 / 3,950.917 / 4,069.292 /
4,262.792 us; maxima 4,381.75 / 4,559.958 / 4,714.375 / 5,010.083 us. Means
improve 5.55–6.14% over cache-table placement, but all 5,513 blocks in every
case still miss the approximately 1,451-us deadline. Drive/echo/compressor
means fall to roughly 236 / 167 / 108 us per block. This remains a timing
failure, with DAC off and no analog/soak acceptance.

[verified] Fresh startup ready and three UART acknowledgements took 78.3 ms;
ROM INQUIRY responded WL82/UBOOT1.00. Both full 8 MiB reads matched the new
image, then exact factory restoration and same-image reinstall passed full
readback before measurement. Both one-shot reset receipts are consumed. The
receive-only capture was closed by matching its exact process command line;
post-workload PING succeeds. Raw capture SHA-256
`a9af49de3520cc7eb43ac22893e4d1ecce1c06d0abfbfd7f7f328e9db03d5853`
is retained privately. No physical buttons were used.


[verified, offline preparation] The next optional `--resampler-outline`
comparison changes only two function qualifiers in a private prepared header:
`fm1_resampler_pop` and `fm1_resampler_intermediate_` become noinline. It
requires timing-only resident-effects placement. All arithmetic bodies,
coefficients, rates and sum order remain byte-identical after removing the
qualifier changes and the existing table-declaration transformation. All 27
local preparation/rejection cases pass, as do 84 focused Linux checks. The
vendor build completed with its downloader disabled. Exact generated-code and
image review, target timing and admission remain pending.

[verified, offline] The outlined image's five vendor exports match independent
ELF reads; all four DSP tables match the resident-effects image. Startup copies
66,928 bytes to ram0_data and 19,740 bytes to cache data RAM, with unchanged
zero instruction/seven data cache ways. Heap before tasks is 51,916 bytes
(expected runtime 5,876, not yet measured). Actual UART setup and successful
1,024-word control-task allocation precede the 3,072-word renderer worker; the
200-tick recovery delay remains before arithmetic. Strong ROM entry and P33
arguments remain reviewed. The SDK dormant-check functions match the preceding
reviewed link except for the relocated key-state pointer; its initializer and
dormant return remain unchanged. Link audit has zero failures; its scheduling
item is manually resolved from vendor disassembly.

[verified, offline] Candidate `e988ec53133161065b051f524495c65cfcf7b0c4c0c70ec9bb295bfd4e3ce47b`
contains a 550,316-byte app. Independent reference-cipher decoding and all
directory/app CRCs pass, protected factory bytes are unchanged, and the NOR
model passes exact install/restore plus four interrupted-page restores over
the same 135 sectors. Exact-hash admission does not establish hardware
acceptance; startup recovery must pass before the workload runs.

[verified, hardware] The outlined-resampler comparison completed four cases,
four arithmetic results, all 32 unit/24 stage rows and unchanged PCM hashes.
Heap is stable at 5,876 bytes across five readings; peak stack remains 5,544
bytes of 12 KiB. Means are 3,686.75 / 3,966.917 / 4,087.875 / 4,286.125 us;
maxima 4,506.333 / 4,574.958 / 4,770.667 / 4,926.917 us. Means are 0.29–0.55%
slower than the effects-in-SRAM baseline: no demonstrated speed benefit. All
5,513 blocks in every case still exceed the approximately 1,451-us deadline.
Keep outlining optional as a measured diagnostic; do not select it as an
optimization. DAC remains off; no analog or soak acceptance is implied.

[verified] Startup ready plus all three UART acknowledgements took 78.31 ms,
followed by responsive WL82/UBOOT1.00 ROM INQUIRY and matching full-flash reads.
Exact factory restoration and same-image reinstall passed full readback before
the measurement. Both outline reset receipts are consumed. Receive-only
capture closed by its exact owned process identity, and post-workload PING
acknowledges. Private raw SHA-256:
`49d39b67ad576919536dc3ce998181401d2141a43bb7e981275ec538ccff6675`.
No buttons were used. The later owner approval of the old sine-image recovery
request was a delayed reply to an already-resolved failure; no new physical
recovery was requested or performed.

[inferred, next comparison] Vendor symbols place `FiltProcess` in XIP at
3,300 bytes, within a Filter stage averaging roughly 279 us/block. Whole-filter
placement exceeds available heap headroom. Optional `--filter-process-ram`
wraps only that function in the private SDK source, preserves source bodies,
and requires timing-only resident-effects placement without outlining. All 30
local preparation/rejection cases and 88 focused Linux checks pass; the vendor
build completes with its downloader disabled. Actual code placement, memory
cost, recovery and timing remain unverified.

[verified, offline alternative evaluation] Pinned SpeexDSP
`7a158783df74efe7c2d1c6ee8363c1e695c71226` source and three-clause BSD terms
were inspected. An isolated bounded Aeon container probe of its unmodified
source reports quality-5 output latency 40/40/41 samples at input rates
96k/48k/47,872.34 to 44,118 Hz, versus Lunar's 30. Coefficient storage is
5,664 bytes per stream; 64-bit host allocation payload is 7,144/6,792/6,792
bytes (not a device allocator measurement). It is not a drop-in replacement
under current latency/memory constraints. No speed, spectral or chunking
equivalence is established; no foreign code is integrated. Primary source:
https://github.com/xiph/speexdsp/blob/7a158783df74efe7c2d1c6ee8363c1e695c71226/libspeexdsp/resample.c

### Function-only filter SRAM image: offline admission

[verified] The vendor filter-v1 ELF places `FiltProcess` (3,300 bytes) at
`0x01c05404`; `FilterRender` and `FiltUpdateCoefs` remain in flash. Its five
section exports independently match ELF contents, and all four DSP tables
match the reviewed FX baseline. SRAM code/data is 70,384 bytes, with 48,460
bytes of heap before task allocations; expected remaining heap is 2,420
bytes, pending hardware measurement. UART allocation precedes the worker,
and the 200-tick recovery window remains before arithmetic/renderer work.

[verified] Link audit has zero failures. Its SDK scheduling item was resolved
against vendor disassembly: two IRQ-123 registrations and the 8,000 ms timer.
All three dormant SDK functions match the reviewed FX build after verifying
call destinations and relocated pointers. Protected factory data and
independent cipher/directory/application CRC checks pass. The NOR model
installs/restores 135 sectors, writes metadata last, and restores after four
injected page interruptions. Exact admitted image SHA-256:
`cf5328fc716e97604b415fab49d5ece58b4ef4d05874504e108041de4f6fa9f7`.
Hardware timing, heap measurement, and recovery acceptance are pending;
this is not a demonstrated speed improvement.

### Filter-v1 startup allocation failure; UART recovery retained

[verified] Filter-v1 passed startup PING/ARM/ENTER in 77.43 ms, responsive
ROM inquiry, two exact full reads, factory restore and same-image reinstall.
The measurement boot then failed to allocate the renderer's 12,288-byte
stack. The UART task was already running and acknowledged ROM entry after
the receive-only capture closed; no owner button was needed. No renderer
case ran, so filter-v1 has no PCM, timing or runtime-heap acceptance. Private
UART SHA-256: `6fb79992e017e386d03fc3fca8fddc0eda82c5d78a2d1f852488706c1b8f617f`.

[inferred] Subtracting SRAM growth from a previous post-startup heap reading
did not establish allocation feasibility during startup. Temporary allocations
or fragmentation may matter; their individual contribution is not measured.
The next timing-only filter build reserves an 8,192-byte renderer stack,
2,648 bytes above the previously measured 5,544-byte peak. Other profiles
retain 12 KiB. UART remains first. This budget must pass actual creation
and high-water checks before it can support a performance claim.

[verified] Filter-v2 builds with downloader disabled; 89 focused Linux checks
pass. Independent five-section comparison against reviewed filter-v1 finds
only the stack-size immediate (3,072 to 2,048 words) and build timestamp.
DSP code, tables, UART/recovery, startup copy and SDK-check instructions are
otherwise identical. Cipher/CRC/protected factory checks and the 135-sector
NOR interruption/restore model pass. Exact admitted image SHA-256:
`842758192917d9eeaf877d1117b1e38426063fd432e6f00fa7fe09c507844bd0`.
Hardware allocation, recovery, timing and stack checks remain pending.

### Filter-v2 target timing and stack acceptance

[verified] The 8 KiB renderer stack allocates successfully. Four cases
complete with all four arithmetic bit patterns and PCM hashes unchanged,
32 unit and 24 stage rows covering 352,832 frames per case, and zero
invalid/clipped samples. Heap remains 6,516 bytes across five readings.
Peak stack use is 5,544 bytes in every case, leaving 2,648 bytes. Ordinary
post-run PING acknowledges. No physical button was needed for recovery or
measurement; full backup/restore/reinstall/readback checks passed.

| FM6 voices | Mean render (us) | Maximum (us) | Filter (us) | Mean reduction versus FX |
| --- | ---: | ---: | ---: | ---: |
| 1 | 3620.25 | 4376.29 | 245.54 | 1.52% |
| 4 | 3898.63 | 4489.50 | 238.88 | 1.32% |
| 8 | 4023.46 | 4702.96 | 238.54 | 1.13% |
| 12 | 4215.13 | 4962.46 | 239.04 | 1.12% |

[verified] The filter's own measured mean improves 14.0–15.0%. Every one
of the 5,513 blocks in every case still exceeds the approximately 1,451 us
deadline. This worker-only, DAC-off run is not dropout-free audio acceptance.
No KA6 analog soak was attempted. Private raw capture SHA-256:
`5e7d1b9f76385ccb52ccd91dd781b9ee4cbfd28f1c9d5734ecc56986a995d23d`.
The installed exact image is `84275819…`; PR #155 remains draft and unmerged.


### Control-path placement comparison, preparation only

[verified, offline] The filter-v2 symbol map leaves the outer render,
sequencer dispatch and modulation tick in XIP. An optional `--control-ram`
comparison relocates four named definitions in private prepared sources,
without changing bodies or the workload. Its 136 KiB pool is a 32-bit budget;
64-bit replay correctly refuses initialization at that capacity. Default
profiles retain 148 KiB. The new receipt reports the actual selected worker
stack bytes rather than an unconditional 12 KiB.

[verified, offline] Vendor build completes with downloader disabled. The
four selected symbols reside in ram0_data; initialized SRAM is 74,832 bytes,
BSS 392,408 bytes, and pre-task heap 56,300 bytes. Link audit reports zero
failures, with SDK scheduling review pending. 33 local preparation/rejection
checks pass; 92 focused Linux checks pass, with the reduced-pool replay
skipped in the image without multilib. A separate bounded multilib replay passes the full eight-case schedule
and deterministic PCM comparison with the 136 KiB pool. No candidate is
admitted or installed; the board remains healthy
idle filter-v2. No performance improvement or audio acceptance is claimed.


[verified, offline admission] Control-v1 independent five-section ELF/flat
comparison, all retained DSP table copies, and cipher/directory/app CRC checks
pass. Protected factory regions remain byte-identical. The NOR model installs
and restores 135 sectors, metadata last, and restores after interruptions at
pages 7/1079/2135/2151. SDK scheduling and three linked SDK functions match
the reviewed filter build after checked symbol/call relocations. UART is
configured and its 1,024-word task created before the guarded 2,048-word
worker; the 200-tick recovery wait precedes renderer work. SRAM/cache startup
copies and the strong ROM marker/P33 path were reviewed in vendor disassembly.
Exact admitted image: `bb3cc21d3fdc9fa0a0920334920845a6795e7726086a3638dbf1f4e20df3f759`.
This permits its bounded recovery rehearsal, not a hardware performance claim.


### Control-path SRAM comparison — hardware result

[verified, dev board] Exact image `bb3cc21d…` passes the UART-only
startup recovery rehearsal: fresh ready and three acknowledgements in 78.24 ms,
responsive WL82 / UBOOT1.00 inquiry, two matching full 8 MiB reads, exact
factory restore, same-image reinstall and full readback. Both one-shot reset
receipts are consumed. No physical button was required.

[verified, timing only] All four cases complete with the expected arithmetic
patterns and PCM hashes `6bcab227`, `46c02687`, `1e2f305d`, `5b7dbc03`;
32 unit rows and 24 stage rows each account for 352,832 frames per case.
Invalid and clipped counts are zero. The 136 KiB pool uses 134,944 bytes.
Free heap stays at 14,356 bytes across five readings. Peak worker stack usage
is 5,544 of 8,192 bytes, leaving 2,648 bytes. Capture closed before an ordinary
post-run PING, which acknowledges.

| Case | Mean block us | Maximum us | Mean reduction from filter-v2 |
| --- | ---: | ---: | ---: |
| 0 | 3431.083 | 4138.917 | 5.23% |
| 1 | 3710.125 | 4309.292 | 4.84% |
| 2 | 3839.875 | 4577.167 | 4.56% |
| 3 | 4032.542 | 4828.167 | 4.33% |

Every one of 5,513 blocks in every case still exceeds the approximately
1,451 us deadline. The DAC is off: this is neither analog nor dropout-free
acceptance. The result supports retaining the optional control placement
comparison, not merging the unfinished campaign. Raw UART stays private;
SHA256 `e3222a68fca7547f0e44c22464200d911558789e8fcabe55808a22d519737589`.


### Plaits table cache comparison — offline preparation

[verified, source] Macro/drums use stmlib's pitch-ratio tables; the drum sine
oscillators use Plaits' sine table. Control-v1 retains these tables in XIP.
The optional `--plaits-cache` comparison annotates only those three private
definitions for the existing initialized cache-data section. Preparation
tests verify exact file equality apart from the selected annotations.

[verified, offline] 37 local preparation/rejection tests and 95 focused Linux
tests pass; one multilib-dependent replay is skipped in that Linux image.
Vendor build succeeds with downloader disabled. Independent ELF/export
packing and retained table-byte comparisons pass. All three selected tables
reside in cache RAM; total initialized cache data is 24,360 bytes. Linked
pre-task heap is 56,620 bytes. No image is admitted or installed yet;
startup copy and exact-image recovery review remain required.

Rarefaction's primary checkout lacks the worktree-only preparer, and rejects
a project path outside its workspace root. Serena locates the actual worktree
preparer; bounded source checks cover this edit. Its C navigation verifies
`NoteToFrequency`, but misses its known callers under fallback include flags.
The source and vendor ELF/disassembly remain necessary for this target.


[verified, offline admission] Plaits-cache-v1 exact image
`1e1068c7a99071d44b1d4400d41e1ab8027feee5b8b6222f7f8adbae74e07dcb`
passes independent cipher/directory/app/config CRC checks and protected factory
region equality. The NOR model installs/restores 135 sectors with metadata last
and restores after interrupted pages 7/1079/2135/2151. No device commands were
used for that model. The linked startup copies 74,512 SRAM bytes and 24,360
cache-data bytes; the latter fits the SDK's **28 KiB usable allocation**,
leaving 4,312 bytes. Cache-way configuration is unchanged. UART configuration
and its 1,024-word task precede the guarded 2,048-word renderer worker; its
200-tick recovery window precedes renderer work. Strong ROM marker/P33 entry
remains linked. SDK scheduling is two IRQ-123 registrations plus the 8,000 ms
check timer; its three functions match control-v1 after verified symbol
relocations. Audit reports zero failures; the scheduling pending item is
resolved by this vendor-instruction review. No eFuse access or weak entry
fallback is present. Admission permits the bounded recovery rehearsal;
hardware allocation, timing and analog acceptance remain unverified.


### Plaits table cache comparison — target result

[verified, timing only] The admitted image completes startup recovery with
three UART acknowledgements in 78.58 ms, fresh WL82 / UBOOT1.00 inquiry, two
matching full reads, exact factory restore, same-image reinstall and full
readback. Both unique reset receipts are consumed. No button was required.
All four arithmetic patterns and PCM hashes match control-v1; 32 unit and
24 stage rows cover 352,832 frames per case. Invalid/clipped counts are zero.
Free heap stays at 14,676 bytes; peak stack remains 5,544 of 8,192 bytes.
Capture was closed before a successful ordinary post-run PING.

| Case | Mean block us | Maximum us | Mean reduction from control-v1 |
| --- | ---: | ---: | ---: |
| 0 | 3415.792 | 4139.667 | 0.446% |
| 1 | 3700.167 | 4369.250 | 0.268% |
| 2 | 3828.250 | 4547.042 | 0.303% |
| 3 | 4023.458 | 4816.417 | 0.225% |

Every block in every case still exceeds the approximately 1,451 us deadline.
The small mean change does not establish an audible improvement. DAC output
remains off; no analog or sustained-soak acceptance is claimed. Raw UART is
private, SHA256 `38613e5573d14c61a2bbd1be5d15549e780d0abdbea319cc6badee239c0ea459`.

[verified, offline only] An independent exhaustive float32 experiment checks
all 768 kernel intervals and all 65,536 phase fractions: pre-scaling each
rounded coefficient difference by 2^-16 gives identical interpolation bits
for all 50,331,648 inputs. This supports a private optional comparison, not
vendor-compiler equivalence or target performance. Rarefaction and Serena
locate the same tap body; Rarefaction finds intermediate/pop callers and
resampler_test.cc co-change history under fallback compiler flags.


### Pre-scaled resampler kernel — offline comparison

[verified, source/tests] Optional `--resampler-slopes` is restricted to the
timing-only Plaits cache profile. Private preparation replaces 769 kernel
values with 768 base/slope pairs; the slope is the rounded float32 adjacent
difference multiplied by 2^-16. Original base literals are preserved and
nine-digit slope literals round-trip exactly. The hot tap drops its scale
multiply and subtraction; the FIR, accumulation order, workload and pool
are unchanged. Ordinary production sources are unchanged.

42 local focused preparation/rejection/coefficient/stream cases pass. The
stream comparison checks 16,384 outputs each at five supported rate pairs,
with uneven input/output chunks. The bounded Linux run passes 101 focused
checks and skips one multilib-dependent 136 KiB replay. Vendor build passes
with downloader disabled. Exact ELF/startup/table/code-generation review,
image admission, actual target timing and analog acceptance remain pending.


[verified, offline admission] Exact slopes-v1 image
`7f1d2286a353084c681258556294b8309d3121fc66c301f80832c98b455f6d34`
contains app `4bba133693b7adabbe1ce23fd3bd0020054269adbd6903ac9151b7068ac49d6a`
(553,140 bytes). Independent ELF/export packing, cipher/directory/app/config
CRC and protected factory equality pass. The NOR model checks 136 sectors
with metadata last and restores after interrupted pages 7/1095/2151/2167.
This image alone extends the allow-list to sector 0x8b000.

Vendor pair bytes independently match values derived from the prior ELF's
float32 kernel. SDK startup copies 74,416 SRAM bytes and 27,428 cache bytes;
BSS remains 392,408 bytes and linked pre-task heap is 56,716 bytes. Cache
ways remain I=0/D=7. UART configuration and its 1,024-word task precede the
guarded 2,048-word renderer task; the 200-tick delay precedes workload.
Strong entry copies its 16-byte ROM marker and calls P33 with 160/4/1/1.
The three SDK key-check functions match the prior link after verified
relocations. Two IRQ-123 registrations and the 8,000 ms timer resolve the
audit's manual scheduling item; zero failures or eFuse accesses are found.
The Macro and drum tap loops load base/slope pairs, convert the fraction,
multiply and add, without the old per-tap subtraction/scale multiply.
The prepared Linux shared renderer matches all eight reference PCM hashes.
Hardware recovery, allocation, timing and analog acceptance are pending.


### Pre-scaled kernel — target result

[verified, hardware] Slopes-v1 passed the startup recovery handshake in
78.34 ms, responsive ROM inquiry, two identical full reads, byte-identical
factory restore, same-image reinstall and full 8 MiB readback. Measurement
boot completed all four arithmetic bit patterns, four expected PCM hashes,
32 unit and 24 stage rows, with 352,832 frames per case and no invalid or
clipped samples. Post-workload ordinary UART PING acknowledged. Both resets
were single-use receipts; no physical button was needed.

Mean block times for 1/4/8/12 FM6 voices were 3,389.875 / 3,678.167 /
3,805.167 / 4,002.917 us; maxima 4,063.750 / 4,244.000 / 4,509.750 /
4,778.333 us. The means are only 0.51–0.76% lower than Plaits-cache-v1 in
this comparison. Every one of 5,513 blocks in every case still exceeds the
approximately 1,451 us deadline. This result does not solve real-time audio.

Free heap remained 14,772 bytes across five readings. Worker peak stack was
5,544 of 8,192 bytes (662 unused words), unchanged from the preceding image.
Private raw capture SHA-256:
`45f2ff43e595237d3ea27433bfa4bb78daaa4619e124201ca403d5b1ba902611`.
The DAC was disabled; no KA6 analog or sustained-soak acceptance is claimed.
Further work must address the larger engine/effect costs rather than treating
this small coefficient change as sufficient.


### Engine detail profiler — offline preparation

[verified, source/tests] Optional `--engine-profile` requires the profiled
slopes comparison and instruments only private Macro/drum source copies.
Four regions observe 12-sample generation and each resampler pop separately;
their totals are nested inside existing unit/stage totals. These clock reads
add overhead, so this image locates costs rather than establishing a clean
speed gain. Source changes to either expected pull-loop anchor refuse
preparation. Production engine sources and audio math remain unchanged.

The compiled actual-loop probes preserve output ordering and pending-input
state across zero, short and uneven calls. A separate prepared Linux full
renderer replay matches all eight reference PCM hashes; all region clock
counts, wrap-safe elapsed ticks and per-case resets pass. Each pop region
covers 352,832 outputs per case and generation covers 31,918 blocks of 12
samples in the steady cases. The focused Linux suite passes 108 checks with
one missing-multilib skip. Earlier attempts hit root-owned cache permissions
and then a non-executable temporary mount; the successful run uses an
isolated writable executable build cache, without weakening tests.

[verified, offline build] Detail-v2 vendor ELF
`e06771a1e4c1f06505169b82e6dc4c5dcbaac2399cc31603c5ab7a037e05caff`
independently packs to app
`2a20a8ce9e712e4da363e2333b545aa36373e5b208be757cef52c1030378e109`
(553,492 bytes). Five vendor section exports and existing coefficient bytes
match independent checks; three SDK functions match after verified pointer
and call relocations. Linked pre-task heap is 56,588 bytes. Final exact
startup/recovery/code-generation, cipher/NOR admission and hardware timing
are pending. No new image has been installed.


[verified, offline admission] Final vendor review confirms UART-first task
allocation and its success guard, the 200-tick window before the workload,
strong ROM entry with the prior exact 16-byte marker, unchanged SDK cache
allocation and two IRQ-123 registrations plus the 8,000 ms timer. Actual
Macro/drum code calls the four counters around generation/pop with correct
entry/exit arguments. Independent cipher/CRC and protected-byte checks pass.
The NOR model installs/restores 136 sectors metadata-last and restores after
four interrupted page positions. Exact candidate SHA-256:
`57a605672d17ae479e8db05f9bacc12fd84bce49940da7c46a56130b352b3027`.
Only that image is admitted at the existing slope-image bounds; older plans
are unchanged. Hardware startup recovery and measurements remain pending.

### Engine detail profiler — target result

[verified, hardware] Detail-v2 passed fresh startup ready/PING/ARM/ENTER in
78.25 ms, responsive WL82/UBOOT1.00 inquiry and two matching full reads.
Factory restore, same-image reinstall and full 8 MiB readbacks passed. Both
single-use resets are consumed. Four arithmetic checks and PCM hashes match;
32 unit, 24 stage and 16 engine-region rows cover 352,832 outputs per case.
No invalid/clipped samples occurred. Synthesis calls produce 12 native samples;
per-case counts are 31,919 / 31,917 / 31,918 / 31,918 for both engines.
The private checker verifies complete pop coverage and generation accounting.

Nested mean times per 64-frame block, in microseconds:

| FM6 voices | Macro synthesis | Macro resampling | Drum synthesis | Drum resampling |
| --- | --- | --- | --- | --- |
| 1 | 616.04 | 394.46 | 98.54 | 408.67 |
| 4 | 686.25 | 393.42 | 98.04 | 406.71 |
| 8 | 685.58 | 393.54 | 98.00 | 406.04 |
| 12 | 683.29 | 391.42 | 97.75 | 405.67 |

These include instrumentation overhead. Total means are 3,491.29 / 3,762.08 /
3,892.83 / 4,085.54 us; maxima 4,198.17 / 4,330.71 / 4,617.33 / 4,889.21 us.
Every 5,513 blocks in every case still misses the approximately 1,451 us
budget. This diagnostic establishes attribution, not a clean speed comparison.
Free heap is stable at 14,644 bytes across five readings; peak worker stack
is 5,544 of 8,192 bytes. Receive-only capture was closed by verified process
identity and ordinary post-workload PING acknowledged. Private raw SHA-256:
`4a8b50ccb873632750f52b4644ec30846cab30fbcf00faaaf46b341e6360cec5`.
No DAC/KA6/analog/soak acceptance is claimed. The substantial common
resampling cost warrants further causal investigation before another image.


### Fixed FIR expansion — offline comparison

[verified, source/tests] Optional `--resampler-unroll` expands the fixed
61 symmetric coefficient pairs in the private prepared header, retaining
all four accumulation chains, coefficient values and final reduction.
It requires the profiled slopes comparison and refuses detail profiling
or drift in the expected loop, delay or length definitions. Production
engine sources, native sample rates and filter quality are unchanged.
The pinned SDK's exposed sample-rate converter uses 16-bit sample buffers
and a different state/filter interface; it is not a direct replacement for
this floating-point stream. A bounded header search found no matching
floating-point dot-product API, so this comparison tests compiler loop
handling without introducing a format conversion or vendor dependency.

Compiled original/expanded stream replay is bit-identical for PCM and full
state at every output over seven input rates and two output rates, including
passthrough and refused configurations. The focused Linux suite passes
121 checks with one unavailable-multilib skip. The actual prepared full
renderer matches all eight desktop reference PCM hashes.

[verified, offline build] Vendor ELF
`d5bc904e1d2181709cbebaa441fcbfe1f1c65cac44a1ef715e6af522057a5fc4`
independently packs to app
`b40148de112066290b6941f49d81a7e41632d40f28dd8bd39474ab6f5a32b24e`
(555,580 bytes). Five exported sections, prior table bytes and three SDK
functions match independent checks. Pre-task heap is 54,028 bytes; the
expanded code spends approximately 2.7 KiB more SRAM than slopes-v1.
The exact image is not yet admitted or installed. Target PCM, speed,
stack and startup recovery remain pending. The current detail-v2 board
is healthy and idle; no analog/soak acceptance is claimed.


[verified, offline admission] Exact startup copies, UART-first allocation
with its success guard, 200-tick recovery window, strong ROM marker/P33
entry and dormant SDK schedule were reviewed against vendor disassembly.
Independent cipher/CRC and protected boot/config/tail checks pass. The NOR
model installs/restores 136 sectors metadata-last and restores after four
interrupted page positions. Only candidate
`92d1e3f1fdea9e5a73961f0d88d683527012026a2c5302bbbda2a9d8288f457e`
is admitted at the existing slopes-image bounds. Target recovery, PCM and
performance remain pending.


### Fixed FIR expansion — target result

[verified, hardware] Fresh startup ready/PING/ARM/ENTER passed in 78.19 ms,
followed by responsive WL82/UBOOT1.00 inquiry and two matching full reads.
Factory restore, same-image reinstall and full 8 MiB readbacks passed. Both
single-use resets are consumed. Four PCM and arithmetic checks match;
32 unit and 24 stage rows cover 352,832 outputs per case. Invalid/clipped
samples remain zero, with an explicit completion marker and post-run PING.

Mean block times are 3,164.38 / 3,445.79 / 3,564.25 / 3,761.13 us for
1 / 4 / 8 / 12 FM6 voices. Maxima are 3,956.88 / 4,164.00 / 4,310.25 /
4,577.33 us. Compared with the clean slopes image, mean reductions are
6.65 / 6.32 / 6.33 / 6.04 percent. Every 5,513 blocks in every case still
misses the approximately 1,451 us deadline. This remains timing-only;
no analog or sustained-soak acceptance is claimed.

Free heap stays at 12,084 bytes across five readings; peak worker stack
is 5,544 of 8,192 bytes. Receive-only capture was closed after verifying its
exact process identity. Private raw SHA-256:
`292ff614f2fe2881c2216596d7b095f56fcb220ab974f78275ad8b74178bf764`.
The optimization is useful but insufficient; further shared-renderer cost
reduction and actual audio acceptance remain required.

### Renderer compiler comparison — offline

[verified, offline] The nested vendor command uses `-O2 -flto`; renderer
input IR has neither `optsize` nor `minsize`. The SDK LTO link uses an
inlining threshold of 5. This does not establish that LTO loses `-O2`.
A private no-LTO comparison exceeded SRAM because unused state buffers
remained in combined BSS. Enabling per-variable data sections then linked,
but placed live buffers in orphan sections outside usable SRAM. Both
experiments are rejected for installation; their private staging receipts
are deliberately marked stale. No device command was sent for either.

[verified, source/tests] Optional `--renderer-o3` instead changes only the
prepared renderer's `OPT` from `-O2` to `-O3`, retaining SDK/LTO flags and
memory-section rules. It requires the timing-only profiled unroll comparison.
The receipt records the optimization and exact prepared make-fragment hash.
Default builds stay at `-O2`. All 23 local preparation cases pass; the focused
Linux suite passes 124 tests with one unavailable-multilib skip. The actual
prepared source at `-O3` matches all eight desktop reference PCM hashes.
Rarefaction cannot resolve the sibling worktree preparer; Serena resolves
its actual definition, with file inspection used for the configuration edit.

[verified, offline build] Vendor ELF
`dd315632f93c3caabfe77000ea23205ad914f84806a77298ee3084aea44ac97c`
independently packs to app
`af221664070a37a5c31b967d1fb14a127c6af01177cb4bc792586a5b7cf7298f`
(562,844 bytes). Five exports, coefficient/table bytes and three dormant SDK
functions match independent checks. SRAM startup data grows by 992 bytes
relative to unroll-v1; pre-task heap is 53,036 bytes. Link audit reports zero
failures and one pending manual SDK-scheduling check. Exact startup/recovery,
cipher/CRC, NOR interruption/restore review and admission remain pending.
No O3 image is installed, and no speed or audio acceptance is claimed.

[verified, offline admission] Startup copies 78,096 SRAM bytes and 27,180
cache-data bytes with the existing cache-way allocation. UART recovery
reserves 1,024 stack words before the guarded 2,048-word worker allocation;
its 200-tick wait precedes probes and renderer work. Strong ROM entry retains
the exact prior marker and P33 arguments. Vendor disassembly confirms the
unchanged dormant SDK schedule. Independent cipher/CRC and protected
boot/config/tail checks pass. The NOR model installs/restores 138 sectors
metadata-last and restores interrupted writes at pages 7, 1111, 2183 and 2199.
Only image `fd32ec039217b59762efc09b185dd25871420c47db689ffa626b07d3e183adf3`
is admitted at those bounds. All 46 final transaction/reset/arithmetic checks
pass. Hardware startup recovery and performance remain pending.


### Community performance follow-up — 2026-10-25

[reported, primary repositories read 2026-10-25] SLOOP 2.7 distributes
audio across both cores; 2.7.1 explicitly describes a short glitch when a
failed second core is retired. Its [PR #111](https://github.com/isod89/sloop-fm1/pull/111)
documents independent accumulators, shared scratch/RNG constraints,
golden-output and fault-injection tests. Those are useful review patterns,
not acceptance evidence for Lunar. [SLOOP notes](https://github.com/isod89/sloop-fm1#whats-new-in-27).

[reported] [Melodee](https://github.com/keremimo/melodee#whats-new-in-121)
moves audio into internal RAM and retains voice-budget protection; its
history also records second-core faults and clock-retuning failures.
[Clipper](https://github.com/isod89/clipper-fm1#new-in-051-an-audio-timing-readout-the-crackle-hunt)
exposes late-buffer counts and worst-buffer budget utilization. These
reports support investigating instruction placement, bounded parallel work
and measured deadline margins. They do not establish that every firmware
or workload is dropout-free. No external firmware is installed and no
third-party code is copied by this follow-up.


### Renderer O3 — target result

[verified, hardware] Fresh startup ready/PING/ARM/ENTER completed in
78.3 ms, followed by responsive WL82/UBOOT1.00 inquiry and two matching
full reads. Factory restore, same-image reinstall and complete 8 MiB
readbacks passed. WINDOW and RUN resets are consumed. Four PCM hashes
and arithmetic probes match; 32 unit and 24 stage rows cover 352,832
outputs per case, with explicit completion and zero invalid/clipped samples.

Mean times are 3,104.88 / 3,370.21 / 3,509.96 / 3,690.71 us for
1 / 4 / 8 / 12 FM6 voices. Maxima are 3,867.33 / 4,015.46 / 4,249.13 /
4,507.08 us. Improvements over unroll-v1 are only
1.88 / 2.19 / 1.52 / 1.87 percent; all 5,513 blocks in every case still
miss the approximately 1,451 us deadline. O3 is insufficient.

Heap stays at 11,092 bytes over five readings; peak worker stack is
5,548 of 8,192 bytes. Receive-only capture was closed after its exact
process command line was checked twice; post-run PING acknowledged.
Private raw SHA-256:
`80757209f68469fde9f99c936ba537b2e80ba96ab877831db326b6c055eab439`.
Analog and sustained-soak acceptance remain pending.


### WebKit resize evidence

[verified, CI] Run 40182264179 failed `sequencer-ui.mjs` at the 844 px
scene-cell measurement (zero height); its failure screenshot shows normal
visible cells. A focused Aeon run then caught an intermediate 667 px grid
with seven stale scene columns compressed into the new viewport.
The test now polls its existing 54–64 px and non-overlap requirements
against one current-DOM snapshot, bounded at two seconds, instead of a
60 ms sleep and separate locator reads. SVG class diagnostics use the
class attribute. No production UI is changed. Three repeated WebKit runs and one Chromium run pass on Aeon against
the synchronized source tree; the passing screenshot was inspected.
Repository CI is pending on the next head.
Rarefaction cannot resolve this sibling-worktree test path; Serena resolves
its helper, and source plus screenshots supply the resize evidence.


### Mixer/dispatch placement — offline comparison

[verified, source/vendor disassembly] O3 retains `render_fx` (846 bytes)
and `render_sounds` (1,146 bytes) in flash despite their SRAM caller.
Optional `--mixer-ram` places exactly those two definitions in startup-copied
SRAM in private prepared sources. It requires the timing-only profiled O3
configuration; production sources, DSP arithmetic, rates and filtering stay
unchanged. Preparation checks compare normalized source bodies, placement
and receipt provenance. All 51 focused preparation/refusal cases pass.
The vendor build links; independent layout/startup review and target timing
are pending. No new image is admitted or installed.

[verified, research] The pinned SDK's `jl_math.c` contains floating-point
assembly helpers as well as integer-vector paths. The inspected operations
are complex multiply/add/subtract/power, with no direct equivalent to this
streaming symmetric FIR. JieLi's [math API documentation](https://doc.zh-jieli.com/AC79/zh-cn/release_v1.1.0/module_example/system/math.html)
also documents fixed-point vector routines. None is substituted without
checking arithmetic, filter behavior and actual target cost.

[verified, offline build/replay] All eight prepared full-renderer PCM hashes
match the reference. Vendor ELF
`359f571e27fbfd603e2bc3722eda76a2a9f1a090775eb40073c9315c43addd3d`
independently packs to app
`871a5ceeef90b3696c2e00cd5761600316b59e3eb404d9930636684ae8205545`
(562,268 bytes). Five vendor section exports, coefficient/table bytes and
three SDK functions match independent checks. Pre-task heap is 51,244 bytes,
1,792 fewer than O3. `render_fx` is now in SRAM; `render_sounds` is no longer
a separate linked symbol, and its SRAM caller grows. Link audit has zero
failures and one pending manual SDK-scheduling check. Exact startup/recovery,
cipher/CRC, interrupted NOR restore and hardware timing remain pending.

[verified, offline admission] Startup copies 79,888 SRAM bytes and the
unchanged 27,180 cache-data bytes. UART-first allocation, its success guard,
1,024/2,048-word task stacks and the 200-tick recovery window are verified
in vendor disassembly. Strong ROM marker/P33 entry and dormant SDK schedule
remain intact. Independent cipher/CRC and protected boot/config/tail checks
pass. The NOR model restores after four interrupted page positions across
the 138-sector metadata-last transaction. Only exact candidate
`ccee05d465d396d5749b9d70b6cf8387c2bca100040b654af8f6306dc539e416`
is admitted at those bounds. All 47 transaction/reset/arithmetic checks pass.
Target startup recovery, PCM, performance and stack remain pending.


### Mixer/dispatch placement — target result

[verified, hardware] Fresh startup ready/PING/ARM/ENTER completes in
78.6 ms, then WL82/UBOOT1.00 inquiry and two full candidate reads match.
Factory restore, same-image reinstall and full 8 MiB readbacks pass.
WINDOW and RUN resets are consumed. All four PCM hashes and arithmetic
probes match, with 32 unit and 24 stage rows covering 352,832 outputs per
case, zero invalid/clipped samples and explicit completion.

Mean block times are 3,040.50 / 3,323.29 / 3,454.67 / 3,638.75 us;
maxima are 3,809.67 / 3,940.04 / 4,197.63 / 4,431.54 us. Gains over
O3 are 2.07 / 1.39 / 1.58 / 1.41 percent. All 5,513 blocks in every
case still miss the approximately 1,451 us deadline. Mixer placement
alone is insufficient. Free heap stays at 9,300 bytes over five readings;
peak worker stack is 5,548 of 8,192 bytes. Capture PID was checked twice
before termination; post-run PING acknowledges. Private raw SHA-256:
`bc965e73198aafe00fe211c4ef35f4503c736b2b1cc9149ee28b9665eb9a0385`.

[verified, profile] Sound/insert work still costs 2,530.63–3,129.79 us per
block, versus approximately 269–270 us master and 181–182 us control/UI.
The next investigation targets the measured engine/resampler work. Native
rates, time constants and filtering remain requirements; no analog or
30-minute-soak acceptance is claimed.


### FIR scheduling — offline comparison

[verified, source/vendor disassembly] The vendor decoder needs
`-mcpu=r3 -mattr=+fprev1` for the floating instructions; decoding without
that feature produces misleading unknown/split instructions. The measured
resampler's expanded lowpass largely serializes four independent chains.
Optional `--resampler-schedule` groups four pair additions, four coefficient
products and four accumulations using empty read/write register constraints.
All 61 symmetric pairs, the centre tap, coefficients, each chain's addition
order, native rates and filtering remain unchanged. The option requires the
existing timing-only resident-mixer configuration and refuses source drift.

[verified, offline] A first prototype retained too many values and raised
standalone stack use from 28 to 156 bytes; it is rejected. Adding the
accumulator-group constraint restores 28-byte standalone stack use. The
revised private SDK prototype links with 224 fewer SRAM bytes and smaller
linked drums/macro renderers. Its eight prepared renderer PCM hashes match.
The hand-patched prototype has intentionally stale provenance and must never
be flashed. Fresh reproducible preparation and final machine-code/layout,
recovery and image checks are pending; no target-speed claim is made.

[verified, tests] 131 focused Linux preparation, renderer, resampler,
transaction, reset and arithmetic tests pass; one ABI-dependent case skips.
Both expanded and scheduled full streaming states match their reference
byte-for-byte across seven native rates and two host rates. Production DSP
sources are unchanged. Hardware still runs the healthy mixer image; no
analog or sustained-soak acceptance is claimed.


[verified, exact offline admission] Fresh reproducible vendor ELF
`0a14e3833b1c07d62161924b1878eca20986100759f9e1e9dff23ce649a5b3fd`
independently exports app
`5f41e45041b2651c5a56beec4c93648e053ba6f8bbf8f777ea9bbab5023b723c`
(562,044 bytes). Five section exports, unchanged table bytes and three SDK
function bodies pass independent checks, allowing only verified relocations.
Vendor floating disassembly confirms grouped pair/product/accumulator work.
Startup copies 79,664 SRAM bytes and 27,180 cache bytes; pre-task heap is
51,468 bytes. UART-first allocation/success guard, 1,024/2,048-word task
stacks, 200-tick window, strong ROM marker/P33 path and dormant SDK schedule
are reviewed. Cipher/CRC, protected boot/config/tail and four interrupted
NOR restores pass across the same 138 sectors. Exact candidate
`fe4a860bcbebd57bee05ff94c3dffb613f2914163f1d302bdb007ccc14016512`
is admitted for the no-button comparison. All 48 final transaction/reset/
arithmetic checks pass. It has not yet been installed or hardware accepted.
Rarefaction cannot resolve the sibling-worktree transaction tool; Serena
resolves its allowlist, and direct source/tests cover this small admission.


### FIR scheduling — target result (rejected optimization)

[verified, hardware] Fresh startup PING/ARM/ENTER acknowledged, followed by
responsive WL82/UBOOT1.00 inquiry and two full 8 MiB candidate reads matching.
Factory restore, same-image reinstall and full readback passed. WINDOW and
RUN resets are consumed. All four arithmetic patterns and PCM hashes match;
32 unit and 24 stage rows cover 352,832 outputs per case, with explicit
completion and zero invalid/clipped samples. Receive-only capture was closed
by exact process identity verified twice; ordinary post-run PING acknowledged.

Mean times are 3,059.79 / 3,337.33 / 3,469.33 / 3,651.33 us; maxima are
3,866.13 / 3,948.04 / 4,207.08 / 4,446.63 us. Means are 0.35–0.63 percent
slower than mixer-v1. Every one of 5,513 blocks per case misses the roughly
1,451 us deadline. Grouping the floating instructions did not improve this
linked workload and is not adopted as a production optimization. The option
remains an explicit diagnostic comparison. Free heap is stable at 9,524 bytes
over five readings; peak worker stack remains 5,548 of 8,192 bytes. Private
raw SHA-256: `76c7f53d1c421b4bb8e345af2ce0f2962ebf87fdc280e75b3ca78172d6d74fc4`.
No analog or sustained-soak acceptance is claimed.

### Named shared-renderer keys arrangement — offline preparation

[verified, source] The default mixed stress arrangement is retained. An
explicit `--workload keys` selects FM6, a filter insert and echo/compressor
masters through the same shared app. Sequencing, LFO brightness modulation,
envelope/filter modulation, note densities, release tails and live level/
cutoff edits remain. Both the build receipt and runtime name the workload;
its results require separate PCM references and cannot accept the mixed test.
Unused unit-profile rows are zero, rather than copies of sound zero.

[verified, offline] The first replay rejected the nonexistent `env1` source;
the arrangement now uses the existing `env3` modulation unit. 79 focused Linux checks pass (one ABI-dependent skip), including
profiled/unprofiled output, full active-unit frame accounting,
zero unused rows, deterministic two-cycle PCM, and refusal when the required
compressor is absent. Target timing, analog and soak acceptance remain pending.


[verified, exact offline review] Eight original/prepared keys cases match in
full PCM SHA-256 `b62e14e11377f683ffc5088e425f4c1c9825ac672ead222f0e4cfc07cc937732`.
Fresh vendor ELF `d28fb051a47766f0ad9b0e7a52c55c508b95a79be745d2789f78e16bb3ba472e`
exports app `242d17b1dc16c57de26f4443f32b9dc56d7d728e4a6b6cabfb62b78af33db6bc`
(559,804 bytes). Five exact exports, unchanged tables and SDK functions
with only verified symbol relocations pass. Vendor floating disassembly
confirms UART-first guarded 1,024-word task, 2,048-word worker, 200-tick
recovery window, strong ROM marker/P33 path and dormant SDK scheduling.
Startup copies 80,048 SRAM and 27,180 cache bytes; pre-task heap is 51,084.
Independent cipher/CRC and protected boot/config/tail checks pass. NOR model
installs/restores exactly and recovers four interrupted pages, metadata last.
Exact keys candidate `bee9d4bc83cc78e1c1a4a40448dc4211f2d8276cb6a8cad5878c9c5d7ee2aa36`
is admitted only for the 137-sector unattended timing comparison. It has not
yet been installed or hardware accepted. Mixed deadline failure remains.


### Named keys arrangement — first target result (deadline failure)

[verified, hardware] Startup UART PING/ARM/ENTER acknowledges, followed by
fresh WL82/UBOOT inquiry and two matching full 8 MiB reads. Exact factory
restore, same-image reinstall/readback and both single reset attempts pass
their applicable gates; reset receipts are consumed. The initial transition
restore using the new smaller image range refused before mutation, correctly
protecting the installed larger image's last sector. Restoring with the
installed image's reviewed range then passed; no bounds were widened.

All four keys PCM hashes match the desktop, with four arithmetic patterns,
32 unit rows (four active/four zero per case), 24 full stage rows and explicit
completion. Means are 1,396.42 / 1,615.42 / 1,753.79 / 1,969.17 us; maxima
are 2,220.46 / 2,319.08 / 2,516.71 / 2,763.17 us. Respectively 1,450 /
5,228 / 5,510 / 5,513 blocks miss the roughly 1,451 us deadline. This named
arrangement also fails acceptance. No analog or sustained soak is claimed.

The instrument costs 244–791 us/block across densities; filter 205–209 us,
echo 163–167 us, compressor 107–108 us, control/UI stage 167–175 us.
The sound-stage time beyond instrument/filter counters is roughly 443–468 us;
this is a profiling lead, not proof of any one function's cost. Free heap
remains 9,140 bytes across five readings; peak worker stack is 5,548/8,192.
The sole RX process was verified twice, terminated, and its session closed
before ordinary post-run PING acknowledged. Private raw SHA-256:
`b90584fd2da94af561b89c640e8fe30d7a6482a5275bc050a8f8306575ff758b`.


### Sequencer dispatch placement comparison — offline only

[verified, offline] Ten complete host keys replays under gprof locate calls
through the sequencer slot dispatch and modulation hooks. Host time is a
profiling lead, not pi32v2 timing. The filter's frequent coefficient updates
are intentional control-rate smoothing and are retained. In the current
linked target, `play_slots_hook`, `walk_next` and `dispatched` remain XIP
and total 2,368 bytes despite the resident dispatch wrapper.

An explicit `--dispatch-ram` preparation option places those three functions
in startup-copied SRAM. It requires the existing timing-only resident mixer
comparison. Removing placement pragmas reproduces the original sources;
no event order, modulation cadence, samples, rates or filtering change.
Preparation/refusal checks pass locally. Actual vendor placement, heap,
startup recovery, PCM equivalence and target performance still require
review and measurement. No dispatch image is admitted or installed.


[verified, exact offline review] Dispatch comparison ELF
`c4eb6e2557584aaafd8b17f8b280608846ee12c8791898410b21cec687dd0e86`
exports app `2213bd5aa22219ae4ecfa0dce3e9041de35338e14fcda98cc705009fefcf8caf`
(559,868 bytes). Startup copies 81,552 SRAM bytes; cache remains 27,180.
Pre-task heap is 49,580 bytes. `walk_next` is resident at `0x01c0154a`;
the slot dispatch including inlined helpers is resident at `0x01c01784`.
Eight original/prepared PCM renders match the keys reference exactly.
81 focused Linux tests pass (one ABI skip); 49 final transaction/reset
checks pass locally. Five vendor exports, tables and SDK exact relocated
functions match. Disassembly confirms guarded UART-first allocation,
200-tick recovery before initialization, strong ROM marker/P33 path and
the unchanged dormant SDK scheduling. Cipher/CRC, protected bytes and
137-sector NOR install/restore with four interrupted-page restores pass.
Candidate `356c0b070d8ac6483fd8034767777b8c5dc13c25d04227c9f63dccaf3b1523e8`
is separately admitted for timing only; it is not installed or hardware
accepted. The prior wrong SDK path failed during preparation and was kept
as failed evidence; the reviewed build uses the established private template.

### Sequencer dispatch SRAM comparison — first target result

[verified, hardware] Candidate `356c0b07…` completed its startup recovery
window: fresh ready followed by PING/ARM/ENTER acknowledgements in about
78 ms, fresh WL82/UBOOT inquiry and two full 8 MiB reads matching the
candidate. Factory restore, same-image installation and full readback passed.
Both unique reset receipts are consumed; neither may be retried.

All four keys PCM fingerprints match the desktop. Four arithmetic patterns,
32 unit rows and 24 stage rows cover the full 352,832 frames per case;
completion is explicit and invalid/clipped counts are zero. Mean times are
1,334.42 / 1,550.63 / 1,683.13 / 1,892.92 us; maxima are 2,160.00 /
2,314.92 / 2,451.29 / 2,747.08 us. This is a 4.44 / 4.01 / 4.03 / 3.87%
mean improvement over the preceding keys image. However, 504 / 4,899 /
5,484 / 5,513 of 5,513 blocks miss the roughly 1,451 us deadline.
The comparison still fails deadline acceptance. The mixed stress fixture
remains unaccepted, and no analog capture or sustained soak is claimed.

Free heap remains 7,636 bytes over five readings; peak worker stack remains
5,548/8,192 bytes. The sole UART RX process was checked twice and closed
before the ordinary post-run PING acknowledged. The board is healthy idle.
Private raw SHA-256:
`9e837ddb8b160b71f0e5118a5be89bdb4ad00aa5ca886b76ab24a3aeec84d4f6`.

### CI notice dismissal polling

[verified, CI/source] Run 40190108909 Chromium job 121159279951 failed at
`files.mjs:107`: its poll dereferenced `.hidden` while SweetAlert2 had
briefly detached the notice before `didClose` restores the original node.
The predicate now waits for optional `hidden === true`: temporary absence
keeps polling, and only the restored hidden node satisfies the assertion.
No timeout or product behavior changes. The complete files browser check passes on Aeon in Chromium 153 using the
pinned Playwright 1.63 image: files, unavailable storage, load links, hashes,
embedding, local origins and layout all pass, with no browser errors. This
uses the existing built Wasm module and current page/test sources; exact-head
repository CI remains a separate gate. This repair does not establish
hardware audio acceptance.

### Compact session metadata (offline, 2026-10-25)

- [verified] `read_session` used eight full track reads (including automation arrays) and 64 full clip reads per refresh. Added `fm1_seq_get_session_track`, a read-only compact reader of occupancy, active/queued/playing slots, pending stop, native position and playing-loop bounds. UI refresh frequency, position scaling, hold/record/hint logic and rendering are unchanged.
- [verified] Bounded Aeon Ubuntu 24.04 container: 152 sequencer/session/song UI tests passed, 6 skipped. The new differential C test covers 17,408 snapshots across 1–16 tracks, empty/full grids, all playing slots/NONE, queued stops and randomized positions; it compares the full getters and checks memory remains unchanged, including invalid-track reads. The first attempt failed at build setup because existing staging objects were unwritable; the successful run used fresh executable build tmpfs mounts.
- [inferred] Removing redundant metadata copies may reduce the measured UI cost; no target speed claim yet. Full original/new PCM replay, vendor compilation and exact-image review remain required before admission. Installed dispatch image remains healthy idle; no hardware operations or analog acceptance in this experiment yet.

- [verified] Full eight-case mixed and keys host replays match their prior PCM byte for byte (`c676e9b4…` mixed, `b62e14e1…` keys). A private checked UI reader also compared the entire UI struct to the original reader at every refresh of both complete workloads. Prepared and original keys builds match all eight PCM rows and the full PCM SHA. An additional 81 dev-board focused tests passed, 1 ABI-dependent skip.
- [verified] Session-v1 vendor ELF `ae5359f7…`, app `f5f5eead…` (560124 B); five independent vendor section exports match ELF packing. SRAM 81552 B, cache data 27180 B, BSS 392412 B and pre-task heap 49580 B unchanged. UI frame decreases from 1676 to 1636 B; no target stack or speed claim. Reviewed startup copy, UART-first 1024-word reservation, worker 2048-word reservation, 200-tick recovery window, strong ROM entry, relocated marker and P33 code. SDK key-check code matches the reviewed prior image with verified pointer/call relocations; automated link audit has no failures, with scheduling resolved by that machine-code review.
- [verified] Candidate `6619c671eaf054db1e7c3e8873787f7a61a54940fd6a3faceb1971d73cf9c4eb`, 137 sectors, app end `0x8cd1c`: independent cipher/CRC/protected-byte checks and NOR install/restore plus interruption pages 7/1095/2167/2183 pass. Exact hash admitted for the same 137-sector boundary. Not installed or hardware accepted.


[verified, CI repair] Exact-head run 40192720153 GPL-disabled job passed 4,494 tests but failed the committed-Wasm freshness check after the session UI change. Rebuilt the module and record in bounded Aeon containers through the existing build/parity workflow: all 108 scenarios pass, matching musl and JavaScript exactly. Local build-record and licensing checks pass. No assertion was relaxed; new exact-head CI remains required.


### Compact session metadata — target comparison

[verified, hardware] Startup ready/PING/ARM/ENTER acknowledged in 78.5 ms, followed by fresh WL82/UBOOT inquiry and two matching full 8 MiB reads. Factory restore, same-image reinstall and full readback pass. WINDOW and RUN receipts are consumed. Four PCM hashes and arithmetic patterns match; 32 unit and 24 stage rows cover 352,832 frames per case, invalid/clipped counts are zero and completion is explicit. Mean block times are 1352.50 / 1573.38 / 1710.42 / 1928.08 us; maxima 2169.50 / 2312.92 / 2402.54 / 2727.46 us. Late counts are 779 / 5026 / 5495 / 5513 of 5513: deadline acceptance still fails. UI-stage means fall to 147.96 / 152.83 / 156.17 / 163.29 us, but total means are slower than dispatch-v2. This is not an overall performance improvement. Free heap remains 7636 B; peak stack is 5548/8192 B. Sole RX identity was checked twice, terminated and terminal before post-run PING acknowledged. Raw private SHA: `947d0ee445c593fe9824dd96416fac4fe6661312d4d9e22aa92f5a0ee9148d3d`. No analog or soak acceptance.

[verified, source/vendor disassembly] The octave LED helper computes seconds before its off/solid returns. In session-v1, both inlined calls execute software double conversion/division before checking the magnitude (0x0201e70a–0x0201e730 and 0x0201e78e–0x0201e7a8). Moved the unchanged seconds calculation below those returns. This removes unnecessary work in source; exact vendor code generation, differential LED/PCM checks and actual timing are still pending. No new candidate is admitted.


### LED early-return guards — offline review

- [verified] Vendor code now branches around software double conversion/division for both off/solid LED paths (guards at `0x0201e708` and `0x0201e780`). Blink calculations, frame clock, native sample rates and UI cadence are unchanged. 7,200,000 old/new helper comparisons pass across eight sample rates and full-range frame counters; 27 focused octave/LED/pitch tests pass in a bounded Aeon container.
- [verified] All eight original/prepared keys PCM rows match, full SHA `b62e14e11377f683ffc5088e425f4c1c9825ac672ead222f0e4cfc07cc937732`. Browser rebuild passes 108 parity scenarios; build-record/licensing checks pass.
- [verified] Vendor ELF `76a7a475…`, app `ca12490d…` (560092 B). Five independent section exports match packing. SRAM/cache/BSS/pre-task heap remain 81552/27180/392412/49580 B. Reviewed UART-first task allocation and failure branch, 200-tick startup window, startup copies, strong ROM/P33 exact prior bytes, relocated `usb_update_mode` marker and SDK key-check relocations. Independent cipher/CRC/protected bytes and NOR install/restore with four interrupted pages pass.
- [verified, offline admission] Exact candidate `f6c74b7b198dd1ac5e154862e39d09dded5a2cfa6dae4613528aa63b8d545f23` uses the existing 137-sector range, app end `0x8ccfc`. Admitted for that exact hash only. It is not installed or hardware accepted; target speed and analog acceptance remain unverified.


### LED early-return guards — target comparison

[verified, hardware] Startup ready/PING/ARM/ENTER completed in 78.3 ms; fresh WL82/UBOOT inquiry, two full matching reads, factory restore, same-image reinstall and full readback pass. WINDOW64020 and RUN81014 receipts are consumed. Four arithmetic patterns, four PCM hashes, 32 unit rows, 24 stage rows and all 352,832 frames per case match, invalid/clipped counts zero, explicit completion. Mean block times are 1301.33 / 1520.71 / 1654.08 / 1873.46 us (2.8–3.8% lower than session-v1); maxima 2141.50 / 2229.00 / 2462.29 / 2700.79 us. Late counts are 268 / 4399 / 5425 / 5513 of 5513: deadline acceptance still fails. UI means fall to 119.75 / 121.21 / 125.21 / 130.96 us. Heap remains 7636 B at all five readings; peak stack 5548/8192 B. Sole RX PID/cmdline verified twice, closed and terminal before ordinary PING acknowledged. Raw private SHA `9374c1a2ecef27e4e1968bd8cc5b303e7249ec2686ffcf076a58eadd9747a690`. No DAC/analog/soak acceptance.


### Explicit 32-bit FM additions (offline experiment)

- [verified] The vendor compiler retains dead high-word carry additions after signed 64-bit multiply/shift results are ultimately converted to 32-bit samples. Explicit unsigned 32-bit additions preserve the final wraparound bits while shortening the probe and complete FM operator loop. Added opt-in `--msfa-narrow-adds` to private preparation only; vendored repository sources remain unchanged. It requires timing-only hot code and records source hashes, rejecting source drift. No audio-image or target-speed claim.
- [verified] 37 focused tests pass in a bounded Aeon container, including 2,000,000 randomized vectors per expression plus signed-boundary cases against the original wide sums. Vendor build passes with downloader disabled. Full original/prepared keys and mixed eight-case PCM replays match. Vendor ELF `ae125d77…`, app `d081abe3…` (560124 B), pre-task heap 49548 B (32 B lower); SDK key-check relocations/table exports match the prior image. All 142 DX7 behavioral tests pass on an isolated ordinary source tree with only the narrow-add changes (normal engine set); the upstream byte-provenance test is deselected only for that intentionally modified private tree and remains unchanged in the repository. Initial attempts used incompatible prepared-table tests or omitted required engines; these were setup failures, not passing checks. Exact startup/recovery/layout/cipher/NOR review remains required before admission. No candidate is admitted or installed.

- [verified, offline admission] Exact vendor review confirms SRAM copy 81584 B, BSS 392412 B, cache 27180 B, UART task first (1024 words), failure skips renderer, worker 2048 words and 200-tick recovery window. ROM/P33 code matches the prior reviewed image with checked +32 B lock-pointer relocations; marker and sole SDK late-init schedule match. Candidate `5370ec631766ddee6594a8648a0840c213dd1e37637d3c064cbc4a8a2412a2ab`, app end `0x8cd1c`, passes independent cipher/CRC/protected-byte checks and 137-sector NOR install/restore plus four interrupted-page restorations. Admitted offline for that exact hash; not installed or hardware accepted.

### Explicit 32-bit FM additions — target comparison

[verified, hardware] Startup ready/PING/ARM/ENTER passed in 78.5 ms. Fresh WL82/UBOOT inquiry and two matching full reads precede factory restore, same-image reinstall and full readback. WINDOW5824 and RUN29034 receipts are consumed. All four arithmetic patterns and PCM hashes match; 32 unit and 24 stage rows cover 352,832 frames per case, with zero invalid/clipped samples and explicit completion. Mean block times are 1292.29 / 1502.29 / 1632.79 / 1841.00 us (0.69–1.73% lower than LED guards); maxima 2134.38 / 2259.67 / 2397.13 / 2662.38 us. Late counts remain 224 / 3952 / 5321 / 5511 of 5513: deadline acceptance fails. FM unit means fall to 237.92 / 442.67 / 565.46 / 751.38 us. Heap is 7604 B at all five readings; peak stack remains 5548/8192 B. Exact owned RX identity checked twice, terminated and terminal before ordinary PING acknowledged. Private raw SHA `ce95cfacf35d13b1276376dd3333d9142154e29c6d4e43a5f14c8a9e17a09792`. No DAC/analog/soak acceptance.


### Bounded sine interpolation multiply — offline experiment

[verified, offline] The fixed delta table has maximum absolute delta 102943;
its largest product with the 14-bit fraction is 1686515169, below INT32_MAX.
Added an opt-in private preparation transform that verifies table dimensions,
all 2048 integer entries and the product bound before replacing this one
64-bit interpolation product with signed 32-bit arithmetic. No table, rate,
gain, event order or vendored repository source changes. 41 focused checks
pass, including all 16,777,216 delta/fraction pairs compared against the
original expression. A vendor compiler probe emits a single 32-bit multiply
and arithmetic shift. Full vendor build, complete keys/mixed PCM replay,
exact-image review and hardware timing remain pending; no new image is
admitted or installed and no dropout-free acceptance is claimed.


[verified, offline admission] Full keys/mixed eight-case PCM replays match
(`b62e14e1…` / `c676e9b4…`); 142 FM behavioral tests pass, with only the
private modified-copy upstream byte-provenance check deselected. Repository
provenance checks remain intact. Vendor ELF `530f5fd4…` exports app
`93c7f29a…` (560060 B). SRAM/cache/BSS sizes are 81520/27180/392412 B,
pre-task heap 49612 B. Manual vendor review confirms UART-first 1024-word
reservation, failure skips worker, worker 2048 words, 200-tick recovery,
startup copies and unchanged ROM/P33 code after verified pointer relocations.
Tables and SDK key-check code match the prior image; sole late-init remains
`sdk_meky_check`. FM loop loads the same sine table and emits signed32
interpolation products while retaining wide gain products.

Candidate `4589d46ba8382c86ae7f05c6c60c8b3c8e3c8b0b942c811ffceefa03d1d2a7bf`
passes independent cipher/CRC/protected-byte checks and 137-sector NOR
install/restore plus four interrupted-page restorations. App end `0x8ccdc`.
Admitted for this exact hash only; not installed or hardware accepted.


### Bounded sine multiply — target comparison

[verified, hardware] Startup ready/PING/ARM/ENTER passed in 78.7 ms,
followed by fresh WL82/UBOOT inquiry and two full reads matching the image.
Factory restore, same-image reinstall and full readback passed. WINDOW22176
and RUN80552 receipts are consumed. Four PCM hashes and arithmetic patterns,
32 unit rows and 24 stage rows cover all 352832 frames/case; invalid/clipped
counts are zero and completion explicit. Mean block times are
1288.625 / 1493.833 / 1621.042 / 1824.125 us (0.28–0.92% lower than narrow
adds); maxima 2139.25 / 2225.75 / 2401.08 / 2642.33 us. Late counts remain
216 / 3740 / 5265 / 5512 of 5513: deadline acceptance fails. FM unit means
are 233.54 / 434.08 / 554.71 / 737.96 us. Heap remains 7668 B in all five
readings; peak worker stack remains 5548/8192 B. Exact owned RX identity
checked twice, terminated and terminal before ordinary PING acknowledged.
Private raw SHA `e2f73f79b3fca7057d15204495902c009756af616c15d92b6edc0348c863eec3`.
No DAC/analog/soak acceptance.

### Compact current-route reads — offline comparison

[verified, source] `fm1_app_unit_of_track` and the sequencer bridge's
per-event/post-dispatch destination reads copied full track snapshots,
including automation arrays, for only route kind/index. Added a two-byte
`fm1_seq_get_route` snapshot and switched those callers. Reads remain current
at every invocation; previous-route note-off handling and event order remain
unchanged. No state cache, persistent allocation, rate or DSP arithmetic change.
The existing differential C test now also checks routes against full getters
across all 17,408 snapshots, varied byte values, unchanged sequencer memory and
invalid-track refusal without changing the output.

[verified, offline] 384 sequencer/UI/render tests pass in a bounded Aeon
container. Eight complete keys and mixed PCM replays match their previous
SHA values (`b62e14e1…` and `c676e9b4…`). Refreshed Wasm passes all 108 parity
scenarios, each identical to JavaScript and musl. Vendor build passes with
downloader disabled: ELF `fcc8db3d…`, app `f93ae8f2…`, 560060 B. Actual route
getter is 44 bytes, reading the same two fields directly. SRAM increases to
81648 B; pre-task heap is 49484 B. Exact startup/recovery/layout, SDK and
packaging review remains required before admission; no new image installed.
The sine32 image stays healthy idle. No target speed or audio acceptance claim.

[verified, rejected probe] Private output-buffer `__restrict__` annotations
for echo/filter/compressor offered no convincing code-generation improvement:
echo remained 2106 bytes, compressor grew 2242→2284 bytes with more stack
accesses. This probe is not part of the committed implementation or board image.

[verified, offline admission] Exact startup/UART-first/200-tick recovery,
ROM/P33 marker and SDK checks pass. Cache-copy `memmove`/`memset` call
relocations are checked against the same target symbols; the FM loop is
byte-identical to sine32. Independent cipher/CRC, protected bytes and all
137-sector NOR install/restore checks pass, including interrupted pages
7/1095/2167/2183. 54 transaction/reset tests pass. Candidate
`e2fb418459789350793538d33ed82dfe5a43ade037c31211d65c84da23c40304`
is admitted for this exact hash only; no installation or hardware acceptance.


### Compact current-route reads — target comparison

[verified, hardware] Startup ready/PING/ARM/ENTER passed in 78.35 ms; a
fresh WL82/UBOOT inquiry and two full image reads matched afterward. Factory
restore, same-image reinstall and full readback passed. WINDOW35040 and
RUN95969 receipts are consumed. Four PCM fingerprints and arithmetic patterns,
32 unit and 24 stage rows cover all 352832 frames/case; invalid/clipped counts
are zero and completion explicit. Means are 1271.125 / 1475.958 / 1600.833 /
1796.542 us (1.20–1.51% lower than sine32); maxima 2115.625 / 2218.125 /
2363.75 / 2648.292 us. Late counts remain 116 / 3439 / 5259 / 5505 of 5513,
so deadline acceptance fails. Heap stays 7540 B in all five readings; peak
worker stack is 5552/8192 B. Owned RX identity checked twice, terminated and
terminal before ordinary PING acknowledged. Private raw SHA
`b307aa90fc5a8120d061eea8c62760f884fe3215c1e9d0824d978f4542043c22`.
Board remains healthy idle; no DAC/analog/soak acceptance.


### Pure FM operator unrolling — offline experiment

[verified, compiler probe] Four-way hints on all six active FM loops increased
stack accesses (modulated kernel 6→30, pure 5→24 static stack-related
instructions). Two-way all-loop hints still added a loop stack read in the
modulated kernel. Neither broad probe is admitted. A narrower opt-in
`--msfa-pure-unroll` annotates only the two branches of the reviewed active
pure operator, after narrow additions. The source-body SHA guard rejects
drift or repeat application; stripping only its two annotations reproduces
the input exactly. Timing-only hot O3 preparation is mandatory. Default
builds and repository vendor source remain unchanged.

[verified, offline] 51 focused checks pass, including the three native
renderer tests rerun with a writable temporary build mount after the initial
read-only-mount refusal. The private full vendor build passes, downloader
disabled. Modulated kernel stays byte-identical at 168 B; pure kernel grows
150→238 B without additional static stack accesses. SRAM is 81744 B, cache
data 27180 B, BSS 392412 B. ELF SHA `df09508ef28fdb2acd1e7ea52b5b279cb46839d60f9a9d5ae16e9d8dce96b9df`.
Eight complete prepared keys and eight mixed replays retain PCM SHA
`b62e14e1…` and `c676e9b4…`; host GCC ignores the clang loop hint, so those
replays verify prepared arithmetic, not vendor loop code generation. Exact
image/startup/recovery/SDK/packaging review and target PCM/timing remain
pending. No new candidate admitted or installed; route image stays healthy idle.


[verified, offline admission] Five independent section exports produce app
SHA `6bee706f772eccff8ad4edda707114166e443ba80bb15f4c710d02ee02a014a1`,
560156 B, end `0x8cd3c`. Manual vendor startup review verifies 81744 B SRAM
and 27180 B cache copies, unchanged 392412 B BSS, UART-first 1024-word
reservation, failure skipping worker, 2048-word worker and 200-tick recovery
window before workload initialization. ROM/P33 and SDK machine code match
prior after verified relocations; marker and sole SDK late-init match. The
link audit has zero failures; exact SDK comparison resolves its scheduling
item. Independent cipher/CRC/protected bytes and 137-sector install/restore
model pass, including interrupted pages 7/1095/2167/2183. Exact candidate
`b8823c2a322aa47e28306ca11d423838438daa1328a393969c554ffedaf4ab98`
is admitted offline only; hardware recovery, target PCM and timing remain
unverified for it.


### Pure FM operator unrolling — target comparison

[verified, hardware] Startup ready/PING/ARM/ENTER passed in 78.28 ms; fresh
WL82/UBOOT inquiry and two full 8 MiB candidate reads matched. Factory
restore, same-image reinstall and full readback passed. WINDOW53431 and
RUN10068 receipts are consumed. Four PCM fingerprints and arithmetic patterns,
32 unit and 24 stage rows cover all 352832 frames/case; invalid/clipped counts
are zero and completion explicit. Means are 1265.792 / 1467.292 / 1590.042 /
1781.625 us (0.42–0.83% lower than route); maxima 2119.417 / 2177.125 /
2372.042 / 2635.542 us. Late counts remain 113 / 3154 / 5181 / 5496 of 5513,
so deadline acceptance fails. Heap stays 7444 B in all five readings; peak
worker stack is unchanged at 5552/8192 B. Owned RX identity checked twice,
terminated and terminal before ordinary PING acknowledged. Private raw SHA
`700a693e9cb87ef3c081a88873a2b595fd58a066363408323ee117ee68eaf69f`.
Board remains healthy idle; no DAC/analog/soak acceptance.


### Compressor settled-control scan — offline comparison

[verified, source] `CompRender` now stops scanning control glides for the
remainder of a render call after finding all settled. Every new render call
checks again. The final step that reaches a target still updates curve and
auto gain, and all detector/gain arithmetic runs at the unchanged sample rate.
The engine API serializes parameter changes and render on the audio task;
`CompUpdateAuto` does not mutate control targets. No persistent state is added.

[verified, offline] The compressor and effect-switch suites pass (86 checks),
including exact hashes and 1/7/64-frame equivalence during control changes.
Eight complete prepared keys and eight mixed replays retain their reference
PCM SHA `b62e14e1…` / `c676e9b4…`. Full vendor build passes; exact generated
code branches around the settled scan at `0x01c054fa`, and local frame
reservation falls 116→96 bytes. This is code-generation evidence, not target
timing or image admission. Host cost comparison, best of three internal runs:
Peak 1348.9→1190.3 ns/block, Glue+Auto 1536.8→1371.8, continuously gliding
1752.8→1786.3. The gliding cost increase must be checked on target too. The
first cost attempt had no baseline executable; the second omitted `--cost`.
Neither failed setup is counted as a timing result.

[verified, browser build] Rebuilt the default module in bounded Aeon
containers. All 108 parity scenarios pass (108 exact versus JavaScript/musl;
105 exact versus glibc, existing libm-sensitive differences). DX7, metadata,
edit parity and the 30-second edit storm pass; zero late storm quanta. Actual
container digests, local source/Wasm hashes and provenance check pass. Local
pytest was unavailable; the provenance test passed in the Aeon test image.
Module SHA `51f8ccf666ff978da065354ba710f3a8a14ad0b17470610b9796b35c0d32072d`.
Private source/build/logs use `source-comp-settled`,
`build-sdk-renderer-comp-settled-v1`, `comp-settled-*` under the existing task
directory. No candidate packaged/admitted/installed; board remains pure2,
healthy idle. Exact image/SDK/startup/recovery/cipher/NOR review, target timing
and analog acceptance remain pending. Rarefaction still selects the primary
checkout with fallback flags; Serena resolves the actual worktree symbols.
Direct worktree source inspection is the authority where they differ.


[verified, offline admission] The settled-compressor candidate is
`f9233d22b81bcd3203e460fa602d2d2d6f00c75387347a5a997c642937f093f3`.
Independent section export/app reconstruction, exact SDK functions with checked
relocations, startup memory copies, UART-first allocation/failure path, 200-tick
recovery window, ROM/P33 code, cipher/CRC/protected bytes and NOR install/restore
checks pass. Four interrupted-write cases restore correctly. App is 560220 bytes;
SRAM 81808 bytes, pre-task heap 49324 bytes; the same 137-sector boundary applies.
The transaction/reset suites pass all 56 checks. Only this exact hash is added
to admission. It has not yet been installed or accepted on hardware.


### Settled compressor — target result

[verified, hardware] Fresh startup recovery acknowledged in 78.6 ms.
Fresh ROM inquiry, two full current-image backups, factory restore, same-image
reinstall and full 8 MiB readback pass. Both one-shot reset receipts are consumed.
All four PCM/arithmetic hashes, 32 unit/24 stage rows and complete frame/block
counts match; invalid/clipped samples remain zero. The compressor falls from
about 108 to 85 us/block. Total means are 1241.29 / 1443.92 / 1565.38 /
1757.63 us (1.3–1.9 percent better); maxima 2095.13 / 2145.25 / 2371.88 /
2600.29 us. Late blocks remain 104 / 2481 / 5034 / 5480 of 5513. Deadline
acceptance FAILS. Heap remains 7380 bytes over five readings; peak worker
stack 5552/8192 bytes. Exact owned RX was checked twice, closed and terminal
before ordinary post-run PING acknowledged. Private raw SHA
`a38a0572bd5828bc7e4a90ae497c6ffa065a763e65fc83aaec93ed0cfd5e8a05`.
No DAC, analog or sustained-soak acceptance is claimed.

[verified, offline investigation] The pinned SDK's linked task initializer
recognizes a `#C0`/`#C1` task-name prefix and validates a core index of 0 or 1.
This establishes a scheduling mechanism, not a working parallel renderer.
FM6 currently shares its FmCore buses and per-voice scratch between voices;
parallel voice work needs separate scratch, unchanged ordered mixing, bounded
publication/timeout handling and fault injection before target admission.
The sequencer/UI profile also remains about 114–120 us/block; its sync copies
a complete 656-byte previous UI snapshot and reserves 1636 local stack bytes
in the current vendor image. These are optimization leads, not measured gains.

### SVF identical-channel shortcut — offline checkpoint

[verified, source] The SVF evaluates one channel and copies its output/history
only when input, cutoff coefficient and all four history floats match bit for
bit. Native control updates, filter arithmetic, state size, rates and stereo
history remain unchanged. A memcpy float-to-integer helper preserves signed
zero while avoiding aliasing casts. Initial memcmp guards generated byte
packing and an external library call; the revised vendor guard uses word loads
and integer comparisons at `0x01c07a46..0x01c07a94`, with a 64-byte local frame.

[verified, offline] Independent old-source/new-source differential replay
matches every PCM byte and complete 656-byte state over 310100 calls / 819200
frames, five rates, stereo tails, spread changes, signed zero and type changes.
All 109 existing filter/effect-switch checks and a new independent-channel
regression pass. That regression compares each channel with a separate instance
fed a deliberately different opposite channel, without duplicating SVF equations.
Full prepared keys and mixed eight-case PCM remain `b62e14e1…` / `c676e9b4…`.
Vendor build passes. Host best-of-three ns/block: mono 1431.09→1261.12,
stereo 1428.26→1276.04, spread 1425.91→1269.33. These are host measurements,
not target gains. Initial rerun setup failures (existing output refused,
harness/PYTHONPATH paths) were corrected before successful checks.

[verified, browser] Default Wasm rebuilt in bounded Aeon containers; 108 parity
scenarios pass (108 exact JS/musl, 105 exact glibc), with DX7/metadata/edit
parity and the 30-second edit storm passing, zero late quanta. Source/module
provenance passes. Module SHA
`fc97b60d07562311f985b956e4d22994527759adda62fab15eb753b8538f562c`.
Private evidence uses `source-filter-mono`, `build-sdk-renderer-filter-mono-word-v2`,
`filter-mono-word-v2-*`, and `wasm-filter-mono-word-v2` in the existing Aeon task.
No new image is admitted or installed. Exact image/recovery/SDK/cipher/NOR
review and hardware timing remain pending; board stays healthy on f923.
Deadline, mixed target, fault/underrun, DAC/KA6 and 30-minute soak acceptance
remain incomplete. PR155 stays draft and unmerged.

[verified, offline admission] Exact candidate
`49ef7762bf3276e5e5ec150ca6d777f285b7b83f60b0ca5f1d771d60e2314a8e`
has app SHA `8ab9ac7c9acdce27ec21c4d14c55bc74c84ad17ae0678945e442af273127b8b9`,
560316 bytes, end `0x8cddc`. Independent section exports reconstruct the app;
SRAM copy is 81904 bytes, cache 27180, BSS 392412, pre-task heap 49228.
Manual generated-code review confirms the UART-first 1024-word allocation,
failure skipping the worker, 2048-word worker and 200-tick recovery window.
Exact SDK scheduling/key-check and ROM/P33 comparison passes after verified
relocations; linker audit has no failures, its scheduling item resolved by
that comparison. Prepared filter source differs only by the intended RAM
section pragmas. Independent cipher/CRC/protected bytes and 137-sector NOR
install/restore pass, including interruption pages 7/1095/2167/2183. The first admission suite failed 21 checks because three older cross-image
exemption lists omitted the new reviewed hash (36 passed). The preceding
commit incorrectly recorded a pass before its result was inspected. The lists
are corrected; final rerun results follow below. This hash is admitted offline only; it has not
yet been installed or accepted on hardware.

[verified, corrected admission rerun] All 57 transaction/reset checks pass
in 0.86 s after updating the three explicit cross-image exemption lists.
Protected-boundary rejection tests remain in place. No hardware traffic was
sent during the failed or corrected admission run.

### SVF channel shortcut — target result

[verified, hardware] Startup fresh-ready/PING/ARM/ENTER completed in 78.34 ms.
Fresh ROM inquiry and two full candidate backups, factory restore, same-image
reinstall and full-flash readback pass. WINDOW30065 and RUN18951 receipts are
consumed. Four PCM/arithmetic fingerprints, 32 unit/24 stage rows and complete
frame/block counts match; invalid/clipped counts are zero. Means are
1235.708 / 1440.417 / 1561.792 / 1753.458 us; maxima 2094.167 / 2153.417 /
2361.042 / 2594.750 us. Late blocks are 101 / 2409 / 5003 / 5482 of 5513:
deadline acceptance still FAILS. Mean changes versus settled compressor are
only about 0.2–0.5%; the host improvement does not establish a substantial
target gain. Filter cost remains about 188–193 us/block. Heap is stable at
7284 bytes over all five readings; peak stack remains 5552/8192 bytes.
Exact RX PID/command was checked twice and terminated, its session terminal
before ordinary post-run PING acknowledged. Board remains healthy idle on
49ef; no capture or device operation remains live. Private raw SHA
`4adcb6f665c36b42a3df5683361d0fb0359324fd2d012db73312757495538ba1`.
No analog/DAC/soak acceptance is claimed.

[verified, offline layout] A separate vendor-ABI object probe reports FM6
Voice=684 bytes, FmCore=544, voice-output buffer=256, Instance=16188 and
Offsets=24. Thus private core/output scratch alone is 800 bytes; a task stack,
scheduler allocation and safe job ownership/timeout behavior must also fit.
The first two standalone probe attempts lacked SDK/MSFA include paths; the
third compiled and exported these constants with the vendor compiler.
These sizes establish neither parallel correctness nor available task headroom.
No parallel implementation or target experiment has been made.

### FM6 copied-kernel adapter — offline development

[verified, source/vendor code] Whole-voice asynchronous rendering would expose
mutable frequency and pitch-envelope rate globals to late jobs. The operator
kernel reads the lifetime-static sine table, copied parameters and feedback,
and private FmCore scratch instead. A private host experiment compared 512
independent jobs, each 128 blocks, across all 32 algorithms and eight feedback
settings: concurrent PCM hashes, final PCM, parameters and feedback match
sequential execution. The host scratch/job total is 904 bytes. This does not
establish CPU1 timing, coherence or available task memory.

[verified, vendor code] A standalone acquire-load/release-store probe with the
pinned vendor compiler emits runtime calls, despite reporting 32-bit atomics
lock-free. The runtime helpers call `__rt_local_irq_disable/enable`; the linked
SDK implementation disables local interrupts and takes the global `bt_lock`
with an unbounded testset loop. They are unsuitable for a bounded audio wait.
SDK semaphore wakeup is available; its tick-based wait is too coarse for the
audio deadline. The verification ladder's CPU1 publication/coherence and pinning
cases remain required. No new device traffic or CPU1 test has occurred.

[implemented, offline only] FM6 now offers an opt-in copied-kernel pair adapter.
Preparation remains on the parent audio task, each envelope advances once,
and gain/mixing/retirement retain ascending voice order. The adapter receives
copies without engine pointers. A rejected result is discarded, and sequential
fallback uses the already prepared live parameters. Backends must complete
within a bound and stop accessing the call's jobs before returning; any late
work must own independent storage. The default has no adapter attached.
The focused native suite passed all 155 tests, including 12 new differential
cases at 16385/44118/96000/384000 Hz for concurrent, partially computed rejected,
and stalled jobs released after engine destruction. Initial build access and
unsupported 8 kHz test setup errors were fixed before that successful rerun.
The same 12 cases passed ASan+UBSan, including releasing a stalled copied job
only after destroying and freeing its engine. Full prepared keys and mixed
replays retain their prior PCM SHA-256 values (b62e14e1… and c676e9b4…).
The private vendor build passes: Instance grows from 16188 to 16192 bytes;
RenderPair reserves 772 bytes plus 52 bytes of saved registers. This is static
code-generation evidence, not measured target stack headroom. No backend is
attached, and no new image has been admitted or installed.

The rebuilt default browser module (SHA-256 a09698b1…) passes all 108 parity
cases and a 30-second edit storm with zero late quanta. A subsequent desktop
harness-only null-allocation check changes the broad engine provenance hash;
the module predates that test-only edit, while its simulator hash still matches.
The prior pushed fc4476fa CI run 40209299831 finished with all 13 jobs passing;
its Pages build succeeded, deployment skipped for the feature branch.
The board remains on 49ef, with its deadline failures; no adapter speedup,
DAC/KA6 or soak acceptance is claimed. PR155 remains draft and unmerged.

### CPU1 short publication/pinning probe — offline only

[implemented, not hardware accepted] A separate diagnostic requests
`#C0lunar_parent` and `#C1lunar_worker`, preserving UART-first reservation and
a 200-tick recovery window. It exchanges 64 sequence-tagged words in both
directions 4096 times, checks actual core IDs and both stack high-water marks,
and bounds each poll with the checked 24 MHz timer. Mailbox and task storage
remain allocated after failure; nothing is cancelled or reused. It produces
no audio and performs no flash operation. This is a target-specific volatile
SRAM plus `csync` experiment, not a portable C atomics implementation.

[verified, offline] The pinned vendor build succeeds. Reviewed generated code
uses aligned word loads/stores, `csync` before publication and after observing
a flag, direct `cnum` reads and timer-bounded polls; no atomic runtime helper
is called by the exchange. Preparation and result-rejection checks pass 17
focused tests, including wrong-core, corrupted, incomplete and timed-out
receipts. The first preparation test exposed an old resampler/control-mode
expectation in the shared fixture; that expectation now includes the new UART
probe mode. Mac Python environments lack pytest; these checks ran in a bounded
Aeon container. No image is packaged, admitted or installed. A passing short
probe would still leave the ladder's long coherence, FPU, ring, real renderer,
underrun, DAC/KA6 and sustained analog soak gates outstanding.

[verified, offline admission] The final short CPU1 probe build has ELF SHA-256
`eacb70e7ba2944fec4df84b029a21e103d5582cc7d6aec892736774ef8a6e3a0`;
independent vendor objcopy of all five load sections matches the 163984-byte
app `f8a989e65683357a157c9b111c2545129d48578bec488bef856687dd9e98d3b0`.
The private factory-based candidate is
`9d3d4f8c46ddf3a0edb3fce6abd5a7482a257f82c3b798ba87ec5460bce9f761`.
Only 41 sectors, 0x4000 through 0x2c000 inclusive, differ; the protected boot
prefix and tail remain factory-identical. Independent cipher derivation,
metadata/app CRCs and exact NOR install/restore pass. Injected interruptions
at pages 7/327/631/647 each restore the full factory image.

[verified, generated code] The final image reserves UART recovery before the
parent task, preserves the 200-tick window, and uses the reviewed aligned
SRAM/csync exchange. SDK dormant-key routines, local IRQ/P33 helpers and the
complete ROM-entry marker routine match the installed image after normalizing
only individually checked symbol/call relocations. The link audit reports zero
failures and one scheduling item, resolved by that exact vendor-instruction
comparison; no forbidden key symbols, SDK key blob, IRQ123 vector use or eFuse
SFR access is found. Pretask heap is 491788 bytes; mailbox is 576 bytes aligned
to 64. This is static layout evidence, not measured target stack/heap acceptance.

The exact probe hash now has its own narrow transaction plan. The existing
49ef renderer restore range remains 137 sectors and must be used to remove
that currently installed image before installing this smaller probe. All 116
focused transaction/reset/probe/preparation checks pass in a bounded Aeon
container. An initial audit CLI invocation omitted the JSON output argument;
the corrected invocation produced the audit above. No device operation occurred.
The candidate is admitted offline only, not installed or hardware accepted.

### CPU1 short publication/pinning — hardware result, 2026-10-25

[verified, dev board only] Image 9d3d4f8c… completed the button-free recovery
cycle. Fresh UART PING/ARM/ENTER preceded a fresh WL82/UBOOT1.00 inquiry and
matching full current-image backups. The installed renderer's full 137-sector
restore produced the exact factory image. The new probe's full installation
readback matched; its fresh startup ready marker and three acknowledgments
completed in 77.784 ms. A new ROM inquiry and two complete 8 MiB probe backups
matched. Restoring its 41-sector plan again reproduced the full factory image;
reinstalling the identical probe again matched all 8 MiB before the single run
reset. Every reset receipt is consumed and must not be retried.

[verified, target UART] All 4096 bidirectional 64-word exchanges pass with zero
errors, abort=0 and exited=1. Parent core counts are 4096/0/0; worker counts are
0/4096/0 for CPU0/CPU1/other. The 10-tick timer check reads 2400058; the exchange
run takes 3820414 ticks (159.184 ms at the checked 24 MHz timer, including
intentional task yields). Unused stack is 994/1024 words on the worker and
1935/2048 on the parent. These are short-probe measurements, not renderer
stack or audio deadlines. The exact RX process identity was verified twice,
terminated and observed terminal before ordinary post-run PING acknowledged.
The board remains healthy idle on 9d3d4f8c; no capture remains live.

Private UART SHA-256:
`87d92152b2c6525604409fd5585f3769169f678fa30cbede547bba25f8f54973`.
The first parse rejected SDK timestamp prefixes. The parser now strips only
the exact SDK timestamp syntax before applying unchanged strict receipt checks;
the saved raw capture then passes, without another hardware run. Timestamped,
corrupted, duplicated and quoted receipt regressions pass 17 focused checks.
The short probe does not satisfy long coherence, FPU, SPSC ring, actual renderer,
underrun/DAC/KA6 or representative 30-minute analog soak acceptance.

### Long CPU1 publication comparison — offline development

[implemented, not admitted] A separate probe exchanges one sequence-tagged
word 100 million times without a fence, then 100 million times with `csync`.
Unfenced data errors are recorded as comparison evidence, never permission to
omit fences; fenced errors fail the gate. Both phases require full completion
and unchanged CPU0/CPU1 pinning. Each wait is limited to one second; a checked
24 MHz timer imposes a 160-second total bound, below its 178.96-second wrap.
Both tasks yield every 65536 exchanges, retain permanent mailbox/task storage,
and leave the timer running after failure while a late worker might read it.
UART reservation and the 200-tick recovery window remain ahead of the workload.
This performs no audio or flash operation and does not replace FPU/ring/audio
acceptance. The default preparer still builds the short probe; the new mode is
explicit `--long-publication` and records exact source hashes and bounds.

[verified, offline] The long mode's preparation and result-rejection tests pass
in a bounded Aeon container, including incomplete, migrated, corrupted,
duplicated, malformed, timed-out and mismatched phase/completion receipts.
The pinned vendor build succeeds with the downloader disabled. Exact generated
code, complete image/recovery/cipher/NOR review and hardware admission remain
pending; no candidate has been packaged or installed. The board remains healthy
idle on the short probe image 9d3d4f8c, with no capture live.

[verified, offline admission] Long probe ELF SHA-256 is
`025158eee554fd2c60aafb58701783b1cb9a08d6681ab1b54976acb9351ee581`;
the independent five-section vendor objcopy matches app
`da8f16aae877ccd6b7aec91128a1d3fc415ae907184799fc407bcb4db3be8db1`
(164496 bytes). The exact factory-based candidate is
`3bbfa865e5c3fd37c8babe9f01c9fe7e6d56f7d41e211488e26b57d71a8a5c23`.
It changes 41 sectors (0x4000..0x2c000 inclusive), with app end 0x2c3b0;
protected bytes, independent cipher derivation and all metadata/app CRCs pass.
The NOR model passes exact install/restore and interrupted pages 7/327/631/647,
with metadata committed last. All 135 focused transaction/reset/short/long
receipt/preparation checks pass in a bounded Aeon container.

[verified, generated code] Both tasks use aligned word accesses and actual
core-ID reads. The first exchange loop has no `csync`; the second fences both
publication and consumption. Generated loops contain the checked 23999999
per-wait and 3839999999 total tick thresholds, plus bounded exit waits and
periodic task yields. No atomic runtime helper or testset loop appears in the
exchange. The final prepared UART-first main hash is identical to the accepted
short image. SDK dormant-key scheduling and complete ROM/P33 helpers again
match after checked relocations; the link audit has zero failures, with its
scheduling item covered by that comparison. Pretask heap is 492300 bytes and
the permanent mailbox is 64-byte aligned/64 bytes. These are offline findings;
actual task stack, run duration and publication results remain unverified.
The exact hash is admitted with the existing narrow CPU1 sector plan. It is
not installed or hardware accepted; the board remains healthy on 9d3d4f8c.

### Full CI metadata example repair — 2026-10-25

[verified] Exact-head CI 40214119758 Linux job 121231670813 finished with
5565 passed and one failure: the metadata example retained meta_id 7b8200b9,
while the actual full build exports a077a566 following the FM6 instance change.
Regenerating the same subset from that build's `fm1-render --meta` changed only
`meta_id`; the example and assertion remain otherwise unchanged. The schema,
engine metadata and editor metadata checks pass 25 tests with one skip in a
bounded Aeon container. An initial command named a nonexistent test file and
collected no tests; the corrected command produced these results. This repairs
an example, not hardware timing or audio acceptance. Current candidate3bb bytes
and startup recovery review are unaffected.

### Long CPU1 publication comparison — hardware result, 2026-10-25

[verified] Candidate 3bbfa865 completed the UART-only WINDOW/RUN cycle.
Fresh startup PING/ARM/ENTER acknowledged within 77.947 ms, followed by a
fresh WL82/UBOOT1.00 inquiry. Both full 8 MiB new-image backups match 3bbfa865;
factory restore matches 127b2ebb, and the same candidate's RUN installation and
full readback match. Both reset attempts were consumed once; neither was retried.

[verified] The strict result parser accepts both 100,000,000-exchange phases.
Parent and worker report zero data errors in both unfenced and fenced phases,
abort=0, exited=1. Parent CPU0 count is 200,000,000 and worker CPU1 count is
200,000,000; opposite/other core counts are zero. Timer calibration is 2,400,021
ticks per ten OS ticks. Total run takes 2,923,701,675 ticks, or 121.821 seconds
at 24 MHz, including deliberate yields. Unused stack is 994/1024 worker words
and 1929/2048 parent words. The unfenced comparison does not authorize removing
`csync`. The exact RX process identity was checked twice before termination;
its session became terminal before ordinary post-run PING acknowledged.
The board is healthy idle on 3bbfa865 and no capture remains live.

Private raw UART SHA-256:
`76a9f64549977b79a5fac39389aa32a54aec9e1598fdf05e38e5da2cb6d4f6a7`.
This establishes only this publication/pinning experiment, not FPU/IRQ behavior,
SPSC streaming, renderer deadlines, DAC continuity or analog soak acceptance.
The installed actual renderer's deadline failures remain unresolved.

### Finite per-task arithmetic and paced SRAM ring — offline prototype

[implemented, not admitted] A separate `--paced-ring` mode reuses the finite
arithmetic probe on CPU0/CPU1, checking exact results and recording batch times.
It then sends 413607 sequence-tagged 64-word CRC blocks through a 16-slot SPSC
ring, with deterministic sample verification. Fractional timer carry preserves
44118 frames/s over 600.001088 seconds. Publication and reuse use target-specific
volatile accesses and `csync`, not a portable C atomic claim. The whole run has
a 625 s millisecond-clock bound, individual waits one second; permanent state
and timer remain valid after failure. All 72 focused prep/result-gate checks
pass in a bounded Aeon container, including corrupted, incomplete, migrated,
late, out-of-duration and mismatched arithmetic receipts. The vendor build and
exact code review remain pending; no candidate is packaged/admitted/installed.
No IRQ or floating exception probes are added; this does not satisfy full C3,
renderer, DAC or analog acceptance. Board3bb remains healthy idle after its
long publication probe, with no capture live.

[verified, offline] The initial vendor link failed because appending a C source
variable after immediate object-list expansion did not link the arithmetic
object. Preparation now inserts its exact SDK-relative path into the original
source list, before expansion. The corrected v2 vendor build passes with the
downloader disabled. All 106 short/long/ring receipt and preparation checks
pass. Exact generated clock/loop/SDK/recovery review remains pending; no candidate
has been packaged, admitted, staged or installed.

[verified, offline review] Final ring probe v3 names its permanent mailbox
`cpu1_ring` so it cannot be confused with a different SDK-local `state` symbol.
ELF SHA-256 is 10a1a1f179d4c07ccc122ade0d336069c6f5bec0ebef1400d5254b46211c8d3c;
independent five-section vendor objcopy matches the 165584-byte app
ce80d73ac4f543880c85440e2294e09c38bfcd67d82e1d8d621a9bc11826c1ea.
Pretask heap is 487756 bytes; mailbox is 4544 bytes at aligned SRAM 0x1c04a40.
The exact UART-first main hash matches the previously accepted main. Generated
pacing uses 34815 ticks plus the 31830/44118 fractional carry; the short signed
timer differences survive timer wrap. The overall timer_get_ms call is a direct
jiffies load times ten, with no lock. Generated loops retain 625000 ms total
and one-second waits, core reads and publication/slot-reuse fences. SDK dormant
key scheduling and complete ROM/P33 helpers match after verified relocations;
audit_link reports zero failures, its one scheduling item covered by that exact
comparison. Finite division operands remain nonzero, and no IRQ is installed.

[verified, offline packaging] Exact candidate SHA-256 is
0fd1dcb5ff74bf036f2c785144745bf2fe6254587a73b86bec4d3396fb9dfd09.
The 41 application sectors end at 0x2c7f0. Protected bytes, independent cipher
key derivation, metadata/app CRCs and independent app export pass. The NOR model
passes install/restore with metadata last and injected interruptions at pages
7/327/631/647 followed by exact factory restore. No hardware commands were sent
by these checks. The exact hash is admitted offline using the existing narrow
sector plan; it is not staged, installed or hardware accepted. Full target
stack/pacing/FPU results and audio acceptance remain unverified.

[verified] Final exact-source transaction/reset/preparation/short/long/ring
receipt checks pass 164 tests in a bounded Aeon container. An initial invocation
used a nonexistent reset-test filename and collected no tests; the corrected
command used test_devkit_loader_reset.py and produced the 164-test result.

### Bounded copied FM6 job handoff — offline only, 2026-10-25

[implemented, offline] A permanent, 64-byte-aligned mailbox copies the second
prepared FM6 job into its own storage before publishing a request. CPU0 computes
the first job; CPU1 computes only the private copy. Import requires completion
inside the total clock budget. Rejection/timeout disables all future submission,
leaving storage valid for a late worker. A finite poll cap also handles a frozen
clock. There is no cancellation, reinitialization, engine pointer or task/device
operation. Default engine behavior is unchanged; no SDK attachment exists.

[verified, host] The mailbox fault test and all 16 copied-kernel differential
cases pass (17 checks), including the new real two-thread mailbox mode at
16385/44118/96000/384000 Hz. PCM remains exact through live edits, release tails,
detach and instance destruction. Host atomic flags test protocol ownership;
they do not verify the target's volatile/csync memory semantics.

[verified, object only] The pi32v2 r3 vendor compiler accepts the C++11 prototype
at O2 without exceptions/RTTI. Generated methods retain copy-before-request,
completion-after-result fences, the unsigned elapsed-time bound and one-million
poll cap, with no atomic library helper. This is an unlinked object, not a
reviewed ELF/image, target performance result or hardware admission. Initial
objdump invocation used unsupported combined -dr; corrected -d disassembly is
private. A sanitizer invocation initially requested a partial-module test target
without all its existing link dependencies; the corrected full ASan/UBSan build
passes the real mailbox mode at 44118 Hz (2533 pairs), with no sanitizer report.

[verified, CI investigation] Head bc0a801b CI40216326749 Chromium job121238387512
fails sequencer-ui.mjs133, inspector focus, with no page errors. Actual completed
job logs were inspected via the jobs API while other jobs were still running.
The unchanged exact test passes an isolated Chromium reproduction. A private
forced refresh(true) then deterministically reproduces lost inspector focus:
the Close button has no aria-label, so the existing label-based focus restorer
cannot find its replacement. Adding the same accessible label preserves focus.
The permanent browser test now forces a refresh and asserts focus remains;
all original assertions remain. Chromium, Firefox and WebKit focused tests
pass in bounded Aeon containers. This proves the redraw repair, not that the
original intermittent opening failure has necessarily the same trigger.
Pages40216326782 succeeded; PR155 remains draft/unmerged.

### Paced CPU1 ring — hardware data pass, pacing FAIL, 2026-10-25

[verified] Exact candidate 0fd1dcb5 completes the UART-only WINDOW/RUN cycle.
Fresh startup ready and PING/ARM/ENTER acknowledge within 77.917 ms; a fresh
WL82/UBOOT1.00 inquiry and two full matching 8 MiB new-image backups follow.
The intervening factory restore matches 127b2ebb, and the same candidate's RUN
installation/full readback match. Each reset was invoked once and consumed.

[verified] All four finite arithmetic results match CPU0/CPU1. The SRAM ring
completes/consumes all 413607 blocks in 600010 ms, with zero CRC/data/sequence
errors, abort=0, exited=1. Parent CPU0 and worker CPU1 counts are each 413607;
opposite/other counts are zero. Peak queue depth is two; unused stack is
972/1024 worker words and 1922/2048 parent words.

[verified, FAIL] There are 2784 late producer blocks. Maximum publication lag
is 50028 ticks (2084.5 microseconds), exceeding the 34815-tick block period.
The unchanged strict parser rejects the result. Correct data and finite FPU
parity do not turn this into a timing or audio pass. No DAC/KA6 capture ran.
The exact RX identity was checked twice, terminated, and its session became
terminal before ordinary post-run PING acknowledged. Board0fd is healthy idle.
Private raw UART SHA-256:
81cf3fa4d2103531cfa132b8fe2169a2c99551813682e7f5a3a023d545995999.

[inferred, unresolved] Parent scheduling, shared XIP/cache contention and the
bitwise CRC's own cost are candidates for the publication delay. This receipt
does not attribute it to any one of them. Measure pre-compute lag and compute
cost separately before claiming a cause; do not weaken the ring acceptance gate.
The actual shared renderer's deadline failures and all analog acceptance gates
remain open. The copied-job mailbox is still an offline prototype.

### Ring phase measurements — offline admission, 2026-10-25

[implemented] The paced ring reports pre-compute lag and producer/worker sample
and CRC wall-time totals/maxima, plus the start/compute times of the worst
publication block. Numeric output occurs after the bounded run. These intervals
include interrupt/preemption time; they cannot by themselves identify an SDK
scheduler, cache or CRC cause. Rates, workload, fences and strict pacing gate
are unchanged. Additional statistics follow publication on the producer path.

[verified, exact vendor image] Generated timer reads bracket the complete
64-sample/CRC loops on both cores. The parent start-lag read precedes slot reuse
waiting; compute starts after its fence, so queue waiting is not compute time.
The parent end read follows CRC storage and precedes publication. The generated
625000 ms total and one-second waits, core reads and recovery window remain.
App SHA-256 is 67db08a689f9ed76bae9e7f8deb06bebe5ece875a39eb4ddb733e5c857979e05
(166160 bytes); independent five-section vendor objcopy matches. SDK/ROM/P33
relocation comparison and UART-first prepared main match the accepted baseline.
Pretask heap is 487692 bytes, permanent mailbox 4608 bytes aligned to 64.

[verified, offline packaging] Candidate SHA-256 is
43b911a84f17e0045e911249c495f967cc42087c33a996f87080c6e4d44b0455.
The same 41 sectors contain the changed app through 0x2ca30. Independent cipher
key derivation, app/metadata CRCs and protected bytes pass. The NOR model passes
exact install/restore, metadata last, and interrupted pages 7/327/631/647 with
exact factory restoration. No hardware operation is part of those checks.
It is admitted offline only; no new installation or hardware acceptance yet.

[verified] Final transaction/reset/preparation/short/long/ring checks pass
165 tests in a bounded Aeon container, including a regression proving the
phase row cannot override a failed pacing receipt. The first test invocation
mounted the wrong parent for the private pytest libraries and collected no
tests; the corrected parent mount produced the passing result.

### Permanent FM6 C bridge — offline only, 2026-10-25

[implemented] A C-callable, one-time initializer constructs the copied-job
mailbox in aligned permanent storage, with an immutable adapter and separate
worker step. Invalid bounds and every reinitialization attempt are refused.
There is no heap allocation, global constructor, SDK task creation, renderer
attachment or device operation. Getters are audio-owner only; initialization
must finish before the worker starts. No current diagnostic image includes it.

[verified, host] All 18 mailbox fault/lifecycle and actual kernel differential
checks pass. A new bridge test covers refusal before initialization, repeated
initialization, successful result import, permanent timeout, late completion
after caller storage reuse, and unchanged adapter lifetime. That exact test
also passes ASan/UBSan without reports. Prior mailbox two-thread PCM coverage
remains part of the 18-check run.

[verified, object only] The pi32v2 r3 O2 C++11 object contains 448-byte mailbox
storage and no initializer/constructor section. Its only undefined symbols are
mailbox constructor/RenderPair/WorkerStep; there is no allocator or guard helper.
Generated init validates bounds and stores the mailbox pointer after construction.
The first compile omitted the SDK C++ include paths and failed on <new>; the
corrected SDK-header compile passes. Objdump relocation names are Unknown in
this object, so symbol-table inspection checked dependencies independently.
This is not final linked layout, target ABI/performance, task readiness or
hardware acceptance. Rarefaction still indexes the primary checkout rather than
this worktree; Serena diagnostics resolve this actual worktree but lack its
engine include path. File inspection plus actual vendor/host compiles cover
this bounded change, not an assertion of complete language-server coverage.

### Ring phase measurements — hardware pacing FAIL, 2026-10-25

[verified] Candidate 43b911a8 completed its UART-only WINDOW/RUN cycle. Fresh
startup ready and PING/ARM/ENTER completed within 77.808 ms. Fresh ROM inquiry,
two full matching new-image backups, factory restore and same-image installation
with full readback passed. Both reset receipts were consumed once.

[verified] All 413607 blocks completed and were consumed in 600010 ms, with
zero CRC/data/sequence errors, abort=0 and exited=1. Every producer block ran on
CPU0 and every worker block on CPU1; peak depth was two. Unused stack was
968/1024 worker words and 1911/2048 parent words. Four finite arithmetic rows
matched across cores.

[verified, FAIL] The unchanged strict parser rejected 2780 late blocks, with
maximum publication lag 50064 ticks. Producer mean measured work was 44.302592
microseconds, maximum 50058 ticks (2085.75 microseconds); worker mean was
43.406808 microseconds, maximum 1341 ticks (55.875 microseconds). The worst
producer block started only two ticks late, so that delay occurred inside its
measured work interval. Maximum pre-compute start lag was also 48944 ticks.
These are wall intervals including preemption/interrupt/cache stalls; the
receipt does not identify the cause. Task pacing failure is not proof of DAC
IRQ failure, and intact data is not audio acceptance. No DAC/KA6 capture ran.

[verified] The exact RX process identity was checked twice, terminated and its
session became terminal before ordinary post-run PING acknowledged. Board43b9
is healthy idle. Private UART SHA-256:
5ab5798b47fa753bd3e54a39331dbae69f8e95e2565e36fd6c66f9f1ccae0184.
The actual shared renderer's deadline failures and all analog acceptance remain
open. Do not weaken the ring gate or claim a scheduling cause from these data.

### Shared renderer copied-kernel attachment — WIP offline, 2026-10-25

[implemented, not admitted] The diagnostic accepts an immutable FM6 adapter
before initialization only and attaches it only to selected DX7 instances.
The default remains sequential. An optional timing-only SDK wrapper reserves
CPU1 before renderer allocation, bounds readiness/shutdown to one second and
lifetime to 120 seconds, and reports completed pairs, fallback, core placement
and stack. Pair timeout retains the original 34829-tick block budget. The
parent retains the timer on failed startup/shutdown; UART recovery allocation
and its 200-tick window still precede this work. No new image is installed.

[verified, host] Mixed and keys shared-renderer replays preserve every PCM
byte through an actual two-thread copied mailbox, synchronous adapter, and
copy-corrupting refusal/fallback. Initialization refuses an invalid adapter
and changes after successful initialization. SDK task mocks exercise normal
exit, wrong core, allocation failure, missing readiness, lifetime expiry and
disabled backend. Focused renderer/mailbox/lifecycle run: 51 pass, one skip
(the container lacks multilib for the smaller target-pool replay). Host
atomics in the test translation do not verify target fences or timing.

[WIP vendor check] A new exact build first refused an existing output folder;
that evidence was preserved and a unique v2 folder used. Compilation found
GNU asm in SDK headers incompatible with the nested renderer's strict C99.
Only the SDK wrapper now requests GNU C99; shared DSP flags stay unchanged.
The correction awaits vendor verification. Final exact code/layout/UART-first,
PCM/stack/performance, packaging/NOR and hardware gates remain outstanding.

### Finite FM6 attachment exact image review — 2026-10-25

[verified, offline] Final focused renderer/mailbox/lifecycle checks: 54 pass,
one multilib skip. SDK GNU99 correction links successfully. The final shutdown
requires worker job count to equal accepted pair count, with no disabled backend
or wrong-core/error receipt. New objects track their header dependencies.

[verified, offline] Final ELF SHA-256
`d0bb533be3d8949fdcabd21ff2737e25aa63045a4f53fa8c05d7794f2695c741`;
independent five-section export matches app SHA-256
`a8b8a3b88b6be5041ff6a035d141533119a318e453ea262c22a6f4f2985d74f2`.
The 562556-byte app preserves relocated SDK key-check/ROM routines and the
UART-first 200-tick window. The vendor machine code retains fences, 34829-tick
pair budget, million-poll bound, finite worker lifetime and final count equality.
The kernel call graph has no allocator or mutable global-rate setup; its final
code matches the prior review except a checked relocation of the memset call.
Pretask heap is 47916 bytes; the permanent mailbox is 448 bytes aligned to 64.
Target heap/stack headroom remains unmeasured and is an acceptance gate.

[verified, offline] Candidate SHA-256
`393f497566bf1ee9b709bdbd67adec23ecb0f216809afd632dffc66adfe7534a`
changes exactly 138 sectors in `[0x4000,0x8e000)`. Independent cipher/CRC and
protected-region checks pass. NOR model install/restore is exact, metadata is
last, and interruptions at pages 7, 1111, 2183 and 2199 restore exactly.
No hardware acceptance or analog result follows from this review. Board43b9
remains healthy idle; the next cycle must prove fresh double backups, factory
restore, unique startup-window verification, then same-image run readback.

### FM6 attachment allocation refusal and static SDK storage — 2026-10-25

[verified, hardware] Image393f passed startup ready/PING/ARM/ENTER in
78.0683 ms, fresh ROM inquiry, two matching full backups, factory restore,
same-image install/readback and a single run reset. All four arithmetic rows
pass. Before renderer initialization the heap reports total 47916, free 5972;
the SDK then refuses the requested 4096-byte worker stack, reports null stack
and create status -1. No renderer timing or pair-count result was produced.
Total free heap is not proof of a contiguous available stack allocation.

[verified] The failure path retains UART recovery; after exact owned RX closure
and terminal session, ordinary PING acknowledges. No physical recovery needed.
Raw capture SHA-256
`e1ce2452db098e46e9d9e929c170d929ffb8e6e0af3ff1c648a17a6b7e53c529`.
WINDOW and RUN receipts are consumed and must never be retried.

[implemented, verified offline] Use the pinned SDK's documented static-task API
instead. Its own zero-queue example specifies aligned TCB-plus-stack storage;
the final linked implementation uses 164 TCB bytes followed by 1024 four-byte
stack words, with no dynamic stack allocation on the zero-queue path. Permanent
storage is 4260 bytes at aligned SRAM 0x1c14580. The original 4 KiB stack,
CPU1 pin, priority, pair deadline and lifetime/exit guards remain unchanged.
All six host lifecycle modes pass; mocks do not verify target ABI or timing.

[verified, offline] ELF SHA-256
`59ed95d77dcf697025e6b37b9f4d32cded8d4359f5d221219bb7aa419b0653d9`,
app SHA-256 `56fc543cf0d8f00ebdce28c95ee64ad947d094675d7fb029716b2b5a4767738f`,
candidate SHA-256
`afdc2fa73bc27aff9ade73f8e10cb1ecdaa1d9e2c1f6e0e693d423af16fe322a`.
Exact SDK/ROM checks, five-section independent export, cipher/CRC and the
138-sector NOR model pass, including the same four interrupted-page restores.
Only the wrapper source input changed; prepared app_main/link script and the
200-tick window are unchanged. Kernel code differs only in a checked memset
call relocation. Pretask heap is now 43628 bytes; estimated remaining boot
heap is only 1684 bytes if allocations are unchanged. Startup recovery, actual
heap/stack headroom and renderer timing remain mandatory target gates.

### Keys arena capacity and parent allocation — 2026-10-25

[verified, hardware] Imageafdc proves fresh UART ready/PING/ARM/ENTER in
77.028 ms, but its 8192-byte parent stack allocation fails. No parent recovery
window, renderer timing or pair work ran. The board returned to ROM; fresh
ROM inquiry and two matching complete current-image backups pass. Both reset
receipts remain consumed.

[implemented, verified offline] The finite keys diagnostic now reserves 96 KiB
for its renderer, versus 136 KiB previously. All prior target keys cases use
86896 bytes, leaving 11408 bytes margin; initialization still checks capacity.
Mixed remains unchanged. Stack sizes, instruments, rates, quality and order
are unchanged. Full host renderer checks pass: 51 tests, one missing-multilib
skip, including pinned four keys hashes, full two-thread PCM, synchronous and
refusal fallback, and mixed replay.

[verified, offline] Final ELF SHA-256
`f9387def164e6ef1a286fd50a5e63efc8a5abe247d91ddb80d0e376cb0278de6`,
independent app SHA-256
`95da0ef4d79bd0bc691f1fe162e9d4a34f743746d6d02e1e5c432c816d1e83b5`,
candidate SHA-256
`718f09c30e9b4efe8fdf226926a3d0701bcab37609dbc4e2dbec7857f5580d25`.
Exact SDK/ROM, UART-first parent window, static worker layout and kernel
review pass. Kernel changes are checked memset-call and immutable algorithm-
table address relocations; table bytes match. Pretask heap rises to 84588 bytes.
Independent cipher/CRC and 138-sector NOR install/restore pass, including
interruptions at pages 7, 1111, 2183 and 2199. Hardware startup, both stack
headrooms, pair completion and renderer deadlines remain unaccepted.

### First copied FM6 hardware run: fallback intact, acceptance failed

[verified, hardware] Image718f passed startup three-ACK recovery in 78.1083 ms,
fresh ROM inquiry, two matching full backups, factory restore and same-image
install/readback. The parent task now starts; the run observes the 200-tick
window, four arithmetic checks, CPU0 parent and CPU1 worker placement.
Heap remains 42644 bytes; arena is 86912. Parent stack retains 2644 of 8192
bytes and worker stack retains 3260 of 4096 bytes.

[verified] All four PCM hashes match; 32 unit and 24 stage rows are complete.
The pair backend nevertheless disables during case 0 after 5393 accepted pairs;
worker jobs reach 5394, with zero wrong-core/error counters and exit acknowledged.
The final pair-equality gate correctly refuses completion. Means are
1270.292 / 1514.417 / 1643.917 / 1860.750 us, late counts
183 / 3755 / 5263 / 5505 of 5513: FAIL, not an audio-acceptance result.
The existing boolean does not identify deadline, poll-bound or kernel-refusal
cause. Do not infer a worker crash from one unaccepted result.

[verified] Exact owned RX closure and terminal session precede ordinary PING ACK;
the board is healthy idle. Both resets are consumed. Private raw SHA-256
`7bbae3b519acdb307a50ebc0f76f1d7994ddb181cd8b55655aad965d9aef4b72`.

[implemented, offline only] Add CPU0-owned first-failure diagnostics: reason,
request/completion sequence, elapsed ticks, poll count and first observed ticks
after caller computation. This uses existing clock reads and retains the total
deadline, poll bound, permanent disable and fallback. No new image is admitted
by this source change. Rarefaction still cannot resolve the external worktree;
Serena sees bridge functions but not the mailbox method. Source and actual
builds remain necessary for this target and its ABI.

[verified, host] Refusal fault and SDK lifecycle tests plus renderer checks:
54 pass, one missing-multilib skip. The initial mixed replay build failed
because its reused ignored build directory was root-owned. Correcting that
exact directory's ownership and rerunning the affected mixed PCM check passes.
Keys full PCM and fallback also pass; no target timing follows from host tests.

[verified, offline] Refusal-diagnostic ELF SHA-256
`ef66cf27e679043149980a3df0851defaf729e418d804564a5d22e38254e5053`,
app SHA-256 `04c5180f1a4081a404fc5c050bd98cf81ab5234ebca55630510c7a828a3a031d`,
candidate SHA-256
`b2b3ab557b788b6c8e500755e41be47db14986ed5aa6dfd6681c4aefd611f983`.
Independent section export/cipher/CRC and the 138-sector interrupted NOR model
pass. Exact linked SDK/ROM routines, UART-first creation and 200-tick window,
static 448-byte mailbox and 4260-byte worker storage are retained; pretask
heap remains 84588. Machine code preserves the total deadline, million-poll
bound, fences, finite lifetime and final equality refusal. Kernel bytes match
after checked memset relocation and pointer-plus-offset algorithm-table
relocations; immutable table bytes match. Hardware acceptance remains open.

### First-refusal evidence: elapsed before polling, CPU1 already done

[verified, hardware] Imageb2b3 passes startup three-ACK recovery in 78.0964 ms,
fresh ROM inquiry, two matching full backups, factory restore and same-image
install/readback. Actual run passes the 200-tick window, four arithmetic and
PCM checks, 32 unit and 24 stage rows. Heap remains 42644 bytes, arena 86912;
parent retains 2620/8192 stack bytes, worker 3260/4096.

[verified] The first refusal is reason 2 (total deadline), elapsed and first
sample both 50218 ticks (2092.417 us), zero wait polls, request 514 and done 514.
CPU1 completion was visible at CPU0's first post-compute check. This excludes
waiting for an unfinished CPU1 job as this refusal's immediate cause, but does
not distinguish publication/copy, caller computation, preemption or stalls.
Do not label it a worker crash or claim a precise stall cause without evidence.

[verified] Accepted pairs 513 versus worker jobs 514, disabled 1, zero wrong-core
and worker-error counters, exited 1; final completion correctly refuses.
Means 1302.750 / 1513.292 / 1644.083 / 1858.125 us; late
255 / 3664 / 5291 / 5506 of 5513: FAIL. No DAC/analog acceptance follows.
Exact owned capture closure and terminal session precede ordinary PING ACK.
Board healthy idle; all reset receipts consumed. Private raw SHA-256
`8bd53f29c3656a60778c65710f8940b47e22792d57d296c5b8f852385d6beacd`.

[verified, linked SDK] Worker lifetime check `timer_get_ms` is a 14-byte routine
that reads jiffies and multiplies by ten, with no lock. It does not establish
a locking explanation for the CPU0 delay. Next investigate documented CPU/task
timing facilities before changing scheduling or DSP behavior.

### Scheduling comparison prepared after coarse SDK statistics review

[verified, offline] Pinned system.a IR and linked task initializer/scheduler show
unmodified task priorities feeding ready-list selection, highest ready priority
first. Runtime-statistics declarations alone are unsuitable for per-block
measurement: ulGetRunTimeCounterValue uses timer_get_ms, while vTaskGetInfo
reads a 16-bit task counter and resets it to one. Private vendor IR stays ignored.
Several unrelated v7 stages have maxima about 48000 ticks above ordinary work;
this suggests a shared interruption/stall but does not establish its cause.

[implemented, not admitted] An explicit --scheduling-probe requires the finite
profiled hot timing-only FM6 experiment. Parent/CPU1 priorities become 16,
above SDK app_core 15 and systimer 14; UART becomes 18, above both render tasks.
System-event priority 29, IRQ behavior, 200-tick startup window, cooperative
parent yields, DSP/PCM order, deadline, lifetime and refusal behavior are retained.
Default priorities remain parent/worker 10 and UART 8. This is a causal comparison,
not an accepted audio implementation or permission to weaken the deadline.

[verified, host] 47 focused preparation rejection, startup/failure and worker
lifecycle tests pass, including both default/probe priority configurations and
all six worker fault modes. Vendor v8 build is running; exact image/SDK/kernel,
independent export/cipher/CRC and NOR reviews remain before hardware admission.
Rarefaction cannot resolve this external worktree symbol; Serena locates the
actual preparer and real-source checks supplement the SDK/ABI review.

[verified, offline] Scheduling v8 ELF SHA-256
bbd2843e7e05b497e2f8795377ad76b064d40971340d6cf04c9c669d681dbcc1;
independent app SHA-256
6685b50882bb5cc274adbaf39fa98f8252922cea91da1ce8eeb4754f1919f968;
exact candidate SHA-256
14dd61780bca60ae1ea772cb925a068d7117539f81f4dd0fbccf5a8f9fc1a061.
App 562876 bytes, end 0x8d7dc, same 138 sectors. Pretask heap 84588,
mailbox 448 bytes and worker storage 4260 bytes remain unchanged. Linked
UART-first creation, priorities 18/16/16, 200-tick recovery window, 34829-tick
deadline, million-poll refusal and finite worker exit are inspected. Exact SDK
and ROM routine comparison passes; dormant-key scheduling pending is covered
by checked full-routine relocations. FM6 kernel/table bytes match v7 after
checked readonly table and memset relocations. Independent objcopy app agrees;
reference cipher/CRC and interrupted NOR restore at pages 7/1111/2183/2199 pass.
The image is admitted offline only. Hardware recovery and timing remain untested.

### Scheduling comparison — target result, deadline still fails

[verified, hardware] Exact14dd startup recovery acknowledges PING/ARM/ENTER in
79.1874 ms. Fresh ROM inquiry, two full current backups, factory restore,
WINDOW install/readback, fresh startup recovery, two full new-image backups,
factory restore and SAME RUN install/readback pass. Both reset receipts are
consumed. Four arithmetic and PCM fingerprints match; 32 unit and 24 stage
rows cover every output frame. All 81,308 pairs complete, disabled/error/
wrong-core counts stay zero, and the worker exits with final equality intact.
Heap is stable at 42,644 bytes; unused parent stack is 2,620/8,192 bytes and
worker stack 3,260/4,096 bytes.

| Keys case | Mean us | Max us | Late blocks / 5,513 |
| --- | ---: | ---: | ---: |
| 0 | 1,111.958 | 2,148.250 | 16 |
| 1 | 1,250.875 | 2,039.167 | 169 |
| 2 | 1,332.958 | 2,172.625 | 528 |
| 3 | 1,425.542 | 2,331.208 | 2,176 |

[verified] The earlier roughly 48,000-tick additions to unrelated stage maxima
are absent in this comparison. Scheduling contributes materially, but the
precise offending prior task/stall is not established. The busiest case has
mean sound/insert 1,014.833 us, masters 247.417 us and control/UI 111.625 us;
these are averages, not simultaneous per-block maxima. Deadline acceptance
still FAILS. Mixed, DAC/KA6 and 30-minute analog acceptance remain open.
Capture PID190628 was verified twice before one SIGTERM; terminal capture
session preceded ordinary PING ACK. Board healthy idle. Private raw SHA-256
40ce9e4ed17c1a9d590babe0fc774a42a3c7c45285f21a5f5cde649edc2fc8fc.

### Exact-head CI evidence and focused repairs

[verified] CI40228013436 macOS job121273554215 fails only the keys case-3
fingerprint: Apple replay produces2e91545b versus Linux/target2f409722.
Two local Apple replays reproduce the exact CI rows and identical complete
PCM SHA-256 1cb0ae8884179c3d7265c28d2468e3cbde2f7fc7313a63bf567d0f6af15b6038.
This establishes a platform-build difference, not its exact math/compiler
cause. The regression pins the observed Apple fingerprint separately;
Linux/target expectations, repeatability and profiled equality stay exact.
The exact test body passes on macOS (pytest unavailable locally, body run
with its environment adapter); the actual focused pytest passes on Aeon Linux.

[verified] Chromium job121273554461 fails sequencer-native.mjs229 before
pointer-down, dereferencing a null boundingBox during a resize redraw. The
focused check now waits for measurable geometry before starting the existing
real held-pointer sequence. Connected-target/click/native-state assertions
remain unchanged. Complete sequencer-native Chromium check passes in the
bounded Aeon container against synchronized tracked UI/test sources.

### Correlated worst-block stages — offline diagnostic

[implemented, not admitted] Profiled timing now retains each stage's last
elapsed value from existing observer clock samples. When a new total maximum
appears, it copies the six values and zero-based block index into that case's
result. UART emits the snapshot outside rendering. This distinguishes costs
that coexist on the slowest block from unrelated per-stage maxima; it does
not identify an IRQ or infer that separate maxima may be added. Six diagnostic
stores add overhead, but no new timer samples, logging or DSP changes occur
inside the measured render. Non-profiled builds retain their prior path.

[verified, host] The actual mixed/profile replay retains complete PCM equality.
Renderer and SDK lifecycle checks report 57 passes, one missing 32-bit-runtime
skip. Synthetic timing verifies wraparound, unchanged clock-call/yield counts,
an early slow block followed by later ordinary blocks, and the matching stage
snapshot rather than the last rendered block. Snapshot reset/bounds are checked.
Vendor v9 build is running; no v9 image has been admitted or installed.

[verified, offline admission] Correlated v9 vendor ELF SHA-256
`df2c981558123ed86b235dd11c96f4e3f0d02d23b598e312219e2edfd29724ac`;
independent objcopy app SHA-256
`633181baedfccef80c4fec33b8700da687631d8e58650ed9aedbeed9d1dbba61`;
exact candidate SHA-256
`fd8a5df8a0d10cf2ab7294c69e5f35b9e1717ba1199131e8c02c34097e891309`.
App 563132 bytes ends0x8d8dc, still138 sectors. Pretask heap84556
(32 fewer); static mailbox448 and worker4260 retain their prior addresses.
Whole linked SDK/ROM routines match after checked relocations; link audit has
zero failures and its manually reviewed SDK-scheduling pending item. UART18
is created before parent16, with allocation-failure guard; worker16, 200-tick
recovery, 34829-tick deadline, poll limit and finite exit remain. Profile
stores use existing samples; the worst-block copy follows the closing clock
read. Kernel leaves/table are exact after verified memset and readonly-base
relocations. The table displacement changes5724→5852 and still resolves to
the identical768-byte algorithm table; both config loads retain identical
containing bytes. No such relocation is treated as an arbitrary ignored diff.
Independent cipher/CRC, protected boot/config/tail and interrupted NOR restore
at pages7/1111/2183/2199 pass.66 admission/reset/SDK tests pass. Exact hash
only is admitted at existing138-sector bounds. Not installed/hardware accepted.

### Correlated v9 hardware result — every worst block starts a case

[verified, hardware] Exactfd8a passes WINDOW recovery in78.8572ms, fresh
WL82/UBOOT1.00 inquiry, two matching full new-image backups,138-sector factory
restore and SAME RUN install/readback. Reset receipts are consumed. Four
arithmetic/PCM receipts,32 unit/24 stage rows and24 correlated snapshots pass.
All81308 pairs complete without refusal/error/wrong-core reports; finite worker
exit succeeds. Heap42612 stays stable; parent unused2556/8192 bytes and worker
unused3260/4096 bytes. Exact owned RX was checked twice, terminated once, and
its session was terminal before ordinary PING ACK. Private capture SHA-256
`e7b62d51295cdeaea67818f6bff8d09470e61c037d46505caf7332b6617b077f`.

| Keys case | Mean us | Max us | Late /5513 | Worst block | Outside six stages us |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 |1130.417|2155.167|26|0|497.667|
| 1 |1269.625|2039.667|283|0|407.875|
| 2 |1350.875|2164.208|796|0|460.667|
| 3 |1443.583|2335.458|2435|0|517.833|

[verified] Case3's simultaneous sound/master/UI costs are1331.125/277.917/
177.333us. Worst-block time outside the six stages includes note/control
preparation and output conversion; the exact subregion and preemption share
are not yet measured. This does not justify removing first blocks. Sustained
cost and deadline failure remain, as do mixed, DAC/KA6 and30-minute acceptance.

[implemented, target untested] The shared app now caches each loaded engine's
immutable knob-page count, keyed by engine pointer per unit. Replacement and
empty-slot transitions refresh it; swapping units carries metadata with them.
FM6 imported bank names change no page indices. The six-target walk, per-block
UI sync, render order and audio processing remain. Target storage grows112
bytes. A native regression exercises changed page layout, swap, removal and
reload; actual shared-workload PCM and UI acceptance are the next host checks.

[verified, host] Fresh-output automation, renderer, sequencer and sequencer-UI
checks pass:242 passed,7 skipped (one unavailable32-bit runtime and six absent
Movy reference cases). Actual mixed/profile PCM remains exact. An initial reused
staging build failed with stale objects: dependency files named the old `/src`
root, so app-layout consumers were not rebuilt. A unique extra compile define
selected a fresh output directory and eliminated those ABI-inconsistent objects.
The target cache benefit remains unmeasured; no v10 image is admitted/installed.
Exact prior head e143e27 CI40229750945 passes all13 jobs; Pages40229750897
passes. Both terminal. PR155 remains draft pending hardware/audio acceptance.

[verified, offline admission] Page-cache v10 ELF SHA-256
`f01333b229368f0ee1d9b8755c13f584b00700fef98b15c1cdc997f785bb5095`;
independent objcopy app SHA-256
`c82f7ab6d31d06c22ceb4cb49f8c38a0443be84fce364913477537af9296cc98`;
exact candidate SHA-256
`cc85c192bffa3118f1e4d19b8caec85858d78a43c1790a7bf23abf90ca2fa178`.
App562876 ends0x8d7dc, still138 sectors. Pretask heap84460. Per-unit
layout grows8 bytes; fourteen units add112 bytes. Link placement/alignment
makes the net pretask-heap change96 bytes. Mailbox448 and worker4260 retain
aligned addresses0x1c143c0/0x1c14580. FM6 kernels and complete algorithm table
match v9 after individually verified readonly/config/memset relocations;
table displacement remains5852. Whole SDK/ROM routines pass checked relocation
comparison and audit has zero failures; its SDK scheduling item is covered by
the complete routine comparison. UART18 creation and allocation-failure guard
precede parent16; worker16,200-tick window,34829-tick budget, million-poll bound,
fences and finite lifetime remain. Vendor lock_sound shows the cached engine
comparison and page-count load, with scan/store on replacement. Independent
app export, cipher/CRC and protected boot/config/tail checks pass; NOR138
install/restore and interruptions7/1111/2183/2199 return the exact factory image.
Only the exact candidate is added to existing bounds. Target timing/stack and
physical audio acceptance remain outstanding; not installed yet.

[verified, host]67 admission/reset/SDK lifecycle tests pass for the exact v10
allowlist change. Packaging and model operations sent zero hardware commands.

### Page-cache v10 hardware result

[verified, hardware] Exact cc85 passes startup recovery in78.8873ms, fresh
WL82/UBOOT1.00 inquiry, two matching full new-image backups,138-sector factory
restore and SAME RUN install/readback. Both reset receipts are consumed. All
four arithmetic/PCM receipts,32 unit/24 stage rows and24 correlated worst-block
snapshots pass. All81308 pairs finish with no refusal/error/wrong-core report;
finite worker exit succeeds. Heap42516 stays stable; parent unused2556/8192
bytes and worker unused3260/4096 bytes. The sole RX process was checked twice,
terminated once, and session56855 was terminal before ordinary PING ACK.
Private capture SHA-256
`bb9a2a31eb03fd7928aaae27d78e468148bad978f565ae6cc844833433a96508`.

| Keys case | Mean us | Max us | Late /5513 | Worst block | Outside six stages us |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 |1104.792|2027.333|8|0|494.792|
| 1 |1245.625|2010.167|169|0|412.958|
| 2 |1328.417|2172.708|472|0|465.375|
| 3 |1419.833|2325.417|1987|0|532.333|

[verified] Means improve22.458–25.625us versus v9. UI stage means fall from
104.333–106.500us to92.875–95.125us; exact attribution of the remaining gain
needs more measurements. Every case still fails its deadline. Initial note
and control setup, shared rendering and output conversion remain within the
reported total; first blocks are never excluded. Mixed, DAC/KA6 and30-minute
soak acceptance remain outstanding.

[verified, CI diagnosis] a13d027's MIT/BSD, sanitizer and32-bit jobs fail the
committed Wasm source-hash gate after the shared app-layout change. Actual job
logs121284866925/121284866911/121284867037 show this same failure. The MIT/BSD
job otherwise passes4511 tests. Rebuilding the module and its build record is
required; the gate is retained. Pages40231711027 succeeds, separately from
hardware and PR CI acceptance.

[implemented, diagnostic] Outer profile regions now separate note/control
preparation, the shared app call, and PCM conversion/checksum. Each region's
aggregate and last-block sample is reset per case; the deadline controller
copies all three samples from the exact worst total block. Four additional
clock reads and aggregate bookkeeping remain part of the outer total. The
existing six stage counts, audio/event operations and unprofiled build remain
unchanged. Host tests verify unchanged PCM, full frame coverage, reset/bounds,
timer wrap and worst-block correlation:99 pass,1 unavailable32-bit skip.

[verified, partial offline review] Detail diagnostic v11 links with downloader
disabled: ELF SHA-256
`10e64e7004dce0ce205bcfe6ec8073bb1c2f8c7bee48a3848aa6774d7d061e77`;
exported app SHA-256
`03206f51f49ee3b3de23a15ee87fa3c29e7fbb73e9fb03e450e2b24b8f55a10d`.
App563452 bytes; pretask heap84396. Complete SDK/ROM routine comparison and
link audit pass (the scheduling pending item is covered by the full routine
comparison). FM6 kernels match after individually verified relocations: the
new readonly-base displacement5984 resolves to the identical768-byte algorithm
table, versus5852 before. Static mailbox/worker layout and priorities remain.
Final renderer/UART machine-code review, independent objcopy/cipher/CRC and
NOR model remain outstanding. No v11 candidate is admitted or installed.

[verified, offline admission] V11 final vendor review confirms four boundary
samples and aggregation after conversion; worst-block samples copy only after
the outer closing clock. The timing routine's stack frame is260 bytes. UART18
creation precedes parent16 with allocation-failure guard,200-tick recovery
window, worker16/34829-tick budget, million-poll bound, permanent aligned
mailbox/worker storage, fences and finite exit. All five changed diagnostic
input hashes match the checkout. Independent five-section objcopy equals the
ELF export. Independent cipher/CRC protects boot/config/tail; app ends0x8da1c.
Exact image SHA-256
`344330443ae9cb9e11b95525b2d5fa58714df2397cf15656940a7a1de974a49a`
uses138 sectors[0x4000,0x8e000). Install/restore and interrupted pages7/1111/
2183/2199 return the exact factory image in the offline NOR model.68 admission,
loader-reset and SDK lifecycle tests pass. Existing image plans are retained;
only this exact hash is newly admitted. Not installed or hardware accepted.

### Outer-region v11 hardware result

[verified, hardware] Exact34433044 passes startup recovery in78.8414ms,
actual WL82/UBOOT1.00 inquiries, two matching full current/new-image backups,
138-sector factory restores and SAME RUN installation/full readback. WINDOW
and RUN reset receipts are consumed. Four arithmetic/PCM receipts,32 unit/
24 stage rows,24 correlated worst-stage rows and12 outer-region rows pass.
All81308 paired jobs are accepted; refusal/error/wrong-core counts are zero
and finite worker exit succeeds. Heap42452 stays stable. Parent unused stack
is2516/8192 bytes; worker unused3260/4096. Sole RX210175 was checked twice,
terminated once, and capture session72526 was terminal before ordinary PING
ACK. Private raw SHA-256:
`258bd93cc63e4b4c713b0ffbf14a791d5e797bb90134badb0ca8540aae1d570e`.

| Keys case | Mean us | Max us | Late /5513 | Worst prep us | Worst shared app us | Worst PCM us |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
|0|1116.542|2169.167|11|464.042|1674.083|23.875|
|1|1257.667|2059.333|170|377.917|1652.417|22.875|
|2|1335.750|2181.708|539|441.583|1712.250|21.708|
|3|1429.708|2358.083|2101|510.125|1819.375|22.250|

[verified] Every worst snapshot is block0; region counts cover all5513 blocks
and352832 frames per case. Mean prep is3.542–3.875us, shared app1091.500–
1404.375us and PCM20.792–21.000us. The first-block prep spike is therefore
substantial, but the shared app itself also exceeds the34829-tick deadline
on those blocks. PCM conversion alone cannot resolve this. In case3, mean
sound/master/UI stages are1027.667/251.667/92.625us. These are diagnostic
measurements with added boundary/accounting overhead, not an optimization
comparison. All four deadlines fail; mixed, fault-validated DAC/KA6 and
representative30-minute analog acceptance remain outstanding.

### Audio-hook clock snapshot, v12

[verified, source/host] Both audio-hook entry paths now use the existing
`fm1_seq_get_clock` API for tempo/playing instead of the full UI snapshot.
The read stays at the same point before hook begin; no rate, event order,
filter or DSP change. The full snapshot scans capture history and song
state unnecessarily for these two fields. A bridge test checks both paths
against the UI snapshot across tempo edits, play/pause/resume/stop and a
missing sequencer.61 focused renderer/transport tests pass with1 unavailable
32-bit skip; the corrected explicit-tempo bridge test also passes. Refreshed
Wasm passes108 parity scenarios (all identical to JS/musl;105 to glibc under
the existing libm policy). Rarefaction still selects the primary checkout;
its empty callers are incomplete. Serena selects this absolute worktree and
locates the current getter; actual source and vendor code bound the change.

[verified, offline admission] V12 ELF SHA-256
`38ea3418594e3e7f179c8bd9c7ea92985e299650ab9c28d5b07e68c349fa9c05`,
app `832d01ec513385de983f7060482ab1d7543fe39ee75216b5d7ea45e48849387a`,
563420bytes, pretask heap84396. Vendor code confirms clock-getter calls at
both dispatch sites, UART18 allocated before parent16 with failure guard,
200-tick recovery,260-byte timing frame, fixed mailbox/worker layout,
fences and finite worker exit. Exact FM6 kernel/table comparison after
checked relocations and complete SDK/ROM-entry comparison pass; link audit
has0 failures and its scheduling pending item is covered by that comparison.
Independent five-section objcopy, cipher/CRC, protected boot/config/tail and
NOR138-sector install/restore/interrupted pages7/1111/2183/2199 pass.
Exact candidate
`2c0b53f53b8e8c240233b9c9233860b5fe4c68bf784e6e53d86145ac24763686`
ends0x8d9fc and is admitted only over[0x4000,0x8e000). Not installed; target
performance and audio acceptance remain unproven. V11 remains healthy idle.

[verified]69 exact-image admission/reset/SDK lifecycle tests pass. Current
UART, worker, renderer and control input hashes match the vendor manifest.

### Clock-snapshot v12 target result

[verified, hardware] Exact2c0b53f5 passes startup recovery in76.496ms,
fresh actual WL82/UBOOT1.00 inquiry, two full current/new-image backups,
138-sector factory restores and SAME RUN installation/full readback. WINDOW
and RUN reset receipts are consumed. All four arithmetic/PCM receipts,32 unit,
24 stage,24 correlated worst and12 outer-region rows pass. All81308 paired
jobs are accepted, with zero refusals/errors/wrong-core jobs and finite exit.
Heap42452 stays stable; parent unused2516/8192 bytes and worker unused3260/4096.
Sole RX217207 was checked twice, terminated once, and session77084 was terminal
before ordinary PING ACK. Private raw SHA-256:
`bbd7ca014bc6262a5a658daf5a96acbeb1d5e720df145654f0bca53e50c66aca`.

| Keys case | Mean us | Max us | Late /5513 | Worst prep us | Worst shared app us | Worst PCM us |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
|0|1126.458|2168.917|18|468.417|1671.083|23.875|
|1|1272.708|2054.708|204|384.167|1642.958|22.958|
|2|1352.542|2207.167|667|442.458|1737.458|21.750|
|3|1445.375|2363.917|2377|512.750|1823.125|21.708|

[verified] Every worst snapshot is block0. V12 shows no target improvement
against V11; no performance gain is claimed for the narrower hook snapshot.
UI stage means89.792/90.333/91.250/91.958us remain a measured placement lead.
Deadline, mixed, fault-validated DAC/KA6 and30-minute analog acceptance still
fail or remain undone. Board healthy idle, no capture/build live after closure.

### UI synchronization placement experiment

[verified, source/host] Opt-in `--ui-ram` prepares private SRAM copies of
`fm1_seq_ui_sync`, `fm1_seq_get_info`, `fm1_seq_get_track` and
`fm1_seq_get_clip`, retaining every query/update and its order. It requires the
timing-only resident-dispatch experiment; default builds are unchanged.
Preparation tests normalize only section pragmas and require byte-identical
original source, selected function markers and original hashes.76 focused
SDK-preparation/refusal tests pass. Vendor layout/stack, exact image admission
and target performance remain pending; this is not a hardware-accepted image.
Rarefaction remains rooted at the primary checkout and cannot find this
worktree-only preparation tool; Serena locates its current function here.

[verified, offline admission] V13 ELF SHA-256
`553feae34c9a0555bdc18ead0f5249f04a21b6bc9120021149722e8b02344955`,
app `69e39f04b660f477a48b1be5606d0c5a4e01fddc205c62554b99ecb1fcc2fb19`,
563580bytes, end0x8da9c. The four selected functions reside in SRAM;
pretask heap80620. Permanent mailbox0x1c15280/448bytes and worker0x1c15440/
4260bytes remain aligned/disjoint in ram0 BSS below heap. Their addresses move;
no claim of unchanged addresses is made. Timing frame260bytes, UI sync frame
1108bytes; target high-water assessment remains required. Vendor code confirms
UART18/4KiB allocation before parent16/8KiB, failed-allocation guard,200-tick
recovery, fixed34829-tick/one-million-poll bounds, fences and finite worker exit.
Exact kernel/table comparison after checked relocations, complete SDK/ROM-entry
comparison and link audit pass (0 failures; scheduling pending covered by
complete comparison). Diagnostic C/header and UI/control source hashes match;
an older noncompiled README in build staging is not claimed current.
Independent five-section objcopy, cipher/CRC and protected boot/config/tail
checks pass. Exact image
`6d977407df3c892278e6d41cd15f4e7c1c4763e886fba36b6c99456e4bf73bc9`
uses138 sectors[0x4000,0x8e000). NOR install/restore and interrupted pages7/
1111/2183/2199 restore factory exactly.113 admission/reset/SDK tests pass.
Not installed or hardware accepted; V12 remains healthy idle.

### UI SRAM v13 target result

[verified, hardware] Exact6d977407 passes startup recovery in78.608ms,
fresh actual WL82/UBOOT1.00 inquiry, two full current/new-image backups,
138-sector factory restores and SAME RUN installation/full readback. WINDOW
24555 and RUN72027 reset receipts are consumed; neither may be retried.
All four arithmetic/PCM receipts,32 unit,24 stage,24 correlated worst and12
outer-region rows pass. All81308 paired jobs are accepted, with zero
refusals/errors/wrong-core jobs and finite exit. Heap38676 stays stable;
parent unused2516/8192 bytes and worker unused3260/4096. Sole RX221969 was
checked twice, terminated once, and session1489 was terminal before ordinary
PING ACK. No capture remains live. Private raw SHA-256:
`ae5cc311700ed54b7748da894ec4ae946b73597ac9f2286a0aaebdd6cf2446b1`.

| Keys case | Mean us | Max us | Late /5513 | UI mean us | Worst prep us | Worst shared app us |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
|0|1015.417|1978.583|1|48.875|466.125|1481.833|
|1|1151.083|1947.625|10|48.375|378.833|1541.750|
|2|1227.625|2060.250|81|49.250|433.125|1600.208|
|3|1325.500|2230.125|321|49.625|499.958|1703.208|

[verified] Means improve8.29..9.86percent against V12, with unchanged PCM
hashes and event schedule. UI stage drops from89.79..91.96us to48.38..49.63us;
other placement/cache effects are included in the whole-block improvement.
Every worst snapshot remains block0. The34829-tick deadline still FAILS;
mixed, fault-validated DAC/KA6 and30-minute analog acceptance remain undone.
Next measure the actual note/control preparation subregions before changing
semantics; no claim that modulation planning causes the spike is supported yet.

### Preparation cost diagnostic source checkpoint

[verified, host] Opt-in `--prep-profile` adds eight nested diagnostic regions
without changing the original call order: note-on/off batches, level/filter
edits, engine note-on, modulation live-note, voice-start and plan build.
Setup calls are excluded; per-call maxima and per-block sums remain distinct.
The worst total-block snapshot retains matching region sums. All observer cost
remains charged to the deadline. Source-normalization tests preserve every
original call, and changed anchors/early planner returns are refused.
83 focused preparation/refusal/PCM/counter-reset tests pass on bounded Aeon.
Initial test execution exposed a fixture variable shadow and stale root-owned
build dependency files; the fixture is fixed and a fresh build tag passes.
Vendor build, exact-image review/admission and hardware timing remain pending;
V13 stays healthy idle. Rarefaction cannot access this external worktree's new
renderer source; Serena resolves the actual renderer symbol here. No missing
caller claim is inferred from Rarefaction's empty/wrong-checkout results.

### V14 exact diagnostic admitted offline

[verified] Candidate SHA-256
`8f705a96c211e8ec06896e99b4d86552a3fb8047eeebff61160b75e5503ca665`
is admitted only for the existing 138 application sectors `[0x4000,0x8e000)`.
Vendor build, independent five-section app reconstruction, cipher/CRC and
protected bytes, exact SDK/ROM entry comparison, six FM6 kernels/tables and
interrupted NOR install/restore model pass. All 627 prepared input hashes
match their manifest. The app is 564412 bytes; its last byte is below0x8dddc.
The timing frame uses272 bytes; planner1060; UI1160 including saved registers.
Pre-task heap is80396 bytes. UART is created first at priority18 with a
1024-word stack before the priority16 parent, and the mandatory200-tick
recovery window precedes renderer initialization. Actual target stack and
recovery still require verification. 115 focused transaction/reset/SDK tests
pass; the new hash exercises the same sector-boundary tests as V13.
No V14 hardware installation or acceptance is claimed here. Nested profiling
measures causes; its overhead cannot be claimed as an audio optimization.

### V14 target preparation measurements

[verified, dev kit] The exact V14 image passed startup PING/ARM/ENTER in
78.751ms, fresh responsive ROM inquiry, two full matching current-image reads,
factory restoration, same-image reinstall and complete full-flash readback.
The four PCM and arithmetic checks, 32 unit,24 stage,24 worst-block,12 detail
and32 preparation receipts pass. All81308 paired jobs completed with zero
refusals/errors/wrong-core execution and finite worker exit. Heap remains38452
bytes; parent unused stack2556/8192 bytes, worker3260/4096 bytes. The receive-only
capture was closed before ordinary PING acknowledged; board is healthy idle.

|Case|Mean us|Maximum us|Late /5513|Worst external preparation us|
|---|---:|---:|---:|---:|
|0|1003.000|2126.917|2|485.917|
|1|1137.667|1961.625|29|400.333|
|2|1213.333|2112.625|99|460.500|
|3|1311.125|2290.583|356|533.458|

[verified] All worst snapshots remain block0. Planner runs once in case0,
138.833us inside the nested live-note region, and zero times in later cases.
Level/filter edits each run87 times per case: ordinary per-call means are
97.1..112.8us and112.3..131.2us respectively. These recurring setters warrant
investigation separately from one-time plan construction. Nested totals must
not be added. The private validator initially omitted its zero-call branch;
that is corrected, requiring every aggregate of an unused region to be zero.
No target source or acceptance threshold was changed to obtain this result.
Deadline still FAILS. Mixed renderer, fault-validated DAC/KA6 and30-minute
analog soaks remain undone. V14 diagnostic overhead is not an optimization.

### Early automation-label rejection experiment

[verified, source] Both recurring control setters call `seq_auto_base`, which
walks64 lanes. `seq_auto_target` previously copied track state before rejecting
an empty, ordinary sound or invalid app-target label. It now classifies the
bounds-checked label first. Accepted labels still query fresh track route/base
state and preserve the original command order; no cache, UI decimation, event
skipping or quality/rate changes were introduced.
206 sequencer UI/shared-renderer tests pass. Six Movy-oracle cases skip because
the private reference is absent in this staging tree; one32-bit target-pool
replay skips because the image lacks that compiler/runtime. These are limits,
not passes. All108 WebAssembly parity scenarios pass with exact JS/musl PCM;
105 match glibc exactly and the established exact scenarios differ by at most
one LSB. Vendor build and checked SDK/ROM/six-kernel comparisons pass.
The linked sequence classifies the label before `fm1_seq_get_track`.
Exact image admission and target timing remain pending; no speedup claimed.

[verified, offline] V15 exact candidate
`7353e97745fae6c2489a85e5ad1a90ab33cdf4b9660bf8561fe63f28e98c1d03`
is admitted for138 sectors after116 transaction/reset/SDK tests pass. App
`303b2869b287526dc2afd249e161ffb1798f0074a9cadc603076f2dc53bb0ce8`
is564412 bytes, ending0x8dddc. Independent objcopy/cipher/CRC, checked SDK/ROM
and FM6 kernel/table comparisons,630 prepared manifest entries, identical
mailbox/worker/diagnostic/heap layout and interrupted NOR install/restore pass.
UART creation remains priority18/1024 words before parent16/2048 words;
its200-tick recovery wait precedes initialization. Timing frame272 bytes,
planner1060 and UI1160 with saved registers remain reviewed; actual high-water
and recovery require target verification. No hardware V15 acceptance yet.

### Early-label V15 hardware measurement

[verified, hardware] Exact7353e977 passes startup UART recovery in78.590ms,
fresh WL82/UBOOT1.00 inquiry, two matching full current/new-image backups,
138-sector factory restore and SAME RUN installation/full8MiB readback.
WINDOW80049 and RUN7033 reset receipts are consumed; neither may be retried.
Four arithmetic/PCM checks,32 unit/24 stage/24 correlated worst/12 detail/
32 preparation rows pass. All81308 paired jobs complete with zero refusal,
error or wrong-core counts and finite exit. Heap38452 remains stable; parent
unused stack2556/8192 bytes and worker3260/4096 match V14. Sole RX233635 was
checked twice, terminated once, and session33684 was terminal before an
ordinary PING ACK. Private raw SHA-256:
`b8ab7782d836046eb3c4c1f31798bfcf888925b5ce361186a08c01cfc8302c1b`.

| Keys case | Mean us | Max us | Late /5513 | Worst prep us | Worst shared app us |
| --- | ---: | ---: | ---: | ---: | ---: |
|0|1000.583|1938.375|2|422.042|1484.833|
|1|1136.708|1902.083|5|333.500|1541.417|
|2|1212.333|2055.958|92|397.625|1629.750|
|3|1310.333|2209.042|349|464.375|1716.125|

[verified] Every worst block remains0. Level setter mean calls fall from
97.458/97.292/97.125/112.792us in V14 to64.333/64.125/64.125/72.667us;
filter setters fall from112.250/113.375/113.292/131.167us to
79.583/80.792/81.042/96.500us. Whole-block means improve only0.06–0.24%;
this change helps recurring controls but does not solve the deadline.
Sound-stage means remain645.500/785.708/861.833/959.458us and worst
correlated sound stages1029.542/1169.583/1260.667/1343.875us. The remaining
first-block cost needs causal investigation. Mixed, fault-validated DAC/KA6
and representative30-minute analog acceptance remain outstanding.

### Correlated dispatch/unit diagnostic (V16, offline only)

[implemented] Profiling retains per-block unit callback sums, clearing them at
entry and copying all eight into the same exact worst-total-block snapshot.
Split callbacks accumulate; independent per-call maxima are not substituted.
The existing private preparation instrumentation additionally observes sequencer
flush, advance, dispatch, and the post-dispatch insert/mix loop (regions8–11).
The twelve regions are nested and cannot all be added as independent costs.
Prepared-source guards reject missing/duplicate anchors and early returns;
removing observer lines reproduces the original source apart from whitespace.
No production event order, DSP math, rate or time constant changes.

[verified, offline]109 renderer/preparer tests pass; one32-bit target-pool
replay skips because its compiler/runtime is unavailable. Two strengthened
PCM/counter tests additionally verify each last-block unit sum against the
change in its aggregate ticks for every block, plus reset/bounds behavior.
A synthetic timing test pins unit snapshots to the exact worst block, including
timer wrap. Vendor build succeeds. Exact SDK/kernel/layout/stack/UART-first,
independent image/cipher/CRC and NOR review remain pending. V16 is not admitted
or installed. The healthy V15 board is idle; deadlines and analog acceptance
remain open.

[verified, offline] V16 exact image
`d7b4d18c6b3a8506ab44244e393fe3f2b0640b3f996103aea18c46d19fec0cab`
is admitted for138 application sectors after73 transaction/reset/SDK tests and
two boot-command tests pass. The initial admission command collected no tests
because it named a nonexistent test file; the corrected command passed.
App `fa055968d06201a36c1362b30efee82b19655f27e2b00c5965f8a3bf7439c7a4`
is564700 bytes, ending0x8defc; independent five-section extraction, full
cipher/CRC and interrupted NOR restoration at four interruption points pass.
All630 manifest inputs, SDK/ROM routines and six FM6 kernels match the reviewed
inputs after independently checked relocations. Static ranges do not overlap;
pre-task heap80140 bytes, timing frame320 bytes, planner1060 and UI1160 bytes.
UART recovery task creation remains guarded before the renderer task and its
200-tick wait precedes workload initialization. These are offline checks;
actual startup recovery, stack high-water and timing still require V16 hardware
measurement. No deadline or analog acceptance is claimed.

### Correlated dispatch V16 hardware measurement

[verified, hardware] Exactd7b4d18c startup recovery succeeds in78.7947ms.
Fresh WL82/UBOOT1.00 inquiry, double full current/new backups,138-sector
factory restores and SAME RUN installation/full readback pass. WINDOW57330
and RUN74773 reset receipts are consumed and must never be retried. Four
PCM/arithmetic cases,32 unit/24 stage/24 correlated stage/12 detail/48 prep/
32 correlated unit rows pass. All81308 paired jobs complete with zero errors,
refusal, disabled or wrong-core counts and finite worker exit. Heap38196
remains stable; parent unused2508/8192 bytes and worker3260/4096. Sole RX240364
was twice argv-checked, terminated once and session60899 became terminal
before ordinary PING ACK. Private raw SHA-256:
`9bd7be25d0f58059bf20477ef0a85eca7ca375679089c0b10d44db4a61af136b`.

|Keys case|Mean us|Max us|Late /5513|Worst dispatch us|Worst FM render us|
|---|---:|---:|---:|---:|---:|
|0|1006.292|1928.375|2|735.292|74.417|
|1|1140.417|1887.083|5|900.833|318.708|
|2|1214.625|2027.500|77|979.958|396.125|
|3|1313.708|2203.500|415|1079.792|513.417|

[verified] All worst blocks are0. Dispatch minus its enclosed FM render is
566–661us on those blocks and277–281us on average. This includes modulation
hooks and control work, not only dispatcher bookkeeping. Worst filter
callbacks238.792/220.292/219.000/220.875us fit inside their post-dispatch
insert/mix regions257.833/236.250/234.333/237.042us. Sequencer advance is
12.750–20.750us on the worst block; flush stays0.292us. New profiling adds
observations and is not a speedup. Deadlines still fail; actual mixed timing,
fault-validated DAC/KA6 and representative30-minute analog soaks remain open.

### Remaining hook SRAM placement comparison (V17, offline)

[implemented] The private `--hook-ram` option places seven unchanged function
definitions in startup-copied SRAM: sequencer automation begin/tick, modulation
glue begin/tick, modulation block begin, voice runner and voice-output helper.
V16 vendor disassembly confirms these paths include flash-resident call targets
inside the measured dispatch region. This motivates a controlled placement
comparison, not an attribution of all dispatch overhead to those functions.
Source guards reject missing/duplicate definitions; stripping placement pragmas
reproduces original files byte for byte. Timing-only/profile/resident-dispatch
prerequisites reject incomplete or DAC configurations before writing outputs.
No production source, tick rate, PCM math or event order changes.

[verified, offline]113 renderer/preparation/diagnostic tests pass; one target
32-bit pool replay skips because its compiler/runtime is unavailable. Vendor
build succeeds; first exact SDK/ROM comparison passes. Pre-task heap78156 bytes
(down1984 from V16) and mailbox448 bytes at0x1c15a80. Remaining kernel, manifest,
independent extraction, layout/stack/UART-first, cipher/CRC and NOR checks must
pass before exact admission. V17 is not admitted, staged or installed.

[verified, offline] V17 exact candidate
`b34e5f591b14bade352c60630aa394fba74f7cedbe0d7080f3481f34930cf27a`
is admitted for138 sectors after76 transaction/reset/SDK/boot tests pass.
App `f5f1ce4a4f550af11f0ae63dcd67f24b31eec2463ce16ade950c384bab88770e`
is564732 bytes, ending0x8df1c. ELF
`1cce03ed2a378af9d60259d6fd1b4baab52538d65ccf4da0e19d3143dab8c2d8`.
All630 manifest entries plus prepared app_main/linker match. Independent
five-section extraction/cipher/CRC, protected factory/config/tail checks and
NOR138 interrupted install/restore at pages7/1111/2183/2199 pass. Six FM6
kernels/tables match V16 after checked relocations. Exact SDK/ROM comparison
covers the link audit's remaining decoder-pending item (zero failures).
Static ranges remain nonoverlapping, pool98304 and worker memory4260 bytes;
mailbox448 aligned64. Timing320/planner1060/app-render296/UI1160 frames remain
unchanged; glue tick184 and sequencer begin64 bytes include saved registers.
Selected voice runner/block begin inline into the resident hook. Actual UART
priority18/1024 task creation0x2021192 precedes guarded parent16/2048 at
0x20211be; the worker's200-tick wait at0x201f02e/0x201f030 precedes workload.
Reviewed fences,34829-tick budget, bounded poll/lifetime and finite exit remain.
Hardware startup recovery, PCM, stack and deadline measurements are still
required; no target speedup or analog acceptance is claimed.

### Hook SRAM V17 hardware measurement

[verified, hardware] Exactb34e5f59 startup recovery succeeds in78.7032ms.
Fresh WL82/UBOOT1.00 inquiries, double full current/new backups,138-sector
factory restores and SAME RUN installation/full8MiB readback pass. WINDOW64766
and RUN90556 reset receipts are consumed; neither may be retried. Four PCM/
arithmetic cases,32 unit/24 stage/24 correlated stage/12 detail/48 prep/
32 correlated unit rows pass. All81308 paired jobs complete with zero errors,
refusals, disabled or wrong-core counts and finite worker exit. Heap36212 bytes
remains stable; parent unused2508/8192 bytes and worker3260/4096 match V16.
Sole RX246072 was twice argv-checked, terminated once and session5971 became
terminal before ordinary PING ACK. Private raw SHA-256:
`a49dfa4227f368e8c28f9bf872fba4d8bacfb0ed24fa4e6ba8c2ecef279e82e1`.

|Keys case|Mean us|Max us|Late /5513|Worst dispatch us|Worst FM render us|
|---|---:|---:|---:|---:|---:|
|0|977.917|1897.083|1|710.667|77.250|
|1|1112.750|1842.542|4|867.083|319.833|
|2|1187.667|2007.208|22|956.625|394.667|
|3|1285.042|2181.917|226|1061.750|515.708|

[verified] Whole-block means improve2.18–2.82% against V16 with unchanged
PCM and arithmetic checks. All worst blocks remain0. SRAM placement helps
this configuration but does not establish an individual function's cost or
solve the deadline. Actual mixed timing, fault-validated DAC/KA6 and
representative30-minute analog soaks remain outstanding. No analog acceptance
or firmware merge is claimed.

### Nested dispatch diagnostic (V18, offline work)

[implemented] The private preparation profile now adds twelve nested regions:
MIDI effects, hook begin/tick, modulation tick, voice-write collection, system
inputs, module/sink/voice loops, voiced/ticked callbacks and hook-write
conversion. Each original call remains in place; source guards reject missing
or duplicate definitions/calls. Removing observer lines reproduces original
source apart from whitespace. The same existing per-block reset and exact
worst-total-block snapshot cover all24 regions. No production DSP source,
rate, math, event order or deadline changes. Observer overhead remains charged
to total time. Host/vendor validation is running; V18 is not admitted or
installed. V17 remains healthy idle, with deadlines and analog acceptance open.

[verified, offline]113 tests pass initially with one unavailable32-bit skip;
one preparation fixture still assumed two instrumented paths. Its updated
five-path/observer checks pass in the32-test preparation subset. A temporary
fixture indentation error and variable shadow were corrected before that pass.
Vendor build and exact SDK/ROM/six FM6 kernel comparisons pass. V18 app is
565084 bytes; pre-task heap77644. Timing frame384 bytes including52 saved
register bytes (64 above V17), glue tick176 bytes and UI1160 bytes. Independent
image/cipher/NOR, complete layout/UART-first review and exact admission remain
pending; no V18 hardware commands have been sent.

[verified, offline] V18 exact-image review is complete: all630 prepared inputs
and app-main/linker/renderer-fragment hashes match. Static mailbox/worker,
24-region counter/start/snapshot, pool/app and profile ranges do not overlap
and precede the heap. Compiled region bound is24; original nested calls and
optional callback guards remain. UART task18/1024 is created before parent
16/2048, and the worker delays200 OS ticks before workload. The independent
five-section app copy, whole cipher/CRC/protected ranges and NOR model pass;
interrupted pages7/1111/2199/2215 each restore byte-identically.73 transaction/
reset tests pass. SDK link audit has0 failures; its one pending machine-code
item is covered by the independent exact vendor comparison.

[verified, offline] Exact candidate SHA-256:
`f68182d2e673abf012b5571c2e45cbfc3fc5d4cdb213e4bd70679461c35b2dfc`.
It extends through0x8e07c,124 bytes into an added sector. Only this SHA admits
139 sectors `[0x4000,0x8f000)`; every older image still rejects the extra sector.
The currently installed V17 restore remains138 sectors. This admits the V18
hardware experiment, not audio acceptance. V18 is not yet installed; V17 is
healthy idle. All previous reset receipts remain consumed.

### V18 target dispatch attribution (deadlines still fail)

[verified] Exact `f68182d2…` completes the protected cycle: fresh acknowledged
UART entry/actual ROM inquiry, double CURRENT V17 backups, CURRENT138-sector
factory restore, WINDOW install/full8MiB readback, fresh startup PING/ARM/ENTER
in78.5215ms, double NEW backups, NEW139-sector factory restore, SAME RUN install/
full readback and finite four-case run. WINDOW66411/RUN26267 are consumed;
neither may be retried. Strict PCM/arithmetic,32 unit/24 stage/24 correlated
stage/12 detail/96 prep/32 correlated unit checks pass. All81308 paired jobs
complete with zero error/refusal/wrong-core/disabled counters and finite exit.
Heap35700 bytes stays stable; parent unused2444/8192 bytes, worker3260/4096.
Sole RX252210 was twice argv-checked and terminated once; session14762 was
terminal before ordinary PING ACK. Private raw SHA-256:
`6e6fc563201499079f5f03195a2ecdb957930f97841c0fda69daaaf3d4697706`.

|Keys case|Mean us|Max us|Late /5513|Mod tick mean us/block|Module loop mean us/block|Module loop worst-block us|
|---|---:|---:|---:|---:|---:|---:|
|0|986.833|1906.792|1|243.208|176.250|417.667|
|1|1122.792|1879.792|3|237.750|171.583|414.375|
|2|1198.875|2044.125|36|239.333|172.833|425.042|
|3|1297.333|2171.542|284|239.750|173.333|381.667|

[verified] All worst total blocks are0. The whole original module loop is the
largest measured modulation subregion; system inputs average40.8–41.4us/block,
sinks18.3–18.5us and voices2.7us. These nested costs must not be added to their
parent. The diagnostic adds observer overhead, so these figures do not claim
an optimization over V17. Source/vendor review finds module-processing helpers
still in XIP; controlled placement is the next experiment. Actual mixed timing,
fault-validated DAC/KA6 and representative30-minute analog soaks remain open.


### Module helper SRAM experiment (V19, offline work)

[implemented] V18 identifies the module loop as the largest measured modulation
subregion. A separate `--module-ram` switch places only the unchanged runner,
parameter, gate and output helper definitions (2904 compiled bytes in V18) in
startup-copied SRAM. It requires timing-only profiled resident hooks. No rack,
kind process function, tick/sample rate, arithmetic or event-order change.
Original prepared source hashes are retained. V19 is not admitted or installed;
V18 remains healthy idle. Vendor/layout/stack/PCM/timing validation is pending.

[verified, offline]118 focused tests pass with one unavailable32-bit skip;
a final two-case placement recheck passes. The first vendor preparation caught
an incorrect `void` anchor for the `int` output helper before link; corrected
signature and a fresh staging directory build successfully. No V19 hardware
commands have been sent. Exact vendor/link/layout/recovery/PCM/cipher/NOR review
still gates admission. Rarefaction's primary checkout lacks this worktree symbol;
Serena selects the actual absolute worktree and finds the exact helper bodies.

[verified, offline] V19 exact candidate `06f2087f…` passes independent app copy,
full cipher/CRC/protected regions,630-input manifest and139-sector NOR install/
restore including interrupted pages7/1111/2199/2215. SRAM helper placement is
verified in vendor instructions; LTO inlines the runner into resident mod tick.
Pre-task heap75532 bytes. Mod tick frame288 plus glue80 replaces the prior
inlined glue176, so target stack assessment remains required. Static mailbox,
worker, pool, app and24-region counter/snapshot ranges are disjoint before heap.
UART18/1024 creation precedes parent16/2048; actual worker200-tick recovery delay,
34829-tick budget,120000ms lifetime and finite completion path are retained.
Only the exact V19 hash gains the existing139-sector bounds; all older bounds
remain unchanged. This is experiment admission, not timing or audio acceptance.

### V19 target module placement results (deadlines still fail)

[verified] Exact `06f2087f…` passes the full protected cycle: double CURRENT
backups43847, CURRENT139 restore66041, WINDOW install43689/full8MiB readback,
startup recovery57335 in78.5923ms, double NEW backups83991, NEW139 restore84166
and SAME RUN install11385/full readback. WINDOW77233/RUN48675 are consumed,
never retry. All four PCM/arithmetic,32 unit/24 stage/24 worst/12 detail/96 prep/
32 unit-worst checks pass. All81308 paired jobs finish with zero error, refusal,
disabled or wrong-core counters and finite exit. Heap33588 bytes is stable;
parent unused2444/8192 and worker3260/4096 bytes. Sole RX257648 was twice
argv-checked and terminated once; session68346 was terminal before ordinary
PING ACK. No capture remains live. Private raw SHA-256:
`e0bfad3f6d3f89f7a0b8bafef1e4744c7b6e7150002d3e144dc95a605e37a99e`.

|Keys case|Mean us|Max us|Late /5513|Module loop mean us/block|Mean reduction vs V18|
|---|---:|---:|---:|---:|---:|
|0|951.167|1852.833|1|154.917|3.61%|
|1|1089.167|1808.875|3|154.958|2.99%|
|2|1164.792|1952.875|3|153.417|2.84%|
|3|1260.542|2114.833|98|153.458|2.84%|

[verified] All worst total blocks remain0. SRAM placement reduces the measured
module-loop cost while preserving PCM, but every case still misses deadlines.
Actual mixed timing, fault-validated DAC/KA6 and representative30-minute analog
soaks remain open. PR155 stays draft and unmerged.

### Default modulation kind SRAM experiment (V20, offline work)

[implemented] V19 still spends153–155us/block in the module loop. Vendor
symbols place default LFO, envelope and chance processors and their LFO/env
process primitives in XIP. A separate `--kind-ram` experiment relocates only
eight existing hot definitions in private prepared copies; guards refuse drift.
No body, random state, rate, arithmetic or event-order changes. Host/vendor
validation and exact admission remain pending; V20 is not installed. V19 is
healthy idle. Rarefaction resolves the older primary checkout as advisory only;
Serena verifies the actual worktree body, including frame-exact LFO carries.

[verified, offline]150 focused tests pass with one unavailable32-bit skip. The
V20 vendor build passes, as do exact SDK/ROM safeguards and six FM6 kernel/
table comparisons against V19 with checked relocations. Pre-task heap65292
bytes is10240 below V19; target heap/stack assessment remains required. Exact
layout/UART-first, independent app/cipher/NOR review still gate admission.
V20 remains uninstalled; V19 is healthy idle.

[verified, offline] Exact V20 candidate `d4c443a8…` passes630-input manifest,
independent five-section app copy, full cipher/CRC/protected ranges and139-
sector NOR model, including interrupted pages7/1111/2199/2215. All static
mailbox/worker/pool/app/profile ranges remain disjoint before heap. UART task
18/1024 precedes parent16/2048; worker200-tick delay,34829-tick budget,120000ms
lifetime and24-region bound remain. LFO-run and chance-clock helpers inline
into their resident processors; frames LFO120, envelope128, chance104 bytes,
with envelope-run68 and primitives48/60. Target PCM, stack and deadlines remain
required. Only exact V20 gains the existing139-sector admission. No target
acceptance is implied; V20 has not yet been installed.

### V20 target default-kind placement (deadlines still fail)

[verified] Exact `d4c443a8…` completes the protected cycle: double CURRENT
94429, CURRENT139 restore11574, WINDOW install30157/full8MiB readback, startup
recovery95514 in78.9516ms, double NEW18181, NEW139 restore5091 and SAME RUN
install75563/full readback. WINDOW39799/RUN34207 are consumed; never retry.
All four PCM/arithmetic,32 unit/24 stage/24 worst/12 detail/96 prep/32 unit-
worst checks pass. All81308 paired jobs finish with zero error/refusal/disabled/
wrong-core and finite exit. Heap23348 bytes is stable; parent unused2444/8192,
worker3260/4096 bytes. Sole RX262440 was twice argv-checked and terminated once;
session26175 was terminal before ordinary PING ACK. Private raw SHA-256:
`6b78eaafb24bc4dcc77021d271cc38b6b5a68efec26ac33b8a74bb8bb438a315`.

|Keys case|Mean us|Max us|Late /5513|Module loop mean us/block|Mean reduction vs V19|
|---|---:|---:|---:|---:|---:|
|0|915.250|1701.417|1|138.917|3.78%|
|1|1054.542|1699.083|1|137.500|3.18%|
|2|1129.125|1844.625|2|137.708|3.06%|
|3|1220.750|2015.000|17|139.250|3.16%|

[verified] All worst total blocks remain0. The worst-block residual outside
the six reported stages is455.542/368.208/419.917/488.333us. That residual
and cold-block preparation need attribution; no deadline failure is excluded.
Actual mixed timing, fault-validated DAC/KA6 and representative30-minute analog
soaks remain open. PR155 remains draft and unmerged.

### First-block attribution and event placement experiment (V21, offline)

[verified] V20's outer counters attribute419.042/340.958/392.708/462.917us
of its worst blocks to control preparation before rendering, and26.125/21.542/
21.583/21.667us to PCM conversion. The six stages cover sounds, masters, amp,
limiter, scope and UI; their residual is not unmeasured DSP alone. Preparation
profiles split note-on and level/filter edits, with nested modulation-note cost.
No first block is excluded and no event is moved outside the deadline.

[implemented, not accepted] A separate guarded `--event-ram` relocates eight
existing definitions in private copies: app note/control dispatch and automation
target/base helpers, plus modulation note/input feeding. Function bodies remain
byte-identical after removing placement pragmas. Existing timing-only/prep/kind
guards apply and original prepared hashes are recorded. V20 stays healthy idle;
V21 requires host, vendor size/heap/stack/layout/PCM and exact admission review.
Rarefaction's primary checkout lacks this preparation script; Serena selects the
absolute worktree and verified actual control/automation/modulation-note bodies.

[verified, offline]81 renderer tests pass with one unavailable32-bit replay
skip, and the V21 vendor build succeeds. Pre-task heap61388 bytes is3904 less
than V20. Exact SDK/ROM safeguards and six FM6 kernels/table comparisons pass
with checked relocations; generic link audit has no failure, with its SDK
scheduling pending item covered by the independent exact comparison. V21 has
not been admitted or installed. Full layout/recovery/cipher/NOR review remains.

[verified, offline] Exact V21 `bb769d4d…`, app `47051658…` (562012bytes,
end0x8d47c), passes independent five-section copy, full cipher/CRC/protected
ranges,630-input manifest and138-sector NOR install/restore including
interrupted pages7/1111/2183/2199. All static mailbox/worker/pool/app/profile
ranges are disjoint before heap. UART18/1024 precedes parent16/2048 on success;
worker200-tick delay,34829-tick budget,120000ms lifetime and24-region bound
remain. New frames target96, base324, param28, level20, play108, feed44/44,
note120 bytes; established timing/planner/render/UI/mod frames are unchanged.
Target stack/PCM/deadlines remain required. Only V21 gains its138-sector bounds;
V20's139-sector restore range stays unchanged. V21 has not been installed.

[verified, offline]76 admission/reset tests pass. The first run exposed two
historical-image exclusion lists missing V21; updated only those test lists,
retaining every existing image's actual bounds. V21 is admitted for an exact
controlled timing experiment, not hardware or audio acceptance.

### V21 target result: improved tails, still fails deadlines

[verified] The exact admitted image completed its protected install/recovery/
restore/reinstall cycle. Startup ready plus three acknowledgements took78.9712ms.
Both full current/new backups, factory restores and full8MiB installs matched.
WINDOW84123 and RUN9680 are consumed and terminal; neither may be retried.
The sole receive-only capture was closed after two exact process-argument checks;
its session85364 terminated before an ordinary PING acknowledged healthy idle.

[verified] All four PCM hashes and arithmetic bits match; strict parsers accept
32unit,24stage,24worst,12detail,96prep and32unit-worst rows,81308paired jobs
without refusal/error/wrong-core/disabled work and finite worker exit. Heap19444
bytes stays stable; unused parent/worker stack2444/3260bytes. Private raw SHA
`7aa9da876b4f851e921c20dd584c6cbc36c3943970cf03943cb2835051317dcb`.

| Density case | Mean us | Maximum us | Late /5513 |
| --- | ---: | ---: | ---: |
| 0 |920.458|1596.083|1|
| 1 |1057.083|1503.250|1|
| 2 |1131.000|1692.042|1|
| 3 |1220.542|1865.750|2|

[verified] All worst blocks remain block0; their outer preparation costs are
339.833/233.583/317.792/404.958us. Case3 rendering alone takes1436.167us
on that block, leaving insufficient preparation/conversion margin. V21 improves
tails but does not satisfy deadline, mixed workload or analog acceptance.
No DAC/KA6/soak acceptance is claimed; PR155 stays draft and unmerged.

### Remaining event helpers and planner placement (V22, offline)

[implemented, not accepted] Guarded `--plan-ram` retains V21 unchanged and
places six additional exact definitions in private build copies: window_of,
feed_level/feed_trigger/feed_rtrg, fm1_mod_set_base and mod_plan_build. It
requires timing-only preparation profiling plus resident events. No first-block
work is moved or excluded; all bodies match after stripping placement pragmas.
Rarefaction resolves planner callers/co-change files from the primary checkout
with fallback clangd flags; Serena verifies the actual worktree planner body.
The preparation script remains outside Rarefaction's primary index.

[verified, offline]85 focused renderer tests pass, one unavailable32-bit
replay skips. The vendor build passes. Exact SDK/ROM safeguards and unchanged
FM6 kernels/table comparisons pass with checked relocations. ELF56593846…;
app611afffb…565340bytes; ram0_data113392bytes, pre-task heap52940bytes.
That is8448bytes more SRAM than V21; target heap/stack remain required.
V22 is NOT admitted or installed. Exact layout/recovery/cipher/NOR review and
hardware timing remain pending. V21 is healthy idle with no capture running.

[verified, offline] Exact V22 `5f893eff…` passes independent five-section app
copy, full cipher decode/CRC/protected ranges and630-input manifest plus
app-main/linker/fragment hashes. Static mailbox448bytes/alignment64, worker
pool/app/profile/24prep regions are disjoint before heap. Compiled UART18/1024
precedes parent16/2048 on success;200-tick window,34829-tick deadline,120000ms
lifetime and24-region bound remain. New planner1056bytes frame, note128,
modtick292; other established large frames are unchanged. Target stack remains
required. App end0x8e17c gives exact139sectors[0x4000,0x8f000). NOR model
passes install/restore and interruptions7/1111/2199/2215 with metadata last.
77 admission/reset tests pass. Only this exact image gains139-sector admission;
V21 retains138 sectors. No hardware installation or acceptance yet.

### V22 target result: planner placement does not meet deadlines

[verified, hardware] Exact `5f893eff…` completed the full protected cycle:
startup recovery acknowledged in78.9318ms; two full current-image backups,
139-sector factory restore, same-image run install and all full8MiB readbacks
matched. WINDOW69984 and RUN46560 receipts are consumed and must never be
retried. Sole RX273605 was checked twice before one termination; its session
68447 became terminal before ordinary PING acknowledged healthy idle.

All four PCM hashes/arithmetic receipts,81308 paired jobs with no errors or
wrong-core/refusal counters and finite worker exit,32 unit/24 stage/24 worst/
12 detail/96 preparation/32 unit-worst records pass strict correlation.
Private raw SHA256:
`edb9d0a435060115e3acf5f11d86e9cb15c56ffa50844402dc9b757a9a8ba889`.

|Case|Mean us|Max us|Late /5513|
|---|---:|---:|---:|
|0|932.708|1497.167|1|
|1|1070.042|1476.958|1|
|2|1142.917|1628.958|1|
|3|1235.250|1778.833|11|

All worst blocks remain block0. Heap10996bytes stays stable; unused parent
stack2444/8192bytes and worker3260/4096. The lower first-block maxima do not
make this a general improvement: average cost and case3 misses increased
relative to V21. No first block or deadline was excluded or relaxed. V22
fails deadline acceptance; mixed, DAC/KA6 and30-minute soaks remain undone.

### Caller-owned screen storage for the mixed timing workload (offline)

[verified, offline] A separate mixed V22 link leaves only12108bytes before
SDK task allocation, with136KiB engine pool and232816-byte shared app. The
observed keys task topology needs about41944bytes, so that image was never
admitted or installed. The shared app embeds115200bytes of240x240 RGB565
pixels; the renderer diagnostic never calls drawing. The existing panel probe
is an offline command emitter with no hardware transport or framebuffer.

[implemented, not hardware accepted] `FM1_TFT_EXTERNAL_PIXELS` keeps embedded
storage as the default and optionally replaces it with caller-owned storage.
Binding checks a full screen's capacity and fails closed; app reinitialization
retains the binding. Unbound app drawing refuses without consuming dirty,
meter or last-draw state. Attached storage uses the same pixel writers and
banner pixel reader. All translation units must use the same compile setting.
The separate `--external-pixels` preparation option is timing-only; it does
not attach a framebuffer, drive a panel or establish display/DAC acceptance.
No audio engine, pool, sample rate, filter or event ordering is removed.

[verified, offline] Two focused tests pass: embedded/attached pixels, all
fonts, clipping, recorded boxes and guard words match; real app audio, pixels,
banner pixel reads and repeated initialization match. Full mixed-renderer PCM
comparison, focused renderer suite and exact vendor mixed memory build are
in progress. The next mixed build uses V21 placements (not the unsuccessful
broad planner placement). No new candidate has been admitted or installed.
Rarefaction's primary-root bounded TFT query supplies caller/co-change leads;
Serena verifies the actual worktree body. Neither verifies target codegen.

[verified, offline] Full focused renderer/TFT suite:89PASS, one unavailable
32-bit replay skipped. GCC ASan+UBSan pixel/app tests:2PASS with leak detection
and halt-on-UB enabled. Clang is absent from this container; its attempted run
skipped both tests and is not counted as sanitizer evidence. Mixed vendor
build passes, app117632bytes, pool139264bytes, pre-task heap135724bytes.
SDK/ROM exact comparisons pass; six copied FM6 kernels and immutable algorithm/
configuration data match V21 after individually verified relocations. Mixed
LTO changes readonly-base displacement from6112 to5576; vendor objdump verifies
the exact instruction and both resolve to the byte-identical768-byte table.
ELF62f2d427…; app5a0dbfef…564444bytes. Exact layout, UART-first startup, cipher/
NOR review and target mixed timing remain pending. V23 is not admitted or
installed; V22 remains healthy idle, with no capture running.


### Exact V23 mixed image admitted offline

[verified, offline] Candidate
`b8f8e24bd6e8ff05ba4609a3593acc2370bfaf18daa4c4fdbd598cd8f3a79d10`
contains app564444bytes ending at0x8ddfc. Its reviewed write/restore range is
138 sectors `[0x4000,0x8e000)`. Installed V22 keeps its independent139-sector
restore range. All630 input hashes,14 disjoint static ranges, UART task creation
before the renderer,200-tick recovery delay,34829-tick deadline and120000-tick
worker lifetime were checked against actual vendor machine code and layout.
Independent five-section app copy and full cipher/CRC/protected-region checks
pass. The offline NOR model passes install/restore and interrupted pages7,
1111,2183 and2199 with metadata last; it sends no hardware commands.
Exact admission/transaction tests:78PASS. Host full mixed reference has PCM
hashes6bcab227/46c02687/1e2f305d/5b7dbc03, cumulative paired jobs9639/26178/
48230/81308 and controls176/358/548/746. Target mixed timing/stack and startup
recovery remain unverified; no hardware or analog acceptance is claimed.


### Browser build record refreshed after framebuffer source changes

[verified] Exact-head CI40254339982 MIT/BSD job121352963397 failed only the
committed Wasm freshness assertion at test_sim_web.py1063:4511 tests passed,
239 skipped,2 expected failures. A bounded four-CPU Aeon rebuild passed all108
parity scenarios, the metadata/SysEx checks and the30-second edit storm with
zero late quanta. Default embedded-storage Wasm and metadata bytes remained
identical; its provenance record now names the current simulator source hash.
The exact CI=true freshness test passes separately. Browser parity is not
dev-board timing or analog acceptance.


### V23 mixed hardware result: memory/recovery pass, deadlines fail

[verified] Exact b8f8e24b completed startup recovery in79.0238ms, fresh ROM
inquiry, two matching full backups,138-sector factory restore, identical run
install and full8MiB readbacks. WINDOW67093/RUN27550 are consumed, never retry.
Sole RX280859 was checked twice before one termination; session93926 became
terminal before ordinary PING acknowledged healthy idle. No capture remains.

All four mixed PCM hashes and control counts match the desktop.32 unit,24
stage,24 worst,12 detail,96 preparation and32 unit-worst rows correlate; all
eight units render352832frames per case.81308 paired jobs complete with no
wrong-core/refusal/error counters and finite worker exit. Heap93780bytes is
stable; unused parent stack2436/8192bytes, worker3260/4096bytes. Private raw
SHA256:2e9932b2f00cf7de83159a480b0fc440f7f29c88c184ee49a22fad4608ffa32f.

|Case|Mean us|Maximum us|Late /5513|Worst block|
|---|---:|---:|---:|---:|
|0|2561.542|2991.250|5513|4224|
|1|2775.250|3111.125|5513|0|
|2|2849.833|3385.000|5513|0|
|3|2941.292|3576.542|5513|0|

Macro costs909.375–981.917us per block; drums389.625–391.875us. The mixed
workload fails the34829-tick deadline in every block. No engine, native rate,
filter, event or first block is removed. DAC/KA6 fault validation and30-minute
soaks remain undone. The next investigation targets this measured engine cost;
keys-only improvements cannot establish mixed acceptance.

### Detailed Macro/drums timing with the optimized resampler

[verified, offline] The first V24 preparation attempt refused the existing
engine-detail/unrolled-FIR exclusion before producing an image. These changes
operate on separate private files: engine wrapper call boundaries versus the
resampler header. The preparer now permits their combination while retaining
all worker-only/profile/slopes prerequisites. No production DSP math changes.
A new native O3 replay instruments both wrappers and uses the prepared slope
and unrolled FIR transformations. It preserves all four mixed PCM fingerprints,
counts every352832 resampler outputs per engine/case, checks12-frame native
block accounting, timer wraparound and counter reset. Full focused renderer
suite:88PASS, one unavailable32-bit replay skipped. This diagnostic adds clock
reads; its measured totals cannot establish audio acceptance.

[verified, offline] V24 vendor build completes. Exact ELF6fa94e8a… and app
ef75a25f…564732bytes pass protected SDK/ROM comparison and link audit. Six
FM6 kernel/data comparisons pass after individually checked relocations;
vendor objdump shows readonly base+5692 resolving to the unchanged768-byte
algorithm table. All630 prepared input hashes and app-main/linker/build-fragment
hashes match. Pre-task heap135564bytes. Layout/startup/cipher/NOR review is still
in progress; V24 is not admitted or installed. V23 remains healthy idle.

[verified, offline] Exact V24 candidate
`a64d6e17162d96367f8ba9fb49c9c07a8839585be63c5aef5553bc0b8b086a0d`
is admitted for138 sectors `[0x4000,0x8e000)`; app ends0x8df1c. Independent
five-section objcopy matches. Full cipher/CRC/protected-region checks and NOR
install/restore/interrupted pages7/1111/2183/2199 pass. Sixteen static ranges
are disjoint below the heap; engine counters add96bytes. Main workload frames
remain unchanged, with20bytes for the new observer. Actual compiled branches
reserve UART18/1024 before parent16/2048, skip parent on UART failure, retain
the200-tick window,34829-tick budget and120000ms lifetime. Eight compiled hook
sites, four-region bounds and timer/counter arithmetic were reviewed. The two
instrumentation preimages exactly match V23 prepared wrappers; app_main is
byte-identical. Final native replay1PASS; transaction/reset suite79PASS.
This is offline admission only: target startup/PCM/counts/stack remain to be
checked. V23 is still installed and healthy idle; no analog acceptance.

### V24 engine detail — target result

[verified, hardware] Exact `a64d6e17…` passed fresh startup ready/PING/ARM/ENTER
in 79.0 ms, responsive WL82/UBOOT1.00 inquiry and two matching full 8 MiB
reads. Both factory restores, the same-image RUN reinstall and full readbacks
passed. WINDOW 10113 and RUN 87926 resets are consumed and must not be retried.
One backup invocation supplied an incorrect expected USB number (35 versus
observed 34); its identity guard refused before loader/device commands. The
failed output directory is preserved; the succeeding unique backup used 34.

[verified, hardware] All four mixed PCM hashes, control counts, arithmetic
patterns, 32 unit, 24 stage, 24 worst-stage, 12 detail, 96 preparation,
32 worst-unit and 16 engine-region records pass strict correlation. Both
engines produce 31,919 / 31,917 / 31,918 / 31,918 native 12-frame blocks and
352,832 resampler outputs per case. The FM6 worker completes 81,308 paired
jobs with zero errors/refusals/wrong-core records and exits. Free heap is
stable at 93,620 bytes; unused parent/worker stacks are 2,436/8,192 and
3,260/4,096 bytes. Receive-only PID 291241 was verified twice before a single
SIGTERM; its SSH session terminated before ordinary PING acknowledged.

Nested mean times per 64-frame block, in microseconds (includes instrumentation):

| Case | Macro synthesis | Macro resampling | Drum synthesis | Drum resampling |
| --- | --- | --- | --- | --- |
| 0 | 602.500 | 284.708 | 97.125 | 270.000 |
| 1 | 675.375 | 284.708 | 97.042 | 269.875 |
| 2 | 673.167 | 284.583 | 96.875 | 269.375 |
| 3 | 672.125 | 283.917 | 96.958 | 269.875 |

Total means are 2,634.292 / 2,847.583 / 2,922.458 / 3,013.958 us; maxima
3,038.958 / 3,197.750 / 3,470.583 / 3,662.375 us. Every 5,513 blocks in every
case misses the unchanged 34,829-tick deadline: FAIL. The counters preserve
the actual mixed workload but add measurement cost; these totals are not a
clean optimization comparison. Native Macro synthesis remains the largest
single region, while the two resamplers together cost roughly 554 us/block.
Neither a named-key result nor this diagnostic establishes analog acceptance.

Private raw SHA-256:
`dca87de88aade921286cb0fc467943853814c588f118416542297c856e52ae4b`.
Raw/facts and strict parsers remain in ignored `scratch/devkit-20261023/`.
V24 is healthy idle, current restore range remains 138 sectors
`[0x4000,0x8e000)`. No UART/KA6 capture remains live. Actual DAC fault validation
and representative 30-minute analog soaks remain undone. PR #155 stays draft.

[verified, tool coverage] Refreshed Rarefaction status still selects the primary
checkout; its `fm1_app_render` body is older and reports no indexed callers.
It cannot establish this external worktree's current call graph. Serena session
433b2929 selects the absolute performance worktree and locates the actual Python
`instrument_engine_profile`; its conditional C observer query is empty, so
source and vendor machine-code inspection remain necessary for that path.

### Two-way VCF scheduling — offline comparison

[verified, source/vendor code generation] V24 identifies native Macro generation
as the largest measured engine region. Its VA+Filter implementation is already
in SRAM, including its called variable-shape oscillators. An offline private
prototype adds only a two-way compiler unroll directive to the VCF sample loop.
It preserves all 11,290,624 PCM bytes across eight mixed cases (two schedule
cycles), with divide-by-zero trapping enabled. PCM SHA-256:
`c676e9b496a63e3817428ade9c067d75a2fd81bd786da7c0ad06ee6255c4f81b`.
The vendor emits a two-sample loop and remainder path: VCF code grows from
1,256 to 2,524 bytes, while its local frame falls from 56 to 52 bytes.
This is code-generation evidence, not a speed result. The prototype's stale
provenance deliberately excludes it from image admission.

[verified, source/tests] Optional `--vcf-unroll` now reproducibly applies that
directive in the private preparation and records its input hash. It requires
timing-only profiled resident O3; defaults and production DSP sources remain
unchanged. Drift/duplicate and unsupported-mode guards are tested. The combined
engine-detail/FIR replay now compares full PCM bytes across eight cases with
and without the VCF option. Focused renderer/profile suite: 96 PASS, one
unavailable 32-bit replay skipped. A fresh vendor build completes; its complete
SDK/machine-code/layout/startup/cipher/NOR review and image admission remain
pending. Nothing from this comparison has been installed. V24 remains healthy
idle, and the mixed deadline/analog acceptance gates remain unsatisfied.

[verified, exact offline admission] Fresh V25 ELF
`d94ac3376b7c92341e40bdb1c14db3fd1d3957358f985eeebbd27e4607db4506`
independently exports app
`9be3bd6b2aeac0d1c0415da15a9ac865922070cf423a6b93196e70e29b826d00`
(565,980 bytes, flash end 0x8e3fc). Its VCF function bytes match the reviewed
prototype exactly. Protected SDK/ROM code and six FM6 kernels/tables pass
checked relocation comparisons; link audit passes with its scheduling item
resolved by exact vendor comparison. All 630 inputs match. Prepared app-main,
linker and build-fragment hashes remain identical to V24. Sixteen static ranges
are disjoint below the heap; pre-task heap is 134,348 bytes. Compiled UART-first
allocation/guard, 200-tick recovery delay, 34,829-tick deadline, 120,000 ms
worker lifetime, all eight profiler sites and unchanged main workload frames
pass review. The VCF local frame is 52 bytes, down from 56.

Independent section copies, cipher/CRC/protected regions and a 139-sector
metadata-last NOR model pass, including interrupted pages 7/1111/2199/2215.
Exact candidate:
`5c57aab671f77465c8024fa94f04e0a2b5c677ad8a67aaeaf68a5762104ad22a`.
Only that image is admitted for `[0x4000,0x8f000)`. The current V24 restore
retains its 138-sector range. Transaction/reset suite: 80 PASS. The first
copy-export attempt lacked the toolchain mount and stopped before packaging;
the corrected mounted run passed independent objcopy/cipher checks. Hardware
startup, PCM, timing and stack checks remain pending. No V25 image has been
installed or hardware accepted; no analog/soak acceptance is claimed.

### V25 two-way VCF scheduling — target result

[verified, hardware] Exact `5c57aab6…` completed the protected cycle: fresh
ready/PING/ARM/ENTER in 79.0203 ms, responsive WL82/UBOOT1.00, two matching
full current-image and new-image backups, factory restores and same-image
RUN install with full 8 MiB readbacks. The current V24 restore used 138
sectors; V25 uses its reviewed 139-sector range `[0x4000,0x8f000)`.
WINDOW 25024 and RUN 68147 are consumed and must never be retried.

All four mixed PCM fingerprints, control counts, arithmetic patterns and
32 unit / 24 stage / 24 worst-stage / 12 detail / 96 preparation /
32 worst-unit / 16 engine-region records pass strict correlation. All 81,308
paired jobs complete without errors/refusals/wrong-core records, followed by
finite worker exit. Free heap remains 92,404 bytes; unused parent stack is
2,436/8,192 bytes and worker stack 3,260/4,096 bytes. Sole RX PID 300125 was
verified twice before one SIGTERM; session 90316 was terminal before the
ordinary PING acknowledged healthy idle. No capture remains live.

| Case | Mean us | Maximum us | Late /5513 | Mean improvement vs V24 |
| --- | ---: | ---: | ---: | ---: |
| 0 | 2622.958 | 3032.042 | 5513 | 0.430% |
| 1 | 2835.583 | 3171.208 | 5513 | 0.421% |
| 2 | 2910.667 | 3454.958 | 5513 | 0.403% |
| 3 | 3002.167 | 3631.208 | 5513 | 0.391% |

Native Macro means fall to 591.917/664.000/662.458/661.625 us per block;
the combined two resamplers remain roughly 554 us. The small total gain does
not justify treating loop unrolling as a solution: every block still fails
the unchanged 34,829-tick deadline. No first block, event, engine, native
rate, filter or PCM requirement was removed. Actual DAC fault validation,
KA6 analog captures and representative 30-minute soaks remain undone.

Private raw SHA-256:
`6e9f60e34c74e8e9c4a85c88e7c6247bfab6ec7d76be9cd6caa07d6c0bab8e5c`.
Raw/facts and strict parsers remain in ignored scratch storage. PR #155 stays
draft and unmerged. At this checkpoint, exact source c63af14c CI40260047105
has three jobs remaining and no failures; Pages40260047129 succeeded.

### VCF oscillator/filter section counters — offline

[implemented, not hardware accepted] Optional `--vcf-profile` requires the
existing timing-only O3 engine profile. It instruments only the privately
prepared VCF source: region 4 covers both oscillators, region 5 covers filter
parameter preparation and the sample loop. Both are nested inside the existing
Macro generation total. The explicit diagnostic flag expands observer storage
from four to six regions; default builds and DSP operations remain unchanged.
Source-drift/duplicate guards and preimage hashes retain reproducibility.

[verified, offline] 100 focused renderer/profile tests pass; one unavailable
32-bit replay skips. The positive native O3 test preserves all 11,290,624 PCM
bytes across eight mixed cases, checks matched per-voice section frame/call
counts, accounts for nested fake-clock reads, resets counters and exercises
timer wrap. A fresh V26 vendor build completes with downloader disabled.
Full machine-code/SDK/kernel/layout/UART-first/cipher/NOR review and admission
remain pending. V26 is not staged or installed; V25 remains healthy idle.
Rarefaction still cannot resolve this external worktree's new Python preparer;
Serena locates its actual instrumentation helper. Source and vendor inspection
remain required for target ABI and conditional instrumentation coverage.

[verified, exact offline admission] V26 ELF
`683d3c71e90a0d81410689bc3fbeba196c19738cf1002a59b7c09cc2ba8b337f`
exports app `b3ed05e620186b8e6db9d35740a374a8e8d3bd421f10002169f88719cb2a93f6`
(566,108 bytes; end 0x8e47c). Protected SDK/ROM routines, six FM6 kernels and
tables, all 630 input hashes, 16 disjoint static regions, UART-first allocation
and success guard, 200-tick window, 34,829-tick budget and finite worker lifetime
pass actual vendor-code review. Observer bounds are six regions with twelve
compiled call sites. Its counters use 144 static bytes; pre-task heap is
134,252 bytes. Main workload frames remain unchanged. VCF local frame grows
from 52 to 56 bytes; hardware stack measurement remains required.

Removing only the four new observer calls and declaration gives the exact
V25 prepared VCF source. Prepared app-main and linker hashes are unchanged.
Independent five-section objcopy, cipher decode/CRC/protected boot/config/tail
and the 139-sector metadata-last NOR model pass, including restoration after
interrupted pages 7/1111/2199/2215. Exact candidate
`836f2967e245dd4848704ec3bc282c9b1364f121db855f6fb8db54acd9e27797`
is admitted only for `[0x4000,0x8f000)`. All prior image bounds remain intact;
transaction/reset suite: 81 PASS. Not installed or hardware accepted.

### V26 VCF sections — target result

[verified, hardware] Exact `836f2967…` completed the full protected cycle:
fresh ready/PING/ARM/ENTER in 79.0732 ms, responsive WL82/UBOOT1.00, matching
two full current/new-image backups, factory restores and same-image RUN
reinstall with complete 8 MiB readbacks. Both current and new restore ranges
are 139 sectors `[0x4000,0x8f000)`. WINDOW62722 and RUN70164 are consumed;
never retry them. Sole RX PID307393 was checked twice before one SIGTERM;
session64071 terminated before ordinary PING acknowledged healthy idle.

All four PCM/control fingerprints, arithmetic patterns, 32 unit, 24 stage,
24 worst-stage, 12 detail, 96 preparation, 32 worst-unit and 24 engine-region
records pass strict correlation. Native block/output counts remain unchanged.
All 81,308 paired jobs complete with zero error/refusal/wrong-core records and
finite worker exit. Heap is stable at 92,308 bytes; unused parent/worker stack
is 2,436/8,192 and 3,260/4,096 bytes. No capture remains live.

| Case | Total mean us | Maximum us | Late /5513 | Oscillator pair us | Filter section us | VCF calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2631.542 | 3029.458 | 5513 | 260.250 | 231.125 | 113626 |
| 1 | 2847.250 | 3192.083 | 5513 | 293.000 | 260.042 | 127668 |
| 2 | 2922.625 | 3460.083 | 5513 | 292.000 | 258.958 | 127672 |
| 3 | 3015.458 | 3650.042 | 5513 | 291.542 | 258.792 | 127672 |

Both section counters match calls and 12 frames per voice call; their sum fits
inside the enclosing Macro generation total. The filter section includes
parameter setup and the sample loop, ending before interpolator destructors.
These instrumented means locate cost, not a production speed regression or
improvement. The unchanged 34,829-tick deadline still fails for every block.
An eventual timing comparison without internal counters is required alongside
actual DAC fault validation and representative 30-minute KA6 analog soaks.

Private raw SHA-256:
`3835ff6c9481d99d561d900aef020db9e4b1b44eff896254029fb0138bbbf17a`.
Raw/facts/parsers remain ignored. Source e9fcf1b8 CI40262261441 was still
running with no failed jobs; Pages40262261567 succeeded. PR155 remains draft,
unmerged; no deployment or analog acceptance is claimed.

[inferred, next offline comparison] The oscillator computes pulse-width
reciprocals each sample. Reuse is potentially exact when interpolation cannot
change the rounded pulse width. Preserve the existing rounded state, including
stalled interpolation; snapping to a requested target would change PCM.

### V27 exact rounded oscillator slopes — offline experiment

[verified, host] Optional private preparation `--oscillator-slopes` splits the
variable-shape oscillator into fixed-width and changing-width template loops.
The fixed path requires that the next interpolated width rounds to the current
state, with a finite denominator inside (0,1); it never snaps state to a target.
The original interpolation and sample arithmetic remain in both loops. The
option requires timing-only, profiled, resident O3 preparation and records the
original header hash. Default and upstream source files remain unchanged.

The full eight-case renderer replay with VCF profiling/unrolling preserves all
11,290,624 PCM bytes. Separate exact-float stress covers four template modes,
48,000 blocks, eight sizes (1/2/3/7/12/31/64/127), endpoints, resets, ramps and
settled widths: 5,928,000 bytes match; Linux FP exception traps remain clear.
The focused renderer/profile suite passed 103 tests with one unavailable
32-bit toolchain skip. Two new harness mistakes were corrected (wrong overload
mutation, executable/include-directory path collision); their rerun passed both
tests. No implementation change was needed for those harness failures.

[verified, vendor build; not admitted] Formal V27 ELF
`b15713f529e216ad1262103553b87abd44118a76ad977397c476e6b28e783ea7`
exports app `b37bd458e2e877534222e01e38d299a65b693fa04a73ccbbd0085844ebdeeb42`
(570,620 bytes). Initial SDK/ROM relocation review passes. Pre-task heap is
131,756 bytes. Full layout, input manifest, actual loop/stack, cipher/CRC and NOR
review remain required before any hardware admission. No V27 image is staged
or installed. Private prototypes have intentionally stale provenance and must
never be flashed. V26 remains the healthy idle installed image; its mixed
workload still misses every deadline. No analog acceptance is claimed.

[verified, exact offline admission] V27's 630 input hashes and prepared
startup/link/make hashes pass; only the oscillator header and reviewed preparer
input differ from V26. Six FM6 kernels/tables, SDK/ROM relocation checks, 16
disjoint static ranges, recovery allocation/guard and unchanged timing/lifetime
constants pass. The fixed non-sync loop's reciprocals at 0x1c198d2/0x1c198da
precede the sample back edge to 0x1c19920. Fixed/changing oscillator local frames
are 64/60 bytes; enclosing VCF local frame is 64 (previously 56). Main workload
frames are unchanged. Hardware stack measurement remains required.

Independent five-section objcopy matches the flat app. Cipher decode, CRCs,
protected boot/config/tail checks pass. Exact candidate
`23ce7c2d55059beae51625efd849c15b71a180fc33b7301e55d8b310228625ec`
is admitted OFFLINE for 140 sectors `[0x4000,0x90000)`, ending app at 0x8f61c.
Metadata-last NOR install/restore and interrupted pages 7/1127/2215/2231 restore
correctly. Previous images retain their original boundaries, including installed
V26's 139 sectors. No hardware speed or acceptance is claimed.

### V27 oscillator slopes — target result

[verified, hardware] Exact `23ce7c2d…` completed the full protected cycle:
fresh ready/PING/ARM/ENTER in 78.7228 ms, responsive WL82/UBOOT1.00, matching
two full current/new backups, V26 139-sector and V27 140-sector factory restores,
same-image RUN reinstall and all full 8 MiB readbacks. WINDOW42848 and RUN69384
are consumed; never retry. Sole RX PID315493 was checked twice before one
SIGTERM; session38498 terminated before ordinary PING acknowledged healthy idle.

All seven strict parsers pass: four mixed PCM/control fingerprints, arithmetic,
32 unit/24 stage/24 worst/12 detail/96 preparation/32 worst-unit/24 engine
records, unchanged native counts, 81,308 paired jobs without refusal/error/wrong
core and finite worker exit. Heap remains 89,812 bytes; unused parent/worker
stack is 2,436/8,192 and 3,260/4,096 bytes. No RX or analog capture remains live.

| Case | Total mean us | Maximum us | Late /5513 | Oscillator pair us | Filter section us |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 2597.458 | 2984.042 | 5513 | 245.208 | 228.833 |
| 1 | 2811.375 | 3177.458 | 5513 | 276.125 | 257.458 |
| 2 | 2886.667 | 3462.042 | 5513 | 276.208 | 257.625 |
| 3 | 2977.333 | 3625.708 | 5513 | 275.833 | 257.250 |

Total means improve 1.23–1.30 percent versus identically instrumented V26;
this is insufficient: every block still misses the unchanged 34,829-tick
budget. The next measurement must remove internal profiling overhead while
retaining outer timing, exact replay and recovery checks. Actual fault-validated
DAC/KA6 and representative 30-minute analog soaks remain undone.

Private raw SHA-256:
`224f7c89539ef98779d6ff5d0711f84afe097d8dd42fb06bb6b40e779ce5bf8f`.
Source ad4e3622 CI40265093573 remains running; Pages40265093502 succeeded.
PR155 is draft and unmerged; no deployment or audio acceptance is claimed.

### V28 outer-only timing — offline comparison

[verified, host] `--outer-timing-only` retains requested placement validation,
DSP transformations and the renderer's outer timer, while omitting preparation,
engine/VCF instrumentation and internal observer compile flags. Effective flags
are recorded as disabled in the receipt. Defaults retain existing profiling.
Full eight-case optimized PCM matches with internal profiling absent. Focused
suite: 108 PASS, one unavailable 32-bit toolchain SKIP.

[verified, vendor build; not admitted] ELF
`610d3671c16b118113e3c8031f1fb9454b64181626ed859d0eb6cc290af3f9d9`
exports app `bcef491fb815c168c3d08d4d0e935daf2a0d783909fb643be3034478de858c33`
(566,620 bytes). No internal observer routines/counter arrays remain linked.
Initial SDK/ROM relocation review passes; pre-task heap is 133,900 bytes.
Full input/layout/stack/UART-first/code/cipher/NOR review is still required.
No V28 candidate is admitted, staged or installed. V27 remains healthy idle.


### V28 outer-only timing image admission (2026-10-26)

[verified] Exact offline image `389b6fa9…6589c53` is admitted only for the dev
board's 139 sectors `[0x4000,0x8f000)`. CURRENT V27 retains its independent
140-sector restore range. Eight-case PCM replay is byte-identical; 108 focused
checks pass with one unavailable 32-bit toolchain check skipped. All 630
manifest inputs match; only internal observer transformations and their compile
flags differ from V27. Prepared startup, linker script and make fragment match.
Vendor ELF has no internal observer routines/counters. Its outer timing frame
is 176 bytes; app render remains 296, UI sync 1160, mod tick 288 and planner
1060. Pre-task heap is 133900 bytes. Actual machine code preserves UART priority
18 / 4 KiB allocation before priority 16 / 8 KiB parent allocation, the success
edge, 200-tick recovery delay, 34829-tick paired budget and finite lifetime.
Six FM6 kernels/tables match after checked relocations; startup copies/BSS,
static ranges, dormant SDK/ROM path and link audit pass, with the audit's manual
SDK scheduling item resolved against vendor disassembly. Independent five-section
objcopy, cipher/CRC and protected boot/cfg/tail checks pass. The offline NOR model
restores interrupted pages 7/1111/2199/2215 and independently restores all 140
CURRENT sectors. Hardware installation, actual timing and analog acceptance are
still pending. Private binaries and review artifacts remain ignored.


### V28 outer-only target result and validation gap (2026-10-26)

[verified, hardware] Full protected cycle passed: two CURRENT V27 backups,
CURRENT140 restore, V28 WINDOW139 install, fresh startup ready/PING/ARM/ENTER
79.1764 ms and actual ROM inquiry, two NEW backups, NEW139 restore and SAME
RUN install, each full 8 MiB comparison exact. WINDOW18612 and RUN83525 are
consumed; never retry. Sole RX PID321860 was checked twice before one SIGTERM;
session63010 terminated before ordinary PING acknowledged healthy idle.
No RX/KA6/build/device operation remains live. CURRENT V28 restore uses139
sectors `[0x4000,0x8f000)`.

| Case | Mean us | Maximum us | Late /5513 |
| --- | ---: | ---: | ---: |
| 0 | 2456.792 | 2871.042 | 5513 |
| 1 | 2668.750 | 2980.625 | 5513 |
| 2 | 2743.708 | 3253.958 | 5513 |
| 3 | 2834.917 | 3423.958 | 5513 |

[verified] Four mixed PCM/control fingerprints match; internal observer records
are absent. Paired jobs total81308 with no refusal/error/wrong core and finite
exit. Heap91956 is stable; unused parent/worker stack2664/8192 and3260/4096.
Every block still misses34829 ticks: observer overhead does not explain the
remaining gap. Raw SHA256 is
`81ed2eb451810281349e0c91e0a5943631c220ed44fa1e2db03f35e41008f39e`.

[verified, validation gap] The full supplement parser FAILS because the
standalone arithmetic probe did not run: `sdk_worker.c` coupled it to the
removed `LUNAR_RENDERER_PROFILE` flag. Pair-only results above are separately
validated; no arithmetic pass or hardware acceptance is claimed for V28.
The next source correction makes that preflight unconditional for timing images,
after the200-tick recovery window and before initialization, with a regression
test executing the actual worker and arithmetic probe without profile flags.
The new test fails against the old worker (missing32 probe yields). A new exact
vendor image and full admission review are required before any further install.
CIaa70a386 remains running; Pages40267102487 succeeded. PR155 is draft and
unmerged. Fault-validated DAC/KA6 and representative30-minute soaks remain undone.

[verified, host correction] Arithmetic preflight is now independent of internal
render observers, while remaining after the 200-tick UART recovery window and
before renderer initialization. The actual-worker regression failed against the
old guard and passes with the correction. Bounded Aeon renderer/arithmetic tests
complete with 101 passed and one unavailable-toolchain skip (59.49 seconds).
This source correction has not been built into or installed as a new vendor
image; it does not retroactively close V28's hardware arithmetic coverage gap.

### Ordered per-engine replay proof (offline, 2026-10-26)

[verified, host only] Two private app-copy experiments preserve all 11,290,624
PCM bytes across eight cases (two consecutive four-case mixed passes), including
all control fingerprints. The first records Macro's render/note/parameter/bend/
per-note operations and replays them after sequencer dispatch. The second records
all four sounds, replays Macro on a persistent pthread and the other sounds on
the caller, then joins before insert processing and ordered mixing. Queue peaks
are 3/6/3/3 operations against capacity128. Neither experiment changes native
rates, controls, sample boundaries or sum order within an engine. Sources and
logs are private under the devkit task scratch storage; no device code or image
was installed. This proves this fixed arrangement's replay result, not arbitrary
engine/model independence or target speed.

[verified, host] A separately compiled address/undefined-behavior sanitized
concurrent replay also completes with identical bytes and no sanitizer error
(leak detection disabled for the permanent test worker). ThreadSanitizer builds,
but cannot start: `unexpected memory mapping`; a per-process `setarch -R` retry
is denied by the container. No race-safety pass is claimed. Target admission
still needs explicit ownership/publication, bounded overflow/timeout behavior,
permanent late-worker storage, a reviewed independent-engine allowlist and vendor
machine-code/layout/UART recovery verification. Existing copied FM6 kernel
parallelism cannot simply remain nested inside a busy whole-engine worker.

[verified] Source18600d4f is remotely backed up. Exact CI40268655368 remains
in progress without a failing job at inspection; Pages40268655347 succeeded.
PR155 remains draft and unmerged. Current hardware remains V28 idle; its missing
arithmetic preflight and failed deadlines are unchanged by these host proofs.

### Bounded ordered queue implementation (offline, 2026-10-26)

[verified] `firmware/devkit/renderer_queue.{h,cc}` now implements fixed command
storage, caller/worker publication and permanent refusal after a protocol fault.
It creates no task and is absent from default build lists. It is not installed
on the board. The caller records four independent engine streams, publishes
sound1 to one worker and executes the others, then waits before consuming outputs.
No engine may share mutable globals with concurrently executing engines; engine
and output ownership must persist even if a timed-out worker completes late.

[verified, host] Both normal and address/undefined-behavior versions of
`tests/test_devkit_renderer_queue.py` pass (2 passed,0.90 seconds). Each executes
2,000 interleaved concurrent batches against independent ordered callback results.
Fault cases include full-capacity overflow before publication, state and command
refusal, duplicate batch execution, elapsed-clock wrap, a stalled clock's poll
bound, and workers completing after timeout both before and during execution.
A late acknowledgement never allows reuse. A separate private app-copy replay
using this actual queue completes44,104 batches/error0 with peaks3/6/3/3 and all
11,290,624 PCM bytes identical across eight mixed cases. This remains offline;
no SDK backend, new image admission or target scheduling speed is established.

### Permanent queue bridge and unintegrated SDK backend (2026-10-26)

[verified] Added a C ABI bridge around the ordered queue using aligned permanent
storage and explicit placement construction. Initialization is single-use; no
heap allocation, global constructor, destructor or reset/reuse API is provided.
Malformed wide command fields are rejected before narrowing. Host bridge tests
exercise successful replay, permanent refusal, invalid initialization and each
wide-field rejection. Together with ownership and ASan/UBSan queue tests, the
focused Aeon run passed **3 tests** (1.18 s; private
`renderer-queue-bridge-tests.log`). This is host evidence, not target ABI proof.

[inferred] The new, currently unintegrated `renderer_queue_sdk.c` backend follows
the existing static SDK task contract: CPU1, priority 16, permanent 2048-word
stack, 120-second finite work interval and explicit exit reporting. It rejects
nested FM6 SDK workers at compile time. Its 100 ms protocol refusal bound is
separate from the unchanged 34829-tick audio deadline. It has not yet been
compiled against the vendor SDK, linked, admitted or installed. No default
build list, app callback, preparer, timer or device behavior changes here.
Next: guarded fixed-arrangement integration, explicit independent-engine/model
allowlist, fatal propagation retaining the arena/timer after timeout, host PCM
and lifecycle checks, then exact vendor/layout/recovery/cipher/NOR review.

[verified, subsequent offline check] All three queue/backend objects compiled
with the pinned vendor pi32v2 toolchain using the reviewed V28 SDK include/config
snapshot, with the old FM6 worker flags removed. No link or image was produced.
Commands and objects remain private under Aeon
`renderer-queue-sdk-compile-v1/`; log `renderer-queue-sdk-compile.log`.
The actual SDK backend source also passed a single-threaded controlled scheduler
harness covering creation failure, startup timeout, wrong-core start/worker,
finite lifetime, worker refusal, normal stop and failed queue status. This test
suppresses only target inline assembly and substitutes SDK calls; it establishes
control flow, not concurrency, target task ABI, cache publication or stack use.
Together with the bridge/ownership tests: **4 passed, 1.27 s**, private
`renderer-queue-lifecycle-tests.log`. The initial harness failed to suppress
pi32 assembly and then interfered with libc assembly aliases; including standard
headers before the test macros corrected the harness without changing backend
source. Guarded preparer/app integration and target admission remain pending.

### Guarded whole-engine queue integration (2026-10-26)

[verified] The explicit --engine-queue preparer option now requires the mixed,
timing-only, resident O3, outer-observer-only experiment. It rejects the FM6
kernel worker/scheduling option. It selects CPU0 parent priority16, UART18,
a finite CPU1 worker with permanent 8 KiB stack, and records queue input hash,
fixed sound allowlist and protocol budget in the preparation receipt. Default
app/build behavior stays unchanged. Only prepared copies record engine calls;
note counters and UI lock mirrors stay at their original sequencer callbacks.
The fixed sound stream IDs are dx7/macro/drums/dx7, and recorded Macro model
changes away from model0 are refused. This is not an arbitrary-engine scheduler;
independent mutable-global/transitive engine review remains an admission gate.

[verified] The actual prepared app, actual C bridge and queue preserve all
11,290,624 PCM bytes across eight mixed cases/44,104 batches; queue peaks remain
3/6/3/3. A whole-renderer injected dispatch timeout returns no timing case,
leaves completed block/case counts zero, preserves caller output, and permits
one late worker completion into the still-live app buffers while permanently
refusing reuse. App returns NULL before effects/mixing; renderer checks before
sample conversion/hash; timing loop checks before a completed-case report.
The SDK wrapper retains timer/arena/task storage on failure. Recovery reservation
and its 200-tick window precede arithmetic, worker startup and renderer init.

[verified] Focused renderer, queue and integration suite: 110 passed, 1
unavailable-toolchain skip in 68.55 s (Aeon private
renderer-queue-integration-focused.log). The first extended test needed an
extern-C wrapper around the existing C-only timing header; no target linkage
behavior changed. A fresh private V29 vendor build linked successfully
(renderer-queue-v29-build.log, build-sdk-renderer-queue-v29). It is NOT admitted,
staged, installed or hardware accepted. Exact machine code, independent app
copy/cipher, layout, UART-first startup, engine-global independence, SDK guard
and NOR restore reviews remain required before any device operation.

### Whole-engine queue V29 offline admission (2026-10-26)

[verified] The private V29 app is 567,804 bytes. Independent vendor objcopy
and ELF section concatenation agree byte for byte. The full candidate passes
independent reference-cipher decoding, directory/app CRCs, protected-byte and
cfg preservation checks. Its exact SHA is
`91f34e30db7ed5008628c98a6104a4269cd1746a2280b5e9b6d2167f05772768`;
139 changed sectors occupy `[0x4000, 0x8f000)`. Its exact transaction entry is
admitted for this experiment; no hardware installation or acceptance is implied.
All 77 transaction tests pass. The offline NOR model checks exact install and
restore, metadata-last ordering, four interrupted page positions and independent
restoration of the currently installed V28 image; it sends no device commands.

[verified] All 636 preparation input hashes and the prepared app-main, linker
script and make fragment hashes match. Exact vendor instructions preserve UART
priority18 reservation before success-only CPU0 parent priority16 creation,
200 recovery ticks before arithmetic and the permanent 8 KiB CPU1 worker, and
worker readiness before renderer allocation. Queue/app/pool/stack static ranges
do not overlap; pre-task heap is 119,788 bytes. Request publication, worker
completion and caller acquisition retain the reviewed csync ordering. SDK
link checks pass with no forbidden writes; the manual scheduling item is
covered by exact normalized vendor-code comparison with the reviewed baseline.

[verified] Bounded model0 independence review covers 18 source files and 23
compiled functions, including smoothing, glide, rate conversion, pitch tables,
VCF oscillators/filter, envelopes and post-processing. Mutable DSP state belongs
to the passed instance/voice/output; shared pitch/FIR/parameter tables are
immutable. The actual model0 vtable resolves to the reviewed VCF implementation.
Drums' global Random stays on CPU0, and other Macro models remain refused.
This is source/instruction evidence, not a runtime race proof. Individual target
frames include a largest 1,160-byte frame; SDK/IRQ overhead and dynamic high-water
marks still require target validation. TSAN remains unavailable due to its
mapping failure, so no TSAN pass is claimed.

[verified] The private strict queue parser accepts a complete synthetic capture,
reports late blocks separately as deadline failure, rejects 17 fault mutations
and rejects the actual V28 pair-only capture. It requires final worker exit and
exact completed/job counts, correct PCM/control/arithmetic, stable heap and
positive stack headroom. A per-case job counter may lag one acknowledgement;
final equality is mandatory. Synthetic fixtures are not hardware evidence.
All private scripts, binaries and detailed reports remain in ignored storage.
Rarefaction's named query could not reach IMAGE_PLANS in this worktree because
its root/default bounded scan is the primary checkout; Serena resolved the
actual worktree symbol, with direct source/tests and vendor outputs used for
verification. Neither tool establishes pi32v2 ABI correctness.

### V29 whole-engine queue target result (2026-10-26)

[verified] V29 completed the protected UART-only cycle: two full CURRENT V28
backups, byte-identical factory restore over 139 sectors, WINDOW install/full
readback, sole verifier armed before one reset, fresh startup PING/ARM/ENTER
acknowledgements in 79.4182 ms and responsive ROM, two full NEW V29 backups,
second byte-identical factory restore, SAME RUN install/full readback, sole RX
armed before one RUN reset. Both reset receipts are consumed and must never
be retried. The receiver was closed after two exact argv checks and its capture
session reached terminal before an ordinary PING was acknowledged. V29 is now
healthy idle; future restore range remains `[0x4000, 0x8f000)` (139 sectors).
No physical buttons, FM1 traffic or KA6 capture were used.

[verified] The strict private parser passes all four arithmetic checks, four
mixed PCM/control fingerprints, 22,052 queue jobs/completions with zero errors
or wrong-core reports, finite worker exit and expected queue peaks. Heap stays
77,844 bytes; unused parent stack is 2,748/8,192 bytes and unused worker stack
7,452/8,192 bytes. The raw private UART SHA is
`6fba467bfb9a1f0fe6f8b57a90870ed62b29d8e2e410b4b3efe975280fe7b7c3`.

[verified] Deadline acceptance FAILS. At 24 MHz, mean ticks are
46,550 / 48,029 / 48,853 / 52,684 (1,939.583 / 2,001.208 / 2,035.542 /
2,195.167 microseconds); maxima are 55,406 / 56,154 / 60,304 / 66,459.
Late counts are 5,512 / 5,513 / 5,513 / 5,513 of 5,513 per case, against the
unchanged 34,829-tick deadline. Mean times improve approximately 21–26% over
V28, but this does not establish dropout-free audio or analog acceptance.
PR155 remains draft and unmerged. Actual DAC/underrun fault validation and
representative 30-minute analog soaks remain outstanding.

### Optional Macro/Drums CPU1 partition (2026-10-26)

[verified] The diagnostic preparer now accepts `--engine-queue-drums` only with
the existing guarded whole-engine queue. It records CPU1 sounds `[1,2]` and
serializes Macro model0 then Drums; CPU0 keeps DX7 sounds `[0,3]`. The default
partition remains `[1]`. No rate, filter, event order, timeout or audio deadline
changes. Fifteen focused tests pass in the bounded Aeon container (14.69 s):
both partitions preserve 11,290,624 PCM bytes over 44,104 batches, retain timeout
refusal/output lifetime, and pass 2,000-batch operation/ownership checks in normal
and ASan/UBSan builds. Render callbacks explicitly check their owning thread.

[verified] Source inspection shows Drums saves/restores stmlib's global Random
around its per-pad rendering. Macro and Drums execute serially with the new
partition. DX7 LFO sample-and-hold uses its instance's randstate; modulation
random generators also use per-instance state. This is a bounded source lead,
not completed target transitive-independence or race proof. TSAN is still
unavailable. A fresh vendor build, complete independence/instruction/stack and
layout/recovery/SDK/cipher/NOR reviews remain prerequisites to admission. No new
image has been admitted, staged or installed; V29 remains healthy idle.


### V30 Macro/Drums queue offline admission (2026-10-26)

[verified, offline] Exact private candidate
`14e39d30b7e01be23d5ecc9e9ab2bcb5cb5e5f4f86f6af57bf4402af34d786c2`
is admitted for 139 sectors `[0x4000,0x8f000)`. Independent vendor objcopy
matches ELF section concatenation (567836 bytes, app SHA `aa725189…f26270d2`).
Reference cipher decoding, directory/app CRCs and protected boot/cfg/tail checks
pass. All 636 preparation hashes match. Existing focused and broader tests
passed 115 checks, with one unavailable-toolchain skip; TSAN remains unavailable.

[verified, bounded review] CPU1 executes Macro model0 then Drums; CPU0 executes
DX7 sounds 0 and 3. Thirty-six source files and 35 compiled functions were
reviewed, including Drums voices, resampling, filters and transitive RNG use.
Drums' global stmlib RNG is saved, per-pad seeded and restored serially on CPU1.
The only direct RNG-address references in the final ELF are Drums RenderVoice,
RenderBlock and the excluded Chiptune model. Concurrent DX7 sample-and-hold and
modulation use instance RNG state; DX7 shared rate initialization precedes work.
Sequencer/control recording precedes publication; effects/UI/mixing follow ACK.
Macro model0's actual vtable matches its reviewed VCF implementation. These
source/instruction checks do not establish runtime race or cache safety.

[verified] Exact target code retains publication/acquisition csync fences and
ACK after both worker streams. UART priority18 reservation precedes success-only
CPU0 parent priority16 creation; its 200-tick recovery window precedes arithmetic,
static 8 KiB CPU1 worker creation and renderer allocation. Static ranges do not
overlap, startup copies/BSS match and pre-task heap is119788 bytes. Drums'
individual Render/RenderBlock/RenderVoice frames are96/164/224 bytes; largest
reviewed individual frame is1160 bytes. Dynamic target stack/IRQ headroom still
requires measurement. SDK link audit has no failures; its manual scheduling item
is resolved by exact normalized reviewed vendor-code/relocation comparison.

[verified, offline] NOR model installs/restores exact V30, preserves metadata-last
ordering and restores interruptions at pages7/1111/2199/2215. It independently
restores all139 CURRENT V29 sectors and sends zero hardware commands. Strict
parser self-test passes synthetic completion, distinguishes late deadlines,
rejects17 fault mutations and rejects the actual V28 pair-only capture. UART
records alone do not identify the image partition: exact transaction/readback
and the reviewed preparation receipt must accompany any future V30 result.
All scripts, binaries and detailed reports remain private and ignored.
V30 has not been staged or installed. V29 remains healthy idle; its missed
deadlines and outstanding fault-validated analog30-minute acceptance remain.


### V30 Macro/Drums queue target result (2026-10-26)

[verified, hardware] Full UART-only protected cycle passed: two full CURRENT
V29 backups, CURRENT139 byte-identical factory restore, V30 WINDOW install/full
readback, fresh startup PING/ARM/ENTER in78.9898ms and responsive actual ROM,
two full NEW V30 backups, NEW139 factory restore and SAME RUN install/full
readback. WINDOW37316 and RUN39436 receipts are consumed; never retry.
The first unprivileged backup stopped on EACCES before opening the device;
its receipt was retained and the existing sudo path used a new directory.
Sole RX PID351570 was checked twice before one SIGTERM; capture50650 reached
terminal255 before ordinary PING acknowledged healthy idle. No RX/KA6/build or
device operation remains live. CURRENT is V30 `14e39d30…34d786c2`,139 sectors
`[0x4000,0x8f000)`; no physical buttons or FM1 traffic were used.

[verified] Strict parser passes arithmetic4, mixed PCM/control4,22052 completed
queue jobs with zero wrong-core/error/refusal, expected peaks and finite worker
exit. Heap77844 bytes is stable; unused parent stack2748/8192 and worker7452/8192.
Private UART SHA256:
`30d4182f48b184ac0fbe69740ebf486e1eacf3d991c4e706d5977570bda7f9a2`.

|Case|Mean us|Maximum ticks|Late /5513|Mean regression vs V29|
|---|---:|---:|---:|---:|
|0|2311.625|64060|5513|19.18%|
|1|2374.458|64893|5513|18.65%|
|2|2375.167|68780|5513|16.68%|
|3|2375.042|71215|5513|8.19%|

[verified] All cases FAIL the unchanged34829-tick deadline. The new worker
partition is correct for this fixed workload but slower than V29. No analog
acceptance is established. [inferred] Additional serialization on CPU1 is a
candidate explanation; exact attribution needs separate recording/caller/worker/
wait measurements. The next experiment should measure those regions before
another scheduling change, retain V29's default partition, and preserve all
PCM/rates/filters/first blocks. Fault-validated DAC/KA6 and representative
30-minute analog soaks remain undone. PR155 stays draft and unmerged.

### Queue critical-path timing instrumentation (2026-10-26)

[verified, host] Added explicit `--engine-queue-profile` to the existing guarded
mixed timing-only resident O3 whole-engine queue. Default partition remains
CPU1 sound1. The new define leaves all old internal profilers disabled. Five
CPU0 regions partition the outer block: before Begin, recording, caller,
wait/acquire, and after dispatch (effects/mix/UI/output conversion/hash).
A sixth measures overlapping worker execution and must not be added to them.
No timer reads occur in idle worker polling. The worker publishes its duration
before the existing completion fence/ACK; CPU0 reads it after acquisition.
Timeout/refusal or duplicate/missing samples cannot produce case completion.
All extra storage/clocks compile out unless explicitly selected.

[verified, host] Fresh tracked-source Aeon focused run passes21 tests (31.03s),
including both partitions, normal+ASan/UBSan ownership, full11,290,624-byte PCM
replay with profiling on/off, and fault lifetime. A separate aggregate test
passes (0.09s), checking all22052 blocks, separate worker overlap, worst/max
statistics and stopping before emit on missing data. The initial focused run
used stale staging sources and failed on missing build rules; fresh source
resolved it. The aggregate fixture initially omitted the engine include path;
corrected before its passing run. TSAN remains unavailable; no race proof.

[verified] No device traffic or new image admission/install occurred for this
change. V30 remains CURRENT healthy idle, its measured deadline regression
unchanged. Fresh vendor build, instruction/layout/UART-first/SDK/cipher/NOR
review and protected installation remain prerequisites to target measurement.
Final uninstrumented deadline and fault-validated analog30-minute acceptance
remain required; PR155 stays draft and unmerged.

### Queue PCM comparison arithmetic policy repair (2026-10-26)

[verified] Exact-head CI40279373239 failed its macOS Python job121429239560
in all four queue PCM combinations. The baseline used default contraction while
only the queue build specified `-ffp-contract=off`. The original failure reproduced
on this Apple Silicon Mac. Set that flag before building either side, preserving
the exact11,290,624-byte comparison and firmware arithmetic. All13 focused queue
integration tests pass locally after the correction, including both partitions
with profiling on/off and timeout lifetime checks. Initial local test attempts
could not start because pytest was absent; a private scratch dependency directory
was used. CI for the corrected source remains required. Pages40279373240 passed.
No board traffic, image admission or hardware acceptance follows from this repair.

### V31 queue region timing offline admission (2026-10-26)

[verified, offline] The private exact V31 candidate
`f9aa8f87f9895b46d71f59d267a8b16515f0a1d4b80c7296f8c2b2fdc4178612`
is admitted for a bounded diagnostic experiment,139 sectors `[0x4000,0x8f000)`.
Vendor ELF `973f0819…45226f`, app568732 bytes `ca23d276…82fca5` come from
source b482bb76; the subsequent test-only arithmetic-policy repair changes no
vendor build input. Independent vendor objcopy,636-file manifest, reference
cipher/directory+app CRC and protected configuration checks pass. Offline NOR
install/restore passes with metadata last and interruptions at pages7/1111/2199/
2215; the installed V30's CURRENT139 restore also passes the model. No device
commands are issued by these checks.

[verified] Exact final-ELF review confirms worker sound1, caller0/2/3, worker
sample before release ACK, CPU0 sample after acquire, and idle polling bypassing
clocks. UART priority18 precedes success-only parent16;200 recovery ticks precede
arithmetic, static8KiB CPU1 worker and renderer initialization. Startup copying,
BSS, nonoverlapping queue/worker/arenas and pretask heap119724 pass. Full36-source/
35-function Macro0/Drums/DX7 independence review passes the fixed workload;
individual frames exclude SDK/IRQ overhead. SDK audit has0 failures; its one
manual scheduling item is resolved by exact normalized vendor code/relocation,
late_initcall and empty syscfg checks. This establishes no runtime race/cache or
stack proof; TSAN remains unavailable.

[verified, offline] Strict region parser requires24 records and checks counts,
unique indices, nonnegative bounded values, additive CPU0 mean/worst consistency
and separate worker overlap. It rejects27 fault fixtures and earlier V28/V30
captures. All79 public transaction tests pass with the new exact-image plan and
retained V30 restore plan. Detailed artifacts remain private in
`scratch/devkit-20261023/build-renderer-queue-region-v31/` and Aeon exports.
V31 is not staged or installed. The full protected WINDOW/RUN cycle, fresh target
region/stack results and final uninstrumented deadline/analog acceptance remain
required. PR155 remains draft and unmerged.

### V31 target regions and community/recovery research, 2026-10-26

[verified] V31 f9aa8f87 completed its full protected WINDOW/RUN cycle and is
healthy idle after ordinary PING ACK. Startup recovery79.0572ms with fresh3ACK
and actualROM. WINDOW77679/RUN17180 and all older reset receipts consumed,
never retry. RUN17180terminal0; soleRX31771/PID367683 twice exactargv checked,
SIGTERM once, terminal255 before PING. Raw capture SHA256
ffde669943276b3ffba9a02cf8e39410fb9933092c170860b28dbcef143a8036.
Strict parser passes four arithmetic and four PCM/control cases,22052queue
jobs zeroerrors/finiteexit; stableheap77780, parentunused2500/8192 and
workerunused7452/8192. Means1950.167/2013/2043.25/2198.667us, all5513late
percase: FAIL34829ticks. CPU0postdispatch790..797us andrecording257..258us;
lightcase removingallwait still1715.5us. CPU1regionoverlaps, neveradd.
No RX/KA6/build/deviceop live. Instrumented timing is not final acceptance.

Owner requested deeper community architecture research and FM-1-transporter
for actual nonbooting FM1, then confirmed Pico2W/Tigard/Cynthion availability.
Read-only findings and exact revisions:
[community audio architecture and recovery](2026-10-26-community-audio-architecture-and-recovery.md).
No actual FM1 traffic or writes. Next performance work splits postdispatch
FX/mix/UI/hash before repartitioning; next recovery dependency is failed-write
history/backup and reviewed electrical/bridge plan. Campaign/PR155/hardware
acceptance remain unfinished.

### 2026-10-26 — CPU0 recording and post-join detail profiler (offline)

[verified] Added guarded `--engine-queue-detail`, requiring the existing queue
profile experiment. Ten non-nested CPU0 categories separate sequence setup,
recorded callbacks, inserts/meters, levels/mix, masters, amp, limiter, scope,
UI and output conversion/hash. Repeated sound intervals accumulate; the
bridge rejects missing/nested/unclosed/out-of-range intervals, elapsed overflow,
repeat reads and sums exceeding the outer duration. No sound/event/DSP order
changed. Hooks are inserted into the private prepared application copy only.
Default worker remains sound1. New diagnostics are not hardware admission.

[verified] Bounded Aeon host run: 27 of 28 tests passed initially, including
all six full-app PCM combinations (profile off/on/detail, both worker partitions),
each comparing all 11,290,624 PCM bytes across44,104 batches and exercising
permanent timeout/buffer lifetime. The new negative test exposed that a null
read did not consume/refuse the detail sample; corrected that failure path.
Three focused bridge/aggregation tests then passed in0.33s. Added aggregate
sum refusal and reran the affected two aggregation variants successfully.
Existing normal/ASAN+UBSAN ownership tests passed; TSAN remains unavailable,
with no target race/cache/stack proof claimed. Logs are private under
Aeon TASK/queue-detail-v32-{host,faultfix,aggregate}.log.

[verified] Tool orientation: Rarefaction remains rooted in the primary checkout
and returns older fm1_app_render at3267; not used as current-worktree evidence.
Serena explicitly selects this absolute worktree and returns3630–3714,
matching direct source. Neither establishes pi32v2 ABI/code generation.

No new image generated, admitted, staged or installed. V31 remains CURRENT,
healthy idle; no device/UART/KA6 operation or build was live during the host
checks. All previous reset receipts remain consumed. Actual deadline and
analog acceptance remain failed/incomplete. Actual FM1 recovery stays read-only;
recorded original092 backups and interrupted-write/Cynthion history remain
in the dated community/recovery note. CI82ac40282425580 is terminal CANCELLED
by later heads; exact092cCI40286012140 was in progress, Pages40286012222 SUCCESS.

### 2026-10-26 — V32 offline admission; not installed

[verified] Exact source2b86a150 vendor link completed successfully. Final ELF
708edea952747d602f2bd36102be389ec8bdd2f4026db2ab40120a655b86712e;
570,204-byte application
3a9ca427a4b3d3ee9b2ff4d9615f221d5ee172518d67f51a7e2f9f8ff9431ddd.
Independent vendor objcopy section concatenation matches the application.
Exact final instructions retain UART18 before parent16, successful receiver
creation before parent startup,200 recovery ticks before arithmetic, static
8KiB CPU1 worker before renderer initialization, and startup copy/BSS bounds.
Queue10,368B and worker8,356B remain disjoint from app/arena; pretask heap119,532B.
Timing function has524B locals plus saved registers; live stack remains untested.
CPU0-only detail marker reads the timer directly, has12B saved registers, and
rejects malformed/overflowed intervals. The final LTO code preserves worker1,
CPU0 engines0/2/3 and csync publication/acquisition. Its detail reader checks
active10, all ten seen bits1023, and a64-bit detail sum bounded by the outer
sample. No target race/cache/stack proof is implied.

[verified] Reviewed36 source files/35 target engine functions, model0 vtable and
shared-global independence; largest individual inspected frame1,160B.
All636 preparation manifest hashes match. SDK link audit has0 failures; its
one manual scheduling item is resolved by normalized exact vendor instructions
and checked relocations, singleton late_initcall and empty syscfg review.
The strict parser passes a complete synthetic capture, separate deadline
failure,37 malformed fixtures and actual V28/V30/V31 rejection.

[verified] Private8MiB candidate
886220b70909556e369eab86aec19c37b4ddcd262ae9c4ca61c999de186eae60
passes independent reference cipher/directory+application CRC/protected cfg
checks. Application ends0x8f47c; NEW requires140 sectors[0x4000,0x90000).
Offline NOR installation/restore and interruptions at pages7/1127/2215/2231
restore exactly, metadata last; hardware commands0. CURRENT V31 independently
restores its existing139 sectors[0x4000,0x8f000), not the new range.
The transaction tool admits only this exact new digest for the additional
sector. Initial transaction run had79 passes and one old test assuming its
previous140-sector image was unique. Updated the explicit image exception;
all80 transaction tests pass. No production protection was relaxed generically.

The cipher container initially lacked crcmod and then pip; no candidate was
produced by those invocations. A bounded Python3.12 container with private
crcmod1.7 completed the independent check. Private artifacts/review scripts
and hash-pinned offline-admission.json are under
scratch/devkit-20261023/build-renderer-queue-detail-v32 and atomic Aeon handoff.
Candidate is OFFLINE ADMITTED, NOT STAGED/INSTALLED/HARDWARE ACCEPTED.
No build, UART RX, KA6 capture or device operation is live. Next is exact
candidate/transaction staging, then the full protected WINDOW/RUN cycle and
fresh40 detail/24 outer-region records for four cases. All old reset receipts
remain consumed. Physical FM1 remains untouched; recovery history is recorded.

## 2026-10-26 V32 target detail: correctness passes, deadline still fails

[verified] Exact admitted V32 `886220b70909556e369eab86aec19c37b4ddcd262ae9c4ca61c999de186eae60` is installed on the dev board, using 140 sectors `[0x4000,0x90000)`. Fresh paired CURRENT V31 backups, factory restore over the CURRENT 139-sector range, WINDOW install/full readback, fresh startup handshake, paired NEW V32 backups, factory restore over the NEW 140-sector range, and SAME-image RUN install/full readback all passed. Startup PING/ARM/ENTER completed 78.7842 ms after the fresh ready marker, followed by an actual WL82 UBOOT1.00 ROM inquiry. WINDOW67584 and RUN20913 are consumed, including all older reset receipts; never retry them.

[verified] Strict V32 parsing passes four arithmetic rows, four PCM hashes/control counts, 24 outer and 40 detail records, 22,052 queue jobs with zero errors/wrong-core reports, and finite worker exit. All four cases have 5,513/5,513 blocks late against the unchanged 34,829-tick deadline. Means are 1,965.042 / 2,025.833 / 2,061.417 / 2,220.750 us. Maximum ticks are 55,978 / 56,846 / 61,947 / 68,406. This instrumented result is not dropout-free acceptance.

[verified] Heap remains 77,588 bytes in all five snapshots. Parent unused stack is 2,276/8,192 bytes; worker unused is 7,452/8,192. Sole RX53879 PID383537 was checked against its exact argv twice, sent one SIGTERM, and reached terminal255 before ordinary PING acknowledged. No capture, build or device operation remains live.

CPU0 detail mean ranges across the four cases (24 MHz timer; these are subsets of outer regions and must not be added to them):

| Category | Mean us |
| --- | ---: |
| setup/advance | 10.750–11.083 |
| record callbacks | 253.542–255.708 |
| inserts/meters | 406.458–410.125 |
| level/mix | 47.167–47.792 |
| masters | 246.333–251.042 |
| amp | 0.458–0.500 |
| click/limiter | 12.625–12.667 |
| scope | 12.833–12.917 |
| UI | 47.000–47.458 |
| conversion/hash | 18.333–18.542 |

[inferred] Inserts/meters and masters together account for about 653–661 us of CPU0 work per block; recording contributes another 254–256 us. Conversion/hash is only about 18 us, so it cannot explain the deficit. The fixed arrangement uses filter and drive inserts, with echo and compressor masters; current measurements do not yet distinguish each effect from its dispatch/meter overhead. Next trace these paths and recording callbacks, then choose an exact-PCM optimization or a bounded per-effect measurement. Do not change the default worker1 partition or weaken audio quality/acceptance.

[verified] Rarefaction still resolves the primary checkout, returning the old fm1_app_render at line3267; it cannot establish this external worktree variant. Serena selected the actual absolute worktree and returned current fm1_app_render at line3630 plus render_fx at3485, matching source. Neither establishes pi32v2 ABI/cache behavior.

Private raw SHA `13ed91ca96bf540a325c388c9964c1900032763c05bf4476eba9d40d072bfeee`; capture `scratch/devkit-20261023/renderer-queue-detail-v32-run-20261026-uart.bin`, strict facts/recovery evidence in `build-renderer-queue-detail-v32/`. No actual FM-1 traffic was sent. Physical FM-1 recovery, actual mixed deadline, fault-validated DAC/KA6 and representative 30-minute analog soaks remain unfinished; PR155 stays draft and unmerged.

## 2026-10-26 Drive settled-control scan optimization (target pending)

[verified] DriveRender now stops rescanning glide controls after a scan finds
every value at its target during the current render call. It preserves the
last glide update and continues Type fade advancement and derived-state
updates independently. Targets cannot change during a render call. This is
the same settled-scan pattern already used by CompRender; sample arithmetic,
filter quality, native rates and time constants are unchanged.

[verified] Bounded Aeon host suite tests/test_engines_drive.py plus
tests/test_devkit_queue_integration.py completed terminal0: 99 tests pass,
including moving controls, Type crossfades, block partitions, all six
queue/profile combinations and queue fault lifetime. A separate pre-change
V32 versus new-source shared-renderer comparison matches all 11,290,624 PCM
bytes exactly: SHA256 c676e9b496a63e3817428ade9c067d75a2fd81bd786da7c0ad06ee6255c4f81b.
Private scripts/logs/results are under scratch/devkit-20261023/ and Aeon TASK
with drive-settled-v33 names. These establish host output preservation, not
a measured target speedup. No new image has been linked/admitted/installed.
Next exact-source vendor build and code/layout/stack/recovery/SDK/cipher/NOR
admission precede any protected hardware timing comparison. V32 stays current;
no board traffic was sent for this source change.

### V33 exact vendor build and offline admission (2026-10-26)

[verified] Exact source 9225abd5e3b8f3ca281dd945f86327b9cd575990 vendor build
95910 terminated0. ELF 7a1e8cecb721444e075af3429144c588843699c0c35a372b2431d2e48dc1f76f;
570268-byte app df3fe5894b45899dfd4c299011661deb6c798182849990567be820f04c648027.
Independent vendor objcopy agrees. Prepared636-file manifest has zero mismatches.
SDK normalized relocation checks, UART18 before parent16, 200-tick delay before
arithmetic/worker/init, queue publication/acquisition, startup copy/BSS, fixed
engine independence and stack-layout checks passed. Heap before tasks119468
(64 bytes below V32); worker allocation and partition unchanged. Drive generated
code skips the eight-control scan after settling, preserves the final glide
update, and reaches independent Type-fade processing on the bypass path.

[verified] Candidate 8f51bda5772b7bcd7e89f4b776b5bff0c9629d709bedd2aa3c2981c5c81dc77e
is offline admitted:140 sectors [0x4000,0x90000), independent cipher/CRC and
protected configuration passed. NOR model restored interruption pages
7/1127/2215/2231 and independently restored CURRENT V32's140 sectors. No device
commands were used. Existing strict parser protocol/37-fault fixtures remain
applicable; no protocol change. Transaction allowlist now admits only this
exact additional digest; all80 transaction tests pass. Private evidence is
in scratch/devkit-20261023/build-renderer-drive-settled-v33 and the atomic Aeon
exports. V33 is NOT staged or installed; target timing/stack and audio acceptance
remain pending. V32 remains healthy idle. No actual FM1 traffic was sent.

### V33 protected cycle and target measurement (2026-10-26)

[verified] Full protected cycle passed: acknowledged UART entry, fresh mask-ROM
response, two CURRENT V32 full backups,140-sector factory restore, V33 WINDOW
install/full readback, armed sole verifier before single reset81461, startup
PING/ARM/ENTER78.6838ms after fresh ready marker and responsive actual ROM, two
NEW full V33 backups,140-sector factory restore, SAME V33 RUN install/full
readback, armed sole RX before single reset38087. Both reset receipts and every
older receipt are CONSUMED and must never be retried. Owned RX5211 PID391896 was
exact-argv checked twice, SIGTERM once, terminal255 before ordinary PING ACK.
V33 is now CURRENT and healthy idle. No capture/build/device operation remains.

[verified] Strict parser passes four arithmetic and four mixed PCM/control cases,
24 outer/40 detail records,22052 queue jobs with zero errors and finite worker
exit. Means1950.667/2012.667/2047.125/2206.958us improve0.62..0.73percent vs V32.
Inserts/meters392.375..393.208us (V32 406.458..410.125us); individual effect cost
is still not isolated from dispatch/meters. Recording254.208..255.917us, masters
246.458..252.375us. ALL5513 blocks in EACH case still late: deadline FAIL34829
ticks. Maxima55828/56321/61139/67449ticks. Heap77524stable; parentunused2276/8192,
workerunused7452/8192. Instrumented timing is not analog acceptance.

[verified] Raw capture SHA524cc56245d6dc6846fcce8919600ef7b61e9f709ca6a44b785c078569070d9a
and target-facts/startup evidence saved locally and hash-verified on Aeon.
Next isolate per-effect/control-recording overhead before choosing another
exact-PCM optimization; retain default worker1. Actual mixed deadline,
fault-validated underrun/DAC/KA6 and representative30-minute analog soaks remain
unfulfilled. Actual FM1 was not contacted.

## 2026-10-26 — V34 opt-in recording/effect micro timers, host checkpoint

[verified] Added guarded `--engine-queue-micro`, requiring existing queue detail/profile and all existing timing-only queue guards. Only the private prepared app receives hooks. Twenty independent CPU0 regions time six recording command kinds, then effect-host DSP calls by fourteen app-unit indices; sparse zero-count slots are intentional. Existing detail/outer banks remain intact and overlap these subsets, never add banks. No PCM arithmetic, rates, quality, polyphony, events or worker partition changed. Counts accompany mean/max/worst timing; malformed/nested/unclosed intervals, half-range/accumulator overflow, missing reads and case count overflow refuse results.

[verified] Bounded Aeon host container session44708 TERMINAL0: 34 focused ownership/bridge/lifecycle/detail/micro/integration/guard checks passed, including normal+ASANUBSAN synthetic interval faults and both partitions across profile off/on/detail/micro. Each full shared-app replay compared 11,290,624 PCM bytes across 44,104 batches exactly and checked permanent refusal/retained late-worker buffers. Host log `scratch/devkit-20261023/queue-micro-v34-host.log` (Aeon task same basename). Three local lightweight timing aggregation checks subsequently passed, including micro missing/impossible/count-overflow failures. Earlier local combined invocation48742 was interrupted deliberately when its full replay was moved to bounded Aeon; it is not a complete-suite pass. No TSAN or target race/cache/ABI/stack proof claimed.

No V34 vendor link/image/admission/staging/install yet. NEXT exact-source vendor build, complete independent admission reviews and strict new MICRO UART parser/fault fixtures before hardware. V33 remains CURRENT8f51bda5 healthy idle, restore140[0x4000,0x90000), deadline FAIL all5513late per case. WINDOW81461/RUN38087 and all older resets consumed, never retry. No RX/KA6/device operation live or owner input pending. PR155 draft open unmerged; actual mixed deadline/stack and analog acceptance unfinished. Actual FM1 remains nonbooting, research-only/no traffic.

[verified] V34 exact-source60bf vendor82111 TERMINAL0 and export16005 TERMINAL0. ELF `6ca8f89d5d2df9b7329d88e4c5dc416ef1499fe52abf5cb59a5e8294e550a475`; app571580bytes `67fab82d20b2e3374f6df03afb449d62aac6cfc1ec244ad1cb7d8068cbf89b05`. Preliminary section concatenation and independently exported vendor-objcopy app match; SDK protected routines match prior reviewed baseline after checked relocations; static queue10368bytes/worker8356bytes, pretaskheap119244. All636 prepared manifest files match, zero mismatches; worker partition remains sound1. Source review/host checks are not target race/cache/stack proof. Exact timing function now reserves1108 local bytes plus saved registers: remaining target stack must be measured, not inferred from V33.

[verified] Private strict V34 parser accepts complete synthetic MICRO and separately marks late deadlines; rejects19new transport/data faults plus37base faults and actualV33 lacking MICRO. Checks80ordered records, calls, sparse inactive slots, and recording/insert/master subgroup containment. Each effect segment advances at least one frame, so per-unit effect calls bounded64*5513 per case; recording count bound comes from fixed queue peaks. Parser scripts/reports in `scratch/devkit-20261023/{parse-renderer-queue-micro-v34.py,test-parser-queue-micro-v34.py,build-renderer-queue-micro-v34/}` and Aeon exports. These are synthetic parser checks, not hardware evidence.

V34 remains NOT admitted: full final-ELF timer/caller/publication/UART-first/stack-layout/engine independence/audit_link, independent cipher/CRC/protected cfg and NOR interruption reviews remain. No8MiBcandidate generated/staged/installed, no device operation/RX/KA6 live. V33 remains installed. Exact60bf CI40296065331 in progress, Pages40296065258 success terminal at check. Prior9df CI40294022295 last in progress, Pages40294022201 success terminal. Do not repeat passing checks without a new reason.

[verified] V34 final offline admission completed. Candidate `c70fddedc7f029bb04dccbc56d80d992b6557ab6b435ecc90260e2bd2ce52974` changes exactly140sectors [0x4000,0x90000), app end0x8f9dc. Exact final-ELF review confirms UART18 before parent16, 200tick recovery before arithmetic/static CPU1 worker/renderer initialization, static ranges/startup copying, fixed Macro0 source independence, release/ACK and acquire ordering, CPU0-only direct24MHz micro timers around recording and segmented/tail DSP calls. Counter/halfwrap/sum/one-consume/count-overflow checks remain fail-closed. SDK audit0fail/1manual item resolved by normalized protected-routine comparison. Timing frame1160bytes; target headroom remains unmeasured.

[verified] Independent reference cipher decode, directory/application CRCs and protected configuration match. Offline NOR model installs/restores exact candidate, keeps metadata last, restores interruptions at pages7/1127/2215/2231 and independently restores CURRENT V33 all140sectors; hardware commands0. Transaction allowlist adds only exact V34 digest/range;81transaction tests pass, preserving older bounds. Private `build-renderer-queue-micro-v34/offline-admission.json` pins artifact hashes; scripts/reports copied to atomic-handoff Aeon task exports. Candidate OFFLINE ADMITTED, NOT staged/installed/hardware accepted. NEXT protected WINDOW/RUN cycle with fresh UART/ROM/double backups and unique consumed reset receipts, then strict4case24outer40DETAIL80MICRO results and runtime stack assessment. V33 remains healthy idle; no device operation live. PR155 remains draft/unmerged and dropout-free/analog acceptance unfinished.

[verified] V34 protected WINDOW/RUN cycle completed on dev kit. Fresh ROM identity, two full CURRENT V33 backups, factory restore, V34 install/full readback, sole startup verifier armed before WINDOW43747 (consumed), fresh3ACK78.5945ms plus actual ROM, two full NEW V34 backups, factory restore and SAME V34 RUN install/readback all passed. SoleRX97007PID404914 armed before RUN26079 (consumed); finite worker exit observed, exact argv verified twice, one SIGTERM, terminal255 before ordinary PING ACK. All prior reset receipts remain consumed; never retry. CURRENT V34c70fdded restore140[0x4000,0x90000), healthy idle. No device/RX/KA6/build operation live.

[verified] Strict target parser passes arithmetic4/mixedPCM-control4/24outer40DETAIL80MICRO and22052queue jobs zero errors, counts/peaks correct, finite worker exit. Means1920.750/1983.750/2017.708/2177.083us, late5510/5513/5513/5513 of5513: deadline FAIL34829ticks. Instrumented runs do not establish performance improvement or analog acceptance. Heap77300stable, parent unused1692/8192bytes, worker unused7452/8192bytes. Raw capture SHA3cd4f023896806a3b63971c966efc2f714d900b166d12dee22c2f55b46094148 and startup/facts saved privately localbuild-renderer-queue-micro-v34 and Aeon exports.

[verified] New DSP mean measurements: Drive208.542..209.833us, Filter159.208..162.042us, Echo154.208..155.042us, Comp77.625..79.083us. Recording render/param callbacks total~8.5..8.7us inside DETAIL recording236.208..242.167us; note-on/off means round to0 with56calls each. Therefore callback recording alone does not explain the surrounding cost; remaining sequencer/control work needs tracing before another optimization. DETAIL insert385.208..387.375us and master246.417..248.667us largely contain these DSP calls. Banks overlap, never add MICRO+DETAIL+outer or worker to CPU0. NEXT trace dispatch/sequence advancement/control work outside recording callbacks, then select an exact-PCM change; preserve rates, quality, events and deadline. PR155 remains draft/unmerged; actual mixed deadline and analog/30minute soak acceptance unfinished. Actual FM1 remains nonbooting, research-only/no traffic.

### V35 offline control-hook diagnostic, 2026-10-26

[verified] V34's DETAIL1 starts after sequence flush/advance and queue-begin;
those operations belong to DETAIL0. Its roughly 236–242 µs therefore cannot be
attributed to sequence advancement. The six command-recording kinds account
for only about 8.5–8.7 µs, leaving the dispatcher, MFX block preparation and
control hooks to distinguish. Source tracing found modulation begin/tick,
event and per-note hooks in that interval; this is a lead, not target-cost
attribution.

[verified] The opt-in micro diagnostic now adds regions 20–25 for begin,
event, lock, tick, lock-slot and note-on. Exact-signature wrappers preserve
arguments, return values and output pointers; each interval closes even when
the original hook returns early. The independent bank has 26 non-nested
regions, still subsets of outer/detail time. Default builds and worker1
partition are unchanged. This format requires a new strict 26-region parser;
V34's historical 20-region capture/parser remain unchanged.

[verified] Bounded Aeon host run 24550 finished exit 0: all 36 focused queue,
bridge, timer, preparation and integration cases pass, including eight full
11,290,624-byte / 44,104-batch PCM comparisons, both worker partitions,
normal/ASan+UBSan ownership, malformed intervals, one-consume and timeout
lifetime refusal. Local non-PCM subset also passed (28 cases). No TSAN or
target race/cache/ABI proof is claimed. Rarefaction's root remains the primary
checkout and cannot select this external worktree; its fallback results were
checked against Serena's actual-worktree symbol bodies and source inspection.

No V35 image is admitted, staged or installed at this checkpoint. V34 remains
CURRENT and idle; its deadline failure and all consumed reset receipts stand.
Next: exact-source vendor link, strict new parser/fault fixtures and complete
machine-code/layout/UART-first/SDK/cipher/NOR admission before any hardware use.

V35 vendor attempt 86623 failed before link because the SDK worker's include
paths do not contain `fm1_engine.h`: importing the bridge from the result
header exposed that renderer-only dependency. The result header now keeps a
small independent region count, checked against the bridge enum in the
producer translation unit; the emitter uses the result-header count. All
three local timing aggregation configurations pass after this correction.
The prior eight full PCM replays remain valid for the unchanged wrapper/DSP
code; this header correction still requires a fresh exact-source vendor build.
V35 strict offline parser fixtures reject 26 new malformed control/micro cases,
all 37 inherited faults, and the actual V34 capture missing six control regions.
These synthetic fixtures are not hardware evidence.

V35 exact-source vendor r2 (74633) linked successfully from firmware commit
`0ad522b5f29fccbd4a9bc2088bca62fa6a9bd3c4`. [verified] Final ELF
`00d12effd636705919718e31515292cf09abe12b2c2b698378938c677d0a18e2`,
571,644-byte application `fb8797290ce388f0f28cbe0eac24051756ab9a1251f22c175163d2c6f66fde53`.
636 prepared manifest hashes match. Independent vendor objcopy matches the
section-concatenated application. Final instruction review confirms paired
six-hook timers with preserved results/output pointers, direct CPU0 timer,
non-nesting/half-wrap/overflow/one-consume checks, unchanged worker1 publication
and ACK/acquire ordering. UART18 starts before parent16, 200 recovery ticks
precede arithmetic and CPU1 static worker allocation; startup copies/BSS/cache,
fixed-engine independence and normalized SDK/ROM routines pass review.
`audit_link` has zero failures; its one manual item is resolved by the exact
normalized protected-routine comparison. Pretask heap is 118,732 bytes. The
parent timing frame is now 1,320 bytes including saved registers (+160), so
fresh target stack high-water measurements remain required.

[verified] Candidate `86f02a974ad0a41c13ce09396a4657289dd7f8943aeb416870cd063e595f3d83`
is admitted OFFLINE for 140 sectors `[0x4000,0x90000)`. Independent reference
cipher/CRC/protected-config checks, exact NOR install/restore, metadata-last
interruptions at pages 7/1127/2215/2231, and CURRENT V34 restore all pass with
zero hardware commands. All 82 transaction tests pass for the added exact hash
and preserved older bounds. Private scripts/reports are under
`scratch/devkit-20261023/build-renderer-queue-control-v35/` and Aeon
`renderer-queue-control-v35-r2-exports/`. No V35 staging or installation has
occurred. CURRENT V34 and every consumed reset receipt remain unchanged.

### V35 control-hook attribution on target — 2026-10-26

[verified] Exact firmware base `0ad522b5f29fccbd4a9bc2088bca62fa6a9bd3c4`,
8 MiB candidate `86f02a974ad0a41c13ce09396a4657289dd7f8943aeb416870cd063e595f3d83`
completed the protected WINDOW/RUN cycle and is now CURRENT, restore/install
140 sectors `[0x4000,0x90000)`. Both full CURRENT V34 backups matched
`c70fdded...`; CURRENT-range factory restore, WINDOW install/full readback,
fresh startup PING/ARM/ENTER in **78.6943 ms**, actual ROM inquiry
`WL82/UBOOT1.00`, two full NEW backups, NEW-range factory restore and SAME
RUN install/full readback all passed. USB45 path3-1.2/sg0. WINDOW71927 and
RUN10303, plus all older reset receipts, are CONSUMED: never retry.
Sole RX2346 PID415677 was armed before RUN invocation, twice exact-argv
verified after finite completion, SIGTERM once, terminal255 before ordinary
PING ACK. No capture, build or device operation remains live.

[verified] Strict parser passed four arithmetic and four mixed PCM/control
cases, 24 outer +40 DETAIL +104 MICRO records, 22,052 queue jobs with zero
ownership/worker errors and finite worker exit. Means were
**1959.292/2019.042/2054.708/2213.042 us**, and **all 5513 blocks in every case
missed the 34829-tick deadline**. Heap 76,788 bytes remained stable; parent
unused stack 1,532/8,192 bytes, worker unused 7,452/8,192 bytes. These are
instrumented observations, not analog acceptance or proof of an optimization.

[verified] MICRO23 (the entire `seq_auto_tick` hook) measured
**213.792/212.333/213.208/214.542 us per block**, with 11025/11026 calls per
case. It explains most of DETAIL1's 254.750/253.042/254.292/255.542 us.
Begin/event together cost approximately 5.1 us per block; lock/lock-slot
had zero calls; note-on hook mean rounded to zero with 56 nonzero-cost
calls. Existing render/parameter callbacks totalled about 9.3–9.5 us.
MICRO and DETAIL are subsets of outer regions: never add their banks;
worker outer5 overlaps CPU0 and must never be added to its total.

[verified source] `seq_auto_tick` delegates to `mod_glue`'s `glue_tick`, which
calls `fm1_mod_tick`, converts global writes and voice writes, and invokes
optional callbacks. App initialization assigns `write=mod_write` and leaves
`ticked` unset. The core tick performs `take_system`, module evaluation,
`write_sinks`, and `run_voices`; this measurement does not separate those
internal costs. Next inspect that path and the exact configured graph, then
choose a PCM-identical optimization or bounded internal measurement. Preserve
native modulation tick rate, gate/event order, first blocks and polyphony.
Do not attribute this result to queue pushes or sequencer advance (outside
DETAIL1), or promote the V30 worker+drums regression.

Evidence stays private: `scratch/devkit-20261023/build-renderer-queue-control-v35/`
contains startup events/raw UART, strict `target-facts.json` and parser log;
run raw `renderer-queue-control-v35-run-20261026-uart.bin` SHA256
`388106921fe4b76fe0eaf933a6ad2a38f389f8ab3ca0922708a98f406ac040ca`.
Original offline-admission evidence remains historical; these fresh target
facts establish installation and runtime observations. No target race/cache
proof is claimed; TSAN unavailable. Physical FM1 remains nonbooting and
untouched. Deadline/stack acceptance, fault-validated underrun/DAC/KA6 and
representative 30-minute analog soaks remain incomplete; PR155 stays draft,
open and unmerged. Exact-head CI40302866231 last in progress;
Pages40302866082 SUCCESS terminal.

### V36 offline envelope advancement fast path (2026-10-26)

[verified] V35's whole modulation tick costs 212.333–214.542 us/block;
this does not attribute that cost to an individual primitive. Source inspection
found two unconditional 64-bit boundary divisions in envelope advancement:
`mp_env.c:advance` and the module wrapper `mod_env.c:env_run`. Both now first
compare the exact uint64 increment-times-frame-count product with remaining
phase distance. Only a crossing computes the original ceiling division.
Equality still crosses, segment overshoot is still discarded, and no envelope
rate, curve, event ordering or floating-point policy changes.

[verified] A new state differential test compares the original algorithm over
20,000 generated states, including loop/sustain/done states, boundary minus/at/
plus one, full uint32 frame counts and extreme increments/phases. Local test
PASS; bounded Aeon host suite TERMINAL0, 187 PASS, covering primitives/runtime/
kinds/voices and eight complete queue PCM/fault configurations. A separate
fresh HEAD35ecfdb0 versus working-source mixed replay is byte-identical for
11,290,624 PCM bytes / 44,104 blocks, SHA256
`c676e9b496a63e3817428ade9c067d75a2fd81bd786da7c0ad06ee6255c4f81b`.
Private evidence: `scratch/devkit-20261023/env-fast-v36-host.log` and
`env-fast-v36-old-new.json`, mirrored under the Aeon task root. Rarefaction's
primary-checkout fallback does not cover the external worktree reliably;
Serena's absolute worktree symbols and direct source inspection were used.

[inferred] Avoiding division on non-crossing blocks may reduce target cost.
No target speedup is established. V35 remains installed/current and healthy
idle; all reset receipts remain consumed. No V36 vendor image, admission,
staging or installation at this source checkpoint. Next: exact-source vendor
build and machine-code review, then all image admission gates before hardware.
Actual mixed deadline, stack, fault-validation and analog soak acceptance are
still incomplete. No actual FM1/Hera traffic or device operation was issued.

[verified] V36 exact-source vendor build passed at b5a9fc35. ELF
`8295eb3f41c1a85b151e2b9e945d02284b69d5477176b4a4d344d00b07f3779a`,
571,676-byte app `ceaa33d7b14a91537db9544b58e6ec3739a96f70f70245af37c90a962677d1f3`.
Both target non-crossing paths branch around native pi32 unsigned wide division;
this is not a software divide-helper removal. Primitive local stack falls 8→4
bytes; env_run remains16, env_process76, timing frame1320 incl saved registers.
Heap before tasks remains118732. Full636-file manifest, UART18-before-parent16,
200-tick recovery-before-workload, startup copies/BSS, queue acquire/release,
26-region timer/aggregation, fixed-worker1 source/global independence and SDK
normalized ROM-entry/keycheck checks pass. audit_link has0fail/1manual item,
resolved by the exact normalized vendor routine comparison, not ignored.
Independent vendor objcopy matches app bytes. Reference cipher/CRC/protected cfg
checks pass; private candidate
`3d00c962b8df3eca3a9ff1122b796cc7328980186498aec97f78a38ee74a8a62`
changes140 sectors [0x4000,0x90000), app end0x8fa3c. Offline NOR model restores
interruptions at pages7/1127/2215/2231 and independently restores CURRENT V35
all140 sectors. No hardware commands. Exact-image admission added;83 transaction
tests pass after explicitly classifying the new140-sector image in the range
fixtures. Reports/hashes in private `build-renderer-env-fast-v36/offline-admission.json`.
V36 OFFLINE_ADMITTED, not staged/installed; target speedup unknown. V35 remains
CURRENT; deadline and analog acceptance remain incomplete.

### V36 protected target cycle: correctness PASS, deadline FAIL (2026-10-26)

[verified] V36 is CURRENT on the devkit, image
`3d00c962b8df3eca3a9ff1122b796cc7328980186498aec97f78a38ee74a8a62`,
restore140[0x4000,0x90000). Ordinary UART entry acknowledged; fresh actual
WL82/UBOOT1.00 inquiry; double full CURRENT V35 backups2601; factory restore84831;
WINDOW install14302/full readback; sole verifier90764PID422245 armed before
ONE WINDOW reset47770. Fresh startup PING/ARM/ENTER completed in78.7961ms and
actual ROM inquiry responded. Double full NEW backups66270 matched V36;
factory restore61822; SAME image RUN install59653/readback; sole receive-only
capture76924PID423663 armed before ONE RUN reset47923. BOTH resets and ALL
older receipts are consumed, NEVER RETRY. SG_IO host7/resid16 is recorded as
interrupted response, not boot proof. After finite completion, capture argv
was checked twice, one SIGTERM sent, terminal255 confirmed before ordinary
PING ACK. Owned process absence verified. No live build/RX/KA6/device operation.

[verified] Strict unchanged V35 parser accepts4 arithmetic/4 mixed PCM+control,
24 outer/40 DETAIL/104 MICRO records,22052 queue jobs with zero errors and finite
worker exit. Case means1958.917/2018.375/2050.917/2206.250us; ALL5513 blocks late
in EVERY case, FAIL34829ticks. Maximum55569/56906/61526/67247ticks. Heap76788 stable;
parent unused1532/8192bytes each case, worker unused7452/8192bytes. Observed mean
reductions versus V35 are0.019/0.033/0.185/0.307percent; one before/after capture
is not proof of a causal speedup. Whole modulation tick means213.458/211.917/
212.667/213.958us, only0.333–0.583us lower than V35. This does not identify the
main ~213us cost. No deadline or analog acceptance, no real-FM1 recovery claim.

Private raw `renderer-env-fast-v36-run-20261026-uart.bin` SHA256
`40c62d0f48623efb0a8cdf8e135bab0258c15d69cd01bf6ff3276b3bf22bded5`;
parsed facts SHA256`86800e69e04eb3b15fcc4fcaa2b1b8ce2ed8c97ca671fb4e156e3d9990c68125`.
Raw/meta/startup/facts/parser/cycle review saved locally under the campaign
scratch and build-renderer-env-fast-v36, mirrored and rehashed on Aeon under
renderer-env-fast-v36-exports. Historical offline-admission hardware=false is
unchanged; target facts/cycle review establish installation, not acceptance.

Next: bounded internal modulation attribution around take_system, module
execution, write_sinks, run_voices and glue write conversion before another
optimization. Preserve event/gate order, rates and exact PCM; account for
observer overhead and the1532-byte parent stack margin. Do not add overlapping
worker time or nested MICRO/DETAIL/outer totals. Retain worker1; the V30 drums
partition remains a measured regression. Deadline/fault-validated DAC/KA6 and
representative30-minute analog soaks remain unfinished. Physical FM1 remains
nonbooting and untouched; no Hera contact or button use.

### V37 preparation: internal modulation attribution (offline, 2026-10-26)

[verified] Added opt-in `--engine-queue-mod-micro`, requiring the existing
micro/detail/queue guard chain. It replaces six whole-hook intervals with six
sequential modulation subsets: system intake, global modules (including params,
gates and output sanitation), sinks, voices, global glue conversion, and voice
glue/callback conversion. The original timer bank remains 26 entries; no result
arrays grow. The outer tick wrapper is omitted so the flat bank never nests.
Default app/engine sources remain unchanged; only private preparation copies
are transformed. Input hashes and alternative region names enter the receipt.

[verified] Seventeen focused transformation/guard checks pass locally. A first
check exposed a missing repeated-transformation refusal; added an explicit
instrumentation marker guard and the check now passes. Full shared-app PCM,
call-balance and timeout-lifetime tests for both partitions completed bounded
on Aeon (session95200 TERMINAL0): all27PASS, each full11290624PCMbytes/44104blocks
exact. No hardware test was run. Exact 0f7b CI40309256826 is in progress;
Pages40309256960 succeeded. No new image has been linked/admitted/staged/installed.
V36 and all consumed reset receipts remain unchanged. Rarefaction is confined
to the primary checkout and returned ENOENT for this worktree's preparer;
Serena session7b7f9712 selected the correct absolute worktree and located it.

[inferred] The six intervals should attribute the roughly213us whole-tick
cost, but omit plan rebuild/tick bookkeeping and include observer overhead.
Host proof cannot establish target stack/cache/race/timing. The narrow parent
stack margin still requires exact vendor frame review before any admission.

[verified] V37 firmware/preparer checkpoint ef4380b10d26a46307c76b66d3f99ebc459facad
pushed with explicit refspec and remote SHA verified. Fresh exact-source vendor
build12291 TERMINAL0; export92462 TERMINAL0. Preliminary final-ELF review finds
8 micro-mark calls in fm1_mod_tick and4 in glue_tick, no remaining whole-hook
wrapper symbols, and no micro calls on CPU1. The core frame remains236 local
bytes plus52 saved (288 total), timing1268+52 (1320 total); glue28+52 (80 total).
This is preliminary frame/symbol evidence, NOT a full call-path stack proof.
Receipt confirms26 regions and six alternative labels. No8MiB candidate,
admission, staging or installation has occurred. Private ELF/disassembly/input
and preliminary-modulation-review.json saved under build-renderer-mod-micro-v37.

[verified] Strict private V37 UART parser requires all six stage counts to match
exact finite-case modulation ticks11025/11026/11026/11026. Its synthetic fixture
and19 malformed/old-mode refusals pass; synthetic zero-time records establish
parser scheduling structure only, not measured performance. Next complete exact
timer branch/control review, full manifest/layout/UART-first/SDK/source-independence,
independent app-copy/cipherCRC/NOR admission and parser fault coverage before
any protected hardware cycle. V36 remains healthy-idle CURRENT and deadline FAIL.

### V37 final offline review (2026-10-26)

[verified] Exact ELF dce46e067ca19a478b842085fcefbcde304d0332fe08555898e73a1c1faa2975:
compiled core/glue branch traversal covers920/176 instruction states, one return
each, with8/4 ordered stage-marker calls and no active marker at a return.
Early paths skip the core intervals; source review confirms opaque module/write
callbacks do not enter the flat bank. The mixed app installs no ticked/voiced
callbacks. Marker code retains direct CPU0 clock67588, overflow/half-wrap
refusal and one-consume semantics. CPU1 has no micro markers. Core frame288,
glue80, seq_auto_tick12, aggregate1320; observer16. Individual frames remain
insufficient for whole-stack/IRQ acceptance. Removing hook wrappers reduced
resident code320bytes, BSS unchanged, pre-task heap119052. Layout review's old
heap pin failed, then the new value was checked against actual section/symbol
arithmetic before updating that private assertion.

[verified] All636 manifest hashes match. UART18 starts before parent16;
200tick recovery precedes arithmetic, static8KiB CPU1 worker and renderer init.
Startup copy/BSS/cache ranges and publication/acquire/release instructions pass.
SDK audit has0fail/1manual; manual scheduling is resolved by complete normalized
comparison of the protected SDK/ROM-entry routines with the approved baseline.
Fixed Macro0 source/target independence reviewed; this is not runtime race proof.
Independent vendor objcopy matches571612-byte app SHA256
3ee2fe15ca6385b56d22959ab6ceb06771264ff022519f3d695698b908b30d6e.

[verified] Private candidate SHA256
5704ca9e632fde350cd10b4a5f2a0a7f54f92857e839a28c778fa55d8cc7e05e,
app end0x8f9fc, exactly140 sectors[0x4000,0x90000). Independent reference
cipher, directory/application CRCs and protected cfg checks pass. Offline NOR
install/restore metadata-last and interruptions7/1127/2215/2231 pass; CURRENT
V36 restore independently covers140sectors. Hardware commands0. Strict parser
now exercises91new malformed/old-mode refusals plus37base faults and separate
synthetic timely/late captures; fixtures are not timing evidence.

[verified] Additional ASAN+UBSAN replay initially failed only when linking the
separate fault executable: replay flags were omitted from that link. The test
now forwards tokenized FM1_SIM_EXTRA there too. Corrected session74465
TERMINAL0: both ASAN+UBSAN full-PCM/call-balance/fault-lifetime casesPASS.
Firmware/prepared C is unchanged by this test-only repair. All84 transaction
checksPASS. Candidate5704ca9e is now OFFLINE ADMITTED, pinned to140 application
sectors; NOT staged/installed/hardware accepted. Local/Aeon reports and
offline-admission.json hash the exact reviewed artifacts. V36 remains CURRENT.

### V37 target modulation-stage attribution (2026-10-26)

[verified] Candidate5704ca9e632fde350cd10b4a5f2a0a7f54f92857e839a28c778fa55d8cc7e05e
completed the protected dev-board WINDOW/RUN cycle. Fresh UART entry and actual
WL82/UBOOT1.00 inquiry preceded two matching full8MiB CURRENT V36 backups.
CURRENT140-sector factoryrestore29130 and V37WINDOWinstall76832 passed complete
flash readback. Sole startup verifier20654/PID431516 was armed before unique
WINDOWreset6022 (consumed at invocation, NEVER retry). Fresh ready-to-three-ACK
latency78.700304ms; actual ROM responded afterwards. Two NEW full8MiB backups
70356 matched V37; NEW140-sector factoryrestore10323 and SAME-image RUNinstall
94033 passed full readback. Sole receive-only capture41538/PID432870 was armed
before unique RUNreset16109 (consumed at invocation, NEVER retry). Both reset
USB host7/resid16 results alone were not boot evidence. All older receipts
remain consumed. After finite workload completion, exact capture argv was
verified twice, one SIGTERM sent, capture terminal255 observed BEFORE ordinary
PING ACK. No RX/build/KA6/device operation remains live; no physical FM1 traffic.

[verified] Strict V37 parser passed4arithmetic/4mixedPCM+control/24outer/40DETAIL/
104MICRO records and22052queuejobs with zero errors and finite worker exit.
Parent unused1532/8192bytes, worker7452/8192bytes; heap77108bytes stable. Mean
block times1953.583/2014.667/2049.792/2208.958us; max55841/57444/61342/68160ticks.
ALL5513blocks late in EVERY case: deadline FAIL34829ticks. Instrumented timing
is not final audio acceptance. No DAC/KA6 capture or30minute analog soak occurred.

[verified] Per-block stage means (24ticks/us): system intake36.375..36.708us;
global module loop145.708..146.875us; sinks17.292..17.417us; voices2.542us;
global glue2.958..3.125us; voice glue2.792..2.833us. All six intervals have
exact11025/11026/11026/11026calls. They are subsets of recording/outer regions,
not additive to them; CPU1 outer5 overlaps CPU0 and must never be added. Markers
include observer overhead and omit tick bookkeeping/plan rebuild. Attribution
identifies the global-module loop, including parameter/gate/output work, as the
largest measured modulation stage; individual module process cost remains
unseparated. Its removal alone could not close the overall mixed-renderer gap.
Next inspect module_params/module_gates/process/module_outputs and exact active
module schedule before a bounded optimization or more granular instrumentation.
Do not infer that envelope arithmetic or voice modulation is the dominant cost.

[verified] Raw UART SHA2568e7ca2c8c6c3de59dd44aae4d11dfb6169a169f769d1d5102eb5bc34d7a8ac5e;
target-facts SHA25624eae4d654b43e3d35ce896879e570d1813a7e5bcb45239e4a7efd09ce18db81.
Private raw/facts/startup/events/transaction receipts saved locally under
scratch/devkit-20261023/build-renderer-mod-micro-v37 and replicated to Aeon
renderer-mod-micro-v37-exports. Historical offline-admission report remains an
offline receipt; target facts establish deployment and correctness, not acceptance.
Rarefaction remains rooted at the primary checkout with fallback flags and could
not resolve this worktree's run_module position; Serena sessionf56a245f selects
the actual absolute worktree and resolved run_module/module_params/module_outputs.
Empty Rarefaction results are not evidence of absent callers or target ABI proof.

### V38 global-module component diagnostic preparation (2026-10-26)

[verified] Added opt-in --engine-queue-module-micro, requiring the existing
modulation-micro dependency chain. The prepared-only core replaces slots20–25
with system intake, module parameters, gates, output/IO initialization, process
callback, and output sanitation. It omits the enclosing module-loop and glue
intervals to avoid flat-bank nesting. The early missing-kind return precedes
all module markers. No algorithm, native rate, event order, state or default
build changes. Same26 result arrays; receipt carries explicit alternative labels.

[verified] Bounded Aeon host session74111 TERMINAL0: all32 focused casesPASS.
Both worker partitions and all12 profile configurations replay44104blocks /
11290624PCMbytes identically, with marker balance and fault-lifetime checks.
The fixed rack's five global modules produce exactly five component calls per
system tick. Sanitizer31328 TERMINAL0: both new-mode partition casesPASS under
ASAN+UBSAN, fullPCM/call-balance and timeout refusal included. Local .venv lacks
pytest; established Aeon container supplied it, no local dependency alteration.
Private strict V38 parser requires system11025/11026/11026/11026 and each
component exactly5x those counts. Its separate synthetic timely/late fixtures,
91new+37base malformed refusals and actual V37 old-format rejectionPASS. This
is structural parser evidence, not target performance.

[verified] Saved preparer/tests/README and private parser/fault scripts; next
fresh exact-source vendor build and full timer/publication/frame/layout/UARTfirst/
SDK/source-independence/appcopy/cipherCRC/NOR reviews before any new admission.
No new8MiB image, staging or installation. V37 remains CURRENT healthy idle;
ALL prior reset receipts including WINDOW6022/RUN16109 consumed, NEVER retry.
Actual mixed deadlines and analog acceptance remain unsatisfied. No physical
FM1 or Hera traffic, device operation or KA6 capture occurred in this step.

[verified] V38 source23067251431ff99a104b081216707289247b9a85 committed,
pushed explicit refspec and remote SHA verified. Fresh exact-source vendor66976
TERMINAL0; export39425 TERMINAL0. ELF SHA256
be75951b4f98150d8d0c9750f4c5acfb68a98f44524108579bbc9fa97594060c;
concatenated571644-byte app19c3454acf7374342dacb8b90538f85ae32447d0770b4eb371f1c8465ffcd74a.
Section concatenation, normalized protected SDK/ROM-entry comparison and static
queue/worker/noFM6/no-global-constructor checksPASS. Pre-task heap118988bytes.

[verified] Preliminary final-ELF component branch review traverses1523
instruction/history states. The compiler lays the end of a module iteration
before its beginning in address order; the old lexical sequence assertion
therefore failed. The replacement checks every branch path for balanced flat
intervals and legal transitions20→21→22→23→24→25→21 (next module), with empty
plan/absent-kind returns allowed after20. Three return HISTORY states are
accepted, each with no active marker; this is not three distinct return sites.
All12 marker call sites reachable; glue and worker have zero micro calls.
Core frame236+52=288bytes, glue24+52=76, timing1268+52=1320, marker16. These are
individual frames, not whole-stack/IRQ proof. Opaque callback source review,
full manifest/layout/UART-first/SDK audit_link/independent objcopy/cipherCRC/NOR
admission remain pending. No8MiB candidate generated/admitted/staged/installed.
Private reports/artifacts copied into local build-renderer-module-micro-v38
and Aeon renderer-module-micro-v38-exports. V37 remains CURRENT; no device ops.

[verified] V38 completed offline admission: 636 input hashes match, exact
UART-before-parent/200-tick recovery/static worker/startup-copy/publication
review PASS, fixed Macro0 source/target independence review covers35 functions
and36 files. Component helper review preserves params→gates→IO→process→outputs,
including finite/clamp and gate-edge order. Clock/active-bank/overflow guards
PASS; no CPU1 observer calls. SDK audit_link has0fail/1manual; the complete
normalized approved SDK/ROM-entry comparison resolves that manual item.
Independent vendor objcopy exactly matches571644-byte app19c3454a….

[verified] Private candidate SHA256
2483bb7c1fcba0d3a3099f826981dd15bac6ca23804bfebe6a99de43ff5f8bd6,
application end0x8fa1c, changed140 sectors[0x4000,0x90000). Independent reference
cipher/CRC/config checksPASS. Offline metadata-last install/restore and four
injected interruptions at pages7/1127/2215/2231 restore byte-identically;
CURRENT V37 also restores all140 sectors. These models sent0hardwarecommands.
Reports and hash-pinned offline-admission.json are private under
scratch/devkit-20261023/build-renderer-module-micro-v38 and Aeon exports.
No target race/cache/whole-stack proof or timing acceptance is claimed.
V38 not staged or installed at this checkpoint; V37 remains healthy idle.

[verified] Added only V38's exact hash and fixed sector plan to the dev-kit
transaction allowlist. New boundary test preserves older restore ranges and
forbids boot/tail writes. Existing exhaustive image-range test inventories also
need the newly admitted V38 entry; initial39 failures identified those five
inventories, corrected without broadening any production range. The isolated
Aeon test staging initially lacked fm1_uboot_read.py, supplied unchanged from
this checkout; this was a collection environment issue, not a device action.

[verified] Corrected exact-source admission transaction suite:85PASS0.97s on
bounded Aeon. V38 firmware bytes unchanged from230672; only hash admission,
boundary inventory/test and these evidence notes changed.

[verified] V38 protected dev-kit cycle completed. Fresh UARTentry/actual ROM
WL82UBOOT1.00, double CURRENT V37 backups, CURRENT140factory restore,
WINDOW install/fullreadback, armed sole startup verifier, one WINDOW reset,
fresh startup3ACK in78.9792ms, actual ROM response, double NEW V38 backups,
NEW140factory restore, SAME RUN install/fullreadback and armed sole receive-only
capture all passed their applicable gates. WINDOW59409/RUN83482 receipts are
CONSUMED at invocation: NEVER retry. Sole RX33358/PID442429 was twice exactargv
verified, sent one SIGTERM and TERMINAL255 before ordinary PINGACK; PID absence
checked. Board now V38 healthy idle. No build/RX/KA6/device operation remains live.

[verified] Strict parser passed4arithmetic/4mixedPCMcontrol/24outer/40DETAIL/
104MICRO records;22052queue jobs zeroerrors, worker finiteexit. Mean per64frame
block1974.375/2033.958/2067.417/2223.458us; ALL5513blocks late in eachcase:
FAIL34829tick deadline. Max56002/57947/62019/68542ticks. Stable heap77044bytes;
parent unused1532/8192bytes, worker7452/8192. No deadline or analog acceptance.

[verified] New six components, means across fourcases per audio block:
systemintake37.167..37.458us; moduleparams49.875..50.250us;
gates20.625..20.833us; output/IOprepare8.792..8.875us;
moduleprocess56.292..56.750us; outputsanitation13.375..13.542us.
System counts11025/11026/11026/11026; each of five modulecomponents exactly
5times thosecounts. These contain observer overhead and are SUBSETS of
recording/outer banks; NEVER add bank totals. Workerouter5 OVERLAPS CPU0.
Instrumentation has higher total means than V37; no speedup claimed.
Neither params nor process alone can close the measured500..772us gap.

[verified] Private raw SHA256
4c577c243e41fa1a5b5d0a994b0cb1c3183102ea9f81aa8639ce668ff696d13a.
Target facts/startup/transaction receipts/uart metadata saved under
scratch/devkit-20261023/build-renderer-module-micro-v38; raw beside that folder.
Offline admission is historical and its hardware flags remain unmodified;
these target facts separately establish deployment/correctness, not acceptance.

[inferred] Next investigate whether the existing CPU1 Macro-only partition can
also process its instance-owned insert Drive/meter work while CPU0 renders the
other sounds, following the community whole-part approach. First inspect exact
app ordering/control updates and transitive mutable state, then host exactPCM
and fault ownership/lifetime proofs before any implementation promotion or new
image. This is a hypothesis, not demonstrated timing savings; do not repeat
V30 Macro+Drums partition regression or weaken PCM/rates/polyphony/firstblocks.
Actual FM1 recovery remains untouched; no physical FM1 or Hera traffic.


### V39 private whole-part post-processing proof and browser artifact repair

[verified] A private shadow-tree experiment moved sound1's insert processing,
raw/insert/level meters and level application after CPU1 Execute1 and before its
completion ACK. CPU0 retained summation in the original sound order. The complete
44104-batch,11290624-byte shared-app replay matched exactly, both normally and
with ASAN/UBSAN (sanitized replay28.05s). Two additional callback protocol checks
passed normally and with ASAN/UBSAN (0.67s):2000 batches, worker ownership,
render-before-post-before-ACK, cleared registration, malformed/duplicate refusal,
and timeout while inside post followed by exactly one late completion and
permanent refusal. This remains private host-only code; no production/preparer
integration, vendor image, target timing/cache/ABI/race/stack proof or new install.
TSAN remains unavailable. Source inspection found per-instance Drive state and
distinct meter/level entries; immutable route/event inputs, fixed insert allowlist,
observer exclusion and target linked-code/stack review remain promotion gates.

[verified] Exact-head CI40318255682 job121556356195 failed the committed-WASM
source freshness check, rather than engine compilation or PCM tests. The existing
bounded Aeon pipeline rebuilt the actual artifacts:108 parity scenarios passed,
all108 exact against JS and musl, metadata/SysEx/edit parity passed; the30-second
edit storm recorded zero late quanta. CI=true focused committed-record test passed
(1 test,0.20s). New WASM SHA256 f15f99d5a881b154c17cbcded36c779adf0aee14f62dbb9a9c1019604a4a79d7,
1587281bytes. The record was generated by the build, not edited manually.
This repairs the browser artifact; new exact-head CI remains required. It does
not change installed V38 or establish hardware deadline/analog acceptance.


### V39 guarded CPU1 insert scheduling source integration

[verified] Added optional `--engine-queue-insert` preparation, with queue post
callback/storage compiled only under `LUNAR_QUEUE_POST`. Sound1's Macro model0
engine stream is followed by its Drive/empty insert chain, meters and mix level
before CPU1 acknowledges completion. CPU0 retains the original summation order.
The per-block guard rejects unsupported inserts, nonzero Macro model, null or
undersized/overlapping/overflowing arenas before publication. Queue refusal
retains all app/context/buffer storage after timeout, even after late completion.
Drums partition/detail/micro/legacy per-unit observers are excluded; outer queue
profiling remains supported. Ordinary builds are unchanged.

[verified] Bounded Aeon queue suite passed53tests in109.85s: both new full-app
PCM modes plus original12 modes, callback ownership, late-worker refusal and
preparer guards. Final ASAN/UBSAN integration passed both new modes in35.96s,
including full11290624-byte/44104-batch equality each, fault lifetime and actual
unsupported-layout Begin refusal before any worker publication. The first layout
harness inherited the audio replay's44104-completion destructor assertion; a
separate layout-only host setup fixed that test error without weakening replay
assertions. Rarefaction cannot reach this external worktree from its fixed primary
root; Serena located the actual preparer function in this checkout. Source/host
proof does not establish target ABI/cache/race/stack safety or timing speedup.
No new vendor image has yet been built, admitted, staged or installed. V38 remains
installed; all5513blocks/case still miss the34829-tick deadline. Next: exact-source
vendor build and linked callback/ACK/stack/recovery/SDK/layout/cipher/NOR review.


### V39 exact image admitted offline; target timing still pending

[verified] Exact source473e6f84 linked with the vendor compiler. The final ELF
review confirms Macro engine execution then Drive/empty insert, meter and level
callback before CPU1 release acknowledgement; CPU0 acquires before its original
sound-ordered sum. Unsupported layouts refuse before recording/publication.
UART18 precedes parent16 on the successful allocation path; the200-tick recovery
window still precedes arithmetic, static8KiB CPU1 worker reservation and renderer
initialization. Source/linked review covers41files and54target functions,
including instance-owned Drive state and register/stack-only linked math paths.
The listed callback frames conservatively sum632bytes, excluding SDK/IRQ and
unlisted paths; actual target stack high-water remains required. TSAN is unavailable.

[verified] All636manifest input hashes and prepared app/linker/build fragments
match. Independent vendor objcopy matches the569436-byte flat app
`e0a332888481e341929623dfe4b6ff5708d5dc3c83ea05a48edcc2cbf22469cc`.
Nine reviewed DSP tables remain byte-identical to V38. SDK audit has zero failures;
its one scheduling pending item is resolved by exact normalized SDK/ROM-entry
comparison against the approved prior link. Independent reference cipher/CRC,
protected config/prefix/tail checks and the NOR model pass complete install/restore,
metadata-last ordering and recovery after interrupted pages7/1127/2215/2231.
CURRENT V38's independent140-sector restore also passes.

[verified] Admitted only the exact8MiB candidate
`de0fa4e5c54bc3e27763e60cce6732160a72dba143348916c190e7efa9ed31a8`,
140sectors `[0x4000,0x90000)`, app end0x8f17c. The transaction/reset suite passed93
checks; parser rejects27existing faults plus two foreign observer banks. Earlier
53host tests and two final ASAN/UBSAN replay/fault cases remain passing. Initial
cipher check lacked crcmod; the existing offline queue-detail-v32-libs dependency
resolved that invocation error. Local test interpreters lacked pytest; existing
cached wheels supplied an ignored task-local test environment. No checks weakened.

[verified] No V39 hardware staging, install, reset or capture occurred. V38 remains
installed and misses the deadline in every block. V39 speedup, cache/ABI behavior
and target stack headroom are unknown. Next is the protected WINDOW/RUN cycle,
followed by mixed timing/stack evaluation; analog/fault/30minute acceptance remains
unfinished. Private reports/scripts/candidate remain ignored research artifacts.

### V39 target insert overlap: correctness passes, deadline still fails

[verified] Installed exact admitted V39 `de0fa4e5` through the full protected
cycle: fresh acknowledged UART entry and actual ROM, two complete CURRENT V38
backups, factory restore, WINDOW install/full readback, armed startup verifier
before one reset, fresh three-command handshake in79.2427ms and responsive ROM,
two complete NEW backups, factory restore and SAME-image RUN install/full readback.
WINDOW35702 and RUN59549 are consumed at invocation, as are all older receipts.
Sole receiver44854/PID458172 was twice exact-argv verified, sent one SIGTERM and
observed terminal255/PID absent before an ordinary PING acknowledgement. Board
healthy idle; no capture or device operation remains live. No physical FM1 traffic.

[verified] Strict actual UART validation passes four arithmetic patterns, all
four mixed PCM/control fingerprints,24outer regions and22052 queue jobs without
errors, with finite worker exit and complete marker. Heap77396bytes stays constant;
unused parent stack2500/8192bytes and worker7444/8192bytes. Means are
1913.125/1979.958/1978.333/1999.500us; maxima55153/55623/59980/61474ticks.
Late blocks are5509/5513/5513/5513 of5513: the34829tick deadline FAILS.
Raw SHA256 `9e352c7d889d3b8bb31353e21a304fc3581fd5fd19bff6380d9770f29d82e5f3`.
Private raw/facts/receipts/startup metadata are in build-renderer-queue-insert-v39.

[verified] CPU0 post-dispatch is538..544us, recording258..259us and caller
execution652..1142us; wait450/325/202/44us. CPU1 engine+insert region1102..1170us
OVERLAPS CPU0 and must never be added. Compared with V31's same outer-profile
configuration, means decrease1.90/1.64/3.18/9.06percent in this single run. This
supports moving complete per-sound work together, but does not establish sustained
speedup or dropout-free acceptance. V38 has extra observers and is not the clean
comparison. Even removing all wait leaves a substantial deadline gap.

[verified] Exact source19560 CI40323150122 Chromium job121573474858 failed its
actual30-second edit storm: two playback underruns totaling23.218ms, with empty
error logs, zero rejected codes and successful snapshot. Actual job log is saved
privately as ci-40323150122-chromium.log. This is a separate actionable browser
audio failure; no gate was relaxed or passing test rerun. Other CI jobs remained
in progress at last inspection. Pages40323150021 succeeded. PR155 stays draft and
unmerged; analog/fault validation and representative30minute soaks remain undone.

### Chromium delivery stall: failing CI trace and independent passing control

[verified] Downloaded the failed job's complete browser trace and phase timeline.
Both SyncReader timeouts occur during the edit loop, about29.46seconds after its
start, before snapshot drain. The two underruns total23.218ms. Three glitch trace
publications describe the same two-event counter, not three separate glitches.
Trace collection is complete with zero dropped events; no FIFO-shortage events
appear. Absence of that event does not negate the playback-counter failure.

[verified] The failing callback contains a38.771ms PushPullFIFO::Push span with
only73us thread CPU time. Its nested under-lock span begins near the end and
takes7us. The immediately preceding RealtimeAudioDestinationHandler::Render
takes175us. AudioOutputDevice's waiting span lasts39.464ms. No overlapping traced
FIFO Pull explains the stall. This locates the observed delay outside that DSP
render; it does not identify a lock owner or distinguish mutex waiting from OS
descheduling. The Chromium FIFO source places its under-lock trace after
AutoLock acquisition [verified against the exact Chromium153.0.8010.12 tagged
source](https://chromium.googlesource.com/chromium/src/+/refs/tags/153.0.8010.12/third_party/blink/renderer/platform/audio/push_pull_fifo.cc),
retrieved independently as base64 text and decoded into private research storage.

[verified] One independent exact9c0c07d7 source archive ran the unchanged30second
storm on bounded Aeon: Playwright1.63.0 / Chromium153.0.8010.12, four CPUs,
6GiB memory/swap limit, PulseAudio null sink and the same scheduling capture.
Session75488 terminated0:7168accepted edits, no rejected codes or error logs,
10695quanta, binary snapshot and zero playback underruns. Its longest FIFO Push
was665us; its longest DSP render was2319us during startup. This is a passing
control, not a fix or proof that the CI failure is harmless. No gate, renderer or
committed WASM changed. Private artifacts are ci-40323150122-chromium-artifacts
and repro-traced under scratch/devkit-20261023; the Aeon source/output directory
is chromium-underrun-9c0c07d7. No test remains live.

[inferred] Browser delivery waiting/descheduling is the next hypothesis to test.
Use a predeclared bounded idle/storm or observer-on/off diagnostic comparison;
retain failures and the ordinary zero-underrun acceptance gate. Existing trace
does not establish that playbackStats polling, tracing, host contention or Lunar
caused the wait. Exact9c0CI40325582091 remained in progress at last check;
Pages40325581941 succeeded. No device traffic occurred during this investigation.

[verified] Predeclared controls40083 terminated0, one30second run each on the
same archived source and bounded Aeon container: idle playback with observers
and ordinary edit storm without CDP trace/timeline polling both had zero playback
underruns. The storm accepted7161edits,10695quanta, no errors and binary snapshot.
The idle JSON says diagnostic_is_acceptance=false, edited=ops=0, pass=true:
contrary to the source comment and our initial expectation, the predicate permits
zero edits when both counts match and initial changes/telemetry exist. This does
not alter the normal storm, which submitted7161edits, and is not a reason to
count idle as acceptance. These three passing Aeon observations cannot establish
that observers, workload or host scheduling caused the failed CI run. All results
are retained; no retry-until-pass or gate change. Outputs are control-idle-traced
and control-storm-unobserved in the same private local/Aeon research directories.

### Private V40 caller insert overlap proof

[verified] V39's Dispatch executes CPU0 sound streams0/2/3 before waiting for
CPU1 sound1, but their inserts/meter/level work remains after the join. A private
shadow prototype invokes the existing generic per-sound post callback immediately
after each Execute, on its owning core. It removes the duplicate post body from
render_sounds while retaining the original sound-order sum and both master FX
after successful acknowledgement. CPU1 still owns only sound1; no Drums worker
partition, algorithm, rates, event order within streams or arithmetic changed.

[verified] Source ownership review covers the new overlap of CPU0 Filter with
CPU1 Macro0/Drive: Filter and its DSP header have constant file-scope data,
instance/local control and filter state, no RNG, and fabsf/floorf/sqrtf math calls.
The shared route/event/write inputs are frozen through the batch; meter rows and
seq_level entries are distinct per sound. This is source evidence, not a new
linked ABI/cache/stack or runtime race proof. Promotion requires a fixed
Filter/Drive/empty allowlist and nonalias arena validation for ALL moved inserts
before publication; the existing V39 guard covers only its earlier worker scope.

[verified] Bounded offline Aeon host suite61746 terminated0 with24checks, including
the full44104batch11290624byte replay exactly matching baseline and timeout buffer
lifetime. Sanitizer replay45779 terminated0,1PASS20.72s. Ownership harness41701
terminated0,2PASS0.68s normal+ASAN/UBSAN:2000batches, expected caller/worker thread,
render-before-post, caller callbacks before the first worker acknowledgement,
timeout after caller post, late worker post and permanent refusal. The first
ownership invocation failed compilation because the private harness's braced
range lacked the required initializer-list declaration; a plain bounded loop
fixed the harness. No production assertion or acceptance gate changed.

[verified] Scripts/review/logs remain private in scratch/devkit-20261023 as
queue-caller-post-v40-proof.py, test_queue_caller_post_v40_proof.py,
test_queue_caller_post_v40_ownership.py and queue-caller-post-v40-ownership-review.md;
the exact4f2afa82 Aeon archive is source-caller-post-v40-proof. No tracked source
integration, vendor build, image admission, staging or hardware operation occurred.
No test remains live. Target speedup is unknown: the current450/325/202/44us waits
bound the work this scheduling change could hide, with less opportunity in the
heaviest case. Next: guarded opt-in integration, focused ownership/PCM/fault checks,
then full vendor and image admission before any target timing comparison.

### V40 guarded caller post integration: host proof

[verified] Added opt-in --engine-queue-caller-post requiring queue inserts and
the existing isolated mixed outer-profile preparation. CPU0 executes sound0/2/3
post work after its stream, before joining sound1. Ordered sum and shared masters
remain after ACK. Default V39 scheduling is preserved. Generated app and compile
flags must agree. The fixed layout permits Filter/empty on sound0, Drive/empty
on sound1 and empty inserts on sounds2/3; every moved sound/insert arena is
capacity-valid, nonalias and instance-owned before publication.

[verified] Bounded Aeon final focused run58744 terminated0:29PASS20.05s, covering
new/default prepared PCM, callback ownership normal+ASAN/UBSAN, unsupported
preparation and ten fresh-process layout faults refusing before publication.
Full caller replay89418 terminated0:1PASS21.06s under ASAN/UBSAN,44104batches
11290624PCMbytes exact and timeout lifetime. Initial integration23999 and revised
fault run88985 passed; final tests supersede them. Logs saved privately as
queue-caller-post-v40-{final,final-asan}.log. No target speed/cache/ABI/stack/race
proof; TSAN remains unavailable. No image built/admitted/staged/installed yet.

[verified] Serena selected this absolute worktree, Python symbol query matched
queue_insert_callbacks. Rarefaction status ready at primary checkout but scope
refused the external worktree path; native inspection used, server not re-rooted.
Exact e7d262c3 CI40328500916 in progress without failed jobs at check;
Pages40328500547 success terminal. Older browser underrun remains unresolved.

[verified] V40 exact source563e56f745893801f5e78d84ea0febeeea32ea7a pushed and
remote SHA verified. Vendor34785 terminated0; export93366 terminated0. ELF
1d8d0fa2ae103110fe4fd080d9d1ec1ec3bd57afa4fcf904ba69d5576c1b06b7, app569276B
50e642eab7b7131dc3fcaffd89eb3baa07215bd50838d5c9acd14a4e2c244f0b.
636manifest files zero mismatches; independent vendor objcopy matches section
concatenation. Linked ordering shows all owner posts after engines, caller0/2/3
before join, worker1 before ACK, acquire fence and unsupported guard before
publication. UART18 before successful parent16,200ticks before arithmetic/static
8KiBworker/init; startup copy/BSS/cache reviewed. Storage nonalias; pretask heap
119596. Protected SDK/strong ROM routines match approved normalized bytes;
audit_link zero failures/one scheduling pending resolved by exact SDK comparison.

[verified] Expanded source/target independence report covers43files61functions,
Filter/Drive instance-owned state and constant globals, no Filter RNG or absolute
SRAM immediates in reviewed DSP functions. Math leaves use registers/stack without
shared writes. Largest listed individual frame1160bytes; this is not a complete
call-chain/SDK/IRQ bound or runtime high-water result. Initial private linked-order
script matched an earlier conditional instead of the callback tail; bounding its
search after the op loop corrected the script. No firmware assertion changed.
Reports/scripts stored in private build-renderer-caller-post-v40 and review-v40-*;
NO8MiBcandidate generated, NOadmission/staging/install. Next full stack/cipherCRC/
protected-config/NOR interruption review and exact transaction/parser gates before
image admission. No build/test/device operation remains live. Exact563e CI40329848882
in progress with no failed jobs at check; Pages40329848910 last in progress.


### 2026-10-26 V40 offline image admission

[verified] Exact firmware source `563e56f745893801f5e78d84ea0febeeea32ea7a` produced private candidate `dae1cd4171dbfdc591e162017d697335a1a6e96e91237e279e23091ce3aafc11`, 140 sectors `[0x4000,0x90000)`. Independent cipher/CRC/protected configuration check passed. NOR install/restore and interruptions at pages 7/1127/2215/2231 restored factory; installed V39 independently restored over its own 140-sector range. Hardware commands: zero. Exact target hash is separately pinned in the transaction tool; V39 restore admission remains intact. Transaction/reset suites: 94 passed (1.15s), including boundary refusals. Strict parser rejects 29 fault fixtures and actual incompatible V28/V30 captures; correct PCM does not imply a deadline pass.

[verified] Nine DSP constant tables (23,454 bytes) match installed V39. Listed stack frame worksheet gives caller Filter post 1,352 bytes, worker Drive post 632, caller control 2,316, caller UI 1,920, worker Macro 812. These deliberately conservative listed sums include mutually exclusive helpers and exclude SDK/IRQ/unlisted paths: they are not whole-stack maxima or runtime safety proof. Fresh target high-water measurements remain required. Full source/vendor/ownership/UART-first/200-tick recovery/SDK/layout reviews and host PCM/fault proofs remain as recorded above. TSAN unavailable, no race pass.

[verified] Private evidence: `scratch/devkit-20261023/build-renderer-caller-post-v40/offline-admission.json` and hashed reports, mirrored to Aeon `renderer-caller-post-v40-exports`. Candidate OFFLINE ADMITTED, not staged or installed at this checkpoint; target gain unknown. Current board V39 remains idle. All prior reset receipts consumed; no retries. Actual mixed deadline and analog acceptance remain unfinished.


### 2026-10-26 V40 target result: faster, deadline still fails

[verified] Protected cycle completed: ordinary PING/acknowledged UART entry; fresh WL82 UBOOT inquiry and two full CURRENT V39 backups; factory restore/full readback; unique V40 WINDOW install/full readback; sole startup verifier armed before one reset; fresh startup PING/ARM/ENTER acknowledgments in 79.1552 ms plus responsive actual ROM; two NEW V40 backups; factory restore; SAME V40 RUN install/full readback; sole receive-only UART armed before one reset. WINDOW43196 and RUN16249 are CONSUMED AT INVOCATION, NEVER RETRY. RX23926/PID474381 was twice exact-argv verified, received one SIGTERM, reached terminal255 and PID absence before ordinary post-run PING ACK. No physical buttons.

[verified] Strict actual parser passed four arithmetic cases, four mixed PCM/control fingerprints, 24 outer region records, all 22,052 worker jobs with zero ownership/error counts and finite worker exit. Heap 77,652 bytes stable; parent unused 2,500/8,192 bytes, worker unused 7,444/8,192 bytes. Mean times: 1,739.208 / 1,804.708 / 1,822.792 / 1,966.500 us; late 4,999 / 5,513 / 5,513 / 5,513 of 5,513 blocks. Worst times: 2,062.042 / 2,150.917 / 2,274.917 / 2,525.333 us. All four FAIL the unchanged 34,829-tick deadline. Compared with V39 under the same outer-profile mode, means improved 9.09 / 8.85 / 7.86 / 1.65 percent; single-run comparison, not sustained acceptance.

[verified] CPU0 recording ~267–269 us, caller execute plus owned post ~841–1,327 us, remaining wait ~266 / 139 / 39 / 4 us, post-join ~353–355 us. CPU1 region5 overlaps CPU0 and must not be added. Regions are diagnostic observations, not proof that a particular source function accounts for all cost. [inferred] Heaviest-case negligible wait means further overlap alone cannot close its remaining ~515 us mean deficit; inspect CPU0 recording/shared-master work and exact independent-track ownership before another transformation. Keep V39 default opt-in behavior and avoid the regressing Macro+Drums partition.

[verified] Raw capture SHA256 `4c5aa0d3b49dbaa9610b8c1fa5473b337840fa151110251f7afccc3df943165e`; target-facts/target-summary/startup evidence saved locally under `scratch/devkit-20261023/build-renderer-caller-post-v40` and hash-verified Aeon exports. V40 is installed and responsive, but hardware audio acceptance remains incomplete. No KA6 capture/build/test/device operation remains live. Physical FM1 remains nonbooting and untouched.


### 2026-10-26 V41 Echo settled-glide source proof

[verified] Echo now retains every original glide calculation through its epsilon/snap sample, then skips settled checks for the remainder of that Render call. The local flag resets on every call; all six steps execute while any remains unsettled. No persistent state/layout, time constant, rate, filter arithmetic, control order or sample order changes. The differential test reconstructs only the prior glide loop inside otherwise-current source and compares PCM plus the complete persistent Instance state after each call: 2,970,528 frames / 40,000 calls, four rates, variable blocks including zero, dynamic parameters, signed zero and hostile inputs. Normal and ASAN/UBSAN passed. Separate complete old/new mixed-app proof passed all 11,290,624 PCM bytes / 44,104 batches. Focused tracked Echo/caller-post checks: 53 passed, 39 deselected (21.37 s).

[verified] Initial focused test setup selected absent g++; explicit c++/cc fixed the environment. Initial browser rebuild session91014 terminated1 because FM1_GPL_MODS=0 omitted acid-bass required by the browser parity suite, after earlier cases passed. Rebuild39300 uses the normal browser GPL-enabled module set, bounded Aeon resources, identical checks and a separate log; pending at this checkpoint. No claim of Chromium acceptance or repaired prior browser underruns. No vendor V41 image built/admitted/staged/installed and no target speedup measured. V40 remains installed and idle; all existing reset receipts remain consumed. Private proof/logs under scratch/devkit-20261023/echo-settled-v41-* and Aeon matching proof paths.

[verified] Corrected browser rebuild39300 TERMINAL0: actual WASM 1,587,368 bytes; all 108 parity scenarios pass, all identical to JavaScript and musl, 105 identical to glibc with existing libm-sensitive cases retained. DX7/metadata/SysEx/native edit checks passed. Actual module and generated build record refreshed, not manually edited. Chromium suites were excluded by --no-screenshot; prior CI playback underruns remain unresolved.

[verified] Strict committed-module/build-record test passed on bounded Aeon (1 test, 0.21 s, CI=true). Local Python environments lacked pytest; no packages installed locally.


### 2026-10-26 V41 offline admission; target not installed

[verified] Exact source e531ed0b6a16d0c9bca206f002723205960ba562 vendor link passed. ELF81ae4ecca85907c7e5f6460b3e3b7da947d3b5c2a9d54bb170339bf01e11a990; app569,372bytes SHA3877a229680a89825f61f871dc2eca04d91ee5cfa58462541bb56bf8e03b38f5. All636manifest hashes match and only fx_echo.cc differs from V40. Independent vendor section objcopy matches the application. SDK protected routines/ROM guards match after checked relocations; audit_link reports zero failures, scheduling pending resolved by that normalized comparison. UART18 before successful parent16 creation, 200tick recovery before arithmetic/8KiB CPU1 worker/renderer initialization, startup copy/BSS/cache and publication/owner callback/ACK ordering passed review. Static queue10368/worker8356 bytes; pretask heap119532. Nine DSP tables23454bytes exact V40. Listed callback stack sums unchanged, Echo listed frame100bytes and InstanceSize return machine bytes identical; these are not whole-chain/SDK/IRQ runtime bounds.

[verified] Vendor branch/store review finds the call-local flag initialized before the loop, a guard spanning all six glide stores, five OR combinations and a flag store before subsequent DSP. Vendor objdump leaves FPU words undecoded: no complete instruction-level floating-point equivalence claim. Host PCM/full-state proofs above remain distinct from fresh target proof. No target race/cache/stack acceptance; TSAN unavailable.

[verified] Private candidate1ccc1e85d9113e229b248205d59307807c36091da3c4fa14b87563e53e19ff06 independently cipher/CRC/config verified, full8MiB, application end0x8f13c and140changed sectors[0x4000,0x90000). Exact NOR install/restore and interrupted pages7/1127/2215/2231 restore factory with metadata last; actual current V40 restore140 separately passes. Model's final text retained an old V39/V40 label; its checked paths/hashes are V40/V41. First cipher container lacked crcmod; existing private offline dependency path fixed the environment. Candidate pull initially refused root-owned0600; corrected ownership without broadening permissions, local SHA verified. All95transaction/reset tests pass1.12s; strict parser rejects29faults and prior V28/V30 captures while keeping deadline separate.

[verified] Full admission hashes/reports saved privately in build-renderer-echo-settled-v41 and mirrored Aeon exports. V41 OFFLINE ADMITTED, not staged or installed; speedup unknown. Current V40 remains idle and all previous reset receipts consumed. Next exact staging/hash verification and protected WINDOW/RUN cycle, then actual PCM/timing/stack assessment. Chromium underruns and hardware deadline/analog soak acceptance remain unfinished; PR155 stays draft and unmerged.


### 2026-10-26 V41 target: exact correctness, ~1% gain, deadline still fails

[verified] Full protected cycle completed with fresh UART entry, actual WL82 UBOOT inquiry and two matching full CURRENT V40 backups, factory restore/full readback, unique V41 WINDOW install/full readback, sole startup verifier armed before one reset, fresh PING/ARM/ENTER acknowledgments79.1421ms plus responsive actual ROM, two matching full NEW V41 backups, factory restore, SAME V41 RUN install/full readback and sole RX armed before one reset. WINDOW96928/RUN95186 and every older reset receipt are CONSUMED AT INVOCATION, NEVER RETRY. RX50433/PID484255 twice exact-argv verified, one SIGTERM, terminal255 and PID absence verified before ordinary PING ACK. Board idle; no physical buttons.

[verified] Strict target parser passes four arithmetic cases, four exact mixed PCM/control fingerprints, 24 outer regions and22,052 queue jobs with zero errors and finite worker exit. Means1721.583/1787.208/1806.250/1950.542us; late4987/5513/5513/5513of5513. Max2042.500/2080.958/2283.000/2535.750us. All four FAIL unchanged34829tick(~1451.2us) deadline. Compared with V40 same outer-profile mode, mean improvements1.013/0.970/0.907/0.812percent, single-run comparison only. Heap77588stable, parentunused2500/8192 and workerunused7444/8192 bytes.

[verified] RawSHA857b8483621e14271acccd57864d85b82700fa0af2ba2cca343c30096734771b; target facts/summary/cycle receipts/startup evidence stored privately in build-renderer-echo-settled-v41 and Aeon exports. CPU1 region5 overlaps CPU0 and must never be added. Echo optimization does not close the remaining mixed-renderer gap. Next inspect CPU0 recording/shared master critical paths before exact-PCM transformation and full admission; do not weaken workload, rate, quality or deadline. Actual mixed deadline, fault-validated DAC/KA6 and representative30minute analog soaks remain unfinished. Physical FM1 untouched/nonbooting, PR155 draft/unmerged.

### 2026-10-26 V42 sparse system-CV intake source proof

[verified] CPU0 modulation intake `take_system` scanned all64 system-source IDs per tick. It now visits only IDs present in either pending-CV bitmap, in the same ascending order, using two32-bit halves and a nonzero-guarded trailing-zero operation. Current-window finite-value handling precedes next-window copying exactly as before. Gate queues, persistent layout, event order, native tick rate and floating-point arithmetic are unchanged. Standalone vendor pi32v2/r3/O3 compilation emits integer operations and native `clz`, with no bit-scan helper call; this is not a complete linked-image or target-timing proof.

[verified] The new regression reconstructs the original linear scan inside otherwise-current runtime source and compares every byte of the26840-byte runtime after intake across20000 states: each single bit in both windows, empty and dense masks, randomized float bit patterns/nonfinite values, pending gate edges and trigger-fall/frame-boundary cases. Normal and ASAN/UBSAN pass. Separate full mixed-app old/new reference comparison preserves all11290624 PCM bytes across44104 batches. Focused tracked regression/modulation/voice/kind/caller-post checks:81 passed10.99s on bounded Aeon. The internal-function isolation uses Linux section garbage collection, so that differential test explicitly skips other platforms. Private scripts, candidate function, assembly and logs remain under scratch/devkit-20261023/system-sparse-v42-* and matching Aeon paths.

[verified] Actual browser WASM rebuild19845 TERMINAL0,1587527bytes:108 parity scenarios pass, all identical to JavaScript and musl,105 identical to glibc with existing libm-sensitive exceptions retained. Strict module/build-record check passes with CI=true (1test0.25s). No manual record edits. Browser rebuild used --no-screenshot and does not establish Chromium playback acceptance; old CI underruns remain unresolved. No V42 vendor image/admission/staging/install or target speedup yet. V41 remains healthy idle; all previous reset receipts are consumed, including WINDOW96928/RUN95186. Physical FM1 remains nonbooting and untouched; PR155 remains draft/unmerged. Rarefaction cannot address this external worktree under its fixed main-checkout root; Serena selected the actual absolute worktree and resolved the inspected runtime symbols. Native inspection filled the remaining coverage gap, without target ABI claims.

[verified] V42 source checkpoint033a0797b82bc3e75d802c8b06aa3fd42bc70d5b pushed with matching remote SHA. Exact-source bounded vendor build90101 TERMINAL0, export complete. ELFde2342d8c7510a92a1522a6c9e6e4a6d0a2cc369ced7c53b469283b04f5dee1b; app569564bytes SHA7b59e17938cac90e88c02c06bc7663459693d7de36175fc2ead2379022fb18c0.636manifest hashes match, independent vendor objcopy matches application bytes. Preliminary SDK normalized routine/ROM guards, static ranges, publication/owner callback/ACK order, UART18-before-parent16,200tick recovery-before-worker and startup copy/BSS/cache checks pass. Static queue10368/worker8356bytes, pretask heap119340. Independence audit lists43files/61functions, largest individual frame1160, not whole-chain/SDK/IRQ stack proof.

[verified] Linked fm1_mod_tick contains both sparse loops in SRAM, native clz instructions, zero-mask exits and lowest-bit clearing; the high-half address includes bit32. Vendor disassembly still leaves floating-point words undecoded, so no complete instruction equivalence claim. Full stack/table comparison, audit_link, independent cipher/CRC/config, NOR interruption and final admission reviews remain pending. No8MiB V42 candidate generated or device operation performed. Target speedup remains unknown; V41 remains CURRENT. Source/instruction checks do not establish race/cache/ABI/runtime acceptance, and TSAN remains unavailable.


### 2026-10-26 V42 offline admission complete

[verified] Final V42 image SHA b3caa5a1df5fdecacf4585cbea428a4c9bb5cac5319bed20973a3f85862c5d39 is admitted offline for exactly140 sectors [0x4000,0x90000), app end0x8f1fc. Independent reference cipher decode, application/header/area CRCs and protected configuration match. NOR model installs/restores byte-identically, writes metadata last, and restores interrupted page7/1127/2215/2231 cases; installed V41 separately restores all140 sectors. Hardware commands in this model:0. Nine DSP constant tables,23454bytes, match installed V41 exactly. Listed control stack path2320bytes grows4bytes; other listed paths unchanged. These sums exclude SDK/IRQ/unlisted paths and do not establish whole-stack safety. audit_link reports no failures; scheduling pending is resolved by exact normalized protected SDK/ROM comparison. Strict parser rejects29 fault fixtures and old V28/V30 captures. Transaction/reset suite96PASS0.87s after exact-hash admission, retaining installed V41 restore support.

[verified] Private offline-admission.json hashes14 artifacts in scratch/devkit-20261023/build-renderer-system-sparse-v42 and mirrored Aeon exports. All candidate/model sessions terminal. V42 NOT staged, installed or hardware accepted; V41 remains healthy idle. Target speedup unknown. Latest observed notes9885130c CI40343532169 in progress; Pages40343532279 succeeded terminal. PR155 remains draft/open/unmerged. Old Chromium underruns and mixed deadline/analog acceptance remain unfinished. Next stage exact candidate and current transaction tool, then fresh protected WINDOW/RUN cycle; no previous reset receipt may be retried. No physical FM1 commands authorized.


### 2026-10-26 V42 target cycle and sparse-intake result

[verified] V42 b3caa5a1df5fdecacf4585cbea428a4c9bb5cac5319bed20973a3f85862c5d39 completed the full protected cycle: acknowledged UART entry, actual WL82 UBOOT inquiry, two matching full CURRENT V41 backups, factory restore and full readback, unique WINDOW install/full readback, sole startup verifier armed before one reset, fresh ready and three acknowledgments79.1516ms, responsive actual ROM and two full NEW V42 backups, factory restore/full readback, SAME unique RUN install/full readback and sole RX armed before one reset. USB devnum52 remained enumerated across the core reset; it was not treated as startup or ROM proof. WINDOW41729/RUN5256 and every older receipt are CONSUMED AT INVOCATION, NEVER RETRY. Sole RX10297/PID497309 was twice exact-argv verified, sent one SIGTERM, terminal255/PID absent before ordinary PING ACK. Board healthy idle, no buttons or physical FM1 traffic.

[verified] Strict parser passes4 arithmetic cases,4 exact mixed PCM/control fingerprints,24 outer regions and22052 queue jobs with zero errors and finite worker exit. Means1704.250/1769.375/1789.042/1934.458us, max2041.333/2089.875/2256.417/2527.958us; late4958/5513/5513/5513of5513. All four FAIL unchanged34829tick(~1451.2us) deadline. Heap77396stable, parentunused2500/8192 and workerunused7444/8192bytes. Versus V41 same outer-profile mode, means improve1.007/0.998/0.953/0.825percent, single-run comparison only. CPU0 recording250..251us versus V41~267..268us; caller842..1328us, wait263/136/37/4us, post337..339us. CPU1 region5 overlaps CPU0 and must never be added. Sparse intake removes measurable work but leaves a substantial deadline gap, especially the heavy case with negligible wait.

[verified] RawSHAe0f09efc4e2dc521c5403282a80c978e91ce5280edd3b15b7bd89a0a980d53e3; private raw/facts/summary/startup/cycle receipts saved locally in build-renderer-system-sparse-v42 and Aeon exports. Next inspect remaining recording/module-system or shared-master critical paths before another exact-PCM change; do not assume additional overlap can close the gap. Actual mixed deadline, fault-validated DAC/KA6 and representative30minute analog soaks remain unfinished. Exact040e76fe CI40344620253 last in progress with no failed jobs; Pages40344619962 succeeded terminal. PR155 remains draft/open/unmerged. No build/test/RX/device operation live, physical FM1 remains nonbooting and untouched.

## Quarter-rate waveform and screen experiment — 2026-10-26 (V43)

[verified] At the owner's request, waveform/peak collection runs on one render
block in four. Normal screen draws, including dirty redraws, wait four times
the requested interval. Explicit zero-interval offline draws remain immediate.
The default visual divisor is four; one restores the original cadence for A/B.
Audio processing, event timing and control polling are unchanged. The separate
sparse modulation-slot experiment was kept private and excluded from V43.

[verified] Full old/new mixed output matches all 11,290,624 PCM bytes across
44,104 blocks. Both existing framebuffer tests pass. Vendor build succeeds.
The owner-approved streamlined installation used acknowledged UART entry,
one application flash and one reset with an armed receiver. No new backup,
factory restore rehearsal, full-flash readback or exhaustive admission cycle.
Initial unprivileged SG open failed before commands; sudo installation succeeded.
Reset marker iteration-visual-quarter-v43-20261026-b/.reset-attempted is consumed;
never retry. Receiver PID503521 was closed and terminal before ordinary PING ACK.

| Density | V42 mean us | Quarter-rate mean us | Saved us | Late / 5513 |
| --- | ---: | ---: | ---: | ---: |
| 0 | 1704.250 | 1702.167 | 2.083 | 4932 |
| 1 | 1769.375 | 1767.667 | 1.708 | 5513 |
| 2 | 1789.042 | 1786.958 | 2.083 | 5513 |
| 3 | 1934.458 | 1931.250 | 3.208 | 5513 |

[verified] Four arithmetic/mixed PCM/control cases, 24 timing regions and 22,052
queue jobs pass correctness checks, zero queue errors and finite exit. Heap is
stable at 77,332 bytes. Unused parent/worker stack is 2500/7444 bytes of 8192.
All four cases still FAIL the unchanged 34,829-tick deadline. This single-run
0.10–0.17% mean difference is small; no sustained or perceptual acceptance claimed.

[verified] Important limit: this timing harness uses unattached external pixels,
so screen drawing already returns early. These figures measure reduced scope
bookkeeping, not the savings from a quarter-rate physical TFT update. Do not
attribute the remaining DSP deficit to screen drawing without measuring the
actual attached-display path. Instrumented timing is not analog acceptance.

Private evidence: scratch/devkit-20261023/build-renderer-visual-quarter-v43,
visual-quarter-v43-proof, visual-quarter-v43-{build,install-b,package,wasm}.log,
and renderer-visual-quarter-v43-run-20261026-uart.bin. Raw SHA256
bc943b1a8f1f4c2dce4a8ff669380845d8548c5fdad437741385701fefaa617b.
Astra review prompt: notes/2026-10-26-astra-performance-review-prompt.md.
Owner target is to resolve the performance within the next 24 hours; this is
a work priority, not a claim that the hardware acceptance has been achieved.

[verified] Rebuilt the committed browser WASM and its generated record on bounded
Aeon jobs: all 108 parity scenarios pass; strict build-record freshness passes.
This used --no-screenshot and does not establish Chromium playback acceptance.
No CI gate was relaxed. PR155 remains draft and unmerged.

### V44b DX7 frequency cache — correct, no useful target gain; rejected

[verified] Tested a per-voice cache of the common pitch-modulation input to six
frequency lookups. Start/retrigger and legato Retune invalidate it; all envelope,
LFO, glide, gain and phase work remains unchanged. The first six-key prototype
exceeded the existing 16 KiB instance limit and was rejected. The compact key
passes all 143 DX7 tests, including that unchanged memory gate, and the full
11,290,624-byte / 44,104-block mixed PCM matches V43 exactly. The initial proof
script accidentally compared the previous V43 pair; an explicit comparison of
the newly generated V44 before/after files independently confirmed equality,
and the saved script is corrected. Vendor build succeeds; actual browser
rebuild passes 108 parity cases, without Chromium acceptance.

[verified] One streamlined application flash, no backup/readback/restore.
UART entry acknowledged, fresh ROM USB 54 at path `3-1.2`, `/dev/sg0`.
Sole receive-only capture armed before one consumed reset. Image
`dde4ffb540a6440acbd7d384bfae7080208f5b6572351a5f7ad89ad727c6e9d8`,
app `2118fb7de6b68a014fc35ed7a09440c619397fef1f8a64be8d14de5c77fcbe63`,
range 140 sectors `[0x4000,0x90000)`.
Reset `iteration-dx7-frequency-v44b-20261026` is CONSUMED, NEVER RETRY.
RX session 64402 / PID 509062 received one SIGTERM after exact identity checks;
terminal 255 and PID absence established before ordinary PING ACK.

[verified] Four arithmetic cases, four mixed PCM/control cases, 24 outer
regions and 22,052 queue jobs pass, with zero errors and finite exit.
Means: 1701.750 / 1767.042 / 1790.333 / 1942.292 us.
Late blocks: 4936 / 5513 / 5513 / 5513 of 5513.
All cases FAIL the unchanged 34,829-tick deadline. Relative to V43, light cases
save under 1 us while heavy cases regress 3.375 / 11.042 us. Single-run
comparison, not sustained acceptance. Heap 77,268 bytes stable; unused parent
stack 2500/8192 and worker 7444/8192 bytes. No useful measured gain: source
cache and generated browser artifacts reverted; private prototype retained.
Board remains on this correct, responsive experimental image until the next
iteration. This is not a production optimization or audio acceptance.

[verified] Private scripts/source/raw/facts remain under
`scratch/devkit-20261023/dx7-frequency-v44b-proof` and
`build-renderer-dx7-frequency-v44b`. Raw SHA:
`2b84764f96f1f9294b10c298033a753680fe17d5b67bf941624fff60550a3484`.
[inferred] Continue targeting engine/control/master cost. Do not promote this
cache or the regressing Macro+Drums partition. Echo has same-sample cross-fed
stereo feedback, so simply assigning one channel to each core is not an
independent-track optimization. Physical FM1 untouched.

### V45 stage-one interpolation scheduling experiment (offline)

[verified, source and vendor disassembly] The two coefficient interpolation
chains in the resampler's first stage were emitted consecutively. The new
opt-in diagnostic flag `--resampler-stage1-schedule` interleaves their
conversions, slope products, base additions, input products and accumulations.
Each chain retains its original operations and addition order. This is distinct
from the earlier rejected stage-two FIR scheduling experiment. Production DSP
and default preparation are unchanged.

[verified, offline] Fourteen focused resampler tests pass, including bitwise
output and complete streaming-state comparisons across seven input rates and
two output rates. Full mixed replay preserves all 11,290,624 PCM bytes across
44,104 blocks. The bounded vendor build succeeds; actual decoded target code
interleaves the two floating chains. Drums/Macro callback local stack allocations
remain44/52bytes, respectively. These observations do not establish a target
speedup. No candidate installed or performance acceptance yet. Private scripts,
logs and disassembly are under scratch/devkit-20261023; no vendor output is
committed. Next: one streamlined application flash and fresh target timings.

### V45 target result — stage-one scheduling rejected

[verified, hardware] One application flash and one consumed reset completed,
with no backups, readbacks or restore rehearsals. Fresh startup completed all
four arithmetic cases, mixed PCM/control fingerprints,24 queue regions and
22,052 worker jobs with zero errors and finite exit. Heap remains77,396bytes;
unused parent/worker stacks remain2,500/7,444bytes of8,192. After closing the
owned receiver, ordinary UART PING acknowledged.

[verified, target timing] Means are1,706.875 /1,773.000 /1,787.792 /1,924.833us;
maxima2,053.750 /2,100.083 /2,245.083 /2,480.583us. Late counts are4,951 /
5,513 /5,513 /5,513 of5,513: all fail the unchanged34,829tick deadline.
Compared with V43, means range from0.30percent worse to0.33percent better.
CPU0 caller work falls about6–7us, but the Macro worker rises about6us.
This single-run result offers no useful overall gain. The opt-in diagnostic
experiment is retained for reproducibility; it is rejected for promotion.
Production DSP/default preparation remain unchanged. More instruction
interleaving alone is not supported as a solution to the remaining gap.

[verified, persistence] Source checkpoint f725a760 pushed and remote verified.
Current board is the experimental V45 image61b5a0ce7be498de25b33b144cd249a3901a483e54dc58d34781e220907b0d1a,
not the default build. Reset iteration-stage1-schedule-v45-20261026 is consumed
and must never be replayed. Receiver25737/PID514173 was exact-argv checked
twice, sent one SIGTERM, then terminal255 and PID absent before PING. Raw
SHA3eeec5dcaeb8f768ab4468a91aa591ad65d10ec11ba8b4e5917dfc2c04083e93;
private target facts and scripts are saved under stage1-schedule-v45-proof.
No process, build, test or capture remains live. No physical FM1/Hera traffic.
Actual mixed deadlines and analog/soak acceptance remain unfinished.

### V46 hot descriptor SRAM placement experiment (offline)

[verified, source/vendor symbols] Opt-in `--metadata-ram` places the fixed
mixed workload's parameter, port, engine and modulation-kind descriptors in
startup-copied SRAM. Existing hot-code placement did not include those data.
Only descriptor definition attributes change in private prepared sources;
strings, DSP source, coefficients, control cadence and default preparation
remain unchanged. The vendor link succeeds and selected descriptor symbols
are in0x01c SRAM. Seventy-four preparation rejection checks pass. Target
performance and PCM remain to be measured; no speedup or acceptance claimed.

### V46 target result — hot descriptors in SRAM

[verified, hardware] A single application flash and one consumed reset ran the
metadata-only placement experiment. Four arithmetic cases, four mixed PCM/control
fingerprints, all 24 timing regions and 22,052 queue jobs pass with zero errors
and finite exit. This checks the target fingerprints; it is not a complete
byte-for-byte target PCM capture or analog acceptance. No backups, full readbacks
or restore rehearsals were performed.

[verified, timing] Means are 1644.250 / 1710.375 / 1727.958 / 1869.625 us,
3.40 / 3.24 / 3.30 / 3.19 percent below the V43 baseline in this single run.
Maxima are 1970.750 / 2021.417 / 2200.917 / 2453.667 us. Late counts are
4840 / 5513 / 5513 / 5513 of 5513: every case still FAILS the unchanged
34,829-tick deadline. Control/recording falls from about 249 to 202 us;
the heaviest mean still exceeds the deadline by about 418 us. Descriptor
placement is worth retaining as an opt-in diagnostic, not a completed fix.

[verified, resources] Heap is stable at 73,172 bytes, down 4,160 bytes from
V45 because of SRAM storage. Unused parent and worker stacks remain
2500/8192 and 7444/8192 bytes. The board is healthy idle after ordinary PING ACK.
Receiver session 89742 / PID 516138 was twice exact-argv verified, sent one
SIGTERM, terminal 255 and PID absent before PING. The reset receipt at
iteration-metadata-ram-v46-20261026 is consumed and must never be replayed.
Current image is c2a1cfc3c517d0e97c1c61e9bbdd54180c74be63e4c4958811090a501e07fcb8;
app d9cb88f76e3aa1705421936f372b37b1502a0b9eabf07ea8dd5db75f250682ea,
140 sectors [0x4000,0x90000). Raw SHA
156bb7d7a1e5ce17611aeb1f0799f6961088422d0755e5899d0750f3ed53af03.
Private facts and placement report are in metadata-ram-v46-proof.

[inferred, next experiment] Keep this measured placement gain while targeting
remaining repeated control/parameter evaluation or shared-master DSP work.
The heavy-case wait is only 4.292 us, so eliminating queue wait cannot close
the remaining gap. Do not repeat rejected pitch-cache or FIR scheduling probes.
No physical FM1 or Hera traffic; no operation remains live. Mixed deadline,
output fault validation and sustained analog acceptance remain unfinished.

### V47 Macro cached-flash placement — rejected

[verified, source and symbols] Private preparation removed only mi_macro.cc
and the two Plaits virtual-analog engine files from HOT_RAM_SOURCES. Their
Render symbols moved to 0x020 flash; descriptors and hot tables stayed in RAM.
CPU0 code placement, algorithms and arithmetic were unchanged. This tested
shared-SRAM contention without changing core ownership or audio calculations.

[verified, target] Single application flash, one consumed reset; no backups,
readbacks or restore cycles. Strict parser passes four arithmetic cases, four
mixed PCM/control fingerprints, 24 regions and 22,052 jobs with zero errors and
finite exit. Means 1826.292 / 1890.333 / 1900.417 / 2030.750 us, regressions
11.07 / 10.52 / 9.98 / 8.62 percent against V46. Maxima 2270.875 / 2306.125 /
2431.958 / 2579.250 us; late 5266 / 5513 / 5513 / 5513. All FAIL the unchanged
34,829-tick deadline. Control and worker both slowed. Reject this placement;
V46 remains the best measured reference. Shared-SRAM contention is not supported
as a useful fix by this experiment; no precise cache-counter attribution claimed.

[verified, persistence] Current board remains healthy idle on the rejected
V47 experiment, image 0cfab95e5ab9484fe059085d22c92277142af820099ec233b7312f3e2bd11d2e,
app 3eaabcdef2da17faab21a5208a8ca41b0c4a45261f1a5e293d4083c2d7cb27b0,
140 sectors [0x4000,0x90000), app_end 0x8f2dc. Heap 90,708 stable; unused
parent/worker stacks 2500/7444 of8192. Sole RX26374 PID519600 twice checked,
one SIGTERM, terminal255 and PID absent before ordinary PING ACK. Reset
iteration-macro-xip-v47-20261026 is consumed, NEVER RETRY; all older resets
remain consumed. Raw SHA38962229ea6d593c50dc15bb6597d4d1172f9cbca1752a26be606d2f1f5106a7.
Private scripts, placement, target facts and logs remain in scratch/devkit-20261023
and Aeon source-macro-xip-v47-proof / renderer-macro-xip-v47-exports. No source
placement change promoted. No operation remains live; physical FM1/Hera untouched.

[verified, coordination] Owner explicitly requested Astra within this session.
Started astra_performance_review with gpt-6-astra/high, the exact saved prompt
and fresh V46 evidence. Read-only review except its private report; no hardware
or competing builds. Review remains in progress, not implementation acceptance.


## V48: narrower LFO phase conversions

[verified] Width and start phase are clamped to [0,1] before conversion. The
largest binary32 value below one scales to 4294967040, which fits uint32.
Handling width one as 2^32 and phase one as wrapped zero lets the other
values use uint32 instead of the software uint64 conversion. NaN fallback,
state layout, rate calculation and update order remain unchanged. Eighty-eight
focused tests pass, including 144 width/start boundary pairs; all 11,290,624
mixed PCM bytes across 44,104 host blocks match the prior source exactly.

[verified] One dev-board application flash and fresh run pass all arithmetic,
mixed PCM/control fingerprints, 24 timing regions and 22,052 queue jobs.
Means are 1624.750 /1691.500 /1705.292 /1839.667 us, compared with V46
1644.250 /1710.375 /1727.958 /1869.625 us. Control work falls from about
202 to 186 us. This is a 1.10–1.60% mean gain in one run, with stable
73,172-byte free heap and unchanged measured stack margins. Late counts are
4808 /5513 /5513 /5513: all cases still fail the unchanged deadline.
No analog or sustained acceptance is claimed. Private target facts and raw
capture are under scratch/devkit-20261023/lfo-narrow-v48-proof and its
sibling capture. The rejected V47 flash-code placement is absent.

[verified] Final linked `lfo_process` uses native `ftou` conversions and no
`__fixunssfdi` calls (the helper still exists for other code). Actual WASM
rebuild passes all 108 parity scenarios and the strict committed-source
record check. This does not resolve the separately recorded Chromium
underrun failure or establish device analog acceptance.


## V49 — skip unchanged effective-parameter work

[verified] Implemented Astra's first bounded recommendation: retain unchanged global effective parameters, refresh edits on the next tick, invalidate on plan rebuild, and still recompute routed global/voice parameters in the original order. Free LFO rate conversion caches its pure result keyed by exact input bits. No phase/gate/random update is skipped. The initial full canonical array consumed 1 KiB and caused four existing RAM-budget scenarios to fail; replaced before promotion with 32 bytes of invalidation masks inside the existing application allocation. Runtime size is now 26,880 bytes.

[verified] All 235 focused tests pass, including route removal, raw fractional enums, rack movement, kind replacement and signed zero. ASan/UBSan core/kind executables pass (3,000 plans and 1,245,985 kind checks). Full old/new mixed render is exact across 11,290,624 PCM bytes and 44,104 batches. Actual WASM rebuild passes 108 parity scenarios and the strict committed-record test. No Chromium acceptance is inferred. Vendor build and private application package succeed.

Target V49 is running the ordinary single-flash experiment; final timing pending. Astra's complete private report is scratch/devkit-20261023/astra-performance-review.md. Larger recommendations concern exact DSP kernel granularity; scheduling alone cannot close the measured heavy-case gap. No backups, full readbacks or restore rehearsals were run.

[verified] V49 target completed: means [1592.0833333333333, 1660.0, 1672.625, 1804.5833333333333] us, late4735/5513/5513/5513, all still fail34829ticks. Single-run improvement versus V48 is1.8..2.1percent. Control mean155.6..158.2us. Arithmetic4/PCMcontrol4/24regions/22052jobs pass; heap73044 stable; unused stacks2500/7444 of8192. Raw SHAf880183759a88de011579fb04365b1607592f4ce84bae83433e245d32e8ebcaf. Sole RX5513 PID527648 closed with twice-verified argv and one SIGTERM, terminal255/PID absence before ordinary PING ACK. Reset iteration-control-cache-v49-20261026 consumed, never retry. No operation remains live. Next exact DSP kernel work follows Astra review.


## V50 private paired-FIR prototype — rejected before installation

[verified] Implemented Astra's two-consecutive-output idea in a private source copy only. Saved overwritten two oldest midpoint samples, shared coefficient loads across the original eight accumulator chains and retained scalar leftovers at render-call boundaries. Full11,290,624mixedPCMbytes/44,104batches remain exact. ASan/UBSan state probe compares160,000pairs/320,000samples across8rates through4:1, complete resampler state equal after every pair.

[verified] Vendor link succeeds, but target render frames grow from44BDrums/52BMacro inV49 to472B/476B. App grows from569916B to578364B and exceeds the existing140-sector experimental range; package generation stopped at its range assertion, no complete candidate generated. The extra register spill/storage footprint fails Astra's code-generation stop condition. Rejected this unrolled paired implementation before staging or device traffic. It is not an audio/timing result. Board remainsV49healthyidle; all reset receipts consumed. Private script prepare-fir-pair-v50.py, source-fir-pair-v50-proof onAeon, fullPCM/state/build/disassembly artifacts preserved. No tracked DSP implementation changed.

Next bounded experiment is actual WARM PAD algorithm5 two-op stacks: retain generic fallback for unsupported flags, feedback and threshold transitions. Match samples, phases and feedback state before target timing. This must remove intermediate bus transfers and one loop traversal, not alter sine lookup, gain products, voice admission or release behavior.

## V51 — exact algorithm-5 operator pairs (2026-10-26)

[verified] Implemented Astra's next bounded kernel experiment in our DX7
adapter, leaving Google's vendored msfa sources unchanged. Algorithm 5's
three two-operator stacks keep each intermediate modulation sample in a
register. Carrier addition order, gain ramps, phase wrap and first-stack
self-feedback remain exact. Any silent operator or unsupported feedback
shift falls back before mutating output or state. Both ordinary voices and
copied kernel jobs use the same implementation.

[verified] A 100,000-block randomized differential matches all 64 output
samples, six operator states and feedback state: 83,094 fused blocks and
16,906 untouched fallbacks, including threshold transitions. The same test
passes ASan/UBSan with legacy shift checks disabled. The full eight-case
mixed render matches all 11,290,624 PCM bytes across 44,104 batches. Host
kernel timing improved approximately 9%; it is not target acceptance.

[verified] One application flash and fresh target run measured means
1,590.625 / 1,659.167 / 1,661.625 / 1,732.500 us versus V49's
1,592.083 / 1,660.000 / 1,672.625 / 1,804.583 us. The heavy case improves
3.99%, principally through CPU0's caller region (1,307.042 to 1,233.792 us);
CPU1 stays near 1,162 us. All arithmetic, PCM/control fingerprints and
22,052 queue jobs pass. Late blocks remain 4,735 / 5,513 / 5,513 / 5,513:
**every workload still fails the unchanged 1,451.208 us deadline**. Heap
72,212 bytes stays stable; unused parent/worker stacks are 2,500/7,444 of
8,192 bytes. This is one instrumented run, not sustained or analog acceptance.

[verified] The board returned to idle and acknowledged an ordinary PING.
No backups, full-flash readbacks or restore rehearsals were performed. The
V51 reset receipt is consumed and must never be retried. Private scripts,
compiler output, raw capture and parsed facts are under
`scratch/devkit-20261023/fm-pair-v51-proof` and corresponding Aeon paths.

## Two-prefix feasibility after V51

[verified] A private host experiment replaces one 64-frame app call with
two consecutive 32-frame calls, copying the first output before the second
reuses the app buffer. All eight workload cases remain byte-identical:
11,290,624 bytes, zero mismatches. This establishes only this workload's
partition compatibility, not concurrent ownership or arbitrary engine support.
The first proof launcher accidentally selected the baseline for both paths;
that run is invalid. The corrected launcher records distinct source and
executable paths before comparison (`prefix-v52-pcm2.log`).

[inferred] A small exhaustive scheduling model uses V51's heavy-case mean
regions, splits each cost evenly between two prefixes, and assumes zero
synchronization overhead and immutable controls. Keeping masters on CPU0
cannot improve its occupied time (best 1,726.792 us). Assigning the ordered
masters to CPU1 yields an optimistic best finish of 1,571.083 us, still
119.875 us beyond the deadline. Total occupied work is approximately
2,888.083 core-us, leaving only 14.333 core-us below two cores' nominal
capacity; IRQs, handoffs and worst-case variation still need margin.
These are model bounds under the stated assumptions, not hardware timings.
No queue implementation or new image was made for this experiment. Additional
work reduction must precede promotion of a two-prefix scheduler. Private
proof/model scripts and results are in `scratch/devkit-20261023/prefix-v52-proof`.

### 2026-10-26: reject V53 coefficient cache and V54 algorithm-one fusion

[verified] Two bounded experiments used the owner's shortened dev-board workflow: acknowledged UART entry, one application flash, one fresh reset and one performance capture each. Neither used a full backup, flash readback, factory-restore rehearsal or physical button. Both completed all four arithmetic and mixed PCM/control cases, 22,052 queue jobs and finite exit without queue errors. The physical FM-1 was untouched.

[verified] V53 cached Macro's two shared decay coefficients by the exact Decay/Colour input bits; per-note offsets retained the original calculation. All 11,290,624 reference PCM bytes matched. Its target means were 1592.333 / 1661.125 / 1663.458 / 1731.208 microseconds versus V51's 1590.625 / 1659.167 / 1661.625 / 1732.500. Worker means increased by approximately 1.6–1.8 microseconds. This is no useful improvement, so the private prototype is rejected and is not integrated. The instance allocation increased by 32 bytes; the private parser asserted that specific new arena size, with all other correctness gates unchanged.

[verified] V54 extended the retained operator-pair primitive privately to DX7 algorithm 1: two fused pairs form the four-operator chain, with a 64-sample intermediate bus, followed by the independent pair. It retained untouched generic fallback for silent-operator combinations. Randomized 100,000-block comparisons matched samples, phases, gains and feedback, including threshold transitions; the same comparison passed ASan/UBSan with legacy shift checks disabled. Full mixed PCM also matched all 11,290,624 bytes. The host kernel improved from 0.606 to 0.563 microseconds per block, but target means were 1591.083 / 1659.500 / 1662.250 / 1738.458 microseconds. The heavy caller regressed from 1233.792 to 1240.250 microseconds. The vendor helper used 284 bytes of locals, including its 256-byte bus. Reject this version; a host kernel gain is insufficient evidence of a pi32v2 gain.

[verified] A separate host-only trace found 16,072 algorithm-one calls and 12,008 fused calls across the full reference workload. Thus the target failure cannot be explained simply by the fast path never running. This trace is not a target performance measurement. No speculative compiler or cache attribution is established.

[verified] The unchanged 34,829-tick deadline still fails every case: V54 had 4736 / 5513 / 5513 / 5513 late blocks out of 5513. Heap was stable at 72,020 bytes; unused parent/worker stack was 2500/7444 bytes. Current board image is the rejected V54 diagnostic, healthy idle with an ordinary PING ACK; retained source remains V51. No new DSP source is integrated. Capture and proof artifacts are private under `scratch/devkit-20261023/{macro-decay-v53-proof,fm-chain-v54-proof}` and the corresponding bounded Aeon directories. Actual output, fault validation and analog soaks remain unfinished.

## Compressor alias and pole snapshots — rejected (2026-10-26)

[verified] V55's guarded disjoint-buffer path produced byte-identical 2306-byte vendor loops with and without restrict. It was rejected before flashing. V56 additionally copied fixed pole sets and pending handover state into render-local values only for disjoint buffers, retaining the original alias path and all per-sample control glides. Its fast loop shrank to 2192 bytes, with a local frame of 116 versus 96 bytes. Full-state differential checks covered 2,970,528 frames over 40,000 calls and 416 deliberate overlaps under normal and ASan/UBSan builds; 11,290,624 mixed PCM bytes remained exact.

[verified] V56's single application flash and target run completed correctly, but means of 1593.667 / 1662.417 / 1665.250 / 1736.292 us offered no gain over retained V51's 1590.625 / 1659.167 / 1661.625 / 1732.500 us. Late counts of 4736 / 5513 / 5513 / 5513 still fail the unchanged 34829-tick deadline. Four arithmetic and four PCM/control cases, 24 regions, 22,052 jobs and finite exit pass; heap stayed stable at 70036 bytes, and unused parent/worker stacks were 2500 / 7444 bytes. Reject both experiments; no compressor source integration. Smaller code alone did not establish faster rendering. Private proofs and captures remain ignored.

## Two-sample FM pair unroll — rejected (2026-10-26)

[verified] A private two-sample compiler unroll of the retained algorithm-five pair preserved the original sample, phase, gain and feedback order. Randomized comparison covered 100,000 blocks, including 83,094 fused blocks and 16,906 untouched fallbacks; ASan/UBSan also passed with legacy signed-shift checks disabled. All 11,290,624 mixed PCM bytes over 44,104 batches remained exact. The vendor pure-pair local frame increased from 8 to 28 bytes, and the application still fitted the existing 140-sector range.

[verified] The single-flash target run passed arithmetic, PCM/control, all 24 regions, 22,052 queue jobs and finite exit. Means were 1591.792 / 1659.833 / 1664.333 / 1761.500 us; late counts were 4735 / 5513 / 5513 / 5513. The heavy caller increased from V51's 1233.792 to 1263.375 us, so reject the unroll. Heap remained stable at 71892 bytes; unused parent/worker stacks were 2500 / 7444 bytes. Ordinary UART PING succeeded after the receive-only capture ended. No DSP changes from these rejected experiments were integrated. The mixed deadline, physical output and sustained analog acceptance remain incomplete.

## Paired FM sine-table loads — retained (2026-10-26)

[verified] V58 reads each adjacent signed sine delta/base pair through an alias-safe eight-byte `memcpy`. The linked pi32v2 FM loop emits native paired loads; its pure-pair local frame falls from 8 to 4 bytes, and the table is aligned at 0x01f29800. The private prepared header leaves interpolation, gain multiplication, feedback, phase wrapping and output summation unchanged. This is now available through guarded timing-only `--msfa-sine-pair`, requiring the existing hot signed32-sine prerequisites. Vendored checkout files remain unchanged; unexpected header layouts are rejected and the input hash is recorded.

[verified] Lookup comparison covers every one of 16,777,216 phase values in a complete period plus one million full-width phases. Randomized comparison of 100,000 operator blocks passes normally and under ASan/UBSan with legacy signed-shift checks disabled. Full mixed rendering remains exact across 11,290,624 PCM bytes and 44,104 batches. All 84 focused preparation/regression checks pass. The tracked transform produces a header byte-identical to the target-tested header; engine/browser sources are unchanged, and the strict committed WASM build record passes.

[verified] A single application flash produced fresh startup and a correct four-case run: arithmetic, PCM/control, all 24 regions, 22,052 queue jobs and finite exit pass. Means are 1591.042 / 1659.583 / 1661.167 / 1714.125 us versus V51's 1590.625 / 1659.167 / 1661.625 / 1732.500 us. The heavy mean improves by 18.375 us (1.06%); its CPU0 caller falls from 1233.792 to 1211.917 us. This is one measured comparison, not sustained acceptance. Heap stays stable at 72340 bytes; unused parent/worker stacks remain 2500 / 7444 bytes. After capture closure, ordinary UART PING succeeds.

[verified] Late counts remain 4737 / 5513 / 5513 / 5513, so every case still fails the unchanged 34829-tick deadline. The heavy mean is still 262.917 us over budget. Fault-validated physical output and representative analog soaks remain incomplete. Private target evidence is in `scratch/devkit-20261023/sine-load-v58-proof` and corresponding Aeon storage; no raw capture or SDK files are published.

## Paired FIR lifetime and bounded-loop experiments — rejected (2026-10-26)

[verified] V60 rearranged the private two-output FIR into two groups of accumulator chains, preserving each chain's operation order and the original final grouping. The vendor compiler canonicalized it back to the earlier V50 expansion: Macro and Drums retained 476/472-byte local frames. Complete resampler state and sample comparisons passed for 160,000 pairs at eight conversion rates, normally and under ASan/UBSan; all 11,290,624 mixed PCM bytes remained exact. Reject before flashing because the intended code-generation improvement did not occur.

[verified] V61 used bounded, explicitly non-unrolled loops for the same chain grouping, retaining the initial additions to zero and the saved oldest ring samples. Both local frames fell to 88 bytes. Normal and sanitized complete-state checks and all 44,104 mixed batches remained exact. The application fitted the existing 140-sector range. One application flash and one fresh target run were performed, without backup/readback/restore rehearsals.

[verified] V61 passes four arithmetic cases, four mixed PCM/control cases, 24 regions, 22,052 queue jobs with zero errors, and finite exit. Means are 1704.333 / 1771.292 / 1773.750 / 1836.417 us, compared with retained V58's 1591.042 / 1659.583 / 1661.167 / 1714.125 us. Late counts are 4962 / 5513 / 5513 / 5513: all fail the unchanged deadline. Heavy CPU0 caller rises to 1335.250 us and overlapping CPU1 work to 1278.125 us. Reject the bounded-loop pairing; smaller frames do not compensate for its target execution cost. Heap stays at 70164 bytes; unused parent/worker stacks are 2500/7408 bytes. Ordinary PING succeeds after the sole receive-only capture closes. Retained firmware source remains V51 plus V58; no FIR experiment is integrated. Private scripts, proofs and captures remain ignored. Actual deadline and analog acceptance are incomplete.

## Control-value function residency — retained (2026-10-26)

[verified] The linked runners for LFO/envelope/chance were already resident, while `fm1_mp_lfo_value` and `fm1_mp_env_value` remained in flash. V63 adds only those two unchanged definitions to the existing guarded `--kind-ram` selection. The linked functions now occupy SRAM at 0x01c04adc and 0x01c05dde. The existing five placement/drift tests pass; they verify byte-identical definitions apart from section pragmas and refuse ambiguous/missing anchors. No engine arithmetic, state, rate or event behavior is changed; no browser source rebuild is needed.

[verified] One application flash and fresh run pass all four arithmetic cases, four PCM/control cases, 24 regions, 22,052 queue jobs and finite exit. Means are 1581.292 / 1649.458 / 1652.167 / 1706.292 us versus retained V58's 1591.042 / 1659.583 / 1661.167 / 1714.125 us. The heavy control-recording region falls from 155.542 to 148.375 us; its end-to-end mean improves 7.833 us. This is a small single-run placement result, not sustained acceptance. Heap remains stable at 71828 bytes; unused parent/worker stacks remain 2500/7444 bytes. Ordinary PING succeeds after capture closure. Late counts of 4726 / 5513 / 5513 / 5513 still fail the unchanged deadline; the heavy mean remains 255.083 us over budget.

[verified] A separate host-only V62 probe counted 2,822,656 compressor gain-exponential calls but only 406 consecutive identical inputs (0.0144%); full mixed PCM remained exact. A result cache was therefore rejected before implementation or device testing. Vendor disassembly also confirms unused LFO-process return-value computation is already eliminated; no redundant-value patch is justified there. Private probe/source/captures stay ignored. Actual physical output, fault validation and representative analog soaks remain incomplete.

## Logarithmic route-range repetition probe (2026-10-26)

[verified] A private host-only V64 instrumentation pass counted 176,414 route contributions in the complete mixed workload. Of these, 88,207 evaluate the logarithmic destination-range branch; 88,206 use the same minimum/maximum pair as the preceding logarithmic call. All 11,290,624 PCM bytes across 44,104 batches remain exact against the uninstrumented baseline. The bounded Aeon job completed successfully. The probe changes no tracked engine source and produces no device image or target timing result.

[inferred] A small per-modulation-instance cache keyed by the exact minimum/maximum float bits could remove repeated range logarithms without changing signal, amount, RNG, accumulation or event order. It must retain the original arithmetic on a miss, initialize validity on instance initialization/reset, distinguish signed zero, and be checked against alternating ranges and independent instances. The call count alone does not establish target benefit; the remaining heavy deadline gap is 255.083 us. Private script `prepare-log-range-count-v64.py` and host log remain ignored; no cache is implemented or hardware accepted yet.

## Log-range cache target experiment — not retained (2026-10-26)

[verified] Private V65 adds an instance-owned, exact-bit-keyed one-entry logarithmic range-factor cache. The app's fixed modulation storage increases by 16 bytes; the first host run correctly refused the old storage bound and the corrected allocation was used before hardware testing. A million alternating/repeated ranges, independent instances, signed zeros and invalidations pass normal and ASan/UBSan checks. The complete 11,290,624-byte mixed PCM stream remains exact. No shared mutable cache, route signal, amount, accumulation order or RNG behavior changes.

[verified] One app flash and fresh target run pass four arithmetic cases, four mixed PCM/control cases, 24 regions, 22,052 queue jobs with zero errors and finite exit. Means are 1579.000 / 1647.583 / 1649.208 / 1703.333 us versus retained V63's 1581.292 / 1649.458 / 1652.167 / 1706.292 us. Late counts remain 4725 / 5513 / 5513 / 5513, failing the unchanged deadline. Heavy control recording falls only 148.375 to 147.250 us. Heap stays at 71828 bytes; unused parent/worker stacks remain 2500/7444 bytes. Ordinary PING succeeds after the sole capture closes. The roughly 2–3 us single-run difference is too small to justify integrating the added cache/layout complexity now. V65 stays private; retained source remains V63.

[inferred] Re-evaluating the existing optimistic two-prefix schedule with retained V63 timings gives 2862.792 core-us total, a 1431.396 us ideal two-core lower bound, but a 1569.542 us best two-prefix finish when masters move to CPU1 (1699.083 us with CPU0 masters). This model assumes exactly half work per prefix, no synchronization cost and no IRQ/tail margin. Two-prefix scheduling alone still misses the deadline by at least 118.333 us under those assumptions. The owner-requested Astra review was resumed with current evidence to identify a substantial work reduction or a better justified schedule. Model and experiment artifacts remain private; no new schedule is implemented or accepted.

## Exact VCF main-output specialization — measured, integration pending (2026-10-26)

[verified] Astra's updated source review identified identical coefficients in the exact zero-resonance case and Macro's discarded final VCF auxiliary output. Private V68 reuses the existing SVF coefficient setter for both filters only when both previous and target resonance are exactly zero. Both oscillators, interpolators, independent SVF histories and all main-output processing continue advancing. A Macro-only `RenderMain` omits only the discarded final auxiliary clip/store; normal virtual `Render` retains both outputs. No quality, rates, filter behavior or voice policy changes.

[verified] Differential checks cover 40,000 calls / 1,300,000 frames with varied block sizes, zero/nonzero resonance transitions and resets. Both full outputs of normal Render, main output of RenderMain and complete persistent engine state match the baseline, normally and under ASan/UBSan (legacy shift checks excluded). The complete 11,290,624-byte mixed stream also matches. An initial templated version unexpectedly placed its render bodies in flash despite the file-level directive; it was rejected before installation. A non-template shared body links in SRAM at 0x01c0e920 with a 60-byte local frame and fits the existing application range.

[verified] One app flash and fresh run pass four arithmetic cases, four mixed PCM/control cases, 24 regions, 22,052 queue jobs and finite exit. Means are 1563.833 / 1629.375 / 1633.333 / 1703.083 us. Compared with V63, worker means improve by 16.458 / 18.708 / 18.792 / 18.917 us; the heavy caller remains dominant. Late counts 4722 / 5513 / 5513 / 5513 still fail the unchanged deadline. Heap is stable at 71380 bytes; unused parent/worker stacks are 2500/7456 bytes. Ordinary PING succeeds after capture closure. This is a modest single-run worker result, not deadline or sustained acceptance. Source integration and browser/source checks remain pending; all prototype changes and captures remain private. Do not expand this into another general resonance cache or claim the heaviest elapsed time is solved.


## Smaller app-call partitions: correct PCM, excessive target cost (2026-10-26)

[verified] V69's host-only partition probe compares 4-, 8-, 16- and 32-frame calls against the saved V68 full mixed render. Every variant reproduces all 11,290,624 PCM bytes across the original 44,104 outer batches. This covers the fixed workload, not arbitrary editing or persistent UI state. No target performance estimate comes from host timing.

[verified] Private V70 measures eight sequential eight-frame calls per original 64-frame block, with separate per-prefix region totals and maxima. Each prefix consumes exactly one queue profile; the outer aggregate charges additional observer work to its before region. The single application write/reset run passes four arithmetic fingerprints, four exact mixed PCM/control fingerprints, all 192 prefix records (5513 calls each), 24 aggregate regions, 176,416 queue jobs with zero errors and finite exit. Heap stays at 69,236 bytes; unused parent/worker stacks are 2004/7456 bytes. After capture closure, ordinary PING succeeds. Two earlier offline links failed on an omitted observer clock reference and produced no installed image; the final build passes with an explicit clock callback.

[verified] Means are 2414.500 / 2639.792 / 2741.958 / 2891.958 us, with all 5513 blocks late in every case. This is an observer experiment, not an optimized pipeline. In the heavy case the first prefix caller costs 710.513 us, while later prefix callers are approximately 82–87 us. Control recording spikes near 99/97 us at prefixes zero/four, versus about 32–33 us elsewhere. Per-prefix post work costs about 81–85 us; aggregate post work rises to 655.750 us versus V68's 326.667 us. Worker aggregate rises to 1221.417 us versus 1144.792 us. Worker regions overlap CPU0 and are never added to elapsed CPU0 time.

[inferred] Reject repeated whole-app calls as a performance implementation. Proportional subdivision of the old 64-frame means misses native-block bursts and repeated per-call overhead. A useful finer pipeline must prepare controls once at their original boundaries, retain original native-block gain/envelope state while making DSP output incrementally available, run shared effects in order, and perform UI/outer accounting once. These measurements are a dependency for that design, not proof it can meet the deadline. Private scripts, source, candidate, raw UART and 192-record facts remain ignored; retained firmware source is unchanged. Actual deadline, physical output, fault validation and sustained analog acceptance remain unfinished.

## Incremental FM kernel and engine composition proofs (2026-10-26)

[verified] Private V71 renders ordered ranges of one original 64-frame FM block for the fixture's zero-based algorithms 0 and 4. Envelope preparation and original gain endpoints remain unchanged. Each range resumes phase/feedback and uses the original rounded 64-frame gain slope at its absolute offset. Silent-operator thresholds and carrier addition order remain exact. Across 100,000 randomized blocks and 809,531 ranges, every available output prefix matches the original kernel, the unrendered suffix remains untouched, and final phases/feedback/gain endpoints match. Normal and ASan/UBSan runs pass; legacy shift sanitizer checks are excluded. Invalid bounds refuse without mutation. Contiguous ordered calls remain a caller contract, not a production ownership API.

[verified] A standalone pi32v2 object compiles; vendor disassembly shows a 124-byte local allocation plus saved registers. This object uses the generic scalar lookup rather than the prepared paired-sine header and is not a linked application or target cost measurement. V72 then composes the range kernel inside the original engine's RunVoiceKernel, leaving PrepareVoice, MixVoice, resampling and outer app calls intact. The full fixed mixed workload reproduces all 11,290,624 PCM bytes. No queue, public engine API, target image or retained source was changed. Private scripts, logs and artifacts are under scratch/devkit-20261023 and matching Aeon task storage.

[inferred] These proofs establish an incremental-output building block, not a performance fix. Astra's current V68 accounting gives 2842.625 core-us occupied work. If the full 158.5-us pre-publication path remains serialized, the optimistic perfect-scheduling bound is 1500.5625 us, already 49.354 us beyond the deadline. At least 98.708 core-us of work reduction or earlier publication is needed even before synchronization, IRQ and tail margin. The sequencer computes a modulation tick before rendering preceding samples; publishing at the first existing render callback is not necessarily early. A new sealed frontier must preserve same-frame event order and publish immutable command/effect-write snapshots. Existing post callbacks read app write arrays still being appended and cannot run concurrently without that ownership change. Actual target deadline/output/fault/soak acceptance remains incomplete.

## Early sound-command readiness: tick-only frontier rejected (2026-10-26)

[verified] Astra's completed follow-up separates sound-instance ownership from app effect logs. The fixed Macro VA sound may execute immutable earlier commands while CPU0 computes later modulation ticks; existing insert/meter/level callbacks may not, because their whole-block driven decision reads future writes. V73's host-only early Macro span before the next tick reproduces the complete mixed PCM stream. No concurrent pipeline was implemented.

[verified] V74 adds a small first-command readiness observer to the original single 64-frame app call, with the worker barrier unchanged. One application flash/reset passes four arithmetic/PCM/control cases, 22,052 queue jobs, 24 regions and finite exit. Means are 1570.500 / 1635.292 / 1639.875 / 1714.917 us; late counts4727/5513/5513/5513 still fail. Heap71252 is stable; unused parent/worker stacks2508/7456 bytes. Owned RX was closed before ordinary PING ACK. No backup/readback/restore rehearsal was performed.

[verified] The intended eight-frame readiness gate fails: first spans range1–28/30 frames because an event can trigger rendering before the instrumented tick boundary. Approximate85-us readiness is therefore not a guaranteed-eight measurement. Private facts explicitly mark exact_eight_frontier=false; production acceptance was not changed. V75 adds the frontier before future events as well as ticks, preserving the original same-frame event order. Its complete11,290,624-byte host render is exact; target build/measurement is pending. No speedup or completed deadline acceptance is claimed.

## Bounded eight-frame frontier measured (2026-10-26)

[verified] V75 closes the Macro sound span before both future ticks and future events. One application flash/reset passes four arithmetic fingerprints, four exact mixed PCM/control cases,24 queue regions,22,052 zero-error jobs and finite exit. All5,513 blocks per case report a first command span between1 and8 frames. The parser rejects V74's oversized spans. Readiness from recording start averages84.469/84.547/86.288/84.231 us; observed maxima172.667/164.375/155.208/158.625 us. Earlier events retain their original boundaries and same-frame ordering. No command is actually published early in this observer.

[verified] Whole-block means1571.083/1636.625/1641.917/1707.583 us and late4726/5513/5513/5513 still fail. Heap71188 remains stable; unused parent/worker stacks2508/7456 bytes. RX was closed before ordinary PING ACK. Current image and private target facts remain in ignored storage. No new scheduler, hardware audio acceptance, or sustained result is claimed.

[inferred] Heavy occupied work is2847.792 core-us; measured mean first readiness from the outer start is96.398 us. Even ideal scheduling with only this initial idle gives1472.095 us,20.886 us late. At least41.773 core-us additional work reduction is required before any range, synchronization, interrupt, terminal dependency or tail margin. Early publication is a necessary building block, not a sufficient fix. Next work must measure native incremental-kernel overhead and identify further actual work removal before committing to a new queue pipeline; synchronous FM composition does not prove correctness across mid-block retriggers or late state import.


### V76: native incremental FM cost exceeds the scheduling budget

[verified] A private eight-range kernel preserves algorithm 5 operator-pair fusion, native paired sine loads and the original 64-frame gain endpoints. Normal and ASan/UBSan each pass 100,000 randomized blocks  / 809,531 ranges, including feedback, silent operators, phase wrap, untouched suffix and refusal. The complete 11,290,624-byte mixed PCM output is exact. An initial host link failed because a board-only observer was selected; correcting the source selection resolves it without changing the checks.

[verified] One application flash/reset passes four arithmetic fingerprints, four mixed PCM/control cases, 24 regions, 22,052 zero-error queue jobs and finite exit. Means are 1574.000/1641.375/1690.208/1866.375us, respectively 2.917/4.750/48.292/158.792us slower than V75. Late counts 4727/5513/5513/5513 of 5513 all fail the unchanged 34,829-tick deadline. Heap 70,100 bytes remains stable; unused parent 2,508/8,192 and worker 7,456/8,192 bytes. These are synchronous range calls, not an event-interleaved or early-publication scheduler.

[verified model] Heavy occupied work rises to 3010.833 core-us. With 96.680 us startup, even the ideal two-core lower bound is 1553.757 us; at least 205.097 core-us must be removed before new synchronization, dependency idle or tail margin. This implementation fails the pipeline feasibility gate. Private raw/facts/model live in renderer-prefix-fused-v76-exports; no source optimization is promoted and no hardware audio acceptance is claimed.

[inferred hypothesis under test] V76 expresses input/feedback/add choices inside each sample loop, while msfa chooses its kernels outside that loop. V77 specializes those choices at compile time while retaining all routing and state semantics. Both randomized normal/sanitizer proofs and the full mixed PCM comparison pass. Native timing is pending; this is not yet a performance improvement.


### V77: specialize range routing; cost remains too high

[verified] Selecting input, feedback and add/replace behavior outside the per-sample loop preserves all 100,000 randomized blocks / 809,531 ranges in normal and sanitizer runs, plus all 11,290,624 mixed PCM bytes. Native range functions remain in SRAM; the application ends at 0x8fffc within the same 140 sectors.

[verified] One application flash/reset passes arithmetic, exact mixed PCM/control, 24 region records, 22,052 zero-error queue jobs, bounded first spans and finite exit. Means are 1572.500 / 1638.500 / 1682.208 / 1857.333 us, with 4727 / 5513 / 5513 / 5513 late blocks. The heavy case recovers only 9.042 us versus V76 and remains 149.750 us slower than V75. Heap is stable at 69,652 bytes, unused parent stack is 2,508 bytes and worker stack 7,456 bytes. This also fails the native range-cost gate; no scheduler or optimization is promoted.

[verified limit] Source identity and exact PCM do not prove safe yielding across note retriggers or asynchronous feedback-state import. Existing msfa pure-loop preparation does not annotate these replacement range loops; its relevance to cost is a follow-up question, not a measured explanation. Astra has the new measurements for a focused source review of substantial work reduction or an earlier legal frontier. No further hardware operation is live; the board acknowledges ordinary PING. Both unique reset attempts are consumed. No backup/readback/restore rehearsal, physical FM1 traffic or Hera contact occurred.


### Astra follow-up: prepare native state once; measure invariant validation

[verified source review] Astra's completed private report recommends preparing thresholds, routing, original gain slopes and working phase/gain once per native 64-frame block, advancing fixed eight-frame chunks and committing only at the end. This removes repeated setup from V77; any speed benefit remains unmeasured. A future asynchronous continuation still needs retrigger/voice-steal ownership proof before importing phase or feedback.

[verified placement] The generated arena/type/alias validator runs after queue Begin stamps the recording timer, before first sound-command readiness. V78 measures this function intact, with per-case call count and tick sum/min/max; all checks remain present. If the cost is under 5 us, stop this candidate. A material cost could justify sealing geometry after setup and invalidating/revalidating on every actual replacement, while retaining runtime identity/model and queue lifecycle guards. A 21-us saving here would reduce both work and startup and merely erase V75's theoretical mean deficit, without practical margin. That is an arithmetic threshold, not a measured or promised saving.


### V78: repeated layout validation costs about 14.5 us

[verified] The intact validator takes 14.501 / 14.387 / 14.470 / 14.502 us mean across four cases, each with 5,513 calls. Minimum is 284 ticks (11.833 us); maxima are 1,682 / 1,431 / 1,467 / 1,211 ticks and include interrupt exposure. The observer adds two clock calls and counters; this is a measured region, not an optimization result. The original unsplit FM kernels are restored in this candidate.

[verified] Strict arithmetic, exact mixed PCM/control, 24 outer records, 22,052 zero-error jobs, bounded first spans and finite exit all pass. Total means are 1576.000 / 1640.625 / 1644.250 / 1713.000 us; late counts 4725 / 5513 / 5513 / 5513 still fail the unchanged deadline. Heap is stable at 71,156 bytes, parent unused stack 2,508 bytes and worker 7,456 bytes. Board is healthy idle with ordinary PING ACK after closing the owned receiver. Raw SHA cfa06a74c80f683293e1076e7a68e18c67af42afe660414ddbf9fe829be86a1d; private artifacts are in renderer-layout-observer-v78-exports, mirrored to Aeon.

[inferred bound] Even removing the entire 14.502-us heavy validator cost from both work and startup would erase only 29.003 of V75's 41.773 core-us deficit, leaving about 12.769 core-us before synchronization or tail margin. Retained runtime guards would reduce the actual saving. The next source experiment can seal invariant arena geometry after setup, revalidate on every engine/arena/type mutation and retain runtime identity/model/queue checks; first prove malformed/replaced layouts refuse before publication. This is not permission to skip ownership checks globally. Native prepared-state range work remains a separate required cost/proof gate; neither a pipeline nor final audio acceptance is established.


### V79: exact layout seal saves roughly 9–12 us; deadline still fails

[verified] The guarded diagnostic preparer retains full type/arena/alias validation and caches its result only while app identity and every live unit's engine, instance, storage, used size and capacity remain identical. Macro model refusal stays live every block. Geometry mismatch invalidates the seal before full revalidation. Added mutation fixtures exercise an unselected master alias, app switch and unused-tail overlap; existing replacement/unsupported/overflow/NULL/refusal tests remain. Three normal PCM modes and sanitizer caller-post pass, including 11,290,624 exact PCM bytes per full run. Private early-frontier proof expects the exact seventh Macro command; standard tracked-source peak-six assertion is unchanged.

[verified] Native build and single application flash/run completed. Four arithmetic and mixed PCM/control cases,24 outer regions,22,052 zero-error queue jobs, bounded first spans1..8 and finite exit pass. Means1561.083/1625.500/1629.458/1698.250us improve10.000/11.125/12.458/9.333us versus V75 with the same observers. First-command readiness also improves; this remains a single-run comparison. Late4722/5513/5513/5513 still FAIL34829 ticks. Heap70,900 stable; parent unused2,508 and worker7,456 bytes. Raw2dea30392257390a1f03c4faecf5418bb22f42ebe74869fc93c6573a5035ce3a; private renderer-layout-seal-v79-exports mirrored to Aeon. Board ordinaryPINGACK after closing owned RX; no backups/readbacks/restores/buttons/FM1/Hera.

[inferred next step] This bounded saving is retained but cannot close the remaining gap. The next useful prototype is Astra's prepared 64-frame native FM block with fixed eight-frame advances: compute thresholds/routes/slopes once, maintain working phase/gain/feedback and commit once. Do not reuse stateless V76/V77 range loops as a pipeline prerequisite: their native regressions remain rejected. Exact randomized prefix/state/refusal and full PCM proofs precede native timing; asynchronous retrigger/import ownership is still unproven.


### V80 rejected: prepare-once FM chunks still regress on the target

[verified] A private prepared native-block job computes thresholds, routing and original 64-frame gain slopes once, carries working phase/gain/feedback across fixed-eight advances, and commits engine state at frame64. The synchronous prototype retains fused algorithm-five pairs and paired sine preparation. Normal and ASan/UBSan proofs pass100,000 randomized blocks/809,531 partitions, emitted prefixes/untouched suffixes, working state, gain endpoints, no premature external-state writes and invalid-step refusal. Normal and sanitizer full mixed renders match11,290,624 PCM bytes. These proofs do not establish event-interleaved continuation ownership.

[verified] Native hot functions reside in SRAM. The574,428-byte application ends0x904fc; the previous140-sector boundary blocked generation, then an explicit141-sector application range[0x4000,0x91000) was used, with boot/protected prefix and suffix preserved. This extension must be accounted for in subsequent iterations, including a shorter-image replacement. No full backup/readback/restore rehearsal occurred. The board completes all arithmetic/PCM/control/queue/first-span checks and ordinaryPING after owned RX closure.

[verified rejection] Means1563.458/1628.958/1674.875/1851.792us regress2.375/3.458/45.417/153.542us versus V79. Late4723/5513/5513/5513 all fail. Heap68,276 stable; parent unused2,508 and worker7,456 bytes. Raw ae7c5a6ee20acff685eb6dd63191f91d3b9ca323a55ddb6b8e60f14c6235f334. Full facts/candidate/plan/comparison/validation are private renderer-prepared-v80-exports, mirrored to Aeon. The prototype exceeds the40-us regression stop criterion and is NOT promoted; no more minor unroll variants are justified on this path. Repeated preparation was not sufficient to explain or recover the prior range regression. Existing owner-requested Astra reviewer is evaluating original full-block alternatives with actual serial master-tail and startup constraints. All deadlines and analog acceptance remain unfinished.


### V81: exact mono Drive removes about 74 us of worker work

[verified] Drive now computes one channel only when all six channel state fields and every input L/R pair are bit-identical. Signed zero is compared by bits; structure padding is excluded. The original sample arithmetic, control glides and crossfades remain. Unequal history or input retains stereo processing. Normal and ASan/UBSan comparisons cover 200,000 calls / 12,883,893 frames with complete state and output equality, varied rates/partitions/parameters, stereo history, signed zero, denormals and guarded nonfinite input. Full mixed renders preserve all 11,290,624 PCM bytes. A permanent independent-channel oracle compares mono processing against the left channel of deliberately stereo input for 10,000 calls. All 83 Drive regression tests pass on bounded Aeon; the first attempt lacked g++, corrected by selecting the installed clang toolchain.

[verified] The single application flash/run passes arithmetic, mixed PCM/control, 24 regions, 22,052 zero-error jobs, first spans1..8 and finite exit. Means1489.917/1550.542/1570.000/1690.333us improve71.167/74.958/59.458/7.917us versus V79. Worker occupied time improves74.125/74.125/74.208/74.375us. Late3952/5135/5474/5511 of5513 still FAIL34829ticks. Heap70,644 stable; parent unused2,508 and worker7,456 bytes. Raw2554765ae93bd46d2c4ccb36970f2b3cbf9c55c6e843a38f4efa35e7e0a44b9a; private renderer-drive-mono-v81-exports contains candidate/facts/comparison/raw, mirrored to Aeon. The shorter image ends0x8fbdc; application writer still replaced141sectors to clear V80's extra sector. Board ordinaryPINGACK after owned RX termination. No routine backups/readbacks/restores/buttons/FM1/Hera.

[inferred limit] This is useful work reduction, not deadline acceptance: CPU0 dominates the heavy case, so nearly74us worker savings yield only8us elapsed gain there. Astra's reviewed bounds reject early Macro streaming alone and whole-voice redistribution with the unchanged serial master tail as sufficient fixes. Next work must reduce/move CPU0 work and account for final master dependencies. Original full-block FM kernels are retained; V80 chunks remain rejected. Actual deadline tails, DAC/KA6 fault validation and 30-minute analog soaks remain unfinished.


### V82 rejected: constant-gain mixing did not improve native timing

[verified] A private MixVoice shortcut skips the gain-ramp expression only when both endpoints are equal; the original changing-gain loop remains. One million randomized mixing blocks and the full11,290,624-byte mixed render match in normal and ASan/UBSan runs. Native means1493.250/1553.250/1572.750/1692.375us regress3.333/2.708/2.750/2.042us versus V81. Late4038/5223/5479/5512 of5513 still fail the34829-tick deadline. All arithmetic/PCM/control/queue/first-span/finite-exit checks pass. The shortcut is rejected and remains private. Board responds to ordinaryPING after owned RX closure; no repeated backups/readbacks/restores occurred. Raw1102335b8ffc728d11f125dab2c5a56e589f53afd9bf1efa4971a0e4247fd117 and private renderer-mix-gain-v82-exports are retained.

[reported: owner,2026-10-26] Claude recovered the actual FM-1: it now boots stock firmware. Actual-unit testing is possible when useful. This task has not independently verified the stock boot or sent device traffic. Inspect the recovery handoff before firmware-changing tests.


### V83 rejected: shared resampler weights move the bottleneck

[verified] A private immutable phase plan shares stage-one resampler weights between Macro on CPU1 and Drums on CPU0, retaining separate histories, original accumulation order and guarded fallback. Normal and ASan/UBSan randomized resampler state/output and full threaded mixed PCM/fault tests pass. The 5,136-byte plan resides in static SRAM. These checks do not establish target race/cache/ABI proof.

[verified] Native means1548.042/1612.792/1615.667/1678.292us change by+58.125/+62.250/+45.667/-12.042us against retained V81. Late4718/5513/5513/5513 of5513 still fail34829ticks. Arithmetic, PCM/control,24regions,22,052 zero-error jobs, first spans1..8 and finite exit pass. Heap64,948 stable; unused parent2,508 and worker7,492 bytes. The prototype is rejected: worker preparation/consumption overhead outweighs caller savings in three cases, and the heavy saving does not close the deadline. No tracked implementation promoted. Raw7cc7651fb76cb3f522ae4a1d4af1c1a9852d2763d89586c6094caf6594a5e4ff; private renderer-resampler-plan-shared-v83-exports retains facts/comparison/raw. RX44357 PID595818 was twice exact-argv checked, sent one SIGTERM, terminal255 and PID absent before ordinaryPINGACK. Reset iteration-resampler-plan-shared-v83b-20261026 is consumed; never retry. Board healthy idle. No physical FM-1 traffic.


### V84 rejected: conservative compressor floor shortcut has no native gain

[verified] A private compressor shortcut bypasses only the logarithm and curve when a conservative exponent bound proves the original curve returns zero and current Auto Gain is off. Detector, smoothing, release, handover and output gain remain unchanged. Complete state/output comparisons cover 2,970,528 frames / 40,000 calls / 416 aliases in normal and ASan/UBSan builds, exhaustive mantissas at five exponents, and all 11,290,624 mixed PCM bytes. Despite a 52.92% host eligibility rate, target means1488.583/1552.292/1572.292/1693.042us change by-1.333/+1.750/+2.292/+2.708us versus retained V81. The shortcut is rejected and remains private. All arithmetic/PCM/control/queue/frontier checks pass, but late3937/5201/5469/5509 of5513 still fail the34829-tick deadline. Heap70,580 stable; unused parent2,508 and worker7,456 bytes.

[verified] Raw e9f7df473229e53d1c80387513455a95cec16219b0bcdf0c40f345079dc466a7 and candidate/facts/comparison are private renderer-comp-floor-v84-exports. RX21687 PID599888 was checked twice against exact argv, sent one SIGTERM, terminal255 and absent before ordinaryPINGACK. Application-only iteration; no backup/readback/restore rehearsal. Reset iteration-comp-floor-v84-20261026 is consumed and must never be retried. Board healthy idle on the rejected V84 diagnostic.

[inferred from measured bounds] Astra's review finds that moving the unchanged Macro/Drive plus serial master tail to CPU1 still needs at least1482.548us even with early first-command publication, before stalls and queue overhead. This exceeds1451.208us; the no-gain compressor trial does not make that schedule viable. Further work must remove actual CPU0/serial work rather than assuming overlap closes the gap. Physical output and sustained acceptance remain unfinished.


### V85 rejected: register-only four-operator fusion does not recover CPU0 time

[verified] A private algorithm-one kernel fuses operators0..3 without the intermediate64-sample bus, keeps the independent pair4..5 and original full64-frame calls, and refuses before mutation when the fully-active guard fails. Normal and ASan/UBSan differential proofs each pass100,000 randomized blocks with complete samples/phases/gains/feedback equality and16,906 untouched fallbacks. Both full mixed renders preserve11,290,624PCMbytes. Native RunVoiceKernel in SRAM inlines the new path with108-byte local stack allocation plus saved registers, versus284bytes for rejected V54's buffer-based version. This is not whole-stack or ABI proof.

[verified] Target means1489.833/1550.583/1571.042/1695.833us change by-0.083/+0.042/+1.042/+5.500us versus retained V81. Late3953/5135/5478/5510 of5513 still fail34829ticks. All arithmetic/PCM/control/24region/22052queue-job/first-span/finite-exit checks pass. Heap70,324 stable; unused parent2,508 and worker7,456bytes. The experiment is rejected, with no tracked implementation promoted. Raw8c9c03b6c22aa0a77856a0e25b0ecda9522e80f46de1b14c4aef381548dcbbaf and private renderer-fm-chain-register-v85-exports retain candidate/facts/comparison. RX30559 PID601875 was twice exact-argv checked, sent one SIGTERM, terminal255 and PID absent before ordinaryPINGACK. Reset iteration-fm-chain-register-v85-20261026 is consumed: never retry. No repeated backups/readbacks/restores.

[verified harness correction] The first whole-render proof failed to link because copied diagnostic renderer_live referenced a removed frontier observer. Restoring all three clean observer source files resolved the mismatch; both complete PCM proofs then passed. No failed-build candidate was installed.


### V86: current finalization observer leaves only narrow pipeline margin

[verified] Observer-only V86 wraps the unchanged UI epilogue with two native clock reads and counts blocks without a due ARP hold, popup commit, picker, snap/toast/follow/capture/step-record action. It changes no DSP, control boundary or epilogue ordering. All5513 blocks per case meet this preliminary predicate. Inclusive mean UI costs42.450/42.186/42.307/42.535us; maxima132.458/90.750/73.833/86.000us. These are upper bounds on removable work, not proof of independent ownership; fm1_edit_block_end remains included, and observer call/placement overhead has not been calibrated. Observer-image total means1500.417/1560.833/1581.542/1702.375us are roughly10–12us above retained V81, so they must not be treated as clean performance comparisons.

[verified] Strict arithmetic/PCM/control/24region/22052queue-job/frontier/finite-exit checks pass. Late4336/5481/5497/5513 of5513 still fail34829ticks. Heap70,292 stable. Candidate0b996ddf1c33394e78ef9efb7b77e33491718610e4119d69cde85b6238e655c1, raw1760daacbd9028c897020284c25f0c18dadae341321746d63d464dd947268896; private renderer-ui-eligibility-v86-exports includes raw/facts/UI counters. RX48527 PID604127 was twice exact-argv checked, sent one SIGTERM, terminal255 and absent before ordinaryPINGACK. Reset iteration-ui-eligibility-v86-20261026 is consumed, never retry. Application-only iteration; no repeated backup/readback/restore cycle. Board healthy idle.

[inferred] Astra's completed source review says moving genuinely independent UI work to CPU0 could make the early Macro/master pipeline algebraically possible, but its required reduction exceeds31.340us before overhead. V86's whole-UI upper bound leaves only about11us ideal mean margin. Next separate observer overhead and output-dependent meter finalization; prove extraction at the original boundary and action-hazard coverage before any reorder. Prefix readiness/finish costs must be measured, never caller/8 or post/8. Current predicate is not a general concurrency guard: synchronization may generate actions and modulation plans can rebuild when dirty. Exact PCM, lifetime, event/control ordering and actual deadline tails remain mandatory. No scheduler implementation or acceptance is claimed.


### V87: current UI cost is sequencer synchronization and LEDs

[verified] V86 final ELF has no separate lunar_ui_probe symbols: LTO inlined the observer into SRAM fm1_app_render. An XIP helper-call explanation for its overhead is unsupported. app_init clears the app through its TFT member and the devkit renderer never attaches an editor; V87 runtime confirms editor attachment count0 for all22,052 blocks.

[verified] Private observer-only V87 preserves the original epilogue ordering and divides it into poll/popup, modulation-plan snapshot, sequencer sync/lock, LEDs and editor-finalizer intervals. Across four cases their means are respectively1.424..1.453us,1.289..1.295us,29.632..29.728us,10.064..10.373us,0.347..0.364us. The last interval is instrumentation and a null-editor branch, not active editor finalization. Timestamp/accounting overhead is included; these are not clean optimization gains or general independence proof. Current sequencer sync+LED work is about40us, leaving narrow ideal mean margin in Astra's proposed early Macro/master schedule before new scheduling, prefix stalls and action fallbacks. No reorder implemented.

[verified] Strict target arithmetic4, PCM/control4,24outerregions,22,052 zero-error queue jobs,first spans1..8 and finite exit pass. Means1497.792/1557.667/1583.292/1710.208us; late4174/5369/5500/5512 of5513 still fail34829ticks. Heap70,516 stable; unused parent2,508/worker7,456bytes. Candidate481b0c731bc5da50d178f0ee5aba41fbc7556896b8e004e922b231be6500d334; rawb24b7a520dd1c70fa25bd85c485e871d18ee0e91dad7744ed175af49ddbcf6c4. Local/Aeon renderer-ui-detail-v87-exports preserves raw and both strict target/detail facts. Application-only install and one reset; no repeated backups, readbacks or restores. RX75054 PID606285 closed with two exact argv checks, one SIGTERM, terminal255/PID absent before ordinary PING ACK. Reset iteration-ui-detail-v87-20261026 consumed, never retry. Retained firmware615c9b12 unchanged.

[verified source, not measured attribution] fm1_seq_ui_sync snapshots the entire UI state, queries selected track/clip twice through read_track plus its later step update, and refreshes session tracks every block. These are candidates for exact-state work elimination; their individual cost has not been measured. Do not skip functional sync at visual cadence. Existing owner-requested Astra review continues on the minimal immutable post context and concrete first host-proof step, in scratch/devkit-20261023/astra-ui-master-pipeline-v87-next.md. No target deadline, analog or soak acceptance.


### V88/V89: exact serial master-prefix boundary proof

[verified] A private immutable block view extracts the shared-master/output tail at its original position, with explicit mutable effect/ramp/click/limiter/scope destinations and sealed control/event inputs. Whole-block execution and then 1-frame, 8-frame and irregular prefixes preserve all11,290,624 mixed PCM bytes in normal and ASan/UBSan runs. Each comparison directly streams3,116,257,306 bytes of per-block UI/control/scope/ramp/click/limiter/unit values/driven and complete Echo/Comp instance state, without saving multi-gigabyte traces. A second fixture injects writes and clicks at frames0/8/63/64, tied writes, changing DRIVEN and gain; all six prefix/sanitizer combinations match their identically modified serial baseline. This covers the fixed eight-case fixture and compared state, not arbitrary engine layouts or whole-application concurrency.

[inferred next experiment] Native eight-frame prefix overhead must be measured before a pipeline is justified: the projected ideal mean margin is only about9us. No scheduling/UI reorder, new concurrency implementation or performance gain is claimed from these host proofs. Private scripts and results remain in scratch/devkit-20261023 and bounded Aeon exports.


### V89 native result: eight-frame master prefixes add too much overhead

[verified] The serial eight-frame prefix prototype passes target arithmetic, all four PCM/control cases,24 regions,22,052 zero-error jobs, first spans1..8 and finite exit. Means1521.375/1581.583/1601.000/1722.042us regress31.458/31.042/31.000/31.708us versus V81. Late4478/5513/5513/5513 of5513 still fail34829ticks. CPU0 post work rises to352.958/353.000/353.042/354.458us; the heavy-case increase27.042us exceeds the roughly9us ideal margin previously estimated for the proposed pipeline. This measures serial adapter/segmentation cost, not concurrent speedup. Further pipeline implementation needs a concrete way to reduce that cost plus measured prefix readiness; no source promotion.

[verified] Heap68,852 stable; unused parent2,508/worker7,456bytes. Raw56642a72974359415bad7f2da9055c48559256167fab5b9751e625fdcf152279 and candidate/facts/comparison are retained privately in renderer-post-prefix-v89-exports, mirrored to Aeon. One application flash and reset, no backup/readback/restore cycle. RX17125 PID611556 was checked twice against exact argv, sent one SIGTERM, terminal255/PID absent before ordinaryPINGACK. Reset iteration-post-prefix-v89-20261026 consumed, never retry. Board healthy idle; physical output/soak acceptance unfinished.


### V90: one-prefix control isolates adapter cost

[verified] The same private V89 adapter with one advance64 preserves the complete compared state stream and mixed PCM in normal/ASanUBSan. Native means1496.708/1557.250/1575.542/1696.208us; post328.292/328.750/327.667/329.417us, near V81's original tail. This separates the small wholeblock adapter floor from most of V89's repeated-prefix overhead; it does not prove a concurrent schedule. Late4094/5305/5492/5510 of5513 still fail34829ticks. Strict arithmetic/PCM/control/regions/queue/frontier/finite exit pass, heap68,852 stable, parent unused2,508/worker7,456bytes.

[verified] Native V89 disassembly retains calls at SRAM01c0487c/048d4 into generic fm1_fx_render in XIP0201b24a. Echo/Comp have no render_ext and that wrapper immediately calls engine.render; direct non-ext dispatch is therefore a concrete bounded follow-up, not an assumed compiler improvement. Capture belongs on CPU0 in a future pipeline, so V89's aggregate27us post increase is not a strict CPU1-only bound. Actual prefix readiness/tail and future ownership remain unproved. V90 raw86ab223b02b8c3d57e35e1d6d7e927f903a75b40c264df8d774952df71210779 retained locally/Aeon. One app flash/reset; exact RX closed before ordinaryPINGACK, reset consumed and never retried.


### V91: direct non-extension dispatch recovers only part of prefix overhead

[verified] Private eight-frame adapter calls engine.render directly when render_ext is null, retaining the existing generic extension fallback. It changes no DSP kernel, setters or cursor order. Full mixed PCM and3,116,257,306-byte compared state streams match in normal/ASanUBSan. The actual fixture uses Echo/Comp without render_ext; the extension fallback was not exercised by that fixture. Native means1515.792/1575.708/1595.250/1716.333us improve5.6..5.9us versus V89; post347.125/347.292/347.333/348.875us remains about20us above V90 wholeblock. All arithmetic/PCM/control/regions/22,052 jobs/frontier/finite-exit gates pass, but late4462/5513/5513/5513 still FAIL34829ticks. No concurrency or source promotion.

[verified] Heap68,724 stable; unused parent2,508/worker7,456bytes. Raw44a3c93ad965414902570afca2d46e1d679b07828235e7dca61a3018b3527fa8 and private renderer-post-direct-v91-exports retain evidence locally/Aeon. One application flash/reset, no backup/readback/restore cycle. RX80183 PID613232 twice argv checked, one SIGTERM, terminal255/PID absent before ordinaryPINGACK. Reset iteration-post-direct-v91-20261026 consumed, never retry. Next dependency is exact producer readiness/coalescing evidence and per-sound ownership, not assuming eight equal pieces or claiming host equivalence establishes a concurrent schedule.

### V92: serial caller reorder and Drums readiness cursor

[verified] Astra's returned review (`scratch/devkit-20261023/astra-post-readiness-v91-next.md`) recommends retaining the current Macro publication/ACK barrier and full FM kernels, executing caller sounds 0,3,2, and observing caller prefixes only after the Drums level cursor completes. A private preparer implements that schedule without moving ordered summation or shared masters. It validates contiguous Drums output coverage against mix[2] before publication, requires exactly 64 frames, empty Drums inserts and no attached editor, drains terminal commands and commits final level once. This is a serial experiment, not a concurrent implementation.

[verified] Full 11,290,624-byte PCM replay passes normally and with ASan/UBSan. The stronger comparison also directly matches 3,470,147,802 streamed bytes of UI/control/shared-effect state and Drums voices, voicing values with pointer normalization, pads/RNG/ramps, native pending/mix buffers and complete resampler state, normally and with ASan/UBSan. A separate normal replay injects level writes at 0/8/8/63/64/80, including same-frame ties and whole-block clamping, and matches the same state/PCM. Sanitized boundary replay and the native observer build are pending at this checkpoint. Initial harness failures were a stale observer dependency and an obsolete expected Macro queue peak (6 versus the retained source's 7); neither was a firmware result.

[inferred] Correlated per-block producer readiness will determine whether coalescing can fit useful work under the deadline. The observer records complete FM0/FM3 post completion, eight Drums output/level endpoints, worker start/end and application/outer completion from the same block. It retains bounded startup/steady/tail samples and all-block maxima; UART reporting is outside timed rendering. It does not move the shared post capture or prove a concurrent schedule, and its observer overhead is not a speedup. No V92 candidate has been installed; V91 remains healthy idle. Runtime deadline and analog acceptance remain incomplete.

### V93: actual caller readiness exposes another serial limit

[verified] The first V92 native run completed strict PCM/arithmetic/control/queue checks, but its new observer collected zero records because it was placed behind LUNAR_RENDERER_PROFILE, disabled by the outer-only build. Its case4 reporting also read beyond a four-case array. V93 moves collection into the active renderer_timing loop after the sampled outer end, guards case4, and emits each record in one formatted print. No DSP change or relaxation; this corrects the experiment rather than accepting missing data.

[verified] V93 completes 72 correlated records (18 selected blocks/case), 5,513 observer calls per case, monotonic prefix timestamps and worker/total bounds. All four arithmetic/PCM/control cases, 24 outer regions, 22,052 zero-error jobs and finite exit pass. Means1506.958/1566.667/1594.667/1724.750us and late4393/5490/5513/5513 still fail34829ticks. Heap63,604 stable; unused parent2,484 and worker7,456bytes. The bounded observer changes timing and is not a speedup claim. Board healthy idle ordinaryPINGACK after exact RX50462/PID617992 shutdown; unique V92/V93 resets are consumed and must never be retried. Routine app-only flashes used no backups/readbacks/restores.

[verified] In the heaviest case, caller output through frame64 is already later than the deadline in12/18 selected rows, before shared masters: block512 ready1482.042us, block4096 ready1484.125us. The selected rows emphasize startup and control boundaries and are not an unbiased frequency estimate. They nevertheless prove early Macro completion alone cannot fix those actual blocks. Full FM kernels and original ordered sum/ACK remain unchanged. No asynchronous rewrite is admitted on optimistic mean bounds. Shared post capture remains unmoved and must not be treated as free.

[verified] Evidence remains private in renderer-producer-v93-exports (raw, target-facts, producer-facts); parser validates every correlated row and call count. Existing owner-requested Astra review is continuing with the actual source/readiness data to identify the next caller-critical-path experiment before any concurrent redesign. Host scheduling proof matches3,470,147,802statebytes/11,290,624PCMbytes normally and sanitized, including level boundaries0/8/8/63/64/80; four malformed coverage cases refuse before publication. No production firmware change, deadline acceptance or analog acceptance is claimed.


### V95: guarded mono Ladder is exact but the first target gain is small

[verified] Astra found that the mixed fixture defaults to Ladder, whereas the retained Filter shortcut covered SVF. A private Ladder path compares both inputs, G/G4 coefficients and all five history floats bit-for-bit, then runs the unchanged first channel and copies next state/output; every mismatch retains stereo. Complete Filter state/output matches through 250,000 direct frames covering all guard mismatches, signed zero and nonfinite inputs, plus 200,000 full calls/12,906,495 frames, normally and with ASan/UBSan. The complete 11,290,624-byte mixed PCM/44,104-batch replay also passes normally and sanitized.

[verified] Native original fullblock V81 scheduling plus this single DSP change produces means1492.667/1553.042/1568.833/1683.750us, late4041/5179/5472/5511 of5513, all FAIL34829ticks. The heavy mean improves6.583us versus V81, while the two lightest means regress about2.5us; this is not a sustained gain or acceptance. Caller cost falls roughly9.6us, mostly becoming extra wait in lighter cases. Heap70,388 stable; parent unused2,508/worker7,456bytes. Arithmetic4/PCMcontrol4/24regions/22052 zero-error jobs/frontier/finite exit pass. No tracked DSP promotion. Next bounded hypothesis is hoisting the mono eligibility proof to an entire stable Ladder block to remove repeated history checks; its control/type/state invariants require review and full equivalence.

[verified] Existing V81 correlated worst-total-block regions0+1+2 sum34676/35010/38845/45075ticks. Thus unfragmented caller completion already exceeds the deadline in cases1/2/3; another profiling image proving that fact is redundant. Astra corrected its recommendation. A finite cross-block FIFO remains an unimplemented alternative requiring deep immutable metadata, control/telemetry ownership proof and correlated capacity evidence. Summary means cannot establish sustainable occupancy.

[verified] V95 candidate3e29172206016bfffab027701430ac04777d5fcc405225c2832d97de102539f7 is healthy idle with ordinary PING ACK after one application flash/reset and exact owned RX shutdown. Unique iteration-ladder-mono-v95-20261026 reset is consumed; never retry. Raw16bc5842 and full facts remain private in renderer-ladder-mono-v95-exports. No backups/readbacks/restores/buttons/Hera/physical-FM1 traffic. Deadline, physical-output fault validation and thirty-minute soaks remain incomplete.

### V96: block-level Ladder mono guard rejected (2026-10-26)

[verified] Hoisting the guarded Ladder mono eligibility check to each actual FilterRender call preserved complete initialized state and output across 200,000 calls / 12,906,495 frames, 6,048 targeted invariant cases, and 11,290,624 mixed PCM bytes / 44,104 batches, with normal and address/undefined sanitizer runs. The guard is local, follows priming, requires stable Ladder with zero Morph, equal coefficients/history and bit-identical full-call input; fallback keeps the original stereo implementation.

[verified] Native means were 1503.458 / 1563.500 / 1578.625 / 1694.833 us; late blocks 4361 / 5470 / 5484 / 5512 of 5513 per case. All four regress versus V81 and fail the unchanged 1451.208333 us deadline. Strict arithmetic, PCM/control, all 22,052 queue jobs and finite exit pass; heap 70,260 bytes stable, unused parent/worker stack 2508/7456 bytes. The candidate remains private and is not promoted. RX was closed before ordinary PING ACK; board healthy idle.

[inferred] The eligibility scan and changed native code layout outweigh this duplicate-channel arithmetic saving. This is a rejected experiment, not progress toward acceptance. Next investigate bounded inter-block scheduling with exact per-block metadata/storage and logical control-state ownership; average throughput alone cannot prove queue capacity or deadline compliance. Private evidence: scratch/devkit-20261023/renderer-ladder-block-v96-exports/.

### V97: exact two-slot shared-tail scheduling proof (2026-10-26)

[verified] A private host-only prototype keeps sound rendering synchronous, seals the ordered mixed PCM and deep copies each block's used automation/event logs, clock, gain and effect decisions. It advances the original UI/control epilogue, produces the next block, then consumes the preceding block's shared effects/output tail. Effect, ramp, click, limiter and scope histories remain continuous on the consumer. Output remains owned through an explicit OUTPUT_READY-to-retire step. This is a serial ownership proof, not a concurrent or native implementation.

[verified] Across 44,104 blocks, the original mixed workload and an extended fixture with master-effect/AMP modulation, metronome changes and master-gain changes retain exact floating PCM. The strengthened extended fixture compares 22,581,248 PCM bytes, 2,855,800,840 producer-state bytes (including complete sequencer/modulation arenas) and 3,002,247,488 consumer-state bytes, directly byte for byte in normal and ASan/UBSan runs. Reusable producer metadata is deliberately poisoned during deferred consumption. Reusing a sealed slot, consuming twice, or reusing OUTPUT_READY storage before retirement is rejected in both builds. Private scripts, logs and compact receipts are saved under scratch/devkit-20261023/two-slot-tail-v97*.

[verified] This does not defer Macro or prove queue depth, real-time throughput, target RAM/cache/race behavior, output latency, interactive event admission or hardware acceptance. The fixed fixture does not issue a direct master-engine setter while older output is pending; those setters and reset/replacement paths need an ordered command or drained-state boundary. Editor-dependent telemetry remains excluded. Astra's source audit is private at scratch/devkit-20261023/astra-two-slot-prototype-v97.md. Next extend the serial model to immutable Macro commands and per-sound PCM, commit level carry on the producer, then execute Macro/Drive and ordered mixing on the consumer before considering target integration.

### V98: deferred Macro/Drive and shared tail preserve serial semantics

[verified] A private host-only prototype extends V97 by recording the original per-engine commands, rebasing output into slot-owned buffers, executing caller sounds 0/2/3 synchronously, and deferring Macro model0/Drive/level plus the original ascending track sum and shared tail. Producer commits the final level carry while sealing; deferred PCM scaling cannot overwrite a later knob change. No DSP kernel or native scheduler is changed.

[verified] Normal and ASan/UBSan replay compare directly byte for byte across 44,104 blocks: 22,581,248 float PCM bytes, 2,855,800,840 producer-state bytes and 4,456,973,824 augmented consumer-state bytes. The latter adds full Macro model0 state with known host engine/vtable pointers normalized, and Drive state. Metadata poisoning and the existing three storage misuse checks pass. Seven level-boundary/carry cases and seven malformed-command/control-mutation cases pass normally and sanitized; refusal logs identify the intended precondition. The first focused harness leaked its early-exit test slots; cleanup was corrected and the sanitizer test then passed without disabling leak detection.

[verified] Host slot size is 23,792 bytes, with 12,384 bytes of shared recorder scratch. This is not native ABI/RAM-fit proof. Consumer-owned direct setters/notes are asserted against while pending; this is a fixed-fixture admission boundary, not a generic interactive dispatcher. Caller DSP state is not newly serialized. No concurrency, target speed, bounded occupancy, race/cache, physical output or sustained acceptance is claimed. Private scripts/receipts: scratch/devkit-20261023/two-slot-macro-v98*, with Astra's implementation handoff beside them. Next obtain a minimal native scheduling/storage plan and all-block correlated producer/consumer service evidence; optimistic means cannot establish a sustainable FIFO.


### V99: threaded native adapter equivalence and CI contract corrections

[verified] The private two-work-slot/eight-output-slot backend passes 11 ownership/failure modes normally and with ASan/UBSan, including 2,000 tagged jobs, output backpressure, held output leases and permanent refusal after timeout. The actual threaded DSP adapter matches the original renderer/converter across 22,052 blocks and all four cases: 5,645,312 stereo int16 PCM bytes, SHA256 ead722bab2f5fff43cc5959f258d1418defd7cdd197f8aefc9156bcf5329c6d3. Both normal and sanitizer runs preserve 746 controls and final hash5b7dbc03. Native final vendor build links successfully; RAM fit at runtime, real service times and continuous output remain unproved. No new image installed. This is a private fixed-workload prototype, not a production interactive dispatcher.

[verified] Exact-head CI40418860856 failed two stale contracts: the metadata example retained the old LFO arena size112 instead of actual120, and the screenshot test required at least10Hz despite the requested quarter-rate display producing7Hz. The example is regenerated from a real default full-engine exporter, with its canonical comparison passing; the container lacks jsonschema, so the complete Python test is left to CI. Chromium's complete screenshot regression passes with a5..10Hz visualization bound. Audio underrun gates are unchanged; Pages40418860828 succeeded.


[verified] V99 native finite screen completes all22,052 blocks with four exact PCM hashes, expected746 controls, no queue faults and7,312 bytes unused worker stack. Producer means1037.750/1202.208/1303.917/1454.500us; consumer1268.792/1335.167/1335.375/1335.792us. Producer over-budget blocks1/5/49/2734; consumer zero. All nine optimistic buffer models fail; eight-output/eight-block-latency has5376 misses. It is segmented every16 blocks and excludes protocol/IRQ/copy overhead in its model, so it is not continuous or DAC acceptance. The heaviest producer still exceeds the original1451.208us mean budget. Board healthy idle ordinaryPINGACK; no backup/readback/restore cycle.

[inferred] Resetting recorder counts instead of clearing unused command capacity, and copying only used immutable Macro commands, can remove CPU0 memory traffic without changing DSP or command order. Private V100 threaded equivalence and native builds are running; no gain or acceptance claimed.


### V100: remove unused recorder traffic; service capacity still fails

[verified] Resetting only stream counts and copying only used Macro commands preserves all5,645,312 stereo int16 PCM bytes in the actual threaded adapter normally and with ASan/UBSan. Native producer means1021.083/1186.708/1288.833/1440.250us, consumer1267.458/1333.625/1334.000/1334.417us. The heaviest producer average is below budget, but8-output/8-block-latency optimistic scheduling still misses669 blocks, max lateness64480ticks. All four PCM/control cases,22052 jobs and finite exit pass; worker unused7312bytes. Board healthy idle ordinaryPINGACK after one application flash/reset and exact RX shutdown. This is not paced or analog acceptance.

[verified] The V101 combination with previously proven per-frame guarded mono Ladder passes full threaded PCM equivalence normally and sanitized, and links natively, but exceeds the current application's0x91000 end boundary. Candidate generation refused before producing an image; nothing flashed. Astra identified a separate CPU0 cost: V98's sealed-layout check still falls through to repeated descriptor and pairwise arena proofs. V102 will keep full initial admission and all-five-field geometry comparisons on every subsequent block, plus live slot/model/UI guards. Its equivalence and mutation-refusal checks are pending; no performance gain claimed.

## V102: sealed admission reaches the first zero-miss pipeline screen

[verified: target UART and strict parser] Moving immutable descriptor and pairwise
arena proofs to initial admission preserves all four PCM hashes, 746 controls,
22,052 produced/consumed/harvested/retired jobs, arithmetic checks and finite exit.
Every subsequent block still compares engine, instance, arena pointer, used bytes
and capacity against the sealed layout. Ten host mutations refuse before second
publication; full threaded normal and ASan/UBSan PCM comparisons remain exact.

Producer means are 24,140 / 28,087 / 30,533 / 34,138 oscillator ticks; consumer
means are 30,448 / 32,041 / 32,049 / 32,058. The eight-output, eight-block-latency
optimistic capacity model reports **zero misses**, versus 669 for V100. Smaller
latencies fail. This is the first successful capacity screen, not continuous
playback: the test still drains every 16 blocks and excludes transport overhead.
The heaviest producer averages 1,422.417 us against the unchanged 1,451.208 us
budget. Worker stack has 7,312 unused bytes. Source, raw UART and strict facts
remain private under `scratch/devkit-20261023/renderer-two-slot-v102-exports`.

[verified: private adapter and host transport fixture] The next V103 diagnostic
connects this pipeline to the existing dev-board internal DAC. DSP stays in task
context; the audio IRQ solely copies completed immutable output leases, checks
integer PCM hashes and retires those leases. Task context only harvests work.
The continuous pump removes the service screen's 16-block pauses and model loops.
It is initially a bounded busy-pump diagnostic, not scheduler or sustained acceptance.
Normal and ASan/UBSan transport checks pass all 22,052 recorded PCM blocks, three
startup prefills, end draining and eight permanent fault/silence cases.

[verified: pinned SDK IR; physical ordering pending] The DAC start routine does
not prefill the ring. V103 therefore checks the allocated three-window geometry,
places exact tags 0..2 into those windows while stopped, publishes the prepared
frame credits and hands sole output reading to the IRQ. Four silence refills
follow the final tagged submission before task-context stop. The host callback
mock is not proof of hardware pointer ordering or actual analog first samples.
Actual continuous underruns, full IRQ cost, memory headroom and physical capture
remain the next gates. No backup, factory-restore or full-readback cycle was used.

### V103 continuous DAC: underrun isolated to sustained producer capacity

[verified: fresh dev-board UART] The first actual continuous DAC run fails after
24.3 seconds of playback, during the held twelve-voice case. The first three
cases each complete 5,513 blocks with exact expected PCM hashes. The fourth
stops after 200 blocks when the completed-output ring becomes empty. Its
producer averages 35,968 OSC24M ticks (1,498.667 us), above the unchanged
34,829-tick (1,451.208 us) block budget. Consumer average is 32,162 ticks.
The full audio IRQ maximum is only 351 ticks (14.625 us), with no recorded
cadence-gap faults. Buffering and copying therefore do not resolve the remaining
producer deficit. The segmented V102 capacity screen hid this sustained held-note
cost by including its release period and periodic pauses.

[verified: diagnostic lifecycle] The transport reports permanent fault 10304
(unavailable completed output), emits silence, and stops the DAC. Both backend
error words remain zero. UART remains responsive after closing the sole receiver;
no crash, backup, restore rehearsal or full-flash readback occurred. The reset
receipt is consumed and will not be retried. This is a failed hardware performance
test, not analog or sustained acceptance. Raw UART and strict failure facts stay
private under `scratch/devkit-20261023/renderer-two-slot-v103-exports`.

[verified: host tests; target gain unknown] Astra identified redundant recording
and replay of CPU0's own engine commands. V104 executes sound0/2/3 directly in
the original sequencer dispatcher and records only deferred Macro sound1, retaining
insert/level boundaries, immutable work slots and ordered shared mixing. Normal
and ASan/UBSan threaded tests match all 5,645,312 PCM bytes exactly. Additional
source-grounded engine-state comparison precedes target testing. No timing gain
is claimed from the host proof.

[verified: bounded threaded host state test] V104 also matches 1,087,869,264 bytes
of CPU0 engine and Filter state across all 22,052 producer boundaries, in each
of the normal and ASan/UBSan runs. The comparison streams records through bounded
pipes and discards them; it does not save gigabytes of private state. DX7's unused
kernel adapter must be null and its instance must have matching alignment. Drums
normalizes only its known voicing pointer and compares the pointed-to state,
including RNG and native/resampler history. This is host evidence, not target
cache, race or analog proof. The native image builds and retains the same DAC
transport for the causal hardware comparison.

### V104 direct CPU0 dispatch and V105 mono-filter combination

[verified: fresh dev-board continuous DAC] V104 still underruns in the heaviest
case, after 843 blocks. Its first three cases retain exact PCM hashes. Producer
means for those complete cases are 24,452 / 28,441 / 30,850 ticks. The incomplete
heavy-case mean is 35,015 ticks (1,458.958 us), with consumer 32,158 ticks and
full IRQ maximum 352 ticks. Comparing this partial heavy-case average directly
with V103's shorter 200-block failure would overstate the saving. The remaining
observed deficit is 186 ticks (7.75 us), but sustained margin is unproven.

[verified: host combined proof; target result pending] V105 combines direct
CPU0 dispatch with V95's per-frame mono Ladder reuse. Inputs, both coefficients,
and all five channel history values must be bit-identical before reusing one
channel's calculation; all other frames retain the original stereo path. The
combined normal and ASan/UBSan runs match all 5,645,312 PCM bytes and all
1,087,869,264 compared DX7/Drums/Filter state bytes per run. The native build
passes. V105's target result is not yet known; neither a deadline pass nor analog
acceptance follows from these host results.

### V105 first continuous digital transport pass

[verified: fresh dev-board DAC run and strict receipt parser] V105 completes all
22,052 blocks continuously, with all four exact PCM hashes, zero unavailable
outputs, zero backend errors, no recorded IRQ cadence-gap faults, and clean worker
exit. All produced, consumed, harvested and retired tags agree. The full IRQ
maximum is 366 ticks (15.25 us). Producer case means are 24,196 / 28,192 /
30,608 / 34,210 ticks; consumer means 30,527 / 32,217 / 32,179 / 32,157.
The heavy producer still has 2,056 individual blocks above the nominal block
budget, but the pipeline absorbs those bursts in this finite run. Minimum ready
outputs is only one, so the sustained margin remains thin. This is the first
32-second **continuous digital transport pass**, not a 30-minute, scheduler,
physical-output or analog acceptance result.

[verified: lifecycle] Application-only install and one unique reset were used;
the sole receiver was closed before a successful ordinary PING. No backup,
factory restore or full-flash readback was performed. Private raw UART SHA-256
is `58d652dca0f3748793a13a5d985da8ae3ed8229a110d76bee165b6f5d318e533`.
The next experiment preserves state across 57 complete workload cycles, derives
228 expected hashes from uninterrupted host rendering, and pairs sustained DAC
operation with KA6 capture. It must use a millisecond duration guard because the
24 MHz timer wraps repeatedly during a 30-minute run.

### V106 sustained reference proof and physical-capture limits

[verified: uninterrupted host rendering] The 57-cycle extension carries all
engine, sequencer, resampler and shared-effect history through 228 cases. Both
normal and ASan/UBSan candidates match the original serial reference across
321,782,784 PCM bytes (1,256,964 blocks), SHA-256
`49dc016876b695ba960c8c6aeed3b485f88c3025a0eaf691875f3e94e3f6acb4`.
The native build passes. The finite watchdog uses elapsed milliseconds; the
24 MHz timer wraps repeatedly during this duration. The strict receipt parser
requires all 228 checked hashes, full tag counts, at least 30 minutes elapsed,
zero transport errors and clean exit. Missing/short/malformed/fault receipts
are rejected. These host/parser checks do not establish sustained hardware
acceptance.

[verified: capture in progress; not accepted] One application-only flash and
one unique reset started the continuous dev-board run with paired UART and
KA6 capture. Startup/control/arithmetic/worker initialization passed. The first
captured minute correlates with the reference; the fitted effective playback
rate is about 44,116.9 Hz. Initial analog correlation is about 0.68 after a
small fitted transfer filter. A conservative synthetic-fault observability
probe misses many missing/repeated 64-frame blocks, especially in quiet
passages, so this capture cannot yet establish dropout-free analog output.
The actual sustained terminal result is pending at this checkpoint.

[verified: pinned SDK IR; inferred capture cause] The diagnostic's
`dac_set_gain(54)` selects combined-volume index 17 / analog gain code 8;
`100` selects index 32 / code 30. Digital volume is already 100. This explains
a likely substantial attenuation before the capture interface. A subsequent
capture can raise analog gain without changing any PCM calculation; this
running soak remains unchanged. Physical injected-fault validation is still
required before claiming the analog detector is adequate.

[verified: source review] Astra's production integration review identifies a
real ownership boundary: drawing clears the peak accumulator that the split
consumer updates, and several live MIDI/parameter operations bypass the fixed
fixture's recorded command path. The next bounded scheduler experiment uses
latched wake predicates on the unchanged fixture before production input/UI
integration. Busy-pump transport success does not establish task fairness or
interactive product acceptance. Detailed SDK evidence and plans remain private.

### Tracked Ladder mono reuse promotion

[verified: source and independent review] Promoted the V95/V105 Ladder
optimization into the tracked filter. It reuses one channel only when input,
G, G4, sigma and all four history values match by bits; otherwise the original
stereo calculation runs. Shared coefficient evaluation and sample arithmetic
are unchanged. Complete Ladder history is copied after the reused calculation.
Astra found no missing channel-dependent input in the guard.

[verified: fresh bounded Aeon tests] All 80 filter tests pass, including the
extended independent-channel oracle for both SVF and Ladder across mono,
stereo history, return to mono, moving parameters and signed-zero inputs.
The initial suite invocation failed because Make selected unavailable g++;
setting CC=clang and CXX=clang++ resolved that environment error. The existing
private V95 differential additionally checked complete state and exceptional
input patterns; the tracked oracle does not claim internal-state coverage.

[verified: actual rebuild] The normal GPL-enabled browser engine set rebuilt
with 108 parity scenarios passing, all identical to JavaScript and musl.
The 30-second edit-layer benchmark recorded zero late quanta; strict CI-mode
build-record validation passed. This --no-screenshot rebuild does not establish
Chromium playback acceptance or resolve the earlier browser underrun failure.
The native V107 wake experiment also matches the full 5,645,312 PCM bytes in
normal and ASan/UBSan builds and links successfully; target wake latency and
fairness remain untested. The V106 hardware soak is still running at this
checkpoint, so no sustained hardware or analog acceptance is claimed here.

### V106 sustained digital transport and V108 physical fault detection

[verified: native dev board] The unchanged mixed workload completed 57
uninterrupted cycles: 1,256,964 blocks, all 228 reference hashes checked,
1,823,490 ms elapsed. Output fault, backend error, late callback and gap
counters were all zero. Maximum measured full IRQ was 357 oscillator ticks
(14.875 us); minimum ready depth was one. Parent stack retained 701 words;
worker retained 1,834 words and exited cleanly. Producer bursts still exceeded
a single block's compute budget in the heavier case; finite buffering absorbed
them throughout this run. This is sustained digital transport evidence from
the busy-pump diagnostic, not scheduler fairness or production acceptance.
Private raw UART SHA-256:
`9a29c35fa69f04e1bbde67aca0db7c46aa39a73377d3699d10be0451d07981d4`.

[verified: physical capture] KA6 captured 1,860 seconds with exit zero and no
reported recorder overrun. The earlier low-gain signal's detector sensitivity
was inadequate. A separate higher-gain V108 probe deliberately erased four
64-frame physical output blocks after validating the original PCM. All four
were detected above 482 nearby comparison windows each. Fitted correlation
was 0.99906; estimated playback rate was 44,116.87 Hz. Measured missing-block
fractions were approximately 1.006, 0.909, 1.009 and 1.004. This validates
observability at those four points, not every signal window or a clean soak.
The probe is explicitly marked acceptance=0 and rejected by clean parsers.
The full capture contains a near-full-scale transient; no clean startup or
clipping-free analog acceptance is claimed.

[verified: source review; inferred integration path] Astra found no existing
small-buffer app display backend. External pixels still require 115,200 bytes,
and banner erasure reads prior pixels. A compact immutable drawing-command
frame plus scanlines is a candidate, with capacity, pixel equivalence, task
stack, raster CPU and SPI lifetime still to prove. The existing quarter-rate
visual cadence is preserved. The native semaphore/canary experiment is next;
production display, live input ownership and final analog acceptance remain
unfinished. No physical FM-1 traffic was issued.

### Interrupt and scheduler stall isolation

[verified: native V119/V120 diagnostics] The failing mixed-render callback
performs normal work: one final 32-frame Macro render executes three native
12-sample blocks, pushes 33 samples and pops 32; pending input changes from
three to four, satisfying 3 + 36 - 33 = 4. With normal interrupts, this render
took about 40.12 ms. A tag-seven-only diagnostic masking CPU1 local interrupts
reduced that render to 270.21 us, and the complete five-operation Macro batch
took 546.13 us. Re-enabling interrupts then took another 9.45 ms. The callback
subsequently stalled and the unchanged timeout still failed. Interrupt masking
is a discriminator, not a production fix or fairness acceptance.

[verified: native negative controls] A public system-sleep veto did not remove
the stalls. Combining that veto with an effective CPU0 raw-idle bypass also
failed. Both retained ordinary interrupt service, queue waits, sample arithmetic
and the deadline. These results reject those particular interventions as
sufficient fixes; they do not identify the responsible interrupt or exclude
other SDK rendezvous paths.

[verified: bounded read-only observations; inferred limit] CPU0 sampled CPU1
ICFG, RETI, PCRS and execution-trace registers at wake boundaries. Paired ICFG
reads matched, with a zero interrupt-context byte at the sampled instants;
addresses varied within ordinary synthesis/resampling code. Raw upper ICFG
bits have not been decoded. These samples cannot establish what CPU1 did
while CPU0 slept, and unpaused PCRS is not a validated continuous PC trace.
No physical FM-1 traffic was issued. Production integration, scheduler fairness
and clean analog acceptance remain unfinished.

### CPU1 affinity loss isolated; first native correction

[verified: native V125/V126] Bounded read-only observations taken before the
SDK tick scheduler showed CPU1 in the idle hook during the long Macro callback.
V126 independently captured both current-task and selected-task arrays: the first
eleven rows contained the two idle tasks, even though the worker callback was
unfinished. The probe cost five to six oscillator ticks. These observations
resolve the earlier post-wake sampling blind spot without pausing either CPU.

[verified: pinned SDK IR and bounded model] Astra identified a matching selector
path: the shared descending-priority traversal initially consumes a CPU1-pinned
candidate for CPU0, then loses that candidate after affinity rejection. A late
copy repair was rejected offline because it can exhaust the candidate mask on
an idle-task migration edge. It was never installed. Early interception retains
the first CPU1-pinned candidate before consuming a lower CPU1 candidate. The
model reproduces the original failure, the rejected repair's exhaustion, and
the early correction's valid selection. General equal-priority mixed-affinity
round-robin fairness remains unproven; this is a bounded diagnostic correction.

[verified: native V128] With that early interception in a private build-copy SDK,
original worker priority 16 and ordinary interrupts, the traced final 32-frame
Macro render took 12,042 oscillator ticks (501.75 us), versus about 40.12 ms in
V126. Work remained three native blocks, 33 pushes and 32 pops. The first three
mixed cases completed all 5,513 blocks with expected hashes 6bcab227, 46c02687
and 1e2f305d. The fourth case ran 123 blocks before output starvation fault
10304. No backend error or callback timeout was recorded. Producer means were
24,544 / 28,460 / 30,936 / 36,388 ticks; the last exceeds the unchanged 34,829
budget. Maximum full IRQ was 1,325 ticks (55.21 us). This removes the observed
large scheduling stalls but does not establish dropout-free playback.

[verified: lifecycle] The sole receiver was closed once after two exact argument
checks, reached terminal status and its PID was absent before ordinary PING ACK.
V128 and all older reset receipts are consumed and must never be retried. Raw
UART and SDK artifacts stay private and are mirrored on Aeon. Next is a run
without per-sample timer probes and with the original low-priority canaries
restored. No physical FM-1 traffic occurred; PR155 remains draft and unmerged.

### Clean native timing and remaining scheduler fairness, 2026-10-27

[verified: V131 target] Removing per-sample Macro timer probes and restoring
both low-priority canaries preserves the first three complete case hashes.
Producer means were 24,935 / 28,937 / 31,392 / 36,349 oscillator ticks. The
heavy case starved the output after 127 blocks, fault 10304; its 36,349-tick
producer mean still exceeds the unchanged 34,829-tick deadline. Worker means
were 30,445 / 32,081 / 32,115 / 32,168 ticks. Maximum complete IRQ was 1,414
ticks with zero callback lateness/gaps before starvation. This is still a
performance failure, not clean playback acceptance.

[verified: V129–131 startup] Restoring the two original diagnostic canaries
exposed allocation pressure. V129 failed parent creation; V130 started tasks
but failed a 1,536-byte DAC allocation. Using 128-word canary stacks and a
1,792-word parent stack allowed V131 DAC startup; the parent retained 445
unused words. Aggregate free heap alone did not establish allocation viability.
The worker stack was unchanged. No canary completion report followed the output
fault, so this run does not establish scheduler fairness. Each receiver ended
and its PID was absent before ordinary PING ACK. All reset attempts are consumed.

[verified: current source inspection] The count-only command-stream reset and
active-prefix immutable copy proposed again during continuation already survived
from V100 into V131. An older V98 snapshot initially obscured that fact. No
duplicate native optimization or speedup is claimed.

[verified: private host fixture] Astra's independent intrusive-list execution
passed 65,601 differential selections, 2,400 removal/reinsertion transitions and
112 primitive cursor cases; all six intentional corruptions were detected.
This exercises pinned list semantics and a bounded selected-node rotation repair,
not vendor ABI, concurrent SMP execution or native fairness. The native candidate
is being compiled separately from the throughput investigation. SDK artifacts
remain private; production integration and dropout-free acceptance are unfinished.

[verified: native V132] The private selected-node rotation linked and started
with unchanged application/DSP source. Final vendor machine code places both
rotation calls before the original lock release/local interrupt enable; the
existing list removal retains its enclosing critical section. The SDK audit
has zero failures and its dormant key-check scheduling was manually reviewed.
The first three 5,513-block case hashes remain exact. Producer means were
24,878 / 28,883 / 31,329 / 36,266 ticks; worker means were 30,445 / 32,082 /
32,120 / 32,179 ticks. The fourth case starved after 133 blocks, fault 10304.
No backend error or callback gap/lateness occurred before starvation; maximum
IRQ was 1,137 ticks and parent unused stack 445 words. This does not close the
throughput gap or establish mixed-affinity scheduler fairness. The receiver
was twice argument-verified, terminated once, reached terminal status and its
PID was absent before ordinary PING ACK. No full backup/restore/readback cycle
was repeated. All reset receipts are consumed; the board is responsive idle.

### Wait-aware yield and bounded CPU0 attribution, 2026-10-27

[verified: V133 target] Keeping every semaphore post and gating only explicit
yield on a receiver's ordered wait flag did not materially improve throughput.
The first three cases retained exact hashes; heavy case ran 135 blocks before
output starvation 10304. Producer means were 24,878 / 28,887 / 31,337 / 36,237
ticks, against the unchanged 34,829-tick budget. Maximum full IRQ was 1,111
ticks with zero callback gaps/lateness before starvation. Finite host wait/notify
schedules passed; two intentionally broken ordering variants became stuck.
Neither that model nor this failed audio run establishes general SMP fairness.

[verified: V134 startup] CPU0-only existing render hooks were added for inclusive
dispatch, two DX7 tracks, drums, both first-track filter inserts and UI. Held
and release buckets are separate. Their added SRAM footprint exposed another
contiguous 1,536-byte DAC allocation failure before playback; no performance
result exists for V134. V135 moves diagnostic counters to spare cache data and
helper code to flash, preserving all task stacks and DSP source. Its native
build and SDK audit passed; the residual dormant-key scheduling check was
manually reviewed against vendor disassembly. The sole UART receiver was armed
before its one unique reset; target results are pending. Probe overhead means
these are attribution measurements, not clean acceptance timings.

[verified: lifecycle] V133 and V134 receivers reached terminal status and PID
absence before ordinary PING ACK. Every invoked reset, including failed-startup
V134, is consumed and must never be retried. No backup/restore/readback rehearsal
was repeated. Private SDK artifacts and raw UART remain ignored and mirrored
on Aeon. No physical FM-1 traffic occurred. PR155 remains draft and unmerged.

[verified: V135 target] The relocated diagnostic started the DAC with 5,364
free heap bytes before open and 3,796 afterward, unchanged task stacks and
445 unused parent words. Its first three complete 5,513-block hashes are exact;
the fourth ran 146 blocks before output starvation10304. Producer means were
24,733 / 28,736 / 31,234 / 36,147 ticks. IRQ maximum1,073 ticks; zero callback
lateness/gaps before starvation. This remains a deadline failure.

[verified: CPU0 attribution] Heavy held inclusive dispatch averaged34,451ticks
per block; first DX7 render15,074ticks/call, drums9,511, other DX7 1,639,
filter inserts3,689 and UI997. The engine spans occurred150times over148blocks,
so weighted engine/filter cost is30,267ticks/block and the non-render dispatch
remainder about4,184ticks. The remainder includes setters/routing/recording and
probe overhead. UI is approximately41.5us; it is not the dominant remaining
path. Timer spans overlap inclusive dispatch and must not be added to it.

[verified: private V136 host proof] A conversion-only Drums loop reuses already
established resampler readiness instead of repeating generic push/pop guards.
Coefficients, arithmetic order, ring updates and native rate are unchanged;
non-conversion modes keep the generic loop. At six rates,720,000 output samples
and complete resampler states match bit-for-bit with randomized partial pushes,
both normally and under ASan/UBSan. The initial native duplication exceeded the
existing app bound; sharing the identical conversion kernel reduced it to588,124
bytes. Native build/link and SDK review pass. Its uninstrumented target run completed as described below; no production
integration or acceptance is claimed.


[verified: V136 target] The first three cases retain exact complete hashes. The
heavy case reaches166blocks before output starvation10304. Producer means are
24,627 /28,631 /31,089 /35,892ticks; worker means30,449 /32,085 /32,121 /32,181.
The heavy mean remains1,063ticks above budget, before jitter allowance. Compared
with clean V133, means decrease251/256/248/345ticks, but truncated heavy sample
populations differ and this is one run. Backend errors0, IRQ maximum1,064ticks,
callback gaps/lateness0 before starvation; heap3,732 after DAC and parent445
unused words. Receiver70801 ended naturally with exit0 and no PID remained
before ordinary PING ACK. Its reset and every older reset remain consumed.

[verified: V137 private preparation] Astra's per-block DX7 common-control proof
passes normal and ASan/UBSan:5,645,312PCM bytes and1,264,773,264compared CPU0
state bytes exact, including per-note fallback probes. The native candidate is
built independently on clean V133, without Drums specialization or profiling.
Only per-block pure Env Time/brightness/feedback preparation is shared; every
voice retains its state advancement and ordered mix. Native gain is unmeasured.


[verified: V137/V138 native falsification] The initial DX7 block-control build
failed the DAC1536-byte allocation before audio (heap4980, fragmented), so it has
no timing result. Moving only cold DX7 Init to flash freed512SRAM bytes; native
Init is at0x203d18a, RenderBlock remains at0x1c1cdf2, with task stacks unchanged.
V138 starts DAC successfully with3924heap bytes afterward. First3complete PCM
hashes remain exact; heavy139blocks starve10304, backend0. Producer means are
24643/28638/31118/36181ticks vsV13324878/28887/31337/36237. Heavy gain56ticks
(~2.3us) is insufficient and truncated sample populations differ. IRQmax1014,
late0/gaps0, parent445unused. No additional common-cache layout variants planned.
The next substantial candidate is a bounded copied-state suffix-voice kernel
assist on CPU1, with prepare/ordered mix still on CPU0; design/ownership review
precedes implementation. No deadline/analog/soak acceptance is claimed.

### Note-on transition attribution and predecoded built-in candidate

[verified: V147 target] Producer misses remain at first-case blocks0/11026/16539:
38273/35180/37114ticks against34829. Four note-on bursts cost5564/3342/5419/7434ticks.
Transport fault/backend/late/gaps0 across22052blocks; adaptive finalcap6 is reduced
polyphony, not fixed12 acceptance. Native LTO already hoists shared rate/velocity
work and removes most intermediate envelope copies, rejecting that rewrite.
[verified: V148 discriminator] SRAM NoteOn slightly reduces note setup to
5333/3091/5058/7085ticks but still two producer misses; not a sufficient fix.
[verified: host] Generated32x156 decoded built-ins match original FromPacked
byte-for-byte in normal and ASan/UBSan tests. V149 copies those immutable bytes
into the existing cache and skips ScaleLevel only when both depths zero. Full
V147 decision replay22052blocks5645312PCMbytes is exact normal+ASan/UBSan,
SHA5631008780acba42d7d62de877fe3b27f7b70adbd18c7a622c9024c949d54932.
No extra instance/cache memory; native timing pending. Soak/analog not accepted.

[verified: V150 nested target timing] All22052blocks complete with transport
fault/backend/IRQlate/gaps0. Engine note-on callbacks cost1104/1731/2575/4251ticks;
whole note setup4910/3545/5245/7193ticks. Producer first blocks37722/34608/35717/
37800ticks, three misses. This separates engine initialization from app/modulation
cost; it is not dropout-free acceptance. V149 predecode alone also retains3misses.
[verified: CV window optimization] feed_cv discards window_of's offset. Direct
current/next window comparison preserves20000fullstate comparisons normal+ASan/
UBSan and complete22052block5645312byte PCM replay with recordedV147 adaptive
limits (SHA5631008780acba42d7d62de877fe3b27f7b70adbd18c7a622c9024c949d54932).
Gate edge offsets remain unchanged. V151 native timing pending; no analog soak.


## 2026-10-27 note-on burst follow-up: empty modulation voice scans

[verified] Added a monotonic internal `voice_ever_started` byte in the existing
reserved byte. Until the first per-voice modulation activation, voice lookup,
voice ticking and pending voice-write scans return immediately. The flag is
never cleared by release, route removal, rebind or reset: pending restorations
must still drain. Object size is unchanged. The directed regression compares
original scans with the shortcut through actual activation, retirement, reset,
steal, counter rollover and recreation, including at least four real zero
restorations. Both normal and ASan/UBSan comparisons pass on the tracked source.
A separate private baseline/new-source proof matches 3,145,488 state/write bytes
per variant. Full mixed replay matches all 5,645,312 PCM bytes across 22,052
blocks under the same recorded adaptive decisions, normal and sanitized.

[verified] V152 plan sealing before the first block and labelled adaptive
reserve75 (four-voice floor) leaves one producer miss. V153 initialized-envelope
memo reduces note setup but leaves two producer misses; it is not promoted.
V154 empty-voice scans improve the heavy first block to 34,976 ticks against the
unchanged 34,829-tick budget; the initial block is 34,844. All 22,052 DAC blocks
complete with zero transport faults/IRQ late/gaps. These small remaining producer
misses still fail acceptance. Adaptive results are not fixed twelve-voice proof.

[verified] V155 relocating four note helpers into SRAM cannot allocate the
renderer parent stack; UART recovery remains responsive. No workload or analog
acceptance is claimed. V156 narrows relocation to the voice-start helper only;
target timing is pending. Fresh physical fault detection and a representative
30-minute analog soak remain outstanding.

[verified] Actual simulator rebuild after the CV/note changes passes all108
parity scenarios; committed WASM/build record source and artifact hashes match.
This repairs the observed stale-record CI failures, not the previously observed
Chromium playback underruns. Private evidence stays in scratch/devkit-20261023
and the matching bounded Aeon lane. Successful directed raw state/PCM traces are
removed after exact comparisons and hash reports; logs and receipts remain.
Mac free space at this checkpoint: 1,155 GiB (above the owner's500GiBfloor).

## 2026-10-27 note-on window sharing and continuous soak

[verified: host] Note-on routing now computes its current/next modulation window
and offset once, reusing those coordinates for current-note gate and CV writes.
Pending trigger falls retain their independently classified timestamps. Directed
normal and ASan/UBSan comparisons preserve all runtime/write bytes, including
boundary/wrap, retrigger, overflow and per-voice lifecycle cases. The tracked
note-window and voice-lifecycle tests pass (four variants); five SRAM-placement
source-preservation tests pass on a fresh source archive. An older transformed
proof staging tree initially failed placement assertions; fresh tracked source
resolves that staging error without changing the assertions.

[verified: target] V158 shares the edge append body in SRAM and puts voice-start
there too. All22,052 producer and consumer blocks meet the unchanged34,829-tick
budget; worst producer34,607. DAC transport faults, backend errors, interrupt
lateness and gaps are zero. This uses labelled adaptive12-to4 voice admission,
not fixed twelve-voice acceptance. Inlining every append copy instead exhausted
SRAM and failed DAC allocation; the shared body avoids that regression.

[verified: physical probe] V159 repeats the passing short timing run with a
6KiB worker stack and four intentional missing64-frame outputs. All four are
detected in the channel0 analog capture above482 nearby controls each. The
calibrated analog correlation is0.9922. This fault-injected run is not clean
audio acceptance, and those local controls alone do not establish sensitivity
for the entire signal. Worker unused stack is5,288bytes; post-DAC heap5,588.

[in progress] V160 removes fault injection and runs57 continuous four-case
cycles,1,256,964blocks (about30.4minutes), without DSP reset. A1,860-second KA6
capture and sole1,900-second UART receiver are running. Final target counters,
actual adaptive-decision host replay, and a calibrated full-recording analog
scan are required before claiming sustained acceptance. No fixed-polyphony,
physical FM-1, merge or release acceptance is implied. Evidence and one-shot
reset receipts remain private in scratch/devkit-20261023 and the Aeon lane.
Mac free space at this checkpoint:1,150GiB.

[verified: recording-window correction] The first V160 soak recording began
76 seconds before reset. Its analog recording ended before the30.4-minute music
sequence finished, and the UART receiver ended before final counters. It cannot
establish sustained acceptance; missing counters do not establish a crash.
The board subsequently acknowledged PING. V160b repeats the same installed image
with capture arming and a new one-shot reset coordinated in one runner. Reset
followed capture start by0.236seconds; analog1900seconds and UART1980seconds
cover the intended workload with margin. No application flash write was needed.
The previous reset receipt remains consumed. V160b acceptance is pending.

[verified: CI] Exact e7dea38b CI40467083871 completed with12 passing jobs,
including all three browsers, native32bit and sanitizers. macOS and Ubuntu each
failed only the generated metadata example's stale ID. A fresh renderer export
regenerated the example (only meta_id changed); all23 schema tests pass on
bounded Aeon. No assertion, timing deadline or zero-underrun gate was relaxed.

[verified: policy source] Added an explicit burst-reserve initializer for the
measured75% pressure /70% recovery experiment. Existing original and85/80
initializers retain their behavior. All six normal/sanitizer policy variants
pass, including full-queue pressure and recovery hysteresis. This names the
private configuration in tracked source; it does not establish fixed-polyphony
or sustained hardware acceptance.

### 2026-10-27: continuous burst failure and endpoint isolation

[verified: dev board] V160b completed 30.4 minutes of uninterrupted mixed work:
1,256,964 blocks and 228 cases, adaptive twelve-to-four voices. Consumer timing,
DAC accounting and fault counters pass, but 85 producer blocks exceed the
unchanged 34,829-tick deadline. The eight retained late-event tags are repeated
case transitions. This is a failed performance result, not sustained acceptance.
Normal and sanitizer host replay match all 228 case hashes and the complete
321,782,784 PCM bytes under the recorded adaptive decisions.

[verified: analog screen] The frozen scanner aligned every block, with its 25
flags confined to startup. Quiet and weak-template coverage remains unqualified.
The recorder split at 2 GiB; preserved files concatenate without sample edits,
but their boundary continuity is not independently established. No blanket
analog acceptance follows. A subsequent whole-capture level check also found a
shutdown transient that a music-interval-only scan would miss.

[verified: experiments] V161 holds the initial eight output leases while the
DAC plays zeros and ramps gain before releasing the first PCM block. V162 also
ramps gain down only after every logical output drains. The complete 125-second
V162 capture has zero near-fullscale samples on both measured output channels,
including both endpoints. A level screen alone is not dropout detection.

[verified: exact candidate] In-place pristine-envelope reuse preserves each
NoteOn and avoids copying templates. Original state after individual events and
PCM agree at four sample rates, including built-ins, user rewrites, repeated
steals and partial blocks, normally and under ASan/UBSan. The directed test
exercises 2,681 reuse hits. Three continuous native cycles still have three
producer overruns, including the repeated eight/twelve-note transitions;
consumer timing and DAC fault checks pass. This candidate does not solve the
burst deadline. A separately labelled adaptive floor-two headroom experiment
is next; no fixed-polyphony acceptance is claimed. Private artifacts remain in
the named devkit scratch and Aeon lanes.

[verified: CI] Exact source 3549c10f CI 40472027768 and Pages 40472027779 both
completed successfully. PR155 remains draft and unmerged; hardware acceptance
is incomplete.


## Repeated note bursts: exact reuse and rejected allocator, 2026-10-27

[verified: host] The pristine-envelope shortcut now returns immediately when
an already-initialized voice slot has unchanged patch, velocity, level scaling
and effective rate scaling. Every NoteOn still executes; phase, gain, glide,
key/age and note-offset semantics stay intact. NoteOff, retuning, patch writes
and rendering invalidate reuse before mutation. Original state and PCM match
at four sample rates across built-ins, user writes, repeated steals, voice
limits, bend/offset setters and partial blocks, normally and under sanitizers.
The polyphonic glide planner also avoids a source search when the selected
mode cannot consume its result; held-key removal skips an unchanged prefix.
A differential compaction test includes inactive trailing bytes and bounds.

[verified: dev board] These are explicitly adaptive65/60, floor-two tests,
not fixed-twelve-voice acceptance. V164 and V165 completed three continuous
cycles (66,156 blocks each), with one producer miss at tag38,591. V165 maxima
were34,618/29,157/33,190/35,454 ticks against the unchanged34,829-tick budget;
consumer deadlines and DAC accounting/fault checks passed. The remaining miss
prevents sustained acceptance. Last-cycle note timers cannot be attributed to
an earlier worst-case transition because those timers are overwritten.

[verified: rejected experiment] A single-pass allocator was exact in expanded
host state/PCM proofs but increased native means from about22,900 to23,700
ticks/block and still missed35,463 ticks. Its allocator change was reverted;
no cache/layout cause is established. V167 instead tests sharing bookkeeping
for the original ordered fall/rise trigger pair. Extracted full-state fixtures
and complete modulation-state traces pass normally and under sanitizers; its
native speed is pending. No new30-minute or blanket analog acceptance is claimed.

### 2026-10-27: empty automation lanes remove the remaining short burst miss

[verified] The three-cycle V170 adaptive65/60 floor2 run completed 66,156 blocks
with zero producer deadline misses, zero consumer misses and zero DAC faults or
gaps. Producer maxima were 32,646 / 28,846 / 31,148 / 33,835 ticks against the
unchanged 34,829-tick budget. All requested note-ons still execute; this is
adaptive-polyphony evidence, not fixed-12-voice acceptance. V169 helper placement
alone did not solve the miss and was rejected.

The retained change computes a fresh mask of nonempty sequencer lane labels in
`seq_auto_base`, skipping only empty-label target resolution. Populated lanes
retain their original resolver, ascending order and base-update commands. No
cached label state, PCM transformation or note-admission cap is introduced.
The automation fixture checks all 256 label masks across every app track,
including clearing and unrelated labels. Normal host automation and the actual
recorded-decision replay pass: 16,935,936 PCM bytes, case hashes, fold, controls,
voice statistics and captured state agree under normal and ASan/UBSan builds.
The actual browser rebuild passes 108 JavaScript/musl PCM parity cases; no new
Chromium playback acceptance is claimed.

V171 extends the same diagnostic to 57 continuous cycles (1,256,964 blocks,
about 30.4 minutes) with single-file six-channel analog capture. At this writing
that run is live, not accepted. The frozen left-channel physical fault detector
calibrates; an independent right-channel calibration currently refuses its
held-out correlation, so stereo analog acceptance remains unqualified.

[verified] The exhaustive label-mask fixture additionally exposed an existing
`ALABEL` clear-path out-of-bounds read: a fixed-size `memcpy` used the one-byte
empty-string literal when no label argument was supplied. Clearing now explicitly
zeroes the label buffer; nonempty commands retain the original copy. The complete
automation fixture passes ASan/UBSan after the fix, and the actual WebAssembly
rebuild again passes all 108 parity cases. V171 was already running and does not
issue label-clear commands; its exact image remains the earlier V170 DSP variant.

### V171 continuous adaptive soak: timing pass, analog anomalies unresolved (2026-10-27)

[verified] V170's empty-label lookup optimization completed 57 continuous cycles,
228 cases and 1,256,964 blocks in 1,823,700 ms. Producer and consumer deadline
misses were zero; producer maxima 32812/30189/31475/34721 ticks remain below
34829. DAC fault/backend/off/close/late/gaps were zero. Exact actual-decision
normal/ASan replay matched 321,782,784 PCM bytes, all 228 hashes, fold c9eec6cf,
42,522 controls and final active2/limit2/shed0/stolen4779. This is adaptive65/60,
initial12/floor2 evidence, not fixed12 acceptance. The board returned ordinary
PING ACK after both capture processes exited normally and their PIDs were absent.

[verified] KA6 recorded exactly 91,200,000 six-channel 48k PCM32 frames (1900s);
whole-capture peaks .500870/.518541 had no near-full-scale samples. Frozen
fault-calibrated left and separately calibrated MIMO right predictors scanned
all logical blocks without long-data fitting or threshold relaxation. Left
flagged the final three blocks; right flagged those three plus 712 blocks,
all in case1, in 155 clusters overall. These are unresolved residual anomalies,
not proven packet drops and not analog acceptance. Weak/silent/unprobed fault
sensitivity remains explicitly limited. Private raw capture, frozen receipts,
all flagged tags and replay are retained in the dated scratch lane/Aeon exports.

[verified] CI40484318024 failed only the metadata-example fingerprint assertion
on Ubuntu/macOS. Regenerated the existing subset using the actual current-source
native build export: only meta_id changed 8d0cd839->aa95d5c8, and canonical
subset equality passes. The focused pytest invocation in the analysis image
could not collect because jsonschema is absent; this is not a pytest pass.
No test expectation or underrun gate was weakened. Native build and generated
example correction do not alter the running V171 image or its PCM.

[verified: analog discriminator] A separate, single-pass prediction-anchor check
preserves the frozen right-channel MIMO coefficients and thresholds. It passes
all four physical packet-hole cases with zero clean-control flags; held-out
correlation is 0.994291 and correlation outside anchor windows is 0.994205 over
23,591 samples. On V171 it leaves exactly the three final-block flags: 712
original internal flags are absent, with no new flags, after at most 0.255542
analysis-sample correction. Exact source/model/receipt bindings were independently
reviewed. This supports timing-template bias as the internal-flag explanation;
it is a post-discovery discriminator, not blanket weak/silent-interval acceptance.
The original frozen flags and reports remain preserved.

[verified: endpoint experiment] V172 changes only the zero-only drain from four
to 64 callbacks before gain-down and adds final submission/drain/gain timestamps.
Its three continuous cycles (66,156 blocks) have zero producer/consumer misses
and zero DAC faults/gaps; producer maxima are 32606/28205/30375/32921 ticks.
Normal and sanitizer actual-decision replay agree exactly. The gain ramp begins
2,228,047 timer ticks (92.8353 ms) after the final logical PCM submission. A
125-second six-channel capture completed normally; endpoint comparison is pending.
An initial runner permissions error occurred after install but before any reset;
the resumed run used the completed install and one unique reset. Both receivers
exited normally, their PIDs were absent, and ordinary PING acknowledged afterward.
No repeat flash, full backup, readback or factory rehearsal was performed.

[verified: pinned SDK binary] The linked dac_set_gain implementation maps its
argument as a percentage through combined_vol_list and directly changes analog
gain registers. Its second argument is overwritten before use in this binary;
the header's 0..31/fade-option comments do not describe this implementation.
This motivates inspecting the actual shutdown gain transition, rather than
assuming that selecting a named fade option would smooth it. No physical FM-1
or fixed-polyphony acceptance follows from these dev-board measurements.


### Steady-zero endpoint and long-soak drain progress (2026-10-27)

[verified] V172 endpoint timing moved the common transient from about 2 ms to
89 ms when zero drain increased from four to 64 callbacks. Its location follows
the physical gain transition; delaying shutdown did not remove it. V173 retains
DAC gain, clock and the static ring on zero output after musical completion,
with musical counters frozen and an independent idle timer. Short target and
both-channel frozen analog checks pass; the final eight blocks pass and the
previous gain transient is absent. This is steady-zero idle, not an off/close
success claim.

[verified] The V174 long run completed all 1,256,964 musical blocks (57 cycles,
228 cases) with zero producer/consumer deadline misses and zero musical gaps.
It nevertheless FAILED at completion: only 63 of 64 zero callbacks drained,
the backend returned timeout6 and the transport reported fault10302. It is not
accepted as a successful analog soak. The parent wait ticket can cover eight
queued musical callbacks plus 64 zero callbacks, about 104.45 ms, while the
unchanged watchdog is 100 ms and the final interrupt signals only at drain64.

[verified] V175 credits strictly advancing zero-drain progress only after all
music has been produced, harvested and submitted. It restarts the same local
100 ms wait ticket; repeated identical reads cannot postpone a stalled drain.
The DSP, deadline and permanent-error behavior are unchanged. Independent source
review and the generated main loop confirm prefill is unaffected. Its short
66,156-block target run has zero producer/consumer misses and DAC faults/gaps;
producer maxima are 32738/29067/30616/32817 against the unchanged 34829 budget.
It enters steady-zero idle for 168 callbacks, exits its worker and responds to
ordinary UART PING after both receivers terminate. The musical projection
matches the previously validated V173 normal/sanitizer replay exactly; no new
replay is claimed for this unchanged trace. Both frozen analog channels have
zero flags and the final-eight-block endpoint check passes.

[verified: setup only] V176 repeats the same fix for 57 cycles with sole UART
and 1900-second KA6 capture armed before one unique reset. Its fresh startup
reports 1,256,964 blocks. Timing, replay, analog and endpoint results remain
pending. These are explicitly adaptive65/60, initial12/floor2 experiments;
every note-on executes or steals. They do not accept fixed-12 polyphony or the
physical FM-1 external-codec path. Quiet/weak/unprobed analog sensitivity limits
remain. No full backups, readbacks or factory rehearsals were repeated.


### V176: complete 30.4-minute adaptive target and analog run (2026-10-27)

[verified] The corrected lifecycle completed 1,256,964 blocks across 57 cycles
and 228 cases in 1,823,800 ms. Producer and consumer deadline misses are both
zero. Producer maxima are 32867/30383/30870/34212 ticks against 34829; consumer
maxima are 32948/32965/32966/32963. DAC fault, backend error, late callback and
gap counters are zero. The run drains all 64 zero callbacks and validates 167
steady-idle callbacks without changing gain or closing the clock. The worker
exits normally; unused stack is 435 parent words and 1322 worker words. Both
UART and capture exit zero; both receiver PIDs are absent before ordinary PING
acknowledges. The unique reset is consumed permanently. No backups, full-flash
readbacks or restore rehearsals were performed.

[verified] Actual-decision normal and ASan/UBSan host replay agree exactly over
321,782,784 PCM bytes, all 228 case hashes, folded hash c9eec6cf and 42,522
control events. The final voice statistics match: active2, limit2, shed0,
stolen4779. Every requested note-on executes or steals; this is adaptive65/60,
initial12/floor2, NOT fixed-12-voice acceptance.

[verified] KA6 recorded one exact 1900-second, six-channel 48 kHz S32LE stream:
91,200,000 frames, wrapped losslessly. The independently frozen stereo screen
aligns and scores all 1,256,964 blocks per channel, with zero flags and no
near-full-scale samples on either music channel. No coefficients or thresholds
were changed for this capture. The unchanged final-eight-block endpoint check
passes on both channels; 2 s versus 4 s IIR warmup agrees exactly and the prior
89 ms gain transient is absent. Raw endpoint intervals through 350 ms are saved.

[verified, bounded conclusion] No dropout was detected in this complete
30.4-minute adaptive workload. Hardware counters, exact actual-decision replay,
the calibrated stereo residual screen and endpoint evidence agree. This is not
proof for every patch, fixed polyphony or the physical FM-1 external codec.
The detector scores every block, but quiet, weak and unprobed missing-packet
sensitivity remains unqualified; its generic analog_acceptance flag deliberately
stays false. Four physical calibration holes establish local observability,
not sample-perfect analog continuity. Preserve these limits with the result.

Evidence is private under scratch/devkit-20261023 (v176 target/replay/analog/
endpoint/capture receipts) and the corresponding Aeon lane. Exact tracked
source64f2e2b7 and notes9125a371 CI runs both completed successfully, all14 jobs;
Pages succeeded. PR155 remains draft/open/unmerged; this milestone does not
complete the wider instrument and physical-unit review/acceptance work.


### Reproducible named adaptive policy (2026-10-27)

[verified: host integration only] The 65% pressure / 60% recovery / two-voice
floor behavior used privately since V163 is now exposed by the explicit opt-in
`lunar_voice_budget_init_burst_safety()`. Existing original, 85% headroom and
75% burst initializers retain their thresholds and four-voice floor. No default
call site or running dev-board image changes. The new headroom selector is3;
the private soak policy had patched selector2, so this is behavior equivalence,
not a claim of identical new native instructions.

[verified] Eight focused policy cases pass normally and with ASan/UBSan on
bounded Aeon (4 CPUs, 2 GiB). The original three policies retain their previous
10,000-observation recovery bounds; the new two-voice policy permits enough
observations for all ten increases. Exact boundary tests exercise strict65%
pressure, strict60% recovery and the1024-observation recovery delay. Refusal,
startup, saturation and repeated load/recovery ownership tests remain intact.
A separate private differential compares the legacy V163 transform and the new
named policy across1,800,000 observations in each normal/sanitizer run: every
state field except the intentionally distinct selector, cap decision and callback
cap agrees, with1210 decreases/1200 increases. There is no new hardware timing,
analog or fixed-polyphony acceptance. V176 remains the installed accepted test
image. Rarefaction cannot reach this external worktree from its main-checkout
root; Serena locates the new symbol in the actual worktree; file inspection and
bounded compiled proofs cover this change.

Evidence and lifecycle: v177-policy-integration under the existing private Aeon
lane retains small test/equivalence logs and the comparison inputs; temporary
compiler executables and pytest outputs clean themselves on exit. This is an
integration checkpoint toward reproducible experiments, not a new soak result.


### Four-voice floor comparison after burst fixes (V178, 2026-10-27)

[verified: failed timing trial] Restored the existing75% pressure/70% recovery
policy with initial12/floor4, retaining the same DSP, note order, three-cycle
workload, drain fix, steady idle and34829-tick deadline. All66156blocks and12
cases complete; producer maxima32584/31296/33171/37636. One producer deadline
miss occurs at tag38591, a heavy note-on transition. Its note/control/app/total
costs are4990/842/31764/37636ticks. Consumer misses and DAC fault/backend/late/
gap counters remain zero, drain64, steadyidle168 and worker finite exit. No
four-voice promotion: transport buffering completing without a gap does not
excuse a failed producer deadline. Board is healthy idle with ordinary PING ACK;
receivers both exited0 and exact PIDs are absent. Unique reset consumed forever.

[verified] Actual-decision normal and ASan/UBSan replay match all16935936PCM
bytes,12hashes,fold63171342 and2238controls. Finalactive4/limit4/shed0/stolen179.
This establishes exact replay, not timing or analog acceptance. Private125-second
KA6 capture is retained with equal Bench/Aeon hashes; no residual screen is run
for this already-disqualified timing trial. The successful V176 two-voice-floor
30.4-minute result is unchanged and must not be extended to four voices.

Next investigate the remaining app cost at that transition before claiming more
polyphony. Small receipts/replay logs and final build inputs are private in the
existing devkit lane; generated SDK/replay source copies are removed after the
result is recorded. No full backups/readbacks or restore rehearsals were used.


### Transition-only profiling points to Drums work (V179/V180, 2026-10-27)

[verified: diagnostic only] The first profiler added 768 bytes of RAM and
prevented a 1,536-byte allocation during DAC open. It never ran the workload.
UART remained responsive after its receiver exited. A new, unique attempt
retained counters for transition 7 only, saving 484 bytes; DAC startup then
succeeded with 3,540 bytes of heap remaining. No backups, restore rehearsals or
full readbacks were performed. Both reset receipts are permanently consumed.

[verified] The reduced profiler completed all 66,156 blocks and again missed
one producer deadline at tag 38,591: 35,424 ticks versus 34,829. Consumer misses
and DAC fault/backend/late/gap counters were zero; drain was 64, steady idle
169 callbacks, and the worker exited. Unused stack was 435 parent words and
1,322 worker words. UART exited zero, its PID was absent before ordinary PING
acknowledged, and no device operation remains live. No timing acceptance.

[verified, instrumented] At that transition, producer app time was 29,468 ticks.
Measured phases were preflight 56, setup/advance 1,281, dispatch 21,870,
inserts/mix 4,245, capture 471 and UI 1,501 ticks. The phase sum is 29,424;
timer hooks and surrounding glue account for the remaining interval. Inside
dispatch, CPU0 DX7 took 5,081 ticks (about 212 us), Drums 9,662 (about 403 us),
and the fourth sink 284; Macro recording took 81. These sink times overlap
dispatch and must not be added to it. They do not measure CPU1 Macro rendering.

[inferred next experiment] Drums is the largest measured CPU0 sink here. Split
its internal block generation from output resampling before choosing an exact
PCM optimization. The source generates native-rate drum blocks lazily inside
the output resampling loop; whether block-boundary alignment causes the spike
is not yet measured. Preserve its native rate, filter quality, RNG order and
voice lifetime. Do not assume the remaining issue is solely DX7 note setup.

This diagnostic changes code layout and adds hooks, so it also changes adaptive
decision timing: final active/limit 4, shed 3, stolen 176. No host replay or
analog acceptance is claimed for it, and its hashes are not compared directly
with a different decision trace. The V176 adaptive two-voice-floor soak remains
the bounded successful milestone. Final sources, ELF, UART and small reports
are private in the existing lane; generated SDK copies are removed after the
result is recorded. PR155 remains draft, open and unmerged.


### Drums conversion dominates the troublesome transition (V181, 2026-10-27)

[verified: private diagnostic] Reusing the spare V180 timer slot around Drums'
native RenderBlock adds no profiler buffer. The actual native source differs
only by the declaration and two timer calls; rates, filters, RNG, voice lifetime
and arithmetic remain unchanged. At ordinal7/tag38591, the Drums sink takes
9,709 ticks: 2,404 inside native generation (100.2us) and 7,305 outside it
(304.4us), about75percent for output conversion, surrounding glue and hook overhead.
These are nested spans, not additive work. This isolates a conversion-path lead;
it does not identify which FIR stage or establish removable cost.

[verified: target limits] All66,156blocks/12cases finish, with producer maxima
32,910/32,626/33,735/35,718ticks. One producer deadline miss remains at38591
against unchanged34,829ticks. Consumer late0; DAC fault/backend/late/gaps0,
drain64, worker finite exit; unused parent435words/worker1322. Instrumentation
changes timing/adaptive decisions, so no cross-trace PCM parity or analog
acceptance is claimed. The V176 adaptive two-voice-floor soak remains separate.

[inferred next step] Investigate exact conversion work without reducing filter
quality or repeating failed shared-weight/paired-unroll prototypes. Earlier V136
readiness specialization saved only about10..14us, insufficient by itself.
The diagnostic receiver exited normally and was absent twice before PING ACK;
the board is healthy idle. The one-shot reset is consumed. Final source, ELF,
raw UART and reports are private; the reproducible SDK copy was removed after
recording them. PR155 remains draft, open and unmerged.


### Three-voice adaptive floor still narrowly misses (V182, 2026-10-27)

[verified] A private65/60 policy trial raises only the V176 floor from2 to3,
initial limit12, with the same DSP, native rates, event order and34,829-tick
budget. Its66,156-block run finishes with maxima32,596/30,300/32,195/34,896:
one producer miss at tag38591 by67ticks (2.792us). Consumer late0 and DAC
fault/backend/late/gaps0, drain64, worker finite exit. Actual final active3,
limit3, shed0, stolen246; nine limit reductions are recorded. This fails the
short timing gate and is not advanced to a long soak. The125s analog capture
is retained privately but no analog acceptance is claimed. Both receiver and
capture exited normally and were absent twice before ordinary PING ACK.

[verified review] Astra found no supported large exact scalar converter shortcut:
the actual native low-pass already has its61 symmetric terms unrolled into
four chains. A copied FIR tile would need a new bounded service and timing
proof. Its report remains private. The smaller next trial reuses V136's
conversion-readiness specialization, which previously saved about10..14us but
could not close the much larger old gap. Current-header normal and ASan/UBSan
proofs match720,000 outputs and complete states across six rates. The first
proof harness omitted the now-shared coefficient definitions; adding the actual
native definitions fixed that harness link error. Native V183 app grows128bytes
and fits the existing range. These offline results do not establish target gain.
No production/default policy change or fixed-polyphony acceptance is implied.


### Three-voice adaptive trial passes; sustained test started (V183/V184, 2026-10-27)

[verified] Reusing the exact Drums readiness specialization with adaptive65/60,
initial12 and floor3 completes66,156blocks with producer maxima32,264/29,755/
32,129/34,379ticks and zero misses against34,829ticks. Consumer misses and DAC
fault/backend/late/gaps are zero; drain64 and finite exit. Normal and ASan/UBSan
replay of the recorded decisions match all12 hashes,2238 controls and16,935,936
PCM bytes. Final active3/limit3/shed0/stolen246. This is adaptive evidence, not
fixed12 acceptance. The earlier floor3 run without this specialization missed
once by67ticks; these single runs do not establish a sustained gain.

[verified start only] V184 changes only the run length from3 to57cycles, about
30.4minutes. After acknowledged UART recovery entry and application-only flash,
sole UART and KA6 capture were armed before one unique reset. The1900s analog
capture and1980s UART receiver are running; timing, replay and frozen analog
analysis remain pending. No backups, full readbacks or restore rehearsals were
performed. Reset receipts are consumed and cannot be retried. Private handoff
contains exact paths, process IDs and continuation steps. PR155 remains draft,
open and unmerged; no sustained or physical FM-1 acceptance is claimed.


### Sustained adaptive three-voice-floor pass (V184, 2026-10-27)

[verified] The57-cycle run completed228cases and1,256,964blocks in30.4minutes.
Producer maxima were32,694/31,636/34,080/34,523ticks, below the unchanged34,829
budget; producer and consumer deadline misses were zero. DAC fault/backend/late/
gap counters were zero, drain64 and worker finite exit. Unused parent435words
and worker1322. Adaptive65/60 started at12 and finished active3/limit3, with
nine limit decreases, shed0 and stolen4597. This is not fixed12 acceptance.

[verified] Normal and ASan/UBSan actual-decision replay match321,782,784PCMbytes,
all228 hashes, fold3989524113 and42,522controls. The1900s KA6 capture was scored
with the unchanged frozen stereo model/thresholds: every block aligned and zero
residual flags on either channel. Both final-eight-block endpoint checks pass.
Quiet and weak-signal detection sensitivity remains unqualified, so the bounded
claim is no detected analog residual anomalies for this adaptive dev-board
workload. This does not accept the physical FM-1 or every possible workload.

[verified lifecycle] Both receivers exited normally and were absent twice before
ordinary PING ACK. Final native ELF/source, raw captures, reports and reset
receipts remain private. Reproducible SDK copies and replay source/PCM were
removed after evidence was recorded. Next integrate the proven exact readiness
transformation into tracked code/preparation, preserve fixed-polyphony checks,
and follow required CI/review. PR155 remains draft, open and unmerged.


### Tracked opt-in Drums readiness integration (2026-10-27)

[verified source/host] The preparer now exposes `--drums-ready-convert`, gated
on resident unrolled outer-only preparation without separate outlining. Only
prepared Drums uses the unchecked conversion entry after supplying exactly its
required inputs. Other translation units retain their original checked path;
PASS/OFF fallback, FIR coefficients/grouping and engine rates remain unchanged.
Both prepared input hashes and the selected option enter the manifest. A named
`lunar_voice_budget_init_burst_safety_three` exposes the V18465/60 floor3 policy;
existing initializers retain their policies. Neither option is enabled by default.

[verified checks]31 focused tests passed on bounded Aeon, including the full
11,290,624-byte shared-renderer PCM comparison and existing/new policy tests.
The whole-renderer comparison also passed ASan/UBSan with the existing shift
exception. Independent review found a source-drift risk in signature-only
validation; exact reviewed Render/needed/push bodies and body-mutation tests
now fail closed. Nine affected checks then passed. Converter tests compare
720,000 outputs and complete states byte-for-byte against a separately compiled
original implementation across six rates, normal and sanitizer builds, including
checked unready and OFF behavior. An initial test applied FIR unrolling after
specialization; it was corrected to the actual preparation order. Firmware
preparation ordering did not change. These are source/host results: the named
tracked integration has not been built or installed as a new target image.
PR155 remains draft, open and unmerged pending CI/review and further integration.


### Tracked readiness native confirmation (V185, 2026-10-27)

[verified] The tracked readiness helper and named three-voice-floor initializer
were built natively, preserving V184's steady-idle/drain behavior, then installed
with acknowledged UART recovery and an application-only flash. The short run
completed 66,156 blocks and 12 cases: producer maxima 32,605/30,290/31,947/34,084
against the unchanged 34,829 ticks, with zero producer or consumer deadline
misses. DAC fault/backend/late/gaps were zero, drain64 and finite worker exit.
Unused parent435words/worker1322words. Adaptive65/60 began at12, ended active3/
limit3 with no rejected note-ons and246 steals. This is not fixed12 acceptance.

[verified] Normal and ASan/UBSan actual-decision replay matched16,935,936PCMbytes,
all12case hashes, fold3572433538 and2238controls. Frozen stereo analysis of the
125s KA6 capture aligned all66,156blocks/channel with zero residual flags; both
final-eight endpoint checks passed. Quiet/weak sensitivity remains unqualified;
this confirms the tracked preparation on this workload, not universal continuity
or production/physical-FM1 acceptance. The prior V18430.4min evidence is retained.

[verified lifecycle] Sole UART/capture exited0 and were absent twice before
ordinary PING ACK; no operation remains live. Private final sources/ELF, raw
captures, logs/reports and reset receipt retained. Generated SDK/replay source/
PCM and local candidate transit copy removed after results; Mac1145GiBfree.
Source05fdf14a's CI40521857180 remains pending/inprogress, no failures observed;
Pages40521857240 lastinprogress. No passing checks rerun. PR155 draft/open/unmerged.
Next integrate proven runtime behavior into the tracked production preparation
and exercise wider workloads without conflating adaptive and fixed-polyphony.

## 2026-10-27: tracked pipeline backend extracted from V185

[verified] Added opt-in `renderer_pipeline_sdk.{c,h}` and the renderer make
selector, preserving the V185 work/output ownership, wake ordering, permanent
refusal and retained-storage behavior. Removed experiment-only timing traces
and canary tasks. No default build, application adapter or preparer enables the
backend yet. The existing whole-engine/FM6 SDK workers conflict explicitly.

[verified] Astra compared the native protocol with V185 and found no unintended
protocol/lifetime changes. Its API review caught missing wake/ready declarations
that an implementation-including fixture concealed. Namespaced declarations,
task-only ownership and drain-before-predicate contracts now accompany separate
C11/C++11 header-client compile checks. Eight focused tests passed on bounded
Aeon (1.33 s): normal and ASAN/UBSAN protocol streams/faults, one-worker build
selection/refusal and separate header clients. The exact tracked C compiled to a
15324-byte pi32v2 object. No linked image, flash or new target measurement was
performed; host atomics/pthreads do not establish native race/cache/IRQ/stack
acceptance. Private logs and compiler receipt remain in the campaign lane.

Next: move the proven producer/consumer application adapter and continuous DAC
steady-idle/drain path into tracked preparation, preserving the scoped adaptive
floor-three policy and fixed-polyphony comparison distinction. V185 remains the
healthy idle installed image; all previous reset attempts remain consumed.

## 2026-10-27: sealed app pipeline interface integrated

[verified] Extracted V185's app-level producer/consumer ownership into opt-in
`FM1_APP_RENDER_PIPELINE`, with a public header and permanent-refusal hooks.
Removed private file-trace/edge-test instrumentation and phase observers. Default
rendering remains the original path. No task, preparer or DAC adapter enables the
new interface. The fixed Macro-model-0/Drive ownership and ordered summation,
copied control/events, master/amp/click/limiter destinations remain explicit.

[verified] The extraction required the private metronome-snapshot helper:
`fm1_seq_click_mix_on` now accepts the sealed block setting, preserving click
history/arithmetic without reading an advanced live sequencer. The original
`fm1_seq_click_mix` is unchanged. Astra identified reinitialization and UI draw
entry points that could touch worker-owned state before refusal; initialization
now refuses once bound, and draw/draw_checked require a drained barrier. Observer
builds refuse rather than sharing unproven observer state across cores.

[verified] Bounded Aeon normal and ASAN/UBSAN tests pass. Each compares the
original renderer with immediate and one-block-delayed consumers across 44,104
blocks (22,581,248 float PCM bytes per run), including metronome/master/modulation
edits. All three PCM outputs match exactly in each build. Seven negative cases
refuse: alias, duplicate production, early retirement, worker parameter edit,
reinitialization, draw and checked draw. Sanitizers retain the existing known
shift exception; these host tests do not establish native cache/IRQ/stack/timing
or new analog acceptance. V185 remains the installed healthy idle image.

[verified] Final Astra review found no remaining source blocker for this bounded
opt-in arrangement. Actual default WASM rebuild passed all 108 parity scenarios;
module bytes are unchanged and the generated source record is updated. Strict
CI-mode committed-WASM record check passes. No screenshot/Chromium acceptance
was requested or claimed. Next dependency is the native live/DAC adapter and
platform hook integration, with the reviewed SDK scheduler correction retained.

## 2026-10-27: tracked live producer/consumer adapter

[verified] Opt-in renderer_pipeline_live connects the sealed app interface to
backend callbacks, preserving V185 note/control order, startup fade, conversion,
four-channel duplication, cumulative fault counts and per-case stereo hash.
It bounds cycles to 1–57 and rejects repeated bind, out-of-order/duplicate output
and malformed case metadata. Direct serial rendering permanently refuses in
pipeline mode. SDK/error hooks now connect to permanent backend refusal.

[verified] Bounded Aeon normal and ASAN/UBSAN replay both pass: 44,104 blocks,
22,581,248 int16 PCM bytes each for original/immediate/delayed paths, identical
PCM and final status in each build. Negative metadata, repeat-completion, cycle
bounds and producer-tag guards run in both paths; direct serial entry refuses.
The known shift sanitizer exception remains. Synchronous test transport is not
native concurrency, IRQ, timing, cache or analog proof. No device operations.
Default rendering and fixed polyphony remain intact. No adaptive controller is
enabled by this adapter; no DAC/preparer/runtime activation yet.

[verified source review] Astra compared ordering/conversion/hash and ownership
with V185; no blocking semantic difference. The continuous DAC adapter, reviewed
SDK scheduler correction and native placement remain the next dependencies.

## 2026-10-27: continuous DAC pipeline extracted into tracked source

[verified] Added opt-in renderer_pipeline_dac and the exact startup window-zero
helper. The tracked driver preserves held initial outputs, gain settling,
three-window lease order, hash checks, 64-zero drain and continuous zero-idle.
It starts/finishes its own finite backend; failures poison admission without
freeing pending state. Direct activation remains absent from the preparer/default
boot path. Fixed twelve voices is default; adaptive floor3 is a separate define
using the existing measured controller. The success gate also rejects producer
or consumer late blocks, without changing the 34829-tick deadline.

[verified] Actual callback body under mock DMA/leases passes normal and
ASAN/UBSAN: nine arm offsets / 198468 ordered blocks, exact PCM/hash, zero preroll
retirement, drain/idle and malformed/queue/metadata/channel/hash/retirement faults.
Both live adapter replay tests and the strict WASM record check pass. Two DAC
make selectors pass. Vendor compilation with LTO disabled yields native ELF
objects: fixed driver13248B, adaptive driver16036B, live adapter8696B. No image
linked, installed or hardware tested this checkpoint. No new analog acceptance.

[verified source review] Astra comparison found no functional source blocker.
Its advisory-count ownership finding was resolved by excluding the local IRQ
around the task's read-only count query. SDK scheduler correction, whole-image
SRAM placement, startup/device timing and independent analog replay remain
required. Private V184/V185 target results retain their exact-image scope.

### Tracked SDK worker pipeline routing (2026-10-27)

[verified] The opt-in DAC pipeline now has a tracked SDK-worker entry. The
200-tick UART recovery window and arithmetic preflight precede its sole driver
invocation. The driver owns backend start/finish; the worker retains TIMER4 and
parks after either return, preserving continuous DAC idle and late-worker storage.
Conflicting workload flags fail compilation. Pipeline recovery priority is 18.

[verified] Five bounded Aeon tests pass: actual worker success/failure/arithmetic
failure routing, existing recovery-before-crashing-init handshake, receiver
startup/allocation faults at priority8, scheduling18 and pipeline18. Temporary
harness files are removed after the result. These SDK mocks do not establish
native scheduling, IRQ/cache/stack, linked placement or new analog acceptance.
No preparer flag or board operation is activated by this checkpoint.

### Reproducible tracked pipeline preparation (2026-10-27)

[verified] Added a separate offline pipeline preset, avoiding the legacy
experiment rewrite chain and nested engine queue. Original pinned SDK and
explicit reviewed private scheduler archive hashes are required before staging;
only the newly copied SDK changes. Vendor archive/IR remain private. Fixed12 is
the default; floor3 and 1..57 cycles are explicit options recorded in the receipt.

[verified] Six bounded full-source synthetic-SDK preparation tests pass for fixed
and adaptive modes, original-input preservation, source manifest, pre-include
build flags, CPU0 parent/UART priorities, hot paths, exact retained eight DX7 XIP
functions and bad-input refusal. First native full link passed before final XIP
placement correction. Broad historical cold-constructor experiments were checked
and excluded because the retained successful pipeline did not use them. Final
native placement/link and fresh target results remain pending; no board action.
