/* SPDX-License-Identifier: MIT
 * The FM-1 application's AC79 SDK glue (pinned V1.2.13 libraries, demo_hello
 * shell prepared by tools/jieli/prepare-fm1-app.py). Owns the hardware:
 *
 *   TIMER4 (24 MHz clock) -> board I/O -> backlight and the boot screen
 *   -> the app and the native pipeline -> eight blocks prefilled
 *   -> panel/MIDI task -> ALNK0 (IRQ 11, CPU0) -> the producer loop.
 *
 * The producer and the ALNK0 interrupt follow the dev-kit DAC transport
 * (firmware/devkit/renderer_pipeline_dac.c): reserve, produce, publish,
 * harvest on the CPU0 task; acquire and retire one output per DMA half in
 * the interrupt. Unlike the kit's soak there is no end: the pipeline is
 * built with LUNAR_PIPELINE_UNBOUNDED.
 *
 * NOTHING HERE HAS RUN ON AN FM-1. Every pin and peripheral fact is
 * [reported] from Felucca, fm1-nes and SLOOP (firmware/board/README.md) or
 * [verified] against the SDK headers; see notes/2026-11-08-fm1-app-image.md.
 */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include <string.h>

#include "fm1_live.h"
#include "renderer_pipeline_sdk.h"
#include "failopen_sdk.h"
#include "../board/board_io.h"
#include "../board/matrix.h"
#include "../board/adc.h"
#include "../board/midi_uart.h"
#include "../board/alnk0_audio.h"
#include "../display/spi1_transport.h"
#include "../display/m5_pattern.h"

#if !defined(LUNAR_PIPELINE_UNBOUNDED)
#error The FM-1 application needs the unbounded pipeline lifetime
#endif
#ifndef LUNAR_FM1_BUILD_NAME
#define LUNAR_FM1_BUILD_NAME "LUNAR FM-1"
#endif
#define PANEL_POLLS 65536u
#define WATCH_MS 2000u          /* a task silent this long resets the unit */
/* The main task's watch starts before its first stage, so a stage that
 * hangs resets too. Generous, because no stage has been timed on an FM-1:
 * the boot screen, the app's init and the prefill [inferred: well under 1 s
 * each from the kit, not measured here]. */
#define MAIN_WATCH_MS 5000u
#define MIDI_RING_BYTES 256u    /* 82 ms of 31,250-baud MIDI */
#define MIDI_BUDGET 64u
#define ADC_POLLS 4096u
#define STATUS_BLOCKS 8192u     /* about 11.9 s at 44,118 Hz */
/* Fault codes recorded in the fail-open record before a deliberate reset,
 * beside failopen_core.h's STALL (0x10 + slot) and TEST (0x80 + case). */
#define FAULT_APP 0x40u
enum { STAGE_TIMER = 1, STAGE_INIT, STAGE_PIPELINE, STAGE_PREFILL, STAGE_PANEL, STAGE_ALNK0,
       STAGE_REFUSED };

/* ---- clock: TIMER4 on the 24 MHz oscillator, as every kit image ---------- */
static uint32_t now(void) { return JL_TIMER4->CNT; }
static void fence(void) { __asm__ volatile("csync;" ::: "memory"); }

static int timer4_take(void)
{
    if (JL_TIMER4->CON & 3u) return 0;     /* someone else owns it */
    JL_TIMER4->CON = (1u << 14);
    JL_TIMER4->CNT = 0;
    JL_TIMER4->PRD = 0xffffffffu;
    JL_TIMER4->CON = 9u;                   /* oscillator, /1, enabled */
    fence();
    return 1;
}

/* `ms` milliseconds on a 24 MHz oscillator: the kit's, and the FM-1's
 * crystal [verified: V15 isd_config OSC_FREQ, docs/02]. A slower clock
 * would lengthen the wait, a faster one shorten it. */
static int wait_ms(void *ctx, unsigned ms)
{
    uint32_t start = now();
    (void)ctx;
    while ((uint32_t)(now() - start) < ms * 24000u) {}
    return 1;
}

