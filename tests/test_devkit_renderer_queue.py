"""Bounded ownership protocol before any whole-engine target scheduling."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("sanitize", [False, True])
def test_renderer_queue_order_and_permanent_refusal(tmp_path, sanitize):
    cxx = os.environ.get("FM1_SIM_CXX", "c++")
    if not shutil.which(cxx):
        pytest.skip("native C++ toolchain unavailable")
    source = tmp_path / "queue.cc"
    source.write_text(r'''
#include "renderer_queue.h"
#include <assert.h>
#include <atomic>
#include <chrono>
#include <cstring>
#include <thread>
struct Voice { unsigned key, calls; float value, bend, offset; };
static void on(void *p, uint8_t k, uint8_t v) { Voice &s=*(Voice*)p; s.key=k; s.value=v; ++s.calls; }
static void off(void *p, uint8_t k) { Voice &s=*(Voice*)p; assert(s.key==k); s.key=0; ++s.calls; }
static void set(void *p, uint16_t i, float v) { assert(i==3); Voice &s=*(Voice*)p; s.value=v; ++s.calls; }
static void bend(void *p, float v) { Voice &s=*(Voice*)p; s.bend=v; ++s.calls; }
static void note(void *p, uint8_t k, uint16_t i, float v) { Voice &s=*(Voice*)p; assert(k==s.key && i==FM1_PARAM_NOTE_PITCH); s.offset=v; ++s.calls; }
static void render(void *p, float *out, uint32_t n) {
 Voice &s=*(Voice*)p;
 for (unsigned f=0;f<n;++f) { out[2*f]=(s.key+s.bend)+s.offset; out[2*f+1]=s.value; }
 ++s.calls;
}
static fm1_engine_t engine() {
 fm1_engine_t e={}; e.kind=FM1_KIND_SOUND; e.note_on=on; e.note_off=off;
 e.set_param=set; e.pitch_bend=bend; e.set_param_note=note; e.render=render;
 return e;
}
static uint32_t now(void *) {
 std::this_thread::yield();
 return (uint32_t)std::chrono::duration_cast<std::chrono::microseconds>(
     std::chrono::steady_clock::now().time_since_epoch()).count();
}
static uint32_t fake_now(void *p) { return (*(unsigned*)p)++; }
static uint32_t stopped_clock(void *) { return 0; }
static std::atomic<bool> entered(false), release_worker(false);
static unsigned blocked_ticks;
static void blocked_render(void *p, float *out, uint32_t frames) {
 entered=true;
 while(!release_worker.load()) std::this_thread::yield();
 render(p,out,frames);
}
static uint32_t blocked_clock(void *) {
 std::this_thread::yield();
 return entered.load() ? blocked_ticks++ : 0;
}
static LunarRendererQueue::Op op(LunarRendererQueue::Kind k) {
 LunarRendererQueue::Op x={}; x.kind=k; return x;
}
int main() {
 typedef LunarRendererQueue Q;
 fm1_engine_t e=engine();
 Voice actual[4]={}, reference[4]={}; float outputs[4][128], expected[4][128];
 Q q(now,0,2000000);
 std::atomic<bool> stop(false);
 std::thread worker([&] { while (!stop.load()) { q.WorkerStep(); std::this_thread::yield(); } });
 for (unsigned cycle=0;cycle<2000;++cycle) {
  assert(q.Begin());
  /* Deliberately interleave streams: only each engine's order is required. */
  for (unsigned s=0;s<4;++s) {
   Q::Op x=op(Q::NoteOn); x.key=(cycle+s)%100+1; x.velocity=80+s;
   assert(q.Push(s,&e,&actual[s],x)); on(&reference[s],x.key,x.velocity);
  }
  for (unsigned s=0;s<4;++s) {
   Q::Op x=op(Q::SetParam); x.index=3; x.value=(float)(cycle%7)*.25f;
   assert(q.Push(s,&e,&actual[s],x)); set(&reference[s],3,x.value);
   x=op(Q::Bend); x.value=-.5f; assert(q.Push(s,&e,&actual[s],x)); bend(&reference[s],-.5f);
   x=op(Q::SetNote); x.key=reference[s].key; x.index=FM1_PARAM_NOTE_PITCH; x.value=.125f;
   assert(q.Push(s,&e,&actual[s],x)); note(&reference[s],x.key,x.index,x.value);
   x=op(Q::Render); x.output=outputs[s]; x.frames=64;
   assert(q.Push(s,&e,&actual[s],x)); render(&reference[s],expected[s],64);
   x=op(Q::NoteOff); x.key=reference[s].key;
   assert(q.Push(s,&e,&actual[s],x)); off(&reference[s],x.key);
  }
  assert(q.Dispatch());
  assert(!memcmp(outputs,expected,sizeof outputs));
  assert(!memcmp(actual,reference,sizeof actual));
 }
 stop=true; worker.join(); assert(q.completed()==2000);
 for(unsigned s=0;s<4;++s) assert(q.peak(s)==6);
 assert(!q.Dispatch() && q.error()==Q::State); /* Never replay a consumed batch. */

 unsigned ticks=0; Voice late={}; float late_output[128]={};
 Q timed(fake_now,&ticks,10); assert(timed.Begin());
 Q::Op x=op(Q::Render); x.output=late_output; x.frames=64;
 assert(timed.Push(1,&e,&late,x));
 assert(!timed.Dispatch() && timed.error()==Q::Deadline && !late.calls);
 assert(!timed.Begin() && !timed.Push(1,&e,&late,x));
 assert(timed.WorkerStep()==1 && late.calls==1); /* The late worker retains its original storage. */
 assert(timed.WorkerStep()==0 && !timed.Begin() && !timed.Dispatch());
 assert(late.calls==1 && timed.error()==Q::Deadline);

 /* Timeout while the worker is already executing, then a late write. */
 fm1_engine_t blocked_engine=e; blocked_engine.render=blocked_render;
 Voice blocked_voice={}; float blocked_output[128]={};
 Q blocked(blocked_clock,0,10); assert(blocked.Begin());
 x=op(Q::Render); x.output=blocked_output; x.frames=64;
 assert(blocked.Push(1,&blocked_engine,&blocked_voice,x));
 std::thread delayed([&] { while(!blocked.WorkerStep()) std::this_thread::yield(); });
 assert(!blocked.Dispatch() && blocked.error()==Q::Deadline && entered.load());
 assert(!blocked_voice.calls && !blocked.Begin() && !blocked.Push(1,&e,&late,x));
 release_worker=true; delayed.join();
 assert(blocked_voice.calls==1 && blocked.WorkerStep()==0 && !blocked.Begin());
 assert(blocked.error()==Q::Deadline);

 unsigned wrapping_ticks=0xfffffffaU;
 Q wrapping(fake_now,&wrapping_ticks,10); assert(wrapping.Begin());
 assert(!wrapping.Dispatch() && wrapping.error()==Q::Deadline && wrapping_ticks<20);
 assert(wrapping.WorkerStep()==1);

 Q stalled(stopped_clock,0,10); assert(stalled.Begin());
 assert(!stalled.Dispatch() && stalled.error()==Q::Polls); assert(stalled.WorkerStep()==1);
 Q full(now,0,2000000); assert(full.Begin());
 x=op(Q::SetParam); x.index=3; x.value=1;
 unsigned before=late.calls;
 for(unsigned i=0;i<Q::kCapacity;++i) assert(full.Push(0,&e,&late,x));
 assert(!full.Push(0,&e,&late,x) && full.error()==Q::Capacity);
 assert(!full.Dispatch() && !full.Begin() && full.WorkerStep()==0 && late.calls==before);
 Q invalid(now,0,2000000); assert(invalid.Begin());
 x=op(Q::Render); x.output=late_output; x.frames=65;
 assert(!invalid.Push(1,&e,&late,x) && invalid.error()==Q::Command);
 Q rebound(now,0,2000000); assert(rebound.Begin());
 x=op(Q::SetParam); x.index=3;
 assert(rebound.Push(0,&e,&late,x));
 assert(!rebound.Push(0,&e,&actual[0],x) && rebound.error()==Q::Command);
 Q state(now,0,2000000); assert(!state.Push(0,&e,&late,x) && state.error()==Q::State);
 Q twice(now,0,2000000); assert(twice.Begin() && !twice.Begin() && twice.error()==Q::State);
 Q config(0,0,1), zero(now,0,0), wrap(now,0,0x80000000u);
 assert(config.error()==Q::Configuration && !config.Begin());
 assert(zero.error()==Q::Configuration && wrap.error()==Q::Configuration);
}
''')
    exe = tmp_path / "queue"
    flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if sanitize else []
    subprocess.run([cxx, "-std=c++11", "-O2", "-pthread", "-ffp-contract=off",
                    "-DLUNAR_QUEUE_HOST_TEST=1", *flags,
                    "-I" + str(ROOT / "firmware/devkit"),
                    "-I" + str(ROOT / "engines/include"), str(source),
                    str(ROOT / "firmware/devkit/renderer_queue.cc"), "-o", str(exe)], check=True)
    env = dict(os.environ, ASAN_OPTIONS="halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1")
    subprocess.run([str(exe)], check=True, env=env, timeout=30)
