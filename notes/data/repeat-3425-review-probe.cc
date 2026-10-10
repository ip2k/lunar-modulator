#include "../../engines/src/fx_repeat.cc"
#include <cstdio>
#include <vector>
using namespace fm1::repeat;
void run(Instance &s,unsigned n,unsigned ev=0,bool running=false){std::vector<float> a(2*n,.5f);fm1_fx_ext_t ext={};ext.bpm=120;ext.running=running;ext.events=ev;s.Render(&ext,a.data(),n);printf("ev=%u n=%u wet=%g held=%u armed=%u last=%g\n",ev,n,s.wet,s.held,s.armed,a.back());}
int main(){fm1_host_t h={FM1_ENGINE_API_VERSION,44118,64};
for(unsigned ev: {unsigned(FM1_FX_EV_START),unsigned(FM1_FX_EV_STOP),unsigned(FM1_FX_EV_RESET)}) {Instance s={};s.Init(&h);run(s,s.ramp_frames,ev,ev==FM1_FX_EV_START);}
Instance off={};off.Init(&h);off.SetParam(P_HOLD,0);run(off,off.ramp_frames);
Instance quick={};quick.Init(&h);run(quick,1,0,true);quick.SetParam(P_HOLD,1);run(quick,kCapacity,0,true);run(quick,quick.ramp_frames,FM1_FX_EV_BEAT,true);unsigned capture_head=quick.ring_write;quick.SetParam(P_HOLD,0);run(quick,5,0,true);quick.SetParam(P_HOLD,1);run(quick,quick.ramp_frames-5,0,true);printf("rehold_before held=%u armed=%u write=%u capture_head=%u\n",quick.held,quick.armed,quick.ring_write,capture_head);run(quick,1,FM1_FX_EV_BEAT,true);printf("rehold_after held=%u write=%u capture_head=%u\n",quick.held,quick.ring_write,capture_head);
Instance a={},b={};a.Init(&h);b.Init(&h);run(a,1);run(b,1);a.SetParam(P_MIX,1);b.SetParam(P_MIX,1);run(a,5);run(b,5);b.SetParam(P_MIX,1);run(a,a.ramp_frames-5);run(b,b.ramp_frames-5);printf("repeat_mix a=%g left=%u b=%g left=%u\n",a.mix,a.mix_left,b.mix,b.mix_left);
}
