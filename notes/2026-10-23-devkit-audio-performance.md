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
