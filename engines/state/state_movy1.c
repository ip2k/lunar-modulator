/* state_movy1.c -- movy1 lines as the binary container's items (the SEQS
 * and CLIP chunks; notes/2026-10-06-state-files.md §8.3).
 *
 * A line the sequencer core writes (seq_persist.c's export) becomes a typed
 * item: its fields in fixed widths, 8 bytes a note and 3 a lock, as design A
 * laid them out. Any other line (a hand edit's extra space, a number past an
 * item's width, a line kind this build does not type: E1's dq, se and sn
 * among them until they get items) rides as a raw item, its bytes as they
 * are. The encoder formats every typed item back and compares it with the
 * line, so movy1 -> items -> movy1 is byte-identical by construction.
 *
 * Item layout: u8 tag, then
 *   0x01 raw     u16 n, n bytes
 *   0x02 movy1
 *   0x03 bpm     u32          0x04 swing  u32          0x05 link  u8
 *   0x06 sg      u16 n, n x u8
 *   0x07 tk      u8 track, u8 active, u8 muted
 *   0x08 pm      u8 track, u8 pad            0x09 ps  u8 track, u8 pad
 *   0x0A au      u8 track, u8 lane, u8 base, u8 n, n bytes of label
 *   0x0B rt      u8 track, u8 kind, u8 index
 *   0x0C cl      u8 track, u8 slot, u16 length, u16 loop start, u16 n,
 *                n x { u16 tick, u16 gate, u8 pitch, u8 velocity, u16 step }
 *   0x0D cp      u8 track, u8 slot, u8 num, u8 den, i8 transpose, u8 quant
 *   0x0E lk      u8 track, u8 slot, u16 n, n x { u8 lane, u8 step, u8 value }
 *   0x0F tg      u8 track, u8 slot, u16 n, n x { u8 step, i8 lane, u8 prob,
 *                u8 a, u8 b, u8 inv }
 * Little-endian. C99, no heap, no stdio. MIT licence. */
#include "state_movy1.h"

#include <string.h>

/* ---- Writing bytes ---------------------------------------------------------------- */
typedef struct {
  uint8_t *b;
  size_t cap, n;
  int over;
} out_t;

static void ob(out_t *o, unsigned v) {
  if (o->n < o->cap) o->b[o->n] = (uint8_t)v;
  else o->over = 1;
  ++o->n;
}
static void o16(out_t *o, unsigned v) { ob(o, v & 0xFFu); ob(o, (v >> 8) & 0xFFu); }
static void o32(out_t *o, uint32_t v) { o16(o, v & 0xFFFFu); o16(o, v >> 16); }

/* ---- Strict tokens ------------------------------------------------------------------- */
typedef struct {
  const char *p;
  size_t n;
} tok_t;

/* Splits at single spaces exactly: "a  b" gives an empty token between. */
static int split(const char *s, size_t n, char sep, tok_t *t, int max) {
  int k = 0;
  size_t i, start = 0;
  for (i = 0; i <= n; ++i) {
    if (i == n || s[i] == sep) {
      if (k == max) return -1;
      t[k].p = s + start;
      t[k].n = i - start;
      ++k;
      start = i + 1;
    }
  }
  return k;
}

/* A plain decimal: digits, no sign, no leading zero, at most max. */
static int num(tok_t t, uint32_t max, uint32_t *out) {
  size_t i;
  uint64_t v = 0;
  if (t.n == 0 || t.n > 10 || (t.n > 1 && t.p[0] == '0')) return 0;
  for (i = 0; i < t.n; ++i) {
    if (t.p[i] < '0' || t.p[i] > '9') return 0;
    v = v * 10u + (uint64_t)(t.p[i] - '0');
  }
  if (v > max) return 0;
  *out = (uint32_t)v;
  return 1;
}

