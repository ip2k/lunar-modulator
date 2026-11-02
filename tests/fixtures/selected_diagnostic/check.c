/* Host-only proof that the target app consumes the linked fixed blob. MIT. */
#include "diagnostic_app.h"
#include "fm1_app_state.h"
#include "selected_project_blob.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static fm1_app_t oracle FM1_APP_ALIGN16;
static unsigned char oracle_sound[16384] FM1_APP_ALIGN16;
static fm1_app_arena_t oracle_arenas[FM1_APP_UNITS];
static unsigned char oracle_space[655360] FM1_APP_ALIGN16;

static uint32_t read_blob(void *ctx, uint32_t off, uint8_t *dest, uint32_t count) {
  (void)ctx;
  if (off >= lunar_selected_project_blob_bytes) return 0;
  if (count > lunar_selected_project_blob_bytes - off)
    count = lunar_selected_project_blob_bytes - off;
  memcpy(dest, lunar_selected_project_blob + off, count);
  return count;
}

int main(void) {
  int32_t pcm[128], silence[128];
  fm1_app_load_opts_t opts;
  fm1_app_state_report_t result;
  fm1_app_state_workspace_t work = {oracle_space, sizeof oracle_space};
  const fm1_app_t *selected;
  assert(lunar_selected_project_blob_bytes == 597u);
  assert(!lunar_diagnostic_init());
  assert(lunar_diagnostic_init() == -1); /* one shot */
  selected = lunar_diagnostic_state();
  assert(selected->unit[0].e && strcmp(selected->unit[0].e->id, "trio") == 0);
  assert(selected->unit[0].e->n_params == 14 && selected->unit[0].bytes == 4240u);
  for (int u = 1; u < FM1_APP_UNITS; ++u) assert(!selected->unit[u].e);
  oracle_arenas[0].mem = oracle_sound;
  oracle_arenas[0].bytes = sizeof oracle_sound;
  assert(!fm1_app_init_arenas(&oracle, LUNAR_DIAGNOSTIC_RATE, oracle_arenas));
  fm1_app_load_opts_init(&opts);
  opts.kind = FM1_STATE_PROJECT;
  opts.flags = FM1_APP_LOAD_QUIET;
  assert(fm1_app_state_load_with_workspace(&oracle, read_blob, NULL,
      lunar_selected_project_blob_bytes, &opts, &work, &result));
  assert(result.r.code == FM1_STATE_OK);
  for (int p = 0; p < 14; ++p)
    assert(fm1_app_get_param(selected, 0, p) == fm1_app_get_param(&oracle, 0, p));
  assert(selected->level[0] == oracle.level[0]);
  assert(!memcmp(&selected->info, &oracle.info, sizeof selected->info));
  lunar_diagnostic_note(60, 100, 1);
  fm1_app_note_on(&oracle, 60, 100);
  assert(!lunar_diagnostic_render(pcm, 64));
  const float *reference = fm1_app_render(&oracle, 64);
  int nonzero = 0;
  for (int i = 0; i < 128; ++i) {
    float v = reference[i];
    assert(isfinite(v));
    int32_t expected = v >= 1.0f ? 32767 : v <= -1.0f ? -32767 : (int32_t)(v * 32767.0f);
    assert(pcm[i] == expected);
    nonzero |= pcm[i] != 0;
  }
  assert(nonzero);
  assert(lunar_diagnostic_render(pcm, 65) == -1);
  assert(lunar_diagnostic_status() == 4);
  memset(silence, 0x55, sizeof silence);
  assert(lunar_diagnostic_render(silence, 64) == -1);
  for (int i = 0; i < 128; ++i) assert(silence[i] == 0);
  assert(lunar_diagnostic_init() == -1);
  puts("selected diagnostic startup, blob, 14 params, 64-frame PCM and sticky fault passed");
  return 0;
}
