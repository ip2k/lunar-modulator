"""Bounded ownership protocol before any whole-engine target scheduling."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("worker_drums", [False, True])
@pytest.mark.parametrize("sanitize", [False, True])
def test_renderer_queue_order_and_permanent_refusal(tmp_path, sanitize, worker_drums):
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
static Voice *owned;
static thread_local bool in_worker;
static void check_owner(void *p) {
 for(unsigned sound=0;owned && sound<4;++sound) if(p==&owned[sound]) {
#ifdef LUNAR_QUEUE_WORKER_DRUMS
  assert(in_worker==(sound==1 || sound==2));
#else
  assert(in_worker==(sound==1));
#endif
 }
}
static void on(void *p, uint8_t k, uint8_t v) { Voice &s=*(Voice*)p; s.key=k; s.value=v; ++s.calls; }
static void off(void *p, uint8_t k) { Voice &s=*(Voice*)p; assert(s.key==k); s.key=0; ++s.calls; }
static void set(void *p, uint16_t i, float v) { assert(i==3); Voice &s=*(Voice*)p; s.value=v; ++s.calls; }
static void bend(void *p, float v) { Voice &s=*(Voice*)p; s.bend=v; ++s.calls; }
static void note(void *p, uint8_t k, uint16_t i, float v) { Voice &s=*(Voice*)p; assert(k==s.key && i==FM1_PARAM_NOTE_PITCH); s.offset=v; ++s.calls; }
static void render(void *p, float *out, uint32_t n) {
 check_owner(p);
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
 owned=actual;
 Q q(now,0,2000000);
 std::atomic<bool> stop(false);
 std::thread worker([&] { in_worker=true; while (!stop.load()) { q.WorkerStep(); std::this_thread::yield(); } });
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
 stop=true; worker.join(); owned=0; assert(q.completed()==2000);
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
    if worker_drums:
        flags += ["-DLUNAR_QUEUE_WORKER_DRUMS=1"]
    subprocess.run([cxx, "-std=c++11", "-O2", "-pthread", "-ffp-contract=off",
                    "-DLUNAR_QUEUE_HOST_TEST=1", *flags,
                    "-I" + str(ROOT / "firmware/devkit"),
                    "-I" + str(ROOT / "engines/include"), str(source),
                    str(ROOT / "firmware/devkit/renderer_queue.cc"), "-o", str(exe)], check=True)
    env = dict(os.environ, ASAN_OPTIONS="halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1")
    subprocess.run([str(exe)], check=True, env=env, timeout=30)


def test_renderer_queue_c_bridge_permanent_storage(tmp_path):
    cxx = os.environ.get("FM1_SIM_CXX", "c++")
    if not shutil.which(cxx):
        pytest.skip("native C++ toolchain unavailable")
    source = tmp_path / "bridge.cc"
    source.write_text(r'''
#include "renderer_queue_bridge.h"
#include <assert.h>
#include <atomic>
#include <thread>
static unsigned calls;
static void render(void *, float *out, uint32_t n) { ++calls; out[n-1]=42; }
static uint32_t clock_now(void) { std::this_thread::yield(); return 0; }
int main(int argc, char **) {
 assert(lunar_renderer_queue_worker_step()==-1);
 assert(!lunar_renderer_queue_begin() && lunar_renderer_queue_error()!=0);
 assert(!lunar_renderer_queue_init(0,100));
 assert(!lunar_renderer_queue_init(clock_now,0));
 assert(!lunar_renderer_queue_init(clock_now,0x80000000u));
 assert(lunar_renderer_queue_init(clock_now,100));
 assert(!lunar_renderer_queue_init(clock_now,100));
 fm1_engine_t e={}; e.kind=FM1_KIND_SOUND; e.render=render;
 int instance=0; float out[128]={};
 assert(lunar_renderer_queue_begin());
 if(argc>1) {
  /* No integer truncation may turn a malformed operation into a valid one. */
  unsigned field=argc-2;
  assert(!lunar_renderer_queue_push(1,&e,&instance,
   field==0 ? 256 : LUNAR_QUEUE_RENDER,out,64,
   field==1 ? 65536 : 0, field==2 ? 256 : 0, field==3 ? 256 : 0,0));
  assert(!lunar_renderer_queue_dispatch() && !lunar_renderer_queue_begin());
  assert(lunar_renderer_queue_worker_step()==0 && calls==0);
  return 0;
 }
 assert(lunar_renderer_queue_push(1,&e,&instance,LUNAR_QUEUE_RENDER,out,64,0,0,0,0));
 std::atomic<bool> stop(false);
 std::thread worker([&]{while(!stop.load()) lunar_renderer_queue_worker_step();});
 assert(lunar_renderer_queue_dispatch()); stop=true; worker.join();
 assert(calls==1 && out[63]==42 && lunar_renderer_queue_completed()==1);
 assert(lunar_renderer_queue_peak(1)==1 && lunar_renderer_queue_peak(4)==0);
 assert(!lunar_renderer_queue_error());
 assert(!lunar_renderer_queue_dispatch());
 assert(!lunar_renderer_queue_begin());
 assert(!lunar_renderer_queue_init(clock_now,100));
 assert(calls==1 && lunar_renderer_queue_completed()==1);
}
''')
    exe = tmp_path / "bridge"
    subprocess.run([cxx, "-std=c++11", "-O2", "-pthread", "-DLUNAR_QUEUE_HOST_TEST=1",
                    "-I" + str(ROOT / "firmware/devkit"), "-I" + str(ROOT / "engines/include"),
                    str(source), str(ROOT / "firmware/devkit/renderer_queue.cc"),
                    str(ROOT / "firmware/devkit/renderer_queue_bridge.cc"), "-o", str(exe)], check=True)
    for arguments in ([], ["kind"], ["index", "x"], ["key", "x", "x"], ["velocity", "x", "x", "x"]):
        subprocess.run([str(exe), *arguments], check=True, timeout=10)


def test_queue_sdk_lifecycle_with_controlled_scheduler(tmp_path):
    """Exercise actual backend control flow; not concurrency/target ABI proof."""
    cc = os.environ.get("FM1_SIM_CC", "cc")
    if not shutil.which(cc):
        pytest.skip("native C toolchain unavailable")
    (tmp_path / "system").mkdir()
    (tmp_path / "os").mkdir()
    (tmp_path / "asm").mkdir()
    (tmp_path / "app_config.h").write_text("")
    (tmp_path / "system/includes.h").write_text('#include <stdio.h>\n#include <stddef.h>\ntypedef struct { unsigned words[16]; } StaticTask_t;\n')
    (tmp_path / "os/os_api.h").write_text('''
unsigned timer_get_ms(void);
void os_time_dly(unsigned);
unsigned uxTaskGetStackHighWaterMark(void *);
int os_task_create_static(void (*)(void *), void *, unsigned, unsigned, unsigned, const char *, unsigned char *);
''')
    (tmp_path / "asm/includes.h").write_text("unsigned current_cpu_id(void);\n")
    source = tmp_path / "sdk.c"
    # Suppress only pi32 assembly in this single-threaded scheduler model.
    # All SDK state, loop bounds and error/exit branches are the actual source.
    source.write_text(r'''
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define __asm__
#define volatile(...)
#include "renderer_queue_sdk.c"
#undef volatile
#undef __asm__
static unsigned ticks, core, mode, completions, initialized, created, steps;
static void (*entry)(void *);
static jmp_buf parked;
unsigned timer_get_ms(void) { return ticks++; }
unsigned current_cpu_id(void) { return core; }
unsigned uxTaskGetStackHighWaterMark(void *p) { assert(!p); return 1024; }
void os_time_dly(unsigned n) {
 if (n==100) longjmp(parked,1); /* Terminal parking loop, no stack reclaimed. */
 assert(n==1);
 if (mode==2) ticks+=1000; /* Startup timeout, never ready. */
 else if (!state.stop) state.ready=1;
 else {
  core=1;
  if (!setjmp(parked)) entry(0);
  core=0;
 }
}
int os_task_create_static(void (*f)(void *), void *arg, unsigned priority,
 unsigned words, unsigned queue_words, const char *name, unsigned char *memory) {
 ++created; assert(!arg && priority==16 && words==2048 && !queue_words);
 assert(!strcmp(name,"#C1lunar_queue") && memory==worker_memory);
 assert(sizeof worker_memory==sizeof(StaticTask_t)+8192);
 entry=f; return mode==1 ? -7 : 0;
}
int lunar_renderer_queue_init(uint32_t (*clock)(void), uint32_t budget) {
 assert(clock && budget==2400000u); return !initialized++;
}
int lunar_renderer_queue_worker_step(void) {
 ++steps;
 if(mode==4) return -1;
 if(steps==3) ticks=state.started_ms+120000u;
 ++completions; return 1;
}
unsigned lunar_renderer_queue_completed(void) { return completions; }
unsigned lunar_renderer_queue_error(void) { return mode==6; }
unsigned lunar_renderer_queue_peak(unsigned s) { return s+1; }
static uint32_t clock_now(void) { return ticks; }
int main(int argc,char **argv) {
 assert(argc==2); mode=(unsigned)atoi(argv[1]);
 if(mode==7) {
  core=1; assert(!lunar_renderer_queue_sdk_start(clock_now));
  assert(!initialized && !created); return 0;
 }
 int ok=lunar_renderer_queue_sdk_start(clock_now);
 assert(initialized==1 && created==1);
 assert(!lunar_renderer_queue_sdk_start(clock_now) && initialized==1 && created==1);
 if(mode==1) { assert(!ok && !steps); return 0; }
 if(mode==2) { assert(!ok && state.stop && !steps); return 0; }
 assert(ok && state.ready);
 if(mode==3 || mode==4 || mode==5) {
  core=mode==5 ? 0 : 1;
  if(!setjmp(parked)) entry(0);
  core=0;
  assert(state.exited && state.error==(mode==3 ? 2u : mode==4 ? 3u : 1u));
  assert(!lunar_renderer_queue_sdk_finish()); return 0;
 }
 /* A completed batch followed by an acknowledged stop. */
 completions=state.jobs=1;
 lunar_renderer_queue_sdk_parent_block();
 assert(state.parent_blocks==1 && !state.parent_wrong_core);
 assert(lunar_renderer_queue_sdk_finish()==(mode!=6));
 assert(state.stop && state.exited && state.stack_unused==1024 && !steps);
}
''')
    exe = tmp_path / "sdk"
    subprocess.run([cc, "-std=c99", "-O2", "-I" + str(tmp_path),
                    "-I" + str(ROOT / "firmware/devkit"), "-I" + str(ROOT / "engines/include"),
                    str(source), "-o", str(exe)], check=True)
    for mode in range(8):
        subprocess.run([str(exe), str(mode)], check=True, timeout=10)


@pytest.mark.parametrize("worker_drums", [False, True])
def test_queue_region_timers_partition_and_refuse_stale_samples(tmp_path, worker_drums):
    """Cooperative clock drives an ACK deterministically, including timer wrap."""
    cxx = os.environ.get("FM1_SIM_CXX", "c++")
    if not shutil.which(cxx):
        pytest.skip("native C++ toolchain unavailable")
    source = tmp_path / "profile.cc"
    source.write_text(r'''
#include "renderer_queue.h"
#include <cassert>
#include <cstring>
struct Clock { unsigned calls; uint32_t base; LunarRendererQueue *queue; };
static uint32_t now(void *p) {
 Clock &c=*(Clock*)p;
 unsigned call=++c.calls;
 if(call==4) assert(c.queue->WorkerStep()==1);
 return c.base+10u*call;
}
static void render(void *p,float *out,uint32_t) { ++*(unsigned*)p; *out=42; }
static void run(uint32_t base, unsigned budget, bool success) {
 Clock c={0,base,0};
 LunarRendererQueue q(now,&c,budget); c.queue=&q;
 uint32_t regions[6]; memset(regions,0x55,sizeof regions);
 uint32_t untouched[6]; memcpy(untouched,regions,sizeof regions);
 assert(!q.ProfileRead(base,base+80,regions));
 assert(!memcmp(regions,untouched,sizeof regions));
 assert(q.WorkerStep()==0 && c.calls==0); // No timer overhead in idle loop.
 assert(q.Begin());
 unsigned calls=0; float out=0;
 fm1_engine_t e={}; e.kind=FM1_KIND_SOUND; e.render=render;
 LunarRendererQueue::Op op={}; op.kind=LunarRendererQueue::Render;
 op.output=&out; op.frames=1;
 assert(q.Push(1,&e,&calls,op));
 assert(q.Dispatch()==success && calls==1 && out==42);
 if(success) {
  assert(q.ProfileRead(base,base+80,regions));
  const uint32_t expected[]={10,10,10,40,10,10};
  assert(!memcmp(regions,expected,sizeof expected));
  unsigned total=0; for(unsigned i=0;i<5;++i) total+=regions[i];
  assert(total==80 && total+regions[5]!=80); // Worker overlaps caller/wait.
  assert(!q.ProfileRead(base,base+80,regions)); // No duplicate sample.
  assert(q.Begin() && !q.ProfileRead(base,base+80,regions));
 } else {
  assert(q.error()==LunarRendererQueue::Deadline);
  assert(!q.ProfileRead(base,base+80,regions));
  assert(!memcmp(regions,untouched,sizeof regions)); // ACK cannot clear refusal.
  assert(!q.Begin());
 }
}
int main() { run(0,100,true); run(0xfffffff0u,100,true); run(0,10,false); }
''')
    exe = tmp_path / "profile"
    subprocess.run([cxx, "-std=c++11", "-O2", "-DLUNAR_QUEUE_HOST_TEST=1",
                    "-DLUNAR_QUEUE_PROFILE=1",
                    *(["-DLUNAR_QUEUE_WORKER_DRUMS=1"] if worker_drums else []),
                    "-I" + str(ROOT / "firmware/devkit"), "-I" + str(ROOT / "engines/include"),
                    str(source), str(ROOT / "firmware/devkit/renderer_queue.cc"),
                    "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)


@pytest.mark.parametrize("detail", [False, True])
def test_queue_timing_aggregates_outer_partition_and_stops_on_missing_sample(tmp_path, detail):
    cc = os.environ.get("FM1_SIM_CC", "cc")
    if not shutil.which(cc):
        pytest.skip("native C toolchain unavailable")
    source = tmp_path / "timing.c"
    source.write_text(r'''
#include "renderer_timing.h"
#include <assert.h>
#include <string.h>
static unsigned ticks, emitted, samples, fault;
static uint32_t now(void) { return ticks+=10; }
static void yield(void) {}
int lunar_devkit_renderer_init(void) { return 1; }
void lunar_devkit_renderer_render(int16_t *out) { (void)out; ticks+=80; }
void lunar_devkit_renderer_status(struct lunar_renderer_status *out) { memset(out,0,sizeof *out); }
unsigned lunar_renderer_queue_error(void) { return 0; }
int lunar_renderer_queue_profile_read(uint32_t start,uint32_t end,uint32_t out[6]) {
 assert(end-start==90); ++samples;
 if(fault==1) return 0;
 for(unsigned i=0;i<5;++i) out[i]=18;
 out[5]=42; return 1;
}
#ifdef LUNAR_QUEUE_DETAIL
int lunar_renderer_queue_detail_read(uint32_t out[10]) {
 if(fault==2) return 0;
 for(unsigned i=0;i<10;++i) out[i]=fault==3?10:i+1;
 return 1;
}
#endif
static void emit(const struct lunar_renderer_timing *r) {
 assert(r->test_case==emitted++ && r->blocks==5513 && r->ticks==90ull*5513);
 assert(r->min_ticks==90 && r->max_ticks==90 && !r->over_budget);
#ifdef LUNAR_QUEUE_DETAIL
 for(unsigned i=0;i<10;++i) {
  assert(r->queue_detail_ticks[i]==(uint64_t)(i+1)*5513);
  assert(r->queue_detail_max[i]==i+1 && r->queue_detail_worst[i]==i+1);
 }
#endif
 for(unsigned i=0;i<6;++i) {
  unsigned duration=i<5?18:42;
  assert(r->queue_ticks[i]==(uint64_t)duration*5513);
  assert(r->queue_max[i]==duration && r->queue_worst[i]==duration);
 }
}
int main(void) {
 assert(lunar_devkit_renderer_timing(now,yield,emit));
 assert(emitted==4 && samples==22052);
 fault=1; assert(!lunar_devkit_renderer_timing(now,yield,emit));
 assert(emitted==4 && samples==22053); // No false case completion.
#ifdef LUNAR_QUEUE_DETAIL
 fault=2; assert(!lunar_devkit_renderer_timing(now,yield,emit));
 assert(emitted==4 && samples==22054);
 fault=3; assert(!lunar_devkit_renderer_timing(now,yield,emit));
 assert(emitted==4 && samples==22055); // Overlapping/corrupt detail sum refused.
#endif
}
''')
    exe = tmp_path / "timing"
    subprocess.run([cc, "-std=c99", "-O2", "-DLUNAR_DEVKIT_ENGINE_QUEUE=1",
                    "-DLUNAR_QUEUE_PROFILE=1", *(["-DLUNAR_QUEUE_DETAIL=1"] if detail else []),
                    "-I" + str(ROOT / "firmware/devkit"),
                    "-I" + str(ROOT / "engines/include"),
                    str(source), str(ROOT / "firmware/devkit/renderer_timing.c"),
                    "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)


def test_queue_detail_clock_wrap_repeats_and_malformed_intervals(tmp_path):
    cxx = os.environ.get("FM1_SIM_CXX", "c++")
    if not shutil.which(cxx):
        pytest.skip("native C++ toolchain unavailable")
    source = tmp_path / "detail.cc"
    source.write_text(r'''
#include "renderer_queue_bridge.h"
#include <cassert>
static uint32_t tick;
static uint32_t now() { return tick; }
static void mark(unsigned r) {
 lunar_renderer_queue_detail_mark(r,1); tick+=7;
 lunar_renderer_queue_detail_mark(r,0);
}
int main() {
 uint32_t out[LUNAR_QUEUE_DETAILS];
 assert(lunar_renderer_queue_init(now,100));
 for(unsigned pass=0;pass<2;++pass) {
  tick=pass?0xfffffffcu:0;
  lunar_renderer_queue_detail_reset();
  for(unsigned r=0;r<LUNAR_QUEUE_DETAILS;++r) mark(r);
  mark(2); // All four sound intervals accumulate in the same category.
  assert(lunar_renderer_queue_detail_read(out));
  for(unsigned r=0;r<LUNAR_QUEUE_DETAILS;++r) assert(out[r]==(r==2?14u:7u));
  assert(!lunar_renderer_queue_detail_read(out));
 }
 for(unsigned fault=0;fault<7;++fault) {
  lunar_renderer_queue_detail_reset();
  for(unsigned r=0;r<LUNAR_QUEUE_DETAILS-1;++r) mark(r);
  if(fault==0) {} // Missing region.
  if(fault==1) lunar_renderer_queue_detail_mark(9,0); // Unmatched exit.
  if(fault==2) { lunar_renderer_queue_detail_mark(9,1); lunar_renderer_queue_detail_mark(8,1); }
  if(fault==3) lunar_renderer_queue_detail_mark(LUNAR_QUEUE_DETAILS,1);
  if(fault==4) lunar_renderer_queue_detail_mark(9,2);
  if(fault==5) { lunar_renderer_queue_detail_mark(9,1); tick+=0x80000000u; lunar_renderer_queue_detail_mark(9,0); }
  if(fault==6) { mark(9); assert(!lunar_renderer_queue_detail_read(0)); }
  assert(!lunar_renderer_queue_detail_read(out));
 }
}
''')
    exe = tmp_path / "detail"
    subprocess.run([cxx, "-std=c++11", "-O2", "-DLUNAR_QUEUE_HOST_TEST=1",
                    "-DLUNAR_QUEUE_PROFILE=1", "-DLUNAR_QUEUE_DETAIL=1",
                    "-I" + str(ROOT / "firmware/devkit"), "-I" + str(ROOT / "engines/include"),
                    str(source), str(ROOT / "firmware/devkit/renderer_queue.cc"),
                    str(ROOT / "firmware/devkit/renderer_queue_bridge.cc"),
                    "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)
