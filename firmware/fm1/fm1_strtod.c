/* MIT. Decimal-to-binary conversion for the FM-1 image's size levers
 * (prepare-fm1-app.py --size-levers cold, tools/jieli/fm1-app.mk).
 *
 * Two text parsers, the modulation script (engines/host/mod_script.c) and the
 * editor (sim/web/src/fm1_edit.c), call strtod and strtof. Their bitcode
 * symbol tables pull newlib's strtod.o and its multi-precision helpers into
 * the link before LTO finds those callers dead, about 7 KB of flash
 * (notes/2026-11-10-size-levers.md). With the lever on, fm1-app.mk compiles
 * those two units with -Dstrtod=lunar_fm1_strtod -Dstrtof=lunar_fm1_strtof,
 * so the references resolve here, inside the LTO object, and nothing is
 * pulled. Host, simulator and WebAssembly builds never see this file.
 *
 * Accepted text: optional leading white space, an optional sign, decimal
 * digits with an optional point, an optional exponent ("e", optional sign,
 * digits). *end points after the last character used, as strtod's does,
 * including its backtracking over an incomplete exponent ("1e", "1e+").
 *
 * Every result returned is the correctly rounded value strtod or strtof
 * would return (Clinger's exact fast path). Text outside that path is
 * refused rather than approximated: the function returns 0 with *end == s,
 * which both callers treat as "not a number". That is: hexadecimal, inf and
 * nan spellings; more than 19 significant digits; a value whose digits do
 * not fit 2^53 (2^24 for floats) with a power of ten above 10^22 (10^10);
 * for floats, a double-path result that lands exactly on a float rounding
 * tie, or one outside the normal float range. Zero is always exact. */
#include <stdint.h>
#include <string.h>

double lunar_fm1_strtod(const char *s, char **end);
float lunar_fm1_strtof(const char *s, char **end);

struct decimal {
    uint64_t digits;   /* up to 19 significant digits */
    int exponent;      /* value = digits * 10^exponent */
    int negative;
    int exact;         /* 0: digits were dropped or the exponent is huge */
};

static int space(char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\v' || c == '\f' || c == '\r';
}

/* Scan one decimal; return the end pointer, or s when nothing was read. */
static const char *scan(const char *s, struct decimal *d) {
    const char *p = s;
    int any = 0, significant = 0;
    memset(d, 0, sizeof *d);
    d->exact = 1;
    while (space(*p)) ++p;
    if (*p == '+' || *p == '-') d->negative = *p++ == '-';
    if (p[0] == '0' && (p[1] == 'x' || p[1] == 'X')) return s;  /* hexadecimal: refused */
    for (; *p >= '0' && *p <= '9'; ++p, any = 1) {
        if (!d->digits && *p == '0') continue;
        if (++significant > 19) {
            if (*p != '0') d->exact = 0;
            ++d->exponent;          /* dropped trailing integer digit */
            continue;
        }
        d->digits = d->digits * 10u + (unsigned)(*p - '0');
    }
    if (*p == '.') {
        for (++p; *p >= '0' && *p <= '9'; ++p, any = 1) {
            if (!d->digits && *p == '0') { --d->exponent; continue; }
            if (++significant > 19) {
                if (*p != '0') d->exact = 0;
                continue;           /* dropped fraction digit */
            }
            d->digits = d->digits * 10u + (unsigned)(*p - '0');
            --d->exponent;
        }
    }
    if (!any) return s;
    if (*p == 'e' || *p == 'E') {
        const char *q = p + 1;
        int negative = 0, value = 0, digits = 0;
        if (*q == '+' || *q == '-') negative = *q++ == '-';
        for (; *q >= '0' && *q <= '9'; ++q, ++digits)
            if (value < 100000) value = value * 10 + (*q - '0');
        if (digits) {               /* otherwise strtod stops before the 'e' */
            if (value >= 100000) d->exact = 0;
            d->exponent += negative ? -value : value;
            p = q;
        }
    }
    if (!d->digits) d->exact = 1, d->exponent = 0;
    while (d->digits && d->digits % 10u == 0) d->digits /= 10u, ++d->exponent;  /* 1000 = 1e3 */
    return p;
}

