# Community FM-1 firmware and JieLi's current SDK: what Lunar can learn (2026-10-05)

**Scope.** Four repositories were read for what they teach Lunar Modulator:
- JieLi's AC79 SDK on Gitee, with its `AC791N_OTA_loader` branch;
- Felucca (hugelton), with its recovery companion FM-1-transporter;
- fm1-nes (Keitark);
- SLOOP (isod89), a fork of Felucca.

How it was done:
- **Read only.** Shallow clones sit in `reference/` (git-ignored): `ac79-sdk`, `ac79-ota-loader`, `Felucca`, `fm1-nes`, `sloop-fm1`. FM-1-transporter was read through the GitHub API.
- **Nothing was built or run.** Six closed SDK libraries were unpacked in a scratch directory, and only their strings were read.
- **Nothing was sent** to any FM-1 or dev board.
- **Local checks** (hashes, decoding) ran only on our own scratch copy of the V15 package and on SLOOP's published package.

**Source tags** used below. Commits and licences are in §7.
- **[SDK]** Gitee `fw-AC79_AIoT_SDK`, branch `release/AC79NN_SDK_V1.2.0` at `e30b1ee` (= tag V1.2.13 plus a README change). **[SDK 1.1.9]** is tag `AC79NN_SDK_V1.1.9_2023-08-01`, our pin.
- **[OTA-loader]** branch `AC791N_OTA_loader` at `79eda0c`.
- **[Felucca]** `hugelton/Felucca` v1.0 at `727f272`.
- **[transporter]** `kurogedelic/FM-1-transporter` at `a632d92`.
- **[fm1-nes]** `Keitark/fm1-nes` at `870f305`.
- **[SLOOP]** `isod89/sloop-fm1` v2.2 at `f2b44c2`.

Marks follow CLAUDE.md:
- [verified] means checked here, against their source, our binaries or SDK files;
- [reported] means the named project says so, for example that something works on hardware;
- [inferred] is our reasoning.

## Contents
1. Short answer
2. The repositories: 2.1 SDK · 2.2 Felucca · 2.3 FM-1-transporter · 2.4 fm1-nes · 2.5 SLOOP
3. What changes for Lunar: 3.1 install path · 3.2 docs/14 and the dev kit · 3.3 second core · 3.4 USB-MIDI class · 3.5 drivers and pin map · 3.6 recovery
4. Corrections to our docs
5. Safety
6. Owner decisions
7. Sources

## 1. Short answer

- **Open firmware already runs on FM-1s.**
  - Felucca 1.0 and its fork SLOOP 2.2 are complete bare-metal synths. They link no JieLi SDK code. Owners install them from a Web MIDI page through the stock update path, and roll back to V15 the same way [reported: Felucca, SLOOP, their issues].
  - fm1-nes runs an AC79 SDK application on one V14 unit, written through mask ROM [reported: fm1-nes `VALIDATION.md:49-75`].
  - So docs/05's "L2 … not started by anyone" is out of date. So are several rows of our hardware table.
- **The board is now largely mapped** [reported: two separate code lineages, Felucca/SLOOP and fm1-nes, agree].
  - Audio leaves through **ALNK0 (I2S) to an external codec**, not through the internal DAC.
  - **All seven encoders are scanned in the key matrix.** MASTER is a pot on PB6 (ADC channel 4), and ADC channel 3 is the battery on PB1.
  - The TFT is an ST7789V on PC7–PC10, with the backlight on PA2.
  - The matrix runs through two 74HC595s on PA1/PA3/PA4 and reads back on PA0, PA5–PA8 and PB7.
  - TRS MIDI comes in on PH8.
  - The flash's JEDEC ID is 0x856014: Puya, 1 MiB.
- **A running app can enter mask-ROM `UBOOT1.00` without a dongle.** There are three ways:
  - stock V15's own `F0 22 24 35 7D F7` "soft key" [reported: transporter];
  - the SDK's `go_mask_usb_updata()` [verified: SDK source; reported working: fm1-nes];
  - a `usb_update_mode` RAM mailbox plus a P33 reset [verified: Felucca source; reported working].
  
  RAM at `0x01C7C000`–`0x01C7FD50` survives resets [reported: Felucca].
- **The design I13 lacked already exists** [reported: Felucca, SLOOP; source verified].
  - A custom app answers the stock update protocol.
  - Stock step 1 accepts a non-M-VAVE `ota.bin`.
  - The loader writes only the app area, so the flash head is never at risk.
  - `UPDATA_PARM` goes to flash `0xE4F00` and RAM `0x01C7FD88`.
- **The SDK has moved on.** Gitee is current to V1.2.13; the GitHub mirrors are stale.
  - From V1.2.7, `system.a` carries a key check, and V1.2.13 adds an eFuse chip-key check. Keep the V1.1.9 pin [verified: SDK].
  - A task-to-core control exists after all: the task-name prefix `#C0`. Whether `#C1` pins a task to cpu1 is still to be tested [verified for `#C0`; inferred for `#C1`].
  - The OTA-loader branch is the template of M-VAVE's `usb_hid_ota.bin`, and JieLi's writer now runs on Linux.
- **Licences.**
  - Felucca and SLOOP are GPL-3.0-only, so we take ideas and facts only.
  - We can reuse:
    - Felucca's `fm6_core.c` (Apache-2.0, an integer msfa port);
    - its `phys_dsp.c` and `phys_symp.c` (MIT);
    - fm1-nes's Apache-2.0 board code, though its constants are copied from stock;
    - FM-1-transporter (MIT);
    - the SDK's Apache-2.0 sources.
  - Two catches:
    - the SDK's `system.a` contains a modified FreeRTOS V9 (GPLv2 with the FreeRTOS exception);
    - the SDK's only USB-MIDI constants are in a GPL-2.0 header.
- **Safety.** Nothing here relaxes the one rule.
  - FM-1-transporter drives D+/D− push-pull with no series resistors, which docs/10's E1 rules out for our unit [verified: `pio/usb_key.pio`, README].
  - Its `fm1t.py` sends the soft key on its own when it sees V15 [verified: README].
  - No bricked unit is reported in any tracker that was read.

## 2. The repositories

### 2.1 JieLi AC79 SDK (Gitee), and the OTA-loader branch

**What it is.** JieLi's official SDK for the AC79 family (AC791N = WL82) [verified: SDK]. It contains:
- Apache-2.0 application, driver-glue and demo sources;
- about 150 closed `.a` libraries (332 MB);
- Windows tools;
- since V1.2.12, a Linux build-and-flash script.

The whole tree is 12,995 files and 750 MB; our sparse checkout is 30 MB [verified: Gitee tree API].

**How far it has got.**
- **Releases.** Gitee has 11 releases after our V1.1.9 pin, from V1.2.1 (2023-12-13) to V1.2.13 (2026-04-20). The branch head `e30b1ee` (2026-06-09) is V1.2.13 plus a README update [verified: git history].
- **Mirrors.** The `amitv87` GitHub mirror stops at 2024-07 [verified]. Gitee has no `master` branch, and its SSL is flaky: two fetches timed out and lazy blob fetches hung [verified].
- **What we called "the V1.2.0 tree"** was the V1.2.1/V1.2.2 era: its `uboot.boot` is `1cc0f013` [verified: blob hashes per tag].
- **Changes since V1.1.9** [verified: blob hashes per tag]:
  - `uboot.boot` changed four times: `b6cb71ea` → … → `b81f8de1`. The 2026 commits deal with ECC and eFuse keys (commits `2559814`, `3bed429`).
  - `ota.bin` grew from 271,182 to 310,497 B, and `wl82loader.bin` from 30,208 to 31,232 B.
  - jl-uboot-tool's `wl82loader.bin` (24,064 B) matches none of the SDK's loaders.
- **Key checks in `system.a`** [verified: strings per tag]:
  - V1.2.7 and later carry `__initcall_sdk_meky_check` (`JL_KEY_2020`).
  - V1.2.13 adds `sdk_chip_key_verify_v2`, which reads an eFuse key (`JL_KEY_2024`).
  - V1.1.9 to V1.2.6 have neither.
  - What the checks do on failure is unread [inferred].
