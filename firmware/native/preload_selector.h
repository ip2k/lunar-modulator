/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_NATIVE_PRELOAD_SELECTOR_H
#define LUNAR_NATIVE_PRELOAD_SELECTOR_H
#include <stdint.h>
#define LUNAR_PRELOAD_MAX_ASSETS 64u
#define LUNAR_PRELOAD_BYPASS 0u
#define LUNAR_PRELOAD_ACTIVE 1u
#define LUNAR_PRELOAD_INVALID 2u
typedef struct lunar_preload_selector {
    uint8_t projects[LUNAR_PRELOAD_MAX_ASSETS];
    uint8_t count, cursor, default_asset;
} lunar_preload_selector_t;
static uint32_t lunar_preload_init(lunar_preload_selector_t *s,
                                    const uint8_t *kinds, uint32_t count,
                                    uint32_t default_asset, uint8_t project_kind)
{
    uint32_t i;
    if (!s || !kinds || count > LUNAR_PRELOAD_MAX_ASSETS) return LUNAR_PRELOAD_INVALID;
    s->count = 0; s->cursor = 0; s->default_asset = 0;
    for (i = 0; i < count; ++i) {
        if (kinds[i] == project_kind) {
            if (i > 255u) return LUNAR_PRELOAD_INVALID;
            s->projects[s->count++] = (uint8_t)i;
        }
    }
    if (!s->count) return LUNAR_PRELOAD_INVALID;
    for (i = 0; i < s->count; ++i)
        if (s->projects[i] == default_asset) { s->default_asset = (uint8_t)i; break; }
    if (i == s->count) return LUNAR_PRELOAD_INVALID;
    s->cursor = s->default_asset;
    return s->count > 1u ? LUNAR_PRELOAD_ACTIVE : LUNAR_PRELOAD_BYPASS;
}
static void lunar_preload_move(lunar_preload_selector_t *s, int32_t delta)
{
    int32_t n, p;
    if (!s || s->count < 2u || !delta) return;
    /* Bound work even if a corrupted input counter reports an extreme delta. */
    if (delta > 64) delta = 64;
    if (delta < -64) delta = -64;
    n = s->count; p = (int32_t)s->cursor + delta;
    p %= n; if (p < 0) p += n;
    s->cursor = (uint8_t)p;
}
static uint32_t lunar_preload_confirm(const lunar_preload_selector_t *s,
                                      uint32_t confirmed)
{
    if (!s || !s->count) return UINT32_MAX;
    return confirmed ? s->projects[s->cursor] : UINT32_MAX;
}
static uint32_t lunar_preload_timeout(const lunar_preload_selector_t *s)
{
    return s && s->count ? s->projects[s->default_asset] : UINT32_MAX;
}
#endif
