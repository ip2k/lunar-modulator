// Exact full/main PCM and persistent state; owned upstream-derived engines.
#include <cassert>
#include <cstring>
#include <cstdio>
#include <new>
#include "reference.h"
#include "plaits/dsp/engine2/virtual_analog_vcf_engine.h"
int main() {
 using namespace plaits;
 alignas(16) unsigned char a[sizeof(ReferenceVirtualAnalogVCFEngine)]={};
 alignas(16) unsigned char b[sizeof(VirtualAnalogVCFEngine)]={};
 alignas(16) unsigned char c[sizeof(VirtualAnalogVCFEngine)]={};
 static_assert(sizeof(a)==sizeof(b),"no new state");
 auto *ref=new(a) ReferenceVirtualAnalogVCFEngine;
 auto *full=new(b) VirtualAnalogVCFEngine;
 auto *main=new(c) VirtualAnalogVCFEngine;
 ref->Init(nullptr);full->Init(nullptr);main->Init(nullptr);
 uint32_t rng=1;size_t frames=0;
 const float hs[]={.5f,.375f,.625f,0.f,1.f,.50001f,.37499f,.62501f};
 for(unsigned n=0;n<40000;++n) {
  rng=rng*1664525u+1013904223u;
  EngineParameters p={};p.note=-48.f+float(rng%18000)/100.f;
  p.harmonics=hs[(n/37)%8];p.timbre=float((rng>>8)%10001)/10000.f;
  p.morph=float((rng>>16)%10001)/10000.f;
  size_t len=1+(n%64);float x[64]={},y[64]={},z[64]={},u[64]={},v[64]={},w[64]={};bool ar=false,af=false,am=false;
  ref->Render(p,x,u,len,&ar);full->Render(p,y,v,len,&af);main->RenderMain(p,z,w,len,&am);
  assert(!memcmp(x,y,len*4)&&!memcmp(x,z,len*4)&&!memcmp(u,v,len*4));
  assert(ar==af&&ar==am);
  assert(!memcmp(a+sizeof(void*),b+sizeof(void*),sizeof(a)-sizeof(void*)));
  assert(!memcmp(a+sizeof(void*),c+sizeof(void*),sizeof(a)-sizeof(void*)));
  if(n%997==0) {ref->Reset();full->Reset();main->Reset();}
  frames+=len;
 }
 printf("PASS 40000 calls %zu frames full/main PCM and complete persistent state exact\n",frames);
}
