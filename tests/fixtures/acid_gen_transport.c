/* Acid Gen transport/origin contract through its public MIDI-effect API. MIT. */
#include "fm1_engine.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern const fm1_midi_fx_t fm1_midi_fx_acid_gen;
static const fm1_midi_fx_t *fx = &fm1_midi_fx_acid_gen;
static const fm1_host_t host = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "line %d: %s\n", __LINE__, #c); exit(1); } } while (0)
static void param(void *s, const char *name, float value) {
  unsigned i;
  for (i = 0; i < fx->engine.n_params; ++i) if (!strcmp(fx->engine.params[i].name, name)) {
    fx->engine.set_param(s, (uint16_t)i, value); return;
  }
  CHECK(0);
}
static void *create(void) {
  void *s = calloc(1, fx->engine.instance_size(&host));
  CHECK(s && fx->engine.create(s, &host) == s);
  param(s, "Density", 100); param(s, "Slide", 100);
  return s;
}
static uint32_t process(void *s, const fm1_midi_ev_t *ev, unsigned ne, unsigned running,
                        unsigned ticks, fm1_midi_ev_t *out, unsigned cap) {
  fm1_midi_fx_ctx_t ctx;
  uint16_t tick[64]; unsigned i;
  memset(&ctx, 0, sizeof(ctx));
  for (i = 0; i < ticks; ++i) tick[i] = (uint16_t)i;
  ctx.ticks = tick; ctx.n_ticks = ticks; ctx.frames = 64; ctx.running = (uint8_t)running;
  return fx->process(s, ev, ne, &ctx, out, cap);
}
static fm1_midi_ev_t event(unsigned frame, unsigned kind, unsigned key, unsigned src) {
  fm1_midi_ev_t e = { (uint16_t)frame, (uint8_t)kind, (uint8_t)key, 0 };
  e.b = FM1_MIDI_EV_B(kind == FM1_MIDI_EV_NOTE_ON ? 100 : 0, src); return e;
}
static void latch_stop(unsigned src) {
  void *s = create(); fm1_midi_ev_t in[3], out[64]; unsigned n, i, later = 0;
  param(s, "Latch", 1);
  in[0] = event(0, FM1_MIDI_EV_NOTE_ON, 45, src);
  in[1] = event(1, FM1_MIDI_EV_NOTE_OFF, 45, src);
  in[2] = event(9, FM1_MIDI_EV_STOP, 0, 0);
  n = process(s, in, 3, 0, 64, out, 64);
  CHECK(n && out[0].kind == FM1_MIDI_EV_NOTE_ON);
  for (i = 0; i < n; ++i) {
    CHECK(FM1_MIDI_EV_SRC(out[i].b) == src);
    if (out[i].frame > 9 && out[i].kind == FM1_MIDI_EV_NOTE_ON) ++later;
  }
  if (src == FM1_MIDI_SRC_SEQ) {
    CHECK(n == 2 && out[1].kind == FM1_MIDI_EV_NOTE_OFF && out[1].frame == 9);
  } else { CHECK(later > 0); }
  free(s);
}
static void run_stop(void) {
  void *s = create(); fm1_midi_ev_t out[64], stop = event(3, FM1_MIDI_EV_STOP, 0, 0); unsigned n;
  param(s, "Keys", 1);
  n = process(s, NULL, 0, 1, 8, out, 64); CHECK(n == 1);
  CHECK(FM1_MIDI_EV_SRC(out[0].b) == FM1_MIDI_SRC_SEQ);
  /* No tick follows the Stop in this call: release must use its own frame. */
  n = process(s, &stop, 1, 0, 0, out, 64);
  CHECK(n == 1 && out[0].kind == FM1_MIDI_EV_NOTE_OFF && out[0].frame == 3);
  CHECK(FM1_MIDI_EV_SRC(out[0].b) == FM1_MIDI_SRC_SEQ);
  CHECK(process(s, NULL, 0, 0, 64, out, 64) == 0);
  free(s);
}
static void same_key_origins(void) {
  void *s = create(); fm1_midi_ev_t in[4], out[64]; unsigned n, i, live_after = 0;
  in[0] = event(0, FM1_MIDI_EV_NOTE_ON, 45, FM1_MIDI_SRC_LIVE);
  in[1] = event(1, FM1_MIDI_EV_NOTE_ON, 45, FM1_MIDI_SRC_SEQ);
  in[2] = event(2, FM1_MIDI_EV_STOP, 0, 0);
  in[3] = event(40, FM1_MIDI_EV_NOTE_OFF, 45, FM1_MIDI_SRC_LIVE);
  n = process(s, in, 4, 0, 64, out, 64);
  for (i = 0; i < n; ++i) {
    if (out[i].kind == FM1_MIDI_EV_NOTE_ON && out[i].frame > 2) {
      ++live_after; CHECK(FM1_MIDI_EV_SRC(out[i].b) == FM1_MIDI_SRC_LIVE);
    }
    CHECK(out[i].frame <= 40);
  }
  CHECK(live_after && out[n - 1].frame == 40 && out[n - 1].kind == FM1_MIDI_EV_NOTE_OFF);
  free(s);
}
static void deferred_origin(void) {
  void *s = create(); fm1_midi_ev_t out[64], in = event(0, FM1_MIDI_EV_NOTE_ON, 45, FM1_MIDI_SRC_SEQ);
  CHECK(process(s, &in, 1, 0, 1, out, 64) == 1);
  in = event(7, FM1_MIDI_EV_STOP, 0, 0);
  CHECK(process(s, &in, 1, 0, 0, NULL, 0) == 0);
  CHECK(process(s, NULL, 0, 0, 0, out, 64) == 1);
  CHECK(out[0].kind == FM1_MIDI_EV_NOTE_OFF && FM1_MIDI_EV_SRC(out[0].b) == FM1_MIDI_SRC_SEQ);
  free(s);
}
static void zero_velocity(void) {
  void *s = create(); fm1_midi_ev_t in[2], out[64]; unsigned n;
  in[0] = event(0, FM1_MIDI_EV_NOTE_ON, 45, FM1_MIDI_SRC_SEQ);
  in[1] = event(7, FM1_MIDI_EV_NOTE_ON, 45, FM1_MIDI_SRC_SEQ);
  in[1].b = FM1_MIDI_EV_B(0, FM1_MIDI_SRC_SEQ);
  n = process(s, in, 2, 0, 64, out, 64);
  CHECK(n == 2 && out[1].kind == FM1_MIDI_EV_NOTE_OFF && out[1].frame == 7);
  CHECK(FM1_MIDI_EV_SRC(out[1].b) == FM1_MIDI_SRC_SEQ);
  free(s);
}
static void run_in_block(void) {
  void *s = create(); fm1_midi_ev_t in[2], out[64]; unsigned n;
  param(s, "Keys", 1);
  in[0] = event(9, FM1_MIDI_EV_STOP, 0, 0);
  in[1] = event(40, FM1_MIDI_EV_RESET, 0, 0);
  n = process(s, in, 2, 1, 48, out, 64);
  CHECK(n == 3 && out[0].frame == 0 && out[0].kind == FM1_MIDI_EV_NOTE_ON);
  CHECK(out[1].frame == 9 && out[1].kind == FM1_MIDI_EV_NOTE_OFF);
  CHECK(out[2].frame == 40 && out[2].kind == FM1_MIDI_EV_NOTE_ON);
  free(s);
}
static void same_pitch_tie(void) {
  void *s = create(); fm1_midi_ev_t in[4], out[64]; unsigned n;
  param(s, "Length", 1); param(s, "Octaves", 0);
  in[0] = event(0, FM1_MIDI_EV_NOTE_ON, 45, FM1_MIDI_SRC_LIVE);
  in[1] = event(1, FM1_MIDI_EV_NOTE_ON, 45, FM1_MIDI_SRC_SEQ);
  in[2] = event(30, FM1_MIDI_EV_STOP, 0, 0);
  in[3] = event(60, FM1_MIDI_EV_NOTE_OFF, 45, FM1_MIDI_SRC_LIVE);
  n = process(s, in, 4, 0, 64, out, 64);
  CHECK(n == 2 && out[0].kind == FM1_MIDI_EV_NOTE_ON && out[0].frame == 0);
  CHECK(out[1].kind == FM1_MIDI_EV_NOTE_OFF && out[1].frame == 60);
  CHECK(FM1_MIDI_EV_SRC(out[0].b) == FM1_MIDI_SRC_LIVE && FM1_MIDI_EV_SRC(out[1].b) == FM1_MIDI_SRC_LIVE);
  free(s);
}
int main(int argc, char **argv) {
  CHECK(argc == 2);
  if (!strcmp(argv[1], "seq-latch")) latch_stop(FM1_MIDI_SRC_SEQ);
  else if (!strcmp(argv[1], "live-latch")) latch_stop(FM1_MIDI_SRC_LIVE);
  else if (!strcmp(argv[1], "run")) run_stop();
  else if (!strcmp(argv[1], "same-key")) same_key_origins();
  else if (!strcmp(argv[1], "deferred")) deferred_origin();
  else if (!strcmp(argv[1], "zero-velocity")) zero_velocity();
  else if (!strcmp(argv[1], "run-in-block")) run_in_block();
  else if (!strcmp(argv[1], "same-pitch-tie")) same_pitch_tie();
  else CHECK(0);
  return 0;
}
