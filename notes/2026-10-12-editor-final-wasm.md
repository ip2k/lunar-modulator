# Editor integration Wasm rebuild

The paused live-MIDI-effect clock repair is linked into the browser module
[verified]. The rebuild ran on Hera in isolated stage
`/home/claude/mvave-fm1/editor-final-build-20261012`, using the recorded Alpine
3.22 and Emscripten 6.0.10 image digests. The generated
`sim/web/www/fm1.wasm.json` records source hashes, metadata and results.

Module SHA-256:
`761b18d3e9a676494a02e2d87867aa0eeab45bad6ab82062fad385a2f8bc2ebc`.
Module size: 1,584,573 bytes.

Validation [verified]:
- 108 audio/display parity scenarios passed; all 108 match JavaScript and
  musl, and 105 are bit-identical to glibc, with the recorded tolerances for
  the remaining floating-point reference cases.
- 18 DX7 SysEx cases and native/browser metadata parity passed.
- Edit parity has zero audio LSB difference. The 30-second edit storm applied
  82,728 edits across 10,341 quanta with zero late quanta and no resyncs.
- The new module passed ten native MIDI transport/visibility/project checks
  in Chromium, Firefox and WebKit, each with zero page errors.

These are build and automated runtime results. Exact-head review, GitHub CI,
merge, Pages deployment and owner controller/listening acceptance are separate
gates. No physical-device write occurred.

Semantic tooling: Serena selected the absolute integration worktree and
returned the MIDI highlight function and its known caller [verified].
Rarefaction selected the primary checkout, where that file was absent; its
index was not used as evidence for this change. The shared server root was
preserved and source inspection supplied the fallback.
