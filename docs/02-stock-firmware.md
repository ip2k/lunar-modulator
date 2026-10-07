# 02 — The stock firmware

What ships on the FM-1, how it boots, what it is built from, and the evidence
that its synth engine is the open-source msfa/Dexed core. Confidence marks as
in docs/01.

## 1. Versions and packages

| Version (device identity) | Where it came from | Notes |
| --- | --- | --- |
| `FM-1_009` (package folder "V13", 2026-07-03) | `FM-1.fwsc` (704084 bytes) analysed by AL-255 | Full disassembly, byte-identical reassembly |
| `FM-1_014` ("V14", updater dated 2026-07-06) | Embedded Qt resource in `M-UPGRADE-FM1.exe`; `FM-1.fwsc` 704052 bytes. **Also what the macOS `M-UPGRADE-FM1.dmg` downloaded 2026-09-06 embeds** (same 2026-07-08 build) [verified] | `app.bin` 1888 bytes larger; `uboot.boot`, `cfg_tool.bin`, `ota.bin` byte-identical to V13. Adds MIDI program change per M-VAVE's video |
| `FM-1_015` ("V15", CDN file dated 2026-07-30) | `https://yms-file-store.oss-cn-hongkong.aliyuncs.com/software/firmware/FM-1.fwsc`; 699956 bytes, sha256 `db1642b2…db8a` | **Analysed here 2026-09-06** (`notes/2026-09-06-bench.md`) [verified]: `app.bin` 581564 bytes (3392 smaller than V14); `uboot.boot`, `isd_config.ini`, `cfg`, `cfg_tool.bin` and `ota.bin` byte-identical to V14; app area shrinks by 0x1000 and VM grows to 0x56000 at `0x93000`; msfa table at `0x8BE8C`; new strings for glide (`Fingered`/`Full Time`), three sequencer pages, two "Globe" pages, reordered OP pages, a patch `Rename` UI. Running on the owner's unit |

The updater apps (`M-UPGRADE-FM1.app` on macOS, `M-UPGRADE-FM1.exe` on Windows)
are Qt6 + RtMidi programs with the firmware embedded as a resource
(`usb_hid_ota.bin`, `@JMUA`/`JLUFW` signatures) **[reported: aroum]**. Version
naming is inconsistent between filenames, marketing (V09/V14/V15) and the
device identity string; always read the identity from the package or device.

## 2. Package format [reported: AL-255, kagaimiq; unpacked copies inspected here]

`FM-1.fwsc` is a JieLi **UFW** update container around a "new-fw" (JLFS) flash
image, exactly what `isd_download`/`ufw_maker` produce for any AC79 product.
kagaimiq's `jl-misctools/firmware/fwunpack_newfw.py` unpacks it (this is what
AL-255's `extract.sh` and probonopd's SMK-37 notes use).

| Entry | Size | Purpose |
| --- | --- | --- |
| `flash.bin` | 0x94000 | the flash image below the VM region |
| `top/uboot.boot` | 14384 B | SPL, "UBOOT2.00", `sha256 730e54f0…d3ef`; byte-identical to `cpu/wl82/tools/uboot.boot` of SDK release `AC79NN_SDK_V1.1.9_2023-08-01` (AL-255) |
| `top/isd_config.ini` | 699 B | packed `[SYS_CFG_PARAM]` entries: `SPI=4_1_0_0`, `OSC0 24MHz`, `UTBD=1000000`, `RESET=PB01_08_0`, `UPDATE_JUMP=0`, `SDRAM_SIZE=0`, no `UTTX`/`UTRX` pins, no double-bank keys; V15's also carries `SYS_CLK`, `HSB_DIV` and `LSB_DIV` keys [verified 2026-10-05: key names in our V15 unpack; values not decoded], which set the clock a bare-metal app inherits from the SPL |
| `files/app.bin` | 583068 B (V13) | the application, SFC-encrypted in flash with chip key `0x980F`, XIP at `0x02000000`, entry `0x02000120` [verified: `entry-point: 33554720` in our V15 and FM-1_092 `jlfw.yaml`]; its first word is `04 81 80 00` ("goto +4; rts") [verified: our V15 unpack; decoding reported: Felucca] |
| `files/cfg_tool.bin` | 383 B | packaged configuration/calibration resource |
| `files/cfg` | 0xB79 | JLFS daisy-chain with `eq_cfg_hw.bin` etc. |
| `ota.bin` | 19969 B | nested bootable image `usb_hid_ota.bin`: the **USB-MIDI OTA loader**, six LZ4 blocks, 23324 B decompressed, load address `0x01C0A800` |
| `script.ver`, `info.log`, `USR`, `blimit.bin`, `tail.bin` | small | `script.ver` decrypts to `AC791N-v0.01-cfg_tool-v0.10` |

