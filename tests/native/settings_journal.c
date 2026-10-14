/* SPDX-License-Identifier: MIT */
#include "settings_journal.h"
#include <assert.h>
#include <stdlib.h>

static uint8_t flash[2 * LJ_SECTOR];
static int budget = -1, read_failure, writes;
static int read_flash(void *ctx, uint32_t off, void *p, uint32_t n)
{
    (void)ctx; assert(off <= sizeof flash && n <= sizeof flash - off);
    if (read_failure) return -1;
    memcpy(p, flash + off, n); return 0;
}
static int step(void)
{
    if (!budget) return -1;
    if (budget > 0) --budget;
    return 0;
}
static int erase_flash(void *ctx, uint32_t off)
{
    unsigned i; (void)ctx;
    assert(off == 0 || off == LJ_SECTOR); ++writes;
    for (i = 0; i < LJ_SECTOR; ++i) {
        if (step()) return -1;
        flash[off + i] = 0xff;
    }
    return budget == 0 ? -1 : 0;
}
static int program_flash(void *ctx, uint32_t off, const void *p, uint32_t n)
{
    const uint8_t *s = p; unsigned i; (void)ctx;
    assert(off <= sizeof flash && n <= sizeof flash - off);
    assert(n <= LJ_PAYLOAD); ++writes;
    for (i = 0; i < n; ++i) {
        if (step()) return -1;
        assert((flash[off + i] & s[i]) == s[i]);
        flash[off + i] &= s[i];
    }
    return budget == 0 ? -1 : 0;
}
static const lunar_journal_io io = {0, read_flash, erase_flash, program_flash};
static void generation(unsigned slot, uint32_t gen)
{
    uint8_t *p = flash + slot * LJ_SECTOR;
    lj_put(p + 8, gen); lj_put(p + 16, lj_crc(p));
}
int main(int argc, char **argv)
{
    static const unsigned sizes[8] = {0, 1, 2, 7, 63, 128, 255, 256};
    uint8_t a[LJ_PAYLOAD], b[LJ_PAYLOAD], got[LJ_PAYLOAD], snapshot[sizeof flash];
    unsigned id, n, cut, total, i; uint32_t length;
    assert(argc == 2); id = (unsigned)strtoul(argv[1], 0, 10);
    memset(a, 0x55, sizeof a); memset(b, 0xaa, sizeof b);
    memset(flash, 0xff, sizeof flash);
    if (id < 8) {
        n = sizes[id];
        /* Target slot contains an older committed value before replacement. */
        assert(!lunar_journal_save(&io, b, 256));
        assert(!lunar_journal_save(&io, a, 256));
        memcpy(snapshot, flash, sizeof flash);
        total = LJ_SECTOR + 20 + n + 4;
        for (cut = 0; cut <= total; ++cut) {
            memcpy(flash, snapshot, sizeof flash); budget = (int)cut;
            assert(lunar_journal_save(&io, b, n) != 0);
            budget = -1; length = 999;
            assert(!lunar_journal_load(&io, got, sizeof got, &length));
            if (cut == total) { assert(length == n); assert(!memcmp(got, b, n)); }
            else { assert(length == 256); assert(!memcmp(got, a, 256)); }
            assert(!memcmp(flash + LJ_SECTOR, snapshot + LJ_SECTOR, LJ_SECTOR));
        }
        return 0;
    }
    assert(!lunar_journal_save(&io, a, 256));
    assert(!lunar_journal_save(&io, b, 256));
    if (id < 16) {
        static const unsigned corrupt[8] = {0,4,8,12,16,20,24,LJ_FRAME-1};
        flash[LJ_SECTOR + corrupt[id-8]] ^= 1;
        assert(!lunar_journal_load(&io, got, sizeof got, &length));
        assert(length == 256 && !memcmp(got, a, 256));
    } else if (id == 16) {
        generation(0, 0xffffffffu); generation(1, 0);
        assert(!lunar_journal_load(&io, got, sizeof got, &length));
        assert(!memcmp(got, b, 256));
        assert(!lunar_journal_save(&io, a, 256));
        assert(lj_word(flash + 8) == 1);
    } else if (id == 17 || id == 18) {
        generation(0, 0); generation(1, id == 17 ? 0 : 0x80000000u);
        assert(lunar_journal_load(&io, got, sizeof got, &length) == -2);
        writes = 0; assert(lunar_journal_save(&io, a, 256) == -2); assert(!writes);
    } else if (id == 19) {
        memcpy(flash + LJ_SECTOR, flash, LJ_FRAME);
        assert(!lunar_journal_load(&io, got, sizeof got, &length));
        assert(!memcmp(got, a, 256));
    } else if (id == 20) {
        writes = 0; assert(!lunar_journal_save(&io, b, 256)); assert(!writes);
    } else if (id == 21) {
        read_failure = 1; writes = 0;
        assert(lunar_journal_save(&io, a, 256) == -1); assert(!writes);
    } else if (id == 22 || id == 23 || id == 24) {
        memset(got, 0xcc, sizeof got); length = 999;
        if (id == 22) read_failure = 1;
        if (id == 23) memset(flash, 0xff, sizeof flash);
        assert(lunar_journal_load(&io, got, id == 24 ? 255 : 256, &length) != 0);
        assert(length == 999);
        for (i = 0; i < sizeof got; ++i) assert(got[i] == 0xcc);
    } else if (id == 25) {
        writes = 0; assert(lunar_journal_save(&io, a, 257) == -3); assert(!writes);
    } else if (id == 26) {
        lunar_journal_io bad = io; bad.read = 0;
        writes = 0; assert(lunar_journal_save(&bad, a, 256) == -1); assert(!writes);
    } else if (id == 27) {
        lunar_journal_io bad = io; bad.erase = 0;
        writes = 0; assert(lunar_journal_save(&bad, a, 256) == -3); assert(!writes);
    } else if (id == 28) {
        for (i = 0; i < 100; ++i) {
            a[0] = (uint8_t)i;
            assert(!lunar_journal_save(&io, a, 256));
            assert(!lunar_journal_load(&io, got, sizeof got, &length));
            assert(length == 256 && !memcmp(got, a, 256));
        }
    } else {
        assert(id == 29);
        memset(flash, 0xff, sizeof flash); length = 999;
        assert(lunar_journal_load(&io, got, sizeof got, &length) == 1);
        assert(!lunar_journal_save(&io, a, 0));
        assert(!lunar_journal_load(&io, got, sizeof got, &length)); assert(length == 0);
    }
    return 0;
}
