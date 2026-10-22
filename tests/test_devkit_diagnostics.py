"""Offline contract checks: transport denial and real resampler workload."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import devkit_flash_backup as backup


@pytest.mark.parametrize('op', [0xFC12, 0xFD06, 0xFC0B, 0xA1, 0xFB09])
def test_flash_writes_and_unknown_commands_denied(op):
    with pytest.raises(ValueError):
        backup.request(op, 'loader')


@pytest.mark.parametrize('address', [-256, 1, 0x800000, 0x1000000])
def test_backup_read_bounds(address):
    with pytest.raises(ValueError):
        backup.request(0xFD05, 'loader', address=address)


def test_last_flash_read():
    cdb, data, size = backup.request(0xFD05, 'loader', address=0x7fff00)
    assert cdb[:8] == bytes.fromhex('fd05007fff000100')
    assert data == b'' and size == 256


def test_loader_rejected_before_any_device_command():
    reader = backup.DevkitReader.__new__(backup.DevkitReader)
    reader.cmd = lambda *a, **k: pytest.fail('must reject before device commands')
    with pytest.raises(ValueError, match='fixed-configuration'):
        reader.load(bytes(backup.base.LOADER_SIZE))


def test_devkit_loader_pin_differs_from_historical_original():
    assert backup.LOADER_SHA != backup.base.LOADER_SHA
    assert backup.LOADER_SHA == 'fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c'


def test_sdk_preparation_disables_downloader_and_orphan_bss(tmp_path):
    spec = importlib.util.spec_from_file_location('prepare_devkit', ROOT/'tools/jieli/prepare-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sdk = tmp_path/'sdk'
    app = sdk/'apps/demo/demo_hello'
    (app/'include').mkdir(parents=True)
    (app/'board/wl82').mkdir(parents=True)
    system_ld = sdk/'include_lib/driver/cpu/wl82/system.ld'
    system_ld.parent.mkdir(parents=True)
    system_ld.write_text('    PROVIDE(syscfg_ops_begin = .);\n'
                         '       *(.syscfg.2.ops)\n       *(.syscfg.1.ops)\n       *(.syscfg.0.ops)\n'
                         '    _syscfg_ops_end = .;\n    PROVIDE(syscfg_ops_end = .);\n')
    (app/'include/app_config.h').write_text('#define __FLASH_SIZE__    (4 * 1024 * 1024)\n#define __SDRAM_SIZE__    (2 * 1024 * 1024)\n#define CONFIG_CXX_SUPPORT\n')
    (app/'app_main.c').write_text('void app_main() {os_task_create(hello_demo_task, NULL, 10, 1000, 0, "hello_demo_task");}')
    (app/'board/wl82/Makefile').write_text('c_SRC_FILES := \\\n\toriginal.c\nall: pre_build $(OUT_ELF)\n\t$(QUITE) $(RUN_POST_SCRIPT) sdk\n')
    out = tmp_path/'prepared'
    module.prepare(sdk, ROOT, out)
    result = (out/'apps/demo/demo_hello/board/wl82/Makefile').read_text()
    assert '\\ \\' not in result
    assert '$(RUN_POST_SCRIPT) sdk' not in result
    assert '-fno-data-sections' in result
    assert '#define __SDRAM_SIZE__    (8 * 1024 * 1024)' in (out/'apps/demo/demo_hello/include/app_config.h').read_text()
    assert 'benchmark.c' in result and 'sdk_worker.c' in result
    linked = (out/'include_lib/driver/cpu/wl82/system.ld').read_text()
    start = linked.index('PROVIDE(syscfg_ops_begin')
    end = linked.index('PROVIDE(syscfg_ops_end')
    assert '.syscfg.' not in linked[start:end]
    assert linked.count('*(.syscfg.') == 3
    assert linked.index('*(.syscfg.') > end
    with pytest.raises(ValueError):
        module.prepare(sdk, ROOT, out)


def test_real_resampler_workload(tmp_path):
    harness = tmp_path/'main.c'
    harness.write_text('''
#include "benchmark.h"
#include <assert.h>
static unsigned clock_value, count, active_hash;
static unsigned now(void) { clock_value += 17; return clock_value; }
static void emit(const struct lunar_devkit_result *r) {
    assert(r->min_ticks == 17 && r->max_ticks == 17);
    assert(r->ticks == r->blocks * 17);
    assert(r->input_frames >= r->blocks * 64);
    if (r->rate == 44118 && r->signal == 1) {
        if (active_hash) assert(active_hash == r->checksum);
        active_hash = r->checksum;
    }
    ++count;
}
int main(void) {
    assert(!lunar_devkit_benchmark(0, emit));
    assert(lunar_devkit_benchmark(now, emit));
    assert(count == 18 && active_hash);
    return 0;
}
''')
    binary = tmp_path/'benchmark'
    subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=undefined,address',
                    '-I'+str(ROOT/'firmware/devkit'),
                    '-I'+str(ROOT/'engines/include'), str(harness),
                    str(ROOT/'firmware/devkit/benchmark.c'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