- **Cross-check against fm1-nes.**
  - fm1-nes links `e30b1ee`'s libraries. Its boot audit requires `sdk_meky_check` as a late initcall that schedules `_mkey_check` after 8,000 ms [verified: fm1-nes `firmware/nes/audit_boot.py:256-276`].
  - That app then ran on a V14 FM-1 [reported]. So the check does not stop a boot at once on at least one unit, but its effect is still unknown.

**How it builds and gets onto a device.**
- **Toolchain.** The `pkgman` links are unchanged since 2026-10-02 [verified: redirects]:
  - linux-toolchain is `jieli-linux-toolchains-20250805.1`;
  - linux-postbuild is `20260923.1`.
- **Linux flashing.** V1.2.12 added `cpu/wl82/tools/download_linux.c` and `init_env.sh` [verified: source]. They run a native `isd_download … -dev wl82 -boot 0x1c02000 … -uboot uboot.boot -app app.bin cfg_tool.bin`. A 2026-01-12 commit changed `wl82loader.bin` to "fix Linux download failure".
- **That tool is a writer.** It may run on aeon in a container for the kit only. It must never be pointed at the FM-1.

**The OTA-loader branch.**
- It holds Code::Blocks projects for every `ota.bin` loader: uart, sd, usb, net, `usb_hid_ota`, uart_user and lcflash. Each is LZ4-packed and loaded at RAM `0x1C0A800` [verified: branch files, `download.sh`].
- `wl82_usb_hid_ota_loader.cbp` builds with `-DUSB_HID_MODULE_CONTROL=1`. It uses a custom HID class with 64-byte interrupt endpoints, and JieLi's RCSP protocol.
- **The update is device-pull** [verified: `update_main.c`]:
  - the loader reads `UPDATA_READ_OFFSIZE` in 512 B pieces;
  - it runs `ufw_head_check`, `flash_update_process` and `flash_all_data_verify`, clears the loader record, and waits for the reboot command.
  - That matches docs/03's step 2.
- **The FM-1's loader is very likely M-VAVE's build of this template with SysEx framing added** [inferred]. Its strings match [verified: our `usb_hid_ota.bin`: `/*.ufw`, `@JMUA`, `UPDATE_JUMP`, `POWER_PIN`, `success`]. So does its load address, `0x01C0A800`.

**Hardware facts it documents** [verified: SDK source, headers and PDFs unless marked]:
- **Task-to-core binding.**
  - A task name starting `#C0` pins the task to core 0. The demos use it for `btctrler`, `btstack`, `btencry` and `usb_msd0`, at V1.1.9 and at head.
  - JieLi's doc 2.18 gates it on `CPU_CORE_NUM > 1`.
  - `StaticTask_t` ends in `int cpu_id`, and the DWARF in `system.a` shows the TCB members `cpu_id` and `cpuSuspend`.
  - `#C1` very likely pins a task to cpu1 [inferred: the parser is inside the closed `system.a`].
- **Uninterruptible interrupts.** With `CONFIG_IPMASK_ENABLE`, `__local_irq_disable` sets the core's IPMASK to 7 instead of masking everything (`apps/common/system/init.c`).
  - A priority-7 interrupt pinned to cpu1 then keeps running through OS critical sections and flash writes.
  - The condition: its code and data must be in RAM, and it may take no lock (doc 7.41).
- **A shared lock.** In the default SMP build, `local_irq_disable()` also takes one global `bt_lock` spinlock shared by both cores (when `CONFIG_BT_ENABLE_SPINLOCK && CPU_CORE_NUM > 1`). A long critical section on cpu0 therefore stalls cpu1.
- **Software entry to mask ROM.** `go_mask_usb_updata()` is in `apps/common/usb/device/msd_upgrade.c`, identical at V1.1.9.
  - It runs from RAM: IRQs off, `ram_protect_close()`, `hw_mmu_disable()`, `nvram_set_boot_state(UPGRADE_USB_SOFT_KEY=2)`, then `JL_CLOCK->PWR_CON |= BIT(4)`.
  - `nvram_set_boot_state` lives in `cpu.a`, at both V1.1.9 and head.
- **The update hand-off.** In SFC builds, `UPDATA_BEG` is `0x01C7FD80` and `UPDATA_PARM` is at `0x01C7FD88` (`cpu/wl82/sdk_ld_sfc.c`, `include/update/update.h`). It holds:
  - a CRC;
  - the type, `USB_HID_UPDATA = 0x5A0D`;
  - the magic `0x5441`;
  - `file_path[32]`;
  - `ota_addr`.

  `boot_info` is 52 B at `0x01C7FD4C`, and `isd_config_rule.c` sets `ENTRY=0x2000120` for SFC builds.
- **The online-tool protocol** (`5A AA A5`), in `new_cfg_tool.c` and `cfg_tool.h`:
  - 0x23 queries basic info;
  - 0x24 erases a range;
  - 0x25 writes a range;
  - 0x26 enters mask-ROM upgrade;
  - 0x27 reads a range.
  
  This makes CLAUDE.md trap 7 concrete.
- **No USB-MIDI class, even at V1.2.13.** The class bitmap is MSD, SPEAKER, MIC, HID, CDC, UVC, CUSTOM_HID and PRINTER. The only MIDI constants are in `uac_audio.h`, which is a GPL-2.0 Linux header.
- **One hardware quadrature decoder** on WL82 (`RDEC_MODULE_NUM 1`; `WL82.h` has only `JL_RDEC`).
- **DSP hardware** (headers only, not timed):
  - a hardware sample-rate converter (`asm/src.h`);
  - fast math (`math_fast_function.h`: `sin_float`, `exp_float`, `root_float`, `tanh_float`);
  - an FFT and vector unit;
  - zero-overhead `rep {}` loops.
- **The closed libraries can be read.** They are LLVM 4.0.1 bitcode with full DWARF: source paths, struct and member names.
- **The dev kit** (schematic PDFs in `doc/datasheet`):
  - Core board `JL_AC79_WIFI V1.2`: AC7916A (QFN76) with an external 25Q64 (8 MB) flash; an UPDATA key (K1) and a RESET key (K2); USB-C wired straight to the chip; no USB-UART bridge.
  - Base board: an earphone jack J12 on DACL/DACR, line in, a microphone, a speaker amp, an ADC key ladder, an LCD header and a TF slot.
  - Debug UART TX is on PB03.
  - JieLi doc 2.3 says: hold UPDATA, press and release RESET, and the kit shows as `WL82 UBOOT1.00` with no dongle [reported].
- **JL USB updater 4.0** (`doc/stuff/usb updater.pdf`):
  - DIP off: the button cuts target power for at least 250 ms, then keys.
  - Bit 1: periodic power cut plus key.
  - Bit 3: continuous key, no power cut.
  - Bit 7: USB functions and a virtual serial port.
  - Bit 5: DP/DM default to UART.
  - The dongle can also carry 2-wire JTAG.
- **Chip variant hypothesis.** JieLi's naming fits `11B8` = **AC7911B8**: 1 MB in-package flash, no SDRAM [verified: `AC7911B_Datasheet_V1.4.pdf`, selection table]. The mapping to the FM-1 is [inferred], and it conflicts with the reported LQFP48 package (the datasheet lists QFN48). Its single DAC channel no longer matters for audio, because audio goes out over I2S (§3.5).

**Licence** [verified]:
- The LICENSE is the standard Apache-2.0 text with the copyright line unfilled. The README says "Copyright © 2024-2026 Zhuhai Jieli Technology".
- The FreeRTOS V9 headers are GPLv2 with the FreeRTOS exception, and `system.a` holds a modified kernel (its TCB adds `cpu_id`).
- `uac_audio.h`, `uac_audio_v2.h` (SPDX GPL-2.0), the sdio headers and `usbnet.h` are GPL-2.0.
- The closed `.a` files and the tools carry no licence.

**What we may reuse** (Apache-2.0, credited to Zhuhai Jieli, with links to Gitee paths at `e30b1ee` or V1.1.9; no vendor binaries committed):
- `go_mask_usb_updata()`;
- the `custom_hid.c`/`cdc.c` pattern with `usb_add_desc_config()`, as the shape of our USB-MIDI class;
- `lcd_drive.c` and its ST7789V/S init tables;
- `matrix_keyboard.c` and `rdec.c`;
- `update.c`'s `update_mode_api_v2`;
- the OTA-loader branch's `update_main.c`, as a model for I3's device simulator and I13;
- `download_linux.c` and `init_env.sh`, as the recipe for a kit-only container on aeon.

