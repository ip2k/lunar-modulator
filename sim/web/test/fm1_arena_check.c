/* MIT. Actual shared-app arena admission and live engine checks. */
#define _POSIX_C_SOURCE 200112L
#include "fm1_app.h"
#if FM1_APP_EXTERNAL_ARENAS
#include "project_start.h"
#endif
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

#if FM1_APP_EXTERNAL_ARENAS
static fm1_app_t managed;
static struct { int fail; unsigned allocations, frees; } storage;
static void *allocate(void *ctx, size_t bytes) {
  (void)ctx;
  if (storage.fail) return NULL;
  void *p = NULL;
  if (posix_memalign(&p, 16, bytes)) return NULL;
  if (p) ++storage.allocations;
  return p;
}
static void deallocate(void *ctx, void *memory) {
  (void)ctx;
  assert(memory);
  ++storage.frees;
  free(memory);
}
static void adoption_check(int shard) {
  fm1_app_unit_t candidate[FM1_APP_UNITS], saved[FM1_APP_UNITS];
  memset(candidate, 0, sizeof candidate);
  for (int k = 0; k < FM1_APP_UNITS; ++k) candidate[k].index = -1;
  fm1_app_init(&managed, 44118.0f);
  assert(fm1_app_set_storage(&managed, NULL, allocate, deallocate) == 0);
  size_t baseline = fm1_app_ram(&managed);
  const int slots[] = {0, 1, 3};
  const char *names[] = {"trio", "test-gain", "test-sine"};
  for (int k = 0; k < 3; ++k) {
    fm1_app_unit_t *u = &candidate[slots[k]];
    u->index = fm1_app_find(names[k]); assert(u->index >= 0);
    u->e = fm1_engines[u->index];
    u->bytes = u->cap = u->e->instance_size(&managed.host);
    u->mem = allocate(NULL, u->bytes); assert(u->mem);
    memset(u->mem, 0, u->bytes);
    u->self = u->e->create(u->mem, &managed.host); assert(u->self);
    for (unsigned n = 0; n < u->e->n_params; ++n) {
      u->value[n] = u->e->params[n].def;
      u->e->set_param(u->self, n, u->value[n]);
    }
  }
  candidate[1].value[0] = 0.5f;
  candidate[1].e->set_param(candidate[1].self, 0, 0.5f);
  memcpy(saved, candidate, sizeof saved);
  unsigned allocations = storage.allocations, frees = storage.frees;
  switch (shard % 8) {
    case 0: candidate[0].index = -1; break;
    case 1: candidate[0].bytes = 0; break;
    case 2: candidate[0].mem++; break;
    case 3: candidate[0].self = NULL; break;
    case 4: candidate[3].mem = candidate[0].mem; candidate[3].cap = candidate[0].cap; break;
    case 5: candidate[2].ram = 1; break;
    case 6: candidate[1].e = candidate[0].e; break;
    case 7: managed.frames = 1; break;
  }
  fm1_app_unit_t refused[FM1_APP_UNITS];
  memcpy(refused, candidate, sizeof refused);
  assert(fm1_app_adopt_start_units(&managed, candidate) != 0);
  assert(!memcmp(refused, candidate, sizeof refused));
  for (int k = 0; k < FM1_APP_UNITS; ++k) assert(!managed.unit[k].e);
  assert(storage.allocations == allocations && storage.frees == frees);
  managed.frames = 0;
  memcpy(candidate, saved, sizeof saved);
  assert(fm1_app_adopt_start_units(&managed, candidate) == 0);
  assert(storage.allocations == allocations && storage.frees == frees);
  size_t expected = 0;
  for (int k = 0; k < 3; ++k) {
    const fm1_app_unit_t *u = &managed.unit[slots[k]];
    assert(u->self == saved[slots[k]].self && u->mem == saved[slots[k]].mem);
    expected += fm1_app_ram_of(u->e);
  }
  assert(fm1_app_ram(&managed) == baseline + expected + FM1_APP_MIX_BLOCK_BYTES);
  assert(fm1_app_get_param(&managed, 1, 0) == 0.5f);
  assert(managed.mod && fm1_mod_base(managed.mod, (unsigned)fm1_app_mod_unit(1), 0) == 0.5f);
  for (int k = 0; k < FM1_APP_UNITS; ++k)
    assert(!candidate[k].e && !candidate[k].mem && candidate[k].index == -1);
  assert(fm1_app_adopt_start_units(&managed, candidate) != 0);
  fm1_app_key(&managed, shard % 27, 1, 100);
  double energy = 0;
  for (int k = 0; k < 128; ++k) {
    const float *samples = fm1_app_render(&managed, 64);
    for (int n = 0; n < 128; ++n) {
      assert(isfinite(samples[n])); energy += samples[n] * samples[n];
    }
  }
  assert(energy > 0.001);
  fm1_app_all_notes_off(&managed);
  assert(fm1_app_select(&managed, 1, -1) == 0);
  assert(fm1_app_select(&managed, 3, -1) == 0);
  managed.unit[0].e->destroy(managed.unit[0].self);
  deallocate(NULL, managed.unit[0].mem);
  memset(&managed.unit[0], 0, sizeof managed.unit[0]); managed.unit[0].index = -1;
  assert(storage.allocations == storage.frees);
}
static void *pool_allocate(void *ctx, size_t bytes) {
  return lunar_instance_pool_alloc(ctx, bytes);
}
static void pool_deallocate(void *ctx, void *memory) {
  assert(lunar_instance_pool_free(ctx, memory) == 0);
}
static void pool_adoption_check(int shard) {
  lunar_instance_pool_t pool;
  lunar_project_engines_t candidate, saved;
  memset(&candidate, 0, sizeof candidate);
  assert(lunar_instance_pool_init(&pool, arena.data, sizeof arena.data) == 0);
  candidate.pool = &pool;
  fm1_app_init(&managed, 44118.0f);
  assert(fm1_app_set_storage(&managed, &pool, pool_allocate, pool_deallocate) == 0);
  unsigned chosen = (unsigned)shard % 14u;
  unsigned midi = 14u + (unsigned)shard % FM1_APP_SOUNDS;
  unsigned parent = chosen >= 4u && chosen < 12u ? (chosen - 4u) / 2u : 0u;
  for (unsigned i = 0; i < 18u; ++i) {
    if (i != chosen && i != parent && i != midi) continue;
    lunar_project_instance_t *u = &candidate.unit[i];
    if (i == midi) u->engine = fm1_app_arp_engine();
    else {
      int index = fm1_app_find(i < 4u ? "trio" : "test-gain");
      assert(index >= 0); u->engine = fm1_engines[index];
    }
    assert(u->engine);
    u->bytes = u->engine->instance_size(&managed.host);
    u->memory = lunar_instance_pool_alloc(&pool, u->bytes); assert(u->memory);
    memset(u->memory, 0, u->bytes);
    u->self = u->engine->create(u->memory, &managed.host); assert(u->self);
    for (unsigned n = 0; n < u->engine->n_params; ++n) {
      u->value[n] = u->engine->params[n].def;
      u->engine->set_param(u->self, n, u->value[n]);
    }
  }
  candidate.unit[midi].value[0] = 1.0f;
  candidate.unit[midi].engine->set_param(candidate.unit[midi].self, 0, 1.0f);
  memcpy(&saved, &candidate, sizeof saved);
  unsigned count = pool.live_allocations; size_t bytes = pool.live_bytes;
  if (shard % 2) managed.storage_ctx = NULL;
  else candidate.unit[chosen].bytes = 0;
  lunar_project_engines_t refused = candidate;
  assert(lunar_project_adopt_audio_units(&managed, &candidate) != 0);
  assert(!memcmp(&refused, &candidate, sizeof candidate));
  assert(pool.live_allocations == count && pool.live_bytes == bytes);
  managed.storage_ctx = &pool; candidate = saved;
  assert(lunar_project_adopt_audio_units(&managed, &candidate) == 0);
  assert(pool.live_allocations == count && pool.live_bytes == bytes);
  int slot = chosen < 4u ? fm1_app_sound_unit((int)chosen) :
             chosen < 12u ? fm1_app_insert_unit((int)((chosen-4u)/2u), (int)((chosen-4u)%2u)) :
             1 + (int)(chosen-12u);
  assert(managed.unit[slot].self == saved.unit[chosen].self);
  assert(managed.unit[slot].mem == saved.unit[chosen].memory);
  for (unsigned i = 0; i < 14u; ++i) assert(!candidate.unit[i].engine && !candidate.unit[i].memory);
  assert(!memcmp(&candidate.unit[14], &saved.unit[14], 4u * sizeof candidate.unit[14]));
  uint8_t on[FM1_APP_SOUNDS] = {0}; on[midi - 14u] = 1;
  fm1_mfx_t prior = managed.mfx;
  float old_values[FM1_APP_SOUNDS][FM1_APP_ARP_PARAMS];
  memcpy(old_values, managed.arp_value, sizeof old_values);
  switch (shard % 4) {
    case 0: candidate.unit[midi].value[0] = NAN; break;
    case 1: candidate.unit[midi].value[0] = 0.5f; break;
    case 2: on[(midi - 14u + 1u) % FM1_APP_SOUNDS] = 1; break;
    case 3: managed.frames = 1; break;
  }
  assert(lunar_project_restore_midi_units(&managed, &candidate, on) != 0);
  assert(!memcmp(&prior, &managed.mfx, sizeof prior));
  assert(!memcmp(old_values, managed.arp_value, sizeof old_values));
  managed.frames = 0; candidate = saved;
  /* Audio rows were already transferred and must not be released twice. */
  memset(candidate.unit, 0, 14u * sizeof candidate.unit[0]);
  memset(on, 0, sizeof on); on[midi - 14u] = 1;
  lunar_project_engines_t before_midi = candidate;
  assert(lunar_project_restore_midi_units(&managed, &candidate, on) == 0);
  assert(!memcmp(&before_midi, &candidate, sizeof candidate));
  assert(pool.live_allocations == count && pool.live_bytes == bytes);
  for (unsigned k = 0; k < FM1_APP_SOUNDS; ++k) {
    const fm1_mfx_slot_t *sl = fm1_mfx_slot(&managed.mfx, k, 0);
    assert(sl && sl->on == on[k]);
    if (k == midi - 14u) {
      assert(&sl->fx->engine == candidate.unit[midi].engine);
      assert(sl->self != candidate.unit[midi].self);
      assert(sl->self == managed.mfx_mem[k]);
      assert(fm1_app_arp_get_param(&managed, (int)k, 0) == 1.0f);
    } else assert(!sl->fx && !sl->self);
  }
  assert(fm1_mfx_live_note(&managed.mfx, midi - 14u, 60, 100));
  for (unsigned k = 0; k < 256u; ++k) {
    const float *audio = fm1_app_render(&managed, 64);
    for (unsigned n = 0; n < 128u; ++n) assert(isfinite(audio[n]));
  }
  assert(managed.mfx.stats.notes_out > 0);
  fm1_app_all_notes_off(&managed);
  for (int i = 0; i < FM1_APP_UNITS; ++i) {
    fm1_app_unit_t *u = &managed.unit[i];
    if (u->self) u->e->destroy(u->self);
    if (u->mem) pool_deallocate(&pool, u->mem);
  }
  candidate.unit[midi].engine->destroy(candidate.unit[midi].self);
  pool_deallocate(&pool, candidate.unit[midi].memory);
  for (unsigned k = 0; k < FM1_APP_SOUNDS; ++k) {
    const fm1_mfx_slot_t *sl = fm1_mfx_slot(&managed.mfx, k, 0);
    if (sl && sl->fx && sl->self) sl->fx->engine.destroy(sl->self);
  }
  assert(!pool.live_allocations && !pool.live_bytes);
}
static void managed_check(int shard) {
  fm1_app_init(&managed, 44118.0f);
  assert(fm1_app_set_storage(NULL, NULL, allocate, deallocate) == -1);
  assert(fm1_app_set_storage(&managed, NULL, allocate, NULL) == -1);
  assert(fm1_app_set_storage(&managed, NULL, allocate, deallocate) == 0);
  assert(fm1_app_bind_arena(&managed, 0, arena.data, sizeof arena.data) == -1);
  int sine = fm1_app_find("test-sine"), trio = fm1_app_find("trio");
  assert(sine >= 0 && trio >= 0);
  assert(fm1_app_select(&managed, 0, sine) == 0);
  assert(storage.allocations == 1 && !storage.frees);
  assert(fm1_app_set_storage(&managed, NULL, NULL, NULL) == -1);
  fm1_app_key(&managed, shard % 27, 1, 100);
  fm1_app_unit_t previous = managed.unit[0];
  storage.fail = 1;
  assert(fm1_app_select(&managed, 0, trio) == FM1_APP_SELECT_ARENA);
  assert(!memcmp(&previous, &managed.unit[0], sizeof previous));
  double energy = 0;
  for (int k = 0; k < 16; ++k) {
    const float *samples = fm1_app_render(&managed, 64);
    for (int n = 0; n < 128; ++n) {
      assert(isfinite(samples[n]));
      energy += samples[n] * samples[n];
    }
  }
  assert(energy > 0.001);
  storage.fail = 0;
  managed.host.sample_rate = 48000.0f;
  assert(fm1_app_select(&managed, 0, trio) == -3);
  assert(!memcmp(&previous, &managed.unit[0], sizeof previous));
  assert(storage.allocations == 2 && storage.frees == 1);
  managed.host.sample_rate = 44118.0f;
  assert(fm1_app_select(&managed, 0, trio) == 0);
  assert(storage.allocations == 3 && storage.frees == 2);
  int gain = fm1_app_find("test-gain");
  assert(gain >= 0 && fm1_app_select(&managed, 1, gain) == 0);
  assert(fm1_app_select(&managed, 1, -1) == 0);
  assert(!managed.unit[1].mem && !managed.unit[1].cap);
  int second = fm1_app_sound_unit(1);
  assert(fm1_app_select(&managed, second, sine) == 0);
  assert(fm1_app_select(&managed, second, -1) == 0);
  assert(!managed.unit[second].mem && !managed.unit[second].cap);
  fm1_app_all_notes_off(&managed);
  managed.unit[0].e->destroy(managed.unit[0].self);
  deallocate(NULL, managed.unit[0].mem);
  memset(&managed.unit[0], 0, sizeof managed.unit[0]);
  managed.unit[0].index = -1;
  assert(storage.allocations == storage.frees);
  assert(fm1_app_set_storage(&managed, NULL, NULL, NULL) == 0);
}
#endif

int main(int argc, char **argv) {
  int shard = argc == 2 ? atoi(argv[1]) : -1;
  assert(shard >= 0 && shard < 16);
#if FM1_APP_EXTERNAL_ARENAS
  managed_check(shard);
  adoption_check(shard);
  pool_adoption_check(shard);
#endif
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
