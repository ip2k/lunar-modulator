# Screenshots

Pictures of Lunar Modulator in the virtual FM-1 (`sim/web/`), for the
README. Taken on 2026-10-01 in headless Chromium 153 (Playwright 1.63) from
`sim/web/www/` as committed with them (`fm1.wasm` `633b45af…`).

| File | What it shows |
| --- | --- |
| `virtual-fm1.png` | The page at 1440 px: the name, the to-scale panel, Macro (VA Pair) through Plate, a C major chord held (three key LEDs) |
| `screen-macro.png` | The firmware's screen, Macro on VA Pair, while the chord sounds |
| `screen-shapes.png` | Shapes on Pluck |
| `screen-macro-heavy.png` | Macro Heavy on Str Machine (its string machine model) |
| `screen-sixop.png` | Six-Op FM on its default patch, E.PIANO 1 |
| `screen-sophie.png` | Sophie's kick pad, 50 ms after MIDI note 36 |
| `screen-fx.png` | FX mode: Plate in slot 1, PSX Verb in slot 2 and its first page |
| `screen-params.png` | Macro's first page after KNOB1–4 turned (2-op FM, 0.68, 0.28, 0.81) |
| `panel-params.png` | The same on the panel, with the four knobs turned |
| `parity.png` | The browser module's output against native `fm1-render`: 25 ms of Six-Op FM, and 0 of 105,882 samples different over the whole render |
| `phone.png` | The page at 390 × 844 (2× pixels): the panel keeps playable sizes and scrolls sideways in its own box |

The `screen-*.png` files are the firmware's 240 × 240 frame buffer with each
pixel doubled, not a photograph of the page.

The page's small text is Exo 2, bundled since 2026-10-01
(`sim/web/www/fonts/README.md`). `virtual-fm1.png`, `phone.png` and
`panel-params.png` were retaken with it. The screen pictures and the parity
figure do not use the page's fonts and were kept.

Still current after the 2026-10-01 review's page changes (a contrast
tweak to text on surfaces, a message for insecure origins), which none of
the pictures show: a fresh run differed from these only in the level meter
and the oscilloscope, which follow the audio's timing [verified: pixel
comparison of every picture].

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
the figure's text runs come closer than 4 px or if the phone page scrolls
sideways.
