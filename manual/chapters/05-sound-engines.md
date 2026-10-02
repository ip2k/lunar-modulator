# Sound engines

A sound engine is the part of the firmware that makes the notes. Lunar
Modulator has several, each a different kind of synthesis, and you choose one
with [[PRESETS]]. The knobs then play that engine's parameters, four to a
page; [[SELECT]] turns the page and [[ALGORITHM]] steps through the engine's
main list.

{{engine-summary sound}}

Most of the engines come from Mutable Instruments' modules, written by Emilie
Gillet and published under the MIT licence; two come from the Schwung
community. Their names here are this project's own; chapter 13 credits each
source.

!!! note "How to read the tables"
    The tables in this chapter are generated from the firmware's code. *Page*
    and *knob* say where a parameter sits: page 1, [[KNOB2]] is the second
    knob on the first page. A *list* parameter steps through named values,
    numbered from 0; a *continuous* one moves smoothly across its range. The
    default is the value an engine starts with.

## Macro

{{status sim desktop planned}}

Macro is eight synthesizers in one, from Mutable Instruments Plaits: a
virtual-analogue voice with a filter, phase distortion, wave terrain,
chiptune, a pair of analogue oscillators, a waveshaper, two-operator FM and a
wavetable. Each note runs through Plaits' low-pass gate, which shapes both its
level and its brightness, like a plucked string or a struck membrane.

- **Model** chooses one of the eight. [[ALGORITHM]] steps through them.
- **Harmonics**, **Timbre** and **Morph** are Plaits' three sound controls.
  What each one does depends on the model: in general Harmonics picks the
  material, Timbre its brightness and Morph its shape.
- **Decay** sets how long a note rings after it starts; **Colour** how much
  the low-pass gate closes the tone as the note dies away, from a dull pluck
  to a bright, open one.
- Playing harder makes a note louder and brighter.

!!! outline "To be written"
    - One paragraph per model: what Harmonics, Timbre and Morph do there and
      a starting point (from `engines/reference-plaits.md` and Plaits'
      manual, summarised in our words).
    - Tips: Chip for bass, VA Pair with Ensemble for pads, 2-op FM's cost
      (the heaviest Macro model).
    - The release after a key is let go: the low-pass gate's tail.

{{engine-table macro}}

## Macro Heavy

{{status sim desktop planned}}

Macro Heavy holds the larger Plaits models: a string machine, chords,
speech, formants, additive synthesis, a swarm of oscillators, filtered noise,
particles, a modelled string, a modal resonator and three drums. Each voice
needs much more memory than Macro's, so Macro Heavy plays four notes at once.

- **Model**, **Harmonics**, **Timbre**, **Morph**, **Decay** and **Colour**
  work as in Macro.
- **Word Speed** sets how fast the Speech model says its words.
- The string, modal and drum models shape their own level; for them Decay
  and Colour set the release after you let go of the key.

!!! outline "To be written"
    - One paragraph per model, as for Macro, with the speech word banks.
    - Drums on a keyboard: which models answer note-off and which ring out.
    - Four voices: what happens with a fifth note.

{{engine-table macro-heavy}}

## Six-Op FM

{{status sim desktop planned}}

Six-Op FM is a six-operator FM synthesizer in the tradition of the classic
1980s keyboards, from Plaits' six-op engine, with the 96 patches Plaits ships
in three banks of 32. Each patch is a complete sound: [[ALGORITHM]] steps
through them and the knobs adjust it.

- **Patch** chooses one of the 96, named by bank and name.
- **Brightness** scales the modulators: below the middle the sound is
  softer, above it brighter and harsher. At the middle the patch plays as
  programmed.
- **Envelope** scales the patch's attack and decay times: shorter towards
  the left, longer towards the right, as programmed at the middle. Releases
  are shortest a little left of the middle and grow longer either side of
  it; at the default they last about three times as long as programmed.
- Eight notes play at once.

!!! note "Patch names"
    A few of the stored patch names are trademarks or a person's name.
    Public builds show those patches under descriptive names of this
    project's own; the sound is the same.

!!! outline "To be written"
    - A short tour of the three banks: basses and leads; keys, mallets and
      percussion; organs, pads, strings and brass.
    - Tips: Envelope for turning a pad into a pluck; Brightness with a
      velocity-sensitive keyboard.
    - Loading your own DX7-style banks: not planned yet (chapter 9).

{{engine-table sixop}}

## Shapes

{{status sim desktop planned}}

Shapes is the macro-oscillator from Mutable Instruments Braids: 47 shapes,
from analogue waveforms and their sync and sub-oscillator versions to
formants, FM, physical models of plucked, bowed and blown instruments, bells
and drums, wavetables, noise and granular textures. Each voice has its own
attack and release envelope.

- **Shape** chooses one of the 47. [[ALGORITHM]] steps through them.
- **Timbre** and **Color** are the two controls Braids gives every shape;
  what they do depends on the shape.
- **Attack** and **Release** shape each note's level.

!!! outline "To be written"
    - The shapes in families, with what Timbre and Color do in each (from
      `engines/reference-braids-fx.md` and Braids' manual, in our words).
    - The struck shapes (Pluck, Bell, Drum, Kick, Cymbal, Snare): they ring
      on their own, so Release matters less.
    - Memory: Shapes is the largest engine (about 200 KB at twelve voices),
      so the FM-1 build may play fewer notes at once.

{{engine-table shapes}}

## Sophie

{{status sim desktop planned}}

Sophie is a sixteen-pad metallic FM percussion synthesizer by Matt Estela,
from the Schwung community. Each pad has its own sound; a hit rings for its
own decay, whether or not you keep the key down.

- Sophie plays MIDI notes 36 to 51, one pad each, and ignores other notes.
  At the FM-1's middle octave the keys start at note 53, so press [[OCT-]]
  twice: the pads then run from the eighth key, a C, upwards.
- **Pad** chooses which pad the knobs edit; [[ALGORITHM]] steps through
  them.
- **Tune**, **Decay**, **Model**, **Color**, **Metal**, **Feedback** and
  **Sweep** edit the chosen pad.
- Sophie ignores pitch bend.

!!! outline "To be written"
    - The four models (Fuse, Stack, Split, Shard) and what Color, Metal,
      Feedback and Sweep do to a hit.
    - Building a kit: start from the default pads, tune them, set decays.
    - The pages beyond the second (crush, drive, filter, ring), which the
      firmware does not show yet.

{{engine-table sw-sophie}}

## Test Sine

{{status sim desktop}}

Test Sine plays a plain sine wave for each note. It exists to test the
firmware and the simulator, and has a single control, **Volume**.

{{engine-table test-sine}}

{{engine-others sound}}
