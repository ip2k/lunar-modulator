# Playing

This chapter covers playing notes: the keys and how many notes sound at once,
how hard you play, the octave and transpose controls, how notes end, pitch
bend, and notes that arrive from a MIDI keyboard.

## Keys and voices

{{status sim desktop planned}}

Each key plays one note for as long as you hold it. A *voice* is one sounding
note, and each engine has a fixed number of them:

| Engine | Voices |
| --- | --- |
| Macro, Shapes, Sophie, Drums, Test Sine | 12 |
| Six-Op FM | 8 |
| Macro Heavy | 4 |

A note keeps its voice while it fades out after you let go, so a fast run of
notes can use more voices than the keys you are holding.

### When every voice is busy

When you play a note and no voice is free, the engine takes one over:

- **Macro, Macro Heavy, Six-Op FM and Shapes** take a voice whose key has
  already been let go, choosing the one whose note started first. If every
  key is still held, they take the note that started first.
- **Sophie** takes the hit that started longest ago.
- **Drums** takes the quietest hit, so an old cymbal that still rings loud
  keeps going. It first takes a hit that a hi-hat is cutting short.
- **Test Sine** ignores the new note until a voice is free.

On Macro, Macro Heavy, Six-Op FM and Shapes, playing a key again while its
note is still fading restarts that note in the same voice. On Sophie each hit
gets a voice of its own. On Drums a pad struck again while it rings is struck
again in its own voice, as a drum is.

!!! note "Many notes at once"
    Twelve voices playing loudly together can add up to more than the output
    can carry. The limiter after the effects turns the sum down so that it
    never clips ([chapter 6](06-effects.md#the-limiter)).

## Velocity

{{status sim desktop planned}}

Every note carries a velocity from 1 to 127 that says how hard it was played.

| Where the note comes from | Its velocity |
| --- | --- |
| A key of the simulator, with the mouse or a touch screen | From 30 at the top of the key to 127 at its bottom edge |
| The computer keyboard | Always 100 |
| A MIDI keyboard | The keyboard's own |
| The desktop tools | The velocity written in each `--note` |

What velocity changes depends on the engine:

| Engine | What a harder note does |
| --- | --- |
| Macro, Macro Heavy | Louder and brighter: velocity opens the low-pass gate further. The range is gentle, so soft notes stay clearly audible. On the models that sound by themselves (String, Modal and the drums) it sets how hard the sound is struck, and on spoken words how loud they are |
| Six-Op FM | Whatever the patch was programmed to do with velocity: depending on the patch, louder, brighter, both, or neither |
| Shapes, Sophie, Test Sine | Louder |
| Drums | Louder and harder: how much, Accent sets |

Whether the FM-1's own keys can sense how hard they are played has not been
measured yet.

## Octave and transpose

{{status sim planned}}

At the middle octave the keys play F3 to G5. You can move the keyboard by
octaves, three at most either way, and transpose it by semitones, twelve at
most either way.

**To move the keyboard by an octave:** press [[OCT-]] or [[OCT+]]. The screen
shows the new octave, such as *Octave +1*.

**To transpose:** hold [[OCT-]] or [[OCT+]] and turn [[ALGORITHM]]. Each step
is a semitone, and the screen shows the total, such as *Transpose -2*.

**To return to the middle octave and cancel the transpose:** press [[OCT-]]
and [[OCT+]] together.

!!! note "Pressing an octave button to transpose"
    The octave changes as soon as you press [[OCT-]] or [[OCT+]], so holding
    one to transpose also moves the keyboard an octave. Let go, then press the
    other button once to move the octave back: the transpose stays.

The note a key plays is

> 53 + the key's position + 12 × the octave + the transpose,

counting the lowest key as position 0. For example, at octave +1 with a
transpose of −2, the lowest key plays 53 + 0 + 12 − 2 = 63, D♯4, instead of
F3.

The lights in [[OCT-]] and [[OCT+]] show the octave: the button for the
direction you moved lights up, with a slow blink one octave from the middle,
a fast blink two away and a steady light three away. The transpose has no
light; the global page ([[GLO]]) shows both the octave and the transpose.

A key you are holding keeps its note when you change the octave or the
transpose: the change applies to the next key you press. The octave and
transpose move the panel's keys only; notes from a MIDI keyboard play as
they arrive.

## How notes end

{{status sim desktop planned}}

When you let go of a key, each engine ends the note in its own way:

| Engine | While you hold the key | After you let go |
| --- | --- | --- |
| Macro | The note sustains, through Plaits' low-pass gate | It fades out as the gate closes; Decay sets how long that takes, Colour how much darker it gets as it fades |
| Macro Heavy, most models | As Macro | As Macro |
| Macro Heavy, String, Modal, the drums and spoken words | The sound rings or speaks by itself, and may end before you let go | Any sound still ringing fades out, over a time set by Decay and Colour |
| Six-Op FM | The patch's own envelopes, scaled by Envelope | The patch's release, scaled by Envelope |
| Shapes | The note rises over the Attack time and then holds. The struck shapes, such as Pluck, Bell and Drum, also die away by themselves | It fades over the Release time |
| Sophie | Each hit rings for its pad's Decay | Letting go changes nothing |
| Drums | Each hit rings for its pad's decay; a closed or pedal hi-hat cuts the open one short | Letting go changes nothing |
| Test Sine | The note holds | It fades in 5 ms |

[Chapter 5](05-sound-engines.md) describes each of these controls.

### Releasing every note

If a note keeps sounding, release everything at once:

- in the simulator, press <kbd>Esc</kbd>;
- from a MIDI keyboard, send control change 123, *all notes off*.

Every note then ends as if you had let go of its key, with its normal
release. Choosing another sound engine also ends every note.

## Pitch bend

{{status sim desktop planned}}

Pitch bend moves the pitch of every sounding note, and of notes played while
it is held, up or down.

- **In the simulator**, the pitch-bend wheel of a MIDI keyboard bends by up
  to two semitones either way.
- **In the desktop tools**, `--bend T:SEMITONES` sets the bend from time *T*,
  by up to 48 semitones either way ([chapter 2](02-getting-started.md#the-desktop-tools)).
- **Sophie** ignores pitch bend; every other engine follows it.

The FM-1 has no pitch wheel, so on the device bend is planned to arrive over
MIDI.

## Playing from MIDI

{{status sim planned}}

Notes, velocity and pitch bend from a MIDI keyboard play the engine as the
panel's keys do, and you can play both at once. The simulator listens on every
MIDI channel; control change 7 sets the volume like [[MASTER]], and control
change 123 releases every note. [Chapter 8](08-midi.md) lists everything the
simulator receives.

On the FM-1, Lunar Modulator is planned to receive MIDI over USB and at the
3.5 mm [[MIDI IN]] jack. The FM-1 also has Bluetooth, which M-VAVE's firmware
uses for MIDI; whether Lunar Modulator will use it is not decided yet.
