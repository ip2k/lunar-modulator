# 07 — Recovery paths, risk register, rules of engagement

**Policy update, 2026-10-07:** the owner has removed the blanket prerequisite
(the old "one rule": a full dump and byte-identical restore before any write)
and authorized staged hardware experiments (§4). The following opening
describes the original rationale, not a current ban on boot-mode probes.

**Owner update, 2026-10-26:** recovery of an unbootable FM-1 whose boot area
`0x0`–`0x4000` is intact is proven on this unit, and docs/17 is the approved
recovery route (§4, decisions D1–D4).

The original single most important fact about this project: **a non-stock
write can leave the FM-1 unable to boot, and the stock updater cannot rescue a
nonbooting application.** That happened on this unit: a stage-7 install
was interrupted on 2026-10-15 and left it with no display and no USB
[verified: notes/2026-10-26-fm1-stock-v15-recovery.md §State]. On
2026-10-26 it was keyed into mask ROM with a Pico 2 W, dumped twice
(identical), and the stock V15 application region was written, read back
equal; it boots [reported: owner] and identifies as `FM-1_015` [verified: docs/17,
notes/2026-10-26-fm1-stock-v15-recovery.md]. That route needs an intact boot
area `0x0`–`0x4000`; recovery from a damaged boot area is unproven. The unit's
own FM-1+VA (`FM-1_092`) image was not restored. This document records the
risks and staged safeguards; it is not a general authorization for device
writes.

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

### 2.1 Mask-ROM USB boot via `USB_KEY` through the USB-C port — proven, the approved route

**Done on the owner's unit [verified 2026-10-26].** A Pico 2 W running
kurogedelic's FM-1-transporter, patched for the RP2350, keyed the unbootable
FM-1 into UBOOT, and the stock V15 application region was written back. The
procedure is docs/17. It is proven for a unit whose boot area `0x0`–`0x4000`
is intact; the transporter refuses to write that area, so a damaged boot area
is still unproven (owner, 2026-10-26, D1). docs/17 is the project's approved
recovery route for this unit (D2).

This project's own dongle is specified, implemented and simulated in docs/10
and `dongle/` (bench procedure docs/10 §6) but has not run on an FM-1. It is
no longer on the critical path; it stays useful for other owners and as the
open-drain design (D2). The material below predates the 2026-10-26 run and
is kept as background.

