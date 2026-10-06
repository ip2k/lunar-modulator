/* state_fuzz.c -- the state codecs under hostile input (notes/2026-10-06-
 * state-files.md §16-§17; engines/state/README.md, "Fuzzing").
 *
 * One input, every reader, and the invariants that make a crash-free run
 * mean something:
 *   - the JSON reader fed whole and in pieces (sizes drawn from the input)
 *     gives the same records and the same verdict;
 *   - the binary reader, with and without its CRC checks (the fuzz path
 *     that lets mutations reach the chunk parsers), never reads out of
 *     bounds and never gives a record it would refuse to write;
 *   - whatever a reader accepts, the canonical JSON writer writes; that text
 *     reads back to the same records and writes back to itself; the binary
 *     writer packs it, and the binary reads back to the same canonical text
 *     (lossless both ways);
 *   - the sequencer core's movy1 import (any input, as set text): fed in
 *     pieces it gives the same verdict and the same set as fed whole, and
 *     an imported set's export imports back to itself; and a state file's
 *     set lines streamed record by record into the import give the set
 *     their joined text gives.
 * A broken invariant aborts, so libFuzzer and the sanitizers report it.
 *
 * Built two ways (mk/state.mk):
 *   fm1-state-fuzz              a seeded mutation loop over seed files:
 *                               fm1-state-fuzz [-n N] [-s SEED] FILE...
 *   with -DFM1_LIBFUZZER        LLVMFuzzerTestOneInput, for clang's
 *                               -fsanitize=fuzzer (run on a Linux host)
 * The names are the build's registries. Host code. MIT licence. */
#include "fm1_seq.h"
#include "fm1_state.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAXIN (300u * 1024u)

typedef struct {
  uint8_t *b;
  size_t n, cap;
} buf_t;

static void bput(void *ctx, const char *s, size_t n) {
  buf_t *b = (buf_t *)ctx;
  if (!n) return;
  if (b->n + n > b->cap) {
    size_t cap = b->cap ? b->cap : 4096;
    while (b->n + n > cap) cap *= 2;
    b->b = (uint8_t *)realloc(b->b, cap);
    if (!b->b) abort();
    b->cap = cap;
  }
  memcpy(b->b + b->n, s, n);
  b->n += n;
}

static uint32_t mread(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
  const buf_t *b = (const buf_t *)ctx;
  if (off >= b->n) return 0;
  if (n > b->n - off) n = (uint32_t)(b->n - off);
  memcpy(out, b->b + off, n);
  return n;
}

static fm1_state_names_t g_names;
static long g_accepted, g_binary, g_movy1, g_streamed;
static void *g_jw, *g_bw;

static const uint8_t *g_cur;
static size_t g_cur_n;

/* A broken invariant: the input goes to fuzz-failure.bin, then abort. */
static void fail(const char *what) {
  FILE *f = fopen("fuzz-failure.bin", "wb");
  if (f) {
    fwrite(g_cur, 1, g_cur_n, f);
    fclose(f);
  }
  fprintf(stderr, "invariant broken: %s (input in fuzz-failure.bin)\n", what);
  abort();
}

/* Records of a JSON input, printed; fed in pieces when `pieces`. */
static int json_records(const uint8_t *d, size_t n, size_t pieces, uint32_t seed, buf_t *out,
                        fm1_state_report_t *rep) {
  fm1_state_printer_t p;
  fm1_state_json_reader_t r;
  size_t off = 0;
  int ok = 1;
  fm1_state_report_init(rep);
  fm1_state_printer_init(&p, bput, out);
  fm1_state_json_begin(&r, &g_names, fm1_state_print, &p, rep);
  while (ok && off < n) {
    size_t m = pieces ? 1u + (seed % pieces) : n - off;
    seed = seed * 1103515245u + 12345u;
    if (m > n - off) m = n - off;
    ok = fm1_state_json_feed(&r, d + off, m);
    off += m;
  }
  return ok && fm1_state_json_end(&r);
}

static int canon(const buf_t *in, int binary, buf_t *out) {
  fm1_state_report_t rep;
  fm1_state_writer_t *w;
  fm1_state_report_init(&rep);
  out->n = 0;
  w = fm1_state_json_writer(g_jw, &g_names, 0, bput, out, &rep);
  if (binary) return fm1_state_bin_read(mread, (void *)in, (uint32_t)in->n, fm1_state_write, w, &rep, 0);
  return fm1_state_json_read(&g_names, mread, (void *)in, fm1_state_write, w, &rep);
}

static int same(const buf_t *a, const buf_t *b) { return a->n == b->n && (!a->n || !memcmp(a->b, b->b, a->n)); }

