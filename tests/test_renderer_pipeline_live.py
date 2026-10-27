"""App-level sealed-block PCM/ownership regression; no target timing claim."""
# Keep the ASan leak-detection default: enabled on Linux, unsupported on macOS.
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]
MODULES='dx7,macro,drums,filter,drive,echo,comp,arp,lfo,env,chance'

@pytest.mark.parametrize('sanitize',[False,True])
def test_live_pipeline_pcm_and_metadata(tmp_path,sanitize):
    cc=shutil.which('clang');cxx=shutil.which('clang++')
    if not cc or not cxx or not shutil.which('make'):
        pytest.skip('native clang toolchain unavailable')
    dev=tmp_path/'devkit';shutil.copytree(ROOT/'firmware/devkit',dev)
    live=dev/'renderer_live.c'
    live.write_text(live.read_text()+'\n'+(ROOT/'tests/fixtures/renderer_pipeline/live_replay.c').read_text())
    # The fixture owns main; leave the normal renderer object list intact.
    (dev/'renderer_pipeline_sdk.c').write_text('/* hooks supplied by live replay */\n')
    (dev/'renderer_reference.c').write_text('/* main supplied by live_replay.c */\n')
    results=[]; reports=[]
    for pipeline in (False,True):
        build=tmp_path/('pipeline' if pipeline else 'baseline')
        flags='-O2 -ffp-contract=off -DFM1_APP_EXTERNAL_ARENAS=1'
        if pipeline:flags+=' -DFM1_APP_RENDER_PIPELINE=1 -DLUNAR_DEVKIT_RENDERER_PIPELINE=1'
        if sanitize:flags+=' -fsanitize=address,undefined -fno-sanitize=shift -fno-omit-frame-pointer'
        exe=build/'fm1-devkit-renderer-ref'
        subprocess.run(['make','-s','-C',str(ROOT/'engines'),'-f','Makefile','-f',
                        str(ROOT/'sim/web/mk/sim.mk'),'-f',str(ROOT/'tools/jieli/renderer.mk'),
                        f'DEVKIT={dev}',f'SIM={ROOT / "sim/web"}',f'BUILD={build}',
                        'FM1_GPL_MODS=0',f'FM1_MODULES={MODULES}',f'CC={cc}',f'CXX={cxx}',
                        f'EXTRA={flags}','-j4',str(exe)],check=True,stdout=subprocess.DEVNULL)
        env=dict(os.environ,ASAN_OPTIONS='halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        for mode in (('immediate','delayed') if pipeline else ('baseline',)):
            pcm=tmp_path/(mode+'.pcm')
            result=subprocess.run([str(exe),str(pcm),mode],check=True,env=env,timeout=90,capture_output=True,text=True)
            reports.append(result.stdout)
            assert pcm.stat().st_size==22581248
            results.append(hashlib.sha256(pcm.read_bytes()).hexdigest());pcm.unlink()
        if pipeline:
            for mode in ('direct',):
                pcm=tmp_path/'fault.pcm'
                result=subprocess.run([str(exe),str(pcm),mode],env=env,capture_output=True,text=True,timeout=10)
                assert result.returncode==72,(mode,result.stderr)
                assert 'pipeline refusal' in result.stderr
                pcm.unlink()
    assert len(set(results))==1,results

    assert len(set(reports))==1,reports
