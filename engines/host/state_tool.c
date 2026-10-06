/* state_tool.c -- fm1-state: the saved-state files on the desktop (stage
 * E3; engines/state/README.md, notes/2026-10-06-state-files.md §12.6).
 *
 *   fm1-state canon FILE [-o OUT] [--compact] [--without]
 *       any state file (JSON or binary) as canonical JSON. A JSON file's
 *       members are put in context order first (R1-R4, fm1_state.h), so a
 *       hand edit that breaks it is put right rather than refused.
 *   fm1-state pack FILE [-o OUT] [--store] [--without]
 *       JSON to the binary container, through canon (--store: no deflate)
 *   fm1-state unpack FILE [-o OUT]
 *       binary to canonical JSON (a binary set to its .movy1 text)
 *   fm1-state from-movy1 FILE.movy1 [-o OUT]
 *       a set as a binary set file (kind 7)
 *   fm1-state records FILE [--pieces N] [--strict]
 *       the records a reader gives, one JSON object a line; --pieces feeds
 *       the JSON reader N bytes at a time, as SysEx pages and flash reads do
 *   fm1-state check FILE [--rate HZ]
 *       pass 1 (§10.1): every engine and kind in this build, each created at
 *       the rate, and the instances' RAM at 44,118 Hz against the budget
 *   fm1-state diff A B
 *       the canonical JSON of both, line by line
 *   fm1-state json-check FILE
 *       the tokenizer alone (the JSONTestSuite run): exit 0 if it accepts
 *   fm1-state names
 *       the build's names, ranges and defaults, exact, for tools/lunar_state.py
 *   fm1-state num
 *       number tests, a line each on stdin: "f TEXT" (decimal to float32,
 *       fast and exact paths), "t BITS" (float32 to text), "q TEXT" (percent
 *       to Q1.14), "p Q" (Q1.14 to percent)
 *
 * A refusal prints the report as one JSON line on stderr and exits 1; an
 * engine or kind this build does not have refuses (UNKNOWN) unless
 * --without leaves it out (§10.3). Host code: stdio and malloc. MIT licence. */
#include "fm1_deflate.h"
#include "fm1_num.h"
#include "fm1_state.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FILE_MAX (1u << 20)

typedef struct {
  uint8_t *b;
  size_t n, cap;
} buf_t;

static void buf_put(void *ctx, const char *s, size_t n) {
  buf_t *b = (buf_t *)ctx;
  if (b->n + n + 1 > b->cap) {
    size_t cap = b->cap ? b->cap : 4096;
    while (b->n + n + 1 > cap) cap *= 2;
    b->b = (uint8_t *)realloc(b->b, cap);
    if (!b->b) { fprintf(stderr, "out of memory\n"); exit(3); }
    b->cap = cap;
  }
  memcpy(b->b + b->n, s, n);
  b->n += n;
  b->b[b->n] = 0;
}

static void file_put(void *ctx, const char *s, size_t n) { fwrite(s, 1, n, (FILE *)ctx); }

static uint32_t mem_read(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
  const buf_t *b = (const buf_t *)ctx;
  if (off >= b->n) return 0;
  if (n > b->n - off) n = (uint32_t)(b->n - off);
  memcpy(out, b->b + off, n);
  return n;
}

static int read_file(const char *path, buf_t *out) {
  FILE *f = strcmp(path, "-") == 0 ? stdin : fopen(path, "rb");
  char t[65536];
  size_t got;
  memset(out, 0, sizeof(*out));
  if (!f) { fprintf(stderr, "cannot open %s\n", path); return 0; }
  while ((got = fread(t, 1, sizeof(t), f)) > 0) {
    buf_put(out, t, got);
    if (out->n > FILE_MAX) { fprintf(stderr, "%s: larger than 1 MiB\n", path); break; }
  }
  if (f != stdin) fclose(f);
  if (!out->b) buf_put(out, "", 0);
  return out->n <= FILE_MAX;
}

static int write_out(const char *path, const buf_t *b) {
  FILE *f = path ? fopen(path, "wb") : stdout;
  if (!f) { fprintf(stderr, "cannot write %s\n", path); return 0; }
  fwrite(b->b, 1, b->n, f);
  if (path) return fclose(f) == 0;
  fflush(f);
  return 1;
}

