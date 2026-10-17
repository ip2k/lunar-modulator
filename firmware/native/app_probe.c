/* SPDX-License-Identifier: GPL-3.0-only */
/* Shared-application integration entry, NOT yet an admitted release.
 * Requires the reviewed generated platform: no NOR writes, 16-row canvas,
 * no OTA cleanup and unity HAL master gain. The shared instance pool is provisional;
 * complete catalogue RAM and timing acceptance remain separate. Device admission is a separate operation. */
#if !defined(LUNAR_APP_PROBE) || !FM1_APP_EXTERNAL_ARENAS
#error "Use the checked external-arena probe build"
#endif
#if defined(LUNAR_DIAGNOSTIC_CLOCK_SNAPSHOT) && !defined(LUNAR_DIAGNOSTIC_TELEMETRY)
#error "Clock snapshots require diagnostic telemetry"
#endif
#if defined(LUNAR_DIAGNOSTIC_PRODUCER_GAPS) && !defined(LUNAR_DIAGNOSTIC_TELEMETRY)
#error "Producer-gap profiling requires diagnostic telemetry"
#endif
#if defined(LUNAR_DIAGNOSTIC_IRQ_PROFILE) && !defined(LUNAR_DIAGNOSTIC_TELEMETRY)
#error "IRQ profiling requires diagnostic telemetry"
#endif
#if defined(LUNAR_DIAGNOSTIC_CPU_RATE) && !defined(LUNAR_DIAGNOSTIC_TELEMETRY)
#error "CPU-rate calibration requires diagnostic telemetry"
#endif
#if defined(LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE) && \
    (!defined(LUNAR_DIAGNOSTIC_TELEMETRY) || !defined(LUNAR_RENDER_STAGE_PROFILE))
#error "Engine render profiling requires telemetry and render-stage profiling"
#endif
#if defined(LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE) && \
    ((defined(LUNAR_DIAGNOSTIC_IRQ_PROFILE) && !defined(LUNAR_DIAGNOSTIC_RESAMPLER_STAGE_PROFILE)) || defined(LUNAR_DIAGNOSTIC_PRODUCER_GAPS))
#error "Engine render profile has a dedicated telemetry cadence"
#endif
#if defined(LUNAR_DIAGNOSTIC_RESAMPLER_STAGE_PROFILE) && \
    (!defined(LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE) || !defined(LUNAR_DIAGNOSTIC_IRQ_PROFILE) || defined(LUNAR_DIAGNOSTIC_CPU_RATE))
#error "Resampler stage profiling requires engine and IRQ profiles and excludes CPU-rate calibration"
#endif
#include <stdint.h>
#include <string.h>
#define APP_NAME "LUNAR MODULATOR"
#define APP_VER "APP PROBE"
#define FM1_BTN_OCT_DOWN DINGHY_BTN_OCT_DOWN
#define FM1_BTN_OCT_UP DINGHY_BTN_OCT_UP
static int32_t lunar_master_raw = 512;
static volatile uint32_t lunar_master_adc_raw;
#if defined(LUNAR_STARTUP_PROJECT_INDEX) && defined(LUNAR_STARTUP_SET_INDEX)
#error "Project and standalone SET startup cannot be enabled together"
#endif
#ifdef LUNAR_STARTUP_PROJECT_INDEX
static uint32_t lunar_selected_startup_project_index = LUNAR_STARTUP_PROJECT_INDEX;
#endif
#ifdef LUNAR_DIAGNOSTIC_CPU_RATE
static void lunar_cpu_rate_calibrate(void);
#endif
#include "platform.c"
#undef FM1_BTN_OCT_DOWN
#undef FM1_BTN_OCT_UP
#ifdef LUNAR_DIAGNOSTIC_CPU_RATE
#include "cpu_rate_calibration.h"
#endif
#include "fm1_app.h"
#include "audio_queue.h"
#include "instance_pool.h"
#include "midi_input.h"
#include "midi_diagnostic_readout.h"
#include "render_stage_profile.h"
#ifdef LUNAR_DIAGNOSTIC_TRIO_PULSE
#include "trio_diagnostic_pulse.h"
#endif
#ifdef LUNAR_DIAGNOSTIC_TELEMETRY
#include "diagnostic_telemetry.h"
#ifdef LUNAR_DIAGNOSTIC_RESAMPLER_STAGE_PROFILE
#include "engine_render_profile.h"
static uint32_t resampler_stage_values[LUNAR_RESAMPLER_STAGE_FIELDS];
/* Render runs on the main loop, never within a tracked IRQ. Quiesce the
 * IRQ writers for the timestamp/union pair only; packet work stays outside. */
