/* Native scope raster probe. MIT licence. Include the app so this exercises
 * its private draw_scope; the test link discards unrelated engine paths. */
#include <stdlib.h>
#include "../src/fm1_app.c"

static fm1_app_t app;

int main(int argc, char **argv) {
  if (argc != 4) return 2;
  int kind = atoi(argv[1]), top = atoi(argv[2]), pos = atoi(argv[3]);
  if (kind < 0 || kind > 4 || top < 0 || top >= SCOPE_BOTTOM - 2 ||
      pos < 0 || pos >= FM1_APP_SCOPE) return 2;
  app.scope_pos = pos;
  for (int i = 0; i < FM1_APP_SCOPE; ++i) {
    float v = 0.0f;
    if (kind == 1) v = 0.7f * sinf((float)i * 0.08f);
    if (kind == 2) v = i % 32 < 16 ? -0.8f : 0.8f;
    if (kind == 3) v = i % 2 ? 4.0f : -4.0f;
    if (kind == 4) v = 0.001f * sinf((float)i * 0.08f);
    app.scope[(pos + i) % FM1_APP_SCOPE] = v;
  }
  fm1_tft_begin(&app.tft, C_TEXT);
  draw_scope(&app, top);
  printf("P6\n%d %d\n255\n", FM1_TFT_W, FM1_TFT_H);
  for (int i = 0; i < FM1_TFT_W * FM1_TFT_H; ++i) {
    uint16_t p = app.tft.px[i];
    unsigned char rgb[3] = {
      (unsigned char)((((p >> 11) & 31) * 255 + 15) / 31),
      (unsigned char)((((p >> 5) & 63) * 255 + 31) / 63),
      (unsigned char)(((p & 31) * 255 + 15) / 31)
    };
    if (fwrite(rgb, sizeof rgb, 1, stdout) != 1) return 3;
  }
  return 0;
}
