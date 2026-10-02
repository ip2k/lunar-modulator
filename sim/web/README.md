# sim/web — a virtual FM-1 in the browser

Lunar Modulator's engines and effects, compiled to WebAssembly, running
behind a to-scale FM-1 front panel with the firmware's own 240 × 240 screen.
Play it with the mouse, a touch screen, the computer keyboard or a MIDI
keyboard. Nothing here talks to a real FM-1.

![The virtual FM-1 playing a chord](../../assets/screenshots/virtual-fm1.png)

Is there an emulator of the FM-1 itself? Not a public one; see
[emulators.md](emulators.md) for what exists and what each route would take.

```bash
cd sim/web/www && python3 -m http.server 8000     # then open http://localhost:8000/
FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh  # rebuild fm1.wasm on a Docker host, test it, screenshot it
python -m pytest tests/test_sim_web.py           # native checks, no WebAssembly needed
```

The page needs a secure context for its AudioWorklet and Web MIDI, which
`http://localhost` and any `https://` page are; opening `index.html` as a
file does not work. It has no dependencies and loads nothing from other
origins; every reference is relative, and `app.js` finds the worklet and
the module next to itself, so the `www/` folder can be published as static
files at any path as it is (but see "Before publishing"). Audio starts on
the "Power on" button, as browsers require a gesture.

## What works

| | |
| --- | --- |
| Engines | Every registered sound engine and effect (engines/README.md): Macro, Shapes, Macro Heavy, Six-Op FM, Sophie, Test Sine; Plate, Ensemble, Diffuse, PSX Verb, Test Gain. One sound and two effect slots, then the host's bus limiter, as `fm1-render` runs them |
| Audio | An AudioWorklet renders each 128-frame quantum as two 64-frame host blocks. The AudioContext asks for 44,118 Hz, then 44,100 Hz (a context that comes back faster than 47,872 Hz is closed and the next rate tried), and only then takes the device's own rate. Headless Chromium ran at 44,118 Hz [verified]. Macro, Macro Heavy and Six-Op run Plaits at 47,872 Hz and resample to the host (engines/resampler.md), so they refuse a faster one: there the firmware starts with Shapes, PRESETS steps over the three, a refused choice puts the previous engine back, and the screen and status line say why [verified natively at 48 and 96 kHz: `tests/test_sim_web.py`] |
| Screen | The firmware draws a 240 × 240 RGB565 frame buffer (stock's layout: a top bar with the sound, the mode's content, a bottom bar with page and mode, one-second popups); the page only copies it to a canvas. HOME's oscilloscope strip scales the trace to its window's peak (at most ×16, so quiet noise stays flat). 287 screens (every page of every engine and effect at defaults, minima, maxima and every list entry, the global page, every popup including the refusals, SEL outside FX mode and an emptied slot) pass a layout check: nothing off screen, no text cut short, and no two labels and no label and bar closer than 4 px [verified: `fm1-sim-render --screens`] |
| Panel | The 27 keys, 14 buttons, MASTER and the seven encoders, with their LEDs, laid out to scale (below) |
| Input | Mouse and touch (lower on a key plays louder; drag or scroll an encoder), the computer keyboard (`A W S E D R F G Y H U J K O L P ; [ '` play F3 to B4, `Z`/`X` are OCT−/OCT+, arrows turn SELECT and PRESETS, `-`/`=` ALGORITHM, `Esc` releases every note), and Web MIDI (notes, pitch bend ±2 semitones, CC 7 volume, CC 123 all notes off). A held key or button is released whatever modifiers are down by then (Cmd lets go of every held key, since macOS drops those keyups), and leaving the window or tab releases every key, button and pointer. Scrolling over an encoder turns it one detent for the first wheel event of a gesture, then one per 60 px of vertical scroll; horizontal scrolling turns nothing |
| Look | Lunar Modulator's: the Rosé Pine Moon palette ([rosepinetheme.com](https://rosepinetheme.com/palette/), MIT; the hex values checked against rose-pine/palette and rose-pine/neovim on 2026-10-01 [verified]) as CSS custom properties, one dark theme, and the firmware's screen in the same colours (`src/fm1_app.c`); Audiowide (Astigmatic, SIL OFL 1.1) for the name, the tagline and headings, from the page's own `fonts/`, unmodified ([fonts/README.md](www/fonts/README.md)); Exo 2 (Natanael Gama, SIL OFL 1.1) for small text, also from `fonts/`, unmodified. Text contrast is at least 4.8:1 against its background on the page, disabled controls aside (WCAG AA asks 4.5:1; secondary text on a surface is subtle with a tenth of text mixed in, since subtle alone is 4.46:1 there) and at least 4.78:1 on the screen after RGB565 rounding [verified: computed from the palette] |
| Info | GLO shows the sample rate, block size, the chain's RAM against the 379 KB the stock layout leaves free (docs/11 §2), voices, octave and transpose. WebAssembly has 4-byte pointers like pi32v2, so these are the 32-bit instance sizes |

