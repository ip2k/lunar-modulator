#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile pinned native math/string sources; never link SDK archives."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--shards', type=int, default=1)
    args = parser.parse_args()
    if args.shards < 1 or not 0 <= args.shard < args.shards:
        parser.error('shard must be within the positive shard count')
    source = ROOT / 'firmware/third_party/musl'
    compat = ROOT / 'firmware/native/libc_compat'
    inventory = json.loads((source / 'inventory.json').read_text())
    for name, digest in inventory['files'].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
            raise SystemExit('Source pin mismatch: ' + name)
    out = args.build.resolve()
    out.mkdir(parents=True, exist_ok=True)
    compiler = args.toolchain.resolve() / 'common/bin/clang'
    flags = ['-target', 'pi32v2', '-mcpu=r3', '-mfprev1', '-Oz',
             '-ffreestanding', '-fno-builtin', '-ffunction-sections',
             '-fdata-sections', '-Werror=implicit-function-declaration',
             '-D_GNU_SOURCE', '-D_XOPEN_SOURCE=700',
             '-Dhidden=__attribute__((visibility("hidden")))',
             '-D__fpclassify=__fpclassifyd',
             '-include', str(compat / 'declarations.h')]
    for directory in [compat, source / 'src/internal', source / 'src/math',
                      source / 'arch/generic']:
        flags += ['-I', str(directory)]
    flags += ['-isystem', str(args.toolchain.resolve() / 'pi32v2/include')]
    results = []
    units = sorted(name for name in inventory['files'] if name.endswith('.c'))
    for index, name in enumerate(units):
        if index % args.shards != args.shard:
            continue
        obj = out / (Path(name).stem + '.o')
        result = subprocess.run([str(compiler), *flags, '-c', str(source / name),
                                 '-o', str(obj)], capture_output=True, text=True)
        results.append(dict(source=name, object=str(obj), exit=result.returncode,
                            log=result.stdout + result.stderr,
                            sha256=hashlib.sha256(obj.read_bytes()).hexdigest()
                            if result.returncode == 0 else None))
    report = dict(revision=inventory['revision'], shard=args.shard,
                  shards=args.shards, flags=flags, sdk_archives=[], results=results)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    if any(item['exit'] for item in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
