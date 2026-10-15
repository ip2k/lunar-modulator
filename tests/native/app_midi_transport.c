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

static int command(const char *text) {
  fm1_seq_cmd_t c;
  return fm1_seq_parse(text, strlen(text), &c) &&
         fm1_app_seq_cmd(&app, &c) == FM1_APP_SEQ_APPLIED;
}

static int song_info(fm1_seq_info_t *info) {
  if (!app.seq) return 0;
  fm1_seq_get_info(app.seq, info);
  return info->song_len == 2 && info->song_entries == 2 &&
         info->song[0] == 0 && info->song[1] == 1;
}

/* Test the semantic transport API against a real two-scene sequencer song.
 * FIFO tests above prove delivery ordering; this verifies what those bytes do
 * to musical position and sounding gates. */
static int transport_semantics_result(void) {
  fm1_seq_info_t info;
  unsigned block, i;
  int found_note_off = 0;
  uint64_t stopped_tick;
  if (!init_app() || fm1_app_default_chain(&app) != 0 || !command("bpm 30000") ||
      !command("route 0 1 0") ||
      !command("tog 0 0 60 100") ||
      !command("clipsel 0 1") || !command("tog 0 0 64 100") ||
      !command("sgins 0 0 1") || !command("sgins 1 1 1") ||
      !song_info(&info) || !command("clipsel 0 0")) return 10;

  if (fm1_app_seq_midi_transport(&app, 0xFAu) != FM1_APP_SEQ_APPLIED) return 11;
  fm1_seq_get_info(app.seq, &info);
  if (!info.playing || info.song_pos != 0 || info.song_entry != 0) return 12;

  /* The first scene contains a step-zero note, so a render creates a real
   * gate which Stop must release. */
  for (block = 0; block < 400 && app.seq_host.notes_to_engine == 0; ++block)
    (void)fm1_app_render(&app, 64);
  if (app.seq_host.notes_to_engine == 0) return 13;
  if (fm1_app_seq_midi_transport(&app, 0xFCu) != FM1_APP_SEQ_APPLIED) return 14;
  fm1_seq_get_info(app.seq, &info);
  stopped_tick = info.master_tick;
  for (i = 0; i < app.seq_host.n; ++i) {
    if (app.seq_host.ev[i].kind == FM1_SEQ_EV_NOTE_OFF) found_note_off = 1;
  }
  if (!found_note_off) return 15;
  (void)fm1_app_render(&app, 64); /* dispatch the queued releases */

  /* Resume, advance into scene 1, then stop and hold its exact cursor. */
  if (fm1_app_seq_midi_transport(&app, 0xFBu) != FM1_APP_SEQ_APPLIED) return 16;
  fm1_seq_get_info(app.seq, &info);
  if (!info.playing || info.song_pos != 0 || info.master_tick != stopped_tick) return 17;
  for (block = 0; block < 800; ++block) {
    (void)fm1_app_render(&app, 64);
    fm1_seq_get_info(app.seq, &info);
    if (info.song_pos == 1) break;
  }
  if (block == 800 || info.song_entry != 1 || !info.playing) return 18;
  if (fm1_app_seq_midi_transport(&app, 0xFCu) != FM1_APP_SEQ_APPLIED) return 19;
  fm1_seq_get_info(app.seq, &info);
  if (info.playing || info.song_pos != 1 || info.song_entry != 1) return 20;
  {
    const uint64_t paused_tick = info.master_tick;
    for (block = 0; block < 32; ++block) (void)fm1_app_render(&app, 64);
    fm1_seq_get_info(app.seq, &info);
    if (info.playing || info.song_pos != 1 || info.master_tick != paused_tick) return 21;
  }

  /* Continue resumes entry 1; Start while there always rewinds to entry 0. */
  if (fm1_app_seq_midi_transport(&app, 0xFBu) != FM1_APP_SEQ_APPLIED) return 22;
  fm1_seq_get_info(app.seq, &info);
  if (!info.playing || info.song_pos != 1 || info.song_entry != 1) return 23;
  if (fm1_app_seq_midi_transport(&app, 0xFAu) != FM1_APP_SEQ_APPLIED) return 24;
  fm1_seq_get_info(app.seq, &info);
  return info.playing && info.song_pos == 0 && info.song_entry == 0 ? 0 : 25;
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
  {
    const int transport_result = transport_semantics_result();
    if (transport_result) {
      fprintf(stderr, "MIDI transport semantic stage %d failed\n", transport_result);
      return 5;
    }
  }
  puts("app MIDI transport FIFO: PASS");
  return 0;
}
