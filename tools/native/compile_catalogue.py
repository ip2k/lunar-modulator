#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile one of 16 native catalogue chunks; no firmware link or device I/O."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--cxx-headers', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--shard', type=int, choices=range(16), required=True)
    parser.add_argument('--opt', choices=('s', 'z'), default='s',
                        help='Clang size optimization: s (-Os) or z (-Oz)')
    parser.add_argument('--shared-resampler', action='store_true',
                        help='Share the unchanged resampler coefficients')
    args = parser.parse_args()
    tc, headers, out = args.toolchain.resolve(), args.cxx_headers.resolve(), args.out.resolve()
    if not (headers / '__config').is_file():
        parser.error('--cxx-headers must contain the libc++ standard headers')
    out.mkdir(parents=True, exist_ok=False)
    # The supplied LLVM headers embed a generated pthread configuration in
    # __config. Adapt a private copy, leaving the pinned input unchanged.
    config = (headers / '__config').read_text()
    pthread = '#define _LIBCPP_HAS_THREAD_API_PTHREAD\n'
    if config.count(pthread) != 1:
        parser.error('Expected exactly one generated pthread configuration')
    configured = out / 'cxx'
    shutil.copytree(headers, configured)
    (configured / '__config').chmod(0o600)
    (configured / '__config').write_text(config.replace(pthread, '/* Native: no thread API. */\n'))
    build = out / 'obj'
    cc = str(tc / 'common/bin/clang') + ' -target pi32v2 -mcpu=r3 -mfprev1'
    extra = ('-ffreestanding -fno-builtin -ffunction-sections -fdata-sections '
             '-D_GNU_SOURCE -D_XOPEN_SOURCE=700 -DFM1_FREESTANDING=1 '
             '-D_LIBCPP_HAS_NO_THREADS -isystem ' + str(configured) +
             ' -isystem ' + str(tc / 'pi32v2/include'))
    make = ['make', '-s', '-C', str(ROOT / 'engines'), '-f', 'Makefile',
            '-f', str(ROOT / 'sim/web/mk/sim.mk'), '-f', str(ROOT / 'tools/jieli/objects.mk'),
            'SIM=' + str(ROOT / 'sim/web'), 'BUILD=' + str(build),
            'FM1_GPL_MODS=1', 'FM1_MODULES=all', 'OPT=-O' + args.opt,
            'FM1_SHARED_RESAMPLER=' + str(int(args.shared_resampler)),
            'CC=' + cc, 'CXX=' + cc, 'EXTRA=' + extra]
    objects = subprocess.check_output(make + ['print-objs'], text=True).splitlines()
    relative = [str(Path(obj).relative_to(build)) for obj in objects]
    (out / 'objects.json').write_text(json.dumps(relative, indent=2) + '\n')
    results = []
    for index in range(args.shard, len(objects), 16):
        obj, name = objects[index], relative[index]
        result = subprocess.run(make + [obj], capture_output=True, text=True)
        log = out / 'logs' / (name + '.log')
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(result.stdout + result.stderr)
        entry = {'index': index, 'object': name, 'exit': result.returncode}
        if result.returncode == 0:
            entry['sha256'] = hashlib.sha256(Path(obj).read_bytes()).hexdigest()
            symbols = subprocess.check_output([str(tc / 'pi32v2/bin/nm'), '-u', obj], text=True)
            entry['undefined_symbols'] = symbols.splitlines()
        results.append(entry)
    report = {'shard': args.shard, 'chunks': 16, 'catalogue_objects': len(objects),
              'gpl_mods': 1, 'modules': 'all', 'closed_sdk_archives': [],
              'optimization': '-O' + args.opt,
              'shared_resampler': args.shared_resampler,
              'cxx_standard_headers': str(headers), 'device_sdk_headers': [],
              'input_config_sha256': hashlib.sha256(config.encode()).hexdigest(),
              'configured_sha256': hashlib.sha256((configured / '__config').read_bytes()).hexdigest(),
              'firmware_linked': False, 'hardware_tested': False, 'results': results}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'shard': args.shard, 'objects': len(results),
                      'failed': sum(r['exit'] != 0 for r in results)}))
    return int(any(r['exit'] != 0 for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