static void json_text(FILE *f, const char *s) {
  fputc('"', f);
  for (; *s; ++s) {
    const unsigned char c = (unsigned char)*s;
    if (c == '"' || c == '\\') fprintf(f, "\\%c", c);
    else if (c < 0x20) fprintf(f, "\\u%04x", c);
    else fputc(c, f);
  }
  fputc('"', f);
}

static void print_report(FILE *f, const fm1_state_report_t *r) {
  fprintf(f, "{\"code\":\"%s\",\"kind\":", fm1_state_code_name(r->code));
  json_text(f, fm1_state_kind_name(r->kind) ? fm1_state_kind_name(r->kind) : "");
  fprintf(f, ",\"what\":");
  json_text(f, r->what);
  fprintf(f, ",\"path\":");
  json_text(f, r->path);
  fprintf(f, ",\"line\":%u,\"col\":%u,\"offset\":%u,\"near\":", r->line, r->col, r->offset);
  json_text(f, r->near);
  fprintf(f, ",\"name\":");
  json_text(f, r->name);
  fprintf(f, ",\"records\":%u,\"skipped\":%u,\"repaired\":%u,\"defaulted\":%u,\"unknown\":%u,"
             "\"units\":%u,\"modules\":%u,\"cables\":%u,\"voices\":%u,\"lines\":%u,\"first_skip\":",
          r->records, r->skipped, r->repaired, r->defaulted, r->unknown, r->units, r->modules, r->cables,
          r->voices, r->lines);
  json_text(f, r->first_skip);
  fprintf(f, "}\n");
}

/* ---- Reorder: a JSON file's members into context order ---------------------
 * A small tree of the whole file, sorted so each object gives the members
 * a streaming reader needs first (R1-R4), then written compactly. Only
 * canon and pack do this, because only they hold the whole file. */
typedef struct node {
  uint8_t type;               /* FM1_JSON_OBJ, ARR, STR, NUM, TRUE, FALSE, NULL */
  char *key;
  size_t keyn;
  char *s;
  size_t sn;
  struct node **kids;
  size_t nkids, capkids;
} node_t;

typedef struct {
  node_t *stack[16];
  int sp;
  node_t *root;
  char *key;
  size_t keyn;
  node_t *str;
  int oom;
} tree_t;

static node_t *node_new(tree_t *t, uint8_t type) {
  node_t *n = (node_t *)calloc(1, sizeof(node_t));
  if (!n) { t->oom = 1; return NULL; }
  n->type = type;
  n->key = t->key;
  n->keyn = t->keyn;
  t->key = NULL;
  t->keyn = 0;
  if (t->sp > 0) {
    node_t *p = t->stack[t->sp - 1];
    if (p->nkids == p->capkids) {
      p->capkids = p->capkids ? 2 * p->capkids : 8;
      p->kids = (node_t **)realloc(p->kids, p->capkids * sizeof(node_t *));
      if (!p->kids) { t->oom = 1; return NULL; }
    }
    p->kids[p->nkids++] = n;
  } else {
    t->root = n;
  }
  return n;
}

static int tree_cb(void *ctx, const fm1_json_ev_t *ev) {
  tree_t *t = (tree_t *)ctx;
  node_t *n;
  switch (ev->type) {
    case FM1_JSON_KEY:
      t->key = (char *)malloc(ev->n + 1);
      if (!t->key) return 0;
      memcpy(t->key, ev->s, ev->n);
      t->keyn = ev->n;
      return 1;
    case FM1_JSON_OBJ:
    case FM1_JSON_ARR:
      n = node_new(t, ev->type);
      if (!n || t->sp >= 16) return 0;
      t->stack[t->sp++] = n;
      return 1;
    case FM1_JSON_OBJ_END:
    case FM1_JSON_ARR_END:
      --t->sp;
      return 1;
    case FM1_JSON_STR:
      if (ev->first) {
        t->str = node_new(t, FM1_JSON_STR);
        if (!t->str) return 0;
      }
      t->str->s = (char *)realloc(t->str->s, t->str->sn + ev->n + 1);
      if (!t->str->s) return 0;
      memcpy(t->str->s + t->str->sn, ev->s, ev->n);
      t->str->sn += ev->n;
      return 1;
    default:
      n = node_new(t, ev->type);
      if (!n) return 0;
      if (ev->type == FM1_JSON_NUM) {
        n->s = (char *)malloc(ev->n + 1);
        if (!n->s) return 0;
        memcpy(n->s, ev->s, ev->n);
        n->sn = ev->n;
      }
      return 1;
  }
}

