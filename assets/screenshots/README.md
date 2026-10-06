# Screenshots

Pictures of Lunar Modulator in the virtual FM-1 (`sim/web/`), for the
README, the user manual (`{{screen NAME ...}}` figures) and DEVELOPERS.md
(the parity figure). Taken on 2026-10-06 in headless Chromium 153
(Playwright 1.63) from `sim/web/www/` as committed with them (`fm1.wasm`
786,256 B, `3dc2ef29…`), all in one run of
`sim/web/test/readme-screenshots.mjs`.

| File | What it shows |
| --- | --- |
| `virtual-fm1.png` | The page at 1440 px: the name, the to-scale panel, Macro (VA Pair) through Plate with LFO1 cabled to Timbre (the gold diamond, bracket and red tick on its row), a C minor chord held (three key LEDs) while the demo pattern plays (PLAY/STOP lit). REC is dark: the chord went down before PLAY/STOP, which empties Capture |
| `screen-macro.png` | The firmware's screen, Macro on VA Pair, while a C major chord sounds |
| `screen-shapes.png` | Shapes on Pluck |
| `screen-macro-heavy.png` | Macro Heavy on Str Machine (its string machine model) |
| `screen-sixop.png` | Six-Op FM on its default patch, E.PIANO 1 |
| `screen-sophie.png` | Sophie's kick pad, 50 ms after MIDI note 36 |
| `screen-drums.png` | Drums' kick pad (the Deep kit), 50 ms after MIDI note 36 |
| `screen-fx.png` | FX mode: the chain S1 In1 In2 Mix M1 M2, Plate in M1, PSX Verb in M2 chosen, and its first page |
| `screen-params.png` | Macro's first page after KNOB1–4 turned (2-op FM, 0.68, 0.28, 0.81) |
| `panel-params.png` | The same on the panel, with the four knobs turned; the chord is held, and a start and stop of the transport emptied Capture, so REC is dark |
| `screen-seq.png` | SEQ mode's Track view while the demo pattern plays: the status line, the grid with the playhead, the knob strip, the hint line |
| `screen-matrix.png` | The modulation matrix: the default rack's two RTRG cables and LFO1's cable to Sound 1's Timbre, chosen |
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
