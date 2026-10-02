# 10 — The `USB_KEY` recovery dongle (RP2040)

Specification, reference implementation and test harness for the dongle that
puts the FM-1's JieLi AC791N into its mask-ROM USB download mode
(`UBOOT1.00`) through the USB-C port, so the flash can be dumped and restored
without opening the case. This is Phase 2 of the roadmap (docs/08): nothing
else may be written to the device until this works (docs/07 §4).

Status 2026-09-06: **specified, implemented and simulated; not yet run against
an FM-1.** JieLi sells a ready-made equivalent ("JL USB Updater", docs/07 §2.1);
buy that first. This design is the open, instrumented alternative. Confidence marks as elsewhere: [reported] = kagaimiq's write-ups,
or the reports in issue #2 and czietz's gist where §1.1 says so, [inferred] =
our reading, [verified] = checked in this repository (host-side simulation
counts as verification of the *logic*, not of the chip's response).

Update 2026-10-01:
- **A simpler Pico dongle works on other FM-1s.** czietz reported in issue #2
  on this repository (§1.1) that their own Pico dongle reaches UBOOT mode on
  their FM-1. Another owner, masanaohayashi, used it to put their FM-1 into
  boot mode, back up its firmware and write firmware [reported].
- **So the mask-ROM route this document plans is reported working on two
  other units.** Nothing has run on this project's unit, and the one rule
  still applies to it (docs/07 §4).
- **What the reports show:** D+ is the clock, moving the cable to the PC
  works as the hand-over, and the ROM may listen only briefly after power-up.
- **Sections updated to match:** §1 items 3 and 7, §3, §5, §6 and §8.

## 1. What the mask ROM does [reported: kagaimiq]

Sources: `jielie/isp/usb/usb-key.md` and
`jl-uboot-tool/docs/how-to-enter-uboot.md` (both by kagaimiq, cloned under
`reference/`). Their content, condensed:

1. At power-up the boot ROM watches the USB data lines for a **16-bit key
   `0x16EF`** (`0001 0110 1110 1111`), sent **MSB first**, one line as clock
   and the other as data; the ROM latches data on the **rising edge** of the
   clock. Reception is software with a timer capture, so the clock "should not
   be too fast"; the vendor dongle uses about **50 kHz**.
2. The key is repeated until the chip acknowledges by **pulling both D+ and
   D− low for about 1–2 ms**. From then on the ROM stops listening for the
   key and initialises USB.
3. **Pin roles: D+ is the clock.**
   - `usb-key.md`, with scope captures, says D+ = clock and D− = data.
   - `how-to-enter-uboot.md` says in its prose that D− is the clock. Its own
     ASCII diagram, though, toggles D+ as the clock and carries `0x16EF` on D−
     (`0001 0110 1110 1111`, two characters per bit). Until 2026-10-01 this
     document cited that page's *diagram* as the D− source, which was wrong.
   - czietz's dongle clocks on D+ and has reached UBOOT mode on two FM-1s
     (§1.1) [reported].
   - Not yet seen on this project's unit. The dongle keeps both roles
     (polarity A = D+ clock, B = D− clock) and can alternate.
4. Sensing the acknowledge needs a **strong external pull-up (< 4.7 kΩ)** on
   each line: the chip keeps its 15 kΩ USB pull-downs active while receiving
   the key, and if the PC is also attached the pull-down becomes 7.5 kΩ, which
   defeats MCU-internal pull-ups and produces false acknowledges.
5. After the acknowledge the chip **pulls D+ up (1.5 kΩ) and measures the
   interval between falling edges on D+** to calibrate its PLL from the host's
   1 ms SOF cadence. It needs about four consistent periods; if nothing arrives
   within roughly a second it drops the pull-up and tries again (forever on
   older families, three times on newer ones — unknown for WL82). Any other
   full/low-speed traffic on the same bus segment can confuse the measurement;
   an isolated port (xHCI ports are isolated by design) or a dedicated USB 2.0
   hub avoids that.
6. Alternatively the **dongle itself can supply the "SOF" edges**: after the
   acknowledge, wait for D+ to go high, drive a short negative pulse every
   1.000 ms until D+ goes low (calibration done), then connect the PC. The
   chip then works regardless of bus activity.
7. In `UBOOT1.00` the chip enumerates as a **USB mass-storage device** that
   speaks JieLi's SCSI vendor protocol (v2 for WL82). It can only read/write
   RAM and jump; flash access needs the `wl82loader.bin` blob loaded to
   `0x1C02000` (jl-uboot-tool, "MengLi" memory cipher quirk). WL82 is listed
   there as **"unknown"** (loader present, never exercised). A backup and a
   write on an FM-1 have since been reported (§1.1).

The vendor's own "USB Updater" dongle is exactly this: a small JieLi MCU that
bit-bangs the key and a USB switch that then passes the bus to the PC.

### 1.1 Reports from FM-1 owners: czietz's Pico dongle (issue #2, 2026-09)

All three reports are in issue #2 on this repository, "Working UBOOT dongle
(fyi)": https://github.com/ip2k/mvave-fm1-open-firmware/issues/2.

- **2026-09-16, czietz.** They built an RP2040 dongle for themselves that gets
  the FM-1 into UBOOT mode: "much more quick&dirty than yours, but works
  reliably". They offered to share it if we needed to debug ours.
- **2026-09-27, czietz.** They posted it as an unlisted gist, "Quick and very
  dirty JieLi UBOOT tool" (https://gist.github.com/czietz/9a94cf3c3e68f2ceb45fab682e1cbbd5), saying they had used it successfully on
  their FM-1. The gist says "use at your own risk", and its first comment is
  a wiring diagram.
- **2026-09-29, masanaohayashi.** It "perfectly worked" on their FM-1: they
  put it into boot mode, backed up the firmware and wrote firmware.

Nobody here has run it. The gist carries no licence, so it is summarized here
and not copied. Neither report names the tool or the commands used for the
backup and the write. The gist points to jl-uboot-tool, so that was probably
used [inferred].

What the gist does [reported: czietz; the code was read here, not run]:

- **Parts:** a stock Pico running MicroPython and a cut USB cable with a USB-C
  plug on the device end. Pico pin 40 (VBUS) goes to 5 V, pin 14 (GP10) to
  D+, pin 15 (GP11) to D− and pin 23 to GND. There are no pull-ups, no series
  resistors and no switch.
- **Key:** sent by the SPI1 peripheral at 50 kHz, with SCK on GP10 (D+) and
  TX on GP11 (D−). MicroPython's defaults apply: mode 0 (clock idles low,
  data valid on the rising edge), MSB first, 8-bit. Each transaction is two
  bytes, `16 EF`. A new SPI object is made and released for every packet,
  which leaves a gap between packets. One round is 3,000 packets: 0.96 s of
  bits alone, plus MicroPython's per-packet overhead.
