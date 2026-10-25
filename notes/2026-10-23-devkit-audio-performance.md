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
