/* fm1_num.c -- exact numbers for the state files (fm1_num.h). C99, no heap,
 * no libm, no stdio. MIT licence. */
#include "fm1_num.h"

#include <float.h>
#include <string.h>

/* ---- Big integers: little-endian 32-bit limbs, fixed size ------------------
 * The largest product the routines below form is about 2^450 (a 31-digit
 * significand times 10^76 or 2^150), so 24 limbs (768 bits) hold every one;
 * a carry past them sets `over`, which the callers treat as out of range. */
#define BN_LIMBS 24

typedef struct {
  uint32_t d[BN_LIMBS];
  int n;          /* limbs in use */
  int over;       /* a carry was lost */
} bn_t;

static void bn_set(bn_t *a, uint64_t v) {
  memset(a, 0, sizeof(*a));
  a->d[0] = (uint32_t)v;
  a->d[1] = (uint32_t)(v >> 32);
  a->n = a->d[1] ? 2 : (a->d[0] ? 1 : 0);
}

static void bn_mul_small(bn_t *a, uint32_t m) {
  uint64_t carry = 0;
  int i;
  for (i = 0; i < a->n; ++i) {
    const uint64_t t = (uint64_t)a->d[i] * m + carry;
    a->d[i] = (uint32_t)t;
    carry = t >> 32;
  }
  if (carry) {
    if (a->n < BN_LIMBS) a->d[a->n++] = (uint32_t)carry;
    else a->over = 1;
  }
}

static void bn_add_small(bn_t *a, uint32_t v) {
  int i = 0;
  uint64_t carry = v;
  while (carry && i < BN_LIMBS) {
    const uint64_t t = (i < a->n ? a->d[i] : 0u) + carry;
    a->d[i] = (uint32_t)t;
    carry = t >> 32;
    if (i >= a->n) a->n = i + 1;
    ++i;
  }
  if (carry) a->over = 1;
}

static void bn_mul_pow10(bn_t *a, int k) {
  while (k >= 9) { bn_mul_small(a, 1000000000u); k -= 9; }
  {
    static const uint32_t p10[9] = { 1u, 10u, 100u, 1000u, 10000u, 100000u, 1000000u, 10000000u,
                                     100000000u };
    if (k > 0) bn_mul_small(a, p10[k]);
  }
}

static void bn_mul_pow5(bn_t *a, int k) {
  while (k >= 13) { bn_mul_small(a, 1220703125u); k -= 13; }   /* 5^13 */
  {
    uint32_t m = 1;
    while (k-- > 0) m *= 5u;
    if (m > 1) bn_mul_small(a, m);
  }
}

static void bn_shl(bn_t *a, int bits) {
  const int limbs = bits / 32, b = bits % 32;
  int i;
  if (a->n == 0 || bits <= 0) return;
  if (a->n + limbs + 1 > BN_LIMBS) { a->over = 1; return; }
  if (b) {
    uint32_t carry = 0;
    for (i = 0; i < a->n; ++i) {
      const uint32_t t = a->d[i];
      a->d[i] = (t << b) | carry;
      carry = t >> (32 - b);
    }
    if (carry) a->d[a->n++] = carry;
  }
  if (limbs) {
    for (i = a->n - 1; i >= 0; --i) a->d[i + limbs] = a->d[i];
    for (i = 0; i < limbs; ++i) a->d[i] = 0;
    a->n += limbs;
  }
}

static int bn_cmp(const bn_t *a, const bn_t *b) {
  int i;
  if (a->n != b->n) return a->n > b->n ? 1 : -1;
  for (i = a->n - 1; i >= 0; --i) {
    if (a->d[i] != b->d[i]) return a->d[i] > b->d[i] ? 1 : -1;
  }
  return 0;
}

/* a = a / d, returning the remainder. */
static uint32_t bn_div_small(bn_t *a, uint32_t d) {
  uint64_t r = 0;
  int i;
  for (i = a->n - 1; i >= 0; --i) {
    const uint64_t t = (r << 32) | a->d[i];
    a->d[i] = (uint32_t)(t / d);
    r = t % d;
  }
  while (a->n > 0 && a->d[a->n - 1] == 0) --a->n;
  return (uint32_t)r;
}

/* ---- Decimal text ---------------------------------------------------------- */
typedef struct {
  int neg;
  char dig[FM1_NUM_MAX];   /* significant digits, no leading or trailing zeros */
  int nd;
  long exp;                /* value = 0.dig... no: value = dig x 10^exp */
  int has_frac, has_exp;
} dec_t;

#define EXP_SAT 100000L

