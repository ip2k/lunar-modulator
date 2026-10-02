# Updating and recovery

Lunar Modulator cannot be installed on an FM-1 today. This chapter explains
what has to happen first, how the project means to make installing and
removing it safe, and what to do about the firmware your FM-1 has now.

## The one rule, again

Nothing is installed on, or written to, an FM-1 until a complete copy of its
memory has been read out and written back, byte for byte, on that unit
(chapter 1). Every step below exists to meet that rule; none of them
skips it.

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
and write its memory, whatever the flash holds. The project's
recovery dongle sends that signal through the USB-C socket, so the case stays
closed. The dongle is a small Raspberry Pi RP2040 board; a ready-made
equivalent is sold by the chip's maker.

Today the dongle's design is complete, its firmware builds, and it has been
tested against a simulation of the chip's recovery mode. It has not been
tried on a real FM-1.

!!! outline "To be written"
    - What the dongle looks like and how it connects: dongle between the
      computer and the FM-1's USB-C socket, power switch as the moment the
      signal is sent.
    - The procedure, once proven: read the whole flash, keep two copies with
      checksums, write it back, read it again and compare.
    - What the dongle cannot do: open an FM-1 that is physically damaged.

## Installing Lunar Modulator

{{status planned}}

!!! outline "To be written"
    - The order, once recovery is proven on a unit: run Lunar Modulator from
      memory without writing flash; then install it, keeping a backup of
      the original firmware.
    - The installer: a web page or a desktop tool over USB, as the FM-1's own
      update method works, with the recovery dongle as the way back.
    - Checking which firmware the unit runs: the version query the FM-1
      answers (`FM-1_0xx`).
    - Updating Lunar Modulator, and going back to the previous version.

## The firmware your FM-1 has now

M-VAVE updates the FM-1 with its own updater over USB, and publishes the
firmware files for it. Third-party firmware for the FM-1 also exists and
installs the same way. All of these need a working FM-1: they cannot repair
one that does not start.

!!! note "Keep your FM-1's firmware as it is"
    Nothing in Lunar Modulator requires you to change the firmware on your
    FM-1. If you want to try another firmware, follow its own instructions,
    and keep M-VAVE's updater and a copy of the official firmware file in
    case you want to go back.

!!! outline "To be written"
    - How to read which firmware version an FM-1 runs (its identity string),
      and why a file name is not a reliable version.
    - Where M-VAVE publishes its firmware and updater.