void lunar_resampler_profile_snapshot(fm1_stage_stamp_t *stamp)
{
    uint32_t flags = irq_save();
    stamp->ticks = fm1_ticks();
    stamp->irq_ticks = lunar_irq_profile.busy_ticks;
    irq_restore(flags);
}
void lunar_resampler_profile_count(uint32_t engine, uint32_t counter)
{
    if (engine < 2u && counter < 4u)
        ++resampler_stage_values[4u + 16u * engine + 4u + counter];
}
void lunar_resampler_profile_stage(uint32_t engine, uint32_t stage,
                                  const fm1_stage_stamp_t *start,
                                  const fm1_stage_stamp_t *end)
{
    if (engine >= 2u || stage >= 4u) return;
    unsigned base = 4u + 16u * engine + 8u + 2u * stage;
    resampler_stage_values[base] += end->ticks - start->ticks;
    resampler_stage_values[base + 1u] += end->irq_ticks - start->irq_ticks;
}
#endif
#ifdef LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE
static volatile uint32_t engine_profile_values[LUNAR_ENGINE_PROFILE_FIELDS];
uint32_t lunar_engine_profile_ticks(void) { return fm1_ticks(); }
void lunar_engine_profile_render(uint32_t engine, uint32_t ticks,
                                 uint32_t block_ticks, uint32_t block_calls)
{
    if (engine >= 2u) return;
    const unsigned base = 1u + engine * 4u;
    engine_profile_values[base] += ticks;
    engine_profile_values[base + 1u] += 1u;
    engine_profile_values[base + 2u] += block_ticks;
    engine_profile_values[base + 3u] += block_calls;
#ifdef LUNAR_DIAGNOSTIC_RESAMPLER_STAGE_PROFILE
    unsigned stage_base = 4u + 16u * engine;
    resampler_stage_values[stage_base] += ticks;
    ++resampler_stage_values[stage_base + 1u];
    resampler_stage_values[stage_base + 2u] += block_ticks;
    resampler_stage_values[stage_base + 3u] += block_calls;
#endif
}
#endif
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
#include "producer_gap_profile.h"
static lunar_producer_gap_profile_t producer_gap_profile;
#endif
#ifdef LUNAR_DIAGNOSTIC_CLOCK_SNAPSHOT
#include "clock_snapshot.h"
static uint32_t clock_snapshot_values[LUNAR_CLOCK_FIELDS];
static uint32_t pll_snapshot_values[LUNAR_PLL_FIELDS];
#endif
#endif
#ifdef LUNAR_DIAGNOSTIC_SONG_PLAY
#include "diagnostic_song_play.h"
#endif
#include "runtime_mode.h"
#ifdef LUNAR_UART1_MIDI
#include "midi_stream.h"
#include "midi_uart_stream.h"
#include "fm1_uart.h"
#endif
#ifdef LUNAR_STACK_WATERMARK
#include "stack_watermark.h"
#include "stack_readout.h"
#include "realtime_readout.h"
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
#ifdef LUNAR_PROJECT_SAVE_SERVICE
#include "save_quiesce.h"
#include "project_save_service.h"
static lunar_audio_pause_t save_pause;
/* Deliberately closed until physical geometry, ownership and migration pass.
 * A compile flag enables scheduling, never grants permission to write flash. */
