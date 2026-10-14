/* SPDX-License-Identifier: GPL-3.0-only */
/* Shared-application integration entry, NOT yet an admitted release.
 * Requires the reviewed generated platform: no NOR writes, 16-row canvas,
 * no OTA cleanup and unity HAL master gain. The shared instance pool is provisional;
 * complete catalogue RAM and timing acceptance remain separate. Device admission is a separate operation. */
#if !defined(LUNAR_APP_PROBE) || !FM1_APP_EXTERNAL_ARENAS
#error "Use the checked external-arena probe build"
#endif
#include <stdint.h>
#include <string.h>
#define APP_NAME "LUNAR MODULATOR"
#define APP_VER "APP PROBE"
#define FM1_BTN_OCT_DOWN DINGHY_BTN_OCT_DOWN
#define FM1_BTN_OCT_UP DINGHY_BTN_OCT_UP
static int32_t lunar_master_raw = 512;
#include "platform.c"
#undef FM1_BTN_OCT_DOWN
#undef FM1_BTN_OCT_UP
#include "fm1_app.h"
#include "audio_queue.h"
#include "instance_pool.h"
#include "midi_input.h"
#include "runtime_mode.h"
#ifdef LUNAR_STACK_WATERMARK
#include "stack_watermark.h"
#include "stack_readout.h"
extern char _ustack_top[];
/* Retained symbols for a diagnostic debugger/readout. Minimum observed free
 * bytes over completed samples; they include this scanner's own stack stores.
 * No host/runtime measurement may substitute for physical values here. */
volatile uint32_t lunar_stack_user_margin = UINT32_MAX;
volatile uint32_t lunar_stack_system_margin = UINT32_MAX;
volatile uint32_t lunar_stack_samples;
static void sample_stacks(void)
{
    uint32_t user = (uint32_t)lunar_stack_pattern_margin(
        (const volatile uint32_t *)(uintptr_t)_ustack_lo,
        ((uintptr_t)_ustack_top - (uintptr_t)_ustack_lo) / 4u);
    uint32_t system = (uint32_t)lunar_stack_pattern_margin(
        (const volatile uint32_t *)(uintptr_t)_sstack_lo,
        ((uintptr_t)_sstack_top - (uintptr_t)_sstack_lo) / 4u);
    if (user < lunar_stack_user_margin) lunar_stack_user_margin = user;
    if (system < lunar_stack_system_margin) lunar_stack_system_margin = system;
    ++lunar_stack_samples;
}
#endif
#if defined(LUNAR_STARTUP_SET_INDEX) || defined(LUNAR_STARTUP_PROJECT_INDEX)
#include "content_catalogue.h"
#endif
#ifdef LUNAR_STARTUP_PROJECT_INDEX
#include "project_boot.h"
static volatile uint32_t startup_project_result, startup_project_report;
#endif
#ifdef LUNAR_STARTUP_SET_INDEX
#include "content_set.h"
static volatile uint32_t startup_set_result, startup_set_report;
#endif

typedef char lunar_probe_canvas_bound[(CV_MAX == 240u * 16u) ? 1 : -1];
static fm1_app_t app __attribute__((section(".pool"), aligned(16)));
#ifndef LUNAR_INSTANCE_MEMORY_BYTES
#define LUNAR_INSTANCE_MEMORY_BYTES 192000
#endif
#ifdef LUNAR_COMPRESSED_WAVETABLES
int lunar_wave_tables_init(void);
#endif
static uint8_t instance_memory[LUNAR_INSTANCE_MEMORY_BYTES]
    __attribute__((section(".pool"), aligned(16)));
static lunar_instance_pool_t instance_pool;
static volatile uint32_t arena_bind_failures;
static void *instance_alloc(void *ctx, size_t bytes) {
    return lunar_instance_pool_alloc((lunar_instance_pool_t *)ctx, bytes);
}
static void instance_free(void *ctx, void *memory) {
    if (lunar_instance_pool_free((lunar_instance_pool_t *)ctx, memory))
        arena_bind_failures++;
}
static lunar_audio_queue_t audio_queue;
static volatile uint32_t render_ticks_max, draw_ticks_max;
static volatile uint32_t initial_engine_result;

