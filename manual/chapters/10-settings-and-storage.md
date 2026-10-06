# Settings and storage

This chapter covers the global page, where Lunar Modulator shows what
applies to the whole instrument and sets the project key, and how projects,
sounds and sequencer sets are kept in files.

!!! warning "Nothing is stored on the FM-1"
    Lunar Modulator writes nothing to an FM-1's memory, and will not until
    the one rule is met ([chapter 1](01-welcome-and-safety.md#the-one-rule)).
    The sounds, patterns and settings your FM-1 holds now stay as they are.

## The global page

{{status sim planned}}

### To open the global page

Press [[GLO]]. Press [[GLO]] again, or [[HOME]], to leave it. It has two
pages: turn [[SELECT]] for *1/2 Globe*, what the instrument runs, and *2/2
Key*, the project key. The bottom bar names the page.

### What it shows

| Line | What it means |
| --- | --- |
| Rate | The sample rate the firmware runs at, such as 44118 Hz |
| Block | How many samples the firmware computes at a time: 64 |
| RAM | The share of the FM-1's free memory the sounds, effects, sequencer and modulation take, in percent, the same figure as the memory meter in the bottom bar (of which the sequencer takes 10 % and modulation 7 %, playing or not). It is red past 100 % ([chapter 6](06-effects.md#memory)) |
| Voices | How many notes the current sound's engine plays at once |
| M1, M2 | The effect in each master slot by its name, such as *Plate*, spelled out where the line has room (*Compressor* for Comp), or `--` for an empty slot |
| Octave | The keyboard's octave, from −3 to +3 ([chapter 4](04-playing.md#octave-and-transpose)) |
| Transpose | The transpose in semitones, from −12 to +12 |

On *Globe* [[KNOB1]] and [[KNOB2]] set the project key, and the page turns
to *Key* to show it; [[KNOB3]] and [[KNOB4]] change nothing.

### The project key

{{status sim desktop}}

One key for the whole project: a root, C to B, and a scale.

| Knob | What it sets |
| --- | --- |
| [[KNOB1]] | The root: C, C#, D and so on to B |
| [[KNOB2]] | The scale: Major, Minor, Dorian, Phrygian, Lydian, Mixolydian, Locrian or Chromatic |

Each knob shows its list while you turn it, the chosen entry marked. The
line under the top bar says the key in words, such as *D Minor*. It starts
at C Major.

- **What it is for.** Every MIDI effect is told the key. The arpeggiator does
  not use it; the scale and chord effects planned next will. The sound
  engines and the sequencer play the same in any key.
- **Where it is kept.** The key belongs to the sequencer's set, beside the
  tempo and the swing ([what a set keeps](#what-a-set-keeps)). Loading a set
  brings its key; a set from Movy, or one saved in C Major, has none and
  loads in C Major. A project file also shows the key near its top, in
  `session`, for anyone reading the file; that copy is written from the
  set's and is never loaded, so editing it changes nothing.
- **In the desktop tools.** The sequencer's `key` command sets it in a
  script, such as `key 2 1` for D Minor ([chapter 7](07-sequencer.md)).

!!! tip "Will it fit on the FM-1?"
    The simulator refuses any sound or effect that would take the figure
    past 100 %, so whatever it plays would fit on the FM-1. To
    make room, choose a smaller engine or effect, or empty a sound or a slot
    ([chapter 6](06-effects.md#memory)).

### Settings

{{status sim desktop}}

Four settings belong to the instrument, not to a project. They are kept in a
settings file of their own, never in a project, so loading a project leaves
them as they are.

| Setting | What it does |
| --- | --- |
| Metronome | The click while the sequencer plays ([chapter 7](07-sequencer.md)) |
| Full velocity | Every step entered at full velocity ([[SEL]] + key 10 in SEQ mode) |
| Count-in click | Whether the count-in clicks (kept for the stage that adds it) |
| MIDI IN channel | The channel MIDI IN listens on, or every channel (kept for the stage that adds it) |

MASTER is not a setting: the page remembers its position in the browser.

## Projects, sounds and other files

{{status sim desktop}}

Everything the simulator holds can be saved to a file and loaded back. A
saved file loaded again gives the same state, and saving it once more gives
the same file, byte for byte.

| Kind | Holds | Loads |
| --- | --- | --- |
| **Project** (`first-orbit.lunar`) | All four sounds with every parameter, every pad of a drum kit, their levels, inserts and arpeggiators; the master effects; FM6's user voices; the modulation rack and its cables; the sequencer's set with its song and key; the current sound, octave and transpose; and the page you were on | In place of everything |
| **Sound** (`deep-bass.sound.lunar`) | One sound, its inserts and arpeggiator, its level, the FM6 voice it plays, and the modulation that reaches only it | Into the sound you choose |
| **Effects** (`space-verbs.fx.lunar`) | One or two effects and their modulation | Into the master slots, or a sound's inserts |
| **Mod rack** (`wobble.mods.lunar`) | The rack and its cables | In place of the rack |
| **Clip** (`bass-a.clip.lunar`) | One clip, with its locks | Into a track and slot you choose |
| **Set** (`.movy1`) | The sequencer's set, as Movy writes it | In place of the set |
| **Settings** | The four settings above | Over the settings |

Files are text you can read, keep under version control or share. Each
names its engines and parameters, so a file stays readable as the
firmware grows.

### What happens when you load

- **A project** replaces everything. The simulator starts afresh and builds
  the project's state.
- **Every other kind** goes into its place and leaves the rest alone. A
  sound loaded into Sound 2 while the song plays changes Sound 2 and nothing
  else.
- **A sound's modulation** goes to free places in the rack and the matrix.
  Its FM6 voice reuses the same voice if the bank has it, or the first
  empty user slot.
- **The screen** shows *LOADED*, the file's name and the memory figure for a
  second, and the page says what came in: *Loaded “First orbit”: 4 sounds,
  5 effects, … It takes 69% of the FM-1's RAM.*
- **What the load replaced** stays in the browser's Recent list as *Before
  First orbit*, and **Undo load** under the message puts it back.

### When a file does not load

A file that cannot load changes nothing. The page says why, under the panel,
in the refusal colour (*“Deep space bass” was not loaded. Needs 117% of the
FM-1's RAM.*), and offers the way round when there is one, such as **Load
without Rings**. In the desktop tools the screen shows *NOT LOADED* and the
short form:

| It says | Why | What you can do |
| --- | --- | --- |
| *Needs 121% RAM* | The file would take more than the FM-1's memory. Every file is measured as the FM-1 would run it, whatever your browser's rate | Load a lighter file. This refusal has no way round it |
| *Uses Rings* | The file uses an engine this build does not have, or one only the GPL build has | Load it without that engine: its sound is left empty |
| *Rack is full* or *Matrix is full* | A sound's modulation has no room | Load it without its modulation, or free a place in the rack |
| *FM6 bank is full* | The sound's FM6 voice has no free user slot | Load it without its voice |
| *Slot holds a clip* | The clip's slot is not empty | Load it again and replace the clip |
| *Macro at 96 kHz* | The engine cannot run at your browser's sample rate | Use a browser or device at 44.1 or 48 kHz |
| *Not a Lunar file*, *Newer format*, *Bad file*, *File too big* | The file is not one this simulator reads | Check the file, or use a newer simulator |

### Tracks without a route

A project's set loads with its routes as saved: a track with no route plays
nothing in the simulator. A set from Movy, where no track is routed, gets
the simulator's start rule: track 1 plays Sound 1.

### SAVE

In the simulator, [[SAVE]] on the panel and the page's buttons under it do
the saving and loading:

| On the page | What it does |
| --- | --- |
| **Open…**, or files dropped on the page | Loads `.lunar` files, a `.movy1` set or `.syx` DX7 patches, several at once. A sound, effects or a clip asks where it goes: *Load sound “Deep space bass” into Sound 2* |
| **Save…** with the list beside it | Downloads the project, the current sound, its effects, the master effects or the mod rack as a `.lunar` file, named with its kind in the middle (`first-orbit-s2.sound.lunar`), or the set as a `.movy1` file for Movy |
| [[SAVE]] on the panel | Keeps the whole project in this browser; the screen shows *SAVED*. **Saved in this browser** lists it, to load or download again |
| **Copy link** | Copies a link that holds the whole project, for anyone to open in their own browser. A link holds up to 32 KiB; a project too big for one says so, and you share the file instead |

- **Autosave.** The page keeps your project in the browser as you work, a
  few seconds after each change and when you leave the page, and the next
  visit, or the next [[POWER]] press, starts where you left off. The message
  then offers **Start fresh**, which puts the start sounds and the demo
  pattern back (your work stays in Recent).
- **Recent** keeps the last five states a load replaced.
- **Links.** A link from the guide or a page of this manual can open a file
  straight into the simulator, such as
  `?load=examples/first-orbit.lunar`. A card names the file and what it
  replaces before you press **Power on and load**; your work goes to Recent
  first. Only files on the simulator's own site, under its `examples/`,
  `guide/` and `manual/` folders, load this way.
- **The examples** under *Saved in this browser, Recent and examples* are
  the guide's files (MIT): a project, a sound, effects, a mod rack and a
  clip.
- **The file formats' schemas** are published with the simulator, at
  `schema/1/` on its site, for editors that check `.lunar` files.

Files are read and written in your browser; nothing is uploaded, and
nothing is ever sent to an FM-1. MASTER is a preference of the page, not
part of a project.

### In the desktop tools

```bash
sim/web/build/native/fm1-sim-render --start --save project:mine.lunar --seconds 0
sim/web/build/native/fm1-sim-render --load mine.lunar --load s2:deep-bass.sound.lunar --save project:mine2.lunar
engines/build/fm1-state check mine.lunar           # whether a file fits, and what it holds
```

On the FM-1, saving sounds and projects to its flash memory waits for the
one rule ([chapter 11](11-updating-and-recovery.md#the-one-rule-again)).

## Sequencer sets

{{status desktop planned}}

A set is everything the sequencer holds ([chapter 7](07-sequencer.md#how-a-pattern-is-organised)).

### What a set keeps

| Kept | Not kept |
| --- | --- |
| The tempo, the swing, the external-clock `link` setting ([chapter 9](09-midi.md#following-an-external-clock)) and the project key | Whether the sequencer was playing |
| The song | The playhead's position |
| Each track's chosen clip, its mute, its muted or soloed drum notes, and its routing | How many times each clip has looped, which conditions count |
| Each track's lock lanes, with their parameters and base values | The random sequence behind probability |
| Every clip: its length, loop window, speed, transpose and quantise | Which tracks are drum tracks |
| Every note, lock, condition and probability | |
| The default quantise for new clips, the song's end mode and its scene names | |

### In the desktop tools

The desktop tools save and load sets as text in Movy's `movy1` format, a
plain text file you can read, keep under version control or share:

```bash
engines/build/fm1-seq --cmd pattern.txt --export pattern.movy1     # save the set a script builds
engines/build/fm1-seq --seq pattern.movy1 --export copy.movy1      # load a set and save it again
engines/build/fm1-render --engine macro --seq pattern.movy1 --seconds 8 --out set.wav
```

Movy reads these files too, and Lunar Modulator reads Movy's. The
differences:

- Lunar Modulator adds a line for each track you route away from its
  default, and one for the project key unless it is C Major, which Movy
  ignores.
- It keeps what it loads within its own ranges, clip speeds of 1/8X to 4X
  among them.
- It leaves out what does not fit its memory: notes and locks beyond its
  pools, and tracks beyond the number it was started with.

### On the FM-1

The FM-1 build is planned to keep sets in three stages:

1. **In memory.** The set lives in the instrument's working memory and is
   lost when you switch off.
2. **On a computer.** You save a set to a computer and load it back over
   USB-MIDI, as system exclusive messages carrying the same `movy1` text.
   A full set is about 90 KB and is sent in parts.
3. **In flash memory, last.** Sets will be written to an area of their own,
   apart from the areas M-VAVE's firmware uses, only when you save. Each set
   is kept twice, so a power cut while saving cannot lose both copies.

The third stage waits for the one rule
([chapter 11](11-updating-and-recovery.md#the-one-rule-again)).

## Backing up

{{status planned}}

### Your work

Planned: one export that saves every sound and every set to a computer, and
an import that brings them back. Until sounds and sets can be stored on the
FM-1 itself, saving a set to a computer is the backup.

### Your FM-1's own sounds and patterns

The patches, patterns and settings that M-VAVE's firmware keeps in the FM-1's
flash memory stay in their own areas. Lunar Modulator is planned never to
write there.

- Reading them would need their formats, which only a complete copy of the
  FM-1's memory can show.
- That copy is exactly what the one rule asks for first: a full read-out of
  the FM-1's memory, kept safe, before anything is written
  ([chapter 11](11-updating-and-recovery.md#the-recovery-dongle)).

!!! tip "Keep your own copies"
    If you use a patch editor or librarian with M-VAVE's firmware, keep your
    banks on your computer as well. The FM-1 accepts voices and banks over
    MIDI but does not send its stored banks back.