static lunar_project_save_service save_service = {
    .pause_ctx = &save_pause,
    .pause = lunar_save_quiesce_begin,
    .resume = lunar_save_quiesce_end
};
#endif
static volatile uint32_t render_ticks_max, draw_ticks_max;
static volatile uint32_t initial_engine_result;
#ifdef LUNAR_RENDER_STAGE_PROFILE
typedef struct {
    uint32_t ticks, maximum, calls;
} lunar_profile_stage_t;
static lunar_profile_stage_t lunar_profile_window[LUNAR_RENDER_PROFILE_STAGE_COUNT];
uint32_t lunar_profile_ticks(void) { return fm1_ticks(); }
void lunar_profile_finish(unsigned stage, uint32_t start_ticks)
{
    if (stage >= LUNAR_RENDER_PROFILE_STAGE_COUNT) return;
    uint32_t elapsed = fm1_ticks() - start_ticks;
    lunar_profile_stage_t *sample = &lunar_profile_window[stage];
    sample->ticks += elapsed;
    if (elapsed > sample->maximum) sample->maximum = elapsed;
    ++sample->calls;
}
#endif

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

#ifdef LUNAR_DIAGNOSTIC_IRQ_PROFILE
static uint32_t irq_render_calls, irq_render_elapsed_ticks, irq_render_irq_ticks;
#endif

static void refill_audio(void)
{
    /* A slow engine must still yield to USB, watchdog and timed recovery. */
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
    lunar_producer_gap_refill_entry(&producer_gap_profile, fm1_ticks());
    lunar_producer_gap_queue(&producer_gap_profile,
        audio_queue.written - audio_queue.read);
#endif
    for (unsigned blocks = 0;
         blocks < LUNAR_AUDIO_QUEUE_BLOCKS &&
         audio_queue.written - audio_queue.read < LUNAR_AUDIO_QUEUE_BLOCKS;
         ++blocks) {
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
        lunar_producer_gap_queue(&producer_gap_profile,
            audio_queue.written - audio_queue.read);
#endif
#ifdef LUNAR_DIAGNOSTIC_IRQ_PROFILE
        uint32_t irq_flags = irq_save();
        uint32_t start = fm1_ticks(), busy_start = lunar_irq_profile.busy_ticks;
        irq_restore(irq_flags);
#else
        uint32_t start = fm1_ticks();
#endif
        const float *p = fm1_app_render(&app, LUNAR_AUDIO_BLOCK_FRAMES);
#ifdef LUNAR_DIAGNOSTIC_IRQ_PROFILE
        irq_flags = irq_save();
        uint32_t elapsed = fm1_ticks() - start;
        irq_render_irq_ticks += lunar_irq_profile.busy_ticks - busy_start;
        irq_restore(irq_flags);
        ++irq_render_calls;
        irq_render_elapsed_ticks += elapsed;
#else
        uint32_t elapsed = fm1_ticks() - start;
#endif
        if (elapsed > render_ticks_max) render_ticks_max = elapsed;
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
        int published = lunar_audio_push(&audio_queue, p);
        lunar_producer_gap_render(&producer_gap_profile, elapsed);
        lunar_producer_gap_queue(&producer_gap_profile,
            audio_queue.written - audio_queue.read);
        if (published) lunar_producer_gap_published(&producer_gap_profile, fm1_ticks());
#else
        lunar_audio_push(&audio_queue, p);
#endif
    }
}

static void display_strip(uint32_t *row)
{
    LUNAR_PROFILE_START(profile_start);
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
    uint32_t wait_ticks = 0;
    uint32_t work_start = 0;
    uint8_t did_work = 0;
#endif
    if (!fm1_tft_pixels_valid(&app.tft)) goto done;
    if (lcd_busy) {
        if (!(FM1_LCD_SPI_CON & 0x8000u)) goto done;
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
        work_start = fm1_ticks();
#endif
        lcd_sync();
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
        wait_ticks = fm1_ticks() - work_start;
#endif
    }
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
    work_start = fm1_ticks();
    did_work = 1;
#endif
    /* DMA reads cv_px, never the framebuffer that the app can redraw. */
    for (uint32_t i = 0; i < 240u * 16u; ++i)
        cv_px[i] = swap16(fm1_tft_pixel(&app.tft, *row * 240u + i));
    lcd_blit(0, *row, 240, 16, cv_px);
    *row = (*row + 16u) % 240u;
done:
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
    lunar_producer_gap_display(&producer_gap_profile, wait_ticks,
        did_work ? fm1_ticks() - work_start : 0u);
#endif
    LUNAR_PROFILE_FINISH(LUNAR_PROFILE_DISPLAY_STRIP, profile_start);
}

