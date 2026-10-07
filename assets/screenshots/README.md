# Screenshots

Pictures of Lunar Modulator in the virtual FM-1 (`sim/web/`), for the
README, the user manual (`{{screen NAME ...}}` figures) and DEVELOPERS.md
(the parity figure). Taken on 2026-10-06 in headless Chromium 153
(Playwright 1.63) from `sim/web/www/` as committed with them (`fm1.wasm`
955,543 B, `8d1f4f74…`), all in one run of
`sim/web/test/readme-screenshots.mjs`, after the UI audit's screens
landed (`notes/2026-10-06-ui-audit.md`: the colour map, the Spleen faces,
the context line, FX mode's chip, MATRIX in colour, the track strip by
sound), and again after the review that put a short list whole in the
large face (none of these pictures shows a list) and the merge of glide
and the voice modes (Macro's pages are four: *1/4 Sound*). They were
retaken with their names kept; `parity.png`, `screen-fx.png` and
`screen-matrix.png` came out byte-identical. From one run to the next only what moves with the
sound differs: the oscilloscope strips, the meters and the lit keys.
`screen-seq.png` and `screen-matrix.png` alone were retaken later the same
day (module 955,320 B), when the track strip's tiles took their sounds'
numbers and MATRIX's mark moved 4 px clear of the source and the
destination; the run's other pictures were left as they were.
`screen-sixop.png`, `screen-shapes.png` and `screen-fm6.png` were retaken
with their names kept after PR #79 gave those engines a third page (the
bar reads *1/3 Sound*), from the module of the GPL follow-ups (1,273,791 B,
44,100 Hz), on 2026-10-06; Shapes' meter now reads 87 %.

| File | What it shows |
| --- | --- |
| `virtual-fm1.png` | The page at 1440 px: the name, the to-scale panel, Macro (VA Pair) through Plate with LFO1 cabled to Timbre (its name, and the bracket on its bar, in the modulation colour, the live tick white), a C minor chord held (three key LEDs) while the demo pattern plays (PLAY/STOP lit). REC is dark: the chord went down before PLAY/STOP, which empties Capture |
| `screen-macro.png` | The firmware's screen, Macro on VA Pair (the context line: VA Pair, 5/8), while a C major chord sounds |
| `screen-shapes.png` | Shapes on Pluck |
| `screen-macro-heavy.png` | Macro Heavy on Str Machine, named in full on the context line (String Machine) |
| `screen-sixop.png` | Six-Op FM on its default patch, E.PIANO 1 |
| `screen-fm6.png` | FM6 on its first voice, TINE EP, while a C major chord sounds |
| `screen-sophie.png` | Sophie's kick pad, 50 ms after MIDI note 36 |
| `screen-drums.png` | Drums' kick pad (the Deep kit), 50 ms after MIDI note 36 |
| `screen-fx.png` | FX mode: the chain S1 In1 In2 Mix M1 M2 (S1 in Sound 1's blue), Plate in M1, PSX Verb in M2 chosen (the lilac chip; "PSX Verb", "master" on the next line), and its first page |
| `screen-params.png` | Macro's first page after KNOB1–4 turned (2-op FM, 0.68, 0.28, 0.81) |
| `panel-params.png` | The same on the panel, with the four knobs turned; the chord is held, and a start and stop of the transport emptied Capture, so REC is dark |
| `screen-seq.png` | SEQ mode's Track view while the demo pattern plays: the status line (120 BPM, the eight tracks as tiles in Sound 1's blue, each with its sound's number, 1, the first focused and taller, PLAY), the grid with the playhead, the knob strip, the model line |
| `screen-matrix.png` | The modulation matrix: the default rack's two RTRG cables and LFO1's cable to Sound 1's Timbre, chosen; sources in the modulation colour, each mark 4 px clear of its source and destination, the hint "To S1 Timbre" |
| `page-editor-flow.png` | The advanced editor on *First orbit* at 1,280 px: the outline, the Flow with the four sounds into the mix and the master slots, the screen card |
| `page-editor-sound.png` | Sound 3 in the editor: its engine, inserts and the cables into it |
| `page-editor-table.png` | Modulation as a table: the rack as eight cards with live traces and the matrix |
| `page-editor-map.png` | Modulation as the Map, with the envelope in rack position 3 in focus |
| `page-editor-memory.png` | The Memory page: the share by part, what is free, what would still fit |
| `parity.png` | The browser module's output against native `fm1-render`: 25 ms of Six-Op FM, and 0 of 105,882 samples different over the whole render |
| `phone.png` | The page at 390 × 844 (2× pixels), in `virtual-fm1.png`'s state: the panel keeps playable sizes and scrolls sideways in its own box |

The `screen-*.png` files are the firmware's 240 × 240 frame buffer with each
pixel doubled, not a photograph of the page. The page's small text is Exo 2,
bundled since 2026-10-01 (`sim/web/www/fonts/README.md`); `parity.png` is
drawn on the page and is set in it too since this run (its waveforms and
figures are the same as in the 2026-10-01 figure, which fell back to
another face). The run's report checks that REC is not lit in
`virtual-fm1.png`, `panel-params.png` or `phone.png`: until 2026-10-06 the
first two caught REC blinking for a chord that Capture held, and
`virtual-fm1.png` and `phone.png` still showed the RAM figure in KB from
before the RAM meter.

## Remaking them

```bash
FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh --readme-screenshots
```

builds and checks the module, runs the page test, then
`sim/web/test/readme-screenshots.mjs`, which writes the pictures and a
report to `sim/web/build/readme-screenshots/` (the parity figure from the
parity run's own renders). Look at every picture before copying it here:
no text may overlap, crowd or be cut by an edge (the page's sideways
scrolling panel on a phone is the one deliberate cut). The report fails if
the figure's text runs come closer than 4 px, if the phone page scrolls
sideways, or if REC is lit in a panel picture.

The `page-editor-*.png` pictures (the advanced editor, for the manual's
chapter 15) are made by `sim/web/test/editor-shots.mjs`, which runs in the
Playwright container on aeon like the other page tests (build-on-aeon.sh
stages the tree; run it by hand with `PLAYWRIGHT_DIR=/pw node
sim/web/test/editor-shots.mjs sim/web/www OUT`), at 1,280 px on the *First
orbit* example. Each was looked at, then rewritten as a 256-colour PNG with
`assets/web-editor/src/shrink.mjs` (the editor is flat colour: nothing a
reader can see is lost), 2026-10-07, Chromium 153.
