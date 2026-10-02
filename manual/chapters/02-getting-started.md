# Getting started

There are two ways to use Lunar Modulator today: play it in a web browser, or
render its sounds with the desktop tools. This chapter sets up both, and ends
with what is still missing before it can run on an FM-1.

## The browser simulator

{{status sim}}

The simulator is a virtual FM-1 on a web page. The firmware's engines and
effects run in your browser, compiled to WebAssembly, behind a to-scale
drawing of the front panel. The screen in the drawing is the firmware's own
240 × 240 display, drawn by the same code that will draw the FM-1's.

### Opening it

1. Open the project's website in a desktop browser. The simulator is its
   front page; this manual is under *manual/*.
2. Click **Power on**. The browser needs this click before it may play
   sound.
3. Play the keys on the screen, or your computer keyboard (below).

The simulator starts with the Macro engine and the Plate reverb. Nothing is
installed and nothing is sent anywhere: the page loads only its own files.

!!! note "Which browsers"
    The simulator has been tested in Chromium-based browsers on a desktop.
    Firefox, Safari, phones and tablets have not been tested yet. On a narrow
    screen the panel keeps its size so the keys stay playable; drag the case
    sideways, or turn the phone to landscape.

### Playing it from the computer keyboard

| Computer keys | What they do |
| --- | --- |
| <kbd>A</kbd> <kbd>W</kbd> <kbd>S</kbd> <kbd>E</kbd> <kbd>D</kbd> <kbd>R</kbd> <kbd>F</kbd> <kbd>G</kbd> <kbd>Y</kbd> <kbd>H</kbd> <kbd>U</kbd> <kbd>J</kbd> <kbd>K</kbd> <kbd>O</kbd> <kbd>L</kbd> <kbd>P</kbd> <kbd>;</kbd> <kbd>[</kbd> <kbd>'</kbd> | The first 19 keys, F3 to B4, laid out like a piano over two rows |
| <kbd>Z</kbd> / <kbd>X</kbd> | [[OCT-]] / [[OCT+]] |
| <kbd>←</kbd> <kbd>→</kbd> | Turn [[SELECT]]: the page |
| <kbd>↑</kbd> <kbd>↓</kbd> | Turn [[PRESETS]]: the sound engine |
| <kbd>-</kbd> <kbd>=</kbd> | Turn [[ALGORITHM]]: the engine's model, or the effect in FX mode |
| <kbd>Esc</kbd> | Release every note |

With the mouse or a touch screen, press lower on a key to play louder, and
drag up or down on a knob (or scroll over it) to turn it.

### Playing it from a MIDI keyboard

Click **Connect MIDI input** and allow the browser to use MIDI. The simulator
plays notes with velocity, follows pitch bend over ±2 semitones, takes
CC 7 as volume and CC 123 as *all notes off*. It sends no MIDI. Chapter 8 has
the full chart.

## The desktop tools

{{status desktop}}

The desktop tools build the same engine, effect and sequencer code that the
firmware will use, and play it into a WAV file. They are the reference the
simulator is checked against, and the way to hear a change before it reaches
the simulator. You need a C and C++ compiler, `make` and Python 3.

```bash
git clone https://github.com/ip2k/lunar-modulator
cd lunar-modulator
make -C engines                       # builds engines/build/fm1-render
engines/build/fm1-render --list       # every engine, effect and parameter, as JSON
engines/build/fm1-render --engine macro --param Model=4 \
    --note 0:57:100:1 --note 0:60:100:1 --note 0:64:100:1 \
    --fx ensemble --fx plate --fx-param Mix=0.3 \
    --seconds 3 --out chord.wav       # an A minor chord through two effects
```

A note is written `start:key:velocity:length`, with times in seconds and keys
as MIDI note numbers (60 is middle C). Parameter names are the ones in this
manual's tables; a list parameter takes the number of its value.

!!! outline "To be written"
    - The rest of `fm1-render`'s options a musician uses: `--bend`,
      `--param-at` for turning a knob during a render, `--rate`, effect
      parameters per effect (`--fx-param` applies to the `--fx` before it).
    - Rendering a sequence: `--cmd` scripts and `--seq` sets (chapter 7),
      once the sequencer is part of the main build.
    - Listening tips: render at 44,118 Hz, the FM-1's rate; the output is
      16-bit stereo and passes through the same limiter as the firmware's.
    - Running the simulator from a checkout:
      `cd sim/web/www && python3 -m http.server 8000`, then
      `http://localhost:8000/` (a file opened directly cannot play audio).

## What runs on the FM-1 today

{{status planned}}

Nothing from this project. The FM-1 keeps whatever firmware it has: M-VAVE's
own, or a third-party release you installed yourself. Chapter 1 explains the
rule that holds Lunar Modulator back from the device, and chapter 10 the
recovery work that has to succeed first.

!!! outline "To be written"
    - The order of work before the device (the project's roadmap, phases 1
      to 6): read-only measurements, recovery with the dongle, first code on
      a JieLi development board, then the FM-1 itself, running from memory
      before anything is written to flash.
    - What a user will need when the device version exists: a USB-C cable, a
      computer with a browser, and nothing inside the case.
    - Where announcements will appear (the repository's releases page).
