/* Native playing Capture refuses an unrepresentable take atomically. MIT. */
#include "../seq/seq_int.h"
#include <assert.h>
#include <stdio.h>

static uint64_t arena[131072u / 8u], before[131072u / 8u], restored[131072u / 8u];
static char saved[65536];

static fm1_seq_t *fresh(unsigned compat, unsigned start, int existing) {
  fm1_seq_limits_t lim;
  fm1_seq_limits_default(&lim, 1);
  lim.compat = (uint8_t)compat;
  assert(fm1_seq_size(&lim) <= sizeof arena);
  fm1_seq_t *s = fm1_seq_create(arena, &lim, 48000);
  sq_clip_set_loop(s, 0, (uint16_t)start, 16);
  if (existing) sq_clip_add_raw(s, 0, (uint16_t)start, start * SQ_TPS, 12, 60, 100);
  s->playing = 1;
  sq_tracks(s)[0].playing = 0;
  return s;
}

static void input(fm1_seq_t *s, unsigned tick, unsigned pos, unsigned pitch, int on) {
  s->master_tick = tick;
  sq_tracks(s)[0].pos_tick = (uint16_t)pos;
  sq_capture_push(s, 0, (uint8_t)pitch, on ? 100 : 0, on, tick * 250u);
}

static void refused_unchanged(fm1_seq_t *s) {
  const size_t bytes = fm1_seq_size(&s->lim);
  const uint32_t refused = s->stats.refused;
  memcpy(before, arena, bytes);
  assert(sq_capture_commit(s, 0) == 0);
  assert(s->stats.refused == refused + 1u);
  --s->stats.refused;
  assert(memcmp(before, arena, bytes) == 0); /* includes ring scratch and transport */
  ++s->stats.refused;
}

static void roundtrip(fm1_seq_t *s) {
  const size_t len = fm1_seq_export_movy1(s, saved, sizeof saved);
  assert(len < sizeof saved);
  fm1_seq_t *r = fm1_seq_create(restored, &s->lim, 48000);
  assert(fm1_seq_import_movy1(r, saved, len));
  fm1_seq_clip_info_t a, b;
  assert(fm1_seq_get_clip(s, 0, 0, &a) && fm1_seq_get_clip(r, 0, 0, &b));
  assert(a.length_steps == b.length_steps && a.loop_start == b.loop_start && a.notes == b.notes);
  for (unsigned i = 0; i < a.notes; ++i) {
    fm1_seq_note_info_t x, y;
    assert(fm1_seq_get_note(s, 0, 0, (uint16_t)i, &x));
    assert(fm1_seq_get_note(r, 0, 0, (uint16_t)i, &y));
    assert(x.tick == y.tick && x.gate == y.gate && x.step == y.step &&
           x.pitch == y.pitch && x.vel == y.vel);
  }
}

int main(void) {
  unsigned cases = 0;
  /* An invalid first anchor and an invalid later anchor, both with and
   * without existing notes: an acceptable prefix must never be committed. */
  for (unsigned existing = 0; existing < 2; ++existing)
    for (unsigned prefix = 0; prefix < 2; ++prefix) {
      fm1_seq_t *s = fresh(0, 240, (int)existing);
      if (prefix) {
        input(s, 192, 5952, 67, 1);
        input(s, 200, 5960, 67, 0);
      }
      input(s, 380, 6140, 72, 1);
      input(s, 382, 6142, 72, 0);
      refused_unchanged(s);
      refused_unchanged(s); /* retries keep exactly the same history */
      ++cases;
    }
  /* All anchors fit, but the legacy fresh-take length would put the
   * offset window beyond 255. Refuse before making that invalid state. */
  fm1_seq_t *s = fresh(0, 240, 0);
  input(s, 192, 5952, 67, 1);
  input(s, 200, 5960, 67, 0);
  refused_unchanged(s);
  /* The retained performance can still be captured at a usable origin. */
  sq_clip_set_loop(s, 0, 0, 16);
  assert(sq_capture_commit(s, 0) == 1 && s->cap_len == 0);
  assert(sq_clips(s)[0].seg[SQ_K_NOTES].len == 1);
  roundtrip(s);
  ++cases;
  /* Same-pitch overlapping ons use FIFO offs; a stray leading off must
   * not steal either note's gate. */
  s = fresh(0, 16, 0);
  input(s, 0, 384, 67, 0);
  input(s, 1, 385, 67, 1);
  input(s, 2, 386, 67, 1);
  input(s, 4, 388, 67, 0);
  input(s, 7, 391, 67, 0);
  assert(sq_capture_commit(s, 0) == 1);
  fm1_seq_note_info_t x, y;
  assert(fm1_seq_get_note(s, 0, 0, 0, &x) && fm1_seq_get_note(s, 0, 0, 1, &y));
  assert(x.gate == 3 && y.gate == 5 && s->stats.refused == 0);
  assert(sq_clips(s)[0].length_steps == 32); /* representable Movy growth kept */
  roundtrip(s);
  ++cases;
  /* Compatibility keeps its historical oversized window in both modes. */
  for (unsigned compat = 1; compat <= 2; ++compat) {
    s = fresh(compat, 240, 0);
    input(s, 192, 5952, 67, 1);
    input(s, 200, 5960, 67, 0);
    assert(sq_capture_commit(s, 0) == 1);
    assert(sq_clips(s)[0].length_steps == 256 && s->stats.refused == 0 && s->cap_len == 0);
    ++cases;
  }
  printf("playing Capture overflow: %u cases\n", cases);
  return 0;
}
