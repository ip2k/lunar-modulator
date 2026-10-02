# Welcome and safety

Thank you for trying Lunar Modulator. It is open firmware being written for
the M-VAVE FM-1, the pocket six-operator FM synthesizer with 27 keys, eight
knobs and a 240 × 240 colour screen. It is designed to give the FM-1 a choice
of synthesis engines, two effect slots and a sequencer with parameter locks,
and every line of its own code is open under the MIT licence.

Lunar Modulator runs today in a web browser and on computers. It does not run
on the FM-1 yet. This manual describes what it does, how to play it, and where
each part of it stands. Please read this chapter before anything else: it
explains what you can use now, and why nothing is offered for the FM-1 itself
yet.

## What you can use today

Lunar Modulator is built and tested on computers first, and each function in
this manual carries a status that says where it works today:

{{status-key}}

- **The browser simulator** is a virtual FM-1. The firmware's engines and
  effects run in your browser, behind a to-scale drawing of the front panel
  with the firmware's own 240 × 240 screen. Play it with the mouse, a touch
  screen, the computer keyboard or a MIDI keyboard. It is the front page of
  the project's website,
  [ip2k.github.io/lunar-modulator](https://ip2k.github.io/lunar-modulator/),
  and [chapter 2](02-getting-started.md) shows how to use it.
- **The desktop tools** play the same engines, effects and sequencer into
  audio files from the command line. They are how the firmware is tested, and
  the only place the sequencer runs so far.
- **The FM-1 itself** runs none of it yet. Everything marked *Planned for the
  device* is designed and documented, and waits for the rule described below.

## Features at a glance

| Function | Where it works today | Chapter |
| --- | --- | --- |
| Six sound engines: Macro, Macro Heavy, Six-Op FM, Shapes, Sophie and Test Sine | Simulator, desktop | [5](05-sound-engines.md) |
| Four effects in two slots, followed by a limiter | Simulator, desktop | [6](06-effects.md) |
| The front panel: the knobs, the keys, the screen, and the [[OCT-]], [[OCT+]], [[FX]], [[SEL]], [[GLO]] and [[HOME]] buttons | Simulator | [3](03-panel-tour.md) |
| Octave, transpose, velocity and pitch bend | Simulator; velocity and bend also on the desktop | [4](04-playing.md) |
| Notes from a MIDI keyboard | Simulator | [8](08-midi.md) |
| Sequencer: steps, parameter locks, conditions, clips, scenes, recording and Capture | Desktop | [7](07-sequencer.md) |
| Sequencer sets saved and loaded as text files | Desktop | [9](09-settings-and-storage.md) |
| Any of the above on the FM-1 | Planned | [10](10-updating-and-recovery.md) |

## The one rule

Nothing is installed on, or written to, an FM-1 until two things have been
shown on that very unit: a complete copy of its memory has been read out, and
that copy has been written back so that the unit is byte for byte as it was.

The reason is that an FM-1 has no safety net. Its firmware lives in a single
bank of memory, and the board has no recovery button and no test connector.
The FM-1's own update method runs inside the firmware that is already
installed: it can replace a working firmware, but it cannot rescue one that no
longer starts. Owners of other FM-1s have reported reading out and writing
their units' memory with a small USB dongle, but this project has not yet
done so itself. Until a way back has been shown to work on the unit in
question, a failed install could leave the instrument permanently unusable.

!!! warning "There is nothing to install on your FM-1 yet"
    There is no Lunar Modulator firmware for the FM-1 yet, and this project
    will not offer one until the one rule is met. Be wary of any file that
    claims to be Lunar Modulator for the device: it is not from this project.
    To try Lunar Modulator, use the browser simulator.

The one rule also limits what this project sends to an FM-1 while the work
goes on: a read-only query that asks the unit which version of its firmware
it runs, and passive listening, nothing else. [Chapter 10](10-updating-and-recovery.md)
describes the recovery work under way and what will change once it succeeds.

## Safety and care

Lunar Modulator does not change how the FM-1 is built or powered. M-VAVE's
instructions for the battery, charging and care of the instrument still apply;
follow M-VAVE's manual for them.

!!! caution "Protect your hearing"
    Synthesizer engines can produce loud, sudden or piercing sounds,
    particularly when you turn a parameter quickly, raise a feedback or
    resonance control, or play many notes at once. Start with the volume low,
    on headphones and on speakers alike, and raise it while you play. In the
    simulator, [[MASTER]] sets the output level and the firmware's limiter
    holds the output just below full scale, but your computer's own volume
    still applies on top of both.

!!! warning "Do not open the case"
    Nothing in this manual asks you to open your FM-1. The recovery dongle
    described in chapter 10 is designed to plug into the USB socket from
    outside.

!!! note "Your FM-1 is unchanged"
    Using the simulator or the desktop tools sends nothing to an FM-1, even
    one connected to the same computer. The simulator reads MIDI from a
    keyboard you connect; it sends no MIDI at all.

## About this manual

- **Controls** are written as the panel prints them: [[SELECT]], [[KNOB1]],
  [[PLAY/STOP]]. Sequencer functions that are still to be given a button are
  drawn with a dashed outline, such as [[role:SHIFT]].
- **Statuses.** The status line under a heading says where the function
  described below it works today, using the three labels above.
- **Notes** add detail and **tips** suggest a way of working. **Cautions**
  protect your hearing and your data; **warnings** protect your instrument.
- **Note names.** Middle C, MIDI note 60, is C4. The FM-1's lowest key, F3,
  is MIDI note 53.
- **Generated reference.** The parameter tables, value lists and sequencer
  tables are generated from the firmware's code each time the manual is built,
  so they always match the build named below.
- **Online and in print.** The newest edition is on the project's website,
  with a PDF of the whole manual beside it. Corrections are welcome as issues
  on the [project's repository](https://github.com/ip2k/lunar-modulator).

{{build-info}}
