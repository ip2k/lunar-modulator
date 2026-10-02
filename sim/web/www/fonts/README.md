# Fonts

| File | Font | Licence | From |
| --- | --- | --- | --- |
| `audiowide/Audiowide-Regular.ttf` | Audiowide, by Brian J. Bonislawsky (Astigmatic) | SIL Open Font License 1.1, with the Reserved Font Name "Audiowide" (`audiowide/OFL.txt`) | [google/fonts](https://github.com/google/fonts/tree/main/ofl/audiowide), `ofl/audiowide/` |

The files are byte for byte the ones in google/fonts (git blob
`8b50bedc…` for the font, `19bb4adf…` for `OFL.txt`, checked on 2026-10-01;
`tests/test_sim_web.py` keeps checking). Do not subset, convert or
otherwise change them: under the OFL a changed font is a Modified Version,
and the Reserved Font Name clause then forbids calling it "Audiowide". A
smaller or converted file would need a new name and its own `OFL.txt`.

Small text asks for Exo 2 (Natanael Gama, SIL OFL 1.1) and falls back to
the system's sans-serif where it is not installed. Its file is not in the
repository yet: adding it means `Exo2[wght].ttf` (303,940 bytes, git blob
`9cb20188a07687580312d2099e6c79ca8ecb7b58`) and its `OFL.txt` (4,386
bytes, blob `5bec9840d2e0df42d80d6fac55279d1d5e5b9199`) from google/fonts'
`ofl/exo2/` (listed on 2026-10-01), unmodified, in `exo2/`, an
`@font-face` in `style.css`, and those hashes in the test.
