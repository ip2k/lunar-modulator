#!/usr/bin/env python3
"""Prepare a private offline dev-kit fail-open/watchdog test; never install it.

Builds on prepare-devkit.py with UART boot control, then adds the fail-open
record (placed and checked by the linker script), the setup_arch hook, the
heartbeat supervisor and a test worker. The image identifies itself at run time
by hashing its own flash image, so nothing here derives a build id.
Output stays private: it is an SDK tree with JieLi's libraries.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

MODES = {'cycle': 'LUNAR_FAILOPEN_TEST_CYCLE', 'escalate': 'LUNAR_FAILOPEN_TEST_ESCALATE',
         'recover': 'LUNAR_FAILOPEN_TEST_RECOVER'}
EXPECTED_SLOTS = {'cycle': 1, 'escalate': 2, 'recover': 4}   # failopen_worker.c
ESCALATE_CRASH_MS = 12000   # failopen_worker.c CRASH_AFTER_MS
FILES = ['firmware/failopen/failopen_core.c', 'firmware/failopen/failopen_core.h',
         'firmware/failopen/failopen_sdk.c', 'firmware/failopen/failopen_sdk.h']
WORKER = 'firmware/devkit/failopen_worker.c'
RECORD_BYTES = 64   # carved from the heap top; the record itself is 36 bytes
SETUP_ANCHOR = '    system_reset_reason_get();\n'
# The hook reads the raw reset registers, then calls system_reset_reason_get().
SETUP_HOOK = ('    {\n'
              '        extern void lunar_failopen_early(void);\n'
              '        lunar_failopen_early();\n'
              '    }\n')
PLACEMENT = '0x1c00000 + RAM0_SIZE - 32 - {}'.format(RECORD_BYTES)
# Link-time checks: a changed SDK layout fails the link instead of moving the
# record onto the heap, boot_info or the UPDATA mailbox.
ASSERTS = ('\n/* Lunar fail-open record placement (prepare-failopen-devkit.py) */\n'
           'ASSERT(lunar_failopen_record == ' + PLACEMENT + ', "lunar_failopen_record moved")\n'
           'ASSERT(lunar_failopen_record >= _HEAP_END, "lunar_failopen_record overlaps the heap")\n'
           'ASSERT(lunar_failopen_record + {} <= ORIGIN(boot_info), '
           '"lunar_failopen_record overlaps boot_info")\n'.format(RECORD_BYTES) +
           'ASSERT(_HEAP_BEGIN <= _HEAP_END, "heap below the fail-open record is negative")\n'
           'ASSERT(lunar_failopen_record % 4 == 0, "lunar_failopen_record misaligned")\n')
HEAP_LINES = ['    _HEAP_END = 0x1c00000 + RAM0_SIZE - 32;\n',
              '    PROVIDE(HEAP_END = 0x1c00000 + RAM0_SIZE - 32);\n']


def prepare(sdk, source, out, mode, limit=3, healthy_ms=10000, stable_ms=30000):
    if mode not in MODES:
        raise ValueError('Select a fail-open test mode: ' + ', '.join(sorted(MODES)))
    if not 1 <= limit <= 16 or not 1000 <= healthy_ms <= 600000:
        raise ValueError('Limit 1..16 and healthy time 1..600 s')
    if not healthy_ms <= stable_ms <= 3600000:
        raise ValueError('Stable time from the healthy time to 3600 s')
    if mode == 'escalate' and not healthy_ms < ESCALATE_CRASH_MS < stable_ms:
        raise ValueError('Escalate crashes at 12 s: healthy must come before it, stable after')
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
    if 'ORIGIN(boot_info)' not in script or 'ASSERT(lunar_failopen_record' in script:
        raise ValueError('Unexpected heap layout; review the fail-open record placement')
    lowered = ' - 32 - {}'.format(RECORD_BYTES)
    for line in HEAP_LINES:
        script = script.replace(line, line.replace(' - 32', lowered), 1)
    marker = HEAP_LINES[1].replace(' - 32', lowered)
    script = script.replace(marker, marker + '    PROVIDE(lunar_failopen_record = ' + PLACEMENT + ');\n', 1)
    linker.write_text(script + ASSERTS)

    makefile = app/'board/wl82/Makefile'
    text = makefile.read_text()
    anchor = 'c_SRC_FILES := ' + chr(92)
    if text.count(anchor) != 1:
        raise ValueError('Unexpected C source list; review fail-open link')
    text = text.replace(anchor, anchor + ''.join(
        '\n\t../../../../../apps/demo/demo_hello/' + name + ' ' + chr(92)
        for name in ('failopen_core.c', 'failopen_sdk.c')), 1)
    text += ('\nCFLAGS += -DLUNAR_FAILOPEN_EXPECTED_SLOTS={} -DLUNAR_FAILOPEN_LIMIT={} '
             '-DLUNAR_FAILOPEN_HEALTHY_MS={} -DLUNAR_FAILOPEN_STABLE_MS={} -D{}=1\n').format(
                 EXPECTED_SLOTS[mode], limit, healthy_ms, stable_ms, MODES[mode])
    makefile.write_text(text)

    receipt = out/'lunar-devkit-input.json'
    record = json.loads(receipt.read_text())
    record['inputs'].pop('firmware/devkit/sdk_worker.c')
    for name in [*FILES, WORKER, 'tools/jieli/prepare-failopen-devkit.py']:
        record['inputs'][name] = hashlib.sha256((source/name).read_bytes()).hexdigest()
    record.update(diagnostic='Fail-open boot counter, heartbeat supervisor and watchdog test; no audio',
                  measurement='UART log of raw reset registers, image id, record contents and the fallback decision',
                  failopen_mode=mode, failopen_limit=limit, failopen_healthy_ms=healthy_ms,
                  failopen_stable_ms=stable_ms, failopen_expected_slots=EXPECTED_SLOTS[mode],
                  failopen_image_id='run time: FNV-1a of the flat application image',
                  failopen_record='heap top, {} bytes below the SDK HEAP_END'.format(RECORD_BYTES),
                  hardware_acceptance=False,
                  admission='OFFLINE ONLY; requires exact image review before hardware',
                  prepared_main_sha256=hashlib.sha256(main.read_bytes()).hexdigest(),
                  prepared_setup_sha256=hashlib.sha256(setup.read_bytes()).hexdigest())
    receipt.write_text(json.dumps(record, indent=2) + '\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('sdk', 'source', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--mode', choices=sorted(MODES), required=True)
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--healthy-ms', type=int, default=10000)
    parser.add_argument('--stable-ms', type=int, default=30000)
    args = parser.parse_args()
    record = prepare(args.sdk.resolve(), args.source.resolve(), args.out.resolve(),
                     args.mode, args.limit, args.healthy_ms, args.stable_ms)
    print(json.dumps({key: record[key] for key in record if key.startswith('failopen_')}))