volatile uint32_t lunar_midi_usb_messages __attribute__((used));
volatile uint32_t lunar_midi_uart_bytes __attribute__((used));
volatile uint32_t lunar_midi_accepted_noteons __attribute__((used));
volatile uint32_t lunar_midi_rejected_messages __attribute__((used));
static void apply_midi_event(uint8_t st, uint8_t a, uint8_t b, uint8_t channel)
{
    if (st == 0xfau || st == 0xfbu || st == 0xfcu) {
        (void)fm1_app_seq_midi_transport(&app, st);
        return;
    }
    if (!lunar_midi_input_accept(st, a, b, channel)) {
        ++lunar_midi_rejected_messages;
        return;
    }
    if ((st & 0xf0u) == 0x90u && b) ++lunar_midi_accepted_noteons;
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
#ifdef LUNAR_UART1_MIDI
static uint8_t uart_midi_ring[256] __attribute__((aligned(16)));
static uint32_t uart_midi_cursor, uart_midi_pending;
void lunar_native_midi_uart_init(void)
{
    lunar_midi_stream_reset();
    fm1_uart1_midi_init(uart_midi_ring, sizeof uart_midi_ring);
}
static void uart_midi_event(void *ctx, uint8_t st, uint8_t a, uint8_t b)
{
    apply_midi_event(st, a, b, *(const uint8_t *)ctx);
}
static void uart_midi_poll(uint8_t channel)
{
    uint32_t received = fm1_uart1_rx_take();
    int consumed = lunar_midi_uart_drain(uart_midi_ring, sizeof uart_midi_ring,
        &uart_midi_cursor, &uart_midi_pending, received, 32u,
        uart_midi_event, &channel);
    if (consumed > 0) lunar_midi_uart_bytes += (uint32_t)consumed;
}
#endif

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
        ++lunar_midi_usb_messages;
        apply_midi_event(st, a, b, channel);
    }
#ifdef LUNAR_UART1_MIDI
    uart_midi_poll(channel);
#endif
}

#ifdef LUNAR_DIAGNOSTIC_TELEMETRY
static void diagnostic_report(void)
{
    static uint32_t last_report;
    uint32_t now = fm1_ms;
    if ((uint32_t)(now - last_report) < 1000u) return;
    last_report = now;
    /* This diagnostic's main loop is the only MIDI-output producer. The USB
     * consumer may free slots meanwhile; reserve room for the whole frame
     * before publishing its first packet. Never block audio for a report. */
    if (!usb.config || mo_w - mo_r > MQ - LUNAR_DIAGNOSTIC_PACKETS) return;
    uint32_t values[LUNAR_DIAGNOSTIC_FIELDS] = {
        now, render_ticks_max, draw_ticks_max, audio_queue.underruns,
        lunar_midi_usb_messages, lunar_midi_uart_bytes,
        lunar_midi_accepted_noteons, lunar_midi_rejected_messages,
        lunar_master_adc_raw, UINT32_MAX, UINT32_MAX, 0u,
        initial_engine_result, audio_queue.written
    };
#ifdef LUNAR_STACK_WATERMARK
    values[9] = lunar_stack_user_margin;
    values[10] = lunar_stack_system_margin;
    values[11] = lunar_stack_samples;
#endif
    uint32_t packets[LUNAR_DIAGNOSTIC_PACKETS];
    lunar_diagnostic_packets(packets, values);
    for (unsigned i = 0; i < LUNAR_DIAGNOSTIC_PACKETS; ++i)
        midi_out_event(packets[i]);
}

