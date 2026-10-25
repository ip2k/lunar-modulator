"""Run the finite SDK worker lifecycle with host task/clock fault injection.

The shared flags use host atomics in this test translation only. This does
not verify pi32v2 fences, target ABI, scheduling, stack use or performance.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sdk_worker_start_stop_and_faults(tmp_path):
    for name in ('system/includes.h', 'os/os_api.h', 'asm/includes.h'):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('')
    (tmp_path / 'app_config.h').write_text(r'''
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
#include <stdatomic.h>
unsigned timer_get_ms(void);
int current_cpu_id(void);
unsigned uxTaskGetStackHighWaterMark(void *);
void os_time_dly(unsigned);
int os_task_create(void (*)(void *), void *, int, unsigned, int, const char *);
''')
    source = (ROOT / 'firmware/devkit/fm6_pair_sdk.c').read_text()
    source = source.replace('volatile unsigned', '_Atomic unsigned').replace(
        '__asm__ volatile("csync;" ::: "memory");',
        'atomic_thread_fence(memory_order_seq_cst);')
    (tmp_path / 'sdk.c').write_text(source)
    harness = tmp_path / 'lifecycle.c'
    harness.write_text(r'''
#define _POSIX_C_SOURCE 200809L
#include "app_config.h"
#include "fm6_pair_sdk.h"
#include "fm6_pair_bridge.h"
#include "renderer_live.h"
#include <assert.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static int mode, created, attached;
static _Thread_local int cpu;
static _Atomic unsigned offset, jobs, completed;
static pthread_t thread;
static void (*entry)(void *);
unsigned timer_get_ms(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (unsigned)(t.tv_sec * 1000u + t.tv_nsec / 1000000u) + offset;
}
int current_cpu_id(void) { return cpu; }
unsigned uxTaskGetStackHighWaterMark(void *p) { assert(!p); return 900; }
void os_time_dly(unsigned ticks) {
    if (cpu && ticks == 100) pthread_exit(0); // worker has published exit
    struct timespec t = {0, ticks * 1000000u}; nanosleep(&t, 0);
}
static void *launch(void *arg) { cpu = mode == 1 ? 2 : 1; entry(arg); return 0; }
int os_task_create(void (*fn)(void *), void *arg, int pri, unsigned stack,
                   int queue, const char *name) {
    assert(!cpu && pri == 10 && stack == 1024 && !queue && !arg);
    assert(!strcmp(name, "#C1lunar_fm6") && !attached);
    ++created; entry = fn;
    if (mode == 2) return -7;
    if (mode == 3) return 0; // task never becomes ready; bounded refusal
    return pthread_create(&thread, 0, launch, 0);
}
int lunar_fm6_pair_init(uint32_t (*clock)(void), uint32_t budget) {
    assert(clock && budget == 24000000u * 64u / 44100u && !created); return 1;
}
int lunar_fm6_pair_worker_step(void) {
    if (atomic_exchange(&jobs, 0)) { ++completed; return 1; } return 0;
}
static const fm1_dx7_kernel_adapter_t adapter = {0, 0};
const fm1_dx7_kernel_adapter_t *lunar_fm6_pair_adapter(void) { return &adapter; }
unsigned lunar_fm6_pair_completed(void) { return completed; }
int lunar_fm6_pair_disabled(void) { return mode == 5; }
int lunar_devkit_renderer_kernel_adapter(const fm1_dx7_kernel_adapter_t *p) {
    assert(!cpu && p == &adapter); ++attached; return 1;
}
static uint32_t clock_tick(void) { return timer_get_ms(); }
int main(int argc, char **argv) {
    assert(argc == 2); mode = atoi(argv[1]);
    if (mode == 1 || mode == 2 || mode == 3) {
        assert(!lunar_fm6_sdk_start(clock_tick));
        assert(!attached && created == 1);
        assert(!lunar_fm6_sdk_start(clock_tick) && created == 1);
        if (mode == 1) pthread_join(thread, 0);
        if (mode == 3) assert(!lunar_fm6_sdk_finish()); // no exit acknowledgement
        return 0;
    }
    assert(lunar_fm6_sdk_start(clock_tick) && attached == 1);
    assert(!lunar_fm6_sdk_start(clock_tick) && created == 1);
    jobs = 1;
    while (!completed) os_time_dly(1);
    lunar_fm6_sdk_parent_block();
    if (mode == 4) {
        offset = 120000;
        os_time_dly(10); // worker expires independently of a parent stop
    }
    assert(lunar_fm6_sdk_finish() == (mode == 0));
    pthread_join(thread, 0);
}
''')
    exe = tmp_path / 'lifecycle'
    subprocess.run(['cc', '-std=c11', '-O2', '-pthread', '-Wall', '-Wextra', '-Werror',
                    '-I' + str(tmp_path), '-I' + str(ROOT / 'firmware/devkit'),
                    '-I' + str(ROOT / 'engines/include'), str(harness),
                    str(tmp_path / 'sdk.c'), '-o', str(exe)], check=True)
    for mode in range(6):
        subprocess.run([str(exe), str(mode)], check=True, timeout=5, capture_output=True)
