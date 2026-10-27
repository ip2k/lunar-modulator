/* Compact session reads agree with the full public getters. MIT. */
#include "../seq/seq_int.h"
#include <assert.h>
#include <stdio.h>

static uint64_t memory[131072 / 8], before[131072 / 8];
static uint32_t seed = 71839;
static uint32_t next(void) {
  seed = seed * 1664525u + 1013904223u;
  return seed;
}

int main(void) {
  unsigned checks = 0;
  for (unsigned tracks = 1; tracks <= FM1_SEQ_MAX_TRACKS; ++tracks) {
    fm1_seq_limits_t limits;
    fm1_seq_limits_default(&limits, (uint8_t)tracks);
    const size_t bytes = fm1_seq_size(&limits);
    assert(bytes <= sizeof memory);
    fm1_seq_t *s = fm1_seq_create(memory, &limits, 44118);
    assert(s);
    /* Include empty/full grids, every playing slot, NONE, loop boundaries,
     * queued selections/stops and unrelated automation metadata. */
    for (unsigned pass = 0; pass < 128; ++pass) {
      for (unsigned t = 0; t < tracks; ++t) {
        sq_track_t *tr = &sq_tracks(s)[t];
        tr->active = (uint8_t)(pass % 9 == 8 ? FM1_SEQ_NONE : pass % 9);
        tr->playing = (uint8_t)(pass % 10 >= 8 ? FM1_SEQ_NONE : pass % 10);
        tr->queued = (uint8_t)(pass % 3 ? next() % 8 : FM1_SEQ_NONE);
        tr->pending_stop = (uint8_t)(pass & 1);
        tr->pos_tick = (uint16_t)next();
        tr->route_kind = (uint8_t)(pass * 16u + t);
        tr->route_index = (uint8_t)(next() >> 16);
        for (unsigned k = 0; k < FM1_SEQ_SLOTS; ++k) {
          sq_clip_t *c = sq_clip(s, t, k);
          c->length_steps = pass % 4 == 0 ? 0 : pass % 4 == 1 ? 256 : (uint16_t)(next() % 257);
          c->loop_start = (uint8_t)next();
        }
      }
      memcpy(before, memory, bytes);
      for (unsigned t = 0; t < tracks; ++t) {
        fm1_seq_track_info_t tr;
        fm1_seq_session_track_info_t got;
        fm1_seq_route_info_t route;
        unsigned clips = 0, length = 0, start = 0;
        assert(fm1_seq_get_track(s, (uint8_t)t, &tr));
        memset(&route, 0xa5, sizeof route);
        assert(fm1_seq_get_route(s, (uint8_t)t, &route));
        assert(route.route_kind == tr.route_kind && route.route_index == tr.route_index);
        for (unsigned k = 0; k < FM1_SEQ_SLOTS; ++k) {
          fm1_seq_clip_info_t c;
          assert(fm1_seq_get_clip(s, (uint8_t)t, (uint8_t)k, &c));
          if (!c.length_steps) continue;
          clips |= 1u << k;
          if (k == tr.playing) { length = c.length_steps; start = c.loop_start; }
        }
        memset(&got, 0xa5, sizeof got);
        assert(fm1_seq_get_session_track(s, (uint8_t)t, &got));
        assert(got.active == tr.active && got.playing == tr.playing);
        assert(got.queued == tr.queued && got.pending_stop == tr.pending_stop);
        assert(got.pos_tick == tr.pos_tick && got.clips == clips);
        assert(got.playing_length == length && got.playing_loop_start == start);
        ++checks;
      }
      assert(!memcmp(before, memory, bytes));
      {
        fm1_seq_session_track_info_t got, untouched;
        memset(&got, 0xa5, sizeof got);
        untouched = got;
        assert(!fm1_seq_get_session_track(s, (uint8_t)tracks, &got));
        assert(!memcmp(&got, &untouched, sizeof got));
        fm1_seq_route_info_t route, route_before;
        memset(&route, 0xa5, sizeof route);
        route_before = route;
        assert(!fm1_seq_get_route(s, (uint8_t)tracks, &route));
        assert(!memcmp(&route, &route_before, sizeof route));
      }
    }
  }
  printf("%u session snapshots passed\n", checks);
  return 0;
}
