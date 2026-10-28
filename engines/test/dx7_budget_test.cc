// SPDX-License-Identifier: MIT. Opt-in admission, retirement and PCM boundary checks.
#include "fm1_engine.h"
#include "fm1_dx7_budget.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
extern "C" const fm1_engine_t fm1_engine_dx7;
struct Engine {
  fm1_host_t host;
  void *memory, *self;
  Engine(float rate): host{FM1_ENGINE_API_VERSION, rate, 129}, memory(NULL), self(NULL) {
    memory = std::malloc(fm1_engine_dx7.instance_size(&host) + 15);
    assert(memory);
    self = fm1_engine_dx7.create(reinterpret_cast<void *>(
      (reinterpret_cast<uintptr_t>(memory) + 15) & ~uintptr_t(15)), &host);
    assert(self);
  }
  ~Engine() { fm1_engine_dx7.destroy(self); std::free(memory); }
  void on(unsigned key) { fm1_engine_dx7.note_on(self, key, 100); }
  void off(unsigned key) { fm1_engine_dx7.note_off(self, key); }
  void render(float *out, unsigned n=64) { fm1_engine_dx7.render(self, out, n); }
  fm1_dx7_budget_stats_t stats() const {
    fm1_dx7_budget_stats_t s; assert(fm1_dx7_get_budget_stats(self, &s)); return s;
  }
};
int main(int argc, char **argv) {
  assert(argc==2); const float rate=std::atof(argv[1]);
  Engine baseline(rate), explicit12(rate);
  fm1_dx7_budget_stats_t untouched={123,456,789,1011}, sentinel=untouched;
  assert(!fm1_dx7_set_voice_limit(NULL,8));
  assert(!fm1_dx7_get_budget_stats(NULL,&untouched));
  assert(!std::memcmp(&untouched,&sentinel,sizeof sentinel));
  assert(!fm1_dx7_get_budget_stats(baseline.self,NULL));
  assert(!fm1_dx7_set_voice_limit(baseline.self,0));
  assert(!fm1_dx7_set_voice_limit(baseline.self,13));
  assert(baseline.stats().limit==12 && !baseline.stats().active);
  float a[258],b[258]; const unsigned sizes[]={1,7,64,129};
  for(unsigned call=0;call<640;++call) {
    if(call%9==0) { baseline.on(36+call/9%35); explicit12.on(36+call/9%35); }
    if(call%13==0) { baseline.off(36+call/13%35); explicit12.off(36+call/13%35); }
    assert(fm1_dx7_set_voice_limit(explicit12.self,12));
    unsigned frames=sizes[call%4]; baseline.render(a,frames); explicit12.render(b,frames);
    assert(!std::memcmp(a,b,frames*2*sizeof(float)));
  }
  // All envelopes/phases are advanced equally. Retiring released keys must
  // leave exactly the independently instantiated eight held voices after
  // the one-block fade; no reference to internal allocation slots is needed.
  Engine full(rate), held(rate);
  for(unsigned key=48;key<60;++key) full.on(key);
  for(unsigned key=52;key<60;++key) held.on(key);
  for(unsigned block=0;block<4;++block) {full.render(a);held.render(b);}
  for(unsigned key=48;key<52;++key)full.off(key);
  assert(full.stats().active==12);
  assert(fm1_dx7_set_voice_limit(full.self,8));
  assert(full.stats().active==12); // request is not a mid-block mutation
  full.render(a); held.render(b);
  assert(full.stats().active==8 && full.stats().retired==4);
  for(unsigned block=0;block<32;++block) {
    full.render(a);held.render(b);
    assert(!std::memcmp(a,b,128*sizeof(float)));
    for(unsigned sample=0;sample<128;++sample)assert(std::isfinite(a[sample]));
  }
  assert(fm1_dx7_set_voice_limit(full.self,12));
  assert(full.stats().active==8); // restoring capacity does not resurrect notes
  for(unsigned key=48;key<52;++key)full.on(key);
  assert(full.stats().active==12);
  assert(fm1_dx7_set_voice_limit(full.self,1));
  full.render(a); assert(full.stats().active==1 && full.stats().retired==15);
  auto before=full.stats(); full.on(100); assert(full.stats().stolen==before.stolen+1);
  full.on(100);assert(full.stats().stolen==before.stolen+1); // retrigger, not a steal
  full.render(a); assert(full.stats().active==1);
  // A partly delivered internal block is immutable; limit applies only when
  // that block is exhausted and the next 64-frame block starts.
  Engine partial(rate);
  for(unsigned key=48;key<60;++key)partial.on(key);
  partial.render(a,1);assert(fm1_dx7_set_voice_limit(partial.self,4));
  partial.render(a,63);assert(partial.stats().active==12);
  partial.render(a,1);assert(partial.stats().active==4 && partial.stats().retired==8);
  std::puts("PASS default12 exact PCM, released retirement, fade boundary, restore, stealing, pending frames and invalid requests");
}
