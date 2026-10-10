# Welcome and safety

Thank you for trying Lunar Modulator. It is open firmware being written for
the M-VAVE FM-1, the pocket six-operator FM synthesizer with 27 keys, eight
knobs and a 240 × 240 colour screen. It is designed to give the FM-1 a choice
of synthesis engines, up to four sounds at once with effects of their own,
a rack of modulation and a sequencer with parameter locks, and every line of
its own code is open under the MIT licence.

Lunar Modulator runs today in a web browser and on computers. It does not run
on the FM-1 yet. This manual describes what it does, how to play it, and where
each part of it stands, including the limits of the device work.

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
- **The desktop tools** play the same engines, effects, modulation and
  sequencer into audio files from the command line. They are how the
  firmware is tested, and the only place a few of the sequencer's functions
  (clips, scenes and songs) run so far.
- **The FM-1 itself** runs none of it yet. Everything marked *Planned for the
  device* is designed and documented, but still needs implementation and
  verification on the hardware.

## Features at a glance

| Function | Where it works today | Chapter |
| --- | --- | --- |
| Eight sound engines: Macro, Macro Heavy, Six-Op FM, FM6, Shapes, Sophie, Drums and Test Sine, up to four sounds at once | Simulator, desktop | [5](05-sound-engines.md) |
| Twenty-four effects: two inserts on each sound and two on the master bus, followed by a limiter | Simulator, desktop | [6](06-effects.md) |
| The front panel: the knobs, the keys, the screen and every button but [[SAVE]] | Simulator | [3](03-panel-tour.md) |
| Octave, transpose, velocity and pitch bend | Simulator; velocity and bend also on the desktop | [4](04-playing.md) |
| Notes from a MIDI keyboard | Simulator | [9](09-midi.md) |
| Sequencer: steps, parameter locks, conditions, recording, Capture, eight tracks | Simulator, desktop | [7](07-sequencer.md) |
| Sequencer clips, scenes and songs | Desktop | [7](07-sequencer.md) |
| Modulation: LFOs, envelopes and fourteen more modules, cabled to any parameter | Simulator, desktop | [8](08-modulation.md) |
| Sequencer sets saved and loaded as text files | Desktop | [10](10-settings-and-storage.md) |
| Any of the above on the FM-1 | Planned | [11](11-updating-and-recovery.md) |

## Device work and recovery {#the-one-rule}

The owner has authorized staged bench work. On the owner's FM-1_092, the
project has entered USB recovery mode, taken matching private full-flash
backups, and programmed, read back and restored one bounded unused sector;
the complete image matched the backups afterward. This proves that bounded
sector operation on that unit worked. It does not prove a full-image rewrite,
recovery from a nonbooting application or a Lunar installation.

The FM-1's own updater runs inside the installed firmware, so it cannot rescue
an application that no longer starts. Before any further erase or program
operation, the staged plan requires private backups to be compared, the exact
image and ranges to be reviewed, and a recovery plan and route to USB update
mode to be retained. UBOOT entry alone is not proof of recovery. The current
limits and safeguards are in [chapter 11](11-updating-and-recovery.md).

!!! warning "There is nothing to install on your FM-1 yet"
    There is no installable Lunar Modulator release for the FM-1 yet. Offline
    diagnostic firmware variants exist, but none has run on an FM-1. Be wary of any file
    that claims to be Lunar Modulator for the device: it is not from this
    project. To try Lunar Modulator, use the browser simulator.

Any additional device interaction must follow the staged plan in [chapter
11](11-updating-and-recovery.md). The project has not installed or run Lunar
on an FM-1.

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
    described in chapter 11 is designed to plug into the USB socket from
    outside.

!!! note "Your FM-1 is unchanged"
    Using the simulator or the desktop tools sends nothing to an FM-1, even
    one connected to the same computer. The simulator reads MIDI from a
    keyboard you connect; it sends no MIDI at all.

## About this manual

- **Controls** are written as the panel prints them: [[SELECT]], [[KNOB1]],
  [[PLAY/STOP]]. Sequencer functions that are still to be given a key are
  drawn with a dashed outline, such as [[role:LOOP]].
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
