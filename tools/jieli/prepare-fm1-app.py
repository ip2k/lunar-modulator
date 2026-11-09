#!/usr/bin/env python3
"""Prepare the first complete FM-1 application image, offline only.

Starts from the dev-kit pipeline tree (prepare-pipeline-devkit.py: cap8,
trunc12, --size-profile, the reviewed scheduler archive) and turns it into the
FM-1 application:

- the dev-kit workload leaves: UART boot control (the kit's recovery path;
  the FM-1's is the fail-open counter and docs/17), the internal-DAC
  transport, the fixed test pattern, the timing and arithmetic probes;
- the FM-1 application comes in (firmware/fm1): the pipelined app at
  44,118 Hz with no lifetime bound, the ALNK0 transport, the panel and TRS
  MIDI input, the boot screen, and the fail-open boot counter and heartbeat
  supervisor (firmware/failopen, as prepare-failopen-devkit.py places it);
- fm1-nes's boot_info bridge (Apache-2.0) is linked with
  --wrap=boot_info_init, internal RAM only (SDRAM 0);
- the rails follow the FM-1's stock levels [reported: fm1-nes
  board_power.c]: VDC14 1.60 V, SYSVDD 1.38 V, VDDIOW 3.2 V, LVD 2.6 V
  (VDDIOM is already 3.2 V);
- the debug UART keeps its driver but maps no pin by default (PB3's role on
  the FM-1 is unknown); --debug-uart pb3 keeps the SDK's PB3 TX.

Output is a private SDK tree with JieLi's libraries: never share a build of
it while FM1_GPL_MODS=1 (CLAUDE.md, the GPL switch). It is not a package:
packaging, package_guard.py and any installation are separate, later steps
that need the owner's approval. No device is touched.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil

FM1_DIRS = ('firmware/fm1', 'firmware/board', 'firmware/display', 'firmware/third_party/fm1-nes',
            'firmware/failopen')
BUILD_ID_SOURCES = ('firmware/fm1', 'firmware/board', 'firmware/display', 'firmware/failopen',
                    'firmware/third_party/fm1-nes', 'firmware/devkit/renderer_pipeline_sdk.c',
                    'tools/jieli/fm1-app.mk', 'tools/jieli/prepare-fm1-app.py')
DEBUG_UART = ('off', 'pb3')
POWER = {
    # macro or field, kit value, FM-1 stock value [reported: fm1-nes board_power.c]
    'vdc14': ('VDC14_VOL_SEL_140V', 'VDC14_VOL_SEL_160V'),
    'sysvdd': ('SYSVDD_VOL_SEL_126V', 'SYSVDD_VOL_SEL_138V'),
    'vddiow': ('VDDIOW_VOL_21V', 'VDDIOW_VOL_32V'),
    'lvd': ('VLVD_SEL_25V', 'VLVD_SEL_26V'),
}
FAILOPEN_LIMIT = 3
FAILOPEN_HEALTHY_MS = 30000
FAILOPEN_STABLE_MS = 300000
FAILOPEN_EXPECTED_SLOTS = 2   # fm1_sdk_main.c: the main task and the panel task


def load(source, name, module):
    spec = importlib.util.spec_from_file_location(module, source / 'tools/jieli' / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def checked_replace(text, before, after, count=1):
    if text.count(before) != count:
        raise ValueError('Unexpected prepared SDK text; review before building: ' + before[:80])
    return text.replace(before, after)


def build_id(source, gpl, debug_uart):
    digest = hashlib.sha256()
    for name in BUILD_ID_SOURCES:
        path = source / name
        files = sorted(p for p in path.rglob('*') if p.is_file()) if path.is_dir() else [path]
        for f in files:
            digest.update(str(f.relative_to(source)).encode() + b'\0' + f.read_bytes() + b'\0')
    digest.update('gpl={} debug_uart={} limit={} healthy_ms={}'.format(
        gpl, debug_uart, FAILOPEN_LIMIT, FAILOPEN_HEALTHY_MS).encode())
    return int.from_bytes(digest.digest()[:4], 'big') or 1


def remove_boot_control(app):
    """Undo prepare-devkit.py's boot_control=True edits, exactly."""
    main = app / 'app_main.c'
    text = checked_replace(main.read_text(), '#include "boot_command.h"\n', '')
    worker = 'os_task_create(lunar_devkit_worker, NULL, 16, 2048, 0, "#C0lunar_parent");'
    block = ('if (!lunar_devkit_boot_control_start()) {\n'
             '    int lunar_status = ' + worker + '\n'
             '    if (lunar_status) printf("LUNAR_CONTROL error=worker_create status=%d\\n", lunar_status);\n'
             '}')
    text = checked_replace(text, block,
        'lunar_failopen_app_start();\n'
        '    {\n'
        '        int lunar_status = os_task_create(lunar_fm1_main, NULL, 16, 2048, 0, "#C0lunar_parent");\n'
        '        if (lunar_status) printf("LUNAR_FM1 error=main_create status=%d\\n", lunar_status);\n'
        '    }')
    text = checked_replace(text, 'extern void lunar_devkit_worker(void *);\n',
                           'extern void lunar_fm1_main(void *);\n')
    main.write_text('#include "failopen_sdk.h"\n' + text)
    for name in ('boot_command.c', 'boot_command.h', 'boot_control.c', 'sdk_worker.c'):
        (app / name).unlink()

    board = app / 'board/wl82/board.c'
    text = board.read_text()
    start = text.find('UART1_PLATFORM_DATA_BEGIN(lunar_control_uart)')
    end = text.find('UART2_PLATFORM_DATA_BEGIN(uart2_data)')
    if start < 0 or end < start or text.count('lunar_control_uart') != 2:
        raise ValueError('Unexpected boot-control UART in board.c')
    text = text[:start] + text[end:]
    text = checked_replace(text, '\n\t{"uart1", &uart_dev_ops, (void *)&lunar_control_uart },', '')
    board.write_text(text)


