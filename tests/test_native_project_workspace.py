"""Actual compact binary writes borrow pixels without touching frame metadata."""
from pathlib import Path
import os
import subprocess
import pytest

from tests.native_test_flags import native_host_link_flags, native_no_pie_flags
from tests.native_test_toolchain import configured_target_toolchain
ROOT=Path(__file__).resolve().parents[1]
FILES=sorted((ROOT/'tests/fixtures/state/1.0').glob('*.lunarb'))
@pytest.fixture(scope='session')
def workspace_probe(tmp_path_factory):
    tmp=tmp_path_factory.mktemp('workspace');exe=tmp/'probe'
    inc=['-I'+str(ROOT/p) for p in ('engines/include','engines/state','sim/web/src','firmware/native')]
    sources=[ROOT/'tests/native/project_workspace.c',ROOT/'sim/web/src/fm1_tft.c']+[ROOT/'engines/state'/p for p in ('state_bin.c','state_names.c','state_movy1.c','fm1_num.c','fm1_deflate.c')]
    subprocess.run(['cc','-DFM1_TFT_INDEXED=1','-DFM1_STATE_BIN_COMPACT_WRITER','-std=c99','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-ffunction-sections','-fdata-sections',*native_no_pie_flags(),*inc,*map(str,sources),*native_host_link_flags(),'-lm','-o',str(exe)],check=True)
    return exe
def test_project_workspace_target_compile(tmp_path):
    tc = configured_target_toolchain()
    inc=['-I'+str(ROOT/p) for p in ('engines/include','engines/state','sim/web/src','firmware/native')]
    subprocess.run([str(tc/'pi32v2/bin/clang'),'-target','pi32v2','-mcpu=r3','-mfprev1','-Oz','-std=c99','-Wall','-Wextra','-Werror','-DFM1_TFT_INDEXED=1','-DFM1_STATE_BIN_COMPACT_WRITER',*inc,'-isystem',str(tc/'pi32v2/include'),'-c',str(ROOT/'tests/native/project_workspace.c'),'-o',str(tmp_path/'target.o')],check=True)


@pytest.mark.parametrize('mode',range(30))
def test_project_workspace(workspace_probe,mode):
    r=subprocess.run([str(workspace_probe),str(FILES[(mode//3)%len(FILES)]),str(mode)],check=True,capture_output=True,text=True)
    print(r.stdout,end='')
