# SPDX-License-Identifier: MIT
"""Bounded C adapter with the real journal and simulated NOR callbacks."""
from pathlib import Path
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='session')
def adapter(tmp_path_factory):
    executable = tmp_path_factory.mktemp('settings-flash')/'adapter'
    subprocess.run(['cc','-std=c99','-O1','-g','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-fno-omit-frame-pointer',
                    '-I',str(ROOT/'firmware/native'),
                    str(ROOT/'tests/native/settings_flash.c'),'-o',str(executable)],check=True)
    return executable


@pytest.mark.parametrize('case',range(30),ids=[f'case-{i:02}' for i in range(30)])
def test_bounded_flash_adapter(adapter,case):
    subprocess.run([str(adapter),str(case)],check=True)
