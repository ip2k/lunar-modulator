#!/usr/bin/env python3
"""Prepare a private offline dev-kit fail-open/watchdog test; never install it.

Builds on prepare-devkit.py with UART boot control, then adds the fail-open
record, the setup_arch hook, the heartbeat supervisor and a test worker.
Output stays private: it is an SDK tree with JieLi's libraries.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

MODES = {'cycle': 'LUNAR_FAILOPEN_TEST_CYCLE', 'recover': 'LUNAR_FAILOPEN_TEST_RECOVER'}
FILES = ['firmware/failopen/failopen_core.c', 'firmware/failopen/failopen_core.h',
         'firmware/failopen/failopen_sdk.c', 'firmware/failopen/failopen_sdk.h']
WORKER = 'firmware/devkit/failopen_worker.c'
RECORD_BYTES = 64   # carved from the heap top; the record itself is 32 bytes
SETUP_ANCHOR = '    system_reset_reason_get();\n'
SETUP_HOOK = ('    {\n'
              '        extern void lunar_failopen_early(int reason);\n'
              '        lunar_failopen_early(system_reset_reason_get());\n'
              '    }\n')
HEAP_LINES = ['    _HEAP_END = 0x1c00000 + RAM0_SIZE - 32;\n',
              '    PROVIDE(HEAP_END = 0x1c00000 + RAM0_SIZE - 32);\n']


def build_id(source, mode, limit, healthy_ms):
    digest = hashlib.sha256()
    for name in [*FILES, WORKER]:
        digest.update(name.encode() + b'\0' + (source/name).read_bytes() + b'\0')
    digest.update('mode={} limit={} healthy_ms={}'.format(mode, limit, healthy_ms).encode())
    value = int.from_bytes(digest.digest()[:4], 'big')
    return value or 1


def prepare(sdk, source, out, mode, limit=3, healthy_ms=10000):
    if mode not in MODES:
        raise ValueError('Select a fail-open test mode: ' + ', '.join(sorted(MODES)))
    if not 1 <= limit <= 16 or not 1000 <= healthy_ms <= 600000:
        raise ValueError('Limit 1..16 and healthy time 1..600 s')
    spec = importlib.util.spec_from_file_location('devkit_prepare', source/'tools/jieli/prepare-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # UART recovery is reserved first, exactly as in every other dev-kit image.
    module.prepare(sdk, source, out, boot_control=True)
    app = out/'apps/demo/demo_hello'
    shutil.copyfile(source/WORKER, app/'sdk_worker.c')
    for name in FILES:
        shutil.copyfile(source/name, app/Path(name).name)

    main = app/'app_main.c'
    text = main.read_text()
    anchor = 'if (!lunar_devkit_boot_control_start())'
    if text.count(anchor) != 1:
        raise ValueError('Unexpected app_main; review fail-open placement')
    text = text.replace(anchor, 'lunar_failopen_app_start();\n' + anchor, 1)
    main.write_text('#include "failopen_sdk.h"\n' + text)

    setup = out/'cpu/wl82/setup.c'
    text = setup.read_text()
    if text.count(SETUP_ANCHOR) != 1:
        raise ValueError('Unexpected setup_arch; review the reset-reason hook')
    setup.write_text(text.replace(SETUP_ANCHOR, SETUP_HOOK, 1))

    linker = out/'cpu/wl82/sdk_ld_sfc.c'
    script = linker.read_text()
    if any(script.count(line) != 1 for line in HEAP_LINES):
        raise ValueError('Unexpected heap layout; review the fail-open record placement')
    lowered = ' - 32 - {}'.format(RECORD_BYTES)
    for line in HEAP_LINES:
        script = script.replace(line, line.replace(' - 32', lowered), 1)
    marker = HEAP_LINES[1].replace(' - 32', lowered)
    script = script.replace(marker, marker + '    PROVIDE(lunar_failopen_record = 0x1c00000 + RAM0_SIZE'
                            + lowered + ');\n', 1)
    linker.write_text(script)

    identity = build_id(source, mode, limit, healthy_ms)
    makefile = app/'board/wl82/Makefile'
    text = makefile.read_text()
    anchor = 'c_SRC_FILES := ' + chr(92)
    if text.count(anchor) != 1:
        raise ValueError('Unexpected C source list; review fail-open link')
    text = text.replace(anchor, anchor + ''.join(
        '\n\t../../../../../apps/demo/demo_hello/' + name + ' ' + chr(92)
        for name in ('failopen_core.c', 'failopen_sdk.c')), 1)
    text += ('\nCFLAGS += -DLUNAR_FAILOPEN_BUILD_ID=0x{:08x}u -DLUNAR_FAILOPEN_LIMIT={} '
             '-DLUNAR_FAILOPEN_HEALTHY_MS={} -D{}=1\n').format(identity, limit, healthy_ms, MODES[mode])
    makefile.write_text(text)

    receipt = out/'lunar-devkit-input.json'
    record = json.loads(receipt.read_text())
    record['inputs'].pop('firmware/devkit/sdk_worker.c')
    for name in [*FILES, WORKER, 'tools/jieli/prepare-failopen-devkit.py']:
        record['inputs'][name] = hashlib.sha256((source/name).read_bytes()).hexdigest()
    record.update(diagnostic='Fail-open boot counter, heartbeat supervisor and watchdog test; no audio',
                  measurement='UART log of reset reasons, record contents and the fallback decision',
                  failopen_mode=mode, failopen_limit=limit, failopen_healthy_ms=healthy_ms,
                  failopen_build_id='0x{:08x}'.format(identity),
                  failopen_record='heap top, {} bytes below the SDK HEAP_END'.format(RECORD_BYTES),
                  hardware_acceptance=False,
                  admission='OFFLINE ONLY; requires exact image review before hardware',
                  prepared_main_sha256=hashlib.sha256(main.read_bytes()).hexdigest(),
                  prepared_setup_sha256=hashlib.sha256(setup.read_bytes()).hexdigest())
    receipt.write_text(json.dumps(record, indent=2) + '\n')
    return identity


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('sdk', 'source', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--mode', choices=sorted(MODES), required=True)
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--healthy-ms', type=int, default=10000)
    args = parser.parse_args()
    print('0x{:08x}'.format(prepare(args.sdk.resolve(), args.source.resolve(), args.out.resolve(),
                                    args.mode, args.limit, args.healthy_ms)))