/* ---- the ALNK0 transport (IRQ 11, CPU0) ---------------------------------- */
static int32_t alnk0_buffer[2u * LUNAR_ALNK0_HALF_WORDS] __attribute__((aligned(32)));
static struct lunar_alnk0_ops alnk0;
static struct {
    volatile uint32_t next, callbacks, underruns, faults, irq_max;
} out;

#pragma code_seg(".volatile_ram_code")
static ___interrupt void alnk0_irq(void)
{
    uint32_t begin = now(), elapsed;
    if (lunar_alnk0_pending(&alnk0) & (1u << LUNAR_ALNK0_TX_CH)) {
        int32_t *half = alnk0_buffer + lunar_alnk0_free_half(&alnk0) * LUNAR_ALNK0_HALF_WORDS;
        const int16_t *pcm = 0;
        const lunar_pipeline_result_t *r = 0;
        unsigned i;
        int got = lunar_pipeline_error() ? -1 : lunar_pipeline_output_acquire(out.next, &pcm, &r);
        if (got == 1) {
            /* Output words: L, R, L, R per frame (fm1_live.c); take the first pair. */
            for (i = 0; i < LUNAR_FM1_BLOCK; ++i) {
                half[2u * i] = lunar_alnk0_word_from_q23((int32_t)pcm[4u * i] * 256);
                half[2u * i + 1u] = lunar_alnk0_word_from_q23((int32_t)pcm[4u * i + 1u] * 256);
            }
            if (lunar_pipeline_output_retire(out.next) == 1) ++out.next;
            else ++out.faults;
        } else {
            /* Late or refused: silence this half, try the same tag next time. */
            for (i = 0; i < LUNAR_ALNK0_HALF_WORDS; ++i) half[i] = 0;
            if (got == 0) ++out.underruns; else ++out.faults;
        }
        fence();
        ++out.callbacks;
    }
    lunar_alnk0_ack(&alnk0, 1u << LUNAR_ALNK0_TX_CH);
    elapsed = now() - begin;
    if (elapsed > out.irq_max) out.irq_max = elapsed;
}
#pragma code_seg()

static int alnk0_attach(void *ctx, unsigned irq, unsigned priority)
{
    (void)ctx;
    if (irq != LUNAR_ALNK0_IRQ) return -1;
    request_irq(irq, priority, alnk0_irq, 0);   /* CPU0: the output owner */
    return 0;
}

static int alnk0_delay(void *ctx, unsigned ms)
{
    return wait_ms(ctx, ms) ? 0 : -1;
}

/* ---- panel and MIDI: one CPU0 task, below the producer -------------------- */
static struct lunar_board_io io;
static struct lunar_fm1_panel panel_state;
static struct lunar_adc adc;
static struct lunar_midi_uart midi;
static volatile unsigned char midi_ring[MIDI_RING_BYTES] __attribute__((aligned(16)));
static int adc_ok, midi_ok, matrix_ok;
static volatile uint32_t battery_raw;

static void midi_emit(void *ctx, const struct lunar_midi_message *m)
{
    struct lunar_fm1_event e;
    if (lunar_fm1_midi_event(m, &e)) lunar_fm1_queue_push((struct lunar_fm1_queue *)ctx, &e);
}

static void panel_task(void *unused)
{
    static const unsigned char leds[LUNAR_MATRIX_COLUMNS] = {0}; /* TODO(app): LED state */
    struct lunar_fm1_queue *q = lunar_fm1_live_queue();
    unsigned char rows[LUNAR_MATRIX_COLUMNS];
    unsigned scans = 0;
    int slot = lunar_failopen_watch(WATCH_MS);
    (void)unused;
    for (;;) {
        unsigned raw = 0;
        int master = -1;
        if (matrix_ok && lunar_matrix_scan(&io, leds, rows)) {
            if (adc_ok && lunar_adc_read(&adc, LUNAR_ADC_MASTER, &raw)) master = (int)raw;
            lunar_fm1_panel_update(&panel_state, rows, master, q);
        }
        if (midi_ok) lunar_midi_uart_poll(&midi, MIDI_BUDGET, midi_emit, q);
        if (adc_ok && !(++scans & 1023u) && lunar_adc_read(&adc, LUNAR_ADC_BATTERY, &raw))
            battery_raw = raw;
        /* TODO(hardware): one SDK tick (10 ms) a pass. Encoders decode on two
         * identical samples, so fast turns may lose detents; measure. */
        lunar_failopen_beat(slot);
        os_time_dly(1);
    }
}

