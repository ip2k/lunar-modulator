#!/usr/bin/env python3
"""Prepare a dev-board pipeline build with some preset entries switched off, to
measure image size (docs/18 M2 fit-tables lane). Offline only; MIT licence.

It runs `prepare_pipeline` of prepare-pipeline-devkit.py with the soak image's
options (cap8, worst-block recorder, 51/47 at 44.1 kHz, 57 cycles) and the
preset of that preparer, less the entries named by `--off`. Nothing in the
preparer changes: with no `--off` the output equals the preparer's own.

A variant built this way is for size and placement only. Switching an entry off
changes where code runs or what the kit workload does, so its timing and its
host-replay hashes are not the soak image's; no variant here is admitted to a
device.
"""
import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load():
    spec = importlib.util.spec_from_file_location('pipeline_prepare', HERE / 'prepare-pipeline-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sdk', type=Path, required=True)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--pipeline-system-archive', type=Path, required=True)
    ap.add_argument('--off', action='append', default=[], metavar='ENTRY',
                    help='preset entry to switch off (repeatable), e.g. drums_ready_convert')
    ap.add_argument('--no-worst-block', action='store_true', help='leave the worst-block recorder out')
    args = ap.parse_args(argv)
    mod = load()
    unknown = [n for n in args.off if n not in mod.PRESET]
    if unknown:
        ap.error('not preset entries: ' + ', '.join(unknown) + ' (see PRESET in prepare-pipeline-devkit.py)')
    for name in args.off:
        mod.PRESET[name] = False
    mod.prepare_pipeline(args.sdk.resolve(), args.source.resolve(), args.out.absolute(),
                         args.pipeline_system_archive.resolve(), False, 57, False, 'cap8',
                         not args.no_worst_block, dx7_sine='trunc12', poly47_at_44100=True)


if __name__ == '__main__':
    main()
