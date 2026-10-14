/* MIT. Actual shared-app arena admission and live engine checks. */
#define _POSIX_C_SOURCE 200112L
#include "fm1_app.h"
#if FM1_APP_EXTERNAL_ARENAS
#include "project_start.h"
#include "project_boot.h"
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
static void mod_cold_check(int which) {
  fm1_app_init(&managed, 44118.0f);
  if (which >= 20) {
    fm1_app_t *before = malloc(sizeof managed);
    assert(before);
    if (which == 20 || which == 25) managed.frames = 1;
    memcpy(before, &managed, sizeof managed);
    switch (which) {
      case 20: assert(!fm1_app_mod_prepare_cold(&managed)); break;
      case 21: assert(!fm1_app_mod_prepare_cold(NULL)); break;
      case 22: assert(!fm1_app_mod_adopt_cold(NULL, managed.mod, 0)); break;
      case 23: assert(!fm1_app_mod_adopt_cold(&managed, NULL, 0)); break;
      case 24: assert(!fm1_app_mod_adopt_cold(&managed, managed.mod, 0)); break;
      case 25: assert(!fm1_app_mod_adopt_cold(&managed, managed.mod, 0)); break;
      default:
        assert(fm1_app_mod_prepare_cold(&managed));
        memcpy(before, &managed, sizeof managed);
        assert(!fm1_app_mod_adopt_cold(&managed,
            which == 26 ? NULL : (fm1_mod_t *)(arena.data + 16 * (which - 27)), 0));
        break;
    }
    assert(!memcmp(before, &managed, sizeof managed));
    free(before);
    return;
  }
  const int trio = fm1_app_find("trio");
  assert(trio >= 0);
  assert(fm1_app_bind_arena(&managed, 0, arena.data, sizeof arena.data) == 0);
  assert(fm1_app_select(&managed, 0, trio) == 0);
  assert(fm1_app_mod_prepare_cold(&managed) && !managed.mod);
  const uint32_t seed = 0x13570000u + (uint32_t)which;
  fm1_mod_t *staged = fm1_mod_create(managed.mod_mem, &managed.host, seed);
  assert(staged && (void *)staged == (void *)managed.mod_mem);
  const int kind = fm1_mod_kind_find(which & 1 ? "env" : "lfo");
  assert(kind >= 0 && fm1_mod_set_kind(staged, 0, kind) >= 0);
  const fm1_param_t *p = &fm1_mod_kinds[kind]->params[0];
  assert(fm1_mod_set_param(staged, 0, 0, p->min + (p->max - p->min) * 0.25f));
  const float param = fm1_mod_param_base(staged, 0, 0);
  fm1_mod_bind(staged, FM1_MOD_SOUND, managed.unit[0].e);
  const fm1_param_t *sound_p = &managed.unit[0].e->params[0];
  fm1_mod_set_base(staged, FM1_MOD_SOUND, 0,
      sound_p->min + (sound_p->max - sound_p->min) * 0.375f);
  const float base = fm1_mod_base(staged, FM1_MOD_SOUND, 0);
  fm1_mod_slot_t slot;
  memset(&slot, 0, sizeof slot);
  slot.src = FM1_MOD_SRC_VEL; slot.via = FM1_MOD_NONE;
  slot.dst_unit = FM1_MOD_HOST; slot.dst = FM1_MOD_HOST_AMP_UID;
  slot.amount = fm1_mod_q14(-0.5f); slot.flags = FM1_MOD_SLOT_ON;
  assert(fm1_mod_set_slot(staged, 0, &slot) >= 0);
  assert(fm1_app_mod_adopt_cold(&managed, staged, seed));
  assert(managed.mod == staged && managed.mod_seed == seed);
  assert(managed.mod_glue.mod == staged && managed.mod_glue.ctx == &managed);
  assert(managed.mod_glue.sound == managed.unit[0].e && managed.mod_glue.write);
  assert(fm1_mod_kind_at(staged, 0) == kind);
  assert(fm1_mod_param_base(staged, 0, 0) == param);
  assert(fm1_mod_base(staged, FM1_MOD_SOUND, 0) == base);
  fm1_mod_slot_t restored;
  assert(fm1_mod_get_slot(staged, 0, &restored));
  assert(!memcmp(&slot, &restored, sizeof slot));
  fm1_app_key(&managed, which % 27, 1, 100);
  double energy = 0;
  for (int block = 0; block < 8; ++block) {
    const float *audio = fm1_app_render(&managed, 64);
    for (int n = 0; n < 128; ++n) {
      assert(isfinite(audio[n])); energy += audio[n] * audio[n];
    }
  }
  assert(energy > 0.0001 && managed.mod_amp_used);
  assert(fm1_mod_sent(staged, FM1_MOD_HOST, FM1_MOD_HOST_AMP) < 1.0f);
  fm1_app_key(&managed, which % 27, 0, 0);
  fm1_app_all_notes_off(&managed);
  fm1_app_mod_reset(&managed, seed);
}
static unsigned char scalar_bytes[16384];
static size_t scalar_size;
static void scalar_put(void *ctx, const char *p, size_t n) {
  (void)ctx;
  assert(n <= sizeof scalar_bytes - scalar_size);
  memcpy(scalar_bytes + scalar_size, p, n);
  scalar_size += n;
}
static void project_mod_check(int which) {
  fm1_state_report_t report;
  fm1_rec_t r = {0};
  const uint8_t version[3] = {0, 1, 0};
  void *writer_mem = calloc(1, fm1_state_bin_writer_size());
  assert(writer_mem);
  fm1_app_init(&managed, 44118.0f);
  assert(fm1_app_bind_arena(&managed, 0, arena.data, sizeof arena.data) == 0);
  assert(fm1_app_select(&managed, 0, fm1_app_find("trio")) == 0);
  /* PROJECT has no MIDI effects: restore that state before modulation. */
  lunar_project_engines_t empty = {0};
  const uint8_t midi_on[FM1_APP_SOUNDS] = {0};
  assert(lunar_project_restore_midi_units(&managed, &empty, midi_on) == FM1_APP_SELECT_OK);
  scalar_size = 0;
  fm1_state_report_init(&report);
  fm1_state_writer_t *writer = fm1_state_bin_writer(writer_mem, 0,
      FM1_STATE_WRITER_DESKTOP, version, scalar_put, NULL, &report);
  assert(writer);
  r.type = FM1_REC_HEAD; r.u.head.kind = FM1_STATE_PROJECT; r.u.head.major = 1;
  assert(fm1_state_bin_write(writer, &r));
  memset(&r, 0, sizeof r); r.type = FM1_REC_UNIT; r.role = FM1_ROLE_SOUND;
  strcpy(r.u.unit.id, which == 24 || which == 29 ? "test-sine" : "trio");
  assert(fm1_state_bin_write(writer, &r));
  memset(&r, 0, sizeof r); r.type = FM1_REC_MOD;
  assert(fm1_state_bin_write(writer, &r));
  uint32_t seed = which & 1 ? 0 : 0x24680000u + (uint32_t)which;
  if (which < 30) { /* Zero is valid; an absent seed is tested separately. */
    r.type = FM1_REC_SEED; r.u.seed = seed;
    assert(fm1_state_bin_write(writer, &r));
  }
  memset(&r, 0, sizeof r); r.type = FM1_REC_MODULE; r.role = FM1_ROLE_MODULE;
  strcpy(r.u.unit.id, which & 1 ? "env" : "lfo");
  assert(fm1_state_bin_write(writer, &r));
  memset(&r, 0, sizeof r); r.type = FM1_REC_CABLE;
  r.u.cable.s.src = FM1_MOD_SRC_VEL; r.u.cable.s.via = FM1_MOD_NONE;
  r.u.cable.s.dst_unit = FM1_MOD_HOST; r.u.cable.s.dst = FM1_MOD_HOST_AMP_UID;
  r.u.cable.s.amount = fm1_mod_q14(-0.5f); r.u.cable.s.flags = FM1_MOD_SLOT_ON;
  assert(fm1_state_bin_write(writer, &r));
  memset(&r, 0, sizeof r); r.type = FM1_REC_END;
  assert(fm1_state_bin_write(writer, &r));
  free(writer_mem);
  if (which >= 20) {
    int bad = which >= 30 ? 5 : which % 5;
    if (bad == 0) managed.frames = 1;
    if (bad == 1) scalar_bytes[scalar_size - 1] ^= 1;
    if (bad == 2) --scalar_size;
    fm1_app_t *before = malloc(sizeof managed);
    assert(before); memcpy(before, &managed, sizeof managed);
    assert(!lunar_project_restore_mod(&managed, scalar_bytes, (uint32_t)scalar_size,
        bad == 3 ? (fm1_state_report_t *)&managed : &report));
    assert(!memcmp(before, &managed, sizeof managed));
    free(before); return;
  }
  int loaded = lunar_project_restore_mod(&managed, scalar_bytes, (uint32_t)scalar_size, &report);
  if (!loaded) fprintf(stderr, "mod startup %u: %s\n", report.code, report.what);
  assert(loaded);
  assert(report.code == FM1_STATE_OK && managed.mod && managed.mod_seed == seed);
  assert(fm1_mod_kind_at(managed.mod, 0) == fm1_mod_kind_find(which & 1 ? "env" : "lfo"));
  fm1_mod_slot_t cable;
  assert(fm1_mod_get_slot(managed.mod, 0, &cable));
  assert(cable.amount == fm1_mod_q14(-0.5f) && cable.flags == FM1_MOD_SLOT_ON);
  fm1_app_key(&managed, which % 27, 1, 100);
  double energy = 0;
  for (int b = 0; b < 8; ++b) {
    const float *audio = fm1_app_render(&managed, 64);
    for (int n = 0; n < 128; ++n) {
      assert(isfinite(audio[n])); energy += audio[n] * audio[n];
    }
  }
  assert(energy > 0.0001 && managed.mod_amp_used);
  assert(fm1_mod_sent(managed.mod, FM1_MOD_HOST, FM1_MOD_HOST_AMP) < 1.0f);
  fm1_app_key(&managed, which % 27, 0, 0);
  fm1_app_all_notes_off(&managed);
  fm1_app_mod_reset(&managed, seed);
}
static void scalar_check(int which) {
  fm1_state_report_t report;
  fm1_rec_t r;
  const uint8_t version[3] = {0, 1, 0};
  void *memory = calloc(1, fm1_state_bin_writer_size());
  assert(memory);
  scalar_size = 0;
  fm1_state_writer_t *writer = fm1_state_bin_writer(memory,
      which & 1 ? FM1_STATE_BIN_DEFLATE : 0, FM1_STATE_WRITER_DESKTOP,
      version, scalar_put, NULL, &report);
  memset(&r, 0, sizeof r);
  r.type = FM1_REC_HEAD; r.u.head.major = 1;
  r.u.head.kind = which == 20 ? FM1_STATE_SETTINGS : FM1_STATE_PROJECT;
  assert(fm1_state_bin_write(writer, &r));
  if (which == 20) {
    memset(&r, 0, sizeof r); r.type = FM1_REC_SETTING;
    r.u.setting.key = FM1_SET_METRONOME;
    r.u.setting.is_bool = 1; r.u.setting.value = 1;
    assert(fm1_state_bin_write(writer, &r));
  } else if (which != 8) {
    memset(&r, 0, sizeof r); r.type = FM1_REC_SESSION;
    r.u.session.current = which % 4;
    r.u.session.octave = which & 1 ? -3 : 3;
    r.u.session.transpose = which & 1 ? -12 : 12;
    if (which == 14) r.u.session.current = -1;
    if (which == 15) r.u.session.current = 4;
    if (which == 16) r.u.session.octave = -4;
    if (which == 17) r.u.session.octave = 4;
    if (which == 18) r.u.session.transpose = -13;
    if (which == 19) r.u.session.transpose = 13;
    assert(fm1_state_bin_write(writer, &r));
  }
  if (which != 20) for (int k = 0; k < 4; ++k) {
    memset(&r, 0, sizeof r); r.type = FM1_REC_UNIT;
    r.role = FM1_ROLE_SOUND; r.sound = k; strcpy(r.u.unit.id, "trio");
    assert(fm1_state_bin_write(writer, &r));
    if (which == 8) continue; /* Valid units, but no scalar records. */
    r.type = FM1_REC_LEVEL;
    float value = k * (100.0f / 3.0f);
    if (k == 3 && which == 9) value = -0.1f;
    if (k == 3 && which == 10) value = 100.1f;
    if (k == 3 && which == 11) value = NAN;
    if (k == 3 && which == 12) value = INFINITY;
    if (k == 3 && which == 13) value = -INFINITY;
    memcpy(&r.u.level, &value, 4);
    assert(fm1_state_bin_write(writer, &r));
  }
  memset(&r, 0, sizeof r); r.type = FM1_REC_END;
  assert(fm1_state_bin_write(writer, &r)); free(memory);
  fm1_app_init(&managed, 44118.0f);
  if (which == 24) managed.frames = 1;
  fm1_app_t *before = malloc(sizeof managed); assert(before);
  memcpy(before, &managed, sizeof managed);
  const uint8_t *input = scalar_bytes;
  uint32_t size = scalar_size;
  fm1_app_t *target = &managed;
  fm1_state_report_t *output = &report;
  if (which == 21) scalar_bytes[scalar_size - 1] ^= 0x80;
  if (which == 22) --size;
  if (which == 23) size = 0;
  if (which == 25) target = NULL;
  if (which == 26) input = NULL;
  if (which == 27) size = FM1_STATE_BIN_MAX + 1;
  if (which == 28) input = (const uint8_t *)&managed;
  if (which == 29) output = (fm1_state_report_t *)&managed;
  int accepted = lunar_project_restore_scalars(target, input, size, output);
  if (which < 9) {
    assert(accepted);
    if (which == 8) assert(!memcmp(before, &managed, sizeof managed));
    else {
      assert(fm1_app_unit_current(&managed) == which % 4);
      assert(managed.octave == (which & 1 ? -3 : 3));
      assert(managed.transpose == (which & 1 ? -12 : 12));
      for (int k = 0; k < 4; ++k) assert(managed.level[k] == k * (100.0f / 3.0f));
    }
  } else {
    assert(!accepted);
    assert(!memcmp(before, &managed, sizeof managed));
  }
  free(before);
}
static void *allocate(void *ctx, size_t bytes);
static void deallocate(void *ctx, void *memory);
static void dx7_check(int which) {
  const int unit = fm1_app_sound_unit(1);
  fm1_state_report_t report;
  fm1_rec_t r;
  lunar_project_dx7_scratch_t scratch;
  uint8_t expected[FM1_DX7_USER_SLOTS][FM1_DX7_VCED_BYTES];
  const uint8_t version[3] = {0, 1, 0};
  void *memory = calloc(1, fm1_state_bin_writer_size()); assert(memory);
  scalar_size = 0;
  fm1_state_writer_t *writer = fm1_state_bin_writer(memory,
      which & 1 ? FM1_STATE_BIN_DEFLATE : 0, FM1_STATE_WRITER_DESKTOP,
      version, scalar_put, NULL, &report);
  memset(&r, 0, sizeof r); r.type = FM1_REC_HEAD; r.u.head.major = 1;
  r.u.head.kind = which == 23 ? FM1_STATE_SETTINGS : FM1_STATE_PROJECT;
  assert(fm1_state_bin_write(writer, &r));
  if (which != 23) {
    memset(&r, 0, sizeof r); r.type = FM1_REC_UNIT;
    r.role = FM1_ROLE_SOUND; strcpy(r.u.unit.id, "dx7");
    assert(fm1_state_bin_write(writer, &r));
  }
  unsigned count = which < 16 ? (which % 4 == 0 ? 32u : 1u + which) : 2u;
  if (which == 23) {
    memset(&r, 0, sizeof r); r.type = FM1_REC_SETTING;
    r.u.setting.key = FM1_SET_METRONOME; r.u.setting.is_bool = 1;
    assert(fm1_state_bin_write(writer, &r));
  } else for (unsigned k = 0; k < count; ++k) {
    memset(&r, 0, sizeof r); r.type = FM1_REC_DX7;
    r.slot = (uint8_t)((k + which) % FM1_DX7_USER_SLOTS);
    memset(r.u.dx7.vced + 145, 'A' + k % 26, 10);
    r.u.dx7.vced[0] = (uint8_t)k;
    memcpy(expected[r.slot], r.u.dx7.vced, FM1_DX7_VCED_BYTES);
    if (k == 1 && which == 16) r.u.dx7.vced[11] = 4;
    if (k == 1 && which == 17) r.u.dx7.vced[134] = 32;
    if (k == 1 && which == 18) r.u.dx7.vced[145] = 31;
    if (k == 1 && which == 19) r.slot = (uint8_t)which;
    assert(fm1_state_bin_write(writer, &r));
  }
  memset(&r, 0, sizeof r); r.type = FM1_REC_END;
  assert(fm1_state_bin_write(writer, &r)); free(memory);
  fm1_app_init(&managed, 44118.0f);
  assert(managed.dx7.index >= 0);
  assert(fm1_app_set_storage(&managed, NULL, allocate, deallocate) == 0);
  if (which < 16 && !(which & 1))
    assert(fm1_app_select(&managed, unit, managed.dx7.index) == 0);
  if (which == 20) managed.dx7.index = -1;
  if (which == 24) managed.frames = 1;
  fm1_app_t *before = malloc(sizeof managed); assert(before);
  memcpy(before, &managed, sizeof managed);
  const uint8_t *input = scalar_bytes; uint32_t size = scalar_size;
  lunar_project_dx7_scratch_t *workspace = &scratch;
  fm1_state_report_t *output = &report;
  if (which == 21) scalar_bytes[scalar_size - 1] ^= 0x80;
  if (which == 22) --size;
  if (which == 25) workspace = NULL;
  if (which == 26) workspace = (lunar_project_dx7_scratch_t *)&managed;
  if (which == 27) workspace = (lunar_project_dx7_scratch_t *)scalar_bytes;
  if (which == 28) output = (fm1_state_report_t *)&scratch;
  int accepted = lunar_project_restore_dx7(which == 29 ? NULL : &managed,
                                          input, size, workspace, output);
  if (which < 16) {
    assert(accepted);
    for (unsigned k = 0; k < count; ++k) {
      unsigned slot = (k + which) % FM1_DX7_USER_SLOTS;
      assert(managed.dx7.loaded[slot]);
      assert(!memcmp(managed.dx7.voice[slot], expected[slot], FM1_DX7_VCED_BYTES));
    }
    assert(managed.frames == 0);
    if (which & 1) assert(fm1_app_select(&managed, unit, managed.dx7.index) == 0);
    for (unsigned k = 0; k < count; ++k) {
      unsigned slot = (k + which) % FM1_DX7_USER_SLOTS;
      uint8_t actual[FM1_DX7_VCED_BYTES];
      assert(fm1_dx7_get_user_voice(managed.unit[unit].self, slot, actual));
      assert(!memcmp(actual, expected[slot], sizeof actual));
    }
    assert(fm1_app_select(&managed, unit, -1) == 0);
    assert(fm1_app_set_storage(&managed, NULL, NULL, NULL) == 0);
  } else {
    assert(!accepted);
    assert(!memcmp(before, &managed, sizeof managed));
  }
  free(before);
}
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

