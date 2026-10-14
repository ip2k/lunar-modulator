# SPDX-License-Identifier: MIT
"""Actual binary reader/writer roundtrips and NOR sink refusal tests."""
from pathlib import Path
import subprocess
import re
import pytest
ROOT=Path(__file__).resolve().parents[1]
FILES=sorted((ROOT/'tests/fixtures/state/1.0').glob('*.lunarb'))
CASES=[(p.name,0) for p in FILES]+[('first-orbit.lunarb',n) for n in list(range(1,20))+[9999,10000]]
@pytest.fixture(scope='session',params=[False,True],ids=['normal','compact'])
def writer(request,tmp_path_factory):
    exe=tmp_path_factory.mktemp('state-stream')/'test'
    sources=['state_bin.c','state_names.c','state_print.c','state_movy1.c','fm1_num.c','fm1_deflate.c']
    cmd=['cc','-std=c99','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-I'+str(ROOT/'engines/include'),'-I'+str(ROOT/'engines/state')]
    if request.param: cmd+=['-DFM1_STATE_BIN_COMPACT_WRITER']
    subprocess.run(cmd+[str(ROOT/'tests/native/state_stream.c')]+[str(ROOT/'engines/state'/s) for s in sources]+['-lm','-o',str(exe)],check=True)
    return exe
@pytest.mark.parametrize('filename,failure',CASES)
def test_stream(writer,filename,failure):
    command=[str(writer),str(ROOT/'tests/fixtures/state/1.0'/filename)]
    result=subprocess.run(command+[str(failure)],check=True,capture_output=True,text=True)
    print(result.stdout,end='')
    if failure==10000:
        calls=int(re.search(r'calls=(\d+)',result.stdout)[1])
        for cut in range(1,calls+1):
            subprocess.run(command+[str(cut)],check=True,capture_output=True)
        print(f'All {calls} callback failure positions refused safely')