static int snum(tok_t t, int32_t lo, int32_t hi, int32_t *out) {
  uint32_t a;
  if (t.n > 0 && t.p[0] == '-') {
    tok_t u;
    u.p = t.p + 1;
    u.n = t.n - 1;
    if (!num(u, (uint32_t)(-(int64_t)lo), &a) || a == 0) return 0;
    *out = -(int32_t)a;
    return 1;
  }
  if (!num(t, (uint32_t)hi, &a)) return 0;
  *out = (int32_t)a;
  return 1;
}

static int is(tok_t t, const char *s) { return t.n == strlen(s) && memcmp(t.p, s, t.n) == 0; }

/* ---- Typed items from a line -------------------------------------------------------------- */
#define MAXTOK 8

static int typed(const char *s, size_t n, out_t *o) {
  tok_t t[MAXTOK];
  int k;
  uint32_t a, b, c, d;
  int32_t x;
  if (n == 5 && memcmp(s, "movy1", 5) == 0) { ob(o, 0x02); return 1; }
  k = split(s, n, ' ', t, MAXTOK);
  if (k < 1) {
    /* "sg" with many entries: more tokens than MAXTOK */
    if (n >= 3 && memcmp(s, "sg ", 3) == 0) {
      size_t i, start = 3;
      uint32_t cnt = 0;
      size_t at;
      ob(o, 0x06);
      at = o->n;
      o16(o, 0);
      for (i = 3; i <= n; ++i) {
        if (i == n || s[i] == ' ') {
          tok_t u;
          u.p = s + start;
          u.n = i - start;
          if (!num(u, 255, &a)) return 0;
          ob(o, a);
          ++cnt;
          start = i + 1;
        }
      }
      if (cnt > 65535u) return 0;
      if (at + 1 < o->cap) { o->b[at] = (uint8_t)cnt; o->b[at + 1] = (uint8_t)(cnt >> 8); }
      return 1;
    }
    return 0;
  }
  if (is(t[0], "bpm") && k == 2 && num(t[1], 0xFFFFFFFFu, &a)) { ob(o, 0x03); o32(o, a); return 1; }
  if (is(t[0], "swing") && k == 2 && num(t[1], 0xFFFFFFFFu, &a)) { ob(o, 0x04); o32(o, a); return 1; }
  if (is(t[0], "link") && k == 2 && num(t[1], 255, &a)) { ob(o, 0x05); ob(o, a); return 1; }
  if (is(t[0], "sg") && k >= 2) {
    int i;
    ob(o, 0x06);
    o16(o, (unsigned)(k - 1));
    for (i = 1; i < k; ++i) {
      if (!num(t[i], 255, &a)) return 0;
      ob(o, a);
    }
    return 1;
  }
  if (is(t[0], "tk") && k == 4 && num(t[1], 255, &a) && num(t[2], 255, &b) && num(t[3], 255, &c)) {
    ob(o, 0x07); ob(o, a); ob(o, b); ob(o, c);
    return 1;
  }
  if ((is(t[0], "pm") || is(t[0], "ps")) && k == 3 && num(t[1], 255, &a) && num(t[2], 255, &b)) {
    ob(o, t[0].p[1] == 'm' ? 0x08 : 0x09); ob(o, a); ob(o, b);
    return 1;
  }
  if (is(t[0], "au") && k >= 4 && num(t[1], 255, &a) && num(t[2], 255, &b) && num(t[3], 255, &c)) {
    /* the label is the rest of the line after the fourth space */
    const char *lab = t[3].p + t[3].n + 1;
    const size_t ln = (size_t)(s + n - lab);
    size_t i;
    if (k == 4 || ln > 255u) return 0;
    for (i = 0; i < ln; ++i) {
      if (lab[i] == ' ') return 0;
    }
    ob(o, 0x0A); ob(o, a); ob(o, b); ob(o, c); ob(o, (unsigned)ln);
    for (i = 0; i < ln; ++i) ob(o, (unsigned char)lab[i]);
    return 1;
  }
  if (is(t[0], "rt") && k == 4 && num(t[1], 255, &a) && num(t[2], 255, &b) && num(t[3], 255, &c)) {
    ob(o, 0x0B); ob(o, a); ob(o, b); ob(o, c);
    return 1;
  }
  if (is(t[0], "cp") && k == 7 && num(t[1], 255, &a) && num(t[2], 255, &b) && num(t[3], 255, &c) &&
      num(t[4], 255, &d) && snum(t[5], -128, 127, &x)) {
    uint32_t q;
    if (!num(t[6], 255, &q)) return 0;
    ob(o, 0x0D); ob(o, a); ob(o, b); ob(o, c); ob(o, d); ob(o, (unsigned)(x & 0xFF)); ob(o, q);
    return 1;
  }
  if (is(t[0], "cl") && k == 6 && num(t[1], 255, &a) && num(t[2], 255, &b) && num(t[3], 65535, &c) &&
      num(t[4], 65535, &d)) {
    tok_t list = t[5];
    size_t at, i, start = 0;
    uint32_t cnt = 0;
    ob(o, 0x0C); ob(o, a); ob(o, b); o16(o, c); o16(o, d);
    at = o->n;
    o16(o, 0);
    if (list.n) {
      for (i = 0; i <= list.n; ++i) {
        if (i == list.n || list.p[i] == ';') {
          tok_t f[6];
          uint32_t v[5];
          int nf = split(list.p + start, i - start, ':', f, 6), j;
          static const uint32_t kMax[5] = { 65535, 65535, 255, 255, 65535 };
          if (nf != 5) return 0;
          for (j = 0; j < 5; ++j) {
            if (!num(f[j], kMax[j], &v[j])) return 0;
          }
          o16(o, v[0]); o16(o, v[1]); ob(o, v[2]); ob(o, v[3]); o16(o, v[4]);
          ++cnt;
          start = i + 1;
        }
      }
    }
    if (cnt > 65535u) return 0;
    if (at + 1 < o->cap) { o->b[at] = (uint8_t)cnt; o->b[at + 1] = (uint8_t)(cnt >> 8); }
    return 1;
  }
  if ((is(t[0], "lk") || is(t[0], "tg")) && k == 4 && num(t[1], 255, &a) && num(t[2], 255, &b) && t[3].n) {
    const int lk = t[0].p[0] == 'l';
    tok_t list = t[3];
    size_t at, i, start = 0;
    uint32_t cnt = 0;
    ob(o, lk ? 0x0E : 0x0F); ob(o, a); ob(o, b);
    at = o->n;
    o16(o, 0);
    for (i = 0; i <= list.n; ++i) {
      if (i == list.n || list.p[i] == ';') {
        tok_t f[7];
        int nf = split(list.p + start, i - start, ':', f, 7);
        if (lk) {
          uint32_t l, st, v;
          if (nf != 3 || !num(f[0], 255, &l) || !num(f[1], 255, &st) || !num(f[2], 255, &v)) return 0;
          ob(o, l); ob(o, st); ob(o, v);
        } else {
          uint32_t st, p, aa, bb, inv;
          int32_t ln;
          if (nf != 6 || !num(f[0], 255, &st) || !snum(f[1], -128, 127, &ln) || !num(f[2], 255, &p) ||
              !num(f[3], 255, &aa) || !num(f[4], 255, &bb) || !num(f[5], 255, &inv)) {
            return 0;
          }
          ob(o, st); ob(o, (unsigned)(ln & 0xFF)); ob(o, p); ob(o, aa); ob(o, bb); ob(o, inv);
        }
        ++cnt;
        start = i + 1;
      }
    }
    if (cnt > 65535u) return 0;
    if (at + 1 < o->cap) { o->b[at] = (uint8_t)cnt; o->b[at + 1] = (uint8_t)(cnt >> 8); }
    return 1;
  }
  return 0;
}

