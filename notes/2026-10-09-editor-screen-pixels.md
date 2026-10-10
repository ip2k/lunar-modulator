# Editor preview pixel preservation

Owner reported incomplete-looking bitmap lettering and gaps in the waveform
in the advanced editor's **ON THE FM-1** preview (2026-10-09).

The canvas has a 240 by 240 framebuffer, but the previous desktop sidebar
rendered it at a fractional smaller size; tablet and phone rules used 144 and
96 pixels respectively [verified: editor.js and editor.css on main 0a033d4e].
Nearest-neighbour reduction can discard single-pixel font strokes and waveform
connectors. The native scope already joins adjacent samples [verified: source
inspection; independent scope regression work is separate].

The preview now has 240 by 240 CSS content pixels, with its one-pixel border
outside that area. Desktop navigation gets a 280-pixel column; the phone card
stacks the caption beneath the screen. Tablet captions retain their adjacent
column. No firmware raster or font changes are needed.

## Validation and state

- [verified] Native macOS Safari at localhost:8780 shows complete lettering,
  a continuous live Macro waveform, and an unclipped screen and caption in
  the desktop sidebar. The simulator's demo played during visual inspection;
  playback was then stopped. This is a visual check, not a listening test.
- [verified] CSS inspection retains native dimensions at all breakpoints;
  phone-specific layout uses one column. Mobile hardware was not tested.
- [verified] `git diff --check` passes.
- Working branch: `fix/2026-10-09@editor-screen-pixels`, based on main
  `0a033d4eeca12103dbdbddbd9124fc078196c936`. Push and PR status are recorded
  in GitHub; integration still requires passing CI.

The owner's latest "sounds are fine" feedback accompanies the visual report.
The earlier Sound 2 A/B crackle report remains under investigation on its own
branch and is not declared resolved by this preview fix.

## CI assertion correction and responsive bounds

[verified] PR125 head `83e9aa8f1f189f776563187e15752bb4f98834fe`,
[CI run 38009726717](https://github.com/ip2k/lunar-modulator/actions/runs/38009726717),
failed Chromium job `114086681572` and Firefox job `114086681508` on the
same obsolete `editor-reach.mjs` assertion: "the screen card shows a 96 px
screen". Both logs measured the intended outer `[242,242]` bounds at a
375-pixel viewport, with page width also 375. Other logged page checks and
audio checks passed; WebKit was cancelled and supplies no completed verdict.
This identifies a stale size expectation, not an observed preview overflow.

The reach test now requires a 240 by 240 framebuffer **and** 240 by 240 CSS
content area, with a 242 by 242 border box. It checks that screen and caption
fit their card, remain separate, avoid clipping ancestors and page overflow,
and fit horizontally in the viewport. The phone, tablet and desktop sweep
includes 320, 375, 640, 641, 768, 1179, 1180 and 1440 pixels. Existing
accessibility, layout, telemetry, audio and panel latency gates are unchanged.
The simulator README's current phone description was corrected too; older
ED5a notes describe the historical smaller preview.

- [verified] Bounded LAN Playwright 1.63.0 runs: Chromium 153.0.8010.12,
  Firefox 155.0 and WebKit 26.5 each pass all 47 reach checks. Receipts are
  `notes/data/2026-10-09-editor-preview-{chromium,firefox,webkit}.json`.
  Chromium's initial sweep used 600/601; a separate focused Chromium probe
  checked 640/641 and rejected the prior main stylesheet's 96 by 96 content
  at 375 pixels (`notes/data/2026-10-09-editor-preview-transitions.json`).
- [verified] Inspected captured card screenshots at phone 320, tablet 768
  and desktop 1440 in Chromium, plus WebKit phone and Firefox desktop:
  bitmap text is intact and captions fit without overlap or clipping.
- Containers used the existing `docker-batch.slice`, bounded CPU/memory and
  a container-local PulseAudio null sink. Artifacts remain on aeon at
  `/home/claude/mvave-fm1/editor-screen-pixels-20261009/src/results/`.
- [verified] Rarefaction oriented the canvas declaration at the main root
  (inferred JS project); Serena navigated the exact worktree's same symbol.
  CSS and test changes were inspected directly. `git diff --check` passes.

These are automated Linux browser and screenshot checks, not mobile device
or owner listening evidence. The localhost:8778 listening server and the
separate A/B correction branch were untouched. Exact updated-head CI remains
required before integration.
