# sim/web — a virtual FM-1 in the browser

The open firmware's engines and effects, compiled to WebAssembly, running
behind a to-scale FM-1 front panel with the firmware's own 240 × 240 screen.
Play it with the mouse, a touch screen, the computer keyboard or a MIDI
keyboard. Nothing here talks to a real FM-1.

Is there an emulator of the FM-1 itself? Not a public one; see
[emulators.md](emulators.md) for what exists and what each route would take.

```bash
cd sim/web/www && python3 -m http.server 8000     # then open http://localhost:8000/
sim/web/build-on-aeon.sh                         # rebuild fm1.wasm on aeon, test it, screenshot it
python -m pytest tests/test_sim_web.py           # native checks, no WebAssembly needed
```

The page needs a secure context for its AudioWorklet and Web MIDI, which
`http://localhost` is; opening `index.html` as a file does not work. It has
no dependencies and loads nothing from other origins, so the `www/` folder
can be published as static files as it is (but see "Before publishing").

## What works

| | |
| --- | --- |
| Engines | Every registered sound engine and effect (engines/README.md): Macro, Shapes, Macro Heavy, Six-Op FM, Sophie, Test Sine; Plate, Ensemble, Diffuse, PSX Verb, Test Gain. One sound and two effect slots, then the host's bus limiter, as `fm1-render` runs them |
| Audio | An AudioWorklet renders each 128-frame quantum as two 64-frame host blocks. The AudioContext asks for 44,118 Hz, falls back to 44,100 Hz, then to the device rate, and the engines get whatever rate it got. Headless Chromium ran at 44,118 Hz [verified] |
| Screen | The firmware draws a 240 × 240 RGB565 frame buffer (stock's layout: a top bar with the sound, the mode's content, a bottom bar with page and mode, one-second popups); the page only copies it to a canvas. 282 screens (every page of every engine and effect at defaults, minima, maxima and every list entry, the global page, every popup) pass a layout check: nothing off screen, no two labels and no label and bar closer than 2 px [verified: `fm1-sim-render --screens`] |
| Panel | The 27 keys, 14 buttons, MASTER and the seven encoders, with their LEDs, laid out to scale (below) |
| Input | Mouse and touch (lower on a key plays louder; drag or scroll an encoder), the computer keyboard (`A W S E D R F G Y H U J K O L P ; [ '` play F3 to B4, `Z`/`X` are OCT−/OCT+, arrows turn SELECT and PRESETS, `-`/`=` ALGORITHM, `Esc` releases every note), and Web MIDI (notes, pitch bend ±2 semitones, CC 7 volume, CC 123 all notes off) |
| Info | GLO shows the sample rate, block size, the chain's RAM against the 379 KB the stock layout leaves free (docs/11 §2), voices, octave and transpose. WebAssembly has 4-byte pointers like pi32v2, so these are the 32-bit instance sizes |

Tested in headless Chromium 153 (Playwright 1.63, on aeon) only: it powers on, a
three-note chord reaches the output (RMS 0.047), three key LEDs light, FX,
SELECT and ALGORITHM put Ensemble in slot 2, and a 390 px phone viewport has
no horizontal scroll [verified: `build/screenshots/report.json`]. Firefox,
Safari and real MIDI hardware are not tested.

## The panel

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

On `feature/2026-10-01@mutable-native-rates` (`b9b41a1`: Shapes at 96 kHz
and Plaits at 47,872 Hz through `fm1_resampler.h`), a trial build
(`--engines-ref`) gives the same result: 12 of 12 pass, identical to musl
and to render.js, identical to glibc but for Sophie; the module grows from
371 to 390 KB [verified, 2026-10-01].

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
natively as `fm1-sim-render`, the test harness, and could drive the real
screen later. The font is drawn for this repository (`tools/font5x9.txt`;
`tools/gen_font.py` writes `src/fm1_font.h`).

`mk/sim.mk` is read after `engines/Makefile`, so it reuses that Makefile's
source lists, flags and rules unchanged, and builds whatever engines the tree
has. The module is standalone (`-sSTANDALONE_WASM`, no imports, 8 MB fixed
memory) and about 370 KB.

### `build-on-aeon.sh`

One command; about 20 seconds once aeon has the three images (the first run
pulls them). On aeon, in containers (nothing runs on the
Mac but ssh, tar and scp; nothing is installed on aeon's host):

1. `alpine:3.22`: a static musl `fm1-render`.
2. `emscripten/emsdk:6.0.10` (`build.sh`): native `fm1-render` and
   `fm1-sim-render` with GCC 13, the screen sweep, `fm1.wasm` and
   `fm1-render.js` with Emscripten 6.0.10, `test/parity.mjs`; then, only if
   everything passed, `www/fm1.wasm` and its record `www/fm1.wasm.json`
   (hashes of the module and of the sources, the parity results).
3. `mcr.microsoft.com/playwright:v1.63.0-noble`: `test/screenshot.mjs` opens
   the page in headless Chromium, plays it and writes screenshots and a
   report to `build/screenshots/`.

Options: `--engines-ref REF` builds another commit's engines into
`build/ref-REF/` (never into `www/`); `--no-screenshot` skips step 3.
`FM1_AEON`, `FM1_REMOTE_DIR` and `FM1_SESSION` override the host, the
directory (`/home/claude/mvave-fm1/virtual`; `src/` there is the staging copy,
replaced on every run, and `playwright/` caches the Playwright package, about
20 MB) and the containers' session label.

### Tests

`tests/test_sim_web.py` runs in the normal suite (and CI): the app layer's
output equals `fm1-render`'s byte for byte for every scenario, natively; the
282-screen layout sweep; the panel against the manual's formula (octave,
transpose, reset); buttons and encoders; the page loads nothing from other
origins; the exports match; and `www/fm1.wasm` matches its record. When the
engines or `src/` change after the last build, that test warns: rebuild with
`build-on-aeon.sh`.

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
- **Eight buttons** do nothing yet. The sequencer (docs/13) can be wired to
  PLAY/STOP, REC and SEQ when its core lands.
- **MIDI in only**; the virtual FM-1 sends nothing.
- **Encoders without acceleration**; a float parameter moves a hundredth of
  its range per detent.

## Before publishing

The module contains Six-Op FM's 96 patch names, which include third-party
trademarks and a person's name (engines/README.md, "Open questions"). Fine
for a personal page; rename or drop them before the page is shared widely.
Every engine is MIT (Mutable Instruments, Schwung modules); the credits are
in each engine's `credits` string and in the page's footer.
