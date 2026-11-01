/* Actual shared codec differential/fault fixture. MIT. No storage/device I/O. */
#include "fm1_state.h"
#include "state_movy1.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef FM1_CODEC_BASELINE
size_t baseline_writer_size(void);
fm1_state_writer_t *baseline_writer(void *, unsigned, unsigned, const uint8_t *, fm1_put_t, void *, fm1_state_report_t *);
int baseline_write(void *, const fm1_rec_t *);
#else
#define baseline_writer_size fm1_state_bin_writer_size
#define baseline_writer fm1_state_bin_writer
#define baseline_write fm1_state_bin_write
#endif

typedef struct { uint8_t b[FM1_STATE_BIN_MAX]; uint32_t n, calls, fail, partial, short_read; } image_t;
static image_t host_image, candidate, input;
static _Alignas(16) uint8_t compact[49152], plan[8192], plan_copy[8192];
static uint8_t *host_memory, *current_host_memory;
static const uint8_t version[3] = {0, 1, 0};
static unsigned cases;
static uint32_t report_digest;
static void put(void *ctx, const char *b, size_t n) {
  image_t *x = ctx; assert(n <= sizeof(x->b) - x->n);
  memcpy(x->b + x->n, b, n); x->n += (uint32_t)n; ++x->calls;
}
static uint32_t write_at(void *ctx, uint32_t off, const uint8_t *b, uint32_t n) {
  image_t *x = ctx;
  assert(off <= x->n && n <= x->n - off);
  ++x->calls;
  if (x->calls == x->fail) {
    uint32_t partial = x->partial && n ? n - 1u : 0;
    memcpy(x->b + off, b, partial);
    return partial;
  }
  memcpy(x->b + off, b, n); return n;
}
static uint32_t read_at(void *ctx, uint32_t off, uint8_t *b, uint32_t n) {
  image_t *x = ctx;
  if (off >= x->n) return 0;
  if (n > x->n - off) n = x->n - off;
  if (x->short_read && n > x->short_read) n = x->short_read;
  memcpy(b, x->b + off, n); return n;
}
static int accept(void *ctx, const fm1_rec_t *r) { (void)ctx; (void)r; return 1; }
static fm1_rec_t rec(unsigned type) { fm1_rec_t r; memset(&r, 0, sizeof(r)); r.type = (uint8_t)type; return r; }

typedef struct { unsigned kind, mode, n, width, fragment; } spec_t;
/* This source is replayed, never stored in the codec's workspace. Invalid
 * tails intentionally reach 65536 before the original writer refuses. */
