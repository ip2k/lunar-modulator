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
| Engines | Every registered sound engine and effect (engines/README.md): Macro, Shapes, Macro Heavy, Six-Op FM, Sophie, Test Sine; Plate, Ensemble, Diffuse, PSX Verb, Test Gain. One sound and two effect slots, then the host's bus limiter, as `fm1-render` runs them; with the lab switch, up to four sounds with two inserts and a level each, mixed into those two slots as the master bus (below, "Multi-sound") |
| Audio | An AudioWorklet renders each 128-frame quantum as two 64-frame host blocks. The AudioContext asks for 44,118 Hz, then 44,100 Hz (a context that comes back faster than 47,872 Hz is closed and the next rate tried), and only then takes the device's own rate. Headless Chromium ran at 44,118 Hz [verified]. Macro, Macro Heavy and Six-Op run Plaits at 47,872 Hz and resample to the host (engines/resampler.md), so they refuse a faster one: there the firmware starts with Shapes, PRESETS steps over the three, a refused choice puts the previous engine back, and the screen and status line say why [verified natively at 48 and 96 kHz: `tests/test_sim_web.py`] |
| Screen | The firmware draws a 240 × 240 RGB565 frame buffer (stock's layout: a top bar with the sound, the mode's content, a bottom bar with page and mode, one-second popups); the page only copies it to a canvas. HOME's oscilloscope strip scales the trace to its window's peak (at most ×16, so quiet noise stays flat). 1,109 screens pass a layout check: nothing off screen, no text cut short, no more than 96 logged boxes, and no two labels and no label and bar closer than 4 px [verified: `fm1-sim-render --screens`]. They are every page of every engine and effect at defaults, minima, maxima and every list entry, the global page, every popup including the refusals, SEL outside FX mode and an emptied slot (335 screens), and, with the lab switch on, the sequencer's Track view, Step pages, record and Capture (below) in 618 states, its tracks, mute and Set, Clip and Track pages (S6) in 69, and multi-sound's FX chain, Mix page, titles, popups and RAM meter in 87 more |
| Panel | The 27 keys, 14 buttons, MASTER and the seven encoders, with their LEDs, laid out to scale (below) |
| Input | Mouse and touch (lower on a key plays louder; drag or scroll an encoder), the computer keyboard (`A W S E D R F G Y H U J K O L P ; [ '` play F3 to B4, `Z`/`X` are OCT−/OCT+, arrows turn SELECT and PRESETS, `-`/`=` ALGORITHM, `Esc` releases every note), and Web MIDI (notes, pitch bend ±2 semitones, CC 7 volume, CC 123 all notes off). A held key or button is released whatever modifiers are down by then (Cmd lets go of every held key, since macOS drops those keyups), and leaving the window or tab releases every key, button and pointer. Scrolling over an encoder turns it one detent for the first wheel event of a gesture, then one per 60 px of vertical scroll; horizontal scrolling turns nothing |
| Look | Lunar Modulator's: the Rosé Pine Moon palette ([rosepinetheme.com](https://rosepinetheme.com/palette/), MIT; the hex values checked against rose-pine/palette and rose-pine/neovim on 2026-10-01 [verified]) as CSS custom properties, one dark theme, and the firmware's screen in the same colours (`src/fm1_app.c`); Audiowide (Astigmatic, SIL OFL 1.1) for the name, the tagline and headings, from the page's own `fonts/`, unmodified ([fonts/README.md](www/fonts/README.md)); Exo 2 (Natanael Gama, SIL OFL 1.1) for small text, also from `fonts/`, unmodified. Text contrast is at least 4.8:1 against its background on the page, disabled controls aside (WCAG AA asks 4.5:1; secondary text on a surface is subtle with a tenth of text mixed in, since subtle alone is 4.46:1 there) and at least 4.78:1 on the screen after RGB565 rounding [verified: computed from the palette] |
| Info | GLO shows the sample rate, block size, the chain's RAM against the 379 KB the stock layout leaves free (docs/11 §2), voices, octave and transpose. WebAssembly has 4-byte pointers like pi32v2, so these are the 32-bit instance sizes. The RAM figure includes the sequencer: its instance (31,880 B at 8 tracks, the same at 32 and 64 bits) and its 3,264-byte event buffer (3,072 B, 256 events, until stage S6, so a chain's figure can read 1K more than before: 4 of the 54 one-effect chains do). With the lab switch it is the RAM meter's figure (below) |
| Sequencer | The app hosts the sequencer core (engines/seq.md) through the shared host bridge (`engines/include/fm1_seq_host.h`), exactly as `fm1-render` does: script lines and commands at block starts, each block's events, and the sound's render split at every note and lock of a track routed to it. 8 tracks (owner decision O3, 2026-10-02), a 272-event buffer (256 until stage S6), one pending command record, and the event-room rule: an op goes in only while 201 events of room are free, otherwise it waits a block, so no note-off is ever lost. The harness and the parity test play verb scripts and `movy1` sets through it; every one of the 34 Movy oracle scripts plays through the app byte for byte as through `fm1-render` at 64-frame blocks [verified: `tests/test_sim_seq.py`]. On the panel only with the lab switch (below): PLAY/STOP, SEQ mode's Track view and a demo pattern (docs/15 stage S3), step entry: the white keys as steps, the Step pages, SHIFT and bar paging (S4), record, step record and Capture (S5), and tracks, mute, the Set, Clip and Track pages and the metronome's click (S6) |

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
REC in SEQ mode while playing overdubs at once (`recording` true, its LED
lit) and REC again stops; two keys played in HOME make REC blink, and
Shift (SHIFT) + REC captures them, after which REC stays dark; without the
switch Space sends nothing, PLAY/STOP, SEQ and REC stay stubs and the page
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
| ENV, LFO, EDIT, SAVE, ARP | | a popup: not in the simulator yet |
| REC | recording | a popup: not in the simulator yet; with the lab switch, record, step record and Capture (below) |
| SEQ, PLAY/STOP | the sequencer: its view and the transport | a popup: not in the simulator yet; with the lab switch, SEQ mode and the transport (below) |
| SEL outside FX mode | (SHIFT, in the sequencer) | a popup: SEL works in FX mode; with the lab switch, SHIFT (below) |

