# Panel tour

This chapter names every control on the FM-1 and says what Lunar Modulator
does with it. The drawing is to scale and matches the simulator's panel. Each
section says which parts work in the simulator today and which are planned
for the device.

{{figure panel}}

| No. | Control | What it does in Lunar Modulator |
| --- | --- | --- |
| 1 | [[MASTER]] | Output volume |
| 2 | [[PRESETS]] | Chooses the sound engine |
| 3 | [[ALGORITHM]] | Steps through the engine's main list: its model, shape, patch or pad. In FX mode it chooses the effect in the chosen slot |
| 4 | [[OCT-]] and [[OCT+]] | Move the keyboard down or up an octave; both together reset octave and transpose |
| 5 | Keys | 27 keys, F3 to G5 at the middle octave |
| 6 | [[SELECT]] | Turns the page. In FX mode it moves between the effect slots and their pages |
| 7 | Screen | The 240 × 240 colour display |
| 8 | [[KNOB1]] to [[KNOB4]] | Change the four parameters shown on the screen |
| 9 | Function buttons | Twelve buttons in two rows. [[FX]], [[SEL]], [[GLO]] and [[HOME]] work today; the others are planned |

## Knobs

{{status sim planned}}

The FM-1 has eight knobs. [[MASTER]] is a potentiometer: it turns between two
end stops, and its position is the volume. The other seven are encoders: they
turn without end, in steps you can feel.

| Knob | What it does |
| --- | --- |
| [[MASTER]] | The output volume, from silent to full. While you turn it the screen shows *Volume* and its position from 0 to 100 |
| [[SELECT]] | On the sound's page, turns the page. In FX mode, moves through the first slot's pages, then the second's. On the global page it does nothing |
| [[PRESETS]] | Chooses the sound engine, in this order: Macro, Shapes, Macro Heavy, Six-Op FM, Sophie, Test Sine, and round again |
| [[ALGORITHM]] | Steps through the engine's main list: Model for Macro and Macro Heavy, Shape for Shapes, Patch for Six-Op FM, Pad for Sophie. Test Sine has none. In FX mode it chooses the effect in the chosen slot. With [[OCT-]] or [[OCT+]] held, it transposes ([chapter 4](04-playing.md)) |
| [[KNOB1]] to [[KNOB4]] | Change the four parameters of the current page, in the order the screen lists them |

### How far one step goes

- **A list parameter** (Model, Shape, Patch, Pad and the like) moves one
  value per step and stops at each end of its list.
- **A continuous parameter** moves a hundredth of its range per step, so 100
  steps take it from one end to the other. Parameters whose range runs
  between whole numbers ten or more apart move in whole units instead:
  Sophie's Tune moves a semitone per step, and its Sweep two units.
- **[[PRESETS]]**, and [[ALGORITHM]] in FX mode, go round: after the last
  choice comes the first.
- **Speed makes no difference.** Every step is the same size however fast you
  turn; there is no acceleration.

[[MASTER]] is not linear: half way round gives a quarter of full level, about
12 dB down.

### Turning knobs in the simulator

Drag a knob up or down, or scroll over it. Dragging 6 pixels turns an encoder
one step; [[MASTER]] goes from silent to full over 180 pixels. Scrolling turns
an encoder one step at the start of each scroll, then one step for every
60 pixels the page would have scrolled, and [[MASTER]] 2 % per step. From the
computer keyboard, choose a knob with <kbd>Tab</kbd> and turn it with the
arrow keys ([chapter 2](02-getting-started.md)).

### On the FM-1

The FM-1's knobs are planned to work as they do in the simulator. Which of the
seven encoders the FM-1's processor reads directly, and which through its key
scanning, is still to be measured; it does not change what the knobs do.

## Buttons

{{status sim planned}}

The FM-1 has fourteen buttons, each with a light. [[OCT-]] and [[OCT+]] sit at
the left, under [[ALGORITHM]]. The other twelve, the function buttons, sit in
two rows of six under [[KNOB1]] to [[KNOB4]]: [[FX]], [[SEL]], [[ENV]],
[[LFO]], [[EDIT]], [[GLO]] on top, and [[HOME]], [[SAVE]], [[ARP]], [[SEQ]],
[[PLAY/STOP]], [[REC]] below.