static int dec_parse(const char *s, size_t n, dec_t *d) {
  size_t i = 0;
  int seen = 0, lead = 1;
  long frac = 0;
  memset(d, 0, sizeof(*d));
  if (n == 0 || n > FM1_NUM_MAX) return FM1_NUM_SYNTAX;
  if (s[i] == '-') { d->neg = 1; ++i; }
  if (i >= n || s[i] < '0' || s[i] > '9') return FM1_NUM_SYNTAX;
  if (s[i] == '0' && i + 1 < n && s[i + 1] >= '0' && s[i + 1] <= '9') return FM1_NUM_SYNTAX;
  for (; i < n && s[i] >= '0' && s[i] <= '9'; ++i) {
    seen = 1;
    if (lead && s[i] == '0') continue;
    lead = 0;
    d->dig[d->nd++] = s[i];
  }
  if (i < n && s[i] == '.') {
    int fd = 0;
    d->has_frac = 1;
    for (++i; i < n && s[i] >= '0' && s[i] <= '9'; ++i, ++fd) {
      ++frac;
      if (lead && s[i] == '0') continue;
      lead = 0;
      d->dig[d->nd++] = s[i];
    }
    if (!fd) return FM1_NUM_SYNTAX;
  }
  if (i < n && (s[i] == 'e' || s[i] == 'E')) {
    int eneg = 0, ed = 0;
    long e = 0;
    d->has_exp = 1;
    ++i;
    if (i < n && (s[i] == '+' || s[i] == '-')) { eneg = s[i] == '-'; ++i; }
    for (; i < n && s[i] >= '0' && s[i] <= '9'; ++i, ++ed) {
      if (e < EXP_SAT) e = e * 10 + (s[i] - '0');
    }
    if (!ed) return FM1_NUM_SYNTAX;
    d->exp = eneg ? -e : e;
  }
  if (i != n || !seen) return FM1_NUM_SYNTAX;
  d->exp -= frac;
  while (d->nd > 0 && d->dig[d->nd - 1] == '0') { --d->nd; ++d->exp; }
  return FM1_NUM_OK;
}

static void bn_digits(bn_t *a, const char *dig, int nd) {
  int i;
  bn_set(a, 0);
  for (i = 0; i < nd; ++i) {
    bn_mul_small(a, 10u);
    bn_add_small(a, (uint32_t)(dig[i] - '0'));
  }
}

/* ---- float32 as M x 2^e -------------------------------------------------- */
#define M_MIN 0x800000u        /* 2^23 */
#define M_LIM 0x1000000u       /* 2^24 */
#define E_MIN (-149)
#define E_MAX 104

uint32_t fm1_num_bits(float f) {
  uint32_t b;
  memcpy(&b, &f, sizeof(b));
  return b;
}

float fm1_num_float(uint32_t bits) {
  float f;
  memcpy(&f, &bits, sizeof(f));
  return f;
}

static void split(uint32_t bits, uint32_t *m, int *e) {
  const uint32_t ex = (bits >> 23) & 0xFFu, fr = bits & 0x7FFFFFu;
  if (ex == 0) { *m = fr; *e = E_MIN; }
  else { *m = fr | M_MIN; *e = (int)ex - 150; }
}

static uint32_t join(uint32_t m, int e) {
  if (m < M_MIN) return m;                 /* subnormal (e is E_MIN) */
  return ((uint32_t)(e + 150) << 23) | (m - M_MIN);
}

/* Sign of dig x 10^k - x x 2^y, for x > 0. `over` on a lost carry. */
static int cmp_dec_bin(const char *dig, int nd, long k, uint64_t x, int y, int *over) {
  bn_t l, r;
  bn_digits(&l, dig, nd);
  bn_set(&r, x);
  if (k >= 0) bn_mul_pow10(&l, (int)k);
  else bn_mul_pow10(&r, (int)-k);
  if (y >= 0) bn_shl(&r, y);
  else bn_shl(&l, -y);
  if (l.over || r.over) *over = 1;
  return bn_cmp(&l, &r);
}

static double pow10d(long k) {
  double r = 1.0, b = 10.0;
  long a = k < 0 ? -k : k;
  while (a) {
    if (a & 1) r *= b;
    b *= b;
    a >>= 1;
  }
  return k < 0 ? 1.0 / r : r;
}

