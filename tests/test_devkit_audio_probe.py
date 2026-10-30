"""Exercise the actual probe with the pinned SDK's three-window DAC contract."""
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('mode', ['tone', 'fm6', 'renderer'])
def test_dac_start_refill_contract(tmp_path, mode):
    headers = ['app_config.h', 'system/includes.h', 'os/os_api.h',
               'asm/includes.h', 'asm/dac.h']
    for name in headers:
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#include "mock.h"\n')
    (tmp_path/'mock.h').write_text('''
#ifndef MOCK_H
#define MOCK_H
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
#define IRQ_AUDIO_IDX 13
#define FADE_DISABLE 0
#define ___interrupt
#define local_irq_save(flags) ((flags) = 0)
#define local_irq_restore(flags) ((void)(flags))
struct dac_platform_data {
    unsigned pa_mute_port, hw_channel, ch_num, sr_points, vcm_init_delay_ms;
};
struct timer_regs { uint32_t CNT; };
struct audio_regs { uint32_t DAC_CON, DAC_HRP, DAC_SWP, DAC_PNS, DAC_LEN, DAC_VL0, DAC_VL1; };
struct analog_regs { uint32_t DAA_CON1; };
static struct timer_regs timer_regs;
static struct audio_regs audio_regs;
static struct analog_regs analog_regs;
#define JL_TIMER4 (&timer_regs)
#define JL_AUDIO (&audio_regs)
#define JL_ANA (&analog_regs)
void dac_irq_handler(void);
void dac_early_init(unsigned, unsigned, unsigned);
int dac_open(const struct dac_platform_data *);
void dac_set_data_handler(void *, void (*)(void *, u8 *, int));
int dac_set_sample_rate(unsigned);
void dac_close(void);
void request_irq(unsigned, unsigned, void (*)(void), unsigned);
void dac_set_volume(unsigned);
void dac_set_gain(unsigned, unsigned);
int dac_on(void);
int dac_get_sample_rate(void);
void os_time_dly(unsigned);
#endif
''')
    harness = tmp_path/'main.c'
    harness.write_text('''
#include "mock.h"
#include <assert.h>
#include <setjmp.h>
#include <math.h>
#include "audio_probe.c"
/* Share the transport stub contract across the two real workload selectors. */
#ifdef LUNAR_DEVKIT_RENDERER_AUDIO
#define lunar_devkit_fm6_live_init lunar_devkit_renderer_init
#define lunar_devkit_fm6_live_render lunar_devkit_renderer_render
#define lunar_devkit_fm6_live_status lunar_devkit_renderer_status
#define lunar_fm6_live_status lunar_renderer_status
#endif
#if defined(LUNAR_DEVKIT_FM6_AUDIO) || defined(LUNAR_DEVKIT_RENDERER_AUDIO)
static unsigned live_fills, live_initialized;
int lunar_devkit_fm6_live_init(void) { ++live_initialized; return 1; }
void lunar_devkit_fm6_live_render(int16_t *out) {
    unsigned i;
    assert(live_initialized == 1);
    ++live_fills;
    for (i=0; i<256; ++i) out[i] = 42;
}
void lunar_devkit_fm6_live_status(struct lunar_fm6_live_status *out) {
    memset(out, 0, sizeof(*out));
}
#endif
static struct dac_platform_data config;
static void (*handler)(void *, u8 *, int);
static unsigned sample_rate;
static jmp_buf completed;
static int16_t guarded[2 + 3 * 64 * 4];
void dac_irq_handler(void) {}
void dac_early_init(unsigned trim, unsigned channel, unsigned delay) {
    assert(trim == 1 && channel == 5 && delay == 1000);
}
int dac_open(const struct dac_platform_data *pd) { config = *pd; return 0; }
void dac_set_data_handler(void *p, void (*f)(void *, u8 *, int)) { assert(!p); handler = f; }
int dac_set_sample_rate(unsigned rate) { sample_rate = rate; return 0; }
void dac_close(void) { assert(0); }
void request_irq(unsigned irq, unsigned priority, void (*f)(void), unsigned core) {
    assert(irq == 13 && priority == 5 && f && core == 0);
}
void dac_set_volume(unsigned volume) {
    /* Verified library contract, not the stale header's PCM-scale units. */
    assert(volume <= 100 && volume * 32 / 100 == 32);
    audio_regs.DAC_VL0 = audio_regs.DAC_VL1 = 15920;
}
void dac_set_gain(unsigned gain, unsigned fade) {
    /* Default table entry 17 is analog gain 8; passing 8 selects entry 2
     * (analog gain 1). Assert the mapped result to catch that regression. */
    assert(gain <= 100 && gain * 32 / 100 == 17 && fade == 0);
    analog_regs.DAA_CON1 = (8u << 15) | (8u << 10) | (8u << 5) | 8u;
}
int dac_get_sample_rate(void) { return (int)sample_rate; }
int dac_on(void) {
    /* Pinned SDK dac_on() writes DAC_PNS = sr_points / 3;
     * dac_irq_handler supplies PNS * channels * sizeof(int16_t) bytes.
     * Use the platform configuration, not the probe's expected size. */
    unsigned frames = config.sr_points / 3;
    unsigned window, i, ch, nonzero = 0;
    assert(config.ch_num == 4 && config.sr_points <= 192);
    guarded[0] = guarded[1 + 3 * 64 * 4] = 12345;
    for (window = 0; window < 3; ++window) {
        timer_regs.CNT += 34829;
        handler(NULL, (u8 *)(guarded + 1 + window * frames * config.ch_num),
                (int)(frames * config.ch_num * sizeof(int16_t)));
    }
    assert(callbacks == 3 && invalid_buffers == 0);
#if defined(LUNAR_DEVKIT_FM6_AUDIO) || defined(LUNAR_DEVKIT_RENDERER_AUDIO)
    assert(live_fills == 3);
#else
    assert(ramp_frames == 192 && phase != 0);
#endif
    for (i = 0; i < 192; ++i) {
        int16_t sample = guarded[1 + i * 4];
#if defined(LUNAR_DEVKIT_FM6_AUDIO) || defined(LUNAR_DEVKIT_RENDERER_AUDIO)
        double expected = 42;
#else
        double expected = 1024 * sin(6.28318530718 * 997 * i / sample_rate) * (i + 1) / 2205;
#endif
        assert(fabs(sample - expected) < 3);
        nonzero += sample != 0;
        for (ch = 1; ch < 4; ++ch) assert(guarded[1 + i * 4 + ch] == sample);
    }
    assert(nonzero > 150);
    assert(guarded[0] == 12345 && guarded[1 + 3 * 64 * 4] == 12345);
    return 0;
}
void os_time_dly(unsigned ticks) { assert(ticks == 100); longjmp(completed, 1); }
int main(void) {
    if (!setjmp(completed)) lunar_devkit_audio_probe();
    assert(sample_rate == 44100);
    /* A genuinely malformed window is silent and cannot advance DDS phase. */
    {
        int16_t bad[10];
        unsigned i;
#if !defined(LUNAR_DEVKIT_FM6_AUDIO) && !defined(LUNAR_DEVKIT_RENDERER_AUDIO)
        uint32_t old_phase = phase;
#endif
        for (i = 0; i < 10; ++i) bad[i] = 12345;
        handler(NULL, (u8 *)(bad + 1), 16);
        assert(invalid_buffers == 1 && callbacks == 3);
#if defined(LUNAR_DEVKIT_FM6_AUDIO) || defined(LUNAR_DEVKIT_RENDERER_AUDIO)
        assert(live_fills == 3);
#else
        assert(phase == old_phase);
#endif
        assert(bad[0] == 12345 && bad[9] == 12345);
        for (i = 1; i < 9; ++i) assert(bad[i] == 0);
    }
    {
        int16_t valid[256];
        assert(long_gaps == 0);
        timer_regs.CNT += PROBE_TICKS * 2;
        handler(NULL, (u8 *)valid, sizeof(valid));
        assert(long_gaps == 1 && callbacks == 4 && invalid_buffers == 1);
    }
    return 0;
}
''')
    binary = tmp_path/'probe'
    subprocess.run(['cc', '-std=c99', '-O1', '-Wall', '-Wextra', '-Werror',
                    *({'tone': [], 'fm6': ['-DLUNAR_DEVKIT_FM6_AUDIO=1'],
                       'renderer': ['-DLUNAR_DEVKIT_RENDERER_AUDIO=1']}[mode]),
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-I'+str(tmp_path), '-I'+str(ROOT/'firmware/devkit'),
                    str(harness), '-lm', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
