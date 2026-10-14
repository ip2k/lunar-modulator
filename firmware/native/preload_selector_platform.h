/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_NATIVE_PRELOAD_SELECTOR_PLATFORM_H
#define LUNAR_NATIVE_PRELOAD_SELECTOR_PLATFORM_H
#include <stdint.h>
#include "content_catalogue.h"
#include "fm1_state.h"
#include "preload_selector.h"
#define LUNAR_PRELOAD_TIMEOUT_TICKS (8000u * 1000u * FM1_TICKS_PER_US)
static void lunar_preload_render(const lunar_preload_selector_t *s)
{
    uint32_t asset = s->projects[s->cursor];
    lcd_fill(0, 0, 240, 240, C_BLACK);
    draw_text_box(0, 32, 240, &FONT_S, "CHOOSE PROJECT", C_WHITE, 1);
    draw_text_box(8, 96, 224, &FONT_S, lunar_content_catalogue[asset].title, C_WHITE, 1);
    draw_text_box(0, 160, 240, &FONT_S, "TURN SELECT", C_WHITE, 1);
    draw_text_box(0, 184, 240, &FONT_S, "PRESS TO OPEN", C_WHITE, 1);
}
static uint32_t lunar_preload_choose(uint32_t default_asset)
{
    lunar_preload_selector_t selector;
    uint8_t kinds[LUNAR_PRELOAD_MAX_ASSETS];
    uint32_t i, started = fm1_ticks(), result;
    if (lunar_content_count > LUNAR_PRELOAD_MAX_ASSETS) return default_asset;
    for (i = 0; i < lunar_content_count; ++i) kinds[i] = lunar_content_catalogue[i].kind;
    if (lunar_preload_init(&selector, kinds, lunar_content_count, default_asset,
                           FM1_STATE_PROJECT) != LUNAR_PRELOAD_ACTIVE)
        return default_asset;
    lunar_preload_render(&selector);
    while ((uint32_t)(fm1_ticks() - started) < LUNAR_PRELOAD_TIMEOUT_TICKS) {
        int32_t movement;
        fm1_wdt_feed();
        fm1_input_scan();
        movement = fm1_enc_take(ENC_SELECT);
        if (movement) {
            lunar_preload_move(&selector, movement);
            lunar_preload_render(&selector);
        }
        result = lunar_preload_confirm(&selector,
            (fm1_input_edges(0) & (1u << BTN_SEL)) != 0u);
        if (result != UINT32_MAX) return result;
    }
    return lunar_preload_timeout(&selector);
}
#endif