### 2.2 Felucca (hugelton / Hügelton Instruments)

**What it is.** Complete, from-scratch, bare-metal replacement firmware for the FM-1 [verified: source; reported: running].
- A four-track synth with 13 engines, including FM6 (an integer msfa port).
- Eight voices shared across the tracks.
- A 64-step sequencer with songs, an arpeggiator and chord keys.
- A modulation matrix, effects, a web editor and optional USB audio recording.

**How far it got.**
- Releases: v0.8-beta and v0.9-beta on 2026-10-03, and v1.0 on 2026-10-05 [verified: GitHub releases].
- The repo had 185 stars when read [reported: GitHub].
- Users report installs, TRS MIDI in on 1.0 (#33) and rollbacks to V15 (#32, #33). The one failed rollback (#32) was a MIDI port held open on the host, and it resolved itself [reported: issues #1–#41].
- No issue reports a bricked unit.
- It has no BLE, because the stock BLE needs JieLi's closed libraries. The author lists BLE as a "v2" goal [reported: README].

**How it builds.**
- The compiler is only JieLi's Linux clang 4.0.1 (`-target pi32v2`, no `-mcpu`), run in a `linux/amd64` Debian container on macOS [verified: `BUILDING.md`, `build.sh`, `tools/get_toolchain.sh`].
- The whole app is one translation unit, `felucca.c`, with a header-only HAL and its own `libc.c`.
- `build.py` checks [verified: `tools/build.py:37-50,189-313`]:
  - `_start` is at `0x02000120`, and the image starts with `04 81 80 00` (`goto +4; rts`);
  - no code references the mask ROM (`0xFFC00000`–`0xFFD00000`);
  - `.ram_text` makes no calls;
  - registers are touched only under `hal/`.
- Toolchain traps worth copying into our notes [verified: source comments]:
  - clang does not emit the `csync` that stock ISRs place before `rti`, so ISRs are assembly wrappers (`fm1_isr.S:3-5`);
  - XIP code (`0x02xxxxxx`) cannot reach RAM code (`0x01C0xxxx`) with a direct call, which is beyond the 23-bit range, so it calls through a volatile function pointer (`fm1_flash.h:19-22`);
  - `-Os` moves register helpers out of line unless they are marked `always_inline`.
- It uses only three SDK files, all for packaging: `uboot.boot`, `cfg_tool.bin` and `eq_cfg_hw.bin`. They are pinned by SHA-256 to SDK V1.2.1.

**How it gets onto the device.**
- **The package.** `tools/fm1pkg_make.py` builds a whole `.fwsc` from scratch [verified: `:30-192`]:
  - a head carrying SDK V1.2.1's `uboot.boot`;
  - a synthetic `isd_config.ini`: a 32-byte blob that decodes to chip key `0x980F`, then `[FELUCCA]`;
  - an app area at `0x4000`, SFC-encrypted, with the slot `0x8DFBC`;
  - its own loader as `ota.bin`, named `usb_hid_ota.bin` and loaded at `0x01C0A800`;
  - the identity `FM-1_900`, or `FM-1_9XY` for a release (1.0 is `FM-1_910`).
- **The first install** goes through stock step 1 from V15. Stock stages Felucca's loader [reported].
- **The loader** [verified: `firmware/loader/loader.c`, `ldr_core.c`]:
  - It enumerates as `1209:0002` "Felucca Update" and answers as `ota-FM-1_900`.
  - It derives the chip key from the device's own `isd_config` blob, and refuses a package that does not decrypt with it.
  - It writes only `[0x4000, 0x93000)`, by 4 KiB sector-diff with verify, and never the head.
  - It clears the update records and resets.
  - After a power cut, the flash record makes the SPL re-run it.
- **A running Felucca answers the update protocol itself** ("step 1 lite") [verified: `firmware/src/ota.c:1-397`]:
  - It accepts only its own loader, or M-VAVE's (recognised by CRCs `0xEBAA`/`0x5881` and length `0x4DE1`). For M-VAVE's, the package head must equal the device's head.
  - It stages the loader at flash `0xE0000` (5 × 4 KiB), writing the JLFS `LOADER.BIN` head last.
  - It writes a 112-byte `UPDATA_PARM` to flash `0xE4F00` and RAM `0x01C7FD88`, then core-resets through PWR_CON bit 4.
  - The SPL scans 4K-boundary-minus-256 slots in `[0x93000, 0xFC000)` for the magic `0x5441` [reported]. So Felucca keeps its data-sector tails erased.
- **Rollback.** "Return to official V15" accepts only M-VAVE's `FM-1.fwsc`: SHA-256 `db1642b2…`, 699,956 B. That equals our `scratch/FM-1_v15_cdn.fwsc` [verified: shasum].

**Hardware it documents.** It is folded into the pin table in §3.5 [reported, from working code]. Also:
- **RAM map** (`firmware/app.ld`):
  - `.ram_text` at `0x01C00000`;
  - `.data`/`.bss` at `0x01C08000`;
  - a pool at `0x01C20000` (336 KiB);
  - stacks with 256 B guard bands;
  - `.noinit` at `0x01C7C000`–`0x01C7FD50`, which survives resets and UBOOT entry;
  - the vectors at `0x01C7FE00`.
- **The SPL's hand-over.** The SPL jumps to `0x02000120` with `r0 = 0x01C7FE08` (`crt0.S`).
- **Flash** (`hal/fm1_flash.h`):
  - CS# is PD0. Runtime writes go through SPI0 with the SFC off, from RAM.
  - `[0x93000, end)` is mapped as a plain window through SFCENC `UNENC_L/H` (`0x40308`/`0x4030C`).
- **Guards and watchdog** (`hal/fm1_sys.h`, `fm1_guard.h`):
  - the P33 watchdog (about 8 s) is armed first;
  - EMU stack limits, CPU0 write limits and a PC limit are set;
  - an ETM branch trace runs, and a crash record goes to `.noinit`.
- **No clock setup.** Felucca never programs the PLL. It runs at whatever clock the SPL sets from the device's `isd_config` [inferred: no PLL writes in `hal/`].
- **One core only.** No cpu1 code, and no float: everything is integer or fixed point [verified: grep].

**Licence** [verified: LICENSE, `LICENSING.md`, file headers]:
- **GPL-3.0-only.** 160 files carry the SPDX line.
- **Exceptions:**
  - `firmware/src/fm6_core.c` is **Apache-2.0** (Google 2012, Pascal Gauthier 2016-2025), an integer C port of msfa;
  - `phys_dsp.c` (DaisySP models) and `phys_symp.c` (Rings' sympathetic strings) are **MIT**.
- **Assets:** the Inter Tight font is OFL, and the samples are CC0.
- `eng_phase.c` (from CrispyZebra) and Hügelton's drum samples are GPL-3.0.

**What we may reuse.**
- Code: `fm6_core.c` as an msfa oracle, and possibly `phys_*.c`. Each would go in `third_party/` with `UPSTREAM.md`.
- Everything else is ideas and facts only: register addresses, pin maps, protocol layouts and the update-service design, restated in our own words and code with credit.

### 2.3 FM-1-transporter (kurogedelic), Felucca's recovery tool

**What it is.** A Seeed XIAO RP2040 wired to the FM-1's D+, D− and GND, never VBUS [verified: README].
- It keys `USB_KEY` `0x16EF`, then acts as a USB host to `UBOOT1.00` through Pico-PIO-USB.
- The Mac talks to the XIAO over CDC, so no cable moves.
- The README promises a full 1 MiB dump in "about 3 s" [verified: README]. The DEVLOG records 20.7 s at 49 KiB/s, probably an earlier milestone [reported; inferred].

**What it reports on FM-1s** [reported: `docs/PROTOCOL.md`, `docs/DEVLOG.md`]:
- **Key polarity.** Polarity A only: D+ is the clock and D− the data. Polarity B never worked.
- **The UBOOT device.** It enumerates as `4C4A:8057` `WL80UBOOT1.00`; the SCSI inquiry gives `WL82`/`UBOOT1.00`. READ_KEY returns `0x980F`, and the flash ID is `0x856014`.
- **Raw reads.** Flash reads are raw: the `.fwsc` type-0 flash entry (602,112 B) is byte-identical to flash from offset 0.
- **Keying and resets.**
  - The ROM accepts `USB_KEY` after a watchdog reset too.
  - A hung unit with no watchdog needs a power-on while the key is sent.
  - If the host drops the device, the chip resets and boots flash.
- **The soft key.** Stock V15 obeys `F0 22 24 35 7D F7`: it left the bus 21 ms later and came back as UBOOT 1.0 s after that. This fails if another full-speed device shares the hub.
- **Stock V15 attaches to USB only after a cold power-on.**
- **Writes.** Only changed sectors in `[0x4000, 0x93000)` are written, each verified. A self-test erased and rewrote sector `0x92000`, and V15 still booted.

**Drive and wiring** [verified: `pio/usb_key.pio`, README at `a632d92`]:
- The key program is `usb_key_pp`. It sets both pins as driven outputs (`set pindirs, 3`): push-pull, like czietz's gist.
- The README wires D6/D7 straight to D+/D−, with no series resistors.
- `fm1t.py` enters UBOOT "by itself" when stock V15 is running.

**Licence.** MIT, "Copyright (c) 2026 kurogedelic" [verified: LICENSE]. It ports routines from jl-uboot-tool (MIT) and does not ship `wl82loader.bin`. Its notes credit an unpublished "fm-1-research-lab".

### 2.4 fm1-nes (Keitark)

**What it is.** Firmware-development resources for the FM-1 [verified: source]. Its worked example is an NES emulator (PeakRacing core, Apache-2.0) as an AC79 SDK application. Around the emulator it provides:
- board support;
- a CDC diagnostics port with a two-step `UBOOT` command;
- an optional UAC1 48 kHz composite (GPL-3.0);
- an app-only packager and sparse sector planner;
- a guard patch for jl-uboot-tool.

The tooling is Windows-only.

**How far it got** [reported: `VALIDATION.md:49-75`]:
- **The install.** On 2026-10-03 a 217,680-byte app went onto the maintainer's V14 unit through mask ROM: 51 changed 4 KiB sectors, directory sector last, one full readback.
  - The writer was "the existing private elevated Jieli writer". Their public wrapper targets jl-uboot-tool `adb3f18` with a guard patch [verified: `scripts/jltool_update.py`, `tools/jltool-fm1-guards.patch.txt`].
- **After reset.** Windows enumerated CDC and both UAC endpoints. Telemetry showed advancing frames, zero underruns and live volume-ADC readings.
- **Entering UBOOT.** The CDC `UBOOT` command entered UBOOT without a dongle.
- **Not yet accepted:** screen, sound and controls. No fps or CPU figures are published.

**How it builds.**
- It takes `demo_hello`'s flags (`-Oz -flto`) and links SDK `e30b1ee`'s closed libraries without `-inline-threshold=5` [verified: `firmware/usb-diag/build.py:177-207`].
- It discards `.syscfg.*.ops` and `#error`s on the SDK's cfg-repair and RF options, so the SDK cannot write flash behind its back.
- It objcopies `app.bin`, entry `0x02000120`, with no JieLi post-build tools.
- **A boot ABI bridge.** The FM-1's installed `uboot.boot` passes 6 words, and the V1.2.x SDK expects 23. `--wrap=boot_info_init` copies 6 and zeroes the rest [verified: `boot/boot_compat.c:17-34`].
  - The accepted bootloader is pinned by SHA-256 `fcaf033c…`. That equals the bank data of `uboot.boot` in our V15 package [verified: recomputed].
  - V15 runs this same SPL with V1.1.9 libraries, so a V1.1.9 build probably needs no bridge [inferred, strong; unchecked].
- **Power values.** `board_power.c` uses FM-1_010's values, not the demo's: VDDIOM and VDDIOW 3.2 V, VDC14 1.60 V with DCDC, SYSVDD 1.38 V, LVD 2.6 V [verified: source; values reported as stock-derived].
- **Size.** A CDC-only SDK app (OS, USB CDC, boot, power) is 129,392 B [reported: `VALIDATION.md:128-132`].

**Hardware it documents.** It is in the pin table in §3.5. These items are particular to fm1-nes:
- **Audio** (`fm1_wl82.c:166-180`):
  - stock FM-1_010's route is `iis_open` on `IIS_PORTC`, output channel 3, MCLK out, 24-in-32;
  - 64 stereo frames per half (a 1,024 B ping-pong), ALNK IRQ 11 at priority 3.
- **The key matrix** (`fm1_wl82_keyscan.c`): stock clocks the two 595s with **SPI2** (`0x11E00`, IRQ 37), with the latch on PA1.
- **The TFT init** (`display_test.c`, `LCD_PROVENANCE.md`): a 21-record ST7789V-class table from FM-1_010 `0x5000c`, including a `2B` row window of 40–279.
- **Encoders.** Seven matrix encoders, decoded with stock's masks `0x2814`/`0x4182`. ALGORITHM and PRESETS give 4 edges per detent [reported: `peripheral_logic.c`].
- **The cores.** The SDK default `CPU_CORE_NUM 2` (SMP) boots under the stock SPL [reported]. Only `#C0` pins are used.
- **Cache RAM.** A cache-RAM window at `0x01F28000`–`0x01F2F000` (28 KB) [verified: `audit_boot.py`; reported behaviour].
- **The planner refuses V15 and FM-1_092.** It accepts only the 010/V14 layouts [verified: `scripts/jl_formats.py`].

**Licence** [verified]:
- The root LICENSE is Apache-2.0. The board, keyscan, volume, power, `boot_compat`, packager and planner files fall under it.
- GPL-3.0-only (from the private `fm1-mdx`): `firmware/usb-audio/*`, `usb-diag/packet.*`, `usb_policy.c`, `descriptors.c`, and parts of `app_main.c`.
- MIT: the `jl_formats.py` cipher routines (from jl-misctools), the jl-uboot-tool guard patch, and `examples/fablenes/`.
- The author says the board constants are **copied from stock FM-1_010, not clean-room**.

**What we may reuse.**
- **Apache-2.0** (in `third_party/fm1-nes/` with LICENSE and `UPSTREAM.md`): keyscan, volume, LCD sender, ALNK setup, `board_power.c`, `boot_compat.c`, the packager and planner logic.
- **MIT:** the guard patch (strict identity, JEDEC check, 256-byte I/O, no READ_KEY, readback per sector).
- **Their stock-derived tables** are cross-checks only. Re-derive each from our own V15 disassembly in I4 and cite both.

### 2.5 SLOOP (isod89)

**What it is.** A four-track live groovebox: three synth tracks plus a drum track, nine engines, a sequencer and looper, song mode, a web editor and a web installer [verified: source; reported: "2.2, running on the FM-1", `SLOOP.md:9`].
- It is a fork of an earlier Felucca, with the same bare-metal HAL and update design [verified: `diff -rq` against Felucca].
- The repo was created on 2026-10-04 and shipped v2.0 to v2.2 within about 12 h. It had 117 stars and 10 forks when read [reported: GitHub].
- Its 15 issues and PRs contain no bricking report. #8 was MIDI-port contention on the host, and the author confirmed rollback to V15 there [reported].

**What it adds beyond Felucca** [verified: source]:
- The loader checks the CRC16 of the whole served `flash.bin` (up to three passes), and refuses any flash whose JEDEC ID is not `0x856014`.
- Bootguard: a `.noinit` record is cleared on power-on and after 30 s healthy. Two early failed boots lead to "SLOOP USB RESCUE" (LCD, USB and the OTA service only), and a reset in rescue goes to UBOOT (`firmware/src/bootguard.h`, `recovery.c`).
- The installer checks SHA-256s.
- An app-image budget: 540,116 of 581,564 B used (92.9 %) [verified: our decode of `docs/firmware/sloop-2.2.fwsc`: identity `FM-1_900`, `flash.bin` 602,112 B, `ota.bin` 6,646 B, entry stub `04818000` after decrypting with `0x980F`].
- A flash erase stops audio for about 50 ms, so autosave runs only when stopped and idle [reported: source comment].
- MIDI out over USB. UART RX is "untested on hardware" in SLOOP, while Felucca 1.0's same header says verified.
- Every SLOOP version reports `FM-1_900`, so the identity cannot tell SLOOP versions apart.
- Baud Girl's installer refuses to go from SLOOP to FM-1+VA [reported: issue #8].

**Licence** [verified]:
- GPL-3.0-only, copyright Leo Kuroshita / Hügelton Instruments. isod89's own files carry SPDX lines without copyright lines.
- `LICENSING.md` adds a §7 permission for Hügelton assets that are all rights reserved.
- The committed `.fwsc` contains the SDK's Apache-2.0 files.

**What we may reuse.** No code. We can take its facts, and its UI and sequencer ideas with credit, mapped onto Movy semantics:
- hold-to-show layers on the 4×4 white keys;
- dim landmark LEDs;
- a free-take loop that infers the bar length;
- latency-compensated recording (512 samples);
- per-step level and ratchets;
- live song sections;
- shedding a voice at 85 % of the block budget.

## 3. What changes for Lunar

### 3.1 The install path (DEVELOPERS.md, I0–I15)

- **I0.** New decisions arise (§6): SDK or bare metal, own loader, the recovery tool, and the soft key.
  - The I0 bullet that rules out czietz's push-pull Pico tool now also covers FM-1-transporter.
- **I1. Keep V1.1.9** for every closed library and for `uboot.boot`, `ota.bin` and `isd_config`.
  - Add a check that refuses a `system.a` containing `sdk_meky_check` or `sdk_chip_key_verify_v2`.
  - Record the blob hashes `37ad8997` (`system.a`) and `f0f65e4b` (`cpu.a`).
  - Cite Gitee, not the stale mirrors.
  - fm1-nes shows that V1.2.13 libraries plus a 6→23-word bridge also boot [reported]. That is a fallback, not a reason to move.
- **I3. Packaging.**
  - **The `.fwsc` builder:** keep "start from the user's V15, head byte-identical".
  - **The mask-ROM image writer:** model it on fm1-nes's planner and transporter's writer:
    - only app sectors plus the directory records, directory last;
    - read each old sector first and read back each write;
    - one final full readback;
    - layout tables for V15 and FM-1_092.
  - **The device model:** model step 2 on the OTA-loader branch's `update_main.c`.
- **I4. The pin map.** Most of it is now a hypothesis from two lineages (§3.5). I4 becomes verification against V15 with the vendor `objdump`. Four items stay open:
  - PC6's role;
  - the codec part;
  - the clock the SPL sets;
  - the LED drive scheme.
- **I6/I7.** See §3.2.
- **I9.**
  - Expect `UBOOT1.00` as `4C4A:8057`, SCSI `WL82/UBOOT1.00/1.00`, JEDEC `0x856014`, and raw reads [reported].
  - The dumps must still be ours.
  - If the host drops the device, the chip reboots into flash, so dump, compare and write in one session [reported: transporter].
- **I10.** Partly answered for custom apps: the SPL scans 4K-boundary−256 slots in `[0x93000, 0xFC000)` for `0x5441` records [reported: Felucca]. Where stock V15 itself stages `ota.bin` is still for the dumps to show.
  - Stock step 1 accepts a non-M-VAVE `ota.bin` [reported: Felucca, SLOOP installs]. So AL-255's failed modified-loader package (docs/03 §5) failed for some other reason.
- **I11. Adopt Felucca's build checks:**
  - the entry stub `04 81 80 00` at `0x02000120`;
  - no mask-ROM calls;
  - no calls from `.ram_text`;
  - `csync` before `rti`;
  - calls from XIP to RAM through a function pointer.
- **I13 has a worked design** [reported: Felucca, SLOOP]:
  - The app's update service accepts known loaders only. For M-VAVE's loader the head must equal the device's.
  - Stage the loader with its JLFS head written last, and write `UPDATA_PARM` to flash and RAM.
  - Keep sector tails clear of record look-alikes.
  - Arm the watchdog first, and keep a `.noinit` boot counter that leads to rescue and then UBOOT.
  - **Fail-open** should read the keys before USB starts. Felucca's 5 s OCT−/OCT+ combination works only once its main loop runs.
  - Two entry mechanisms exist: `go_mask_usb_updata()` (SDK) and the `usb_update_mode` mailbox.
- **I14.**
  - Felucca and SLOOP overwrite the stock VM region (`0x93000`+). A later V15 rollback starts with foreign VM data [inferred].
  - Lunar should keep its data out of VM, or erase VM back to blank on rollback. Then add "VM handled" to the done-when.
- **I15.**
  - Fix the "no GPL" framing (§3.4, §4).
  - Use `FM-1_5xx`: it is clear of M-VAVE (≤ `019`), Baud Girl (`020`–`092`+) and Felucca/SLOOP (`9xx`).
  - Keep the product string `FM-1`, so editors and installers find the port (the Felucca #32 lesson: a port named "Felucca" was missed).
  - Detect a MIDI port held by another app (Felucca #32, SLOOP #8).

### 3.2 docs/14 stage B and the dev-kit plan

- **Step 1 (inventory).** The kit's schematic answers part of it [verified: SDK PDFs]:
  - an earphone jack J12 on DACL/DACR;
  - a TF slot;
  - no USB-UART bridge on the core board, with UART TX on PB03;
  - an external 25Q64 flash, unlike the FM-1's.
  
  Check the bought kit's revision: docs/07 lists V1.0, and the schematic is V1.2.
- **Step 3 (recovery).** The kit has its own UPDATA and RESET keys for UBOOT [reported: JieLi doc 2.3].
  - Still rehearse JieLi's dongle on the kit, in DIP bit 3 (continuous key, no power cut) with a power-up. The FM-1 runs on its battery, so the power-cut modes may not reset it [inferred].
  - Clipping the kit's 25Q64 gives a raw dump to compare with jl-uboot-tool's [inferred].
- **Steps 4 and 6.** Flash the kit with Linux `isd_download` from linux-postbuild `20260923.1` in a container on aeon. Archive its SHA-256.
- **Live mode and C6a.** On the FM-1 the audio interrupt is **ALNK0, IRQ 11**, not the DAC. The kit can rehearse only the DAC path. Its ALNK has no codec on the board [inferred].
  - `bsp_audio_start` already hides this.
  - The R2 "live" rung on the kit and on the FM-1 will differ in interrupt source.
- **Step 5b (second core).** Add three probes. They are cheaper than asking JieLi for a single-core `system.a`:
  - **C6d:** a task named `#C1audio` on the public SMP library.
  - **C6e:** audio rendered in a priority-7 IPMASK interrupt pinned to cpu1, with RAM-resident code, measured through flash writes.
  - **C6f:** how long cpu1 stalls on the shared `bt_lock` while cpu0 does BT, USB and flash work.
- **Before the kit, on aeon.** Run a modern `llvm-dis` in a container over V1.1.9's `system.a` (`tasks.c.o`, `os_api.c.o`) and over `cpu.a`'s USB and DAC objects. That reads how `#C<n>` and `cpu_id` are handled. The output stays in scratch.
- **Optional stage B fast paths.** Time the hardware SRC and `math_fast_function` against newlib. They stay out of the bit-exact ladder profile.
- **Budget.** I8's "70 % of 348,160 cycles at 240 MHz" assumes the stock CRT's PLL setting. A bare-metal build inherits the SPL's clock. Decode V15's `isd_config` `SYS_CLK`/`HSB_DIV`/`LSB_DIV` keys [verified present] to learn it.

### 3.3 The second core

- **Stock:** cpu1 renders msfa outside the OS (docs/11 §2). Unchanged.
- **SDK:**
  - `#C0` exists [verified], and `#C1` very likely pins to cpu1 [inferred].
  - IPMASK priority-7 interrupts can run on cpu1 through critical sections [verified: source].
  - The shared `bt_lock` can stall cpu1 [verified: source].
  - SMP with `CPU_CORE_NUM 2` boots on an FM-1 under the stock SPL [reported: fm1-nes].
- **Felucca and SLOOP prove one core is enough for a full instrument** [reported]. They run 8 voices of integer engines plus effects and a sequencer on cpu0, at whatever clock the SPL sets, shedding voices at 85 %.
  - This supports the preview's single-core plan (DEVELOPERS.md I7).
  - It says nothing about our float engines or the FPU.

### 3.4 The USB-MIDI device class

- **Still absent from the SDK** at V1.2.13 [verified].
- **The recipe** [verified: source]:
  - `usb_add_desc_config()`;
  - `usb_g_ep_config` with bulk endpoints;
  - an rx handler, as in `custom_hid.c` (312 lines on the OTA branch) or `cdc.c`.
- **Write the MIDI descriptors from the USB-MIDI 1.0 spec.** Never include `uac_audio.h` or `uac_audio_v2.h`, which are GPL-2.0.
- **Keep stock's interface:**
  - bulk EP `0x84` IN and `0x04` OUT, 64 B;
  - jacks 1, 2, 7 and 8 (DEVELOPERS.md:338-341);
  - the product string `FM-1`.
- **Lessons from fm1-nes's patched SDK CDC class** [reported]:
  - non-blocking packet writes;
  - no ZLP;
  - a setup-request filter;
  - a composite setup policy. A stale CDC-only policy gave Windows `CM_PROB_FAILED_START`.
- **Felucca's own class** is GPL, so ideas only.
  - It is polled from a 2 kHz timer, with no USB interrupt. MIDI is on EP1 bulk, CDC sits behind an IAD, and UAC1 IN is on EP4 [verified: source].
  - Felucca uses the pid.codes test ID `1209:0001`, which its own comment says to replace. We must not copy it.

### 3.5 Drivers and the pin map

All rows are [reported] from working code, unless marked. "F" = Felucca/SLOOP (one lineage). "N" = fm1-nes (from stock FM-1_010). Base addresses were checked against `WL82.h` [verified: SLOOP lane, against the SDK header].

| Function | What the code does | Source |
| --- | --- | --- |
| TFT | ST7789V on SPI1 `0x11D00` (IRQ 16): SCK PC9, MOSI PC10, CS PC7, D/C PC8; no reset line; PA2 backlight, active low (N: driven low, role unstated); `SPI_CON 0x4021`, `BAUD 4` ≈ 12 MHz; DMA from RAM only | F `hal/fm1_lcd_hw.h`; N `display_test.c` |
| TFT speed | Full RGB565 frame ≈ 77 ms at 12 MHz (≤ 13 fps); RGB444 at 30 MHz ≈ 23 ms, bench-tested by N [inferred arithmetic] | F `lcd.c:11`; N `display_test.h` |
| Key matrix | 11 select lines × 6 return lines; two 74HC595s on PA4 (data), PA3 (clock), PA1 (latch); stock clocks them with SPI2 `0x11E00`, IRQ 37 (N), F bit-bangs; 16-bit word, bits 11 and 12 also low for columns 0 and 1; returns PA0, PA5–PA8, PB7 with pull-ups, low = closed | F `hal/fm1_input.h`; N `fm1_wl82_keyscan.c:25-35,143-183` |
| IDs | 41: 0–13 the 14 buttons, 14–40 the 27 keys F3–G5 | F `hal/fm1_input.h`; N `fm1_stock_keys.c` |
| LEDs | Lines PA9, PA10, PH6, PH9 (high drive), lit on the selected column; dim = one frame in four (F); N does not drive LEDs | F `hal/fm1_input.h`; issue #28 |
| Encoders | 7 (SELECT, ALGORITHM, PRESETS, KNOB1–4) as A/B contacts in the matrix, decoded in software with stock's masks `0x2814`/`0x4182`; the one hardware RDEC is not used | F, N, SDK `rdec.h` [verified for RDEC] |
| MASTER | Pot on PB6, SARADC ch4 (`0x13100`), 10-bit | F `hal/fm1_adc.h`; N `fm1_volume.c` |
| Battery | PB1, SARADC ch3; stock thresholds 531, 561, 591; PB1 is also the 8 s reset pin, so keep it analog | F `ui_draw.c:17-19`; AL-255 |
| Audio | ALNK0 `0x12E00`, channel 3 (F writes `ADR3`, N `output_channel=3`), IIS_PORTC, MCLK out, 24-bit left-justified in 32; IRQ 11 at priority 3; stock 64 frames per half (N); F runs 24 MHz / 544 = **44,117.6 Hz**; output ceiling −6 dBFS (F) | F `hal/fm1_audio.h` [verified: source]; N `fm1_wl82.c:166-180` |
| Codec lines | F drives PC0, PC1, PC2 and PC6 as GPIOs during bring-up and calls them codec control lines; N says PC6 is channel-3 data. **Conflict**; likely PC0–PC2 are the clocks and PC6 the data [inferred]; the codec is probably `U5` or `U9` [inferred] | as above |
| TRS MIDI in | UART1 `0x12100` RX on PH8 through input channel 1; 31,250 baud from PLL48M; RX DMA ring, polled; no TRS out | F `hal/fm1_uart.h` ("RX verified on hardware" in F 1.0) |
| Flash | JEDEC `0x856014` (Puya, 1 MiB) [reported by two separate sources]; CS# PD0; runtime writes on SPI0 `0x11C00` with the SFC off, from RAM | F `hal/fm1_flash.h`; N guard patch; transporter |
| Timers | TIMER4 `0x10800` free-running at 24 MHz (it also runs under UBOOT); TIMER5 `0x10900` 10 kHz tick on IRQ 63 | F `hal/fm1_time.h`, `fm1_timer.h` |
| Watchdog | P33 `P3_WDT_CON` ≈ 8 s, through the P33 serial interface at `0x13E08`/`0x13E0C` | F `hal/fm1_sys.h` |
| Power (SDK builds) | VDDIOM and VDDIOW 3.2 V, VDC14 1.60 V DCDC, SYSVDD 1.38 V, LVD 2.6 V, not the demo's 1.40 V, 1.26 V, 2.5 V | N `board_power.c:8-47` |

Consequences:
- **docs/14 §4.3's audio and knob rows change.** The kit and the FM-1 differ in audio interrupt and audio path.
- **The UI should keep strip and dirty-region rendering.** The SPI clock caps full-frame redraws.
- **Mirror the physical facts in sim/web:** the key-slot order (14..40 = F3..G5) and the detent behaviour.

### 3.6 Recovery

| Path | What it needs | Status |
| --- | --- | --- |
| `USB_KEY` dongle at power-on | a dongle; D+ is the clock | [reported] on FM-1s by czietz (docs/10 §1.1) and transporter; polarity B never worked (transporter) |
| `USB_KEY` after a watchdog reset | a dongle | [reported: transporter] |
| Stock soft key `F0 22 24 35 7D F7` | stock V15 running, no other full-speed device on the hub | [reported: transporter log; AL-255 flagged a `7D`/`7F` trailer calling mask ROM `0xFFC02532` at medium confidence, `FM-1-RE/docs/io/05-midi.md:97`]; **FM-1_092 not checked** |
| `go_mask_usb_updata()` | our app running | [verified: SDK source; reported working: fm1-nes CDC `UBOOT`] |
| `usb_update_mode` mailbox at `0x01C7FD80`, then P33 reset | our app running | [verified: Felucca source; reported working] |
| Boot-loop guard in `.noinit`, then rescue, then UBOOT | our app reaching main | [verified: SLOOP source] |
| Kit UPDATA + RESET keys | the kit only | [reported: JieLi doc 2.3] |

- A failed boot and a hung app are different cases. kagaimiq says the ROM enters USB mode when flash does not boot. A hung app needs the watchdog, or a dongle at power-on [reported: transporter].
- jl-uboot-tool `adb3f18`'s `wl82loader.bin` works on FM-1s with 256-byte I/O [reported: fm1-nes guard patch]. Our clone has the identical loader [verified: hash].
- All of these leave docs/07 rule 1 unmet for the owner's unit. The demonstrated dump-and-restores were on other people's FM-1s.

## 4. Corrections to our docs

| Doc and line | What it says | What the evidence says | Confidence | Proposed change |
| --- | --- | --- | --- | --- |
| CLAUDE.md:94; DEVELOPERS.md:291 and :1066; docs/01:134; docs/14:235 | internal DAC via a DMA ring | ALNK0 I2S, channel 3, PORTC, MCLK out, to an external codec; IRQ 11 | [reported: Felucca, fm1-nes; bases verified against WL82.h] | "ALNK0 (I2S) to an external codec (`U5`/`U9`?) [reported]; confirm in V15 by grepping for `0x12E00` and `0x12F00` accesses" |
| docs/05:124 | "I2S/SPDIF also on chip, unused on this board" | I2S is the board's audio path | [reported] | Swap the cells: internal DAC unused, I2S used |
| CLAUDE.md:93; DEVELOPERS.md:290; docs/01:114; docs/14:232 | stock reads 2 quadrature encoders and 2 ADC channels; split unresolved | 7 encoders in the matrix, software-decoded; MASTER pot on ADC4/PB6; ADC3 is the battery; WL82 has one RDEC, unused | [reported: Felucca, fm1-nes, SLOOP; RDEC count verified] | Rewrite as stated; close docs/01 §6 Q1 |
| docs/01:135 | ADC 3/4 for "wheels" | ch4 MASTER, ch3 battery divider on PB1 | [reported] | Rewrite |
| docs/01:117-118 | `U2`/`U3` "LED drivers"; GPIO matrix scan | the 595s select the 11 matrix columns (stock clocks them on SPI2); LEDs on PA9/PA10/PH6/PH9 | [reported] | Rename to "matrix column drivers", add pins; narrow §6 Q7 |
| docs/01:159 (§6 Q2) | JEDEC ID and size unknown | `0x856014`, Puya, 1 MiB; in-package or not still open | [reported: two separate sources] | Narrow Q2 |
| docs/01:164-165 (§6 Q4, Q5) | TFT pinout and controller; codec routing | ST7789V on PC7–PC10 + PA2; codec on ALNK0 PORTC | [reported] | Narrow Q4; reword Q5 as "which part is the I2S codec, and what PC0/1/2/6 do" |
| docs/01:51 | load address `0x02000120` [inferred] | our V15 `jlfw.yaml` says `entry-point: 33554720`; three firmwares boot there | [verified + reported] | Raise the mark |
| docs/02:33 and :51 | entry/jump at `0x020000A0` | the SPL jumps to `0x02000120`; first instruction `04 81 80 00`; `r0 = 0x01C7FE08` | [verified: jlfw.yaml; reported: Felucca crt0.S] | Correct both lines |
| docs/02:52 | `isd_config.ini` entries listed without clock keys | V15's has `SYS_CLK`, `HSB_DIV`, `LSB_DIV` | [verified: Felucca lane, on our V15] | Add them; decode in I4 |
| docs/05:14 | L2 "not started by anyone" | Felucca and SLOOP are L2 apps running on FM-1s, without BLE | [reported] | Update the status cell and cite them |
| docs/07:57 | DIP "all off for chips with a crystal" | off = button cuts target power, then keys; the FM-1's battery may defeat a power cut; bit 3 = continuous key | [verified: updater 4.0 manual; FM-1 fit inferred] | Bit 3 plus the slide switch for the FM-1; bit 7 for the virtual serial port |
| docs/07:59 | vendor software Windows-only | Linux `isd_download` since SDK V1.2.12 | [verified: SDK] | Correct; keep "never against the FM-1" |
| docs/07:88 | WL82 PID unknown | `4C4A:8057` `WL80UBOOT1.00`; SCSI `WL82/UBOOT1.00/1.00` | [reported: transporter, fm1-nes] | Add |
| docs/07:111-117 (§2.2) | the ROM enters USB mode by itself on a failed boot | true for a failed boot; a hung app needs a watchdog or a dongle at power-on | [reported: transporter] | Add the distinction |
| docs/07:119-126 (§2.3) | "The stock app has no reachable equivalent" | stock V15 enters UBOOT on `F0 22 24 35 7D F7`; SDK `go_mask_usb_updata()`; mailbox method | [reported; SDK source verified] | Rewrite §2.3 with the three mechanisms; FM-1_092 unchecked |
| docs/07:151 | jl-uboot-tool marks WL82 "unknown" | `adb3f18` works on FM-1s with 256-byte I/O | [reported: fm1-nes] | Update the mitigation |
| docs/10:71 | WL82 "never exercised" | exercised on FM-1s (transporter, fm1-nes) | [reported] | Update; add transporter to §1.1 (push-pull, polarity A only) |
| docs/11:403-404; docs/14:289-293 and :401; DEVELOPERS.md:309-310 and :670 | the SDK has no task-to-core API | `#C0` name prefix pins to core 0; TCB has `cpu_id`; `#C1` likely | [verified for `#C0`; inferred for `#C1`] | "No API with a core argument; a `#C<n>` name prefix exists"; add C6d–C6f |
| docs/14:399 and :132 | kit audio may be speaker and mic only; TF slot unknown | base board has earphone jack J12 and a TF slot (schematic V1.2) | [verified: SDK PDFs; bought revision unchecked] | Update both rows |
| docs/14:249 (step 3) | enter download mode through the vendor dongle | the kit has its own UPDATA + RESET keys | [reported: JieLi doc 2.3] | Use the keys for the kit; still rehearse the dongle |
| DEVELOPERS.md:833-835 | the FM-1's loader is M-VAVE's own | derived from JieLi's `usb_hid_ota` template; stock step 1 accepts a foreign loader | [inferred; reported] | Reword; point I3/I13 at the OTA-loader branch |
| DEVELOPERS.md:882 | czietz's Pico tool is push-pull and ruled out | FM-1-transporter is push-pull too | [verified: `usb_key.pio`] | Name both |
| DEVELOPERS.md:1161-1172 | open questions before the preview | UBOOT from code: yes; raw reads: yes; `.noinit` survives resets; installs onto `FM-1_9xx` work; custom-app staging at `0xE0000`/`0xE4F00` | [reported] | Move the answers into the I-steps; keep "where stock V15 stages" and distribution open |
| DEVELOPERS.md:1115-1127 (I15) | "MIT, BSD and Apache code plus the SDK's libraries, no GPL" | `system.a` contains a modified FreeRTOS V9 (GPLv2 + exception); `uac_audio*.h` are GPL-2.0 | [verified: SDK] | Reword; add to docs/12 §6 |
| docs/01:13 | markings never carry the part number | `11B8` fits AC7911B8 in JieLi's scheme, but conflicts with LQFP48 | [inferred] | Add as a hypothesis |
| docs/01 §2 | RAM map | `.noinit` usable at `0x01C7C000`–`0x01C7FD50`; cache RAM `0x01F28000`–`0x01F2F000`; `boot_info` 52 B at `0x01C7FD4C` | [reported: Felucca, fm1-nes] | Add rows |
| docs/03 §5 | the modified-loader package hit an error path | Felucca and SLOOP loaders pass stock step 1 | [reported] | Add; list the `FM-1_9xx` range |
| HANDOFF.md:214 and :208 | gitee.com blocked; use the mirrors | Gitee reachable but flaky; the mirrors are stale (amitv87 2024-07; jeffreywugz V1.0.3) | [verified] | Point at Gitee with commit pins |
| docs/04 | no Felucca, SLOOP, fm1-nes or transporter | all four exist | [verified] | Add entries with pins and licences |

## 5. Safety

**What these projects did that our one rule forbids for us:**
- Felucca and SLOOP users install non-stock firmware through the stock path, with no dump. The installer says "at your own risk". For the owner's unit that waits for I9.
- fm1-nes wrote 51 sectors through mask ROM on its maintainer's unit. It relied on a private backup, and programming is not atomic. Its app also replaces the stock USB-MIDI update service, so the way back is only through mask ROM [reported].
- FM-1-transporter erased and rewrote sector `0x92000` on a V15 unit as a self-test [reported].
- **The soft key `F0 22 24 35 7D F7` is not the identity query.** It reboots the unit into mask ROM. It is forbidden before the gate.
  - `fm1t.py` sends it on its own when it sees V15. Never run it against the owner's unit.
  - The upgrade command `F0 22 24 35 7F F7` differs by one byte.
- **FM-1-transporter drives the key push-pull with no series resistors.** docs/10's E1 rules that out for our unit [verified: source].

**Bricking reports:**
- None in Felucca issues #1–#41, SLOOP's 15 issues and PRs, or fm1-nes [reported].
- fm1-nes recorded one unexplained mode change after a write, and a CP932 logging exception in jl-uboot-tool on reset.
- Two failed rollbacks were a host holding the MIDI port (Felucca #32, SLOOP #8).

**Hazards to remember:**
- **Felucca and SLOOP package heads are not stock's.** They carry SDK V1.2.1's `uboot.boot` and a synthetic `isd_config`. That is harmless with their own loader, which never writes the head. It would replace the SPL and its clock and SPI settings if fed to anything that writes `flash.bin` from offset 0 [inferred]:
  - M-VAVE's loader (Baud Girl FINDINGS 5.4);
  - a whole-image jl-uboot-tool restore;
  - our own I3 imaging.
  
  Our tools must refuse any head that is not the device's.
- **Never put a newer SDK's `uboot.boot`, `wl82loader.bin` or key-checking `system.a` into an FM-1 package.**
- **Online-tool operations:** 0x24 and 0x25 erase and write, 0x26 reboots into ROM, and 0x27 reads. They stay under trap 7.
- **Linux `isd_download` is a writer.** Kit only.
- **Installs that reuse the VM region** (`0x93000`+: settings, calibration, maybe the BT MAC) leave foreign data behind on rollback [inferred].
- **UBOOT sessions die if the host drops the device.** The chip then boots flash, so a write must finish in one session [reported: transporter].

## 6. Owner decisions

1. **Platform for the preview: an SDK app (L1) or bare metal (L2)?**
   - *Recommended:* stay on L1 with SDK V1.1.9 for the kit work and the preview. Write the FM-1 board layer at register level and MIT-clean behind `bsp_*`, so an L2 build stays possible. Record this as an ADR and revisit after I8.
   - Why: our float engines, the second-core plan, BLE later, and the compile check all fit the SDK. Felucca proves L2 works, but L2 means our own USB, flash and cpu1 bring-up.
2. **Loader for install and rollback: M-VAVE's `ota.bin` (the current I13) or our own, Felucca-style?**
   - *Recommended:* keep M-VAVE's loader for the preview. It is taken from the user's own V15 and needs no new USB stack.
   - Add Felucca's app-side checks: a known loader, recognised by CRC, and a head equal to the device's.
   - Reconsider our own app-area-only loader after I14.
3. **Recovery tool for the gate.**
   - *Recommended:* JieLi's dongle, rehearsed on the kit in DIP bit 3, as plan A, and our open-drain RP2040 dongle as plan B.
   - Do not use FM-1-transporter as built on the owner's unit: it is push-pull, has no series resistors, and sends the soft key on its own.
   - Port its PIO-USB host idea (MIT) into `dongle/`, so the Mac can run sessions.
4. **May the soft key ever be sent to the owner's FM-1?**
   - *Recommended:* not for the gate. The gate must prove the path that works when no app runs.
   - Before any use, find the `7D` handler in FM-1_092's `app.bin` by disassembly (desk only).
   - After I9, allow it as a convenience entry, recorded in CLAUDE.md.
5. **The SDK pin.**
   - *Recommended:* keep V1.1.9 (`8eae664`) for the libraries and the head. Add the key-check refusal and the blob hashes. Take open-source fixes file by file.
   - Cite Gitee, not the mirrors.
6. **Licence policy for the shareable build.**
   - *Recommended:* treat `system.a`'s FreeRTOS as JieLi's distribution under the FreeRTOS exception; our app does not modify the kernel.
   - Never include `uac_audio*.h`.
   - Write the MIDI descriptors from the spec.
   - Reword I15 and docs/12 §6. This is not legal advice.
7. **Vendor Felucca's `fm6_core.c` (Apache-2.0)?**
   - *Recommended:* yes, as a test oracle in `third_party/felucca-fm6/` with `UPSTREAM.md`, after a diff against msfa.
   - Leave `phys_*.c` (MIT) until there is a use.
8. **Identity and USB names.**
   - *Recommended:* `FM-1_5xx`. Keep stock's VID:PID and the product string `FM-1` for the preview, so existing tools find the device.
   - Never ship a pid.codes test ID.
9. **Read the closed libraries with `llvm-dis` in a container on aeon (a build-host change).**
   - *Recommended:* yes. Keep the output in scratch, never committed.
10. **Contact kurogedelic and Keitark?**
    - *Recommended:* yes, as drafts under `oss-contributions`, sent by the owner.
    - Topics:
      - the push-pull concern;
      - publishing "fm-1-research-lab";
      - fm1-nes's unpublished `STOCK_BOARD_PROFILE.md`, fps and audible output;
      - our pin-map findings in return.

## 7. Sources

- **JieLi AC79 SDK**: https://gitee.com/Jieli-Tech/fw-AC79_AIoT_SDK
  - Branch `release/AC79NN_SDK_V1.2.0` at `e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d` (2026-06-09), which is tag `AC79NN_SDK_V1.2.13_2026-04-20` (`64afb30b`) plus a README change.
  - Compared with tag `AC79NN_SDK_V1.1.9_2023-08-01` (`8eae6645…`) and every tag from V1.2.1 to V1.2.13.
  - Branch `AC791N_OTA_loader` at `79eda0ca3853c781cae942b3e7f705eb49a989ca` (2025-09-13).
  - Apache-2.0 (LICENSE SHA-256 `c71d239d…0ab4`). Closed `.a` files and tools carry no licence. FreeRTOS V9 is GPLv2 with the exception. `uac_audio*.h` are GPL-2.0.
  - Clones: `reference/ac79-sdk`, `reference/ac79-ota-loader`.
- **JieLi docs**: https://doc.zh-jieli.com/AC79/zh-cn/release_v1.2.0/, sections 2.3, 2.18, 7.13, 7.40, 7.41 and 9.2.
- **SDK PDFs** (read, not committed): the kit schematics in `doc/datasheet`, `doc/stuff/usb updater.pdf`, `AC7911B_Datasheet_V1.4.pdf` and `AC791N选型表231122.xlsx`.
- **Felucca**: https://github.com/hugelton/Felucca
  - Tag v1.0, `727f272015da26eb2d0291bd652eba28ff57cb37` (2026-10-05).
  - GPL-3.0-only. `fm6_core.c` is Apache-2.0; `phys_dsp.c` and `phys_symp.c` are MIT.
  - Clone: `reference/Felucca`. Issues #1–#41 were read through the GitHub API.
- **FM-1-transporter**: https://github.com/kurogedelic/FM-1-transporter
  - `a632d923203170e3a08565f4056dbb3fd3d65ca5` (2026-10-01). MIT.
  - Read through the API: README, `docs/PROTOCOL.md`, `docs/DEVLOG.md`, `docs/ARCHITECTURE.md`, `pio/usb_key.pio`, LICENSE.
- **fm1-nes**: https://github.com/Keitark/fm1-nes
  - `main` at `870f3054869c77f03fc1c8a3a425dafa3dfa7b22` (2026-10-03). No tags.
  - PR #17 (2026-10-05) was read as its description only.
  - Licences: Apache-2.0 root; GPL-3.0-only USB audio and packet code; MIT `jl_formats.py` routines, guard patch and `examples/fablenes/`.
  - Depends on PeakRacing/nes `68bdfc8` (Apache-2.0) and jl-uboot-tool `adb3f18` (MIT).
  - Clone: `reference/fm1-nes`.
- **SLOOP**: https://github.com/isod89/sloop-fm1
  - Tag v2.2, `f2b44c219b8a4ac00bc06dca756cdae8a259dd1a` (2026-10-04). GPL-3.0-only.
  - Clone: `reference/sloop-fm1`. Issues and PRs were read through the API.
  - The Melodee fork (`keremimo/melodee`) is mentioned there as having USB audio [reported, not read].
- **Our own material:**
  - `scratch/FM-1_v15_cdn.fwsc` (SHA-256 `db1642b2b6fa5c2c…`, 699,956 B) and its unpack's `jlfw.yaml`;
  - `reference/jl-uboot-tool` `adb3f18`;
  - `reference/FM-1-RE` `95eca84`, `docs/io/05-midi.md:97`.
