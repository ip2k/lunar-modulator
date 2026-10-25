#!/usr/bin/env python3
"""Prepare a private offline SDK CPU1 probe; never package or install it."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil


def prepare(sdk, source, out, long_publication=False):
    spec = importlib.util.spec_from_file_location('devkit_prepare', source / 'tools/jieli/prepare-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Reserves UART recovery first; suppresses diagnostic startup on failure.
    module.prepare(sdk, source, out, boot_control=True)
    app = out / 'apps/demo/demo_hello'
    probe = source / ('firmware/devkit/cpu1_publication_long.c' if long_publication
                      else 'firmware/devkit/cpu1_probe.c')
    shutil.copyfile(probe, app / 'sdk_worker.c')
    main = app / 'app_main.c'
    text = main.read_text()
    anchor = '10, 2048, 0, "lunar_devkit"'
    if text.count(anchor) != 1:
        raise ValueError('Unexpected parent task; review CPU0 pinning')
    main.write_text(text.replace(anchor, '10, 2048, 0, "#C0lunar_parent"'))
    makefile = app / 'board/wl82/Makefile'
    with makefile.open('a') as stream:
        stream.write('\nobjs/apps/demo/demo_hello/sdk_worker.c.o: CFLAGS := '
                     '$(filter-out -Oz -flto,$(CFLAGS)) -O2 -fno-data-sections\n')
    receipt = out / 'lunar-devkit-input.json'
    record = json.loads(receipt.read_text())
    record['inputs'].pop('firmware/devkit/sdk_worker.c')
    for path in (probe, source / 'tools/jieli/prepare-cpu1-devkit.py'):
        record['inputs'][str(path.relative_to(source))] = hashlib.sha256(path.read_bytes()).hexdigest()
    record.update(diagnostic='Short CPU1 SRAM publication/pinning; no audio',
                  measurement='4096 bidirectional 64-word exchanges; CPU histograms; no renderer/DAC',
                  hardware_acceptance=False,
                  admission='OFFLINE ONLY; requires exact image review before hardware',
                  parent_task='#C0lunar_parent', worker_task='#C1lunar_worker',
                  rounds=4096, worker_stack_words=1024, parent_stack_words=2048,
                  recovery_window_ticks=200,
                  prepared_main_sha256=hashlib.sha256(main.read_bytes()).hexdigest(),
                  prepared_worker_sha256=hashlib.sha256((app / 'sdk_worker.c').read_bytes()).hexdigest())
    if long_publication:
        record.update(diagnostic='Long CPU1 SRAM publication comparison; no audio',
                      measurement='100 million exchanges per phase; unfenced then csync; 160 s bound',
                      rounds=100000000, phases=2, total_budget_ticks=3840000000)
    receipt.write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('sdk', 'source', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--long-publication', action='store_true')
    args = parser.parse_args()
    prepare(args.sdk.resolve(), args.source.resolve(), args.out.resolve(), args.long_publication)
