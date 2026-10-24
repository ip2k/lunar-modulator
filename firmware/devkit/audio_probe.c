/* SPDX-License-Identifier: MIT */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "asm/dac.h"
#include "audio_probe.h"
#include <math.h>
#if defined(LUNAR_DEVKIT_FM6_AUDIO) && defined(LUNAR_DEVKIT_RENDERER_AUDIO)
#error Choose one instrument workload
#endif
#ifdef LUNAR_DEVKIT_RENDERER_AUDIO
#include "renderer_live.h"
#elif defined(LUNAR_DEVKIT_FM6_AUDIO)
#include "fm6_live.h"
#endif

#define PROBE_RATE 44100u
#define PROBE_FRAMES 64u
#define PROBE_CHANNELS 4u
#define PROBE_TICKS (24000000u * PROBE_FRAMES / PROBE_RATE)
#if IRQ_AUDIO_IDX != 13
#error Review the pinned WL82 audio IRQ before building
#endif

#if !defined(LUNAR_DEVKIT_FM6_AUDIO) && !defined(LUNAR_DEVKIT_RENDERER_AUDIO)
static int16_t sine_table[257];
static uint32_t phase, ramp_frames;
#endif
static volatile uint32_t callbacks, over_budget, invalid_buffers;
static volatile uint32_t max_ticks, max_gap, previous_tick;
static volatile uint32_t max_irq_ticks, irq_over_budget;
static volatile uint32_t long_gaps;
static volatile int last_buffer_bytes;

/* dac_on() divides sr_points by three to set DAC_PNS. Reserve three exact
 * 64-frame refill windows. The callback receives
 * writable interleaved signed-16 data and its size in bytes. Never log,
 * allocate or sleep in this path. This probe fills all four digital channels
 * equally so routing can be established without assuming headphone wiring. */
static void fill(void *unused, u8 *data, int len)
{
    uint32_t start = JL_TIMER4->CNT;
    uint32_t elapsed;
    int16_t *out = (int16_t *)data;
    (void)unused;
    if (previous_tick) {
        uint32_t gap = start - previous_tick;
        if (gap > max_gap) max_gap = gap;
        if (gap > PROBE_TICKS * 3u / 2u) ++long_gaps;
    }
    previous_tick = start;
    last_buffer_bytes = len;
    if (len != (int)(PROBE_FRAMES * PROBE_CHANNELS * sizeof(*out))) {
        ++invalid_buffers;
        if (len > 0) memset(data, 0, len);
        return;
    }
#ifdef LUNAR_DEVKIT_RENDERER_AUDIO
    lunar_devkit_renderer_render(out);
#elif defined(LUNAR_DEVKIT_FM6_AUDIO)
    lunar_devkit_fm6_live_render(out);
#else
    uint32_t i;
    for (i = 0; i < PROBE_FRAMES; ++i) {
        uint32_t index = phase >> 24, fraction = (phase >> 8) & 65535u;
        int32_t a = sine_table[index], b = sine_table[index + 1];
        int32_t sample = a + (b - a) * (int32_t)fraction / 65536;
        uint32_t channel;
        /* ~50 ms ramp to a 1024/32768 (-30 dBFS) digital peak. */
        if (ramp_frames < 2205u) sample = sample * (int32_t)++ramp_frames / 2205;
        for (channel = 0; channel < PROBE_CHANNELS; ++channel)
            out[i * PROBE_CHANNELS + channel] = (int16_t)sample;
        phase += (uint32_t)(997ull * 4294967296ull / PROBE_RATE);
    }
#endif
    elapsed = JL_TIMER4->CNT - start;
    if (elapsed > max_ticks) max_ticks = elapsed;
    if (elapsed >= PROBE_TICKS) ++over_budget;
    ++callbacks;
}

static ___interrupt void audio_irq(void)
{
    uint32_t start = JL_TIMER4->CNT, elapsed;
    dac_irq_handler();
    elapsed = JL_TIMER4->CNT - start;
    if (elapsed > max_irq_ticks) max_irq_ticks = elapsed;
    if (elapsed >= PROBE_TICKS) ++irq_over_budget;
}