Integrity is **CRC-16/CCITT-FALSE everywhere** (UFW header, entry list, entry
data, nested OTA image). There is **no RSA/ECDSA signature** — confirmed
independently by aroum (updater strings) and AL-255 (loader disassembly). The
SFC cipher with the chip key is obfuscation, not authentication; the key is in
the package.

## 3. Boot chain [reported: AL-255 `io/01-boot.md`, kagaimiq `what-is-uboot.md`]

1. **Mask ROM** ("UBOOT1.00" capable) loads the SPL from flash `0xA0` and jumps
   to it. If the flash does not boot, or if the `USB_KEY` signal is present on
   D+/D−, it stays in ROM and exposes a USB mass-storage download mode (docs/07).
2. **SPL `uboot.boot`** ("UBOOT2.00", generic AC79 SDK build) applies
   `isd_config.ini`, maps the JLFS app area for XIP and jumps to the app's
   first byte at `0x02000120` with `r0 = 0x01C7FE08` [entry verified: our
   `jlfw.yaml`; `r0` reported: Felucca `crt0.S`]. This page said `0x020000A0`
   until 2026-10-05; docs/01 §2 has the evidence.
   The debug build's strings show generic support for two directory heads and
   an `update from inside flash` / `usb_update_mode` path; the FM-1 config
   provisions only **one application bank**.
3. **Application CRT** at `0x02000120`, the image's first byte (docs/01
   §2): set stacks, zero `.bss`, copy `.data` from `0x02084820`, save boot
   parameters to `0x01C7FD50`, PLL to 240 MHz, board init (keys, ADC, SPI
   display, audio server at ~44.1 kHz), create `usr_app_task`, start the
   scheduler. The audio leaves over ALNK0 (I2S) to an external codec, not
   the internal DAC [reported: Felucca, fm1-nes; docs/01 §3.1].

## 4. What the application is made of

AL-255 classified 2062 call-target-derived functions in V13 **[reported]**:

| Subsystem | Functions | Origin |
| --- | --- | --- |
| Bluetooth (btctrler + btstack, BLE + BR/EDR, profiles) | 719 | JieLi closed `.a` libraries |
| RTOS (FreeRTOS-derived SMP kernel, JieLi `os_*` API, dlmalloc) | 224 | JieLi SDK (partly `.a`) |
| Storage (NOR/SFC, FatFS + exFAT, VFS, VM store) | 215 | JieLi SDK `fs.a` |
| UI (`ui_core` widget tree + FM-1 menu) | 165 + 91 | JieLi `ui.a`/`ui_draw.a` + M-VAVE glue |
| Audio out (DAC, DMA, jlstream, mixer) | 137 | JieLi `audio_server.a` / drivers |
| libc / libm / soft-float | 103 + 46 | toolchain libraries |
| USB device stack (MUSB-derived, USB-MIDI + UAC1) | 74 | JieLi SDK |
| Security (AES/SHA-256/HMAC/P-192, SSP, update checks) | 70 | JieLi SDK |
| Peripherals, boot, power | 55 + 42 + 21 | JieLi SDK |
| MIDI parser/routing/DX7 SysEx/arp/sequencer | 28 | **M-VAVE** |
| App state machine | 26 | **M-VAVE** |
| FM synth engine | 20 | **msfa / Dexed** (Apache-2.0) |
| Effects (reverb, phaser, chorus, filters) | 9 | M-VAVE or SDK (`lib_reverb_cal.a` exists in the SDK) |
| Input scan, patch store | 3 + 3 | M-VAVE |

Build stamps in V13 `app.bin` **[verified]**:

```
INCLUDE_BTCTRLER-$17e777e   INCLUDE_BTSTACK-$ac3ebaf   INCLUDE_DRIVER-$affd8c5
INCLUDE_MEDIA-$f7109fe      INCLUDE_NET-$6addaec       INCLUDE_SERVER-$4199060
INCLUDE_SYSTEM-$241dfb0     INCLUDE_UPDATE-$0c1663e    INCLUDE_UTILS-$77f38d5
DRIVER-*modified*-liangyongxin-@20231109-$9aaf4e5
SYSTEM-*modified #define CPU_CORE_NUM     1 *-fengshunjian-@20220920-$fdc21c0
UPDATE-*modified*-tanchiquan-@20230817-$2374938
JL-BR22
```

The `JL-BR22` string misled early analysis toward the AC693N (BR22) family; it
is inherited library naming, not the SoC (AL-255, corroborated by the SPL and
package identity).