static void node_free(node_t *n) {
  size_t i;
  if (!n) return;
  for (i = 0; i < n->nkids; ++i) node_free(n->kids[i]);
  free(n->kids);
  free(n->key);
  free(n->s);
  free(n);
}

static int key_is(const node_t *n, const char *k) {
  return n->key && n->keyn == strlen(k) && memcmp(n->key, k, n->keyn) == 0;
}

static int rank(const node_t *n) {
  static const char *const first[] = { "$schema", "lunar", "kind", "pos", "engine", "version" };
  static const char *const units[] = { "sounds", "sound", "master", "chain", "rack" };
  size_t i;
  for (i = 0; i < sizeof(first) / sizeof(first[0]); ++i) {
    if (key_is(n, first[i])) return (int)i;
  }
  for (i = 0; i < sizeof(units) / sizeof(units[0]); ++i) {
    if (key_is(n, units[i])) return 10;
  }
  if (key_is(n, "mod") || key_is(n, "cables")) return 30;
  return 20;
}

static void node_sort(node_t *n) {
  size_t i, j;
  for (i = 0; i < n->nkids; ++i) node_sort(n->kids[i]);
  if (n->type != FM1_JSON_OBJ) return;
  for (i = 1; i < n->nkids; ++i) {             /* stable insertion sort by rank */
    node_t *x = n->kids[i];
    const int r = rank(x);
    for (j = i; j > 0 && rank(n->kids[j - 1]) > r; --j) n->kids[j] = n->kids[j - 1];
    n->kids[j] = x;
  }
}

static void put_json_str(buf_t *o, const char *s, size_t n) {
  static const char hx[] = "0123456789abcdef";
  size_t i;
  buf_put(o, "\"", 1);
  for (i = 0; i < n; ++i) {
    const unsigned char c = (unsigned char)s[i];
    if (c == '"' || c == '\\') { char e[2] = { '\\', (char)c }; buf_put(o, e, 2); }
    else if (c < 0x20) { char e[6] = { '\\', 'u', '0', '0', hx[c >> 4], hx[c & 15] }; buf_put(o, e, 6); }
    else buf_put(o, (const char *)&s[i], 1);
  }
  buf_put(o, "\"", 1);
}

static void node_write(const node_t *n, buf_t *o) {
  size_t i;
  switch (n->type) {
    case FM1_JSON_OBJ:
    case FM1_JSON_ARR:
      buf_put(o, n->type == FM1_JSON_OBJ ? "{" : "[", 1);
      for (i = 0; i < n->nkids; ++i) {
        if (i) buf_put(o, ",", 1);
        if (n->type == FM1_JSON_OBJ) {
          put_json_str(o, n->kids[i]->key, n->kids[i]->keyn);
          buf_put(o, ":", 1);
        }
        node_write(n->kids[i], o);
      }
      buf_put(o, n->type == FM1_JSON_OBJ ? "}" : "]", 1);
      break;
    case FM1_JSON_STR: put_json_str(o, n->s ? n->s : "", n->sn); break;
    case FM1_JSON_NUM: buf_put(o, n->s, n->sn); break;
    case FM1_JSON_TRUE: buf_put(o, "true", 4); break;
    case FM1_JSON_FALSE: buf_put(o, "false", 5); break;
    default: buf_put(o, "null", 4); break;
  }
}

/* The file's members in context order, or 0 (then the reader is given the
 * file as it is, and refuses it with its own report). */
