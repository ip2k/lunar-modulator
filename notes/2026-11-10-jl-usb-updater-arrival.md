# 2026-11-10 — JieLi's USB updater dongle has arrived

The "JL USB Updater" (强制升级工具, the forced-upgrade dongle of docs/07 §2.1,
ordered with the dev kit, docs/14) is in hand. Nothing has been connected to
it yet. These are observations from the owner's three photos of the case and
the board, the case opened [verified: owner photos, 2026-11-10]. Where a photo
does not settle a point, the point is marked as such.

## What it is

| | |
| --- | --- |
| Board | silkscreen `USB Updater V4.1`, `2023.02.24` |
| Case | `杰理科技 JIELI TECHNOLOGY` on one face; `JL USB Updater`, an `Update` button, an LED window and a `GND RX TX` label on the other |
| Ends | `PC端` (PC end) at the USB-A **female** socket, `样机端` (target end) at the USB-A **male** plug; male-plug pads `GND DP DM +5V` |
| Controls | 8-way DIP switch (`ON`, 1–8), a tact switch under the `Update` button, a 3-position slide switch `5.0V / 4.2V / 3.3V` |
| Headers and pads | 3-pin right-angle header `G RX TX`; pads `TCK TDO TMS NC TDI` |
| Other parts | a 220 µF 16 V electrolytic by the socket, two LEDs, small SOT-23-class parts marked `A15HB`; the controller IC is not visible in the photos |

The ends match the vendor manual quoted in docs/07 §2.1: the female socket
takes a cable from a USB 2.0 port on the PC, and the male plug goes into the
target. The FM-1 and the dev kit both need a USB-A-female-to-USB-C-male
adapter on the male plug.

## Not settled by the photos

- **DIP switch positions.** They cannot be read reliably from the photo.
  JieLi's manual covers updater **4.0** (SDK `doc/stuff/usb updater.pdf`):
  - all off: the button cuts target power for at least 250 ms, then keys;
  - bit 1: periodic power cut plus key;
  - bit 3: continuous key with no power cut;
  - bit 5: DP/DM default to UART;
  - bit 7: USB functions and a virtual serial port.

  This board is **V4.1**. That the bits mean the same here is [inferred].
- **Supply selector position**, and whether it sets the target's VBUS or a
  battery-style rail. 5.0 V is the expected setting for a USB-powered target
  [inferred]. Read it before anything is plugged in.
- **The pads.** They are four JTAG-named pads plus NC, while our earlier note
  said "2-wire JTAG" (`notes/2026-10-05-community-repos.md`). What the
  dongle drives on them is unknown.
- **The key drive.** The photos do not show whether the dongle keys D+/D− open-drain or
  push-pull, or through series resistors. docs/10 E1/E2 are written for our
  own dongle; how the vendor's compares is unknown.

## Where it fits, and what is not authorised

- **Dev kit.** The kit enters UBOOT with its UPDATE and RESET buttons and
  with acknowledged UART entry, so it does not need the dongle (docs/14).
  The dongle is a third route there. Using it on the kit falls under the
  standing dev-kit authorisation. Plugging it in is a physical step for the
  owner.
- **FM-1.** The approved recovery route stays docs/17 (Pico 2 W and our
  patched FM-1-transporter, D2), and the M5 and M6 sessions are approved on
  that route only. Using this dongle on the FM-1 is a **new route** and needs
  the owner's yes first (docs/07 §4).
- **Software.** JieLi's PC download tools (`isd_download`, the Windows
  downloader) are writers: dev kit only, never the FM-1. Never pass
  `-key`/`-key1`/`-mkey`, and never send `0xFC12` or raw `0xA1` (trap 11).

## Proposed first checks (none run)

1. **No target attached.** Owner plugs the dongle into bench01 alone. Record
   `lsusb` and the kernel log, first with the DIP switch all off and then with bit 7 on. This shows
   what the dongle itself enumerates as. Nothing is sent.
2. **Dev kit, bit 3.** Dongle between bench01 and the kit. Check that the kit appears as
   `4c4a:8057` `UBOOT1.00` through the dongle with no button pressed, then
   return the kit to its app with the existing fixed-loader reset adapter.
   This proves the dongle keys a WL82 ROM.
3. **FM-1:** only after the owner approves it as a route. With bit 3 and the
   FM-1's slide switch as the power-up, it could become a second recovery path
   that needs no Pico. Read-only identity, then dumps compared with the
   2026-10-26 pair, as docs/17 did.

## First observation, 13:04 PST (nothing sent)

