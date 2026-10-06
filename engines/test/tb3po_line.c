/* tb3po_line.c -- prints the line TB-3PO (fm1-x0x's seq/tb3po.c) writes for
 * one setting, through upstream's own calls only, as JSON: each step's note
 * and flags. tests/test_engine_acid_gen.py builds it against the vendored
 * file (and against fm1-x0x's own, when reference/fm1-x0x is cloned) and
 * plays Acid Gen beside it.
 *
 *   cc -std=c99 -I SEQ_DIR tb3po_line.c SEQ_DIR/tb3po.c -o line
 *   ./line SEED DENSITY ACCENT SLIDE OCTAVES ROOT SCALE BASE_OCT LENGTH MUTATIONS
 *
 * MIT licence (this file); it links GPL-3.0 code.
 */
#include <stdio.h>
#include <stdlib.h>

#include "tb3po.h"

int main(int argc, char **argv) {
  bpart_t b;
  uint32_t r = 0;
  int i, k, muts;
  if (argc != 11) {
    fprintf(stderr, "usage: line SEED DENSITY ACCENT SLIDE OCTAVES ROOT SCALE BASE_OCT LENGTH MUTATIONS\n");
    return 2;
  }
  tb3po_defaults(&b.gen, (uint32_t)strtoul(argv[1], NULL, 0));
  b.gen.seed = (uint32_t)strtoul(argv[1], NULL, 0);
  b.gen.density = (uint8_t)atoi(argv[2]);
  b.gen.accent = (uint8_t)atoi(argv[3]);
  b.gen.slide = (uint8_t)atoi(argv[4]);
  b.gen.oct_range = (uint8_t)atoi(argv[5]);
  b.gen.root = (uint8_t)atoi(argv[6]);
  b.gen.scale = (uint8_t)atoi(argv[7]);
  b.gen.base_oct = (uint8_t)atoi(argv[8]);
  b.len = (uint8_t)atoi(argv[9]);
  muts = atoi(argv[10]);
  tb3po_generate(&b);
  for (k = 0; k < muts; ++k) tb3po_mutate(&b, &r);
  printf("[");
  for (i = 0; i < b.len; ++i) {
    printf("%s{\"note\":%d,\"gate\":%d,\"accent\":%d,\"slide\":%d}", i ? "," : "", b.step[i].note,
           bstep_gate(&b.step[i]), (b.step[i].flags & BS_ACCENT) != 0, (b.step[i].flags & BS_SLIDE) != 0);
  }
  printf("]\n");
  return 0;
}
