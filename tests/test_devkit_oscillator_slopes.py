"""Exact oscillator output across settled/ramping PWM and all template modes."""
import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
HEADER = Path("plaits/dsp/oscillator/variable_shape_oscillator.h")


def preparer():
    spec = importlib.util.spec_from_file_location(
        "renderer_prepare", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_oscillator_slopes_refuses_drift():
    module = preparer()
    source = (ROOT / "engines/third_party/mutable" / HEADER).read_text()
    changed = module.reuse_oscillator_slopes(source)
    for bad in (changed,
                source.replace("template<bool enable_sync, bool output_phase>",
                               "template<bool changed_sync, bool output_phase>", 1),
                source.replace("    float next_sample = next_sample_;", ""),
                source.replace("      const float slope_up = 1.0f / (pw);", ""),
                source + source):
        with pytest.raises(ValueError, match="Unexpected oscillator loop"):
            module.reuse_oscillator_slopes(bad)


def test_oscillator_slopes_preserves_exact_float_output(tmp_path):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("C++ compiler unavailable")
    original = ROOT / "engines/third_party/mutable"
    modified = tmp_path / "modified"
    header = modified / HEADER
    header.parent.mkdir(parents=True)
    header.write_text(preparer().reuse_oscillator_slopes((original / HEADER).read_text()))
    cpp = tmp_path / "stress.cc"
    cpp.write_text(HARNESS)
    outputs = []
    for name, includes in (("baseline", [original]),
                           ("modified", [modified, original])):
        exe = tmp_path / (name + "-test")
        subprocess.run([compiler, "-std=c++11", "-O3", "-ffp-contract=off",
                        *["-I" + str(root) for root in includes],
                        str(cpp), "-o", str(exe)], check=True)
        outputs.append(subprocess.run([str(exe)], capture_output=True,
                                      check=True).stdout)
    # Four modes, 12,000 blocks each, eight uneven chunk sizes. Every float
    # must match, including startup, resets, endpoints and rounded PWM stalls.
    assert len(outputs[0]) == 5928000
    assert outputs[0] == outputs[1]


HARNESS = r'''#include "plaits/dsp/oscillator/variable_shape_oscillator.h"
#include <stdio.h>
#include <stdint.h>
#include <cmath>
#include <fenv.h>
static uint32_t seed=129734u;
static float rnd() { seed=seed*1664525u+1013904223u;return (seed>>8)*(1.0f/16777216.0f); }
template<bool sync, bool phase> static int run() {
 plaits::VariableShapeOscillator osc;osc.Init();float block[127];
 const unsigned sizes[]={1,2,3,7,12,31,64,127};
 for(unsigned i=0;i<12000;++i) {
  // Long settled runs, consecutive ramps, endpoint controls and resets.
  if (!(i%3000))osc.Init();
  float f=0.00001f+0.49f*rnd(),master=0.00001f+0.49f*rnd();
  float pw=(i%2000<1000)?0.5f:rnd();
  float shape=(i%3000<1000)?1.0f:((i%3000<2000)?0.0f:rnd());
  if(i%97==0)pw=0.0f;if(i%113==0)pw=1.0f;
  unsigned n=sizes[i%8];
  osc.Render<sync,phase>(master,f,pw,shape,0.37f,block,n);
  for(unsigned k=0;k<n;++k)if(!std::isfinite(block[k]))return 1;
  if(fwrite(block,sizeof(float),n,stdout)!=n)return 2;
 }
 return 0;
}
int main(){
#ifdef __GLIBC__
feenableexcept(FE_DIVBYZERO|FE_INVALID|FE_OVERFLOW);
#endif
return run<false,false>()||run<true,false>()||run<false,true>()||run<true,true>();}
'''
