/* fm1_deflate.c -- raw deflate in and out (fm1_deflate.h). C99, no heap.
 * The inflater decodes canonical Huffman codes a bit at a time, as Mark
 * Adler's puff does (zlib's contrib/puff, the zlib licence; this is our own
 * code after its method). MIT licence. */
#include "fm1_deflate.h"

#include <string.h>

static const uint16_t kLenBase[29] = { 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
                                       35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258 };
static const uint8_t kLenExtra[29] = { 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
                                       3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0 };
static const uint16_t kDistBase[30] = { 1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
                                        257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
                                        8193, 12289, 16385, 24577 };
static const uint8_t kDistExtra[30] = { 0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
                                        7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13 };

enum { Z_HEADER = 0, Z_STORED, Z_HUFF, Z_DONE };

/* ---- Inflate ------------------------------------------------------------------- */
void fm1_inflate_init(fm1_inflate_t *z, fm1_inflate_src_t rd, void *ctx, uint32_t off, uint32_t len,
                      uint32_t out_len) {
  memset(z, 0, offsetof(fm1_inflate_t, lcount));
  z->rd = rd;
  z->ctx = ctx;
  z->in_off = off;
  z->in_end = off + len;
  z->out_cap = out_len;
  z->state = Z_HEADER;
}

static int in_byte(fm1_inflate_t *z, uint32_t *b) {
  if (z->in_pos == z->in_len) {
    uint32_t want = z->in_end - z->in_off;
    if (want == 0) { z->err = 1; return 0; }
    if (want > sizeof(z->inbuf)) want = sizeof(z->inbuf);
    z->in_len = z->rd(z->ctx, z->in_off, z->inbuf, want);
    if (z->in_len == 0) { z->err = 1; return 0; }
    z->in_off += z->in_len;
    z->in_pos = 0;
  }
  *b = z->inbuf[z->in_pos++];
  return 1;
}

static int bits(fm1_inflate_t *z, unsigned need, uint32_t *out) {
  while (z->bitcnt < need) {
    uint32_t b;
    if (!in_byte(z, &b)) return 0;
    z->bitbuf |= b << z->bitcnt;
    z->bitcnt += 8;
  }
  *out = z->bitbuf & ((need == 32u) ? 0xFFFFFFFFu : ((1u << need) - 1u));
  z->bitbuf = need == 32u ? 0 : z->bitbuf >> need;
  z->bitcnt -= need;
  return 1;
}

/* Canonical decode: one bit at a time, MSB of the code first. */
static int decode(fm1_inflate_t *z, const uint16_t *count, const uint16_t *sym, int *out) {
  int code = 0, first = 0, index = 0, len;
  for (len = 1; len < 16; ++len) {
    uint32_t b;
    int c;
    if (!bits(z, 1, &b)) return 0;
    code |= (int)b;
    c = count[len];
    if (code - c < first) {
      *out = sym[index + (code - first)];
      return 1;
    }
    index += c;
    first += c;
    first <<= 1;
    code <<= 1;
  }
  z->err = 1;
  return 0;
}

/* Builds count/sym from code lengths; 0 if over-subscribed (an incomplete
 * code is allowed, as RFC 1951 allows a single distance code). */
static int build(uint16_t *count, uint16_t *sym, const uint8_t *lens, int n) {
  uint16_t offs[16];
  int i, left = 1;
  for (i = 0; i < 16; ++i) count[i] = 0;
  for (i = 0; i < n; ++i) count[lens[i]]++;
  if (count[0] == n) return 1;
  for (i = 1; i < 16; ++i) {
    left <<= 1;
    left -= count[i];
    if (left < 0) return 0;
  }
  offs[1] = 0;
  for (i = 1; i < 15; ++i) offs[i + 1] = (uint16_t)(offs[i] + count[i]);
  for (i = 0; i < n; ++i) {
    if (lens[i]) sym[offs[lens[i]]++] = (uint16_t)i;
  }
  return 1;
}

static int fixed_tables(fm1_inflate_t *z) {
  uint8_t lens[288];
  int i;
  for (i = 0; i < 144; ++i) lens[i] = 8;
  for (; i < 256; ++i) lens[i] = 9;
  for (; i < 280; ++i) lens[i] = 7;
  for (; i < 288; ++i) lens[i] = 8;
  build(z->lcount, z->lsym, lens, 288);
  for (i = 0; i < 30; ++i) lens[i] = 5;
  build(z->dcount, z->dsym, lens, 30);
  return 1;
}

