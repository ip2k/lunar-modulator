/* SPDX-License-Identifier: MIT */
#include "settings_flash.h"
int target_settings_init(lunar_settings_flash *s, uint32_t base,
                         const lunar_settings_hal *hal, lunar_journal_io *io)
{
    return lunar_settings_flash_init(s, base, hal, io);
}
int target_settings_load(const lunar_journal_io *io, void *dst,
                         uint32_t capacity, uint32_t *length)
{
    return lunar_journal_load(io, dst, capacity, length);
}
int target_settings_save(const lunar_journal_io *io, const void *src, uint32_t n)
{
    return lunar_journal_save(io, src, n);
}
