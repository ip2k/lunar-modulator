# Vendored Schwung module: Sophie

| | |
| --- | --- |
| Upstream | https://github.com/mestela/schwung-sophie at `5682295124170ebd979b6a3e0add7e86af3693c6` (2026-09-09, "Release Sophie v0.5.1") |
| Author | Matt Estela |
| Licence | MIT (`LICENSE`, copied whole; checked 2026-09-30). No other licence, notice or third-party code in the repository |
| What it is | A 16-pad metallic FM percussion sound generator: 12 one-shot voices, four operator models, per-pad pitch sweep, crush, drive, a short ring delay and a multimode filter. MIDI notes 36–51 play the pads |
| What is vendored | The DSP (`src/dsp/sophie.c`), the module's own copy of the Schwung header it includes, and `src/module.json` (metadata). Not vendored: the JavaScript UI (`src/ui_chain.js`), the Movy config, docs, tests and build scripts |
| Local changes | `sophie.c` includes a local multi-turn phase-wrap correction; all other listed files remain byte-identical to upstream |
| Built as | engine `sw-sophie` (`engines/src/sw_sophie.cc`) through the Schwung v2 shim; see `engines/schwung.md` |

| File | Upstream path | SHA-256 |
| --- | --- | --- |
| `sophie.c` | `src/dsp/sophie.c` | `6a43cd14ca377e3ce9d0bf3e63e121a9f04146252bf21b8a5ccea2b09fc1e1b1` |
| `plugin_api_v1.h` | `src/dsp/plugin_api_v1.h` | `e6b2e3699a9e9229d32017750e55d9bd92b58dd7f68f3faff868664d30134928` |
| `module.json` | `src/module.json` | `ce0703b9a2e3e25eaa494e3ae8c59c461370798efdfce5fbc224668ba5b3466e` |
| `LICENSE` | `LICENSE` | `45ed064a3df7798cd92805dbd00ba2962068d26e72d29afada8b864e1c5bf63d` |

Notes for the next update:

- Pinned upstream `sophie.c` SHA-256: `efbf03b42b23d40f9c12f757f7cd253bdefae8dd45cab6184bfe2b2ce8da5974`.
- The phase-wrap correction preserves the original one-turn arithmetic and
  applies bounded quotient reduction only when one subtraction/addition is
  insufficient. `engines/test/sophie_phase_test.c` covers the high-ratio,
  high-frequency edge at 44,118 and 8,000 Hz.

- `plugin_api_v1.h` here is Sophie's own trimmed copy. Its `host_api_v1_t`
  appends `get_project_bpm` where Schwung's canonical header has its
  `reserved` run (the "breakbeat drift" that header warns about). Sophie never
  calls it, and the shim passes zeros there.
- `create_instance` makes one `calloc` of 76,752 bytes (the 12 voices with
  their 1,536-sample ring delays, and 16 pad patches). The adapter's arena is
  sized for it; the selftest fails if it grows.

Re-vendoring:

```bash
git clone https://github.com/mestela/schwung-sophie reference/schwung-sophie
git -C reference/schwung-sophie checkout 5682295124170ebd979b6a3e0add7e86af3693c6
cp reference/schwung-sophie/LICENSE reference/schwung-sophie/src/module.json \
   reference/schwung-sophie/src/dsp/sophie.c reference/schwung-sophie/src/dsp/plugin_api_v1.h \
   engines/third_party/schwung-modules/sophie/
```
