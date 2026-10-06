# 04 — Prior art and sources

Everything this project stands on, what each source contributes, its license,
and how far it got. Check these before re-deriving anything.

## 1. FM-1 specific

### aroum/fm1-custom-fw — https://github.com/aroum/fm1-custom-fw
*No license stated. Read at `d08360f` (2026-08-21); `main` at `4e9d6d3`
(2026-10-04) when checked on 2026-10-05, see the last bullet.*

- Identified the SoC as JieLi AC791N (WL82) and the JL_AC79_DevKit V1.0 as its
  reference board (Taobao).
- Reverse-engineered the **macOS** `M-UPGRADE-FM1.app`: Qt6 + RtMidi, firmware
  embedded as `usb_hid_ota.bin` with `@JMUA`/`JLUFW` signatures, no asymmetric
  signature, SysEx command families `0x01/0x02/0x03/0x04/0x58`.
- Teardown photos (`photos/`) and case-opening instructions; the observation
  that the PCB has **no debug pads and no recovery button**.
- `fm1_flasher.py` (mido/python-rtmidi; extracts the embedded firmware,
  flashes, uploads presets) and `fm1_sysex_scanner.py` — **untested on
  hardware**, by the author's own warning.
- Fuzzing result: the device answers identity item `0x40` only.
- **Caveats found here (2026-09-06, reported as their issue #2):** the
  README's offsets describe the *end* of the embedded package (`@JMUA` sits 308
  bytes before `JLUFW`), so `extract_embedded_firmware()` returns the package
  tail plus unrelated executable bytes; and `flash_firmware()` uses a
  `cmd_type`/MSB-flag framing that does not match the device-pull protocol
  AL-255 captured and Echomatter used on hardware. The identity query is
  correct.
- Links: firmware V15 on Aliyun, r/synthdiy teardown thread, esp8266.ru JieLi
  thread, fm1-editor.com, openpatch.es.