- **SOF stand-in:** a 1 kHz, 50 % square wave on D+ (GP10 switched to PWM) for
  2 s, in place of the PC's 1 ms SOFs.
- **Loop:** key, then SOF, forever. It never looks for the acknowledge or for
  the chip's D+ pull-up.
- **Use:**
  - Switch the target on. There is "about a 50:50 chance" of reaching UBOOT
    mode; on a miss, power-cycle and repeat.
  - On success, unplug the target from the Pico and plug it straight into
    the PC with an ordinary cable. It "should appear" as a USB device, "for
    example `WL80UBOOT1.00`".
  - Then use jl-uboot-tool.
  - The gist does not say which chip showed that example name. WL80 is the
    AC790N in `chips.yaml`; the FM-1 is a WL82.

What it tells us about the FM-1:

1. **D+ is the clock on the FM-1** [reported]. The dongle clocks on D+ and
   reached UBOOT mode on two FM-1s. This matches `usb-key.md` and the diagram
   in `how-to-enter-uboot.md` (item 3). Polarity A is the first thing to try
   on this project's unit (§6).
2. **The mask-ROM route reaches a dump and a write on an FM-1**
   [reported: masanaohayashi].
   - It goes through the USB-C port, with the case closed: the path docs/08
     Phase 2 plans.
   - It suggests that jl-uboot-tool's `wl82loader.bin`, which the tool lists
     as "unknown", works [inferred].
   - The one rule is unchanged: on this project's unit, a full dump and a
     byte-identical restore come before any write (docs/07 §4).
