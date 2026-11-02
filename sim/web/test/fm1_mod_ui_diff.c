/* Offline differential oracle for the MATRIX destination storage change.
 * Link a symbol-renamed baseline fm1_mod_ui.c alongside the current object. */
#include "fm1_mod_ui.h"
#include "fm1_app.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef NDEBUG
#error "The differential oracle requires assertions"
#endif
int old_fm1_mod_ui_dests(const fm1_mod_ui_env_t *, fm1_mod_dest_t *, int);
void old_fm1_mod_ui_matrix_knob(const fm1_mod_ui_env_t *, fm1_mod_ui_t *, int, int, uint64_t, fm1_mod_ui_say_t *);
void old_fm1_mod_ui_matrix_algorithm(const fm1_mod_ui_env_t *, fm1_mod_ui_t *, int, fm1_mod_ui_say_t *);
int old_fm1_mod_ui_commit(const fm1_mod_ui_env_t *, fm1_mod_ui_t *);
static fm1_mod_ui_env_t env[2];
static fm1_mod_ui_t ui[2];
static fm1_mod_ui_say_t say[2];
static char logbuf[2][8192];
static size_t used[2];
static unsigned long events, layouts;
static uint32_t seed = 1979;
static unsigned rnd(void) { seed = seed * 1664525u + 1013904223u; return seed; }
static void emit(void *ctx, const char *line) {
  unsigned k = (unsigned)(uintptr_t)ctx;
  int n = snprintf(logbuf[k] + used[k], sizeof logbuf[k] - used[k], "%s\n", line);
  assert(n >= 0 && (size_t)n < sizeof logbuf[k] - used[k]);
  used[k] += (size_t)n;
}
static void equal(void) {
  unsigned i;
  assert(!memcmp(&ui[0], &ui[1], sizeof ui[0]));
  assert(!memcmp(&say[0], &say[1], sizeof say[0]));
  assert(used[0] == used[1] && !memcmp(logbuf[0], logbuf[1], used[0]));
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t a, b;
    assert(fm1_mod_get_slot(env[0].m, i, &a));
    assert(fm1_mod_get_slot(env[1].m, i, &b));
    assert(!memcmp(&a, &b, sizeof a));
  }
  for (i = 0; i < FM1_MOD_POSITIONS; ++i) {
    unsigned j;
    assert(fm1_mod_kind_at(env[0].m, i) == fm1_mod_kind_at(env[1].m, i));
    for (j = 0; j < FM1_MOD_MAX_PARAMS; ++j)
      assert(fm1_mod_param(env[0].m, i, j) == fm1_mod_param(env[1].m, i, j));
  }
  assert(!memcmp(env[0].m, env[1].m, fm1_mod_size()));
  ++events;
}
static void event(int op, int knob, int delta) {
  used[0] = used[1] = 0;
  memset(say, 0xa5, sizeof say);
  switch (op) {
  case 0:
    fm1_mod_ui_matrix_knob(&env[0], &ui[0], knob, delta, events + 100, &say[0]);
    old_fm1_mod_ui_matrix_knob(&env[1], &ui[1], knob, delta, events + 100, &say[1]); break;
  case 1:
    fm1_mod_ui_matrix_algorithm(&env[0], &ui[0], delta, &say[0]);
    old_fm1_mod_ui_matrix_algorithm(&env[1], &ui[1], delta, &say[1]); break;
  case 2: assert(fm1_mod_ui_commit(&env[0], &ui[0]) == old_fm1_mod_ui_commit(&env[1], &ui[1])); break;
  case 3:
    fm1_mod_ui_matrix_select(&ui[0], delta);
    fm1_mod_ui_matrix_select(&ui[1], delta); break;
  }
  equal();
}
static int lists(void) {
  fm1_mod_dest_t a[FM1_MOD_UI_MAX_DESTS + 2], b[FM1_MOD_UI_MAX_DESTS + 2];
  int n, m, cap;
  memset(a, 0x5a, sizeof a); memset(b, 0x5a, sizeof b);
  n = fm1_mod_ui_dests(&env[0], a, FM1_MOD_UI_MAX_DESTS);
  m = old_fm1_mod_ui_dests(&env[1], b, FM1_MOD_UI_MAX_DESTS);
  assert(n == m && !memcmp(a, b, sizeof a));
  for (cap = -1; cap <= n + 1; ++cap) {
    memset(a, 0x5a, sizeof a); memset(b, 0x5a, sizeof b);
    assert(fm1_mod_ui_dests(&env[0], a, cap) == old_fm1_mod_ui_dests(&env[1], b, cap));
    assert(!memcmp(a, b, sizeof a));
  }
  ++layouts;
  return n;
}
static void kind(unsigned p, int k) {
  assert(fm1_mod_set_kind(env[0].m, p, k) == fm1_mod_set_kind(env[1].m, p, k));
}
static void reset_ui(void) { fm1_mod_ui_init(&ui[0]); ui[1] = ui[0]; }
static void fm6_identity(void) {
  static fm1_app_t app;
  fm1_mod_slot_t s;
  unsigned i;
  int dx7 = fm1_app_find("dx7"), macro = fm1_app_find("macro");
  assert(dx7 >= 0 && macro >= 0);
  fm1_app_init(&app, 44118);
  assert(fm1_app_select(&app, 0, dx7) == 0);
  assert(app.unit[0].e == &app.dx7.engine && app.unit[0].e != fm1_engines[dx7]);
  fm1_mod_ui_init(&app.mui);
  memset(&s, 0, sizeof s); s.via = FM1_MOD_NONE;
  for (i = 0; i < FM1_MOD_SLOTS; ++i) assert(fm1_mod_set_slot(app.mod, i, &s));
  s.src = FM1_MOD_SRC_VEL; s.dst_unit = FM1_MOD_SOUND; s.dst = 2;
  s.flags = FM1_MOD_SLOT_ON; s.amount = 1234;
  assert(fm1_mod_set_slot(app.mod, 0, &s));       /* FM6 Brightness: ON */
  s.flags = 0; assert(fm1_mod_set_slot(app.mod, 1, &s)); /* Brightness: OFF */
  s.flags = FM1_MOD_SLOT_ON; s.dst = 5;
  assert(fm1_mod_set_slot(app.mod, 2, &s));       /* shared Volume */
  assert(fm1_app_select(&app, 0, macro) == 0);
  for (i = 0; i < 2; ++i) {
    assert(fm1_mod_get_slot(app.mod, i, &s));
    assert(!(s.flags & FM1_MOD_SLOT_ON) && s.dst == 2 && s.amount == 1234);
    assert(app.mui.aim[i] == dx7 + 1);
    assert(((app.mui.aim_on >> i) & 1u) == (i == 0));
  }
  assert(fm1_mod_get_slot(app.mod, 2, &s));
  assert((s.flags & FM1_MOD_SLOT_ON) && s.dst == 7 && s.amount == 1234);
  assert(!app.mui.aim[2]);
  assert(fm1_app_select(&app, 0, dx7) == 0);
  for (i = 0; i < 3; ++i) {
    assert(fm1_mod_get_slot(app.mod, i, &s));
    assert(((s.flags & FM1_MOD_SLOT_ON) != 0) == (i != 1));
    assert(s.dst == (i == 2 ? 5 : 2) && s.amount == 1234);
    assert(!app.mui.aim[i] && !((app.mui.aim_on >> i) & 1u));
  }
  puts("PASS: live FM6 descriptor cable disable/re-aim/restore (ON and OFF)");
}
int main(void) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, 44118, 64 };
  void *mem[2];
  unsigned k, p, j;
  clock_t start = clock();
  for (k = 0; k < 2; ++k) {
    mem[k] = calloc(1, fm1_mod_size()); assert(mem[k]);
    env[k].m = fm1_mod_create(mem[k], &host, 1); assert(env[k].m);
    env[k].emit = emit; env[k].ctx = (void *)(uintptr_t)k;
  }
  reset_ui(); lists();
  /* Every registry descriptor at every sink and every kind at every position,
   * including empty positions. Every bulk-output cap and every picker boundary. */
  for (p = 0; p < FM1_MOD_UI_SINKS; ++p) {
    for (k = 0; k < fm1_engine_count; ++k) {
      env[0].unit[p] = env[1].unit[p] = fm1_engines[k]; lists();
    }
    env[0].unit[p] = env[1].unit[p] = NULL;
  }
  for (p = 0; p < FM1_MOD_POSITIONS; ++p) {
    for (k = 0; k < fm1_mod_kind_count; ++k) {
      int n;
      kind(p, k); n = lists();
      for (j = 0; j < (unsigned)n; ++j) {
        static const int deltas[] = { -1000, -2, -1, 0, 1, 2, 1000 };
        unsigned d;
        for (d = 0; d < sizeof deltas / sizeof deltas[0]; ++d) {
          reset_ui(); ui[0].picker = FM1_MOD_PICK_DEST; ui[0].pick = (int16_t)j; ui[1] = ui[0];
          event(1, 0, deltas[d]); event(2, 0, 0);
        }
      }
    }
    kind(p, -1);
  }
  /* Every index of a fully populated list, every current sound (including
   * invalid fallback), signed group jumps and knob clamping. */
  for (p = 0; p < FM1_MOD_UI_SINKS; ++p)
    env[0].unit[p] = env[1].unit[p] = fm1_engines[p % fm1_engine_count];
  for (p = 0; p < FM1_MOD_POSITIONS; ++p) kind(p, p % fm1_mod_kind_count);
  {
    int n = lists(), at, sound;
    for (sound = 0; sound <= FM1_MOD_SOUNDS; ++sound) {
      env[0].sound = env[1].sound = sound;
      for (at = -1; at <= n; ++at) {
        int delta;
        for (delta = -24; delta <= 24; ++delta) {
          reset_ui(); ui[0].picker = FM1_MOD_PICK_DEST; ui[0].pick = at; ui[1] = ui[0];
          event(1, 0, delta); event(2, 0, 0);
          event(0, 1, delta); event(2, 0, 0);
        }
      }
    }
  }
  /* Dense mixed layouts and event streams: page A/B, new/removal/unchanged
   * destinations, slot selection, source/VIA, kind-picker commit on entry. */
  for (k = 0; k < 256; ++k) {
    for (p = 0; p < FM1_MOD_UI_SINKS; ++p) {
      unsigned e = rnd() % (fm1_engine_count + 1);
      env[0].unit[p] = env[1].unit[p] = e < fm1_engine_count ? fm1_engines[e] : NULL;
    }
    for (p = 0; p < FM1_MOD_POSITIONS; ++p) kind(p, (int)(rnd() % (fm1_mod_kind_count + 1)) - 1);
    env[0].sound = env[1].sound = rnd() % (FM1_MOD_SOUNDS + 1);
    lists(); reset_ui();
    for (j = 0; j < 1024; ++j) {
      unsigned r = rnd();
      if (!(r % 41)) {
        ui[0].picker = FM1_MOD_PICK_KIND; ui[0].pick_at = rnd() % FM1_MOD_POSITIONS;
        ui[0].pick = rnd() % (fm1_mod_kind_count + 1); ui[1] = ui[0];
      }
      event((r >> 8) % 4, (r >> 16) % 4, (int)((r >> 24) % 9) - 4);
    }
  }
  printf("PASS: %lu layouts, %lu events, %.3f CPU seconds\n", layouts, events,
         (double)(clock() - start) / CLOCKS_PER_SEC);
  for (k = 0; k < 2; ++k) { fm1_mod_destroy(env[k].m); free(mem[k]); }
  fm6_identity();
  return 0;
}