static unsigned generate(const spec_t *s, fm1_rec_sink_t sink, void *ctx) {
  fm1_rec_t r = rec(FM1_REC_HEAD);
  unsigned pos = 0, i, j;
  static char text[FM1_MOVY1_LINE_MAX + 1];
  static uint8_t data[FM1_STATE_DATA_ONE + 1];
#define EMIT() do { ++pos; if (!sink(ctx, &r)) return pos; } while (0)
  memset(text, 'x', sizeof(text)); text[sizeof(text)-1] = 0;
  memset(data, 0x53, sizeof(data));
  r.u.head.kind = (uint8_t)s->kind; r.u.head.major = 1; EMIT();
  if (s->mode == 0) { /* raw lines; includes exact and one-over per-tag/logical limits */
    for (i = 0; i < s->n; ++i) {
      r = rec(FM1_REC_LINE); r.u.line.which = s->kind == FM1_STATE_CLIP ? FM1_LINES_CLIP : FM1_LINES_SET;
      if (s->fragment && s->width) {
        r.piece = FM1_REC_FIRST; r.u.line.s = text; r.u.line.n = s->width / 2; EMIT();
        r.piece = FM1_REC_LAST; r.u.line.s += r.u.line.n; r.u.line.n = s->width - s->width / 2; EMIT();
      } else { r.piece = 3; r.u.line.s = text; r.u.line.n = s->width; EMIT(); }
    }
  } else if (s->mode == 1) {
    for (i = 0; i < s->n; ++i) {
      r = rec(FM1_REC_INFO); r.piece = 3; r.u.info.key = FM1_INFO_NAME;
      r.u.info.s = text; r.u.info.n = (uint16_t)s->width; EMIT();
    }
  } else if (s->mode == 2) {
    for (i = 0; i < s->n; ++i) {
      r = rec(FM1_REC_UNIT); r.role = FM1_ROLE_SOUND; r.sound = (uint8_t)(i % 4);
      strcpy(r.u.unit.id, "test-sine"); EMIT();
      for (j = 0; j < s->width; ++j) {
        r = rec(FM1_REC_PARAM); r.role = FM1_ROLE_SOUND; r.sound = (uint8_t)(i % 4);
        r.u.param.uid = (uint16_t)(j + 1); r.u.param.focus = FM1_FOCUS_NONE;
        r.u.param.bits = 0x3f800000u; EMIT();
      }
    }
  } else if (s->mode == 3) {
    r = rec(FM1_REC_MOD); EMIT(); r = rec(FM1_REC_SEED); r.u.seed = 42; EMIT();
    for (i = 0; i < s->n; ++i) {
      r = rec(FM1_REC_DATA); r.slot = (uint8_t)(i % 8); r.piece = 3;
      r.u.data.b = data; r.u.data.n = (uint16_t)s->width; r.u.data.version = 1; EMIT();
    }
  } else if (s->mode == 4) {
    for (i = 0; i < s->n; ++i) { r = rec(FM1_REC_DX7); r.slot = (uint8_t)i; memset(r.u.dx7.vced, 0, 155); EMIT(); }
  } else if (s->mode == 5) {
    r = rec(FM1_REC_MIDI_MAP); r.u.map_version = 1; EMIT();
    for (i = 0; i < s->n; ++i) {
      char target[80]; snprintf(target, sizeof(target), "project/sound/%u/param/pitch", i);
      r = rec(FM1_REC_MIDI_BINDING); r.u.binding.target = target;
      r.u.binding.source = "test"; r.u.binding.channel = 0;
      r.u.binding.kind = 0; r.u.binding.number = (uint8_t)i; EMIT();
    }
  } else if (s->mode == 6) {
    r = rec(FM1_REC_SETTING); r.u.setting.key = FM1_SET_METRONOME;
    r.u.setting.is_bool = 1; r.u.setting.value = (int)s->width;
    for (i = 0; i < s->n; ++i) EMIT();
  } else if (s->mode == 7) { /* same payload, distinguish replay fragmentation */
    r = rec(FM1_REC_INFO); r.u.info.key = FM1_INFO_NAME; r.u.info.s = "test";
    r.u.info.n = s->width ? 2 : 4; r.piece = s->width ? 1 : 3; EMIT();
    if (s->width) { r.u.info.s = "st"; r.piece = 2; EMIT(); }
  } else if (s->mode == 8) {
    const char *typed[] = {"movy1", "bpm 120", "sw 0", "cl 0 1 16 0 ", "sg 1 2 3 4", "sn 0 0"};
    for (i = 0; i < s->n; ++i) {
      r = rec(FM1_REC_LINE); r.piece = 3; r.u.line.s = typed[i % 6];
      r.u.line.n = (uint32_t)strlen(r.u.line.s); EMIT();
    }
  }
  r = rec(FM1_REC_END); EMIT();
#undef EMIT
  return pos;
}

