# Getting started

There are two ways to use Lunar Modulator today: play it in a web browser, or
render its sounds with the desktop tools. This chapter sets up both, takes you
through a first session, and ends with what still has to happen before
Lunar Modulator can run on an FM-1.

## The browser simulator

{{status sim}}

The simulator is a virtual FM-1 on a web page. The firmware's engines and
effects run inside your browser, behind a to-scale drawing of the front
panel. The screen in the drawing is the firmware's own 240 × 240 display,
drawn by the code that is meant to draw the FM-1's.

### What you need

- A desktop or laptop computer with a current web browser. The simulator
  needs WebAssembly and the Web Audio API's AudioWorklet, and the page must
  come from an `https://` address or from your own computer.
- Headphones or speakers.
- Optionally, a MIDI keyboard connected to the computer, and a browser with
  Web MIDI.

The simulator is tested in Chromium, the engine behind Chrome and Edge.
Firefox and WebKit automated checks are also run; native Safari listening,
phones and tablets with real touch screens, and real MIDI hardware have not
been fully verified.

Nothing is installed. The page loads only its own files, from its own
website, and sends nothing anywhere.

### Turning it on

1. Open the project's website,
   [ip2k.github.io/lunar-modulator](https://ip2k.github.io/lunar-modulator/).
   The simulator is its front page; this manual is in its *manual* section.
2. Click **Power on**. Browsers allow a page to make sound only after a
   click, so the simulator waits for this one. Clicking the [[POWER]] switch
   drawn on the top edge of the case does the same.
3. Play the keys.

The simulator starts with the Macro engine as Sound 1 (Sounds 2 to 4
empty), the Plate reverb in the first master effect slot, the second slot
empty, a one-bar demo pattern on sequencer track 1, the modulation rack's
default modules, and [[MASTER]] at three quarters. Press [[PLAY/STOP]], or
<kbd>Space</kbd>, to hear the pattern. The status line under the controls
reports the sample rate, the block size, the delay your computer adds to
the output, how much of the FM-1's memory the sounds and effects take, in
percent, and the sequencer's tempo and whether it plays.

To stop, click **Power off** or the [[POWER]] switch. The simulator keeps
nothing: it starts from the same settings every time, and DX7 voices you
loaded into FM6 ([chapter 5](05-sound-engines.md#loading-voices-from-sysex))
go with the power.

!!! note "When an engine refuses to start"
    The simulator asks your browser for 44,100 samples a second, close to
    the 44,118 reported for the FM-1. If the browser insists on a faster rate, such
    as 48,000, the four engines built from Plaits' code (Macro, Macro Heavy,
    Six-Op FM and Drums) cannot run. The simulator then starts with Shapes,
    steps over those four when you turn [[PRESETS]], and says why on its
    screen and in the status line. The other engines, FM6 among them, run
    at any of these rates. Set your computer's audio output to 44.1 kHz and
    reload the page to get them back.

### Playing with the mouse or a touch screen

- **Keys.** Click or touch a key to play it, and hold it for as long as the
  note should last. Where you press sets how hard the note is played: near
  the top of a key for the softest note (velocity 30), at the bottom edge for
  the loudest (127).
- **Knobs.** Drag up to turn a knob clockwise and down to turn it
  anticlockwise, or scroll over it with the mouse wheel or trackpad. Each
  6 pixels of dragging is one step of an encoder.
- **Buttons.** Click or touch.

On a narrow screen the panel keeps its size, so that the keys stay large
enough to play, and scrolls sideways in its own box: drag the case, not a
control, to see the rest, or turn the phone to landscape. The screen then
also appears enlarged below the panel.

### Playing from the computer keyboard

The letter keys play the first 19 keys of the panel, F3 to B4, laid out like
a piano: the middle row of letters plays the white keys, and the row above it
the black keys. Notes from the computer keyboard play at velocity 100.

| Computer keys | What they do |
| --- | --- |
| <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> <kbd>F</kbd> <kbd>G</kbd> <kbd>H</kbd> <kbd>J</kbd> <kbd>K</kbd> <kbd>L</kbd> <kbd>;</kbd> <kbd>&#39;</kbd> | The white keys F3, G3, A3, B3, C4, D4, E4, F4, G4, A4 and B4 |
| <kbd>W</kbd> <kbd>E</kbd> <kbd>R</kbd> <kbd>Y</kbd> <kbd>U</kbd> <kbd>O</kbd> <kbd>P</kbd> <kbd>[</kbd> | The black keys F♯3, G♯3, A♯3, C♯4, D♯4, F♯4, G♯4 and A♯4 |
| <kbd>Z</kbd> / <kbd>X</kbd> | [[OCT-]] / [[OCT+]] |
| <kbd>←</kbd> <kbd>→</kbd> | Turn [[SELECT]]: the page, or in FX mode the effect slot and its pages |
| <kbd>↑</kbd> <kbd>↓</kbd> | Turn [[PRESETS]]: the sound engine |
| <kbd>-</kbd> <kbd>=</kbd> | Turn [[ALGORITHM]]: the engine's main list, or in FX mode the effect in the slot |
| <kbd>Space</kbd> | [[PLAY/STOP]]: starts and stops the sequencer |
| <kbd>1</kbd> to <kbd>8</kbd>, <kbd>C</kbd> <kbd>V</kbd> <kbd>B</kbd> <kbd>N</kbd> <kbd>M</kbd> <kbd>,</kbd> <kbd>.</kbd> <kbd>/</kbd> | In SEQ mode, white keys 1 to 16: the sequencer's steps ([chapter 7](07-sequencer.md)) |
| <kbd>Shift</kbd> | In SEQ mode, holds [[SEL]], the sequencer's SHIFT |
| <kbd>Tab</kbd> | Move between the knobs and buttons of the drawing. With a knob chosen, the arrow keys turn it; with a button chosen, <kbd>Enter</kbd> or <kbd>Space</kbd> presses it |
| <kbd>Esc</kbd> | Release every note |

[[KNOB1]] to [[KNOB4]] and [[MASTER]] have no letter of their own: choose
them with <kbd>Tab</kbd>, or use the mouse.

!!! tip "Keys that seem stuck"
    If you switch to another window or tab while holding a key, the simulator
    lets go of everything you were holding. If a note still hangs, press
    <kbd>Esc</kbd>.

### Playing from a MIDI keyboard

1. Connect the keyboard to the computer.
2. Click **Connect MIDI input** under the panel, and allow the browser to use
   MIDI devices when it asks.
3. The button now names the keyboards it found. Play.

The simulator listens on every MIDI channel. It plays notes with their
velocity, bends sounding notes by up to two semitones either way, follows
control change 7 as [[MASTER]] and control change 123 as *all notes off*, and
ignores everything else. It sends no MIDI. [Chapter 9](09-midi.md) has the
full list.

### The controls under the panel

| Control | What it does |
| --- | --- |
| **Sound (PRESETS)** | Chooses the current sound's engine directly, as turning [[PRESETS]] does. The label names the current sound, such as *Sound 2 (PRESETS)*; Sounds 2 to 4 can be *(none)* |
| **Effect 1**, **Effect 2** | Choose the effect in each master slot, or *(none)* to empty it |
| **Connect MIDI input** | Asks the browser for your MIDI keyboards (above) |
| **Open…**, **Save…**, **Copy link** | Load and save projects, sounds and other files, and share a project as a link ([chapter 10](10-settings-and-storage.md#save)). Files can also be dropped on the page |
| **Screen ×2** | Shows a second, larger copy of the screen below the panel. On by default in a narrow window |
| **Power off** | Stops the sound |

A choice in one of the lists hands the computer keyboard straight back to the
instrument, so the next letter you type plays a note.

The page remembers your project in the browser as you work: come back later,
press **Power on**, and it is as you left it. To start from an example, open
*Saved in this browser, Recent and examples* under the status line and load
*First orbit*, the guide's first song.

### The advanced editor

The switch at the top of the page, **Panel**, **Workbench** and **Editor**,
opens the advanced editor beside the panel or in its place. It shows every
value of a sound at once, grouped by the panel's own pages, and changes the
same simulator the panel plays: turn a knob on the panel and its row lights
in the editor; move a slider in the editor and the panel opens that page.
It also draws the signal flow, the modulation rack and its cables (as a table
or as a patch bay), and says what each choice would cost in memory before you
make it. [Chapter 15](15-the-advanced-editor.md) describes it.

### Running the simulator from your own copy

To run the simulator without the website, for example from a copy of the
project you have changed, serve its folder from your own computer. You need
Git and Python 3.9 or newer.

```bash
git clone https://github.com/ip2k/lunar-modulator
cd lunar-modulator/sim/web/www
python3 -m http.server 8000
```

Then open `http://localhost:8000/` in the browser. Opening `index.html`
straight from the disk does not work: browsers allow the simulator's audio
only on a web address.

## A first session

{{status sim}}

This short tour plays notes from the computer keyboard and turns the four
parameter knobs and the buttons with the mouse. Start with the volume low.

1. Click **Power on**.
2. Hold <kbd>A</kbd>, <kbd>D</kbd> and <kbd>G</kbd> together: an F major
   chord on the Macro engine, through the Plate reverb. Each key's light
   comes on while you hold it.
3. Press <kbd>=</kbd> four times. [[ALGORITHM]] steps Macro's Model from
   VA+Filter to VA Pair, and the screen shows the new model for a moment.
4. Hold the chord again and drag [[KNOB3]] slowly upwards. [[KNOB3]] is
   Timbre on the first page: watch its bar move on the screen as the sound
   changes.
5. Press <kbd>→</kbd>. [[SELECT]] turns to the second page: Decay, Colour and
   Volume. Drag [[KNOB1]] up to raise Decay, and the notes ring on after you
   let go of the keys.
6. Click [[FX]]. The screen shows the effect chain, with M1, the first
   master slot, chosen: Plate is there, and [[KNOB1]] is now Plate's Mix.
7. Press <kbd>→</kbd> twice, past Plate's second page (Freeze), to move to
   M2, the second master slot, empty, then <kbd>=</kbd> twice: Ensemble, a
   chorus, fills it.
8. To put Ensemble before Plate, click [[SEL]], press <kbd>←</kbd>, and click
   [[SEL]] again.
9. Click [[HOME]] to return to the sound, then press <kbd>↑</kbd> to turn
   [[PRESETS]] to the next engine, Shapes.
10. Press <kbd>Space</kbd>: the demo pattern plays on Shapes. Click [[SEQ]]
    to see it: the white keys' lights follow the steps, and a tap on a white
    key adds or removes a note. Press <kbd>Space</kbd> again to stop.

[Chapter 3](03-panel-tour.md) describes every control, chapters
[5](05-sound-engines.md) and [6](06-effects.md) every engine and effect,
[chapter 7](07-sequencer.md) the sequencer and [chapter 8](08-modulation.md)
modulation.

!!! note "Changing the engine starts it afresh"
    Each time you choose a sound engine or an effect, it starts with its
    default settings. The simulator does not keep sounds yet; saving them is
    planned ([chapter 10](10-settings-and-storage.md)).

## The desktop tools

{{status desktop}}

The desktop tools build the same engine, effect and sequencer code that the
firmware will use, and play it into a WAV file. They are the reference the
simulator is checked against, and the way to hear a change before it reaches
the simulator.

### Building them

You need Git, `make` and a C and C++ compiler that supports C++11: on macOS
the Xcode command-line tools, on Linux a package such as `build-essential`.

```bash
git clone https://github.com/ip2k/lunar-modulator
cd lunar-modulator
make -C engines                       # builds engines/build/fm1-render
engines/build/fm1-render --list       # every engine, effect and parameter, as JSON
```

### Rendering a sound

`fm1-render` plays a list of notes through one sound engine and any number of
effects, then through the same limiter as the firmware, and writes the result
as a 16-bit stereo WAV file at 44,118 samples a second.

```bash
engines/build/fm1-render --engine macro --param Model=4 \
    --note 0:57:100:1 --note 0:60:100:1 --note 0:64:100:1 \
    --fx ensemble --fx plate --fx-param Mix=0.3 \
    --seconds 3 --out chord.wav
```

This plays an A minor chord on Macro's VA Pair model, through Ensemble and
then Plate, with Plate's Mix at 0.3.

- **A note** is written `start:key:velocity:length`, with the start and length
  in seconds, the key as a MIDI note number (60 is middle C) and the velocity
  from 1 to 127.
- **Parameter names** are the ones in this manual's tables, in any mix of
  capitals. A list parameter takes the number of its value, not its name:
  `Model=4` is VA Pair.
- **Effects** run in the order you give them, and each `--fx-param` sets a
  parameter of the `--fx` just before it.
- **Events** take effect at the start of the next block of 64 samples, every
  1.45 ms.

After each render the tool prints one line of figures, among them the peak
level before and after the limiter.

More examples:

```bash
# FM6's tine electric piano, a C major chord, through Ensemble and Plate
engines/build/fm1-render --engine dx7 --param Patch=0 \
    --note 0:60:90:1 --note 0:64:90:1 --note 0:67:90:1 \
    --fx ensemble --fx plate --seconds 3 --out tines.wav

# FM6 playing the eighth voice of a 32-voice bank of your own, a .syx file
engines/build/fm1-render --engine dx7 --sysex mybank.syx --param Patch=39 \
    --note 0:48:100:2 --seconds 3 --out mine.wav

# Six-Op FM's first electric piano, a C major chord, through Ensemble and Plate
engines/build/fm1-render --engine sixop --param Patch=32 \
    --note 0:60:90:1 --note 0:64:90:1 --note 0:67:90:1 \
    --fx ensemble --fx plate --seconds 3 --out piano.wav

# Macro's 2-op FM model, with Timbre turned up after one second and down after two
engines/build/fm1-render --engine macro --param Model=6 --note 0:45:100:3 \
    --param-at 1:Timbre=0.9 --param-at 2:Timbre=0.1 --seconds 4 --out fm.wav

# A low note through Filter's diode ladder, its cutoff opened after half a second
engines/build/fm1-render --engine macro --param Model=0 --note 0:36:110:2 \
    --fx filter --fx-param Type=2 --fx-param Cutoff=300 --fx-param Resonance=0.8 \
    --fx-param-at 0.5:1:Cutoff=1500 --seconds 2.5 --out acid.wav

# Sophie's kick, closed hi-hat and snare, through PSX Verb's Room
engines/build/fm1-render --engine sw-sophie \
    --note 0:36:110:0.5 --note 0.25:42:90:0.2 --note 0.5:38:100:0.2 \
    --fx sw-psxverb --fx-param Model=0 --seconds 2 --out kit.wav
```

### Options

| Option | What it does |
| --- | --- |
| `--list` | Prints every engine and effect with its parameters, ranges, defaults and value names, as JSON |
| `--engine ID` | The sound engine: `macro`, `macro-heavy`, `sixop`, `dx7` (FM6), `shapes`, `sw-sophie`, `drums` or `test-sine`. Each engine's identifier is under its table in chapter 5 |
| `--param NAME=VALUE` | Sets one of the engine's parameters before the first note |
| `--note T:KEY:VEL:LEN` | Plays a note (above) |
| `--param-at T:NAME=VALUE` | Sets one of the engine's parameters at time *T*, in seconds |
| `--bend T:SEMITONES` | Bends every note from time *T*, by up to 48 semitones either way. Sophie has no pitch bend and refuses it |
| `--fx ID` | Adds an effect to the chain: `plate`, `ensemble`, `diffuse`, `sw-psxverb`, `crush`, `fold`, `drive`, `echo`, `filter`, `comb`, `comp`, `limit`, `djfilter`, `tilt`, `sat`, `isolator`, `eq`, `room`, `hall`, `gate`, `test-gain` or `test-ext`. With the multi-sound options below, the first two are the master effects |
| `--fx-param NAME=VALUE` | Sets a parameter of the effect before it |
| `--fx-param-at T:K:NAME=VALUE` | Sets a parameter of the *K*-th effect (the first `--fx` is 1) at time *T*, in seconds |
| `--seconds S` | The length of the file, 2 seconds unless you say otherwise |
| `--rate HZ` | The sample rate, 44,118 unless you say otherwise. Macro, Macro Heavy, Six-Op FM and Drums refuse rates above 47,872; Shapes runs from 24,000 to 96,000; FM6 from 16,385 to 384,000 |
| `--sysex FILE.syx` | Loads DX7 voices from a SysEx file into FM6's user slots (`--engine dx7`): a bank fills User 1 to 32, single voices go to User 1, 2 and on, in the order given ([chapter 5](05-sound-engines.md#fm6)) |
| `--frames N` | The block size, 64 unless you say otherwise |
| `--tempo BPM` | The tempo the effects hear when no sequencer plays, from 20 to 300; 120 unless you say otherwise. Of the effects, only Test Ext listens to it so far |
| `--out FILE.wav` | Where to write the sound |
| `--sound K:ID`, `--insert K:ID`, `--level K:PCT`, `--sound-note K:T:KEY:VEL:LEN`, `--slots` | Several sounds at once, as in the simulator: sound *K* (1 to 3; `--engine` is 0), an insert effect on sound *K*, its level into the mix, a note on it; `--slots` routes the sequencer's tracks to the sounds ([chapter 5](05-sound-engines.md#four-sounds-at-once)) |
| `--mod FILE` | Modulation from a file ([chapter 8](08-modulation.md#modulation-on-the-desktop)) |
| `--cmd`, `--seq`, `--log-events`, `--route`, `--tracks` | Play the sequencer (chapter 7) |

An unknown engine or parameter name, or a rate an engine cannot run at, stops
the tool with a message saying so.

### Rendering a sequence

`fm1-render` can also play the sequencer: a script of sequencer commands
(`--cmd`) or a saved set (`--seq`) drives the engine, note for note and lock
for lock. [Chapter 7](07-sequencer.md) describes the sequencer and its
scripts.

## What runs on the FM-1 today

{{status planned}}

Nothing from this project. The FM-1 keeps whatever firmware it has: M-VAVE's
own, or a third-party firmware you chose to install yourself.
[Chapter 1](01-welcome-and-safety.md#the-one-rule) explains the current
staged recovery safeguards. The device roadmap remains planned: no Lunar
application has been installed or run on an FM-1.

### The road to the device

Each step below has to succeed before the next one starts:

1. **Recovery evidence.** Continue from the verified bounded sector
   program/restore and matching full-flash backups. Full-image rewrite and
   recovery from a nonbooting application remain untested; see
   [chapter 11](11-updating-and-recovery.md).
2. **A development board.** Run Lunar Modulator's code on a board with the
   same family of processor, and show that it gives the same results as the
   desktop tools and the simulator.
3. **The FM-1, from memory.** Run Lunar Modulator on the FM-1 without
   writing anything to its permanent memory.
4. **The FM-1, installed.** Install it with a way back built in: a key held
   at power-up that returns the unit to its update mode, and a copy of the
   original firmware kept.
5. **For everyone.** Publish an installer that works over USB and can also
   put the original firmware back.

### What you will need

When a device version exists, the plan is that installing it will need a
computer and the FM-1's USB socket, and nothing inside the case
([chapter 11](11-updating-and-recovery.md#how-it-will-be-installed)). Until
then, keep playing your FM-1 with the firmware it has, and play Lunar
Modulator in the simulator.