## The lab switch

The sequencer's panel controls arrive stage by stage (docs/15, S3 onward).
Every merge to main publishes the page, so until step entry and recording
work (stages S5 and S6) the public page hides them (the owner's decision
O24, 2026-10-02). An address with a `lab` query parameter or hash turns
them on, for development and review:

```
http://localhost:8000/?lab        http://localhost:8000/#lab
```

`app.js` reads the address once at load and passes the switch to the
worklet, which calls `fm1w_set_lab(1)` before `fm1w_default_chain()`; in
the app layer `fm1_app_set_lab` is the one switch, and `fm1_app_init`
leaves it off. The harness takes `--lab`. Nothing else changes between the
two: the engines, the sequencer and the module are the same.

| | Off (the public page) | On |
| --- | --- | --- |
| SEQ | "not in the simulator yet" | SEQ mode, the Track view; HOME, FX and GLO leave it; SEQ inside it stays (Session comes in S9). There the white keys are steps and the black keys roles (owner decision O1), and play nothing (S4, below) |
| SEL outside FX mode | "SEL works in FX mode" | SHIFT (O2), its LED on while held; FX mode keeps the slot grab |
| PLAY/STOP | "not in the simulator yet" | `play` or `stop`, in every mode, as a typed command (`src/fm1_seq_ui.c`, then `fm1_app_seq_cmd` under the event-room rule) |
| REC | "not in the simulator yet" | `rec` on the focused track: stopped, a bar's count-in; playing, a take from the next bar over an empty clip, an overdub at once over notes; again, off. In SEQ mode while stopped it acts on its release: a quick tap records, held it is step record. SHIFT + REC is Capture (S5, below) |
| Keys outside SEQ mode, MIDI IN | play the sound | the same, and they are live input to the focused track (`non`/`nof`): recording and Capture hear them, unless a step took the note |
| Space | nothing new (the page scrolls) | PLAY/STOP, unless a button has focus (owner decision O19) |
| `1`–`8`, `C V B N M , . /`, Shift | nothing new | in SEQ mode, white keys 1–16 and SEL (O19) |
| Start | Macro and Plate, the sequencer empty | the same, every track on Sound 1 (track 1 by the default route, the others by `fm1_app_seq_start_routes`, O10 as changed on 2026-10-02) and the demo pattern: one bar on track 1 in C minor at 120 BPM (`fm1_app_demo_pattern`, O4) |
| Tracks | — | 8 (O3): SEQ + white key 1–8 focuses one from any mode, C#5 and D#5 step through them, F#4 mutes; SHIFT + 2, 3 and 5/7/9 open the Track, Clip and Set pages, 6 the metronome, 16 the clip's quantize (S6, below) |
| Metronome | — (a script's `metro 1` clicks) | the click, the shared bridge's (`fm1_seq_click_mix`, O11), on the Set page or SHIFT + 6 |
| LEDs | as before | SEQ in SEQ mode, PLAY/STOP while the transport runs, SEL while SHIFT is held; in SEQ mode the white keys show the bar's steps, lit for a note, the playhead's inverted, held keys lit and the steps under the held step's note blinking slowly, and F#3 and A#3 lit while they can page or nudge (in step record, the head's key blinking fast, A#3 lit, F#3 while it can step back); F#4 (MUTE) lit with no step held, C#5 and D#5 while there is a track before or after; MUTE held, white keys 1–8 lit while their track sounds; SEQ held, the focused track's key. REC on while recording or step recording, fast during a count-in or a waiting take, slow while Capture holds notes (O7). Sequencer notes light no key outside SEQ mode (O6) |
| Status line, help | as before | the tempo and the transport (posted by the worklet only when they change); a "Sequencer (lab)" entry in the help, "counting in" in the status line, and ENV, LFO, EDIT, SAVE and ARP in the stub list |
| Full velocity | — | SHIFT + white key 10 in SEQ mode: every step entered, and the keys played outside SEQ mode, at 127 |
| Sounds | one sound and two effect slots | up to four sounds, each with two inserts and a level, then the two slots as the master bus; SHIFT + PRESETS chooses the current sound (below, "Multi-sound") |
| RAM | the figure in the bottom bar, red past the budget | a meter there, which refuses whatever would pass the budget |

Tests and parity runs never load the demo pattern or route tracks 2–8:
only the browser's start chain does (`fm1-sim-render --lab --start` plays
that chain natively).

