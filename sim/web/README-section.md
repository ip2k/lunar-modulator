<!--
Draft for the top-level README (written in sim/web/ so the README itself is
left to the branch that is editing it). Image paths are relative to the
repository root, so the two sections can be pasted into README.md as they
are. The sequencer paragraph describes feature/2026-10-01@seq-core, which
is not on main yet: its engines/seq.md link resolves once that merges.
-->

## Features

Nothing here runs on an FM-1 yet: the engines, effects and sequencer core
are built and tested on a desktop, and the virtual FM-1 runs them in a
browser. The screenshots below are that virtual FM-1, showing the
firmware's own 240 × 240 screen.

### Sound engines

Five swappable sound engines behind one C API with no heap
([`engines/`](engines/README.md)). **Macro** is Plaits' eight light
models (virtual analogue, phase distortion, terrain, chiptune, VA pair,
waveshaper, 2-op FM, wavetable) with 12 voices; **Shapes** is Braids' 47
shapes; **Macro Heavy** is Plaits' other 13 (string machine, chords,
speech, modal, particle, three drums and more) with 4 voices; **Six-Op FM**
is Plaits' DX7-style engine with its 96 patches, 8 voices; **Sophie** is a
16-pad FM drum kit, an MIT Schwung module compiled unmodified through a
compatibility shim. Each engine pages its parameters four at a time, one
per knob, as the FM-1's four free knobs want.

<table>
<tr>
<td><img src="assets/screenshots/screen-macro.png" width="150" alt="Macro on VA Pair: Model, Harmonics, Timbre and Morph with bars, and an oscilloscope strip"></td>
<td><img src="assets/screenshots/screen-shapes.png" width="150" alt="Shapes on Pluck: Shape, Timbre, Color and Attack"></td>
<td><img src="assets/screenshots/screen-macro-heavy.png" width="150" alt="Macro Heavy on its string machine model"></td>
<td><img src="assets/screenshots/screen-sixop.png" width="150" alt="Six-Op FM on patch E.PIANO 1: Patch, Brightness and Envelope"></td>
<td><img src="assets/screenshots/screen-sophie.png" width="150" alt="Sophie's kick pad: Pad, Tune, Decay and Model"></td>
</tr>
<tr>
<td align="center">Macro</td>
<td align="center">Shapes</td>
<td align="center">Macro Heavy</td>
<td align="center">Six-Op FM</td>
<td align="center">Sophie</td>
</tr>
</table>

### Effects

Effects chain after any engine: **Plate** (Rings' reverb), **Ensemble** and
**Diffuse** (Plaits), and **PSX Verb**, a second MIT Schwung module. The
virtual FM-1 has two effect slots: FX shows them, SELECT moves between
them and their pages, ALGORITHM picks the effect, SEL then SELECT swaps
the two. A host limiter on the bus keeps twelve voices started in phase
under full scale.

<img src="assets/screenshots/screen-fx.png" width="240" alt="FX mode: slot 1 Plate, slot 2 PSX Verb selected, with its Model, Decay, Mix and Level">

### Renders checked against the reference, sample by sample

Every engine and effect built from Mutable Instruments code is compared
with the upstream classes it wraps: reference renderers drive the original
Plaits, Braids and Rings code as the modules' own firmware does, with
nothing of ours in the path, and about 350 tests compare the two. At the
upstream rates the engines match sample for sample or within half a
16-bit step ([`engines/reference-plaits.md`](engines/reference-plaits.md),
[`engines/reference-braids-fx.md`](engines/reference-braids-fx.md)); the
two Schwung modules are compiled unmodified. The browser adds nothing: twelve note scripts covering every engine and effect
render identically, sample for sample, in the browser's WebAssembly module
and in the native renderer built with GCC and musl; against GCC with glibc
ten of the twelve are identical, and the two that differ are Sophie's,
whose feedback FM amplifies last-bit differences between the two C
libraries' `sinf` and `expf` [verified: `sim/web/www/fm1.wasm.json`,
2026-10-01].

