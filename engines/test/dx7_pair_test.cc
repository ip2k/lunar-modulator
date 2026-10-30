// SPDX-License-Identifier: MIT
// Algorithm-5 differential against the unmodified msfa scalar runner.
#include "../src/dx7_loop.h"
#include <cstdio>
#include <cstring>
using namespace fm1_msfa;
static uint32_t rng=71;
static uint32_t next() { rng^=rng<<13; rng^=rng>>17; rng^=rng<<5; return rng; }
int main() {
  FmCore core;
  const int edge[]={0,1119,1120,1121,1<<20,1<<24};
  unsigned hits=0, fallback=0;
  for (int trial=0; trial<100000; ++trial) {
    FmOpParams a[6],b[6]; int32_t x[64],y[64],f[2],g[2];
    for(int j=0;j<6;++j) {
      a[j].gain[0]=trial%3 ? next()%(1<<25) : edge[next()%6];
      a[j].gain[1]=trial%3 ? next()%(1<<25) : edge[next()%6];
      a[j].freq=static_cast<int32_t>(next()); a[j].phase=static_cast<int32_t>(next());
    }
    for(int j=0;j<64;++j) x[j]=y[j]=static_cast<int32_t>(next());
    for(int j=0;j<2;++j) f[j]=g[j]=static_cast<int32_t>(next()%(1<<26))-(1<<25);
    std::memcpy(b,a,sizeof(a)); const int shift=trial%17;
    bool used=fm1::dx7::RenderAlgorithmFive(b,shift,g,y);
    if(!used) { ++fallback; if(std::memcmp(a,b,sizeof(a))||std::memcmp(f,g,sizeof(f))||std::memcmp(x,y,sizeof(x))) return 2; core.compute(y,b,4,g,shift); }
    else ++hits;
    core.compute(x,a,4,f,shift);
    if(std::memcmp(a,b,sizeof(a))||std::memcmp(f,g,sizeof(f))||std::memcmp(x,y,sizeof(x))) { std::printf("FAIL trial %d shift %d\n",trial,shift); return 3; }
  }
  std::printf("PASS 100000 randomized blocks, %u fused / %u untouched fallback; exact samples, phases, gains, feedback\n",hits,fallback);
  return 0;
}