/* ---- Formatting items back to text ---------------------------------------------------------- */
typedef struct {
  const uint8_t *b;           /* a buffer, or NULL for get */
  size_t n, i;
  fm1_movy1_pull_t get;
  void *gctx;
  int bad;
} in_t;

static unsigned ib(in_t *in) {
  uint8_t c;
  if (in->b) {
    if (in->i >= in->n) { in->bad = 1; return 0; }
    return in->b[in->i++];
  }
  if (in->bad || !in->get(in->gctx, &c)) { in->bad = 1; return 0; }
  ++in->i;
  return c;
}
static unsigned i16(in_t *in) { const unsigned lo = ib(in); return lo | (ib(in) << 8); }
static uint32_t i32(in_t *in) { const uint32_t lo = i16(in); return lo | ((uint32_t)i16(in) << 16); }

typedef struct {
  fm1_movy1_text_fn fn;
  void *ctx;
  char buf[64];
  size_t n;
  size_t total;
  int first, stop;
} txt_t;

static void tflush(txt_t *t, int last) {
  if (t->stop) return;
  if (!t->n && !last) return;
  if (!t->fn(t->ctx, t->buf, t->n, t->first, last)) t->stop = 1;
  t->first = 0;
  t->n = 0;
}

static void tc(txt_t *t, char c) {
  if (t->n == sizeof(t->buf)) tflush(t, 0);
  t->buf[t->n++] = c;
  ++t->total;
}
static void ts(txt_t *t, const char *s) { while (*s) tc(t, *s++); }
static void tu(txt_t *t, uint32_t v) {
  char d[12];
  int k = 0;
  do { d[k++] = (char)('0' + v % 10u); v /= 10u; } while (v);
  while (k) tc(t, d[--k]);
}
static void ti(txt_t *t, int32_t v) {
  if (v < 0) { tc(t, '-'); tu(t, (uint32_t)(-(int64_t)v)); }
  else tu(t, (uint32_t)v);
}