static void app_audio(int32_t *out, uint32_t n)
{
    /* The platform calls with 256 frames. Each dequeue is exactly 64. */
    if (n % LUNAR_AUDIO_BLOCK_FRAMES) {
        memset(out, 0, n * 2u * sizeof *out);
        return;
    }
    for (uint32_t i = 0; i < n; i += LUNAR_AUDIO_BLOCK_FRAMES)
        lunar_audio_pop(&audio_queue, out + i * 2u);
}

static void refill_audio(void)
{
    /* A slow engine must still yield to USB, watchdog and timed recovery. */
    for (unsigned blocks = 0;
         blocks < LUNAR_AUDIO_QUEUE_BLOCKS &&
         audio_queue.written - audio_queue.read < LUNAR_AUDIO_QUEUE_BLOCKS;
         ++blocks) {
        uint32_t start = fm1_ticks();
        const float *p = fm1_app_render(&app, LUNAR_AUDIO_BLOCK_FRAMES);
        uint32_t elapsed = fm1_ticks() - start;
        if (elapsed > render_ticks_max) render_ticks_max = elapsed;
        lunar_audio_push(&audio_queue, p);
    }
}

static void display_strip(uint32_t *row)
{
    if (!fm1_tft_pixels_valid(&app.tft)) return;
    if (lcd_busy) {
        if (!(FM1_LCD_SPI_CON & 0x8000u)) return;
        lcd_sync();
    }
    /* DMA reads cv_px, never the framebuffer that the app can redraw. */
    for (uint32_t i = 0; i < 240u * 16u; ++i)
        cv_px[i] = swap16(fm1_tft_pixel(&app.tft, *row * 240u + i));
    lcd_blit(0, *row, 240, 16, cv_px);
    *row = (*row + 16u) % 240u;
}

static void incoming_midi(void)
{
    uint8_t st, a, b;
    static uint8_t previous_channel = 255u;
    uint8_t channel = app.settings.midi_in_channel;
    if (channel != previous_channel) {
        /* Releases must not be filtered after their note-ons were accepted.
         * A filter change ends current notes before admitting the new stream. */
        if (previous_channel != 255u) fm1_app_all_notes_off(&app);
        previous_channel = channel;
    }
    /* Bound each poll so a sustained USB stream cannot starve rendering. */
    for (unsigned i = 0; i < 32u && midi_get(&st, &a, &b); ++i) {
        if (!lunar_midi_input_accept(st, a, b, channel)) continue;
        switch (st & 0xf0u) {
        case 0x90:
            if (b) fm1_app_note_on(&app, a, b);
            else fm1_app_note_off(&app, a);
            break;
        case 0x80: fm1_app_note_off(&app, a); break;
        case 0xe0:
            fm1_app_pitch_bend(&app, ((int)a + ((int)b << 7) - 8192) / 4096.0f);
            break;
        case 0xb0:
            if (a == 120u || a == 123u) fm1_app_all_notes_off(&app);
            break;
        }
    }
}