The owner reported the dongle plugged into bench01, with the FM-1 powered on
behind it. bench01 showed **no device at all**: `lsusb` listed only the four root hubs,
and the kernel log has no new-device line and no enumeration error since
12:56:25–12:56:33. At that time the Pico (`1-2`), the `3-2` device, the
external hub `3-1` and its FTDI adapter (`3-1.4`) all disconnected
[verified: bench01 `lsusb`, `dmesg`]. A running V15 passed straight through
would show as `4c4a:c755` `FM-1`, and a keyed ROM as `4c4a:8057`. Neither
appeared, and no failed attempt was logged either. Still open: whether the
dongle is on a powered bench01 port, its DIP and supply-selector settings,
and its LEDs.

**Owner's report, then a closer look at the board photo:**
- The dongle is in a port directly on bench01, not on the hub. Its red LED is solid and its green
  LED flashes. The vendor manual pairs red with power and blue with download, and says nothing of a
  flashing green.
- The DIP switch is at its default: all eight actuators sit on the side away from `ON`, so
  **all off** [verified: enlarged photo]. In JieLi's 4.0 manual, all off means the dongle keys only
  when the Update button is pressed, after a power cut of at least 250 ms.
- The supply selector's slider looks centred, which would be **4.2 V** [inferred: photo]. That is to
  be confirmed by eye.
- With all bits off, the dongle neither enumerates on bench01 nor passes the running FM-1 through
  [verified: no USB event, above]. This fits the dongle holding the target's D+/D− until it keys
  [inferred]; bit 7 would be needed for it to show up itself.
- Nothing was pressed or sent. Pressing Update with the FM-1 attached would key it into mask ROM,
  which makes this a new FM-1 route. That needs the owner's yes.

## Owner approval, 2026-11-10: one FM-1 keying test

The owner answered "Approve FM-1 keying test". The approved scope:
- The owner presses Update **once**, with the DIP switch all off and the FM-1 attached.
- bench01 only watches for the mask ROM (`4c4a:8057`) and reads the descriptors the kernel collects.
- No dump, no write, and no ROM or loader command.
- The owner then power-cycles the FM-1 back to V15, and its identity is read with the read-only
  query.

Anything more needs a new yes.

## Result of the keying test, 13:14 PST (one press)

- **bench01** logged a single line, `usb usb3-port1: connect-debounce failed`, at
  13:14:23 [verified: `dmesg -w`]. Port 1 of bus 3 is the dongle's port. The host
  saw the line change state but never got a stable connection, so nothing
  enumerated: no `8057` and no `c755`. No device was present 30 s later either.
- **The dongle's LEDs** went from solid red with flashing green to **solid red
  and solid green** [reported: owner].
- **The FM-1** stayed on its normal V15 screen and **did not reboot**
  [reported: owner]. The dongle's power cut did not reset it. That matches the
  earlier inference that a battery-powered FM-1 is not reset by cutting VBUS
  (docs/07 §2.1). The mask ROM only looks for the key at power-up, so no key was
  seen.
- Nothing else was sent or pressed. V15 is still running, so no recovery was
  needed. The identity read waits for a direct USB connection, because the dongle
  does not pass the FM-1 through.

What would make it work, by the manual and inference (not run, needs a new yes):
power-up keying, i.e. the FM-1's slide switch off and then on while the dongle is
keying. That is either this solid-green state, or DIP bit 3 (continuous key, no
power cut). The Pico route (docs/17) does the same power-up keying.

## Owner approval, 2026-11-10: one power-up keying try

The owner answered "Approve power-up try". The approved scope is one try:
- The dongle stays in its current solid-green state, with the DIP switch all off and unchanged.
- The owner switches the FM-1 off and then on with its slide switch.
- bench01 only watches. If the mask ROM appears, the kernel reads its descriptors and nothing else
  is sent: no dump, no write, no ROM or loader command.
- Return: the owner unplugs the dongle, power-cycles the FM-1, and connects it directly. Then the
  read-only identity query runs.

## Result of the power-up try, 13:2x PST

- By the time of the power cycle, the dongle had gone back from solid green to **flashing green**
  [reported: owner]. When the FM-1 was switched off and on, it **booted normally into V15**, on the
  same screen [reported: owner].
- bench01 logged **nothing at all**: no connect, no debounce failure, no device, checked at
  13:26:21 [verified: `dmesg -w`, `lsusb`].
- So with the DIP switch all off, the dongle keys only in a short window after its own button
  press and power cut. Solid green is that window, and it ends by itself. When idle (flashing
  green), it neither keys the target at power-up nor passes the target's USB through to the PC
  [inferred from the two runs].
- For a battery-powered FM-1, the all-off mode cannot work unless the FM-1 happens to be powered up
  inside that window.

