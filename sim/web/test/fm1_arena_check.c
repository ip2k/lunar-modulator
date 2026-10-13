/* MIT. Actual shared-app arena admission and live engine checks. */
#include "fm1_app.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static fm1_app_t app;
static struct {
  unsigned char before[16];
  unsigned char data[128 * 1024];
  unsigned char after[16];
} arena FM1_APP_ALIGN16;

int main(int argc, char **argv) {
  int shard = argc == 2 ? atoi(argv[1]) : -1;
  assert(shard >= 0 && shard < 16);
  memset(&arena, 0x5a, sizeof arena);
  fm1_app_init(&app, 44118.0f);
  int trio = fm1_app_find("trio");
  assert(trio >= 0);
#if FM1_APP_EXTERNAL_ARENAS
  assert(sizeof app < 400000);
  for (int k = 0; k < FM1_APP_UNITS; ++k) {
    assert(!app.unit[k].mem && !app.unit[k].cap);
  }
  assert(fm1_app_select(&app, 0, trio) == FM1_APP_SELECT_ARENA);
  assert(fm1_app_bind_arena(&app, 0, arena.data, sizeof arena.data) == 0);
  fm1_app_unit_t original = app.unit[0];
  switch (shard) {
    case 0: assert(fm1_app_bind_arena(NULL, 0, arena.data, 16) == -1); break;
    case 1: assert(fm1_app_bind_arena(&app, -1, arena.data, 16) == -1); break;
    case 2: assert(fm1_app_bind_arena(&app, FM1_APP_UNITS, arena.data, 16) == -1); break;
    case 3: assert(fm1_app_bind_arena(&app, 0, NULL, 16) == -1); break;
    case 4: assert(fm1_app_bind_arena(&app, 0, arena.data, 0) == -1); break;
    case 5: assert(fm1_app_bind_arena(&app, 0, arena.data + 1, 16) == -1); break;
    case 6: assert(fm1_app_bind_arena(&app, 0, (void *)(UINTPTR_MAX & ~(uintptr_t)15), 32) == -1); break;
    case 7: assert(fm1_app_bind_arena(&app, 0, &app, sizeof app) == -1); break;
    case 8: assert(fm1_app_bind_arena(&app, 1, arena.data, 16) == -1); break;
    case 9: assert(fm1_app_bind_arena(&app, 1, arena.data + 16, 16) == -1); break;
    case 10: assert(fm1_app_bind_arena(&app, 1, arena.before, 32) == -1); break;
    case 11:
      assert(fm1_app_bind_arena(&app, 1, arena.after, 16) == 0);
      assert(fm1_app_bind_arena(&app, 1, NULL, 0) == 0);
      break;
    case 12:
      assert(fm1_app_bind_arena(&app, 0, NULL, 0) == 0);
      assert(fm1_app_select(&app, 0, trio) == FM1_APP_SELECT_ARENA);
      assert(fm1_app_bind_arena(&app, 0, arena.data, sizeof arena.data) == 0);
      break;
    case 13:
      assert(fm1_app_bind_arena(&app, 0, arena.data, 16) == 0);
      assert(fm1_app_select(&app, 0, trio) == FM1_APP_SELECT_ARENA);
      assert(fm1_app_bind_arena(&app, 0, arena.data, sizeof arena.data) == 0);
      break;
    case 14:
      app.unit[1].mem = (unsigned char *)(UINTPTR_MAX & ~(uintptr_t)15);
      app.unit[1].cap = 32;
      assert(fm1_app_bind_arena(&app, 0, arena.data, 16) == -1);
      app.unit[1].mem = NULL; app.unit[1].cap = 0;
      break;
    default: break;
  }
  assert(!memcmp(&original, &app.unit[0], sizeof original));
#else
  assert(app.unit[0].mem == app.sound_mem[0]);
  assert(app.unit[0].cap == FM1_APP_SOUND_BYTES);
#endif
  assert(fm1_app_select(&app, 0, trio) == 0);
#if FM1_APP_EXTERNAL_ARENAS
  fm1_app_unit_t live = app.unit[0];
  assert(fm1_app_bind_arena(&app, 0, NULL, 0) == -1);
  assert(fm1_app_bind_arena(&app, 0, arena.after, 16) == -1);
  assert(!memcmp(&live, &app.unit[0], sizeof live));
#endif
  fm1_app_key(&app, shard % 27, 1, 100);
  double energy = 0;
  for (int block = 0; block < 128; ++block) {
    const float *audio = fm1_app_render(&app, 64);
    for (int frame = 0; frame < 128; ++frame) {
      assert(isfinite(audio[frame]));
      energy += audio[frame] * audio[frame];
    }
  }
  assert(energy > 0.001);
  fm1_app_key(&app, shard % 27, 0, 0);
  fm1_app_all_notes_off(&app);
  for (unsigned k = 0; k < 16; ++k) {
    assert(arena.before[k] == 0x5a && arena.after[k] == 0x5a);
  }
  printf("{\"shard\":%d,\"external\":%d,\"app_bytes\":%zu,\"passed\":true}\n",
         shard, FM1_APP_EXTERNAL_ARENAS, sizeof app);
  return 0;
}
