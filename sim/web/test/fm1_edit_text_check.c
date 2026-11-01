/* Focused edit-wire text checks. C99, MIT licence. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "fm1_edit.h"

static void text(const uint8_t *b, const char *expected) {
  char out[160];
  const size_t len = strlen(expected);
  fm1_edit_rec_text(b, NULL, 0);
  for (size_t cap = 1; cap <= len + 2; ++cap) {
    memset(out, 0x5a, sizeof out);
    fm1_edit_rec_text(b, out, cap);
    assert(strlen(out) == (len < cap ? len : cap - 1));
    assert(strncmp(out, expected, cap - 1) == 0);
    assert(out[cap] == 0x5a);
  }
}

int main(int argc, char **argv) {
  uint8_t b[FM1_EDIT_REC_BYTES], round[FM1_EDIT_REC_BYTES];
  fm1_rec_t r;
  fm1_edit_verb_t v;
  if (argc == 4) {
    char line[160];
    snprintf(line, sizeof line, "param sound 0 0 1 %s index", argv[1]);
    const int ok = fm1_edit_parse_text(line, b);
    assert(ok == atoi(argv[2]));
    if (ok) {
      assert(fm1_edit_unpack(b, &r, &v) == 1);
      assert(r.u.param.vtype == FM1_VAL_INDEX);
      assert(r.u.param.bits == (uint32_t)strtoull(argv[3], NULL, 0));
      assert(fm1_edit_pack(&r, round));
      assert(memcmp(b, round, sizeof b) == 0);
    }
    return 0;
  }
  const char *const lines[] = {
    "current 3", "view matrix", "swap sound 0 0 sound 1 0",
    "move insert 0 1 insert 1 0", "param sound 0 0 1 2 index",
    "param sound 0 0 1 0.5", "unit sound 0 0 macro", "module 0 lfo",
    "on 0 1", "level 0 50", "cable 0 1 0 1 1 2 -3 4 5"
  };
  for (unsigned i = 0; i < sizeof lines / sizeof *lines; ++i) {
    assert(fm1_edit_parse_text(lines[i], b));
    text(b, i == 1 ? "view matrix has=0" : lines[i]);
    if (fm1_edit_unpack(b, &r, &v) == 1) assert(fm1_edit_pack(&r, round));
    else fm1_edit_verb_pack(&v, round);
    assert(memcmp(b, round, sizeof b) == 0);
  }
  /* Golden PARAM bytes: neither the wire layout nor padding may change. */
  const uint8_t expected[FM1_EDIT_REC_BYTES] = {
    FM1_REC_PARAM, FM1_ROLE_SOUND, 0, 0, 1, 0, 255, FM1_VAL_INDEX, 2
  };
  assert(fm1_edit_parse_text("param sound 0 0 1 2 index", b));
  assert(memcmp(b, expected, sizeof b) == 0);
  memset(b, 0, sizeof b);
  b[0] = FM1_EDIT_LOADED; text(b, "loaded");
  b[0] = 255; text(b, "type 255");
  /* Unknown roles are still printable, bounded by the formatter. */
  assert(fm1_edit_parse_text("unit sound 0 0 macro", b));
  b[1] = 255; text(b, "unit ? 0 0 macro");
  puts("edit text wire checks passed");
  return 0;
}