/* The exact rounding of dig x 10^k (dig nonzero) to float32 bits. */
static int exact_f32(const char *dig, int nd, long k, uint32_t *bits) {
  uint32_t m;
  int e, c, over = 0;
  double approx = 0.0;
  int i;
  const long e10 = k + nd;
  if (e10 > 39) return FM1_NUM_RANGE;
  if (e10 < -45) { *bits = 0; return FM1_NUM_OK; }
  /* A candidate from double arithmetic: within a float32 ulp or two. */
  for (i = 0; i < nd && i < 19; ++i) approx = approx * 10.0 + (dig[i] - '0');
  approx *= pow10d(k + (nd - i));
  if (!(approx < 3.4028234663852886e38)) {
    m = M_LIM - 1u;
    e = E_MAX;
  } else {
    split(fm1_num_bits((float)approx), &m, &e);
  }
  for (;;) {
    /* Up: past the midpoint to the next float (ties to the even one). */
    c = cmp_dec_bin(dig, nd, k, 2u * (uint64_t)m + 1u, e - 1, &over);
    if (over) return FM1_NUM_RANGE;
    if (c > 0 || (c == 0 && (m & 1u))) {
      if (m == M_LIM - 1u && e == E_MAX) return FM1_NUM_RANGE;
      if (++m == M_LIM) { m = M_MIN; ++e; }
      continue;
    }
    /* Down: below the midpoint to the previous one. */
    if (m > 0) {
      uint64_t x;
      int y;
      if (m == M_MIN && e > E_MIN) { x = 2u * (uint64_t)M_LIM - 1u; y = e - 2; }
      else { x = 2u * (uint64_t)m - 1u; y = e - 1; }
      c = cmp_dec_bin(dig, nd, k, x, y, &over);
      if (over) return FM1_NUM_RANGE;
      if (c < 0 || (c == 0 && (m & 1u))) {
        if (m == M_MIN && e > E_MIN) { m = M_LIM - 1u; --e; }
        else --m;
        continue;
      }
    }
    break;
  }
  *bits = join(m, e);
  return FM1_NUM_OK;
}

static int to_f32(const dec_t *d, float *out, int allow_fast) {
  uint32_t bits = 0;
  int r;
  if (d->nd == 0) {
    *out = d->neg ? -0.0f : 0.0f;
    return FM1_NUM_OK;
  }
#if defined(FLT_EVAL_METHOD) && FLT_EVAL_METHOD == 0
  if (allow_fast && d->nd <= 7 && d->exp >= -10 && d->exp <= 10) {
    static const float p10[11] = { 1e0f, 1e1f, 1e2f, 1e3f, 1e4f, 1e5f, 1e6f, 1e7f, 1e8f, 1e9f, 1e10f };
    uint32_t v = 0;
    int i;
    volatile float f;
    for (i = 0; i < d->nd; ++i) v = v * 10u + (uint32_t)(d->dig[i] - '0');
    f = (float)v;                                     /* exact: v < 2^24 */
    if (d->exp >= 0) f = f * p10[d->exp];             /* one correctly rounded operation */
    else f = f / p10[-d->exp];
    if (!(f <= FLT_MAX)) return FM1_NUM_RANGE;
    *out = d->neg ? -f : f;
    return FM1_NUM_OK;
  }
#else
  (void)allow_fast;
#endif
  r = exact_f32(d->dig, d->nd, d->exp, &bits);
  if (r != FM1_NUM_OK) return r;
  if (d->neg) bits |= 0x80000000u;
  *out = fm1_num_float(bits);
  return FM1_NUM_OK;
}

int fm1_num_f32(const char *s, size_t n, float *out) {
  dec_t d;
  const int r = dec_parse(s, n, &d);
  if (r != FM1_NUM_OK) return r;
  return to_f32(&d, out, 1);
}

int fm1_num_f32_exact(const char *s, size_t n, float *out) {
  dec_t d;
  const int r = dec_parse(s, n, &d);
  if (r != FM1_NUM_OK) return r;
  return to_f32(&d, out, 0);
}

int fm1_num_int(const char *s, size_t n, int64_t lo, int64_t hi, int64_t *out) {
  size_t i = 0;
  int neg = 0;
  uint64_t v = 0;
  if (n == 0 || n > FM1_NUM_MAX) return FM1_NUM_SYNTAX;
  if (s[0] == '-') { neg = 1; i = 1; }
  if (i >= n) return FM1_NUM_SYNTAX;
  if (s[i] == '0' && i + 1 < n && s[i + 1] >= '0' && s[i + 1] <= '9') return FM1_NUM_SYNTAX;
  for (; i < n; ++i) {
    if (s[i] == '.' || s[i] == 'e' || s[i] == 'E') {
      dec_t d;
      return dec_parse(s, n, &d) == FM1_NUM_OK ? FM1_NUM_NOT_INT : FM1_NUM_SYNTAX;
    }
    if (s[i] < '0' || s[i] > '9') return FM1_NUM_SYNTAX;
    if (v > (UINT64_MAX - 9u) / 10u) return FM1_NUM_RANGE;
    v = v * 10u + (uint64_t)(s[i] - '0');
  }
  if (v > (uint64_t)INT64_MAX) return FM1_NUM_RANGE;
  {
    const int64_t x = neg ? -(int64_t)v : (int64_t)v;
    if (x < lo || x > hi) return FM1_NUM_RANGE;
    *out = x;
  }
  return FM1_NUM_OK;
}

