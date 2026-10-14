/* SPDX-License-Identifier: GPL-3.0-only */
/*
 * Geometry/admission checks only. This header has no HAL dependency and does
 * not assign ownership to any flash byte. A caller must supply an independently
 * verified layout and keep its descriptor/extents immutable while in use.
 */
#ifndef LUNAR_PROJECT_STORAGE_PROFILE_H
#define LUNAR_PROJECT_STORAGE_PROFILE_H

#include <stdint.h>

#define LUNAR_NOR_SUPPORTED_JEDEC 0x856014u
#define LUNAR_NOR_SUPPORTED_BYTES 0x00100000u
#define LUNAR_NOR_SECTOR_BYTES 4096u
#define LUNAR_NOR_PAGE_BYTES 256u
#define LUNAR_NOR_MAX_EXTENTS 16u

typedef struct {
    uint32_t offset;
    uint32_t length;
} lunar_storage_extent;

typedef struct {
    uint32_t jedec_id;
    uint32_t flash_bytes;
    uint32_t sector_bytes;
    uint32_t page_bytes;
    int layout_verified;
    const lunar_storage_extent *allowed;
    uint32_t allowed_count;
    const lunar_storage_extent *protected_ranges;
    uint32_t protected_count;
} lunar_project_storage_profile;

typedef enum {
    LUNAR_STORAGE_OK = 0,
    LUNAR_STORAGE_INVALID_ARGUMENT = -1,
    LUNAR_STORAGE_LAYOUT_UNVERIFIED = -2,
    LUNAR_STORAGE_UNSUPPORTED_DEVICE = -3,
    LUNAR_STORAGE_INVALID_GEOMETRY = -4,
    LUNAR_STORAGE_INVALID_EXTENT = -5,
    LUNAR_STORAGE_EXTENT_OVERLAP = -6,
    LUNAR_STORAGE_PROTECTED_OVERLAP = -7,
    LUNAR_STORAGE_OUTSIDE_ALLOWED = -8,
    LUNAR_STORAGE_MISALIGNED = -9
} lunar_storage_status;

/* Check [offset, offset+length) without ever evaluating an overflowing sum. */
static int lunar_storage_range_valid(uint32_t offset, uint32_t length,
                                     uint32_t limit)
{
    return length != 0u && offset <= limit && length <= limit - offset;
}

static int lunar_storage_intersects(const lunar_storage_extent *a,
                                    const lunar_storage_extent *b)
{
    /* Both ranges have already passed overflow-safe validation. */
    return a->offset < b->offset + b->length &&
           b->offset < a->offset + a->length;
}

static int lunar_project_storage_validate(
    const lunar_project_storage_profile *p, uint32_t observed_jedec)
{
    uint32_t i, j;
    if (!p) return LUNAR_STORAGE_INVALID_ARGUMENT;
    if (p->layout_verified != 1) return LUNAR_STORAGE_LAYOUT_UNVERIFIED;
    if (p->jedec_id != LUNAR_NOR_SUPPORTED_JEDEC ||
        observed_jedec != p->jedec_id)
        return LUNAR_STORAGE_UNSUPPORTED_DEVICE;
    if (p->flash_bytes != LUNAR_NOR_SUPPORTED_BYTES ||
        p->sector_bytes != LUNAR_NOR_SECTOR_BYTES ||
        p->page_bytes != LUNAR_NOR_PAGE_BYTES ||
        !p->allowed || p->allowed_count == 0u ||
        p->allowed_count > LUNAR_NOR_MAX_EXTENTS ||
        (p->protected_count && !p->protected_ranges) ||
        p->protected_count > LUNAR_NOR_MAX_EXTENTS)
        return LUNAR_STORAGE_INVALID_GEOMETRY;

    for (i = 0; i < p->allowed_count; ++i) {
        const lunar_storage_extent *a = &p->allowed[i];
        if (!lunar_storage_range_valid(a->offset, a->length, p->flash_bytes))
            return LUNAR_STORAGE_INVALID_EXTENT;
        if ((a->offset % p->sector_bytes) ||
            (a->length % p->sector_bytes))
            return LUNAR_STORAGE_MISALIGNED;
        for (j = 0; j < i; ++j)
            if (lunar_storage_intersects(a, &p->allowed[j]))
                return LUNAR_STORAGE_EXTENT_OVERLAP;
    }
    for (i = 0; i < p->protected_count; ++i) {
        const lunar_storage_extent *r = &p->protected_ranges[i];
        if (!lunar_storage_range_valid(r->offset, r->length, p->flash_bytes))
            return LUNAR_STORAGE_INVALID_EXTENT;
        for (j = 0; j < i; ++j)
            if (lunar_storage_intersects(r, &p->protected_ranges[j]))
                return LUNAR_STORAGE_EXTENT_OVERLAP;
        for (j = 0; j < p->allowed_count; ++j)
            if (lunar_storage_intersects(r, &p->allowed[j]))
                return LUNAR_STORAGE_PROTECTED_OVERLAP;
    }
    return LUNAR_STORAGE_OK;
}

static int lunar_project_storage_erase_allowed(
    const lunar_project_storage_profile *p, uint32_t observed_jedec,
    uint32_t offset, uint32_t length)
{
    uint32_t i;
    int rc = lunar_project_storage_validate(p, observed_jedec);
    if (rc) return rc;
    if (!lunar_storage_range_valid(offset, length, p->flash_bytes))
        return LUNAR_STORAGE_INVALID_EXTENT;
    if ((offset % p->sector_bytes) || (length % p->sector_bytes))
        return LUNAR_STORAGE_MISALIGNED;
    for (i = 0; i < p->allowed_count; ++i) {
        const lunar_storage_extent *e = &p->allowed[i];
        if (offset >= e->offset && length <= e->length &&
            offset - e->offset <= e->length - length)
            return LUNAR_STORAGE_OK;
    }
    return LUNAR_STORAGE_OUTSIDE_ALLOWED;
}

static int lunar_project_storage_program_allowed(
    const lunar_project_storage_profile *p, uint32_t observed_jedec,
    uint32_t offset, uint32_t length)
{
    uint32_t i;
    int rc = lunar_project_storage_validate(p, observed_jedec);
    if (rc) return rc;
    if (!lunar_storage_range_valid(offset, length, p->flash_bytes))
        return LUNAR_STORAGE_INVALID_EXTENT;
    if (length > p->page_bytes ||
        offset / p->page_bytes != (offset + length - 1u) / p->page_bytes)
        return LUNAR_STORAGE_MISALIGNED;
    for (i = 0; i < p->allowed_count; ++i) {
        const lunar_storage_extent *e = &p->allowed[i];
        if (offset >= e->offset && length <= e->length &&
            offset - e->offset <= e->length - length)
            return LUNAR_STORAGE_OK;
    }
    return LUNAR_STORAGE_OUTSIDE_ALLOWED;
}

#endif
