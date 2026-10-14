/* SPDX-License-Identifier: GPL-3.0-only */
/* Two-sector settings journal. Offsets are relative to a separately admitted
 * 8 KiB storage window. This module grants no physical flash write permission.
 * Call only while audio is stopped; callbacks must enforce their own bounds.
 */
#ifndef LUNAR_SETTINGS_JOURNAL_H
#define LUNAR_SETTINGS_JOURNAL_H
#include <stdint.h>
#include <string.h>

#define LJ_SECTOR 4096u
#define LJ_PAYLOAD 256u
#define LJ_HEADER 24u
#define LJ_FRAME (LJ_HEADER + LJ_PAYLOAD)
#define LJ_MAGIC 0x534A4E4Cu
#define LJ_COMMIT 0x434F4D54u

typedef struct {
    void *ctx;
    int (*read)(void *, uint32_t, void *, uint32_t);
    int (*erase)(void *, uint32_t);
    int (*program)(void *, uint32_t, const void *, uint32_t);
} lunar_journal_io;

static uint32_t lj_word(const uint8_t *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
           (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static void lj_put(uint8_t *p, uint32_t v)
{
    unsigned i;
    for (i = 0; i < 4; ++i) p[i] = (uint8_t)(v >> (8u * i));
}
static uint32_t lj_crc(const uint8_t *frame)
{
    uint32_t c = 0xffffffffu, i, j, n = lj_word(frame + 12);
    /* Bind schema, generation and length as well as the payload. */
    for (i = 4; i < LJ_HEADER + n; ++i) {
        if (i >= 16 && i < LJ_HEADER) continue;
        c ^= frame[i];
        for (j = 0; j < 8; ++j)
            c = (c >> 1) ^ ((c & 1u) ? 0xedb88320u : 0u);
    }
    return ~c;
}
static int lj_valid(const uint8_t *p)
{
    return lj_word(p) == LJ_MAGIC && lj_word(p + 4) == 1u &&
           lj_word(p + 20) == LJ_COMMIT && lj_word(p + 12) <= LJ_PAYLOAD &&
           lj_word(p + 16) == lj_crc(p);
}
/* 0: found, 1: empty, -1: read failure, -2: ambiguous generations. */
static int lj_scan(const lunar_journal_io *io, uint8_t frames[2][LJ_FRAME], int *slot)
{
    int a, b;
    uint32_t delta;
    if (!io || !io->read || !slot) return -1;
    if (io->read(io->ctx, 0, frames[0], LJ_FRAME) ||
        io->read(io->ctx, LJ_SECTOR, frames[1], LJ_FRAME)) return -1;
    a = lj_valid(frames[0]); b = lj_valid(frames[1]);
    if (!a && !b) { *slot = -1; return 1; }
    if (!a || !b) { *slot = a ? 0 : 1; return 0; }
    delta = lj_word(frames[1] + 8) - lj_word(frames[0] + 8);
    if (delta == 0) {
        uint32_t n = lj_word(frames[0] + 12);
        if (n != lj_word(frames[1] + 12) ||
            memcmp(frames[0] + LJ_HEADER, frames[1] + LJ_HEADER, n)) return -2;
        *slot = 0; return 0;
    }
    if (delta == 0x80000000u) return -2;
    *slot = delta < 0x80000000u ? 1 : 0;
    return 0;
}
/* Destination and length remain untouched on every failure. */
static int lunar_journal_load(const lunar_journal_io *io, void *dst,
                              uint32_t capacity, uint32_t *length)
{
    uint8_t frames[2][LJ_FRAME];
    int slot, rc = lj_scan(io, frames, &slot);
    uint32_t n;
    if (rc) return rc;
    n = lj_word(frames[slot] + 12);
    if (!dst || !length || n > capacity) return -3;
    memcpy(dst, frames[slot] + LJ_HEADER, n); *length = n;
    return 0;
}
/* Nonzero means no success claim; never retry an ambiguous transport result
 * automatically. A later load may find a committed replacement after a failed
 * acknowledgement. Previous slot is never erased during this transaction. */
static int lunar_journal_save(const lunar_journal_io *io, const void *src, uint32_t n)
{
    uint8_t frames[2][LJ_FRAME], next[LJ_FRAME], check[LJ_FRAME];
    int slot, target, rc;
    uint32_t generation, off;
    if (!io || !io->erase || !io->program || !src || n > LJ_PAYLOAD) return -3;
    rc = lj_scan(io, frames, &slot);
    if (rc < 0) return rc;
    if (!rc && lj_word(frames[slot] + 12) == n &&
        !memcmp(frames[slot] + LJ_HEADER, src, n)) return 0;
    generation = rc == 1 ? 0u : lj_word(frames[slot] + 8) + 1u;
    target = rc == 1 ? 0 : 1 - slot; off = (uint32_t)target * LJ_SECTOR;
    memset(next, 0xff, sizeof next);
    lj_put(next, LJ_MAGIC); lj_put(next + 4, 1u);
    lj_put(next + 8, generation); lj_put(next + 12, n);
    memcpy(next + LJ_HEADER, src, n);
    lj_put(next + 16, lj_crc(next)); lj_put(next + 20, LJ_COMMIT);
    if (io->erase(io->ctx, off) ||
        io->program(io->ctx, off, next, 20u) ||
        (n && io->program(io->ctx, off + LJ_HEADER, next + LJ_HEADER, n)) ||
        io->program(io->ctx, off + 20u, next + 20u, 4u)) return -1;
    if (io->read(io->ctx, off, check, LJ_FRAME) || !lj_valid(check) ||
        memcmp(check, next, LJ_HEADER + n)) return -1;
    return 0;
}
#endif
