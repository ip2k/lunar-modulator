"""Queue post-callback ownership and timeout proof, host only."""
from pathlib import Path
import shutil
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('sanitize',[False,True])
def test_post_callback_ownership(tmp_path,sanitize):
    dest=ROOT/'firmware/devkit'
    src=tmp_path/'proof.cc'
    src.write_text(r'''
#include "renderer_queue.h"
#include <cassert>
#include <atomic>
#include <thread>
#include <chrono>
struct Context { unsigned rendered=0, posted=0; };
static thread_local bool worker=false;
static std::atomic<bool> entered(false), release_post(false);
static unsigned ticks;
static void render(void *p,float *out,uint32_t n) {
 assert(worker); Context &c=*(Context*)p; ++c.rendered; out[0]=n;
}
static void post(void *p,unsigned s) {
 assert(worker && s==1); Context &c=*(Context*)p;
 assert(c.rendered==c.posted+1); ++c.posted;
}
static void blocked_post(void *p,unsigned s) {
 entered=true; while(!release_post.load()) std::this_thread::yield(); post(p,s);
}
static uint32_t now(void*) {
 std::this_thread::yield();
 return (uint32_t)std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static uint32_t blocked_clock(void*) { std::this_thread::yield(); return entered.load()?ticks++:0; }
int main() {
 typedef LunarRendererQueue Q; Context c; float output[128]={}; fm1_engine_t e={};
 e.kind=FM1_KIND_SOUND;e.render=render; Q::Op op={};op.kind=Q::Render;op.frames=64;op.output=output;
 Q q(now,0,2000000);std::atomic<bool> stop(false);
 std::thread t([&]{worker=true;while(!stop.load()){q.WorkerStep();std::this_thread::yield();}});
 for(unsigned batch=0;batch<2000;++batch){
  assert(q.Begin() && q.Push(1,&e,&c,op) && q.SetPost(1,post,&c));
  assert(q.Dispatch() && c.rendered==batch+1 && c.posted==batch+1);
 }
 // Registration clears at Begin: a following unregistered batch cannot replay post.
 assert(q.Begin() && q.Push(1,&e,&c,op) && q.Dispatch());
 assert(c.rendered==2001 && c.posted==2000);
 stop=true;t.join();assert(q.completed()==2001 && q.WorkerStep()==0);
 // Invalid and duplicate registrations permanently refuse before publication.
 for(unsigned bad=0;bad<5;++bad){Q invalid(now,0,2000000);Context z;
  if(bad!=0) assert(invalid.Begin());
  if(bad==0) assert(!invalid.SetPost(1,post,&z));
  if(bad==1) assert(!invalid.SetPost(4,post,&z));
  if(bad==2) assert(!invalid.SetPost(1,0,&z));
  if(bad==3) assert(!invalid.SetPost(1,post,0));
  if(bad==4){assert(invalid.SetPost(1,post,&z));assert(!invalid.SetPost(1,post,&z));}
  assert(invalid.disabled() && !invalid.Dispatch() && invalid.WorkerStep()==0 && !z.posted);
 }
 Context late; Q blocked(blocked_clock,0,10);
 assert(blocked.Begin() && blocked.Push(1,&e,&late,op) && blocked.SetPost(1,blocked_post,&late));
 std::thread delayed([&]{worker=true;while(!blocked.WorkerStep())std::this_thread::yield();});
 assert(!blocked.Dispatch() && blocked.error()==Q::Deadline && entered.load());
 assert(late.rendered==1 && !late.posted && !blocked.Begin());
 release_post=true;delayed.join();
 assert(late.posted==1 && blocked.WorkerStep()==0 && blocked.completed()==0);
 assert(!blocked.Begin() && !blocked.SetPost(1,post,&late) && !blocked.Dispatch());
}
''')
    exe=tmp_path/'proof'
    flags=['-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitize else []
    subprocess.run(['c++','-std=c++11','-O2','-pthread','-DLUNAR_QUEUE_HOST_TEST','-DLUNAR_QUEUE_POST',*flags,'-I'+str(dest),'-I'+str(ROOT/'engines/include'),str(src),str(dest/'renderer_queue.cc'),'-o',str(exe)],check=True,capture_output=True)
    subprocess.run([str(exe)],check=True,capture_output=True,timeout=30)
