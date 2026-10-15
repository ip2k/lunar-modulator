/* SPDX-License-Identifier: MIT */
/* Exercise the app's real bounded MIDI transport queue under event pressure. */
#include "fm1_app.h"

#include <stdio.h>
#include <string.h>

static fm1_app_t app;

static int init_app(void) {
  fm1_app_init(&app, 44118.0f);
  return app.seq != NULL;
}

/* Leave one event less room than the documented largest command burst. */
static void apply_pressure(void) {
  const uint32_t need = fm1_seq_cmd_max_events(&app.seq_lim) +
                        fm1_seq_min_events(&app.seq_lim);
  app.seq_host.n = app.seq_host.cap - need + 1u;
}

static int flush_held(void) {
  app.seq_host.n = 0;
  (void)fm1_app_seq_line(&app, "", 0);
  (void)fm1_app_render(&app, 1);
  return !app.seq_pending && app.seq_midi_count == 0;
}

static int playing_is(int expected) {
  fm1_seq_info_t info;
  fm1_seq_get_info(app.seq, &info);
  return (info.playing != 0) == expected && app.ui.playing == info.playing;
}

static int saturated_stop_is_retained(void) {
  unsigned i;
  if (!init_app()) return 0;
  apply_pressure();
  for (i = 0; i < FM1_APP_SEQ_MIDI_PENDING; ++i)
    if (fm1_app_seq_midi_transport(&app, 0xFAu) != FM1_APP_SEQ_HELD) return 0;
  if (fm1_app_seq_midi_transport(&app, 0xFCu) != FM1_APP_SEQ_HELD ||
      app.seq_midi_count != FM1_APP_SEQ_MIDI_PENDING) return 0;
  if (app.seq_midi_pend[(app.seq_midi_head + FM1_APP_SEQ_MIDI_PENDING - 1u) %
                        FM1_APP_SEQ_MIDI_PENDING] != 0xFCu) return 0;
  return flush_held() && playing_is(0);
}

static int held_transport_order_is_preserved(void) {
  if (!init_app()) return 0;
  apply_pressure();
  if (fm1_app_seq_midi_transport(&app, 0xFAu) != FM1_APP_SEQ_HELD ||
      fm1_app_seq_midi_transport(&app, 0xFCu) != FM1_APP_SEQ_HELD ||
      fm1_app_seq_midi_transport(&app, 0xFBu) != FM1_APP_SEQ_HELD) return 0;
  if (app.seq_midi_count != 3u || app.seq_midi_pend[0] != 0xFAu ||
      app.seq_midi_pend[1] != 0xFCu || app.seq_midi_pend[2] != 0xFBu) return 0;
  /* Start, Stop, Continue in that order leaves the transport running. */
  return flush_held() && playing_is(1);
}

static int local_command_supersedes_midi(uint8_t midi, const char *local,
                                         int expect_playing) {
  fm1_seq_cmd_t command;
  if (!init_app() || !fm1_seq_parse(local, strlen(local), &command)) return 0;
  apply_pressure();
  if (fm1_app_seq_midi_transport(&app, midi) != FM1_APP_SEQ_HELD ||
      fm1_app_seq_cmd(&app, &command) != FM1_APP_SEQ_HELD) return 0;
  if (app.seq_midi_count != 0 || !app.seq_pending) return 0;
  return flush_held() && playing_is(expect_playing);
}

int main(void) {
  if (!saturated_stop_is_retained()) {
    fputs("saturated MIDI Stop was lost\n", stderr);
    return 1;
  }
  if (!held_transport_order_is_preserved()) {
    fputs("held Start/Stop/Continue order changed\n", stderr);
    return 2;
  }
  if (!local_command_supersedes_midi(0xFAu, "stop", 0)) {
    fputs("local Stop did not supersede held MIDI transport\n", stderr);
    return 3;
  }
  if (!local_command_supersedes_midi(0xFCu, "play", 1)) {
    fputs("local Play did not supersede held MIDI transport\n", stderr);
    return 4;
  }
  puts("app MIDI transport FIFO: PASS");
  return 0;
}