def adapt_makefile(app, flags):
    makefile = app / 'board/wl82/Makefile'
    text = makefile.read_text()
    for name in ('boot_command.c', 'boot_control.c', 'sdk_worker.c'):
        text = checked_replace(text, '\t../../../../../apps/demo/demo_hello/' + name + ' \\\n', '')
    if 'benchmark.c' in text:
        raise ValueError('The resampler benchmark should already be unlisted')
    anchor = 'c_SRC_FILES := \\\n'
    text = checked_replace(text, anchor, anchor + ''.join(
        '\t../../../../../apps/demo/demo_hello/' + name + ' \\\n'
        for name in ('failopen_core.c', 'failopen_sdk.c', 'boot_compat.c')))
    text = checked_replace(text, '\nCFLAGS += -DLUNAR_DEVKIT_BOOT_CONTROL=1\n', '\n')
    # The engine make's EXTRA is captured when lunar-renderer.mk is included,
    # so the application's switches go in with the pipeline's, before it.
    pipeline = ('CFLAGS += -DLUNAR_DEVKIT_RENDERER_PIPELINE=1 '
                '-DLUNAR_DEVKIT_RENDERER_PIPELINE_DAC=1 -DFM1_APP_RENDER_PIPELINE=1\n')
    text = checked_replace(text, pipeline,
        'CFLAGS += -DLUNAR_DEVKIT_RENDERER_PIPELINE=1 -DFM1_APP_RENDER_PIPELINE=1\n' + flags)
    text += '\n# fm1-nes boot_info bridge (Apache-2.0): copies the stock SPL\'s 6 words.\nLFLAGS += --wrap=boot_info_init\n'
    makefile.write_text(text)
    return makefile


def adapt_fragment(app, gpl):
    fragment = app / 'board/wl82/lunar-renderer.mk'
    text = fragment.read_text()
    text = checked_replace(text, '-f $(LUNAR_ROOT)/tools/jieli/size-profile.mk',
                           '-f $(LUNAR_ROOT)/tools/jieli/size-profile.mk -f $(LUNAR_ROOT)/tools/jieli/fm1-app.mk')
    text = checked_replace(text, 'FM1_GPL_MODS=0 ', 'FM1_GPL_MODS={} '.format(gpl))
    fragment.write_text(text)


def adapt_config(app, debug_uart):
    config = app / 'include/app_config.h'
    text = config.read_text()
    text = checked_replace(text, '#define __SDRAM_SIZE__    (8 * 1024 * 1024)', '#define __SDRAM_SIZE__    0')
    for key in ('vdc14', 'sysvdd', 'vddiow'):
        kit, stock = POWER[key]
        text = checked_replace(text, kit, stock)
    config.write_text(text)
    board = app / 'board/wl82/board.c'
    text = board.read_text()
    text = checked_replace(text, POWER['lvd'][0], POWER['lvd'][1])
    if debug_uart == 'off':
        text = checked_replace(text, '.tx_pin = IO_PORTB_03,', '.tx_pin = -1, /* FM-1: PB3 unknown; no pin */')
    board.write_text(text)


def adapt_failopen(failopen, out, app, source):
    for name in failopen.FILES:
        shutil.copyfile(source / name, app / Path(name).name)
    setup = out / 'cpu/wl82/setup.c'
    setup.write_text(checked_replace(setup.read_text(), failopen.SETUP_ANCHOR, failopen.SETUP_HOOK))
    linker = out / 'cpu/wl82/sdk_ld_sfc.c'
    script = linker.read_text()
    lowered = ' - 32 - {}'.format(failopen.RECORD_BYTES)
    for line in failopen.HEAP_LINES:
        script = checked_replace(script, line, line.replace(' - 32', lowered))
    marker = failopen.HEAP_LINES[1].replace(' - 32', lowered)
    script = script.replace(marker, marker + '    PROVIDE(lunar_failopen_record = 0x1c00000 + RAM0_SIZE'
                            + lowered + ');\n', 1)
    linker.write_text(script + failopen.ASSERTS)
    return setup