static int reorder(const buf_t *in, buf_t *out) {
  tree_t t;
  fm1_json_t p;
  int ok;
  memset(&t, 0, sizeof(t));
  memset(out, 0, sizeof(*out));
  fm1_json_init(&p, tree_cb, &t);
  ok = fm1_json_feed(&p, in->b, in->n) && fm1_json_end(&p) && !t.oom && t.root;
  if (ok) {
    node_sort(t.root);
    node_write(t.root, out);
  }
  free(t.key);
  node_free(t.root);
  return ok;
}

/* ---- Reading any state file -------------------------------------------------- */
static int read_any(const fm1_state_names_t *nm, const buf_t *in, fm1_rec_sink_t sink, void *sctx,
                    fm1_state_report_t *rep, size_t pieces) {
  const int kind = fm1_state_sniff(in->b, in->n);
  if (kind == 1) return fm1_state_bin_read(mem_read, (void *)in, (uint32_t)in->n, sink, sctx, rep, 0);
  if (kind == 3) {
    rep->code = FM1_STATE_NOT_LUNAR;
    strcpy(rep->what, "a movy1 set: fm1-state from-movy1 makes it a state file");
    return 0;
  }
  if (pieces) {
    fm1_state_json_reader_t r;
    size_t off = 0;
    int ok = 1;
    fm1_state_json_begin(&r, nm, sink, sctx, rep);
    while (ok && off < in->n) {
      const size_t m = in->n - off < pieces ? in->n - off : pieces;
      ok = fm1_state_json_feed(&r, in->b + off, m);
      off += m;
    }
    return ok && fm1_state_json_end(&r);
  }
  return fm1_state_json_read(nm, mem_read, (void *)in, sink, sctx, rep);
}

/* Reads a file into the canonical JSON writer. `reord`: put a JSON file's
 * members in context order first. */
static int to_canon(const fm1_state_names_t *nm, const buf_t *in, int compact, int without, int reord,
                    buf_t *out, fm1_state_report_t *rep) {
  void *mem = calloc(1, fm1_state_json_writer_size());
  fm1_state_writer_t *w;
  buf_t sorted;
  const buf_t *src = in;
  int ok;
  memset(out, 0, sizeof(*out));
  memset(&sorted, 0, sizeof(sorted));
  if (!mem) return 0;
  if (reord && fm1_state_sniff(in->b, in->n) == 2 && reorder(in, &sorted)) src = &sorted;
  w = fm1_state_json_writer(mem, nm, compact, buf_put, out, rep);
  ok = read_any(nm, src, fm1_state_write, w, rep, 0);
  if (ok && rep->unknown && !without) {
    rep->code = FM1_STATE_UNKNOWN;
    snprintf(rep->what, sizeof(rep->what), "uses %s, which this build does not have (--without leaves it out)",
             rep->name);
    ok = 0;
  }
  free(mem);
  free(sorted.b);
  return ok;
}

/* ---- check: pass 1 ------------------------------------------------------------ */
typedef struct {
  const fm1_state_names_t *nm;
  fm1_state_report_t *rep;
  float rate;
  size_t ram;
  int mod;
  int refused;
} check_t;

static int check_sink(void *ctx, const fm1_rec_t *r) {
  check_t *c = (check_t *)ctx;
  if (r->type == FM1_REC_MOD) c->mod = 1;
  if (r->type == FM1_REC_UNIT && r->u.unit.id[0]) {
    const fm1_engine_t *e = fm1_state_engine(c->nm, r->role, r->u.unit.id);
    fm1_host_t at44 = { FM1_ENGINE_API_VERSION, (float)FM1_STATE_HZ, 64 };
    fm1_host_t here = { FM1_ENGINE_API_VERSION, c->rate, 64 };
    void *mem, *self;
    size_t n;
    if (!e) return 1;                       /* counted by the reader as unknown */
    c->ram += (e->instance_size(&at44) + 15u) & ~(size_t)15u;
    n = e->instance_size(&here);
    mem = calloc(1, n ? n + 16 : 16);
    if (!mem) return 0;
    self = e->create((void *)(((uintptr_t)mem + 15u) & ~(uintptr_t)15u), &here);
    if (self && e->destroy) e->destroy(self);
    free(mem);
    if (!self) {
      c->rep->code = FM1_STATE_RATE;
      snprintf(c->rep->what, sizeof(c->rep->what), "%s cannot run at %g Hz", e->name, (double)c->rate);
      snprintf(c->rep->name, sizeof(c->rep->name), "%s", e->id);
      return 0;
    }
  }
  return 1;
}