/* One item at in->i, formatted; 0 on a malformed item. */
static int item_text(in_t *in, txt_t *t) {
  const unsigned tag = ib(in);
  unsigned a, b, c, n, i;
  if (in->bad) return 0;
  switch (tag) {
    case 0x01:
      n = i16(in);
      if (n > FM1_MOVY1_LINE_MAX) return 0;
      for (i = 0; i < n && !in->bad; ++i) tc(t, (char)ib(in));
      break;
    case 0x02: ts(t, "movy1"); break;
    case 0x03: ts(t, "bpm "); tu(t, i32(in)); break;
    case 0x04: ts(t, "swing "); tu(t, i32(in)); break;
    case 0x05: ts(t, "link "); tu(t, ib(in)); break;
    case 0x06:
      n = i16(in);
      ts(t, "sg");
      for (i = 0; i < n && !in->bad; ++i) { tc(t, ' '); tu(t, ib(in)); }
      break;
    case 0x07: ts(t, "tk "); a = ib(in); b = ib(in); c = ib(in); tu(t, a); tc(t, ' '); tu(t, b); tc(t, ' '); tu(t, c); break;
    case 0x08:
    case 0x09:
      ts(t, tag == 0x08 ? "pm " : "ps "); a = ib(in); b = ib(in); tu(t, a); tc(t, ' '); tu(t, b);
      break;
    case 0x0A:
      ts(t, "au "); a = ib(in); b = ib(in); c = ib(in); n = ib(in);
      tu(t, a); tc(t, ' '); tu(t, b); tc(t, ' '); tu(t, c); tc(t, ' ');
      for (i = 0; i < n && !in->bad; ++i) tc(t, (char)ib(in));
      break;
    case 0x0B: ts(t, "rt "); a = ib(in); b = ib(in); c = ib(in); tu(t, a); tc(t, ' '); tu(t, b); tc(t, ' '); tu(t, c); break;
    case 0x0C: {
      unsigned len, ls;
      ts(t, "cl "); a = ib(in); b = ib(in); len = i16(in); ls = i16(in); n = i16(in);
      tu(t, a); tc(t, ' '); tu(t, b); tc(t, ' '); tu(t, len); tc(t, ' '); tu(t, ls); tc(t, ' ');
      for (i = 0; i < n && !in->bad && !t->stop; ++i) {
        unsigned tick = i16(in), gate = i16(in), p = ib(in), v = ib(in), st = i16(in);
        if (i) tc(t, ';');
        tu(t, tick); tc(t, ':'); tu(t, gate); tc(t, ':'); tu(t, p); tc(t, ':'); tu(t, v); tc(t, ':'); tu(t, st);
      }
      break;
    }
    case 0x0D:
      ts(t, "cp "); a = ib(in); b = ib(in); tu(t, a); tc(t, ' '); tu(t, b); tc(t, ' ');
      a = ib(in); b = ib(in); tu(t, a); tc(t, ' '); tu(t, b); tc(t, ' ');
      ti(t, (int8_t)(uint8_t)ib(in)); tc(t, ' '); tu(t, ib(in));
      break;
    case 0x0E:
    case 0x0F:
      ts(t, tag == 0x0E ? "lk " : "tg "); a = ib(in); b = ib(in); n = i16(in);
      tu(t, a); tc(t, ' '); tu(t, b); tc(t, ' ');
      for (i = 0; i < n && !in->bad && !t->stop; ++i) {
        if (i) tc(t, ';');
        if (tag == 0x0E) {
          a = ib(in); b = ib(in); c = ib(in);
          tu(t, a); tc(t, ':'); tu(t, b); tc(t, ':'); tu(t, c);
        } else {
          unsigned st = ib(in);
          int ln = (int8_t)(uint8_t)ib(in);
          unsigned p = ib(in), aa = ib(in), bb = ib(in), inv = ib(in);
          tu(t, st); tc(t, ':'); ti(t, ln); tc(t, ':'); tu(t, p); tc(t, ':'); tu(t, aa); tc(t, ':');
          tu(t, bb); tc(t, ':'); tu(t, inv);
        }
      }
      break;
    default:
      return 0;
  }
  return !in->bad;
}

