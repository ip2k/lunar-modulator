# SPDX-License-Identifier: MIT
"""Real codec plus transactional NOR, including reboot after torn callbacks."""
from pathlib import Path
import subprocess
import os
import pytest

from tests.native_test_flags import native_host_link_flags, native_no_pie_flags
from tests.native_test_toolchain import configured_target_toolchain
ROOT=Path(__file__).resolve().parents[1]
FILES=sorted((ROOT/'tests/fixtures/state/1.0').glob('*.lunarb'))
CASES=[(p.name,i) for i,p in enumerate(FILES)]+[('first-orbit.lunarb',i) for i in range(9,30)]
@pytest.fixture(scope='session')
def writer(tmp_path_factory):
    exe=tmp_path_factory.mktemp('project-stream')/'test'
    sources=['state_bin.c','state_names.c','state_print.c','state_movy1.c','fm1_num.c','fm1_deflate.c']
    cmd=['cc','-std=c99','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',*native_no_pie_flags(),'-ffunction-sections','-fdata-sections',*native_host_link_flags(),'-DFM1_STATE_BIN_COMPACT_WRITER','-DFM1_TFT_INDEXED=1','-I'+str(ROOT/'sim/web/src'),'-I'+str(ROOT/'firmware/native'),'-I'+str(ROOT/'engines/include'),'-I'+str(ROOT/'engines/state')]
    subprocess.run(cmd+[str(ROOT/'tests/native/project_save.c'),str(ROOT/'sim/web/src/fm1_tft.c')]+[str(ROOT/'engines/state'/s) for s in sources]+['-lm','-o',str(exe)],check=True)
    return exe
def test_project_save_target_compile(tmp_path):
    tc = configured_target_toolchain()
    subprocess.run([str(tc/'pi32v2/bin/clang'),'-target','pi32v2','-mcpu=r3','-mfprev1','-Oz','-std=c99','-Wall','-Wextra','-Werror','-DFM1_TFT_INDEXED=1','-DFM1_STATE_BIN_COMPACT_WRITER',*['-I'+str(ROOT/p) for p in ('firmware/native','engines/include','engines/state','sim/web/src')],'-isystem',str(tc/'pi32v2/include'),'-c',str(ROOT/'tests/native/project_save.c'),'-o',str(tmp_path/'target.o')],check=True)


@pytest.mark.parametrize('filename,case',CASES)
def test_project_save(writer,filename,case):
    subprocess.run([str(writer),str(ROOT/'tests/fixtures/state/1.0'/filename),str(case)],check=True)
