# Troubleshooting

Find the symptom, then try the remedies in order. The simulator and the
desktop tools both say what went wrong in plain words; the tables quote
those messages so you can search for them.

## The simulator

### Sound and starting up

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| No sound after **Power on** | The browser blocked audio, or the computer's output is muted or set to another device | Click **Power on** again; check the computer's volume and output device; turn [[MASTER]] up |
| **Power on** does nothing, and the status line still says *Powered off* | The page was opened as a file, so its scripts did not load | Open the project's website, or serve your checkout: `cd sim/web/www && python3 -m http.server 8000`, then open `http://localhost:8000/` |
| The status line says *This page needs a secure context for its audio* | The page was opened over plain http from another computer's address | Open it over https, as the project's website serves it, or from `http://localhost` on the computer that serves it |
| The status line says *Could not start audio* | One of the simulator's files did not load | Reload the page; check that the whole folder is served, `fm1.wasm` included |
| The status line says *This browser has no AudioWorklet* | The browser is too old, or lacks the audio feature the simulator needs | Use a current Chromium-based browser such as Chrome or Edge |
| The status line says *The firmware did not start* | The firmware's code did not load in this browser | Reload the page; try a current Chromium-based browser |
| Crackles or dropouts | The computer is busy, or a phone is too slow | Close other tabs and programs; on a phone, try a computer |
| The status line says that Macro *was refused: it does not run at 48,000 Hz*, and the simulator started with another sound | The browser would not run audio at 44,118 or 44,100 Hz, and Macro, Macro Heavy and Six-Op FM need 47,872 Hz or less | Set the computer's audio output to 44.1 kHz and reload. Shapes, Sophie and Test Sine work at 48 kHz too |

