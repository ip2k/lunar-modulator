# Fonts

| File | Font | Licence | From |
| --- | --- | --- | --- |
| `audiowide/Audiowide-Regular.ttf` | Audiowide, by Brian J. Bonislawsky (Astigmatic) | SIL Open Font License 1.1, with the Reserved Font Name "Audiowide" (`audiowide/OFL.txt`) | [google/fonts](https://github.com/google/fonts/tree/main/ofl/audiowide), `ofl/audiowide/` |
| `exo2/Exo2[wght].ttf` | Exo 2, by Natanael Gama ("The Exo 2 Project Authors"), a variable font, weights 100–900 | SIL Open Font License 1.1, no Reserved Font Name (`exo2/OFL.txt`) | [google/fonts](https://github.com/google/fonts/tree/main/ofl/exo2), `ofl/exo2/` |
| `spleen/LICENSE` | Spleen 2.2.0, by Frederic Cambus: no font file here. Its 8×16 and 6×12 bitmaps are the screen's MID and SMALL faces (`sim/web/third_party/spleen/`, `src/fm1_font_mid.h`, `src/fm1_font_small.h`), compiled into `fm1.wasm` once a screen draws in them (the linker leaves them out until then [verified: 2026-10-06 build]) | BSD 2-Clause; the binary must carry this notice, so the page serves it and links it from its credits | [fcambus/spleen](https://github.com/fcambus/spleen), tag `2.2.0` |

The files are byte for byte the ones in google/fonts (git blob
`8b50bedc…` for the font, `19bb4adf…` for `OFL.txt`, checked on 2026-10-01;
`tests/test_sim_web.py` keeps checking). Do not subset, convert or
otherwise change them: under the OFL a changed font is a Modified Version,
and the Reserved Font Name clause then forbids calling it "Audiowide". A
smaller or converted file would need a new name and its own `OFL.txt`.

Small text is set in Exo 2.
- The files are `exo2/Exo2[wght].ttf` (303,940 bytes, git blob
  `9cb20188a07687580312d2099e6c79ca8ecb7b58`) and its `OFL.txt` (4,386 bytes,
  blob `5bec9840d2e0df42d80d6fac55279d1d5e5b9199`).
- Both were fetched from google/fonts' `ofl/exo2/` by those blob hashes on
  2026-10-01 and are unmodified. `tests/test_sim_web.py` checks them.
- The italic file is not included.
- The file name keeps upstream's brackets, so `style.css` refers to it as
  `Exo2%5Bwght%5D.ttf`.
- Exo 2's OFL names no Reserved Font Name. The rule here is the same anyway:
  do not subset or convert it.
