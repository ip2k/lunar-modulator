/* SPDX-License-Identifier: MIT */
#include "settings_journal.h"
int target_journal_load(const lunar_journal_io *io, void *dst,
                        uint32_t capacity, uint32_t *length)
{
    return lunar_journal_load(io, dst, capacity, length);
}
int target_journal_save(const lunar_journal_io *io, const void *src, uint32_t n)
{
    return lunar_journal_save(io, src, n);
}
