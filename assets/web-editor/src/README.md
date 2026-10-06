# The Advanced editor's mockups: sources

The six final mockups of `notes/2026-10-06-web-editor.md`, as static HTML
and CSS, and the scripts that render and check them. The PNGs one folder up
are their renders at 1440 × 900 and 1024 × 768, full page.

| File | What it is |
| --- | --- |
| `01-workbench.html` … `06-project.html` | The mockups |
| `editor.css` | The tokens and roles of `sim/web/PALETTE.md` v2 (Rosé Pine Moon and the four sound colours), and the editor's components |
| `shell.js` | The frame every mockup shares: app bar, outline with the FM-1's screen, status bar |
| `editor.js` | Draws parameter rows, scopes, curves and cables from `meta.js` by the editor's rules, then checks the layout |
| `meta.js` | A subset of `fm1-render --list` and `--list-mod` from the UI colour lane's build, with instance sizes at 44,118 Hz |
| `render.mjs` | Renders every mockup in a Chromium headless shell over the DevTools protocol (no npm packages) and prints the check |
| `shrink.mjs` | Rewrites the PNGs as 256-colour palette PNGs, keeping the 168 most used colours exact |
| `img/` | The FM-1 screens (the native harness's renders of the example project) and the panel capture they are laid into |

The fonts come from the page: `sim/web/www/fonts/` (Audiowide and Exo 2,
SIL OFL 1.1).

## Rebuild

```bash
cd assets/web-editor/src
CHROME=/path/to/chrome-headless-shell node render.mjs   # all, or: node render.mjs 02 05
node shrink.mjs ../*.png
```

Any Chromium headless shell works; Playwright's (`chromium_headless_shell`)
is the one the renders were made with. Node 22 or newer (for its built-in
WebSocket).

## The check

`editor.js` prints `LAYOUT` lines for: text over text, text over a mark
(thumbs, brackets, ticks, tags, jacks, pills), a mark within 3 px of text
on its line, a cable over text, text outside its panel or block, clipped
text, and a page wider than its window. The last run reported none in all
twelve renders. Two overlaps are deliberate and skipped: the block in hand
during a drag (`.intent` in `03-chain`), and a dimmed cable passing under
an amount pill's opaque ground in `05-map` when no clear place exists.

## The example project

Designer A's "First orbit", built in the native harness
(`sim/web/build/native/fm1-sim-render`, the UI colour lane's build):

```bash
fm1-sim-render --rate 44118 --engine drums --param Kit=1 \
  --insert 0:comp --insert-param 0:Character=3 --insert 0:gate \
  --sound 1:macro --sound-param 1:Model=7 --insert 1:echo \
  --sound 2:macro --sound-param 2:Model=0 --insert 2:filter --insert-param 2:Type=1 \
  --insert-param 2:Cutoff=420 --insert-param 2:Resonance=0.3 --insert 2:drive --insert-param 2:Type=1 \
  --sound 3:dx7 --insert 3:plate --fx sat --fx limit \
  --level 0:85 --level 1:70 --level 2:80 --level 3:60 --mod orbit.mod --slots --screen out.ppm
```

with `orbit.mod`:

```
rack default
slot 1 rtrg > env3:gate
slot 2 rtrg > env4:gate
mod 6 function Mode=Cycle Rise=0.4 Fall=0.6
set 1 Rate=0.35 Shape=Triangle Sync=1/4
set 3 Attack=0.05 Decay=0.45 Sustain=0.4 Release=0.5
slot 3 lfo1 > snd3.fx1:Cutoff amt=35
slot 4 lfo2 > snd2:Timbre amt=20 via=s2vel
slot 5 env3 > snd2:Morph amt=60 voice
slot 6 env3 > fx1:Drive amt=30 voice
slot 7 chance5.smth > snd4:Brightness amt=25
slot 8 lfo1.wrap > function6:trig
slot 9 function6 > lfo1.rate amt=30
slot 10 beat > chance5:trig
```

It reports 300,672 B of RAM, slot 6 refused and slot 9 a tick late. The
screens in `img/` were taken with the panel driven to each page; the values
the note marks illustrative were not asked of the harness.
