/* Offline current-app oracle for the selected native PROJECT adapter. MIT. */
#include "selected_project.h"
#include "fm1_app_state.h"
#include "selected_project_blob.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static fm1_app_t selected_app, oracle_app, before_app;
static unsigned char selected_arena[FM1_APP_SOUND_BYTES] FM1_APP_ALIGN16;
static unsigned char oracle_arena[FM1_APP_SOUND_BYTES] FM1_APP_ALIGN16;
static fm1_app_arena_t selected_arenas[FM1_APP_UNITS], oracle_arenas[FM1_APP_UNITS];
static unsigned char reader_space[16384] FM1_APP_ALIGN16;
static unsigned char oracle_space[655360] FM1_APP_ALIGN16;
static unsigned char packed[FM1_STATE_BIN_MAX], damaged[FM1_STATE_BIN_MAX];

static size_t load_file(const char *name, unsigned char *out) {
  FILE *file = fopen(name, "rb");
  long end;
  assert(file);
  assert(fseek(file, 0, SEEK_END) == 0);
  end = ftell(file);
  assert(end > 0 && end <= FM1_STATE_BIN_MAX);
  assert(fseek(file, 0, SEEK_SET) == 0);
  assert(fread(out, 1, (size_t)end, file) == (size_t)end);
  assert(fclose(file) == 0);
  return (size_t)end;
}

static uint32_t read_bytes(void *ctx, uint32_t off, uint8_t *dest, uint32_t count) {
  const fm1_app_state_mem_t *m = (const fm1_app_state_mem_t *)ctx;
  if (off >= m->n) return 0;
  if (count > m->n - off) count = m->n - off;
  memcpy(dest, m->b + off, count);
  return count;
}

int main(int argc, char **argv) {
  size_t end;
  fm1_state_report_t result;
  fm1_app_state_report_t oracle_result;
  fm1_app_state_workspace_t oracle_work;
  fm1_app_state_mem_t source;
  fm1_app_load_opts_t opts;
  assert(argc >= 2);
  end = load_file(argv[1], packed);
  assert(lunar_selected_project_blob_bytes == end);
  assert(!memcmp(lunar_selected_project_blob, packed, end));
  selected_arenas[0].mem = selected_arena;
  selected_arenas[0].bytes = sizeof selected_arena;
  oracle_arenas[0].mem = oracle_arena;
  oracle_arenas[0].bytes = sizeof oracle_arena;
  assert(!fm1_app_init_arenas(&selected_app, FM1_APP_RAM_RATE, selected_arenas));
  assert(!fm1_app_init_arenas(&oracle_app, FM1_APP_RAM_RATE, oracle_arenas));
  assert(fm1_state_bin_reader_size() <= sizeof reader_space);
  assert(fm1_app_state_workspace_size(FM1_APP_STATE_WORK_LOAD) <= sizeof oracle_space);

  /* A real CRC refusal must happen before any app/arena mutation. */
  memcpy(&before_app, &selected_app, sizeof selected_app);
  memcpy(damaged, packed, end);
  damaged[end / 2u] ^= 0x01u;
  assert(!lunar_selected_project_load(&selected_app, damaged, (uint32_t)end,
      reader_space, sizeof reader_space, &result));
  assert(result.code != FM1_STATE_OK);
  assert(!memcmp(&selected_app, &before_app, sizeof selected_app));
  for (size_t i = 0; i < sizeof selected_arena; ++i) assert(selected_arena[i] == 0);
  for (int arg = 2; arg < argc; ++arg) {
    size_t n = load_file(argv[arg], damaged);
    assert(!lunar_selected_project_load(&selected_app, damaged, (uint32_t)n,
        reader_space, sizeof reader_space, &result));
    assert(result.code != FM1_STATE_OK);
    assert(!memcmp(&selected_app, &before_app, sizeof selected_app));
    for (size_t i = 0; i < sizeof selected_arena; ++i) assert(selected_arena[i] == 0);
  }

  int selected_ok = lunar_selected_project_load(&selected_app, lunar_selected_project_blob,
      lunar_selected_project_blob_bytes,
      reader_space, sizeof reader_space, &result);
  if (!selected_ok) fprintf(stderr, "selected refusal: code=%u records=%u what=%s\n",
      result.code, result.records, result.what);
  assert(selected_ok);
  assert(result.code == FM1_STATE_OK && result.records >= 30);
  assert(selected_app.unit[0].e && strcmp(selected_app.unit[0].e->id, "trio") == 0);
  assert(selected_app.unit[0].e->n_params == 14);
  for (int u = 1; u < FM1_APP_UNITS; ++u) assert(!selected_app.unit[u].e);

  source.b = packed;
  source.n = (uint32_t)end;
  oracle_work.memory = oracle_space;
  oracle_work.bytes = sizeof oracle_space;
  fm1_app_load_opts_init(&opts);
  opts.kind = FM1_STATE_PROJECT;
  opts.flags = FM1_APP_LOAD_QUIET;
  assert(fm1_app_state_load_with_workspace(&oracle_app, read_bytes, &source,
      (uint32_t)end, &opts, &oracle_work, &oracle_result));
  assert(oracle_result.r.code == FM1_STATE_OK);
  assert(oracle_app.unit[0].e && strcmp(oracle_app.unit[0].e->id, "trio") == 0);
  for (unsigned i = 0; i < 14; ++i)
    assert(fm1_app_get_param(&selected_app, 0, (int)i) ==
           fm1_app_get_param(&oracle_app, 0, (int)i));
  assert(selected_app.level[0] == oracle_app.level[0]);
  assert(!memcmp(&selected_app.info, &oracle_app.info, sizeof selected_app.info));
  assert(fm1_app_ram(&selected_app) <= FM1_APP_RAM_BUDGET);
  fm1_app_note_on(&selected_app, 60, 100);
  fm1_app_note_on(&oracle_app, 60, 100);
  const float *chosen = fm1_app_render(&selected_app, 64);
  const float *reference = fm1_app_render(&oracle_app, 64);
  assert(chosen && reference && !memcmp(chosen, reference, 128 * sizeof(float)));
  printf("selected Trio proof passed: 14 params, %zu engine bytes, %zu RAM bytes\n",
         selected_app.unit[0].bytes, fm1_app_ram(&selected_app));
  return 0;
}
