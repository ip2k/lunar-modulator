"""prepare-devkit.py --usb-midi: the FM-1 USB-MIDI device as a dev-kit probe,
prepared offline against a minimal fake of the SDK tree (as
tests/test_devkit_diagnostics.py does). No device is touched."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_devkit_usb', ROOT/'tools/jieli/prepare-devkit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PROBE = ROOT/'firmware/devkit/usb_midi_probe.c'
WORKER = ROOT/'firmware/devkit/sdk_worker.c'


@pytest.fixture
def sdk(tmp_path):
    sdk = tmp_path/'sdk'
    app = sdk/'apps/demo/demo_hello'
    (app/'include').mkdir(parents=True)
    (app/'board/wl82').mkdir(parents=True)
    system_ld = sdk/'include_lib/driver/cpu/wl82/system.ld'
    system_ld.parent.mkdir(parents=True)
    system_ld.write_text('    PROVIDE(syscfg_ops_begin = .);\n'
                         '       *(.syscfg.2.ops)\n       *(.syscfg.1.ops)\n       *(.syscfg.0.ops)\n'
                         '    _syscfg_ops_end = .;\n    PROVIDE(syscfg_ops_end = .);\n')
    (app/'include/app_config.h').write_text('#define __FLASH_SIZE__    (4 * 1024 * 1024)\n'
                                            '#define __SDRAM_SIZE__    (2 * 1024 * 1024)\n'
                                            '#define CONFIG_CXX_SUPPORT\n')
    (app/'app_main.c').write_text('void app_main() {os_task_create(hello_demo_task, NULL, 10, 1000, 0, "hello_demo_task");}')
    (app/'board/wl82/Makefile').write_text('OUT_ELF := sdk.elf\nc_SRC_FILES := \\\n\toriginal.c\ncc_SRC_FILES :=\n'
                                           'all: pre_build $(OUT_ELF)\n\t$(QUITE) $(RUN_POST_SCRIPT) sdk\n')
    (app/'board/wl82/board.c').write_text('UART2_PLATFORM_DATA_BEGIN(uart2_data)\n'
                                          '\t.rx_pin = -1,\nUART2_PLATFORM_DATA_END();\n'
                                          '\t{"uart2", &uart_dev_ops, (void *)&uart2_data },\n')
    return sdk


def test_usb_midi_prepares_the_probe(sdk, tmp_path):
    out = tmp_path/'prepared'
    module.prepare(sdk, ROOT, out, boot_control=True, usb_midi=True)
    app = out/'apps/demo/demo_hello'
    make = (app/'board/wl82/Makefile').read_text()
    assert '-DLUNAR_DEVKIT_USB_MIDI=1 -DLUNAR_FM1_USB_MIDI=1' in make
    assert '-DLUNAR_DEVKIT_BOOT_CONTROL=1' in make
    sources = re.search(r'c_SRC_FILES := \\\n((?:\t\S+ \\\n)+)\toriginal\.c', make).group(1)
    names = [Path(line.strip(' \\\t')).name for line in sources.splitlines()]
    assert {'usb_midi_probe.c', 'fm1_usb_midi.c', 'fm1_usb_sdk.c', 'boot_command.c',
            'boot_control.c', 'benchmark.c', 'sdk_worker.c'} == set(names)
    assert '\\ \\' not in make and '$(RUN_POST_SCRIPT) sdk' not in make
    for name in ('fm1_usb_midi.c', 'fm1_usb_midi.h', 'fm1_usb_sdk.c'):
        assert (app/name).read_bytes() == (ROOT/'firmware/fm1'/name).read_bytes()
    for name in ('usb_midi_probe.c', 'usb_midi_probe.h', 'sdk_worker.c'):
        assert (app/name).read_bytes() == (ROOT/'firmware/devkit'/name).read_bytes()
    receipt = json.loads((out/'lunar-devkit-input.json').read_text())
    assert receipt['usb_midi'].startswith('4C4A:C755')
    assert receipt['measurement'].startswith('USB-MIDI device probe')
    for rel in ('firmware/fm1/fm1_usb_sdk.c', 'firmware/fm1/fm1_usb_midi.c',
                'firmware/devkit/usb_midi_probe.c', 'tools/jieli/prepare-devkit.py'):
        assert receipt['inputs'][rel] == hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
    main = (app/'app_main.c').read_text()
    assert main.index('lunar_devkit_boot_control_start()') < main.index('int lunar_status = os_task_create')


def test_usb_midi_needs_boot_control_and_is_alone(sdk, tmp_path):
    with pytest.raises(ValueError, match='requires unattended UART control'):
        module.prepare(sdk, ROOT, tmp_path/'a', usb_midi=True)
    assert not (tmp_path/'a').exists()
    with pytest.raises(ValueError, match='Choose one'):
        module.prepare(sdk, ROOT, tmp_path/'b', boot_control=True, usb_midi=True, audio_probe=True)
    assert not (tmp_path/'b').exists()


def test_default_build_is_unchanged_by_the_option(sdk, tmp_path):
    module.prepare(sdk, ROOT, tmp_path/'plain', boot_control=True)
    app = tmp_path/'plain/apps/demo/demo_hello'
    assert 'USB_MIDI' not in (app/'board/wl82/Makefile').read_text()
    assert not any((app/name).exists() for name in ('usb_midi_probe.c', 'fm1_usb_sdk.c', 'fm1_usb_midi.c'))
    assert json.loads((tmp_path/'plain/lunar-devkit-input.json').read_text())['usb_midi'] is False


def test_probe_reads_one_packet_a_pass_after_the_recovery_window():
    probe = PROBE.read_text()
    # R1: the waiting packet's own length is logged before the one read a pass.
    assert 'usb_read_rxcount(0, LUNAR_USB_MIDI_EP)' in probe
    assert probe.index('usb_read_rxcount') < probe.index('lunar_usb_midi_poll(emit, 0)')
    assert '#define POLL_TICKS 50u' in probe
    for banned in ('uac_audio', 'ch9.h', 'usb_stack.h', 'usb/device/', 'usb_g_ep_read(',
                   'efuse', 'sfc_', 'norflash_write', 'norflash_erase'):
        assert banned not in probe
    worker = WORKER.read_text()
    window = worker.index('os_time_dly(200);')
    assert worker.index('lunar_devkit_usb_midi_probe();') > window
    assert 'source=usb-midi-probe' in worker
