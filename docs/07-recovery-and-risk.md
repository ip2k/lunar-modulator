# 07 — Recovery paths, risk register, rules of engagement

The single most important fact about this project: **until a full flash dump
and a byte-identical restore have been demonstrated, every non-stock write to
the FM-1 risks a permanent brick.** This document is the plan to remove that
risk, ranked by how likely each path is to work and how invasive it is.

## 1. Why recovery is hard on this device

- One application bank (`NEW_FLASH_FS` single-backup configuration, no
  double-bank keys in `isd_config.ini`) — AL-255.
- No JTAG/UART header, no test pads, no recovery button — aroum, photos. The
  one candidate header (three pads left of `U2`) turned out to be the battery
  connector's leads (owner's photos, 2026-09-29).
- `RESET=PB01_08_0` is a long-press reset, `UPDATE_JUMP=0` selects the reset
  path rather than a mask-ROM jump — AL-255.
- The only vendor update path runs inside the stock application over
  USB-MIDI; a device whose application does not boot cannot be updated that way.
- The stock app exposes no console, CDC, factory mode or recovery chord —
  AL-255's audit of V13/V14.
- Partial safety net [reported: Echomatter, 2026-09-04]: a *running*
  non-stock build that keeps the stock update service reachable can be
  overwritten with a stock package (their `FM-1_016` build with a broken USB
  descriptor was still recoverable through a Windows descriptor filter).
  A build that does not boot, or whose USB or update service is dead, is not.
- Wider evidence for that net [reported: Baud Girl, 2026-09-23 to 09-29]:
  dozens of non-stock builds (`FM-1_020` … `FM-1_092`) installed through the
  stock path, public installs and rollbacks to V15, and an install
  interrupted after step 1 resumed from the loader, which stays in `ota-FM-1`
  mode across power cycles (docs/03 §5). This covers an interrupted *transfer*. It still does
  not cover a *bad image*.

## 2. Candidate recovery paths, ranked

### 2.1 Mask-ROM USB boot via `USB_KEY` through the USB-C port — try first

The dongle for this is specified, implemented and simulated in docs/10 and
`dongle/`; the bench procedure is docs/10 §6.