### Playing

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| The screen says an engine *refuses* a rate, and the previous one comes back | As above: the audio runs faster than 47,872 Hz | Set the output to 44.1 kHz and reload |
| Sophie is silent | Sophie plays only MIDI notes 36 to 51 | Press [[OCT-]] twice ([chapter 5](05-sound-engines.md#sophie)) |
| A note keeps sounding | A key release was lost, for example when the window lost focus | Press <kbd>Esc</kbd>, or send CC 123 from a MIDI keyboard |
| The computer keys play nothing | A dropdown under the panel has the keyboard's focus, a modifier key such as Ctrl, Alt or Cmd is down, or the page is not in front | Click the panel's case once, release the modifier keys, then play |
| The computer keys play the wrong notes | The keyboard layout is not QWERTY | The keys work by position: play the keys that sit where a QWERTY keyboard has <kbd>A</kbd> to <kbd>L</kbd> and the keys after it ([chapter 2](02-getting-started.md#the-browser-simulator)) |
| Every note from the computer keys is equally loud | Computer keys always play at velocity 100 | Click lower on a key on the panel to play louder, or use a MIDI keyboard |
| The keys play the wrong octave | The octave or transpose is not at zero | Press [[OCT-]] and [[OCT+]] together to reset both |
| Only part of the panel shows on a phone | The panel keeps its size so the keys stay playable | Drag the case sideways, or turn the phone to landscape |
| [[ENV]], [[SAVE]], [[SEQ]] and others say *not in the simulator yet* | Those buttons are planned, not built | See [chapter 3](03-panel-tour.md#buttons) for the buttons that work |
| [[SEL]] says *works in FX mode* | [[SEL]] moves effect slots and works only on the effect page | Press [[FX]] first ([chapter 6](06-effects.md)) |
| The effect page says *Empty slot: turn ALGORITHM* | That slot holds no effect | Turn [[ALGORITHM]] to choose one |

### MIDI

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| The status line says *This browser has no Web MIDI* | The browser does not offer MIDI to web pages | Use a Chromium-based browser for MIDI, or play the panel and the computer keys |
| The status line says *MIDI was not allowed* | The browser's permission was refused | Allow MIDI for the page in the browser's site settings, reload, and click **Connect MIDI input** again |
| The button reads *MIDI: no inputs* | No keyboard is connected, or another program holds it | Connect the keyboard; the simulator picks it up by itself. Close other programs that use it |
| The keyboard plays, but the sustain pedal and modulation wheel do nothing | The simulator ignores those messages | See [chapter 8](08-midi.md#in-the-simulator) for what it receives |

!!! note "Which browsers"
    The simulator has been tested in Chromium-based browsers on a desktop.
    Firefox, Safari, phones, tablets and real MIDI hardware have not been
    tested yet, so problems there may have causes this chapter does not
    list.

## The desktop tools

### Building and rendering

| Symptom or message | Likely cause | What to do |
| --- | --- | --- |
| `make -C engines` stops with compiler errors | No C and C++ compiler, or one without C++11 | On macOS install the command-line tools (`xcode-select --install`); on Linux, your distribution's build tools package |
| *macro refused this host (rate 48000 Hz, 64 frames)* | Macro, Macro Heavy and Six-Op FM refuse rates above 47,872 Hz | Leave out `--rate` (the default is 44,118 Hz) or choose 44100 |
| *unknown parameter for macro: Timbr* | The name is misspelt, or belongs to another engine | Use the names in [chapter 5](05-sound-engines.md)'s tables; case does not matter. Quote names with spaces: `--param "Word Speed=0.5"` |
| *unknown, incompatible or wrong-kind engine* | The identifier is misspelt, or names an effect where an engine is wanted | `engines/build/fm1-render --list` prints every identifier and kind |
| *sw-sophie has no pitch bend* | Sophie ignores pitch bend, so `--bend` is refused | Leave out `--bend` for Sophie |
| *--bend and --param-at need --engine* | Those options act on a sound engine | Add `--engine` |
| The WAV file is silent | No `--note`, or notes outside an engine's range | Add notes; Sophie answers only notes 36 to 51 |

### The sequencer

| Symptom or message | Likely cause | What to do |
| --- | --- | --- |
| A script renders, but nothing plays | The script never sends `play`, or the run ends too soon | Add `@0 play`; set `end=` in the `#!` line, or give `--seconds` |
| Notes play, but a lock changes nothing | The lane's label names no parameter of the engine | Label the lane with the parameter's name, as in `synth:Timbre` ([chapter 7](07-sequencer.md#scripts-on-the-desktop)) |
| A track's notes are logged but not heard | The track is routed to MIDI | Add `--route T:engine` for that track |
| *--route, --log-events, --compat and --tracks need --cmd or --seq* | Those options belong to sequencer renders | Add a script with `--cmd` or a set with `--seq` |
| *not a movy1 set* | The file does not start with the line `movy1` | Export sets with `fm1-seq --export`, or check the file |
| The summary reports `seq_refused` above 0 | An edit did not fit the sequencer's memory and was refused whole | Use fewer notes or locks, or fewer tracks ([chapter 7](07-sequencer.md#memory)) |
| A command seems to be ignored | Tracks, steps, slots and scenes count from 0 in scripts; an unknown verb is ignored without a message | Check the numbering and the verb's spelling against chapter 7's table of commands |

## The FM-1

The FM-1 does not run Lunar Modulator, so problems with the instrument
itself are for M-VAVE's manual and support. Chapter 10 describes the
firmware the FM-1 has now and how to find out which one it is
([chapter 10](10-updating-and-recovery.md#the-firmware-your-fm-1-has-now)).

## Reporting a problem

If a remedy here does not help, open an issue on the project's repository at
`github.com/ip2k/lunar-modulator`. Say:

- what you did, what you expected, and what happened instead;
- for the simulator: the browser and its version, the computer or phone, and
  the status line under the panel;
- for the desktop tools: the command, its full output, and the commit you
  built from;
- the edition of this manual, from the table in
  [chapter 1](01-welcome-and-safety.md#about-this-manual).
