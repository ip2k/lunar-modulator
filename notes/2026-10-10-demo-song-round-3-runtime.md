# Demo song Round 3 runtime acceptance

The frozen Round 3 project files at `cdf8d8fcc0bd89518f3fe28ec1a6661a827c19bc`
passed the bounded full-arrangement native/Wasm harness and Chromium
preload/play/stop/UI Save/fresh-context Open harness on aeon. This is runtime,
state, and browser workflow evidence; it is not a listening or hardware result.

The native renderer was
`/home/claude/mvave-fm1/worklet-ready-final-c44a808/src/sim/web/build/native/fm1-sim-render`
(SHA-256 `a17a9a3255dc80a88a528f4ba24ecf85d14852fb310cb8fc831314285ce4dda2`).
The Wasm module was SHA-256
`4667498f919529ba0f1059f127ea02e60c2c2a76ee5bc16983cfeabbb96b76ec`.
The R3 manifest SHA-256 is
`1c1e003dbb4f25f61209a93600eeaa4659af689900d3c55103c933a475619730`.
The renderer and module paths were verified on aeon before execution. The
browser harness used the checked-in simulator assets from integration checkout
`87bd06ff5b26f7017848cbb2ce61104e95cb73bb`, with the four R3 `.lunar` files
copied byte-for-byte into its example library. Browser testing used Chromium
153.0.8010.12 in `mcr.microsoft.com/playwright:v1.63.0-noble`, image digest
`sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27`.

| Song | Tempo | Bars | Runtime | Wasm RAM | Wasm peak / RMS | Native RAM | Native events |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Afterglow Relay | 92 BPM | 76 | 198.261 s | 67% | 0.8093 / 0.08758 | 73% | 11,672 |
| Event Horizon | 144 BPM | 116 | 193.333 s | 67% | 0.8624 / 0.09772 | 73% | 19,239 |
| Packet Bloom | 112 BPM | 88 | 188.571 s | 54% | 0.7425 / 0.08151 | 61% | 14,097 |
| Neon Transit | 120 BPM | 104 | 208.000 s | 67% | 0.7765 / 0.08485 | 73% | 16,343 |

All four Wasm runs rendered finite, non-silent audio, saved and reloaded without
repairs or skipped content, and stopped within one render block of the declared
arrangement duration. All four native runs loaded with `ok=1`, no skipped or
left-out content, audible finite output, stopped at end, and zero dropped
sequencer events. Wasm/native render receipts are under
`/home/claude/mvave-fm1/round3-cdf8d8fc/out/demo-songs.json`; WAVs are in its
`out/audio/` and `out/native/` directories. The browser receipt is
`/home/claude/mvave-fm1/round3-cdf8d8fc/out/browser/demo-files.json`; it records
all four examples listed, played, saved through the UI, and reopened in fresh
contexts with equal project state, with zero page exceptions. Browser
screenshots are alongside that receipt. Large WAVs and screenshots remain on
aeon rather than in Git.

No physical FM-1 was used. RMS and peak are measurements, not a claim of
subjective musical quality. The independent critic's Round 3 source review
remains a separate gate; this checkpoint does not change the frozen song
assets.