static int dynamic_tables(fm1_inflate_t *z) {
  static const uint8_t order[19] = { 16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15 };
  uint8_t lens[320];
  uint32_t nlen, ndist, ncode, v;
  int i, idx;
  if (!bits(z, 5, &nlen) || !bits(z, 5, &ndist) || !bits(z, 4, &ncode)) return 0;
  nlen += 257;
  ndist += 1;
  ncode += 4;
  if (nlen > 286 || ndist > 30) { z->err = 1; return 0; }
  for (i = 0; i < 19; ++i) lens[order[i]] = 0;
  for (i = 0; i < (int)ncode; ++i) {
    if (!bits(z, 3, &v)) return 0;
    lens[order[i]] = (uint8_t)v;
  }
  if (!build(z->lcount, z->lsym, lens, 19)) { z->err = 1; return 0; }
  idx = 0;
  while (idx < (int)(nlen + ndist)) {
    int sym, len = 0;
    uint32_t rep;
    if (!decode(z, z->lcount, z->lsym, &sym)) return 0;
    if (sym < 16) {
      lens[idx++] = (uint8_t)sym;
      continue;
    }
    if (sym == 16) {
      if (idx == 0) { z->err = 1; return 0; }
      len = lens[idx - 1];
      if (!bits(z, 2, &rep)) return 0;
      rep += 3;
    } else if (sym == 17) {
      if (!bits(z, 3, &rep)) return 0;
      rep += 3;
    } else {
      if (!bits(z, 7, &rep)) return 0;
      rep += 11;
    }
    if (idx + (int)rep > (int)(nlen + ndist)) { z->err = 1; return 0; }
    while (rep--) lens[idx++] = (uint8_t)len;
  }
  if (lens[256] == 0) { z->err = 1; return 0; }
  if (!build(z->lcount, z->lsym, lens, (int)nlen)) { z->err = 1; return 0; }
  if (!build(z->dcount, z->dsym, lens + nlen, (int)ndist)) { z->err = 1; return 0; }
  return 1;
}

static int put_out(fm1_inflate_t *z, uint8_t c, uint8_t *out, uint32_t *k) {
  if (z->out_total >= z->out_cap) { z->err = 1; return 0; }
  z->window[z->out_total & (FM1_DEFLATE_WINDOW - 1u)] = c;
  ++z->out_total;
  out[(*k)++] = c;
  return 1;
}

uint32_t fm1_inflate_read(fm1_inflate_t *z, uint8_t *out, uint32_t n) {
  uint32_t k = 0, v;
  while (k < n && !z->err) {
    if (z->match_len) {
      const uint8_t c = z->window[(z->out_total - z->match_dist) & (FM1_DEFLATE_WINDOW - 1u)];
      if (!put_out(z, c, out, &k)) break;
      --z->match_len;
      continue;
    }
    switch (z->state) {
      case Z_HEADER:
        if (z->final) { z->state = Z_DONE; break; }
        if (!bits(z, 1, &v)) break;
        z->final = (uint8_t)v;
        if (!bits(z, 2, &v)) break;
        if (v == 0) {
          uint32_t lo, hi;
          z->bitbuf = 0;
          z->bitcnt = 0;
          if (!in_byte(z, &lo) || !in_byte(z, &hi)) break;
          z->stored_left = lo | (hi << 8);
          if (!in_byte(z, &lo) || !in_byte(z, &hi)) break;
          if ((lo | (hi << 8)) != (~z->stored_left & 0xFFFFu)) { z->err = 1; break; }
          z->state = Z_STORED;
        } else if (v == 1) {
          fixed_tables(z);
          z->state = Z_HUFF;
        } else if (v == 2) {
          if (!dynamic_tables(z)) { z->err = 1; break; }
          z->state = Z_HUFF;
        } else {
          z->err = 1;
        }
        break;
      case Z_STORED:
        if (!z->stored_left) { z->state = Z_HEADER; break; }
        if (!in_byte(z, &v)) break;
        if (!put_out(z, (uint8_t)v, out, &k)) break;
        --z->stored_left;
        break;
      case Z_HUFF: {
        int sym;
        if (!decode(z, z->lcount, z->lsym, &sym)) break;
        if (sym < 256) {
          put_out(z, (uint8_t)sym, out, &k);
        } else if (sym == 256) {
          z->state = Z_HEADER;
        } else {
          uint32_t extra, len, dist;
          int ds;
          sym -= 257;
          if (sym >= 29) { z->err = 1; break; }
          if (!bits(z, kLenExtra[sym], &extra)) break;
          len = kLenBase[sym] + extra;
          if (!decode(z, z->dcount, z->dsym, &ds)) break;
          if (ds >= 30) { z->err = 1; break; }
          if (!bits(z, kDistExtra[ds], &extra)) break;
          dist = kDistBase[ds] + extra;
          if (dist > FM1_DEFLATE_WINDOW || dist > z->out_total) { z->err = 1; break; }
          z->match_len = len;
          z->match_dist = dist;
        }
        break;
      }
      default:
        return k;
    }
    if (z->state == Z_DONE) break;
  }
  return z->err ? 0 : k;
}

