/* Shared reader forward-compatibility reporting probe. MIT. Test-only I/O. */
#include "fm1_state.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t input[FM1_STATE_BIN_MAX];
static _Alignas(16) uint8_t workspace[16384];
static char text[2][262144];
static size_t used[2];
static unsigned arm;
static uint32_t total;
static uint32_t read_at(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
  (void)ctx;
  if (off > total || n > total - off) return 0;
  memcpy(out, input + off, n); return n;
}
static void put(void *ctx, const char *bytes, size_t n) {
  (void)ctx; assert(n <= sizeof(text[arm]) - used[arm]);
  memcpy(text[arm] + used[arm], bytes, n); used[arm] += n;
}
int main(int argc, char **argv) {
  fm1_state_report_t reports[2];
  fm1_state_printer_t printer;
  int ok[2];
  FILE *f;
  assert(argc == 2); f = fopen(argv[1], "rb"); assert(f);
  total = (uint32_t)fread(input, 1, sizeof(input), f);
  assert(!ferror(f) && feof(f)); fclose(f);
  for (arm = 0; arm < 2; ++arm) {
    fm1_state_report_init(&reports[arm]);
    fm1_state_printer_init(&printer, put, NULL);
    ok[arm] = arm ? fm1_state_bin_read_workspace(workspace, sizeof(workspace), read_at, NULL,
      total, fm1_state_print, &printer, &reports[arm], 0) :
      fm1_state_bin_read(read_at, NULL, total, fm1_state_print, &printer, &reports[arm], 0);
  }
  assert(ok[0] == ok[1] && !memcmp(&reports[0], &reports[1], sizeof(reports[0])));
  assert(used[0] == used[1] && !memcmp(text[0], text[1], used[0]));
  if (ok[0]) assert(fwrite(text[0], 1, used[0], stdout) == used[0]);
  const fm1_state_report_t *r = &reports[0];
  fprintf(stderr, "{\"code\":\"%s\",\"what\":\"%s\",\"path\":\"%s\",\"name\":\"%s\","
    "\"known\":\"%s\",\"first_skip\":\"%s\",\"skipped\":%u,\"repaired\":%u,"
    "\"defaulted\":%u,\"unknown\":%u}\n", fm1_state_code_name(r->code), r->what, r->path,
    r->name, r->known, r->first_skip, r->skipped, r->repaired, r->defaulted, r->unknown);
  return ok[0] ? 0 : 1;
}
