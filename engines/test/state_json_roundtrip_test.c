/* Bounded JSON contract probe; no engine registry, DSP or device. MIT. */
#include "fm1_state.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  uint8_t bytes[FM1_STATE_CAP_PROJECT + 1u];
  size_t n;
} bytes_t;
typedef struct { unsigned units, ends; } counts_t;
static bytes_t input, first, second;

static void put(void *ctx, const char *data, size_t n) {
  bytes_t *b = (bytes_t *)ctx;
  if (n > sizeof b->bytes - b->n) abort();
  memcpy(b->bytes + b->n, data, n);
  b->n += n;
}
static int count(void *ctx, const fm1_rec_t *r) {
  counts_t *c = (counts_t *)ctx;
  if (r->type == FM1_REC_UNIT) ++c->units;
  if (r->type == FM1_REC_END) ++c->ends;
  return 1;
}
static int read_json(const bytes_t *b, size_t piece, int maps_only,
                     fm1_rec_sink_t sink, void *ctx, fm1_state_report_t *rep) {
  fm1_state_json_reader_t r;
  fm1_state_json_begin(&r, NULL, sink, ctx, rep);
  r.maps_only = (uint8_t)maps_only;
  for (size_t at = 0; at < b->n;) {
    const size_t n = b->n - at < piece ? b->n - at : piece;
    if (!fm1_state_json_feed(&r, b->bytes + at, n)) return 0;
    at += n;
  }
  return fm1_state_json_end(&r);
}
static void report(int rd, int wr, int stable, const counts_t *c,
                    const fm1_state_report_t *r) {
  fprintf(stderr, "{\"read_ok\":%d,\"write_ok\":%d,\"stable\":%d,"
          "\"units\":%u,\"ends\":%u,\"code\":\"%s\"}\n",
          rd, wr, stable, c->units, c->ends, fm1_state_code_name(r->code));
}
int main(int argc, char **argv) {
  const int fresh = argc > 1 && !strcmp(argv[1], "fresh");
  const int maps = argc > 1 && !strcmp(argv[1], "maps");
  const size_t piece = argc > 2 ? (size_t)strtoul(argv[2], NULL, 10) : 256u;
  counts_t counts = {0, 0};
  fm1_state_report_t rep, writing;
  void *memory;
  fm1_state_writer_t *w;
  int rd, wr, stable;
  if (!piece) return 4;
  memory = malloc(fm1_state_json_writer_size());
  if (!memory) return 4;
  fm1_state_report_init(&rep);
  fm1_state_report_init(&writing);
  if (fresh) {
    fm1_rec_t r;
    memset(&r, 0, sizeof r);
    r.type = FM1_REC_HEAD;
    r.u.head.kind = FM1_STATE_PROJECT;
    w = fm1_state_json_writer(memory, NULL, 0, put, &first, &writing);
    wr = fm1_state_write(w, &r);
    r.type = FM1_REC_END;
    wr = wr && fm1_state_write(w, &r);
    report(-1, wr, 0, &counts, &writing);
    free(memory);
    return wr ? 0 : 1;
  }
  input.n = fread(input.bytes, 1, sizeof input.bytes, stdin);
  if (ferror(stdin)) { free(memory); return 4; }
  rd = read_json(&input, piece, maps, count, &counts, &rep);
  if (!rd || maps) {
    report(rd, -1, 0, &counts, &rep);
    free(memory);
    return rd ? 0 : 1;
  }
  /* First prove reader acceptance independently of a writer sink. */
  w = fm1_state_json_writer(memory, NULL, 0, put, &first, &writing);
  fm1_state_report_init(&rep);
  wr = read_json(&input, piece, 0, fm1_state_write, w, &rep);
  if (!wr) {
    report(rd, wr, 0, &counts, &writing);
    free(memory);
    return 2;
  }
  fm1_state_report_init(&writing);
  fm1_state_report_init(&rep);
  w = fm1_state_json_writer(memory, NULL, 0, put, &second, &writing);
  stable = read_json(&first, piece, 0, fm1_state_write, w, &rep) &&
           first.n == second.n && !memcmp(first.bytes, second.bytes, first.n);
  report(rd, wr, stable, &counts, &rep);
  if (stable) fwrite(first.bytes, 1, first.n, stdout);
  free(memory);
  return stable ? 0 : 3;
}