Tested in Chromium only. In headless Chromium 153 (Playwright 1.63, on
aeon) [verified: `build/screenshots/report.json`, 2026-10-01]: the page is titled
"Lunar Modulator", Audiowide loads from `fonts/`, the background is the
palette's base; it powers on, a
three-note chord reaches the output (RMS 0.046), three key LEDs light, FX,
SELECT and ALGORITHM put Ensemble in slot 2. The input checks: a double
click on Power on opens one AudioContext and Power off closes it; a key
released under Cmd, Ctrl or Alt is released, and Cmd alone releases held
keys; window blur and a hidden tab release computer keys, `Z`/`X` and a
pointer-held key; Enter on FX, Tab, release sends FX's up, and the next FX
press works; choosing in a dropdown gives the keys back to the instrument;
a horizontal scroll turns nothing, 20 trackpad events of 4 px turn 2 detents,
five mouse notches five; screens keep coming (29 a second while a note
sounds) on two recycled buffers. At 390 × 844 the page does not scroll
sideways, the smallest targets are 24.8 px (OCT−/OCT+, 5.2 mm tall) and
the keys 35 and 31.5 px wide, the panel opens scrolled just far enough to
show the whole screen, and dragging the case pans it; at 844 × 390 the
panel fits with 25 px targets, the header shrinks to the name and tagline,
and Power on sits over the panel's top row. Published as a static host
would publish it, over https (a self-signed certificate) under
`/some/where/lunar/`, it is a secure context, every request succeeds and
stays under that path, Audiowide loads and a key reaches the output at
44,118 Hz (RMS 0.031); over plain http from a name that is not localhost,
Power on says the page needs https or localhost and opens no
AudioContext. By hand in Chromium 152 on macOS (the Claude desktop app's
browser pane), from `python3 -m http.server`: 44,118 Hz, the panel's keys
and the computer keyboard reach the output (RMS 0.022), a scroll over
KNOB1 turns it, and at 375 px the page does not scroll sideways
[verified, 2026-10-01]. Firefox, Safari, real touch screens and real MIDI
hardware are not tested.

## The panel

Narrower than 832 px, the panel keeps 800 px (4.8 px/mm) and scrolls
sideways in its own box rather than shrinking: at a phone's width the
to-scale panel had 11 px buttons and 16 px keys, under WCAG 2.5.8's 24 px
minimum. Drag the case (not a control) to pan it, or turn the phone to
landscape. Desktop widths show the whole panel to scale as before.

