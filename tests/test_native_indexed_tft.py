"""Exact raster parity and failure bounds for the optional indexed TFT."""
import shutil
import subprocess
import sys

import pytest

from tests.engine_helpers import ROOT

SOURCE = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "fm1_tft.h"
static fm1_tft_t t;
static unsigned state;
static unsigned rnd(void) { state = state * 1664525u + 1013904223u; return state; }
int main(int argc, char **argv) {
  assert(argc == 2); state = (unsigned)atoi(argv[1]) + 1;
  t.record = 1;
  fm1_tft_begin(&t, 0);
  /* Exercise all 256 exact colours, including index 255. */
  for (unsigned i = 1; i < 256; ++i) fm1_tft_paint(&t, i % 240, i / 240, 1, 1, i);
  for (unsigned i = 0; i < 256; ++i)
    assert(fm1_tft_pixel(&t, (i / 240) * 240 + i % 240) == i);
  assert(fm1_tft_pixels_valid(&t));
#if FM1_TFT_INDEXED
  assert(t.palette_count == 256);
  /* Offscreen colours consume no capacity; failure must not wrap index 256. */
  fm1_tft_paint(&t, 250, 0, 2, 2, 65535);
  assert(fm1_tft_pixels_valid(&t));
  fm1_tft_paint(&t, 0, 0, 1, 1, 65535);
  assert(!fm1_tft_pixels_valid(&t));
  assert(fm1_tft_pixel(&t, 0) == 0);
  assert(t.palette_count == 256);
#endif
  for (unsigned frame = 0; frame < 4; ++frame) {
    fm1_tft_begin(&t, frame ? 65535 : 0);
    assert(fm1_tft_pixels_valid(&t));
    for (unsigned i = 0; i < 1000; ++i) {
      int x = (int)(rnd() % 300) - 30, y = (int)(rnd() % 300) - 30;
      int w = (int)(rnd() % 50), h = (int)(rnd() % 50);
      uint16_t c = (uint16_t)((rnd() % 128) * 257u);
      if (i % 3 == 0) fm1_tft_fill(&t, x, y, w, h, c);
      else if (i % 3 == 1) fm1_tft_frame(&t, x, y, w, h, c);
      else fm1_tft_font_text(&t, x, y, "Lunar 0123?", 10,
                            (fm1_tft_font_t)(rnd() % 3), c);
    }
    assert(fm1_tft_pixels_valid(&t));
    for (unsigned i = 0; i < 240u * 240u; ++i) {
      uint16_t p = fm1_tft_pixel(&t, i);
      assert(putchar(p & 255) != EOF && putchar(p >> 8) != EOF);
    }
    /* Compare layout metadata too: palette storage cannot change text boxes. */
    assert(fwrite(&t.record, sizeof t.record, 1, stdout) == 1);
    assert(fwrite(&t.n_boxes, sizeof t.n_boxes, 1, stdout) == 1);
    assert(fwrite(&t.overflow, sizeof t.overflow, 1, stdout) == 1);
    assert(fwrite(&t.truncated, sizeof t.truncated, 1, stdout) == 1);
    assert(fwrite(t.boxes, sizeof t.boxes, 1, stdout) == 1);
  }
  fprintf(stderr, "%zu\n", sizeof t);
  return 0;
}
'''


@pytest.fixture(scope="session")
def raster_pair(tmp_path_factory):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("no C compiler")
    build = tmp_path_factory.mktemp("indexed-tft")
    source = build / "parity.c"
    source.write_text(SOURCE)
    binaries = []
    for indexed in (0, 1):
        binary = build / f"raster-{indexed}"
        subprocess.run([
            cc, "-std=c99", "-O1", "-g", "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            *(["-fno-pie", "-no-pie"] if sys.platform == "linux" else []),
            f"-DFM1_TFT_INDEXED={indexed}", f"-I{ROOT / 'sim/web/src'}",
            str(source), str(ROOT / "sim/web/src/fm1_tft.c"), "-o", str(binary),
        ], check=True, capture_output=True)
        binaries.append(binary)
    return binaries


@pytest.mark.parametrize("seed", range(16))
def test_indexed_raster_matches_rgb565(raster_pair, seed):
    reference, indexed = [subprocess.run([str(p), str(seed)], capture_output=True,
                                         check=True) for p in raster_pair]
    assert indexed.stdout == reference.stdout
    assert int(reference.stderr) - int(indexed.stderr) == 57084