Next candidate, per the 4.0 manual (needs a new yes): **DIP bit 3**, continuous key with no power
cut, followed by an FM-1 power-up. This is the same principle the Pico route uses (docs/17).

## What JieLi's 4.0 manual says (read 2026-11-10)

Source: SDK `doc/stuff/usb updater.pdf`, §3 and §(4) [verified: read]. Summarised and translated:

- **DIP positions are the switch numbers 1–8.** "Bit 3" is switch 3.
- **Low four switches** (only one on at a time):
  - none: sends `usbkey`; needs a button press;
  - 1: power-cycles periodically and keys each time;
  - 2: sends `ispkey`, for chips that need it;
  - 3: **keys continuously with no power cut**. The chip must be power-on reset ("quick plug-in or
    chip wake-up");
  - 4: reserved.
- **High four switches:**
  - 5: DP/DM default to UART;
  - 6: SH50 flash mode;
  - 7: the tool has USB functions (virtual serial, PC commands), after power-up;
  - 8: stay in upgrade mode.
- **How entry works:** the chip must restart from its boot code, the tool keys at that moment,
  and on a successful handshake the PC sees a disk device. A button press **stops the tool's power
  output for at least 250 ms**. That restarts only a target powered by the tool, which explains the
  first FM-1 try.
- **LEDs:**
  - at power-up, both flash once;
  - idle: red on, green flashing;
  - button pressed: red on, green on;
  - **target in upgrade mode: red on, green off**;
  - JTAG failure: both flash.
- **Flash pads:** on PC command, the tool can drive a SPI flash directly. RX goes to CS, DP to CLK,
  and DM to both DO and DI. These are brought out as the JTAG pads (TCK = DP, TDO = TDI = DM,
  TMS = RX). This is noted only: it is not a route for the FM-1, whose flash is in-package.

## Owner approval, 2026-11-10: one switch-3 try

The owner answered "Approve bit 3 try". The approved scope:
- Only switch 3 is turned on; the rest stay off.
- The dongle is re-plugged so it reads the switches at power-up.
- The FM-1 is switched off, then on, once.
- bench01 only watches; the same no-dump, no-write, no-command rule applies.
- Return: the owner sets switch 3 back off, unplugs the dongle, and power-cycles the FM-1 directly.
  Then the read-only identity query runs.

**Correction (owner, 13:39):** before the switch-3 try, the owner moved the supply selector to
**5.0 V**. The earlier tries ran at the selector's previous setting, and the "looks centred, 4.2 V"
reading above was not confirmed. The owner set switch 3 to ON. In a later photo it looked off, but that was a
shadow [reported: owner]. Ask about switch positions rather than reading them from photos. As of
13:39:21, bench01 had logged nothing since the watch started.

## Result of the switch-3 try (port 3-1)

- The FM-1 **booted V15 normally** [reported: owner].
- The dongle stayed **red on, green on**, the manual's "keying" state. It never reached "green off",
  which would mean the target is in upgrade mode [reported: owner].
- bench01 logged **nothing**: no connect, no device [verified: `dmesg -w`, 13:37–13:41].
- So the dongle keyed through the FM-1's power-up, but the FM-1's mask ROM did not take the key,
  while the Pico's key does work (docs/17). Open causes:
  - the manual forbids USB 3.0 ports, and 3-1 is on bench01's USB 3 controller;
  - the key's timing or electrical drive versus the FM-1's power-up.
- The owner offered a retry on a USB 2 port. That changes one variable under the same switch-3
  scope.

## Result of the switch-3 retry on a USB 2-only port (≈14:05)

- The dongle stayed **red on, green on**, and the FM-1 **booted V15 normally** [reported: owner].
- bench01 logged nothing; its last kernel line is still 13:14:23. No device was present at
  14:06:33 [verified].
- The port is ruled out. The summary and the comparison with the Pico route are in
  `docs/21-jl-usb-updater.md`.
- Return state: the FM-1 is on V15. Nothing beyond the approved tries was run.

## Dev-kit control (standing dev-kit authorisation, owner-run)

- **Try 5, switch 3, kit plugged into the dongle:** LEDs red on, green on. bench01 saw nothing
  (14:10–14:14:50).
- **Try 6, all switches off, dongle re-plugged, Update pressed once:** the green LED went from
  flashing to solid, then back to flashing a few seconds later [reported: owner]. bench01 logged
  `usb1-port2: connect-debounce failed` at 14:15:52 and nothing after [verified].
- Neither try reached the ROM. The cause is the dongle or its setup, not the FM-1. Whether the kit
  was powered through the adapter is still to be confirmed. Details are in docs/21 §3–4.
