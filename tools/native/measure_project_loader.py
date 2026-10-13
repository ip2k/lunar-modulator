#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure retained project-adapter sections, not a complete firmware budget.

Sixteen chunks cover eight entry-point combinations at Os/Oz. A relocatable
garbage-collected link retains local references; unresolved external code,
allocator overhead, alignment and runtime stack remain outside this measurement.
No firmware package or device operation is produced.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/jieli'))
from audit_link import Elf

ENTRIES = ('check', 'load', 'save', 'pack')
PROFILES = ((0,), (1,), (2,), (3,), (0, 1), (1, 2), (1, 3), (0, 1, 2, 3))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--shard', type=int, choices=range(16), required=True)
    args = parser.parse_args()
    tc, out = args.toolchain.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'sim/web/src/fm1_app_state.c'
    inputs = [source, Path(__file__).resolve(), ROOT / 'tools/jieli/audit_link.py']
    for directory in ('engines/include', 'engines/state', 'engines/mod', 'engines/host',
                      'sim/web/src'):
        inputs.extend((ROOT / directory).glob('*.h'))
    inputs = sorted(set(inputs))
    manifest = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    optimization = ('-Os', '-Oz')[args.shard // 8]
    roots = ['fm1_app_state_' + ENTRIES[i] for i in PROFILES[args.shard % 8]]
    compiler, linker = tc / 'common/bin/clang', tc / 'pi32v2/bin/ld'
    flags = ['-target', 'pi32v2', '-mcpu=r3', '-mfprev1', optimization,
             '-std=c99', '-ffreestanding', '-fno-builtin',
             '-ffunction-sections', '-fdata-sections',
             '-DFM1_APP_EXTERNAL_ARENAS=1', '-DFM1_TFT_INDEXED=1']
    for directory in ('engines/include', 'engines/state', 'engines/mod', 'engines/host',
                      'sim/web/src'):
        flags.extend(['-I', str(ROOT / directory)])
    flags.extend(['-isystem', str(tc / 'pi32v2/include')])
    obj, retained = out / 'adapter.o', out / 'retained.o'
    subprocess.run([str(compiler), *flags, '-c', str(source), '-o', str(obj)],
                   check=True)
    subprocess.run([str(linker), '-r', '--gc-sections',
                    *[arg for name in roots for arg in ('-u', name)],
                    str(obj), '-o', str(retained)], check=True)
    elf = Elf(retained.read_bytes())
    sections = [s for s in elf.sections if s['flags'] & 2]
    ram = [s for s in sections if s['flags'] & 1]
    undefined = subprocess.check_output([str(tc / 'pi32v2/bin/nm'), '-u',
                                        str(retained)], text=True)
    (out / 'undefined.txt').write_text(undefined)
    if manifest != {str(p.relative_to(ROOT)): digest(p) for p in inputs}:
        raise SystemExit('Project-adapter inputs changed during measurement')
    report = dict(shard=args.shard, roots=roots, optimization=optimization,
                  source_manifest=manifest, flags=flags,
                  compiler_sha256=digest(compiler), linker_sha256=digest(linker),
                  object_sha256=digest(obj), retained_sha256=digest(retained),
                  retained_allocated_bytes=sum(s['size'] for s in sections),
                  retained_writable_bytes=sum(s['size'] for s in ram),
                  writable_sections=[dict(name=s['name'], bytes=s['size']) for s in ram],
                  unresolved_symbols=undefined.splitlines(), lto=False,
                  complete_firmware_budget=False, native_runtime_verified=False,
                  device_access=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('shard', 'roots', 'optimization',
                                            'retained_writable_bytes')}))


if __name__ == '__main__':
    main()