static void app_main(void)
{
    /* HAL: SELECT, ALGORITHM, KNOB1..4, PRESETS. Shared app differs. */
    static const uint8_t encoders[7] = {
        FM1_ENC_SELECT, FM1_ENC_ALGORITHM, FM1_ENC_KNOB1,
        FM1_ENC_KNOB2, FM1_ENC_KNOB3, FM1_ENC_KNOB4, FM1_ENC_PRESETS
    };
    uint32_t previous_keys = 0, row = 0, last_draw = 0;
    uint32_t start = fm1_ticks();
    int previous_master = -1;
#ifdef LUNAR_COMPRESSED_WAVETABLES
    if (lunar_wave_tables_init()) {
        arena_bind_failures++;
        fm1_audio_stop();
        usb_detach();
        fm1_delay_ms(30);
        bootguard_clear(&bootguard);
        fm1_enter_uboot();
    }
#endif
    fm1_app_init(&app, 44118.0f);
    if (lunar_instance_pool_init(&instance_pool, instance_memory, sizeof instance_memory) ||
        fm1_app_set_storage(&app, &instance_pool, instance_alloc, instance_free))
        arena_bind_failures++;
#ifdef LUNAR_STARTUP_SET_INDEX
    {
        fm1_state_report_t report;
        const lunar_content_asset_t *asset = &lunar_content_catalogue[LUNAR_STARTUP_SET_INDEX];
        startup_set_result = (uint32_t)lunar_content_start_set(
            &app, &instance_pool, asset->bytes, asset->size, 44118, &report);
        startup_set_report = (uint32_t)report.code;
    }
#endif
#ifdef LUNAR_STARTUP_PROJECT_INDEX
    {
        fm1_state_report_t report;
        fm1_state_report_init(&report);
        const lunar_content_asset_t *asset = &lunar_content_catalogue[LUNAR_STARTUP_PROJECT_INDEX];
        startup_project_result = !arena_bind_failures &&
            asset->kind == FM1_STATE_PROJECT && lunar_project_start(
                &app, &instance_pool, asset->bytes, asset->size, 44118, &report);
        startup_project_report = (uint32_t)report.code;
        if (!startup_project_result) {
            fm1_audio_stop();
            usb_detach();
            fm1_delay_ms(30);
            bootguard_clear(&bootguard);
            fm1_enter_uboot();
        }
    }
#else
    initial_engine_result = (uint32_t)fm1_app_select(&app, 0, fm1_app_find("trio"));
#endif
    refill_audio();
#ifdef LUNAR_STACK_WATERMARK
    sample_stacks();
    uint32_t last_stack_sample = fm1_ms;
#endif
    for (;;) {
        if (lunar_runtime_expired(fm1_ticks(), start, FM1_TICKS_PER_US)) {
            fm1_audio_stop();
            usb_detach();
            fm1_delay_ms(30);
            bootguard_clear(&bootguard);
            fm1_enter_uboot();
        }
        refill_audio();
        platform_poll();
#ifdef LUNAR_STACK_WATERMARK
        if ((uint32_t)(fm1_ms - last_stack_sample) >= 1000u) {
            sample_stacks();
            last_stack_sample = fm1_ms;
        }
#endif
        uint32_t keys = fm1_in.notes, changed = keys ^ previous_keys;
        previous_keys = keys;
        for (unsigned k = 0; k < 27u; ++k) {
            if ((changed >> k) & 1u) fm1_app_key(&app, k, (keys >> k) & 1u, 100);
            fm1_led_key(KEY_LED(k), (keys >> k) & 1u);
        }
        uint32_t released, pressed = fm1_input_edges(&released);
        for (unsigned b = 0; b < 14u; ++b) {
            if ((pressed >> b) & 1u) fm1_app_button(&app, b, 1);
            if ((released >> b) & 1u) fm1_app_button(&app, b, 0);
        }
        for (unsigned e = 0; e < 7u; ++e) {
            int delta = fm1_enc_take(e);
            if (delta) fm1_app_encoder(&app, encoders[e], delta);
        }
        int master = lunar_master_raw;
        if (master != previous_master) {
            previous_master = master;
            float position = master / 1024.0f;
            if (position < 0.0f) position = 0.0f;
            if (position > 1.0f) position = 1.0f;
            fm1_app_master(&app, position, 0);
        }
        incoming_midi();
        refill_audio();
        if ((uint32_t)(fm1_ms - last_draw) >= 33u) {
            uint32_t tick = fm1_ticks();
            last_draw = fm1_ms;
            fm1_app_draw(&app, 0);
#ifdef LUNAR_STACK_WATERMARK
            {
                char margins[20], samples[19];
                lunar_stack_readout(margins, samples, lunar_stack_user_margin,
                    lunar_stack_system_margin, lunar_stack_samples);
                /* Diagnostic footer owns these rows, with four-pixel padding.
                 * Values are observed free bytes, not a worst-case bound. */
                fm1_tft_fill(&app.tft, 0, 208, 240, 32, 0);
                fm1_tft_text(&app.tft, 4, 212, margins, 19, 1, 0xffff);
                fm1_tft_text(&app.tft, 4, 224, samples, 18, 1, 0xffff);
            }
#endif
            uint32_t elapsed = fm1_ticks() - tick;
            if (elapsed > draw_ticks_max) draw_ticks_max = elapsed;
        }
        refill_audio();
        display_strip(&row);
    }
}