/* Recovery combination (docs/07 section 4 rule 4): OCT- and OCT+ held, and
 * nothing else, on three consecutive scans at boot, enters mask-ROM USB
 * update mode. TODO(owner): the combination is a proposal, not decided. */
int lunar_failopen_key_requested(void)
{
    struct lunar_board_io bio;
    unsigned char rows[LUNAR_MATRIX_COLUMNS];
    static const unsigned char none[LUNAR_MATRIX_COLUMNS] = {0};
    unsigned pressed[2], agree = 0, pass;
    lunar_board_native_io(&bio);
    if (!lunar_matrix_init(&bio)) return 0;
    for (pass = 0; pass < 3u; ++pass) {
        if (!lunar_matrix_scan(&bio, none, rows)) break;
        lunar_keys_decode(rows, pressed);
        if (pressed[0] == ((1u << 0) | (1u << 1)) && !pressed[1]) ++agree;
    }
    lunar_matrix_release(&bio);
    return agree == 3u;
}

/* ---- the producer: CPU0, priority 16 ------------------------------------- */
static uint32_t produced, harvested;
static uint32_t p_max, c_max;

static int harvest(void)
{
    lunar_pipeline_completion_t c;
    int n = lunar_pipeline_harvest(&c);
    if (n <= 0) return n;
    if (c.tag != harvested) return -1;
    if (c.p_ticks > p_max) p_max = c.p_ticks;
    if (c.c_ticks > c_max) c_max = c.c_ticks;
    ++harvested;
    return 1;
}

static int produce(void)
{
    void *work = 0;
    uint32_t begin, end;
    int n = lunar_pipeline_reserve_work(produced, &work);
    if (n <= 0) return n;
    lunar_pipeline_sdk_parent_block();
    begin = now();
    if (!lunar_fm1_live_produce(work)) return -1;
    end = now();
    if (lunar_pipeline_publish(produced, begin, end) != 1) return -1;
    ++produced;
    return 1;
}

static void report(const char *stage)
{
    struct lunar_fm1_live_status s;
    lunar_fm1_live_status(&s);
    printf("LUNAR_FM1 stage=%s produced=%u harvested=%u out=%u callbacks=%u underruns=%u faults=%u "
           "irq_max=%u p_max=%u c_max=%u events=%u applied=%u deferred=%u ignored=%u dropped=%u "
           "invalid=%u clipped=%u voices=%u battery=%u error=%u\n",
           stage, produced, harvested, out.next, out.callbacks, out.underruns, out.faults,
           out.irq_max, p_max, c_max, s.events, s.applied, s.deferred, s.ignored, s.dropped,
           s.invalid, s.clipped, s.dx7_voices, battery_raw, lunar_pipeline_error());
}

/* Every failure ends here, never in a return from the task: record why,
 * then reset. The warm reset counts as a boot that did not reach healthy,
 * so a build that fails the same way three times in a row enters mask-ROM
 * update mode (firmware/failopen). Returning instead would leave a silent
 * unit that the supervisor could still mark healthy on the panel task's
 * beats alone. */
static void fail(unsigned stage)
{
    report("fail");
    printf("LUNAR_FM1 fail=%u fault=0x%x action=reset\n", stage, FAULT_APP + stage);
    lunar_failopen_note(FAULT_APP + stage);
    cpu_reset();
    for (;;) {}
}

static int pump(uint32_t *wait)
{
    int changed;
    if (lunar_pipeline_wake_drain(0) < 0) return -1;
    changed = harvest();
    if (changed < 0) return -1;
    {
        int r = produce();
        if (r < 0) return -1;
        changed |= r;
    }
    if (changed) { *wait = 0; return 1; }
    if (lunar_pipeline_wait_check(wait) < 0) return -1;
    if (lunar_pipeline_wake_wait(0) < 0) return -1;
    return 0;
}

