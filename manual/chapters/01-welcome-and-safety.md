# Welcome and safety

Lunar Modulator is open firmware for the M-VAVE FM-1, the pocket six-operator
FM synthesizer with 27 keys, eight knobs and a colour screen. It replaces the
FM-1's sound with a choice of synthesis engines, adds effects and a sequencer
with parameter locks, and keeps every line of its own code open under the MIT
licence.

This manual describes what Lunar Modulator does, how to play it and where each
part of it stands today. Please read this chapter before anything else: it
explains what you can use now and why nothing is offered for the FM-1 itself
yet.

## What you can use today

Lunar Modulator is built and tested on computers first. Each function in this
manual carries a status that says where it works today:

{{status-key}}

- **The browser simulator** is a virtual FM-1: the firmware's engines and
  effects, compiled for the web, behind a to-scale drawing of the front panel
  with the firmware's own 240 × 240 screen. Play it with the mouse, a touch
  screen, the computer keyboard or a MIDI keyboard. Chapter 2 shows how.
- **The desktop tools** render the same engines, effects and sequencer to
  audio files from the command line. They are how the firmware is tested.
- **The FM-1 itself** runs none of it yet. Everything marked *Planned for the
  device* is designed and documented, and waits for the step described next.

## The one rule

Nothing is installed on, or written to, an FM-1 until two things have been
shown on that very unit: a complete copy of its memory has been read out, and
that copy has been written back so that the unit is byte for byte as it was.

The reason is that an FM-1 has no safety net. It has one bank of memory, no
recovery button, no test connector inside, and no proven way to bring it back
if the software on it stops starting up. The update method the FM-1 uses needs
the existing software to be running; it cannot rescue a unit whose software
does not start. Until a way back has been shown to work, a failed install
could leave the instrument permanently unusable.

!!! warning "Do not install anything on your FM-1"
    There is no Lunar Modulator firmware for the FM-1 yet, and this project
    will not offer one until the one rule is met. Be wary of any file that
    claims to be Lunar Modulator for the device: it is not from this project.
    To try Lunar Modulator, use the browser simulator.

The one rule also limits what this project sends to an FM-1 during
development: only a read-only query that asks the unit which version of its
software it runs, and passive listening. Chapter 10 describes the recovery
work that is under way and what will change once it succeeds.

## Safety and care

Lunar Modulator does not change how the FM-1 is built or powered. The
instrument's own instructions for its battery, charging and care still apply;
follow M-VAVE's manual for them.

!!! caution "Protect your hearing"
    Synthesizer engines can produce loud, sudden or piercing sounds, in
    particular when you turn a parameter quickly or play many notes at once.
    Start with the volume low, on headphones and on speakers, and raise it
    while you play. In the simulator, [[MASTER]] sets the output level and the
    firmware's limiter holds the output below full scale, but your computer's
    volume still applies on top.

!!! caution "Do not open the case"
    Nothing in this manual asks you to open your FM-1. The recovery dongle in
    chapter 10 plugs into the USB socket from outside.

## About this manual

- **Conventions.** Controls are written as the panel prints them:
  [[SELECT]], [[KNOB1]], [[PLAY/STOP]]. A status line under a heading says
  where the function described below it works today. *Notes* add detail,
  *tips* suggest a way of working, *cautions* and *warnings* protect your
  hearing, your data and your instrument.
- **Generated reference.** The parameter tables, value lists and sequencer
  tables are generated from the firmware's code each time the manual is
  built, so they always match the build named on the front page.
- **Draft sections.** Sections still being written show a dashed *Draft*
  box with the outline of what they will cover.
- **Online and in print.** The newest edition is online, and a PDF of the
  whole manual is published with it.

{{build-info}}
