/* Capture's actual app/panel feedback, including retained history. MIT. */
#include "fm1_app.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static fm1_app_t app;
static const char *busy_screenshot;
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
static unsigned cap_applied;
static void applied(void *ctx, uint64_t frame, const fm1_seq_cmd_t *c) {
  (void)ctx; (void)frame;
  if (c->verb == FM1_SEQ_V_CAP) ++cap_applied;
}
static void setup(unsigned start, int take) {
  fm1_app_init(&app, 48000);
  assert(fm1_app_select(&app, 0, fm1_app_find("test-sine")) == 0);
  assert(fm1_app_seq_reset(&app, 8) == 0);
  render();
  line("alabel 0 0 level");
  line(start ? "loop 0 240 16;play" : "loop 0 0 16;play");
  if (take) note(1);
  app.on_cmd = applied; cap_applied = 0;
}
static void fill(void) {
  const char *op = "abase 0 0 100";
  unsigned accepted = 0;
  while (fm1_app_seq_line(&app, op, strlen(op)) == strlen(op)) {
    assert(++accepted < FM1_APP_SEQ_EVENTS);
  }
  assert(accepted == 71 && !app.seq_pending);
}
static void press_capture(void) {
  fm1_app_button(&app, FM1_BTN_SEL, 1); fm1_app_button(&app, FM1_BTN_REC, 1);
  fm1_app_button(&app, FM1_BTN_REC, 0); fm1_app_button(&app, FM1_BTN_SEL, 0);
}
static void delayed(void) {
  for (unsigned bad = 0; bad < 2; ++bad) {
    static char before[65536], after[65536];
    setup(bad, 1); fill();
    press_capture();
    assert(app.seq_pending && app.ui.cap_sent && cap_applied == 0);
    const uint64_t held = app.seq_held;
    press_capture();
    assert(app.seq_held == held && cap_applied == 0); /* already admitted, never duplicate */
    /* Unrelated accepted route input and rejected text both increment the
     * broad generation; neither may complete or replace this held CAP. */
    assert(fm1_app_seq_route(&app, 1, FM1_SEQ_ROUTE_ENGINE, 0));
    assert(!fm1_app_seq_route(&app, 1, FM1_SEQ_ROUTE_MIDI, 0));
    assert(fm1_app_seq_line(&app, "metro 1", 7) == 0);
    const size_t size = fm1_seq_export_movy1(app.seq, before, sizeof before);
    assert(size && size < sizeof before); /* after legitimate unrelated edits */
    render();
    assert(app.seq_pending && app.ui.cap_sent && cap_applied == 0);
    assert(strcmp(app.popup[0], "Nothing to capture") != 0);
    /* Inputs can flush too: exercise that boundary as well as block start. */
    if (!bad) assert(fm1_app_seq_line(&app, "metro 1", 7) == 7);
    render();
    fm1_seq_info_t info; fm1_seq_stats_t stats;
    fm1_seq_get_info(app.seq, &info); fm1_seq_get_stats(app.seq, &stats);
    assert(!app.seq_pending && !app.ui.cap_sent && cap_applied == 1);
    assert(info.capture_pending == bad && stats.refused == bad);
    assert(strcmp(app.popup[0], bad ? "Not captured" : "Captured") == 0);
    if (bad) {
      assert(fm1_seq_export_movy1(app.seq, after, sizeof after) == size);
      assert(memcmp(before, after, size) == 0); /* refused Capture changes no saved content */
    }
    for (unsigned i = 0; i < 4; ++i) render();
    assert(cap_applied == 1);
  }
}
static void busy_and_cancel(void) {
  /* A different typed CAP occupies the slot. The panel's BUSY attempt is
   * not admitted and must not inherit that older command's refusal. */
  setup(240, 1); fill();
  fm1_seq_cmd_t cmd; const int64_t track = 0;
  fm1_seq_cmd_make(&cmd, FM1_SEQ_V_CAP, 1, &track);
  assert(fm1_app_seq_cmd(&app, &cmd) == FM1_APP_SEQ_HELD);
  const uint64_t busy = app.seq_busy;
  press_capture();
  assert(app.seq_busy == busy + 1 && !app.ui.cap_sent && !app.seq_pend_ui_capture);
  assert(strcmp(app.popup[0], "Capture busy") == 0);
  screenshot(busy_screenshot);
  render(); render();
  fm1_seq_info_t info; fm1_seq_stats_t stats;
  fm1_seq_get_info(app.seq, &info); fm1_seq_get_stats(app.seq, &stats);
  assert(cap_applied == 1 && info.capture_pending == 1 && stats.refused == 1);
  assert(strcmp(app.popup[0], "Capture busy") == 0); /* no fabricated panel completion */
  for (unsigned i = 0; i < 4; ++i) render();
  assert(cap_applied == 1); /* BUSY never retries itself */
  press_capture(); render();
  assert(cap_applied == 2 && strcmp(app.popup[0], "Not captured") == 0);

  static char saved[65536];
  for (unsigned importing = 0; importing < 3; ++importing) {
    setup(240, 1);
    const size_t bytes = fm1_seq_export_movy1(app.seq, saved, sizeof saved);
    assert(bytes && bytes < sizeof saved);
    fill(); press_capture();
    assert(app.seq_pending && app.ui.cap_sent && app.seq_pend_ui_capture);
    if (importing == 2) {
      /* An invalid import preserves the admitted command and its feedback. */
      assert(!fm1_app_seq_import(&app, "invalid", 7));
      assert(app.seq_pending && app.ui.cap_sent && app.seq_pend_ui_capture);
      render(); render();
      assert(cap_applied == 1 && strcmp(app.popup[0], "Not captured") == 0);
    } else {
      if (importing) assert(fm1_app_seq_import(&app, saved, bytes));
      else assert(fm1_app_seq_reset(&app, 8) == 0);
      assert(!app.seq_pending && !app.ui.cap_sent && !app.seq_pend_ui_capture);
      render(); render();
      assert(cap_applied == 0);
      assert(strcmp(app.popup[0], "Captured") != 0 && strcmp(app.popup[0], "Not captured") != 0);
      assert(fm1_app_seq_cmd(&app, &cmd) == FM1_APP_SEQ_APPLIED);
      render();
      assert(cap_applied == 1 && !app.ui.cap_sent); /* no stale association */
      assert(strcmp(app.popup[0], "Captured") != 0 && strcmp(app.popup[0], "Not captured") != 0);
    }
  }
  setup(0, 0); fill(); press_capture();
  assert(!app.seq_pending && !app.ui.cap_sent && cap_applied == 0);
  assert(strcmp(app.popup[0], "Nothing to capture") == 0);
  render(); render(); assert(cap_applied == 0);
}
int main(int argc, char **argv) {
  busy_screenshot = argc > 2 ? argv[2] : NULL;
  delayed();
  busy_and_cancel();
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
  printf("PASS app Capture: delayed, BUSY, cancellation, empty, refused/history, valid held note; ui=%zu app=%zu\n",
         sizeof(fm1_seq_ui_t), sizeof(fm1_app_t));
  return 0;
}