/* ---- Q1.14 ----------------------------------------------------------------- */
int fm1_num_q14(const char *s, size_t n, int16_t *out) {
  dec_t d;
  int r = dec_parse(s, n, &d), cmp;
  bn_t l, rr, a, b, t;
  int lo = 0, hi = 16384;
  if (r != FM1_NUM_OK) return r;
  if (d.nd == 0) { *out = 0; return FM1_NUM_OK; }
  if (d.exp + d.nd > 3) {
    *out = d.neg ? -16384 : 16384;
    return FM1_NUM_CLAMPED;
  }
  if (d.exp + d.nd < -12) { *out = 0; return FM1_NUM_OK; }
  bn_digits(&l, d.dig, d.nd);
  bn_set(&rr, 100);
  if (d.exp >= 0) bn_mul_pow10(&l, (int)d.exp);
  else bn_mul_pow10(&rr, (int)-d.exp);
  cmp = bn_cmp(&l, &rr);
  if (cmp >= 0) {
    *out = d.neg ? -16384 : 16384;
    return cmp > 0 ? FM1_NUM_CLAMPED : FM1_NUM_OK;
  }
  /* q = floor((2 L 16384 + R) / (2 R)): the largest q with q x 2R <= A. */
  a = l;
  bn_mul_small(&a, 32768u);
  {
    /* a += rr */
    uint64_t carry = 0;
    int i, m = a.n > rr.n ? a.n : rr.n;
    for (i = 0; i < m; ++i) {
      const uint64_t x = (uint64_t)(i < a.n ? a.d[i] : 0u) + (i < rr.n ? rr.d[i] : 0u) + carry;
      a.d[i] = (uint32_t)x;
      carry = x >> 32;
    }
    a.n = m;
    if (carry) { if (a.n < BN_LIMBS) a.d[a.n++] = (uint32_t)carry; else a.over = 1; }
  }
  b = rr;
  bn_mul_small(&b, 2u);
  while (lo < hi) {
    const int mid = (lo + hi + 1) / 2;
    t = b;
    bn_mul_small(&t, (uint32_t)mid);
    if (bn_cmp(&t, &a) <= 0) lo = mid;
    else hi = mid - 1;
  }
  *out = (int16_t)(d.neg ? -lo : lo);
  return FM1_NUM_OK;
}

static int64_t q14_of(int neg, int64_t n, int d) {
  /* round_half_away(n / 10^d x 16384 / 100) */
  int64_t den = 100, q;
  while (d-- > 0) den *= 10;
  q = (2 * n * 16384 + den) / (2 * den);
  return neg ? -q : q;
}

size_t fm1_num_q14_text(int q, char out[16]) {
  int neg = q < 0, d;
  int64_t aq;
  if (q > 16384) q = 16384;
  if (q < -16384) q = -16384;
  neg = q < 0;
  aq = neg ? -(int64_t)q : (int64_t)q;
  for (d = 0; d <= 3; ++d) {
    int64_t scale = 1, n;
    int i;
    for (i = 0; i < d; ++i) scale *= 10;
    /* n = round_half_away(aq x 25 x 10^d / 4096) */
    n = (2 * aq * 25 * scale + 4096) / (2 * 4096);
    if (q14_of(neg, n, d) == q) {
      char tmp[16];
      size_t k = 0, len = 0;
      int64_t ip = n / scale, fp = n % scale;
      int fd = d;
      while (fd > 0 && fp % 10 == 0) { fp /= 10; --fd; }
      if (neg && n) out[len++] = '-';
      do { tmp[k++] = (char)('0' + ip % 10); ip /= 10; } while (ip);
      while (k) out[len++] = tmp[--k];
      if (fd > 0) {
        out[len++] = '.';
        for (i = fd - 1; i >= 0; --i) {
          int64_t p = 1;
          int j;
          for (j = 0; j < i; ++j) p *= 10;
          out[len++] = (char)('0' + (fp / p) % 10);
        }
      }
      out[len] = '\0';
      return len;
    }
  }
  out[0] = '0';
  out[1] = '\0';
  return 1;   /* not reached: three decimals always reach a Q1.14 value */
}