/* ---- The comparison the encoder makes ----------------------------------------------------------- */
typedef struct {
  const char *line;
  size_t n, at;
  int same;
} cmp_t;

static int cmp_piece(void *ctx, const char *s, size_t n, int first, int last) {
  cmp_t *c = (cmp_t *)ctx;
  (void)first;
  (void)last;
  if (c->at + n > c->n || memcmp(c->line + c->at, s, n) != 0) {
    c->same = 0;
    return 0;
  }
  c->at += n;
  return 1;
}

size_t fm1_movy1_encode(const char *line, size_t n, uint8_t *out, size_t cap) {
  out_t o;
  o.b = out;
  o.cap = cap;
  o.n = 0;
  o.over = 0;
  if (typed(line, n, &o) && !o.over) {
    in_t in;
    txt_t t;
    cmp_t c;
    c.line = line;
    c.n = n;
    c.at = 0;
    c.same = 1;
    memset(&t, 0, sizeof(t));
    t.fn = cmp_piece;
    t.ctx = &c;
    t.first = 1;
    memset(&in, 0, sizeof(in));
    in.b = out;
    in.n = o.n;
    if (item_text(&in, &t) && in.i == o.n) {
      tflush(&t, 1);
      if (c.same && c.at == n) return o.n;
    }
  }
  /* Raw. */
  o.n = 0;
  o.over = 0;
  if (n > 65535u) return 0;
  ob(&o, 0x01);
  o16(&o, (unsigned)n);
  {
    size_t i;
    for (i = 0; i < n; ++i) ob(&o, (unsigned char)line[i]);
  }
  return o.over ? 0 : o.n;
}

int fm1_movy1_decode(fm1_movy1_pull_t get, void *gctx, fm1_movy1_text_fn fn, void *ctx) {
  in_t in;
  txt_t t;
  memset(&in, 0, sizeof(in));
  in.get = get;
  in.gctx = gctx;
  memset(&t, 0, sizeof(t));
  t.fn = fn;
  t.ctx = ctx;
  t.first = 1;
  if (!item_text(&in, &t) || t.total > FM1_MOVY1_LINE_MAX) return t.stop ? -1 : 0;
  tflush(&t, 1);
  return t.stop ? -1 : 1;
}
