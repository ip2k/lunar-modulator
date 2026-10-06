/* state_alias_test.c -- fm1-state-alias-test: the state readers' old names
 * (fm1_known.h's aliases, ST4) with a table of the test's own, since the
 * build's is empty until something is renamed. It reads a JSON state file
 * (argv[1], or stdin) against the build's registries plus these aliases and
 * prints its records as fm1-state records does; tests/test_state_whole.py
 * holds them to P1's, given the same aliases. The aliases:
 *   shapes  "Old Timbre"  -> Timbre        filter  Type "Moogish" -> entry 1
 *   lfo     "Speed"       -> Rate          lfo     Shape "Tri"    -> entry 1
 * MIT licence. */
#include "fm1_state.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint16_t uid_of(const fm1_param_t *p, unsigned n, const char *name) {
  unsigned i;
  for (i = 0; i < n; ++i) {
    if (strcmp(p[i].name, name) == 0) return p[i].uid;
  }
  fprintf(stderr, "no parameter %s\n", name);
  exit(2);
}

static void put(void *ctx, const char *s, size_t n) {
  (void)ctx;
  fwrite(s, 1, n, stdout);
}

typedef struct {
  const uint8_t *b;
  size_t n;
} src_t;

static uint32_t rd(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
  const src_t *s = (const src_t *)ctx;
  if (off >= s->n) return 0;
  if (n > s->n - off) n = (uint32_t)(s->n - off);
  memcpy(out, s->b + off, n);
  return n;
}

int main(int argc, char **argv) {
  static uint8_t buf[1u << 20];
  static fm1_alias_t aliases[5];
  fm1_state_names_t nm;
  fm1_state_report_t rep;
  fm1_state_printer_t pr;
  const fm1_engine_t *shapes, *filter;
  const fm1_mod_kind_t *lfo;
  FILE *f = argc > 1 ? fopen(argv[1], "rb") : stdin;
  src_t src;
  if (!f) return 2;
  src.b = buf;
  src.n = fread(buf, 1, sizeof(buf), f);
  if (f != stdin) fclose(f);
  fm1_state_names_default(&nm);
  shapes = fm1_state_engine(&nm, FM1_ROLE_SOUND, "shapes");
  filter = fm1_state_engine(&nm, FM1_ROLE_INSERT, "filter");
  lfo = fm1_state_kind(&nm, "lfo");
  if (!shapes || !filter || !lfo) return 2;
  aliases[0].owner = FM1_ALIAS_ENGINE; aliases[0].id = "shapes"; aliases[0].entry = -1;
  aliases[0].uid = uid_of(shapes->params, shapes->n_params, "Timbre"); aliases[0].name = "Old Timbre";
  aliases[1].owner = FM1_ALIAS_ENGINE; aliases[1].id = "filter"; aliases[1].entry = 1;
  aliases[1].uid = uid_of(filter->params, filter->n_params, "Type"); aliases[1].name = "Moogish";
  aliases[2].owner = FM1_ALIAS_MOD; aliases[2].id = "lfo"; aliases[2].entry = -1;
  aliases[2].uid = uid_of(lfo->params, lfo->n_params, "Rate"); aliases[2].name = "Speed";
  aliases[3].owner = FM1_ALIAS_MOD; aliases[3].id = "lfo"; aliases[3].entry = 1;
  aliases[3].uid = uid_of(lfo->params, lfo->n_params, "Shape"); aliases[3].name = "Tri";
  nm.aliases = aliases;
  nm.n_aliases = 4;
  fm1_state_report_init(&rep);
  fm1_state_printer_init(&pr, put, NULL);
  if (!fm1_state_json_read(&nm, rd, &src, fm1_state_print, &pr, &rep)) {
    fprintf(stderr, "%s: %s %s\n", fm1_state_code_name(rep.code), rep.what, rep.path);
    return 1;
  }
  fprintf(stderr, "skipped %u\n", rep.skipped);
  return 0;
}
