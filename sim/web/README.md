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
| Engines | Every registered sound engine and effect (engines/README.md): Macro, Shapes, Macro Heavy, Six-Op FM, Sophie, Drums, Test Sine; Plate, Ensemble, Diffuse, PSX Verb, Crush, Fold, Drive, Echo, Filter, Comb, Comp, Limiter, DJ Filter, Tilt, Master Sat, Isolator, EQ, Room, Hall, Gate, Test Gain, Test Ext. Up to four sounds with two inserts and a level each, mixed into two effect slots as the master bus, then the host's bus limiter, as `fm1-render --slots` runs them; one sound with no insert at full level renders as `fm1-render`'s one engine does, to the bit (below, "Multi-sound") |
| Audio | An AudioWorklet renders each 128-frame quantum as two 64-frame host blocks. The AudioContext asks for 44,118 Hz, then 44,100 Hz (a context that comes back faster than 47,872 Hz is closed and the next rate tried), and only then takes the device's own rate. Headless Chromium ran at 44,118 Hz [verified]. Macro, Macro Heavy, Six-Op and Drums run Plaits at 47,872 Hz and resample to the host (engines/resampler.md), so they refuse a faster one: there the firmware starts with Shapes, PRESETS steps over the four, a refused choice puts the previous engine back, and the screen and status line say why [verified natively at 48 and 96 kHz: `tests/test_sim_web.py`] |
| Screen | The firmware draws a 240 × 240 RGB565 frame buffer (stock's layout: a top bar with the sound, the mode's content, a bottom bar with page and mode, one-second popups); the page only copies it to a canvas. A list popup (PRESETS, ALGORITHM, a knob on a list parameter of five entries or more, SHIFT + PRESETS, SHIFT + 16's quantize, the kind and destination pickers, Capture's tempos, the ARP presets) shows the list's title in the context colour, the chosen entry's place (`34/96`) and as many entries as its face holds (`fm1_list_rows`, `src/fm1_panel.h`: MAIN 6 of 18 characters, MID 8 of 27, SMALL 9 of 36; the long lists are MID, the short ones MAIN, which shows them whole), by their full names (`fm1_look_full_name`), the chosen one on the selection bar, on the third row where it can be (`fm1_list_first`), and a triangle above or below the entries where the list goes on (three lines until 2026-10-06, then six in MAIN; the audit note's "Built" section has the table). A confirmation that fits one line is a banner over the page's bottom 28 px (MAIN up to 18 characters, MID up to 27); a refusal keeps the full popup, its reason in the refusal colour. HOME's oscilloscope strip scales the trace to its window's peak (at most ×16, so quiet noise stays flat) and starts under the page's last row. 3,543 screens pass a layout check, every text box in one of the three faces at its height: nothing off screen, no text cut short, no more than 96 logged boxes, and no two labels and no label and bar closer than 4 px [verified: `fm1-sim-render --screens`, 2026-10-06, 3,543 with glide's modes on their own page (Shapes, Six-Op FM and FM6 have a third page), Drums' fourth page with Choke and Kit Decay, and the Voice Mode keys' popups and LEDs; 3,408 with glide's pages and voice modes; 3,336 with the ARP pages (134 of them with their knobs' lists) and with RACK's line in SMALL; 3,204 before them, with the knobs' lists of every sound and effect, banners over HOME, FX, GLO and MATRIX and FX mode's chip on every slot; 3,165 with per-voice modulation; 40 of them FM6's user bank (every user slot with a 10-character name, the ALGORITHM popup, SEQ mode and the load popups); 3,104 without them, with Squash and Transient; 2,695 before every list popup at every entry (2,470 recorded here on 2026-10-05), 2,338 before Drums, 2,299 before Comb and Test Ext arrived with engine API v3, which the counts below predate]. They are every page of every engine (HOME) and of every effect on both master slots (M1, M2) at defaults, minima, maxima and every list entry, the global page, every popup including the refusals, the SAVE stub and an emptied slot (600 screens), every ARP page at its defaults, extremes and list entries with its popups and knobs' lists (134), the sequencer's Track view, Step pages, record and Capture (below) in 618 states, its tracks, mute and Set, Clip and Track pages (S6) in 69, multi-sound's FX chain, Mix page, titles, popups and RAM meter in 216 (every effect as an insert, now twenty), parameter locks (S8) in 55, modulation's pages and marks (below) in 741, and Drums' pages and its sound in the others' sweeps in 132 more; since 2026-10-06 every list popup at every entry, each window checked (345: ALGORITHM through every sound's list, Six-Op FM's 96 patches the longest, PRESETS through the engines, ALGORITHM in FX mode through the effects, and the destination picker through every destination; the kind picker's 17 were already there). Until 2026-10-05 the sweep drew two sets, with the lab switch off and on (2,325 screens; 2,366 with Comb and Test Ext) |
| Panel | The 27 keys, 14 buttons, MASTER and the seven encoders, with their LEDs, laid out to scale (below) |
| Input | Mouse and touch (lower on a key plays louder; drag or scroll an encoder), the computer keyboard (`A W S E D R F G Y H U J K O L P ; [ '` play F3 to B4, `Z`/`X` are OCT−/OCT+, arrows turn SELECT and PRESETS, `-`/`=` ALGORITHM, `Esc` releases every note), and Web MIDI (notes, pitch bend ±2 semitones, CC 7 volume, CC 123 all notes off). A held key or button is released whatever modifiers are down by then (Cmd lets go of every held key, since macOS drops those keyups), and leaving the window or tab releases every key, button and pointer. Scrolling over an encoder turns it one detent for the first wheel event of a gesture, then one per 60 px of vertical scroll; horizontal scrolling turns nothing |
| Look | Lunar Modulator's: the Rosé Pine Moon palette ([rosepinetheme.com](https://rosepinetheme.com/palette/), MIT; the hex values checked against rose-pine/palette and rose-pine/neovim on 2026-10-01 [verified]) and, since 2026-10-06, four hues of the project's own for the sounds (nebula, nova, aurora and comet, derived in OKLCH at Moon's accent lightness and chroma), as CSS custom properties, one dark theme, and the firmware's screen in the same colours (`src/fm1_look.h`), with one meaning per colour on both: [PALETTE.md](PALETTE.md) has the semantic colour map, the derivation and the figures, and `tools/palette.py` checks the two files against it [verified: `tests/test_sim_palette.py`]; Audiowide (Astigmatic, SIL OFL 1.1) for the name, the tagline and headings, from the page's own `fonts/`, unmodified ([fonts/README.md](www/fonts/README.md)); Exo 2 (Natanael Gama, SIL OFL 1.1) for small text, also from `fonts/`, unmodified. On the screen, the project's own 5×9 at ×2 and, for dense screens, Spleen 8×16 and 6×12 by Frederic Cambus (BSD 2-Clause; [third_party/spleen/](third_party/spleen/UPSTREAM.md), its licence served as `fonts/spleen/LICENSE`; below, "Text faces"). Text contrast is at least 4.8:1 against its background on the page, disabled controls aside (WCAG AA asks 4.5:1; secondary text on a surface is subtle with a tenth of text mixed in, since subtle alone is 4.46:1 there) and at least 4.78:1 on the screen after RGB565 rounding [verified: computed from the palette] |
| Info | GLO shows the sample rate, block size, the chain's RAM against the 379 KB the stock layout leaves free (docs/11 §2), voices, octave and transpose. WebAssembly has 4-byte pointers like pi32v2, so these are the 32-bit instance sizes. The RAM figure includes the sequencer: its instance (31,880 B at 8 tracks, the same at 32 and 64 bits) and its 3,264-byte event buffer (3,072 B, 256 events, until stage S6, so a chain's figure can read 1K more than before: 4 of the 54 one-effect chains do). It is the RAM meter's figure (below), which also counts the sequencer's pending record, UI bound and click voice and the modulation runtime |
| Sequencer | The app hosts the sequencer core (engines/seq.md) through the shared host bridge (`engines/include/fm1_seq_host.h`), exactly as `fm1-render` does: script lines and commands at block starts, each block's events, and the sound's render split at every note and lock of a track routed to it. 8 tracks (owner decision O3, 2026-10-02), a 272-event buffer (256 until stage S6), one pending command record, and the event-room rule: an op goes in only while 201 events of room are free, otherwise it waits a block, so no note-off is ever lost. The harness and the parity test play verb scripts and `movy1` sets through it; every one of the 34 Movy oracle scripts plays through the app byte for byte as through `fm1-render` at 64-frame blocks [verified: `tests/test_sim_seq.py`]. On the panel (below): PLAY/STOP, SEQ mode's Track view and a demo pattern (docs/15 stage S3), step entry: the white keys as steps, the Step pages, SHIFT and bar paging (S4), record, step record and Capture (S5), tracks, mute, the Set, Clip and Track pages and the metronome's click (S6), and parameter locks from KNOB1–4 (S8) |

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
AudioContext. The sequencer, multi-sound and modulation [verified: the
same report, 2026-10-05]: the help lists them, PLAY/STOP plays the demo
pattern (RMS 0.025, 52 ms after the press) and lights its LED, the status
line reads "Sequencer: 120 BPM, playing." (the screen's tempo format since
2026-10-06; "120.00 BPM" before), SEQ shows the Track view
with the SEQ LED on and the white keys' lights moving with the playhead,
Space stops and starts the transport, HOME leaves SEQ mode; REC in SEQ mode
while playing overdubs at once (`recording` true, its LED lit) and REC
again stops; two keys played in HOME make REC blink, and Shift (SHIFT) +
REC captures them, after which REC stays dark; SHIFT + PRESETS makes Sound
2 current and the Sound dropdown follows; LFO opens RACK and EDIT MATRIX;
and an old `?lab#lab` address opens the same page, whose Space plays the
demo pattern. By hand in Chromium 152 on macOS (the Claude desktop app's
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
| Keys | key position + 53 + 12 × octave + transpose: F3–G5 at rest | the same; with a pad kit as the current sound (Sophie, Drums: an engine with `pad_count`, engines/README.md "Pad kits"), the 16 white keys play its pads 1–16 at any octave and the black keys nothing; step record and SHIFT's pitches on held steps enter the note the key plays (the pad), not 53 + key, and a key lights while the note it plays sounds |
| MONO, POLY (C#5, D#5) with SHIFT | labelled for stock's voice modes; its gesture for them is not recorded [inferred] | outside SEQ mode, SHIFT (SEL held) with MONO sets the current sound's Voice Mode to Mono, and on Mono to Legato (and back); with POLY to Poly (owner, 2026-10-06; engines/README.md "Glide and voice modes"). The key plays nothing; the change goes in as a knob turn would (the base under any cable, the lanes' bases follow), with a popup naming the mode; while SHIFT is held MONO lights on Mono or Legato and POLY on Poly. A sound without Voice Mode (Drums, Sophie, Test Sine) says so. In SEQ mode they stay the track keys |
| OCT− / OCT+ | octave −3..+3; both together reset octave and transpose; hold one and turn ALGORITHM to transpose ±12; LED off / slow / fast / solid for 0 / 1 / 2 / 3 | the same |
| MASTER | volume (a potentiometer) | output gain after the limiter, popup "Volume N" |
| SELECT | page within the mode; in FX mode, the effect slot | the same, for the engine's pages and FX mode's five slots (In1, In2, Mix, M1, M2) |
| PRESETS | the 128 presets | the current sound's engine, with a list popup; with SEL held, the current sound |
| ALGORITHM | the FM algorithm | the engine's first list parameter (Model, Shape, Patch or Pad); in FX mode, the effect in the selected slot |
| KNOB1–4 | the four parameters on the bottom bar | the four parameters of the page, shown as rows with bars |
| FX, SEL | effect chain mode; SEL grabs a slot so SELECT reorders it | the same: the current sound's two inserts, the Mix page and the two master slots |
| GLO | global settings | the global page above |
| HOME | home (oscilloscope) | home: the sound's page, with an oscilloscope strip |
| SAVE | | a popup: not in the simulator yet |
| ARP | the arpeggiator | the arpeggiator on the current sound: a tap switches it (on, its pages open), a hold latches, SHIFT + ARP opens the pages (below, "The arpeggiator") |
| ENV, LFO, EDIT | envelope, LFO and edit pages | modulation: RACK, the gesture, MATRIX (below) |
| REC | recording | record, step record and Capture (below) |
| SEQ, PLAY/STOP | the sequencer: its view and the transport | SEQ mode and the transport (below) |
| SEL outside FX mode | (SHIFT, in the sequencer) | SHIFT, and with PRESETS the current sound (below) |

## DX7 patches: FM6's user bank

FM6 (engines/msfa.md) plays 32 built-in voices and 32 user slots. The page
loads DX7 voices into those slots from `.syx` files (the owner's request,
2026-10-06):

- **How:** **Load DX7 patches…** under the panel (a file chooser, several
  files at once), or files dropped anywhere on the page, which shows where
  to drop while files are dragged over it. The button waits for power on.
- **Nothing leaves the browser.** `app.js` reads the file
  (`File.arrayBuffer`) and posts its bytes to the AudioWorklet, which
  copies them into the module's 64 KiB text buffer and calls
  `fm1w_dx7_load(len, 1)`; no request is made [verified: the page check
  records none while files load]. Files past 64 KiB are refused in the
  page and by the module.
- **What is loaded:** single voices (VCED) and 32-voice banks (VMEM),
  several in one file, or a bank's 4,096 data bytes alone, through the
  engine's own reader (`fm1_dx7_read_sysex`, `include/fm1_dx7.h`): a bank
  fills User 1–32, single voices go to the slot after the last one loaded
  (User 1 first, and again after a bank), as `fm1-render --sysex` orders
  them. Every value is clamped to its range.
- **Checked, and said:** the result counts dumps found, wrong checksums,
  foreign messages, messages cut short, dumps of the wrong length, bytes
  outside SysEx and raw bank data (`fm1w_dx7_result`), and the status line
  turns them into words: a file that loads nothing is called empty, not
  SysEx, SysEx of another kind, cut short or the wrong length, with the two
  formats' sizes and headers; a wrong checksum loads all the same, as DX7
  editors do, and is flagged as possible damage.
- **The bank** lives in the app (`fm1_app_dx7_t`, `fm1_app.h`): it stands
  for the voices the FM-1 would keep in flash. Every FM6 sound gets it in
  its user slots when it is created and whenever a file loads
  (`fm1_dx7_set_user_voice`), and FM6's Patch list shows the voices' names
  in place of "User N" everywhere the screen names a Patch value (HOME, the
  ALGORITHM popup, SEQ mode, the lock pages, modulation's rows): the app
  points FM6's units at a copy of its engine entry whose Patch names are
  the bank's. A popup says what loaded (*Loaded 32 voices*, *User 1-32*,
  the first name) or *No DX7 voices*. Then the current sound plays the
  first voice loaded (`fm1_app_dx7_play`): it becomes FM6 if it was not,
  unless the RAM meter refuses it. The bank is not in the RAM meter; each
  FM6 instance's copy of it is, in its instance. It lasts until power off.
- **Tested:** an original test bank (`test/dx7/`, written by
  `tools/dx7_bank.py --test-bank`: LUNAR 01–32, voice k on algorithm k,
  never Yamaha's voices), as one bank and as 32 single voices.
  `tests/test_sim_web.py` runs the app's loader natively
  (`fm1-sim-render --sysex` and `--sysex-play`): every refusal and its
  reason, slot order, names on the screen, play, an FM6 made after a load,
  and the bank played as `fm1-render --sysex` plays it, byte for byte.
  `test/sysex.mjs` checks the module's export itself (18 cases, in
  `build.sh`, recorded in `fm1.wasm.json`), including each of four voices
  rendering the same samples from the bank as from its single dump; the
  parity scenario `dx7-user-bank` plays three user voices against
  `fm1-render`, glibc, musl and render.js; `test/screenshot.mjs` loads the
  bank through the page's file chooser, plays it, and drops a broken file;
  the layout sweep shows every user slot with a 10-character name and the
  load popups.

## The sequencer, multi-sound and modulation

The sequencer's panel controls arrived stage by stage (docs/15, S3 to S8),
and so did multi-sound (docs/15 §3.16) and modulation (docs/16 MG3). Until
2026-10-05 the public page hid them behind a lab switch (`?lab` or `#lab`;
owner decision O24, `fm1_app_set_lab`, the harness's `--lab`); the owner
retired it once MG3 had landed, and every page has them now. An old
`?lab` address opens the same page: nothing reads the parameter.

**The user manual has every gesture:** chapter 5 (four sounds at once, the
current sound), chapter 6 (inserts, the Mix page, the memory meter),
chapter 7 (the sequencer: SEQ mode, steps, the step and lock pages,
recording, step recording, Capture, tracks, mute, the Set, Clip and Track
pages) and chapter 8 (modulation: the rack, the gesture, the matrix, the
chain). This section is how they are built.

| | The page |
| --- | --- |
| SEQ | SEQ mode, the Track view; HOME, FX and GLO leave it; SEQ inside it stays (Session comes in S9). There the white keys are steps and the black keys roles (owner decision O1), and play nothing |
| SEL outside FX mode | SHIFT (O2), its LED on while held; FX mode keeps the slot grab, RACK grabs the module, MATRIX opens CHAIN and CHAIN goes back (docs/16 §5.2) |
| LFO, ENV | a tap opens RACK at the LFOs or the Envelopes, a page per module; held while a knob turns on HOME, FX or RACK, a cable from the selected one to that knob's parameter |
| EDIT | MATRIX, the 32 cables; SEL there opens CHAIN; EDIT again goes HOME |
| Modulation | a runtime (`engines/mod`) on every sound unit, the inserts, the master effects and the host, built by `fm1_app_init` from the default rack: LFO1, LFO2, ENV3, ENV4 and CHN5 (Chance), with RTRG (the note gate, retriggered by each note-on) cabled into both envelopes' GATE so every note restarts them |
| PLAY/STOP | `play` or `stop`, in every mode, as a typed command (`src/fm1_seq_ui.c`, then `fm1_app_seq_cmd` under the event-room rule) |
| REC | `rec` on the focused track: stopped, a bar's count-in; playing, a take from the next bar over an empty clip, an overdub at once over notes; again, off. In SEQ mode while stopped it acts on its release: a quick tap records, held it is step record. SHIFT + REC is Capture (S5) |
| Keys outside SEQ mode, MIDI IN | play the current sound, and are live input to the focused track (`non`/`nof`): recording and Capture hear them, unless a step took the note |
| Space | PLAY/STOP, unless a button has focus (owner decision O19) |
| `1`–`8`, `C V B N M , . /`, Shift | in SEQ mode, white keys 1–16 and SEL (O19) |
| Start | Macro and Plate, every track on Sound 1 (track 1 by the default route, the others by `fm1_app_seq_start_routes`, O10 as changed on 2026-10-02) and the demo pattern: one bar on track 1 in C minor at 120 BPM (`fm1_app_demo_pattern`, O4) |
| Tracks | 8 (O3): SEQ + white key 1–8 focuses one from any mode, C#5 and D#5 step through them, F#4 mutes; SHIFT + 2, 3 and 5/7/9 open the Track, Clip and Set pages, 6 the metronome, 16 the clip's quantize (S6) |
| Metronome | the click, the shared bridge's (`fm1_seq_click_mix`, O11), on the Set page or SHIFT + 6 |
| Locks | a held step's lock pages, past Step 2/2, lock the focused track's sound's parameters; a knob on a parameter with a lane turns on the 7-bit grid and the lanes' bases follow; a live take while recording; SHIFT + knob, D#4 (CLEAR) with steps held or + knob clear (S8) |
| LEDs | SEQ in SEQ mode, PLAY/STOP while the transport runs, SEL while SHIFT is held; in SEQ mode the white keys show the bar's steps (fm1_seq_ui.h has the rules); REC on while recording or step recording, fast during a count-in or a waiting take, slow while Capture holds notes (O7). Sequencer notes light no key outside SEQ mode (O6). LFO or ENV while RACK shows one of theirs, EDIT in MATRIX and CHAIN, SEL in CHAIN and while RACK holds a module |
| Status line, help | the tempo and the transport (posted by the worklet only when they change); the help's Sequencer, Tracks, Locks, Sounds, Effects, Arpeggiator and Modulation entries; SAVE in the stub list |
| Sounds | up to four sounds, each with two inserts and a level, then the two slots as the master bus; SHIFT + PRESETS chooses the current sound (below, "Multi-sound") |
| RAM | a meter in the bottom bar, which refuses whatever would pass the budget; it counts the modulation runtime (`fm1_mod_size()`, 26,848 B since glide's modes, 26,512 B since glide, 26,192 B since per-voice modulation, docs/16 MG9), and each arp that is on (736 B) with the MIDI effects' stage while one is (`fm1_mfx_t`, 7,344 B natively, less with 32-bit pointers) |
| ARP | the arpeggiator, below |

Tests and parity runs never load the demo pattern or route tracks 2–8:
only the browser's start chain does (`fm1-sim-render --start` plays that
chain natively).

**The Track view** (docs/15 §4; `src/fm1_seq_view.c`) draws the status
line, the four-bar grid, the knob strip, the hint line and the bottom bar
(`1/3 Seq T1`); **the Step pages** (S4) and **the lock pages** (S8), past
Step 2/2 with one step held, draw HOME's rows; **the Set, Clip and Track
pages** (S6) too. Manual chapter 7, "What the screen shows" and "The Set,
Clip and Track pages", describes them for users. With no step held, SELECT
pages through the sound and KNOB1–4 turn it, as in HOME; past the sound's
last page SELECT goes on to the Set, Clip and Track pages. The UI state
(`fm1_seq_ui_t`) is 600 bytes (552 before S8) against its 1,024-byte
bound; it reads the transport and the focused clip once per block, the
grid's 64 steps again (through `fm1_seq_get_page`) only after the
sequencer had input, and the held step while one is held [verified:
`fm1-sim-render --sizes`].

**Multi-sound** (docs/15 §3.16; the owner's decision of 2026-10-02, in
place of docs/15 O10's one shared sound):

- **Sound units.** Up to four sounds play at once (`FM1_APP_SOUNDS`), each
  an engine with its own two insert effects (`FM1_APP_INSERTS`) and its
  own level into the mix (0 to 100 %, unity by default); the two effect
  slots are the master bus after the mix. A track routed to the engine
  plays the sound its route index names (`route t 1 k`: Sound k + 1); a
  track routed to an empty sound plays nothing.
- **The current sound** (`a->sound`): the keys and MIDI IN play it, and
  HOME, PRESETS, ALGORITHM and the knobs edit it; a key or a MIDI note
  releases on the sound it started on, and with Sophie current the white
  keys are her pads. FX mode shows the current sound's chain on its first
  line (`S2 In1 In2 Mix M1 M2`) and opens on M1 at first; SEL then SELECT
  swaps the two inserts or the two master slots. The page's Sound menu is
  the current sound's.
- **The RAM meter.** The bottom bar's right side shows a bar and the
  percentage of `FM1_APP_RAM_BUDGET` (387,924 B, docs/11 §2) the chain
  takes, red past 100 %, and GLO's RAM line the same figure: every
  instance (`instance_size`, 32-bit in the browser's module, as on pi32v2),
  the sequencer's instance, event buffer, pending command record and UI
  state bound and click voice (36,428 B at 8 tracks), the modulation
  runtime, and a 512-byte mix block for each sound past the first
  [inferred: the firmware's layout]. A choice that would take it past the
  budget is refused (`fm1_app_select` returns -4, `FM1_APP_SELECT_RAM`)
  with a popup (`Shapes` / `does not fit` / `150K over budget`, the figure
  of the first choice refused), from the panel, the page's menus or the API
  alike, and PRESETS and ALGORITHM step past such a choice to the next one
  that fits, so whatever plays here fits the device. A chain already past
  the budget (one that fitted beside a one-track sequencer, after
  `fm1_app_seq_reset` back to eight) may shrink but not grow. Shapes twice
  does not fit; Macro, Shapes and Six-Op with four inserts and Plate do
  (about 349 KB at 32 bits).
- **Memory.** Each sound unit has a 512 KiB arena and each effect slot a
  256 KiB one: 4.5 MiB of the module's fixed 8 MiB. `fm1_app_t` is
  4,939,616 B natively (clang, 64-bit) [verified: `fm1-sim-render --sizes`].
- **The API** stage S6 routes tracks with is `fm1_app_unit_*`
  (`src/fm1_app.h`): the current sound, a sound's engine, inserts and
  level, notes on a given sound, `fm1_app_unit_route(a, track, sound)` and
  `fm1_app_unit_of_track`. The route goes in as a typed `route t 1 k`, as
  the panel's commands do, so the harness logs it and `fm1-render` replays
  it (`fm1-sim-render --unit-route T:TRACK:SOUND` calls it).
  `fm1_app_sound_unit` and `fm1_app_insert_unit`
  give the unit ids `fm1_app_select` and `fm1_app_set_param` take (0 is
  Sound 1 and 1, 2 the master slots, as before; 3–5 are Sounds 2–4 and
  6–13 the inserts). The module exports them as `fm1w_sound_unit`,
  `fm1w_insert_unit`, `fm1w_unit_current`, `fm1w_unit_set_current`,
  `fm1w_unit_level`, `fm1w_unit_set_level`, `fm1w_unit_note_on`,
  `fm1w_unit_note_off`, `fm1w_unit_route` and `fm1w_ram_budget`.
- **The render** (`fm1_app.c`, `render_sounds`): each sound renders its own
  64-frame block, split at its own tracks' events
  (`fm1_seq_host_dispatch_slots_ticks`, engines/seq.md), through its
  inserts, times its level (skipped at 100 %), and the sounds are summed in
  order, the first copied; then the master bus and the limiter.
  `fm1-render --slots` with `--sound`, `--insert` and `--level` renders the
  same float for float. With one sound, no insert and full level that is
  `fm1-render`'s one engine without `--slots`, to the bit [verified: every
  one-sound parity scenario, natively in `tests/test_sim_web.py` and in
  WebAssembly in `parity.mjs`].

**Modulation** (docs/16 §5, stage MG3; `src/fm1_mod_ui.c` has the pages'
logic, `src/fm1_mod_view.c` draws them; manual chapter 8 has the gestures
and screens). The app hosts the runtime on the sequencer's bridge exactly
as `fm1-render --mod` does: a knob, a lock or the bend moves a parameter's
base, the runtime adds what its cables give, each effect renders split at
its own writes, and HOST AMP is applied before the limiter. It runs over
every sound unit at once (`fm1_seq_host_dispatch_slots_ticks`), and a
cable can reach any sound unit's parameters, its inserts', the master
effects' and the host's. Every note on any sound restarts the default
envelopes (RTRG). A parameter with no cable is never written, so a chain
with the default rack renders what `fm1-render` renders without `--mod`
[verified: every parity scenario without `mod`]. Modules are named by the
kind's three-letter abbreviation and the rack position (LFO1, LFO2, ENV3,
ENV4, CHN5: Chance, Calc, Compare and Coin are CHN, CLC, CMP and COI), so
no two share a name. A kind change switches off the cables that touch the
module and remembers them; the pickers commit a second after their last
turn or at once when another control is used. An Envelope with no cable
into its GATE restarts at every note too (RTRG is its normal since MG9).

Destinations are a slot's unit code and a uid (`fm1_mod.h`): 0 Sound 1,
17–19 Sounds 2–4, 20 + 4k + j Sound k + 1's insert j + 1, 1 and 2 the
master slots, 3 the host, 8–15 a rack position. HOST PITCH bends Sound 1,
PITCH2–4 (`Pitch2`–`Pitch4` in MATRIX) Sounds 2–4, and PITCH_CUR
(`PitchC`) the current sound; SHIFT + PRESETS logs a `current K` line for
it. One sound's note sources, S1NOTE … S4RTRG, follow SQV8 in KNOB1's list.

**Per voice** (docs/16 MG9). MATRIX page B's KNOB4 is a cable's state:
off, on, on per voice (`v` in its row, `!` when refused). A per-voice
cable runs once for every note on a sound whose engine takes per-note
offsets (Macro, Macro Heavy, Shapes, Six-Op FM, FM6, Drums): its note
sources are the note's own, an Envelope, LFO or Chance it reads runs one
instance per note, and it reaches only that note, through the engine's
`set_param_note`; the app sends a key's first offsets right after its
note-on, as the bridge does for the sequencer's notes. Into an effect, AMP
or a parameter every note shares it is refused. RACK's line says `vN` for
a module that runs per voice, N its voices now. When a unit's engine
changes, each cable into it re-aims at the new engine's parameter of the
same name or switches off under its old name until an engine with it comes
back (the owner's rule, 2026-10-05). MG2's Filter module is the Resonator
(RES) since then.

**Gesture traces and two-step parity** (docs/15 §6.3). `fm1-sim-render
--panel FILE` reads panel input, one `--key`, `--button` or `--turn` per
line, and `--note` for a note at MIDI IN. `--log-cmds FILE.verbs` writes
what reached the sequencer, the script's lines, the panel's typed
commands (`fm1_seq_cmd_format`, `engines/host/seq_script.h`) and the live
notes the app gave it as `non` and `nof` ops (S5), at the blocks they led, under a header with the run's length; next to it, `FILE.args`
lists the arguments `fm1-render` needs to replay it, one per line: the
engine and effects, the MIDI IN notes, a `--note` for each key that played
the sound (written at its press, so notes keep their order, at mid-block
times), and a `--param-at` at mid-block for every sound parameter the
panel turned. `fm1-render --cmd FILE.verbs` with those arguments renders
the same bytes. A run the replay cannot follow (a new sound or effect from
the panel, an effect's parameter, MASTER below full, or notes sent to the
sound in one block in an order `fm1-render` would not play them, such as a
MIDI IN note after a key's) says `"replayable":0`. The sidecar starts
with `--slots` (the app routes tracks to its sound units), a note on
another sound goes into it as
`--sound-note` (one on an empty sound too, which plays nothing in
either), a knob turn on another sound's page as `--sound-param-at`
and a level on the Mix page as `--level-at`; an insert's change, a bend
on another sound, or a MIDI note-off that another sound's note of the
same pitch would make ambiguous is not replayable. The harness takes the
same multi-sound flags as `fm1-render`. A modulation edit
no script line can say is not replayable either. `--format-check` writes
and reads back every verb.

With modulation running (always, from `fm1_app_init`'s default rack or a
`--mod` file), `--log-cmds` also writes `FILE.mod`: the
runtime's whole state before the first block (seed, rack, the bases that
differ from their defaults, every cable) and every edit after it, as
`@<block start>` lines of `fm1-render --mod` (`engines/host/mod_script.h`),
and the sidecar ends with `--mod` and that file, so the replay modulates
exactly as the panel did. `--mod FILE` plays a modulation script as
`fm1-render --mod` does (a new runtime with the file's seed after the
chain, untimed lines first, `@FRAME` lines at the first block starting
there), in place of the default runtime. `--mod-format-check` writes 300
random racks, bases and cable tables whole and applies random edits line
by line (cables, kinds with their switch-off and restore, bases, moves),
each read back by `mod_script.c` into a second runtime: the same state
every time [verified: about 25,000 lines, 0 refused].

## The arpeggiator

The arpeggiator (`engines/midi_fx/`, after Yarns, MCL and Super Arp) is
engine API v3's first MIDI effect (`FM1_KIND_MIDI_FX`; DEVELOPERS.md, "MIDI
effects"). The app keeps one per sound unit, bypassed, in the first slot of
the chain in front of it, on the sequencer's bridge, exactly as
`fm1-render --mfx` runs it (`engines/include/fm1_mfx_host.h`): so the
browser, the native harness and fm1-render play the same notes. The user
manual's chapter 4, "Arpeggiator", has every gesture; this is how it is
built.

| | |
| --- | --- |
| ARP tap | the current sound's arp on (and the ARP pages, `FM1_MODE_ARP`, open; its popup "Arp on") or off (the pages close back to the mode they came from; "Arp off"). A press with another button or a turn before its release is no tap |
| ARP held | `FM1_APP_ARP_HOLD_S` (0.5 s, measured in the app's blocks): Latch on, and the arp with it, or, while the arp is on and latched, Latch off; an arp that is off always comes on latched; the release does nothing more |
| SHIFT + ARP | the ARP pages, nothing switched |
| The ARP pages | SELECT: PLAY, RHYTHM, CHANCE, FEEL, MORE, KEYS, SEED (the options note's §2.4 and three pages for the rest); KNOB1–4 the page's parameters; ALGORITHM the stock FM-1's arp modes as presets of Mode and Order, in a list popup as a model's (titled "Arp preset") (Up, Down, Up/Down, Down/Up, Random as Shuffle, Played; AL-255's FM-1-RE `docs/io/05-midi.md` §6.3 [reported]; owner, 2026-10-05: as presets); OCT held + ALGORITHM still transposes; PRESETS still the sound; a knob on a list of five or more (Mode, Rate, Pattern, Oct Mode, Repeat) opens its list in MID (audit D1). The context line says "Arp on" (rose), "Arp latched" (gold: held) or "Arp off" (subtle) and, on its right, the preset, if the mode and order make one; the rows start under it, and the scope runs under the last row (L4) |
| LED | ARP lit while the current sound's arp is on, half of each second while it latches, and while held |
| Notes | keys and MIDI IN on the current sound go to its arp while it is on (`fm1_mfx_live_note`; at the next block's first frame), and so do the sequencer's notes of tracks routed to that sound (the bridge takes them out of the block); a note-off follows its note-on, so an arp switched on or off while keys are down leaves no note hanging. The arp's notes reach the sound through the bridge's sink (counted with the sequencer's) and feed modulation's note sources as notes on the sound |
| Recording | the keys go to the sequencer as live input before the arp (owner, 2026-10-05: record what was played), so a recorded part plays through the arp again; switched off, it plays as played |
| Clock | the sequencer's ticks, playing or stopped (its sum runs on at the tempo); Start resets the arp, Stop flushes it (`FM1_MIDI_EV_RESET`, `_FLUSH`) |
| Flushes | a bypass, at once; a new engine on the sound, a panic, a sequencer reset or import: PANIC (the arp forgets its keys) |
| Slots | the owner's design has four MIDI-effect slots per track (2026-10-05). The stage has the four (fm1-render fills them with `--mfx`); the panel fills the first, with the arp, as the only MIDI effect so far. The chain is per sound unit, so a track's notes meet the chain of the sound it plays |
| Project key | the context every MIDI effect gets carries one key for the project (owner, 2026-10-05); C major until a page sets it. The arp reads none of it |
| RAM | an arp that is on (736 B) and the stage while one is; a tap that would pass the budget is refused with "Arp does not fit" and by how much |
| Replay | every change of an arp reaches `fm1_app_t.on_mfx`; the harness writes it into the sidecar (`--mfx K:arp:off` at the sound's first change, then `--mfx-on-at` and `--mfx-param-at` at mid-block), so a panel trace replays through fm1-render byte for byte; `--log-mfx` writes the arps' notes as fm1-render's does |
| Exports | `fm1w_arp_on`, `fm1w_arp_set_on`, `fm1w_arp_set_param`, `fm1w_arp_get_param`; the catalogue lists the arp (kind `midi_fx`, after the engines) |

`tests/test_sim_arp.py` checks the gestures, the pages and presets, the
LED, the RAM meter's refusal, the recording rule (a take with the arp on
plays the keys' pitches back through it, and plainly once it is off, both
replayed by fm1-render), and that nothing sounds after a bypass, a new
sound, a sequencer reset or Latch off. `tests/test_engine_midi_fx.py`
checks the stage and the arp through fm1-render: block sizes 1, 7, 64 and
448, the sequencer's ticks, Start and Stop, a 24-seed fuzz with no note
hanging, chains of two. The parity scenarios `arp-macro-chord`,
`arp-sequencer-latch`, `arp-multi-sound` and the gesture trace `arp-panel`
(`test/arp/`) compare the app, fm1-render and the module, the arps' notes
included.

## Parity: does the browser sound like the native engines?

`build-on-aeon.sh` renders 69 scenarios (`test/scenarios.json`) four ways
and compares the 16-bit output sample by sample [verified:
`www/fm1.wasm.json`, 2026-10-05]. Forty-eight are note scripts: every engine
and effect, pitch bend, parameter changes mid-note on the sound and on
every effect (`fx_param_at`: `fm1-render --fx-param-at T:K:NAME=VALUE`, K
the effect's place in the chain; the module gets `fm1w_set_param` on that
slot), more notes than voices, 44,100 Hz, the low-pass gate, and Drums' two
kits with a choke, a pad's Model and a Kit change, and all sixteen pads with
every voice busy (steals by the level a voice holds). Six play sequencer verb scripts
(`test/seq/`, `fm1-render --cmd`): Test Sine's Volume under float locks
with a stop that sends the lanes back to their bases; two Six-Op tracks
with swing and a clip at twice the speed; locks on Six-Op's Patch, a list;
Capture committed while playing; a stopped Capture whose tempo is then
changed with `capsel`; and the metronome's click on, off and on again with
swing, then a REC count-in (`metro-click.verbs`, S6). Six are played on
the panel:
`seq/panel-play-stop.panel` (SEQ, PLAY/STOP in SEQ mode and in HOME, and
knob turns on two sound pages, ending in the Track view) and
`seq/panel-step-entry.panel` (S4: a chord from MIDI IN entered on two
steps, a probability, a condition and an invert on the Step pages, a
second bar, a nudge, a pitch added with SHIFT and a step cleared with a
SHIFT tap, then two passes of the two-bar clip),
`seq/panel-record.panel` (S5: a take after a count-in, step record with a
tie, a rest and a MIDI IN note, and Capture while playing; the keys reach
the sequencer as live input, which the render legs replay as `non` and
`nof`), `seq/panel-capture-stopped.panel` (S5: a stopped Capture, its
tempo picker and a key closing it; `libm_sensitive`, as the scripted
stopped Capture) and `seq/panel-tracks.panel` (S6: SEQ + a white key
focuses track 2, its Track page routes it to Sound 2, the mute map mutes
track 4, the Set page's swing and tempo, track 2's Clip page at 1/2X and
2X, the click on and off with SHIFT + 6, a MUTE tap) and
`seq/panel-locks.panel` (S8: locks on two steps from the lock pages, a
knob turned with no step held while playing, which its lane's base
follows, and a stop just after the locks, which sends the lanes back to
their bases). Three play several sound
units (docs/15 §3.16): `multi-two-sounds-inserts`
(Macro through a Crush insert at 80 % and Shapes through Diffuse and
Ensemble at 60 %, notes on each, into the master Comp),
`multi-four-sounds-seq` (four tracks routed to Macro, Shapes, an empty
slot and Six-Op, each with its inserts and level, and lock lanes that
resolve on their own track's sound) and `multi-panel` (SHIFT + PRESETS, a
key, a MIDI IN note and a knob on Sound 2, the Mix page's levels, two
tracks on two sounds, replayed through `fm1-render --slots`). Two modulate
(`test/mod/`, docs/16 MG3): `mod-macro-routes` plays a `--mod` script with
cables into the sound, both effects, HOST PITCH and AMP, a chain of
modules, a gate cable at 70 % and timed edits (the module takes it through
`fm1w_mod_reset` and `fm1w_mod_text`); `mod-panel-gestures` makes its
cables on the panel (the gesture on HOME and FX, knobs
in RACK, two cables from MATRIX), and its render legs replay the harness's
`.mod` log with the rest of its sidecar. Two modulate several sound
units: `mod-multi-routes` plays a script with cables into Sound 1, Sounds 2
and 4, an insert on each of them and both of Sound 2's, the master Plate
and HOST AMP, with notes on three sounds (`fm1-render --slots --mod`), and
`mod-multi-panel` makes its cables on the panel with Sound 2 current (the
gesture on HOME, its insert and the master, a MATRIX cable whose picker
opens at Sound 2) and then on Sound 1, while tracks play both sounds.

Since the lab switch went (2026-10-05) the module and the harness run every
scenario with four sound units and the default modulation rack; the
one-sound scenarios are still rendered by `fm1-render` without `--slots`
or `--mod`, so they check that path against the app's multi-sound one.
`fx-turns-diffuse-psxverb` plays Macro's 2-op FM through its ping LPG in
place of Shapes' Pluck, which the RAM meter refuses beside Diffuse and PSX
Verb.

| Against | Result |
| --- | --- |
| `render.cc` compiled to WebAssembly (Node) | identical in all 69: the app layer adds nothing |
| native `fm1-render`, GCC with musl (static, Alpine) | identical in all 69: the compiler adds nothing |
| native `fm1-render`, GCC with glibc | identical in 66, Drums' three among them (no libm in it). Sophie differs (23,286 and 694 samples, up to 4,082 and 12,330 LSB), and Fold within 1 LSB (19 samples of `fold-sine-asymmetric`) |

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
pixel, except the RAM meter in the bottom bar, which is the 32-bit figure.

The module links the sequencer core, its host bridge and, since stage S3,
its panel UI and Track view, with step entry since S4, record and Capture
since S5, multi-sound, tracks, mute, the pages and the click since S6, and
parameter locks since S8, the engines' SMOOTH ramps since S7b, the
master-bus effects (DJ Filter, Tilt, Master Sat, Isolator, EQ), since
docs/16 MG3 the modulation runtime, its kinds, its script reader
(`host/mod_script.c`: snprintf and strtod, no files) and modulation's
pages, Room, Hall, Gate and Plate's Freeze, since engine API v3
(2026-10-05) Comb, Test Ext, the LOG law and the effects' extension
(`fm1_fx_render`), Drums, FM6 (msfa), the list popups, FM6's user bank
with msfa's tables as const data, Squash, Transient and the Limiter's
Round mode, per-voice modulation (MG9) (2026-10-06), the idle paths of
EQ, Isolator and Master Sat (engines/README.md, "Idle at pass-through"),
the arpeggiator with the MIDI effects' stage (engine API v3's MIDI effects),
glide and the voice modes (`engines/src/glide.h`) and the UI audit's
screens: 86 of 86 scenarios pass,
identical to musl and to render.js (six of them turn the effects' switches
every 4.4 ms, and two let EQ with Master Sat and Isolator rest past 2 s and
wake them; those two, the three Drums, the four FM6 and the three glide
scenarios are identical to glibc too), and it imports nothing; it is
955,464 bytes (955,543 before the dead-code audit's removals) with the UI
audit's screens (the palette, the two Spleen faces and the screens that
use them), 938,723 before them with glide
(939,251 with them before glide), 922,439 before both, 907,256 with glide
before the arpeggiator, 890,975 before both (890,874 before Shapes'
clamps), 887,038 before the idle paths, 850,731 before
per-voice modulation (826,339 without the user bank, 840,216 without
Squash, Transient and Round), 837,480 with
the user bank before the list popups, 815,821 with the list popups before the
user bank, 813,115 before both, 786,256 before FM6,
765,189 before Drums since the lab switch went (790,801
with Drums and the switch's second code path, 769,693 with the switch
alone), 761,171 before both API v3 and Drums, up from
737,880 before Room, Hall, Gate and Plate's Freeze (622,338 with them
before MG3, 547,963 before the master-bus effects, multi-sound, S8 and
S7b), 598,994 before MG3 (the runtime, its sixteen kinds with MG2's Peaks
and Braids tables, the pages and the script reader), 573,403 before the
master-bus effects (550,252 with them before multi-sound, S8 and S7b),
560,033 before the engines' SMOOTH ramps (docs/15 S7b; 559,930 before
MG1's rebuild), 548,493 before S8 (526,111
with S8 before the second effects pack), 524,659 before multi-sound and S6
(514,688 with them before the second effects pack), 516,035 before S5,
482,291 before the second effects pack (Drive, Filter, Comp, Limiter),
466,635 before S4, 459,122 before S3 and 391 KB before the sequencer
[verified, 2026-10-06, `www/fm1.wasm.json`]. With S7b nine scenarios sound
different, each because a knob or a lock turns while something sounds:
`seq-panel-play-stop`, `seq-panel-locks`, `multi-panel`,
`multi-four-sounds-seq`, `drive-fuzz-gated` (its Plate Decay turn) and the
four `fx-turns-*`; the others change only their RAM figures, by 12 bytes
per SMOOTH parameter (engines/README.md, "SMOOTH").

The sequencer's own cost in WebAssembly, measured with `fm1-render.js` under
Node 24.19 in the emsdk container on aeon: tools/seq_bench.py's burst (8
tracks of 12-note chords on every step and 8 locked lanes, 300 BPM, up to
193 events in a block) takes 5.7–10.2 µs per 64-frame block for commands and
advance (three runs; the first includes the JIT's warm-up), against 1.7–1.8
µs for native GCC on the same host and the 1,451 µs a block lasts
[verified, 2026-10-02]. Phones are not measured. That burst was also the
one load that the app's first 256 events did not hold whole: the core keeps
room for the note-off of every sounding gate (64) beside a block's events,
so a 193-event block needs 257, and at 256 the burst drops 400 note-ons
(whole, with nothing left hanging). Since stage S6 the app has 272, which
hold it [verified: `fm1-render --events 256` and `--events 272` on the
burst, `tests/test_seq_render.py`]. No oracle script puts more than 7
events in a block.

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
                                      typed commands out
                  src/fm1_seq_view.c  its screens: the Track view
                  src/fm1_mod_ui.c    modulation's pages and gesture: edges
                                      in, runtime edits and script lines
                                      out
                  src/fm1_mod_view.c  their screens and the routed marks
                  src/fm1_tft.c   240 x 240 RGB565 frame buffer, three text faces
                  engines/        every engine, effect and the bus limiter,
                                  the sequencer core and its host bridge,
                                  the modulation runtime and its kinds
```

`src/` is C99 with no heap: instance memory lives in fixed arenas inside
`fm1_app_t`. Nothing in it is browser-specific, so the same app layer builds
natively as `fm1-sim-render`, the test harness. Its panel logic and drawing
code are meant to carry over to the firmware, but not `fm1_app_t` as it
stands: it is 4,939,616 bytes (4.5 MiB of fixed arenas, four 512 KiB
ones for the sound units and ten 256 KiB ones for the effect slots, a
115,200-byte full frame buffer, and the sequencer's 32 KiB arena and 3 KiB
event buffer, and modulation's runtime and a block's writes; clang, 64-bit), against the FM-1's 578 KB of SRAM and
the ~379 KB the stock layout leaves free [verified: `sizeof`; SRAM from
docs/01]. The firmware needs one arena sized to the chain it loads and
strip rendering (ten 240 × 24 strips, 11.5 KB each, as stock does;
`src/fm1_tft.h`) [inferred]. The main font is drawn for this repository
(`tools/font5x9.txt`; `tools/gen_font.py` writes `src/fm1_font.h`).

**Text faces** (`src/fm1_tft.h`, the audit's decision D7, 2026-10-06). Three
faces, each a table of one byte a glyph row in flash, printable ASCII only
[verified: `fm1-sim-render --font-check`, `tests/test_sim_fonts.py`]:

| Face | Glyphs | Advance | Box height | Capitals | Characters a line | Line pitch | Flash |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MAIN | the 5×9 at ×2 | 12 px | 18 px | 14 px | 19 | 22 px | 855 B |
| MID | Spleen 8×16 at ×1 | 8 px | 14 px | 10 px | 28 | 18 px | 1,330 B |
| SMALL | Spleen 6×12 at ×1 | 6 px | 12 px | 8 px | 38 | 16 px | 1,140 B |

- A run's logged box is what its face's characters can paint, whatever the
  run holds: the 5×9's descenders are in it and its spacing column is not;
  Spleen 8×16's top and bottom rows, which no ASCII glyph paints, are not
  in its table at all, so a run's y is the top of its box in every face.
- `tools/gen_font.py` writes the Spleen tables from the BDF files
  (`third_party/spleen/`, Spleen 2.2.0, unmodified;
  [UPSTREAM.md](third_party/spleen/UPSTREAM.md) has the licence notice a
  binary must carry), and `--check` keeps all three headers current.
- `fm1_tft_font_text`, `fm1_tft_font_width` and `fm1_tft_font_fit` draw and
  measure in a face; `fm1_tft_text` stays MAIN at any scale.
  `fm1_tft_span_text` draws a run of several colours (MATRIX's columns,
  audit L2) and logs it as one box. The layout check's rule is the same for
  every face: 4 px between boxes.
- `fm1-sim-render --font-sheet FILE.ppm` draws both Spleen faces on one
  screen, layout-checked
  ([the sheet at ×3](../../assets/ui-audit/fonts-spleen.png)).
- Until a screen uses MID or SMALL, every screen draws as before, pixel for
  pixel [verified: the 3,144 screens of `--screens`, byte for byte, before
  and after the faces arrived].

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
`fm1w_seq_info()` returns eight
32-bit words for the status line: playing, the tempo in hundredths of a
BPM, recording, the watched track, counting in, following an external
clock, and the master tick's two halves. `fm1w_mod_reset(seed)` makes a new,
empty modulation runtime and `fm1w_mod_text(len)` applies one line of
`fm1-render --mod` from the text buffer (1, or 0 for a bad line); the
parity test plays a scenario's modulation through them.
`fm1w_dx7_load(len, play)` reads a `.syx` file's bytes from the same
buffer into FM6's user bank (above); `fm1w_dx7_result()` returns thirteen
words saying what the file held, and `fm1w_dx7_name(slot)` the name a user
slot shows.

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
   `fm1-render.js` with Emscripten 6.0.10, `test/parity.mjs`,
   `test/sysex.mjs` (the DX7 export, above); then, only if everything
   passed, `www/fm1.wasm` and its record `www/fm1.wasm.json` (hashes of the
   module and of the sources, the parity and SysEx results).
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
change of sound; the 3,288-screen layout sweep, every list popup's window at every entry
among them; the panel against the manual's formula (octave,
transpose, reset); buttons and encoders; PLAY/STOP's
LED while playing, SEQ mode, the white keys following the playhead in SEQ
mode (eight points across two bars), HOME's key LEDs unchanged and the
Track view's knob hint cleared by a new sound; an effect slot emptied on its
second page; sounds that refuse a 48 kHz host stepped over and the previous
one kept; the page loads nothing from other origins; the exports match; and
`www/fm1.wasm` matches its record; every effect has a knob turned
mid-render in some scenario (`fx_param_at`), and `--fx-param-at` applies at
its block in both hosts and refuses a slot or a name that is not there. The record carries two source hashes
(`tools/source_hash.py`): engines/ (less Markdown) and sim/web's own inputs
(`src/`, `mk/`, `build.sh`, the parity test, its scenarios and their
sequencer and modulation scripts in `test/seq/` and `test/mod/`, the DX7
test files in `test/dx7/` and `test/sysex.mjs`, the harness, the loader), which since the module links the sequencer include
`engines/seq/` and `engines/include/fm1_seq*.h` too, and since it links
modulation `engines/mod/` (less its Markdown), `engines/include/fm1_mod*.h`
and `engines/host/mod_script.*`. When sim/web's inputs have changed since the last
build, the test fails in CI (`CI=true`) and warns locally; when only the
engines have, it warns, so engine work elsewhere does not need aeon.
Rebuild with `build-on-aeon.sh` before publishing the page or merging a
change to the simulator.

`tests/test_sim_palette.py` runs `tools/palette.py`: the screen's and the
page's tokens and roles agree, contrast after the RGB565 round trip,
CIEDE2000 between colours with different meanings, the sound colours under
simulated colour-vision deficiencies, one meaning per colour in
`style.css`, and PALETTE.md's figures equal to the checker's report; and the
colour science against the audit's figures and Sharma's CIEDE2000 data.

`tests/test_sim_multi.py` checks multi-sound: SHIFT + PRESETS and its
popups, the keys and a MIDI note-off on the sound that started them,
Sophie's pads on the current sound, Empty on Sounds 2–4, FX mode's walk and
the Mix page, the insert swap, the RAM meter's figure (every instance and
the fixed costs) and its refusals from the harness, PRESETS and ALGORITHM,
tracks routed to sound units as in `fm1-render --slots` (and every one on
the one engine in `fm1-render` without it), a bend on another sound marked
not replayable, and every parity scenario inside the meter's budget.

`tests/test_sim_seq.py` plays all 34 Movy oracle scripts through the app
with Test Sine, and six with Macro, against `fm1-render --frames 64`: event
logs and WAVs byte-identical, nothing dropped.

`tests/test_seq_ui.py` checks the sequencer on the panel: 27 golden
gesture traces (`tests/fixtures/seq-ui/`; S3's five: SEQ in and out,
PLAY/STOP from HOME, FX and SEQ mode, two presses in one block; S4's 22,
`step-*`: a tap, the hold threshold to the frame, hold A and press B,
steps held together with a knob, OCT and the nudge on a hold, bar paging,
full velocity, every Step page field at its minimum and maximum, a pitch
added and a step cleared with SHIFT, chords from the keys and from MIDI
IN, a MIDI note added to a held step, SHIFT + PLAY, HOME during a hold
and the hidden rest of a short clip), each logging its golden script and
replaying through `fm1-render` byte for byte; the mode and button LEDs the
S3 traces end in; the parity scenarios' own traces; the Step page's
threshold and read-outs, the keys' LEDs in SEQ mode, the bar keys'
limits, sixteen held steps, the 12-note chord, full velocity on the keys,
SEL as SHIFT, OCT on a held step left out of the keys' octave and
transpose, and notes in one block that the replay would play in another
order marked not replayable; every verb through `fm1_seq_cmd_format` and
back; the demo pattern and the routes of tracks 2–8 only on the start
chain; a sound changed from the panel marked not replayable; and the UI
state's size. `tests/test_seq_core.py` checks
`fm1_seq_get_page` against every Movy fixture's `movy1` export.

`tests/test_sim_mod.py` checks modulation on the panel (docs/16 MG3): the
runtime from the start, in the RAM figure, with SAVE the only stub
left; the default rack and its two cables; LFO, ENV, EDIT and SEL and their LEDs;
the gesture on HOME, FX and RACK, and its refusal; rule M1 on a routed
knob; every MATRIX field; a kind change switching cables off and back on,
also after the other kind got cables of its own; a hold with any turn
being no tap; a new MATRIX cable starting from the selected LFO; CHAIN
not running on through a refused cable; the envelopes opening for notes
from the sequencer, MIDI in and the keys, and the default cable
re-patched; six golden gesture traces (`tests/fixtures/mod-ui/`, one of
them knob turns on routed parameters) whose `.mod` logs replay through
`fm1-render --mod` byte for byte; and `--mod-format-check`.

`tests/test_sim_lists.py` checks the list popups: ALGORITHM through Six-Op
FM's 96 patches, PRESETS through the engines, ALGORITHM in FX mode through
the effects, SHIFT + PRESETS, the kind picker and the destination picker,
each at the top of its list, in the middle and at the end, where the
window (`popup_list` in the summary) must be `fm1_list_first`'s and its six
entries the list's own; and that the messages stay messages.

CI also runs these files in its 32-bit job (`-m32`, like pi32v2's
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
- **SAVE** does nothing yet but say so. Only the arpeggiator's first
  MIDI-effect slot is on the panel. On the panel the sequencer
  has no Session, scenes, song, Loop view, COPY or a CLEAR tap (docs/15
  S9), and no sets in the browser or MIDI clock in (S10); the desktop tools
  have them. Per-voice modulation reaches only the engines with per-note
  offsets; Sophie and Test Sine refuse it (docs/16 MG9).
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
