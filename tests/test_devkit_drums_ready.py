"""Exact streaming/state comparison for prepared Drums readiness specialization."""
import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def preparer():
    spec = importlib.util.spec_from_file_location(
        'drums_ready_prepare', ROOT / 'tools/jieli/prepare-renderer-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sources():
    return ((ROOT / 'engines/include/fm1_resampler.h').read_text(),
            (ROOT / 'engines/src/drums.cc').read_text())


@pytest.mark.parametrize('damaged', ['header', 'drums', 'duplicate', 'render_body', 'input_body'])
def test_changed_boundaries_refuse(damaged):
    header, drums = sources()
    if damaged == 'header':
        header = header.replace('  if (fm1_resampler_needed(r)) return 0.0f;', '')
    elif damaged == 'drums':
        drums = drums.replace('  void Render(float *out_lr, uint32_t frames) {', '')
    elif damaged == 'render_body':
        drums = drums.replace('pending_ -= took;', 'pending_ -= took; ++pending_;', 1)
    elif damaged == 'input_body':
        header = header.replace('if (n > need) n = need;', 'if (n > need) n = need - 1;', 1)
    else:
        header += '\n/* Array form:'
    with pytest.raises(ValueError, match='readiness boundary'):
        preparer().drums_ready_conversion(header, drums)


def test_option_refuses_without_reviewed_prerequisites(tmp_path):
    with pytest.raises(ValueError, match='Drums readiness requires'):
        preparer().prepare_renderer(tmp_path, ROOT, tmp_path / 'out', drums_ready_convert=True)


@pytest.mark.parametrize('sanitized', [False, True])
def test_streams_and_complete_states_match(tmp_path, sanitized):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('clang++ unavailable')
    header, drums = sources()
    # Match preparation order: specialize only after FIR scheduling/unrolling.
    header = preparer().unroll_resampler_lowpass(header)
    changed, _ = preparer().drums_ready_conversion(header, drums)
    reference = r'''
#include "baseline.h"
extern "C" {
void base_init(void *p,float rate) { assert(fm1_resampler_init((fm1_resampler_t*)p,47872.34f,rate)); }
unsigned base_need(const void *p) { return fm1_resampler_needed((const fm1_resampler_t*)p); }
unsigned base_push(void *p,const float *x,unsigned n) { return fm1_resampler_push((fm1_resampler_t*)p,x,n); }
float base_pop(void *p) { return fm1_resampler_pop((fm1_resampler_t*)p); }
}
'''
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef READY
#define FM1_DRUMS_READY_CONVERT 1
#endif
#include "resampler.h"
extern "C" {
void base_init(void *,float);unsigned base_need(const void *);
unsigned base_push(void *,const float *,unsigned);float base_pop(void *);
}
static uint32_t seed=136, hash=2166136261u;
static uint32_t rnd() { seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed; }
static void fold(const void *p, unsigned n) {
  const unsigned char *s=(const unsigned char*)p;
  while(n--) hash=(hash^*s++)*16777619u;
}
int main() {
  const float rates[]={47872.34f,44100.f,44118.f,32000.f,24000.f,12000.f};
  unsigned samples=0;
  for(float rate:rates) {
    fm1_resampler_t r,b; memset(&r,0,sizeof r);memset(&b,0,sizeof b);
    base_init(&b,rate);
    assert(fm1_resampler_init(&r,47872.34f,rate));
    for(unsigned j=0;j<120000;++j) {
      unsigned need=fm1_resampler_needed(&r);
      assert(need==base_need(&b));
      if(need) { float x=fm1_resampler_pop(&r),y=base_pop(&b);
        assert(x==0.f && !memcmp(&x,&y,sizeof x));assert(!memcmp(&r,&b,sizeof r)); }
#ifdef READY
      if(r.mode==FM1_RESAMPLER_CONVERT) assert(need==fm1_resampler_needed_convert(&r));
#endif
      while(need) {
        unsigned n=1+rnd()%need;float x[32];assert(n<=32);
        for(unsigned i=0;i<n;++i)x[i]=(int32_t)rnd()*(1.f/2147483648.f);
#ifdef READY
        if(r.mode==FM1_RESAMPLER_CONVERT) fm1_resampler_push_convert(&r,x,n);
        else
#endif
          assert(fm1_resampler_push(&r,x,n)==n);
        assert(base_push(&b,x,n)==n);assert(!memcmp(&r,&b,sizeof r));
        need-=n;fold(&r,sizeof r);
      }
      float y;
#ifdef READY
      if(r.mode==FM1_RESAMPLER_CONVERT)y=fm1_resampler_ready_convert(&r);
      else
#endif
        y=fm1_resampler_pop(&r);
      float expected=base_pop(&b);assert(!memcmp(&y,&expected,sizeof y));
      assert(!memcmp(&r,&b,sizeof r));fold(&y,sizeof y);fold(&r,sizeof r);++samples;
    }
    r.mode=b.mode=FM1_RESAMPLER_OFF;r.held=b.held=0;
    float x=fm1_resampler_pop(&r),y=base_pop(&b);
    assert(x==0.f && !memcmp(&x,&y,sizeof x));assert(!memcmp(&r,&b,sizeof r));
  }
  printf("%u %08x\n",samples,hash);
}
'''
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitized else []
    outputs = []
    for name, text in [('baseline', header), ('ready', changed)]:
        lane = tmp_path / name
        lane.mkdir()
        (lane / 'resampler.h').write_text(text)
        (lane / 'baseline.h').write_text(header)
        (lane / 'reference.cc').write_text('#include <assert.h>\n' + reference)
        (lane / 'test.cc').write_text(code)
        exe = lane / 'test'
        subprocess.run([compiler, '-O3', '-std=c++11', '-ffp-contract=off', *flags,
                        *(['-DREADY'] if name == 'ready' else []),
                        str(lane / 'test.cc'), str(lane / 'reference.cc'), '-o', str(exe)], check=True)
        outputs.append(subprocess.check_output([str(exe)]))
    assert outputs[0] == outputs[1]
    assert outputs[0].startswith(b'720000 ')
