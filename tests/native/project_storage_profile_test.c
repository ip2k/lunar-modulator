/* SPDX-License-Identifier: GPL-3.0-only */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "project_storage_profile.h"

#define ID LUNAR_NOR_SUPPORTED_JEDEC
#define FLASH LUNAR_NOR_SUPPORTED_BYTES
#define SECTOR LUNAR_NOR_SECTOR_BYTES

static void set_profile(lunar_project_storage_profile *p,
                        const lunar_storage_extent *allowed,
                        uint32_t allowed_count,
                        const lunar_storage_extent *protected_ranges,
                        uint32_t protected_count)
{
    p->jedec_id = ID;
    p->flash_bytes = FLASH;
    p->sector_bytes = SECTOR;
    p->page_bytes = LUNAR_NOR_PAGE_BYTES;
    p->layout_verified = 1;
    p->allowed = allowed;
    p->allowed_count = allowed_count;
    p->protected_ranges = protected_ranges;
    p->protected_count = protected_count;
}

int main(void)
{
    lunar_project_storage_profile p;
    const lunar_storage_extent good_allowed[] = {
        {0x00010000u, 0x00008000u},
        {0x00020000u, 0x00001000u},
        {0x000ff000u, 0x00001000u}
    };
    const lunar_storage_extent good_protected[] = {
        {0u, 0x00010000u},
        {0x00018000u, 0x00008000u},
        {0x00021000u, 0x000de000u}
    };
    const lunar_storage_extent reordered_disjoint[] = {
        {0x00020000u, 0x00001000u},
        {0x00010000u, 0x00001000u}
    };
    const lunar_storage_extent adjacent_reversed[] = {
        {0x00011000u, 0x00001000u},
        {0x00010000u, 0x00001000u}
    };
    lunar_storage_extent bad[2];

    /* Valid caller-supplied, non-overlapping layout, including flash tail. */
    set_profile(&p, good_allowed, 3u, good_protected, 3u);
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_OK);
    assert(lunar_project_storage_erase_allowed(&p, ID, 0x10000u, SECTOR) == LUNAR_STORAGE_OK);
    assert(lunar_project_storage_erase_allowed(&p, ID, 0x11000u, 0x7000u) == LUNAR_STORAGE_OK);
    assert(lunar_project_storage_erase_allowed(&p, ID, 0xff000u, SECTOR) == LUNAR_STORAGE_OK);
    assert(lunar_project_storage_program_allowed(&p, ID, 0x100ffu, 1u) == LUNAR_STORAGE_OK);
    assert(lunar_project_storage_program_allowed(&p, ID, 0x10100u, 256u) == LUNAR_STORAGE_OK);
    assert(lunar_project_storage_program_allowed(&p, ID, 0xfffffu, 1u) == LUNAR_STORAGE_OK);

    /* No implicit/default ownership; exact verifier bit and known device only. */
    set_profile(&p, good_allowed, 0u, good_protected, 3u);
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_INVALID_GEOMETRY);
    set_profile(&p, good_allowed, 3u, good_protected, 3u);
    p.layout_verified = 0;
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_LAYOUT_UNVERIFIED);
    p.layout_verified = 1;
    assert(lunar_project_storage_validate(&p, 0x856015u) == LUNAR_STORAGE_UNSUPPORTED_DEVICE);
    p.jedec_id = 0x856015u;
    assert(lunar_project_storage_validate(&p, 0x856015u) == LUNAR_STORAGE_UNSUPPORTED_DEVICE);

    /* Geometry mismatch, missing arrays, excessive counts and empty extents. */
    set_profile(&p, good_allowed, 3u, good_protected, 3u);
    p.flash_bytes = FLASH - 1u;
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_INVALID_GEOMETRY);
    p.flash_bytes = FLASH;
    p.page_bytes = 128u;
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_INVALID_GEOMETRY);
    p.page_bytes = LUNAR_NOR_PAGE_BYTES;
    p.allowed = 0;
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_INVALID_GEOMETRY);
    p.allowed = good_allowed;
    p.allowed_count = LUNAR_NOR_MAX_EXTENTS + 1u;
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_INVALID_GEOMETRY);
    set_profile(&p, good_allowed, 3u, 0, 1u);
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_INVALID_GEOMETRY);

    /* Overflow and outside-flash extents fail before intersection arithmetic. */
    bad[0] = (lunar_storage_extent){0xfffff000u, 0x2000u};
    set_profile(&p, bad, 1u, 0, 0u);
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_INVALID_EXTENT);
    bad[0] = (lunar_storage_extent){FLASH, 1u};
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_INVALID_EXTENT);
    bad[0] = (lunar_storage_extent){0x10001u, SECTOR};
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_MISALIGNED);
    bad[0] = (lunar_storage_extent){0x10000u, SECTOR - 1u};
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_MISALIGNED);

    /* Protected extents independently reject zero length, bounds, and overflow. */
    {
        const lunar_storage_extent invalid[] = {{0x30000u, 0u}};
        set_profile(&p, good_allowed, 3u, invalid, 1u);
        assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_INVALID_EXTENT);
    }
    {
        const lunar_storage_extent invalid[] = {{FLASH - 1u, 2u}};
        set_profile(&p, good_allowed, 3u, invalid, 1u);
        assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_INVALID_EXTENT);
    }
    {
        const lunar_storage_extent invalid[] = {{UINT32_MAX - 3u, 8u}};
        set_profile(&p, good_allowed, 3u, invalid, 1u);
        assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_INVALID_EXTENT);
    }

    /* Caller order is irrelevant, and adjacent half-open extents do not overlap. */
    set_profile(&p, reordered_disjoint, 2u, 0, 0u);
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_OK);
    set_profile(&p, adjacent_reversed, 2u, 0, 0u);
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_OK);

    /* Allowed/allowed and protected/protected conflicts are rejected. */
    bad[0] = (lunar_storage_extent){0x10000u, 0x2000u};
    bad[1] = (lunar_storage_extent){0x11000u, 0x1000u};
    set_profile(&p, bad, 2u, 0, 0u);
    assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_EXTENT_OVERLAP);
    bad[1] = (lunar_storage_extent){0x12000u, 0x1000u};
    {
        const lunar_storage_extent conflicts[] = {
            {0x30000u, 0x1000u}, {0x30800u, 0x1000u}
        };
        set_profile(&p, good_allowed, 3u, conflicts, 2u);
        assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_EXTENT_OVERLAP);
    }
    {
        const lunar_storage_extent conflicts[] = {{0x10000u, 0x1000u}};
        set_profile(&p, good_allowed, 3u, conflicts, 1u);
        assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_PROTECTED_OVERLAP);
    }
    {
        const lunar_storage_extent edge[] = {{0x10fffu, 2u}};
        const lunar_storage_extent one_allowed[] = {{0x10000u, 0x1000u}};
        set_profile(&p, one_allowed, 1u, edge, 1u);
        assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_PROTECTED_OVERLAP);
    }

    /* Operation admission: allowed edges pass; crossing/protected ranges fail. */
    set_profile(&p, good_allowed, 3u, good_protected, 3u);
    assert(lunar_project_storage_erase_allowed(&p, ID, 0x0f000u, SECTOR) == LUNAR_STORAGE_OUTSIDE_ALLOWED);
    assert(lunar_project_storage_erase_allowed(&p, ID, 0x17000u, 0x2000u) == LUNAR_STORAGE_OUTSIDE_ALLOWED);
    assert(lunar_project_storage_erase_allowed(&p, ID, 0x10001u, SECTOR) == LUNAR_STORAGE_MISALIGNED);
    assert(lunar_project_storage_erase_allowed(&p, ID, 0x10000u, 0u) == LUNAR_STORAGE_INVALID_EXTENT);
    assert(lunar_project_storage_erase_allowed(&p, ID, 0xfffff000u, 0x2000u) == LUNAR_STORAGE_INVALID_EXTENT);
    assert(lunar_project_storage_program_allowed(&p, ID, 0x100ffu, 2u) == LUNAR_STORAGE_MISALIGNED);
    assert(lunar_project_storage_program_allowed(&p, ID, 0x10000u, 257u) == LUNAR_STORAGE_MISALIGNED);
    assert(lunar_project_storage_program_allowed(&p, ID, 0x18000u, 1u) == LUNAR_STORAGE_OUTSIDE_ALLOWED);
    assert(lunar_project_storage_program_allowed(&p, ID, 0xfffffu, 2u) == LUNAR_STORAGE_INVALID_EXTENT);

    /* The verified bit is caller-controlled, not layout provenance or immutability. */
    {
        lunar_storage_extent mutable_allowed[] = {{0x30000u, 0x1000u}};
        set_profile(&p, mutable_allowed, 1u, 0, 0u);
        assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_OK);
        assert(p.layout_verified == 1);
        assert(lunar_project_storage_program_allowed(&p, ID, 0x30000u, 1u) == LUNAR_STORAGE_OK);
        mutable_allowed[0].offset = 0x40000u;
        assert(p.layout_verified == 1);
        assert(lunar_project_storage_validate(&p, ID) == LUNAR_STORAGE_OK);
        assert(lunar_project_storage_program_allowed(&p, ID, 0x30000u, 1u) == LUNAR_STORAGE_OUTSIDE_ALLOWED);
        assert(lunar_project_storage_program_allowed(&p, ID, 0x40000u, 1u) == LUNAR_STORAGE_OK);
    }

    puts("project storage profile: 45 assertions passed");
    return 0;
}