#ifdef LUNAR_DIAGNOSTIC_CPU_RATE
static void diagnostic_cpu_rate_report(void)
{
    static uint32_t last_report;
    uint32_t now = fm1_ms;
    if ((uint32_t)(now - last_report) < 30000u || !usb.config ||
        mo_w - mo_r > MQ - LUNAR_CPU_RATE_PACKETS) return;
    const uint32_t values[LUNAR_CPU_RATE_FIELDS] = {
        lunar_cpu_rate_result.uptime_ms,
        lunar_cpu_rate_result.iterations,
        lunar_cpu_rate_result.trials,
        lunar_cpu_rate_result.xip_ticks,
        lunar_cpu_rate_result.ram_ticks,
        lunar_cpu_rate_result.xip_checksum,
        lunar_cpu_rate_result.ram_checksum,
        lunar_cpu_rate_result.status,
    };
    for (unsigned i = 0; i < LUNAR_CPU_RATE_PACKETS; ++i)
        midi_out_event(lunar_cpu_rate_packet(values, i));
    last_report = now;
}
#endif

#ifdef LUNAR_RENDER_STAGE_PROFILE
static void diagnostic_profile_report(void)
{
    static uint32_t last_report;
    static uint32_t values[LUNAR_PROFILE_FIELDS];
    uint32_t now = fm1_ms;
    if ((uint32_t)(now - last_report) < 1000u) return;
    if (!usb.config || mo_w - mo_r > MQ - LUNAR_PROFILE_PACKETS) return;
    values[0] = now;
    for (unsigned i = 0; i < LUNAR_RENDER_PROFILE_STAGE_COUNT; ++i) {
        values[1u + 3u * i] = lunar_profile_window[i].ticks;
        values[2u + 3u * i] = lunar_profile_window[i].maximum;
        values[3u + 3u * i] = lunar_profile_window[i].calls;
    }
    for (unsigned i = 0; i < LUNAR_PROFILE_PACKETS; ++i)
        midi_out_event(lunar_profile_packet(values, i));
    memset(lunar_profile_window, 0, sizeof lunar_profile_window);
    last_report = now;
}
#endif

#ifdef LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE
static void diagnostic_engine_profile_report(void)
{
    static uint32_t last_report;
    uint32_t values[LUNAR_ENGINE_PROFILE_FIELDS];
    uint32_t now = fm1_ms;
    if ((uint32_t)(now - last_report) < 4000u || !usb.config ||
        mo_w - mo_r > MQ - LUNAR_ENGINE_PROFILE_PACKETS) return;
    values[0] = now;
    for (unsigned i = 1; i < LUNAR_ENGINE_PROFILE_FIELDS; ++i)
        values[i] = engine_profile_values[i];
    for (unsigned i = 0; i < LUNAR_ENGINE_PROFILE_PACKETS; ++i)
        midi_out_event(lunar_engine_profile_packet(values, i));
    last_report = now;
}
#endif

#ifdef LUNAR_DIAGNOSTIC_RESAMPLER_STAGE_PROFILE
static void diagnostic_resampler_stage_report(void)
{
    static uint32_t last_report;
    uint32_t now = fm1_ms;
    if ((uint32_t)(now - last_report) < 4000u || !usb.config ||
        mo_w - mo_r > MQ - LUNAR_RESAMPLER_STAGE_PACKETS) return;
    uint32_t values[LUNAR_RESAMPLER_STAGE_FIELDS];
    memcpy(values, resampler_stage_values, sizeof values);
    values[0] = now;
    values[1] = FM1_RESAMPLER_PROFILE_STRIDE;
    uint32_t flags = irq_save();
    values[2] = lunar_irq_profile.overflow_count;
    values[3] = lunar_irq_profile.mismatch_count;
    irq_restore(flags);
    for (unsigned i = 0; i < LUNAR_RESAMPLER_STAGE_PACKETS; ++i)
        midi_out_event(lunar_resampler_stage_packet(values, i));
    last_report = now;
}
#endif

/* Both frames share the same USB-MIDI ring. The opt-in cadence alternates
 * bounded slots so no complete frame is perpetually crowded out. */