/* ---- The sequencer core's import ------------------------------------------- */
static void *g_seq_mem[3];
static size_t g_seq_bytes;

static fm1_seq_t *seq_fresh(int k, int compat) {
  fm1_seq_limits_t lim;
  fm1_seq_limits_default(&lim, 8);
  lim.compat = (uint8_t)(compat != 0);
  if (!g_seq_mem[k]) {
    g_seq_bytes = fm1_seq_size(&lim);
    g_seq_mem[k] = calloc(1, g_seq_bytes + 16u);
    if (!g_seq_mem[k]) abort();
  }
  return fm1_seq_create(g_seq_mem[k], &lim, 44118u);
}

static void seq_export(const fm1_seq_t *s, buf_t *out) {
  const size_t need = fm1_seq_export_movy1(s, NULL, 0);
  char *t = (char *)malloc(need + 1u);
  if (!t) abort();
  fm1_seq_export_movy1(s, t, need + 1u);
  out->n = 0;
  bput(out, t, need);
  free(t);
}

/* Any input as set text: whole against pieces, and export as a fixed point. */
static void movy1_import(const uint8_t *d, size_t n, uint32_t seed) {
  const int compat = (int)(seed >> 1 & 1u);
  fm1_seq_t *a = seq_fresh(0, compat), *b = seq_fresh(1, compat);
  fm1_seq_import_t im;
  buf_t ea = { NULL, 0, 0 }, eb = { NULL, 0, 0 }, ec = { NULL, 0, 0 };
  size_t off = 0, piece = 1u + seed % 61u;
  int ra, rb;
  if (!a || !b) abort();
  ra = fm1_seq_import_movy1(a, (const char *)d, n);
  fm1_seq_import_begin(&im, b);
  while (off < n) {
    const size_t m = n - off < piece ? n - off : piece;
    fm1_seq_import_feed(&im, (const char *)d + off, m);
    off += m;
    piece = 1u + (piece * 7u + 3u) % 61u;
  }
  rb = fm1_seq_import_end(&im);
  if (ra != rb) fail("pieces change the import's verdict");
  if (ra) {
    fm1_seq_t *c = seq_fresh(2, compat);
    ++g_movy1;
    seq_export(a, &ea);
    seq_export(b, &eb);
    if (!same(&ea, &eb)) fail("pieces change the imported set");
    if (!c || !fm1_seq_import_movy1(c, (const char *)ea.b, ea.n)) fail("an export does not import");
    seq_export(c, &ec);
    if (!same(&ea, &ec)) fail("an imported set's export is not a fixed point");
  }
  free(ea.b); free(eb.b); free(ec.b);
}

/* A state file's set lines: streamed into the import as their records come,
 * and joined. */
typedef struct {
  fm1_seq_import_t im;
  buf_t text;
  int any;
} set_lines_t;

static int set_lines_sink(void *ctx, const fm1_rec_t *r) {
  set_lines_t *k = (set_lines_t *)ctx;
  if (r->type != FM1_REC_LINE || r->u.line.which != FM1_LINES_SET) return 1;
  k->any = 1;
  fm1_seq_import_feed(&k->im, r->u.line.s, r->u.line.n);
  bput(&k->text, r->u.line.s, r->u.line.n);
  if (r->piece & FM1_REC_LAST) {
    fm1_seq_import_feed(&k->im, "\n", 1);
    bput(&k->text, "\n", 1);
  }
  return 1;
}

static void set_records(const buf_t *in, int binary) {
  set_lines_t k;
  fm1_state_report_t rep;
  buf_t ea = { NULL, 0, 0 }, eb = { NULL, 0, 0 };
  fm1_seq_t *a = seq_fresh(0, 0), *b = seq_fresh(1, 0);
  int ok, ra, rb;
  if (!a || !b) abort();
  memset(&k, 0, sizeof(k));
  fm1_seq_import_begin(&k.im, b);
  fm1_state_report_init(&rep);
  ok = binary ? fm1_state_bin_read(mread, (void *)in, (uint32_t)in->n, set_lines_sink, &k, &rep, 0)
              : fm1_state_json_read(&g_names, mread, (void *)in, set_lines_sink, &k, &rep);
  if (ok && k.any) {
    rb = fm1_seq_import_end(&k.im);
    ra = fm1_seq_import_movy1(a, k.text.b ? (const char *)k.text.b : "", k.text.n);
    if (ra != rb) fail("streamed set lines change the import's verdict");
    if (ra) {
      ++g_streamed;
      seq_export(a, &ea);
      seq_export(b, &eb);
      if (!same(&ea, &eb)) fail("streamed set lines give another set");
    }
  }
  free(k.text.b); free(ea.b); free(eb.b);
}