**The Track view** (docs/15 §4; `src/fm1_seq_view.c`), between the title
and bottom bars:

- the status line: the tempo, the eight tracks between it and the
  transport (S6: one cell each, the focused one gold, a muted one an
  outline), and PLAY, STOP, REC (the focused track recording; gold
  through its count-in or while the take waits for its bar) or STEP (step
  record);
- the grid: the four bars round the bar on the keys, 16 steps a row, one
  logged graphic: a filled cell for a note, an outline outside the loop
  (a note there a dim bar), the playhead inverted, a tick under a step
  with a probability, condition or invert, held steps framed, step
  record's head framed red, and a mark at both ends of the bar on the keys;
  a muted track's notes dim; with SHIFT held (no step held) the shortcuts'
  legend in its place (`Key 2  Track page` to `Key 16  Quant 0%`, with the
  metronome's, full velocity's and the clip quantize's states);
- the knob strip: four bars for KNOB1–4 on the current sound page, no text
  (O23, option b); the knob being turned is drawn brighter;
- the hint line: in step record, the head's step (`Step rec 17`, a tie
  `17-19`), or with SEL held `Keys move the head`; else that knob's name
  and value, as HOME's rows show them, or
  the bar the keys moved to, for two seconds or until SELECT or PRESETS
  moves on; with SEQ held `Keys 1-8  pick track`, with MUTE held `Keys
  1-8  mute`; otherwise the sound's model in gold, as HOME's first line;
- the bottom bar: `1/3 Seq T1` (sound page, mode, track) and the RAM figure.