void lunar_devkit_audio_probe(void)
{
    static const struct dac_platform_data config = {
        .pa_mute_port = 0xff, /* No unreviewed GPIO change to an external PA. */
        .hw_channel = 0x05,  /* Pinned SDK DevKitBoard single-ended outputs. */
        .ch_num = PROBE_CHANNELS,
        .sr_points = PROBE_FRAMES * 3u,
        .vcm_init_delay_ms = 1000,
    };
    int status;
#ifdef LUNAR_DEVKIT_RENDERER_AUDIO
    if (!lunar_devkit_renderer_init()) {
        struct lunar_renderer_status failed;
        lunar_devkit_renderer_status(&failed);
        printf("LUNAR_AUDIO ERROR renderer_init stage=%u\n", failed.init_error);
        return;
    }
#elif defined(LUNAR_DEVKIT_FM6_AUDIO)
    if (!lunar_devkit_fm6_live_init()) {
        puts("LUNAR_AUDIO ERROR fm6_init\n");
        return;
    }
#else
    uint32_t i;
    for (i = 0; i <= 256; ++i)
        sine_table[i] = (int16_t)(1024.0f * sinf(6.28318530718f * (float)i / 256.0f));
#endif
    /* trim_en=1 calibrates without the SDK's syscfg_write(CFG_DAC_TRIM).
     * Calibration is temporary; settings backends remain unregistered. */
    dac_early_init(1, config.hw_channel, 1000);
    status = dac_open(&config);
#ifdef LUNAR_DEVKIT_RENDERER_AUDIO
    printf("LUNAR_AUDIO open=%d rate=%u frames=%u channels=%u source=shared-renderer gain_db=-18 cases=4\n",
#elif defined(LUNAR_DEVKIT_FM6_AUDIO)
    printf("LUNAR_AUDIO open=%d rate=%u frames=%u channels=%u source=fm6 gain_db=-18 cases=12\n",
#else
    printf("LUNAR_AUDIO open=%d rate=%u frames=%u channels=%u tone_hz=997 peak_pcm=1024\n",
#endif
           status, PROBE_RATE, PROBE_FRAMES, PROBE_CHANNELS);
    if (status) return;
    dac_set_data_handler(NULL, fill);
    status = dac_set_sample_rate(PROBE_RATE);
    if (status) {
        printf("LUNAR_AUDIO ERROR sample_rate=%d\n", status);
        dac_close();
        return;
    }
    request_irq(13, 5, audio_irq, 0); /* IRQ_AUDIO_IDX, proven above. */
    /* Pinned V1.2.13 cpu.a uses percentages, contrary to dac.h's units.
     * Default table index floor(54 * 32 / 100) = 17 selects analog gain 8;
     * digital 100 selects 15920. dac_direct_set_gain uses the same table.
     * Keep the independent PCM peak at -30 dBFS and ramp it at startup. */
    dac_set_volume(100);
    dac_set_gain(54, FADE_DISABLE);
    status = dac_on();
#ifdef LUNAR_DEVKIT_RENDERER_AUDIO
    printf("LUNAR_AUDIO on=%d actual_rate=%d source=internal-dac-shared-renderer\n",
#elif defined(LUNAR_DEVKIT_FM6_AUDIO)
    printf("LUNAR_AUDIO on=%d actual_rate=%d source=internal-dac-fm6\n",
#else
    printf("LUNAR_AUDIO on=%d actual_rate=%d source=internal-dac-reference-only\n",
#endif
           status, dac_get_sample_rate());
    if (status) return;
    printf("LUNAR_AUDIO gain_percent=54 volume_percent=100 analog=%08x vl0=%08x vl1=%08x\n",
           (unsigned)JL_ANA->DAA_CON1, (unsigned)JL_AUDIO->DAC_VL0,
           (unsigned)JL_AUDIO->DAC_VL1);
    for (;;) {
        uint32_t flags, count, over, bad, peak, gap, irq_peak, irq_over, late;
#ifdef LUNAR_DEVKIT_RENDERER_AUDIO
        struct lunar_renderer_status renderer;
#elif defined(LUNAR_DEVKIT_FM6_AUDIO)
        struct lunar_fm6_live_status live;
#endif
        int buffer_bytes;
        os_time_dly(100);
        /* Read a coherent snapshot; UART work stays outside the audio IRQ. */
        local_irq_save(flags);
        count = callbacks; over = over_budget; bad = invalid_buffers;
        peak = max_ticks; gap = max_gap;
        irq_peak = max_irq_ticks; irq_over = irq_over_budget;
        late = long_gaps;
#ifdef LUNAR_DEVKIT_RENDERER_AUDIO
        lunar_devkit_renderer_status(&renderer);
#elif defined(LUNAR_DEVKIT_FM6_AUDIO)
        lunar_devkit_fm6_live_status(&live);
#endif
        buffer_bytes = last_buffer_bytes;
        local_irq_restore(flags);
        printf("LUNAR_AUDIO callbacks=%u over_budget=%u invalid=%u max_ticks=%u max_gap=%u irq_max=%u irq_over=%u con=%08x hrp=%u swp=%u bytes=%d pns=%u ring=%u\n",
               count, over, bad, peak, gap, irq_peak, irq_over, JL_AUDIO->DAC_CON,
               (unsigned)JL_AUDIO->DAC_HRP, (unsigned)JL_AUDIO->DAC_SWP,
               buffer_bytes, (unsigned)JL_AUDIO->DAC_PNS, (unsigned)JL_AUDIO->DAC_LEN);
        printf("LUNAR_AUDIO gaps_over_1p5_blocks=%u\n", late);
#ifdef LUNAR_DEVKIT_RENDERER_AUDIO
        printf("LUNAR_RENDERER case=%u cycles=%u blocks=%u controls=%u arena=%u invalid=%u clipped=%u\n",
               renderer.test_case, renderer.cycles, renderer.blocks, renderer.controls,
               renderer.arena_bytes, renderer.invalid, renderer.clipped);
        printf("LUNAR_RENDERER_PCM completed=%u case=%u fnv1a=%08x\n",
               renderer.completed_cases, renderer.completed_case, renderer.completed_hash);
#elif defined(LUNAR_DEVKIT_FM6_AUDIO)
        printf("LUNAR_LIVE case=%u patch=%u voices=%u cycles=%u note_batches=%u invalid=%u clipped=%u\n",
               live.test_case, live.patch, live.voices, live.cycles,
               live.note_batches, live.invalid, live.clipped);
        printf("LUNAR_PCM completed=%u case=%u fnv1a=%08x\n",
               live.completed_cases, live.completed_case, live.completed_hash);
#endif
    }
}
