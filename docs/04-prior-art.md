# 04 — Prior art and sources

Everything this project stands on, what each source contributes, its license,
and how far it got. Check these before re-deriving anything.

## 1. FM-1 specific

### aroum/fm1-custom-fw — https://github.com/aroum/fm1-custom-fw
*No license stated. Last commit 2026-08-21.*

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

### AL-255/FM-1-RE — https://github.com/AL-255/FM-1-RE
*WTFPL. `main` last commit 2026-08-16, `with-custom-firmware` 2026-08-02.*

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
  with 14 offline tests; udev rule.
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
- **PR #2 by Echomatter (2026-09-05, open):** fixes the partial-block
  response framing, adds the plain V15 identity parse, and documents a
  hardware-verified rollback from a modified `FM-1_016` package to stock V15
  over USB-MIDI (`docs/io/12-v15-reflash-proof.md`, redacted request record,
  `tools/verify_reflash_record.py`, 27 tests). First non-stock package known to
  have run on an FM-1. Our 2026-09-06 identity capture decodes correctly with
  its parser and not with `main`'s.
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

- **What it is**: a modified V15 package whose application adds a "Virtual
  Analog" engine (supersaw-style unison, sub, noise, PWM, drift, a
  LP12/LP24/BP/HP filter with its own envelope, also usable on FM presets), a
  64-step sequencer with real-time recording, MIDI CC control and colour
  themes. The installer keeps the stock flash head, and the code refers to
  stock functions and RAM addresses. It extends V15's `app.bin` rather than
  rebuilding on the SDK [inferred from the installer's code comments].
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
  cipher quirk). WL82 listed as **"unknown"** (present but untested).
  `docs/how-to-enter-uboot.md`, `usb-protocol.md`, `usb-loader-v2.md`.
- **jl-misctools**: https://github.com/kagaimiq/jl-misctools — `fwunpack_newfw.py`
  and friends; unpacks `FM-1.fwsc`.
- **ghidra-jieli**: https://github.com/kagaimiq/ghidra-jieli — SLEIGH processor
  module for pi32/pi32v2/q32s (needs the `80 ff` long-call fix).

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
- DimaDake/schwung-movy — https://github.com/DimaDake/schwung-movy — MIT,
  v0.31.0. TypeScript/JS UI (~26k lines) running in Schwung's QuickJS context
  plus a Rust engine (`seq-core` ~9k lines, `movy-dsp` ~7k lines) built as
  `dsp.so`. See docs/06.
- Ableton Move hardware: quad-core ARM Cortex-A72 at 1.5 GHz, 2 GB RAM, 64 GB
  storage, Linux (Ableton tech specs; teardown coverage).

## 5. What was cloned and inspected for this study

`aroum/fm1-custom-fw`, `AL-255/FM-1-RE` (both branches), `kagaimiq/jielie`,
`kagaimiq/jl-misctools`, `kagaimiq/jl-uboot-tool`, `DimaDake/schwung-movy`,
and a blobless clone of `jeffreywugz/fw-AC79_AIoT_SDK`. Vendor firmware images
were inspected in AL-255's checkout and are not redistributed here.