| Button | In the simulator | Planned for the device |
| --- | --- | --- |
| [[OCT-]], [[OCT+]] | Move the keyboard an octave down or up, three octaves at most either way. Press both together to return to the middle octave and cancel any transpose. Hold one and turn [[ALGORITHM]] to transpose | The same ([chapter 4](04-playing.md#octave-and-transpose)) |
| [[FX]] | Shows the effect slots. Press it again to return to the sound's page | The same |
| [[SEL]] | In FX mode, picks up the chosen slot so that [[SELECT]] moves it along the chain; press [[SEL]] again to put it down. Anywhere else the screen says it works in FX mode | The same |
| [[GLO]] | Shows the global page; press it again to leave | The global page, with settings ([chapter 9](09-settings-and-storage.md)) |
| [[HOME]] | Returns to the sound's page from any mode | The same |
| [[SEQ]], [[PLAY/STOP]], [[REC]] | Show a message that they are not in the simulator yet | The sequencer: its view, the transport and recording ([chapter 7](07-sequencer.md)) |
| [[SAVE]] | The same message | Saving patterns, and later sounds ([chapter 9](09-settings-and-storage.md)) |
| [[ARP]] | The same message | An arpeggiator is planned; how it will work is not designed yet |
| [[ENV]], [[LFO]], [[EDIT]] | The same message | Not decided yet |

### Button lights

| Light | What it means |
| --- | --- |
| [[OCT-]] or [[OCT+]] | How far the keyboard is from the middle octave, on the button for that direction: off at the middle octave, a slow blink one octave away, a fast blink two away, steady three away |
| [[FX]] | On in FX mode |
| [[SEL]] | On while an effect slot is picked up |
| [[GLO]] | On while the global page is shown |
| Any other button | On while you hold it |

### Functions still to be given a button

The sequencer needs more functions than the panel has free buttons. Until
each is assigned a button, or a combination of buttons, this manual draws it
with a dashed outline: [[role:SHIFT]], [[role:CLEAR]], [[role:COPY]],
[[role:LOOP]], [[role:SESSION]], [[role:MUTE]] and [[role:UNDO]].
[Chapter 7](07-sequencer.md) describes what each one does.

## Keys

{{status sim planned}}

The FM-1 has 27 keys, from F3 to G5 at the middle octave: 16 white and 11
black, each with a light. The lowest key plays MIDI note 53. [[OCT-]] and
[[OCT+]] move the whole keyboard by octaves, and [[ALGORITHM]] with one of
them held moves it by semitones ([chapter 4](04-playing.md)).

- **How hard you play.** In the simulator, the place you press a key sets its
  velocity: softest at the top of the key, loudest at the bottom. Whether the
  FM-1's own keys can sense how hard they are played has not been measured
  yet.
- **Key lights.** A key's light is on while its note is held, whether you
  hold the key or a MIDI keyboard plays that note.

The FM-1 prints labels under its black keys for M-VAVE's own firmware: from
the lowest black key upwards, [[OP1]] to [[OP6]], [[PIT]], [[GLO]], [[MONO]]
and [[POLY]]; the highest black key has none. Lunar Modulator does not use
these labels.

!!! note "The keys and the sequencer"
    The sequencer is planned with two ways of using the keys: in *KEYS* mode
    they play notes as usual, and in *GRID* mode the sixteen white keys are
    the sixteen steps of a bar. [Chapter 7](07-sequencer.md) describes them.

## Screen

{{status sim planned}}

The screen has three parts: a bar along the top, the current mode in the
middle, and a bar along the bottom. The code that draws it is meant to carry
over to the FM-1, so the device's screen is planned to look as the
simulator's does.

### The top and bottom bars

- **Top bar.** The name of the sound engine, and at the right a level meter.
  The meter shows the output from silent (−48 dB) to full scale, before
  [[MASTER]]. It turns red when the output comes close to full scale, where
  the limiter is holding it down ([chapter 6](06-effects.md#the-limiter)).
- **Bottom bar, left.** The page you are on and how many there are, such as
  *1/2*, and the mode: *Sound*, *FX1* or *FX2*, or *Globe* on the global page.
- **Bottom bar, right.** How much memory the engine and effects would take on
  the FM-1, in KB. The figure turns red when it is more than about 379 KB,
  the room M-VAVE's firmware leaves free on the FM-1 and the simulator's
  estimate of what Lunar Modulator will have there
  ([chapter 12](12-specifications.md)).

### The sound's page

The simulator starts on this page, and [[HOME]] returns to it.

- **The main list.** Under the top bar, in gold, the current value of the
  engine's main list: the model, shape, patch or pad. Test Sine has no list,
  so the line is left out.
- **Four rows.** One row for each parameter on the page, in knob order:
  [[KNOB1]] at the top, [[KNOB4]] at the bottom. Each row shows the name and
  the value, with a bar beneath.
- **Bars.** A bar fills from the left for most parameters. For a parameter
  that runs from negative to positive, such as Sophie's Tune, it fills from a
  centre mark. For a list parameter, a short marker shows where the value
  sits in the list.
- **Oscilloscope.** A strip at the bottom shows the waveform of the output.
  It is scaled to fill the strip, so quiet sounds show up too.

### The effects page

[[FX]] shows the effect chain:

- **Two slot lines**, such as *> 1 Plate* and *2 --*. The arrow marks the
  chosen slot; it becomes an asterisk while you have the slot picked up with
  [[SEL]]. Two dashes mean an empty slot.
- **The chosen effect's parameters**, as rows and bars like the sound's page.
  An empty slot says *Empty slot: turn ALGORITHM* instead.
- **The bottom bar** shows the page and the slot, such as *1/2 FX2*.

### The global page

[[GLO]] shows the sample rate, the block size, the memory the engine and
effects take against the memory the FM-1 has free, the engine's number of
voices, the identifiers of the two effects, and the octave and transpose.
The bottom bar reads *Globe*, the name M-VAVE's firmware gives this page. The
knobs and [[SELECT]] do nothing here. [Chapter 9](09-settings-and-storage.md)
describes the page.

### Messages

Short messages appear over the middle of the screen for about a second:

| Message | When |
| --- | --- |
| *Volume 75* | You turn [[MASTER]] |
| Three engine names, the middle one highlighted | You turn [[PRESETS]]: the previous engine, the new one and the next |
| A parameter and its value, such as *Model, VA Pair* | You turn [[ALGORITHM]] |
| The effect's name, or *Empty slot* | You turn [[ALGORITHM]] in FX mode |
| *Octave +1* | You press [[OCT-]] or [[OCT+]] |
| *Transpose -2* | You turn [[ALGORITHM]] with [[OCT-]] or [[OCT+]] held |
| *Octave 0, Transpose 0* | You press [[OCT-]] and [[OCT+]] together |
| An engine's name and *refuses 48000 Hz* | That engine cannot run at the sample rate the browser chose ([chapter 2](02-getting-started.md#the-browser-simulator)) |
| *SEL works in FX mode* | You press [[SEL]] outside FX mode |
| A button's name and *not in the simulator yet* | You press a button that has no function yet |

!!! tip "A larger screen"
    Under the panel, **Screen ×2** shows a second copy of the screen at twice
    the size.

## Connections

{{status planned}}

{{figure edge}}

The connectors are on the edge above the screen. From left to right, seen
from above with the keys towards you:

| Connector | What it is | With Lunar Modulator |
| --- | --- | --- |
| [[POWER]] | The power slide switch. While it is off, a computer does not see the FM-1 over USB | Unchanged. In the simulator, clicking the drawn switch turns the simulator on and off |
| [[USB]] | USB-C. With M-VAVE's firmware it charges the battery and carries MIDI and two channels of audio each way between the FM-1 and a computer | Planned: MIDI in and out, and the way Lunar Modulator will be installed ([chapter 10](10-updating-and-recovery.md)). Whether it will also carry audio is not decided yet |
| [[MIDI IN]] | MIDI input on a 3.5 mm TRS jack. It receives only | Planned: MIDI input ([chapter 8](08-midi.md)). Which kind of TRS adapter it expects has not been measured yet |
| [[OUT]] | Stereo audio output on a 3.5 mm jack, for headphones, an amplifier or a mixer | The instrument's output |

The FM-1 also has a speaker of its own inside the case. For the battery and
charging, follow M-VAVE's manual: Lunar Modulator changes neither.