The update loaders the app knows about **[verified strings]**:
`usb_hid_ota.bin` (the USB-MIDI OTA loader M-UPGRADE uses), `usb_update2.bin`,
`ble_ota.bin`, `ble_app_ota.bin` (a **BLE OTA** path exists, presumably for the
M-VAVE phone app; JieLi publishes Apache-2.0 Android/iOS `JL_OTA` client SDKs).

## 5. The synth engine is msfa (Dexed) — verified here

AL-255 concluded from byte-exact DX7 lookup tables and the parameter surface
that the engine is Google's *music-synthesizer-for-android* (msfa) core as used
by Dexed, Synth_Dexed, MicroDexed and MiniDexed. This project re-checked one
concrete, hard-to-fake artifact: the 32×6 byte `FmCore::algorithms` table from
msfa's `fm_core.cc`.

`tools/check_msfa_table.py` finds it at **offset `0x8C46C` of V13 `app.bin`**
and at the corresponding place in V14 **[verified]**. All 32 rows match Google's
msfa exactly, rows 4 and 6 included, where the sixth operator's flag is `0x41`:

```
         FM-1               Google msfa        Dexed (Felucca's port of it)
alg 4:   41 11 94 01 11 14  41 11 94 01 11 14  c1 11 94 01 11 14
alg 6:   41 94 01 14 01 14  41 94 01 14 01 14  c1 94 01 14 01 14
```

