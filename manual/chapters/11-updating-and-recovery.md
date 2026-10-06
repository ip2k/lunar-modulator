# Updating and recovery

Lunar Modulator cannot be installed on an FM-1 today. This chapter explains
what has to happen first, how the project means to make installing and
removing it safe, and what to do about the firmware your FM-1 has now.

## The one rule, again

Nothing is installed on, or written to, an FM-1 until a complete copy of its
memory has been read out and written back, byte for byte, on that unit
([chapter 1](01-welcome-and-safety.md#the-one-rule)). Every step below
exists to meet that rule; none of them skips it.

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

## The recovery dongle

{{status desktop}}

The FM-1's processor has a recovery mode built into its read-only memory:
given a special signal on the USB lines at power-up, it lets a computer read
and write its memory, whatever the flash holds. A recovery dongle sends that
signal through the USB-C socket, so the case stays closed.

There are two kinds:

- **The chip maker's own USB updater**, a small ready-made dongle sold for
  JieLi chips. The project tries this one first.
- **The project's open design**, a Raspberry Pi RP2040 board with a switch
  that hands the USB lines from the dongle to the computer. It reports every
  step it takes, which helps if the ready-made one does not work on this
  chip.

The open design's firmware builds and has been tested against a simulation
of the chip's recovery mode, but nobody has built the board yet. Neither
dongle has been used on an FM-1 by this project yet.

Other FM-1 owners have reported that the route works. czietz built a
simpler dongle of their own from a Raspberry Pi Pico, which brings their
FM-1 into recovery mode about one power-on in two, and masanaohayashi used
it to back up their FM-1's firmware and to write firmware to it. Their
reports, in issue #2 on the project's repository, also showed which of the
two USB data lines carries the signal, and this project's dongle now tries
that one first. This project has not run their dongle, and the one rule
still asks for the whole procedure below on a unit before anything is
written to it.

### How it connects

The dongle sits between the computer and the FM-1:

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

### The procedure, once proven

The project's first goal with the dongle is to show, on one FM-1, that a
unit can always be brought back:

1. Bring the FM-1 into recovery mode with the dongle.
2. Read out its whole flash memory, twice, and check that both copies are
   identical.
3. Keep the copies safe, with checksums.
4. Write the copy back, start the FM-1, read it out again and compare: the
   unit must be byte for byte as it was.
5. Do it twice. Then change one byte in a harmless place, and put it back.

Only after this has worked does anything else get written to an FM-1. The
project will publish the exact procedure, with photographs, when it has.

### What the dongle cannot do

- It cannot repair a unit that is physically damaged.
- It cannot help if the processor's recovery mode itself does not answer.
- It never needs the case opened, and changes nothing on the FM-1 by being
  connected.

## Installing Lunar Modulator

{{status planned}}

### The order of work

Lunar Modulator reaches the FM-1 in stages, each with its own test:

1. **Measuring a unit, read-only.** Asking the FM-1 which firmware it runs
   and listening to it, without changing anything. Done in part.
2. **Recovery.** The dongle procedure above, on a unit, twice.
3. **A development board.** The firmware's code runs on a JieLi development
   board from the same chip family. Its output is compared, bit for bit,
   with the desktop tools and the browser simulator.
4. **The FM-1, from memory.** Lunar Modulator runs on an FM-1 loaded into
   its working memory, without writing the flash. Switching off brings back
   the FM-1's own firmware.
5. **Installing.** Only then is Lunar Modulator written to the flash, with
   the original firmware kept as a backup.

### A way back built in

Lunar Modulator is planned with a way into update mode that does not depend
on the rest of the firmware working: a key combination held while you
switch on, and a counter that notices when the firmware fails to start.
Both are tested before anyone is asked to install it.

### How it will be installed

The installer is not decided. Two routes exist: the FM-1's own update
method over USB-MIDI, through which third-party firmware already installs
on working units, and the processor's recovery mode with a dongle. Either
way the case stays closed: the first route needs a computer and a USB-C
cable, the second a recovery dongle as well.

### Updating and going back

- A newer Lunar Modulator is planned to install over an older one.
- Going back to M-VAVE's firmware is planned from the backup of your FM-1's
  memory, with the dongle.
- Whether M-VAVE's own updater will also be able to replace Lunar Modulator
  depends on whether Lunar Modulator answers that updater, which is not
  decided.

## The firmware your FM-1 has now

M-VAVE updates the FM-1 with its own updater over USB, and publishes the
firmware and the updater for macOS and Windows in the download centre of
its website, m-vave.com. Third-party firmware for the FM-1 also exists and
installs the same way. All of these need a working FM-1: they cannot repair
one that does not start.

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
