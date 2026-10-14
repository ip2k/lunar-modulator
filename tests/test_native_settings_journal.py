# SPDX-License-Identifier: MIT
"""Actual C journal under byte-by-byte NOR interruption and corruption."""
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='session')
def journal(tmp_path_factory):
    executable = tmp_path_factory.mktemp('journal') / 'journal'
    subprocess.run(['cc', '-std=c99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-I', str(ROOT / 'firmware/native'),
                    str(ROOT / 'tests/native/settings_journal.c'),
                    '-o', str(executable)], check=True)
    return executable


@pytest.mark.parametrize('case', range(30), ids=[f'case-{i:02}' for i in range(30)])
def test_journal_nor_faults(journal, case):
    subprocess.run([str(journal), str(case)], check=True)