/* ---- float32 to its shortest decimal ------------------------------------------ */

/* Exact decimal digits of m x 2^e (m > 0): digits into dig (no leading
 * zeros), value = dig x 10^*q. Returns the digit count. */
static int exact_digits(uint32_t m, int e, char *dig, int cap, long *q) {
  bn_t a;
  char tmp[160];
  int n = 0, i;
  bn_set(&a, m);
  if (e >= 0) { bn_shl(&a, e); *q = 0; }
  else { bn_mul_pow5(&a, -e); *q = e; }
  while (a.n > 0) {
    uint32_t r = bn_div_small(&a, 1000000000u);
    int k;
    for (k = 0; k < 9; ++k) {
      if (n < (int)sizeof(tmp)) tmp[n++] = (char)('0' + r % 10u);
      r /= 10u;
    }
  }
  while (n > 1 && tmp[n - 1] == '0') --n;
  if (n > cap) n = cap;   /* never: a float32 has at most 112 digits */
  for (i = 0; i < n; ++i) dig[i] = tmp[n - 1 - i];
  return n;
}

size_t fm1_num_f32_text(uint32_t bits, char out[24]) {
  const int neg = (bits >> 31) != 0;
  uint32_t m, a = bits & 0x7FFFFFFFu;
  int e, nd, p;
  long q;
  char dig[160];
  size_t len = 0;
  if (a == 0 || a >= 0x7F800000u) {
    out[0] = '0';
    out[1] = '\0';
    return 1;
  }
  split(a, &m, &e);
  nd = exact_digits(m, e, dig, (int)sizeof(dig), &q);
  for (p = 1; p <= 9; ++p) {
    char h[12];
    int hn, i, up = 0;
    long ex;               /* value = h x 10^ex */
    uint32_t back = 0;
    if (nd <= p) {
      memcpy(h, dig, (size_t)nd);
      hn = nd;
      ex = q;
    } else {
      memcpy(h, dig, (size_t)p);
      hn = p;
      ex = q + (nd - p);
      if (dig[p] > '5') {
        up = 1;
      } else if (dig[p] == '5') {
        for (i = p + 1; i < nd && dig[i] == '0'; ++i) {}
        up = i < nd ? 1 : ((h[p - 1] - '0') & 1);
      }
      if (up) {
        for (i = hn - 1; i >= 0; --i) {
          if (h[i] == '9') h[i] = '0';
          else { ++h[i]; break; }
        }
        if (i < 0) {        /* 99..9 -> 100..0 */
          h[0] = '1';
          for (i = 1; i < hn; ++i) h[i] = '0';
          ++ex;
        }
      }
    }
    while (hn > 1 && h[hn - 1] == '0') { --hn; ++ex; }
    if (exact_f32(h, hn, ex, &back) != FM1_NUM_OK || back != a) continue;
    /* ECMAScript's Number::toString of h x 10^ex. */
    {
      const long k = hn, n = ex + hn;   /* value = 0.h x 10^n */
      if (neg) out[len++] = '-';
      if (k <= n && n <= 21) {
        for (i = 0; i < hn; ++i) out[len++] = h[i];
        for (i = 0; i < n - k; ++i) out[len++] = '0';
      } else if (0 < n && n <= 21) {
        for (i = 0; i < n; ++i) out[len++] = h[i];
        out[len++] = '.';
        for (; i < hn; ++i) out[len++] = h[i];
      } else if (-6 < n && n <= 0) {
        out[len++] = '0';
        out[len++] = '.';
        for (i = 0; i < -n; ++i) out[len++] = '0';
        for (i = 0; i < hn; ++i) out[len++] = h[i];
      } else {
        const long x = n - 1;
        long ax = x < 0 ? -x : x;
        char t[8];
        int tn = 0;
        out[len++] = h[0];
        if (hn > 1) {
          out[len++] = '.';
          for (i = 1; i < hn; ++i) out[len++] = h[i];
        }
        out[len++] = 'e';
        out[len++] = x > 0 ? '+' : '-';
        do { t[tn++] = (char)('0' + ax % 10); ax /= 10; } while (ax);
        while (tn) out[len++] = t[--tn];
      }
      out[len] = '\0';
      return len;
    }
  }
  out[0] = '0';   /* not reached: 9 digits always round-trip a float32 */
  out[1] = '\0';
  return 1;
}
