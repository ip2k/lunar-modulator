"""Caller-owned pixels must draw the same frame and leave adjacent memory intact."""
import hashlib
import os
from pathlib import Path
import shutil
import shlex
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
#include "fm1_tft.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static fm1_tft_t screen;
#if FM1_TFT_EXTERNAL_PIXELS
static struct {
  uint16_t before[16];
  uint16_t pixels[FM1_TFT_W * FM1_TFT_H];
  uint16_t after[16];
} storage;
#endif

int main(void) {
#if FM1_TFT_EXTERNAL_PIXELS
  memset(&storage, 0x5a, sizeof storage);
  assert(!fm1_tft_ready(&screen));
  fm1_tft_begin(&screen, 0xffff);
  fm1_tft_paint(&screen, -10, -10, 400, 400, 0);
  assert(fm1_tft_bind_pixels(&screen, storage.pixels, FM1_TFT_W * FM1_TFT_H - 1) == -1);
  assert(!fm1_tft_ready(&screen));
  assert(fm1_tft_bind_pixels(&screen, storage.pixels, FM1_TFT_W * FM1_TFT_H) == 0);
#endif
  assert(fm1_tft_ready(&screen));
  for (int frame = 0; frame < 3; ++frame) {
    screen.record = 1;
    fm1_tft_begin(&screen, (uint16_t)(0x0123 + frame));
    fm1_tft_graphic(&screen, 10, 10, 23, 19);
    fm1_tft_paint(&screen, -8, -3, 18, 23, 0xabcd);
    fm1_tft_paint(&screen, 229, 231, 80, 60, 0x1234);
    fm1_tft_paint(&screen, 400, 400, 5, 5, 0xffff);
    fm1_tft_paint(&screen, 20, 20, -3, -7, 0xffff);
    fm1_tft_frame(&screen, 3, 3, 234, 234, 0xf800);
    fm1_tft_text(&screen, 12, 12, "FM6?", 4, 2, 0x07e0);
    for (int face = 0; face < FM1_TFT_FONTS; ++face)
      fm1_tft_font_text(&screen, 20, 45 + face * 25, "Alpha 0123 *&?", 10,
                        (fm1_tft_font_t)face, 0xffff);
    fm1_tft_span_t spans[] = {{"red", 0xf800}, {" green", 0x07e0}, {" blue", 0x001f}};
    fm1_tft_span_text(&screen, -4, 140, spans, 3, 10, FM1_TFT_SMALL);
    fm1_tft_fill(&screen, 0, 8, 50, 40, 0x4321);
    fwrite(screen.px, sizeof(uint16_t), FM1_TFT_W * FM1_TFT_H, stdout);
    fwrite(&screen.n_boxes, sizeof screen.n_boxes, 1, stdout);
    fwrite(&screen.overflow, sizeof screen.overflow, 1, stdout);
    fwrite(&screen.truncated, sizeof screen.truncated, 1, stdout);
    fwrite(screen.boxes, sizeof screen.boxes, 1, stdout);
  }
#if FM1_TFT_EXTERNAL_PIXELS
  for (int i = 0; i < 16; ++i)
    assert(storage.before[i] == 0x5a5a && storage.after[i] == 0x5a5a);
  assert(fm1_tft_bind_pixels(&screen, NULL, 1) == -1);
  assert(!fm1_tft_ready(&screen));
  assert(fm1_tft_bind_pixels(&screen, NULL, 0) == 0);
#endif
  fprintf(stderr, "%zu\n", sizeof screen);
  return 0;
}
'''


def test_attached_pixels_match_embedded_with_clipping_fonts_and_guards(tmp_path):
    cc = os.environ.get("FM1_SIM_CC", "cc")
    if not shutil.which(cc):
        pytest.skip("C compiler unavailable")
    source = tmp_path / "pixels.c"
    source.write_text(PROBE)
    results = []
    for external in (0, 1):
        target = tmp_path / f"pixels-{external}"
        subprocess.run([cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                        *shlex.split(os.environ.get("FM1_SIM_EXTRA", "")),
                        f"-DFM1_TFT_EXTERNAL_PIXELS={external}",
                        "-I", str(ROOT / "sim/web/src"), str(source),
                        str(ROOT / "sim/web/src/fm1_tft.c"), "-o", str(target)], check=True)
        results.append(subprocess.run([str(target)], capture_output=True, check=True))
    assert results[0].stdout == results[1].stdout
    # The pointer replaces the whole framebuffer; metadata stays present.
    assert int(results[0].stderr) - int(results[1].stderr) >= 115192


APP_PROBE = r'''
#include "fm1_app.h"
#include <assert.h>
#include <stdio.h>
static fm1_app_t app;
#if FM1_TFT_EXTERNAL_PIXELS
static uint16_t pixels[FM1_TFT_W * FM1_TFT_H];
#endif
int main(void) {
  for (int init = 0; init < 2; ++init) {
#if FM1_TFT_EXTERNAL_PIXELS
    if (!init) assert(fm1_tft_bind_pixels(&app.tft, pixels, FM1_TFT_W * FM1_TFT_H) == 0);
#endif
    fm1_app_init(&app, 44118.0f);
#if FM1_TFT_EXTERNAL_PIXELS
    assert(app.tft.px == pixels);
    assert(fm1_tft_bind_pixels(&app.tft, NULL, 0) == 0);
    app.peak = 0.5f; app.meter = 0.25f; app.last_draw = 123;
    assert(!fm1_app_draw(&app, 0));
    fm1_app_draw_checked(&app);
    assert(app.dirty && app.peak == 0.5f && app.meter == 0.25f && app.last_draw == 123);
    assert(fm1_tft_bind_pixels(&app.tft, pixels, FM1_TFT_W * FM1_TFT_H) == 0);
#else
    app.peak = 0.5f; app.meter = 0.25f; app.last_draw = 123;
#endif
    assert(fm1_app_select(&app, fm1_app_sound_unit(0), fm1_app_find("dx7")) == 0);
    fm1_app_note_on(&app, 60, 100);
    for (int frame = 0; frame < 8; ++frame) {
      const float *audio = fm1_app_render(&app, 64);
      fwrite(audio, sizeof(float), 128, stdout);
      fm1_app_set_param(&app, fm1_app_sound_unit(0), 0, (float)(frame + 1));
      fm1_app_master(&app, 0.7f, 1); /* Popup/banner: includes pixel readback. */
      fm1_app_draw_checked(&app);
      fwrite(app.tft.px, sizeof(uint16_t), FM1_TFT_W * FM1_TFT_H, stdout);
      fwrite(&app.tft.n_boxes, sizeof app.tft.n_boxes, 1, stdout);
      fwrite(app.tft.boxes, sizeof app.tft.boxes, 1, stdout);
    }
    fm1_app_all_notes_off(&app);
  }
  return 0;
}
'''


def test_app_pixels_audio_and_reinitialization_match(tmp_path):
    cc = os.environ.get("FM1_SIM_CC", "cc")
    cxx = os.environ.get("FM1_SIM_CXX", "c++")
    if not all(shutil.which(tool) for tool in (cc, cxx, "make")):
        pytest.skip("native toolchain unavailable")
    source = tmp_path / "app-pixels.c"
    source.write_text(APP_PROBE)
    makefile = tmp_path / "pixels.mk"
    makefile.write_text(
        f"$(BUILD)/app-pixels.o: {source}\n"
        "\t@mkdir -p $(dir $@)\n"
        "\t$(CC) $(SIM_CFLAGS) -c $< -o $@\n"
        "$(BUILD)/app-pixels: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) $(BUILD)/app-pixels.o\n"
        "\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm\n")
    results = []
    extra = os.environ.get("FM1_SIM_EXTRA", "")
    tag = hashlib.sha256((cc + cxx + extra).encode()).hexdigest()[:12]
    for external in (0, 1):
        build = ROOT / "sim/web/build" / f"pixels-storage-{tag}-{external}"
        target = build / "app-pixels"
        subprocess.run([
            "make", "-s", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
            str(ROOT / "sim/web/mk/sim.mk"), "-f", str(makefile),
            f"SIM={ROOT / 'sim/web'}", f"BUILD={build}", "FM1_GPL_MODS=0",
            "FM1_MODULES=dx7,filter,echo,comp,arp,lfo,env,chance", f"CC={cc}", f"CXX={cxx}",
            f"EXTRA={extra} -DFM1_TFT_EXTERNAL_PIXELS={external}", "-j4", str(target),
        ], check=True, stdout=subprocess.DEVNULL)
        results.append(subprocess.run([str(target)], capture_output=True, check=True))
    assert results[0].stdout == results[1].stdout