- **README links to this project (since 2026-09-13; commits `cb5796c`,
  `d988b84`, `4e9d6d3`) [verified 2026-10-05: GitHub API].** `cb5796c`
  adds a mask-ROM recovery route to the hardware section and a reference to
  this repository (under its old name): it describes the RP2040 design in
  `dongle/` as forcing `UBOOT1.00` through the USB-C port, enabling flash
  backup and unbricking. The later two add Baud Girl's FM-1+VA, Felucca and
  Lunar Modulator (as research and bench stage) under a new "Custom &
  Alternative Firmwares" section. What is established: this project's dongle
  is implemented and simulated and its UF2 is built in CI, but no unit of it
  has been assembled or run against an FM-1 (docs/10, `dongle/README.md`); a
  different, simpler Pico tool by czietz reaches UBOOT mode on two FM-1s,
  czietz's own and masanaohayashi's, and masanaohayashi reports a firmware
  backup and a write with it [reported: issue #2, docs/10 §1.1]; no dongle
  has yet shown a dump and a byte-identical restore on this project's unit
  (docs/07 §4).

### AL-255/FM-1-RE — https://github.com/AL-255/FM-1-RE
*WTFPL. Read at `main` `95eca84` (2026-08-16) and PR #2; `main` at
`ec832f2` (2026-09-08, the merge of PR #2) and `with-custom-firmware` at
`628fcaf` (2026-08-02) when checked on 2026-10-05.*

The deep one. `main` is analysis only; `with-custom-firmware` preserves the
experimental firmware and package builders.

- Firmware images V13 (`FM-1_009`) and V14 (`FM-1_014`) unpacked, with vendor
  `objdump` listings, function databases (2062 entries), string tables, a
  byte-identical reassembly of V13, and Ghidra headless scripts for pi32v2.
- 25 documents: architecture, boot/CRT, RTOS, audio DAC, synth engine, MIDI,
  USB, input, display, storage, Bluetooth, OTA protocol, toolchain, hardware
  map, function index.
- **OTA protocol byte-verified** against live captures of the Windows updater
  under Wine; decompiled updater worker; extracted and disassembled the
  on-device OTA loader (`usb_hid_ota.bin`, 23324 bytes at `0x01C0A800`) and
  traced its finish gates; mapped it to the SDK's `updata_mode` framework.
- `tools/fm1_ota.py`: Linux client (`scan`, `flash`) over the ALSA sequencer
  with 14 offline tests at `95eca84` (22 at `ec832f2`, after PR #2); udev
  rule.
- Safety analysis (`TODO_aug2.md`, `analysis/device/debug-surfaces.md`): no
  UART shell, no CDC, no factory mode, no recovery chord; PB01 is a reset, not
  recovery; single-bank layout; **verdict NO-GO for non-stock flashing**.
- On-device probing of the step-1 verifier (2026-07-21): cfg gate bypassed,
  19456-byte loader staging limit found, `ota.bin` accept gate still unexplained.
- `with-custom-firmware` branch: `firmware/` = a pi32v2 demo blob (basic synth,
  LCD overlay, hooks that trampoline from the stock app task via
  `demo_install()`), a Synth_Dexed/`EngineMsfa` port with host builds (ALSA,
  JACK, LV2, VST2), `link.ld` placing the blob at XIP `0x02046600` with RAM at
  `0x01C30000`, `tools/build_fwsc.py`/`build_image.py` package builders,
  quarantined `legacy-uboot` scripts. Built with the real JieLi Linux toolchain.
  **Not flash-ready**; last device test stopped at the `0xE0000000` signal with
  stock still installed.
- **PR #2 by Echomatter (opened 2026-09-05, merged 2026-09-08):** fixes the
  partial-block response framing, adds the plain V15 identity parse, and
  documents a hardware-verified rollback from a modified `FM-1_016` package to
  stock V15 over USB-MIDI (`docs/io/12-v15-reflash-proof.md`, redacted request
  record, `tools/verify_reflash_record.py`, 27 tests). First non-stock package
  known to have run on an FM-1. Our 2026-09-06 identity capture decodes
  correctly with its parser and did not with `main`'s before the merge.
- **Our engagement (2026-09-06):** hardware confirmation of the plain
  identity parse posted on PR #2 (comment with the byte-exact `FM-1_015`
  reply and a fixture); V15 analysis on issue #1; **PR #3**
  (`ip2k/FM-1-RE`, branch `firmware-images-v15`) adds `firmware-images/v15/`
  in the V14 layout with a fork-side CI run that reproduces the unpack.
- Toolchain notes: `jieli-linux-toolchains-*` = Clang/LLVM 4.0.1 with
  `pi32`/`pi32v2`/`q32s` backends from `https://pkgman.jieliapp.com/s/linux-toolchain`;
  post-build tools from `.../s/linux-postbuild`. The vendor objdump decodes the
  `80 ff` long-call prefix that ghidra-jieli's SLEIGH mis-splits.

### probonopd — SMK-37 Pro notes
https://gist.github.com/probonopd/18b3ed65a69d0229eb630c47d7e316dc

Sibling M-VAVE product (DX7-style MIDI keyboard) on the same AC791N platform:
`.fwsc` unpacked with `jl-misctools/firmware/fwunpack_newfw.py` (needs
`crcmod`), partitions `uboot.boot` / `isd_config.ini` / `app.bin` / VM / USRFLASH
/ USR, chip key `980F`, product id `AC791N_STORY`, 1 MB flash, community
teardown identified AC7911BA (QFN48). Same conventions as the FM-1.

### fm1-editor.com — "M-VAVE FM1 Editor & Librarian" (benny-sparra)
https://github.com/benny-sparra/fm1-dx7-patch-importer — open source (no
license file), active (2026-09-07). Web MIDI editor/librarian using only
standard DX7 SysEx, program change and CC; **no vendor messages**. Its
`docs/fm1-research.md`, `docs/fx-003-hardware-verification.md`,
`docs/seq-001-findings.md` and `docs/sequencer-fixtures/V15/*.ndjson` are
careful, confidence-marked hardware notes (effects CC map verified on V15,
sequencer playback captures, the observation that the unit cannot send banks
back). `scripts/capture-midi.swift` is a CoreMIDI capture tool for macOS.
Summary in `notes/2026-09-08-desk-review.md` §2. openpatch.es is a general
DX7 patch tool.

### Baud Girl — FM-1+VA firmware — https://baudgirl.com/work/FM-1+VA
*Madeline's workshop label. `Copyright Baud Girl, 2026`; no source repository
linked, so treat it as all rights reserved. Active: `FM-1_092` released
2026-09-29.*

The first third-party firmware for the FM-1 that ordinary users install.
Details and marks are in `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`.

- **What it is**: a binary patch of V15 that adds a "Virtual Analog" engine
  (supersaw-style unison, sub, noise, PWM, drift, a LP12/LP24/BP/HP filter
  with its own envelope, also usable on FM presets), a 64-step sequencer with
  real-time recording, MIDI CC control and colour themes. **[verified,
  `FM-1_092`]:** V15's `app.bin` byte for byte except 1,820 bytes in 90 hook
  sites, plus 110 KB of new code appended; VM moved to `0xD9000` and shrunk
  to 64 KB for room; head, OTA loader and `cfg` untouched; msfa table intact.
  The owner's unit runs it (identifies as `FM-1_092`, 2026-09-29).
- **How it installs**: a Web MIDI installer in Chrome/Edge, ported from
  AL-255's `fm1_ota.py` with three fixes. It gates on the SHA-256 of V15's
  flash head, refuses a reinstall of the running version, and resumes an
  install whose synth is left in its loader (`ota-FM-1`). Rollback to M-VAVE's
  `.fwsc` goes through the same page. Accepted starting points are V15 or Baud
  Girl's own versions, which are numbered from `FM-1_020`.
- **What it settled for this project** (docs/03 §5): the step-1 gate is a
  same-version refusal, content is not authenticated, the OTA loader can
  rewrite `uboot.boot`, and an interrupted step 2 is resumable. All
  [reported], from Baud Girl's measurements.
- **What it has that we do not**: an FM-1 emulator used to test builds, a
  numbered FINDINGS document, and a preset read/write SysEx format (128-byte
  VMEM voice + 59-byte settings record) in its own firmware. None of these are
  published.
- **Privacy note**: the install and presets pages send progress events,
  failure traces and script errors to `baudgirl.com/api/event`, tied to the
  site's visitor cookie.

### Felucca (hugelton / Hügelton Instruments) — https://github.com/hugelton/Felucca
*v1.0 at `727f272` (2026-10-05). **GPL-3.0-only**, except `firmware/src/fm6_core.c`
(Apache-2.0, an integer C port of msfa) and `phys_dsp.c`/`phys_symp.c` (MIT).
Read here, not built or run.*

- **What it is**: complete, from-scratch, bare-metal replacement firmware for
  the FM-1: four tracks, 13 engines including FM6, eight voices, a 64-step
  sequencer with songs, an arpeggiator, a modulation matrix, effects and a
  web editor. One core, integer only, no BLE (the author lists BLE as a "v2"
  goal) [verified: source; reported: running].
- **How it installs**: a Web MIDI page; the first install goes through stock
  step 1 from V15 with Felucca's own loader as `ota.bin`, which writes only
  the app area. A running Felucca answers the update protocol itself and
  accepts only its own loader or M-VAVE's (recognised by CRC, with a head
  equal to the device's). "Return to official V15" takes only M-VAVE's
  `FM-1.fwsc` [reported: users' issues #1–#41; source verified]. Identities
  `FM-1_900` and `FM-1_9XY` (1.0 is `FM-1_910`).
- **What it settled for this project**: the board's pin map (docs/01 §3.1),
  that stock step 1 accepts a foreign loader (docs/03 §5), RAM that survives
  resets, and a worked design for DEVELOPERS.md's I13.
- **What we may take**: facts and ideas, restated with credit; code only from
  the Apache-2.0 and MIT files, in `third_party/` with `UPSTREAM.md`.
- Details: `notes/2026-10-05-community-repos.md` §2.2.

### FM-1-transporter (kurogedelic) — https://github.com/kurogedelic/FM-1-transporter
*`a632d92` (2026-10-01). **MIT**, "Copyright (c) 2026 kurogedelic". Read
through the GitHub API, not cloned or run.*

- Felucca's recovery tool: a Seeed XIAO RP2040 on the FM-1's D+, D− and GND
  that keys `USB_KEY` `0x16EF`, then acts as USB host to `UBOOT1.00` through
  Pico-PIO-USB, so the Mac drives dumps and writes over CDC [verified:
  README].
- **Reports on FM-1s** [reported: `docs/PROTOCOL.md`, `docs/DEVLOG.md`]:
  polarity A only (D+ clock); `UBOOT1.00` as `4C4A:8057` `WL80UBOOT1.00`,
  SCSI `WL82`/`UBOOT1.00`; JEDEC `0x856014`; raw flash reads; keying works
  after a watchdog reset; stock V15 obeys the soft key `F0 22 24 35 7D F7`;
  sector writes in `[0x4000, 0x93000)` with verify.
- **Not for this project's unit as built**: it drives push-pull with no
  series resistors (`usb_key_pp`, `set pindirs, 3`) against docs/10's E1,
  and its `fm1t.py` sends the soft key by itself when it sees V15 [verified:
  `pio/usb_key.pio`, README]. Its PIO-USB host idea is a candidate for
  `dongle/` (docs/10 §1.1).

### fm1-nes (Keitark) — https://github.com/Keitark/fm1-nes
*`main` at `870f305` (2026-10-03). Apache-2.0 root; GPL-3.0-only USB audio
and packet code; MIT `jl_formats.py` cipher routines, jl-uboot-tool guard
patch and `examples/fablenes/`. The board constants are copied from stock
FM-1_010, by the author's account.*

- An NES emulator (PeakRacing core) as an AC79 SDK app, with FM-1 board
  support, a CDC diagnostics port, an app-only packager and a sparse sector
  planner. Windows-only tooling.
- **How far it got** [reported: `VALIDATION.md:49-75`]: on 2026-10-03 a
  217,680-byte app went onto the maintainer's V14 unit through mask ROM (51
  changed sectors, directory last, one full readback); CDC and UAC enumerated
  and telemetry ran; the CDC `UBOOT` command entered mask ROM without a
  dongle. Screen, sound and controls not yet accepted.
- **What it settled**: SDK `e30b1ee` libraries plus a 6→23-word
  `boot_info` bridge boot under the FM-1's SPL; SMP with `CPU_CORE_NUM 2`
  boots; stock's power values and audio route (docs/01 §3.1); a cache-RAM
  window [reported].
- **What we may take**: the Apache-2.0 board code and the MIT guard patch,
  in `third_party/` with `UPSTREAM.md`; the stock-derived tables only as
  cross-checks, re-derived from our own V15 disassembly.

### SLOOP (isod89) — https://github.com/isod89/sloop-fm1
*v2.2 at `f2b44c2` (2026-10-04). **GPL-3.0-only**. Read here, not built or run.*

- A four-track live groovebox forked from an earlier Felucca: three synth
  tracks and a drum track, nine engines, a sequencer and looper, song mode, a
  web editor and installer [verified: source; reported: running].
- **Adds beyond Felucca** [verified: source]: the loader checks the CRC16 of
  the whole served `flash.bin` and refuses a flash whose JEDEC ID is not
  `0x856014`; a `.noinit` boot guard leads two failed boots to a USB rescue
  mode and then to UBOOT; the installer checks SHA-256s.
- Every version reports `FM-1_900`. Rollback to V15 confirmed by the author
  (issue #8); Baud Girl's installer refuses to go from SLOOP to FM-1+VA
  [reported].
- **What we may take**: facts and UI ideas, with credit; no code.

### M-VAVE official downloads
https://www.m-vave.com/download lists the V15 `.fwsc` (2026-07-30) as the
latest PC firmware, V14 updaters for Windows/macOS, release notes and the
**"FM-1 MIDI CONTROL" guide** (EN/CN; the EN `.docx` is at
`https://yms-file-store.oss-cn-hongkong.aliyuncs.com/software/releaseNote/firmware/FM-1%20MIDI%20EN.docx`):
channels, CC 0–23 effects map, real-time messages, single-parameter SysEx.
No V16 as of 2026-09-08.

### Community threads (not reachable from the sandbox)
- r/synthdiy teardown: https://www.reddit.com/r/synthdiy/comments/1vgotwe/comment/p3gk1ko/
- Elektronauts: https://www.elektronauts.com/t/m-vave-fm-1/252170
- Gearspace: https://gearspace.com/threads/m-vave-fm-1.1465371/
- Synth Anatomy news (2026-07, V15) and review; "patch librarian" article.
- Firmware Radar version history: https://fwradar.com/p/m-vave-fm-1
- Manufacturer page: http://www.cuvave.com/product?id=fm-1 ; manual PDF via
  Amazon (`m.media-amazon.com/images/I/A1WOydif9HL.pdf`) — states 1.54" TFT with
  oscilloscope view, SELECT / PRESETS / ALGORITHM encoders, DX7 bank import.

## 2. JieLi platform

### kagaimiq — the JieLi reverse-engineering corpus
- **jielie** (docs): https://github.com/kagaimiq/jielie — chip families and
  codenames (WL82 = AC791N), pi32/pi32v2/q32s ISA with opcode tables, data
  formats (`newfw.md`, `jlfs.md`, `bankcb.md`, `sdkcfg.md`), peripherals
  (br17/21/23/25-era: spi, uart, adc, sfc, usb-fs, p33 PMU/RTC…), **ISP docs**
  (`isp/usb/usb-key.md`, `isp/uart/uart-key.md`, `isp/isp/isp-key.md`), USB
  VID/PID list. Rendered at https://kagaimiq.github.io/jielie/ (blocked from
  the sandbox; the repo was cloned instead).
- **jl-uboot-tool**: https://github.com/kagaimiq/jl-uboot-tool — dumper/flasher
  for chips in USB download ("UBOOT1.00") mode over SCSI vendor commands;
  `jldevfind.py`, `jlrunner.py`, `jluboottool.py`; loader blobs incl.
  **`wl82loader.bin`** (load address `0x1C02000`, protocol v2, "MengLi" memory
  cipher quirk). WL82 listed as **"unknown"** (present but untested); at
  `adb3f18` it works on FM-1s with 256-byte I/O [reported: fm1-nes's guard
  patch; our clone's loader is the same file, verified by hash].
  `docs/how-to-enter-uboot.md`, `usb-protocol.md`, `usb-loader-v2.md`.
- **jl-misctools**: https://github.com/kagaimiq/jl-misctools — `fwunpack_newfw.py`
  and friends; unpacks `FM-1.fwsc`.
- **ghidra-jieli**: https://github.com/kagaimiq/ghidra-jieli — SLEIGH processor
  module for pi32/pi32v2/q32s (needs the `80 ff` long-call fix).

### czietz — a Pico `USB_KEY` dongle for the FM-1
- **"Quick and very dirty JieLi UBOOT tool"**: an unlisted gist from
  2026-09-27, https://gist.github.com/czietz/9a94cf3c3e68f2ceb45fab682e1cbbd5, which czietz linked in issue #2 on this repository
  (https://github.com/ip2k/mvave-fm1-open-firmware/issues/2).
  - MicroPython on a bare Raspberry Pi Pico. It sends the key with SPI1 at
    50 kHz, clocked on D+, then fakes the SOFs with a 1 kHz square wave on D+.
  - czietz reports it gets their FM-1 into UBOOT mode, about one power-on in
    two.
  - masanaohayashi reports that it put their FM-1 into boot mode, and that
    they then backed up and wrote its firmware.
  - The gist gives `WL80UBOOT1.00` as an example of the name shown on the
    PC.
  - No licence.
  - What it shows for this project: docs/10 §1.1.

### JieLi (Zhuhai Jieli Technology) official
- **fw-AC79_AIoT_SDK** — https://gitee.com/Jieli-Tech/fw-AC79_AIoT_SDK
  (GitHub mirrors: `jeffreywugz/fw-AC79_AIoT_SDK`, `amitv87/fw-AC79_AIoT_SDK`,
  branch `release/AC79NN_SDK_V1.0.3`; the stock FM-1 SPL matches the later
  `AC79NN_SDK_V1.1.9_2023-08-01`). **Apache-2.0** LICENSE file.
  Inspected here (blobless clone, 10917 files):
  - `cpu/wl82/`: `sdk_ld.c` / `sdk_ld_sfc.c` / `sdk_ld_sdram.c` linker scripts,
    `setup.c`, `debug.c`, `liba/` with **~110 closed `.a` libraries** (among
    them `cpu.a`, `system.a`, `event.a`, `fs.a`, `common_lib.a`, `update.a`,
    `cfg_tool.a`, `btctrler.a`, `btstack.a`, `audio_server.a`, `ui.a`,
    `ui_draw.a`, `font.a`, `lib_usb_syn.a`, `lib_reverb_cal.a`, Wi-Fi libs,
    codecs, cloud SDKs).
  - `cpu/wl82/tools/`: `isd_download.exe`, `ufw_maker.exe`, `fw_add.exe`,
    `download.bat` (`isd_download.exe isd_config.ini -tonorflash -dev wl82
    -boot 0x1c02000 … -uboot uboot.boot -app app.bin cfg_tool.bin …`),
    `isd_config.ini`, `uboot.boot`, `ota.bin`, `usb_update2.bin`,
    `sd_update2.bin`, **`wl82loader.bin`**, `AC791N_config_tool/`, and a
    **`jtag/`** folder (`DebugServer.exe`, `loader_jtag.bin`,
    `isd_config_debug.ini`, `download_jtag.bat`) — JieLi's proprietary 2-wire
    debug TAP (`sdtap` options in the ini: `PA9/PA10`, `USB`, `PB1/PB2`, `PB6/PB7`).
  - `include_lib/driver/cpu/wl82/asm/WL82.h`: the **register map**, plus
    per-peripheral headers (`dac.h`, `spi.h`, `uart.h`, `usb.h`, `gpio.h`,
    `adc_api.h`, `sfc_norflash_api.h`, `p33.h`, `clock.h`, `hwaccel.h`, …).
  - `apps/demo/demo_hello` (task table, `app_main`, `board.c` for wl82),
    `demo_audio`, `demo_ble`, `demo_ui`, `demo_wifi`, …; `Makefile` documents
    the Linux build (`/opt/jieli/common/bin/clang`, `-target pi32v2`, LTO via
    `pi32v2-lto-wrapper`, `--plugin-opt=-pi32v2-*`).
  - `doc/datasheet/AC791N规格书/`: AC7911B, AC7913A0/A6, AC7915A, AC7916A
    datasheets and reference schematics (Chinese).
  - `doc/AC79NN_SDK_发布版本信息.pdf`: release notes.
  - **Update, 2026-10-05** (`notes/2026-10-05-community-repos.md` §2.1):
    Gitee is reachable, if flaky, and current to V1.2.13: branch
    `release/AC79NN_SDK_V1.2.0` at `e30b1ee` (2026-06-09) is tag
    `AC79NN_SDK_V1.2.13_2026-04-20` plus a README change. Our pin stays tag
    `AC79NN_SDK_V1.1.9_2023-08-01` (`8eae664`). The GitHub mirrors are stale
    (`amitv87` stops at 2024-07; `jeffreywugz` carries V1.0.3), so cite Gitee
    by commit. From V1.2.7, `system.a` carries `sdk_meky_check`, and V1.2.13
    adds `sdk_chip_key_verify_v2` [verified: strings per tag]. V1.2.12 added
    a Linux `isd_download` flow (`cpu/wl82/tools/download_linux.c`,
    `init_env.sh`).
  - **Branch `AC791N_OTA_loader`** at `79eda0c` (2025-09-13): Code::Blocks
    projects for every `ota.bin` loader, including `usb_hid_ota`, the likely
    template of the FM-1's loader [inferred; strings and load address
    verified]. Its `update_main.c` is the device-pull step 2 of docs/03.
- **fw-Bootloader** — https://github.com/Jieli-Tech/fw-Bootloader — Apache-2.0
  "user boot" source producing `uboot.boot`, supporting **AC791N (wl82)** among
  others; custom serial and USB-HID upgrade paths. Makes the SPL layer
  replaceable with open code.
- **fw-AC63_BT_SDK** — https://github.com/Jieli-Tech/fw-AC63_BT_SDK —
  Bluetooth SDK for the AC63/AC69 families; the FM-1's `JL-BR22`/`INCLUDE_BTSTACK`
  stamps point at this lineage. Issue #211 documents the Linux toolchain setup
  pain (`pkgman.jieliapp.com`, `/opt/jieli`, missing post-build tools).
- **Android-JL_OTA / iOS-JL_OTA / JL_OTA_Flutter / HarmonyOS-JL_OTA** —
  Apache-2.0 BLE OTA client SDKs (the FM-1 app references `ble_ota.bin`).
- **"JL USB Updater" / forced-upgrade dongle (强制升级工具)**, V2.0–V4.0: the
  vendor's `USB_KEY` dongle, US$8–18 (AliExpress 1005007090348648 and
  1005009768042266, GoldSupplier p173085127, JieLi's Taobao shop); manual at
  https://manuals.plus/ae/1005009768042266 (USB 2.0 port, no hubs, target
  powered while attached, Windows batch tools). Named for built-in-flash chips
  in the WL83 docs: https://doc.zh-jieli.com/AC792/zh-cn/wifi_video_master/getting_started/preparation/update.html
- Documentation portals: https://doc.zh-jieli.com/AC79/zh-cn/release_v1.0.3/
  and https://doc.zh-jieli.com/Tools/zh-cn/dev_tools/build_download/ ;
  toolchain downloads http://pkgman.jieliapp.com/doc/all .

### Other JieLi community work
- esp8266.ru JL SoC thread (Russian): https://esp8266.ru/forum/threads/jl-soc.5500/
  — years of notes on boot activators, USB/UART/ISP keys, programmers.
- Madushan, "Reverse Engineering Jieli SDK" (2025-08-09):
  https://madushan.caas.lk/posts/2025-08-09-reverse-engineering-jieli-sdk/
  (blocked from the sandbox; search snippets say the toolchain is LLVM 4.0.1
  based and targets only JieLi chips).
- DanMaxic/jielie-rev — a fork/mirror of kagaimiq's docs.

## 3. FM engine lineage

| Project | Role | License |
| --- | --- | --- |
| google/music-synthesizer-for-android (msfa) | the DX7 core: `fm_core`, `fm_op_kernel`, `env`, `lfo`, `pitchenv`, `freqlut`, `sin`, `exp2`, `dx7note` | Apache-2.0 |
| asb2m10/dexed | desktop plugin; the msfa files with fixes (algorithm 4/6 feedback) | GPL-3.0 overall, msfa files Apache-2.0 |
| dcoredump/Synth_Dexed (Codeberg) | library port for MCUs; `EngineMsfa` bit-accurate, `EngineMkI`, `EngineOpl` | GPL-3.0 overall, msfa files Apache-2.0 |
| dcoredump/MicroDexed (Teensy), probonopd/MiniDexed (bare-metal Raspberry Pi) | embedded hardware synths built on it | GPL-3.0 |

AL-255's `docs/03-dx7-core-identification.md` and this project's
`tools/check_msfa_table.py` establish that the FM-1 runs this engine.

## 4. Ableton Move side

- charlesvestal/schwung — https://github.com/charlesvestal/schwung — MIT.
  "Shadow UI" injected into Move's process; modules are aarch64 `.so` plugins;
  installer over SSH; module catalog at schwung.dev.
- DimaDake/schwung-movy — https://github.com/DimaDake/schwung-movy — MIT;
  read for this study at `5627d51` (2026-09-05, `module.json` 0.31.0; the
  v0.31.0 tag is `675054f`), and the sequencer port is pinned to `9190e79`
  (docs/13). TypeScript/JS UI (~26k lines) running in Schwung's QuickJS
  context plus a Rust engine (`seq-core` ~9k lines, `movy-dsp` ~7k lines) built as
  `dsp.so`. See docs/06.
- Ableton Move hardware: quad-core ARM Cortex-A72 at 1.5 GHz, 2 GB RAM, 64 GB
  storage, Linux (Ableton tech specs; teardown coverage).

## 5. What was cloned and inspected for this study

`aroum/fm1-custom-fw`, `AL-255/FM-1-RE` (both branches), `kagaimiq/jielie`,
`kagaimiq/jl-misctools`, `kagaimiq/jl-uboot-tool`, `DimaDake/schwung-movy`,
and a blobless clone of `jeffreywugz/fw-AC79_AIoT_SDK`. Vendor firmware images
were inspected in AL-255's checkout and are not redistributed here.

On 2026-10-05, shallow read-only clones of the Gitee AC79 SDK (`e30b1ee`,
sparse) and its `AC791N_OTA_loader` branch (`79eda0c`), `hugelton/Felucca`
(`727f272`), `Keitark/fm1-nes` (`870f305`) and `isod89/sloop-fm1`
(`f2b44c2`); FM-1-transporter (`a632d92`) was read through the API. Nothing
was built, run or sent to a device (`notes/2026-10-05-community-repos.md`).
