"""Pinned source-based native math/memory subset versus an independent host libc."""
import hashlib
import json
import os
import shutil
import subprocess

import pytest

from tests.native_test_flags import native_no_pie_flags

from tests.engine_helpers import ROOT


@pytest.fixture(scope='session')
def native_libc(tmp_path_factory):
    cc, nm, objcopy = (shutil.which(name) for name in ('cc', 'nm', 'objcopy'))
    if not all((cc, nm, objcopy)):
        pytest.skip('host C compiler, nm and ELF objcopy required')
    source = ROOT / 'firmware/third_party/musl'
    compat = ROOT / 'firmware/native/libc_compat'
    inventory = json.loads((source / 'inventory.json').read_text())
    for name, digest in inventory['files'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
    out = tmp_path_factory.mktemp('native-libc')
    flags = ['-O2', '-g', '-fno-builtin', '-D_GNU_SOURCE',
             '-DLUNAR_MUSL_HOST_TEST', '-Werror=implicit-function-declaration',
             '-include', str(compat / 'declarations.h')]
    for directory in (compat, source / 'src/internal', source / 'src/math',
                      source / 'arch/generic'):
        flags += ['-I', str(directory)]
    sanitizer = os.environ.get('FM1_NATIVE_SANITIZERS') == '1'
    san_flags = (['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
                 if sanitizer else [])
    objects, names = [], set()
    for name in sorted(inventory['files']):
        if not name.endswith('.c'):
            continue
        obj = out / (source / name).with_suffix('.o').name
        subprocess.run([cc, *flags, *san_flags, '-c', str(source / name),
                        '-o', str(obj)], check=True)
        objects.append(obj)
        symbols = subprocess.check_output([nm, '-g', '--defined-only', str(obj)],
                                          text=True)
        names.update(line.split()[-1] for line in symbols.splitlines() if line)
    # Rename definitions and references together after compilation. The harness
    # retains normal host names, so it cannot compare a function with itself.
    aliases = out / 'rename.txt'
    aliases.write_text(''.join(f'{name} probe_{name}\n' for name in sorted(names)))
    for obj in objects:
        subprocess.run([objcopy, f'--redefine-syms={aliases}', str(obj)], check=True)
    binary = out / 'check'
    subprocess.run([cc, '-O2', '-g', '-fno-builtin', *san_flags,
                    *native_no_pie_flags(), str(ROOT / 'tests/native_libc_check.c'),
                    *map(str, objects), '-lm', '-o', str(binary)], check=True)
    return binary


@pytest.mark.parametrize('shard', range(16))
def test_native_libc(native_libc, shard):
    subprocess.run([str(native_libc), str(shard)], check=True)