3. **A square wave probably works as SOF** [inferred].
   - The loop supplies 1 ms falling edges as a 50 % square wave, and the chip
     reached `UBOOT1.00` [reported].
   - Whether those edges or the PC's SOFs after the cable swap did the
     calibration is not stated. The ROM times falling edges only
     (`usb-key.md`).
   - Our 4 µs pulses give the same edges and keep D+ released.
4. **The ROM may listen only briefly after power-up** [inferred].
   - A key round lasts about 1.2–1.35 s (3,000 packets plus MicroPython's
     overhead), followed by 2 s of SOF. If the ROM listened for 2 s or more,
     timing alone would never make it miss.
   - A hit rate near one in two fits a window anywhere from a few
     milliseconds to a few hundred. So it cannot show whether the window is
     shorter than our 20 ms alternate blocks.
   - Other causes are not excluded, and "50:50" is a rough figure. After an
     acknowledge the gist keeps clocking D+ for up to about a second, which
     can upset the SOF measurement (§1 item 5).
   - Our dongle keys from before power-up and stops at the acknowledge, so
     the window length matters only in alternate mode. Fixed polarity A
     avoids that (§6).
5. **The FM-1 tolerated push-pull drive** [inferred from the reported
   successes].
   - The gist drives both lines push-pull at 3.3 V with no series resistance,
     and it keeps keying through the chip's 1–2 ms acknowledge. For a moment
     the chip pulls a line low that the Pico is driving high.
   - E1 (open-drain only) stays anyway: this project has one FM-1 and no
     spare.
