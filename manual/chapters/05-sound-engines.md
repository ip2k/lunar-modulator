# Sound engines

A sound engine is the part of the firmware that makes the notes. Lunar
Modulator has several, each a different kind of synthesis, and one plays at a
time. You choose it with [[PRESETS]]. The knobs then play that engine's
parameters, four to a page: [[SELECT]] turns the page and [[ALGORITHM]] steps
through the engine's main list.

{{engine-summary sound}}

Four of the engines are built from the code of Mutable Instruments' modules,
written by Emilie Gillet and published under the MIT licence; Sophie comes
from the Schwung community. Their names here are this project's own, and
[chapter 13](13-credits-and-licences.md) credits each source.

!!! note "How to read the tables"
    The tables in this chapter are generated from the firmware's code. *Where*
    says on which page, and under which knob, a parameter sits: page 1,
    KNOB2 is the second knob on the first page. A *list* parameter steps
    through named values, numbered from 0; a *continuous* one moves smoothly
    across its range. The default is the value an engine starts with. The
    screen rounds what it shows: two decimals for a range of up to 2, one
    decimal up to 20, whole numbers beyond.

## Choosing an engine

{{status sim planned}}

**To choose an engine:** turn [[PRESETS]]. The engines come in this order:
Macro, Shapes, Macro Heavy, Six-Op FM, Sophie, Test Sine, and round again.
While you turn, the screen shows the previous engine, the new one
(highlighted) and the next. In the simulator you can also pick one from the
**Sound (PRESETS)** list under the panel.

When you choose an engine:

- every note that was sounding ends;
- the new engine starts with its default settings, so changes you made to
  the previous engine are not kept;
- the effects keep their settings;
- the screen stays on the same page if the new engine has that many pages,
  and goes to its last page otherwise.

Every engine but Sophie has a **Volume** parameter, its own output level, on
its last page. It is separate from [[MASTER]], which sets the level of
everything.

