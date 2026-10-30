"""Exact native callback body under mock leases/DMA; no SDK IRQ timing claim."""
# Keep the ASan leak-detection default: enabled on Linux, unsupported on macOS.
from pathlib import Path
import shutil
import subprocess
import os
import pytest
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('sanitize',[False,True])
def test_pipeline_dac_output(tmp_path,sanitize):
    cc=shutil.which('clang')
    if not cc:pytest.skip('clang unavailable')
    text=(ROOT/'firmware/devkit/renderer_pipeline_dac.c').read_text()
    actual=text[text.index('#define CASE_BLOCKS'):text.index('static void fill103')]
    fence='__asm__ volatile("csync;" ::: "memory");'
    assert actual.count(fence)==1
    actual=actual.replace(fence,'__asm__ volatile("" ::: "memory");')
    actual='\n'.join(line for line in actual.splitlines() if not line.startswith('#pragma'))
    prefix='''#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#include "renderer_pipeline_live.h"
typedef uint8_t u8;
#define local_irq_save(f) ((f)=0)
#define local_irq_restore(f) ((void)(f))
'''
    source=tmp_path/'output.c'
    source.write_text(prefix+actual+(ROOT/'tests/fixtures/renderer_pipeline/dac_output.c').read_text())
    flags=['-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitize else []
    exe=tmp_path/'output'
    subprocess.run([cc,'-std=c11','-O2','-g',*flags,'-DLUNAR_PIPELINE_CYCLES=1',
                    '-I'+str(ROOT/'firmware/devkit'),str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=30,env=dict(os.environ,
        ASAN_OPTIONS='halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1'))

@pytest.mark.parametrize('backend',[False,True])
def test_pipeline_dac_build_selector(backend):
    make=shutil.which('make')
    if not make:pytest.skip('make unavailable')
    flags='-DLUNAR_DEVKIT_RENDERER_PIPELINE_DAC=1'
    if backend:flags+=' -DLUNAR_DEVKIT_RENDERER_PIPELINE=1'
    result=subprocess.run([make,'--no-print-directory','-f',str(ROOT/'tools/jieli/renderer.mk'),
        'print-devkit-renderer-objs','BUILD=/lane/build','SIM=/lane/sim',f'EXTRA={flags}'],capture_output=True,text=True)
    if backend:
        assert result.returncode==0,result.stderr
        assert '/lane/build/devkit/renderer_pipeline_dac.o' in result.stdout
    else:
        assert result.returncode!=0 and 'requires the renderer pipeline backend' in result.stderr
