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
