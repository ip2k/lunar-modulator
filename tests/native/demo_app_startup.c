/* SPDX-License-Identifier: MIT */
/* Host-native cold-start admission of packed demo projects. */
#define _POSIX_C_SOURCE 200112L
#include "fm1_app.h"
#include "project_boot.h"
#include "instance_pool.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define INSTANCE_BYTES 192000u /* app_probe.c default; not a target-RAM proof */
static fm1_app_t app;
static lunar_instance_pool_t pool;
static unsigned char instance_memory[INSTANCE_BYTES] FM1_APP_ALIGN16;
static size_t peak_live_bytes;
static unsigned peak_live_allocations;
static size_t allocation_attempts, allocation_failures, largest_request;
extern void *__real_lunar_instance_pool_alloc(lunar_instance_pool_t *, size_t);
void *__wrap_lunar_instance_pool_alloc(lunar_instance_pool_t *p, size_t n) {
  ++allocation_attempts;
  if (n > largest_request) largest_request = n;
  void *result = __real_lunar_instance_pool_alloc(p, n);
  if (!result) ++allocation_failures;
  if (result && p->live_bytes > peak_live_bytes) peak_live_bytes = p->live_bytes;
  if (result && p->live_allocations > peak_live_allocations)
    peak_live_allocations = p->live_allocations;
  return result;
}
static void *pool_allocate(void *ctx, size_t bytes) {
  return lunar_instance_pool_alloc((lunar_instance_pool_t *)ctx, bytes);
}
static void pool_deallocate(void *ctx, void *memory) {
  (void)lunar_instance_pool_free((lunar_instance_pool_t *)ctx, memory);
}
static unsigned read_file(const char *path, uint8_t **out) {
  FILE *f = fopen(path, "rb");
  long n;
  uint8_t *p;
  if (!f || fseek(f, 0, SEEK_END) || (n = ftell(f)) <= 0 ||
      fseek(f, 0, SEEK_SET)) { if (f) fclose(f); return 0; }
  p = (uint8_t *)malloc((size_t)n);
  if (!p || fread(p, 1, (size_t)n, f) != (size_t)n) {
    free(p); fclose(f); return 0;
  }
  fclose(f); *out = p; return (unsigned)n;
}
int main(int argc, char **argv) {
  uint8_t *bytes = NULL;
  unsigned size;
  fm1_state_report_t report;
  size_t seq_size;
  unsigned active_units = 0;
  int ok;
  if (argc != 2 || !(size = read_file(argv[1], &bytes))) {
    fprintf(stderr, "expected one readable packed project path\n"); return 2;
  }
  fm1_app_init(&app, 44118.0f);
  seq_size = fm1_seq_size(&app.seq_lim);
  if (seq_size > FM1_APP_SEQ_BYTES || !app.seq ||
      lunar_instance_pool_init(&pool, instance_memory, sizeof instance_memory) ||
      fm1_app_set_storage(&app, &pool, pool_allocate, pool_deallocate)) {
    fprintf(stderr, "app/8-track sequencer/pool initialization failed\n");
    free(bytes); return 3;
  }
  fm1_state_report_init(&report);
  ok = lunar_project_start(&app, &pool, bytes, size, 44118, &report);
  for (unsigned i = 0; i < FM1_APP_UNITS; ++i)
    if (app.unit[i].e) ++active_units;
  printf("{\"passed\":%s,\"report_code\":%u,\"report_what\":\"%s\","
         "\"seq_tracks\":%u,\"seq_bytes\":%zu,\"seq_capacity\":%u,"
         "\"pool_capacity\":%u,\"pool_peak_live_bytes\":%zu,"
         "\"pool_peak_live_allocations\":%u,\"pool_live_bytes\":%zu,"
         "\"pool_live_allocations\":%u,\"allocation_attempts\":%zu,"
         "\"allocation_failures\":%zu,\"largest_allocation_request\":%zu,"
         "\"active_units\":%u,"
         "\"modulation_active\":%s}\n",
         ok ? "true" : "false", (unsigned)report.code, report.what,
         (unsigned)app.seq_lim.tracks, seq_size, FM1_APP_SEQ_BYTES,
         INSTANCE_BYTES, peak_live_bytes, peak_live_allocations,
         pool.live_bytes, pool.live_allocations, allocation_attempts,
         allocation_failures, largest_request, active_units,
         app.mod ? "true" : "false");
  free(bytes);
  return ok && report.code == FM1_STATE_OK ? 0 : 1;
}
