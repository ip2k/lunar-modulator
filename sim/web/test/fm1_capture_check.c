/* Capture's actual app/panel feedback, including retained history. MIT. */
#include "fm1_app.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static fm1_app_t app;
static void render(void) { fm1_app_render(&app, FM1_APP_MAX_FRAMES); }
static void line(const char *text) {
  assert(fm1_app_seq_line(&app, text, strlen(text)) == strlen(text));
  render();
}
static void edge(int button, int down) { fm1_app_button(&app, button, down); render(); }
static void capture(void) {
  edge(FM1_BTN_SEL, 1); edge(FM1_BTN_REC, 1);
  edge(FM1_BTN_REC, 0); edge(FM1_BTN_SEL, 0);
}
static void note(int release) {
  fm1_app_seq_note_in(&app, 0, 67, 100); render();
  if (release) { fm1_app_seq_note_in(&app, 0, 67, 0); render(); }
}
static void screenshot(const char *path) {
  int boxes[8];
  fm1_app_draw_checked(&app);
  assert(fm1_tft_check_layout(&app.tft, FM1_APP_LAYOUT_GAP, boxes, 4) == 0);
  assert(!app.tft.truncated && !app.tft.overflow);
  if (!path) return;
  FILE *f = fopen(path, "wb"); assert(f);
  fprintf(f, "P6\n240 240\n255\n");
  for (unsigned i = 0; i < 240u * 240u; ++i) {
    const unsigned p = app.tft.px[i];
    const unsigned char rgb[] = {(unsigned char)((p >> 11) * 255u / 31u),
                                (unsigned char)(((p >> 5) & 63u) * 255u / 63u),
                                (unsigned char)((p & 31u) * 255u / 31u)};
    assert(fwrite(rgb, 1, 3, f) == 3);
  }
  assert(fclose(f) == 0);
}
int main(int argc, char **argv) {
  fm1_seq_info_t info;
  fm1_seq_stats_t stats;
  fm1_seq_clip_info_t clip;
  fm1_app_init(&app, 48000);
  assert(app.seq && fm1_app_select(&app, 0, fm1_app_find("test-sine")) == 0);
  render();
  capture();
  assert(app.popup_lines == 1 && strcmp(app.popup[0], "Nothing to capture") == 0);
  line("loop 0 240 16;play"); note(1);
  fm1_seq_get_info(app.seq, &info);
  const uint32_t gen = info.capture_gen;
  assert(info.capture_pending == 1);
  capture();
  fm1_seq_get_info(app.seq, &info); fm1_seq_get_stats(app.seq, &stats);
  assert(info.capture_pending == 1 && app.ui.capture_pending == 1 && info.capture_gen == gen);
  assert(stats.refused == 1);
  assert(app.popup_lines == 3 && app.popup_tone == FM1_APP_TONE_REFUSE);
  assert(strcmp(app.popup[0], "Not captured") == 0 && strcmp(app.popup[1], "Clip limit reached") == 0 &&
         strcmp(app.popup[2], "Take kept") == 0);
  assert(fm1_seq_get_clip(app.seq, 0, 0, &clip));
  assert(clip.length_steps == 16 && clip.loop_start == 240 && clip.notes == 0);
  screenshot(argc > 1 ? argv[1] : NULL);
  /* An old refusal is not a new failure; empty and held-note takes keep
   * their existing feedback. The saved counter is sampled per Capture. */
  line("capclr"); capture();
  assert(app.popup_lines == 1 && strcmp(app.popup[0], "Nothing to capture") == 0);
  line("loop 0 0 16"); note(0); capture();
  fm1_seq_get_info(app.seq, &info); fm1_seq_get_stats(app.seq, &stats);
  assert(info.capture_pending == 0 && info.capture_gen == gen + 1u && stats.refused == 1);
  assert(app.popup_lines == 1 && strcmp(app.popup[0], "Captured") == 0);
  fm1_app_seq_note_in(&app, 0, 67, 0); render();
  printf("PASS app Capture: empty, refused/history, valid held note; ui=%zu app=%zu\n",
         sizeof(fm1_seq_ui_t), sizeof(fm1_app_t));
  return 0;
}
