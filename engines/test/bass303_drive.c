/* bass303_drive.c -- drives fm1-x0x's 303 bass (bass303.c) through upstream's
 * own API only (bass303_init, bass303_set with integer pots, note_on with the
 * slide flag, note_off, render in X0X's 256-frame calls at 44.1 kHz), and
 * writes the samples as raw float32 to stdout. tests/test_engine_acid_bass.py
 * builds it twice, against fm1-x0x's own file (reference/fm1-x0x) and against
 * the vendored, patched one (third_party/fm1-x0x), and compares the bytes: the
 * local changes must leave upstream's samples as they are.
 *
 *   cc -std=c99 -O2 -ffp-contract=off -I DSP_DIR bass303_drive.c DSP_DIR/bass303.c -o drive
 *   ./drive > out.f32
 *
 * MIT licence (this file); it links GPL-3.0 code.
 */
#include <stdio.h>

#include "bass303.h"

/* A 16-step line: key (or -1, a rest), accent, slide. */
static const int kLine[16][3] = {
  {45, 1, 0}, {45, 0, 1}, {57, 0, 0}, {-1, 0, 0}, {48, 0, 1}, {52, 1, 1}, {55, 0, 0}, {45, 0, 0},
  {-1, 0, 0}, {57, 1, 0}, {45, 0, 1}, {43, 0, 1}, {45, 1, 0}, {-1, 0, 0}, {60, 0, 1}, {57, 0, 0},
};

/* Settings as pots: {parameter, value} pairs, -1 ends. */
static const int kSettings[][13] = {
  {-1},
  {BASS303_CUTOFF, 20, BASS303_RESO, 120, BASS303_ENVMOD, 110, BASS303_DECAY, 30, -1},
  {BASS303_WAVE, 1, BASS303_SLIDE, 90, BASS303_ACCDEC, 70, BASS303_TUNE, 80, -1},
  {BASS303_DRIVE, 80, BASS303_DRVTYPE, 1, BASS303_RESO, 100, -1},
  {BASS303_DRIVE, 100, BASS303_DRVTYPE, 2, BASS303_ENVMOD, 127, BASS303_VOLUME, 127, -1},
};

static bass303_t g_b;
static float g_buf[BASS303_MAX_BLOCK];

static void run(int frames) {
  while (frames > 0) {
    int n = frames < 256 ? frames : 256;
    bass303_render(&g_b, g_buf, n);
    fwrite(g_buf, sizeof(float), (size_t)n, stdout);
    frames -= n;
  }
}

int main(void) {
  const int step = 5168;                  /* a 16th at 128 BPM, 44.1 kHz, rounded */
  unsigned s;
  for (s = 0; s < sizeof(kSettings) / sizeof(kSettings[0]); ++s) {
    int i, held = 0;
    bass303_init(&g_b);
    for (i = 0; kSettings[s][i] >= 0; i += 2) bass303_set(&g_b, kSettings[s][i], kSettings[s][i + 1]);
    for (i = 0; i < 32; ++i) {
      const int *st = kLine[i % 16];
      if (st[0] < 0) {
        if (held) bass303_note_off(&g_b);
        held = 0;
        run(step);
        continue;
      }
      bass303_note_on(&g_b, st[0], st[1], held);
      held = 1;
      if (st[2]) {
        run(step);
      } else {
        run(step / 2);
        bass303_note_off(&g_b);
        held = 0;
        run(step - step / 2);
      }
    }
    if (held) bass303_note_off(&g_b);
    run(44100);                           /* the tail, past the idle hold-off */
  }
  return 0;
}
