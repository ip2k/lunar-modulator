"""Fixed-loop expansion must preserve the whole streaming state and PCM."""
import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def preparer():
    spec = importlib.util.spec_from_file_location(
        'renderer_prepare', ROOT / 'tools/jieli/prepare-renderer-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_expanded_lowpass_stream_is_bit_identical(tmp_path):
    if not shutil.which('c++'):
        pytest.skip('C++ compiler unavailable')
    original = (ROOT / 'engines/include/fm1_resampler.h').read_text()
    expanded = preparer().unroll_resampler_lowpass(original)
    # Separate namespaces compile both real implementations in one program.
    # Strip only the header guard, which would suppress the second copy.
    (tmp_path / 'original.h').write_text(original)
    expanded = expanded.replace('FM1_RESAMPLER_H', 'FM1_RESAMPLER_UNROLLED_H')
    (tmp_path / 'expanded.h').write_text(expanded)
    source = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
namespace reference {
#include "original.h"
}
namespace expanded {
#include "expanded.h"
}
int main() {
  const float rates[] = {44100, 44118, 47872.34f, 48000, 88200, 96000, 176400};
  uint32_t seed = 17;
  for (float out : {44100.0f, 44118.0f}) for (float in : rates) {
    reference::fm1_resampler_t a; expanded::fm1_resampler_t b;
    memset(&a, 0, sizeof a); memset(&b, 0, sizeof b);
    assert(reference::fm1_resampler_init(&a,in,out) == expanded::fm1_resampler_init(&b,in,out));
    for (unsigned n=0;n<16384;++n) {
      assert(reference::fm1_resampler_needed(&a)==expanded::fm1_resampler_needed(&b));
      while(reference::fm1_resampler_needed(&a)) {
        seed=seed*1664525u+1013904223u;
        float sample=(float)(int32_t(seed)>>8)*(1.0f/8388608.0f);
        assert(reference::fm1_resampler_push(&a,&sample,1)==expanded::fm1_resampler_push(&b,&sample,1));
      }
      float x=reference::fm1_resampler_pop(&a), y=expanded::fm1_resampler_pop(&b);
      assert(memcmp(&x,&y,sizeof x)==0);
      assert(sizeof a==sizeof b && memcmp(&a,&b,sizeof a)==0);
    }
  }
}
'''
    cpp = tmp_path / 'compare.cc'
    cpp.write_text('#include <initializer_list>\n' + source)
    exe = tmp_path / 'compare'
    subprocess.run(['c++', '-std=c++11', '-O2', '-ffp-contract=off', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


@pytest.mark.parametrize('change', ['FM1_RESAMPLER_DELAY 30', 'FM1_RESAMPLER_LP_LEN (4 * FM1_RESAMPLER_DELAY + 3)', 'y2 += h[j + 2]',
                                    'j + 4 <= FM1_RESAMPLER_LP_PAIRS'])
def test_lowpass_source_drift_refuses(change):
    original = (ROOT / 'engines/include/fm1_resampler.h').read_text()
    with pytest.raises(ValueError, match='lowpass'):
        preparer().unroll_resampler_lowpass(original.replace(change, 'source_changed', 1))