void lunar_fm1_main(void *unused)
{
    static struct lunar_spi1_io spi_io;
    static struct lunar_spi1 spi;
    static struct lunar_panel_transport panel;
    struct lunar_alnk0_config cfg;
    uint32_t wait = 0, next_report = STATUS_BLOCKS;
    int slot, status;
    (void)unused;
    slot = lunar_failopen_watch(MAIN_WATCH_MS);
    printf("LUNAR_FM1 build=%08x sys=%d rate=%u\n", (unsigned)LUNAR_FAILOPEN_BUILD_ID,
           clk_get("sys"), LUNAR_FM1_RATE);
    if (!timer4_take()) { puts("LUNAR_FM1 error=timer4_busy"); fail(STAGE_TIMER); }

    lunar_board_native_io(&io);
    lunar_backlight_on(&io);
    lunar_spi1_native_io(&spi_io, 0, wait_ms);
    if (lunar_spi1_bind(&spi, &spi_io, PANEL_POLLS, &panel) && lunar_spi1_configure(&spi))
        printf("LUNAR_FM1 panel=%d\n", (int)lunar_panel_m5_pattern(&panel, LUNAR_FM1_BUILD_NAME));
    else
        puts("LUNAR_FM1 panel=unbound");
    lunar_failopen_beat(slot);
    /* TODO(display): the app's 240x240 RGB565 UI needs a 115,200 B frame
     * buffer or a strip renderer; neither fits the SRAM budget yet. */

    if (!lunar_fm1_live_init()) { puts("LUNAR_FM1 error=app_init"); fail(STAGE_INIT); }
    if (!lunar_pipeline_sdk_start(now) || !lunar_fm1_live_bind()) {
        puts("LUNAR_FM1 error=pipeline_start");
        fail(STAGE_PIPELINE);
    }
    lunar_failopen_beat(slot);
    while (harvested < LUNAR_PIPELINE_OUTPUT_SLOTS) {
        if (pump(&wait) < 0) fail(STAGE_PREFILL);
        lunar_failopen_beat(slot);
    }

    matrix_ok = lunar_matrix_init(&io);
    adc_ok = lunar_adc_init(&adc, &io, ADC_POLLS);
    midi_ok = lunar_midi_uart_configure(&midi, &io, midi_ring, MIDI_RING_BYTES,
                                        (unsigned)(uintptr_t)midi_ring);
    lunar_fm1_panel_reset(&panel_state);
    printf("LUNAR_FM1 matrix=%d adc=%d midi=%d\n", matrix_ok, adc_ok, midi_ok);
    status = os_task_create(panel_task, NULL, 12, 1024, 0, "#C0lunar_panel");
    if (status) { printf("LUNAR_FM1 error=panel_task status=%d\n", status); fail(STAGE_PANEL); }

    memset(alnk0_buffer, 0, sizeof alnk0_buffer);
    alnk0.context = 0;
    alnk0.read = lunar_alnk0_mmio_read;
    alnk0.write = lunar_alnk0_mmio_write;
    alnk0.sync = lunar_alnk0_mmio_sync;
    alnk0.attach_irq = alnk0_attach;
    alnk0.delay_ms = alnk0_delay;
    lunar_alnk0_default_config(&cfg, alnk0_buffer, (uint32_t)(uintptr_t)alnk0_buffer);
    status = lunar_alnk0_start(&alnk0, &cfg);
    printf("LUNAR_FM1 alnk0=%d\n", status);
    if (status != LUNAR_ALNK0_OK) fail(STAGE_ALNK0);

    for (;;) {
        if (pump(&wait) < 0) break;
        lunar_failopen_beat(slot);
        if (produced >= next_report) { next_report = produced + STATUS_BLOCKS; report("run"); }
    }
    /* A refusal parks audio: reset, and the boot counter decides between a
     * retry and mask ROM. A refusal after healthy counts as one boot again. */
    fail(STAGE_REFUSED);
}
