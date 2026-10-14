# SPDX-License-Identifier: MIT
"""Exercise scattered IO and the real journal without binding physical flash."""
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('harness,expected', [
    ('extent_io.c', 'extent IO checks passed'),
    ('storage48_scatter.c', 'storage48 scatter checks passed'),
])
def test_scattered_project_io(tmp_path, harness, expected):
    executable = tmp_path / 'extent-io'
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    if sys.platform.startswith('linux'):
        flags += ['-fno-pie', '-no-pie']
    subprocess.run([
        'cc', '-std=c99', '-O1', '-g', '-Wall', '-Wextra', '-Werror', *flags,
        '-I' + str(ROOT / 'firmware/native'),
        str(ROOT / 'tests/native' / harness), '-o', str(executable),
    ], check=True)
    result = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
    assert result.stdout.strip() == expected
