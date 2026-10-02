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
| Screen | The firmware draws a 240 × 240 RGB565 frame buffer (stock's layout: a top bar with the sound, the mode's content, a bottom bar with page and mode, one-second popups); the page only copies it to a canvas. HOME's oscilloscope strip scales the trace to its window's peak (at most ×16, so quiet noise stays flat). 1,084 screens pass a layout check: nothing off screen, no text cut short, no more than 96 logged boxes, and no two labels and no label and bar closer than 4 px [verified: `fm1-sim-render --screens`]. They are every page of every engine and effect at defaults, minima, maxima and every list entry, the global page, every popup including the refusals, SEL outside FX mode and an emptied slot (335 screens), and, with the lab switch on, the sequencer's Track view (below) in 480 states and modulation's pages and marks (below) in 269 |
| Panel | The 27 keys, 14 buttons, MASTER and the seven encoders, with their LEDs, laid out to scale (below) |
| Input | Mouse and touch (lower on a key plays louder; drag or scroll an encoder), the computer keyboard (`A W S E D R F G Y H U J K O L P ; [ '` play F3 to B4, `Z`/`X` are OCT−/OCT+, arrows turn SELECT and PRESETS, `-`/`=` ALGORITHM, `Esc` releases every note), and Web MIDI (notes, pitch bend ±2 semitones, CC 7 volume, CC 123 all notes off). A held key or button is released whatever modifiers are down by then (Cmd lets go of every held key, since macOS drops those keyups), and leaving the window or tab releases every key, button and pointer. Scrolling over an encoder turns it one detent for the first wheel event of a gesture, then one per 60 px of vertical scroll; horizontal scrolling turns nothing |
| Look | Lunar Modulator's: the Rosé Pine Moon palette ([rosepinetheme.com](https://rosepinetheme.com/palette/), MIT; the hex values checked against rose-pine/palette and rose-pine/neovim on 2026-10-01 [verified]) as CSS custom properties, one dark theme, and the firmware's screen in the same colours (`src/fm1_app.c`); Audiowide (Astigmatic, SIL OFL 1.1) for the name, the tagline and headings, from the page's own `fonts/`, unmodified ([fonts/README.md](www/fonts/README.md)); Exo 2 (Natanael Gama, SIL OFL 1.1) for small text, also from `fonts/`, unmodified. Text contrast is at least 4.8:1 against its background on the page, disabled controls aside (WCAG AA asks 4.5:1; secondary text on a surface is subtle with a tenth of text mixed in, since subtle alone is 4.46:1 there) and at least 4.78:1 on the screen after RGB565 rounding [verified: computed from the palette] |
| Info | GLO shows the sample rate, block size, the chain's RAM against the 379 KB the stock layout leaves free (docs/11 §2), voices, octave and transpose. WebAssembly has 4-byte pointers like pi32v2, so these are the 32-bit instance sizes. The RAM figure includes the sequencer: its instance (31,880 B at 8 tracks, the same at 32 and 64 bits) and its 3,072-byte event buffer |
| Sequencer | The app hosts the sequencer core (engines/seq.md) through the shared host bridge (`engines/include/fm1_seq_host.h`), exactly as `fm1-render` does: script lines and commands at block starts, each block's events, and the sound's render split at every note and lock of a track routed to it. 8 tracks (owner decision O3, 2026-10-02), a 256-event buffer, one pending command record, and the event-room rule: an op goes in only while 201 events of room are free, otherwise it waits a block, so no note-off is ever lost. The harness and the parity test play verb scripts and `movy1` sets through it; every one of the 34 Movy oracle scripts plays through the app byte for byte as through `fm1-render` at 64-frame blocks [verified: `tests/test_sim_seq.py`]. On the panel only with the lab switch (below): PLAY/STOP, SEQ mode's Track view and a demo pattern (docs/15 stage S3) |

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
AudioContext. With the lab switch (`?lab`) [verified: the same report,
2026-10-02]: PLAY/STOP plays the demo pattern (RMS 0.025, 52 ms after the
press) and lights its LED, the status line reads "Sequencer: 120.00 BPM,
playing.", SEQ shows the Track view with the SEQ LED on and the white
keys' lights moving with the playhead, Space stops and starts the
transport, HOME leaves SEQ mode, and `#lab` turns the switch on too;
without it Space sends nothing, PLAY/STOP and SEQ stay stubs and the page
stays silent. By hand in Chromium 152 on macOS (the Claude desktop app's
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
| ENV, LFO, EDIT | envelope, LFO and edit pages | a popup: not in the simulator yet; with the lab switch, modulation (below) |
| SAVE, ARP, REC | | a popup: not in the simulator yet |
| SEQ, PLAY/STOP | the sequencer: its view and the transport | a popup: not in the simulator yet; with the lab switch, SEQ mode and the transport (below) |

## The lab switch

The sequencer's panel controls arrive stage by stage (docs/15, S3 onward),
and so does modulation (docs/16, MG3 onward). Every merge to main
publishes the page, so until step entry and recording work (stages S5 and
S6) the public page hides them (the owner's decision O24, 2026-10-02), and
modulation with them. An address with a `lab` query parameter or hash
turns them on, for development and review:

```
http://localhost:8000/?lab        http://localhost:8000/#lab
```

`app.js` reads the address once at load and passes the switch to the
worklet, which calls `fm1w_set_lab(1)` before `fm1w_default_chain()`; in
the app layer `fm1_app_set_lab` is the one switch, and `fm1_app_init`
leaves it off. The harness takes `--lab`. Nothing else changes between the
two: the engines, the sequencer and the module are the same. With the
switch off no modulation runtime exists and the page is what it was before
modulation came: every one of the 335 screens the layout sweep draws with
the switch off is byte for byte what main's harness draws [verified
2026-10-02, every screen written out by both builds], and the
renders without the switch go the same way as before (no hook, no split).

| | Off (the public page) | On |
| --- | --- | --- |
| SEQ | "not in the simulator yet" | SEQ mode, the Track view; HOME, FX and GLO leave it; SEQ inside it stays (Session comes in S9); the keys still play the sound |
| LFO, ENV | "not in the simulator yet" | a tap opens RACK at the LFOs or the Envelopes, a page per module; held while a knob turns on HOME, FX or RACK, a cable from the selected one to that knob's parameter (below) |
| EDIT | "not in the simulator yet" | MATRIX, the 32 cables; SEL there opens CHAIN; EDIT again goes HOME |
| Modulation | none | a runtime (`engines/mod`) on the sound, both effects and the host, from the default rack: LFO1, LFO2, ENV1, ENV2 and Chance, with KEY cabled into both envelopes' GATE so they follow every note |
| PLAY/STOP | "not in the simulator yet" | `play` or `stop`, in every mode, as a typed command (`src/fm1_seq_ui.c`, then `fm1_app_seq_cmd` under the event-room rule) |
| REC | "not in the simulator yet" | the same (S5) |
| Space | nothing new (the page scrolls) | PLAY/STOP, unless a button has focus (owner decision O19) |
| Start | Macro and Plate, the sequencer empty | the same, and the demo pattern: one bar on track 1 in C minor at 120 BPM (`fm1_app_demo_pattern`, O4) |
| LEDs | as before | SEQ in SEQ mode, PLAY/STOP while the transport runs; in SEQ mode the white keys show the bar's steps, lit for a note, the playhead's inverted. Sequencer notes light no key outside SEQ mode (O6). LFO or ENV while RACK shows one of theirs, EDIT in MATRIX and CHAIN, SEL in CHAIN and while RACK holds a module |
| Status line, help | as before | the tempo and the transport (posted by the worklet only when they change); "Sequencer (lab)" and "Modulation (lab)" entries in the help, and SAVE, ARP and REC in the stub list |
| RAM figure | the chain and the sequencer | the same and the modulation runtime, 20,016 B (`fm1_mod_size()`) |

Tests and parity runs never load the demo pattern: only the browser's start
chain does (`fm1-sim-render --lab --start` plays that chain natively).

**The Track view** (docs/15 §4; `src/fm1_seq_view.c`), between the title
and bottom bars:

- the status line: the tempo, and PLAY or STOP;
- the grid: the focused track's first four bars, 16 steps a row, one
  logged graphic: a filled cell for a note, an outline outside the loop
  (a note there a dim bar), the playhead inverted;
- the knob strip: four bars for KNOB1–4 on the current sound page, no text
  (O23, option b); the knob being turned is drawn brighter;
- the hint line: that knob's name and value, as HOME's rows show them, for
  two seconds or until SELECT or PRESETS moves on; otherwise the sound's
  model in gold, as HOME's first line;
- the bottom bar: `1/3 Seq T1` (sound page, mode, track) and the RAM figure.

SELECT pages through the sound and KNOB1–4 turn it, as in HOME. The UI
state (`fm1_seq_ui_t`) is 64 bytes against its 1,024-byte bound; it reads
the transport and the focused clip once per block, and its notes again only
after the sequencer had input [verified: `fm1-sim-render --sizes`].

**Modulation** (docs/16 §5, stage MG3; `src/fm1_mod_ui.c` has the pages'
logic, `src/fm1_mod_view.c` draws them). The app hosts the runtime on the
sequencer's bridge exactly as `fm1-render --mod` does: a knob, a lock or
the bend moves a parameter's base, the runtime adds what its cables give,
each effect renders split at its own writes, and HOST AMP is applied before
the limiter. Modules are named by kind and order (LFO1, LFO2, ENV1, ENV2,
CHN1), as the owner names them.

- **LFO, ENV** (a tap): RACK at the LFO or Envelope last shown (LFO1 and
  ENV1 at first); another tap there steps to the next one of that kind.
  RACK shows a module a page at a time:
  - the rack: eight cells, each filled to its module's first output, the
    one shown outlined, an empty position hollow;
  - under it `3 ENV1 >2 <1 ~1`: the position, the module, its cables out
    and in, and those that run a tick late;
  - four parameter rows on KNOB1–4, as HOME's; the bottom bar `1/2 Mod3`.
  SELECT walks every position and page; ALGORITHM opens the kind picker
  (Empty, LFO, Envelope, Chance), which commits a second after its last
  turn or at once when another control is used. Changing a kind switches
  off the cables that touch the module and remembers them: changing it
  back switches them on again, those whose other end is still there.
  SEL grabs the module (SEL lit, the line starred) so SELECT moves it.
- **Hold LFO or ENV and turn KNOB1–4** on HOME, FX or RACK: a cable from
  the selected LFO or Envelope (its first output) to that knob's
  parameter, its amount following the turn, 1 % a detent; turning again
  adjusts the same cable. The popup says `LFO1 > Timbre` and the amount.
  A parameter that takes no modulation (Macro's Model) says so. Released
  without a turn, the button is a tap.
- **EDIT**: MATRIX, seven of the 32 slots as rows of 19 characters, the
  selected one inverted, and a hint line:
  ```
   LFO1  >Timbre  +40     state, source, > (or ~ a tick late), target, amount
  -SEQ8  >F2PngP -100     - off, ! refused, v per voice (not made yet)
  ```
  SELECT moves the selection. Page A: KNOB1 the source (`--` first, which
  empties the slot), KNOB2 the target through a picker (prev, current and
  next in full, `Snd Timbre`, `FX1 Mix`, `Host Amp`, `ENV1 Attack`,
  `ENV1 Gate`; ALGORITHM jumps between groups while it is open; it commits
  as the kind picker does), KNOB3 the amount, KNOB4 the offset, 1 % a
  detent. ALGORITHM otherwise turns to page B: KNOB1 VIA, KNOB2 the curve,
  KNOB3 the polarity, KNOB4 on or off. A new cable starts on, at 0 %, from
  the selected LFO unless KNOB1 chose a source first. The hint line names
  the field last turned for two seconds, else the slot's target.
- **SEL in MATRIX**: CHAIN, the longest path through the selected cable,
  node and cable lines alternating (`LFO2 Wrap  +1`, `+100 >ENV1 Gate`),
  the selected cable in the accent colour, `+N` for a node's other cables
  and `~` for one a tick late; a refused cable (`!`) is not followed. SELECT steps to the next cable; SEL goes
  back to MATRIX.
- **On every parameter page** (HOME, FX, RACK) a parameter that cables
  reach shows its short label, a gold diamond after it, a gold bracket of
  plus or minus the cables' depth round the base on its bar, and a red tick
  at the value it has now. The rows keep the 4 px gaps.

Destinations are a slot's unit code and a uid: 0 the sound, 1 and 2 the
effect slots, 3 the host, 8–15 a rack position. `fm1_mod_ui.h` keeps the
code space for the sound units 1–4, their inserts and the master slots that
come with several sounds, and every cable here is global, while the slot
record keeps the per-voice flag for the next stage (docs/16 MG3, "As
built").

**Gesture traces and two-step parity** (docs/15 §6.3). `fm1-sim-render
--panel FILE` reads panel input, one `--key`, `--button` or `--turn` per
line. `--log-cmds FILE.verbs` writes what reached the sequencer, the
script's lines and the panel's typed commands (`fm1_seq_cmd_format`,
`engines/host/seq_script.h`) at the blocks they led, under a header with
the run's length; next to it, `FILE.args` lists the arguments `fm1-render`
needs to replay it, one per line: the engine and effects, and a
`--param-at` at mid-block for every sound parameter the panel turned.
`fm1-render --cmd FILE.verbs` with those arguments renders the same bytes.
A run the replay cannot follow (a new sound or effect from the panel, an
effect's parameter, a key played, MASTER below full, a modulation edit no
script line can say) says `"replayable":0`. `--format-check` writes and
reads back every verb.

With modulation running, `--log-cmds` also writes `FILE.mod`: the
runtime's whole state before the first block (seed, rack, the bases that
differ from their defaults, every cable) and every edit after it, as
`@<block start>` lines of `fm1-render --mod` (`engines/host/mod_script.h`),
and the sidecar ends with `--mod` and that file, so the replay modulates
exactly as the panel did. `--mod FILE` plays a modulation script as
`fm1-render --mod` does (a new runtime with the file's seed after the
chain, untimed lines first, `@FRAME` lines at the first block starting
there), with or without the lab switch. `--mod-format-check` writes 300
random racks, bases and cable tables whole and applies random edits line
by line (cables, kinds with their switch-off and restore, bases, moves),
each read back by `mod_script.c` into a second runtime: the same state
every time [verified: about 25,000 lines, 0 refused].

## Parity: does the browser sound like the native engines?

`build-on-aeon.sh` renders 26 scenarios (`test/scenarios.json`) four ways
and compares the 16-bit output sample by sample [verified:
`www/fm1.wasm.json`, 2026-10-02]. Eighteen are note scripts: every engine
and effect, pitch bend, parameter changes mid-note, more notes than voices,
44,100 Hz, the low-pass gate. Five play sequencer verb scripts
(`test/seq/`, `fm1-render --cmd`): Test Sine's Volume under float locks
with a stop that sends the lanes back to their bases; two Six-Op tracks
with swing and a clip at twice the speed; locks on Six-Op's Patch, a list;
Capture committed while playing; and a stopped Capture whose tempo is then
changed with `capsel`. One is played on the panel with the lab switch on
(`seq/panel-play-stop.panel`): SEQ, PLAY/STOP in SEQ mode and in HOME, and
knob turns on two sound pages, ending in the Track view. Two modulate
(`test/mod/`, docs/16 MG3): `mod-macro-routes` plays a `--mod` script with
cables into the sound, both effects, HOST PITCH and AMP, a chain of
modules, a gate cable at 70 % and timed edits (the module takes it through
`fm1w_mod_reset` and `fm1w_mod_text`); `mod-panel-gestures` makes its
cables on the panel with the lab switch (the gesture on HOME and FX, knobs
in RACK, two cables from MATRIX), and its render legs replay the harness's
`.mod` log with the rest of its sidecar.

| Against | Result |
| --- | --- |
| `render.cc` compiled to WebAssembly (Node) | identical in all 26: the app layer adds nothing |
| native `fm1-render`, GCC with musl (static, Alpine) | identical in all 26: the compiler adds nothing |
| native `fm1-render`, GCC with glibc | identical in 23. Sophie differs (23,286 and 694 samples, up to 4,082 and 12,330 LSB), and Fold within 1 LSB (19 samples) |

The sequencer scenarios add three rules. Every leg applies a script line at
the first 64-frame block starting at or after its frame, after the notes;
the module drops no sequencer event (`fm1w_seq_dropped`); and `parity.mjs`,
which reads the script itself to feed the module, first checks that it
applied the same lines at the same blocks as the native harness logged
(`fm1-sim-render --log-cmds`), so a third reader of the script format
cannot drift unnoticed. The stopped Capture is marked `libm_sensitive`:
its tempo search scores candidates with `logf`, so glibc could choose
differently from musl; in this build it did not.

The panel scenario is two-step parity in WebAssembly (docs/15 §6.3): the
native harness plays it first with `--panel` and `--log-cmds`, the glibc,
js and musl legs replay its log with the arguments of its sidecar, and the
module presses the same buttons and turns the same encoders
(`fm1w_button`, `fm1w_encoder`). Before audio counts, the script lines the
module applied must equal the harness's log less the panel's commands
(which the harness lists, `seq_ui_cmds`), and the harness must call the
run replayable; the screens are compared as for every scenario, here the
Track view with the playhead running and the hint line.

The Sophie difference is libm, not the port: Sophie calls `sinf`, `expf`,
`exp2f` and `powf` per sample and per note, its feedback FM amplifies their
last-bit differences, and glibc and musl (Emscripten's C library) round some
of them differently. A native build against musl renders Sophie byte for byte
like the browser. The same holds for the firmware: whatever libm JieLi's
toolchain ships will decide Sophie's last bits there too.

The screen the browser module draws matches the native harness's pixel for
pixel, except the RAM figure in the bottom bar, which is the 32-bit one.

The module links the sequencer core, its host bridge and, since stage S3,
its panel UI and Track view, and since docs/16 MG3 the modulation runtime,
its kinds, its script reader (`host/mod_script.c`: snprintf and strtod,
no files) and modulation's pages: 26 of 26 scenarios pass, identical to
musl and to render.js, and it imports nothing; it is 557,311 bytes, up from
464,688 before MG3, 459,122 before S3 and 391 KB before the sequencer
[verified, 2026-10-02, `www/fm1.wasm.json`].

The sequencer's own cost in WebAssembly, measured with `fm1-render.js` under
Node 24.19 in the emsdk container on aeon: tools/seq_bench.py's burst (8
tracks of 12-note chords on every step and 8 locked lanes, 300 BPM, up to
193 events in a block) takes 5.7–10.2 µs per 64-frame block for commands and
advance (three runs; the first includes the JIT's warm-up), against 1.7–1.8
µs for native GCC on the same host and the 1,451 µs a block lasts
[verified, 2026-10-02]. Phones are not measured. That burst is also the one
load that 256 events do not hold whole: the core keeps room for the note-off
of every sounding gate (64) beside a block's events, so a 193-event block
needs 257, and at 256 the burst drops 400 of its 76,800 note-ons (whole,
with nothing left hanging) [verified: `fm1-render --events`]. No oracle
script puts more than 7 events in a block.

## How it is built

```
www/app.js        page: panel (SVG), input, screen canvas, MIDI    main thread
   | port messages (events at block boundaries) / screen and LED updates
www/worklet.js    AudioWorkletProcessor: 2 x 64-frame blocks per quantum
www/fm1-wasm.mjs  loader shared with the Node test (no Emscripten runtime)
www/fm1.wasm      src/fm1_web.c   flat exports (fm1w_*)
                  src/fm1_app.c   the "firmware": chain, panel logic, screen,
                                  the sequencer's host
                  src/fm1_seq_ui.c    the sequencer's panel UI: edges in,
                                      typed commands out (lab switch)
                  src/fm1_seq_view.c  its screens: the Track view
                  src/fm1_mod_ui.c    modulation's pages and gesture: edges
                                      in, runtime edits and script lines
                                      out (lab switch)
                  src/fm1_mod_view.c  their screens and the routed marks
                  src/fm1_tft.c   240 x 240 RGB565 frame buffer, 5 x 9 font
                  engines/        every engine, effect and the bus limiter,
                                  the sequencer core and its host bridge,
                                  the modulation runtime and its kinds
```

`src/` is C99 with no heap: instance memory lives in fixed arenas inside
`fm1_app_t`. Nothing in it is browser-specific, so the same app layer builds
natively as `fm1-sim-render`, the test harness. Its panel logic and drawing
code are meant to carry over to the firmware, but not `fm1_app_t` as it
stands: it is 1,228,416 bytes (1 MiB of fixed arenas, a 115,200-byte full
frame buffer, the sequencer's 32 KiB arena and 3 KiB event buffer, and
modulation's 20,480 B runtime and 2,304 B of a block's writes; clang,
64-bit), against the FM-1's 578 KB of SRAM and
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
memory). It links the sequencer core and bridge (`SEQ_OBJ`: C99, no heap,
no stdio) and the modulation runtime (`MODC_OBJ`, `MOD_OBJ`: no heap, no
stdio, no libm) with its script reader (`MOD_SCRIPT_OBJ`), but not the
verb script reader (`host/seq_script.c`), which allocates and uses stdio;
only the native harness links that.

The sequencer's text comes in through `fm1w_text_buf()`, a 64 KiB buffer
(the largest `movy1` set an 8-track instance exports is 53,208 B), and
`fm1w_seq_text(len)`, which applies one script line at the coming block's
start and returns the bytes it took. `fm1w_seq_reset(tracks)` makes a new
instance and applies the default route (track 0 plays the sound, as in
`fm1-render`); `fm1w_seq_dropped()` reports any event that did not fit.
`fm1w_set_lab(on)` is the lab switch, and `fm1w_seq_info()` returns eight
32-bit words for the status line: playing, the tempo in hundredths of a
BPM, recording, the watched track, counting in, following an external
clock, and the master tick's two halves. `fm1w_mod_reset(seed)` makes a new,
empty modulation runtime and `fm1w_mod_text(len)` applies one line of
`fm1-render --mod` from the text buffer (1, or 0 for a bad line); the
parity test plays a scenario's modulation through them.

`fm1_panel.h` holds the panel's buttons, encoders and modes, which the app
and the sequencer's UI share; `fm1_look.h` the screen's palette, geometry
and the drawing helpers every mode uses.

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
output equals `fm1-render`'s byte for byte for every scenario, natively, and
for the sequencer scenarios so do the event logs; the sequencer's sizes
against its arena and the 36,864 B budget; the event-room rule on script
lines and on typed commands (a stop, a play and a restart at full load in
one gap, and 128 lane bases after a stop, which `fm1-render --events 256`
drops and the app holds back), with nothing dropped or left sounding; routes
(the default route, `--route`, `route` verbs and a set's own `rt` lines)
as in `fm1-render`; no note left hanging after a reset, an import or a
change of sound; the 1,084-screen layout sweep; the panel against the manual's formula (octave,
transpose, reset); buttons and encoders; with the lab switch, PLAY/STOP's
LED while playing, SEQ mode, the white keys following the playhead in SEQ
mode (eight points across two bars), HOME's key LEDs unchanged and the
Track view's knob hint cleared by a new sound; an effect slot emptied on its
second page; sounds that refuse a 48 kHz host stepped over and the previous
one kept; the page loads nothing from other origins; the exports match; and
`www/fm1.wasm` matches its record. The record carries two source hashes
(`tools/source_hash.py`): engines/ (less Markdown) and sim/web's own inputs
(`src/`, `mk/`, `build.sh`, the parity test, its scenarios and their
sequencer and modulation scripts in `test/seq/` and `test/mod/`, the
harness, the loader), which since the module links the sequencer include
`engines/seq/` and `engines/include/fm1_seq*.h` too, and since it links
modulation `engines/mod/` (less its Markdown), `engines/include/fm1_mod*.h`
and `engines/host/mod_script.*`. When sim/web's inputs have changed since the last
build, the test fails in CI (`CI=true`) and warns locally; when only the
engines have, it warns, so engine work elsewhere does not need aeon.
Rebuild with `build-on-aeon.sh` before publishing the page or merging a
change to the simulator.

`tests/test_sim_seq.py` plays all 34 Movy oracle scripts through the app
with Test Sine, and six with Macro, against `fm1-render --frames 64`: event
logs and WAVs byte-identical, nothing dropped.

`tests/test_seq_ui.py` checks the sequencer on the panel: five golden
gesture traces (`tests/fixtures/seq-ui/`: SEQ in and out, PLAY/STOP from
HOME, FX and SEQ mode, two presses in one block), each logging its golden
script and replaying through `fm1-render` byte for byte, with the mode and
button LEDs each ends in; the parity scenario's own trace; every verb
through `fm1_seq_cmd_format` and back; the demo pattern only on the start
chain with the switch on; the switch off changing nothing; a sound changed
from the panel marked not replayable; and the UI state's size.

`tests/test_sim_mod.py` checks modulation on the panel (docs/16 MG3): the
switch off keeping ENV, LFO and EDIT as stubs and nothing running; the
default rack and its two cables; LFO, ENV, EDIT and SEL and their LEDs;
the gesture on HOME, FX and RACK, and its refusal; rule M1 on a routed
knob; every MATRIX field; a kind change switching cables off and back on,
also after the other kind got cables of its own; a hold with any turn
being no tap; a new MATRIX cable starting from the selected LFO; CHAIN
not running on through a refused cable; the envelopes opening for notes
from the sequencer, MIDI in and the keys, and the default cable
re-patched; six golden gesture traces (`tests/fixtures/mod-ui/`, one of
them knob turns on routed parameters) whose `.mod` logs replay through
`fm1-render --mod` byte for byte; and `--mod-format-check`.

CI also runs the four files in its 32-bit job (`-m32`, like pi32v2's
pointers) and under ASan + UBSan, through the variables below.

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
- **Eight buttons** do nothing on the public page yet. With the lab switch
  SEQ and PLAY/STOP work (docs/15 stage S3), and the Track view only shows
  a pattern: steps are entered on the panel from S4, REC comes in S5; ENV,
  LFO and EDIT open modulation's pages (docs/16 MG3), whose envelopes and
  LFOs are global until the per-voice stage.
  Compat mode (Movy's exact behaviour) stays on `fm1-seq` and
  `fm1-render`; the app runs the FM-1's default mode.
- **MIDI in only**; the virtual FM-1 sends nothing.
- **Encoders without acceleration**; a float parameter moves a hundredth of
  its range per detent.
- **The screen is drawn on the audio thread**, as UI and the effect chain
  share cpu0 on the stock FM-1 (its voices render on cpu1, docs/11 §2): a
  full redraw at most every ~33 ms while sound plays.
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
