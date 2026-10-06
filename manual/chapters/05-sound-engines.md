# Sound engines

A sound engine is the part of the firmware that makes the notes. Lunar
Modulator has several, each a different kind of synthesis, and up to four
sounds, each with an engine of its own, play at once
([Four sounds at once](#four-sounds-at-once)). You choose the current
sound's engine with [[PRESETS]]. The knobs then play that engine's
parameters, four to a page: [[SELECT]] turns the page and [[ALGORITHM]] steps
through the engine's main list.

{{engine-summary sound}}

Four of the engines are built from the code of Mutable Instruments' modules,
written by Emilie Gillet and published under the MIT licence, and Drums
takes its kicks, toms, snares and hi-hats from it; FM6 comes from msfa,
the FM synthesizer core Google published under the Apache licence; Sophie
comes from the Schwung community. Their names here are this project's own,
and [chapter 14](14-credits-and-licences.md) credits each source.

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
Macro, Shapes, Macro Heavy, Six-Op FM, FM6, Sophie, Drums, Acid Bass,
Crater Kit, Test Sine, and round again. Acid Bass and Crater Kit are there
only in builds with the GPL switch on, as the simulator is while we test
([Acid Bass](#acid-bass), [Crater Kit](#crater-kit)).
While you turn, the screen lists the engines, eight at a time, with the new one
highlighted ([chapter 3](03-panel-tour.md#lists)). In the simulator you can also pick one from the
**Sound (PRESETS)** list under the panel.

When you choose an engine:

- every note that was sounding on that sound ends; the other sounds play on;
- the new engine starts with its default settings, so changes you made to
  the previous engine are not kept;
- the effects keep their settings;
- the screen stays on the same page if the new engine has that many pages,
  and goes to its last page otherwise.

Every engine but Sophie has a **Volume** parameter, its own output level, on
its second page (on Drums and Crater Kit, their third). It is separate from [[MASTER]], which sets the level of
everything. Macro, Macro Heavy, Six-Op FM, FM6 and Shapes also have
**Glide** and **Voice Mode**, for sliding between notes and playing one
voice at a time ([chapter 4](04-playing.md#glide-and-voice-modes)).

!!! note "Engines that need the FM-1's sample rate"
    Macro, Macro Heavy, Six-Op FM and Drums run Plaits' code at its own
    rate, 47,872 samples a second, and convert the result to the output's
    rate. They cannot run when the output is faster than that. If your
    browser runs the simulator at 48,000 samples a second, [[PRESETS]] steps
    over those four and the screen names the one it skipped ([chapter 2](02-getting-started.md#the-browser-simulator)).
    Crater Kit, built for 44,100 samples a second, runs only near that
    rate, 44,000 to 44,200, and is stepped over at others in the same way.

## Four sounds at once

{{status sim desktop planned}}

Up to four sounds play at once, each an engine of its own with two insert
effects and a level into the mix; the mix then goes through the two master
effects ([chapter 6](06-effects.md#the-effect-chain)). Sound 1 always holds
an engine; Sounds 2 to 4 can be empty, as they are when the simulator
starts. The sequencer's tracks play whichever sound their route names
([chapter 7](07-sequencer.md#routing)).

{{diagram signal-flow}}

**The current sound** is the one the keys and [[MIDI IN]] play, and the one
the sound's page, [[PRESETS]], [[ALGORITHM]] and the knobs edit.

- **To choose it:** hold [[SEL]] and turn [[PRESETS]]: Sound 1 to 4. The
  screen lists the four sounds and the engine each holds, such as *S2
  Shapes* or *S3 Empty*, with the current one highlighted. [[SEL]] has this
  job everywhere but in FX mode, where it picks up effects.
- **To give it an engine:** turn [[PRESETS]]. On Sounds 2 to 4 the list
  starts with *Empty*, which unloads that sound.
- Once a second sound is in use, the top bar names the current one, such as
  *S2 Shapes*.
- Focusing a sequencer track makes the sound it plays the current one
  ([chapter 7](07-sequencer.md#tracks-and-routing)); you can choose another
  afterwards.
- A key you hold, or a note at [[MIDI IN]], is released on the sound it
  started on, even after you choose another.
- In the simulator, the **Sound (PRESETS)** list under the panel is the
  current sound's, and its label names it.

Each sound's level, from 0 to 100 %, is on the Mix page in FX mode
([chapter 6](06-effects.md#the-mix-page)). Every sound counts against the
FM-1's memory, and a sound that would not fit is refused
([chapter 6](06-effects.md#memory)): Shapes twice, for one, does not fit.

In the desktop tools, `--sound K:ID` loads sound *K*, `--sound-note` plays a
note on it and `--level K:PCT` sets its level
([chapter 2](02-getting-started.md#options)).

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
- Page 3 holds Plaits' own envelope, which every note restarts and Decay
  shortens or lengthens:
  - **Env Pitch**, **Env Timbre** and **Env Morph** set how far it moves the
    note, Timbre and Morph, from nothing in the middle to the most at either
    end, to the right upwards and to the left downwards. A short Decay with
    some Env Pitch gives a falling zap or a drum-like thump. On Chip, Env
    Timbre sets the arpeggio's own fade instead: the further from the
    middle, the shorter each note.
  - **LPG** chooses how the low-pass gate plays: **Gate** follows the key,
    as described above; **Ping** strikes the gate at each key press and lets
    it close over the Decay time even if you hold the key, like a plucked or
    struck sound; **Off** takes the gate out, so the note keeps its full
    brightness and only its level fades after you let go.
- Page 4 holds **Glide** and **Voice Mode**: slides between notes, and
  one-voice playing ([chapter 4](04-playing.md#glide-and-voice-modes)).

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
- Page 3 works as in Macro. On Speech, Env Pitch also lets a spoken word's
  own pitch contour through. With LPG on Ping, String, Modal and the drums
  ring out after you let go, instead of fading.
- Page 4, **Glide** and **Voice Mode**, works as in Macro. On Legato a
  string, a modal sound or a drum is not struck again when you play over a
  held key, and a word goes on; on Mono it is.
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
- **Glide** and **Voice Mode**, on page 2, slide between notes and play one
  voice ([chapter 4](04-playing.md#glide-and-voice-modes)). On Legato a
  note played over a held one does not restart the patch's envelopes.
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

## FM6

{{status sim desktop planned}}

FM6 is a six-operator FM synthesizer that plays voices in the format of
the classic 1980s FM keyboards, the DX7's: 155 parameters for six operators
with their own envelopes, 32 algorithms, feedback, an LFO and a pitch
envelope. Its synthesis is msfa, the FM core Google published for Android,
the same core the FM-1's own firmware runs. It comes with 32 voices of this
project's own, and plays voices you load from SysEx files (below).
[[ALGORITHM]] steps through the voices, and the knobs shape the one you
have chosen.

Both the engine and its name are borrowed, with thanks: the engine is
Google's msfa, and the name is that of the FM engine in hugelton's Felucca,
open firmware for the FM-1, whose port of the same core checks FM6's sound
in this project's tests.

{{screen fm6 FM6 on its first voice, TINE EP, while a chord sounds.}}

- **Patch** chooses a voice: the 32 built-in ones, then User 1 to User 32,
  which show the names of the voices you have loaded. A new voice applies
  to the next note you play; notes already sounding keep theirs.
- **Brightness** moves the level of every modulating operator, up to 24 dB
  down at the left and up at the right. In the middle the voice plays as
  programmed. The carriers, and so the loudness, do not change.
- **Env Time** runs all the voice's envelopes faster or slower, the pitch
  envelope's too: up to 8 times faster at the left, 8 times slower at the
  right, as programmed in the middle. It acts on notes that are sounding.
- **Feedback** adds to the voice's own feedback, from 0 to 7 in whole steps.
- **Volume**, on page 2, is the engine's output level.
- **Glide** and **Voice Mode**, on page 2, slide between notes and play one
  voice ([chapter 4](04-playing.md#glide-and-voice-modes)). On Legato a
  note played over a held one keeps the envelopes and the LFO running.
- Twelve notes play at once.

The built-in voices:

| Patch numbers | What they are |
| --- | --- |
| 0 – 4 | Keys: two electric pianos, a clavinet-like pluck, a harpsichord, a koto |
| 5 – 10 | Mallets and bells: marimba, vibraphone (with tremolo), tubular bell, glass bell, chimes, steel drum |
| 11 – 13 | Organs: drawbars, drawbars with a percussive click, a gritty rock organ |
| 14 – 17 | Brass and winds: brass, soft brass, flute, clarinet |
| 18 – 21 | Strings and pads: strings, warm pad, glass pad, a slow sweep |
| 22 – 24 | Basses: FM bass, plucked bass, saw bass |
| 25 – 27 | Leads: saw, square, a sync-like sweep |
| 28 – 30 | Drums: kick (play it low), snare, hi-hat |
| 31 | A pure sine, for tuning and tests |
| 32 – 63 | User 1 to User 32, named after the voices loaded into them |

### Loading voices from SysEx

{{status sim desktop}}

The user slots take voices from SysEx files (`.syx`), the format the DX7 and
its editors save: a single voice, or a bank of 32. A bank fills User 1 to
User 32; single voices go to the user slots one after another, starting
after the last one loaded. A file may hold several dumps. Values out of
range are brought into range, and anything that is not a voice dump is
skipped.

In the simulator ([chapter 2](02-getting-started.md#the-browser-simulator)):

1. Power on.
2. Choose **Load DX7 patches…** under the panel and pick one or more `.syx`
   files, or drop the files anywhere on the page.
3. The screen shows *Loaded 32 voices* (or how many there were), which user
   slots they went to and the first voice's name, and the status line under
   the panel says the same. The current sound now plays the first voice
   loaded: if it was another engine, it becomes FM6.
4. Turn [[ALGORITHM]] to step through the voices by name. Every sound you
   set to FM6 later has them too.

The file is read in your browser; nothing is uploaded. The simulator checks
it first: a file that is empty, is not SysEx, holds SysEx of another kind,
is cut short, or holds a voice dump of the wrong length loads nothing, and
the status line says which. A dump whose checksum is wrong is loaded all the
same, as DX7 editors load one, and the status line says the file may be
damaged. Files of up to 64 KB are read. The voices stay until you power
off.

On the desktop, `fm1-render --sysex FILE.syx` loads files before the first
note ([chapter 2](02-getting-started.md#rendering-a-sound)), and prints the
names it found.

!!! note "Voices from elsewhere"
    Files of DX7 voices circulate widely, Yamaha's own factory voices among
    them. They are not part of Lunar Modulator, and nothing here comes with
    them: load only files you are entitled to use.

!!! tip "Two algorithms with a loop"
    Algorithms 4 and 6 feed a whole stack of operators back on itself, as
    the DX7 does; FM6 runs that loop, where msfa itself plays those two
    algorithms without feedback. The built-in SAW BASS uses it.

{{engine-table dx7}}

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
- **Glide** and **Voice Mode**, on page 2, slide between notes and play one
  voice ([chapter 4](04-playing.md#glide-and-voice-modes)). On Legato a
  note played over a held one does not strike the shape again.
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
    Shapes is the largest engine: twelve voices take about 202 KB of the
    roughly 379 KB the simulator allows for everything
    ([chapter 13](13-specifications.md)). With PSX Verb and Plate together
    as effects it does not fit, nor as two sounds at once, and the simulator
    refuses what would not ([chapter 6](06-effects.md#memory)). The FM-1
    build may play fewer Shapes notes at once.

!!! note "At the edges"
    Shapes keeps Braids within the range its code was written for. A note
    bent or offset above MIDI 127 sounds as the top of that range, on every
    shape. Comb's Timbre stops where the comb reaches its lowest pitch, which
    only the lowest four octaves of keys get to, and sounds the same there.
    The last sliver of Wave Line's Timbre (above about 98 %) plays the
    line's last wave.

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

**To play Sophie from the FM-1's keys:** play the white keys. With a drum
kit as the sound (Sophie or Drums), the sixteen white keys play the sixteen
pads at any octave, from the kick on the lowest F up to the ride on the
highest white key, and the black keys play nothing. On the computer
keyboard, <kbd>A</kbd> is the kick, <kbd>S</kbd> the rim, <kbd>D</kbd> the
snare, <kbd>F</kbd> the clap, <kbd>J</kbd> the closed hi-hat, <kbd>L</kbd>
the pedal hi-hat and <kbd>&#39;</kbd> the open hi-hat. A MIDI keyboard
plays the pads on notes 36 to 51, as a drum part from another instrument
expects.

!!! caution "The values shown after you change pads"
    The screen cannot read a pad's settings back from Sophie. When you choose
    another pad, the screen keeps showing the values you last set. The first
    turn of a knob gives the new pad the value shown, plus that turn.

Sophie has further controls for each pad, for bit crushing, drive, level, a
filter and a ring resonator, which this build does not show on the screen
yet.

{{engine-table sw-sophie}}

## Drums

{{status sim desktop planned}}

Drums is a sixteen-pad drum kit after the classic analogue drum machines: a
deep kick with a long boom, a short punchy one, two snares, a clap, closed,
pedal and open hi-hats, six toms, a rim shot, a crash and a ride, and a
cowbell you can put on any pad. Its kicks, toms, snares and hi-hats are
Plaits' drum models; the rim shot, clap, cowbell and cymbals are this
project's own, after published studies of the analogue circuits
([chapter 14](14-credits-and-licences.md)).

- Drums plays MIDI notes 36 to 51, one pad each, in the same order as
  Sophie, and ignores other notes: 36 is the kick, 38 the snare, 42 the
  closed hi-hat, 46 the open one, 49 the crash and 51 the ride. On the
  FM-1's keys the sixteen white keys play the pads ([Sophie](#sophie) shows
  which key is which).
- A hit rings for its pad's decay, whether or not you keep the key down. Up
  to twelve hits sound at once. A pad struck again while it rings is struck
  again, as a drum is, rather than starting a second sound; a thirteenth pad
  takes over the quietest hit.
- A closed or pedal hi-hat cuts the open hi-hat short, as on the machines.
- **Pad** chooses which pad the pad's knobs edit: those on pages 1 and 2,
  and Model on page 3. [[ALGORITHM]] steps through the pads, and so does
  [[KNOB1]] on page 1. Each pad keeps its own settings.
- The pad's knobs start in the middle, Tune at 0: that is the pad as the
  kit sets it up, and you turn from there. So until you change them the
  screen shows true values whichever pad you choose.
  - **Tune** sets the pad's pitch, up to two octaves either way.
  - **Decay** sets how long it rings.
  - **Level** sets its level in the kit.
  - **Tone** (page 2) makes it brighter to the right.
  - **Snap** sets the attack: the kick's click, the snare's wires, the
    hi-hats' noise against their metal, the clap's bursts, the rim's click,
    the cymbals' wash, the cowbell's first clank.
  - **Sweep** sets the fall in pitch at the start of a hit, the kick's and
    the toms' especially. On the other sounds, above the middle the hit falls
    in pitch, and below it rises.
  - **Drive** saturates the pad, clean at 0.
  - **Model** (page 3) chooses the pad's sound. *Kit* is the kit's own
    choice; the others are *Analog Drum* (a deep kick or tom), *Punch Drum*
    (a punchy, swept kick or tom), *Snare*, *Snap Snare*, *Hat*, *Ring Hat*,
    *Cymbal*, *Clap*, *Rim* and *Cowbell*. A pad given another sound plays
    that sound as Drums sets it up, so a cowbell on a tom's pad is a cowbell.
    The three hi-hat pads cut each other short whatever sound they play.
- The rest of page 3 is the whole kit's:
  - **Kit** chooses *Deep*, the long, round kit, or *Punch*, harder and
    shorter, with a swept kick, a crisper snare and ring-modulated hi-hats.
  - **Accent** sets how much velocity matters: at 0 every hit plays the
    same, at the right a soft hit is quiet and dull and a hard one loud and
    bright.
  - **Volume** sets the kit's level.
- Model and Kit reach the next hit; a hit that is ringing keeps the sound it
  started with. The other knobs move a ringing hit too.
- Pitch bend bends every pad.

{{screen drums Drums on pad 1, the kick of the Deep kit, just after it was struck.}}

!!! caution "The values shown after you change pads"
    As on Sophie, the screen cannot read a pad's settings back. When you
    choose another pad, the screen keeps showing the values you last set,
    and the first turn of a knob gives the new pad the value shown, plus
    that turn.

{{engine-table drums}}

## Acid Bass

{{status sim desktop planned}}

Acid Bass is a bass after the TB-303: one voice, a sawtooth or square wave
through a resonant filter swept by an envelope, with accents and slides.
It is the 303 of fm1-x0x, Charles Vestal's firmware for the FM-1, which
ports Robin Schmidt's Open303 with the Devilfish's longer slides and accent
decays and a RAT-style drive ([chapter 14](14-credits-and-licences.md)).

!!! note "In builds with the GPL switch on"
    fm1-x0x's code is published under the GNU General Public License, so
    Acid Bass is built in only while the firmware's GPL switch is on: in
    the simulator while we test, and in firmware for the person who builds
    it, never in a shared build ([chapter 14](14-credits-and-licences.md#licences)).

- **Accent.** A note played with a velocity of 100 or more is accented:
  louder, and with a harder sweep of the filter. Velocity does nothing
  else, as on the original, so play softer than 100 for a plain note.
- **Slide.** A key you play while holding another slides to its pitch
  instead of starting again: the 303's slide. Let go of the newer key while
  the older one is still down and the note slides back. Let go of the last
  key and the note ends.
- **Page 1, the filter.**
  - **Cutoff** sets how bright the note is at rest, 314 to 2,394 Hz.
  - **Resonance** adds the squelch: at the right the filter sings.
  - **Env Mod** sets how far each note opens the filter.
  - **Decay** sets how long that sweep takes to close, 200 ms to 2 s.
- **Page 2, the voice.**
  - **Accent** sets how hard an accented note hits.
  - **Wave** chooses *Saw* or *Square*.
  - **Tune** moves the pitch up to an octave either way.
  - **Volume** sets the level.
- **Page 3, drive and slides.**
  - **Drive** saturates the sound, clean at 0.
  - **Drive Type** chooses *Soft*, a warm overdrive, *RAT*, a gritty
    distortion pedal, or *Off*.
  - **Slide** sets how long a slide takes, 2 to 360 ms (60 ms, the
    original's, to begin with).
  - **Acc Decay** sets the filter sweep's decay on accented notes, 30 ms to
    3 s.
- Cutoff, Resonance, Env Mod, Tune, Volume, Drive and Slide move a note
  that sounds. Decay, Accent and Acc Decay reach the next note, a slide
  included. Wave and Drive Type wait for the next note that is not a slide,
  so they never click in the middle of one; while nothing sounds they
  change at once.
- Pitch bend bends the note, slides included.
- [[ALGORITHM]] steps through Wave.

Some settings to start from:

| Sound | Cutoff | Resonance | Env Mod | Decay | Accent | Drive |
| --- | --- | --- | --- | --- | --- | --- |
| Rubber bass | 500 Hz | 40 % | 30 % | 900 ms | 40 % | 0 |
| Squelch | 420 Hz | 92 % | 85 % | 300 ms | 90 % | 0 |
| Acid lead (Square) | 1,500 Hz | 70 % | 60 % | 630 ms | 60 % | 0 |
| Distorted acid | 700 Hz | 80 % | 100 % | 400 ms | 80 % | 75 %, RAT |

{{engine-table acid-bass gpl}}

## Crater Kit

{{status sim desktop planned}}

Crater Kit is a sixteen-pad drum kit after the TR-808: a booming kick, a
snare, three toms and three congas, a clap and maracas, a rim shot and
claves, a cowbell, closed and open hi-hats and a cymbal, every one the
machine's own sound. It is the 808 of fm1-x0x, Charles Vestal's firmware
for the FM-1, which ports 8W8 by athousanddetails: fifteen of the sounds
are models of the machine's circuits, built from its service notes and
published analyses, and the rim shot is sc808's
([chapter 14](14-credits-and-licences.md)). [Drums](#drums) stays beside
it: two kits of its own, any sound on any pad, in every build.

!!! note "In builds with the GPL switch on"
    fm1-x0x's code is published under the GNU General Public License, so
    Crater Kit is built in only while the firmware's GPL switch is on: in
    the simulator while we test, and in firmware for the person who builds
    it, never in a shared build ([chapter 14](14-credits-and-licences.md#licences)).

- Crater Kit plays MIDI notes 36 to 51, one sound each, and ignores other
  notes; on the FM-1's keys the sixteen white keys play them, from F3:

  | Note | Pad | Note | Pad | Note | Pad | Note | Pad |
  | --- | --- | --- | --- | --- | --- | --- | --- |
  | 36 | Kick | 40 | Claves | 44 | Maracas | 48 | High Tom |
  | 37 | Rim Shot | 41 | Low Tom | 45 | Mid Tom | 49 | Cymbal |
  | 38 | Snare | 42 | Closed HH | 46 | Open HH | 50 | Hi Conga |
  | 39 | Clap | 43 | Low Conga | 47 | Mid Conga | 51 | Cowbell |

- A hit rings for its sound's decay, whether or not you keep the key down.
  Struck again while it rings, a sound is struck again in its own circuit,
  as on the machine.
- As on the machine, each conga is its tom's circuit switched over: a low
  conga stops a ringing low tom, and the other way round. The rim shot and
  the claves, and the clap and the maracas, sound together freely.
- **Velocity** 88 is the 808's normal hit and 127 its accent, louder and
  harder; between them the hit grows, and below 88 it is quieter.
- **Pad** chooses which pad the pad's knobs edit: those on pages 1 and 2.
  [[ALGORITHM]] steps through the pads, and so does [[KNOB1]] on page 1.
  Each pad keeps its own settings, and starts as the 808 is set up: Tune
  at 0 and the other knobs in the middle, so until you change them the
  screen shows true values whichever pad you choose.
  - **Tune** sets the pad's pitch, up to an octave either way (the toms
    and congas go further than the machine's, which move two semitones).
  - **Decay** sets how long it rings: the kick's boom, the snare's ring,
    the hi-hats' and cymbal's length.
  - **Level** sets its level in the kit, up to twice the 808's.
  - **Tone** (page 2) shapes the kick (brighter to the right) and the
    snare (from its low shell to its high one); it does nothing on the
    other pads.
  - **Snap** sets the kick's attack click, the snare's snares and the
    maracas' attack; it does nothing on the other pads.
  - **Drive** saturates the pad, clean at 0.
  - **Dist** chooses how Drive saturates: *Diode* (the machine's own
    rounding), *Clip*, *Sat*, *Fuzz*, *Cubic* (a biased crunch), *Fold* (a
    wavefolder) or *Crush* (bits and rate falling together).
- Page 3 is the whole kit's:
  - **Accent** sets how far below an accent a softer hit sits: at 100 %,
    velocity 88 is the 808's normal hit; at 0 every hit is as loud as an
    accent.
  - **Choke** sets which hi-hat cuts which: *Off*, *Closed>Open* (a closed
    hi-hat cuts the open one, as on the machine), or *Both*.
  - **Volume** sets the kit's level.
- Tune, Decay, Tone, Snap, Accent and Choke reach the next hit; a hit that
  is ringing keeps what it started with. Level, Drive and Volume move a
  ringing hit too. Dist waits for the pad's next hit, so it never clicks in
  the middle of one.
- Pitch bend moves the hits you strike while you hold it, together with
  Tune up to an octave either way.

!!! caution "The values shown after you change pads"
    As on Drums, the screen cannot read a pad's settings back. When you
    choose another pad, the screen keeps showing the values you last set,
    and the first turn of a knob gives the new pad the value shown, plus
    that turn.

Some settings to start from:

| Sound | Pad | Tune | Decay | Tone | Snap | Drive, Dist |
| --- | --- | --- | --- | --- | --- | --- |
| Long boom kick | 1 Kick | −2 | 0.85 | 0.3 | 0.3 | 0 |
| Short punchy kick | 1 Kick | +3 | 0.3 | 0.7 | 0.9 | 0.3, Sat |
| Crisp snare | 3 Snare | +2 | 0.4 | 0.8 | 0.8 | 0 |
| Gritty cowbell | 16 Cowbell | 0 | 0.5 | – | – | 0.5, Fold |

{{engine-table crater gpl}}

## Test Sine

{{status sim desktop}}

Test Sine plays a plain sine wave for each note, at a level set by velocity,
with 5 ms fades in and out. It exists to test the firmware and the
simulator, and has a single control, **Volume**. When all twelve voices are
busy, it ignores further notes until one is free.

{{engine-table test-sine}}

{{engine-others sound}}
