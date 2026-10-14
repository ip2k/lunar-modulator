/* SPDX-License-Identifier: GPL-3.0-only */
/* Bounded adapter for the settings journal. Allocation/admission is external;
 * this header neither selects a window nor grants hardware permission. */
#ifndef LUNAR_SETTINGS_FLASH_H
#define LUNAR_SETTINGS_FLASH_H
#include "settings_journal.h"

typedef struct {
    void *ctx;
    int (*read)(void *, uint32_t, void *, uint32_t);
    int (*erase)(void *, uint32_t);
    int (*program)(void *, uint32_t, const void *, uint32_t);
    int (*flash_ready)(void *);
    int (*audio_stopped)(void *);
} lunar_settings_hal;

typedef struct {
    lunar_settings_hal hal;
    uint32_t base;
    uint8_t admitted, uncertain;
} lunar_settings_flash;

static int lsf_bounds(const lunar_settings_flash *s, uint32_t off, uint32_t n)
{
    return s && s->admitted &&
        (s->base == 0xFC000u || s->base == 0xFD000u) &&
        off <= 2u * LJ_SECTOR && n <= 2u * LJ_SECTOR - off;
}
static int lsf_ready(const lunar_settings_flash *s)
{
    return s && s->hal.flash_ready && s->hal.flash_ready(s->hal.ctx) == 1;
}
static int lsf_read(void *ctx, uint32_t off, void *dst, uint32_t n)
{
    lunar_settings_flash *s = ctx;
    int rc;
    if (!lsf_bounds(s, off, n) || (!dst && n) || !s->hal.read || !lsf_ready(s))
        return -8;
    if (!n) return 0;
    rc = s->hal.read(s->hal.ctx, s->base + off, dst, n);
    if (rc) s->uncertain = 1;
    return rc;
}
static int lsf_write_ready(lunar_settings_flash *s)
{
    return s && !s->uncertain && lsf_ready(s) && s->hal.audio_stopped &&
        s->hal.audio_stopped(s->hal.ctx) == 1;
}
static int lsf_erase(void *ctx, uint32_t off)
{
    lunar_settings_flash *s = ctx;
    int rc;
    if (!lsf_bounds(s, off, LJ_SECTOR) || off % LJ_SECTOR ||
        !s->hal.erase || !lsf_write_ready(s)) return -8;
    rc = s->hal.erase(s->hal.ctx, s->base + off);
    if (rc) s->uncertain = 1;
    return rc;
}
static int lsf_program(void *ctx, uint32_t off, const void *src, uint32_t n)
{
    lunar_settings_flash *s = ctx;
    int rc;
    if (!lsf_bounds(s, off, n) || n > LJ_PAYLOAD || (!src && n) ||
        !s->hal.program || !lsf_write_ready(s)) return -8;
    if (!n) return 0;
    rc = s->hal.program(s->hal.ctx, s->base + off, src, n);
    if (rc) s->uncertain = 1;
    return rc;
}
/* Initialise disarmed. The build/platform must independently admit the exact
 * window before setting admitted=1. Never clear uncertain to retry a save:
 * reconstruct context only after caller recovery/readback decisions. */
static int lunar_settings_flash_init(lunar_settings_flash *s, uint32_t base,
                                     const lunar_settings_hal *hal,
                                     lunar_journal_io *io)
{
    if (s) memset(s, 0, sizeof *s);
    if (io) memset(io, 0, sizeof *io);
    if (!s || !io || !hal) return -8;
    if ((base != 0xFC000u && base != 0xFD000u) || !hal->read || !hal->erase ||
        !hal->program || !hal->flash_ready || !hal->audio_stopped) return -8;
    s->base = base; s->hal = *hal;
    io->ctx = s; io->read = lsf_read; io->erase = lsf_erase; io->program = lsf_program;
    return 0;
}
#endif
