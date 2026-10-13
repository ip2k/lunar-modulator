/* SPDX-License-Identifier: MIT */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
extern double lunar_test_signed(int64_t);
extern double lunar_test_unsigned(uint64_t);
static uint64_t bits(double x) { uint64_t u; memcpy(&u, &x, sizeof u); return u; }
static int check(uint64_t u) {
    int64_t s; memcpy(&s, &u, sizeof s);
    if (bits(lunar_test_unsigned(u)) != bits((double)u) ||
        bits(lunar_test_signed(s)) != bits((double)s)) {
        fprintf(stderr, "conversion mismatch at 0x%016llx\n", (unsigned long long)u);
        return 1;
    }
    return 0;
}
int main(int argc, char **argv) {
    unsigned shard = argc > 1 ? (unsigned)atoi(argv[1]) : 0;
    if (shard >= 16) return 2;
    for (unsigned bit = 0; bit < 64; ++bit) {
        uint64_t center = UINT64_C(1) << bit;
        for (int delta = -4; delta <= 4; ++delta) {
            uint64_t u = center + (uint64_t)delta;
            if (check(u) || check(~u)) return 1;
        }
    }
    /* Full-width deterministic samples plus rounding ties at every exponent. */
    uint64_t state = UINT64_C(0x9e3779b97f4a7c15) ^ shard;
    for (unsigned i = 0; i < 16384; ++i) {
        state ^= state << 13; state ^= state >> 7; state ^= state << 17;
        if (check(state)) return 1;
        unsigned shift = 1 + i % 11;
        uint64_t tie = ((state >> shift) << shift) + (UINT64_C(1) << (shift - 1));
        if (check(tie - 1) || check(tie) || check(tie + 1)) return 1;
    }
    printf("i64-double shard %u passed\n", shard);
    return 0;
}
