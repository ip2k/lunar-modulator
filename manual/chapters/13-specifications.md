# Specifications

## The instrument

These are the M-VAVE FM-1's own specifications, as far as they matter to
Lunar Modulator. The *source* column says where each figure comes from:
*checked on a unit* means seen on an FM-1's board or read from its firmware
by this project; *M-VAVE* means M-VAVE's documentation; *published analysis*
means the work of others who have studied the FM-1, credited in
[chapter 14](14-credits-and-licences.md).

| Item | Specification | Source |
| --- | --- | --- |
| Processor | JieLi AC791N, with a 32-bit pi32v2 core. M-VAVE's firmware runs it at 240 MHz of a possible 320 MHz | Chip checked on a unit; clock from published analysis |
| Memory | 578 KB of RAM on the chip, of which about 514 KB is usable; 1 MB of flash memory, probably inside the chip's package | RAM from the chip maker's documentation; flash from published analysis |
| Display | 1.54-inch colour screen, 240 × 240 pixels | Published analysis and M-VAVE |
| Keys | 27, from F3 to G5, each with a light | Count checked on a unit; range from M-VAVE |
| Knobs | 7 encoders and 1 potentiometer ([[MASTER]]) | Checked on a unit |
| Buttons | 14, each with a light | Checked on a unit; names from M-VAVE |
| Connectors | USB-C; 3.5 mm stereo audio output; 3.5 mm MIDI input (TRS, input only) | Checked on a unit; MIDI input from M-VAVE |
| Speaker | Built in | Checked on a unit (its connector on the board) |
| USB | USB 2.0 full speed. With M-VAVE's firmware: MIDI, and two channels of audio in each direction at 44.1 kHz | Checked on a unit |
| Wireless | Bluetooth LE, which M-VAVE's firmware uses for MIDI | Published analysis |
| Power | Lithium-polymer battery, 3.7 V, 2000 mAh (7.4 Wh), charged over USB-C; slide switch | Battery checked on a unit (cell label); charging from M-VAVE |
| Size | 161.5 × 96.5 mm | M-VAVE |

## Lunar Modulator

{{status sim desktop}}

| Item | Specification |
| --- | --- |
| Sample rate | 44,118 samples a second, the rate reported for the FM-1's audio output. The simulator uses 44,100 or the computer's own rate when the browser cannot give it 44,118 |
| Block | 64 samples, 1.45 ms at 44,118 |
| Output | Stereo |
| Engines' own rates | Macro, Macro Heavy, Six-Op FM and Drums run Plaits' code at 47,872 samples a second, and Shapes runs Braids' at 96,000, each converted to the output's rate, so that they sound and keep time as on the modules they come from. The four Plaits-based engines cannot run when the output is faster than 47,872. FM6 runs at the output's rate, from 16,385 samples a second up, with its envelope times kept |
| Sound engines | Eight; up to four sounds at once, each with its own engine ([chapter 5](05-sound-engines.md)) |
| Effects | Twenty-two, Test Gain and Test Ext included: two inserts on each sound, then two master effects in series after the mix ([chapter 6](06-effects.md)) |
| Limiter | Ceiling 0.98 of full scale (−0.18 dBFS), instant attack, about 100 ms release; samples that are not numbers become silence |
| [[MASTER]] | After the limiter. Half way round is a quarter of full level, about −12 dB |
| Pitch bend | Up to ±48 semitones in the engines; ±2 semitones from MIDI in the simulator |
| Memory for sounds | About 379 KB (387,924 bytes) for the sounds, effects, sequencer and modulation: the room M-VAVE's firmware leaves free on the FM-1. The real figure for Lunar Modulator on the device will be known once it runs there |
| Sequencer | 8 tracks in the simulator, as planned for the FM-1 ([chapter 7](07-sequencer.md)) |
| Licence | MIT for Lunar Modulator's own code; code from other projects under its own licence ([chapter 14](14-credits-and-licences.md)) |

### Engines and effects in figures

