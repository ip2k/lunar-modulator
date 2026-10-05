# 01 — Hardware

What the FM-1 is made of, what the stock firmware actually uses, and what still
has to be measured on the bench. Confidence marks: **[verified]** checked in
this project (photos, binaries, SDK files), **[reported]** from a named source,
**[inferred]** our reading.

## 1. The SoC

| Item | Value | Confidence |
| --- | --- | --- |
| Part | JieLi **AC791N**, family codename **WL82** | [verified] product ID string `AC791N_STORY` and `AC791N-v0.01-cfg_tool-v0.10` in the update package (AL-255); SPL byte-identical to the AC79 SDK's `cpu/wl82/tools/uboot.boot` (AL-255) |
| Marking | `C156211-11B8` (aroum's unit) and `C188612-11B8` (the owner's unit) under the slanted "JL" logo; the first group changes per lot, `11B8` is common to both | [verified] aroum's `photo_01.png` and the owner's close-up (`notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md` §2); JieLi markings never carry the real part number ([kagaimiq, chip-marks](https://github.com/kagaimiq/jielie/blob/main/chips/chip-marks.md)). **Hypothesis:** `11B8` fits JieLi's naming for the **AC7911B8**, which has 1 MB of in-package flash and no SDRAM [verified 2026-10-05: `AC7911B_Datasheet_V1.4.pdf` and the SDK's selection table, `notes/2026-10-05-community-repos.md` §2.1]; that it is the FM-1's part is [inferred], and the datasheet lists QFN48, not the LQFP48 reported below |
| Package | LQFP48, leads exposed | [reported] AL-255 `01-hardware-map.md`; photo is consistent (gull-wing leads, not a QFN). The sibling SMK-37 Pro keyboard was identified as AC7911BA in QFN48 by its community |
| CPU | JieLi **pi32v2**: 32-bit, little-endian, Blackfin-derived custom ISA, 16 GPRs, 16/32/48-bit instruction words, algebraic assembly, ELF machine `0xF1` | [reported] kagaimiq `cpu/pi32v2.md`, AL-255 `04-toolchain-and-vendoring.md` |
| Cores | Two pi32v2 "DSP" cores, and **stock uses both**: JieLi's OS runs on cpu0 in the SDK's `CPU_CORE_NUM 1` mode, and the msfa voice render runs on cpu1, outside the OS (docs/11 §2). `CPU_CORE_NUM 1` means one core for the OS, not one core used | [verified] string `SYSTEM-*modified #define CPU_CORE_NUM 1 *-…-@20220920` in the V13, V15 and FM-1_092 `app.bin`; the render loop and its call [verified: V13 disassembly, file `0x86AD6`]; that it runs on cpu1 [reported: AL-255's symbol names; inferred from the `cpu1_run_flag`]; the mode [reported: JieLi AC79 doc 7.40]; family spec from the AC79 SDK README |
| Clock | Family max 320 MHz; stock app runs at **240 MHz** from a 24 MHz crystal | [reported] AL-255 `architecture.md`; SDK README for the family max |
| FPU / accel | Single-precision FPU, hardware FFT/matrix, AES-128/256, SHA, CRC16, RNG | [verified] AC79 SDK README |
| SRAM | **578 KB** on chip, of which 32 KB I-cache and 32 KB D-cache (8-way each) are carved out, so about 514 KB is usable | [verified] AC79 SDK README (`片上集成了共578K字节SRAM`); caches [reported] JL-AC79-DevKit V1.0 listing, 2026-09-30 (docs/07 §3) |
| SDRAM | Some AC79 packages carry 2 or 8 MB SDRAM; **the FM-1 has none** | [verified] `SDRAM_SIZE = 0` in the FM-1's `isd_config.ini`; LQFP48 packages are the SDRAM-less ones [inferred] |
| Radios | Wi-Fi 802.11 b/g/n and dual-mode Bluetooth 5.0 (BR/EDR + BLE) on chip; Wi-Fi unused by the FM-1, Classic BT vestigial, BLE used for BLE-MIDI | [reported] AL-255 `10-bluetooth.md`; SDK README |
| Peripherals | USB 1.1/2.0 device/host, audio DAC/ADC, I2S, SPI, I2C, UART, SDIO, PWM, timers, ADC, cap-touch, RTC | [verified] SDK README and `include_lib/driver/cpu/wl82/asm/*.h` |
| Register map | Public in the SDK: `include_lib/driver/cpu/wl82/asm/WL82.h` (1330 lines, `JL_*` typedefs; SFR windows `lsfr 0x10000`, `bsfr 0x20000`, `hsfr 0x40000`, `psfr 0x50000`) | [verified] |

The AC79 SDK ships datasheets for the AC7911B, AC7913A0/A6, AC7915A and AC7916A
variants under `doc/datasheet/AC791N规格书/` (Chinese). The FM-1's exact
variant is unknown; the LQFP48 marking points at the AC7911 class, and
`11B8` at the AC7911B8 (§1, [inferred]). Pinout work should start from
`AC7911B_Datasheet_V1.4.pdf` in the Gitee SDK (`e30b1ee`; the mirrors carry
V1.1). Most of the board's pins are now named by working code (§3.1).

## 2. Memory and flash

### Address space seen by the stock application [reported: AL-255]

| Range | Contents |
| --- | --- |
| `0x02000000 – 0x0208E59C` | Flash, execute-in-place: `app.bin` (`.text`, `.rodata`, `.data` image) |
| `0x02084820` | `.data` initializer image, copied to RAM at boot |
| `0x01C00000 – 0x01C09E7B` | RAM `.data` (0x9E7C bytes) |
| `0x01C09E7C – 0x01C211FB` | RAM `.bss` (0x17380 bytes) |
| `0x01C14BB4` / `0x01C15BB4` | main / system stack tops (cpu0) |
| `0x01C7FD50` | boot hardware-info struct written from SPL parameters |
| `0x01C7FE00` | RAM interrupt vector table |
| `0x04000120` | cache-locked overlay window (unused in this build, length 0) |
| `0x0001xxxx – 0x0005xxxx` | peripheral SFRs; `0x01EExxxx` interrupt controller |
| `0xFFC0xxxx` | mask-ROM service routines (delay, config write, reset, P33 access) |

Added 2026-10-05 from the AC79 SDK and the community firmware
(`notes/2026-10-05-community-repos.md`):

| Range | Contents | Confidence |
| --- | --- | --- |
| `0x01C7C000 – 0x01C7FD50` | RAM that survives resets and UBOOT entry: Felucca's `.noinit` (crash record, boot counter) | [reported: Felucca `firmware/app.ld`, SLOOP bootguard] |
| `0x01C7FD4C` | `boot_info`, 52 B, in the SDK V1.2.x linker script; AL-255 and Felucca put the stock boot struct at `0x01C7FD50`, and the 4-byte difference is not explained | SDK [verified: `cpu/wl82/sdk_ld_sfc.c` at `e30b1ee`]; the rest [reported] |
| `0x01C7FD80` / `0x01C7FD88` | `UPDATA_BEG`, and `UPDATA_PARM`: the update hand-off (CRC, type `USB_HID_UPDATA = 0x5A0D`, magic `0x5441`, `file_path[32]`, `ota_addr`) | [verified: SDK `sdk_ld_sfc.c`, `include/update/update.h`] |
| `0x01C7FE08` | `r0` when the SPL jumps to the app at `0x02000120` | [reported: Felucca `crt0.S`] |
| `0x01F28000 – 0x01F2F000` | cache-RAM window, 28 KB, usable by an SDK app | [reported: fm1-nes `audit_boot.py`] |

Static RAM use of the stock app is therefore about 135 KB plus heap and the
two 11.5 KB display strip buffers; against 578 KB of SRAM that leaves a lot of
headroom for more voices, effects or a sequencer.

**Load address** [verified: the `entry-point: 33554720` (`0x02000120`) of
our V15 and FM-1_092 `jlfw.yaml` unpacks; reported: Felucca, SLOOP and
fm1-nes all boot there]: `app.bin` runs from `0x02000120`, not
`0x02000000`. V15's `app.bin` starts with `04 81 80 00` ("goto +4; rts")
[verified: our V15 unpack; decoding reported: Felucca `tools/build.py`]. The
runtime addresses AL-255 read from literals stand, but each is `0x120` above
its file offset, and the app spans `0x02000120`–`0x0208E6BC`.
- AL-255's `cpu1_boot_start` writes `0x020001B8` to the cpu1 mailbox; that
  lands on the cpu1 vector at file `0x98` only with this offset [verified:
  V13 disassembly].
- The `.data` image (`0x9E7C` bytes) would overrun V13's 583,068-byte file
  by `0x100` bytes from file `0x84820`; from `0x84700` it fits [verified:
  arithmetic].
- docs/02 §3 used to give the SPL's jump as `0x020000A0`; the SPL jumps
  to `0x02000120` with `r0 = 0x01C7FE08` [reported: Felucca `crt0.S`].
- RAM-code addresses that AL-255 derived from file offsets are therefore
  `0x120` low. That is how cpu1's entry was read as the cross-core IPC path
  (docs/11 §2).

### Flash layout (1 MB) [reported: AL-255 `architecture.md`, from the JLFS directory in `FM-1.fwsc`]

| Flash offset | Contents |
| --- | --- |
| `0x00000` | flash header (burner, VID/PID `AC791N`) |
| `0x000A0` | SPL `uboot.boot` ("UBOOT2.00", 14384 bytes) |
| `0x038D0` | `isd_config.ini` (699 bytes; chip key `0x980F`) |
| `0x04000` | app area (JLFS, chip-key encrypted): directory, `app.bin` at `0x4120` (583068 bytes in V13), `cfg_tool.bin` at `0x926BC` (383 bytes), `cfg` at `0x9283B` |
| `0x94000` | VM region: key/value config store, 0x55000 bytes (holds BT MAC, wheel calibration, settings) |
| `0xE9000` | BTIF region (0x1000) |
| `0xEA000` | USR region: user patch storage (0x12000) |
| `0xFC000+` | free; `key_mac` at `0xFF000` |

**V15 moves the boundary [verified, `notes/2026-09-06-bench.md`]:** app area
`0x4000–0x93000`, `cfg_tool.bin` at `0x920DC`, VM at `0x93000` (0x56000 bytes);
`BTIF`, `USR` and the SPL/config region are unchanged.

**Baud Girl's FM-1+VA moves it again [verified, `FM-1_092` package,
`notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md` §3]:** `PRCT` `[0, 0xD9000)`,
VM at `0xD9000` shrunk to 0x10000 (64 KB), so the app area can reach
`0xD9000`; `BTIF`, `USR`, `key_mac` and the head are unchanged. The owner's unit
runs this layout since installing FM-1+VA.

aroum's README assumes a 4 or 8 MB flash. The package directory and the
SMK-37 Pro notes both point at **1 MB**. No discrete SPI flash chip is visible
in the photos, so the flash is most likely in-package **[inferred]**. Its
JEDEC ID reads `0x856014` (Puya, 1 MiB) on other owners' FM-1s [reported:
FM-1-transporter, fm1-nes's guard patch, SLOOP's loader check]; in-package
or not is still open. Read the ID on this unit in mask-ROM USB mode (docs/07).

## 3. The board

Source: aroum's teardown photos (`photos/photo_01..05.png` in
[aroum/fm1-custom-fw](https://github.com/aroum/fm1-custom-fw/tree/main/photos))
plus AL-255's disassembly. Photos are not copied here; they carry no license.
Since 2026-09-29 there are also the owner's own photos of their unit (same
`V07` layout, later batch), in [`photos/2026-09-29/`](../photos/2026-09-29/)
and described in `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md` §2.

| Item | Observation | Confidence |
| --- | --- | --- |
| Mainboard | Silkscreen `DX7 MB V07 260620` (2026-06-20), bottom marking `MA 26 06 24` on aroum's unit; `DX7 MB V07 260708`, bottom `MC 26 0727` on the owner's | [verified] aroum photos 2, 3, 4; owner's photos 2026-09-29 |
| Case | 6 self-tapping screws underneath, one hidden under the centre sticker; rubber feet stay on; plastic latches along the seam | [reported] aroum README §1.3 |
| USB-C | `J6`, top edge, data to the SoC's USB PHY; composite USB-MIDI + UAC1 audio device | [verified] photo 1; enumeration [reported] AL-255 |
| Jacks | two 3.5 mm TRS on the top edge: stereo audio out and MIDI IN (TRS), **input only**. Read as `J7`, `J9` on aroum's photo; on the owner's board (later batch) they are `J3`, beside the USB-C, and `J7`, and `J3` is the MIDI input, with the optocoupler `PC1` at its pads | [verified] photo 1/4; owner's [`2-bottom.jpg`](../photos/2026-09-29/2-bottom.jpg); `J3` = MIDI [inferred, strong]; function [reported] product listings, manual, Baud Girl's FM-1+VA manual; input only also fits the code (§3.1: UART RX on PH8, no TX) |
| Power switch | slide switch at top right | [verified] photo 3/5 |
| Battery | Li-Po `DTP704060`, 3.7 V 2000 mAh 7.4 Wh, dated 2026-06-24 (aroum) / 2026-07-31 (owner), bottom-side 3-wire connector `电池` (`正` +, `负` −, `NTC`) | [verified] photo 4; owner's photo 2 |
| Speaker | SMD 2-pin connector labelled `喇叭` (speaker), `+S`/`−S`: read as `J11` on aroum's photo, `J13` on the owner's; near two 16 V/100 µF electrolytics (`C112`, `C113`) and a 10 V/100 µF (`C111`) | [verified] photo 4; owner's photo 2; amp part unidentified |
| Display | 1.54" TFT, **240×240 RGB565 over SPI1** (SFR base `0x11D00`), 12–14 pin FPC `J12`; command set `2A/2B/2C/29` (ST7789/ILI9341 class); flushed in ten 240×24 strips. The controller is an **ST7789V** on PC7–PC10 with the backlight on PA2 (§3.1) | [reported] AL-255 `08-display.md`; FPC [verified] photo 1; 1.54" [reported] user manual via search snippet; controller and pins [reported: Felucca, fm1-nes] |
| Knobs | **8 rotary controls**: a 2×2 block (`RW1` with an index mark, i.e. a potentiometer, plus three encoders including `E6`) and a row of four encoders `E2`–`E5` (the owner's photo, USB edge up). Baud Girl's manual names them MASTER (volume), SELECT, ALGORITHM, PRESETS and KNOB1–KNOB4, which fits `E2`–`E5` = KNOB1–KNOB4 and `RW1` = MASTER. **All seven encoders are scanned in the key matrix and decoded in software; MASTER is a pot on PB6 (ADC channel 4); ADC channel 3 is the battery on PB1** (§3.1). AL-255's "two quadrature encoders and ADC channels 3 and 4" reading is superseded; WL82 has one hardware quadrature decoder, and neither firmware uses it | layout [verified] photos; names [reported] Baud Girl's manual; `RW1` = MASTER [inferred, now strong: a pot on the ADC]; matrix encoders and ADC use [reported: Felucca, fm1-nes, SLOOP]; one RDEC [verified: `WL82.h`] |
| Keys | 27 silicone keys on interdigitated contact pads, each with an LED and a diode beside it. Baud Girl's manual calls them "touch keys"; the pads look like contacts, not capacitive electrodes | [verified] photos 3/5, owner's photo 3; reading [inferred] |
| Buttons | 14 tactile switches with LEDs (`K30…K41`, `LED31…LED56`); the firmware's input IDs 0–13 are the buttons and 14–40 the 27 keys | switches [verified] photos 2/3; the count of 14 and the IDs [reported: Felucca, fm1-nes] |
| Matrix column drivers | `U2`, `U3`: two **SOIC-16** shift registers; `U3` reads `74HC595D`. They select the 11 columns of the key matrix (earlier read here as LED drivers); the LEDs light on the selected column (§3.1) | package and marking [verified] owner's photo 3 (leads counted 2026-09-29; the earlier "SOIC-20" was wrong); role [reported: Felucca, fm1-nes] |
| Key/button scan | an 11 × 6 diode matrix (41 inputs plus the encoders' contacts) with debounce, plus per-bank locks; stock clocks the 595s on SPI2 (`0x11E00`) | [reported] AL-255 `07-input.md`; matrix shape and SPI2 [reported: Felucca, fm1-nes] |
| Crystal | 24.000 MHz can next to the SoC | [verified] the owner's close-up (aroum's photo 1 shows `24.0…`) |
| Antenna | a bare **wire** soldered to pad `P1`, labelled `天线` (antenna); the SoC area's silkscreen box has oblong corner slots, probably for an unpopulated shield-can frame | wire [verified] photo 1; shield [inferred] |
| Passives | `L2 100` buck inductor for the SoC, `L1 4R7`, ferrites `FB1..FB6` on audio | [verified] photo 1 |
| Unidentified | `U5` (QFN-20 class, near the jacks, with ferrites `FB4`/`FB5`) and `U9` (8-lead SOP): audio amp / codec candidates, one of them probably the I2S codec on ALNK0 (§3.1) [inferred]; `U6` (SOT-89/SOT-223 class, probably a regulator); an SOP-10 marked **`SLS316D` / `6253KD`** right of `J12` (designator not legible, function unknown); `U11` (SOT-23-6), `Q2`, `Q4`, `D1..D57`; a **3-pin SOT-23 plus `R21` on the USB data/VBUS path right under J6** [verified present]; a **bottom-side SOIC-8 `U12` near the USB-C with `R35`/`R36` and `R32` = `R100` (0.1 Ω)**: charger IC [inferred] or, if it is an SPI NOR flash, an external-programmer recovery path (docs/07 §2.5); its marking is still unread. `PC1` = `OCIC P2362`, a 5-lead SO6-style TLP2362-class photocoupler: the **MIDI IN optocoupler** [inferred, strong] | `notes/2026-09-08-desk-review.md`; `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md` §2 |
| Debug access | **No header, no test pads, no recovery button.** The "unpopulated 3-pin header" left of U2 (desk review 2026-09-08) is the through-hole leads of the bottom-side battery connector, and the plated holes labelled `J14` carry the leads of `C111`–`C113`: in the owner's photos, flipped and aligned on a mounting hole, the pins land on those pads. The round bare pads near the SoC are fiducials | aroum README §1.2; overlay [verified] `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md` §2 |
| Reset | `RESET=PB01_08_0`: hold PB01 low for 8 s to reset (long-press power path). **Not** a recovery input. PB1 is also the battery's ADC input, so firmware keeps it analog | [reported] AL-255 decode of `isd_config.ini`; battery [reported: Felucca `hal/fm1_adc.h`] |

### 3.1 Pin map from working code [reported, 2026-10-05]

Two separate code lineages drive this board and agree on it: Felucca 1.0
(hugelton, `727f272`) with its fork SLOOP (isod89), marked **F**, and fm1-nes
(Keitark, `870f305`), marked **N**, whose constants are copied from stock
FM-1_010. Felucca and SLOOP are GPL-3.0-only, so these are facts restated in
our words, not code. SFR base addresses were checked against `WL82.h`
[verified]. Everything else is [reported] from working code, unless marked.
The detail is in `notes/2026-10-05-community-repos.md` §3.5. I4 (DEVELOPERS.md)
checks each row against V15 with the vendor `objdump`.

| Function | What the code does | Source | Against our own photos and notes |
| --- | --- | --- | --- |
| TFT | ST7789V on SPI1 `0x11D00` (IRQ 16): CS PC7, D/C PC8, SCK PC9, MOSI PC10; no reset line; about 12 MHz (`BAUD 4`); a 21-record init table from FM-1_010 | F `hal/fm1_lcd_hw.h`; N `display_test.c` | Agrees: AL-255's SPI1 base and `2A/2B/2C` commands; FPC `J12` [verified]. Adds the controller and pins |
| Backlight | PA2, active low (F); N drives it low, role unstated | F `hal/fm1_lcd_hw.h`; N | Not visible in the photos |
| Key matrix | 11 columns × 6 rows. Two 74HC595s: PA4 data, PA3 clock, PA1 latch; stock clocks them on SPI2 `0x11E00`, IRQ 37 (N), F bit-bangs them. Rows read on PA0, PA5–PA8 and PB7 with pull-ups, low = closed | F `hal/fm1_input.h`; N `fm1_wl82_keyscan.c` | Agrees: two SOIC-16 595s (`U2`, `U3`) and a diode beside every key [verified]. Differs: §3 called the 595s LED drivers |
| Input IDs | 41: 0–13 the 14 buttons, 14–40 the 27 keys F3–G5 | F `hal/fm1_input.h`; N `fm1_stock_keys.c` | Agrees: 27 keys [verified] and AL-255's 41 inputs [reported] |
| LEDs | lines PA9, PA10, PH6 and PH9, lit on the selected column; F dims with one frame in four; N drives no LEDs | F `hal/fm1_input.h` | Agrees: an LED beside each key and button [verified]. The drive scheme beyond that is open (§6, LEDs) |
| Encoders | 7 (SELECT, ALGORITHM, PRESETS, KNOB1–4) as A/B contacts in the matrix, decoded in software with stock's masks `0x2814`/`0x4182`; the one hardware decoder (RDEC) is unused | F `hal/fm1_input.h`; N `peripheral_logic.c`; one RDEC [verified: `WL82.h`] | Agrees: seven `E` encoders [verified]. Differs from AL-255's two-decoder reading |
| MASTER | pot on PB6, SARADC channel 4 (`0x13100`), 10-bit | F `hal/fm1_adc.h`; N `fm1_volume.c` | Agrees: `RW1` is the only pot [verified], so `RW1` = MASTER |
| Battery | PB1, SARADC channel 3, through a divider; stock thresholds 531, 561, 591 | F `hal/fm1_adc.h`, `ui_draw.c` | Agrees with AL-255's "battery divider possibly on channel 3" and with `RESET=PB01_08_0` [reported] |
| Audio | ALNK0 `0x12E00` (I2S), channel 3, `IIS_PORTC`, MCLK out, 24-bit left-justified in 32; IRQ 11 at priority 3; 64 frames per half (a 1,024 B ping-pong); F runs at 24 MHz / 544 = **44,117.6 Hz**. The internal DAC (`JL_AUDIO`, `0x12F00`) is not used | F `hal/fm1_audio.h`, `src/usb.c`; N `fm1_wl82.c:166-180` | Differs from AL-255's "internal DAC" reading (§4). The codec is probably `U5` or `U9` [inferred] |
| Codec lines | F drives PC0, PC1, PC2 and PC6 as GPIOs during bring-up and calls them codec control lines; N says PC6 is the channel-3 data line. **The two disagree**; PC0–PC2 are perhaps the I2S clocks and PC6 the data [inferred] | F `hal/fm1_audio.h`; N | Open (§6, audio) |
| TRS MIDI in | UART1 `0x12100` RX on PH8, through input channel 1; 31,250 baud; RX DMA ring, polled; no TX pin | F `hal/fm1_uart.h` ("RX verified on hardware" in F 1.0) | Agrees: the jack is input only, and on the owner's board MIDI IN is `J3` with optocoupler `PC1` at its pads [verified photo; inferred]. PH8 is the lead to look for when tracing PC1's output (DEVELOPERS.md, bench check 1) |
| Flash | JEDEC `0x856014` (Puya, 1 MiB); CS# PD0; runtime writes on SPI0 `0x11C00` with the SFC off, from RAM | F `hal/fm1_flash.h`; N guard patch; FM-1-transporter | Agrees: 1 MB and no discrete flash seen [verified photos]; in-package still open (`U12`, §6) |
| Watchdog | P33 `P3_WDT_CON`, about 8 s | F `hal/fm1_sys.h` | — |
| Power (SDK builds) | VDDIOM and VDDIOW 3.2 V, VDC14 1.60 V with DCDC, SYSVDD 1.38 V, LVD 2.6 V: stock's values, not the SDK demo's | N `boot/board_power.c` | — |

## 4. Interfaces as the stock firmware exposes them [reported: AL-255 `06-usb.md`, `05-midi.md`, `11-ota-protocol.md`]

| Interface | Details |
| --- | --- |
| USB, normal mode | VID:PID `4C4A:C755` ("LJ" = JieLi), strings "FM-1 Midi" / "FM-1 Audio" / "Jieli Technology"; USB-MIDI on a 64-byte bulk endpoint pair (EP4) and a UAC1 24-bit stereo isochronous audio interface; serial = chip ID hex. **[verified on the owner's unit 2026-09-06]** USB 2.0 full-speed, `bcdDevice 1.00`, device-level product string `FM-1`, a 16-hex-digit serial (the chip ID; not reproduced here), five interfaces (0 audio control, 1–2 audio streaming = 2 out / 2 in at 44.1 kHz, 3 audio control, 4 MIDI streaming); CoreMIDI port `FM-1`, CoreAudio device `FM-1 Audio` |
| USB, OTA mode | VID:PID `4D4A:4155` ("ota-FM-1"), same MIDI port name; the OTA loader runs from RAM at `0x01C0A800` |
| UART MIDI | DIN over TRS on the UART at SFR `0x12100`, RX DMA, MIDI-thru merge to TX. RX is on PH8, and no TX pin is known on the board [reported: Felucca; §3.1] |
| BLE-MIDI | GATT service, notifications on ATT handle `0x72`; Classic BT profiles (A2DP/AVRCP/HFP) linked but vestigial |
| Audio | AL-255 read an internal DAC via a DMA ring, 44.1 kHz, 64-sample blocks, with digital volume and analog trim calibration in firmware. **Two working firmwares instead send audio over ALNK0 (I2S) to an external codec**, at 44,117.6 Hz in 64-frame halves on IRQ 11 [reported: Felucca, fm1-nes; §3.1]. To confirm in V15: accesses to `0x12E00` (ALNK0) against `0x12F00` (`JL_AUDIO`) |
| ADC | SARADC channel 4 is MASTER (pot on PB6) and channel 3 the battery divider on PB1 [reported: Felucca, fm1-nes; §3.1]. AL-255's "wheels" are SDK names; the FM-1 has no wheels |
| Storage | NOR flash over SPI0 (`0x11C00`) with SFC command mode (`0x40200`); FatFS-derived filesystem; ping-pong VM key/value store; DX7 banks as files under `/mnt/sdfile/app/usr` |

## 5. What the SoC gives an open firmware

- Compute headroom: the stock app runs at 240 MHz of a possible 320. It
  renders its 12 msfa voices on the second core and everything else,
  effects included, on the first (docs/11 §2). How loaded either core is has
  not been measured.
- 578 KB SRAM against ~135 KB static use.
- A colour TFT with a fast SPI path and an existing strip-buffer rendering
  model that a custom UI can copy.
- Class-compliant USB-MIDI plus USB audio already proven on this silicon.
- Open firmware already proven on this board: Felucca and SLOOP run bare
  metal on one core, and fm1-nes runs an SDK app [reported; docs/04].
- A public register map (`WL82.h`) for blob-free drivers, and Apache-2.0 SDK
  sources for reference.

## 6. Open questions for the bench

The knob question (which encoders use hardware decoders, and what the two
ADC channels read) is answered in §3 and §3.1 [reported: Felucca, fm1-nes];
I4 checks it against V15.

1. **Flash**: JEDEC `0x856014`, Puya, 1 MiB on other owners' units
   [reported, §2]. Still open: in-package or discrete, and the ID on this
   unit (mask-ROM USB mode).
2. **Exact AC791N variant** and therefore pinout: AC7911B8 is the
   hypothesis (§1), against a QFN48-versus-LQFP48 conflict. Match the pins
   to the AC7911B datasheet; locate USB D+/D−, the UART candidates (`PB00`,
   `PB05`, `PA05` per SDK comments) and the debug-TAP options (`PA9/PA10`,
   `PB1/PB2`, `PB6/PB7`, or on the USB pins per `sdtap` in the SDK's
   `isd_config.ini`). PA9/PA10 are LED lines, PB1 the battery, PB6 MASTER and
   PB7 a matrix row (§3.1), so only the USB-pin TAP looks free [inferred].
3. **Display**: an ST7789V on PC7–PC10 with the backlight on PA2 [reported,
   §3.1]. Still open: the FPC pinout, and the controller ID on this unit
   (`RDDID` `0x04` over SPI).
4. **Audio**: which part is the I2S codec on ALNK0 (`U5` or `U9`), what
   PC0, PC1, PC2 and PC6 do (§3.1: the two code lineages disagree), the
   amp, and the SOP-10 marked `SLS316D`.
5. **Charger** IC. Whether the SoC boots on USB power with the switch off is
   answered: it does not enumerate at all with the switch off [verified
   2026-09-06, `notes/2026-09-06-bench.md`], so the switch is the power-up
   moment for the `USB_KEY` attempt.
6. **LEDs**: the lines are PA9, PA10, PH6 and PH9, lit on the column the
   595s select [reported, §3.1]. Still open: the drive scheme (current,
   multiplexing duty, how the dim state is made in stock).
7. **`U12`** (bottom SOIC-8 near the connectors): charger or external flash?
   Read the marking.
