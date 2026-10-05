# MIDI

This chapter lists the MIDI messages Lunar Modulator receives and sends.
Today the browser simulator receives MIDI from a keyboard connected to your
computer, and the sequencer in the desktop tools writes down the MIDI its
tracks would send; the simulator sends none. On the FM-1, MIDI over USB and the 3.5 mm input is
planned.

## In the simulator

{{status sim}}

The simulator receives MIDI on every channel and sends nothing.

### To connect a MIDI keyboard

1. Connect the keyboard to your computer.
2. In the simulator, click **Connect MIDI input** under the panel and allow
   the browser to use MIDI devices when it asks.
3. The button now reads **MIDI:** followed by the names of the inputs it
   listens to, or **MIDI: no inputs** if it found none.

The simulator listens to every input the browser offers, and picks up a
keyboard you connect later without another click. Notes from a keyboard and
from the panel's keys play together.

### What the simulator receives

| Message | Received | What it does |
| --- | --- | --- |
| Note on, note off | Yes, any channel | Plays the current sound, with velocity 1 to 127, and goes to the sequencer's focused track for recording and Capture. A note on with velocity 0 is a note off |
| Pitch bend | Yes | Bends the current sound's notes, up to 2 semitones up or down |
| Control change 7 | Yes | Sets the volume, as [[MASTER]] does |
| Control change 123 | Yes | All notes off |
| Other control changes | No | Ignored, including modulation (CC 1) and sustain (CC 64) |
| Program change | No | Ignored |
| Aftertouch | No | Ignored, channel and polyphonic |
| System exclusive | No | Ignored |
| Clock, Start, Stop | No | Ignored: the simulator's sequencer runs on its own clock |

!!! note "Notes the keys cannot reach"
    A MIDI keyboard can play any note from 0 to 127, beyond the 27 keys'
    reach. Sophie answers only notes 36 to 51
    ([chapter 5](05-sound-engines.md#sophie)); on the panel her pads are the
    white keys.

## From the sequencer

{{status desktop planned}}

A sequencer track routed to MIDI sends its notes on its own channel, 1 to
16; unless you route it otherwise, track 1 uses channel 1, track 2 channel
2, and so on ([chapter 7](07-sequencer.md#tracks-and-routing)).

| What the track does | Message sent |
| --- | --- |
| A note starts | Note on, with the note's velocity |
| A note ends | Note off |
| A parameter lock changes a value | Control change 102 to 109, one per lock lane: lane 1 is CC 102, lane 8 CC 109, with the value 0 to 127 |

While it plays, the sequencer also sends MIDI clock for the whole set: Start
when it starts, 24 clock pulses per quarter note, and Stop when it stops. A
restart sends Stop and then Start.

In the desktop tools these messages go to the event log instead of a MIDI
port ([chapter 7](07-sequencer.md#scripts-on-the-desktop)). In the simulator
a track routed to MIDI is silent: it sends nothing. On the FM-1 they
are planned on USB-MIDI. The controller numbers are Movy's, which the FM-1
build is planned to keep as the default for MIDI tracks.

### Following an external clock

The sequencer can follow MIDI clock from another instrument or a computer:

| Message | What the sequencer does |
| --- | --- |
| Clock (F8) | Follows the tempo of the pulses, smoothing out small changes. If the pulses arrive while the sequencer plays, it joins at the next bar of the incoming clock, counted from its first pulse |
| Start (FA) | Restarts the sequencer from the beginning, if it is playing. With the set's `link` setting on, it also starts a stopped sequencer |
| Stop (FC) | Stops following: the sequencer carries on at the last tempo. With `link` on, it stops the sequencer |
| Continue (FB) | Resumes following |
| No pulses for half a second | Stops following, as Stop does |

While it follows a clock, the sequencer sends no clock of its own. When it
stops following, it plays on at the tempo it last measured and sends Start
to its own followers at the next bar.

This is how the sequencer behaves in the desktop tools today. The `link`
setting is off unless a script turns it on with `link 1`, or a set was saved
with it on. For the FM-1 the plan adds Song Position and a Continue that
resumes where the music stopped, as part of the MIDI implementation below.

## Implementation chart

{{status sim desktop planned}}

The chart sums up Lunar Modulator's MIDI as it is built today. *Sent*
describes the sequencer in the desktop tools, whose messages go to the event
log; *received* describes the browser simulator. The FM-1's MIDI is planned
and follows in the next section.

| Function | Sent | Received | Remarks |
| --- | --- | --- | --- |
| Basic channel | 1 to 16 | All | One channel per sequencer track; the simulator listens on every channel |
| Mode | — | Omni, poly | |
| Note number | 0 to 127 | 0 to 127 | Engines may answer fewer notes |
| Velocity, note on | 1 to 127 | 1 to 127 | A note on with velocity 0 counts as a note off |
| Velocity, note off | No | No | |
| Aftertouch, key and channel | No | No | |
| Pitch bend | No | Yes | Received: ±2 semitones |
| Control change | 102 to 109 | 7, 123 | Sent: parameter locks on MIDI tracks. Received: volume, all notes off |
| Program change | No | No | |
| System exclusive | No | No | Planned for saving and loading sequencer sets (chapter 10) |
| System common: song position, song select, tune request | No | No | Song position is planned for following a clock on the FM-1 |
| System real time: clock | Yes | Sequencer only | Sent at 24 pulses per quarter note while playing |
| System real time: Start, Continue, Stop | Start, Stop | Sequencer only | See *Following an external clock* |
| All notes off | No | Yes | Control change 123 |
| Active sensing, reset, local on/off | No | No | |

## On the FM-1

{{status planned}}

Lunar Modulator's MIDI on the FM-1 is planned and not yet designed in every
detail. What is settled so far:

- **Ports.** USB-MIDI, in and out, through the USB-C socket. The 3.5 mm
  [[MIDI IN]] jack receives only: the FM-1 has no MIDI output jack. Whether
  Bluetooth MIDI, which M-VAVE's firmware offers, will be supported is
  still open.
- **The adapter for MIDI IN.** The 3.5 mm input is wired for one of the two
  kinds of TRS-to-DIN adapter, type A or type B. Which one has not been
  measured yet.
- **The sequencer** sends notes, parameter locks and clock as described
  above, on USB-MIDI.
- **Sets over MIDI.** Sequencer sets are planned to be saved to a computer
  and loaded from one as system exclusive messages, carrying the set as text
  ([chapter 10](10-settings-and-storage.md#sequencer-sets)).
- **Still open:** the channel the sound engine listens on, a pitch bend
  range, and how the instrument answers Start, Continue and Stop.

### If you know M-VAVE's MIDI map

M-VAVE's firmware has a MIDI map of its own. Lunar Modulator's engines and
effects are different, so that map does not carry over:

| In M-VAVE's firmware | In Lunar Modulator today |
| --- | --- |
| Program change chooses one of 128 presets | Not received |
| An effects channel, channel 2 by default, with control changes 0 to 23 for its filter, reverb, delay, distortion, chorus and phaser | Not received; Lunar Modulator's effects are those of [chapter 6](06-effects.md) |
| Modulation, sustain and other control changes | Not received |
| DX7-style system exclusive for voices and banks | Not received; Six-Op FM plays its own patches |
| Channel aftertouch | Not received |
