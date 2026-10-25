/* SPDX-License-Identifier: MIT. Private dev-kit diagnostic. */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "benchmark.h"
#ifdef LUNAR_DEVKIT_FM6_SDK
#include "fm6_pair_sdk.h"
#endif
#if defined(LUNAR_DEVKIT_RENDERER_TIMING) || defined(LUNAR_DEVKIT_RENDERER_AUDIO)
#include "renderer_live.h"
#endif
#ifdef LUNAR_DEVKIT_RENDERER_TIMING
#include "renderer_timing.h"
#ifdef LUNAR_RENDERER_PROFILE
#include "arithmetic_probe.h"
static void emit_arithmetic(const struct lunar_arithmetic_result *r)
{
    printf("LUNAR_ARITHMETIC op=%u iterations=%u batches=%u min=%u max=%u mean=%u bits=%08x\n",
           r->operation, r->iterations, r->batches, r->min_ticks, r->max_ticks,
           (unsigned)(r->ticks / r->batches), r->result_bits);
}
#endif
/* SDK allocator diagnostics, emitted only outside timed render blocks. */
extern void malloc_stats(void);
static void renderer_yield(void) { os_time_dly(1); }
static void emit_renderer(const struct lunar_renderer_timing *r)
{
#ifdef LUNAR_DEVKIT_FM6_SDK
    lunar_fm6_sdk_report(r->test_case);
#endif
    printf("\nLUNAR_RENDERER_TIMING case=%u blocks=%u min=%u max=%u mean=%u over=%u controls=%u arena=%u invalid=%u clipped=%u hash=%08x\n",
           r->test_case, r->blocks, r->min_ticks, r->max_ticks,
           (unsigned)(r->ticks / r->blocks), r->over_budget, r->state.controls,
           r->state.arena_bytes, r->state.invalid, r->state.clipped,
           r->state.completed_hash);
    puts("LUNAR_RENDERER_HEAP after_case=1\n");
    malloc_stats();
    printf("LUNAR_RENDERER_STACK unused_words=%u word_bytes=4\n",
           (unsigned)uxTaskGetStackHighWaterMark(NULL));
#ifdef LUNAR_RENDERER_PROFILE
    for (unsigned i = 0; i < LUNAR_RENDERER_PROFILE_STAGES; ++i)
        printf("LUNAR_RENDERER_WORST case=%u block=%u total=%u stage=%u ticks=%u\n",
               r->test_case, r->worst_block, r->max_ticks, i, r->worst_stages[i]);
#ifdef LUNAR_RENDERER_PREP_PROFILE
    for (unsigned i = 0; i < LUNAR_RENDERER_PREP_REGIONS; ++i) {
        struct lunar_renderer_profile p;
        lunar_devkit_renderer_prep_read(i, &p);
        printf("LUNAR_RENDERER_PREP case=%u region=%u calls=%u mean_call=%u max_call=%u mean_block=%u worst_block=%u worst_ticks=%u\n",
               r->test_case, i, p.calls, p.calls ? (unsigned)(p.ticks / p.calls) : 0u,
               p.max_ticks, (unsigned)(p.ticks / r->blocks), r->worst_block, r->worst_prep[i]);
    }
#endif
    for (unsigned i = 0; i < LUNAR_RENDERER_DETAIL_REGIONS; ++i) {
        struct lunar_renderer_profile p;
        lunar_devkit_renderer_detail_read(i, &p);
        printf("LUNAR_RENDERER_DETAIL case=%u region=%u calls=%u frames=%u mean_call=%u max_call=%u mean_block=%u worst_block=%u worst_ticks=%u\n",
               r->test_case, i, p.calls, p.frames, p.calls ? (unsigned)(p.ticks / p.calls) : 0u,
               p.max_ticks, (unsigned)(p.ticks / r->blocks), r->worst_block, r->worst_details[i]);
    }
    for (unsigned i = 0; i < 8; ++i) {
        struct lunar_renderer_profile p;
        lunar_devkit_renderer_profile_read(i, &p);
        printf("LUNAR_RENDERER_PROFILE case=%u unit=%u calls=%u frames=%u mean_call=%u max_call=%u mean_block=%u\n",
               r->test_case, i, p.calls, p.frames, p.calls ? (unsigned)(p.ticks / p.calls) : 0u,
               p.max_ticks, (unsigned)(p.ticks / r->blocks));
    }
    for (unsigned i = 0; i < lunar_devkit_renderer_profile_stages(); ++i) {
        struct lunar_renderer_profile p;
        lunar_devkit_renderer_stage_read(i, &p);
        printf("LUNAR_RENDERER_STAGE case=%u stage=%u calls=%u frames=%u mean_call=%u max_call=%u mean_block=%u\n",
               r->test_case, i, p.calls, p.frames, p.calls ? (unsigned)(p.ticks / p.calls) : 0u,
               p.max_ticks, (unsigned)(p.ticks / r->blocks));
    }
#ifdef LUNAR_RENDERER_ENGINE_PROFILE
    for (unsigned i = 0; i < LUNAR_RENDERER_ENGINE_REGIONS; ++i) {
        struct lunar_renderer_profile p;
        lunar_devkit_renderer_engine_read(i, &p);
        printf("LUNAR_RENDERER_ENGINE case=%u region=%u calls=%u frames=%u mean_call=%u max_call=%u mean_block=%u\n",
               r->test_case, i, p.calls, p.frames, p.calls ? (unsigned)(p.ticks / p.calls) : 0u,
               p.max_ticks, (unsigned)(p.ticks / r->blocks));
    }
#endif
#endif
}
#endif
#ifdef LUNAR_DEVKIT_BOOT_CONTROL
#include "boot_command.h"
#endif
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
#ifdef LUNAR_DEVKIT_RENDERER_TIMING
    printf("\nLUNAR_DEVKIT schema=1 sys=%d timer_clock=OSC_24M irq=enabled source=shared-renderer-no-dac workload=" LUNAR_RENDERER_WORKLOAD_NAME "\n", clk_get("sys"));