static void reset_image(image_t *x, uint32_t n) { memset(x, 0, sizeof(*x)); memset(x->b, 0xa5, sizeof(x->b)); x->n = n; }
static void compare(const spec_t *s, int faults) {
  fm1_state_report_t a, b, rep;
  fm1_state_writer_t *h, *c;
  unsigned ha, cb, calls, k;
  fm1_state_report_init(&a); fm1_state_report_init(&b);
  reset_image(&host_image, 0);
  h = baseline_writer(host_memory, 0, FM1_STATE_WRITER_SIM, version, put, &host_image, &a);
  c = fm1_state_bin_preflight(compact, sizeof(compact), plan, sizeof(plan), FM1_STATE_WRITER_SIM, version, &b);
  assert(h && c);
  ha = generate(s, baseline_write, h); cb = generate(s, fm1_state_bin_write, c);
  if (ha != cb || memcmp(&a, &b, sizeof(a))) {
    fprintf(stderr, "parity kind=%u mode=%u n=%u width=%u pos %u/%u code %u/%u %s / %s\n",s->kind,s->mode,s->n,s->width,ha,cb,a.code,b.code,a.what,b.what); abort();
  }
  report_digest = fm1_state_crc32(report_digest, (const uint8_t *)&ha, sizeof(ha));
  report_digest = fm1_state_crc32(report_digest, (const uint8_t *)&a, sizeof(a));
  ++cases;
  if (a.code) { assert(!host_image.calls && !fm1_state_bin_plan_total(plan, sizeof(plan))); return; }
  assert(host_image.n == fm1_state_bin_plan_total(plan, sizeof(plan)));
  memcpy(plan_copy, plan, sizeof(plan));
  reset_image(&candidate, host_image.n);
  fm1_state_report_init(&rep);
  c = fm1_state_bin_replay(compact, sizeof(compact), plan, sizeof(plan), write_at, &candidate, &rep);
  assert(c && generate(s, fm1_state_bin_write, c) == ha && !rep.code);
  assert(!memcmp(plan, plan_copy, sizeof(plan)));
  assert(!memcmp(candidate.b, host_image.b, host_image.n));
  calls = candidate.calls;
  candidate.short_read = 1;
  assert(fm1_state_bin_plan_match(plan, sizeof(plan), read_at, &candidate, candidate.n, &rep));
  candidate.short_read = 0;
  if (!faults) return;
  {
    image_t *x = &input;
    fm1_state_report_t old_report, new_report;
    fm1_state_writer_t *old_writer, *new_writer;
    reset_image(x, 0); reset_image(&candidate, 0);
    fm1_state_report_init(&old_report); fm1_state_report_init(&new_report);
    old_writer = baseline_writer(host_memory, FM1_STATE_BIN_DEFLATE, 1, version, put, x, &old_report);
    new_writer = fm1_state_bin_writer(current_host_memory, FM1_STATE_BIN_DEFLATE, 1, version, put, &candidate, &new_report);
    assert(generate(s, baseline_write, old_writer) == generate(s, fm1_state_bin_write, new_writer));
    assert(!memcmp(&old_report, &new_report, sizeof(old_report)));
    assert(x->n == candidate.n && !memcmp(x->b, candidate.b, x->n));
  }
  for (k = 1; k <= calls; ++k) {
    unsigned partial;
    for (partial = 0; partial < 2; ++partial) {
      fm1_rec_t end = rec(FM1_REC_END);
      reset_image(&candidate, host_image.n); candidate.fail = k; candidate.partial = partial;
      fm1_state_report_init(&rep);
      c = fm1_state_bin_replay(compact, sizeof(compact), plan, sizeof(plan), write_at, &candidate, &rep);
      assert(c); generate(s, fm1_state_bin_write, c);
      assert(rep.code == FM1_STATE_STOPPED && candidate.calls == k);
      assert(!fm1_state_bin_write(c, &end) && candidate.calls == k);
    }
  }
  reset_image(&candidate, host_image.n); memcpy(candidate.b, host_image.b, host_image.n);
  for (k = 0; k < host_image.n; k += host_image.n < 512 ? 1 : 73) {
    candidate.b[k] ^= 1; fm1_state_report_init(&rep);
    assert(!fm1_state_bin_plan_match(plan, sizeof(plan), read_at, &candidate, candidate.n, &rep));
    candidate.b[k] ^= 1;
  }
  fm1_state_report_init(&rep);
  assert(!fm1_state_bin_plan_match(plan, sizeof(plan), read_at, &candidate, candidate.n - 1, &rep));
}