static void one(const uint8_t *data, size_t size) {
  buf_t in = { NULL, 0, 0 }, whole = { NULL, 0, 0 }, cut = { NULL, 0, 0 }, c1 = { NULL, 0, 0 },
        c2 = { NULL, 0, 0 }, bin = { NULL, 0, 0 }, c3 = { NULL, 0, 0 }, sink = { NULL, 0, 0 };
  fm1_state_report_t r1, r2;
  const uint32_t seed = size ? (uint32_t)data[0] * 2654435761u + (uint32_t)size : 1u;
  int ok1, ok2, binary;
  if (size > MAXIN) return;
  g_cur = data;
  g_cur_n = size;
  bput(&in, (const char *)data, size);
  binary = fm1_state_sniff(data, size) == 1;
  if (binary) {
    fm1_state_printer_t p;
    fm1_state_report_init(&r1);
    fm1_state_printer_init(&p, bput, &sink);
    fm1_state_bin_read(mread, &in, (uint32_t)in.n, fm1_state_print, &p, &r1, 1);   /* past the CRCs */
    ok1 = canon(&in, 1, &c1);
  } else {
    ok1 = json_records(data, size, 0, seed, &whole, &r1);
    ok2 = json_records(data, size, 1u + (seed % 257u), seed, &cut, &r2);
    if (ok1 != ok2 || r1.code != r2.code) fail("pieces change the verdict");
    if (ok1 && !same(&whole, &cut)) fail("pieces change the records");
    ok1 = ok1 && canon(&in, 0, &c1);
  }
  movy1_import(data, size, seed);
  if (ok1) {
    ++g_accepted;
    g_binary += binary;
    set_records(&in, binary);
    /* The canonical text reads back and writes back to itself. */
    if (!canon(&c1, 0, &c2)) fail("the canonical text does not read back");
    if (!same(&c1, &c2)) fail("canonical text is not a fixed point");
    /* JSON -> binary -> JSON. */
    {
      fm1_state_report_t rep;
      static const uint8_t version[3] = { 0, 0, 0 };
      fm1_state_writer_t *w;
      fm1_state_report_init(&rep);
      w = fm1_state_bin_writer(g_bw, (seed & 1u) ? FM1_STATE_BIN_DEFLATE : 0u, FM1_STATE_WRITER_DESKTOP,
                               version, bput, &bin, &rep);
      if (fm1_state_json_read(&g_names, mread, &c1, fm1_state_bin_write, w, &rep)) {
        if (!canon(&bin, 1, &c3)) fail("a written binary does not read back");
        if (!same(&c1, &c3)) fail("JSON -> binary -> JSON is not lossless");
      } else if (rep.code != FM1_STATE_TOO_BIG) {
        fail("canonical text the binary writer refuses");
      }
    }
  }
  free(in.b); free(whole.b); free(cut.b); free(c1.b); free(c2.b); free(bin.b); free(c3.b); free(sink.b);
}

static void setup(void) {
  if (g_jw) return;
  fm1_state_names_default(&g_names);
  g_jw = calloc(1, fm1_state_json_writer_size());
  g_bw = calloc(1, fm1_state_bin_writer_size());
  if (!g_jw || !g_bw) abort();
}

#ifdef FM1_LIBFUZZER
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  setup();
  one(data, size);
  return 0;
}
#else
/* ---- A seeded mutation loop, where libFuzzer is not at hand ----------------- */
static uint32_t g_rng = 1;
static uint32_t rnd(void) {
  g_rng ^= g_rng << 13;
  g_rng ^= g_rng >> 17;
  g_rng ^= g_rng << 5;
  return g_rng;
}

static const char *const kTokens[] = { "{", "}", "[", "]", ",", ":", "\"", "null", "true", "0", "-0",
                                       "1e39", "0.5", "\"#7\"", "\\u0000", "\\ud800", "\"engine\"",
                                       "\"params\"", "\"mod\"", "\"sounds\"", "\"lunar\"", "99999999999" };

/* A binary's header, directory and chunk CRCs made right again, so a
 * mutation reaches the chunk parsers with the checks on. */