#elif defined(LUNAR_DEVKIT_AUDIO_PROBE)
#ifdef LUNAR_DEVKIT_RENDERER_AUDIO
    printf("\nLUNAR_DEVKIT schema=1 sys=%d timer_clock=OSC_24M irq=enabled source=shared-renderer-internal-dac workload=" LUNAR_RENDERER_WORKLOAD_NAME "\n", clk_get("sys"));
#elif defined(LUNAR_DEVKIT_FM6_AUDIO)
    printf("\nLUNAR_DEVKIT schema=1 sys=%d timer_clock=OSC_24M irq=enabled source=fm6-internal-dac\n", clk_get("sys"));
#else
    printf("\nLUNAR_DEVKIT schema=1 sys=%d timer_clock=OSC_24M irq=enabled source=internal-dac-probe\n", clk_get("sys"));
#endif
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
#ifdef LUNAR_DEVKIT_BOOT_CONTROL
    /* Allow a complete acknowledged PING/ARM/ENTER recovery handshake even
     * when the next workload crashes during initialization. SDK ticks are
     * 10 ms here; no rendering or benchmark timing occurs in this window. */
    puts("LUNAR_CONTROL recovery_window_ticks=200\n");
    os_time_dly(200);
#endif
#ifdef LUNAR_DEVKIT_RENDERER_TIMING
#ifdef LUNAR_RENDERER_PROFILE
    if (!lunar_devkit_arithmetic_probe(now, renderer_yield, emit_arithmetic)) {
        puts("LUNAR_DEVKIT ERROR arithmetic_probe\n");
        JL_TIMER4->CON = (1u << 14);
        return;
    }
#endif
    puts("LUNAR_RENDERER_HEAP before_init=1\n");
    malloc_stats();
#ifdef LUNAR_DEVKIT_FM6_SDK
    if (!lunar_fm6_sdk_start(now)) {
        puts("LUNAR_DEVKIT ERROR fm6_pair_start\n");
        /* Worker might be late: retain its timer and permanent storage. */
        for (;;) os_time_dly(100);
    }
#endif
    int complete = lunar_devkit_renderer_timing(now, renderer_yield, emit_renderer);
#ifdef LUNAR_DEVKIT_FM6_SDK
    if (!lunar_fm6_sdk_finish()) {
        puts("LUNAR_DEVKIT ERROR fm6_pair_finish\n");
        for (;;) os_time_dly(100);
    }
#endif
    printf("LUNAR_DEVKIT complete=%d\n", complete);
#elif defined(LUNAR_DEVKIT_AUDIO_PROBE)
    lunar_devkit_audio_probe();
#elif defined(LUNAR_DEVKIT_FM6_BENCHMARK)
    printf("LUNAR_DEVKIT complete=%d\n", lunar_devkit_fm6_benchmark(now, emit_fm6));
#else
    printf("LUNAR_DEVKIT complete=%d\n", lunar_devkit_benchmark(now, emit));
#endif
    JL_TIMER4->CON = (1u << 14);
    for (;;) os_time_dly(100);
}
