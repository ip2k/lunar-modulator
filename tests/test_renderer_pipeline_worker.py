"""Execute actual worker routing; SDK mocks do not establish native IRQ timing."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_worker_recovery_preflight_and_idle(tmp_path):
    for name in ('app_config.h', 'system/includes.h', 'os/os_api.h', 'asm/includes.h'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('')
    (tmp_path / 'app_config.h').write_text(r'''#include <stdint.h>
#include <stdio.h>
struct mock_timer { uint32_t CON, CNT, PRD; };
extern struct mock_timer timer;
#define JL_TIMER4 (&timer)
int clk_get(const char *);
void os_time_dly(unsigned);
''')
    harness = tmp_path / 'worker.c'
    harness.write_text(r'''#include "app_config.h"
#include "arithmetic_probe.h"
#include <assert.h>
#include <setjmp.h>
#include <string.h>
struct mock_timer timer;
static jmp_buf stop;
static unsigned ticks, recovery, probes, runs, idles;
static int mode;
void lunar_devkit_worker(void *);
int clk_get(const char *name) { assert(!strcmp(name,"sys")); return 320000000; }
void os_time_dly(unsigned n) {
    if (n==200) { assert(!probes&&!runs); ++recovery; }
    if (runs) {
        assert(n==100 && timer.CON==9 && idles==1);
        longjmp(stop,1); /* continuous idle retains timer on success AND failure */
    }
    ticks+=n; timer.CNT+=n*240000u;
}
int lunar_devkit_arithmetic_probe(uint32_t (*clock)(void), void (*yield)(void),
                                 void (*emit)(const struct lunar_arithmetic_result *)) {
    assert(clock&&yield&&emit&&recovery==1&&ticks==310&&!runs);
    ++probes;
    return mode!=2;
}
int lunar_pipeline_dac_run(uint32_t (*clock)(void)) {
    assert(clock&&probes==1&&recovery==1&&ticks==310&&!runs);
    ++runs; return mode==0;
}
int lunar_pipeline_dac_idle(void) { assert(runs==1); ++idles; return mode==0; }
int main(void) {
    for(mode=0;mode<3;++mode) {
        memset(&timer,0,sizeof timer); ticks=recovery=probes=runs=idles=0;
        if (!setjmp(stop)) {
            lunar_devkit_worker(0);
            assert(mode==2 && !runs && timer.CON==(1u<<14));
        } else assert(mode!=2 && runs==1 && idles==1 && timer.CON==9);
        assert(recovery==1 && probes==1);
    }
    return 0;
}
''')
    source = (ROOT / 'firmware/devkit/sdk_worker.c').read_text()
    barrier = '__asm__ volatile("csync;" ::: "memory");'
    assert source.count(barrier) == 1
    worker = tmp_path / 'sdk_worker.c'
    worker.write_text(source.replace(barrier, '__asm__ volatile("" ::: "memory");'))
    exe = tmp_path / 'worker'
    subprocess.run([os.environ.get('FM1_SIM_CC', 'cc'), '-std=c99', '-O2',
                    '-DLUNAR_DEVKIT_RENDERER_PIPELINE_DAC=1',
                    '-DLUNAR_DEVKIT_RENDERER_PIPELINE=1', '-DFM1_APP_RENDER_PIPELINE=1',
                    '-DLUNAR_DEVKIT_BOOT_CONTROL=1',
                    '-I'+str(tmp_path), '-I'+str(ROOT/'firmware/devkit'),
                    str(harness), str(worker), '-o', str(exe)], check=True)
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=10)
    assert 'complete=1 idle=1' in result.stdout
    assert 'complete=0 idle=0' in result.stdout
    assert 'ERROR arithmetic_probe' in result.stdout