def prepare(sdk, source, out, system_archive, gpl=1, debug_uart='off'):
    if gpl not in (0, 1):
        raise ValueError('FM1_GPL_MODS is 0 or 1')
    if debug_uart not in DEBUG_UART:
        raise ValueError('Debug UART: ' + ', '.join(DEBUG_UART))
    pipeline = load(source, 'prepare-pipeline-devkit.py', 'pipeline_prepare')
    failopen = load(source, 'prepare-failopen-devkit.py', 'failopen_prepare')
    # 320 MHz: the stock SPL sets the FM-1's 360 MHz before the app runs
    # [verified: V15 isd_config SYS_CLK]; the app does not switch clocks.
    pipeline.prepare_pipeline(sdk, source, out, system_archive, policy='cap8', dx7_sine='trunc12',
                              size_profile=True)
    app = out / 'apps/demo/demo_hello'
    staging = out / 'lunar-source'
    for directory in FM1_DIRS:
        target = staging / directory
        if target.exists():
            raise ValueError('Unexpected staged directory ' + directory)
        shutil.copytree(source / directory, target)
    shutil.copyfile(source / 'tools/jieli/fm1-app.mk', staging / 'tools/jieli/fm1-app.mk')
    shutil.copyfile(source / 'firmware/third_party/fm1-nes/boot_compat.c', app / 'boot_compat.c')

    identity = build_id(source, gpl, debug_uart)
    remove_boot_control(app)
    setup = adapt_failopen(failopen, out, app, source)
    flags = ('CFLAGS += -DLUNAR_FM1_APP=1 -DLUNAR_PIPELINE_UNBOUNDED=1\n'
             'CFLAGS += -DLUNAR_FAILOPEN_BUILD_ID=0x{:08x}u -DLUNAR_FAILOPEN_LIMIT={} '
             '-DLUNAR_FAILOPEN_HEALTHY_MS={} -DLUNAR_FAILOPEN_STABLE_MS={} '
             '-DLUNAR_FAILOPEN_EXPECTED_SLOTS={}\n').format(
                 identity, FAILOPEN_LIMIT, FAILOPEN_HEALTHY_MS, FAILOPEN_STABLE_MS,
                 FAILOPEN_EXPECTED_SLOTS)
    makefile = adapt_makefile(app, flags)
    adapt_fragment(app, gpl)
    adapt_config(app, debug_uart)

    receipt_path = out / 'lunar-devkit-input.json'
    receipt = json.loads(receipt_path.read_text())
    for key in ('firmware/devkit/sdk_worker.c', 'firmware/devkit/boot_command.c',
                'firmware/devkit/boot_command.h', 'firmware/devkit/boot_control.c'):
        receipt['inputs'].pop(key, None)
    for directory in FM1_DIRS:
        for path in sorted((source / directory).rglob('*')):
            if path.is_file():
                receipt['inputs'][str(path.relative_to(source))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('tools/jieli/fm1-app.mk', 'tools/jieli/prepare-fm1-app.py', 'tools/jieli/prepare-failopen-devkit.py'):
        receipt['inputs'][name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
    receipt.update({
        'image': 'FM-1 application (firmware/fm1)',
        'measurement': 'offline size, SRAM and link audit only; nothing installed',
        'renderer_pipeline_dac': False, 'boot_control': False,
        'pipeline_unbounded': True, 'pipeline_polyphony': 'cap8',
        'rate_hz': 44118, 'audio': 'ALNK0 IRQ 11 CPU0, 64-frame halves',
        'fm1_gpl_mods': gpl, 'debug_uart': debug_uart,
        'power': {k: v[1] for k, v in POWER.items()},
        'sdram_bytes': 0, 'boot_info_bridge': 'fm1-nes boot_compat.c, --wrap=boot_info_init',
        'failopen_build_id': '0x{:08x}'.format(identity), 'failopen_limit': FAILOPEN_LIMIT,
        'failopen_healthy_ms': FAILOPEN_HEALTHY_MS,
        'failopen_stable_ms': FAILOPEN_STABLE_MS, 'failopen_expected_slots': FAILOPEN_EXPECTED_SLOTS,
        'shareable': gpl == 0,
        'hardware_acceptance': False,
        'admission': 'OFFLINE ONLY; FM-1 installation needs a separate owner approval',
        'prepared_app_main_sha256': hashlib.sha256((app / 'app_main.c').read_bytes()).hexdigest(),
        'prepared_board_makefile_sha256': hashlib.sha256(makefile.read_bytes()).hexdigest(),
        'prepared_setup_sha256': hashlib.sha256(setup.read_bytes()).hexdigest(),
    })
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    return identity


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--pipeline-system-archive', type=Path, required=True)
    parser.add_argument('--gpl', type=int, choices=(0, 1), default=1,
                        help='FM1_GPL_MODS (default 1, on while we test; a GPL build is never shared)')
    parser.add_argument('--debug-uart', choices=DEBUG_UART, default='off')
    args = parser.parse_args()
    print('0x{:08x}'.format(prepare(args.sdk.resolve(), args.source.resolve(), args.out.absolute(),
                                    args.pipeline_system_archive.resolve(), args.gpl, args.debug_uart)))
