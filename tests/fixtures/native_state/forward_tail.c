/* Shared reader forward-compatibility reporting probe. MIT. Test-only I/O. */
#include "fm1_state.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t input[FM1_STATE_BIN_MAX];
static char text[262144];
static size_t used;
static uint32_t total;
static uint32_t read_at(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
  (void)ctx;
  if (off > total || n > total - off) return 0;
  memcpy(out, input + off, n); return n;
}
static void put(void *ctx, const char *bytes, size_t n) {
  (void)ctx; assert(n <= sizeof(text) - used);
  memcpy(text + used, bytes, n); used += n;
}
int main(int argc, char **argv) {
  fm1_state_report_t report;
  fm1_state_printer_t printer;
  int ok;
  FILE *f;
  assert(argc == 2); f = fopen(argv[1], "rb"); assert(f);
  total = (uint32_t)fread(input, 1, sizeof(input), f);
  assert(!ferror(f) && feof(f)); fclose(f);
  fm1_state_report_init(&report);
  fm1_state_printer_init(&printer, put, NULL);
  ok = fm1_state_bin_read(read_at, NULL, total, fm1_state_print, &printer, &report, 0);
  if (ok) assert(fwrite(text, 1, used, stdout) == used);
  const fm1_state_report_t *r = &report;
  fprintf(stderr, "{\"code\":\"%s\",\"what\":\"%s\",\"path\":\"%s\",\"name\":\"%s\","
    "\"known\":\"%s\",\"first_skip\":\"%s\",\"skipped\":%u,\"repaired\":%u,"
    "\"defaulted\":%u,\"unknown\":%u}\n", fm1_state_code_name(r->code), r->what, r->path,
    r->name, r->known, r->first_skip, r->skipped, r->repaired, r->defaulted, r->unknown);
  return ok ? 0 : 1;
}