static uint32_t g32(const uint8_t *p) { return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
static void p32(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24); }
static void fix_crcs(uint8_t *d, size_t n) {
  uint32_t hdr, count, esz, i;
  if (n < 32 || fm1_state_sniff(d, n) != 1) return;
  hdr = (uint32_t)d[12] | (uint32_t)d[13] << 8;
  count = (uint32_t)d[14] | (uint32_t)d[15] << 8;
  esz = (uint32_t)d[16] | (uint32_t)d[17] << 8;
  p32(d + 20, (uint32_t)n);
  for (i = 0; i < count && hdr + (i + 1) * esz <= n && esz >= 20; ++i) {
    uint8_t *e = d + hdr + i * esz;
    const uint32_t off = g32(e + 8), len = g32(e + 12);
    if (off <= n && len <= n - off) p32(e + 16, fm1_state_crc32(0, d + off, len));
  }
  if (esz >= 20 && hdr + count * esz + 4 <= n) p32(d + hdr + count * esz, fm1_state_crc32(0, d + hdr, count * esz));
  p32(d + 28, fm1_state_crc32(0, d, 28));
}

static size_t mutate(uint8_t *d, size_t n, size_t cap) {
  const unsigned k = 1u + rnd() % 4u;
  unsigned i;
  for (i = 0; i < k; ++i) {
    const unsigned op = rnd() % 8u;
    const size_t at = n ? rnd() % n : 0;
    if (op >= 6 && n) {                              /* a digit for a digit */
      size_t j = at;
      while (j < n && !(d[j] >= '0' && d[j] <= '9')) ++j;
      if (j < n) d[j] = (uint8_t)('0' + rnd() % 10u);
    } else if (op == 0 && n) {
      d[at] ^= (uint8_t)(1u << (rnd() % 8u));
    } else if (op == 1 && n) {
      d[at] = (uint8_t)rnd();
    } else if (op == 2 && n) {                       /* cut */
      const size_t m = 1u + rnd() % (n - at < 64 ? n - at : 64);
      memmove(d + at, d + at + m, n - at - m);
      n -= m;
    } else if (op == 3 && n && n < cap / 2) {        /* duplicate a span */
      const size_t m = 1u + rnd() % (n - at < 64 ? n - at : 64);
      memmove(d + at + m, d + at, n - at);
      n += m;
    } else if (op == 4 && n + 16 < cap) {            /* a token */
      const char *t = kTokens[rnd() % (sizeof(kTokens) / sizeof(kTokens[0]))];
      const size_t m = strlen(t);
      memmove(d + at + m, d + at, n - at);
      memcpy(d + at, t, m);
      n += m;
    } else if (op == 5) {
      n = n ? rnd() % n : 0;                         /* truncate */
    }
  }
  return n;
}

int main(int argc, char **argv) {
  long iters = 2000;
  int i, files = 0;
  static uint8_t seeds[32][MAXIN];
  static size_t seed_n[32];
  static uint8_t work[MAXIN];
  for (i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "-n") == 0 && i + 1 < argc) iters = atol(argv[++i]);
    else if (strcmp(argv[i], "-s") == 0 && i + 1 < argc) {
      /* Every seed its own stream: mixed (murmur3's finaliser), then kept
       * nonzero for xorshift32. `| 1` alone made seeds 2k and 2k+1 one run. */
      uint32_t x = (uint32_t)strtoul(argv[++i], NULL, 0) ^ 0x9E3779B9u;
      x ^= x >> 16; x *= 0x85EBCA6Bu; x ^= x >> 13; x *= 0xC2B2AE35u; x ^= x >> 16;
      g_rng = x ? x : 1u;
    } else if (files >= 32) {
      fprintf(stderr, "at most 32 seed files (%s is the 33rd)\n", argv[i]);
      return 2;
    } else {
      FILE *f = fopen(argv[i], "rb");
      if (!f) { fprintf(stderr, "cannot open %s\n", argv[i]); return 2; }
      seed_n[files] = fread(seeds[files], 1, MAXIN / 2, f);
      fclose(f);
      ++files;
    }
  }
  if (!files) {
    fprintf(stderr, "usage: fm1-state-fuzz [-n N] [-s SEED] FILE...\n");
    return 2;
  }
  setup();
  for (i = 0; i < files; ++i) one(seeds[i], seed_n[i]);
  for (long it = 0; it < iters; ++it) {
    const int s = (int)(rnd() % (unsigned)files);
    size_t n = seed_n[s];
    memcpy(work, seeds[s], n);
    n = mutate(work, n, sizeof(work));
    if (rnd() & 1u) fix_crcs(work, n);
    one(work, n);
  }
  printf("{\"iterations\":%ld,\"seeds\":%d,\"accepted\":%ld,\"accepted_binary\":%ld,"
         "\"movy1_imported\":%ld,\"sets_streamed\":%ld}\n", iters, files, g_accepted, g_binary, g_movy1,
         g_streamed);
  free(g_jw);
  free(g_bw);
  for (i = 0; i < 3; ++i) free(g_seq_mem[i]);
  return 0;
}
#endif
