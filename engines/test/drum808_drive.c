/* drum808_drive.c -- drives fm1-x0x's 808 kit (drum808.c) through upstream's
 * own API only (drum808_init, drum808_set with integer pots, the track
 * switches, drum808_trigger, drum808_render in X0X's 256-frame calls at
 * 44.1 kHz), and writes the dry bus and both send buses as raw float32 to
 * stdout. tests/test_engine_crater_kit.py builds it twice, against fm1-x0x's
 * own file (reference/fm1-x0x) and against the vendored, patched one
 * (third_party/fm1-x0x), and compares the bytes: the local changes must leave
 * upstream's samples as they are.
 *
 *   cc -std=c99 -O2 -ffp-contract=off -I DSP_DIR drum808_drive.c DSP_DIR/drum808.c -o drive
 *   ./drive > out.f32
 *
 * MIT licence (this file); it links GPL-3.0 code.
 */
#include <stdio.h>

#include "drum808.h"

/* A bar of 16ths per track: '.' rest, 'x' a normal hit, 'A' an accent. */
static const char *const kBar[D8_NUM] = {
  "A..x..x...A..x..", /* BD */ "....A.......x..x", /* SD */ "x.....x.....A...", /* LT */
  "..x.....x.......", /* MT */ "....x.....x...A.", /* HT */ ".x.....x....x...", /* RS */
  "........A.....x.", /* CP */ "......x.....x...", /* CB */ "A...............", /* CY */
  "..x.......x.....", /* OH */ "x.x.x.x.x.x.x.x.", /* CH */
};

/* Settings: {track, parameter index, value} triples, -1 ends. A track's
 * "Sound" switch is a parameter too (index 3 on LT, MT, HT and RS, 4 on CP). */
static const int kSettings[][64] = {
  {-1},
  /* the switches over: congas, claves, maracas; the mutual choke */
  {D8_LT, 3, 1, D8_MT, 3, 1, D8_HT, 3, 1, D8_RS, 3, 1, D8_CP, 4, 1, D8_KIT, 2, 2, -1},
  /* pots at their ends, drives through every distortion */
  {D8_BD, 1, 127, D8_BD, 2, 20, D8_BD, 3, 100, D8_BD, 4, 127, D8_BD, 5, 60, D8_BD, 6, 3,
   D8_SD, 1, 0, D8_SD, 2, 127, D8_SD, 4, 10, D8_SD, 5, 90, D8_SD, 6, 5,
   D8_CH, 2, 127, D8_CH, 3, 50, D8_CH, 4, 6, D8_KIT, 1, 30, -1},
  {D8_CY, 1, 127, D8_CY, 2, 0, D8_OH, 1, 10, D8_CB, 1, 100, D8_CB, 3, 127, D8_CB, 4, 1,
   D8_CP, 2, 127, D8_CP, 3, 0, D8_CP, 5, 40, D8_CP, 6, 4, D8_RS, 1, 127, D8_RS, 2, 127, -1},
};

static drum808_t g_d;
static float g_dry[256], g_rev[256], g_dly[256];

static void run(int frames) {
  while (frames > 0) {
    int n = frames < 256 ? frames : 256, i;
    for (i = 0; i < n; ++i) g_dry[i] = g_rev[i] = g_dly[i] = 0.0f;
    drum808_render(&g_d, g_dry, g_rev, g_dly, n);
    fwrite(g_dry, sizeof(float), (size_t)n, stdout);
    fwrite(g_rev, sizeof(float), (size_t)n, stdout);
    fwrite(g_dly, sizeof(float), (size_t)n, stdout);
    frames -= n;
  }
}

int main(void) {
  const int step = 5512;                  /* a 16th at 120 BPM, 44.1 kHz, rounded */
  unsigned s;
  for (s = 0; s < sizeof(kSettings) / sizeof(kSettings[0]); ++s) {
    int i, b, t;
    drum808_init(&g_d);
    for (i = 0; kSettings[s][i] >= 0; i += 3) drum808_set(&g_d, kSettings[s][i], kSettings[s][i + 1], kSettings[s][i + 2]);
    /* also the sends, on the snare and the open hat */
    drum808_set(&g_d, D8_SD, 7, 64);
    drum808_set(&g_d, D8_OH, 6, 100);
    for (b = 0; b < 32; ++b) {
      for (t = 0; t < D8_NUM; ++t) {
        const char c = kBar[t][b % 16];
        if (c == 'x') drum808_trigger(&g_d, t, D8_VEL_NORMAL);
        else if (c == 'A') drum808_trigger(&g_d, t, 1.0f);
      }
      run(step);
    }
    run(2 * 44100);                       /* the tails */
  }
  return 0;
}
