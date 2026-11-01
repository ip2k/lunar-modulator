/* State workspace ownership/equivalence regression. Host-only, MIT. */
#include "fm1_app_state.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#ifndef FM1_WORKSPACE_BASELINE
#define FM1_WORKSPACE_BASELINE 0
#endif
static fm1_app_t app, loaded, before;
static unsigned char scratch[1024 * 1024 + 32] FM1_APP_ALIGN16;
typedef struct output { unsigned char b[262144]; size_t n; unsigned calls; int nested; } output_t;
static output_t saved, other, packed;
static uint32_t digest = 2166136261u;
static void hash(const void *p, size_t n) {
  const unsigned char *b = p;
  while (n--) digest = (digest ^ *b++) * 16777619u;
}
#if !FM1_WORKSPACE_BASELINE
static fm1_app_state_workspace_t workspace(unsigned op) {
  fm1_app_state_workspace_t w = {scratch + 16, fm1_app_state_workspace_size(op)};
  assert(w.bytes && w.bytes <= sizeof scratch - 32);
  memset(scratch, 0x5a, sizeof scratch);
  return w;
}
static void canaries(const fm1_app_state_workspace_t *w) {
  for (unsigned i = 0; i < 16; ++i) {
    assert(scratch[i] == 0x5a);
    assert(scratch[16 + w->bytes + i] == 0x5a);
  }
}
#endif
static void put(void *ctx, const char *s, size_t n) {
  output_t *o = ctx;
  assert(n <= sizeof o->b - o->n);
  memcpy(o->b + o->n, s, n); o->n += n; ++o->calls;
#if !FM1_WORKSPACE_BASELINE
  if (o->nested) {
    fm1_state_report_t r;
    fm1_app_state_report_t lr;
    fm1_app_state_workspace_t w = {scratch + 16, sizeof scratch - 32};
    fm1_app_state_mem_t m = {(const uint8_t *)"{}", 2};
    size_t old_n = other.n;
    assert(!fm1_app_state_save_with_workspace(&app, FM1_STATE_PROJECT, 0, 0, put, &other, &w, &r));
    assert(!fm1_app_state_pack_with_workspace(fm1_app_state_mem_read, &m, put, &other, &w, &r));
    assert(!fm1_app_state_check_with_workspace(&app, fm1_app_state_mem_read, &m, 2, NULL, &w, &lr));
    assert(!fm1_app_state_load_with_workspace(&app, fm1_app_state_mem_read, &m, 2, NULL, &w, &lr));
    assert(!fm1_app_midi_map_set(&app, m.b, m.n, &r));
    assert(other.n == old_n && !memcmp(&app, &before, sizeof app));
  }
#endif
}
static void setup(fm1_app_t *a) {
  fm1_app_init(a, 44118);
  assert(!fm1_app_select(a, 0, fm1_app_find("test-sine")));
  assert(!fm1_app_select(a, 1, fm1_app_find("test-gain")));
  assert(!fm1_app_select(a, fm1_app_insert_unit(0, 0), fm1_app_find("test-gain")));
  assert(fm1_app_seq_demo(a));
}
static int save(fm1_app_t *a, unsigned kind, int arg, int binary, output_t *o) {
  fm1_state_report_t r;
  o->n = o->calls = 0;
#if FM1_WORKSPACE_BASELINE
  return fm1_app_state_save(a, kind, arg, binary, put, o, &r);
#else
  fm1_app_state_workspace_t w = workspace(FM1_APP_STATE_WORK_SAVE);
  int ok = fm1_app_state_save_with_workspace(a, kind, arg, binary, put, o, &w, &r);
  canaries(&w);
  return ok;
#endif
}
static int check_load(fm1_app_t *a, const output_t *o, unsigned kind, int load) {
  fm1_app_state_mem_t m = {o->b, (uint32_t)o->n};
  fm1_app_state_report_t r;
  fm1_app_load_opts_t opts;
  fm1_app_load_opts_init(&opts); opts.kind = kind; opts.flags = FM1_APP_LOAD_QUIET | FM1_APP_LOAD_REPLACE;
#if FM1_WORKSPACE_BASELINE
  return load ? fm1_app_state_load(a, fm1_app_state_mem_read, &m, m.n, &opts, &r) :
                fm1_app_state_check(a, fm1_app_state_mem_read, &m, m.n, &opts, &r);
#else
  fm1_app_state_workspace_t w = workspace(FM1_APP_STATE_WORK_LOAD);
  int ok = load ? fm1_app_state_load_with_workspace(a, fm1_app_state_mem_read, &m, m.n, &opts, &w, &r) :
                  fm1_app_state_check_with_workspace(a, fm1_app_state_mem_read, &m, m.n, &opts, &w, &r);
  canaries(&w);
  return ok;
#endif
}
static int pack(const output_t *in, output_t *o) {
  fm1_app_state_mem_t m = {in->b, (uint32_t)in->n};
  fm1_state_report_t r;
  o->n = o->calls = 0;
#if FM1_WORKSPACE_BASELINE
  return fm1_app_state_pack(fm1_app_state_mem_read, &m, put, o, &r);
#else
  fm1_app_state_workspace_t w = workspace(FM1_APP_STATE_WORK_PACK);
  int ok = fm1_app_state_pack_with_workspace(fm1_app_state_mem_read, &m, put, o, &w, &r);
  canaries(&w);
  return ok;
#endif
}
#if !FM1_WORKSPACE_BASELINE
static void invalid_storage(void) {
  fm1_app_state_workspace_t w = workspace(FM1_APP_STATE_WORK_SAVE), bad = w;
  fm1_state_report_t r;
  fm1_app_state_report_t lr;
  fm1_app_load_opts_t opts;
  fm1_app_state_mem_t m = {saved.b, (uint32_t)saved.n};
  memcpy(&before, &app, sizeof app); other.n = other.calls = 0;
#define REFUSE(ws) do { assert(!fm1_app_state_save_with_workspace(&app, FM1_STATE_PROJECT, 0, 0, put, &other, ws, &r)); assert(!other.calls && !memcmp(&app, &before, sizeof app)); } while (0)
  REFUSE(NULL);
  bad.memory = NULL; REFUSE(&bad);
  bad = w; --bad.bytes; REFUSE(&bad);
  bad = w; bad.memory = scratch + 17; REFUSE(&bad);
  bad = w; bad.memory = (void *)(UINTPTR_MAX & ~(uintptr_t)15); REFUSE(&bad);
  bad = w; bad.memory = &app; REFUSE(&bad);
  bad = w; bad.memory = app.unit[0].mem; REFUSE(&bad);
  /* A genuine external engine arena, independently of the app object. */
  app.unit[0].mem = w.memory; app.unit[0].cap = 16;
  memcpy(&before, &app, sizeof app); REFUSE(&w);
  app.unit[0].mem = before.unit[1].mem; /* setup below restores every pointer */
  setup(&app); memcpy(&before, &app, sizeof app);
  bad = w;
  memcpy(w.memory, &bad, sizeof bad);
  REFUSE((const fm1_app_state_workspace_t *)w.memory);
  memset(w.memory, 0x5a, sizeof r);
  assert(!fm1_app_state_save_with_workspace(&app, FM1_STATE_PROJECT, 0, 0, put, &other, &w, w.memory));
  for (size_t i = 0; i < sizeof r; ++i) assert(((unsigned char *)w.memory)[i] == 0x5a);
  fm1_app_load_opts_init(&opts);
  assert(!fm1_app_state_check_with_workspace(&app, fm1_app_state_mem_read, &m, m.n, w.memory, &w, &lr));
  assert(!fm1_app_state_load_with_workspace(&app, fm1_app_state_mem_read, &m, m.n, &opts, &w, w.memory));
  {
    fm1_app_state_workspace_t tail = {scratch + 1024, fm1_app_state_workspace_size(FM1_APP_STATE_WORK_LOAD)};
    fm1_app_state_report_t *over = (fm1_app_state_report_t *)(scratch + 1024 - sizeof(fm1_state_report_t) - 16);
    unsigned char copy[sizeof *over];
    memset(over, 0x6b, sizeof *over); memcpy(copy, over, sizeof copy);
    assert(!fm1_app_state_check_with_workspace(&app, fm1_app_state_mem_read, &m, m.n, &opts, &tail, over));
    assert(!memcmp(over, copy, sizeof copy));
  }
  m.b = w.memory;
  assert(!fm1_app_state_pack_with_workspace(fm1_app_state_mem_read, &m, put, &other, &w, &r));
  m.b = saved.b;
  memcpy(w.memory, &m, sizeof m);
  assert(!fm1_app_state_pack_with_workspace(fm1_app_state_mem_read, w.memory, put, &other, &w, &r));
  assert(!other.calls && !memcmp(&app, &before, sizeof app));
  canaries(&w);
#undef REFUSE
  /* Legacy host wrappers are preserved; external builds fail closed. */
#if FM1_APP_STATE_EXTERNAL_WORKSPACE
  assert(!fm1_app_state_save(&app, FM1_STATE_PROJECT, 0, 0, put, &other, &r));
  assert(!fm1_app_state_pack(fm1_app_state_mem_read, &m, put, &other, &r));
  assert(!fm1_app_state_check(&app, fm1_app_state_mem_read, &m, m.n, &opts, &lr));
  assert(!fm1_app_state_load(&app, fm1_app_state_mem_read, &m, m.n, &opts, &lr));
  assert(!other.calls && !memcmp(&app, &before, sizeof app));
#else
  assert(fm1_app_state_save(&app, FM1_STATE_PROJECT, 0, 0, put, &other, &r));
  assert(save(&app, FM1_STATE_PROJECT, 0, 0, &saved));
  assert(saved.n == other.n && !memcmp(saved.b, other.b, saved.n));
#endif
  memcpy(&before, &app, sizeof app); saved.nested = 1;
  assert(save(&app, FM1_STATE_PROJECT, 0, 1, &saved));
  saved.nested = 0;
  assert(!memcmp(&app, &before, sizeof app));
  /* A refused codec operation must release ownership for the next operation. */
  assert(!save(&app, 255, 0, 0, &saved) && !saved.calls);
  saved.b[0] = '{'; saved.b[1] = '!'; saved.n = 2;
  assert(!pack(&saved, &packed) && !packed.calls);
  assert(!check_load(&app, &saved, 0, 1));
  assert(!memcmp(&app, &before, sizeof app));
  assert(save(&app, FM1_STATE_PROJECT, 0, 0, &saved));
}
#endif
int main(void) {
  static const unsigned kinds[] = {FM1_STATE_PROJECT, FM1_STATE_SOUND, FM1_STATE_FX,
    FM1_STATE_MODS, FM1_STATE_CLIP, FM1_STATE_SET, FM1_STATE_SETTINGS};
  setup(&app);
  for (unsigned k = 0; k < sizeof kinds / sizeof *kinds; ++k) {
    int arg = kinds[k] == FM1_STATE_FX ? -1 : 0;
    for (int binary = 0; binary < 4; ++binary) {
      assert(save(&app, kinds[k], arg, binary, &saved));
      assert(saved.n && saved.calls == 1); hash(saved.b, saved.n);
      /* Raw movy text is a separate set import path; binary SET is checked here. */
      if (kinds[k] != FM1_STATE_SET || binary) {
        setup(&loaded);
        assert(check_load(&loaded, &saved, kinds[k], 0));
        assert(check_load(&loaded, &saved, kinds[k], 1));
        assert(save(&loaded, FM1_STATE_PROJECT, 0, 0, &other)); hash(other.b, other.n);
      }
      if (!binary && kinds[k] != FM1_STATE_SET) {
        assert(pack(&saved, &packed)); hash(packed.b, packed.n);
      }
    }
  }
  setup(&app);
  assert(save(&app, FM1_STATE_PROJECT, 0, 1, &saved));
  setup(&loaded); assert(check_load(&loaded, &saved, FM1_STATE_PROJECT, 1));
  fm1_app_unit_note_on(&app, 0, 60, 100); fm1_app_unit_note_on(&loaded, 0, 60, 100);
  for (unsigned b = 0; b < 32; ++b) {
    const float *a = fm1_app_render(&app, 64), *c = fm1_app_render(&loaded, 64);
    assert(!memcmp(a, c, 128 * sizeof(float)));
    for (unsigned i = 0; i < 128; ++i) assert(isfinite(a[i]));
    hash(a, 128 * sizeof(float));
  }
#if !FM1_WORKSPACE_BASELINE
  assert(fm1_app_state_workspace_size(0) == 0);
  assert(fm1_app_state_workspace_size(FM1_APP_STATE_WORK_SAVE) == 917536);
  assert(fm1_app_state_workspace_size(FM1_APP_STATE_WORK_PACK) == 851984);
  assert(fm1_app_state_workspace_size(FM1_APP_STATE_WORK_LOAD) == 557072);
  invalid_storage();
#endif
  printf("state-workspace %08x\n", digest);
  return 0;
}