The case is 161.5 × 96.5 mm (the M-VAVE manual's specifications)
[reported]. Control centres were measured on the owner's board photo
(`photos/2026-09-29/3-top.jpg`) at 12.8 px/mm with the board centred in the
case [verified positions; scale inferred, within about 5 %]. The printed
names, the screen window and the combo labels under the black keys (OP1–OP6,
PIT, GLO, MONO, POLY) come from the manual's panel drawing [reported].

| Control | On the FM-1 (manual) [reported] | In the simulator |
| --- | --- | --- |
| Keys | key position + 53 + 12 × octave + transpose: F3–G5 at rest | the same |
| OCT− / OCT+ | octave −3..+3; both together reset octave and transpose; hold one and turn ALGORITHM to transpose ±12; LED off / slow / fast / solid for 0 / 1 / 2 / 3 | the same |
| MASTER | volume (a potentiometer) | output gain after the limiter, popup "Volume N" |
| SELECT | page within the mode; in FX mode, the effect slot | the same, for the engine's pages and the two slots |
| PRESETS | the 128 presets | the sound engine, with a list popup |
| ALGORITHM | the FM algorithm | the engine's first list parameter (Model, Shape, Patch or Pad); in FX mode, the effect in the selected slot |
| KNOB1–4 | the four parameters on the bottom bar | the four parameters of the page, shown as rows with bars |
| FX, SEL | effect chain mode; SEL grabs a slot so SELECT reorders it | the same, with two slots |
| GLO | global settings | the global page above |
| HOME | home (oscilloscope) | home: the sound's page, with an oscilloscope strip |
| ENV, LFO, EDIT, SAVE, ARP, SEQ, PLAY/STOP, REC | | a popup: not in the simulator yet |

## Parity: does the browser sound like the native engines?

`build-on-aeon.sh` renders twelve note scripts (`test/scenarios.json`;
every engine and effect, pitch bend, parameter changes mid-note, more notes
than voices, 44,100 Hz) four ways and compares the 16-bit output sample by
sample [verified: `www/fm1.wasm.json`]:

| Against | Result |
| --- | --- |
| `render.cc` compiled to WebAssembly (Node) | identical in all 12: the app layer adds nothing |
| native `fm1-render`, GCC with musl (static, Alpine) | identical in all 12: the compiler adds nothing |
| native `fm1-render`, GCC with glibc | identical in the 10 scenarios without Sophie. Sophie differs (23,286 and 694 samples, up to 4,082 and 12,330 LSB) |

The Sophie difference is libm, not the port: Sophie calls `sinf`, `expf`,
`exp2f` and `powf` per sample and per note, its feedback FM amplifies their
last-bit differences, and glibc and musl (Emscripten's C library) round some
of them differently. A native build against musl renders Sophie byte for byte
like the browser. The same holds for the firmware: whatever libm JieLi's
toolchain ships will decide Sophie's last bits there too.

The screen the browser module draws matches the native harness's pixel for
pixel, except the RAM figure in the bottom bar, which is the 32-bit one.

The module is built from main's engines as of PR #12 (Shapes at 96 kHz and
Plaits at 47,872 Hz through `fm1_resampler.h`): 12 of 12 scenarios pass,
identical to musl and to render.js, identical to glibc but for Sophie; the
module is 391 KB [verified, 2026-10-01, `www/fm1.wasm.json`].

## How it is built

```
www/app.js        page: panel (SVG), input, screen canvas, MIDI    main thread
   | port messages (events at block boundaries) / screen and LED updates
www/worklet.js    AudioWorkletProcessor: 2 x 64-frame blocks per quantum
www/fm1-wasm.mjs  loader shared with the Node test (no Emscripten runtime)
www/fm1.wasm      src/fm1_web.c   flat exports (fm1w_*)
                  src/fm1_app.c   the "firmware": chain, panel logic, screen
                  src/fm1_tft.c   240 x 240 RGB565 frame buffer, 5 x 9 font
                  engines/        every engine, effect and the bus limiter
```

`src/` is C99 with no heap: instance memory lives in fixed arenas inside
`fm1_app_t`. Nothing in it is browser-specific, so the same app layer builds
natively as `fm1-sim-render`, the test harness. Its panel logic and drawing
code are meant to carry over to the firmware, but not `fm1_app_t` as it
stands: it is 1,168,288 bytes (1 MiB of fixed arenas and a 115,200-byte
full frame buffer; clang, 64-bit), against the FM-1's 578 KB of SRAM and
the ~379 KB the stock layout leaves free [verified: `sizeof`; SRAM from
docs/01]. The firmware needs one arena sized to the chain it loads and
strip rendering (ten 240 × 24 strips, 11.5 KB each, as stock does;
`src/fm1_tft.h`) [inferred]. The font is drawn for this repository
(`tools/font5x9.txt`; `tools/gen_font.py` writes `src/fm1_font.h`).

The worklet allocates as little as it can on the audio thread: the module's
memory never grows, so its views on the output, LEDs and screen are made
once, and screens travel to the page in two buffers that the page hands
back after drawing (a screen waits, still dirty, while both are out). A
message envelope per screen and a 41-byte copy per LED change remain.
Measured on aeon: rendering takes 7–37 µs per 64-frame block (max 244 µs)
and drawing plus copying 8–65 µs (max 288 µs), against the 1,451 µs a
block lasts [reported: the 2026-10-01 review]; phones are not measured.

`mk/sim.mk` is read after `engines/Makefile`, so it reuses that Makefile's
source lists, flags and rules unchanged, and builds whatever engines the tree
has. The module is standalone (`-sSTANDALONE_WASM`, no imports, 8 MB fixed
memory) and about 390 KB.

### `build-on-aeon.sh`

One command, run against any Linux machine with Docker that you can ssh
to (`FM1_SIM_HOST=user@host`; the project's has been aeon, a box on the
owner's LAN); about 20 seconds once that host has the three images (the
first run pulls them). There, in containers (nothing runs locally but ssh,
tar and scp; nothing is installed on the host):

1. `alpine:3.22`: a static musl `fm1-render`.
2. `emscripten/emsdk:6.0.10` (`build.sh`): native `fm1-render` and
   `fm1-sim-render` with GCC 13, the screen sweep, `fm1.wasm` and
   `fm1-render.js` with Emscripten 6.0.10, `test/parity.mjs`; then, only if
   everything passed, `www/fm1.wasm` and its record `www/fm1.wasm.json`
   (hashes of the module and of the sources, the parity results).
3. `mcr.microsoft.com/playwright:v1.63.0-noble`: `test/screenshot.mjs` opens
   the page in headless Chromium, plays it and writes screenshots and a
   report to `build/screenshots/`; with `--readme-screenshots`,
   `test/readme-screenshots.mjs` then takes the README's pictures (the page,
   each engine's screen, an effect page, a parameter page, the phone and
   the parity figure) into `build/readme-screenshots/`, for a person to look
   at and copy to `assets/screenshots/` ([its README](../../assets/screenshots/README.md)).

