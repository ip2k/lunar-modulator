# Panel tour

This chapter names every control on the FM-1 and says what Lunar Modulator
does with it. The drawing is to scale and matches the simulator's panel.

{{figure panel}}

| No. | Control | What it does in Lunar Modulator |
| --- | --- | --- |
| 1 | [[MASTER]] | Output volume |
| 2 | [[PRESETS]] | Chooses the sound engine |
| 3 | [[ALGORITHM]] | Steps through the engine's main list: its model, shape, patch or pad; in FX mode, the effect in the chosen slot |
| 4 | [[OCT-]] and [[OCT+]] | Octave down and up; both together reset octave and transpose |
| 5 | Keys | 27 keys, F3 to G5 at the middle octave |
| 6 | [[SELECT]] | Steps through the pages of the current mode; in FX mode, between the effect slots |
| 7 | Screen | The 240 × 240 colour display |
| 8 | [[KNOB1]] to [[KNOB4]] | The four parameters shown along the bottom of the screen |
| 9 | Function buttons | [[FX]], [[SEL]], [[GLO]] and [[HOME]] today; the others are planned (below) |

## Knobs

{{status sim planned}}

The FM-1 has eight knobs. [[MASTER]] is a potentiometer: it has an end stop
and its position is the volume. The other seven are encoders: they turn
without end, in steps you can feel.

- [[KNOB1]] to [[KNOB4]] change the four parameters the screen shows for the
  current page. A continuous parameter moves a hundredth of its range per
  step; a list moves one entry.
- [[SELECT]] changes the page. Engines with more than four parameters spread
  them over pages of four, and chapter 5's knob maps show which parameter is
  on which page.
- [[PRESETS]] chooses the sound engine and [[ALGORITHM]] the engine's main
  list.

!!! outline "To be written"
    - Encoder acceleration (not in the simulator yet: every step is the same
      size).
    - What each knob does in the sequencer: hold a step key and turn
      [[KNOB1]] to [[KNOB4]] to lock a value (chapter 7).
    - On the FM-1: which encoders the hardware reads directly, once measured
      (docs/01 §6, question 1).

## Buttons

{{status sim planned}}

Fourteen buttons with lights. In the simulator four of them work:

- [[FX]] shows the effect chain: two slots after the sound engine.
  [[SELECT]] moves between the slots and [[ALGORITHM]] changes the effect
  in the chosen slot.
- [[SEL]], in FX mode, picks up the chosen slot so that [[SELECT]] moves it
  along the chain; press [[SEL]] again to put it down.
- [[GLO]] shows the global page (chapter 9); press it again to leave.
- [[HOME]] returns to the sound's page, with a live oscilloscope strip.

[[ENV]], [[LFO]], [[EDIT]], [[SAVE]], [[ARP]], [[SEQ]], [[PLAY/STOP]] and
[[REC]] show a short note in the simulator that they are not there yet.
[[SEQ]], [[PLAY/STOP]] and [[REC]] are planned for the sequencer (chapter 7)
and [[SAVE]] for storage (chapter 9).

!!! outline "To be written"
    - [[OCT-]] and [[OCT+]]: the octave range −3 to +3, the light (off,
      slow, fast or steady for octave 0 to 3 away from the middle), holding
      one and turning [[ALGORITHM]] to transpose by up to ±12 semitones.
    - The button lights: which ones Lunar Modulator uses and what blinking
      means.
    - Planned roles for [[ENV]], [[LFO]], [[EDIT]] and [[ARP]], once decided.

## Keys

{{status sim planned}}

27 keys from F3 to G5: 16 white and 11 black, each with a light. At the
middle octave the lowest key plays MIDI note 53. [[OCT-]] and [[OCT+]] move
the whole keyboard by octaves.

The FM-1 prints labels under the black keys for M-VAVE's own firmware:
[[OP1]] to [[OP6]], [[PIT]], [[MONO]] and [[POLY]], and [[GLO]] once more.
Lunar Modulator does not use them yet.

!!! outline "To be written"
    - Velocity: how hard a key is played (in the simulator, where on the key
      you press).
    - The keys in the sequencer: in GRID mode the white keys are steps and
      the black keys functions (chapter 7).
    - The key lights: notes sounding, steps in the sequencer.

## Screen

{{status sim planned}}

The screen has three parts: a top bar with the sound's name, the current
mode's content in the middle, and a bottom bar with the page and the mode.
Short messages appear for a second over the middle, for example the new value
of [[MASTER]] or why an engine could not be chosen.

!!! outline "To be written"
    - Screenshots of each mode from the simulator: HOME with the
      oscilloscope, a parameter page with its four rows and bars, FX mode
      with both slots, the global page, a list popup.
    - What the bars and highlights mean; how a list opens and closes.

## Connections

{{status planned}}

{{figure edge}}

The connectors are on the edge above the screen. From left to right, seen
from above with the keys towards you:

- [[POWER]]: the slide switch.
- [[USB]]: USB-C, for charging, MIDI and audio to and from a computer.
- [[MIDI IN]]: MIDI input on a 3.5 mm jack.
- [[OUT]]: stereo audio output on a 3.5 mm jack.

!!! outline "To be written"
    - What Lunar Modulator will do over USB: MIDI in and out, and audio to
      the computer (chapter 8).
    - Which MIDI adapter the 3.5 mm input expects (TRS type), once measured.
    - Battery and charging: M-VAVE's manual applies; Lunar Modulator changes
      neither.
