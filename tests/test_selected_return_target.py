"""Actual offline target binding with injected typed register operations."""
import importlib.util
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'firmware/third_party/selected-return'
FLAGS = ['-DLUNAR_SELECTED_RETURN_OFFLINE_PROOF=1',
         '-DLUNAR_SELECTED_RETURN_PI32V2_BINDING=1',
         '-DLUNAR_SELECTED_RETURN_TARGET_INJECTED=1']


@pytest.mark.parametrize('sanitized', [False, True])
def test_actual_injected_target_binding(tmp_path, sanitized):
    binary = tmp_path / 'check'
    flags = ['-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', *FLAGS]
    if sanitized:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    subprocess.run([os.environ.get('CC', 'cc'), *flags, '-I', str(PACKAGE),
                    str(PACKAGE / 'selected_return.c'),
                    str(PACKAGE / 'selected_return_pi32v2.c'),
                    str(ROOT / 'tests/fixtures/selected_return_target/check.c'),
                    '-o', str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'selected target binding passed' in result.stdout
    print(result.stdout, end='')


@pytest.mark.parametrize('defines,diagnostic', [
    ([*FLAGS, '-DLUNAR_SELECTED_RETURN_FAKE_MMIO=1'], 'mutually exclusive'),
    ([*FLAGS, '-D__PI32V2__=1'], 'injected target binding is host only'),
    (FLAGS[:2], 'target compiler or explicit injected target test required'),
    ([*FLAGS[:2], '-DLUNAR_SELECTED_RETURN_TARGET_INJECTED=0'],
     'injected target selection must equal one'),
])
def test_mutually_exclusive_bindings(tmp_path, defines, diagnostic):
    src = tmp_path / 'guard.c'
    src.write_text('#include "selected_return_pi32v2.h"\n')
    result = subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', *defines,
                             '-I', str(PACKAGE), '-fsyntax-only', str(src)],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert diagnostic in result.stderr


def test_target_qualifiers_preserve_host_layout(tmp_path):
    src = tmp_path / 'layout.c'
    src.write_text('#include "selected_return.h"\n#include <stdio.h>\n'
                   '#include <stddef.h>\nint main(void) { printf("%zu %zu %zu\\n",'
                   'sizeof(lunar_selected_return_t),offsetof(lunar_selected_return_t,io),'
                   'offsetof(lunar_selected_return_t,reset_attempted)); }\n')
    outputs = []
    for n, flags in enumerate([['-DLUNAR_SELECTED_RETURN_OFFLINE_PROOF=1',
                                '-DLUNAR_SELECTED_RETURN_FAKE_MMIO=1'], FLAGS]):
        binary = tmp_path / f'layout{n}'
        subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', *flags,
                        '-I', str(PACKAGE), str(src), '-o', str(binary)], check=True)
        outputs.append(subprocess.check_output([str(binary)]))
    assert outputs[0] == outputs[1]


def test_return_candidate_is_separate_fixed_plan(tmp_path):
    spec = importlib.util.spec_from_file_location('return_builder',
                                                ROOT / 'tools/native/build_diagnostic.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.check_inventory(PACKAGE)
    for call in [lambda: builder.diagnostic_plan(return_candidate=True),
                 lambda: builder.manifest(return_candidate=True)]:
        with pytest.raises(ValueError, match='requires fixed selected plan'):
            call()
    old = builder.diagnostic_plan(selected=True, prepared=tmp_path)
    candidate = builder.diagnostic_plan(selected=True, prepared=tmp_path, return_candidate=True)
    assert candidate['extra'][:3] == old['extra'][:3]
    assert ROOT / 'firmware/native/diagnostic_platform.c' not in candidate['extra']
    assert candidate['extra'][3:6] == [PACKAGE / name for name in
        ['selected_return.c', 'selected_return_pi32v2.c', 'selected_return_platform.c']]
    assert candidate['linker'] == PACKAGE / 'selected_return_candidate.ld'
    assert candidate['profile'] == 'sdk-free-selected-trio-return-binding-candidate-v1'
    assert 'linker' not in old
    assert not any('selected-return/' in name for name in builder.manifest(True))
    manifest = builder.manifest(True, return_candidate=True)
    assert manifest['firmware/third_party/selected-return/selected_return_pi32v2.c'] == \
        builder.digest(PACKAGE / 'selected_return_pi32v2.c')
