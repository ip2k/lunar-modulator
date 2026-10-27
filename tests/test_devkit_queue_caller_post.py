"""Caller/worker callback ownership proof, not target or race proof."""
from pathlib import Path
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]
@pytest.mark.parametrize('sanitized',[False,True])
def test_caller_post_ownership(tmp_path,sanitized):
    shadow=tmp_path/'source';(shadow/'firmware/devkit').mkdir(parents=True)
    for name in ['renderer_queue.h','renderer_queue.cc']:
        (shadow/'firmware/devkit'/name).write_text((ROOT/'firmware/devkit'/name).read_text())
    q=shadow/'firmware/devkit/renderer_queue.cc'
    src=tmp_path/'proof.cc';src.write_text(r'''
#include "renderer_queue.h"
#include <cassert>
#include <atomic>
#include <thread>
#include <chrono>
static thread_local bool worker=false;
struct State { unsigned id, rendered, posted; };
struct Context { State sounds[4]; std::atomic<unsigned> callers; Context():sounds{},callers(0){} };
static std::atomic<bool> blocked(false),release(false),expire(false);
static unsigned ticks;
static void render(void *p,float*,uint32_t) {
 State &s=*(State*)p;assert(worker==(s.id==1));++s.rendered;
 if(worker && blocked.load()) while(!release.load()) std::this_thread::yield();
}
static void post(void *p,unsigned id) {
 Context &c=*(Context*)p;State &s=c.sounds[id];assert(worker==(id==1));
 assert(s.rendered==s.posted+1);++s.posted;
 if(id!=1)c.callers.fetch_add(1);
 if(blocked.load() && id==0)expire=true;
}
static uint32_t clock(void*) {std::this_thread::yield();return (uint32_t)std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
static uint32_t fault_clock(void*) {std::this_thread::yield();return expire.load()?++ticks:0;}
static void record(LunarRendererQueue &q,Context &c,fm1_engine_t &e,float *out) {
 assert(q.Begin());for(unsigned s=0;s<4;++s){c.sounds[s].id=s;LunarRendererQueue::Op op={};op.kind=LunarRendererQueue::Render;op.output=out+128*s;op.frames=64;assert(q.Push(s,&e,&c.sounds[s],op));}assert(q.SetPost(1,post,&c));
}
int main(){typedef LunarRendererQueue Q;fm1_engine_t e={};e.kind=FM1_KIND_SOUND;e.render=render;float out[512]={};
 Context c;Q q(clock,0,2000000);std::atomic<bool> stop(false);
 std::thread t([&]{worker=true;while(!stop.load()){
  // The first worker ACK cannot occur until CPU0 ran all three callbacks.
  if(c.callers.load()<3){std::this_thread::yield();continue;}
  q.WorkerStep();std::this_thread::yield();}});
 for(unsigned i=0;i<2000;++i){record(q,c,e,out);assert(q.Dispatch());for(unsigned s=0;s<4;++s)assert(c.sounds[s].rendered==i+1 && c.sounds[s].posted==i+1);}
 stop=true;t.join();assert(q.completed()==2000 && q.WorkerStep()==0);
 Context late;Q timeout(fault_clock,0,10);blocked=true;record(timeout,late,e,out);
 std::thread delayed([&]{worker=true;while(!timeout.WorkerStep())std::this_thread::yield();});
 assert(!timeout.Dispatch() && timeout.error()==Q::Deadline && timeout.completed()==0);
 for(unsigned s=0;s<4;++s)if(s!=1)assert(late.sounds[s].posted==1);
 assert(!late.sounds[1].posted && !timeout.Begin());release=true;delayed.join();
 assert(late.sounds[1].posted==1 && timeout.WorkerStep()==0 && !timeout.Begin() && !timeout.Dispatch());
}
''')
    flags=['-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitized else []
    exe=tmp_path/'proof'
    subprocess.run(['c++','-std=c++11','-O2','-pthread','-DLUNAR_QUEUE_HOST_TEST','-DLUNAR_QUEUE_POST','-DLUNAR_QUEUE_CALLER_POST',*flags,'-I'+str(shadow/'firmware/devkit'),'-I'+str(ROOT/'engines/include'),str(src),str(q),'-o',str(exe)],check=True,capture_output=True)
    subprocess.run([str(exe)],check=True,capture_output=True,timeout=30)
