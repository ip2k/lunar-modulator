# Preview scope continuity — 2026-10-09

The owner reported holes in the cyan staircase waveform in the editor's
“On the FM-1” preview. This stream starts from `origin/main`
`0a033d4eeca12103dbdbddbd9124fc078196c936` on
`fix/2026-10-09@scope-line-continuity`; the separate preview-sizing stream
owns the CSS correction. No hardware traffic or firmware change.

## Finding

- [verified] `draw_scope` in `sim/web/src/fm1_app.c` already joins successive
  sample positions with an inclusive vertical span at each next column.
  Adjacent spans share a row, so the native trace is edge-connected, including
  abrupt amplitude changes. `fm1_tft_paint` writes the full requested span.
- [verified] The editor receives the same native 240×240 RGB565 framebuffer
  through `putImageData`, without an independent waveform renderer.
- [verified] The actual C renderer produces one connected component for the
  sine probe at 240 pixels (489 trace pixels). Nearest-neighbour reduction to
  190 pixels drops connectors: 299 trace pixels in 65 edge-connected
  components. The rendered native and reduced images were visually inspected.
  The images are ignored local artifacts in `scratch/scope-continuity/`.
- [inferred] This explains the supplied narrow-preview screenshot's gaps.
  Preserve the native minimum preview size; changing the already connected
  source raster or blurring the image would address a different problem.

## Regression and handoff

`tests/test_sim_scope.py` compiles `sim/web/test/fm1_scope_check.c`, which
includes the actual application source to reach its private `draw_scope`.
The test linker discards unrelated engine paths; its test-only module header
disables FM6, which the scope does not use. There is no production C change.

[verified] The focused suite passes 31 cases on macOS and on aeon Linux
(`lunar-asan:ubuntu-24.04`, GCC, network disabled, two CPUs/1 GiB): silence, sine slopes,
square steps, alternating over-range samples, quiet signals, three scope
heights and both unwrapped/wrapped ring buffers. It checks four-neighbour
connectivity, all 228 sample columns, confinement to the scope rectangle,
preservation of surrounding pixels and identical output after ring wrapping.
The reduced-size case reproduces connector loss.

Run with the project Python environment:

```sh
python -m pytest tests/test_sim_scope.py -q
```

Rarefaction oriented the original checkout's `draw_scope` by exact position;
its configured root is not the managed worktree. Serena was explicitly
activated on this stream's managed root and inspected `fm1_tft_paint` there.
Compiler/test evidence, rather than the approximate clangd index, establishes
the raster behavior. These are native UI checks, with no device or browser
runtime claim. The parent stream owns browser validation of preview sizing.
