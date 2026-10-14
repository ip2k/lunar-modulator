#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <printf/printf.h>

/* Compare bounded UI formats, including the returned untruncated length. */
static void check(const char *format, ...) {
    static const size_t capacities[] = {0, 1, 2, 7, 32, 128};
    for (size_t i = 0; i < sizeof capacities / sizeof capacities[0]; ++i) {
        unsigned char expected[132], actual[132];
        memset(expected, 0xa5, sizeof expected);
        memset(actual, 0xa5, sizeof actual);
        va_list a, b;
        va_start(a, format);
        va_copy(b, a);
        int want = vsnprintf((char *)expected + 2, capacities[i], format, a);
        int got = vsnprintf_((char *)actual + 2, capacities[i], format, b);
        va_end(b);
        va_end(a);
        assert(want == got);
        assert(memcmp(expected, actual, sizeof expected) == 0);
    }
}

int main(int argc, char **argv) {
    assert(argc == 2);
    int shard = atoi(argv[1]);
    assert(shard >= 0 && shard < 30);
    /* Unsupported writeback specifiers must never modify argument storage,
       including when the output buffer is empty or truncated. */
    static const size_t capacities[] = {0, 1, 2, 7, 32};
    char out[32];
    signed char c = 91;
    short s = 92;
    int n = 93;
    long l = 94;
    long long ll = 95;
    size_t z = 96;
    const size_t cap = capacities[shard / 6];
    int got = 0;
    switch (shard % 6) {
    case 0: got = snprintf_(out, cap, "ab%hhn", &c); break;
    case 1: got = snprintf_(out, cap, "ab%hn", &s); break;
    case 2: got = snprintf_(out, cap, "ab%n", &n); break;
    case 3: got = snprintf_(out, cap, "ab%ln", &l); break;
    case 4: got = snprintf_(out, cap, "ab%lln", &ll); break;
    case 5: got = snprintf_(out, cap, "ab%zn", &z); break;
    }
    assert(c == 91 && s == 92 && n == 93 && l == 94 && ll == 95 && z == 96);
    /* Library policy treats an unsupported specifier as its literal letter. */
    assert(got == 3);
    if (cap > 3) assert(strcmp(out, "abn") == 0);
    switch (shard % 16) {
    case 0: check("LUNAR TRIO"); break;
    case 1: check("%s %c", "Trio", 'A'); break;
    case 2: check("%d %i", -127, 42); break;
    case 3: check("%u %x %X", 44118u, 0xc755u, 0x4c4au); break;
    case 4: check("%08x %04d", 0x123u, 7); break;
    case 5: check("%+d % d %-8d", 42, 42, -7); break;
    case 6: check("%zu", (size_t)220816); break;
    case 7: check("%lld %llu", -1234567890123LL, 1234567890123ULL); break;
    case 8: check("%.2f", 44117.625); break;
    case 9: check("%.*f", 3, -0.125); break;
    case 10: check("%8.2f", 0.25); break;
    case 11: check("%.3e", 125.0); break;
    case 12: check("%.4g", 0.125); break;
    case 13: check("%.*s", 5, "INTERGALACTIC"); break;
    case 14: check("%*d%%", 4, 100); break;
    case 15: check("%s:%02u %.2f", "FM6", 7u, 0.75); break;
    }
    return 0;
}