#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
static void diagnostic_producer_gap_report(void)
{
    static uint32_t last_report;
    uint32_t now = fm1_ms;
    if ((uint32_t)(now - last_report) < 1000u || !usb.config ||
        mo_w - mo_r > MQ - LUNAR_PRODUCER_GAP_PACKETS) return;
    uint32_t values[LUNAR_PRODUCER_GAP_FIELDS];
    uint32_t packets[LUNAR_PRODUCER_GAP_PACKETS];
    lunar_producer_gap_snapshot(&producer_gap_profile, now, values);
    for (unsigned i = 0; i < LUNAR_PRODUCER_GAP_PACKETS; ++i)
        packets[i] = lunar_producer_gap_packet(values, i);
    for (unsigned i = 0; i < LUNAR_PRODUCER_GAP_PACKETS; ++i)
        midi_out_event(packets[i]);
    last_report = now;
}
#endif

#ifdef LUNAR_DIAGNOSTIC_IRQ_PROFILE
static void diagnostic_irq_report(void)
{
    static uint32_t last_report;
    uint32_t now = fm1_ms;
    if ((uint32_t)(now - last_report) < 1000u || !usb.config ||
        mo_w - mo_r > MQ - LUNAR_IRQ_PACKETS) return;
    uint32_t values[LUNAR_IRQ_FIELDS];
    /* Freeze only the bounded multiword counter copy, never packet encoding
     * or USB output. Main-loop render counters have no concurrent writer. */
    uint32_t flags = irq_save();
    values[0] = now;
    values[1] = lunar_irq_profile.busy_ticks;
    for (unsigned i = 0; i < LUNAR_IRQ_PROFILE_SOURCE_COUNT; ++i) {
        values[2u + 3u * i] = lunar_irq_profile.source[i].count;
        values[3u + 3u * i] = lunar_irq_profile.source[i].total_ticks;
        values[4u + 3u * i] = lunar_irq_profile.source[i].max_ticks;
    }
    values[20] = lunar_irq_profile.overflow_count;
    values[21] = lunar_irq_profile.mismatch_count;
    irq_restore(flags);
    values[17] = irq_render_calls;
    values[18] = irq_render_elapsed_ticks;
    values[19] = irq_render_irq_ticks;
    for (unsigned i = 0; i < LUNAR_IRQ_PACKETS; ++i)
        midi_out_event(lunar_irq_packet(values, i));
    last_report = now;
}
#endif

static void diagnostic_reports(void)
{
#ifdef LUNAR_DIAGNOSTIC_CPU_RATE
    diagnostic_cpu_rate_report();
#endif
#ifdef LUNAR_DIAGNOSTIC_CLOCK_SNAPSHOT
    static uint32_t last_clock_report;
    static uint32_t last_pll_report;
    /* Repeat the immutable sample for hosts that attach after startup. It is
     * only ten packets, and is deferred until a complete frame fits. */
    if ((uint32_t)(fm1_ms - last_clock_report) >= 10000u && usb.config &&
        mo_w - mo_r <= MQ - LUNAR_CLOCK_PACKETS) {
        for (unsigned i = 0; i < LUNAR_CLOCK_PACKETS; ++i)
            midi_out_event(lunar_clock_packet(clock_snapshot_values, i));
        last_clock_report = fm1_ms;
        return;
    }
    /* A second ten-second cadence, offset by five seconds, carries only raw
     * PLL inputs. Reserve the whole frame before publishing any packet. */
    if ((last_pll_report == 0u ? fm1_ms >= 5000u :
         (uint32_t)(fm1_ms - last_pll_report) >= 10000u) && usb.config &&
        mo_w - mo_r <= MQ - LUNAR_PLL_PACKETS) {
        for (unsigned i = 0; i < LUNAR_PLL_PACKETS; ++i)
            midi_out_event(lunar_pll_packet(pll_snapshot_values, i));
        last_pll_report = fm1_ms;
        return;
    }
#endif
#if defined(LUNAR_DIAGNOSTIC_RESAMPLER_STAGE_PROFILE)
    switch ((fm1_ms / 1000u) % 4u) {
    case 0: diagnostic_report(); break;
    case 1: diagnostic_profile_report(); break;
    case 2: diagnostic_engine_profile_report(); break;
    default: diagnostic_resampler_stage_report(); break;
    }
#elif defined(LUNAR_DIAGNOSTIC_IRQ_PROFILE)
    switch ((fm1_ms / 1000u) % 4u) {
    case 0: diagnostic_report(); break;
    case 1:
#ifdef LUNAR_RENDER_STAGE_PROFILE
        diagnostic_profile_report();
#else
        diagnostic_report();
#endif
        break;
    case 2:
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
        diagnostic_producer_gap_report();
#else
        diagnostic_report();
#endif
        break;
    default: diagnostic_irq_report(); break;
    }
#elif defined(LUNAR_DIAGNOSTIC_PRODUCER_GAPS)
#ifdef LUNAR_RENDER_STAGE_PROFILE
    switch ((fm1_ms / 1000u) % 3u) {
    case 0: diagnostic_report(); break;
    case 1: diagnostic_profile_report(); break;
    default: diagnostic_producer_gap_report(); break;
    }
#else
    if (((fm1_ms / 1000u) & 1u) == 0u) diagnostic_report();
    else diagnostic_producer_gap_report();
#endif
#elif defined(LUNAR_RENDER_STAGE_PROFILE)
#ifdef LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE
    switch ((fm1_ms / 1000u) % 4u) {
    case 0: diagnostic_report(); break;
    case 1: diagnostic_profile_report(); break;
    case 2: diagnostic_report(); break;
    default: diagnostic_engine_profile_report(); break;
    }
#else
    if (((fm1_ms / 1000u) & 1u) == 0u) diagnostic_report();
    else diagnostic_profile_report();
#endif
#else
    diagnostic_report();
#endif
}
#endif

