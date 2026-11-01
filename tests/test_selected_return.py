"""Offline fake-MMIO executes the actual selected return policy; no target build."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'firmware/third_party/selected-return'
PROOF = ['-DLUNAR_SELECTED_RETURN_OFFLINE_PROOF=1',
         '-DLUNAR_SELECTED_RETURN_FAKE_MMIO=1']


@pytest.mark.parametrize('sanitized', [False, True])
def test_actual_selected_return_policy(tmp_path, sanitized):
    binary = tmp_path / 'check'
    flags = ['-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', *PROOF]
    if sanitized:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    subprocess.run([os.environ.get('CC', 'cc'), *flags, '-I', str(PACKAGE),
                    str(PACKAGE / 'selected_return.c'),
                    str(ROOT / 'tests/fixtures/selected_return/check.c'),
                    '-o', str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'selected return proof passed' in result.stdout
    print(result.stdout, end='')


@pytest.mark.parametrize('defines,diagnostic', [
    ([], 'selected return is offline proof only'),
    (['-DLUNAR_SELECTED_RETURN_OFFLINE_PROOF=1'], 'selected return needs fake MMIO'),
    ([*PROOF, '-D__PI32V2__=1'], 'target binding is not admitted'),
])
def test_selected_return_binding_refuses(tmp_path, defines, diagnostic):
    src = tmp_path / 'guard.c'
    src.write_text('#include "selected_return.h"\n')
    result = subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', *defines,
                             '-I', str(PACKAGE), '-fsyntax-only', str(src)],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert diagnostic in result.stderr
