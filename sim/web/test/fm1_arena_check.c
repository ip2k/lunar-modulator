/* Shared renderer storage regression; no hardware acceptance is implied. */
#include "fm1_app.h"
#include "fm1_app_state.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static fm1_app_t app, reference, untouched;
static unsigned char storage[5][65536 + 32] FM1_APP_ALIGN16;
static fm1_app_arena_t arena[FM1_APP_UNITS];
static unsigned char saved[131072];
static uint32_t saved_n;

static void save_put(void *ctx, const char *s, size_t n) {
  (void)ctx;
  assert(n <= sizeof saved - saved_n);
  memcpy(saved + saved_n, s, n);
  saved_n += (uint32_t)n;
}

static void invalid(float rate) {
  assert(fm1_app_init_arenas(&app, rate, arena) == -1);
  assert(memcmp(&app, &untouched, sizeof app) == 0);
}

static void setup(fm1_app_t *a) {
  int sine = fm1_app_find("test-sine"), gain = fm1_app_find("test-gain");
  assert(sine >= 0 && gain >= 0);
  assert(fm1_app_select(a, 0, sine) == 0);
  assert(fm1_app_unit_select(a, 1, sine) == 0);
  assert(fm1_app_select(a, fm1_app_insert_unit(0, 0), gain) == 0);
  assert(fm1_app_select(a, 1, gain) == 0);
  assert(fm1_app_select(a, 2, gain) == 0);
  fm1_app_set_param(a, 1, 0, .8f);
  fm1_app_set_param(a, 2, 0, .6f);
  fm1_app_unit_note_on(a, 0, 60, 100);
  fm1_app_unit_note_on(a, 1, 67, 90);
  assert(fm1_app_seq_demo(a));
  fm1_app_seq_start_routes(a);
  fm1_app_button(a, FM1_BTN_PLAY, 1);
  fm1_app_button(a, FM1_BTN_PLAY, 0);
}

static void controls(fm1_app_t *a, unsigned block) {
  if (block == 20) fm1_app_unit_set_level(a, 1, 35);
  if (block == 40) fm1_app_set_param(a, 1, 0, .3f);
  if (block == 60) fm1_app_unit_note_off(a, 0, 60);
  if (block == 80) fm1_app_unit_note_off(a, 1, 67);
}

int main(void) {
  memset(&app, 0xa5, sizeof app);
  memcpy(&untouched, &app, sizeof app);
  invalid(NAN); invalid(INFINITY); invalid(0); invalid(-1);
  assert(fm1_app_init_arenas(NULL, 44118, arena) == -1);
  assert(fm1_app_init_arenas(&app, 44118, NULL) == -1);
  arena[0].bytes = 16; invalid(44118); /* null, nonzero */
  arena[0].mem = storage[0] + 1; invalid(44118); /* alignment */
  arena[0].mem = storage[0]; arena[0].bytes = 0; invalid(44118);
  arena[0].bytes = 64; arena[1] = arena[0]; invalid(44118);
  memset(arena, 0, sizeof arena);
  arena[0].mem = (unsigned char *)&app; arena[0].bytes = 16; invalid(44118);
  arena[0].mem = (unsigned char *)arena; invalid(44118);
  arena[0].mem = (unsigned char *)(UINTPTR_MAX & ~(uintptr_t)15);
  arena[0].bytes = 32; invalid(44118);
  memset(arena, 0, sizeof arena);
  assert(fm1_app_init_arenas(&app, 44118, arena) == 0);
  assert(fm1_app_select(&app, 0, fm1_app_find("test-sine")) == FM1_APP_SELECT_ARENA);
  for (unsigned i = 0; i < 128; ++i) assert(fm1_app_render(&app, 64)[i] == 0);

  const int units[5] = {0, 1, 2, fm1_app_sound_unit(1), fm1_app_insert_unit(0, 0)};
  memset(storage, 0x5a, sizeof storage);
  for (int i = 0; i < 5; ++i) {
    arena[units[i]].mem = storage[i] + 16;
    arena[units[i]].bytes = 65536;
  }
  assert(fm1_app_init_arenas(&app, 44118, arena) == 0);
  setup(&app);
#if !FM1_APP_EXTERNAL_ARENAS
  fm1_app_init(&reference, 44118);
  setup(&reference);
#else
  fm1_app_init(&reference, 44118);
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    assert(reference.unit[u].mem == NULL && reference.unit[u].cap == 0);
  }
#endif
  uint32_t hash = 2166136261u;
  double energy = 0;
  for (unsigned b = 0; b < 128; ++b) {
    controls(&app, b);
    const float *out = fm1_app_render(&app, 64);
#if !FM1_APP_EXTERNAL_ARENAS
    controls(&reference, b);
    assert(memcmp(out, fm1_app_render(&reference, 64), 128 * sizeof(float)) == 0);
#endif
    for (unsigned i = 0; i < 128; ++i) {
      assert(isfinite(out[i])); energy += out[i] * out[i];
      const unsigned char *bytes = (const unsigned char *)&out[i];
      for (unsigned j = 0; j < sizeof(float); ++j) hash = (hash ^ bytes[j]) * 16777619u;
    }
  }
  assert(energy > 0);
  fm1_state_report_t report;
  fm1_app_state_report_t load_report;
  assert(fm1_app_state_save(&app, FM1_STATE_PROJECT, 0, 0, save_put, NULL, &report));
  fm1_app_state_mem_t input = {saved, saved_n};
  assert(fm1_app_state_load(&app, fm1_app_state_mem_read, &input, saved_n, NULL, &load_report));
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    assert(app.unit[u].mem == arena[u].mem && app.unit[u].cap == arena[u].bytes);
  }
  assert(app.unit[0].self && app.unit[1].self && app.unit[2].self);
  for (int i = 0; i < 5; ++i) for (int j = 0; j < 16; ++j) {
    assert(storage[i][j] == 0x5a && storage[i][65536 + 16 + j] == 0x5a);
  }
  printf("{\"app_bytes\":%lu,\"pcm_hash\":\"%08x\",\"external\":%d}\n",
         (unsigned long)sizeof app, hash, FM1_APP_EXTERNAL_ARENAS);
  return 0;
}
