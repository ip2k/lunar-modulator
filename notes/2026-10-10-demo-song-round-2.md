# Four demo songs: Round 2 revision record

Round 2 revises the four sample-free projects after the independent critic's
Round 1 report. The revisions below are source and arrangement changes; they
are not listening claims or final scores. The generator in
`tools/demo_songs.py` remains the source for the checked-in project files.

## Response to Round 1

| Finding | Round 2 action |
| --- | --- |
| A, E — pickups need phrase anchors and answers need space | Kept the short pickup notes, lengthened selected bass roots, and let the last note of each four-bar peak/build phrase reach the barline. Track 7 answers later in lead rests rather than doubling the full hook. |
| B — second sections and repeated peaks need development | Rewrote Vrs2/B-side bass and lead contours; scene 6 now changes its lead contour, rotates the chord voicing, raises the late response, and applies a separate late lock lift. Repeated chain entries remain intentional repetitions of their full eight-bar scenes; the chain format has no occurrence-level automation. |
| C — builds, bridges, and endings need clearer direction | Four-bar build locks now use a different rise-and-release shape for each style, drums tighten in the supported build patterns, and the last build bar withholds late attacks. Contrast sections remove most kick/hats rather than relabeling the verse groove. Each outro uses a written four-chord cadence and ends on a held tonic lead note. |
| D — harmony needs more movement | Later scenes begin at different places in the chord cycle; the second peak uses a changed chord-stack inversion. Every ending moves through its song-specific cadence to the tonic. These are structural voicing changes, not a claim of fully optimized voice leading. |
| F, H — modulation should follow the arrangement | Bass Timbre and lead Brightness locks now trace style-specific four-bar build shapes, fall during the contrast scene, and lift later in each second peak. This uses the existing supported per-step lock format. |
| G — future-bass swell did not span the arp interval | The future-bass arp Gate is 100%, and peak chord triggers last 192 raw Movy ticks across four eighth-note arp intervals (48 ticks each). The two-beat hold carries the arp into the next two-beat voicing; this is a legato chord change, not a whole-bar pad. |

## Change map

- **Afterglow Relay:** Lift lock contour rises then releases; the eight-bar
  bridge removes the kick for its first half and leaves sparse markers; Vrs2
  uses a changed bass/lead phrase; Hook2 changes its chord inversion and late
  reply; the C–F–G–Am outro settles on A.
- **Event Horizon:** build locks use the broadest rise, the last bar clears
  chord attacks from step 12 and other new attacks from step 14; the break
  removes the kick and reduces bass to two sparse attacks; Vrs2 changes contour; Drop2 raises its
  second-half modulation and revoices the stack; Ab–Db–Eb–Fm closes on F.
- **Packet Bloom:** the B-side changes bass rhythm and lead order; Glitch uses
  isolated drum markers; Bloom2 changes the chord stack and upper reply; the
  F–Bb–C–Dm outro leaves a held D closing tone. Warble remains its distinctive
  lead insert.
- **Neon Transit:** the Pre has a style-specific rising lock and last-bar
  release; the four-bar bridge removes the kick; Vrs2 changes the verse
  phrase; Chor2 revoices the chord stack and adds a late upper response; the
  G–C–D–Em outro resolves to E.

## Verification boundary

`tools/demo_songs.py --write`, `--check`, `python3 -m py_compile`, and
`git diff --check` pass. `engines/build/fm1-state check` reports 0 repaired,
0 skipped, and 0 defaulted records for each source project. The checker
reports 244,640, 245,312, 195,360, and 244,640 bytes respectively against
its 387,924-byte project budget. These are file-level and state-loader checks;
they do not establish full-chain audio quality or physical FM-1 fit. Parent
acceptance owns complete native/Wasm renders. No one has accepted Round 2 by
ear yet; the independent critic will score the frozen revision after it is
checkpointed.