/* ---- diff ------------------------------------------------------------------------- */
typedef struct {
  const char *p;
  size_t n;
} line_t;

static size_t split_lines(const buf_t *b, line_t **out) {
  size_t i, start = 0, n = 0, cap = 64;
  line_t *l = (line_t *)malloc(cap * sizeof(line_t));
  for (i = 0; l && i < b->n; ++i) {
    if (b->b[i] == '\n') {
      if (n == cap) { cap *= 2; l = (line_t *)realloc(l, cap * sizeof(line_t)); if (!l) break; }
      l[n].p = (const char *)b->b + start;
      l[n].n = i - start;
      ++n;
      start = i + 1;
    }
  }
  *out = l;
  return n;
}

static int same_line(const line_t *a, const line_t *b) { return a->n == b->n && memcmp(a->p, b->p, a->n) == 0; }

static int diff(const buf_t *a, const buf_t *b) {
  line_t *x, *y;
  const size_t nx = split_lines(a, &x), ny = split_lines(b, &y);
  size_t i, j;
  unsigned *t;
  int differ = 0;
  if (!x || !y) return 2;
  t = (unsigned *)calloc((nx + 1) * (ny + 1), sizeof(unsigned));
  if (!t) return 2;
  for (i = nx; i-- > 0;) {
    for (j = ny; j-- > 0;) {
      t[i * (ny + 1) + j] = same_line(&x[i], &y[j]) ? t[(i + 1) * (ny + 1) + j + 1] + 1
                          : (t[(i + 1) * (ny + 1) + j] > t[i * (ny + 1) + j + 1] ? t[(i + 1) * (ny + 1) + j]
                                                                                 : t[i * (ny + 1) + j + 1]);
    }
  }
  i = j = 0;
  while (i < nx || j < ny) {
    if (i < nx && j < ny && same_line(&x[i], &y[j])) { ++i; ++j; continue; }
    differ = 1;
    if (j < ny && (i == nx || t[i * (ny + 1) + j + 1] >= t[(i + 1) * (ny + 1) + j])) {
      printf("+%zu: %.*s\n", j + 1, (int)y[j].n, y[j].p);
      ++j;
    } else {
      printf("-%zu: %.*s\n", i + 1, (int)x[i].n, x[i].p);
      ++i;
    }
  }
  if (!differ) printf("same\n");
  free(t);
  free(x);
  free(y);
  return differ;
}

/* ---- from-movy1 ---------------------------------------------------------------------- */
static int movy1_records(const buf_t *in, fm1_rec_sink_t sink, void *sctx) {
  fm1_rec_t r;
  size_t i, start = 0;
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_HEAD;
  r.u.head.kind = FM1_STATE_SET;
  r.u.head.major = FM1_STATE_MAJOR;
  if (!sink(sctx, &r)) return 0;
  for (i = 0; i < in->n; ++i) {
    if (in->b[i] != '\n') continue;
    memset(&r, 0, sizeof(r));
    r.type = FM1_REC_LINE;
    r.piece = FM1_REC_FIRST | FM1_REC_LAST;
    r.u.line.which = FM1_LINES_SET;
    r.u.line.s = (const char *)in->b + start;
    r.u.line.n = (uint32_t)(i - start);
    if (!sink(sctx, &r)) return 0;
    start = i + 1;
  }
  if (start != in->n) {
    fprintf(stderr, "a movy1 set ends with a line end\n");
    return 0;
  }
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_END;
  return sink(sctx, &r);
}

/* A binary set's lines back to text. */
typedef struct {
  buf_t *out;
  int kind;
} lines_t;

static int lines_sink(void *ctx, const fm1_rec_t *r) {
  lines_t *l = (lines_t *)ctx;
  if (r->type == FM1_REC_HEAD) l->kind = r->u.head.kind;
  if (r->type == FM1_REC_LINE) {
    buf_put(l->out, r->u.line.s, r->u.line.n);
    if (r->piece & FM1_REC_LAST) buf_put(l->out, "\n", 1);
  }
  return 1;
}