!!! note "Engines that need the FM-1's sample rate"
    Macro, Macro Heavy and Six-Op FM run Plaits' code at its own rate, 47,872
    samples a second, and convert the result to the output's rate. They
    cannot run when the output is faster than that. If your browser runs the
    simulator at 48,000 samples a second, [[PRESETS]] steps over those three
    and the screen names the one it skipped ([chapter 2](02-getting-started.md#the-browser-simulator)).

## Macro

{{status sim desktop planned}}

Macro is eight synthesizers in one, from Mutable Instruments Plaits: a
virtual-analogue voice with a filter, phase distortion, wave terrain, a
chiptune voice, a pair of analogue oscillators, a waveshaper, two-operator FM
and a wavetable. Each note passes through Plaits' low-pass gate, which ties
the note's brightness to its level, so that it darkens as it fades, as
acoustic instruments do.

- **Model** chooses one of the eight. [[ALGORITHM]] steps through them, and so
  does [[KNOB1]] on page 1. Changing the model ends the notes that are
  sounding.
- **Harmonics**, **Timbre** and **Morph** are Plaits' three sound controls.
  What each one does depends on the model (below).
- **Decay** sets how long a note takes to fade after you let go of the key.
  While you hold a key, the note sustains.
- **Colour** sets how much the low-pass gate darkens the note as it fades:
  at the left the tone closes down with the level, like a plucked string; at
  the right only the level falls.
- **Volume** is the engine's output level.
- Playing harder makes a note louder and brighter.

| Model | Harmonics | Timbre | Morph |
| --- | --- | --- | --- |
| VA+Filter: an analogue-style waveform through a resonant low-pass filter | The filter's character: a steeper slope on the left, a gentler one on the right, and more resonance the further from the middle | The filter's cutoff | The waveform: sawtooth on the left, square in the middle, a narrowing pulse towards the right; near either end a sub-oscillator an octave down joins in |
| PhaseDist: phase-distortion synthesis | The frequency of the distortion, in steps of musical ratios | The amount of distortion | The asymmetry of the distortion |
| Terrain: the waveform is read along a circular path over a surface | Which of eight terrains, blending between neighbours | The size of the path | Where the path sits on the terrain |
| Chip: a chiptune voice with an arpeggiator | The chord the arpeggiator plays | The arpeggio: up, down, up and down, or random, over one, two or four octaves | Below the middle, a pulse-width effect; above it, hard sync |
| VA Pair: two classic oscillators | The detuning between them | The first oscillator: from a narrow pulse to a square, then hard-sync formants | The second oscillator: from a triangle to a sawtooth with a widening notch |
| Shaper: a waveshaper and wavefolder | The waveshaper's curve | How much the wave is folded | The waveform's asymmetry, from triangle to sawtooth |
| 2-op FM: two operators, one modulating the other | The frequency ratio between them | The modulation amount | Feedback: towards the right the second operator modulates itself, for a rough tone; towards the left it feeds back into the first, for chaotic tones; none in the middle |
| Wavetable: banks of waveforms on an 8 × 8 grid | Which bank. In the first half of its range the waves blend smoothly; in the second they step from one to the next, for a grainier sound | The row in the bank | The column in the bank |

!!! note "Chip, the arpeggiating model"
    Each key press on Chip plays the next note of the arpeggio, a chord built
    on the key you press. Strike one key repeatedly and the notes walk
    through the chord. Each voice keeps its own place in the pattern, so the
    first notes of a chord played across several keys may start at different
    places.

!!! tip "Starting points"
    - **Bass:** VA+Filter with Morph at the left, a sawtooth with its
      sub-oscillator, Timbre low and Decay low.
    - **Pads:** VA Pair with Decay high, and Ensemble then Plate in the effect
      slots ([chapter 6](06-effects.md)).

Macro's output is mono; the effects spread it in stereo. 2-op FM is the
heaviest of its models for the processor, and the others are light.

{{screen macro Macro on its VA Pair model, page 1, while a chord sounds.}}

{{engine-table macro}}

## Macro Heavy

{{status sim desktop planned}}

Macro Heavy holds the larger Plaits models: a string machine, chords,
speech, formants, additive synthesis, a swarm of oscillators, filtered noise,
particles, a modelled string, a modal resonator and three drums. Each voice
needs much more memory than Macro's, so Macro Heavy plays four notes at once.

- **Model**, **Harmonics**, **Timbre**, **Morph**, **Decay**, **Colour** and
  **Volume** work as in Macro. Changing the model ends the notes that are
  sounding.
- **Word Speed**, on page 2, sets how fast the Speech model says its words:
  from a quarter of the normal speed at the left, through normal at 0, to
  four times as fast at the right.
- **String, Modal, Bass Drum, Snare and Hi-Hat** sound by themselves: a key
  press strikes them, and they ring for as long as Morph sets. Speech, when
  it says words, says one word per key press. When you let go of the key,
  Decay and Colour set how quickly whatever is still sounding fades.
- Str Machine plays in stereo. The other models are mono.

{{screen macro-heavy Macro Heavy on Str Machine, page 1.}}

| Model | Harmonics | Timbre | Morph |
| --- | --- | --- | --- |
| Str Machine: a string machine playing a chord on each key, through a filter and an ensemble | The chord | Brightness, with more ensemble towards either end | The registration: sawtooth footages on the left, square ones on the right |
| Chords: a chord on each key | The chord | Inversion and transposition | On the left half, mixes of square and sawtooth harmonics, like an organ or a string machine; on the right half, waveforms from a wavetable |
| Speech: vowels and words | Formant vowels, then early computer-speech vowels, then LPC vowels; above about 0.44, banks of spoken words | The size of the voice, from deep to squeaky | The vowel, or which word of the bank |
| Formant: two formants over a carrier | The ratio between the two formants | The formant frequency | The formants' width and shape |
| Additive: a spectrum of harmonics | How many bumps the spectrum has | Which harmonic is strongest | The shape of the bumps, from flat and wide to peaked and narrow |
| Swarm: a cloud of enveloped sawtooth grains | How far the grains' pitches scatter | How dense the cloud is | The grains' length and overlap |
| Filt Noise: noise through a resonant filter | The filter's response: low-pass, band-pass, high-pass | The noise's clock rate | The resonance |
| Particle: random clicks through filters | How far the particles' pitches scatter | How dense the particles are | Below the middle a reverberating diffuser; above it, increasingly resonant band-pass filters |
| String: a plucked, inharmonic string | Inharmonicity, or the material | The brightness of the excitation, and the amount of dust in it | How long it rings |
| Modal: a struck resonator, such as a bar, a bell or a plate | Inharmonicity, or the material | The brightness of the excitation, and the amount of dust in it | How long it rings |
| Bass Drum: an analogue-style kick | How sharp the attack is, and how much overdrive | Brightness | How long it rings |
| Snare: an analogue-style snare | The balance of tone and noise | The balance between the drum's modes | How long it rings |
| Hi-Hat: an analogue-style hi-hat | The balance of metallic tone and noise | The cutoff of its high-pass filter | How long it rings |

!!! tip "Speaking a word"
    Set Speech's Harmonics above the middle to choose a bank of words, and
    Morph to choose the word. Each key press says it once, on the key's
    pitch. Word Speed makes it faster or slower without changing its pitch.

!!! tip "Drums on a keyboard"
    The drums, String and Modal ring by themselves while you hold the key,
    and fade over the Decay time when you let go. For short taps that still
    ring out, raise Decay. With four voices, a fifth note takes over one that
    is already sounding.

{{engine-table macro-heavy}}

## Six-Op FM

{{status sim desktop planned}}

Six-Op FM is a six-operator FM synthesizer in the tradition of the classic
1980s FM keyboards, from Plaits' six-operator engine, with the 96 patches
that Plaits ships in three banks of 32. Each patch is a complete sound with
its own algorithm, envelopes and velocity response. [[ALGORITHM]] steps
through the patches, and the knobs adjust the one you have chosen.

- **Patch** chooses one of the 96. Its name starts with its bank, 1 to 3. A
  new patch applies to the next note you play; notes already sounding keep
  theirs.
- **Brightness** scales the modulating operators: below the middle the sound
  is softer, above it brighter and harsher. In the middle the patch plays as
  programmed.
- **Envelope** scales the patch's envelope times. Attacks and decays are
  shorter towards the left and longer towards the right, and play as
  programmed in the middle. Releases play as programmed a little left of the
  middle, at 0.3, and grow longer either side of it: at the default, 0.5,
  they last about three times as long as programmed.
- **Volume**, on page 2, is the engine's output level.
- Eight notes play at once.

{{screen sixop Six-Op FM on its default patch, 2 E.PIANO 1. Its first page has three controls.}}

The banks:

| Bank | Patch numbers | What is in it |
| --- | --- | --- |
| 1 | 0 – 31 | Basses, analogue-style synthesizers, leads, textures and effects |
| 2 | 32 – 63 | Electric and acoustic pianos, clavinets, plucked strings, mallets, bells, drums and percussion |
| 3 | 64 – 95 | Organs, pads, textures, strings and brass |

!!! note "Patch names"
    A few of the stored patch names are trademarks or a person's name. Public
    builds show those patches under descriptive names of this project's own;
    the sound is the same.

!!! tip "Shaping a patch"
    Turn Envelope left for snappier attacks and quicker decays, and right to
    slow them into swells. Brightness works like a tone control for the whole
    patch.

{{engine-table sixop}}

## Shapes

{{status sim desktop planned}}

Shapes is the macro-oscillator from Mutable Instruments Braids: 47 shapes,
from analogue waveforms and their sync and sub-oscillator versions to
formants, FM, physical models of plucked, bowed and blown instruments, bells
and drums, wavetables, noise and granular textures. Each voice has its own
attack and release envelope.

- **Shape** chooses one of the 47. [[ALGORITHM]] steps through them, and a new
  shape applies at once, to notes that are sounding too.
- **Timbre** and **Color** are the two controls Braids gives every shape;
  what they do depends on the shape (below).
- **Attack** sets how long a note takes to rise, and **Release**, on page 2,
  how long it takes to fade after you let go. Both run from 1 ms at the left
  to 4 seconds at the right.
- **Volume**, on page 2, is the engine's output level.
- Playing harder makes a note louder.

{{screen shapes Shapes on Pluck, page 1.}}

| No. | Shape | Timbre | Color |
| --- | --- | --- | --- |
| 0 | CSaw: a sawtooth with a notch | Where the notch falls | How deep it is |
| 1 | Morph: one oscillator through a filter | The waveform: triangle, sawtooth, square, then a narrowing pulse | A low-pass filter that closes, with more overdrive, as Color rises |
| 2 | Saw/Sqr | The shape of both waves | From sawtooth to square |
| 3 | Sine/Tri: a wavefolder | How much the wave is folded | From a folded sine to a folded triangle |
| 4 | Buzz: a buzzy train of harmonics | How many harmonics | A second buzz voice, detuned by up to a semitone |
| 5, 6 | Sqr Sub, Saw Sub: a wave with a sub-oscillator | The pulse width, or the sawtooth's shape | The sub-oscillator: none in the middle, two octaves down towards the left, one octave down towards the right |
| 7, 8 | Sqr Sync, Saw Sync: two oscillators in hard sync | The pitch of the synced oscillator | The balance between the two |
| 9 – 12 | 3x Saw, 3x Sqr, 3x Tri, 3x Sine: three oscillators | The second oscillator's interval, from two octaves down to two up, slightly detuned near the middle | The third oscillator's interval |
| 13 | 3x Ring: three sines, ring-modulated | The second sine's pitch | The third sine's pitch |
| 14 | Swarm: a swarm of sawtooths | How far they are detuned | A high-pass filter |
| 15 | Comb: a sawtooth through a comb filter | The comb's pitch | The resonance, from negative on the left to positive on the right |
| 16 | Toy: a circuit-bent, low-fidelity oscillator | The sample-rate reduction | Digital bit-mangling |
| 17 – 20 | LP Flt, Peak Flt, BP Flt, HP Flt: waveforms that sound like a resonant filter | The filter's frequency | The shape of the wave under it |
| 21 | Vosim: two formants | The first formant's frequency | The second formant's frequency |
| 22 | Vowel: vowel synthesis | The vowel | The size of the voice |
| 23 | Vowel FOF: sung vowels | The vowel | The kind of voice |
| 24 | Harmonic: additive harmonics | Which harmonic is strongest | How widely the energy spreads around it |
| 25 – 27 | FM, FB FM, Chaos FM: two-operator FM, with feedback in the last two | The modulation amount | The frequency ratio |
| 28 | Pluck: a plucked string | How long it rings | Where it is plucked |
| 29 | Bowed: a bowed string | The bow's friction | Where it is bowed |
| 30 | Blown: a reed instrument | The breath pressure | The instrument's body |
| 31 | Flute: a flute | The breath pressure | The mouthpiece's geometry |
| 32 | Bell: a struck bell | How long it rings | Inharmonicity |
| 33 | Drum: a struck drum | How long it rings | Brightness, from tone towards noise |
| 34 | Kick: an analogue-style kick | How long it rings | Its tone |
| 35 | Cymbal: a metallic cymbal | The filter's frequency | The balance of metal and noise |
| 36 | Snare: an analogue-style snare | The drum's tone | How much snare rattle |
| 37 | Wavetbl: wavetables | The position in the table | Which table |
| 38 | Wave Map: a map of waveforms | One coordinate on the map | The other coordinate |
| 39 | Wave Line: a line of waveforms | The position along the line | How the waves are drawn and joined, between smooth and stepped |
| 40 | Wave x4: four voices from wavetables | The position among the waves | The chord |
| 41 | Filt Noise: noise through a filter that follows the key | The resonance | The response: low-pass, band-pass, high-pass |
| 42 | Twin Peak: noise through two resonant peaks | The resonance | The second peak's frequency |
| 43 | Clk Noise: stepped noise clocked by the key's pitch | How often the random pattern repeats | How many levels it steps between, from 2 to 32 |
| 44 | Granular: a cloud of sine grains | The grains' length | How far their pitches scatter |
| 45 | Particle: random clicks through resonant filters | How dense the particles are | How far the filters' frequencies scatter |
| 46 | Digital: a digitally modulated carrier | The data rate | The data sent |

!!! note "The struck shapes"
    Pluck, Bell, Drum, Kick, Cymbal and Snare are struck when you press a key
    and die away by themselves, however long you hold it. Release matters
    only if you let go before they have finished.

!!! note "Memory"
    Shapes is the largest engine: twelve voices take about 201 KB of the
    roughly 379 KB the simulator allows for the engine and both effects
    ([chapter 12](12-specifications.md)). With
    PSX Verb and Plate together in the effect slots it does not fit, and the
    memory figure on the screen turns red. The FM-1 build may play fewer
    Shapes notes at once.

{{engine-table shapes}}

## Sophie

{{status sim desktop planned}}

Sophie is a sixteen-pad metallic FM percussion synthesizer by Matt Estela,
from the Schwung community. Each pad is a drum sound of its own. A hit rings
for its pad's Decay, whether or not you keep the key down.

- Sophie plays MIDI notes 36 to 51, one pad each, and ignores other notes.
  Its pads follow the General MIDI drum layout: 36 is the kick, 38 the snare,
  42 the closed hi-hat and so on, so drum parts from other instruments play
  the right sounds.
- **Pad** chooses which pad the other knobs edit. [[ALGORITHM]] steps through
  the pads, and so does [[KNOB1]] on page 1.
- **Tune** sets the pad's pitch in semitones, from two octaves down to two
  octaves up, relative to its key.
- **Decay** is how long a hit takes to die away, in seconds.
- **Model** chooses how the pad's operators are wired: *Fuse*, two
  modulators in series, very responsive to feedback; *Stack*, a dense stack
  of operators; *Split*, operators side by side with uneven modulation; and
  *Shard*, a coarse, stepped wave mixed with noise. On pad 1, the kick,
  a sine body always carries the weight, and Model adds a layer over it.
- **Color** moves the modulators' frequency ratios through inharmonic,
  clangorous zones.
- **Metal** sets how much the operators modulate one another: the higher, the
  more metallic.
- **Feedback** feeds the sound back into its own modulator, for a rougher
  edge.
- **Sweep** bends the start of each hit: a fast drop in pitch towards the
  right, a fast rise towards the left.
- Playing harder makes a hit louder. Sophie ignores pitch bend.

{{screen sophie Sophie on pad 1, the kick, just after it was struck.}}

**To play Sophie from the FM-1's keys:** press [[OCT-]] twice. The pads then
run from the eighth key, a C, upwards: kick, rim, snare, clap and so on, up
the white and black keys. On the computer keyboard, after pressing
<kbd>Z</kbd> twice, <kbd>G</kbd> is the kick, <kbd>H</kbd> the snare,
<kbd>O</kbd> the closed hi-hat and <kbd>[</kbd> the open hi-hat.

!!! caution "The values shown after you change pads"
    The screen cannot read a pad's settings back from Sophie. When you choose
    another pad, the screen keeps showing the values you last set. The first
    turn of a knob gives the new pad the value shown, plus that turn.

Sophie has further controls for each pad, for bit crushing, drive, level, a
filter and a ring resonator, which this build does not show on the screen
yet.

{{engine-table sw-sophie}}

## Test Sine

{{status sim desktop}}

Test Sine plays a plain sine wave for each note, at a level set by velocity,
with 5 ms fades in and out. It exists to test the firmware and the
simulator, and has a single control, **Volume**. When all twelve voices are
busy, it ignores further notes until one is free.

{{engine-table test-sine}}

{{engine-others sound}}
