# Vendored Schwung module: PSX Verb

| | |
| --- | --- |
| Upstream | https://github.com/charlesvestal/schwung-psxverb at `b0b44dbebc6badf14b6cf0391fdf3c2f8dc6fc71` (2026-03-16, "chore: dual-license plugin_api_v1.h under MIT") |
| Author | Charles Vestal |
| Licence | MIT (`LICENSE`, copied whole; checked 2026-09-30). The module's copy of `plugin_api_v1.h` also carries an MIT header |
| What it is | A PlayStation 1 SPU reverb emulation: 2:1 half-band decimation, the SPU's same/cross-side reflections, four combs and two all-passes in a saturating 16-bit work area, and six register presets (Room, Studio S/M/L, Hall, Space Echo) |
| What is vendored | The DSP (`src/dsp/psxverb.c`), the module's own copies of the Schwung headers it includes, and `src/module.json` (metadata and parameter list). Not vendored: docs, build scripts, CI |
| Local changes | `psxverb.c`: corrected the 39-tap 2x interpolator's polyphase coefficient split and history indexing. Verified against the original MIT-licensed `CVCHothouse/PSXVerb/PSXVerb/Halfband39.h` at `b94500f72be70140f3d094d69d0c43d04ce72ecc`; upstream at the Schwung pin has the same indexing defect. Other listed files remain byte-identical to the pinned Schwung source. |
| Built as | engine `sw-psxverb` (`engines/src/sw_psxverb.cc`) through the Schwung v2 shim; see `engines/schwung.md` |

| File | Upstream path | SHA-256 |
| --- | --- | --- |
| `psxverb.c` | `src/dsp/psxverb.c` | `789bc7ed9f42fb0164651e986be585041b6b97305362aa9c7dcfc879b177f05b` |
| `plugin_api_v1.h` | `src/dsp/plugin_api_v1.h` | `0936fb1784d001f7ad1cac075cbe760d49d73727a52259b0b2a0d7850e02ea32` |
| `audio_fx_api_v1.h` | `src/dsp/audio_fx_api_v1.h` | `28a54a5c79ec768f73e3730870209970518218b588872b551794e719f5072be9` |
| `module.json` | `src/module.json` | `f63213735ea9ab408151421088a3c7c3e5b31181937a6061770f1c67820ead41` |
| `LICENSE` | `LICENSE` | `b1c3367e745b53e52b90ba17e4534fa19d86fae3da7cd8addb51398d5fec83cc` |

Notes for the next update:

- **Provenance of the presets.** The six presets are the SPU reverb register
  values published in Martin Korth's psx-spx documentation; the source says
  it is a port of the author's own CVCHothouse `PSXVerb` (Daisy Seed). The
  README names Mednafen (GPL) as a reference for the algorithm; no Mednafen
  code was found in `psxverb.c` [inferred from reading it, not a clean-room
  audit]. Register values are factual data, but that is a judgement, not
  legal advice; revisit before shipping.
- The module defines its own `audio_fx_api_v2_t` without `on_midi`; the shim
  never reads that field.
- `create_instance` makes two `calloc`s: the instance (about 1.3 KB) and a
  fixed 65,536-sample int16 work area (128 KB) whatever the preset needs.
- `process_block` works on frame pairs and silently skips a trailing odd
  frame; the shim always calls it with an even block.
- The code assumes a 48 kHz device (`SAMPLE_RATE 48000`) and scales every
  delay by 48000/44100, so on Schwung's 44.1 kHz and on the FM-1's 44,118 Hz
  the reverb is about 9 % longer than the PlayStation's. Kept as upstream.

Re-vendoring:

```bash
git clone https://github.com/charlesvestal/schwung-psxverb reference/schwung-psxverb
git -C reference/schwung-psxverb checkout b0b44dbebc6badf14b6cf0391fdf3c2f8dc6fc71
cp reference/schwung-psxverb/LICENSE reference/schwung-psxverb/src/module.json \
   reference/schwung-psxverb/src/dsp/psxverb.c reference/schwung-psxverb/src/dsp/plugin_api_v1.h \
   reference/schwung-psxverb/src/dsp/audio_fx_api_v1.h engines/third_party/schwung-modules/psxverb/
```

After re-vendoring, reapply the focused `psxverb.c` interpolation correction
and rerun `tests/test_engines_schwung.py::test_psxverb_interpolator_matches_pinned_zero_stuffed_fir`;
do not treat the upstream file as byte-identical to the corrected local copy.
