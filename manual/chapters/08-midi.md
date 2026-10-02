# MIDI

This chapter lists the MIDI messages Lunar Modulator receives and sends. The
simulator receives MIDI from a keyboard connected to your computer; the
desktop sequencer produces MIDI events for tracks routed to MIDI; the FM-1
build is planned to do both over USB and its 3.5 mm input.

## In the simulator

{{status sim}}

The simulator listens on every channel and sends nothing. Connect a keyboard
with **Connect MIDI input** under the panel (chapter 2).

| Message | Received | What it does |
| --- | --- | --- |
| Note on, note off | Yes, any channel | Plays the engine; velocity 1 to 127. A note on with velocity 0 is a note off |
| Pitch bend | Yes | Bends every sounding note, ±2 semitones |
| Control change 7 | Yes | Sets the volume, like [[MASTER]] |
| Control change 123 | Yes | All notes off |
| Other control changes | No | Ignored |
| Program change | No | Ignored |
| Aftertouch | No | Ignored |
| System exclusive | No | Ignored |
| Clock, start, stop | No | Ignored; the simulator has no sequencer yet |

## From the sequencer

{{status desktop planned}}

A sequencer track routed to MIDI produces note on and note off messages on
its channel, and each lock lane a value from 0 to 127. While the sequencer
plays it produces MIDI clock (24 pulses per quarter note), Start when it
starts and Stop when it stops. It can also follow MIDI clock from outside:
clock pulses, Start, Continue and Stop.

In the desktop tools these messages are written to the event log, not sent
to a MIDI port.

!!! outline "To be written"
    - Which control change numbers lock lanes use on a MIDI track
      (Movy sends lane *n* as CC 102 + *n*), and whether the FM-1 keeps that.
    - Following external clock: how quickly the tempo settles, what happens
      when the clock stops.

## Implementation chart for the FM-1

{{status planned}}

!!! outline "To be written"
    - The standard four-column chart (function, transmitted, recognised,
      remarks) for the FM-1 build, once the device's MIDI is designed: basic
      channel, mode, note numbers, velocity, aftertouch, pitch bend, control
      changes, program change, system exclusive, system common, system
      real time, and auxiliary messages.
    - Ports: USB-MIDI, the 3.5 mm TRS input (receive only), and whether
      Bluetooth MIDI is supported.
    - System exclusive for saving and loading patterns and sounds (chapter 9).
    - Differences from M-VAVE's firmware, whose MIDI map (an FX channel with
      control changes 0 to 23, program changes for voices) does not carry
      over.
