#!/usr/bin/env python3
"""Prepare an offline-only SDK hello diagnostic; never execute a downloader.

Input SDK must be a private archive of AC79 V1.2.13, commit e30b1ee.
Output remains private: SDK libraries and generated firmware are not redistributable.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def prepare(sdk, source, out):
    if out.exists():
        raise ValueError('Output must not exist; preserve prior build evidence')
    shutil.copytree(sdk, out)
    app = out/'apps/demo/demo_hello'
    config = app/'include/app_config.h'
    text = config.read_text()
    assert '#define __FLASH_SIZE__    (4 * 1024 * 1024)' in text
    text = text.replace('(4 * 1024 * 1024)', '(8 * 1024 * 1024)', 1)
    assert '#define __SDRAM_SIZE__    (2 * 1024 * 1024)' in text
    text = text.replace('#define __SDRAM_SIZE__    (2 * 1024 * 1024)',
                        '#define __SDRAM_SIZE__    (8 * 1024 * 1024)', 1)
    text = text.replace('#define CONFIG_CXX_SUPPORT', '// #define CONFIG_CXX_SUPPORT')
    config.write_text(text)
    main = app/'app_main.c'
    text = main.read_text()
    text = text.replace('void app_main()', 'extern void lunar_devkit_worker(void *);\nvoid app_main()')
    assert 'os_task_create(hello_demo_task, NULL, 10, 1000, 0, "hello_demo_task");' in text
    text = text.replace('os_task_create(hello_demo_task, NULL, 10, 1000, 0, "hello_demo_task");',
                        'os_task_create(lunar_devkit_worker, NULL, 10, 2048, 0, "lunar_devkit");')
    main.write_text(text)
    for name in ('benchmark.c', 'benchmark.h', 'sdk_worker.c'):
        shutil.copyfile(source/'firmware/devkit'/name, app/name)
    shutil.copyfile(source/'engines/include/fm1_resampler.h', app/'fm1_resampler.h')
    makefile = app/'board/wl82/Makefile'
    text = makefile.read_text()
    assert 'all: pre_build $(OUT_ELF)' in text
    text = text.replace('c_SRC_FILES := ' + chr(92), 'c_SRC_FILES := \\\n\t../../../../../apps/demo/demo_hello/benchmark.c \\\n\t../../../../../apps/demo/demo_hello/sdk_worker.c \\', 1)
    # Eliminate the post-build path, including command-line overrides. No USB
    # devices are passed into the build container either.
    text = text.replace('$(QUITE) $(RUN_POST_SCRIPT) sdk', '@echo "Offline build only: downloader disabled"')
    # SDK's C-only script collects .bss, but .bss.* only when CXX is enabled.
    # Keep this non-LTO object's state out of orphan sections in SDRAM.
    text += '\nobjs/apps/demo/demo_hello/benchmark.c.o: CFLAGS := $(filter-out -Oz -flto,$(CFLAGS)) -O2 -ffp-contract=off -fno-data-sections\n'
    makefile.write_text(text)
    receipts = {'sdk_commit_required': 'e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d',
                'placement': 'XIP code/constants; internal SRAM state; SDK CONFIG_NO_SDRAM_ENABLE',
                'measurement': 'resampler-only, IRQ enabled, raw oscillator timer ticks',
                'download_disabled': True,
                'inputs': {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [source/'firmware/devkit/benchmark.c',
                                     source/'firmware/devkit/benchmark.h',
                                     source/'firmware/devkit/sdk_worker.c',
                                     source/'tools/jieli/prepare-devkit.py',
                                     source/'engines/include/fm1_resampler.h']}}
    (out/'lunar-devkit-input.json').write_text(json.dumps(receipts, indent=2)+'\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sdk', type=Path, required=True)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    prepare(a.sdk, a.source, a.out)
