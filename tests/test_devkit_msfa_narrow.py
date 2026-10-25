"""The private pi32 comparison preserves the original low sample bits."""
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def preparer():
    spec = importlib.util.spec_from_file_location('renderer_prepare', ROOT / 'tools/jieli/prepare-renderer-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('name', ['sin.h', 'fm_op_kernel.cc'])
def test_narrow_adds_reject_source_drift(name):
    source = (ROOT / 'engines/third_party/msfa' / name).read_text()
    changed = preparer().narrow_msfa_adds(source, name)
    with pytest.raises(ValueError, match='Unexpected msfa addition'):
        preparer().narrow_msfa_adds(changed, name)
    with pytest.raises(ValueError, match='Unexpected msfa source'):
        preparer().narrow_msfa_adds(source, 'other.cc')
    assert (ROOT / 'engines/third_party/msfa' / name).read_text() == source


def test_narrow_adds_match_signed_wide_sums(tmp_path):
    cc = shutil.which('cc')
    if not cc:
        pytest.skip('native compiler unavailable')
    module = preparer()
    sine = (ROOT / 'engines/third_party/msfa/sin.h').read_text()
    kernel = (ROOT / 'engines/third_party/msfa/fm_op_kernel.cc').read_text()
    old_sine = re.search(r'  return y0 .*?;', sine).group()
    new_sine = re.search(r'  return \(int32_t\).*?;', module.narrow_msfa_adds(sine, 'sin.h')).group()
    old_mix = re.search(r'output\[i\] \+= .*?;', kernel).group()
    new_mix = re.search(r'output\[i\] = \(int32_t\).*?;', module.narrow_msfa_adds(kernel, 'fm_op_kernel.cc')).group()
    source = '#include <stdint.h>\n#define SHIFT 14\n'
    for name, body in [('old_sine', old_sine), ('new_sine', new_sine)]:
        source += 'int32_t ' + name + '(int32_t y0,int32_t dy,int32_t lowbits){' + body + '}\n'
    for name, body in [('old_mix', old_mix), ('new_mix', new_mix)]:
        source += 'int32_t ' + name + '(int32_t x,int32_t y,int32_t gain){int32_t output[1]={x};int i=0;' + body + 'return output[0];}\n'
    source += r'''
static uint32_t rng=0x6d2b79f5;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
int main(void){
  const int32_t edge[]={0,1,-1,INT32_MIN,INT32_MAX,0x01000000,-0x01000000};
  for(unsigned i=0;i<7;i++)for(unsigned j=0;j<7;j++)for(unsigned k=0;k<7;k++){
    if(old_mix(edge[i],edge[j],edge[k])!=new_mix(edge[i],edge[j],edge[k]))return 1;
    if(old_sine(edge[i],edge[j],(uint32_t)edge[k]&16383)!=new_sine(edge[i],edge[j],(uint32_t)edge[k]&16383))return 2;
  }
  for(unsigned i=0;i<2000000;i++){
    int32_t a=(int32_t)next(),b=(int32_t)next(),c=(int32_t)next();
    if(old_mix(a,b,c)!=new_mix(a,b,c))return 3;
    if(old_sine(a,b,(uint32_t)c&16383)!=new_sine(a,b,(uint32_t)c&16383))return 4;
  }
  return 0;
}
'''
    path = tmp_path / 'sums.c'
    path.write_text(source)
    exe = tmp_path / 'sums'
    subprocess.run([cc, '-std=c99', '-O2', str(path), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
