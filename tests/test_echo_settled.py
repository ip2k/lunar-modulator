"""Differential PCM and full-state regression for settled Echo glides."""
from pathlib import Path
import os
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("sanitized", [False, True])
def test_echo_settled_glides_preserve_pcm_and_state(tmp_path, sanitized):
    current = (ROOT / "engines/src/fx_echo.cc").read_text()
    new_step = r'''  bool Step(float k, float epsilon) {
    const float d = target - value;
    if (d > -epsilon && d < epsilon) { value = target; return false; }
    value += k * d;
    return true;
  }'''
    old_step = r'''  void Step(float k, float epsilon) {
    const float d = target - value;
    if (d > -epsilon && d < epsilon) value = target;
    else value += k * d;
  }'''
    new_render = r'''    // Parameters cannot change within this call. Keep every original glide
    // step through its snap sample, then skip settled checks until next call.
    bool gliding = true;
    for (uint32_t i = 0; i < frames; ++i, lr += 2) {
      const float in[2] = { Guard(lr[0]), Guard(lr[1]) };
      if (gliding) {
        gliding = time.Step(k_time, 1e-3f);
        gliding |= depth.Step(k_time, 1e-3f);
        gliding |= feedback.Step(k_gain, 1e-6f);
        gliding |= pingpong.Step(k_gain, 1e-6f);
        gliding |= mix.Step(k_gain, 1e-6f);
        gliding |= level.Step(k_gain, 1e-6f);
      }
'''
    old_render = r'''    for (uint32_t i = 0; i < frames; ++i, lr += 2) {
      const float in[2] = { Guard(lr[0]), Guard(lr[1]) };
      time.Step(k_time, 1e-3f);
      depth.Step(k_time, 1e-3f);
      feedback.Step(k_gain, 1e-6f);
      pingpong.Step(k_gain, 1e-6f);
      mix.Step(k_gain, 1e-6f);
      level.Step(k_gain, 1e-6f);
'''
    assert current.count(new_step) == current.count(new_render) == 1
    baseline = current.replace(new_step, old_step).replace(new_render, old_render)
    baseline = baseline.replace("namespace echo", "namespace echo_baseline").replace(
        "fm1::echo::", "fm1::echo_baseline::").replace("fm1_engine_echo", "fm1_engine_echo_baseline")
    (tmp_path / "baseline.cc").write_text(baseline)
    (tmp_path / "candidate.cc").write_text(current)
    (tmp_path / "proof.cc").write_text(r'''#include <initializer_list>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <limits>
#include "baseline.cc"
#include "candidate.cc"
int main() {
  uint32_t rng=7;unsigned long frames=0,calls=0;
  const unsigned sizes[]={0,1,7,64,65,127,256};
  for(float rate: {8000.f,44118.f,48000.f,96000.f}) {
    fm1_host_t host={};host.sample_rate=rate;
    auto *a=new fm1::echo_baseline::Instance();auto *b=new fm1::echo::Instance();
    static_assert(sizeof(*a)==sizeof(*b),"unchanged state layout");
    a->Init(&host);b->Init(&host);
    float x[512],y[512];
    for(unsigned k=0;k<10000;++k) {
      if(k%997==0 || k<14) {
        unsigned param=(k/997+k)%7;
        const auto &p=fm1::echo::kParams[param];
        float v=(k%3==0)?p.min:(k%3==1)?p.max:p.def;
        a->Set(param,v);b->Set(param,v);
      }
      if(k==19){a->Set(3,-0.f);b->Set(3,-0.f);}
      if(k==31){a->Set(0,std::numeric_limits<float>::quiet_NaN());b->Set(0,std::numeric_limits<float>::quiet_NaN());}
      unsigned n=sizes[k%7];
      for(unsigned j=0;j<2*n;++j){rng=rng*1664525u+1013904223u;x[j]=(int32_t)rng*(1.f/2147483648.f);}
      if(k%100==0 && n){x[0]=std::numeric_limits<float>::infinity();x[1]=std::numeric_limits<float>::quiet_NaN();}
      memcpy(y,x,2*n*sizeof(float));a->Render(x,n);b->Render(y,n);
      if(memcmp(x,y,2*n*sizeof(float)) || memcmp(a,b,sizeof(*a))){fprintf(stderr,"mismatch rate=%g block=%u\n",rate,k);return 1;}
      frames+=n;++calls;
    }
    delete a;delete b;
  }
  printf("PASS exact PCM and full persistent state: %lu frames %lu calls four rates, parameter changes, signed zero, hostile inputs\n",frames,calls);
}
''')
    flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if sanitized else []
    exe = tmp_path / "proof"
    subprocess.run([os.environ.get("FM1_SIM_CXX", "c++"), "-std=c++11", "-O2",
                    "-ffp-contract=off", *flags, "-I" + str(ROOT / "engines/include"),
                    str(tmp_path / "proof.cc"), "-o", str(exe)], check=True, capture_output=True)
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=120)
    assert "2970528 frames 40000 calls" in result.stdout
