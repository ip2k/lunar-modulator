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


@pytest.mark.parametrize('mode', ['resampler', 'audio', 'fm6', 'fm6-ram', 'fm6-audio', 'control', 'renderer', 'renderer-timing'])
def test_sdk_preparation_disables_downloader_and_orphan_bss(tmp_path, mode):
    renderer = mode in ('renderer', 'renderer-timing')
    timing = mode == 'renderer-timing'
    live = mode == 'fm6-audio'
    audio_probe, fm6 = mode in ('audio', 'renderer'), mode in ('fm6', 'fm6-ram')
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
    (app/'board/wl82/Makefile').write_text('OUT_ELF := sdk.elf\nifeq ($(LINK_AT), 1)\nendif\nc_SRC_FILES := \\\n\toriginal.c\ncc_SRC_FILES :=\nall: pre_build $(OUT_ELF)\n\t$(QUITE) $(RUN_POST_SCRIPT) sdk\n')
    (app/'board/wl82/board.c').write_text('UART2_PLATFORM_DATA_BEGIN(uart2_data)\n'
                                       '\t.rx_pin = -1,\nUART2_PLATFORM_DATA_END();\n'
                                       '\t{"uart2", &uart_dev_ops, (void *)&uart2_data },\n')
    (sdk/'cpu/wl82').mkdir(parents=True)
    (sdk/'cpu/wl82/sdk_ld_sfc.c').write_text('        *(.text*)\n        *(.rodata*)\n'
                                          '        *(.volatile_ram_code)\n')
    out = tmp_path/'prepared'
    if renderer:
        renderer_spec = importlib.util.spec_from_file_location('prepare_renderer', ROOT/'tools/jieli/prepare-renderer-devkit.py')
        renderer_module = importlib.util.module_from_spec(renderer_spec)
        renderer_spec.loader.exec_module(renderer_module)
        renderer_module.prepare_renderer(sdk, ROOT, out, timing_only=timing)
    else:
        module.prepare(sdk, ROOT, out, audio_probe=audio_probe, fm6_benchmark=fm6,
                       boot_control=mode == 'control' or live,
                       fm6_ram=mode == 'fm6-ram' or live, fm6_audio=live)
    result = (out/'apps/demo/demo_hello/board/wl82/Makefile').read_text()
    assert '\\ \\' not in result
    assert '$(RUN_POST_SCRIPT) sdk' not in result
    assert '-fno-data-sections' in result
    assert '#define __SDRAM_SIZE__    (8 * 1024 * 1024)' in (out/'apps/demo/demo_hello/include/app_config.h').read_text()
    assert 'benchmark.c' in result and 'sdk_worker.c' in result
    assert ('-DLUNAR_DEVKIT_AUDIO_PROBE=1' in result) == (audio_probe or live)
    assert (out/'apps/demo/demo_hello/audio_probe.c').exists() == (audio_probe or live)
    assert ('-DLUNAR_DEVKIT_FM6_AUDIO=1' in result) == live
    if renderer:
        assert '10, 5120, 0, "lunar_devkit"' in (out/'apps/demo/demo_hello/app_main.c').read_text()
    if timing:
        assert '-DLUNAR_DEVKIT_RENDERER_TIMING=1' in result
        assert (out/'apps/demo/demo_hello/renderer_timing.h').exists()
        assert not (out/'apps/demo/demo_hello/audio_probe.c').exists()
    if audio_probe or live:
        # Exercise Make's immediate target-variable expansion, not merely the
        # presence of a later global define in the generated text.
        makefile = out/'apps/demo/demo_hello/board/wl82/Makefile'
        target = 'objs/apps/demo/demo_hello/audio_probe.c.o'
        with makefile.open('a') as fp:
            fp.write('\n'+target+':\n\t@echo $(CFLAGS)\n')
        flags = subprocess.run(['make', '-s', '-f', str(makefile), target],
                               cwd=makefile.parent, check=True, capture_output=True, text=True).stdout
        assert '-DLUNAR_DEVKIT_AUDIO_PROBE=1' in flags
        assert ('-DLUNAR_DEVKIT_FM6_AUDIO=1' in flags) == live
        assert ('-DLUNAR_DEVKIT_RENDERER_AUDIO=1' in flags) == renderer
        if renderer:
            # Both the non-LTO DAC callback and the normal SDK worker must
            # retain UART control. Routine tests cannot require physical reset.
            assert '-DLUNAR_DEVKIT_BOOT_CONTROL=1' in flags
            assert (out/'apps/demo/demo_hello/boot_control.c').exists()
            import json
            receipt = json.loads((out/'lunar-devkit-input.json').read_text())
            assert receipt['download_disabled'] is True
            assert receipt['boot_control']
            assert receipt['hardware_acceptance'] is False
    assert ('-DLUNAR_DEVKIT_FM6_BENCHMARK=1' in result) == fm6
    assert ('-DLUNAR_DEVKIT_BOOT_CONTROL=1' in result) == (mode == 'control' or live or renderer)
    if mode == 'control':
        board = (out/'apps/demo/demo_hello/board/wl82/board.c').read_text()
        assert '.rx_pin = IO_PORTA_05' in board and '.tx_pin = -1' in board
        assert '.rx_pin = -1' in board  # Logging UART stays transmit-only.
        assert 'boot_control.c' in result and 'boot_command.c' in result
    if fm6 or live:
        import json
        receipt = json.loads((out/'lunar-devkit-input.json').read_text())
        assert 'engines/src/msfa_dx7.cc' in receipt['inputs']
        assert 'engines/third_party/msfa/LICENSE' in receipt['inputs']
        assert ('live FM6 through internal DAC' if live else 'no DAC/mixer/effects') in receipt['measurement']
        assert '-fwrapv' in result and '-std=c++11' in result
        assert (out/'apps/demo/demo_hello/fm6_unit_env.cc').read_text().startswith('#define FM1_MSFA_UNIT "env.cc"')
        script = (out/'cpu/wl82/sdk_ld_sfc.c').read_text()
        assert ('EXCLUDE_FILE' in script) == (mode == 'fm6-ram' or live)
        if mode == 'fm6-ram' or live:
            assert '*msfa_dx7.cc.o(.text* .rodata*)' in script
            assert '*fm6_unit_fm_op_kernel.cc.o(.text* .rodata*)' in script
            assert '*fm6_benchmark.cc.o' not in script
            assert 'startup-copied ram0_data' in receipt['placement']
        if live:
            assert '*fm6_live.cc.o(.text* .rodata*)' in script
            assert 'fm6_benchmark.cc' not in result
    linked = (out/'include_lib/driver/cpu/wl82/system.ld').read_text()
    start = linked.index('PROVIDE(syscfg_ops_begin')
    end = linked.index('PROVIDE(syscfg_ops_end')
    assert '.syscfg.' not in linked[start:end]
    assert linked.count('*(.syscfg.') == 3
    assert linked.index('*(.syscfg.') > end
    with pytest.raises(ValueError):
        module.prepare(sdk, ROOT, out)
    with pytest.raises(ValueError, match='Choose one'):
        module.prepare(sdk, ROOT, tmp_path/'ambiguous', audio_probe=True, fm6_benchmark=True)
    assert not (tmp_path/'ambiguous').exists()
    with pytest.raises(ValueError, match='requires the FM6'):
        module.prepare(sdk, ROOT, tmp_path/'invalid-ram', fm6_ram=True)
    assert not (tmp_path/'invalid-ram').exists()
    with pytest.raises(ValueError, match='requires SRAM'):
        module.prepare(sdk, ROOT, tmp_path/'invalid-live', fm6_audio=True)
    assert not (tmp_path/'invalid-live').exists()


