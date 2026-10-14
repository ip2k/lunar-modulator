# SPDX-License-Identifier: MIT
"""Exercise scattered IO and the real journal without binding physical flash."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_scattered_project_io(tmp_path):
    executable = tmp_path / 'extent-io'
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    if sys.platform.startswith('linux'):
        flags += ['-fno-pie', '-no-pie']
    subprocess.run([
        'cc', '-std=c99', '-O1', '-g', '-Wall', '-Wextra', '-Werror', *flags,
        '-I' + str(ROOT / 'firmware/native'),
        str(ROOT / 'tests/native/extent_io.c'), '-o', str(executable),
    ], check=True)
    result = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
    assert result.stdout.strip() == 'extent IO checks passed'