static void guards(void) {
  fm1_state_report_t rep;
  fm1_state_writer_t *c;
  spec_t s = {FM1_STATE_PROJECT, 7, 1, 0, 0};
  fm1_state_report_init(&rep);
  assert(!fm1_state_bin_preflight(compact + 1, sizeof(compact)-1, plan, sizeof(plan), 1, version, &rep));
  fm1_state_report_init(&rep);
  assert(!fm1_state_bin_preflight(compact, fm1_state_bin_compact_size()-1, plan, sizeof(plan), 1, version, &rep));
  fm1_state_report_init(&rep);
  assert(!fm1_state_bin_preflight(compact, sizeof(compact), compact, sizeof(compact), 1, version, &rep));
  fm1_state_report_init(&rep);
  assert(!fm1_state_bin_preflight(compact, sizeof(compact), plan, fm1_state_bin_plan_size()-1, 1, version, &rep));
  c = fm1_state_bin_preflight(compact, sizeof(compact), plan, sizeof(plan), 1, version, &rep);
  assert(c && !fm1_state_bin_plan_total(plan, sizeof(plan)));
  fm1_state_report_init(&rep); assert(generate(&s, fm1_state_bin_write, c));
  reset_image(&candidate, fm1_state_bin_plan_total(plan, sizeof(plan)));
  s.width = 1; fm1_state_report_init(&rep);
  c = fm1_state_bin_replay(compact, sizeof(compact), plan, sizeof(plan), write_at, &candidate, &rep);
  generate(&s, fm1_state_bin_write, c);
  assert(rep.code == FM1_STATE_BAD); /* bytes same, fragmented record trace differs */
  plan[0] ^= 1; fm1_state_report_init(&rep);
  assert(!fm1_state_bin_replay(compact, sizeof(compact), plan, sizeof(plan), write_at, &candidate, &rep));
  assert(!candidate.calls || candidate.b[0] == 0xa5); /* header was never published */
}

/* JSON input drives the ordinary parser positions/counters into the same
 * report as the writer, as app save does. Deferred cap failures must retain
 * line/column/path/offset/near and the exact first failing record. */
static void json_report(unsigned lines, unsigned width) {
  fm1_state_names_t names;
  fm1_state_report_t a, b;
  fm1_state_writer_t *h, *c;
  unsigned i;
  int x, y;
  memset(&names, 0, sizeof(names)); reset_image(&input, 0);
  put(&input, "{\"lunar\":\"1.0\",\"kind\":\"clip\",\"clip\":[", 37);
  for (i = 0; i < lines; ++i) {
    unsigned j;
    if (i) put(&input, ",", 1);
    put(&input, "\"", 1);
    for (j = 0; j < width; ++j) put(&input, "x", 1);
    put(&input, "\"", 1);
  }
  put(&input, "]}\n", 3);
  fm1_state_report_init(&a); fm1_state_report_init(&b); reset_image(&host_image, 0);
  h = baseline_writer(host_memory, 0, 1, version, put, &host_image, &a);
  c = fm1_state_bin_preflight(compact, sizeof(compact), plan, sizeof(plan), 1, version, &b);
  x = fm1_state_json_read(&names, read_at, &input, baseline_write, h, &a);
  y = fm1_state_json_read(&names, read_at, &input, fm1_state_bin_write, c, &b);
  assert(x == y && !memcmp(&a, &b, sizeof(a)));
  if (!x) assert(!fm1_state_bin_plan_total(plan, sizeof(plan)));
  report_digest = fm1_state_crc32(report_digest, (const uint8_t *)&a, sizeof(a));
  ++cases;
}