**The Step pages** (S4), while steps are held: the held step on the first
line (`Step 7`, or `Step 7 +2` with two more held), then HOME's four rows
of label, value and bar. Page 1: Velocity, Length (`1/32` to `16 bars`,
`...` when the step's notes differ), Prob (`100%` to `10%`) and Condition
(`1:1` to `8:8`); page 2: Invert, and the Nudge (`+2 ticks`) and Note
(`C4 +2`: a chord) as read-outs. Under them, where HOME has its scope, the
bar's 16 steps: held ones gold, the steps under the first held step's
note marked. With SHIFT held the first line reads `Keys add a pitch` and
the strip `Tap SHIFT: clear`. The bottom bar reads `1/2 Step T1`.

**The Set, Clip and Track pages** (S6), HOME's rows again, the page's
subject on the first line: Set (`Set: all tracks`): Tempo (`120.00 BPM`),
Swing (`50%` to `80%`), Def quant (`0%` to `100%`), Metronome; Clip
(`Clip: track 1`): Speed (`1/8X` to `4X`), Length (`16 steps`, `--` with
no clip), Transpose (`-36` to `+36`), Quantize; Track (`Track 1 of 8`):
Route (`Sound`, `MIDI out`), Sound (`2 Macro Heavy`, `3 Empty`) or Channel
(`1` to `16`), Mute. Track page 2 lists the focused track's eight lanes,
each label's text after its last `:` (cut to 13 characters) and its 7-bit
base, an unused lane `--`. The bottom bar reads `1/1 Set`, `1/1 Clip T1`
or `1/2 Track 1`.

With no step held, SELECT pages through the sound and KNOB1–4 turn it, as
in HOME; past the sound's last page SELECT goes on to the Set, Clip and
Track pages. The UI state (`fm1_seq_ui_t`) is 552 bytes against its 1,024-byte
bound; it reads the transport and the focused clip once per block, the
grid's 64 steps again (through `fm1_seq_get_page`) only after the
sequencer had input, and the held step while one is held [verified:
`fm1-sim-render --sizes`].

**Step entry, for the manual** (manual chapter 07 waits for the lab switch
to go, O24; until then this is its text). In SEQ mode the white keys are
the 16 steps of the bar shown on the screen, numbered from the left, and
the black keys are sequencer controls: so far the two under OP1 and OP3
(the others get their jobs in later stages):

- **Enter a step:** tap its key. It gets the last chord you played (on the
  keys outside SEQ mode, or at MIDI IN), each note at the velocity you
  played it, or C4 at 100 if you have played nothing. Tap it again to
  clear it.
- **Edit a step:** hold its key. After a moment the Step page shows its
  velocity, length, probability and condition on the four knobs; turn one
  to change it. SELECT turns to the second page: invert, and where the
  note sits and what it is. Holding several steps edits them all.
- **Note length:** hold a step with a note and tap a later step: the note
  lasts until the end of that step; tap it again for its start.
- **Add a pitch:** hold the step, hold SEL (SHIFT) and press white keys:
  each adds its pitch in the current octave. A note at MIDI IN adds its
  pitch too.
- **Clear a step:** hold the step and tap SEL (SHIFT) on its own.
- **Move and transpose:** with a step held, OP1 and OP3 nudge it a little
  earlier or later (less with SHIFT), OCT− and OCT+ move it a semitone (an
  octave with SHIFT).
- **Bars:** OP1 and OP3, with no step held, show the previous and next bar;
  one empty bar past the pattern is there to grow it.
- **Full velocity:** SHIFT and white key 10 enter every step, and play the
  keys, at full velocity, until you press them again.
- **Restart:** SHIFT and PLAY/STOP while playing.

On a computer keyboard, `1` to `8` and `C V B N M , . /` are the 16 steps
and Shift is SHIFT. docs/15 §3.5 has the full gesture table, with the
commands each gesture sends.

**Record and Capture, for the manual** (S5; the same wait for the lab
switch). Everything you play on the keys (outside SEQ mode) or at MIDI IN
goes to track 1 as well as to the sound:

- **Record:** press REC. Stopped, a bar counts in (REC blinks fast) and
  recording starts with the transport; playing, it starts at once over a
  pattern, or at the next bar on an empty track. REC is lit while it
  records; press it again to stop. In SEQ mode while stopped, REC acts
  when you let go of it, so tap it.
- **Step record:** in SEQ mode, stopped, hold REC. Each white key you play
  goes onto the step under the red frame, and the frame moves on when you
  let go; keys held together make a chord. OP3 leaves a rest, or with keys
  held ties them into the next step; OP1 steps back (or unties). SHIFT and
  a white key move the frame to that step and clear it. On an empty track
  the pattern grows to what you play; on a pattern the frame wraps at its
  end. Notes at MIDI IN go in too (that is how sharps go in). Let go of
  REC when you are done.
- **Capture:** play first, keep it after. While something is waiting to be
  kept, REC blinks slowly. SHIFT and REC keep it: playing, it lands where
  you heard it ("Captured"); stopped, it also reads your tempo and starts
  playing. Then the screen shows the tempos it found: SELECT (or KNOB1)
  tries another, heard at once, and any other press keeps the one you
  hear. Over a pattern the take is fitted to the set's tempo instead, and
  the screen says which (any press closes it). Anything that edits the
  pattern, REC, and starting or stopping the transport empty what Capture
  holds.

docs/15 §5 (S5, as built) has the commands each gesture sends.

**Tracks, mute and the pages, for the manual** (S6; the same wait for the
lab switch). There are eight tracks, and the one you work on is the
focused track: the steps, REC, Capture and what you play all go to it.

- **Choose a track:** hold SEQ and press white key 1 to 8, in any mode (if
  you were outside SEQ mode, you are back there when you let go of SEQ).
  In SEQ mode MONO and POLY (C#5, D#5) choose the previous and next track.
  The screen says which; choosing another track empties what Capture
  holds, and it says that too. The track's sound becomes the one the keys
  play and HOME edits.
- **Mute:** in SEQ mode, tap OP6 (F#4) to mute or unmute the track. Hold it
  and the white keys 1 to 8 mute and unmute tracks 1 to 8; their lights
  show which are playing. The track cells at the top of the screen show
  the muted ones as outlines.
- **Pages:** hold SHIFT (SEL) to see the shortcuts. SHIFT and white key 2
  open the Track page: where the track plays (one of the four sounds, or
  MIDI out on a channel, which the simulator does not send) and its mute;
  turn SELECT for its lanes. SHIFT and 3 open the Clip page: speed (1/8X
  to 4X), length, transpose and quantize. SHIFT and 5, 7 or 9 open the
  Set page: tempo (1 BPM a click, 0.1 with SHIFT held), swing, the
  quantize new clips get, and the metronome. SELECT also walks from the
  sound's pages to these; SEQ goes back to the steps.
- **Metronome:** SHIFT and white key 6, or the Set page, turn the click
  on and off. With it on, a REC count-in clicks too.
- **Quantize:** SHIFT and white key 16 step the clip's quantize through
  0, the Set page's default and 100 %.

docs/15 §5 (S6, as built) has the commands each gesture sends.

**Multi-sound** (docs/15 §3.16; the owner's decision of 2026-10-02, in
place of docs/15 O10's one shared sound). With the lab switch:

- **Sound units.** Up to four sounds play at once (`FM1_APP_SOUNDS`), each
  an engine with its own two insert effects (`FM1_APP_INSERTS`) and its
  own level into the mix (0 to 100 %, unity by default); the two effect
  slots of the public page are the master bus after the mix. A track
  routed to the engine plays the sound its route index names (`route t 1
  k`: Sound k + 1); a track routed to an empty sound plays nothing. Without
  the switch every engine-routed track plays the one sound, as `fm1-render`
  without `--slots` does.
- **The current sound.** Hold SEL (SHIFT) and turn PRESETS: Sound 1 to 4,
  with a popup (`Sound 2 of 4` / `Shapes`). The keys and MIDI IN play the
  current sound, and HOME, PRESETS, ALGORITHM and the knobs edit it; a key
  or a MIDI note releases on the sound it started on. PRESETS on Sounds
  2–4 lists Empty before the sounds, which unloads that sound. Once a
  second sound is in use the title names the current one (`S2 Shapes`).
  FX mode's SEL stays the slot grab, so the current sound is chosen
  outside FX mode. The page's Sound menu is the current sound's.
- **FX mode** shows the current sound's chain on its first line (`S2 In1
  In2 Mix M1 M2`, the selected slot in the accent colour, an empty one
  dim) and the selected slot and its effect on the second; SELECT walks
  In1, In2 (the inserts), Mix (the four levels on KNOB1–4, a percent a
  detent, with each sound's engine) and M1, M2 (the master bus), page by
  page; ALGORITHM chooses the selected slot's effect; SEL then SELECT swaps
  the two inserts, or the two master slots. FX mode opens on the master
  slot the public page had selected.
- **The RAM meter.** The bottom bar's right side shows a bar and the
  percentage of `FM1_APP_RAM_BUDGET` (387,924 B, docs/11 §2) the chain
  takes, red past 100 %, and GLO's RAM line the same figure: every
  instance (`instance_size`, 32-bit in the browser's module, as on pi32v2),
  the sequencer's instance, event buffer, pending command record and UI
  state bound and click voice (36,428 B at 8 tracks), and a 512-byte mix block for each
  sound past the first [inferred: the firmware's layout]. A choice that
  would take it past the budget is refused (`fm1_app_select` returns -4,
  `FM1_APP_SELECT_RAM`) with a popup (`Shapes` / `does not fit` / `150K
  over budget`, the figure of the first choice refused), from the panel,
  the page's menus or the API alike, and PRESETS and ALGORITHM step past
  such a choice to the next one that fits, so whatever plays here fits the
  device. A chain already
  past the budget (the switch turned on over Shapes, PSX Verb and Plate)
  may shrink but not grow. Shapes twice does not fit; Macro, Shapes and
  Six-Op with four inserts and Plate do (about 349 KB at 32 bits).
- **Memory.** Each sound unit has a 512 KiB arena and each effect slot a
  256 KiB one: 4.5 MiB of the module's fixed 8 MiB. `fm1_app_t` is
  4,881,424 B natively (clang, 64-bit) [verified: `fm1-sim-render
  --sizes`].
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
  (`fm1_seq_host_dispatch_slots`, engines/seq.md), through its inserts,
  times its level (skipped at 100 %), and the sounds are summed in order,
  the first copied; then the master bus and the limiter. `fm1-render
  --slots` with `--sound`, `--insert` and `--level` renders the same float
  for float. With one sound, no insert and full level that is the public
  page's output to the bit [verified: every note-script scenario with and
  without `--lab`, `tests/test_sim_multi.py`].

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
MIDI IN note after a key's) says `"replayable":0`. With the lab switch the
sidecar starts with `--slots`, a note on another sound goes into it as
`--sound-note` (one on an empty sound too, which plays nothing in
either), a knob turn on another sound's page as `--sound-param-at`
and a level on the Mix page as `--level-at`; an insert's change, a bend
on another sound, or a MIDI note-off that another sound's note of the
same pitch would make ambiguous is not replayable. The harness takes the
same multi-sound flags as `fm1-render` (with `--lab`). `--format-check`
writes and reads back every verb.

## Parity: does the browser sound like the native engines?

`build-on-aeon.sh` renders 32 scenarios (`test/scenarios.json`) four ways
and compares the 16-bit output sample by sample [verified:
`www/fm1.wasm.json`, 2026-10-02]. Eighteen are note scripts: every engine
and effect, pitch bend, parameter changes mid-note, more notes than voices,
44,100 Hz, the low-pass gate. Six play sequencer verb scripts
(`test/seq/`, `fm1-render --cmd`): Test Sine's Volume under float locks
with a stop that sends the lanes back to their bases; two Six-Op tracks
with swing and a clip at twice the speed; locks on Six-Op's Patch, a list;
Capture committed while playing; a stopped Capture whose tempo is then
changed with `capsel`; and the metronome's click on, off and on again with
swing, then a REC count-in (`metro-click.verbs`, S6). Five are played on
the panel with the lab switch on:
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
2X, the click on and off with SHIFT + 6, a MUTE tap). Three play several sound
units with the lab switch (docs/15 §3.16): `multi-two-sounds-inserts`
(Macro through a Crush insert at 80 % and Shapes through Diffuse and
Ensemble at 60 %, notes on each, into the master Plate),
`multi-four-sounds-seq` (four tracks routed to Macro, Shapes, an empty
slot and Six-Op, each with its inserts and level, and lock lanes that
resolve on their own track's sound) and `multi-panel` (SHIFT + PRESETS, a
key, a MIDI IN note and a knob on Sound 2, the Mix page's levels, two
tracks on two sounds, replayed through `fm1-render --slots`).

| Against | Result |
| --- | --- |
| `render.cc` compiled to WebAssembly (Node) | identical in all 32: the app layer adds nothing |
| native `fm1-render`, GCC with musl (static, Alpine) | identical in all 32: the compiler adds nothing |
| native `fm1-render`, GCC with glibc | identical in 29. Sophie differs (23,286 and 694 samples, up to 4,082 and 12,330 LSB), and Fold within 1 LSB (19 samples) |

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
its panel UI and Track view, with step entry since S4, record and Capture
since S5, multi-sound, and tracks, mute, the pages and the click since S6:
32 of 32 scenarios pass, identical to musl and to render.js, and it imports
nothing; it is 514,270 bytes, up from 490,916 with S5 and 496,050 with
multi-sound (each alone), 466,635 before S4, 459,122 before S3 and 391 KB
before the sequencer [verified, 2026-10-02, `www/fm1.wasm.json`].

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
                                      typed commands out (lab switch)
                  src/fm1_seq_view.c  its screens: the Track view
                  src/fm1_tft.c   240 x 240 RGB565 frame buffer, 5 x 9 font
                  engines/        every engine, effect and the bus limiter,
                                  the sequencer core and its host bridge
```

`src/` is C99 with no heap: instance memory lives in fixed arenas inside
`fm1_app_t`. Nothing in it is browser-specific, so the same app layer builds
natively as `fm1-sim-render`, the test harness. Its panel logic and drawing
code are meant to carry over to the firmware, but not `fm1_app_t` as it
stands: it is 4,881,424 bytes (4.5 MiB of fixed arenas, four 512 KiB
ones for the sound units and ten 256 KiB ones for the effect slots, a
115,200-byte full frame buffer, and the sequencer's 32 KiB arena and 3 KiB
event buffer; clang, 64-bit), against the FM-1's 578 KB of SRAM and
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
memory) and about 450 KB. It links the sequencer core and bridge
(`SEQ_OBJ`: C99, no heap, no stdio) but not the script reader
(`host/seq_script.c`), which allocates and uses stdio; only the native
harness links that.

The sequencer's text comes in through `fm1w_text_buf()`, a 64 KiB buffer
(the largest `movy1` set an 8-track instance exports is 53,208 B), and
`fm1w_seq_text(len)`, which applies one script line at the coming block's
start and returns the bytes it took. `fm1w_seq_reset(tracks)` makes a new
instance and applies the default route (track 0 plays the sound, as in
`fm1-render`); `fm1w_seq_dropped()` reports any event that did not fit.
`fm1w_set_lab(on)` is the lab switch, and `fm1w_seq_info()` returns eight
32-bit words for the status line: playing, the tempo in hundredths of a
BPM, recording, the watched track, counting in, following an external
clock, and the master tick's two halves.

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
change of sound; the 1,109-screen layout sweep; the panel against the manual's formula (octave,
transpose, reset); buttons and encoders; with the lab switch, PLAY/STOP's
LED while playing, SEQ mode, the white keys following the playhead in SEQ
mode (eight points across two bars), HOME's key LEDs unchanged and the
Track view's knob hint cleared by a new sound; an effect slot emptied on its
second page; sounds that refuse a 48 kHz host stepped over and the previous
one kept; the page loads nothing from other origins; the exports match; and
`www/fm1.wasm` matches its record. The record carries two source hashes
(`tools/source_hash.py`): engines/ (less Markdown) and sim/web's own inputs
(`src/`, `mk/`, `build.sh`, the parity test, its scenarios and their
sequencer scripts in `test/seq/`, the harness, the loader), which since
the module links the sequencer include `engines/seq/` and
`engines/include/fm1_seq*.h` too. When sim/web's inputs have changed since the last
build, the test fails in CI (`CI=true`) and warns locally; when only the
engines have, it warns, so engine work elsewhere does not need aeon.
Rebuild with `build-on-aeon.sh` before publishing the page or merging a
change to the simulator.

`tests/test_sim_multi.py` checks multi-sound (lab): SHIFT + PRESETS and
its popups, the keys and a MIDI note-off on the sound that started them,
Empty on Sounds 2–4, FX mode's walk and the Mix page, the insert swap, the
RAM meter's figure (every instance and the fixed costs) and its refusals
from the harness, PRESETS and ALGORITHM, tracks routed to sound units as in
`fm1-render --slots` (and every one on sound 0 without the switch), a bend
on another sound marked not replayable, and every note-script scenario
rendering the same bytes with the switch on and off.

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
back; the demo pattern only on the start chain with the switch on; the
switch off changing nothing; a sound changed from the panel marked not
replayable; and the UI state's size. `tests/test_seq_core.py` checks
`fm1_seq_get_page` against every Movy fixture's `movy1` export.

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
  SEQ, PLAY/STOP and REC work (docs/15 stages S3 to S5): steps are entered,
  recorded and captured on the panel; more tracks and the Set, Clip and
  Track pages come in S6, locks in S8.
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