**Buy first, build second [added 2026-09-06; JieLi's updater on order since 2026-10-01, docs/14].** JieLi sells exactly this
dongle: the "JL USB Updater" / "JL Forced Download Tool" (强制升级工具),
versions 2.0–4.0, US$8–18 on AliExpress, Taobao and GoldSupplier (e.g.
AliExpress item 1005007090348648 "Original JL USB Updater 4.0", GoldSupplier
p173085127 at US$8). JieLi's own documentation for the sibling WL83/AC792
family names it as the way into the ROM for chips with built-in flash:
"对于内置FLASH的芯片型号，可以使用杰理强制升级工具" (for chip models with
built-in FLASH, use JieLi's forced upgrade tool; obtainable through
distributors or JieLi's Taobao shop), after which Windows shows
"WL83 UBOOT1.00 USB Device" [reported]. The AC791N/WL82 is the same
generation and the mechanism is the mask ROM's, so it should apply, but the
listings only enumerate the Bluetooth families [inferred]. From the vendor
manual (manuals.plus/ae/1005009768042266): female side into a **USB 2.0 port
on the PC**, male side into the target; **no hubs, docks or USB 3.0 ports**;
the target's MCU must power up while the dongle is attached (our finding that
the FM-1 only starts when its switch is thrown fits: connect first, then
switch on); red LED = power, blue LED = download state; V4 has a DIP switch
and an "update" button; that manual says "all off for chips with a crystal".
JieLi's own manual for updater 4.0 (SDK `doc/stuff/usb updater.pdf`)
describes the modes [verified 2026-10-05]: all off, the button cuts target
power for at least 250 ms and then keys; bit 1, periodic power cut plus key;
**bit 3, continuous key with no power cut**; bit 5, D+/D− default to UART;
bit 7, USB functions and a virtual serial port. The FM-1 runs on its battery,
so a power cut from the dongle may not reset it: use bit 3 and the FM-1's
slide switch as the power-up [inferred].
The FM-1 needs a **USB-A-female-to-USB-C-male adapter** between the dongle's
plug and the synth. The vendor software was Windows-only until SDK V1.2.12
added a Linux `isd_download` flow (`cpu/wl82/tools/download_linux.c`)
[verified 2026-10-05]. Either is a *writer*: use it on the dev kit only,
never against the FM-1. For read-only dumps use
`jl-uboot-tool` on a Linux PC once the chip shows up as `UBOOT1.00`
(docs/10 §5). The RP2040 design in docs/10 stays as the open, instrumented
alternative (it logs which polarity worked and every timing step) and is not
being turned into a PCB unless the vendor tool fails on this chip.

JieLi's mask ROM contains a USB bootloader ("UBOOT1.00"). Besides entering it
when the flash fails to boot, the ROM watches for a special signal on the USB
data lines at power-up **[reported: kagaimiq `isp/usb/usb-key.md`,
`jl-uboot-tool/docs/how-to-enter-uboot.md`]**:

- The key is the 16-bit value **`0x16EF`** (`0001 0110 1110 1111`), sent
  MSB-first, one line as clock (data latched on the rising edge), the other as
  data, at roughly **50 kHz** (not critical; reception is bit-banged in ROM),
  repeated until the chip acknowledges by **pulling both D+ and D− low for
  1–2 ms**.
- **The clock is D+.**
  - `usb-key.md` and the ASCII diagram in `how-to-enter-uboot.md` put the
    clock on D+; only that page's prose says D−.
  - czietz's Pico dongle clocks on D+ and has reached UBOOT mode on two FM-1s
    [reported: issue #2, docs/10 §1.1]; FM-1-transporter reports polarity A
    (D+ clock) only, and polarity B never worked [reported].
  - Try D+ first; the dongle keeps both.
- After the ACK the chip pulls D+ up and measures **SOF pulses** to calibrate
  its PLL, so the host bus must be quiet: use a dedicated USB 2.0 hub (an MTT
  hub such as Terminus FE2.1 isolates per port) or a separate host controller,
  and no other full/low-speed devices on it. Noise makes the ROM miscalculate
  the clock, time out on the watchdog and boot from flash instead.
- Then the chip enumerates as a **USB mass-storage device**. On FM-1s the
  WL82 shows as `4C4A:8057` `WL80UBOOT1.00`, SCSI inquiry
  `WL82`/`UBOOT1.00`/`1.00` [reported: FM-1-transporter, fm1-nes] (other
  families follow a `4C4A:xx42` pattern). It speaks JieLi's SCSI
  vendor protocol v2. `jl-uboot-tool` loads `wl82loader.bin` to
  `0x1C02000` (with the "MengLi" memory cipher quirk) and can then read, write
  and erase flash and run code (`jlrunner.py`). The vendor's `isd_download`
  does the same (`-dev wl82 -boot 0x1c02000`).
- Hardware needed: a small MCU dongle (RP2040, ESP32, Arduino) that bit-bangs
  the key on the FM-1's D+/D−, senses the ACK with a **strong external pull-up
  (< 4.7 kΩ)** because the chip's 15 kΩ pull-downs defeat MCU-internal pull-ups,
  then hands the bus to the PC (USB mux, or a relay, or a manual re-plug within
  the SOF window). The vendor sells exactly this as the "USB Updater" dongle
  (AC6925B-based) — buying one from Taobao/AliExpress is a legitimate shortcut.
- FM-1 specifics to check: any series resistors or ESD parts between the USB-C
  connector and the SoC. Power sequencing is settled: with the slide switch off
  the unit does not enumerate on USB power at all [verified 2026-09-06], so the
  ROM starts when the switch is thrown and the key must already be on the lines
  at that moment (the dongle keys continuously).

**Why this is the priority:** it needs no soldering, it is the vendor's own
production flashing path, and the tooling already exists. Its only unknown is
whether the AC791N's ROM honours the key on the FM-1's wiring. If it works,
dump the whole 1 MB, verify the dump matches the stock package where it
should, restore it, and dump again.

### 2.2 Failed-boot fallback

The ROM enters USB download mode by itself if the flash does not boot
**[reported: kagaimiq]**. A *hung* app is a different case: the ROM has
already handed over, so it needs a watchdog reset (the ROM accepts
`USB_KEY` after one) or a dongle at power-on [reported: FM-1-transporter].
This is a safety net only *after* we can write flash:
a custom firmware that deliberately invalidates its own header on a key combo,
or a watchdog-backed failure counter that erases the app directory head, would
guarantee a way back. It does not help a stock device.

### 2.3 Software entry into ROM USB mode from a running custom app

The SDK's `isd_config.ini` has `UPDATE_JUMP` (reset vs. jump to mask-ROM
update) and the online config tool protocol has a "MaskROM-update entry"
command (0x26; trap 7 forbids it). **Every custom firmware must include a
robust, early, key-combo-triggered path into this mode plus a boot-failure
counter** (AL-255's P0 "fail-open boot path"). Three ways for a running app
to enter `UBOOT1.00` are now known (`notes/2026-10-05-community-repos.md`
§3.6):
- **The stock "soft key"** `F0 22 24 35 7D F7`: stock V15 left the bus
  21 ms later and came back as `UBOOT1.00` [reported: FM-1-transporter; it
  fails with another full-speed device on the hub]. FM-1_092 is unchecked.
  It is one byte from the upgrade command `F0 22 24 35 7F F7`, and it is
  **forbidden before the gate** (rule 1, CLAUDE.md trap 9): the gate must
  prove the path that works when no app runs. Before any later use, find
  the `7D` handler in FM-1_092's `app.bin` at the desk.
- **`go_mask_usb_updata()`** in the SDK (`apps/common/usb/device/msd_upgrade.c`,
  identical at V1.1.9): from RAM, IRQs off, `nvram_set_boot_state(2)`, then a
  core reset through `PWR_CON` bit 4 [verified: SDK source; reported
  working: fm1-nes's CDC `UBOOT` command].
- **The `usb_update_mode` mailbox** at `0x01C7FD80`, then a P33 reset
  [verified: Felucca source; reported working]. SLOOP adds a `.noinit` boot
  guard: two failed early boots lead to a USB rescue mode and then to UBOOT
  [verified: SLOOP source].

Read the fail-open keys before USB starts: Felucca's key combination works
only once its main loop runs [verified: Felucca source].

### 2.4 `UART_KEY` / ISP / debug TAP over soldered wires

If `USB_KEY` fails: the LQFP48 leads are solderable. The SDK ini comments name
UART update pins `PB00`, `PB05`, `PA05` and debug-TAP options `PA9/PA10`,
`PB1/PB2`, `PB6/PB7` (or the USB pins). kagaimiq documents `UART_KEY` and the
ISP key. Requires the pinout from the AC7911B datasheet in the SDK and steady
hands; still far better than nothing. On the FM-1, PA9/PA10 are LED lines,
PB1 the battery, PB6 MASTER and PB7 a matrix row [reported: Felucca,
fm1-nes; docs/01 §3.1], so those TAP options share pins with the board
[inferred].

### 2.5 External flash programmer

Only if the flash is a discrete chip. The photos show one candidate: a
bottom-side SOIC-8 (`U12`?) near the connectors next to a 0.1 Ω resistor,
which reads more like a charger IC than a flash [inferred, 2026-09-08]. If
its marking turns out to be a `25Qxx`-class SPI NOR, a clip and a cheap
programmer become the simplest recovery path of all; read it on the bench
(docs/09 §5).

## 3. Risk register

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Custom package bricks the only device | high if attempted before recovery | total loss of the unit | **do not flash non-stock before 2.1 is proven**; first experiments go on the AC79 dev kit, on order since 2026-10-01 (docs/14), or a second FM-1. The kit is the **JL-AC79-DevKit V1.0**: base board, core board JL-AC79-WIFI V1.0 with an **AC7916** (same dual pi32v2 at up to 320 MHz, 578 KB SRAM), LCD board and cameras. eBay resellers listed it for about US$126–144 delivered (2026-09-30). The AC7916 may carry in-package SDRAM the FM-1 lacks; keep benchmark state in internal SRAM. It is also where to rehearse `USB_KEY` and the JieLi USB updater before the FM-1 |
| `USB_KEY` does not work on AC791N through the connector | low (reported working on FM-1s through the USB-C port with czietz's dongle and with FM-1-transporter, docs/10 §1.1) | forces soldering (2.4) | D+ clock first, then the other polarity; quiet bus; dev-board rehearsal |
| Wrong loader / wrong chip family in tooling | medium | corrupt flash | jl-uboot-tool marks WL82 "unknown", but `adb3f18`'s `wl82loader.bin` works on FM-1s with 256-byte I/O [reported: fm1-nes guard patch]. Read-only operations first, compare the dump with the stock package before any write, and finish dump, compare and write in one session: if the host drops the device, the chip boots flash [reported: FM-1-transporter] |
| Interrupted write (power loss, USB drop) | medium | unbootable app | battery charged, no hubs during writes, dump before every write. Through the stock path, a loader left waiting after step 1 can be resumed [reported: Baud Girl] |
| Package changes the flash head (`uboot.boot`, `isd_config.ini`) | low if rule 2 is kept | the OTA loader rewrites the second-stage bootloader [reported: Baud Girl FINDINGS 5.4]; a bad one bricks the unit | keep the head byte-identical to V15 and compare its SHA-256 (file bytes `[0x414, 0x4414)`) before anything is sent |
| Verifier gate never explained | low (was medium) | none for development | largely explained: a same-version refusal, content not authenticated (docs/03 §5); bump the version |
| Toolchain download disappears | low–medium | cannot build | archive the toolchain privately (do not publish) |
| Legal complaint about redistributing vendor binaries | low | takedown | never commit `.fwsc`/`app.bin`; link to sources |
| Bluetooth radio regulatory issues with custom firmware | low | none for personal use | keep vendor BT stack or disable BT |

## 4. Rules of engagement (adopted from AL-255's safety review)

1. No non-stock flash on any device without a proven dump-and-restore path for
   that device.
2. Keep `uboot.boot`, `ota.bin`, `cfg`, `isd_config.ini` and the partition
   layout **byte-identical to stock** in any experimental package until the
   loader checks are understood.
3. Never send syscmd commands 33–36 or 48; never send the `5A AA A5` online-tool
   erase/write commands blind.
4. Every custom firmware carries a fail-open boot path (key combo → USB update
   mode) and a watchdog-backed failure counter from day one.
5. Test power loss and disconnects at every update stage on the recoverable
   device before anyone else is told to flash anything.
6. Read the stock identity (`FM-1_0xx`) from the device/package; never infer
   version from filenames.
7. Log everything on the bench: USB descriptors, SysEx traces, dumps with
   SHA-256, photos of pin probes. Put them under `notes/`.

**2026-09-29 note.** Baud Girl's FM-1+VA (docs/04) shows the stock path
installing and removing non-stock applications at scale. That is new
evidence, but it is evidence about *transfers*. Rule 1 exists for the image
that does not come back, and no FM-1 has yet been dumped and restored through
mask ROM. Since 2026-10-01 a backup and a write through mask ROM are reported
on another owner's FM-1 (issue #2, docs/10 §1.1), but not a byte-identical
restore, and nothing here on this project's unit. Since then fm1-nes
(Keitark) wrote 51 sectors through mask ROM on its maintainer's V14 unit,
FM-1-transporter erased and rewrote one sector on a V15 unit, and Felucca
and SLOOP install and roll back through the stock path [reported; docs/04].
None of it was on this project's unit. The rules stand unchanged unless the
owner decides otherwise.

The owner has since installed FM-1+VA on the unit by their own decision (it
identifies as `FM-1_092` on 2026-09-29). That leaves the rules as they are:
they govern what *this project* builds and sends. The documented way back to
stock is M-VAVE's V15 `.fwsc` through Baud Girl's installer [reported]; it
has not been exercised here. A dump taken now captures FM-1+VA, not stock.