def test_real_resampler_workload(tmp_path):
    harness = tmp_path/'main.c'
    harness.write_text('''
#include "benchmark.h"
#include <assert.h>
static unsigned clock_value, count, active_hash;
static unsigned now(void) { clock_value += 17; return clock_value; }
static void emit(const struct lunar_devkit_result *r) {
    /* Captured on the dev board and independently matched on the host:
     * notes/2026-10-23-devkit-resampler-results.md. These are fixture output
     * hashes, not timing expectations or a complete sample-stream oracle. */
    static const unsigned expected[3][3] = {
        {0xbcc31dc5u, 0x80cf1dc5u, 0x4d7705c5u},
        {0xbcc31dc5u, 0x0c28d304u, 0x18efc0bfu},
        {0xbcc31dc5u, 0x8d5cd591u, 0x0a82150fu}
    };
    unsigned rate_index = r->rate == 44118 ? 0 : r->rate == 47872 ? 1 : 2;
    assert(r->signal < 3 && r->checksum == expected[rate_index][r->signal]);
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
    subprocess.run(['cc', '-std=c99', '-O2', '-ffp-contract=off', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=undefined,address',
                    '-I'+str(ROOT/'firmware/devkit'),
                    '-I'+str(ROOT/'engines/include'), str(harness),
                    str(ROOT/'firmware/devkit/benchmark.c'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def test_real_fm6_workload_and_wrapping_timer(tmp_path):
    """Build the actual source set, not a mock engine; hashes are host fixtures,
    never a claim that the target has produced the same output yet."""
    spec = importlib.util.spec_from_file_location('prepare_devkit', ROOT/'tools/jieli/prepare-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    harness = tmp_path/'main.cc'
    harness.write_text(r'''
#include "fm6_benchmark.h"
#include <assert.h>
static uint32_t clock_value = 0xfffffff0u, count;
static uint32_t now() { clock_value += 17; return clock_value; }
static void emit(const lunar_fm6_result *r) {
    const uint32_t expected[12] = {
        0xb3891185u, 0xd1d87f07u, 0xc7fae18fu, 0x2b6c31e3u,
        0x323880bdu, 0x6a0d808fu, 0x099ddb63u, 0xffe2fb73u,
        0x11a55cadu, 0x183f0eebu, 0x6bf19151u, 0x86a5a4adu
    };
    const uint32_t patches[] = {0, 19, 25}, voices[] = {1, 4, 8, 12};
    assert(count < 12 && r->checksum == expected[count]);
    assert(r->patch == patches[count / 4] && r->voices == voices[count % 4]);
    assert(r->blocks == 256 && r->ticks == 256 * 17);
    assert(r->min_ticks == 17 && r->max_ticks == 17);
    assert(r->note_on_ticks == 17 && r->note_off_ticks == 17);
    assert(r->instance_bytes > 0 && r->instance_bytes <= 65536);
    assert(!r->invalid_samples && r->nonzero_samples > 0);
    ++count;
}
int main() {
    assert(!lunar_devkit_fm6_benchmark(0, emit));
    assert(!lunar_devkit_fm6_benchmark(now, 0));
    assert(lunar_devkit_fm6_benchmark(now, emit));
    assert(count == 12);
}
''')
    units = []
    for unit in module.MSFA_UNITS:
        path = tmp_path/(unit+'.cc')
        path.write_text('#define FM1_MSFA_UNIT "'+unit+'.cc"\n#include "msfa_unit.cc"\n')
        units.append(path)
    binary = tmp_path/'fm6-benchmark'
    subprocess.run(['c++', '-std=c++11', '-O2', '-ffp-contract=off', '-fwrapv',
                    '-fno-exceptions', '-fno-rtti', '-fsanitize=address',
                    '-I'+str(ROOT/'firmware/devkit'), '-I'+str(ROOT/'engines/include'),
                    '-I'+str(ROOT/'engines/src'), '-isystem', str(ROOT/'engines/third_party/msfa'),
                    str(harness), str(ROOT/'firmware/devkit/fm6_benchmark.cc'),
                    *(str(ROOT/'engines/src'/p) for p in module.FM6_SOURCES),
                    *(str(p) for p in units), '-lm', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