**Buy first, build second [added 2026-09-06].** JieLi sells exactly this
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
production flashing path, and the tooling already exists. Its only unknown
was whether the AC791N's ROM honours the key on the FM-1's wiring. That is
answered on this unit: the ROM took the key with D+ as the clock, and two
identical 1 MB dumps, a stock V15 write with read-back and a boot followed
[verified 2026-10-26, docs/17].

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
  fails with another full-speed device on the hub]. FM-1_092 was never checked, and no longer runs on the unit.
  It is one byte from the upgrade command `F0 22 24 35 7F F7`, and it
  stays **banned except in an authorised session** (§4 D4, CLAUDE.md trap
  9). The gate it was held back for (the path that works when no app runs)
  was met on 2026-10-26 (§4 D3). Before any later use on stock V15, find the
  `7D` handler in V15's `app.bin` at the desk.
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
| Custom package bricks the only device | medium; it happened once (interrupted install, 2026-10-15) | loss of the application region, recoverable through docs/17 while `0x0`–`0x4000` is intact (proven 2026-10-26); total loss only if the boot area is damaged, which is unproven to recover | Follow §4 before any flash erase/program; keep the boot area byte-identical to stock (rule 2); first Lunar code runs from RAM only (D3). Rehearse firmware on the dev kit, which is in hand: `JL_AC79_DevKitBoard V1.2` (notes/2026-10-22-devkit-uart-bringup.md, docs/14). The V1.0 / AC7916 description the order was based on is superseded, and the V1.2 core board's chip is not yet identified; if it has in-package SDRAM the FM-1 lacks, keep benchmark state in internal SRAM. The kit enters download mode with its own UPDATE (K1) and RESET (K2) buttons and has a UART header, so it needs no `USB_KEY` dongle |
| `USB_KEY` does not work on AC791N through the connector | retired on this unit: it worked on 2026-10-26 with FM-1-transporter on a Pico 2 W, D+ clock [verified, docs/17]; also reported with czietz's dongle (docs/10 §1.1) | forces soldering (2.4) | docs/17; D+ clock first; quiet bus |
| Wrong loader / wrong chip family in tooling | medium | corrupt flash | jl-uboot-tool marks WL82 "unknown", but `adb3f18`'s `wl82loader.bin` works on FM-1s with 256-byte I/O [reported: fm1-nes guard patch]. Read-only operations first, compare the dump with the stock package before any write, and finish dump, compare and write in one session: if the host drops the device, the chip boots flash [reported: FM-1-transporter] |
| Interrupted write (power loss, USB drop) | medium; happened 2026-10-15 | unbootable app | battery charged, no hubs during writes, dump before every write. Recovered on 2026-10-26 by keying again and rewriting the application region (docs/17 §4, §6) [verified]. Through the stock path, a loader left waiting after step 1 can be resumed [reported: Baud Girl] |
| Package changes the flash head (`uboot.boot`, `isd_config.ini`) | low if rule 2 is kept | the OTA loader rewrites the second-stage bootloader [reported: Baud Girl FINDINGS 5.4]; a bad one bricks the unit | keep the head byte-identical to V15 and compare its SHA-256 (file bytes `[0x414, 0x4414)`) before anything is sent |
| Verifier gate never explained | low (was medium) | none for development | largely explained: a same-version refusal, content not authenticated (docs/03 §5); bump the version |
| Toolchain download disappears | low–medium | cannot build | archive the toolchain privately (do not publish) |
| Legal complaint about redistributing vendor binaries | low | takedown | never commit `.fwsc`/`app.bin`; link to sources |
| Bluetooth radio regulatory issues with custom firmware | low | none for personal use | keep vendor BT stack or disable BT |

## 4. Rules of engagement (owner revised, 2026-10-07)

These rules replace the old "one rule" (a full dump and a byte-identical
restore before anything is written), which the owner superseded on
2026-10-07; CLAUDE.md's "Hardware experimentation policy" is the same policy.
The owner revised them again on 2026-10-26: decisions D1–D4, below the
numbered rules, apply on top of them.

1. The owner permits staged bench01 experiments without a prior full dump and
   byte-identical restore: vetted soft-key UBOOT entry, reviewed RAM-loader
   flash reads, then evaluation of a bounded restore or prototype install.
   Take and compare private backups before flash erase/program operations,
   record the exact image/ranges and recovery plan, and retain a route to USB
   update mode. UBOOT entry alone is not proven recovery: proof needs the
   dumps, a verified write and a boot, as D1 records. No blanket erase or
   eFuse programming is authorized. See
   [the 2026-10-07 bench record](../notes/2026-10-07-fm1-softkey-bench.md)
   and [the 2026-10-26 recovery](../notes/2026-10-26-fm1-stock-v15-recovery.md).
2. Keep `uboot.boot`, `ota.bin`, `cfg`, `isd_config.ini` and the partition
   layout **byte-identical to stock** in any experimental package until the
   loader checks are understood.
3. Never send syscmd commands 33–36 or 48; never send the `5A AA A5` online-tool
   erase/write commands blind (both banned except in an authorised session,
   D4).
4. Every custom firmware carries a fail-open boot path (key combo → USB update
   mode) and a watchdog-backed failure counter from day one.
5. Test power loss and disconnects at every update stage on the recoverable
   device before anyone else is told to flash anything.
6. Read the stock identity (`FM-1_0xx`) from the device/package; never infer
   version from filenames.
7. Log everything on the bench: USB descriptors, SysEx traces, dumps with
   SHA-256, photos of pin probes. Put them under `notes/`.

**Owner revision, 2026-10-26** (after the recovery in docs/17):