static void app_main(void)
{
    /* HAL: SELECT, ALGORITHM, KNOB1..4, PRESETS. Shared app differs. */
    static const uint8_t encoders[7] = {
        FM1_ENC_SELECT, FM1_ENC_ALGORITHM, FM1_ENC_KNOB1,
        FM1_ENC_KNOB2, FM1_ENC_KNOB3, FM1_ENC_KNOB4, FM1_ENC_PRESETS
    };
    uint32_t previous_keys = 0, row = 0, last_draw = 0;
    uint32_t start = fm1_ms;
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
    lunar_producer_gap_init(&producer_gap_profile);
#endif
#ifdef LUNAR_DIAGNOSTIC_CLOCK_SNAPSHOT
    lunar_clock_snapshot(clock_snapshot_values, start);
    lunar_pll_snapshot(pll_snapshot_values, start);
#endif
#ifdef LUNAR_DIAGNOSTIC_TRIO_PULSE
    uint32_t pulse_start = 0;
#endif
#ifdef LUNAR_DIAGNOSTIC_SONG_PLAY
    uint32_t song_ready_ms = 0;
    uint8_t song_play_attempted = 0;
#endif
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
#ifdef LUNAR_PROJECT_SAVE_SERVICE
    app.store_ready = lunar_project_save_service_ready(&save_service);
#endif
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
        const lunar_content_asset_t *asset = &lunar_content_catalogue[lunar_selected_startup_project_index];
        startup_project_result = !arena_bind_failures && asset->kind == FM1_STATE_PROJECT;
#ifdef LUNAR_COMPANION_SET_CHOOSER
        if (startup_project_result && lunar_selected_companion_set_index != UINT32_MAX) {
            if (lunar_selected_companion_set_index >= lunar_content_count) {
                startup_project_result = 0;
            } else {
                const lunar_content_asset_t *set =
                    &lunar_content_catalogue[lunar_selected_companion_set_index];
                startup_project_result = set->kind == FM1_STATE_SET &&
                    set->parent_project_index == lunar_selected_startup_project_index &&
                    lunar_project_start_with_set(&app, &instance_pool,
                        asset->bytes, asset->size, set->bytes, set->size, 44118, &report);
            }
        } else
#endif
        if (startup_project_result) {
            startup_project_result = lunar_project_start(
                &app, &instance_pool, asset->bytes, asset->size, 44118, &report);
        }
        startup_project_report = (uint32_t)report.code;
        if (!startup_project_result) {
            fm1_audio_stop();
            usb_detach();
            fm1_delay_ms(30);
            bootguard_clear(&bootguard);
            fm1_enter_uboot();
        }
        /* Preserve the exact startup-project API result in the existing
         * telemetry field; project starts return 1 on success. */
        initial_engine_result = startup_project_result;
    }
