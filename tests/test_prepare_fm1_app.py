"""The FM-1 application preparer (tools/jieli/prepare-fm1-app.py) against a
tiny synthetic SDK: offline only, never hardware. The real build and its
size, SRAM and link gates are recorded in notes/2026-11-08-fm1-app-image.md."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, module):
    spec = importlib.util.spec_from_file_location(module, ROOT/'tools/jieli'/name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sdk_fixture(tmp_path):
    sdk = tmp_path/'sdk'
    app = sdk/'apps/demo/demo_hello'
    (app/'include').mkdir(parents=True)
    (app/'board/wl82').mkdir(parents=True)
    (sdk/'include_lib/driver/cpu/wl82').mkdir(parents=True)
    (sdk/'include_lib/driver/cpu/wl82/system.ld').write_text(
        '       *(.syscfg.2.ops)\n       *(.syscfg.1.ops)\n       *(.syscfg.0.ops)\n'
        '    _syscfg_ops_end = .;\n    PROVIDE(syscfg_ops_end = .);\n')
    (app/'include/app_config.h').write_text(
        '#define __FLASH_SIZE__    (4 * 1024 * 1024)\n'
        '#define __SDRAM_SIZE__    (2 * 1024 * 1024)\n#define CONFIG_CXX_SUPPORT\n'
        '#define TCFG_LOWPOWER_VDDIOW_LEVEL\t\t\tVDDIOW_VOL_21V\n'
        '#define VDC14_VOL_SEL_LEVEL\t\t\t\t\tVDC14_VOL_SEL_140V\n'
        '#define SYSVDD_VOL_SEL_LEVEL\t\t\t\tSYSVDD_VOL_SEL_126V\n')
    (app/'app_main.c').write_text('void app_main() {os_task_create(hello_demo_task, NULL, 10, 1000, 0, "hello_demo_task");}')
    (app/'board/wl82/Makefile').write_text(
        'OUT_ELF := sdk.elf\nifeq ($(LINK_AT), 1)\nendif\nc_SRC_FILES := \\\n\toriginal.c\ncc_SRC_FILES :=\n'
        'all: pre_build $(OUT_ELF)\n\t$(QUITE) $(RUN_POST_SCRIPT) sdk\n')
    (app/'board/wl82/board.c').write_text(
        'UART2_PLATFORM_DATA_BEGIN(uart2_data)\n\t.tx_pin = IO_PORTB_03,\n'
        '\t.rx_pin = -1,\nUART2_PLATFORM_DATA_END();\n'
        '\t.vlvd_value\t\t= VLVD_SEL_25V,\n'
        '\t{"uart2", &uart_dev_ops, (void *)&uart2_data },\n')
    (sdk/'cpu/wl82/liba').mkdir(parents=True)
    (sdk/'cpu/wl82/sdk_ld_sfc.c').write_text(
        'RAM0_SIZE = 0x1c7fe00 - 0x1c00000 - TLB_SIZE - BOOT_INFO_SIZE - 128;\n'
        '        *(.text*)\n        *(.rodata*)\n'
        '        *(.volatile_ram_code)\n    .cache_ram_data ALIGN(4):\n    {\n    } > cache_ram\n'
        '    _HEAP_END = 0x1c00000 + RAM0_SIZE - 32;\n'
        '    PROVIDE(HEAP_END = 0x1c00000 + RAM0_SIZE - 32);\n'
        '    _MALLOC_SIZE = _HEAP_END - _HEAP_BEGIN;\n')
    (sdk/'cpu/wl82/setup.c').write_text('void setup_arch()\n{\n    wdt_init(0xc);\n'
                                        '    system_reset_reason_get();\n    puts("x");\n}\n')
    (sdk/'cpu/wl82/liba/system.a').write_bytes(b'original fixture archive')
    correction = tmp_path/'corrected.a'
    correction.write_bytes(b'reviewed fixture archive')
    return sdk, correction


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    def run(gpl=1, debug_uart='off', name='out', usb_midi='off', **switches):
        module = load('prepare-fm1-app.py', 'fm1_prepare')
        sdk, correction = sdk_fixture(tmp_path/name)
        real = module.load

        def patched(source, filename, modname):
            mod = real(source, filename, modname)
            if filename == 'prepare-pipeline-devkit.py':
                monkeypatch.setattr(mod, 'ORIGINAL_SYSTEM_SHA256', mod.sha256(sdk/mod.SYSTEM))
                monkeypatch.setattr(mod, 'PIPELINE_SYSTEM_SHA256', mod.sha256(correction))
            return mod
        monkeypatch.setattr(module, 'load', patched)
        out = tmp_path/name/'prepared'
        identity = module.prepare(sdk, ROOT, out, correction, gpl, debug_uart, usb_midi, **switches)
        return out, identity
    return run


def test_fm1_app_tree(prepared):
    out, identity = prepared()
    app = out/'apps/demo/demo_hello'
    main = (app/'app_main.c').read_text()
    assert main.startswith('#include "failopen_sdk.h"\n')
    assert main.index('lunar_failopen_app_start();') < main.index('os_task_create(lunar_fm1_main')
    assert 'boot_control' not in main and 'lunar_devkit_worker' not in main
    for name in ('boot_command.c', 'boot_control.c', 'sdk_worker.c'):
        assert not (app/name).exists()
    for name in ('failopen_core.c', 'failopen_sdk.c', 'boot_compat.c'):
        assert (app/name).exists()

    make = (app/'board/wl82/Makefile').read_text()
    assert '-DLUNAR_DEVKIT_RENDERER_PIPELINE_DAC' not in make
    assert 'LUNAR_DEVKIT_BOOT_CONTROL' not in make
    for flag in ('-DFM1_APP_RENDER_PIPELINE=1', '-DLUNAR_FM1_APP=1', '-DLUNAR_PIPELINE_UNBOUNDED=1',
                 '-DLUNAR_FAILOPEN_BUILD_ID=0x{:08x}u'.format(identity), '-DLUNAR_FAILOPEN_EXPECTED_SLOTS=2', '-DLUNAR_RENDERER_POLICY_CAP8=1'):
        assert make.index(flag) < make.index('include lunar-renderer.mk'), flag
    assert make.rstrip().endswith('LFLAGS += --wrap=boot_info_init')
    for name in ('boot_command.c', 'boot_control.c', 'sdk_worker.c'):
        assert name not in make
    fragment = (app/'board/wl82/lunar-renderer.mk').read_text()
    assert 'FM1_GPL_MODS=1 ' in fragment and 'tools/jieli/fm1-app.mk' in fragment
    assert 'size-profile.mk' in fragment

    config = (app/'include/app_config.h').read_text()
    assert '#define __SDRAM_SIZE__    0' in config
    for stock in ('VDC14_VOL_SEL_160V', 'SYSVDD_VOL_SEL_138V', 'VDDIOW_VOL_32V'):
        assert stock in config
    board = (app/'board/wl82/board.c').read_text()
    assert 'VLVD_SEL_26V' in board and 'lunar_control_uart' not in board
    assert '.tx_pin = -1,' in board and 'IO_PORTB_03' not in board

    linker = (out/'cpu/wl82/sdk_ld_sfc.c').read_text()
    assert 'PROVIDE(lunar_failopen_record = 0x1c00000 + RAM0_SIZE - 32 - 64);' in linker
    assert 'lunar_failopen_early();' in (out/'cpu/wl82/setup.c').read_text()
    assert 'ASSERT(lunar_failopen_record >= _HEAP_END' in linker
    for d in ('firmware/fm1', 'firmware/board', 'firmware/display', 'firmware/failopen'):
        assert (out/'lunar-source'/d).is_dir()
    assert (out/'lunar-source/tools/jieli/fm1-app.mk').exists()

    receipt = json.loads((out/'lunar-devkit-input.json').read_text())
    assert receipt['boot_control'] is False and receipt['renderer_pipeline_dac'] is False
    assert receipt['fm1_gpl_mods'] == 1 and receipt['shareable'] is False
    assert receipt['hardware_acceptance'] is False
    assert 'firmware/devkit/sdk_worker.c' not in receipt['inputs']
    assert 'firmware/fm1/fm1_sdk_main.c' in receipt['inputs']


def test_switch_and_debug_uart(prepared):
    out0, id0 = prepared(gpl=0, name='gpl0')
    out1, id1 = prepared(gpl=1, debug_uart='pb3', name='gpl1')
    assert id0 != id1
    app0, app1 = out0/'apps/demo/demo_hello', out1/'apps/demo/demo_hello'
    assert 'FM1_GPL_MODS=0 ' in (app0/'board/wl82/lunar-renderer.mk').read_text()
    assert json.loads((out0/'lunar-devkit-input.json').read_text())['shareable'] is True
    assert '.tx_pin = IO_PORTB_03,' in (app1/'board/wl82/board.c').read_text()


def test_usb_midi_switch(prepared):
    off, id_off = prepared(gpl=0, name='usboff')
    on, id_on = prepared(gpl=0, name='usbon', usb_midi='on')
    assert id_off != id_on
    make_off = (off/'apps/demo/demo_hello/board/wl82/Makefile').read_text()
    make_on = (on/'apps/demo/demo_hello/board/wl82/Makefile').read_text()
    assert '-DLUNAR_FM1_USB_MIDI' not in make_off
    # Before the engine make captures EXTRA, as the other application switches.
    assert make_on.index('-DLUNAR_FM1_USB_MIDI=1') < make_on.index('include lunar-renderer.mk')
    assert json.loads((off/'lunar-devkit-input.json').read_text())['usb_midi'] is False
    receipt = json.loads((on/'lunar-devkit-input.json').read_text())
    assert receipt['usb_midi'] is True
    for name in ('firmware/fm1/fm1_usb_midi.c', 'firmware/fm1/fm1_usb_sdk.c'):
        assert name in receipt['inputs'] and (on/'lunar-source'/name).exists()


def test_full_ui_and_size_levers(prepared):
    off, id_off = prepared(gpl=0, name='default')
    make_off = (off/'apps/demo/demo_hello/board/wl82/Makefile').read_text()
    for flag in ('LUNAR_FM1_FULL_UI', 'LUNAR_FM1_SIZE_COLD', 'LUNAR_FM1_SIZE_CONTROL'):
        assert flag not in make_off
    receipt = json.loads((off/'lunar-devkit-input.json').read_text())
    assert receipt['full_ui'] is False and receipt['size_levers'] == 'off'
    seen = {id_off}
    for name, switches, flags in (
            ('full', dict(full_ui='on'), ['-DLUNAR_FM1_FULL_UI=1']),
            ('cold', dict(size_levers='cold'), ['-DLUNAR_FM1_SIZE_COLD=1']),
            ('control', dict(full_ui='on', size_levers='control'),
             ['-DLUNAR_FM1_FULL_UI=1', '-DLUNAR_FM1_SIZE_COLD=1', '-DLUNAR_FM1_SIZE_CONTROL=1'])):
        out, identity = prepared(gpl=0, name=name, **switches)
        assert identity not in seen
        seen.add(identity)
        make = (out/'apps/demo/demo_hello/board/wl82/Makefile').read_text()
        for flag in flags:
            # Before the engine make captures EXTRA, as the other application switches.
            assert make.index(flag) < make.index('include lunar-renderer.mk'), flag
        if 'control' not in name:
            assert '-DLUNAR_FM1_SIZE_CONTROL' not in make
        receipt = json.loads((out/'lunar-devkit-input.json').read_text())
        assert receipt['full_ui'] is (switches.get('full_ui') == 'on')
        assert receipt['size_levers'] == switches.get('size_levers', 'off')
        assert 'firmware/fm1/fm1_strtod.c' in receipt['inputs']


def test_default_build_id_string_is_unchanged():
    # A later switch left at its default must not change the hashed option
    # string, so default images differ from earlier ones only by the sources.
    module = load('prepare-fm1-app.py', 'fm1_prepare_id')
    assert module.build_id(ROOT, 0, 'off', 'off') == module.build_id(ROOT, 0, 'off', 'off', 'off', 'off')
    assert module.build_id(ROOT, 0, 'off', 'off', 'on') != module.build_id(ROOT, 0, 'off', 'off')
    assert module.build_id(ROOT, 0, 'off', 'off', 'off', 'cold') != module.build_id(ROOT, 0, 'off', 'off')


def test_size_lever_fragment():
    text = (ROOT/'tools/jieli/fm1-app.mk').read_text()
    def unit_list(name):
        start = text.index(name + ' :=')
        return text[start + len(name) + 3:text.index('\n$(', start)].replace('\\', ' ')
    cold, control = unit_list('FM1_SIZE_COLD'), unit_list('FM1_SIZE_CONTROL')
    # The renderer and the engines never take COLDOPT.
    for unit in (cold + control).split():
        assert not unit.startswith(('tp/', 'engines/', 'src/')), unit
    for unit in ('sim/src/fm1_app ', 'sim/src/fm1_seq_ui', 'fm1app/fm1/fm1_input'):
        assert unit not in cold and unit in control
    # The sequencer engine, the arpeggiator and the modulation runtime keep
    # the build's level: at COLDOPT they cost 6.4% of the producer's block.
    # So does fm1_live, the FM-1's per-block producer wrapper and consumer
    # conversion, which no dev-kit image runs, so its timing is unmeasured.
    for hot in ('c/seq/seq_engine', 'midi_fx/fm1_arp', 'midi_fx/arp_engine', 'mod/mod/mod_core', 'mod/mod/mp_lfo',
                'fm1app/fm1/fm1_live'):
        assert hot not in cold and hot not in control
    assert '-Dstrtod=lunar_fm1_strtod -Dstrtof=lunar_fm1_strtof' in text
    assert 'FM1_APP_SOURCES += fm1/fm1_strtod' in text
    assert '$(error -DLUNAR_FM1_SIZE_CONTROL=1 needs -DLUNAR_FM1_SIZE_COLD=1)' in text
    # Without COLDOPT the levers would build nothing at -Oz while the receipt names them.
    assert 'ifeq ($(strip $(COLDOPT)),)' in text
    # The objects are named as the rules name them: each COLD/CONTROL unit
    # must resolve to a source file in the tree.
    prefixes = {'sim/src/': 'sim/web/src/', 'c/seq/': 'engines/seq/', 'c/state/': 'engines/state/',
                'c/host/': 'engines/host/', 'state/host/': 'engines/host/',
                'state/state/': 'engines/state/', 'our/src/': 'engines/src/', 'midi_fx/': 'engines/midi_fx/',
                'mod/mod/': 'engines/mod/', 'fm1app/': 'firmware/'}
    for unit in (cold + control).split():
        for prefix, directory in prefixes.items():
            if unit.startswith(prefix):
                stem = directory + unit[len(prefix):]
                assert any((ROOT/(stem + ext)).exists() for ext in ('.c', '.cc')), unit
                break
        else:
            raise AssertionError('unmapped unit ' + unit)


def test_refuses_bad_arguments(tmp_path):
    module = load('prepare-fm1-app.py', 'fm1_prepare_args')
    with pytest.raises(ValueError):
        module.prepare(tmp_path, ROOT, tmp_path/'o', tmp_path/'a', gpl=2)
    with pytest.raises(ValueError):
        module.prepare(tmp_path, ROOT, tmp_path/'o', tmp_path/'a', debug_uart='pb4')
    with pytest.raises(ValueError):
        module.prepare(tmp_path, ROOT, tmp_path/'o', tmp_path/'a', usb_midi='yes')
    with pytest.raises(ValueError):
        module.prepare(tmp_path, ROOT, tmp_path/'o', tmp_path/'a', full_ui='yes')
    with pytest.raises(ValueError):
        module.prepare(tmp_path, ROOT, tmp_path/'o', tmp_path/'a', size_levers='all')


def test_fragment_swaps_the_kit_workload():
    text = (ROOT/'tools/jieli/fm1-app.mk').read_text()
    for gone in ('renderer_live.o', 'renderer_timing.o', 'arithmetic_probe.o', 'renderer_pipeline_dac.o'):
        assert gone in text
    assert '$(error The FM-1 application needs -DLUNAR_PIPELINE_UNBOUNDED=1)' in text
    assert 'fm1/fm1_sdk_main' in text and 'board/alnk0_audio' in text