static const double kPow10[23] = {
    1e0, 1e1, 1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9, 1e10, 1e11,
    1e12, 1e13, 1e14, 1e15, 1e16, 1e17, 1e18, 1e19, 1e20, 1e21, 1e22,
};

/* Clinger's fast path: digits and the power of ten are exact doubles, so one
 * IEEE multiply or divide rounds once. *exact says the result had no
 * rounding at all (an integer product within 2^53). */
static int fast_double(const struct decimal *d, double *out, int *exact) {
    uint64_t m = d->digits;
    int e = d->exponent;
    *exact = 0;
    if (!d->exact) return 0;
    if (!m) { *out = d->negative ? -0.0 : 0.0; *exact = 1; return 1; }
    if (m > (UINT64_C(1) << 53)) return 0;
    while (e > 22 && m <= (UINT64_C(1) << 53) / 10u) m *= 10u, --e;  /* 1e30 = 1e8 * 1e22 */
    if (e > 22 || e < -22) return 0;
    if (e >= 0) {
        uint64_t p = m;
        int i;
        *out = (double)m * kPow10[e];
        *exact = 1;                 /* unless the integer product passes 2^53 */
        for (i = 0; i < e && *exact; ++i) {
            if (p > (UINT64_C(1) << 53) / 10u) *exact = 0;
            p *= 10u;
        }
    } else {
        *out = (double)m / kPow10[-e];
    }
    if (d->negative) *out = -*out;
    return 1;
}

double lunar_fm1_strtod(const char *s, char **end) {
    struct decimal d;
    const char *p = scan(s, &d);
    double v;
    int exact;
    if (p == s || !fast_double(&d, &v, &exact)) {
        if (end) *end = (char *)s;
        return 0.0;
    }
    if (end) *end = (char *)p;
    return v;
}

static const float kPow10f[11] = {1e0f, 1e1f, 1e2f, 1e3f, 1e4f, 1e5f, 1e6f, 1e7f, 1e8f, 1e9f, 1e10f};

float lunar_fm1_strtof(const char *s, char **end) {
    struct decimal d;
    const char *p = scan(s, &d);
    float f;
    double v;
    int exact;
    uint64_t bits;
    if (p == s || !d.exact) goto refuse;
    if (d.digits <= (UINT64_C(1) << 24) && d.exponent >= -10 && d.exponent <= 10) {
        /* The float fast path: one float operation, one rounding. */
        f = (float)d.digits;
        f = d.exponent < 0 ? f / kPow10f[-d.exponent] : f * kPow10f[d.exponent];
        if (d.negative) f = -f;
        goto done;
    }
    if (!fast_double(&d, &v, &exact)) goto refuse;
    if (v == 0.0) { f = (float)v; goto done; }
    memcpy(&bits, &v, sizeof bits);
    {
        int biased = (int)((bits >> 52) & 0x7ff) - 1023;
        /* Normal floats only: 2^-126 <= |v| < 2^128 (a carry to 2^128 is an
         * overflow strtof would report; refuse that too). */
        if (biased < -126 || biased > 127) goto refuse;
        /* The correctly rounded double sits on a float tie only if bit 28 of
         * its fraction is set and bits 0-27 are clear. A decimal and its
         * nearest double lie on the same side of every tie, so any other
         * double rounds to the right float; a tie is right only when the
         * double is the decimal itself. */
        if ((bits & UINT64_C(0x1fffffff)) == UINT64_C(0x10000000) && !exact) goto refuse;
    }
    f = (float)v;
    if (f - f != 0.0f) goto refuse;     /* rounded up to infinity */
done:
    if (end) *end = (char *)p;
    return f;
refuse:
    if (end) *end = (char *)s;
    return 0.0f;
}