- **D1 — Recovery proven, bounded.** Recovery of an unbootable FM-1 whose
  boot area `0x0`–`0x4000` is intact is proven on this unit: mask-ROM
  `USB_KEY` entry, two identical full dumps, a verified write [verified: docs/17],
  a boot [reported: owner] and identity `FM-1_015` [verified]. UBOOT enumeration alone is still not proof (rule 1).
  A damaged boot area remains unproven: the transporter refuses to write
  `0x0`–`0x4000`.
- **D2 — Standing route.** docs/17 (Pico 2 W, patched FM-1-transporter,
  V15-only research shim) is the project's approved recovery route for this
  unit. While a running V15 is attached, the soft-key-sending commands
  `fm1t info`, `dump`, `write`, `uboot` and console `k` are off limits. Its
  push-pull wiring without series resistors is an approved exception to
  docs/10 E1/E2 for that route only; E1/E2 still bind the project's own
  `USB_KEY` dongle (docs/10, `dongle/`). The dongle stays useful for other
  owners and as the open-drain design, but it is no longer on the critical
  path.
- **D3 — I9 gate met, with V15 as the target.** The dump, restore and boot
  gate (I9) is met on 2026-10-26 with stock V15 as the restore target: two
  identical dumps, a known image written byte-identically over
  `[0, 0x93000)` and read back [verified: docs/17], and a boot [reported: owner]. The restore
  target is stock V15, not `FM-1_092`. Gates elsewhere that waited on "the
  dump and restore", "I9" or "Phase 2 exit" are met. The next milestone is
  the first Lunar code on the FM-1, RAM-only first, under these rules, with
  docs/17 as the fallback.
- **D4 — MIDI in allowed.** Ordinary MIDI (notes, CC, program change) may be
  sent into the unit on stock V15 for testing. SysEx stays limited to the
  read-only identity query `F0 00 32 45 00 00 00 40 7F F7`. The soft key
  `F0 22 24 35 7D F7` (trap 9), syscmd 33–36 and 48, and `5A AA A5` frames
  (trap 7) stay banned except in an authorised session.
- **Unchanged:** no blanket erase; no eFuse writes; never loader command
  `FC12` or the raw `0xA1` write; the stock SPL, `ota.bin` and `cfg` package
  guards (rule 2, CLAUDE.md trap 11); never ship a V1.2.x `uboot.boot` or
  loader.

Not done, and not covered by D3: restoring the unit's own FM-1+VA
(`FM-1_092`) image. The two private 092 backups are the only copy of that
state.

**Historical policy note (2026-09-29; superseded by §4 rule 1, the 2026-10-07 bench result and the 2026-10-26 recovery).** Baud Girl's FM-1+VA (docs/04) shows the stock path
installing and removing non-stock applications at scale. That is new
evidence, but it is evidence about *transfers*. Rule 1 exists for the image
that does not come back, and no FM-1 has yet been dumped and restored through
mask ROM. Since 2026-10-01 a backup and a write through mask ROM are reported
on another owner's FM-1 (issue #2, docs/10 §1.1), but not a byte-identical
restore. At that time there had been no such test on this project's unit.
Since then fm1-nes
(Keitark) wrote 51 sectors through mask ROM on its maintainer's V14 unit,
FM-1-transporter erased and rewrote one sector on a V15 unit, and Felucca
and SLOOP install and roll back through the stock path [reported; docs/04].
Those reports and the statements above are historical context, not current
rules or current bench status. See §4 rule 1 and the current bench record.
On 2026-10-26 this project's unit was dumped twice through mask ROM
(identical) and the stock V15 application region was written and read back
(docs/17) [verified]; the unit's own `FM-1_092` image was not restored.

The owner had installed FM-1+VA on the unit by their own decision; it
identified as `FM-1_092` from 2026-09-29 to the interrupted install of
2026-10-15. Since 2026-10-26 it runs stock V15 [reported: owner] and identifies as
`FM-1_015` [verified: docs/17 §7]. It went back to stock through mask ROM (docs/17), not
through Baud Girl's installer, which has not been exercised here. A dump
taken now captures stock V15; the two 092 backups are the only copy of
FM-1+VA as it ran on this unit.