int fm1_inflate_done(const fm1_inflate_t *z) {
  return !z->err && z->final && z->state != Z_HUFF && z->state != Z_STORED && !z->match_len &&
         z->out_total == z->out_cap;
}

/* ---- Deflate --------------------------------------------------------------------- */
typedef struct {
  uint8_t *out;
  size_t cap, n;
  uint32_t bitbuf, bitcnt;
  int over;
} bw_t;

static void put_bits(bw_t *b, uint32_t v, unsigned n) {
  b->bitbuf |= v << b->bitcnt;
  b->bitcnt += n;
  while (b->bitcnt >= 8) {
    if (b->n < b->cap) b->out[b->n] = (uint8_t)b->bitbuf;
    else b->over = 1;
    ++b->n;
    b->bitbuf >>= 8;
    b->bitcnt -= 8;
  }
}

/* A Huffman code, MSB first, into the LSB-first stream. */
static void put_code(bw_t *b, uint32_t code, unsigned len) {
  uint32_t r = 0;
  unsigned i;
  for (i = 0; i < len; ++i) r |= ((code >> i) & 1u) << (len - 1u - i);
  put_bits(b, r, len);
}

static void lit(bw_t *b, unsigned c) {
  if (c < 144) put_code(b, 0x30u + c, 8);
  else if (c < 256) put_code(b, 0x190u + (c - 144u), 9);
  else if (c < 280) put_code(b, c - 256u, 7);
  else put_code(b, 0xC0u + (c - 280u), 8);
}

static void match(bw_t *b, unsigned len, unsigned dist) {
  unsigned s = 0;
  while (s < 28 && kLenBase[s + 1] <= len) ++s;
  lit(b, 257u + s);
  if (kLenExtra[s]) put_bits(b, len - kLenBase[s], kLenExtra[s]);
  s = 0;
  while (s < 29 && kDistBase[s + 1] <= dist) ++s;
  put_code(b, s, 5);
  if (kDistExtra[s]) put_bits(b, dist - kDistBase[s], kDistExtra[s]);
}

static unsigned hash3(const uint8_t *p) {
  return (((unsigned)p[0] << 8) ^ ((unsigned)p[1] << 4) ^ (unsigned)p[2]) & 4095u;
}

size_t fm1_deflate(const uint8_t *in, size_t n, uint8_t *out, size_t cap, void *scratch) {
  int32_t *head = (int32_t *)scratch, *prev = head + 4096;
  bw_t b;
  size_t i = 0, p;
  for (p = 0; p < 4096u; ++p) { head[p] = -1; prev[p] = -1; }
  memset(&b, 0, sizeof(b));
  b.out = out;
  b.cap = cap;
  put_bits(&b, 1, 1);         /* final */
  put_bits(&b, 1, 2);         /* fixed Huffman */
  while (i < n) {
    size_t best = 0, dist = 0;
    if (i + 3 <= n) {
      int32_t j = head[hash3(in + i)];
      int steps = 0;
      while (j >= 0 && i - (size_t)j <= 4096u && steps < 128) {
        size_t l = 0, lim = n - i < 258u ? n - i : 258u;
        while (l < lim && in[(size_t)j + l] == in[i + l]) ++l;
        if (l > best) {
          best = l;
          dist = i - (size_t)j;
          if (l == 258u) break;
        }
        j = prev[(size_t)j & 4095u];
        ++steps;
      }
    }
    if (best >= 3) {
      size_t k;
      match(&b, (unsigned)best, (unsigned)dist);
      for (k = 0; k < best; ++k) {
        if (i + k + 3 <= n) {
          const unsigned h = hash3(in + i + k);
          prev[(i + k) & 4095u] = head[h];
          head[h] = (int32_t)(i + k);
        }
      }
      i += best;
    } else {
      lit(&b, in[i]);
      if (i + 3 <= n) {
        const unsigned h = hash3(in + i);
        prev[i & 4095u] = head[h];
        head[h] = (int32_t)i;
      }
      ++i;
    }
  }
  lit(&b, 256);
  if (b.bitcnt) put_bits(&b, 0, 8u - b.bitcnt);
  return b.over ? 0 : b.n;
}