![Six-Op FM's chord rendered natively and in the browser, with a flat difference line: 0 of 105,882 samples differ](assets/screenshots/parity.png)

### Sequencer core

`fm1_seq` is a C99, heap-free port of Movy's sequencer (schwung-movy, MIT)
with the fixes planned in [docs/13](docs/13-movy-port.md) on by default and
an exact-Movy mode for tests: 4–8 tracks, each routed to the engine or to
USB-MIDI on its own channel, in 14,984 bytes at 4 tracks and 28,808 at 8.
The desktop renderer plays Movy sets and timed scripts through it with
sample-accurate notes and parameter locks, and Movy's own unmodified core,
run in a container, drives 24 golden fixtures that ours matches event for
event, undo aside ([`engines/seq.md`](engines/seq.md)). It is not wired
into the virtual FM-1 yet, so there is no screen to show: SEQ, PLAY/STOP
and REC still say "not in the simulator yet".

### The virtual FM-1

The firmware's app layer (panel logic, the effect chain and the screen
drawing) compiled to WebAssembly and run in an AudioWorklet, behind a
to-scale drawing of the FM-1's front panel: the 27 keys, the 14 buttons
with their LEDs, MASTER and the seven encoders. The screen is the
firmware's own RGB565 frame buffer, copied to a canvas; every one of its
287 screens passes a layout check with no text cut short and nothing
closer than 4 px. Turn KNOB1–4 and the four parameters on the page follow.
Play it with the mouse, a touch screen, the computer keyboard or a MIDI
keyboard.

![Lunar Modulator in the browser: the to-scale FM-1 panel with a chord held on Macro](assets/screenshots/virtual-fm1.png)

<img src="assets/screenshots/panel-params.png" width="560" alt="The screen beside KNOB1-4, turned: Model 2-op FM, Harmonics 0.68, Timbre 0.28, Morph 0.81"> <img src="assets/screenshots/phone.png" width="200" alt="The page on a 390-pixel-wide phone: the panel keeps playable key sizes and scrolls sideways">

On a phone the panel keeps playable sizes (keys 31–35 px wide, no target
under 24 px) and scrolls sideways in its own box; turned to landscape it
fits whole.

## Try it in your browser

The built module is in the repository, so all it takes is Python 3 and a
current browser:

```bash
cd sim/web/www && python3 -m http.server 8000
```

Open <http://localhost:8000/> and press **Power on** (browsers only start
audio after a click). The page needs `http://localhost` or `https://`;
opening `index.html` as a file does not work. It loads nothing from
anywhere else, so `sim/web/www/` can also be published as static files.

**Browsers.** It needs WebAssembly, an AudioWorklet and a secure context.
It is tested in headless Chromium 153 only; Firefox, Safari, real touch
screens and MIDI hardware are not tested yet. "Connect MIDI input" needs a
browser with Web MIDI; without it the panel and the computer keyboard
still play.

**Controls.**

| Control | Mouse or touch | Computer keyboard |
| --- | --- | --- |
| Keys | Click or touch; lower on a key plays louder | `A` `S` `D` `F` `G` `H` `J` `K` `L` `;` `'` play the white keys F3 to B4, `W` `E` `R` `Y` `U` `O` `P` `[` the black ones |
| OCT− / OCT+ | Click | `Z` / `X`. Both together reset octave and transpose; hold one and turn ALGORITHM to transpose ±12 |
| SELECT | Drag up or down, or scroll | `←` `→`: the page, or in FX mode the slot and its pages |
| PRESETS | Drag or scroll | `↑` `↓`: the sound engine |
| ALGORITHM | Drag or scroll | `-` `=`: the engine's model (Model, Shape, Patch or Pad), or in FX mode the effect in the selected slot |
| KNOB1–4 | Drag or scroll | Tab to a knob, then the arrow keys: the four parameters on the screen |
| MASTER | Drag or scroll | Tab to it, then the arrow keys: the volume |
| FX, SEL, GLO, HOME | Click | Tab to a button, then Enter or Space. FX: the effect slots; SEL then SELECT: swap them; GLO: rate, block, RAM, voices, effects, octave and transpose; HOME: back to the sound |
| Everything | | `Esc` releases every note |

ENV, LFO, EDIT, SAVE, ARP, SEQ, PLAY/STOP and REC show "not in the
simulator yet". The dropdowns under the panel pick the sound and both
effects directly, "Screen ×2" shows the screen enlarged, and a MIDI
keyboard plays notes with pitch bend (±2 semitones), CC 7 (volume) and
CC 123 (all notes off).

**Rebuilding the module.** Only needed after changing `engines/` or
`sim/web/src/`. It builds in containers on any Linux machine with Docker
that you can reach over ssh, checks the result sample by sample against
the native renderer, plays the page in headless Chromium, and only then
replaces `sim/web/www/fm1.wasm`:

```bash
FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh   # about 20 s once the images are pulled
python -m pytest tests/test_sim_web.py            # the native checks, no WebAssembly needed
```

Details, the panel's measurements and the parity results are in
[`sim/web/README.md`](sim/web/README.md).