`0x41` = `FB_IN|OUT_BUS_ONE` is the receiving end of the DX7's feedback loop,
whose sending end is the `0x94` operator (`FB_OUT|IN_BUS_ONE|OUT_BUS_ADD`): the
multi-operator topology the real DX7 uses for algorithms 4 and 6. msfa's
`FmCore` marks that loop but runs only an operator fed back to itself ("todo:
more than one op in a feedback loop"), so with this table those two algorithms
play without feedback. `0xC1` (`FB_OUT|FB_IN|OUT_BUS_ONE`) feeds the sixth
operator back to itself instead, an approximation. Google's repository has had
`0x41` since its first commit (`a99ac7a`, 2012-03-04) **[verified: `git log -S`
on google/music-synthesizer-for-android; `engines/third_party/msfa/`]**, and
Felucca's port of Dexed's msfa has `0xC1` **[verified:
`engines/third_party/felucca-fm6/fm6_core.c`; Dexed itself not checked]**, so
the FM-1's table is Google's original, or an msfa-family copy from before such
a change **[inferred]**. Until 2026-10-05 this section had it the other way
round (`0xC1` as msfa's original, `0x41` as a Dexed-family fix). Either way the
engine is msfa-lineage code. The FM6 engine (`engines/msfa.md`) runs Google's
table and closes the two loops in its own code.

It is msfa-lineage in its tables, algorithm table, envelope and patch format,
but not in its operator arithmetic. V15's operator works in the log domain
(exponent and log-sine tables, no phase interpolation, attenuation ramped
per sample across each block), where msfa multiplies a linear gain, and its
three-operator kernel runs algorithm 4's feedback loop, which msfa's `FmCore`
leaves out **[reported: Echomatter, PR #1 here; both tables equal its
formulas entry for entry, verified 2026-10-06]**. So the FM-1 is
sound-compatible with msfa at the level of patches, not of the arithmetic.
Details: `notes/2026-10-06-echomatter-pr1.md`.

Other supporting evidence: the DX7 parameter names (`Algorithm`, `Feedback`,
`Osc Sync`, `Lfo Sync`, `BreakPoint`, `L Depth`, `R Depth`, `RateScale`,
`A ModSens`, `KeyVelocity`, `OscMode`, `FreqCoarse`, `FreqFine`, `Detune`),
the `Dx7 32 Voice Save To` bank UI, 155-byte edit buffer → 128-byte VMEM pack,
12 voices with a 468-byte stride, 64-sample render blocks, RAM-resident
`dx7note_compute_block` and `fm_core_render` kernels **[reported: AL-255
`04-synth-engine.md`]**. The factory bank is reported by the community to be the
literal Yamaha DX7 ROM1A cartridge.

**Why this matters for an open firmware:** the DSP that defines the FM-1's
sound has an open-source reference implementation. A custom firmware can be
*sound-compatible with the stock unit* (same patches, same engine, including
the ability to load DX7 `.syx` banks) without decompiling anything. What is
proprietary and would have to be re-implemented is the glue: menu tree, MIDI
routing, arpeggiator, 16-step sequencer, effects, patch storage.

**Licensing note.** The msfa files are Apache-2.0, also inside Dexed and
Synth_Dexed, so their presence creates no source-disclosure obligation for
M-VAVE. Only if GPL-3.0-only parts of Dexed (e.g. `PluginFx`) or of
Synth_Dexed were also copied would GPL terms apply. That has **not** been
checked and is not claimed here; it is listed as a research item in docs/08.

## 6. MIDI surface [reported: AL-255 `05-midi.md`, manual snippets]

- Three input routes (USB-MIDI, UART DIN, BLE-MIDI) merged through one parser
  with running status; MIDI-thru to the UART.
- Note on/off with velocity, 12-voice allocation/stealing, CC 1/2/4/64, 14-bit
  pitch bend; program change from `FM-1_014`; CC control of parameters from V15.
- **Official MIDI map [reported: M-VAVE "FM-1 MIDI EN" guide, V14/V15;
  `notes/2026-09-08-desk-review.md` §3]:** note channel defaults to Omni;
  Program Change `0–127` → Voice 001–128; channel aftertouch; **FX channel
  defaults to MIDI channel 2** with CC 0–23 in six groups of four (Filter:
  Switch, Type LPF/BPF/HPF, Cutoff 0–107, Q 0–10; Reverb: Switch, Type
  Room/Hall/Plate, Decay, Mix; Delay: Switch, Decay, Rate, Mix; Distortion:
  Switch, Gain, Tone, Level; Chorus and Phaser: Switch, Freq, Depth, Mix;
  0–100 unless stated); **System Real-Time** `F8` clock, `FA` start from
  step 0, `FB` = start, `FC` stop. benny-sparra confirmed CC 0/2 on a V15
  unit. Sending CC 1 on the FX channel changes Filter Type, not modulation.
- **The FM-1 transmits MIDI** [reported: benny-sparra's V15 fixtures]: key
  presses and sequencer playback go out as Note On/Off over USB-MIDI; our
  "no spontaneous traffic" applies to an idle unit only.
- **V15 sequencer** [reported: photographed stock UI, benny-sparra]: 16 steps,
  pages `1/3` Pattern · Clear · Chain · Step, `2/3` Voice · Rate · Tempo ·
  Gate, `3/3` Swing · Sync · Transpose; V13's internal record held 10
  notes + 10 velocities per 32-byte slot (AL-255), so the record format
  changed in V15.
- **No read-back over MIDI [verified 2026-09-06]**: the device answers nothing
  but the vendor identity query — no reply to DX7 dump requests
  (`F0 43 20 09 F7`, `F0 43 20 00 F7`), none to the universal identity request
  (`F0 7E 7F 06 01 F7`), no spontaneous traffic (no clock, no active sensing).
  Patch retrieval therefore needs the UI-triggered dump, if any [inferred].
  fm1-editor.com's author states the same: "the FM1 accepts voices and banks
  but cannot send its stored banks back"; after a bank dump the unit shows a
  bank-selection screen and K1–K4 pick destination A–D [reported].
- **DX7 SysEx**: 32-voice bulk dump `F0 43 0n 09 20 00 … (4096 bytes) … F7`
  with checksum, single voice `F0 43 0n 00 1B …`, 7-byte parameter changes into
  the edit buffer. This is how fm1-editor.com and DX7 `.syx` banks work.
- **Vendor SysEx** magic `F0 35 59 … F7` arms the vendor channel; the update
  handshake header is `00 32 45`; a "syscmd" family framed
  `[00 59][cmd][len24][payload][~sum]` carries device-control commands 17–48
  (docs/03).
- Arpeggiator (7 modes, patterns, octaves, random via the SFR RNG) and a
  16-step sequencer with 16 sequences; UI strings `1/2 Arpeggio`,
  `1/2 Sequencer`, `Disable ARP to enter`, `Enable SEQ`.
- Effects strings: `Filter` (`Low Pass`, `Band Pass`, `High Pass`), `Reverb`
  (`Room`, `Hall`, `Plate`), `Delay`, `Distortion`, `Chorus`, `Phaser`, two FX
  slots **[verified strings]**.

## 7. Display and UI [reported: AL-255 `08-display.md`]

240×240 RGB565 TFT on SPI1, JieLi `ui_core` element tree (64-byte elements),
RGB565 layer compositor, two 240×24 strip buffers, UTF-8 font engine, in-house
`sprintf`. FM-1 pages are 488-byte structs dispatched through a page-handler
table; the main synth page shows six operator buttons; parameter rows draw from
a 6×21 per-operator name table plus 19 globals. Knob events arrive as class-7
events with the encoder id in bits 23:16.
