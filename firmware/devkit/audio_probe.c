/* SPDX-License-Identifier: MIT */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "asm/dac.h"
#include "audio_probe.h"
#include <math.h>

#define PROBE_RATE 44100u
#define PROBE_FRAMES 64u
#define PROBE_CHANNELS 4u
#define PROBE_TICKS (24000000u * PROBE_FRAMES / PROBE_RATE)
#if IRQ_AUDIO_IDX != 13
#error Review the pinned WL82 audio IRQ before building
#endif

static int16_t sine_table[257];
static uint32_t phase, ramp_frames;
static volatile uint32_t callbacks, over_budget, invalid_buffers;
static volatile uint32_t max_ticks, max_gap, previous_tick;
static volatile uint32_t max_irq_ticks, irq_over_budget;

/* The SDK DAC ring has four 64-frame refill windows. The callback receives
 * writable interleaved signed-16 data and its size in bytes. Never log,
 * allocate or sleep in this path. This probe fills all four digital channels
 * equally so routing can be established without assuming headphone wiring. */
static void fill(void *unused, u8 *data, int len)
{
    uint32_t start = JL_TIMER4->CNT;
    uint32_t i, elapsed;
    int16_t *out = (int16_t *)data;
    (void)unused;
    if (previous_tick) {
        uint32_t gap = start - previous_tick;
        if (gap > max_gap) max_gap = gap;
    }
    previous_tick = start;
    if (len != (int)(PROBE_FRAMES * PROBE_CHANNELS * sizeof(*out))) {
        ++invalid_buffers;
        if (len > 0) memset(data, 0, len);
        return;
    }
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
        .sr_points = PROBE_FRAMES * 4u,
        .vcm_init_delay_ms = 1000,
    };
    uint32_t i;
    int status;
    for (i = 0; i <= 256; ++i)
        sine_table[i] = (int16_t)(1024.0f * sinf(6.28318530718f * (float)i / 256.0f));
    /* trim_en=1 calibrates without the SDK's syscfg_write(CFG_DAC_TRIM).
     * Calibration is temporary; settings backends remain unregistered. */
    dac_early_init(1, config.hw_channel, 1000);
    status = dac_open(&config);
    printf("LUNAR_AUDIO open=%d rate=%u frames=%u channels=%u tone_hz=997 peak_pcm=1024\n",
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
    dac_set_volume(16384);
    dac_set_gain(8, FADE_DISABLE);
    status = dac_on();
    printf("LUNAR_AUDIO on=%d actual_rate=%d source=internal-dac-reference-only\n",
           status, dac_get_sample_rate());
    if (status) return;
    for (;;) {
        uint32_t flags, count, over, bad, peak, gap, irq_peak, irq_over;
        os_time_dly(100);
        /* Read a coherent snapshot; UART work stays outside the audio IRQ. */
        local_irq_save(flags);
        count = callbacks; over = over_budget; bad = invalid_buffers;
        peak = max_ticks; gap = max_gap;
        irq_peak = max_irq_ticks; irq_over = irq_over_budget;
        local_irq_restore(flags);
        printf("LUNAR_AUDIO callbacks=%u over_budget=%u invalid=%u max_ticks=%u max_gap=%u irq_max=%u irq_over=%u con=%08x hrp=%u swp=%u\n",
               count, over, bad, peak, gap, irq_peak, irq_over, JL_AUDIO->DAC_CON,
               (unsigned)JL_AUDIO->DAC_HRP, (unsigned)JL_AUDIO->DAC_SWP);
    }
}
