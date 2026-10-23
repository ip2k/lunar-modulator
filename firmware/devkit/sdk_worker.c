/* SPDX-License-Identifier: MIT. Private dev-kit diagnostic. */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "benchmark.h"
#ifdef LUNAR_DEVKIT_FM6_BENCHMARK
#include "fm6_benchmark.h"
#endif
#ifdef LUNAR_DEVKIT_AUDIO_PROBE
#include "audio_probe.h"
#endif

static uint32_t now(void) { return JL_TIMER4->CNT; }

#ifdef LUNAR_DEVKIT_FM6_BENCHMARK
static void emit_fm6(const struct lunar_fm6_result *r)
{
    printf("\nLUNAR_FM6 patch=%u voices=%u blocks=%u instance=%u ticks=%u min=%u max=%u note_on=%u note_off=%u hash=%08x invalid=%u nonzero=%u\n",
           r->patch, r->voices, r->blocks, r->instance_bytes, r->ticks,
           r->min_ticks, r->max_ticks, r->note_on_ticks, r->note_off_ticks,
           r->checksum, r->invalid_samples, r->nonzero_samples);
    os_time_dly(2);
}
#elif !defined(LUNAR_DEVKIT_AUDIO_PROBE)
static void emit(const struct lunar_devkit_result *r)
{
    printf("\nLUNAR_BENCH rate=%u producer=%u signal=%u blocks=%u ticks=%u min=%u max=%u inputs=%u hash=%08x\n",
           r->rate, r->producer_frames, r->signal, r->blocks, r->ticks,
           r->min_ticks, r->max_ticks, r->input_frames, r->checksum);
    /* Let vendor system/event/watchdog work execute between cases. */
    os_time_dly(2);
}

#endif

void lunar_devkit_worker(void *unused)
{
    uint32_t before;
    (void)unused;
    os_time_dly(100);
#ifdef LUNAR_DEVKIT_AUDIO_PROBE
    printf("\nLUNAR_DEVKIT schema=1 sys=%d timer_clock=OSC_24M irq=enabled source=internal-dac-probe\n", clk_get("sys"));
#elif defined(LUNAR_DEVKIT_FM6_BENCHMARK)
    printf("\nLUNAR_DEVKIT schema=1 sys=%d timer_clock=OSC_24M irq=enabled source=fm6-no-dac\n", clk_get("sys"));
#else
    printf("\nLUNAR_DEVKIT schema=1 sys=%d timer_clock=OSC_24M irq=enabled source=resampler-only\n", clk_get("sys"));
#endif
    /* This minimal image does not register an owner for TIMER4. Never
     * overwrite an enabled peripheral if a future SDK changes that. */
    if (JL_TIMER4->CON & 3u) {
        puts("LUNAR_DEVKIT ERROR timer4_busy\n");
        return;
    }
    JL_TIMER4->CON = (1u << 14);
    JL_TIMER4->CNT = 0;
    JL_TIMER4->PRD = 0xffffffffu;
    JL_TIMER4->CON = 9u; /* oscillator source, prescaler /1, enabled */
    __asm__ volatile("csync;" ::: "memory");
    before = now();
    os_time_dly(10);
    printf("LUNAR_DEVKIT timer_check_ticks=%u delay_os_ticks=10\n", now()-before);
#ifdef LUNAR_DEVKIT_AUDIO_PROBE
    lunar_devkit_audio_probe();
#elif defined(LUNAR_DEVKIT_FM6_BENCHMARK)
    printf("LUNAR_DEVKIT complete=%d\n", lunar_devkit_fm6_benchmark(now, emit_fm6));
#else
    printf("LUNAR_DEVKIT complete=%d\n", lunar_devkit_benchmark(now, emit));
#endif
    JL_TIMER4->CON = (1u << 14);
    for (;;) os_time_dly(100);
}
