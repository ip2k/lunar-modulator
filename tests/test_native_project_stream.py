# SPDX-License-Identifier: MIT
"""Real codec plus transactional NOR, including reboot after torn callbacks."""
from pathlib import Path
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]
FILES=sorted((ROOT/'tests/fixtures/state/1.0').glob('*.lunarb'))
CASES=[(p.name,i) for i,p in enumerate(FILES)]+[('first-orbit.lunarb',i) for i in range(9,30)]
@pytest.fixture(scope='session')
def writer(tmp_path_factory):
    exe=tmp_path_factory.mktemp('project-stream')/'test'
    sources=['state_bin.c','state_names.c','state_print.c','state_movy1.c','fm1_num.c','fm1_deflate.c']
    cmd=['cc','-std=c99','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DFM1_STATE_BIN_COMPACT_WRITER','-I'+str(ROOT/'firmware/native'),'-I'+str(ROOT/'engines/include'),'-I'+str(ROOT/'engines/state')]
    subprocess.run(cmd+[str(ROOT/'tests/native/project_stream.c')]+[str(ROOT/'engines/state'/s) for s in sources]+['-lm','-o',str(exe)],check=True)
    return exe
@pytest.mark.parametrize('filename,case',CASES)
def test_project_stream(writer,filename,case):
    subprocess.run([str(writer),str(ROOT/'tests/fixtures/state/1.0'/filename),str(case)],check=True)
