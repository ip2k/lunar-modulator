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


def optimization_overrides(base_opt, hot_dsp_os=False, hot_dsp_hall_o2=False):
    """Return exact opt-in per-TU overrides for bounded DSP experiments."""
    if type(hot_dsp_os) is not bool or type(hot_dsp_hall_o2) is not bool:
        raise TypeError('Hot DSP optimization options must be bools')
    if base_opt not in ('s', 'z'):
        raise ValueError('Catalogue base optimization must be s or z')
    if hot_dsp_os and hot_dsp_hall_o2:
        raise ValueError('Choose only one hot DSP optimization profile')
    if (hot_dsp_os or hot_dsp_hall_o2) and base_opt != 'z':
        raise ValueError('Hot DSP experiments require a -Oz base catalogue')
    if hot_dsp_hall_o2:
        return {'our/src/mi_sixop.o': '-Os', 'our/src/fx_hall.o': '-O2'}
    return ({'our/src/mi_sixop.o': '-Os', 'our/src/fx_hall.o': '-Os'}
            if hot_dsp_os else {})


def source_manifest(root):
    """Bind cached objects to source/build inputs, excluding build outputs."""
    files = []
    for relative in ('engines', 'sim/web/src', 'sim/web/mk'):
        for path in (root / relative).rglob('*'):
            parts = path.relative_to(root / relative).parts
            if any(p.startswith(('build', '.')) or p == '__pycache__' for p in parts):
                continue
            if path.is_file() and (path.suffix in ('.c', '.cc', '.cpp', '.h', '.hpp',
                                                   '.inc', '.mk', '.json', '.py',
                                                   '.S', '.s', '.in', '.tcc', '.def')
                                   or path.name == 'Makefile'):
                files.append(path)
    files += [root / 'tools/jieli/objects.mk', root / 'tools/native/compile_catalogue.py',
              root / 'tools/native/build_application_probe.py',
              root / 'tools/native/probe_artifact.py', root / 'firmware/native/app.ld']
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--cxx-headers', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--shard', type=int, choices=range(16), required=True)
    parser.add_argument('--opt', choices=('s', 'z'), default='s',
                        help='Clang size optimization: s (-Os) or z (-Oz)')
    parser.add_argument('--hot-dsp-os', action='store_true',
                        help='Explicit experiment: -Os for sixop/Hall with --opt z; '
                        'does not establish hardware performance')
    parser.add_argument('--hot-dsp-hall-o2', action='store_true',
                        help='Harness-only experiment: SixOp -Os and Hall -O2 over -Oz; '
                        'not a firmware performance or acceptance claim')
    parser.add_argument('--hot-dsp-ram', action='store_true',
                        help='Explicit experiment: place selected sixop/Hall/limiter render bodies in RAM')
    parser.add_argument('--shared-resampler', action='store_true',
                        help='Share the unchanged resampler coefficients')
    parser.add_argument('--shapes-voices', type=int, choices=range(1, 13), default=12,
                        help='Shapes polyphony; retain every synthesis mode')
    parser.add_argument('--indexed-tft', action='store_true',
                        help='Use lossless indexed pixels in every app translation unit')
    parser.add_argument('--lto', action='store_true',
                        help='Emit pinned-toolchain bitcode for cross-unit optimization')
    args = parser.parse_args()
    try:
        overrides = optimization_overrides(args.opt, args.hot_dsp_os, args.hot_dsp_hall_o2)
    except ValueError as error:
        parser.error(str(error))
    inputs = source_manifest(ROOT)
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
             '-D_LIBCPP_HAS_NO_THREADS -D_LIBCPP_DISABLE_EXTERN_TEMPLATE -isystem ' + str(configured) +
             ' -isystem ' + str(tc / 'pi32v2/include'))
    extra += ' -DFM1_TFT_INDEXED=' + str(int(args.indexed_tft))
    extra += ' -DFM1_SHAPES_VOICES=' + str(args.shapes_voices)
    if args.hot_dsp_ram:
        extra += ' -DFM1_HOT_DSP_RAM=1'
    if args.lto:
        extra += ' -flto'
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
        object_opt = overrides.get(name, '-O' + args.opt)
        # The final command-line assignment overrides the base make variable
        # before Makefile's immediate COMMON expansion for this invocation.
        result = subprocess.run(make + ['OPT=' + object_opt, obj],
                                capture_output=True, text=True)
        log = out / 'logs' / (name + '.log')
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(result.stdout + result.stderr)
        entry = {'index': index, 'object': name, 'exit': result.returncode,
                 'optimization': object_opt}
        if result.returncode == 0:
            entry['sha256'] = hashlib.sha256(Path(obj).read_bytes()).hexdigest()
            nm = [str(tc / 'pi32v2/bin/nm')]
            if args.lto:
                nm += ['--plugin', str(tc / 'common/bin/LLVMgold.so')]
            symbols = subprocess.check_output([*nm, '-u', obj], text=True)
            entry['undefined_symbols'] = symbols.splitlines()
        results.append(entry)
    if source_manifest(ROOT) != inputs:
        raise SystemExit('Source inputs changed during compilation')
    report = {'shard': args.shard, 'chunks': 16, 'catalogue_objects': len(objects),
              'gpl_mods': 1, 'modules': 'all', 'closed_sdk_archives': [],
              'optimization': '-O' + args.opt, 'lto': args.lto,
              'optimization_overrides': overrides,
              'hot_dsp_hall_o2': args.hot_dsp_hall_o2,
              'hot_dsp_ram': args.hot_dsp_ram,
              'shared_resampler': args.shared_resampler,
              'indexed_tft': args.indexed_tft,
              'shapes_voices': args.shapes_voices,
              'cxx_standard_headers': str(headers), 'device_sdk_headers': [],
              'input_config_sha256': hashlib.sha256(config.encode()).hexdigest(),
              'configured_sha256': hashlib.sha256((configured / '__config').read_bytes()).hexdigest(),
              'source_manifest': inputs,
              'firmware_linked': False, 'hardware_tested': False, 'results': results}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'shard': args.shard, 'objects': len(results),
                      'failed': sum(r['exit'] != 0 for r in results)}))
    return int(any(r['exit'] != 0 for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