Memory is given as a 32-bit build lays it out, as in the simulator and on the
FM-1. The screen's memory figure adds up these numbers for the chain in use,
and is the one to trust if the two ever differ.

| Engine or effect | Voices | Memory, about |
| --- | --- | --- |
| Macro | 12 | 18 KB |
| Macro Heavy | 4 | 69 KB |
| Six-Op FM | 8 | 11 KB |
| FM6 | 12 | 14 KB, and 28 KB of tables shared by every FM6 sound |
| Shapes | 12 | 201 KB |
| Sophie | 12 | 76 KB |
| Drums | 12 | 8 KB |
| Test Sine | 12 | under 1 KB |
| Plate | – | 64 KB |
| Ensemble | – | 5 KB |
| Diffuse | – | 18 KB |
| PSX Verb | – | 131 KB |
| Crush | – | under 1 KB |
| Fold | – | under 1 KB |
| Drive | – | under 1 KB |
| Echo | – | 64 KB |
| Filter | – | 18 KB |
| Comp | – | under 1 KB |
| Limiter | – | 9 KB |
| DJ Filter | – | under 1 KB |
| Tilt | – | under 1 KB |
| Master Sat | – | under 1 KB |
| Isolator | – | under 1 KB |
| EQ | – | under 1 KB |
| Room | – | 40 KB |
| Hall | – | 49 KB |
| Gate | – | 2 KB |
| Test Gain | – | under 1 KB |

### The sequencer

{{status sim desktop planned}}

{{seq-glance}}

### Sounds, effects and modulation

{{status sim desktop planned}}

| Item | Specification |
| --- | --- |
| Sounds | Up to four at once, each with its own engine and a level into the mix |
| Effects | Two inserts on each sound, two master effects after the mix, then the limiter |
| Modulation | A rack of eight positions for sixteen kinds of module, 32 cables, worked out every 32 samples |
| Memory | Everything refused that would take the chain past about 379 KB |

## The simulator

{{status sim}}

| Item | Specification |
| --- | --- |
| Runs in | A web browser with WebAssembly and the Web Audio API's AudioWorklet, from an `https://` address or from the computer it runs on |
| Tested in | Chromium. Firefox, Safari, real touch screens and real MIDI hardware are not tested yet |
| Sample rate | Asks for 44,118, then 44,100; otherwise the computer's own rate |
| Input | Mouse, touch, the computer keyboard, and MIDI from a keyboard: notes, velocity, pitch bend, control changes 7 and 123 |
| Output | Audio only. It sends no MIDI |
| Screen | The firmware's 240 × 240 screen, redrawn up to about 30 times a second while sound plays |
| Panel | To scale, 161.5 × 96.5 mm. On narrow screens it keeps a width of 800 pixels and scrolls sideways |
| Download | About 730 KB for the firmware, plus the page; nothing is loaded from other websites |

## The desktop tools

{{status desktop}}

| Item | Specification |
| --- | --- |
| Renderer | `fm1-render` plays notes, or the sequencer, through one engine, any number of effects and the limiter, or through up to four sounds with their inserts, levels and master effects as the simulator does, with modulation from a file, into a 16-bit stereo WAV file. Unless told otherwise: 44,118 samples a second, 64-sample blocks, 2 seconds |
| Sequencer tool | `fm1-seq` runs the sequencer alone, writes the events it produces, and saves and loads sets as text |
| Builds with | `make` and a C and C++11 compiler. The project's automatic tests build and run them on Linux and macOS |

## Still to be measured on the device

{{status planned}}

These figures will be added once Lunar Modulator runs on the hardware:

- the processor load of each engine and effect on the FM-1's processor, first
  measured on a JieLi development board;
- how many voices each engine can play on the FM-1, which memory and
  processor load will decide;
- battery life with Lunar Modulator;
- whether the FM-1's keys sense how hard they are played;
- which kind of TRS adapter the [[MIDI IN]] jack expects;
- the exact sample rate of the FM-1's audio output, so far reported, not
  measured, as 44,118.