Options: `--engines-ref REF` builds another commit's engines as a trial:
its module, record, `parity.json` and screenshots go to `build/ref-REF/`,
never to `www/`, and the working tree's own results in `build/` stay;
`--no-screenshot` skips step 3 (and keeps the last screenshots). The record
names the three images by digest (`images`), since tags move, and a
rebuild of a byte-identical module from unchanged sources keeps the
record's `built` time, so the file changes only when something in it did.
`FM1_SIM_HOST` (required) names the host; `FM1_REMOTE_DIR` and
`FM1_SESSION` override the directory there (`~/mvave-fm1/virtual`; `src/`
in it is the staging copy, replaced on every run, and `playwright/` caches
the Playwright package, about 20 MB) and the containers' session label.

### Tests

`tests/test_sim_web.py` runs in the normal suite (and CI): the app layer's
output equals `fm1-render`'s byte for byte for every scenario, natively; the
287-screen layout sweep; the panel against the manual's formula (octave,
transpose, reset); buttons and encoders; an effect slot emptied on its
second page; sounds that refuse a 48 kHz host stepped over and the previous
one kept; the page loads nothing from other origins; the exports match; and
`www/fm1.wasm` matches its record. The record carries two source hashes
(`tools/source_hash.py`): engines/ (less Markdown) and sim/web's own inputs
(`src/`, `mk/`, `build.sh`, the parity test and its scenarios, the
harness, the loader). When sim/web's inputs have changed since the last
build, the test fails in CI (`CI=true`) and warns locally; when only the
engines have, it warns, so engine work elsewhere does not need aeon.
Rebuild with `build-on-aeon.sh` before publishing the page or merging a
change to the simulator.

CI also runs this file in its 32-bit job (`-m32`, like pi32v2's pointers)
and under ASan + UBSan, through the variables below.

The harness builds into `sim/web/build/native` with the default compiler.
`FM1_SIM_EXTRA` (with `FM1_SIM_CC`, `FM1_SIM_CXX`, `FM1_SIM_OPT`) builds it
another way, for example under ASan and UBSan:

```bash
FM1_SIM_CC=clang FM1_SIM_CXX=clang++ FM1_SIM_OPT=-O1 \
FM1_SIM_EXTRA="-fsanitize=address,undefined -fno-omit-frame-pointer -g -fsanitize-ignorelist=sanitizers/ignorelist.txt" \
UBSAN_OPTIONS=suppressions=$PWD/engines/sanitizers/ubsan.supp:halt_on_error=1 \
    python -m pytest tests/test_sim_web.py
```

## Limits

- **Timing and CPU** are the browser's, not pi32v2's. The simulator says
  nothing about whether a chain fits the FM-1's cycle budget (stage B
  measures that), nor about FPU edge cases on the real core.
- **No drivers**: no SPI, DMA, ADC or USB; the panel calls the app directly.
- **Eight buttons** do nothing yet. The sequencer core is built
  (engines/seq.md); it is not yet wired to PLAY/STOP, REC and SEQ.
- **MIDI in only**; the virtual FM-1 sends nothing.
- **Encoders without acceleration**; a float parameter moves a hundredth of
  its range per detent.
- **The screen is drawn on the audio thread**, as UI and audio share one
  core on the FM-1: a full redraw at most every ~33 ms while sound plays.
  Phones are not measured; if one drops out, a lower scope rate there is
  the next step.

## Before publishing

Six-Op FM's 23 patch names that are third-party trademarks or a person's
name are shown under descriptive names of our own (PR #15; engines/README.md,
"Open questions"), and the module was rebuilt with them. The stored names are
still in the vendored patch data, but they are not displayed.
Every engine is MIT (Mutable Instruments, Schwung modules); the credits are
in each engine's `credits` string and in the page's footer.

Publishing is copying `www/` as it is: `index.html`, `style.css`, `app.js`,
`worklet.js`, `fm1-wasm.mjs`, `fm1.wasm` and `fonts/`. The host must serve
`.js` and `.mjs` as JavaScript (module scripts and the worklet's import
need it; Python's `http.server` does from 3.9 on [verified: 3.9 to 3.12])
and the page over https or from localhost. The page test serves it over
https under a sub-path (above); a real static host has not been tried. A
host that serves pages from an opaque origin (a sandboxed iframe) would
also need CORS headers on the module scripts [inferred].