/* ---- num ---------------------------------------------------------------------------- */
static int num_tests(void) {
  char line[256];
  while (fgets(line, sizeof(line), stdin)) {
    size_t n = strlen(line);
    while (n && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = '\0';
    if (n < 3 || line[1] != ' ') { puts("?"); continue; }
    if (line[0] == 'f') {
      float a = 0.0f, b = 0.0f;
      const int sa = fm1_num_f32(line + 2, n - 2, &a), sb = fm1_num_f32_exact(line + 2, n - 2, &b);
      printf("%d %08x %d %08x\n", sa, (unsigned)fm1_num_bits(a), sb, (unsigned)fm1_num_bits(b));
    } else if (line[0] == 't') {
      char t[24];
      fm1_num_f32_text((uint32_t)strtoul(line + 2, NULL, 16), t);
      puts(t);
    } else if (line[0] == 'q') {
      int16_t q = 0;
      const int s = fm1_num_q14(line + 2, n - 2, &q);
      printf("%d %d\n", s, q);
    } else if (line[0] == 'p') {
      char t[16];
      fm1_num_q14_text(atoi(line + 2), t);
      puts(t);
    } else {
      puts("?");
    }
  }
  return 0;
}


/* ---- names: the tables a JSON file resolves against, exact ------------------
 * What tools/lunar_state.py (P1) reads to name and clamp values the way the
 * C reader does: every engine, MIDI effect and modulation kind with each
 * parameter's uid, name, abbreviation, range and default as canonical
 * float32 text, its entries and its pad role. SEAM(E2): fm1-render --meta,
 * the metadata export, replaces it for P1 once it lands. */
static void names_params(const fm1_param_t *p, unsigned n, const fm1_engine_t *e) {
  unsigned i;
  int k;
  char t[24];
  printf("[");
  for (i = 0; i < n; ++i) {
    printf(i ? ",{" : "{");
    printf("\"uid\":%u,\"name\":", p[i].uid);
    json_text(stdout, p[i].name);
    printf(",\"abbr\":");
    json_text(stdout, p[i].abbr ? p[i].abbr : "");
    printf(",\"type\":\"%s\"", p[i].type == FM1_PARAM_ENUM ? "enum" : "float");
    fm1_num_f32_text(fm1_num_bits(p[i].min), t);
    printf(",\"min\":\"%s\"", t);
    fm1_num_f32_text(fm1_num_bits(p[i].max), t);
    printf(",\"max\":\"%s\"", t);
    fm1_num_f32_text(fm1_num_bits(p[i].def), t);
    printf(",\"def\":\"%s\",\"focus\":%d", t, e ? fm1_state_param_focus(e, i) : 0);
    if (p[i].type == FM1_PARAM_ENUM && p[i].enum_names) {
      printf(",\"entries\":[");
      for (k = 0; k <= (int)(p[i].max - p[i].min); ++k) {
        if (k) printf(",");
        json_text(stdout, p[i].enum_names[k]);
      }
      printf("]");
    }
    printf("}");
  }
  printf("]");
}

static void names_ports(const fm1_port_t *p, unsigned n) {
  unsigned i;
  printf("[");
  for (i = 0; i < n; ++i) {
    if (i) printf(",");
    json_text(stdout, p[i].name);
  }
  printf("]");
}

static int names_dump(const fm1_state_names_t *nm) {
  size_t i;
  unsigned id;
  int first = 1;
  printf("{\"engines\":[");
  for (i = 0; i < nm->n_engines + nm->n_mfx; ++i) {
    const fm1_engine_t *e = i < nm->n_engines ? nm->engines[i] : &nm->mfx[i - nm->n_engines]->engine;
    printf(i ? ",{" : "{");
    printf("\"id\":");
    json_text(stdout, e->id);
    printf(",\"role\":\"%s\",\"pads\":%u,\"params\":",
           e->kind == FM1_KIND_SOUND ? "sound" : (e->kind == FM1_KIND_AUDIO_FX ? "fx" : "mfx"), e->pad_count);
    names_params(e->params, e->n_params, e);
    printf("}");
  }
  printf("],\"kinds\":[");
  for (i = 0; i < nm->n_kinds; ++i) {
    const fm1_mod_kind_t *k = nm->kinds[i];
    printf(i ? ",{" : "{");
    printf("\"id\":");
    json_text(stdout, k->id);
    printf(",\"params\":");
    names_params(k->params, k->n_params, NULL);
    printf(",\"outs\":");
    names_ports(k->out, k->n_out);
    printf(",\"gates\":");
    names_ports(k->gate_in, k->n_gate_in);
    printf("}");
  }
  printf("],\"sources\":[");
  for (id = 0; id < 64u; ++id) {
    const fm1_mod_source_info_t *si = nm->source ? nm->source(id) : NULL;
    if (!si) continue;
    printf(first ? "{" : ",{");
    first = 0;
    printf("\"id\":%u,\"name\":", id);
    json_text(stdout, si->name);
    printf("}");
  }
  printf("],\"host\":");
  names_params(nm->host, nm->n_host, NULL);
  printf("}\n");
  return 0;
}

static int nop_cb(void *ctx, const fm1_json_ev_t *ev) {
  (void)ctx;
  (void)ev;
  return 1;
}

static void usage(void) {
  fprintf(stderr,
          "usage: fm1-state canon FILE [-o OUT] [--compact] [--without]\n"
          "       fm1-state pack FILE [-o OUT] [--store] [--without]\n"
          "       fm1-state unpack FILE [-o OUT]\n"
          "       fm1-state from-movy1 FILE.movy1 [-o OUT]\n"
          "       fm1-state records FILE [--pieces N]\n"
          "       fm1-state check FILE [--rate HZ]\n"
          "       fm1-state diff A B\n"
          "       fm1-state json-check FILE\n"
          "       fm1-state names\n"
          "       fm1-state num < LINES\n");
}

int main(int argc, char **argv) {
  const char *cmd, *file = NULL, *file2 = NULL, *out_path = NULL;
  int compact = 0, without = 0, store = 0, i, ok;
  size_t pieces = 0;
  float rate = (float)FM1_STATE_HZ;
  fm1_state_names_t nm;
  fm1_state_report_t rep;
  buf_t in, out;
  if (argc < 2) { usage(); return 2; }
  cmd = argv[1];
  for (i = 2; i < argc; ++i) {
    const char *a = argv[i];
    if (strcmp(a, "-o") == 0 && i + 1 < argc) out_path = argv[++i];
    else if (strcmp(a, "--compact") == 0) compact = 1;
    else if (strcmp(a, "--without") == 0) without = 1;
    else if (strcmp(a, "--store") == 0) store = 1;
    else if (strcmp(a, "--pieces") == 0 && i + 1 < argc) pieces = (size_t)strtoul(argv[++i], NULL, 10);
    else if (strcmp(a, "--rate") == 0 && i + 1 < argc) rate = (float)atof(argv[++i]);
    else if (a[0] == '-' && a[1]) { usage(); return 2; }
    else if (!file) file = a;
    else if (!file2) file2 = a;
    else { usage(); return 2; }
  }
  if (strcmp(cmd, "num") == 0) return num_tests();
  if (strcmp(cmd, "names") == 0) {
    fm1_state_names_default(&nm);
    return names_dump(&nm);
  }
  if (!file) { usage(); return 2; }
  fm1_state_names_default(&nm);
  fm1_state_report_init(&rep);
  memset(&out, 0, sizeof(out));
  if (!read_file(file, &in)) return 2;

  if (strcmp(cmd, "json-check") == 0) {
    fm1_json_t p;
    fm1_json_init(&p, nop_cb, NULL);
    ok = fm1_json_feed(&p, in.b, in.n) && fm1_json_end(&p);
    if (!ok) fprintf(stderr, "%s at %u:%u\n", fm1_json_error(p.err), p.line, p.col);
    return ok ? 0 : 1;
  }
  if (strcmp(cmd, "canon") == 0 || strcmp(cmd, "unpack") == 0) {
    if (strcmp(cmd, "unpack") == 0 && fm1_state_sniff(in.b, in.n) != 1) {
      fprintf(stderr, "%s: not a binary state file\n", file);
      return 2;
    }
    if (fm1_state_sniff(in.b, in.n) == 1 && in.n >= 11 && in.b[10] == FM1_STATE_SET) {
      lines_t l;
      l.out = &out;
      l.kind = 0;
      ok = fm1_state_bin_read(mem_read, &in, (uint32_t)in.n, lines_sink, &l, &rep, 0);
    } else {
      ok = to_canon(&nm, &in, compact, without, 1, &out, &rep);
    }
    if (!ok) { print_report(stderr, &rep); return 1; }
    return write_out(out_path, &out) ? 0 : 2;
  }
  if (strcmp(cmd, "pack") == 0 || strcmp(cmd, "from-movy1") == 0) {
    buf_t canon;
    void *mem = calloc(1, fm1_state_bin_writer_size());
    static const uint8_t version[3] = { 0, 1, 0 };
    fm1_state_writer_t *w;
    if (!mem) return 3;
    w = fm1_state_bin_writer(mem, store ? 0u : FM1_STATE_BIN_DEFLATE, FM1_STATE_WRITER_DESKTOP, version,
                             buf_put, &out, &rep);
    if (strcmp(cmd, "from-movy1") == 0) {
      ok = movy1_records(&in, fm1_state_bin_write, w);
    } else {
      ok = to_canon(&nm, &in, 0, without, 1, &canon, &rep);
      if (ok) {
        fm1_state_report_t rep2;
        fm1_state_report_init(&rep2);
        ok = fm1_state_json_read(&nm, mem_read, &canon, fm1_state_bin_write, w, &rep2);
        if (!ok) rep = rep2;
      }
      free(canon.b);
    }
    free(mem);
    if (!ok) { print_report(stderr, &rep); return 1; }
    return write_out(out_path, &out) ? 0 : 2;
  }
  if (strcmp(cmd, "records") == 0) {
    fm1_state_printer_t p;
    fm1_state_printer_init(&p, file_put, stdout);
    ok = read_any(&nm, &in, fm1_state_print, &p, &rep, pieces);
    fflush(stdout);
    if (!ok) { print_report(stderr, &rep); return 1; }
    return 0;
  }
  if (strcmp(cmd, "check") == 0) {
    check_t c;
    memset(&c, 0, sizeof(c));
    c.nm = &nm;
    c.rep = &rep;
    c.rate = rate;
    ok = read_any(&nm, &in, check_sink, &c, &rep, 0);
    if (ok && c.mod) c.ram += (fm1_mod_size() + 15u) & ~(size_t)15u;
    if (ok && rep.unknown) {
      rep.code = FM1_STATE_UNKNOWN;
      snprintf(rep.what, sizeof(rep.what), "uses %s, which this build does not have", rep.name);
      ok = 0;
    }
    if (ok && c.ram > FM1_STATE_RAM_BUDGET) {
      rep.code = FM1_STATE_RAM;
      snprintf(rep.what, sizeof(rep.what), "needs %zu B of instances at 44,118 Hz; the budget is %u B",
               c.ram, FM1_STATE_RAM_BUDGET);
      ok = 0;
    }
    printf("{\"ram_instances\":%zu,\"ram_budget\":%u,\"report\":", c.ram, FM1_STATE_RAM_BUDGET);
    print_report(stdout, &rep);
    printf("}\n");
    return ok ? 0 : 1;
  }
  if (strcmp(cmd, "diff") == 0) {
    buf_t in2, a, b;
    fm1_state_report_t rep2;
    if (!file2 || !read_file(file2, &in2)) { usage(); return 2; }
    fm1_state_report_init(&rep2);
    if (!to_canon(&nm, &in, 0, 1, 1, &a, &rep)) { print_report(stderr, &rep); return 2; }
    if (!to_canon(&nm, &in2, 0, 1, 1, &b, &rep2)) { print_report(stderr, &rep2); return 2; }
    return diff(&a, &b);
  }
  usage();
  return 2;
}
