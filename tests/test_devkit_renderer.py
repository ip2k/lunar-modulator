"""The hardware workload must exercise the actual shared renderer on desktop."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = "dx7,macro,drums,filter,drive,echo,comp,arp,lfo,env,chance"


def build_reference(modules):
    cc = os.environ.get("FM1_SIM_CC", "cc")
    cxx = os.environ.get("FM1_SIM_CXX", "c++")
    if not shutil.which("make") or not shutil.which(cxx):
        pytest.skip("native toolchain unavailable")
    extra = os.environ.get("FM1_SIM_EXTRA", "") + " -DFM1_APP_EXTERNAL_ARENAS=1"
    tag = hashlib.sha256((cc + cxx + extra + modules).encode()).hexdigest()[:12]
    build = ROOT / "sim/web/build" / f"devkit-renderer-{tag}"
    target = build / "fm1-devkit-renderer-ref"
    subprocess.run([
        "make", "-s", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
        str(ROOT / "sim/web/mk/sim.mk"), "-f", str(ROOT / "tools/jieli/renderer.mk"),
        f"SIM={ROOT / 'sim/web'}", f"BUILD={build}", "FM1_GPL_MODS=0",
        f"FM1_MODULES={modules}", f"CC={cc}", f"CXX={cxx}", f"EXTRA={extra}",
        "-j4", str(target),
    ], check=True, stdout=subprocess.DEVNULL)
    return target


def test_shared_renderer_schedule_and_pcm(tmp_path):
    target = build_reference(MODULES)
    pcm = tmp_path / "reference.pcm"
    # glibc replay enables the same divide-by-zero trap that exposed a
    # speculative logarithmic division on the chip's linear modulation path.
    env = dict(os.environ, LUNAR_TRAP_DIVZERO="1")
    result = subprocess.run([str(target), str(pcm)], capture_output=True, text=True, check=True, env=env)
    rows = [dict(re.findall(r"(\w+)=(\w+)", line)) for line in result.stdout.splitlines()]
    assert len(rows) == 8
    for i, row in enumerate(rows):
        assert int(row["completed"]) == i + 1
        assert int(row["case"]) == i % 4
        assert int(row["blocks"]) == (i + 1) * 5513
        assert row["invalid"] == row["clipped"] == "0"
        assert 0 < int(row["arena"]) <= 148 * 1024
    assert int(rows[-1]["controls"]) > 1000
    assert pcm.stat().st_size == 8 * 5513 * 64 * 4
    # The same source and schedule, fresh process: reproducible PCM receipts.
    again = tmp_path / "again.pcm"
    replay = subprocess.run([str(target), str(again)], capture_output=True, text=True, check=True)
    assert result.stdout == replay.stdout
    assert hashlib.sha256(pcm.read_bytes()).digest() == hashlib.sha256(again.read_bytes()).digest()


def test_missing_effect_refuses_whole_workload():
    target = build_reference(MODULES.replace(",comp", ""))
    result = subprocess.run([str(target)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "initialization refused: stage 1" in result.stderr
    assert "LUNAR_RENDERER completed=" not in result.stdout



def test_profile_preserves_pcm_and_counts_all_unit_frames(tmp_path, monkeypatch):
    # Profiling must preserve PCM relative to the unprofiled build on this
    # same host/libm. Keep the target-compatible Linux fingerprints pinned too.
    baseline = subprocess.run([str(build_reference(MODULES))], capture_output=True,
                              text=True, check=True)
    hashes = [int(x, 16) for x in re.findall(r"hash=([0-9a-fA-F]+)", baseline.stdout)][:4]
    assert len(hashes) == 4
    if sys.platform.startswith("linux"):
        assert hashes == [0x6bcab227, 0x46c02687, 0x1e2f305d, 0x5b7dbc03]
    monkeypatch.setenv("FM1_SIM_EXTRA", os.environ.get("FM1_SIM_EXTRA", "") +
                      " -DLUNAR_RENDERER_PROFILE=1 -DFM1_APP_RENDER_PROFILE=1")
    target = build_reference(MODULES)
    harness = tmp_path / "profile.cc"
    harness.write_text(r'''
#include "renderer_live.h"
#include <assert.h>
#include <stdint.h>
static uint32_t tick = UINT32_MAX - 40u;
static uint32_t now(void) { tick += 17u; return tick; }
int main(void) {
    const uint32_t hashes[] = {0x6bcab227u, 0x46c02687u, 0x1e2f305du, 0x5b7dbc03u};
    lunar_devkit_renderer_profile_clock(now);
    assert(lunar_devkit_renderer_init());
    int16_t pcm[256];
    for (unsigned c = 0; c < 4; ++c) {
        for (unsigned b = 0; b < 5513; ++b) lunar_devkit_renderer_render(pcm);
        struct lunar_renderer_status state;
        lunar_devkit_renderer_status(&state);
        assert(state.completed_hash == hashes[c] && !state.invalid && !state.clipped);
        for (unsigned i = 0; i < 8; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_profile_read(i, &p);
            assert(p.calls && p.frames == 5513u * 64u);
            assert(p.ticks == 17ull * p.calls && p.max_ticks == 17u);
        }
        assert(lunar_devkit_renderer_profile_stages() == 6);
        for (unsigned i = 0; i < 6; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_stage_read(i, &p);
            assert(p.calls == 5513 && p.frames == 5513u * 64u);
            /* Sounds/masters include the nested unit clock reads. */
            assert(p.ticks >= 17ull * p.calls && p.max_ticks >= 17u);
            if (i >= 2) assert(p.ticks == 17ull * p.calls && p.max_ticks == 17u);
        }
        lunar_devkit_renderer_profile_reset();
        for (unsigned i = 0; i <= 6; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_stage_read(i, &p);
            assert(!p.calls && !p.frames && !p.ticks && !p.max_ticks);
        }
        for (unsigned i = 0; i <= 8; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_profile_read(i, &p);
            assert(!p.calls && !p.frames && !p.ticks && !p.max_ticks);
        }
    }
}
''')
    harness.write_text(harness.read_text().replace(
        "0x6bcab227u, 0x46c02687u, 0x1e2f305du, 0x5b7dbc03u",
        ", ".join(f"0x{x:08x}u" for x in hashes)))
    objects = sorted(str(p) for p in target.parent.rglob("*.o") if p.name != "renderer_reference.o")
    exe = tmp_path / "profile"
    subprocess.run([os.environ.get("FM1_SIM_CXX", "c++"), "-std=c++11", "-DLUNAR_RENDERER_PROFILE=1",
                    "-I" + str(ROOT / "firmware/devkit"), str(harness), *objects,
                    "-lm", "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


@pytest.mark.parametrize('options', [
    {'fx_ram': True},
    {'fx_ram': True, 'timing_only': True},
    {'cache_tables': True},
    {'cache_tables': True, 'timing_only': True, 'hot_ram': True, 'sine_ram': True},
    {'profile': True}, {'hot_ram': True}, {'sine_ram': True},
    {'sine_ram': True, 'timing_only': True},
    {'resampler_ram': True},
    {'resampler_ram': True, 'timing_only': True, 'hot_ram': True},
])
def test_profile_rejects_dac_preparation_before_writing(tmp_path, options):
    import importlib.util
    spec = importlib.util.spec_from_file_location("renderer_prepare", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="worker-only|timing-only"):
        module.prepare_renderer(tmp_path / "absent-sdk", ROOT, out, **options)
    assert not out.exists()

def test_worker_timing_wrap_and_yields(tmp_path):
    # Test the timing controller independently of DSP cost: the injected clock
    # wraps and makes every render late. UART scheduling yields and reporting
    # must stay outside each measured region and cover every density case.
    harness = tmp_path / "timing.c"
    harness.write_text(r'''
#include "renderer_timing.h"
#include <assert.h>
#include <string.h>
static unsigned clock_calls, rendered, yielded, emitted, init_ok = 1;
static uint32_t tick = UINT32_MAX - 40000u;
int lunar_devkit_renderer_init(void) { return init_ok; }
void lunar_devkit_renderer_render(int16_t *p) { ++rendered; memset(p, 0, 512); }
void lunar_devkit_renderer_status(struct lunar_renderer_status *p) {
    memset(p, 0, sizeof *p); p->blocks = rendered;
}
static uint32_t now(void) { ++clock_calls; tick += 35000u; return tick; }
static void yield(void) { assert(!(clock_calls & 1u)); ++yielded; }
static void emit(const struct lunar_renderer_timing *r) {
    assert(!(clock_calls & 1u)); assert(r->test_case == emitted++);
    assert(r->blocks == 5513 && r->over_budget == 5513);
    assert(r->min_ticks == 35000 && r->max_ticks == 35000);
    assert(r->ticks == 5513ull * 35000u);
    assert(r->state.blocks == emitted * 5513u);
}
int main(void) {
    assert(!lunar_devkit_renderer_timing(0, yield, emit));
    assert(!lunar_devkit_renderer_timing(now, 0, emit));
    assert(!lunar_devkit_renderer_timing(now, yield, 0));
    init_ok = 0;
    assert(!lunar_devkit_renderer_timing(now, yield, emit));
    assert(!clock_calls && !rendered && !yielded && !emitted);
    init_ok = 1;
    assert(lunar_devkit_renderer_timing(now, yield, emit));
    assert(rendered == 4u * 5513u && clock_calls == 2u * rendered);
    assert(yielded == 4u * (345u + 1u) && emitted == 4);
    return 0;
}
''')
    exe = tmp_path / "timing"
    subprocess.run([os.environ.get("FM1_SIM_CC", "cc"), "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-I" + str(ROOT / "firmware/devkit"), str(harness),
                    str(ROOT / "firmware/devkit/renderer_timing.c"), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


def test_worker_recovery_window_precedes_crashing_initialization(tmp_path):
    # Run the actual worker and parser with only SDK hardware/scheduling mocked.
    # First simulate an init crash, then a fresh boot receiving an acknowledged
    # three-command handshake during its recovery window. No physical I/O.
    for name in ('app_config.h', 'system/includes.h', 'os/os_api.h', 'asm/includes.h'):
        header = tmp_path / name
        header.parent.mkdir(parents=True, exist_ok=True)
        header.write_text('')
    (tmp_path / 'app_config.h').write_text(r'''
#include <stdint.h>
#include <stdio.h>
struct mock_timer { uint32_t CON, CNT, PRD; };
extern struct mock_timer timer;
#define JL_TIMER4 (&timer)
int clk_get(const char *);
void os_time_dly(unsigned);
unsigned uxTaskGetStackHighWaterMark(void *);
void malloc_stats(void);
''')
    harness = tmp_path / 'worker.c'
    harness.write_text(r'''
#include "app_config.h"
#include "renderer_timing.h"
#include "boot_command.h"
#include <assert.h>
#include <setjmp.h>
#include <string.h>
struct mock_timer timer;
static jmp_buf exit_worker;
static unsigned recovering, ready, ticks, init_calls, acknowledgments;
static struct lunar_boot_command parser;
void lunar_devkit_worker(void *);
int clk_get(const char *name) { assert(!strcmp(name, "sys")); return 320000000; }
unsigned uxTaskGetStackHighWaterMark(void *p) { (void)p; return 256; }
void malloc_stats(void) {}

static void command(const char *s, enum lunar_boot_action expected) {
    enum lunar_boot_action action = LUNAR_BOOT_NONE;
    while (*s) action = lunar_boot_command_feed(&parser, *s++, ticks * 10u);
    assert(action == expected);
    ++acknowledgments;
}
void os_time_dly(unsigned n) {
    if (ready) {
        /* Receiver was reserved by app_main; host exchanges fit in this
         * window before a fault in workload initialization. */
        if (n == 200 && recovering) {
            ticks += 10; command("LUNAR PING\n", LUNAR_BOOT_PONG);
            ticks += 10; command("LUNAR ARM UBOOT\n", LUNAR_BOOT_ARMED);
            ticks += 10; command("LUNAR ENTER UBOOT\n", LUNAR_BOOT_ENTER);
            longjmp(exit_worker, 2);
        }
    }
    ticks += n; timer.CNT += n * 240000u;
}
int lunar_devkit_renderer_timing(uint32_t (*now)(void), void (*yield)(void),
    void (*emit)(const struct lunar_renderer_timing *)) {
    assert(now && yield && emit && ready && ticks >= 310);
    ++init_calls;
    longjmp(exit_worker, 1); /* workload initialization faults */
}
int main(void) {
    switch (setjmp(exit_worker)) {
    case 0: ready = 1; lunar_devkit_worker(0); assert(0); break;
    case 1: assert(init_calls == 1); break;
    default: assert(0);
    }
    recovering = 1; ready = ticks = init_calls = 0;
    memset(&timer, 0, sizeof timer); memset(&parser, 0, sizeof parser);
    switch (setjmp(exit_worker)) {
    case 0: ready = 1; lunar_devkit_worker(0); assert(0); break;
    case 2: assert(acknowledgments == 3); break;
    default: assert(0);
    }
    assert(!init_calls); /* Recovery completes before the faulty workload runs. */
    return 0;
}
''')
    # Keep the compiler barrier, replacing only the pi32v2 hardware opcode.
    worker = tmp_path / 'sdk_worker.c'
    source = (ROOT / 'firmware/devkit/sdk_worker.c').read_text()
    barrier = '__asm__ volatile("csync;" ::: "memory");'
    assert source.count(barrier) == 1
    worker.write_text(source.replace(barrier, '__asm__ volatile("" ::: "memory");'))
    exe = tmp_path / 'worker'
    subprocess.run([os.environ.get('FM1_SIM_CC', 'cc'), '-std=c99', '-O2',
                    '-DLUNAR_DEVKIT_RENDERER_TIMING=1', '-DLUNAR_DEVKIT_BOOT_CONTROL=1',
                    '-I' + str(tmp_path), '-I' + str(ROOT / 'firmware/devkit'),
                    str(harness), str(worker),
                    str(ROOT / 'firmware/devkit/boot_command.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, capture_output=True)


def test_recovery_is_reserved_before_workload_and_fails_closed(tmp_path):
    # Execute actual receiver startup against allocation/UART fault injection.
    # The prepared app_main contract only allocates work on a zero result.
    for name in ('app_config.h', 'system/includes.h', 'device/includes.h',
                 'device/uart.h', 'asm/includes.h'):
        header = tmp_path / name
        header.parent.mkdir(parents=True, exist_ok=True)
        header.write_text('')
    (tmp_path / 'app_config.h').write_text(r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uintptr_t u32;
#define CPU_CRITICAL_ENTER() ((void)0)
#define UART_SET_CIRCULAR_BUFF_ADDR 1
#define UART_SET_CIRCULAR_BUFF_LENTH 2
#define UART_SET_RECV_BLOCK 3
#define UART_START 4
#define UART_FLUSH 5
void *dev_open(const char *, void *);
int dev_ioctl(void *, int, u32);
int dev_close(void *);
int dev_read(void *, void *, unsigned);
int os_task_create(void (*)(void *), void *, int, unsigned, int, const char *);
void os_time_dly(unsigned);
uint32_t sys_timer_get_ms(void);
""")
    harness = tmp_path / 'startup.c'
    harness.write_text(r"""
#include "app_config.h"
#include "boot_command.h"
#include <assert.h>
static int fault, io, closed, recovery, work;
static unsigned char handle;
void *dev_open(const char *name, void *arg) {
    assert(!strcmp(name, "uart1") && !arg && !work);
    return fault == 1 ? NULL : &handle;
}
int dev_ioctl(void *p, int cmd, u32 value) {
    (void)value; assert(p == &handle && !work); ++io;
    return fault == cmd + 1 ? -1 : 0;
}
int dev_close(void *p) { assert(p == &handle); ++closed; return 0; }
int dev_read(void *p, void *b, unsigned n) { (void)p;(void)b;(void)n;return 0; }
int os_task_create(void (*fn)(void *), void *arg, int priority, unsigned stack,
                   int queue, const char *name) {
    assert(fn && arg == &handle && priority == 8 && stack == 1024 && !queue);
    assert(!strcmp(name, "lunar_control") && io == 4 && !work);
    if (fault == 6) return -6;
    recovery = 1; return 0;
}
void os_time_dly(unsigned n) { (void)n; }
uint32_t sys_timer_get_ms(void) { return 0; }
void nvram_set_boot_state(u32 state) { (void)state; assert(0); }
static void app_start(int worker_oom) {
    if (!lunar_devkit_boot_control_start()) {
        assert(recovery && io == 4);
        if (!worker_oom) work = 1;
    }
}
int main(void) {
    for (fault = 0; fault <= 6; ++fault) {
        io = closed = recovery = work = 0;
        app_start(0);
        assert(work == (fault == 0));
        assert(recovery == (fault == 0));
        assert(closed == (fault >= 2));
    }
    fault = io = closed = recovery = work = 0;
    app_start(1);
    assert(recovery && !work && !closed); // worker OOM leaves receiver allocated
    return 0;
}
""")
    # Keep the actual startup logic; only ELF placement is target-specific.
    control = tmp_path / 'boot_control.c'
    control.write_text((ROOT / 'firmware/devkit/boot_control.c').read_text().replace(
        'section(".volatile_ram_code"), noinline', 'noinline'))
    exe = tmp_path / 'startup'
    subprocess.run([os.environ.get('FM1_SIM_CC', 'cc'), '-std=c99', '-O2',
                    '-I' + str(tmp_path), '-I' + str(ROOT / 'firmware/devkit'),
                    str(harness), str(control),
                    str(ROOT / 'firmware/devkit/boot_command.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, capture_output=True)
