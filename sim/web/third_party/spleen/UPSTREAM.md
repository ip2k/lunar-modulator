# Spleen (Frederic Cambus) — the screen's MID and SMALL faces

Spleen is a monospaced bitmap font by Frederic Cambus,
[fcambus/spleen](https://github.com/fcambus/spleen), under the BSD 2-Clause
licence (`LICENSE` in this directory is upstream's, unmodified). The rest of
Lunar Modulator is MIT; BSD 2-Clause code and data combine with it, with
JieLi's Apache-2.0 SDK and with the closed SDK libraries, and carry none of
the GPL's limits on sharing a firmware image (CLAUDE.md, "Project status and
licences").

| Upstream file | Tag | Commit | Git blob | Here |
| --- | --- | --- | --- | --- |
| `spleen-8x16.bdf` | `2.2.0` (2026-02-01) | `0493c34e22791824767c618fed42c434b477662c` | `ebd9ed0562b9132a15862454bc82ffcdc05da7a2` | `spleen-8x16.bdf` |
| `spleen-6x12.bdf` | `2.2.0` | the same | `26dc8b5adf89db6d23ded1403c49d723435e0f2c` | `spleen-6x12.bdf` |
| `LICENSE` | `2.2.0` | the same | `6928cd0fc323641bac9f0abc1268ed063d782edb` | `LICENSE` |

All three files are byte for byte upstream's; `tests/test_sim_fonts.py`
checks the blob hashes. The tag is a lightweight one on that commit.

## What is taken

- **Printable ASCII, 0x20–0x7E, from both files: 95 glyphs each.** No string
  the screens draw has any other character [verified: every string literal
  in `sim/web/src/` and `engines/`, 2026-10-06], so nothing beyond ASCII is
  taken. Spleen has much more (Latin-1, box drawing, arrows); a screen that
  needs one of them adds it to `sim/web/tools/gen_font.py` and the drawing
  code then has to read UTF-8, which it does not today.
- **`sim/web/tools/gen_font.py` derives the tables** `sim/web/src/fm1_font_mid.h`
  (8×16) and `sim/web/src/fm1_font_small.h` (6×12) from the BDF files: one
  byte a glyph row, each glyph placed in its cell by the BDF's bounding box.
  The 8×16 table leaves out the cell's rows 0 and 15, which none of the 95
  glyphs paints, so a run's logged box is the 14 rows its characters can
  reach. The 6×12 table keeps all 12 rows. The generated headers say "do not
  edit" and carry Spleen's copyright line; `gen_font.py --check` and
  `tests/test_sim_fonts.py` keep them, and the glyphs as drawn, equal to the
  BDF files.
- **Flash cost** (the FM-1 keeps fonts in flash with its other constant
  data; `gen_font.py --sizes`): 8×16, 1,330 bytes (95 × 14); 6×12, 1,140
  bytes (95 × 12); together 2,470 bytes, beside the hand-made 5×9's 855
  (95 × 9). The drawing code shared by the three faces is a few hundred bytes
  more [inferred].
- **Not taken:** the other sizes (5×8, 12×24, 16×32, 32×64), the PCF, OTF
  and console (`.psfu`, wsfont) builds, and the `dos`, `cp437` and `blocks`
  variants.

## The notice with binaries

BSD 2-Clause asks that "redistributions in binary form must reproduce the
above copyright notice, this list of conditions and the following
disclaimer in the documentation and/or other materials provided with the
distribution." So:

- **The simulator:** the page serves the same `LICENSE` as
  `www/fonts/spleen/LICENSE` and links it from its credits.
- **A firmware image** that contains these tables (any build whose screens
  use MID or SMALL) must ship with this `LICENSE` in its release notes, its
  package or the manual's credits (chapter 14 names Spleen and its licence).
  A package handed to anyone without it does not meet the licence.
- **The source tree** keeps `LICENSE` here, and the copyright line in each
  generated header.