#else
    initial_engine_result = (uint32_t)fm1_app_select(&app, 0, fm1_app_find("trio"));
#endif
    refill_audio();
#ifdef LUNAR_DIAGNOSTIC_TRIO_PULSE
    /* Start the controlled pulse only after engines/content and initial audio
     * queue production are ready; keep the overall runtime deadline unchanged. */
    pulse_start = fm1_ms;
#endif
#ifdef LUNAR_DIAGNOSTIC_SONG_PLAY
    song_ready_ms = fm1_ms;
#endif
#ifdef LUNAR_STACK_WATERMARK
    sample_stacks();
    uint32_t last_stack_sample = fm1_ms;
#endif
    for (;;) {
        if (lunar_runtime_expired(fm1_ms, start)) {
            fm1_audio_stop();
            usb_detach();
            fm1_delay_ms(30);
            bootguard_clear(&bootguard);
            fm1_enter_uboot();
        }
        refill_audio();
        platform_poll();
#ifdef LUNAR_DIAGNOSTIC_SONG_PLAY
        if (lunar_diagnostic_song_play_poll(fm1_ms, song_ready_ms,
                                           &song_play_attempted) && !app.ui.playing) {
            fm1_app_button(&app, FM1_BTN_PLAY, 1);
            fm1_app_button(&app, FM1_BTN_PLAY, 0);
        }
#endif
#ifdef LUNAR_DIAGNOSTIC_TRIO_PULSE
        {
            static uint8_t pulse_state;
            int pulse_event = lunar_trio_diagnostic_pulse_poll(
                fm1_ms, pulse_start, &pulse_state);
            if (pulse_event > 0) fm1_app_note_on(&app, 60u, 100u);
            else if (pulse_event < 0) fm1_app_note_off(&app, 60u);
        }
#endif
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
#ifdef LUNAR_DIAGNOSTIC_TELEMETRY
        diagnostic_reports();
#endif
#ifdef LUNAR_PROJECT_SAVE_SERVICE
        (void)lunar_project_save_service_poll(&save_service, &app);
#endif
        refill_audio();
        if ((uint32_t)(fm1_ms - last_draw) >= 33u) {
            uint32_t tick = fm1_ticks();
            last_draw = fm1_ms;
            fm1_app_draw(&app, 0);
#ifdef LUNAR_STACK_WATERMARK
            {
                char margins[20], samples[19], timing[36], midi_diag[27];
                lunar_stack_readout(margins, samples, lunar_stack_user_margin,
                    lunar_stack_system_margin, lunar_stack_samples);
                lunar_realtime_readout(timing, render_ticks_max / FM1_TICKS_PER_US,
                    draw_ticks_max / FM1_TICKS_PER_US, audio_queue.underruns);
                /* Diagnostic footer owns these rows, with four-pixel padding.
                 * Values are observed free bytes, not a worst-case bound. */
                fm1_tft_fill(&app.tft, 0, 208, 240, 32, 0);
                fm1_tft_text(&app.tft, 4, 212, margins, 19, 1, 0xffff);
                fm1_tft_text(&app.tft, 128, 212, "R/D us", 6, 1, 0xffff);
                if ((fm1_ms / 1000u) & 1u) {
                    lunar_midi_diagnostic_readout(midi_diag,
                        lunar_midi_usb_messages, lunar_midi_uart_bytes,
                        lunar_midi_accepted_noteons, lunar_master_adc_raw);
                    fm1_tft_text(&app.tft, 4, 224, midi_diag, 26, 1, 0xffff);
                } else {
                    fm1_tft_text(&app.tft, 4, 224, timing, 35, 1, 0xffff);
                }
            }
#endif
            uint32_t elapsed = fm1_ticks() - tick;
            if (elapsed > draw_ticks_max) draw_ticks_max = elapsed;
        }
        refill_audio();
        display_strip(&row);
    }
}
