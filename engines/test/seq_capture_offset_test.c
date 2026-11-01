/* Playing Capture keeps the loop origin; compatibility keeps Movy's ticks. MIT. */
#include "fm1_seq.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint64_t arena[32768u / 8u];
static fm1_seq_ev_t events[128];
static void cmd(fm1_seq_t *s, const char *text) {
  fm1_seq_apply_text(s, text, strlen(text), events, 128);
}
static unsigned ticks(fm1_seq_t *s, unsigned count) {
  unsigned n, hits = 0;
  while (count--) {
    n = fm1_seq_advance(s, 100, events, 128);
    for (unsigned i = 0; i < n; ++i)
      hits += events[i].kind == FM1_SEQ_EV_NOTE_ON && events[i].a == 67;
  }
  return hits;
}
int main(void) {
  const unsigned starts[] = {16, 32, 48};
  const unsigned lengths[] = {16, 17, 32};
  const unsigned scales[][2] = {{1, 1}, {2, 1}, {1, 2}};
  unsigned cases = 0;
  for (unsigned compat = 0; compat <= 2; ++compat)
    for (unsigned k = 0; k < 3; ++k)
      for (unsigned q = 0; q < 3; ++q) {
        fm1_seq_limits_t lim;
        fm1_seq_track_info_t tr;
        fm1_seq_clip_info_t clip;
        fm1_seq_note_info_t note;
        fm1_seq_t *s;
        char line[128];
        unsigned expected, found = 0;
        fm1_seq_limits_default(&lim, 1);
        lim.compat = (uint8_t)compat;
        assert(fm1_seq_size(&lim) <= sizeof arena);
        s = fm1_seq_create(arena, &lim, 48000);
        snprintf(line, sizeof line, "bpm 30000;tog 0 %u 60 100;loop 0 %u %u;cscl 0 %u %u;play",
                 starts[k], starts[k], lengths[k], scales[q][0], scales[q][1]);
        cmd(s, line);
        ticks(s, 20);
        assert(fm1_seq_get_track(s, 0, &tr));
        expected = tr.pos_tick;
        cmd(s, "non 0 67 100");
        ticks(s, 2);
        cmd(s, "nof 0 67;cap 0");
        assert(fm1_seq_get_clip(s, 0, 0, &clip));
        if (compat) expected %= lengths[k] * 24u;
        for (unsigned i = 0; fm1_seq_get_note(s, 0, 0, (uint16_t)i, &note); ++i) {
          if (note.pitch != 67) continue;
          ++found;
          assert(note.tick == (int32_t)expected);
          if (!compat) assert(note.step >= starts[k] && note.step < starts[k] + lengths[k]);
        }
        assert(found == 1);
        assert(clip.length_steps == lengths[k]);
        if (!compat) assert(ticks(s, 2000) > 0);
        ++cases;
      }
  printf("playing Capture offset loops: %u cases\n", cases);
  return 0;
}