static void project_boot_check(int which) {
  lunar_instance_pool_t pool;
  fm1_state_report_t report;
  fm1_rec_t r = {0};
  const uint8_t version[3] = {0, 1, 0};
  void *writer_mem = calloc(1, fm1_state_bin_writer_size());
  assert(writer_mem);
  fm1_app_init(&managed, 44118.0f);
  assert(lunar_instance_pool_init(&pool, arena.data, sizeof arena.data) == 0);
  assert(fm1_app_set_storage(&managed, &pool, pool_allocate, pool_deallocate) == 0);
  scalar_size = 0;
  fm1_state_report_init(&report);
  fm1_state_writer_t *writer = fm1_state_bin_writer(writer_mem, 0,
      FM1_STATE_WRITER_DESKTOP, version, scalar_put, NULL, &report);
  assert(writer);
  r.type = FM1_REC_HEAD; r.u.head.kind = FM1_STATE_PROJECT; r.u.head.major = 1;
  assert(fm1_state_bin_write(writer, &r));
  memset(&r, 0, sizeof r); r.type = FM1_REC_UNIT; r.role = FM1_ROLE_SOUND;
  strcpy(r.u.unit.id, "trio");
  assert(fm1_state_bin_write(writer, &r));
  memset(&r, 0, sizeof r); r.type = FM1_REC_MOD;
  assert(fm1_state_bin_write(writer, &r));
  r.type = FM1_REC_SEED; r.u.seed = 0xabc000u + (uint32_t)which;
  assert(fm1_state_bin_write(writer, &r));
  memset(&r, 0, sizeof r); r.type = FM1_REC_MODULE; r.role = FM1_ROLE_MODULE;
  strcpy(r.u.unit.id, which & 1 ? "env" : "lfo");
  assert(fm1_state_bin_write(writer, &r));
  memset(&r, 0, sizeof r); r.type = FM1_REC_VIEW;
  r.u.view.mode = (uint8_t)(which % FM1_VIEW_MODES);
  assert(fm1_state_bin_write(writer, &r));
  memset(&r, 0, sizeof r); r.type = FM1_REC_END;
  assert(fm1_state_bin_write(writer, &r));
  free(writer_mem);
  void *held = NULL;
  if (which >= 18) {
    unsigned negative = (unsigned)(which - 18) % 6;
    if (negative == 0) managed.frames = 1;
    if (negative == 1) scalar_bytes[scalar_size - 1] ^= 1;
    if (negative == 2) --scalar_size;
    if (negative == 4) { held = lunar_instance_pool_alloc(&pool, 64); assert(held); }
    fm1_app_t *before = malloc(sizeof managed); assert(before);
    memcpy(before, &managed, sizeof managed);
    assert(!lunar_project_start(&managed, &pool, scalar_bytes, (uint32_t)scalar_size,
        negative == 5 ? 48000 : 44118,
        negative == 3 ? (fm1_state_report_t *)&managed : &report));
    assert(!memcmp(before, &managed, sizeof managed));
    free(before);
    if (held) assert(!lunar_instance_pool_free(&pool, held));
    assert(!pool.live_allocations && !pool.live_bytes);
    return;
  }
  int ok = lunar_project_start(&managed, &pool, scalar_bytes, (uint32_t)scalar_size,
                               44118, &report);
  if (!ok) fprintf(stderr, "project boot %u: %s\n", report.code, report.what);
  assert(ok && report.code == FM1_STATE_OK);
  assert(managed.unit[0].e && !strcmp(managed.unit[0].e->id, "trio"));
  assert(pool.live_allocations == 1); /* No retained staging or candidate MIDI allocations. */
  assert(managed.mod_seed == 0xabc000u + (uint32_t)which);
  const int modes[FM1_VIEW_MODES] = {FM1_MODE_HOME, FM1_MODE_FX, FM1_MODE_GLOBAL,
      FM1_MODE_SEQ, FM1_MODE_SEQ, FM1_MODE_SEQ, FM1_MODE_RACK,
      FM1_MODE_MATRIX, FM1_MODE_CHAIN};
  assert(managed.mode == modes[which % FM1_VIEW_MODES]);
  if (which % FM1_VIEW_MODES == FM1_VIEW_SESSION)
    assert(managed.ui.view == FM1_SEQ_VIEW_SESSION);
  if (which % FM1_VIEW_MODES == FM1_VIEW_SONG)
    assert(managed.ui.view == FM1_SEQ_VIEW_SONG);
  fm1_app_note_on(&managed, 60 + which % 12, 100);
  double energy = 0;
  for (int block = 0; block < 8; ++block) {
    const float *audio = fm1_app_render(&managed, 64);
    for (int n = 0; n < 128; ++n) {
      assert(isfinite(audio[n])); energy += audio[n] * audio[n];
    }
  }
  assert(energy > 0.0001);
  fm1_app_all_notes_off(&managed);
  managed.unit[0].e->destroy(managed.unit[0].self);
  pool_deallocate(&pool, managed.unit[0].mem);
  assert(!pool.live_allocations && !pool.live_bytes);
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
#if FM1_APP_EXTERNAL_ARENAS
  if (argc == 3 && !strcmp(argv[1], "--project-boot")) {
    int which = atoi(argv[2]); assert(which >= 0 && which < 30);
    project_boot_check(which);
    printf("{\"passed\":true,\"case\":%d}\n", which);
    return 0;
  }
  if (argc == 3 && !strcmp(argv[1], "--project-mod")) {
    int which = atoi(argv[2]);
    assert(which >= 0 && which < 32);
    project_mod_check(which);
    printf("{\"passed\":true,\"case\":%d}\n", which);
    return 0;
  }
  if (argc == 3 && !strcmp(argv[1], "--mod-cold")) {
    int which = atoi(argv[2]); assert(which >= 0 && which < 30);
    mod_cold_check(which);
    printf("{\"passed\":true,\"case\":%d}\n", which);
    return 0;
  }
  if (argc == 3 && !strcmp(argv[1], "--dx7")) {
    int which = atoi(argv[2]); assert(which >= 0 && which < 30);
    dx7_check(which);
    printf("{\"passed\":true,\"case\":%d}\n", which);
    return 0;
  }
  if (argc == 3 && !strcmp(argv[1], "--scalar")) {
    int which = atoi(argv[2]); assert(which >= 0 && which < 30);
    scalar_check(which);
    printf("{\"passed\":true,\"case\":%d}\n", which);
    return 0;
  }
#endif
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