6. **Moving the cable to the PC works as a hand-over on the FM-1** [reported:
   the gist's procedure, which both owners followed].
   - The chip stays in `UBOOT1.00` while the cable goes from the Pico to the
     PC.
   - The FM-1's 2000 mAh battery (docs/01) presumably keeps it powered
     through the swap [inferred]. Leave the switch on and charge the battery
     first.
   - This makes the relay optional (§3, minimal build).
7. **The inquiry vendor field names the chip family.**
   - `jluboottool.py` takes the SCSI inquiry vendor field, lower-cased, as the
     chip name and looks it up in `chips.yaml` [verified in code].
   - The gist's example `WL80UBOOT1.00` reads as vendor `WL80` plus product
     `UBOOT1.00` [inferred].
   - Expect `WL82` on the FM-1 [inferred], and record what it shows (§6
     step 6).

| | czietz's gist | This design |
| --- | --- | --- |
| Parts | Pico, cut USB cable | Pico, 2 × 2.2 kΩ, 2 × 100 Ω, relay or mux (or none, §3) |
| Drive | push-pull: SPI1, then PWM | open-drain PIO (E1) |
| Key | 50 kHz, `16 EF` MSB first, D+ clock; SPI mode 0, so the clock idles low | same bit rate and order; our clock idles released (high); D+ clock by default, D− by the button, both alternating as a build option |
| Between packets | a new SPI object per packet | 160 µs with both lines released, sampled for the ACK |
| Acknowledge | not detected | both lines low ≥ 100 µs |
| SOF | 1 kHz square wave for 2 s, blind | 4 µs pulses every 1 ms, from D+ high until the chip releases D+ |
| Hand-over | move the cable to the PC | relay or mux to the PC; moving the cable also works (§3) |
| Result | UBOOT mode on two FM-1s, about one power-on in two; a backup and a write afterwards [reported] | not yet run on hardware; logic simulated |

**Cross-check:** on the RP2040, GP14 and GP15 can also be SPI1's SCK and TX
(RP2040 datasheet, GPIO function table). Those are our board's D+ and D−
pins, in the same order as czietz's GP10 and GP11. So the gist's approach can
run on our dongle board with only the pin numbers changed, the relay
energised (GP17 high) and the pull-ups off.

That gives a second, independent waveform to compare on a logic analyser (§6
step 1), and a second implementation for the dev-kit rehearsal (docs/08
Phase 2). It drives push-pull, so by E1 it is not for this project's FM-1,
even though it has worked on others.

## 2. Requirements

Functional

- R1 Send the key continuously from before the target powers up until the
  acknowledge, in either pin polarity (fixed or alternating in blocks).
- R2 Detect the acknowledge reliably (both lines low ≥ 100 µs while the dongle
  drives nothing) and never while the target is unpowered or absent.
- R3 After the acknowledge, either hand the bus to the PC immediately
  (`SOF_MODE_PC`) or generate 1 ms falling edges on D+ until the chip finishes
  calibration, then hand over (`SOF_MODE_DONGLE`, default).
- R4 Report every step and its timing on a serial console; show state on the
  LED; allow a restart with a button.
- R5 Keep the target's VBUS connected to the PC at all times so the FM-1 sees a
  normal USB power source.

Electrical and safety

- E1 Never drive a line high: **open-drain only** (drive low or release). The
  chip pulls both lines low during the acknowledge, and push-pull outputs
  would short against it.
- E2 3.3 V logic on both sides (USB signalling is 3.3 V); 100 Ω series
  resistors on the two GPIO lines as a fault limiter.
- E3 The pull-ups (2.2 kΩ to 3.3 V) must be switchable, because during the
  SOF phase the dongle has to *see* the chip release its own D+ pull-up, and a
  strong dongle pull-up would mask that (2.2 kΩ against 15 kΩ still reads high).
  Each pull-up has its own pin: GP16 for D+, GP19 for D−, with the pads'
  default pull-downs disabled.
  - Until 2026-10-01 both resistors went to GP16. Switched off (hi-Z), they
    still joined D+ and D− through 4.4 kΩ.
  - D− then followed the chip's D+ pull-up to about 2.4 V, which reads high
    [inferred: resistor divider, with the chip's 15 kΩ pull-down].
  - The SOF phase waits for D+ high and D− low, so it would have timed out
    every time.
  - `tests/test_dongle_model.py` now reproduces this with the shared node.
- E4 With the dongle unpowered the target must be connected straight to the
  PC (relay normally-closed contacts = PC side).
- E5 Nothing here writes to the device. Entering `UBOOT1.00` is a read-only
  event; all flash writes are separate, deliberate `jluboottool` commands
  covered by docs/07 §4.

## 3. Hardware

```
                 ┌──────────────────────────────────────────────────┐
   PC  ══USB══►  │ HOST port (USB-C/micro-B breakout)               │
   (data+5V)     │   VBUS ───────────────────────────────┬── VBUS   │  TARGET port
                 │   D+  ──┐                              │          │  (USB-A female
                 │   D−  ──┼── K1 DPDT relay (NC = PC) ───┼── D+/D− ═╪══ USB-A→C cable ══► FM-1
                 │         │       │ NO = dongle           │          │
                 │         │       │                       │          │
                 │  Pico   │   GP14 ─100Ω─┬── D+ (dongle side)        │
                 │  GP16 ──┴─2.2k──────────┤                          │
                 │  GP19 ────2.2k──┐       │                          │
                 │  GP15 ─100Ω─────┴───────┼── D− (dongle side)       │
                 │  GP17 ── 2N7002 gate → K1 coil (+flyback diode)    │
                 │  GP18 ── button to GND  GP25 ── on-board LED        │
                 │  Pico micro-USB ══► PC (power + serial console)     │
                 └──────────────────────────────────────────────────┘
```

Bill of materials (reference build, all through-hole/breakout friendly)

| Ref | Part | Why |
| --- | --- | --- |
| U1 | Raspberry Pi Pico (RP2040) | PIO gives cycle-exact open-drain bit-banging and a 1.000 ms pulse train; USB CDC console for free |
| J1 | USB-A female breakout (TARGET) | plug the FM-1 in with an ordinary USB-A→C cable; avoids USB-C CC/Rp handling entirely |
| J2 | USB-C or micro-B female breakout (HOST) | the PC's pass-through connection; supplies TARGET VBUS |
| K1 | DPDT signal relay, 3 V or 5 V coil (e.g. Omron G6K-2F-Y / Panasonic TQ2) | transparent switch for a full-speed bus; NC contacts wired to the PC so the default path is "straight through" |
| Q1, D1 | 2N7002 (or any logic-level N-MOSFET), 1N4148 across the coil | coil current exceeds a GPIO's 12 mA |
| R1, R2 | 2.2 kΩ from D+ (dongle side) to GP16, and from D− to GP19 | switchable strong pull-ups, one pin each (E3, §1 item 4) |
| R3, R4 | 100 Ω in series with GP14 and GP15 | fault current limit, ESD |
| SW1 | tactile button GP18–GND | restart; held at boot: fixed polarity B |

Alternatives: a TS3USB221 / FSUSB42 USB 2.0 mux instead of K1 (SEL from GP17,
dongle side = "NO"); or, for a first prototype, a **manual DPDT slide switch**
as in the vendor's V2/V3 dongle, flipped when the LED says so (only with
`SOF_MODE_DONGLE`, which makes the hand-over timing non-critical).

**Minimal build (no relay)**, using the hand-over from the gist (§1.1
item 6):

- **Parts:** the Pico, the two 2.2 kΩ pull-ups, the two 100 Ω resistors and a
  cut USB-A→C cable. Keep its USB-C end: the C plug of an A→C cable carries
  the 56 kΩ Rp that tells a USB-C sink it has a default USB source
  [reported: USB Type-C specification; non-compliant cables exist]. Leave out
  K1, Q1 and D1.
- **Wiring:** the cable's 5 V goes to the Pico's VBUS (pin 40), so the PC
  powers the FM-1 through the Pico, as in the gist. D+ and D− go to the
  dongle side of the resistors.
- **Firmware:** unchanged; GP17 then drives nothing.
  - Nothing isolates the FM-1 during SELFTEST, including after a button
    restart. Plug it in only after `SELFTEST ok`: a switched-off SoC may load
    the lines [inferred].
- **Hand-over:** when the console prints `DONE`, unplug the FM-1 from the
  dongle and plug it into the PC with an ordinary cable. Leave its power
  switch on.
- **What it gives up:**
  - R5: the FM-1 loses VBUS during the swap and runs on its battery, so
    charge it first.
  - E4: nothing connects the FM-1 to the PC while the Pico is off.
  - In `SOF_MODE_PC` there are no SOFs until the cable is moved.
- **Track record:** the swap worked on two FM-1s with czietz's dongle
  [reported].

Pin map (`dongle/firmware/config.h`)

| GPIO | Name | Direction | Function |
| --- | --- | --- | --- |
| GP14 | `PIN_DP` | open-drain / input | D+ of the target (via 100 Ω) |
| GP15 | `PIN_DM` | open-drain / input | D− of the target (via 100 Ω) |
| GP16 | `PIN_PULLUP_DP` | output-high or hi-Z | top of D+'s 2.2 kΩ pull-up |
| GP17 | `PIN_MUX_SEL` | output | 1 = relay energised = dongle owns the bus |
| GP18 | `PIN_BUTTON` | input, internal pull-up | short press: restart; hold at boot: fixed polarity B (D− clock) |
| GP19 | `PIN_PULLUP_DM` | output-high or hi-Z | top of D−'s 2.2 kΩ pull-up |
| GP25 | LED | output | state indication |

Power: the Pico runs from its own micro-USB (also the console). TARGET VBUS
comes from the HOST port's VBUS straight through (R5). Do not tie the two 5 V
rails together.

## 4. Firmware (`dongle/firmware/`)

Two PIO programs (`usb_key.pio`) and a small state machine in `main.c`.

`usb_key` — bit-bangs one 16-bit key packet per TX-FIFO word. The word holds
the key **inverted** in its top 16 bits so that `out pindirs, 1` writes the
pin *direction* (1 = drive low) straight from the data; the pin's output value
is latched at 0 and never changes, which is the open-drain trick (E1). Timing
at a 1 MHz PIO clock: clock low 8 µs (data changes 3 µs after the falling
edge), clock released 12 µs → 20 µs per bit, 50 kHz, 320 µs per packet. After
the 16 bits both lines are released and the state machine stalls on `pull
block` until the CPU sends the next word; that stall is the inter-packet gap
in which the CPU samples for the acknowledge.

`sof_pulse` — drives D+ low for 4 µs every 1000 µs (cycle-counted, crystal
accurate), used in `SOF_MODE_DONGLE`.

Control flow (`main.c`, mirrored line-for-line by `dongle/sim/dongle.py`):

```
SELFTEST   pull-ups on, lines released → both must read high, else FAULT
KEY        loop: put packet word → wait 326 µs → gap 160 µs sampling both lines
           every 10 µs; both low for ≥ 100 µs ⇒ ACK. Polarity: fixed, or
           alternate every 40 packets (≈ 20 ms per block).
ACK        log polarity and packet count; stop the key; wait ≤ 20 ms for both
           lines to be released again
SOF_MODE_PC:      pull-ups off → relay to PC → DONE
SOF_MODE_DONGLE:  pull-ups off → wait ≤ 500 ms for D+ high (chip pull-up)
                  → start sof_pulse → sample D+ every 100 µs (outside our own
                  4 µs pulses) → 30 consecutive low samples (3 ms) ⇒ chip
                  released D+ ⇒ stop pulses → relay to PC → DONE
                  (6 s overall timeout ⇒ FAILED)
DONE       LED solid; console prints the next command to run on the PC
FAILED/FAULT  LED pattern; button restarts (power-cycle the FM-1 first)
```

Parameters (single source of truth `config.h`; the simulator reads the same
file, and a test fails if the two drift):

| Parameter | Value | Note |
| --- | --- | --- |
| `USB_KEY_WORD` | `0x16EF` | MSB first |
| `KEY_BIT_CYCLES` | 20 (µs) | 50 kHz |
| `KEY_GAP_US` | 160 | packet period ≈ 486 µs |
| `ACK_MIN_LOW_US` | 100 | real ACK is 1000–2000 µs |
| `KEY_PACKETS_PER_POLARITY` | 40 | alternate mode |
| `SOF_PERIOD_CYCLES` / `SOF_PULSE_CYCLES` | 1000 / 4 | 1.000 ms, 4 µs low |
| `SOF_DP_HIGH_TIMEOUT_MS` | 500 | chip should pull D+ up within ms |
| `SOF_DONE_LOW_MS` | 3 | D+ low this long = calibration finished |
| `SOF_PHASE_TIMEOUT_MS` | 6000 | covers several ROM retry windows |

LED: 1 Hz blink = keying; 3 fast blinks = ACK; solid = DONE; 5 Hz = FAILED;
10 Hz = FAULT (self-test). Console (115200 8N1 over the Pico's USB CDC) prints
one line per transition with microsecond timestamps.

## 5. Host side after `UBOOT1.00`

- **Use a Linux PC** (or Windows). `jl-uboot-tool` talks SCSI through
  `/dev/sg*` or `\\.\HardDiskVolumeN`; its device finder has no macOS path.
  Any Linux box on the LAN (or a Raspberry Pi) with the dongle attached works.
- Expected: a new mass-storage device whose SCSI inquiry product string is
  `UBOOT1.00` and whose vendor field is the chip family, which `jluboottool.py`
  uses as the chip name. czietz's gist gives `WL80UBOOT1.00` as its example
  name (§1.1), so expect `WL82` [inferred]. The VID:PID is unknown for WL82;
  BR23–BR34 use VID `4C4A` with PIDs `x342`. `python3 jldevfind.py` lists it.
- Then, **read-only first**: `python3 jluboottool.py --chip wl82` loads
  `wl82loader.bin` (address `0x1C02000`, MengLi cipher); inside the shell,
  identify the flash (JEDEC ID; expect a 1 MB density code `0x14`) and
  `read 0 0x100000 dump1.bin`. Power-cycle, re-enter, `read` again to
  `dump2.bin`; the two must be identical and must match the stock package
  where it maps (docs/01 §2). Only then is a `write` of `dump1.bin` allowed,
  followed by a third dump. Exit criteria are in docs/08 Phase 2.
- `jlrunner.py` can load and run code in RAM without touching flash; that is
  the path for the first custom code (docs/08 Phase 3).

## 6. Bench procedure (first attempt)

1. Build the dongle; before connecting the FM-1, power the Pico and watch the
   console: `SELFTEST ok` means the pull-ups and lines are wired. With a
   scope or logic analyser on D+/D−, confirm the 50 kHz packets and the
   ~160 µs gaps (optional but cheap insurance).
2. Connect the HOST port to the Linux PC and the FM-1 (**switched off**) to
   the TARGET port with a USB-A→C cable. A switched-off FM-1 does not
   enumerate on USB power [verified 2026-09-06], so nothing should appear on
   the PC yet.
3. Start keying, then switch the FM-1 on.
   - The defaults are **fixed polarity A** (D+ clock), the polarity reported
     working on two FM-1s (§1.1), and `SOF_MODE_DONGLE`. A is the default
     since 2026-10-01; it was alternate before.
   - Expected within a second: `ACK polarity=A packets=<n>`, then `D+ high`,
     `SOF pulses`, `D+ released after <n> pulses`, `bus → PC`, and
     `UBOOT1.00` on the PC.
4. If no ACK:
   - Try the switch several times before concluding anything: czietz's tool
     reaches the mode about one power-on in two (§1.1).
   - Then try fixed polarity B (hold the button at boot).
   - Then try alternate mode, a build with `DEFAULT_POLARITY_MODE` set to
     `POLARITY_ALTERNATE`. If the ROM's listening window is shorter than one
     20 ms block, it misses whenever power-up lands in the wrong block
     [inferred].
   - Then try with the FM-1 already on before keying, and then with
     `SOF_MODE_PC`.
   - Record every attempt in `notes/`.
5. If the stock app boots instead (the FM-1's screen comes up, `4C4A:C755`
   appears on the PC after the relay switches), the ROM did not honour the
   key: see §7.
6. First success: record polarity, timing lines, the PC's `lsusb` output and
   the SCSI inquiry string in `notes/`, then follow §5.

## 7. Test harness (`dongle/sim/`, `tests/test_dongle_*.py`)

- `tests/test_usb_key_pio.py` assembles `usb_key.pio` with `adafruit_pioasm`
  and runs it in `rp2040-pio-emulator`: the emitted waveform is decoded by a
  model of the ROM's receiver (rising-edge sampling) and must yield `0x16EF`
  with 20-cycle bit periods and ≥ 4 cycles of data setup; the `sof_pulse`
  program must produce exactly 1000-cycle periods with 4-cycle low pulses.
- `dongle/sim/jieli_rom.py` is a behavioural model of the ROM per §1 (key
  receiver in either polarity, 1.5 ms acknowledge, D+ pull-up and SOF period
  measurement with retry windows, optional short listening window).
- `dongle/sim/dongle.py` is the control logic of `main.c` in Python, driven
  by the *emulated PIO waveforms*, and `dongle/sim/cosim.py` resolves the two
  open-drain parties on a shared bus microsecond by microsecond.
- `tests/test_dongle_model.py` runs the whole sequence end to end for both ROM
  polarities and both SOF modes, checks that the dongle reports the right
  polarity, that no acknowledge is detected with an absent or unpowered
  target, that a wrong fixed polarity never triggers, and that
  `config.h` and the model agree.

What the harness cannot tell us: whether the AC791N's ROM honours the key on
the FM-1's wiring, the real listening window at power-up, the true polarity,
and whether VBUS alone powers the SoC. Those are §6.

## 8. Risks and open questions

| Item | Status |
| --- | --- |
| Pin polarity (which line is clock) | D+ (polarity A) on the FM-1 [reported: czietz's dongle on two FM-1s, §1.1]; `usb-key.md` and the diagram in `how-to-enter-uboot.md` agree, and only that page's prose says D− (§1 item 3). Not yet seen on this project's unit; both roles stay implemented |
| Does the ROM listen continuously or only briefly at power-up? | perhaps briefly [inferred]: czietz's blind key/SOF loop hits about one power-on in two, which fits a window from milliseconds to a few hundred (§1.1 item 4). Keying from before power-up covers it; fixed polarity A avoids the alternate-mode miss |
| Does the chip stay in `UBOOT1.00` while the cable moves from dongle to PC? | yes on two FM-1s [reported, §1.1]; presumably the battery holds the SoC up through the swap [inferred] |
| Push-pull drive against the chip's acknowledge | survived on two FM-1s [inferred from the reported successes]; we stay open-drain (E1) |
| Does the WL82 UBOOT route reach the flash? | a backup and a write on an FM-1 are reported (masanaohayashi, §1.1), tool and commands not stated; read-only commands first here (§5) |
| Does the FM-1 SoC start on VBUS with the switch off? | **No** [verified 2026-09-06]: with the switch off the unit is absent from USB (no device node, no MIDI port, no identity reply). Power-up is the switch; no VBUS load switch needed |
| Series/ESD parts between the USB-C receptacle and the SoC | unknown; 2.2 kΩ pull-ups tolerate a few hundred ohms in series |
| WL82 `UBOOT1.00` VID:PID and inquiry string | unknown; jl-uboot-tool marks WL82 "unknown" — read-only commands first |
| MengLi cipher / loader block size for wl82 | from `usb-loaders.yaml` [reported] |
| Battery keeps the SoC powered while "off" | No: the USB device disappears within seconds of switching off [verified 2026-09-06]. The key must be present when the switch is thrown; the dongle keys continuously |

## 9. Sources

kagaimiq — `jielie/isp/usb/usb-key.md`, `jielie/isp/index.md`,
`jl-uboot-tool/docs/how-to-enter-uboot.md`, `what-is-uboot.md`,
`usb-protocol.md`, `usb-loader-v2.md`, `data/usb-loaders.yaml`,
`data/chips.yaml`, `jluboottool.py` (chip name from the inquiry vendor);
czietz and masanaohayashi — issue #2 on this repository, 2026-09-16 to
2026-09-29; czietz — "Quick and very dirty JieLi UBOOT tool", an unlisted gist
(`9a94cf3c3e68f2ceb45fab682e1cbbd5`, 2026-09-27) that its author linked in
issue #2, with its wiring diagram (both read 2026-10-01); RP2040 datasheet (PIO, GPIO function table, pad electrical
characteristics); USB 2.0 specification §7.1 (pull-up/pull-down values,
full-speed signalling); USB Type-C specification (Rp in legacy A→C cables).