static void golden(const char *path) {
  FILE *f = fopen(path, "rb"); fm1_state_report_t a, b, parse;
  fm1_state_writer_t *h, *c;
  assert(f); reset_image(&input, 0); input.n = (uint32_t)fread(input.b, 1, sizeof(input.b), f); assert(!ferror(f)); fclose(f);
  reset_image(&host_image, 0); fm1_state_report_init(&a); fm1_state_report_init(&b); fm1_state_report_init(&parse);
  h = baseline_writer(host_memory, 0, 1, version, put, &host_image, &a);
  assert(fm1_state_bin_read(read_at, &input, input.n, baseline_write, h, &parse, 0));
  c = fm1_state_bin_preflight(compact, sizeof(compact), plan, sizeof(plan), 1, version, &b);
  fm1_state_report_init(&parse);
  assert(fm1_state_bin_read(read_at, &input, input.n, fm1_state_bin_write, c, &parse, 0));
  assert(!memcmp(&a, &b, sizeof(a))); reset_image(&candidate, host_image.n);
  c = fm1_state_bin_replay(compact, sizeof(compact), plan, sizeof(plan), write_at, &candidate, &b);
  fm1_state_report_init(&parse);
  assert(fm1_state_bin_read(read_at, &input, input.n, fm1_state_bin_write, c, &parse, 0));
  assert(!memcmp(candidate.b, host_image.b, host_image.n));
  assert(fm1_state_bin_plan_match(plan, sizeof(plan), read_at, &candidate, candidate.n, &b));
  fm1_state_report_init(&parse);
  assert(fm1_state_bin_read(read_at, &candidate, candidate.n, accept, NULL, &parse, 0));
  ++cases;
}
int main(int argc, char **argv) {
  unsigned i, j;
  const unsigned widths[] = {0, 1, 5, 127, 1024, 2045, 4093, 8190, 16381, 16384, 16385};
  const unsigned counts[] = {1, 2, 3, 4, 5, 16, 64, 65};
  spec_t s = {FM1_STATE_SET, 0, 0, 0, 0};
  assert(fm1_state_bin_compact_size() <= sizeof(compact)); assert(fm1_state_bin_plan_size() <= sizeof(plan));
  host_memory = malloc(baseline_writer_size()); assert(host_memory);
  current_host_memory = malloc(fm1_state_bin_writer_size()); assert(current_host_memory);
  for (i = 0; i < sizeof(widths)/sizeof(widths[0]); ++i) for (j = 0; j < sizeof(counts)/sizeof(counts[0]); ++j) {
    s.width = widths[i]; s.n = counts[j]; s.kind = FM1_STATE_SET; s.fragment = 0; compare(&s, i == 2 && j == 1);
    s.fragment = 1; compare(&s, 0); s.fragment = 0; s.kind = FM1_STATE_CLIP; compare(&s, 0);
  }
  for (s.mode = 1; s.mode <= 8; ++s.mode) {
    s.kind = s.mode == 6 ? FM1_STATE_SETTINGS : FM1_STATE_PROJECT;
    for (i = 0; i < sizeof(counts)/sizeof(counts[0]); ++i) {
      s.n = counts[i]; s.width = s.mode == 2 ? 512 : s.mode == 3 ? 4096 : s.mode == 1 ? 1024 : 0;
      compare(&s, i == 0);
      if (s.mode == 2 || s.mode == 3 || s.mode == 1) { ++s.width; compare(&s, 0); }
    }
  }
  {
    const spec_t boundary[] = {
      {FM1_STATE_PROJECT, 2, 64, 0, 0}, {FM1_STATE_PROJECT, 2, 65, 0, 0},
      {FM1_STATE_PROJECT, 2, 24, 506, 0}, {FM1_STATE_PROJECT, 2, 24, 507, 0},
      {FM1_STATE_PROJECT, 4, 32, 0, 0}, {FM1_STATE_PROJECT, 4, 33, 0, 0},
      {FM1_STATE_PROJECT, 4, 409, 0, 0}, {FM1_STATE_PROJECT, 4, 410, 0, 0},
      {FM1_STATE_PROJECT, 3, 16, 4091, 0}, {FM1_STATE_PROJECT, 3, 16, 4092, 0},
      {0, 0, 0, 0, 0}, {FM1_STATE_DX7BANK, 1, 1, 1, 0},
      {FM1_STATE_SETTINGS, 6, 204, 0, 0}, {FM1_STATE_SETTINGS, 6, 205, 0, 0}
    };
    for (i = 0; i < sizeof(boundary)/sizeof(boundary[0]); ++i) compare(&boundary[i], 0);
  }
  guards();
  for (i = 1; i <= 5; ++i) { json_report(i, 8190); json_report(i, 4093); }
  json_report(1, 16384); json_report(1, 16385);
  for (i = 1; i < (unsigned)argc; ++i) golden(argv[i]);
  printf("codec cases=%u reports=%08x compact=%zu plan=%zu host=%zu\n", cases, report_digest,
      fm1_state_bin_compact_size(), fm1_state_bin_plan_size(), fm1_state_bin_writer_size());
  free(current_host_memory); free(host_memory); return 0;
}
