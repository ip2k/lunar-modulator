# Updating and recovery

Lunar Modulator has not been installed or run on an FM-1. One FM-1 that
would not start has been brought back to M-VAVE's own firmware. This chapter
describes how that was done, the safeguards for any further device work, and
what remains unproven.

## The staged recovery policy

The owner authorized staged experiments on their own FM-1. In October 2026
an interrupted install left that unit unable to start. On 26 October 2026
the project brought it back to M-VAVE's firmware V15 through the processor's
recovery mode: two full backups that matched, a rewrite that was read back
and checked, and a unit that starts again and identifies as `FM-1_015`
([how it was done](#back-to-stock-firmware)). Earlier, on the same unit, the
project had also written and restored one unused part of the memory.

What this proves, on that one unit: an FM-1 that will not start can be
brought back to M-VAVE's firmware, as long as the small boot area at the
start of its memory is intact. What remains untested:

- a unit whose boot area is damaged;
- putting back a unit's own earlier firmware rather than M-VAVE's;
- installing Lunar on an FM-1. No Lunar application has run on one.

Before any further flash erase or program, compare private backups, review the
exact image and ranges, record the recovery plan and keep a way back to the
recovery mode. Reaching recovery mode alone does not prove that a unit can be
recovered. The detailed rules are in
[the recovery record](https://github.com/ip2k/lunar-modulator/blob/main/docs/07-recovery-and-risk.md#4-rules-of-engagement-owner-revised-2026-10-07)
and [the bench note](https://github.com/ip2k/lunar-modulator/blob/main/notes/2026-10-07-fm1-softkey-bench.md).

!!! warning "No installer exists"
    This project publishes no firmware file for the FM-1 and no installer
    for one. If you find a file that claims to be Lunar Modulator for the
    device, do not install it.

## Why the FM-1 needs a way back

The FM-1 keeps its firmware in one bank of flash memory. Its own update
method runs inside the firmware that is already installed, so it can replace
a working firmware but cannot rescue one that no longer starts. The board has
no recovery button and no test connector. Before anything new goes on the
device, there must be a way to bring it back that does not depend on the
firmware at all.

## Bringing back an FM-1 that will not start {#back-to-stock-firmware}

The FM-1's processor has a recovery mode built into its read-only memory:
given a special signal on the USB lines as it switches on, it lets a computer
read and write its flash memory, whatever the flash holds. This is the route
the project has used, once, on the owner's FM-1:

1. A Raspberry Pi Pico 2 W, a small microcontroller board, ran
   **FM-1-transporter**, an open tool by kurogedelic, with a small fix from
   this project so that it works on the Pico 2's chip.
2. Three wires joined the Pico to the FM-1's USB-C socket: the two data lines
   and ground, not power. The case stayed closed. With the FM-1 switched off,
   the Pico started sending the signal, and when the FM-1 was switched on it
   entered recovery mode.
3. The tool read out the whole flash memory twice. Both copies were
   identical, and both were kept.
4. It wrote M-VAVE's V15 firmware, only the parts that differed, checking
   each one, then read the whole memory back. It matched the V15 image.
5. With the Pico disconnected, the owner switched the FM-1 on, and it started
   M-VAVE's V15. Asked for its identity, it answered `FM-1_015`.

The tool never writes the boot area, the small first part of the flash that
starts the processor, so a write that fails part way can be tried again. A unit whose boot area is
itself damaged is outside this route.

Before the failed install, the owner's FM-1 ran Baud Girl's third-party
FM-1+VA (identity `FM-1_092`). The route and the project's checks accept
only M-VAVE's V15, so the unit now runs V15. Putting the unit's own earlier
firmware back has not been tried.

!!! warning "Only for an FM-1 that will not start"
    This route rewrites the FM-1's flash memory and replaces whatever
    firmware it had with M-VAVE's V15. Use it only on an FM-1 that no longer
    starts, or when you have decided to return yours to M-VAVE's firmware.
    The wiring connects the Pico straight to the FM-1's USB data lines,
    without the protective resistors the project's own dongle design uses.
    Never leave the Pico connected to a working FM-1: some of the tool's
    commands put a running FM-1 into recovery mode.

The step-by-step guide, with the parts list, the wiring, the build and every
check, is the developer guide
[Recovering an FM-1 to stock V15 with a Raspberry Pi Pico 2 W](https://github.com/ip2k/lunar-modulator/blob/main/docs/17-pico2w-recovery.md).
It is written for people at home on a command line. Follow it exactly, and
stop at the first step whose result does not match.

## Recovery dongles {#the-recovery-dongle}

{{status desktop}}

Other ways to send the recovery signal exist. The project has not used any
of them on an FM-1, and does not need them for the route above.

- **The chip maker's own USB updater**, a small ready-made dongle sold for
  JieLi chips.
- **The project's open design**, a Raspberry Pi RP2040 board with a switch
  that hands the USB lines from the dongle to the computer. Its firmware
  builds and has been tested against a simulation of the chip's recovery
  mode. The project has not assembled it.
- **czietz's Pico dongle.** Other FM-1 owners have reported that it works:
  czietz built a simple dongle from a Raspberry Pi Pico, which brings their
  FM-1 into recovery mode about one power-on in two, and masanaohayashi used
  it to back up their FM-1's firmware and to write firmware to it. Their
  reports, in issue #2 on the project's repository, also showed which of the
  two USB data lines carries the signal.

### How a dongle connects

A dongle sits between the computer and the FM-1:

1. Plug the dongle into the computer as its own instructions say. The
   ready-made one wants a USB 2.0 port on the computer itself, not a hub, a
   dock or a USB 3 port.
2. Connect the FM-1's USB-C socket to the dongle, with a USB-A to USB-C cable
   or adapter.
3. Switch the FM-1 on with [[POWER]] last. The chip listens for the signal
   only as it starts up.

!!! caution "Not the dongle maker's software"
    The ready-made dongle comes with Windows software that writes to the
    chip. Never run it against an FM-1. Reading the memory is done with
    open tools that the project checks step by step.

### The original recovery plan

The earlier plan was to prove a full restore before any write:

1. Bring the FM-1 into recovery mode.
2. Read out its whole flash memory, twice, and check that both copies are
   identical.
3. Keep the copies safe, with checksums.
4. Write the copy back, start the FM-1, read it out again and compare: the
   unit must be byte for byte as it was.
5. Do it twice. Then change one byte in a harmless place, and put it back.

The recovery of 26 October 2026 did steps 1 to 3, and step 4 once with
M-VAVE's V15 written in place of the unit's own copy. The owner accepted that
as meeting the plan. Writing back the unit's own copy, and step 5, have not
been done.

### What recovery cannot do

- It cannot repair a unit that is physically damaged.
- It cannot help if the processor's recovery mode itself does not answer.
- It never needs the case opened, and a dongle or a Pico changes nothing on
  the FM-1 just by being connected. Sending it commands can.

## Installing Lunar Modulator

{{status planned}}

### The work ahead

These are separate validation routes, not a requirement to wait for one before
starting another. Evidence from one route does not stand in for another:

1. **Measuring a unit, read-only.** Asking the FM-1 which firmware it runs
   and listening to it, without changing anything. Done in part.
2. **Recovery evidence.** Done once on the owner's unit: an FM-1 that would
   not start was brought back to M-VAVE's V15. A damaged boot area and
   putting back a unit's own earlier firmware remain untested.
3. **A development board.** The firmware's code runs on a JieLi development
   board from the same chip family, and its output is compared, bit for bit,
   with the desktop tools and the browser simulator. The board is in hand.
   It has its own update and reset buttons, so it needs no dongle.
4. **The FM-1, from memory.** Lunar Modulator runs on an FM-1 loaded into
   its working memory, without writing the flash. Switching off brings back
   the FM-1's own firmware.
5. **Installing.** A flash installation is a later, separately gated route:
   it requires a concrete image, a reviewed recovery plan, and the applicable
   verification evidence. No installable Lunar release is available now.

### A way back built in

Lunar Modulator is planned with a way into update mode that does not depend
on the rest of the firmware working: a key combination held while you
switch on, and a counter that notices when the firmware fails to start.
Both are tested before anyone is asked to install it.

### How it will be installed

The installer is not decided. Two routes exist: the FM-1's own update
method over USB-MIDI, through which third-party firmware already installs
on working units, and the processor's recovery mode. The first needs a
working FM-1, a computer and a USB-C cable; the second needs a board such as
the Pico 2 W described above. The recovery route has brought one FM-1 back
to M-VAVE's firmware; it has not yet been used to install anything else.

### Updating and going back

- A newer Lunar Modulator is planned to install over an older one.
- Going back to M-VAVE's firmware is planned through the recovery route in
  this chapter, which has done exactly that once.
- Whether M-VAVE's own updater will also be able to replace Lunar Modulator
  depends on whether Lunar Modulator answers that updater, which is not
  decided.

## The firmware your FM-1 has now

M-VAVE updates the FM-1 with its own updater over USB, and publishes the
firmware and the updater for macOS and Windows in the download centre of
its website, m-vave.com. Third-party firmware for the FM-1 also exists and
some installs through that same updater. That USB-MIDI updater route needs a
working FM-1 app; it cannot repair one that does not start. Other firmware
may use a processor mask-ROM route, whose recovery capability depends on its
specific loader and image.

!!! note "Keep your FM-1's firmware as it is"
    Nothing in Lunar Modulator requires you to change the firmware on your
    FM-1. If you want to try another firmware, follow its own instructions,
    and keep M-VAVE's updater and a copy of the official firmware file in
    case you want to go back.

### To find out which firmware your FM-1 runs

The FM-1 answers one question over USB-MIDI with its identity, a model name
and a number such as `FM-1_015`. The project's identity tool asks exactly
the question M-VAVE's updater asks when it starts, and sends nothing else:

1. Connect the FM-1 to your computer with USB and switch it on.
2. Close any other program that uses the FM-1's MIDI port.
3. In a checkout of the project, with Python 3:

```bash
python3 -m pip install mido python-rtmidi
python3 tools/fm1_identify.py --list     # the MIDI ports your computer sees
python3 tools/fm1_identify.py            # asks the first port named FM-1
```

The line `identity:` in its answer is the firmware's identity.

| Identity | M-VAVE's name for it |
| --- | --- |
| `FM-1_009` | V13 |
| `FM-1_014` | V14 |
| `FM-1_015` | V15 |

Third-party firmware reports numbers of its own.

!!! tip "Trust the identity, not the file name"
    Version numbers in file names, in M-VAVE's announcements and in the
    identity often disagree: the package called V13, for example, identifies
    as `FM-1_009`. When it matters which firmware you have, ask the unit.
