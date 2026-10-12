/* Native track-name persistence, strict bounds and arena regressions. MIT. */
#include "seq_int.h"
#include "state_movy1.h"
#include <assert.h>
#include <stdio.h>

static uint64_t arena[32768u / 8u + 1u];
static char exported[8192];
static const char set[] = "movy1\nbpm 12000\nswing 50\nlink 0\nsn 0 Intro\ntk 0 0 0\n"
  "tn 0 2042617373203120\ncl 0 0 16 0 0:24:60:96:0\ncp 0 0 1 1 0 0\n";
static int consume(void *ctx, const char *text, size_t len, int first, int last) {
  (void)first;
  return fm1_seq_import_feed(ctx, text, len) && (!last || fm1_seq_import_feed(ctx, "\n", 1));
}
typedef struct { const uint8_t *data; size_t pos, len; } reader_t;
static int pull(void *ctx, uint8_t *b) {
  reader_t *r = ctx;
  if (r->pos == r->len) return 0;
  *b = r->data[r->pos++]; return 1;
}
int main(void) {
  fm1_seq_limits_t lim;
  fm1_seq_t *s;
  unsigned chunk, t;
  size_t size;
  fm1_seq_limits_default(&lim, 8);
  size = fm1_seq_size(&lim);
  /* 16 bytes per track added: the NUL uses existing tail alignment padding.
   * The instance plus the host's fixed event/pending/UI/click allocations. */
  assert(sizeof(sq_track_t) == 256u && size == 32080u);
  assert(size <= 32768u);
  assert(size + 272u * sizeof(fm1_seq_ev_t) + sizeof(fm1_seq_cmd_t) + 1024u + 20u <= 36864u);
  arena[32768u / 8u] = UINT64_C(0x123456789abcdef0);
  s = fm1_seq_create(arena, &lim, 44118);
  assert(s);
  for (t = 0; t < 8; ++t) {
    assert(!fm1_seq_track_name(s, (uint8_t)t)[0]);
    assert(fm1_seq_set_track_name(s, (uint8_t)t, "1234567890123456", 16));
  }
  assert(!fm1_seq_set_track_name(s, 8, "oops", 4));
  assert(!fm1_seq_set_track_name(s, 0, "12345678901234567", 17));
  assert(!fm1_seq_set_track_name(s, 0, "bad\n", 4));
  assert(!fm1_seq_set_track_name(s, 0, "\177", 1));
  assert(!fm1_seq_set_track_name(s, 0, "\xc3\xa9", 2));
  assert(!fm1_seq_set_track_name(s, 0, NULL, 1));
  assert(!strcmp(fm1_seq_track_name(s, 0), "1234567890123456"));
  assert(fm1_seq_set_track_name(s, 0, NULL, 0));
  assert(!fm1_seq_track_name(s, 0)[0]);
  assert(!fm1_seq_track_name(s, 255)[0]);
  for (chunk = 1; chunk <= sizeof set; ++chunk) {
    fm1_seq_import_t im;
    size_t off;
    fm1_seq_import_begin(&im, s);
    for (off = 0; off < strlen(set); off += chunk) {
      const size_t left = strlen(set) - off;
      assert(fm1_seq_import_feed(&im, set + off, left < chunk ? left : chunk));
    }
    assert(fm1_seq_import_end(&im));
    assert(!strcmp(fm1_seq_track_name(s, 0), " Bass 1 "));
    assert(!strcmp(fm1_seq_scene_name(s, 0), "Intro"));
    assert(fm1_seq_export_movy1(s, exported, sizeof exported) < sizeof exported);
    assert(strstr(exported, "tk 0 0 0\ntn 0 2042617373203120\n"));
    assert(strstr(exported, "cl 0 0 16 0 0:24:60:96:0\n"));
  }
  /* Invalid duplicate lines cannot shorten or overwrite a valid name. */
  {
    const char invalid[] = "movy1\ntn 0 42617373\ntn 0 42zz\ntn 0 0a\ntn 0 00\n"
      "tn 0 7f\ntn 0 c3a9\ntn 0 123\ntn 0 3132333435363738393031323334353637\n"
      "tn 0 4142 extra\ntn 8 4142\ntn nope 4142\ntn 0";
    assert(fm1_seq_import_movy1(s, invalid, sizeof invalid - 1u));
  }
  assert(!strcmp(fm1_seq_track_name(s, 0), "Bass"));
  /* The existing .lunarb raw-item codec preserves tn without a new binary
   * schema tag. Its streamed result enters the same native importer. */
  {
    uint8_t binary[128];
    const char *line = "tn 0 4c4541442031";
    reader_t r;
    fm1_seq_import_t im;
    r.len = fm1_movy1_encode(line, strlen(line), binary, sizeof binary);
    r.data = binary; r.pos = 0;
    assert(r.len && binary[0] == 1u); /* backward-compatible raw item */
    fm1_seq_import_begin(&im, s);
    assert(fm1_seq_import_feed(&im, "movy1\n", 6));
    assert(fm1_movy1_decode(pull, &r, consume, &im));
    assert(fm1_seq_import_end(&im));
    assert(!strcmp(fm1_seq_track_name(s, 0), "LEAD 1"));
  }
  assert(fm1_seq_import_movy1(s, "movy1\ntk 0 0 0\n", 15));
  assert(!fm1_seq_track_name(s, 0)[0]); /* absent line resets to default */
  lim.compat = 1;
  s = fm1_seq_create(arena, &lim, 44118);
  assert(fm1_seq_import_movy1(s, set, strlen(set)));
  assert(!fm1_seq_track_name(s, 0)[0]);
  assert(!fm1_seq_set_track_name(s, 0, "Bass", 4));
  fm1_seq_export_movy1(s, exported, sizeof exported);
  assert(!strstr(exported, "tn "));
  assert(arena[32768u / 8u] == UINT64_C(0x123456789abcdef0));
  printf("native track names: instance %zu B; track %zu B; importer %zu B; budget %zu/36864 B\n",
    size, sizeof(sq_track_t), sizeof(fm1_seq_import_t), size + 3264u + 240u + 1024u + 20u);
  return 0;
}
